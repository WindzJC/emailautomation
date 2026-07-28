#!/usr/bin/env python3
"""Fail-closed packaging and restore for a WSL-to-Mac runtime cutover.

The tool never starts the dashboard or a sender. Secrets are intentionally
excluded and must be transferred separately over an encrypted channel.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


DEFAULT_TARGET_ROOT = Path("/Users/windellereboquio/AstraHandoff/emailautomation")
ACTIVE_JOB_STATES = {
    "queued", "running", "checking", "verifying", "dispatching",
    "auto_triage_running",
}
CURRENT_JOB_MAX_AGE_SECONDS = 15 * 60
PROCESS_BLOCKERS = (
    "send_shard.py --profile",
    "uvicorn live_dashboard:app",
    "cloudflared",
)
SECRET_NAMES = {".env", ".env.local", "KEYS"}
EXCLUDED_PARTS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", "node_modules",
    "backups", "audits", "tmp", "temp",
}
EXCLUDED_SUFFIXES = (
    ".lock", ".tmp", ".bak", ".tgz", ".tar", ".tar.gz", ".zip",
)
EPHEMERAL_STATE_NAMES = {
    "dashboard_auto_start_state.json",
    "dashboard_timer_state.json",
    "runtime_heartbeat.json",
    "runtime_lifecycle.json",
}
REQUIRED_DATA_FILES = (
    "data/shards/recipients_*.csv",
    "data/logs/*_log.csv",
    "data/logs/*_domain_log.csv",
    "data/logs/campaign_run_history.jsonl",
    "data/logs/sendgrid_events.jsonl",
    "data/logs/sendgridlogs/**/*",
    "data/state/active_campaign_snapshot.json",
    "data/state/auto_stop_events.jsonl",
    "data/state/dashboard_run_settings.json",
    "data/state/dispatch_run_history.json",
    "data/state/lead_ledger.sqlite3",
    "data/state/leads_dashboard_state.json",
    "data/state/private_bounce_monitor.json",
    "data/state/private_bounce_state.json",
    "data/state/provider_pacing_state.json",
    "data/state/resume_audit_latest.json",
    "data/state/safer_recontact_source_summary.json",
    "data/state/send_idempotency.sqlite3",
    "data/state/sendgrid_daily_counters.json",
    "data/state/sendgrid_other_observability.csv",
    "data/state/sendgrid_shard_normalize_report.json",
    "data/state/sendgrid_suppressions.csv",
    "data/state/sendgrid_webhook_dedupe.sqlite3",
    "data/state/sendgrid_webhook_receiver.sqlite3",
    "data/state/shard_report_latest.json",
    "data/state/suppressed.csv",
    "data/state/unsubscribed.csv",
    "data/state/warm_private_jc_confirmation.json",
    "data/message_previews/**/*",
    "data/reference/**/*",
)
REQUIRED_IMPORTANT_FILES = (
    "_important/leads*.csv",
    "_important/latest_*",
    "_important/*triage*.csv",
    "_important/*verify*.csv",
)


class MigrationError(RuntimeError):
    """A safe, operator-readable migration refusal."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise MigrationError(f"git {' '.join(args)} failed")
    return result.stdout.strip()


def process_blockers() -> list[str]:
    result = subprocess.run(
        ["ps", "-eo", "pid=,args="], check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise MigrationError("Could not inspect running processes")
    own_pid = os.getpid()
    blocked = []
    for line in result.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(.*)", line)
        if not match or int(match.group(1)) == own_pid:
            continue
        command = match.group(2)
        if "mac_runtime_migration.py" in command:
            continue
        for marker in PROCESS_BLOCKERS:
            if marker in command:
                blocked.append(f"{match.group(1)} {marker}")
                break
    return blocked


def job_file_status(repo: Path) -> tuple[list[str], list[str]]:
    roots = (
        repo / "_important/check_runs/jobs",
        repo / "_important/dispatch_jobs",
        repo / "_important/verify_jobs",
    )
    active = []
    stale_or_unreadable = []
    now = time.time()
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*.json"):
            relative = path.relative_to(repo).as_posix()
            try:
                age = max(0.0, now - path.stat().st_mtime)
            except OSError:
                stale_or_unreadable.append(relative)
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                if age <= CURRENT_JOB_MAX_AGE_SECONDS:
                    raise MigrationError(f"Unreadable recent job state: {relative}")
                stale_or_unreadable.append(relative)
                continue
            values = {
                str(payload.get("status", "")).strip().lower(),
                str(payload.get("stage", "")).strip().lower(),
            }
            if values & ACTIVE_JOB_STATES:
                if age <= CURRENT_JOB_MAX_AGE_SECONDS:
                    active.append(relative)
                else:
                    stale_or_unreadable.append(relative)
    return active, stale_or_unreadable


def active_job_files(repo: Path) -> list[str]:
    return job_file_status(repo)[0]


def held_lock_files(repo: Path) -> list[str]:
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - source is WSL
        raise MigrationError("POSIX lock inspection is unavailable") from exc
    held = []
    for root in (repo / "data", repo / "_important"):
        if not root.exists():
            continue
        for path in root.rglob("*.lock"):
            try:
                with path.open("rb") as handle:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        held.append(path.relative_to(repo).as_posix())
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                held.append(path.relative_to(repo).as_posix())
    return held


def assert_frozen(repo: Path, *, require_clean_git: bool = True) -> str:
    blockers = process_blockers()
    if blockers:
        raise MigrationError(
            "Runtime is not frozen; blocking processes: " + ", ".join(blockers)
        )
    jobs = active_job_files(repo)
    if jobs:
        raise MigrationError(
            "Runtime is not frozen; active job files: " + ", ".join(jobs)
        )
    locks = held_lock_files(repo)
    if locks:
        raise MigrationError("Runtime is not frozen; held locks: " + ", ".join(locks))
    head = git(repo, "rev-parse", "HEAD")
    if require_clean_git and git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise MigrationError("Tracked worktree is dirty; commit or restore code first")
    try:
        upstream = git(repo, "rev-parse", "origin/main")
    except MigrationError:
        upstream = ""
    if upstream and upstream != head:
        raise MigrationError("HEAD does not match origin/main")
    return head


def excluded(relative: Path) -> bool:
    parts = set(relative.parts)
    name = relative.name
    if parts & EXCLUDED_PARTS or name in SECRET_NAMES:
        return True
    if name in EPHEMERAL_STATE_NAMES:
        return True
    if name.endswith(EXCLUDED_SUFFIXES) or name.endswith(("-wal", "-shm")):
        return True
    if ".pre_" in name or name.startswith("."):
        return True
    return False


def candidate_files(repo: Path) -> list[tuple[Path, str]]:
    found: dict[Path, str] = {}
    for pattern in REQUIRED_DATA_FILES:
        for path in repo.glob(pattern):
            if path.is_file():
                found[path] = "REQUIRED_RUNTIME"
    for pattern in REQUIRED_IMPORTANT_FILES:
        for path in repo.glob(pattern):
            if path.is_file():
                found[path] = "REQUIRED_LEAD_OPS"
    for path in referenced_important_files(repo, found):
        found[path] = "REQUIRED_LEAD_OPS"
    return sorted(
        (
            (path, classification)
            for path, classification in found.items()
            if not excluded(path.relative_to(repo))
        ),
        key=lambda item: item[0].as_posix(),
    )


def _string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def referenced_important_files(
    repo: Path, already_found: dict[Path, str]
) -> set[Path]:
    """Resolve current state references, bounded to this repo's _important tree."""
    important_root = (repo / "_important").resolve()
    pending = [
        path
        for path in already_found
        if path.suffix == ".json" and path.is_file()
    ]
    pending.extend(sorted((repo / "data/state").glob("*.json")))
    inspected: set[Path] = set()
    referenced: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in inspected:
            continue
        inspected.add(source)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for value in _string_values(payload):
            if "_important/" not in value.replace("\\", "/"):
                continue
            raw = Path(value)
            target = raw if raw.is_absolute() else repo / raw
            try:
                resolved = target.resolve()
                resolved.relative_to(important_root)
            except (OSError, ValueError):
                continue
            if not resolved.exists():
                continue
            if resolved.is_file():
                referenced.add(resolved)
                if resolved.suffix == ".json":
                    pending.append(resolved)
            parts = resolved.relative_to(important_root).parts
            if len(parts) >= 2 and parts[0] == "runs":
                run_root = important_root / parts[0] / parts[1]
                run_patterns = (
                    "leads*.csv",
                    "*triage*.csv",
                    "dispatch_previews/*.json",
                    "dispatch_confirmed/*.json",
                    "confirmed*.json",
                )
                for pattern in run_patterns:
                    for child in run_root.glob(pattern):
                        if child.is_file() and not excluded(child.relative_to(repo)):
                            referenced.add(child)
                            if child.suffix == ".json":
                                pending.append(child)
    return referenced


def portable_json_bytes(path: Path, source_root: Path, target_root: Path) -> bytes:
    raw = path.read_text(encoding="utf-8")
    return raw.replace(str(source_root), str(target_root)).encode("utf-8")


def sqlite_snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_db:
        with sqlite3.connect(destination) as target_db:
            source_db.backup(target_db)
            result = target_db.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise MigrationError(f"SQLite integrity check failed: {source.name}")


def queue_counts(repo: Path) -> dict[str, int]:
    counts = {}
    for path in sorted((repo / "data/shards").glob("recipients_*.csv")):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                counts[path.name] = sum(1 for _ in csv.DictReader(handle))
        except (OSError, csv.Error):
            counts[path.name] = -1
    return counts


def profile_queue_map(repo: Path) -> dict[str, str]:
    """Read static profile-to-queue names without importing runtime modules."""
    tree = ast.parse((repo / "send_shard.py").read_text(encoding="utf-8"))
    profiles = None
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "PROFILES"
        ):
            profiles = ast.literal_eval(node.value)
            break
    if not isinstance(profiles, dict):
        raise MigrationError("Could not read static send_shard PROFILES")
    return {
        str(name): str(config["csv"])
        for name, config in profiles.items()
        if isinstance(config, dict) and config.get("csv")
    }


def profile_inventory(repo: Path) -> dict:
    mapping = profile_queue_map(repo)
    counts = queue_counts(repo)
    return {
        "profiles": mapping,
        "active_intended_profiles": sorted(
            profile for profile, queue in mapping.items() if counts.get(queue, 0) > 0
        ),
    }


def build_manifest(
    repo: Path, staging: Path, target_root: Path, expected_commit: str
) -> dict:
    entries = []
    for source, classification in candidate_files(repo):
        relative = source.relative_to(repo)
        destination = staging / "runtime" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_hash = sha256_file(source)
        if source.suffix == ".sqlite3":
            sqlite_snapshot(source, destination)
            method = "sqlite_backup"
        elif source.suffix == ".json":
            destination.write_bytes(portable_json_bytes(source, repo, target_root))
            method = "copy_with_root_remap"
        else:
            shutil.copy2(source, destination)
            method = "byte_copy"
        entries.append(
            {
                "path": relative.as_posix(),
                "classification": classification,
                "size": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "source_sha256": source_hash,
                "method": method,
            }
        )
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(repo),
        "target_root": str(target_root),
        "expected_commit": expected_commit,
        "files": entries,
        "queue_row_counts": queue_counts(repo),
        "private_configuration": {
            "classification": "REQUIRED_PRIVATE_TRANSFER",
            "included": False,
            "files": [".env"],
            "transfer": "encrypted direct SSH/SCP only; chmod 600 on target",
        },
        "excluded": {
            "code": "CODE_GIT_ONLY",
            "venv_caches_locks": "REGENERATED_MAC",
            "old_bundles_backups_audits": "OPTIONAL_ARCHIVE_NOT_INCLUDED",
            "secrets": "MUST_NOT_TRANSFER_IN_RUNTIME_BUNDLE",
        },
    }


def bundle(repo: Path, output_dir: Path, target_root: Path) -> Path:
    expected_commit = assert_frozen(repo)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"emailautomation_runtime_{stamp}.tgz"
    if destination.exists():
        raise MigrationError(f"Refusing to overwrite {destination}")
    with tempfile.TemporaryDirectory(prefix="mac-runtime-", dir=output_dir) as temp:
        staging = Path(temp)
        manifest = build_manifest(repo, staging, target_root, expected_commit)
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with tarfile.open(destination, "x:gz") as archive:
            archive.add(manifest_path, arcname="manifest.json", recursive=False)
            archive.add(staging / "runtime", arcname="runtime")
    destination.chmod(0o600)
    return destination


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise MigrationError(f"Unsafe archive member: {member.name}")
        if member.name != "manifest.json" and not member.name.startswith("runtime/"):
            raise MigrationError(f"Unexpected archive member: {member.name}")
    return members


def read_manifest(bundle_path: Path) -> dict:
    with tarfile.open(bundle_path, "r:gz") as archive:
        safe_members(archive)
        try:
            member = archive.getmember("manifest.json")
        except KeyError as exc:
            raise MigrationError("Bundle manifest is missing") from exc
        handle = archive.extractfile(member)
        if handle is None:
            raise MigrationError("Bundle manifest is unreadable")
        return json.load(handle)


def verify_bundle(bundle_path: Path) -> dict:
    manifest = read_manifest(bundle_path)
    expected = {entry["path"]: entry for entry in manifest.get("files", [])}
    with tarfile.open(bundle_path, "r:gz") as archive:
        safe_members(archive)
        for relative, entry in expected.items():
            name = f"runtime/{relative}"
            try:
                member = archive.getmember(name)
            except KeyError as exc:
                raise MigrationError(f"Missing bundle file: {relative}") from exc
            handle = archive.extractfile(member)
            if handle is None:
                raise MigrationError(f"Unreadable bundle file: {relative}")
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
            if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise MigrationError(f"Checksum mismatch: {relative}")
    return manifest


def restore(repo: Path, bundle_path: Path) -> None:
    blockers = process_blockers()
    if blockers:
        raise MigrationError("Target runtime is active: " + ", ".join(blockers))
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise MigrationError("Target tracked worktree is dirty")
    manifest = verify_bundle(bundle_path)
    if git(repo, "rev-parse", "HEAD") != manifest["expected_commit"]:
        raise MigrationError("Target commit does not match bundle")
    entries = manifest["files"]
    conflicts = [entry["path"] for entry in entries if (repo / entry["path"]).exists()]
    if conflicts:
        raise MigrationError(
            "Refusing to overwrite existing runtime files: " + ", ".join(conflicts[:5])
        )
    with tempfile.TemporaryDirectory(prefix="mac-restore-", dir=repo.parent) as temp:
        staging = Path(temp)
        with tarfile.open(bundle_path, "r:gz") as archive:
            archive.extractall(staging, members=safe_members(archive))
        moved = []
        try:
            for entry in entries:
                relative = Path(entry["path"])
                source = staging / "runtime" / relative
                destination = repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
                moved.append(destination)
        except Exception:
            for destination in reversed(moved):
                destination.unlink(missing_ok=True)
            raise


def inventory(repo: Path) -> dict:
    active_jobs, stale_jobs = job_file_status(repo)
    profiles = profile_inventory(repo)
    return {
        "repo": str(repo),
        "head": git(repo, "rev-parse", "HEAD"),
        "origin_main": git(repo, "rev-parse", "origin/main"),
        "process_blockers": process_blockers(),
        "active_job_files": active_jobs,
        "stale_or_unreadable_job_files": stale_jobs,
        "held_locks": held_lock_files(repo),
        "candidate_file_count": len(candidate_files(repo)),
        "queue_row_counts": queue_counts(repo),
        **profiles,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory")
    subparsers.add_parser("profiles")
    package = subparsers.add_parser("bundle")
    package.add_argument("--output-dir", type=Path, default=Path("_migration"))
    package.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    verify = subparsers.add_parser("verify")
    verify.add_argument("bundle", type=Path)
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("bundle", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "inventory":
            print(json.dumps(inventory(repo), indent=2, sort_keys=True))
        elif args.command == "profiles":
            print(json.dumps(profile_inventory(repo), indent=2, sort_keys=True))
        elif args.command == "bundle":
            output = bundle(repo, args.output_dir.resolve(), args.target_root)
            print(f"Created frozen runtime bundle: {output}")
        elif args.command == "verify":
            manifest = verify_bundle(args.bundle.resolve())
            print(
                f"Verified {len(manifest['files'])} files for "
                f"commit {manifest['expected_commit']}"
            )
        elif args.command == "restore":
            restore(repo, args.bundle.resolve())
            print("Runtime restore completed; senders remain disabled")
    except MigrationError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
