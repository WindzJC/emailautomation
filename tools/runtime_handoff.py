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
        ["ps", "-eo", "pid=,args="], text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise HandoffError("Could not inspect running processes")
    own_pid = os.getpid()
    blockers: list[str] = []
    for line in result.stdout.splitlines():
        match = re.match(r"\s*(\d+)\s+(.*)", line)
        if not match or int(match.group(1)) == own_pid:
            continue
        command = match.group(2)
        if "runtime_handoff.py" in command:
            continue
        for category, markers in PROCESS_MARKERS.items():
            if any(marker in command for marker in markers):
                blockers.append(f"{match.group(1)} {category}: {command}")
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
