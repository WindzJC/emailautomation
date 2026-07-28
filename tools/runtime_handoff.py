#!/usr/bin/env python3
"""Production-safe bidirectional runtime handoff.

Archives contain runtime data only. They are mode 0600 and intended for SCP,
which encrypts transport. Secrets and source code are never included.
"""

from __future__ import annotations

import argparse
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


def recompute_queue_safety(runtime_root: Path) -> dict[str, Any]:
    queue_emails: set[str] = set()
    duplicate_count = 0
    invalid_count = 0
    for path in sorted((runtime_root / "data/shards").glob("recipients_*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = {str(field or "").strip().lower() for field in (reader.fieldnames or [])}
            if "email" not in fields and "authoremail" not in fields:
                raise HandoffError(f"Queue safety failure: missing Email header in {path.name}")
            local_seen: set[str] = set()
            for row in reader:
                email = str(row.get("Email") or row.get("AuthorEmail") or "").strip().lower()
                if not EMAIL_RE.match(email):
                    invalid_count += 1
                elif email in local_seen:
                    duplicate_count += 1
                else:
                    local_seen.add(email)
                    queue_emails.add(email)
    suppression_count = 0
    suppressed_emails: set[str] = set()
    for name in ("suppressed.csv", "unsubscribed.csv", "sendgrid_suppressions.csv"):
        path = runtime_root / "data/state" / name
        if not path.exists() or path.stat().st_size == 0:
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = {str(field or "").strip().lower() for field in (reader.fieldnames or [])}
            if "email" not in fields:
                raise HandoffError(f"Suppression validation failure: missing Email header in {name}")
            for row in reader:
                email = str(row.get("Email") or "").strip().lower()
                if email:
                    suppressed_emails.add(email)
                    suppression_count += 1
    authoritative_sent: set[str] = set()
    logs_root = runtime_root / "data/logs"
    if logs_root.exists():
        for path in logs_root.rglob("*.csv"):
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    status = str(row.get("Status") or "").strip().upper()
                    info = str(row.get("Info") or "").strip().lower()
                    if status == "SENT" or (
                        status == "ATTEMPT" and "outcome=sent" in info
                    ):
                        email = str(row.get("Email") or "").strip().lower()
                        if email:
                            authoritative_sent.add(email)
    idempotency_path = runtime_root / "data/state/send_idempotency.sqlite3"
    if idempotency_path.exists():
        try:
            with sqlite3.connect(
                f"file:{idempotency_path.resolve().as_posix()}?mode=ro", uri=True
            ) as db:
                table = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='send_reservations'"
                ).fetchone()
                if table:
                    for (email,) in db.execute(
                        """
                        SELECT email FROM send_reservations
                        WHERE lower(coalesce(status, '')) IN
                              ('submitted', 'sent', 'reserved', 'ambiguous')
                           OR lower(coalesce(outcome, '')) = 'sent'
                        """
                    ):
                        normalized = str(email or "").strip().lower()
                        if normalized:
                            authoritative_sent.add(normalized)
        except sqlite3.DatabaseError as exc:
            raise HandoffError(
                f"Queue safety failure: unreadable idempotency state: {exc}"
            ) from exc
    sent_overlap = queue_emails & authoritative_sent
    failed_preview_rows = 0
    previews = runtime_root / "data/message_previews"
    if previews.exists():
        for path in previews.glob("*_message_preview_failed.csv"):
            failed_preview_rows += _csv_count(path)
        for path in previews.glob("*_message_preview_summary.txt"):
            text = path.read_text(encoding="utf-8").lower()
            match = re.search(r"(?:failed|failures)\s*[:=]\s*(\d+)", text)
            if match:
                failed_preview_rows += int(match.group(1))
    reasons: list[str] = []
    if duplicate_count:
        reasons.append("duplicate queue recipients")
    if invalid_count:
        reasons.append("invalid queue recipients")
    if failed_preview_rows:
        reasons.append("preview validation failures")
    if sent_overlap:
        reasons.append("queue overlaps authoritative sent/idempotency state")
    return {
        "safe": not reasons,
        "unsafe_reasons": reasons,
        "queue_unique_emails": len(queue_emails),
        "duplicate_queue_rows": duplicate_count,
        "invalid_queue_rows": invalid_count,
        "suppression_records": suppression_count,
        "queue_suppression_overlap": len(queue_emails & suppressed_emails),
        "queue_sent_overlap": len(sent_overlap),
        "preview_failed_rows": failed_preview_rows,
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
        raise HandoffError(
            "Cannot initialize unsafe runtime: " + ", ".join(safety["unsafe_reasons"])
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
