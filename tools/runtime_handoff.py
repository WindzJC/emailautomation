#!/usr/bin/env python3
"""Production-safe bidirectional runtime handoff.

Archives contain runtime data only. They are mode 0600 and intended for SCP,
which encrypts transport. Secrets and source code are never included.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_authority import (  # noqa: E402
    ACTIVE_STATUS,
    AuthorityError,
    authority_path,
    assert_send_authorized,
    current_machine,
    generation_floor_path,
    load_authority,
    load_generation_floor,
    utc_now,
    write_authority,
    write_generation_floor,
)
from sendgrid_hygiene import (  # noqa: E402
    SuppressionSchemaError,
    load_suppression_email_tokens,
)


SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
BUNDLE_AUTHORITY_NAME = "authority.json"
RUNTIME_ROOT = "runtime"
LOCAL_STATE_DIR = ".runtime_handoff"
USED_BUNDLES_NAME = "used_bundles.json"
LAST_IMPORT_NAME = "last_import.json"
BACKUP_DIR_NAME = "backups"
PROCESS_MARKERS = {
    "sender": ("send_shard.py",),
    "dashboard": ("live_dashboard.py", "uvicorn live_dashboard:app", "streamlit_monitor.py"),
    "tunnel": ("cloudflared", "run_tunnel_tmux.sh"),
    "dispatch": ("dispatch",),
    "check": ("check_pending.py", "check_1hr.py", "check_24h.py"),
    "triage": ("triage",),
    "workflow": (
        "important_leads_workflow.py",
        "leads_workflow.py",
        "precheck_leads.py",
    ),
    "handoff": ("runtime_handoff.py", "mac_runtime_migration.py"),
}
ACTIVE_JOB_STATES = {"queued", "running", "checking", "verifying", "dispatching", "triaging"}
JOB_ROOTS = (
    "_important/check_runs/jobs",
    "_important/dispatch_jobs",
    "_important/verify_jobs",
    "data/state/dispatch_jobs",
)
SECRET_NAMES = {".env", ".env.local", "KEYS"}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "cache",
    "caches",
    "backups",
    "tmp",
    "temp",
    LOCAL_STATE_DIR,
}
ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".zip", ".age", ".gpg")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
QUEUE_SAFETY_MANIFEST = Path("data/state/active_campaign_snapshot.json")
QUEUE_SAFETY_FALLBACKS = {
    "checked": Path("_important/leads.csv"),
    "intended": Path("_important/leads_triaged_keep.csv"),
    "triaged_keep": Path("_important/leads_triaged_keep.csv"),
    "triaged_reject": Path("_important/leads_triaged_reject.csv"),
}
EMERGENCY_EXPECTED_BUNDLE_SHA256 = (
    "e23c636baecdd74c3233078256acf18ceedd7bac97302df731edbea398625375"
)
EMERGENCY_EXPECTED_SOURCE_COMMIT = "006d10eec45c2156595fe1203e07de33ce64fdbb"
EMERGENCY_EXPECTED_PRIVATE_JC_ROWS = 2574
EMERGENCY_EXPECTED_PRIVATE_JC_FINGERPRINT = (
    "644d003718e09d3be1d57044d24ba514d2de58d6e8e4e2dd615384d1c6515c90"
)
EMERGENCY_TAKEOVER_ROOT = Path("data/state/emergency_takeovers")
PITCH_VALIDATION_MODES = {
    "pitch1": "consignment",
    "pitch2": "consignment",
    "pitch3": "consignment",
    "pitch4": "consignment",
    "pitch5": "consignment",
    "pitch_jc": "astra_visual",
}


class HandoffError(RuntimeError):
    """A fail-closed operator-readable refusal."""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise HandoffError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_runtime(repo: Path) -> None:
    for root_name in ("data", "_important"):
        root = repo / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or excluded(repo, path):
                continue
            try:
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise HandoffError(f"Could not fsync runtime file {path}: {exc}") from exc
        _fsync_directory(root)


def excluded(repo: Path, path: Path) -> bool:
    relative = path.relative_to(repo)
    if relative == Path("data/state/runtime_authority.json"):
        return True
    if set(relative.parts) & (EXCLUDED_PARTS | SECRET_NAMES):
        return True
    if relative.name in SECRET_NAMES or relative.name.startswith(".env"):
        return True
    if relative.name.endswith(ARCHIVE_SUFFIXES) or relative.name.endswith((".lock", ".tmp")):
        return True
    return False


def runtime_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in ("data", "_important"):
        root = repo / root_name
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and not excluded(repo, path)
        )
    return sorted(files, key=lambda path: path.relative_to(repo).as_posix())


def process_blockers() -> list[str]:
    result = subprocess.run(
        ["ps", "-eo", "pid=,ppid=,args="],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise HandoffError("Could not inspect running processes")
    own_pid = os.getpid()
    processes: dict[int, tuple[int, str]] = {}
    for line in result.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)", line)
        if match:
            processes[int(match.group(1))] = (int(match.group(2)), match.group(3))
    ignored_pids = {own_pid}
    ancestor = processes.get(own_pid, (os.getppid(), ""))[0]
    while ancestor > 0 and ancestor not in ignored_pids:
        ignored_pids.add(ancestor)
        ancestor = processes.get(ancestor, (0, ""))[0]
    blockers: list[str] = []
    for pid, (_ppid, command) in processes.items():
        if pid in ignored_pids:
            continue
        for category, markers in PROCESS_MARKERS.items():
            if any(marker in command for marker in markers):
                blockers.append(f"{pid} {category}: {command}")
                break
    return blockers


def active_job_files(repo: Path) -> list[str]:
    active: list[str] = []
    for relative_root in JOB_ROOTS:
        root = repo / relative_root
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise HandoffError(f"Unreadable job state: {path.relative_to(repo)}") from exc
            statuses = {
                str(payload.get("status", "")).strip().lower(),
                str(payload.get("stage", "")).strip().lower(),
            }
            if statuses & ACTIVE_JOB_STATES:
                active.append(path.relative_to(repo).as_posix())
    return sorted(active)


def assert_processes_stopped(repo: Path) -> None:
    blockers = process_blockers()
    if blockers:
        raise HandoffError("Runtime processes are still running: " + "; ".join(blockers))
    jobs = active_job_files(repo)
    if jobs:
        raise HandoffError("Runtime job state is active: " + ", ".join(jobs))


def sqlite_snapshot(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    uri = f"file:{source.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as source_db:
            with sqlite3.connect(destination) as target_db:
                source_db.backup(target_db)
                result = target_db.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise HandoffError(f"SQLite integrity failure: {source}") from exc
    if result != [("ok",)]:
        raise HandoffError(f"SQLite integrity failure: {source}: {result[:3]}")
    return {
        "method": "sqlite_backup_includes_wal",
        "source_wal_present": source.with_name(source.name + "-wal").exists(),
        "source_shm_present": source.with_name(source.name + "-shm").exists(),
    }


def _csv_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def queue_counts(root: Path) -> dict[str, int]:
    base = root / "data/shards"
    return {
        path.relative_to(root).as_posix(): _csv_count(path)
        for path in sorted(base.glob("recipients_*.csv"))
        if path.is_file()
    }


def log_counts(root: Path) -> dict[str, int]:
    base = root / "data/logs"
    counts: dict[str, int] = {}
    if not base.exists():
        return counts
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".jsonl"}:
            continue
        with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
            line_count = sum(1 for line in handle if line.strip())
        if path.suffix.lower() == ".csv" and line_count:
            line_count -= 1
        counts[path.relative_to(root).as_posix()] = max(0, line_count)
    return counts


def build_staging(repo: Path, staging: Path) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    entries: list[dict[str, Any]] = []
    for source in runtime_files(repo):
        relative = source.relative_to(repo)
        destination = staging / RUNTIME_ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        metadata: dict[str, Any] = {"method": "byte_copy"}
        if source.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
            metadata = sqlite_snapshot(source, destination)
        elif source.name.endswith(("-wal", "-shm")):
            # Sidecars are represented by the consistent SQLite backup and are
            # not independently restored against a different database image.
            continue
        else:
            shutil.copy2(source, destination)
        entries.append(
            {
                "path": relative.as_posix(),
                "size": destination.stat().st_size,
                "sha256": sha256_file(destination),
                **metadata,
            }
        )
    return entries, queue_counts(staging / RUNTIME_ROOT), log_counts(staging / RUNTIME_ROOT)


def manifest_hash(entries: list[dict[str, Any]]) -> str:
    return canonical_hash(entries)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def export_runtime(
    repo: Path,
    output_dir: Path,
    target_machine: str,
    *,
    machine: str | None = None,
) -> Path:
    identity = machine or current_machine()
    if target_machine == identity:
        raise HandoffError("Source and target machine must differ")
    assert_processes_stopped(repo)
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise HandoffError("Tracked source worktree is dirty")
    try:
        active = assert_send_authorized(repo, machine=identity)
    except AuthorityError as exc:
        raise HandoffError(str(exc)) from exc
    expected_commit = git(repo, "rev-parse", "HEAD")
    bundle_id = str(uuid.uuid4())
    handoff_authority = {
        **active,
        "authorized_machine": identity,
        "bundle_id": bundle_id,
        "source_machine": identity,
        "target_machine": target_machine,
        "created_utc": utc_now(),
        "expected_git_commit": expected_commit,
        "runtime_manifest_hash": "pending",
        "status": "handoff_in_progress",
    }
    # This is deliberately first: every later failure leaves the source unable to send.
    write_authority(repo, handoff_authority)
    fsync_runtime(repo)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"runtime_handoff_{identity}_to_{target_machine}_{stamp}_{bundle_id}.tgz"
    if destination.exists():
        raise HandoffError(f"Refusing to overwrite bundle: {destination}")
    try:
        with tempfile.TemporaryDirectory(prefix="handoff-export-", dir=output_dir) as temp:
            staging = Path(temp)
            entries, queues, logs = build_staging(repo, staging)
            runtime_hash = manifest_hash(entries)
            handoff_authority["runtime_manifest_hash"] = runtime_hash
            write_authority(repo, handoff_authority)
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "bundle_id": bundle_id,
                "source_machine": identity,
                "target_machine": target_machine,
                "created_utc": handoff_authority["created_utc"],
                "expected_git_commit": expected_commit,
                "source_generation": active["generation"],
                "runtime_manifest_hash": runtime_hash,
                "files": entries,
                "queue_row_counts": queues,
                "log_record_counts": logs,
                "transport_security": "0600 archive; transfer only with SSH/SCP",
                "secrets_included": False,
            }
            _write_json(staging / MANIFEST_NAME, manifest)
            _write_json(staging / BUNDLE_AUTHORITY_NAME, handoff_authority)
            with tarfile.open(destination, "x:gz") as archive:
                archive.add(staging / MANIFEST_NAME, arcname=MANIFEST_NAME, recursive=False)
                archive.add(
                    staging / BUNDLE_AUTHORITY_NAME,
                    arcname=BUNDLE_AUTHORITY_NAME,
                    recursive=False,
                )
                runtime = staging / RUNTIME_ROOT
                runtime.mkdir(exist_ok=True)
                archive.add(runtime, arcname=RUNTIME_ROOT)
        destination.chmod(0o600)
        return destination
    except Exception:
        # Never reactivate here. Duplicate authority is less safe than downtime.
        raise


def _safe_relative(value: Any) -> str:
    text = str(value or "")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or path.as_posix() in {"", "."}:
        raise HandoffError(f"Unsafe manifest path: {text!r}")
    return path.as_posix()


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    seen: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        name = path.as_posix().rstrip("/")
        if path.is_absolute() or ".." in path.parts or name in {"", "."}:
            raise HandoffError(f"Unsafe archive member: {member.name}")
        if not (member.isfile() or member.isdir()) or member.issym() or member.islnk():
            raise HandoffError(f"Unsafe archive member type: {member.name}")
        if name in seen:
            raise HandoffError(f"Duplicate archive member: {member.name}")
        seen[name] = member
        allowed = (
            name in {MANIFEST_NAME, BUNDLE_AUTHORITY_NAME, RUNTIME_ROOT}
            or name.startswith(f"{RUNTIME_ROOT}/")
        )
        if not allowed:
            raise HandoffError(f"Unexpected archive member: {member.name}")
    for required in (MANIFEST_NAME, BUNDLE_AUTHORITY_NAME, RUNTIME_ROOT):
        if required not in seen:
            raise HandoffError(f"Archive is missing {required}")
    if not seen[MANIFEST_NAME].isfile() or not seen[BUNDLE_AUTHORITY_NAME].isfile():
        raise HandoffError("Manifest and authority must be regular files")
    if not seen[RUNTIME_ROOT].isdir():
        raise HandoffError("Runtime archive root must be a directory")
    return list(seen.values())


def _read_json_member(archive: tarfile.TarFile, name: str) -> dict[str, Any]:
    member = archive.getmember(name)
    handle = archive.extractfile(member)
    if handle is None:
        raise HandoffError(f"Archive member is unreadable: {name}")
    try:
        payload = json.load(handle)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HandoffError(f"Archive member is invalid JSON: {name}") from exc
    if not isinstance(payload, dict):
        raise HandoffError(f"Archive member must be a JSON object: {name}")
    return payload


def read_bundle_metadata(bundle: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        with tarfile.open(bundle, "r:gz") as archive:
            safe_members(archive)
            return (
                _read_json_member(archive, MANIFEST_NAME),
                _read_json_member(archive, BUNDLE_AUTHORITY_NAME),
            )
    except (OSError, tarfile.TarError) as exc:
        raise HandoffError(f"Unreadable handoff archive: {bundle}") from exc


def _sqlite_integrity(path: Path) -> None:
    try:
        with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as db:
            result = db.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise HandoffError(f"SQLite integrity failure: {path}") from exc
    if result != [("ok",)]:
        raise HandoffError(f"SQLite integrity failure: {path}: {result[:3]}")


def verify_extracted(staging: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise HandoffError("Manifest files must be a list")
    if manifest_hash(entries) != manifest.get("runtime_manifest_hash"):
        raise HandoffError("Runtime manifest hash mismatch")
    expected: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise HandoffError("Invalid manifest file entry")
        relative = _safe_relative(entry.get("path"))
        if relative in expected:
            raise HandoffError(f"Duplicate manifest path: {relative}")
        expected.add(relative)
        path = staging / RUNTIME_ROOT / relative
        if not path.is_file():
            raise HandoffError(f"Missing runtime file: {relative}")
        if path.stat().st_size != entry.get("size") or sha256_file(path) != entry.get("sha256"):
            raise HandoffError(f"Checksum mismatch: {relative}")
        if path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
            _sqlite_integrity(path)
    actual = {
        path.relative_to(staging / RUNTIME_ROOT).as_posix()
        for path in (staging / RUNTIME_ROOT).rglob("*")
        if path.is_file()
    }
    unexpected = actual - expected
    if unexpected:
        raise HandoffError(f"Unexpected runtime file: {sorted(unexpected)[0]}")
    queues = queue_counts(staging / RUNTIME_ROOT)
    logs = log_counts(staging / RUNTIME_ROOT)
    if queues != manifest.get("queue_row_counts"):
        raise HandoffError("Queue row counts do not match manifest")
    if logs != manifest.get("log_record_counts"):
        raise HandoffError("Log record counts do not match manifest")
    return {"files": len(entries), "queue_row_counts": queues, "log_record_counts": logs}


def extract_and_verify(bundle: Path, staging: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest, bundled_authority = read_bundle_metadata(bundle)
    with tarfile.open(bundle, "r:gz") as archive:
        archive.extractall(staging, members=safe_members(archive), filter="data")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HandoffError("Unsupported handoff schema version")
    matching = (
        ("bundle_id", manifest.get("bundle_id"), bundled_authority.get("bundle_id")),
        ("source_machine", manifest.get("source_machine"), bundled_authority.get("source_machine")),
        ("target_machine", manifest.get("target_machine"), bundled_authority.get("target_machine")),
        (
            "expected_git_commit",
            manifest.get("expected_git_commit"),
            bundled_authority.get("expected_git_commit"),
        ),
        (
            "runtime_manifest_hash",
            manifest.get("runtime_manifest_hash"),
            bundled_authority.get("runtime_manifest_hash"),
        ),
    )
    for field, left, right in matching:
        if not left or left != right:
            raise HandoffError(f"Bundle {field} metadata mismatch")
    if bundled_authority.get("status") != "handoff_in_progress":
        raise HandoffError("Bundled source authority is not handoff_in_progress")
    if bundled_authority.get("authorized_machine") != bundled_authority.get("source_machine"):
        raise HandoffError("Bundled authority is not assigned to its source")
    if bundled_authority.get("generation") != manifest.get("source_generation"):
        raise HandoffError("Bundle generation metadata mismatch")
    report = verify_extracted(staging, manifest)
    return manifest, bundled_authority, report


def verify_runtime_bundle(bundle: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="handoff-verify-") as temp:
        manifest, authority, report = extract_and_verify(bundle, Path(temp))
    return {"manifest": manifest, "authority": authority, "verification": report}


def _read_used_bundles(repo: Path) -> set[str]:
    path = repo / LOCAL_STATE_DIR / USED_BUNDLES_NAME
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("bundle_ids", [])
    except (OSError, ValueError, AttributeError) as exc:
        raise HandoffError(f"Used-bundle ledger is unreadable: {path}") from exc
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise HandoffError("Used-bundle ledger is malformed")
    return set(values)


def _write_used_bundles(repo: Path, values: set[str]) -> None:
    _write_json(
        repo / LOCAL_STATE_DIR / USED_BUNDLES_NAME,
        {"bundle_ids": sorted(values), "updated_utc": utc_now()},
    )


def mark_target_disabled(
    repo: Path,
    *,
    status: str,
    metadata: dict[str, Any] | None = None,
    machine: str | None = None,
) -> None:
    try:
        current = load_authority(repo)
        generation = current["generation"]
        bundle_id = current["bundle_id"]
        source = current["source_machine"]
        target = current["target_machine"]
        commit = current["expected_git_commit"]
        runtime_hash = current["runtime_manifest_hash"]
        authorized = current["authorized_machine"]
    except AuthorityError:
        identity = machine or current_machine()
        generation = max(1, load_generation_floor(repo))
        bundle_id = str((metadata or {}).get("bundle_id") or uuid.uuid4())
        source = str((metadata or {}).get("source_machine") or ("mac" if identity == "windows-wsl" else "windows-wsl"))
        target = identity
        commit = str((metadata or {}).get("expected_git_commit") or git(repo, "rev-parse", "HEAD"))
        runtime_hash = str((metadata or {}).get("runtime_manifest_hash") or "import-not-verified")
        authorized = identity
    write_authority(
        repo,
        {
            "authorized_machine": authorized,
            "generation": generation,
            "bundle_id": bundle_id,
            "source_machine": source,
            "target_machine": target,
            "created_utc": utc_now(),
            "expected_git_commit": commit,
            "runtime_manifest_hash": runtime_hash,
            "status": status,
        },
    )


def _profile_runtime_layout() -> dict[str, dict[str, Any]]:
    source_path = Path(__file__).resolve().parents[1] / "send_shard.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    profiles: dict[str, dict[str, Any]] | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "PROFILES"
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, dict):
                profiles = value
            break
    if profiles is None:
        raise HandoffError(f"Could not read sender profile layout: {source_path}")
    return profiles


def _profile_validation_mode(profile: str) -> str:
    config = _profile_runtime_layout().get(profile)
    if not isinstance(config, dict):
        raise HandoffError(f"Unknown emergency profile: {profile}")
    pitch = str(config.get("pitch") or "").strip()
    mode = PITCH_VALIDATION_MODES.get(pitch)
    if not mode:
        raise HandoffError(
            "Emergency preview validation has no known mode mapping: "
            f"profile={profile} pitch={pitch or '<missing>'}"
        )
    return mode


def _emergency_next_action(profile: str) -> str:
    mode = _profile_validation_mode(profile)
    return (
        f"./.venv/bin/python send_shard.py --profile {profile} --preview_messages && "
        "./.venv/bin/python tools/validate_message_preview.py "
        f"--profile {profile} --pitch-mode {mode} --fail-on-errors"
    )


def _normalized_row_value(row: dict[str, str], *names: str) -> str:
    values = {
        str(key or "").strip().lower(): str(value or "").strip()
        for key, value in row.items()
    }
    return next((values.get(name.lower(), "") for name in names if values.get(name.lower())), "")


def _read_queue_state(path: Path, profile: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {str(field or "").strip().lower() for field in (reader.fieldnames or [])}
        if "email" not in fields and "authoremail" not in fields:
            raise HandoffError(
                f"Queue safety failure: profile={profile} queue={path} missing Email header"
            )
        emails: set[str] = set()
        campaigns: dict[str, set[str]] = {}
        duplicate_count = 0
        invalid_count = 0
        row_count = 0
        fallback_campaign = "warm_research" if profile == "private_jc_warm" else "cold"
        for row in reader:
            row_count += 1
            email = _normalized_row_value(row, "Email", "AuthorEmail").lower()
            if not EMAIL_RE.match(email):
                invalid_count += 1
                continue
            if email in emails:
                duplicate_count += 1
            emails.add(email)
            campaign = _normalized_row_value(
                row,
                "campaign_id",
                "dispatch_id",
                "preview_id",
                "campaign_type",
            ).lower() or fallback_campaign
            campaigns.setdefault(email, set()).add(campaign)
    return {
        "row_count": row_count,
        "emails": emails,
        "campaigns": campaigns,
        "duplicate_count": duplicate_count,
        "invalid_count": invalid_count,
        "fingerprint": _email_fingerprint(emails),
    }


def _email_fingerprint(emails: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for email in sorted(set(emails)):
        digest.update(email.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest() if emails else ""


def _resolve_runtime_path(runtime_root: Path, value: object) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        candidate = runtime_root / path
    else:
        parts = path.parts
        marker_index = next(
            (index for index, part in enumerate(parts) if part in {"data", "_important"}),
            None,
        )
        if marker_index is None:
            return None
        candidate = runtime_root.joinpath(*parts[marker_index:])
    try:
        candidate.resolve(strict=False).relative_to(runtime_root.resolve())
    except ValueError:
        return None
    return candidate


def _queue_safety_sources(runtime_root: Path) -> dict[str, Any]:
    manifest_path = runtime_root / QUEUE_SAFETY_MANIFEST
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HandoffError(f"Unreadable queue safety state: {manifest_path}") from exc
        if not isinstance(manifest, dict):
            raise HandoffError(f"Queue safety state is not an object: {manifest_path}")
        intended = _resolve_runtime_path(
            runtime_root,
            manifest.get("intended_source_path") or manifest.get("triaged_keep_path"),
        )
        checked = _resolve_runtime_path(runtime_root, manifest.get("checked_path"))
        keep = _resolve_runtime_path(
            runtime_root,
            manifest.get("triaged_keep_path") or manifest.get("intended_source_path"),
        )
        reject = _resolve_runtime_path(runtime_root, manifest.get("triaged_reject_path"))
        return {
            "origin": "active_campaign_manifest",
            "state_path": manifest_path,
            "state_fingerprint": sha256_file(manifest_path),
            "manifest": manifest,
            "intended": intended,
            "checked": checked,
            "triaged_keep": keep,
            "triaged_reject": reject,
        }
    checked = runtime_root / QUEUE_SAFETY_FALLBACKS["checked"]
    intended = runtime_root / QUEUE_SAFETY_FALLBACKS["intended"]
    if not intended.exists():
        intended = checked
    return {
        "origin": "current_important_fallback",
        "state_path": "",
        "state_fingerprint": "",
        "manifest": {},
        "intended": intended,
        "checked": checked,
        "triaged_keep": intended,
        "triaged_reject": runtime_root / QUEUE_SAFETY_FALLBACKS["triaged_reject"],
    }


def _read_email_set(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            email
            for row in reader
            if (email := _normalized_row_value(row, "Email", "AuthorEmail").lower())
            and EMAIL_RE.match(email)
        }


def _profile_log_paths(
    runtime_root: Path,
    profiles: dict[str, dict[str, Any]],
    profile: str,
) -> list[Path]:
    if profile in {"private_jc", "private_jc_warm"}:
        family_profiles = ("private_jc", "private_jc_warm")
    elif str(profiles.get(profile, {}).get("provider") or "").lower() == "sendgrid":
        family_profiles = tuple(
            name
            for name, config in profiles.items()
            if str(config.get("provider") or "").lower() == "sendgrid"
        )
    else:
        family_profiles = (profile,)
    paths: list[Path] = []
    for name in family_profiles:
        config = profiles.get(name, {})
        keys = ("log", "domain_log") if str(config.get("provider") or "").lower() == "sendgrid" else ("log",)
        for key in keys:
            filename = str(config.get(key) or "").strip()
            path = runtime_root / "data/logs" / filename
            if filename and path not in paths:
                paths.append(path)
    return paths


def _authoritative_sent_emails(paths: Iterable[Path]) -> set[str]:
    sent: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                status = _normalized_row_value(row, "Status", "Event", "Result").upper()
                info = _normalized_row_value(row, "Info", "Details", "Message").lower()
                if status != "SENT" and not (
                    status == "ATTEMPT" and "outcome=sent" in info
                ):
                    continue
                email = _normalized_row_value(row, "Email", "AuthorEmail").lower()
                if email:
                    sent.add(email)
    return sent


def _idempotency_overlap(
    runtime_root: Path,
    profile: str,
    provider: str,
    queue_state: dict[str, Any],
) -> set[str]:
    path = runtime_root / "data/state/send_idempotency.sqlite3"
    if not path.is_file():
        return set()
    try:
        with sqlite3.connect(
            f"file:{path.resolve().as_posix()}?mode=ro",
            uri=True,
        ) as db:
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='send_reservations'"
            ).fetchone()
            if not table:
                return set()
            rows = db.execute(
                "SELECT campaign_id, provider, email, profile FROM send_reservations"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise HandoffError(
            f"Queue safety failure: unreadable idempotency state path={path}: {exc}"
        ) from exc
    queue_emails = queue_state["emails"]
    campaigns = queue_state["campaigns"]
    overlap: set[str] = set()
    for campaign_id, row_provider, email_value, row_profile in rows:
        email = str(email_value or "").strip().lower()
        if email not in queue_emails:
            continue
        same_campaign = (
            str(row_provider or "").strip().lower() == provider
            and str(campaign_id or "").strip().lower() in campaigns.get(email, set())
        )
        cross_lane = (
            profile == "private_jc_warm"
            or (
                profile == "private_jc"
                and str(row_profile or "").strip().lower() == "private_jc_warm"
            )
        )
        if same_campaign or cross_lane:
            overlap.add(email)
    return overlap


def _preview_safety(
    runtime_root: Path,
    profile: str,
    queue_path: Path,
    queue_state: dict[str, Any],
) -> dict[str, Any]:
    preview_dir = runtime_root / "data/message_previews"
    preview_path = preview_dir / f"{profile}_message_preview.csv"
    validated_path = preview_dir / f"{profile}_message_preview_validated.csv"
    failed_path = preview_dir / f"{profile}_message_preview_failed.csv"
    summary_path = preview_dir / f"{profile}_message_preview_summary.txt"
    queue_rows = int(queue_state["row_count"])
    queue_emails = set(queue_state["emails"])
    preview_rows = _csv_count(preview_path) if preview_path.is_file() else 0
    preview_emails = _read_email_set(preview_path)
    validated_rows = _csv_count(validated_path) if validated_path.is_file() else 0
    validated_emails = _read_email_set(validated_path)
    failed_rows = _csv_count(failed_path) if failed_path.is_file() else -1
    summary_counts: dict[str, int] = {}
    if summary_path.is_file():
        text = summary_path.read_text(encoding="utf-8")
        for key in ("total", "passed", "failed"):
            match = re.search(rf"(?im)^{key}\s+rows:\s*(\d+)\s*$", text)
            if match:
                summary_counts[key] = int(match.group(1))
    summary_matches = summary_counts == {
        "total": queue_rows,
        "passed": queue_rows,
        "failed": 0,
    }
    exact_match = (
        preview_path.is_file()
        and validated_path.is_file()
        and failed_path.is_file()
        and summary_path.is_file()
        and preview_rows == queue_rows
        and validated_rows == queue_rows
        and preview_emails == queue_emails
        and validated_emails == queue_emails
        and failed_rows == 0
        and summary_matches
    )
    return {
        "safe": exact_match,
        "profile": profile,
        "queue_path": str(queue_path),
        "queue_row_count": queue_rows,
        "queue_fingerprint": queue_state["fingerprint"],
        "preview_path": str(preview_path),
        "preview_row_count": preview_rows,
        "preview_fingerprint": _email_fingerprint(preview_emails),
        "validated_path": str(validated_path),
        "validated_row_count": validated_rows,
        "validated_fingerprint": _email_fingerprint(validated_emails),
        "failed_path": str(failed_path),
        "failed_row_count": failed_rows,
        "summary_path": str(summary_path),
        "summary_counts": summary_counts,
        "message": (
            ""
            if exact_match
            else (
                f"profile={profile} queue={queue_path} queue_rows={queue_rows} "
                f"queue_fingerprint={queue_state['fingerprint']} preview={preview_path} "
                f"preview_rows={preview_rows} preview_fingerprint={_email_fingerprint(preview_emails)} "
                f"validated={validated_path} validated_rows={validated_rows} "
                f"failed={failed_path} failed_rows={failed_rows} summary={summary_path} "
                "reason=current queue requires a matching generated and validated preview; "
                "regenerate and validate the active profile preview"
            )
        ),
    }


def recompute_queue_safety(runtime_root: Path) -> dict[str, Any]:
    profiles = _profile_runtime_layout()
    queue_dir = runtime_root / "data/shards"
    active: list[tuple[str, dict[str, Any], Path, dict[str, Any]]] = []
    known_queue_names: set[str] = set()
    for profile, config in profiles.items():
        queue_name = str(config.get("csv") or "").strip()
        if not queue_name:
            continue
        known_queue_names.add(queue_name)
        queue_path = queue_dir / queue_name
        if not queue_path.is_file():
            continue
        queue_state = _read_queue_state(queue_path, profile)
        if int(queue_state["row_count"]) > 0:
            active.append((profile, config, queue_path, queue_state))
    unknown_active = []
    for queue_path in sorted(queue_dir.glob("recipients_*.csv")):
        if queue_path.name not in known_queue_names and _csv_count(queue_path) > 0:
            unknown_active.append(queue_path)

    sources = _queue_safety_sources(runtime_root)
    intended_path = sources["intended"]
    checked_path = sources["checked"]
    reject_path = sources["triaged_reject"]
    intended_emails = _read_email_set(intended_path)
    checked_emails = _read_email_set(checked_path)
    reject_emails = _read_email_set(reject_path)
    source_actual_fingerprints = {
        "checked": _email_fingerprint(checked_emails),
        "intended_source": _email_fingerprint(intended_emails),
        "triaged_keep": _email_fingerprint(_read_email_set(sources["triaged_keep"])),
        "triaged_reject": _email_fingerprint(reject_emails),
    }
    source_fingerprint_mismatches: list[str] = []
    manifest_files = sources.get("manifest", {}).get("files")
    if isinstance(manifest_files, dict):
        for key, actual in source_actual_fingerprints.items():
            stored = manifest_files.get(key)
            expected = (
                str(stored.get("email_fingerprint") or "")
                if isinstance(stored, dict)
                else ""
            )
            if expected and expected != actual:
                source_fingerprint_mismatches.append(
                    f"{key}:expected={expected}:actual={actual}"
                )
    suppressed_emails: set[str] = set()
    suppression_records = 0
    suppression_paths = [
        runtime_root / "data/state/suppressed.csv",
        runtime_root / "data/state/unsubscribed.csv",
        runtime_root / "data/state/sendgrid_suppressions.csv",
    ]
    for path in suppression_paths:
        values = _read_email_set(path)
        suppressed_emails.update(values)
        suppression_records += len(values)

    reasons: list[str] = []
    details: list[str] = []
    profile_reports: list[dict[str, Any]] = []
    all_queue_emails: set[str] = set()
    duplicate_across_profiles = 0
    duplicate_rows = 0
    invalid_rows = 0
    suppression_overlap: set[str] = set()
    sent_overlap: set[str] = set()
    idempotency_overlap: set[str] = set()
    preview_failed_rows = 0

    if unknown_active:
        reasons.append("unknown active recipient queues")
        details.extend(
            f"profile=unknown queue={path} overlap_count={_csv_count(path)} "
            "authoritative_source=sender profile configuration reason=queue is not mapped to a sender profile"
            for path in unknown_active
        )

    for profile, config, queue_path, queue_state in active:
        queue_emails = set(queue_state["emails"])
        duplicate_across_profiles += len(all_queue_emails & queue_emails)
        all_queue_emails.update(queue_emails)
        duplicate_rows += int(queue_state["duplicate_count"])
        invalid_rows += int(queue_state["invalid_count"])
        outside_checked = queue_emails - checked_emails if checked_emails else set(queue_emails)
        outside_intended = queue_emails - intended_emails if intended_emails else set(queue_emails)
        reject_overlap = queue_emails & reject_emails
        profile_suppressed = queue_emails & suppressed_emails
        suppression_overlap.update(profile_suppressed)
        provider = str(config.get("provider") or "").strip().lower()
        log_paths = _profile_log_paths(runtime_root, profiles, profile)
        profile_sent = queue_emails & _authoritative_sent_emails(log_paths)
        profile_idempotency = _idempotency_overlap(
            runtime_root,
            profile,
            provider,
            queue_state,
        )
        sent_overlap.update(profile_sent)
        idempotency_overlap.update(profile_idempotency)
        preview = _preview_safety(runtime_root, profile, queue_path, queue_state)
        if not preview["safe"]:
            preview_failed_rows += max(1, abs(int(preview["queue_row_count"]) - int(preview["preview_row_count"])))

        source_state_path = str(sources.get("state_path") or "")
        source_state_fingerprint = str(sources.get("state_fingerprint") or "")
        source_description = (
            f"checked={checked_path} intended={intended_path} reject={reject_path} "
            f"state={source_state_path or 'current_important_fallback'} "
            f"state_fingerprint={source_state_fingerprint or 'none'}"
        )
        source_failures = (
            len(outside_checked)
            + len(outside_intended)
            + len(reject_overlap)
        )
        if source_failures:
            reasons.append("queue source validation failures")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count={source_failures} "
                f"outside_checked={len(outside_checked)} outside_intended={len(outside_intended)} "
                f"reject_overlap={len(reject_overlap)} authoritative_source={source_description} "
                f"queue_fingerprint={queue_state['fingerprint']}"
            )
        if source_fingerprint_mismatches:
            reasons.append("queue source fingerprint mismatch")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count=0 "
                f"authoritative_source={source_description} "
                f"fingerprint_mismatch={','.join(source_fingerprint_mismatches)} "
                "reason=active campaign source fingerprint does not match its state file"
            )
        if int(queue_state["duplicate_count"]):
            reasons.append("duplicate queue recipients")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count={queue_state['duplicate_count']} "
                f"authoritative_source={queue_path} fingerprint={queue_state['fingerprint']} "
                "reason=duplicate recipients in active queue"
            )
        if int(queue_state["invalid_count"]):
            reasons.append("invalid queue recipients")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count={queue_state['invalid_count']} "
                f"authoritative_source={queue_path} fingerprint={queue_state['fingerprint']} "
                "reason=invalid recipient rows"
            )
        if profile_suppressed:
            reasons.append("queue overlaps suppression/unsubscribe state")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count={len(profile_suppressed)} "
                f"authoritative_source={','.join(str(path) for path in suppression_paths)} "
                f"fingerprint={_email_fingerprint(profile_suppressed)}"
            )
        if profile_sent:
            reasons.append("queue overlaps authoritative sent logs")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count={len(profile_sent)} "
                f"authoritative_source={','.join(str(path) for path in log_paths)} "
                f"fingerprint={_email_fingerprint(profile_sent)}"
            )
        if profile_idempotency:
            idempotency_path = runtime_root / "data/state/send_idempotency.sqlite3"
            reasons.append("queue overlaps current idempotency state")
            details.append(
                f"profile={profile} queue={queue_path} overlap_count={len(profile_idempotency)} "
                f"authoritative_source={idempotency_path} "
                f"fingerprint={_email_fingerprint(profile_idempotency)}"
            )
        if not preview["safe"]:
            reasons.append("active profile preview is stale or invalid")
            details.append(str(preview["message"]))

        profile_reports.append(
            {
                "profile": profile,
                "queue_path": str(queue_path),
                "queue_row_count": queue_state["row_count"],
                "queue_unique_emails": len(queue_emails),
                "queue_fingerprint": queue_state["fingerprint"],
                "outside_checked_output_count": len(outside_checked),
                "outside_intended_source_count": len(outside_intended),
                "reject_overlap_count": len(reject_overlap),
                "duplicate_overlap_count": int(queue_state["duplicate_count"]),
                "suppression_overlap_count": len(profile_suppressed),
                "sent_overlap_count": len(profile_sent),
                "idempotency_overlap_count": len(profile_idempotency),
                "authoritative_log_paths": [str(path) for path in log_paths],
                "source_state_path": source_state_path,
                "source_state_fingerprint": source_state_fingerprint,
                "source_fingerprint_mismatches": list(source_fingerprint_mismatches),
                "preview": preview,
            }
        )

    if duplicate_across_profiles:
        reasons.append("duplicate queue recipients")
        details.append(
            f"profile=multiple-active-profiles queue={queue_dir} overlap_count={duplicate_across_profiles} "
            f"authoritative_source={queue_dir} fingerprint={_email_fingerprint(all_queue_emails)} "
            "reason=recipient appears in more than one active queue"
        )
    reasons = list(dict.fromkeys(reasons))
    return {
        "safe": not reasons,
        "unsafe_reasons": reasons,
        "failure_details": details,
        "active_intended_profiles": [profile for profile, _config, _path, _state in active],
        "profiles": profile_reports,
        "queue_unique_emails": len(all_queue_emails),
        "duplicate_queue_rows": duplicate_rows + duplicate_across_profiles,
        "invalid_queue_rows": invalid_rows,
        "suppression_records": suppression_records,
        "queue_suppression_overlap": len(suppression_overlap),
        "queue_sent_overlap": len(sent_overlap),
        "queue_idempotency_overlap": len(idempotency_overlap),
        "preview_failed_rows": preview_failed_rows,
        "source_origin": sources["origin"],
        "source_state_path": str(sources.get("state_path") or ""),
        "source_state_fingerprint": str(sources.get("state_fingerprint") or ""),
        "source_fingerprint_mismatches": source_fingerprint_mismatches,
        "checked_path": str(checked_path or ""),
        "checked_fingerprint": _email_fingerprint(checked_emails),
        "intended_source_path": str(intended_path or ""),
        "intended_source_fingerprint": _email_fingerprint(intended_emails),
        "triaged_reject_path": str(reject_path or ""),
        "triaged_reject_fingerprint": _email_fingerprint(reject_emails),
    }


def _atomic_replace_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _sender_role_blocklist() -> set[str]:
    source_path = Path(__file__).resolve().parents[1] / "send_shard.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "ROLE_LOCALPART_BLOCKLIST"
                for target in node.targets
            )
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, set):
                return {str(item).strip().lower() for item in value if str(item).strip()}
    raise HandoffError(f"Could not read sender role-recipient policy: {source_path}")


def _validated_email_state(
    path: Path,
    label: str,
) -> tuple[set[str], dict[str, Any]]:
    try:
        emails, diagnostics = load_suppression_email_tokens(path)
    except SuppressionSchemaError as exc:
        raise HandoffError(
            f"Emergency validation failed: {label} is structurally invalid: {exc}"
        ) from exc
    malformed = int(diagnostics["malformed_email_rows"])
    if malformed:
        raise HandoffError(
            f"Emergency validation failed: {label} has {malformed} malformed "
            f"email row(s): {path}"
        )
    return emails, diagnostics


def _verify_legacy_emergency_bundle(
    bundle: Path,
    *,
    expected_sha256: str,
    expected_commit: str,
    queue_relative: str,
    expected_rows: int,
    extraction_root: Path,
) -> tuple[dict[str, Any], Path]:
    from tools import mac_runtime_migration as legacy_migration

    if not bundle.is_file():
        raise HandoffError(f"Emergency bundle does not exist: {bundle}")
    actual_bundle_sha256 = sha256_file(bundle)
    if actual_bundle_sha256 != expected_sha256:
        raise HandoffError(
            "Emergency bundle SHA-256 mismatch: "
            f"expected={expected_sha256} actual={actual_bundle_sha256}"
        )
    try:
        manifest = legacy_migration.verify_bundle(bundle)
    except (legacy_migration.MigrationError, OSError, tarfile.TarError, KeyError, TypeError) as exc:
        raise HandoffError(f"Emergency bundle verification failed: {exc}") from exc
    if manifest.get("schema_version") != 1:
        raise HandoffError("Emergency bundle manifest schema_version must be 1")
    if manifest.get("expected_commit") != expected_commit:
        raise HandoffError(
            "Emergency bundle expected commit mismatch: "
            f"expected={expected_commit} actual={manifest.get('expected_commit')!r}"
        )
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise HandoffError("Emergency bundle manifest has no file inventory")
    queue_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("path") == queue_relative
    ]
    if len(queue_entries) != 1:
        raise HandoffError(
            f"Emergency bundle must contain exactly one {queue_relative} entry"
        )
    queue_entry = queue_entries[0]
    if (
        not isinstance(queue_entry.get("size"), int)
        or queue_entry["size"] < 1
        or not re.fullmatch(r"[0-9a-f]{64}", str(queue_entry.get("sha256") or ""))
    ):
        raise HandoffError("Emergency queue manifest entry is malformed")
    manifest_counts = manifest.get("queue_row_counts")
    if isinstance(manifest_counts, dict):
        declared = manifest_counts.get(Path(queue_relative).name)
        if declared is not None and declared != expected_rows:
            raise HandoffError(
                "Emergency bundle queue count mismatch: "
                f"expected={expected_rows} manifest={declared}"
            )
    extraction_root.mkdir(parents=True, exist_ok=True)
    queue_output = extraction_root / Path(queue_relative).name
    try:
        with tarfile.open(bundle, "r:gz") as archive:
            legacy_migration.safe_members(archive)
            member = archive.getmember(
                legacy_migration.runtime_archive_name(queue_relative)
            )
            handle = archive.extractfile(member)
            if handle is None:
                raise HandoffError("Emergency bundle queue is unreadable")
            queue_bytes = handle.read()
    except (KeyError, OSError, tarfile.TarError) as exc:
        raise HandoffError("Could not extract emergency queue from verified bundle") from exc
    _atomic_replace_bytes(queue_output, queue_bytes)
    if (
        queue_output.stat().st_size != queue_entry["size"]
        or sha256_file(queue_output) != queue_entry["sha256"]
    ):
        raise HandoffError("Extracted emergency queue does not match its manifest")
    return manifest, queue_output


def _emergency_idempotency_state(
    repo: Path,
    *,
    profile: str,
    provider: str,
    queue_state: dict[str, Any],
) -> tuple[set[str], set[str]]:
    database = repo / "data/state/send_idempotency.sqlite3"
    if not database.is_file():
        return set(), set()
    current_overlap = _idempotency_overlap(
        repo,
        profile,
        provider,
        queue_state,
    )
    try:
        with sqlite3.connect(
            f"file:{database.resolve().as_posix()}?mode=ro",
            uri=True,
        ) as db:
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='send_reservations'"
            ).fetchone()
            if not table:
                return current_overlap, set()
            columns = {
                str(row[1]).strip().lower()
                for row in db.execute("PRAGMA table_info(send_reservations)")
            }
            if not {"email", "status"} <= columns:
                return current_overlap, set()
            active_rows = db.execute(
                """
                SELECT email FROM send_reservations
                WHERE lower(coalesce(status, '')) IN
                      ('reserved', 'attempting', 'submitted', 'ambiguous')
                """
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise HandoffError(
            f"Emergency validation failed: unreadable idempotency database: {exc}"
        ) from exc
    queue_emails = set(queue_state["emails"])
    active = {
        str(row[0] or "").strip().lower()
        for row in active_rows
        if str(row[0] or "").strip().lower() in queue_emails
    }
    return current_overlap, active


def _emergency_reject_source(repo: Path) -> tuple[Path | None, set[str]]:
    sources = _queue_safety_sources(repo)
    candidates = [
        sources.get("triaged_reject"),
        repo / QUEUE_SAFETY_FALLBACKS["triaged_reject"],
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if not isinstance(candidate, Path) or candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        emails, _diagnostics = _validated_email_state(
            candidate,
            "triaged reject source",
        )
        return candidate, emails
    return None, set()


def _emergency_queue_validation(
    repo: Path,
    *,
    profile: str,
    queue_path: Path,
    queue_state: dict[str, Any],
) -> dict[str, Any]:
    queue_emails = set(queue_state["emails"])
    role_blocklist = _sender_role_blocklist()
    role_violations = {
        email
        for email in queue_emails
        if email.partition("@")[0].strip().lower() in role_blocklist
    }
    suppressed_path = repo / "data/state/suppressed.csv"
    sendgrid_suppression_path = repo / "data/state/sendgrid_suppressions.csv"
    unsubscribed_path = repo / "data/state/unsubscribed.csv"
    suppressed, suppressed_diagnostics = _validated_email_state(
        suppressed_path,
        "global suppression state",
    )
    sendgrid_suppressed, sendgrid_diagnostics = _validated_email_state(
        sendgrid_suppression_path,
        "SendGrid suppression state",
    )
    unsubscribed, unsubscribe_diagnostics = _validated_email_state(
        unsubscribed_path,
        "unsubscribe state",
    )
    suppression_overlap = queue_emails & (suppressed | sendgrid_suppressed)
    unsubscribe_overlap = queue_emails & unsubscribed
    profiles = _profile_runtime_layout()
    config = profiles.get(profile)
    if not isinstance(config, dict):
        raise HandoffError(f"Unknown emergency profile: {profile}")
    provider = str(config.get("provider") or "").strip().lower()
    log_paths = _profile_log_paths(repo, profiles, profile)
    sent_overlap = queue_emails & _authoritative_sent_emails(log_paths)
    current_idempotency, active_reservations = _emergency_idempotency_state(
        repo,
        profile=profile,
        provider=provider,
        queue_state=queue_state,
    )
    reject_path, reject_emails = _emergency_reject_source(repo)
    reject_overlap = queue_emails & reject_emails
    violations = {
        "duplicate_recipient_count": int(queue_state["duplicate_count"]),
        "malformed_recipient_count": int(queue_state["invalid_count"]),
        "role_filter_violation_count": len(role_violations),
        "suppression_overlap_count": len(suppression_overlap),
        "unsubscribe_overlap_count": len(unsubscribe_overlap),
        "authoritative_sent_overlap_count": len(sent_overlap),
        "current_campaign_idempotency_overlap_count": len(current_idempotency),
        "active_reservation_overlap_count": len(active_reservations),
        "reject_overlap_count": len(reject_overlap),
    }
    if any(violations.values()):
        fingerprints = {
            "role_filter_fingerprint": _email_fingerprint(role_violations),
            "suppression_overlap_fingerprint": _email_fingerprint(suppression_overlap),
            "unsubscribe_overlap_fingerprint": _email_fingerprint(unsubscribe_overlap),
            "authoritative_sent_overlap_fingerprint": _email_fingerprint(sent_overlap),
            "idempotency_overlap_fingerprint": _email_fingerprint(current_idempotency),
            "active_reservation_fingerprint": _email_fingerprint(active_reservations),
            "reject_overlap_fingerprint": _email_fingerprint(reject_overlap),
        }
        raise HandoffError(
            "Emergency queue validation refused: "
            + " ".join(f"{key}={value}" for key, value in violations.items())
            + " "
            + " ".join(f"{key}={value or 'none'}" for key, value in fingerprints.items())
        )
    return {
        **violations,
        "queue_path": str(queue_path),
        "queue_row_count": int(queue_state["row_count"]),
        "queue_unique_count": len(queue_emails),
        "queue_fingerprint": queue_state["fingerprint"],
        "suppression_record_count": len(suppressed | sendgrid_suppressed),
        "suppression_sources": {
            "global": suppressed_diagnostics,
            "sendgrid": sendgrid_diagnostics,
            "unsubscribe": unsubscribe_diagnostics,
        },
        "unsubscribe_record_count": len(unsubscribed),
        "authoritative_sent_record_count": len(
            _authoritative_sent_emails(log_paths)
        ),
        "current_campaign_idempotency_record_count": len(current_idempotency),
        "active_reservation_record_count": len(active_reservations),
        "reject_record_count": len(reject_emails),
        "reject_source_path": str(reject_path or ""),
        "authoritative_log_paths": [str(path) for path in log_paths],
    }


def _copy_previous_campaign_metadata(
    repo: Path,
    destination: Path,
    previous_snapshot: dict[str, Any],
) -> dict[str, Any]:
    archived: dict[str, Any] = {}
    sources = _queue_safety_sources(repo)
    source_dir = destination / "sources"
    metadata_dir = destination / "metadata"
    copied_sources: set[Path] = set()
    for key in ("checked", "intended", "triaged_keep", "triaged_reject"):
        source = sources.get(key)
        if not isinstance(source, Path):
            archived[key] = {"status": "missing"}
            continue
        record: dict[str, Any] = {"source_path": str(source)}
        if source.is_file():
            resolved = source.resolve()
            if resolved not in copied_sources:
                copied_sources.add(resolved)
                target = source_dir / f"{key}_{source.name}"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                record.update(
                    {
                        "status": "archived",
                        "archived_path": target.name,
                        "sha256": sha256_file(target),
                    }
                )
            else:
                record["status"] = "duplicate_reference"
        else:
            record["status"] = "missing"
        archived[key] = record
    for name in (
        "leads_dashboard_state.json",
        "dashboard_run_settings.json",
        "dispatch_run_history.json",
    ):
        source = repo / "data/state" / name
        if not source.is_file():
            continue
        target = metadata_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        archived[name] = {
            "status": "archived",
            "source_path": str(source),
            "archived_path": target.name,
            "sha256": sha256_file(target),
        }
    return archived


def _make_takeover_immutable(path: Path) -> None:
    for child in path.rglob("*"):
        os.chmod(child, 0o500 if child.is_dir() else 0o400)
    os.chmod(path, 0o500)


def emergency_takeover(
    repo: Path,
    bundle: Path,
    *,
    machine: str,
    profile: str,
    reason: str,
    expected_bundle_sha256: str = EMERGENCY_EXPECTED_BUNDLE_SHA256,
    expected_source_commit: str = EMERGENCY_EXPECTED_SOURCE_COMMIT,
    expected_rows: int = EMERGENCY_EXPECTED_PRIVATE_JC_ROWS,
    expected_queue_fingerprint: str = EMERGENCY_EXPECTED_PRIVATE_JC_FINGERPRINT,
    write_hook=None,
) -> dict[str, Any]:
    repo = repo.resolve()
    bundle = bundle.resolve()
    if os.environ.get("ASTRA_MACHINE_ID", "").strip().lower() != "mac":
        raise HandoffError("Emergency takeover requires ASTRA_MACHINE_ID=mac")
    if machine != "mac" or platform.system() != "Darwin":
        raise HandoffError("Emergency takeover is restricted to a physical Mac host")
    if profile != "private_jc":
        raise HandoffError("Emergency takeover supports only profile=private_jc")
    if not reason.strip():
        raise HandoffError("Emergency takeover requires a non-empty operator reason")
    assert_processes_stopped(repo)
    if authority_path(repo).exists():
        raise HandoffError("Emergency takeover refused because runtime authority already exists")

    profiles = _profile_runtime_layout()
    config = profiles.get(profile)
    validation_mode = _profile_validation_mode(profile)
    next_required_action = _emergency_next_action(profile)
    queue_name = str(config.get("csv") or "") if isinstance(config, dict) else ""
    if not queue_name:
        raise HandoffError(f"Emergency profile has no configured queue: {profile}")
    queue_relative = f"data/shards/{queue_name}"
    queue_path = repo / queue_relative
    if not queue_path.is_file():
        raise HandoffError(f"Restored emergency queue is missing: {queue_path}")

    state_dir = repo / "data/state"
    state_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="emergency-bundle-", dir=repo.parent) as temp:
        manifest, bundled_queue = _verify_legacy_emergency_bundle(
            bundle,
            expected_sha256=expected_bundle_sha256,
            expected_commit=expected_source_commit,
            queue_relative=queue_relative,
            expected_rows=expected_rows,
            extraction_root=Path(temp),
        )
        bundled_state = _read_queue_state(bundled_queue, profile)
        current_state = _read_queue_state(queue_path, profile)
        for label, state in (
            ("bundled", bundled_state),
            ("current restored", current_state),
        ):
            if (
                int(state["row_count"]) != expected_rows
                or len(state["emails"]) != expected_rows
            ):
                raise HandoffError(
                    f"Emergency {label} queue must contain exactly {expected_rows} "
                    f"unique recipient rows: rows={state['row_count']} "
                    f"unique={len(state['emails'])}"
                )
            if state["duplicate_count"] or state["invalid_count"]:
                raise HandoffError(
                    f"Emergency {label} queue is invalid: "
                    f"duplicates={state['duplicate_count']} malformed={state['invalid_count']}"
                )
            if state["fingerprint"] != expected_queue_fingerprint:
                raise HandoffError(
                    f"Emergency {label} queue fingerprint mismatch: "
                    f"expected={expected_queue_fingerprint} actual={state['fingerprint']}"
                )
        byte_identical = queue_path.read_bytes() == bundled_queue.read_bytes()
        set_identical = current_state["emails"] == bundled_state["emails"]
        if not byte_identical and not set_identical:
            raise HandoffError(
                "Current restored private_jc queue differs from the verified bundle: "
                f"current_fingerprint={current_state['fingerprint']} "
                f"bundled_fingerprint={bundled_state['fingerprint']}"
            )
        validation = _emergency_queue_validation(
            repo,
            profile=profile,
            queue_path=queue_path,
            queue_state=current_state,
        )

        snapshot_path = repo / QUEUE_SAFETY_MANIFEST
        previous_snapshot_bytes = (
            snapshot_path.read_bytes() if snapshot_path.is_file() else None
        )
        previous_snapshot_fingerprint = (
            hashlib.sha256(previous_snapshot_bytes).hexdigest()
            if previous_snapshot_bytes is not None
            else ""
        )
        try:
            previous_snapshot = (
                json.loads(previous_snapshot_bytes)
                if previous_snapshot_bytes is not None
                else {}
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise HandoffError(
                f"Existing campaign snapshot is unreadable: {snapshot_path}"
            ) from exc
        if not isinstance(previous_snapshot, dict):
            raise HandoffError("Existing campaign snapshot must be a JSON object")

        created_utc = utc_now()
        takeover_id = (
            "emergency_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "_"
            + uuid.uuid4().hex[:12]
        )
        staging = Path(
            tempfile.mkdtemp(prefix=f".{takeover_id}.", dir=state_dir)
        )
        final_root = repo / EMERGENCY_TAKEOVER_ROOT / takeover_id
        takeover_parent = final_root.parent
        parent_preexisted = takeover_parent.exists()
        final_installed = False
        snapshot_replaced = False
        snapshot_temporary: Path | None = None
        try:
            checked = staging / "checked_source.csv"
            intended = staging / "intended_source.csv"
            keep = staging / "triaged_keep.csv"
            reject = staging / "triaged_reject.csv"
            source_bytes = bundled_queue.read_bytes()
            for target in (checked, intended, keep):
                _atomic_replace_bytes(target, source_bytes)
            _atomic_replace_bytes(reject, b"Email\n")
            previous_dir = staging / "previous_campaign"
            previous_dir.mkdir(parents=True, exist_ok=True)
            archived_snapshot = previous_dir / "active_campaign_snapshot.json"
            if previous_snapshot_bytes is not None:
                _atomic_replace_bytes(archived_snapshot, previous_snapshot_bytes)
            archived_metadata = _copy_previous_campaign_metadata(
                repo,
                previous_dir,
                previous_snapshot,
            )

            relative_root = final_root.relative_to(repo)
            source_paths = {
                "checked": relative_root / checked.name,
                "intended_source": relative_root / intended.name,
                "triaged_keep": relative_root / keep.name,
                "triaged_reject": relative_root / reject.name,
            }
            source_files = {
                key: {
                    "path": path.as_posix(),
                    "sha256": sha256_file(staging / Path(path).name),
                    "size": (staging / Path(path).name).stat().st_size,
                    "row_count": _csv_count(staging / Path(path).name),
                    "email_fingerprint": _email_fingerprint(
                        _read_email_set(staging / Path(path).name)
                    ),
                }
                for key, path in source_paths.items()
            }
            provenance_path = relative_root / "provenance_manifest.json"
            provenance = {
                "schema_version": 1,
                "takeover_id": takeover_id,
                "created_utc": created_utc,
                "machine_id": machine,
                "profile": profile,
                "preview_validation_mode": validation_mode,
                "operator_reason": reason.strip(),
                "bundle_path": str(bundle),
                "bundle_sha256": expected_bundle_sha256,
                "bundle_expected_commit": manifest["expected_commit"],
                "current_application_commit": git(repo, "rev-parse", "HEAD"),
                "queue_path": queue_relative,
                "queue_row_count": current_state["row_count"],
                "queue_unique_count": len(current_state["emails"]),
                "queue_fingerprint": current_state["fingerprint"],
                "queue_match_mode": (
                    "byte_for_byte" if byte_identical else "canonical_email_set"
                ),
                "generated_sources": source_files,
                "validation": validation,
                "previous_campaign_snapshot_path": (
                    (
                        relative_root
                        / "previous_campaign"
                        / "active_campaign_snapshot.json"
                    ).as_posix()
                    if previous_snapshot_bytes is not None
                    else ""
                ),
                "previous_campaign_snapshot_fingerprint": previous_snapshot_fingerprint,
                "previous_campaign_metadata": archived_metadata,
                "emergency_source_decision": (
                    "The checked and intended sources are canonical copies of the exact "
                    "verified bundled private_jc queue. This is emergency provenance "
                    "reconstruction, not a normal lead check or triage result."
                ),
                "status": "awaiting_preview_validation",
            }
            _write_json(staging / "provenance_manifest.json", provenance)
            new_snapshot = {
                "schema_version": 2,
                "snapshot_type": "emergency_takeover",
                "takeover_id": takeover_id,
                "created_utc": created_utc,
                "profile": profile,
                "status": "awaiting_preview_validation",
                "checked_path": source_paths["checked"].as_posix(),
                "intended_source_path": source_paths["intended_source"].as_posix(),
                "triaged_keep_path": source_paths["triaged_keep"].as_posix(),
                "triaged_reject_path": source_paths["triaged_reject"].as_posix(),
                "provenance_manifest_path": provenance_path.as_posix(),
                "files": source_files,
            }
            snapshot_payload = (
                json.dumps(new_snapshot, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            fd, temporary_name = tempfile.mkstemp(
                prefix=".active_campaign_snapshot.",
                dir=state_dir,
            )
            snapshot_temporary = Path(temporary_name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(snapshot_payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(snapshot_temporary, 0o600)

            takeover_parent.mkdir(parents=True, exist_ok=True)
            if final_root.exists():
                raise HandoffError(f"Emergency takeover ID collision: {final_root}")
            os.replace(staging, final_root)
            final_installed = True
            _fsync_directory(takeover_parent)
            if write_hook is not None:
                write_hook("after_takeover_directory", final_root)
            os.replace(snapshot_temporary, snapshot_path)
            snapshot_temporary = None
            snapshot_replaced = True
            _fsync_directory(state_dir)
            if write_hook is not None:
                write_hook("after_snapshot_replace", snapshot_path)

            safety = recompute_queue_safety(repo)
            expected_blockers = ["active profile preview is stale or invalid"]
            if safety.get("unsafe_reasons") != expected_blockers:
                raise HandoffError(
                    "Emergency post-write safety validation failed: "
                    f"unsafe_reasons={safety.get('unsafe_reasons')} "
                    f"details={safety.get('failure_details')}"
                )
            profile_reports = safety.get("profiles") or []
            preview = (
                profile_reports[0].get("preview", {})
                if len(profile_reports) == 1 and isinstance(profile_reports[0], dict)
                else {}
            )
            if preview.get("safe") is not False:
                raise HandoffError(
                    "Emergency takeover requires preview validation to remain blocked"
                )
            if authority_path(repo).exists():
                raise HandoffError("Emergency takeover unexpectedly created authority")
            _make_takeover_immutable(final_root)
            return {
                "takeover_id": takeover_id,
                "status": "awaiting_preview_validation",
                "takeover_root": str(final_root),
                "active_campaign_snapshot": str(snapshot_path),
                "queue_row_count": current_state["row_count"],
                "queue_fingerprint": current_state["fingerprint"],
                "preview": preview,
                "authority_initialized": False,
                "sender_started": False,
                "activation_allowed": False,
                "next_required_action": next_required_action,
            }
        except Exception:
            if snapshot_replaced:
                if previous_snapshot_bytes is None:
                    snapshot_path.unlink(missing_ok=True)
                    _fsync_directory(snapshot_path.parent)
                else:
                    _atomic_replace_bytes(snapshot_path, previous_snapshot_bytes)
            if final_installed and final_root.exists():
                try:
                    os.chmod(final_root, 0o700)
                except OSError:
                    pass
                for child in final_root.rglob("*"):
                    try:
                        os.chmod(child, 0o700 if child.is_dir() else 0o600)
                    except OSError:
                        pass
                shutil.rmtree(final_root)
            elif staging.exists():
                shutil.rmtree(staging)
            if not parent_preexisted and takeover_parent.exists():
                try:
                    takeover_parent.rmdir()
                except OSError:
                    pass
            raise
        finally:
            if snapshot_temporary is not None:
                snapshot_temporary.unlink(missing_ok=True)


def _archive_existing_runtime(repo: Path, bundle_id: str) -> Path:
    backup_dir = repo / LOCAL_STATE_DIR / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"pre_import_{bundle_id}.tgz"
    if destination.exists():
        raise HandoffError(f"Target backup already exists: {destination}")
    with tarfile.open(destination, "x:gz") as archive:
        for root_name in ("data", "_important"):
            root = repo / root_name
            if root.exists():
                archive.add(root, arcname=root_name)
    destination.chmod(0o600)
    return destination


def _atomic_replace_runtime(repo: Path, extracted_runtime: Path) -> None:
    transaction = Path(tempfile.mkdtemp(prefix=".handoff-swap-", dir=repo.parent))
    moved_old: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for root_name in ("data", "_important"):
            source = extracted_runtime / root_name
            source.mkdir(parents=True, exist_ok=True)
            target = repo / root_name
            old = transaction / f"{root_name}.old"
            if target.exists():
                os.replace(target, old)
                moved_old.append((old, target))
            os.replace(source, target)
            installed.append(target)
        _fsync_directory(repo)
    except Exception:
        for target in reversed(installed):
            if target.exists():
                shutil.rmtree(target)
        for old, target in reversed(moved_old):
            if old.exists():
                os.replace(old, target)
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)


def _restore_runtime_backup(repo: Path, backup: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="handoff-recover-", dir=repo.parent) as temp:
        staging = Path(temp)
        with tarfile.open(backup, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] not in {"data", "_important"}
                    or not (member.isfile() or member.isdir())
                    or member.issym()
                    or member.islnk()
                ):
                    raise HandoffError(f"Unsafe recovery archive member: {member.name}")
            archive.extractall(staging, members=members, filter="data")
        _atomic_replace_runtime(repo, staging)


def activate_import(
    repo: Path,
    bundled_authority: dict[str, Any],
    *,
    machine: str | None = None,
) -> dict[str, Any]:
    identity = machine or current_machine()
    floor = load_generation_floor(repo)
    source_generation = int(bundled_authority["generation"])
    new_generation = max(floor, source_generation) + 1
    active = {
        **bundled_authority,
        "authorized_machine": identity,
        "generation": new_generation,
        "created_utc": utc_now(),
        "status": ACTIVE_STATUS,
    }
    write_authority(repo, active)
    write_generation_floor(repo, new_generation, active["bundle_id"])
    return active


def import_runtime(
    repo: Path,
    bundle: Path,
    *,
    machine: str | None = None,
    replace_hook=None,
) -> dict[str, Any]:
    identity = machine or current_machine()
    try:
        assert_processes_stopped(repo)
    except Exception:
        mark_target_disabled(repo, status="import_failed", machine=identity)
        raise
    mark_target_disabled(repo, status="import_in_progress", machine=identity)
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        mark_target_disabled(repo, status="import_failed", machine=identity)
        raise HandoffError("Tracked target worktree is dirty")
    try:
        manifest_hint, _authority_hint = read_bundle_metadata(bundle)
    except Exception:
        mark_target_disabled(repo, status="import_failed", machine=identity)
        raise
    mark_target_disabled(
        repo,
        status="import_in_progress",
        metadata=manifest_hint,
        machine=identity,
    )
    if manifest_hint.get("target_machine") != identity:
        mark_target_disabled(
            repo, status="import_failed", metadata=manifest_hint, machine=identity
        )
        raise HandoffError(
            f"Bundle targets {manifest_hint.get('target_machine')}, not {identity}"
        )
    if git(repo, "rev-parse", "HEAD") != manifest_hint.get("expected_git_commit"):
        mark_target_disabled(
            repo, status="import_failed", metadata=manifest_hint, machine=identity
        )
        raise HandoffError("Target Git commit does not exactly match bundle")
    bundle_id = str(manifest_hint.get("bundle_id") or "")
    used = _read_used_bundles(repo)
    if bundle_id in used:
        mark_target_disabled(
            repo, status="import_failed", metadata=manifest_hint, machine=identity
        )
        raise HandoffError(f"Bundle has already been used: {bundle_id}")
    floor = load_generation_floor(repo)
    source_generation = manifest_hint.get("source_generation")
    if (
        isinstance(source_generation, bool)
        or not isinstance(source_generation, int)
        or source_generation < floor
    ):
        mark_target_disabled(
            repo, status="import_failed", metadata=manifest_hint, machine=identity
        )
        raise HandoffError(
            f"Stale generation {source_generation!r}; local floor is {floor}"
        )
    with tempfile.TemporaryDirectory(prefix="handoff-import-", dir=repo.parent) as temp:
        staging = Path(temp)
        backup: Path | None = None
        replacement_attempted = False
        try:
            manifest, bundled_authority, verification = extract_and_verify(bundle, staging)
            safety = recompute_queue_safety(staging / RUNTIME_ROOT)
            if not safety["safe"]:
                raise HandoffError(
                    "Queue safety failure: " + ", ".join(safety["unsafe_reasons"])
                )
            backup = _archive_existing_runtime(repo, bundle_id)
            replacement_attempted = True
            if replace_hook is not None:
                replace_hook(repo, staging / RUNTIME_ROOT)
            else:
                _atomic_replace_runtime(repo, staging / RUNTIME_ROOT)
            active = activate_import(repo, bundled_authority, machine=identity)
            used.add(bundle_id)
            _write_used_bundles(repo, used)
            result = {
                "bundle_id": bundle_id,
                "backup": str(backup),
                "authority": active,
                "verification": verification,
                "queue_safety": safety,
                "sender_started": False,
            }
            _write_json(repo / LOCAL_STATE_DIR / LAST_IMPORT_NAME, result)
            return result
        except Exception:
            if replacement_attempted and backup is not None:
                try:
                    _restore_runtime_backup(repo, backup)
                except Exception as recovery_exc:
                    mark_target_disabled(
                        repo,
                        status="rollback_failed",
                        metadata=manifest_hint,
                        machine=identity,
                    )
                    raise HandoffError(
                        f"Import failed and target rollback also failed: {recovery_exc}"
                    ) from recovery_exc
            mark_target_disabled(
                repo,
                status="import_failed",
                metadata=manifest_hint,
                machine=identity,
            )
            raise


def initialize_authority(
    repo: Path,
    *,
    machine: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    identity = machine or current_machine()
    assert_processes_stopped(repo)
    safety = recompute_queue_safety(repo)
    if not safety["safe"]:
        details = list(safety.get("failure_details") or [])
        message = "; ".join(str(detail) for detail in details) or ", ".join(
            str(reason) for reason in safety["unsafe_reasons"]
        )
        raise HandoffError(
            "Cannot initialize unsafe runtime: " + message
        )
    if authority_path(repo).exists() and not force:
        raise HandoffError("Authority already exists; refusing bootstrap without --force")
    generation = max(1, load_generation_floor(repo))
    other = "windows-wsl" if identity == "mac" else "mac"
    payload = {
        "authorized_machine": identity,
        "generation": generation,
        "bundle_id": f"bootstrap-{uuid.uuid4()}",
        "source_machine": other,
        "target_machine": identity,
        "created_utc": utc_now(),
        "expected_git_commit": git(repo, "rev-parse", "HEAD"),
        "runtime_manifest_hash": "bootstrap-no-runtime-bundle",
        "status": ACTIVE_STATUS,
    }
    write_authority(repo, payload)
    write_generation_floor(repo, generation, payload["bundle_id"])
    return payload


def rollback(repo: Path, backup: Path | None = None) -> dict[str, Any]:
    assert_processes_stopped(repo)
    backup_dir = repo / LOCAL_STATE_DIR / BACKUP_DIR_NAME
    candidates = sorted(backup_dir.glob("pre_import_*.tgz"), key=lambda p: p.stat().st_mtime)
    selected = backup or (candidates[-1] if candidates else None)
    if selected is None or not selected.is_file():
        raise HandoffError("No runtime backup is available for rollback")
    mark_target_disabled(repo, status="rollback_in_progress")
    with tempfile.TemporaryDirectory(prefix="handoff-rollback-", dir=repo.parent) as temp:
        staging = Path(temp)
        with tarfile.open(selected, "r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or path.parts[0] not in {"data", "_important"}:
                    raise HandoffError(f"Unsafe rollback archive member: {member.name}")
                if not (member.isfile() or member.isdir()) or member.issym() or member.islnk():
                    raise HandoffError(f"Unsafe rollback archive type: {member.name}")
            archive.extractall(staging, filter="data")
        _atomic_replace_runtime(repo, staging)
    mark_target_disabled(repo, status="rolled_back")
    return {"backup": str(selected), "status": "rolled_back", "sender_started": False}


def status(repo: Path, *, machine: str | None = None) -> dict[str, Any]:
    try:
        identity = machine or current_machine()
        identity_error = ""
    except AuthorityError as exc:
        identity = ""
        identity_error = str(exc)
    try:
        authority = load_authority(repo)
        authority_error = ""
    except AuthorityError as exc:
        authority = None
        authority_error = str(exc)
    try:
        floor = load_generation_floor(repo)
        floor_error = ""
    except AuthorityError as exc:
        floor = 0
        floor_error = str(exc)
    authorized = False
    if identity:
        try:
            assert_send_authorized(repo, machine=identity)
            authorized = True
        except AuthorityError:
            pass
    return {
        "machine": identity,
        "machine_error": identity_error,
        "authority": authority,
        "authority_error": authority_error,
        "generation_floor": floor,
        "generation_floor_error": floor_error,
        "real_send_authorized": authorized,
        "process_blockers": process_blockers(),
        "active_job_files": active_job_files(repo),
        "head": git(repo, "rev-parse", "HEAD"),
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--machine", choices=("mac", "windows-wsl"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    export_parser = commands.add_parser("export")
    export_parser.add_argument("--target", required=True, choices=("mac", "windows-wsl"))
    export_parser.add_argument("--output-dir", type=Path, default=Path("runtime_handoff_bundles"))
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("bundle", type=Path)
    import_parser = commands.add_parser("import")
    import_parser.add_argument("bundle", type=Path)
    activate_parser = commands.add_parser("activate")
    activate_parser.add_argument("--initialize", action="store_true")
    activate_parser.add_argument("--force", action="store_true")
    emergency_parser = commands.add_parser("emergency-takeover")
    emergency_parser.add_argument("--bundle", type=Path, required=True)
    emergency_parser.add_argument(
        "--machine",
        dest="emergency_machine",
        choices=("mac",),
        required=True,
    )
    emergency_parser.add_argument(
        "--profile",
        choices=("private_jc",),
        required=True,
    )
    emergency_parser.add_argument("--reason", required=True)
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("--backup", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            print(json.dumps(status(repo, machine=args.machine), indent=2, sort_keys=True))
        elif args.command == "export":
            bundle = export_runtime(
                repo,
                args.output_dir.resolve(),
                args.target,
                machine=args.machine,
            )
            print(bundle)
        elif args.command == "verify":
            print(
                json.dumps(
                    verify_runtime_bundle(args.bundle.resolve()),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif args.command == "import":
            print(
                json.dumps(
                    import_runtime(repo, args.bundle.resolve(), machine=args.machine),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif args.command == "activate":
            if not args.initialize:
                raise HandoffError("Standalone activate requires --initialize")
            print(
                json.dumps(
                    initialize_authority(repo, machine=args.machine, force=args.force),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif args.command == "emergency-takeover":
            result = emergency_takeover(
                repo,
                args.bundle,
                machine=args.emergency_machine,
                profile=args.profile,
                reason=args.reason,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            print(f"NEXT REQUIRED ACTION: {result['next_required_action']}")
        elif args.command == "rollback":
            print(
                json.dumps(
                    rollback(repo, args.backup.resolve() if args.backup else None),
                    indent=2,
                    sort_keys=True,
                )
            )
    except (HandoffError, AuthorityError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
