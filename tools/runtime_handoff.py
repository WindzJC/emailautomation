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
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_authority import (  # noqa: E402
    ACTIVE_STATUS,
    MACHINES,
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
IMPORT_STAGING_DIR_NAME = "import-staging"
RECEIVE_TRANSACTION_DIR_NAME = "receive-transactions"
RECEIVE_TRANSACTION_SCHEMA_VERSION = 1
RECEIVE_TRANSACTION_INTEGRITY_FIELD = "transaction_integrity_hash"
INTERRUPTED_BUNDLE_SHA_ENV = "ASTRA_INTERRUPTED_RECEIVE_BUNDLE_SHA256"
INTERRUPTED_BASELINE_ENV = "ASTRA_INTERRUPTED_RECEIVE_BASELINE_SHA256"
PROCESS_ENTRYPOINT_CATEGORIES = {
    "send_shard.py": "sender",
    "live_dashboard.py": "dashboard",
    "streamlit_monitor.py": "dashboard",
    "run_dashboard_tmux.sh": "dashboard",
    "run_live_dashboard.sh": "dashboard",
    "cloudflared": "tunnel",
    "run_tunnel_tmux.sh": "tunnel",
    "dispatch.py": "dispatch",
    "check_pending.py": "check",
    "check_1hr.py": "check",
    "check_24h.py": "check",
    "check_important_leads.py": "check",
    "triage.py": "triage",
    "important_leads_verify.py": "verification",
    "verification.py": "verification",
    "important_leads_workflow.py": "workflow",
    "leads_workflow.py": "workflow",
    "precheck_leads.py": "workflow",
    "handoff": "handoff",
    "runtime_handoff.py": "handoff",
    "mac_runtime_migration.py": "handoff",
    "package_campaign_handoff.py": "handoff",
}
PROCESS_MODULE_CATEGORIES = {
    "send_shard": "sender",
    "live_dashboard": "dashboard",
    "important_leads_verify": "verification",
    "important_leads_workflow": "workflow",
    "leads_workflow": "workflow",
    "precheck_leads": "workflow",
    "tools.runtime_handoff": "handoff",
    "tools.mac_runtime_migration": "handoff",
    "tools.package_campaign_handoff": "handoff",
}
PYTHON_ENTRYPOINT_RE = re.compile(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?$")
SHELL_ENTRYPOINTS = {"bash", "dash", "sh", "zsh"}
ACTIVE_JOB_STATES = {"queued", "running", "checking", "verifying", "dispatching", "triaging"}
JOB_ROOTS = (
    "_important/check_runs/jobs",
    "_important/dispatch_jobs",
    "_important/verify_jobs",
    "data/state/dispatch_jobs",
)
SECRET_NAMES = {".env", ".env.local", "KEYS", "ACC GMAIL"}
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
CONTROLLED_SENDGRID_PROFILE = "sendgrid_controlled_test"
CONTROLLED_SENDGRID_RECIPIENT = (
    "astraproductionsbyjc+sendgridtest@gmail.com"
)
COMMIT_COMPATIBILITY_FILE_ENV = "ASTRA_HANDOFF_COMMIT_COMPATIBILITY_FILE"
COMMIT_COMPATIBILITY_ROOT_KEY = "commit_compatibility_mappings"
COMMIT_COMPATIBILITY_REQUIRED_FIELDS = {
    "source_machine",
    "target_machine",
    "source_commit",
    "source_tree",
    "approved_destination_commit",
}
COMMIT_COMPATIBILITY_OPTIONAL_FIELDS = {
    "approved_interrupted_destination_commits",
}
COMMIT_COMPATIBILITY_FIELDS = (
    COMMIT_COMPATIBILITY_REQUIRED_FIELDS | COMMIT_COMPATIBILITY_OPTIONAL_FIELDS
)
FULL_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
APPROVED_LEGACY_SOURCE_IDENTITY = {
    "source_machine": "mac",
    "target_machine": "cloud",
    "source_commit": "14c3eaf79507cc33fab06ba107fe128ba251a9dc",
    "source_tree": "9dc901637974651e05f0c2550d4f08f91839ef91",
}
APPROVED_LEGACY_CLEANED_EQUIVALENT_COMMIT = (
    "c5e9af123b7a2c66fd83323ce3e8f3e6484f6759"
)


class HandoffError(RuntimeError):
    """A fail-closed operator-readable refusal."""


class _DuplicateConfigurationKey(ValueError):
    """Internal signal for duplicate JSON configuration keys."""


def _default_peer_machine(identity: str) -> str:
    if identity == "mac":
        return "windows-wsl"
    return "mac"


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


def _secure_directory(
    path: Path,
    *,
    create: bool,
    expected_device: int | None = None,
) -> os.stat_result:
    """Create/open a private directory without following a symlink."""
    if not path.is_absolute():
        raise HandoffError(f"Private handoff path must be absolute: {path}")
    if create and not path.exists():
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise HandoffError(f"Private handoff directory is missing: {path}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        raise HandoffError(f"Private handoff path must be a regular directory: {path}")
    if before.st_uid != os.geteuid() or before.st_gid != os.getegid():
        raise HandoffError(f"Private handoff directory has the wrong owner: {path}")
    if stat.S_IMODE(before.st_mode) != 0o700:
        raise HandoffError(f"Private handoff directory must use mode 0700: {path}")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise HandoffError("Secure handoff directories require O_NOFOLLOW support")
    fd = os.open(path, flags | nofollow)
    try:
        opened = os.fstat(fd)
    finally:
        os.close(fd)
    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
        raise HandoffError(f"Private handoff directory changed while opening: {path}")
    if expected_device is not None and opened.st_dev != expected_device:
        raise HandoffError(
            f"Private handoff directory is on a different filesystem: {path}"
        )
    return opened


def _private_handoff_layout(repo: Path) -> dict[str, Path]:
    try:
        repo_stat = repo.lstat()
    except FileNotFoundError as exc:
        raise HandoffError(f"Repository path is missing: {repo}") from exc
    if stat.S_ISLNK(repo_stat.st_mode) or not stat.S_ISDIR(repo_stat.st_mode):
        raise HandoffError("Repository path must be a regular directory, not a symlink")
    if repo_stat.st_uid != os.geteuid() or repo_stat.st_gid != os.getegid():
        raise HandoffError("Repository must be owned by the handoff service account")
    root = repo / LOCAL_STATE_DIR
    if not root.exists():
        try:
            os.mkdir(root, 0o700)
        except FileExistsError:
            pass
    _secure_directory(root, create=False, expected_device=repo_stat.st_dev)
    layout = {
        "root": root,
        "staging": root / IMPORT_STAGING_DIR_NAME,
        "transactions": root / RECEIVE_TRANSACTION_DIR_NAME,
        "backups": root / BACKUP_DIR_NAME,
    }
    for name in ("staging", "transactions", "backups"):
        path = layout[name]
        if not path.exists():
            try:
                os.mkdir(path, 0o700)
            except FileExistsError:
                pass
        _secure_directory(path, create=False, expected_device=repo_stat.st_dev)
    return layout


def _open_private_file(
    path: Path, *, required: bool = True
) -> tuple[int, os.stat_result] | None:
    try:
        before = path.lstat()
    except FileNotFoundError:
        if required:
            raise HandoffError(f"Private handoff file is missing: {path}")
        return None
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise HandoffError(f"Private handoff path must be a regular file: {path}")
    if before.st_uid != os.geteuid() or before.st_gid != os.getegid():
        raise HandoffError(f"Private handoff file has the wrong owner: {path}")
    if stat.S_IMODE(before.st_mode) != 0o600:
        raise HandoffError(f"Private handoff file must use mode 0600: {path}")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise HandoffError("Secure handoff files require O_NOFOLLOW support")
    try:
        fd = os.open(path, os.O_RDONLY | nofollow)
    except OSError as exc:
        raise HandoffError(f"Private handoff file could not be opened safely: {path}") from exc
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
        os.close(fd)
        raise HandoffError(f"Private handoff file changed while opening: {path}")
    return fd, opened


def _validate_private_file(path: Path, *, required: bool = True) -> os.stat_result | None:
    opened_file = _open_private_file(path, required=required)
    if opened_file is None:
        return None
    fd, opened = opened_file
    try:
        return opened
    finally:
        os.close(fd)


def _read_private_json(path: Path, *, label: str) -> Any:
    opened_file = _open_private_file(path)
    assert opened_file is not None
    descriptor, _metadata = opened_file
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, ValueError) as exc:
        raise HandoffError(f"{label} is unreadable: {path}") from exc


@contextmanager
def _open_private_tar(path: Path) -> Iterator[tarfile.TarFile]:
    opened_file = _open_private_file(path)
    assert opened_file is not None
    descriptor, _metadata = opened_file
    try:
        with os.fdopen(descriptor, "rb") as handle:
            with tarfile.open(fileobj=handle, mode="r:gz") as archive:
                yield archive
    except (OSError, tarfile.TarError) as exc:
        raise HandoffError(f"Private runtime backup is unreadable: {path}") from exc


def _atomic_private_json_write(path: Path, payload: dict[str, Any]) -> None:
    _secure_directory(path.parent, create=False)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(temporary_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        if path.exists() or path.is_symlink():
            _validate_private_file(path)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _private_staging_directory(repo: Path, *, prefix: str) -> Iterator[Path]:
    layout = _private_handoff_layout(repo)
    parent = layout["staging"]
    name = tempfile.mkdtemp(prefix=prefix, dir=parent)
    staging = Path(name)
    try:
        _secure_directory(
            staging,
            create=False,
            expected_device=repo.lstat().st_dev,
        )
        yield staging
    finally:
        if staging.exists():
            current = staging.lstat()
            if stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode):
                raise HandoffError(f"Refusing unsafe staging cleanup: {staging}")
            shutil.rmtree(staging)
            _fsync_directory(parent)


def _runtime_baseline_fingerprint(repo: Path) -> str:
    authority = authority_path(repo)
    inventory: list[dict[str, Any]] = []
    for root_name in ("data", "_important"):
        root = repo / root_name
        if not root.exists():
            continue
        if root.is_symlink() or not root.is_dir():
            raise HandoffError(f"Runtime root must be a regular directory: {root}")
        for path in sorted(root.rglob("*")):
            if path == authority:
                continue
            if path.is_symlink():
                raise HandoffError(
                    f"Runtime baseline contains a symlink: {path.relative_to(repo)}"
                )
            if path.is_file() and not _contains_secret_name(path.relative_to(repo)):
                inventory.append(
                    {
                        "path": path.relative_to(repo).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
    return canonical_hash(inventory)


def _archive_expanded_size(bundle: Path) -> int:
    try:
        with tarfile.open(bundle, "r:gz") as archive:
            return sum(member.size for member in safe_members(archive) if member.isfile())
    except (OSError, tarfile.TarError) as exc:
        raise HandoffError(f"Unreadable handoff archive: {bundle}") from exc


def _assert_import_disk_space(repo: Path, bundle: Path) -> dict[str, int]:
    layout = _private_handoff_layout(repo)
    expanded = _archive_expanded_size(bundle)
    current = 0
    for root_name in ("data", "_important"):
        root = repo / root_name
        if root.exists():
            current += sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    required = expanded + current + max(16 * 1024 * 1024, (expanded + current) // 10)
    free = shutil.disk_usage(layout["root"]).free
    if free < required:
        raise HandoffError(
            f"Insufficient free space for receive staging: required={required} available={free}"
        )
    return {"required": required, "available": free}


def _transaction_path(repo: Path, bundle_id: str) -> Path:
    token = hashlib.sha256(bundle_id.encode("utf-8")).hexdigest()
    return _private_handoff_layout(repo)["transactions"] / f"receive_{token}.json"


def _receive_transaction_integrity_hash(payload: dict[str, Any]) -> str:
    protected = {
        key: value
        for key, value in payload.items()
        if key != RECEIVE_TRANSACTION_INTEGRITY_FIELD
    }
    return canonical_hash(protected)


def _load_receive_transaction(path: Path) -> dict[str, Any]:
    payload = _read_private_json(path, label="Receive transaction")
    if not isinstance(payload, dict) or payload.get("schema_version") != RECEIVE_TRANSACTION_SCHEMA_VERSION:
        raise HandoffError("Receive transaction metadata is malformed")
    recorded_integrity = payload.get(RECEIVE_TRANSACTION_INTEGRITY_FIELD)
    if (
        not isinstance(recorded_integrity, str)
        or not SHA256_RE.fullmatch(recorded_integrity)
        or recorded_integrity != _receive_transaction_integrity_hash(payload)
    ):
        raise HandoffError("Receive transaction integrity check failed")
    return payload


def _write_receive_transaction(repo: Path, payload: dict[str, Any]) -> Path:
    bundle_id = str(payload.get("bundle_id") or "")
    if not bundle_id:
        raise HandoffError("Receive transaction requires a bundle identity")
    payload[RECEIVE_TRANSACTION_INTEGRITY_FIELD] = (
        _receive_transaction_integrity_hash(payload)
    )
    path = _transaction_path(repo, bundle_id)
    _atomic_private_json_write(path, payload)
    return path


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


def _contains_secret_name(path: Path | PurePosixPath) -> bool:
    return any(
        part in SECRET_NAMES or part.startswith(".env.")
        for part in path.parts
    )


def excluded(repo: Path, path: Path) -> bool:
    relative = path.relative_to(repo)
    if relative == Path("data/state/runtime_authority.json"):
        return True
    if set(relative.parts) & EXCLUDED_PARTS:
        return True
    if _contains_secret_name(relative):
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


def _entrypoint_basename(value: str) -> str:
    return PurePosixPath(value).name


def _python_process_category(arguments: list[str]) -> str | None:
    index = 1
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            index += 1
            break
        if token == "-m":
            if index + 1 >= len(arguments):
                return None
            module = arguments[index + 1]
            remaining = arguments[index + 2 :]
            if module == "uvicorn" and "live_dashboard:app" in remaining:
                return "dashboard"
            if module == "streamlit" and any(
                _entrypoint_basename(value) == "streamlit_monitor.py"
                for value in remaining
            ):
                return "dashboard"
            return PROCESS_MODULE_CATEGORIES.get(module)
        if token in {"-c", "-"}:
            return None
        if token in {"-W", "-X"}:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        break
    if index >= len(arguments):
        return None
    return PROCESS_ENTRYPOINT_CATEGORIES.get(
        _entrypoint_basename(arguments[index])
    )


def _shell_process_category(arguments: list[str]) -> str | None:
    index = 1
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            index += 1
            break
        if token in {"-c", "--command"}:
            return None
        if token in {"-o", "+o"}:
            index += 2
            continue
        if token.startswith(("-", "+")):
            index += 1
            continue
        break
    if index >= len(arguments):
        return None
    return PROCESS_ENTRYPOINT_CATEGORIES.get(
        _entrypoint_basename(arguments[index])
    )


def classify_process_command(command: str) -> str | None:
    arguments = command.split()
    if not arguments:
        return None
    entrypoint = _entrypoint_basename(arguments[0])
    if PYTHON_ENTRYPOINT_RE.fullmatch(entrypoint):
        return _python_process_category(arguments)
    if entrypoint in SHELL_ENTRYPOINTS:
        return _shell_process_category(arguments)
    if entrypoint == "uvicorn" and "live_dashboard:app" in arguments[1:]:
        return "dashboard"
    if entrypoint == "streamlit" and any(
        _entrypoint_basename(value) == "streamlit_monitor.py"
        for value in arguments[1:]
    ):
        return "dashboard"
    return PROCESS_ENTRYPOINT_CATEGORIES.get(entrypoint)


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
        category = classify_process_command(command)
        if category is not None:
            blockers.append(f"{pid} {category}: {command}")
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
    path.chmod(0o600)


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
    if _contains_secret_name(path):
        raise HandoffError(f"Sensitive manifest path is forbidden: {text!r}")
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
        if name.startswith(f"{RUNTIME_ROOT}/"):
            relative = PurePosixPath(*path.parts[1:])
            if _contains_secret_name(relative):
                raise HandoffError(
                    f"Sensitive archive member is forbidden: {member.name}"
                )
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


def _reject_duplicate_configuration_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateConfigurationKey(key)
        result[key] = value
    return result


def _load_commit_compatibility_mappings() -> list[dict[str, Any]]:
    configured_path = os.environ.get(COMMIT_COMPATIBILITY_FILE_ENV, "").strip()
    if not configured_path:
        raise HandoffError(
            "Target Git commit does not exactly match bundle and commit compatibility "
            "is not configured"
        )
    path = Path(configured_path)
    if not path.is_absolute():
        raise HandoffError("Commit compatibility file path must be absolute")
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise HandoffError("Commit compatibility requires platform O_NOFOLLOW support")
    close_exec = getattr(os, "O_CLOEXEC", None)
    if close_exec is None:
        raise HandoffError("Commit compatibility requires platform O_CLOEXEC support")
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(path, os.O_RDONLY | close_exec | no_follow)
        except OSError as exc:
            raise HandoffError(
                f"Commit compatibility file is unavailable or unsafe: {path}"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise HandoffError("Commit compatibility file must be a regular file")
        if metadata.st_uid not in {0, os.geteuid()}:
            raise HandoffError("Commit compatibility file has an untrusted owner")
        if stat.S_IMODE(metadata.st_mode) & 0o037:
            raise HandoffError(
                "Commit compatibility file must not be group-writable, "
                "group-executable, or accessible by others"
            )
        try:
            handle = os.fdopen(descriptor, "r", encoding="utf-8")
        except OSError as exc:
            raise HandoffError("Commit compatibility configuration is unreadable") from exc
        descriptor = None
        try:
            with handle:
                payload = json.load(
                    handle,
                    object_pairs_hook=_reject_duplicate_configuration_keys,
                )
        except _DuplicateConfigurationKey as exc:
            raise HandoffError(
                f"Commit compatibility configuration has duplicate key: {exc}"
            ) from exc
        except (OSError, UnicodeError, ValueError) as exc:
            raise HandoffError("Commit compatibility configuration is malformed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not isinstance(payload, dict) or set(payload) != {COMMIT_COMPATIBILITY_ROOT_KEY}:
        raise HandoffError("Commit compatibility configuration is malformed")
    raw_mappings = payload.get(COMMIT_COMPATIBILITY_ROOT_KEY)
    if not isinstance(raw_mappings, list) or not raw_mappings:
        raise HandoffError("Commit compatibility mapping is absent")

    mappings: list[dict[str, Any]] = []
    seen: set[str] = set()
    routes: dict[tuple[str, str, str], str] = {}
    for raw_mapping in raw_mappings:
        if (
            not isinstance(raw_mapping, dict)
            or not COMMIT_COMPATIBILITY_REQUIRED_FIELDS.issubset(raw_mapping)
            or not set(raw_mapping).issubset(COMMIT_COMPATIBILITY_FIELDS)
        ):
            raise HandoffError("Commit compatibility mapping is incomplete or malformed")
        if not all(
            isinstance(raw_mapping[field], str)
            for field in COMMIT_COMPATIBILITY_REQUIRED_FIELDS
        ):
            raise HandoffError("Commit compatibility mapping values must be strings")
        interrupted = raw_mapping.get("approved_interrupted_destination_commits", [])
        if (
            not isinstance(interrupted, list)
            or not all(isinstance(value, str) for value in interrupted)
            or len(set(interrupted)) != len(interrupted)
        ):
            raise HandoffError(
                "Approved interrupted destination commits must be a unique list"
            )
        mapping: dict[str, Any] = {
            field: raw_mapping[field]
            for field in COMMIT_COMPATIBILITY_REQUIRED_FIELDS
        }
        mapping["approved_interrupted_destination_commits"] = interrupted
        if (
            mapping["source_machine"] not in MACHINES
            or mapping["target_machine"] not in MACHINES
            or mapping["source_machine"] == mapping["target_machine"]
        ):
            raise HandoffError("Commit compatibility mapping has invalid machines")
        for field in (
            "source_commit",
            "source_tree",
            "approved_destination_commit",
        ):
            if not FULL_GIT_SHA_RE.fullmatch(mapping[field]):
                raise HandoffError(
                    f"Commit compatibility {field} must be a full lowercase Git SHA"
                )
        if not all(FULL_GIT_SHA_RE.fullmatch(value) for value in interrupted):
            raise HandoffError(
                "Approved interrupted destination commits must be full lowercase Git SHAs"
            )
        identity = canonical_hash(mapping)
        if identity in seen:
            raise HandoffError("Commit compatibility mapping is duplicated")
        seen.add(identity)
        route = (
            mapping["source_machine"],
            mapping["target_machine"],
            mapping["source_commit"],
        )
        if route in routes and routes[route] != identity:
            raise HandoffError("Commit compatibility mappings conflict")
        routes[route] = identity
        mappings.append(mapping)

    if any(
        {
            field: mapping[field]
            for field in APPROVED_LEGACY_SOURCE_IDENTITY
        }
        != APPROVED_LEGACY_SOURCE_IDENTITY
        for mapping in mappings
    ):
        raise HandoffError("Commit compatibility source identity is not approved")
    return mappings


def validate_bundle_commit_compatibility(
    repo: Path,
    manifest: dict[str, Any],
    bundled_authority: dict[str, Any],
    *,
    machine: str | None = None,
) -> dict[str, Any]:
    identity = machine or current_machine()
    source_machine = manifest.get("source_machine")
    target_machine = manifest.get("target_machine")
    source_commit = manifest.get("expected_git_commit")
    if source_machine != bundled_authority.get("source_machine"):
        raise HandoffError("Bundle source_machine metadata mismatch")
    if target_machine != bundled_authority.get("target_machine"):
        raise HandoffError("Bundle target_machine metadata mismatch")
    if source_commit != bundled_authority.get("expected_git_commit"):
        raise HandoffError("Bundle expected_git_commit metadata mismatch")
    if target_machine != identity:
        raise HandoffError(f"Bundle targets {target_machine}, not {identity}")

    destination_commit = git(repo, "rev-parse", "HEAD")
    if source_commit == destination_commit:
        return {
            "mode": "exact_commit",
            "source_commit": source_commit,
            "destination_commit": destination_commit,
        }

    mappings = _load_commit_compatibility_mappings()
    matches = [
        mapping
        for mapping in mappings
        if mapping["source_machine"] == source_machine
        and mapping["target_machine"] == target_machine
        and mapping["source_commit"] == source_commit
    ]
    if len(matches) != 1:
        raise HandoffError("Bundle does not match the configured commit compatibility mapping")
    mapping = matches[0]
    if mapping["approved_destination_commit"] != destination_commit:
        raise HandoffError(
            "Configured approved destination commit does not match current HEAD"
        )
    cleaned_tree = git(
        repo,
        "rev-parse",
        f"{APPROVED_LEGACY_CLEANED_EQUIVALENT_COMMIT}^{{tree}}",
    )
    if cleaned_tree != mapping["source_tree"]:
        raise HandoffError("Approved legacy source tree does not match its cleaned equivalent")
    return {
        "mode": "approved_legacy_source",
        "source_machine": source_machine,
        "target_machine": target_machine,
        "source_commit": source_commit,
        "source_tree": mapping["source_tree"],
        "destination_commit": destination_commit,
        "approved_interrupted_destination_commits": list(
            mapping["approved_interrupted_destination_commits"]
        ),
    }


def _sqlite_integrity(path: Path) -> None:
    try:
        with sqlite3.connect(
            f"file:{path.resolve().as_posix()}?mode=ro&immutable=1",
            uri=True,
        ) as db:
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


def verify_runtime_bundle(
    repo: Path,
    bundle: Path,
    *,
    machine: str | None = None,
) -> dict[str, Any]:
    assert_processes_stopped(repo)
    with _private_staging_directory(repo, prefix="verify-") as staging:
        manifest, authority, report = extract_and_verify(bundle, staging)
        compatibility = validate_bundle_commit_compatibility(
            repo,
            manifest,
            authority,
            machine=machine,
        )
    return {
        "manifest": manifest,
        "authority": authority,
        "verification": report,
        "commit_compatibility": compatibility,
    }


def _read_used_bundles(repo: Path) -> set[str]:
    path = _private_handoff_layout(repo)["root"] / USED_BUNDLES_NAME
    if not path.exists() and not path.is_symlink():
        return set()
    try:
        payload = _read_private_json(path, label="Used-bundle ledger")
        values = payload.get("bundle_ids", [])
    except AttributeError as exc:
        raise HandoffError(f"Used-bundle ledger is unreadable: {path}") from exc
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise HandoffError("Used-bundle ledger is malformed")
    return set(values)


def _write_used_bundles(repo: Path, values: set[str]) -> None:
    _atomic_private_json_write(
        _private_handoff_layout(repo)["root"] / USED_BUNDLES_NAME,
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
        source = str(
            (metadata or {}).get("source_machine")
            or _default_peer_machine(identity)
        )
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


PREVIEW_GENERATED_REQUIRED_FIELDS = {
    "email",
    "authoremail",
    "authorname",
    "firstname",
    "booktitle",
    "personalizedopeningline",
    "subject",
    "body",
}
PREVIEW_VALIDATED_REQUIRED_FIELDS = PREVIEW_GENERATED_REQUIRED_FIELDS | {
    "validationstatus",
    "failurereasons",
}


def _read_preview_csv(
    path: Path,
    *,
    required_fields: set[str],
    require_pass: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "exists": path.is_file(),
        "row_count": 0,
        "emails": set(),
        "ordered_emails": [],
        "rows_by_email": {},
        "fingerprint": "",
        "headers": [],
        "missing_fields": [],
        "duplicate_headers": [],
        "extra_column_rows": 0,
        "blank_email_rows": 0,
        "malformed_email_rows": 0,
        "conflicting_email_rows": 0,
        "duplicate_email_rows": 0,
        "non_pass_rows": 0,
        "parse_error": "",
    }
    if not path.is_file():
        return result
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            headers = [str(field or "").strip() for field in (reader.fieldnames or [])]
            lowered = [field.casefold() for field in headers]
            duplicate_headers = sorted(
                {field for field in lowered if field and lowered.count(field) > 1}
            )
            result["headers"] = headers
            result["duplicate_headers"] = duplicate_headers
            result["missing_fields"] = sorted(required_fields - set(lowered))
            if not headers or any(not field for field in headers):
                result["parse_error"] = "blank_or_missing_header"
                return result
            if duplicate_headers:
                result["parse_error"] = "duplicate_headers"
                return result
            field_map = dict(zip(lowered, headers))
            if result["missing_fields"]:
                return result
            emails: set[str] = set()
            ordered_emails: list[str] = []
            rows_by_email: dict[str, dict[str, str]] = {}
            for row in reader:
                result["row_count"] += 1
                if None in row and row[None]:
                    result["extra_column_rows"] += 1
                    continue
                email = str(row.get(field_map["email"]) or "").strip().lower()
                author_email = str(
                    row.get(field_map.get("authoremail", "")) or ""
                ).strip().lower()
                if not email:
                    result["blank_email_rows"] += 1
                    continue
                if not EMAIL_RE.fullmatch(email):
                    result["malformed_email_rows"] += 1
                    continue
                if author_email:
                    if not EMAIL_RE.fullmatch(author_email):
                        result["malformed_email_rows"] += 1
                        continue
                    if author_email != email:
                        result["conflicting_email_rows"] += 1
                        continue
                if email in emails:
                    result["duplicate_email_rows"] += 1
                emails.add(email)
                ordered_emails.append(email)
                rows_by_email[email] = {
                    header: str(row.get(header) or "")
                    for header in headers
                }
                if require_pass:
                    status = str(
                        row.get(field_map["validationstatus"]) or ""
                    ).strip().upper()
                    if status != "PASS":
                        result["non_pass_rows"] += 1
            result["emails"] = emails
            result["ordered_emails"] = ordered_emails
            result["rows_by_email"] = rows_by_email
            result["fingerprint"] = _email_fingerprint(emails)
    except (OSError, UnicodeError, csv.Error) as exc:
        result["parse_error"] = type(exc).__name__
    return result


def _read_preview_summary(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "exists": path.is_file(),
        "mode": "",
        "counts": {},
        "missing_fields": [],
        "duplicate_fields": [],
        "parse_error": "",
    }
    if not path.is_file():
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        result["parse_error"] = type(exc).__name__
        return result
    patterns = {
        "mode": r"(?im)^pitch\s+mode:\s*([A-Za-z0-9_.-]+)\s*$",
        "total": r"(?im)^total\s+rows\s+checked:\s*(\d+)\s*$",
        "passed": r"(?im)^passed\s+rows:\s*(\d+)\s*$",
        "failed": r"(?im)^failed\s+rows:\s*(\d+)\s*$",
    }
    values: dict[str, str] = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text)
        if not matches:
            result["missing_fields"].append(key)
        elif len(matches) > 1:
            result["duplicate_fields"].append(key)
        else:
            values[key] = matches[0]
    if result["missing_fields"] or result["duplicate_fields"]:
        return result
    result["mode"] = values["mode"].strip().lower()
    result["counts"] = {
        "total": int(values["total"]),
        "passed": int(values["passed"]),
        "failed": int(values["failed"]),
    }
    return result



def _select_email_field(fieldnames: Iterable[str]) -> str | None:
    names = [str(name or "").strip() for name in fieldnames]

    preferred = {
        "email",
        "authoremail",
        "author_email",
        "recipientemail",
        "recipient_email",
        "toemail",
        "to_email",
    }

    for name in names:
        normalized = "".join(
            character for character in name.lower()
            if character.isalnum() or character == "_"
        )
        if normalized in preferred:
            return name

    for name in names:
        normalized = "".join(
            character for character in name.lower()
            if character.isalnum()
        )
        if "email" in normalized:
            return name

    return None


def _read_ordered_emails(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []

    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            email_field = _select_email_field(reader.fieldnames or [])
            if email_field is None:
                return []

            emails: list[str] = []
            for row in reader:
                email = str(row.get(email_field) or "").strip().lower()
                if email:
                    emails.append(email)
            return emails
    except (OSError, UnicodeError, csv.Error):
        return []


def _read_successfully_sent_emails(path: Path) -> set[str]:
    """Return recipients safely completed by send or authoritative prior-send."""
    if not path.is_file():
        return set()

    def row_value(row: dict[str, Any], field_name: str) -> str:
        for key, value in row.items():
            if str(key or "").strip().lower() == field_name:
                return str(value or "").strip()
        return ""

    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            email_field = _select_email_field(reader.fieldnames or [])
            if email_field is None:
                return set()

            completed: set[str] = set()

            for row in reader:
                email = str(row.get(email_field) or "").strip().lower()
                status = row_value(row, "status").upper()
                info = row_value(row, "info").upper()

                sent_now = status == "SENT"
                sent_previously = (
                    status == "SKIP"
                    and (
                        "EVENT_TYPE="
                        "SKIPPED_ALREADY_SENT_AUTHORITATIVE"
                    )
                    in info
                )

                if email and (sent_now or sent_previously):
                    completed.add(email)

            return completed
    except (OSError, UnicodeError, csv.Error):
        return set()


def _read_ordered_recipient_rows(path: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "safe": False,
        "headers": [],
        "ordered_emails": [],
        "rows_by_email": {},
        "fingerprint": "",
        "failed_predicates": [],
    }
    if path is None or not path.is_file():
        result["failed_predicates"].append("file_exists")
        return result
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = [str(name or "").strip() for name in (reader.fieldnames or [])]
            lowered = [name.casefold() for name in headers]
            if not headers or any(not name for name in headers):
                result["failed_predicates"].append("headers_present")
                return result
            if len(set(lowered)) != len(lowered):
                result["failed_predicates"].append("headers_unique")
                return result
            field_map = dict(zip(lowered, headers))
            email_field = field_map.get("email")
            author_email_field = field_map.get("authoremail")
            if email_field is None:
                result["failed_predicates"].append("email_column_present")
                return result

            ordered_emails: list[str] = []
            rows_by_email: dict[str, dict[str, str]] = {}
            for row in reader:
                if None in row and row[None]:
                    result["failed_predicates"].append("no_extra_columns")
                    continue
                normalized_row = {
                    header: str(row.get(header) or "")
                    for header in headers
                }
                email = normalized_row[email_field].strip().lower()
                author_email = (
                    normalized_row[author_email_field].strip().lower()
                    if author_email_field is not None
                    else ""
                )
                if not email:
                    result["failed_predicates"].append("no_blank_emails")
                    continue
                if not EMAIL_RE.fullmatch(email):
                    result["failed_predicates"].append("valid_emails")
                    continue
                if author_email:
                    if not EMAIL_RE.fullmatch(author_email):
                        result["failed_predicates"].append("valid_emails")
                        continue
                    if author_email != email:
                        result["failed_predicates"].append(
                            "email_authoremail_match"
                        )
                        continue
                if email in rows_by_email:
                    result["failed_predicates"].append("unique_emails")
                    continue
                ordered_emails.append(email)
                rows_by_email[email] = normalized_row
    except (OSError, UnicodeError, csv.Error) as exc:
        result["failed_predicates"].append(
            f"csv_readable:{type(exc).__name__}"
        )
        return result

    result["headers"] = headers
    result["ordered_emails"] = ordered_emails
    result["rows_by_email"] = rows_by_email
    result["fingerprint"] = _email_fingerprint(ordered_emails)
    result["failed_predicates"] = list(
        dict.fromkeys(result["failed_predicates"])
    )
    result["safe"] = not result["failed_predicates"]
    return result


def _emergency_terminal_outcomes(
    path: Path,
    removed_emails: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "safe": False,
        "sent_rows": 0,
        "authoritative_skip_rows": 0,
        "missing_rows": 0,
        "generic_rows": 0,
        "ambiguous_rows": 0,
        "failed_predicates": [],
    }
    if not path.is_file():
        result["failed_predicates"].append("terminal_log_exists")
        return result

    removed = set(removed_emails)
    outcomes: dict[str, list[str]] = {
        email: []
        for email in removed_emails
    }
    authoritative_skip = re.compile(
        r"(?:^|\s)event_type="
        r"SKIPPED_ALREADY_SENT_AUTHORITATIVE(?:\s|$)"
    )
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = [str(name or "").strip() for name in (reader.fieldnames or [])]
            lowered = [name.casefold() for name in headers]
            if not headers or any(not name for name in headers):
                result["failed_predicates"].append(
                    "terminal_log_headers_present"
                )
                return result
            if len(set(lowered)) != len(lowered):
                result["failed_predicates"].append(
                    "terminal_log_headers_unique"
                )
                return result
            field_map = dict(zip(lowered, headers))
            missing = {
                name
                for name in ("email", "status", "info")
                if name not in field_map
            }
            if missing:
                result["failed_predicates"].append(
                    "terminal_log_required_columns"
                )
                return result

            for row in reader:
                if None in row and row[None]:
                    result["failed_predicates"].append(
                        "terminal_log_no_extra_columns"
                    )
                    continue
                email = str(
                    row.get(field_map["email"]) or ""
                ).strip().lower()
                if email and not EMAIL_RE.fullmatch(email):
                    result["failed_predicates"].append(
                        "terminal_log_valid_emails"
                    )
                    continue
                if email not in removed:
                    continue
                status = str(
                    row.get(field_map["status"]) or ""
                ).strip().upper()
                info = str(row.get(field_map["info"]) or "").strip()
                if status == "SENT":
                    outcomes[email].append("SENT")
                elif status == "SKIP" and authoritative_skip.search(info):
                    outcomes[email].append(
                        "SKIPPED_ALREADY_SENT_AUTHORITATIVE"
                    )
                else:
                    outcomes[email].append("NON_AUTHORITATIVE")
    except (OSError, UnicodeError, csv.Error) as exc:
        result["failed_predicates"].append(
            f"terminal_log_readable:{type(exc).__name__}"
        )
        return result

    for email in removed_emails:
        history = outcomes[email]
        if not history:
            result["missing_rows"] += 1
            continue
        terminal = history[-1]
        if terminal == "NON_AUTHORITATIVE":
            result["generic_rows"] += 1
            continue
        if terminal == "SENT":
            result["sent_rows"] += 1
        elif terminal == "SKIPPED_ALREADY_SENT_AUTHORITATIVE":
            result["authoritative_skip_rows"] += 1
        else:
            result["ambiguous_rows"] += 1

    if result["missing_rows"]:
        result["failed_predicates"].append(
            "every_removed_recipient_has_terminal_result"
        )
    if result["generic_rows"]:
        result["failed_predicates"].append(
            "no_generic_or_non_authoritative_results"
        )
    if result["ambiguous_rows"]:
        result["failed_predicates"].append(
            "no_ambiguous_terminal_results"
        )
    result["failed_predicates"] = list(
        dict.fromkeys(result["failed_predicates"])
    )
    result["safe"] = not result["failed_predicates"]
    return result


def _source_record_matches(
    runtime_root: Path,
    record: dict[str, Any] | None,
    source_path: Path,
    source_rows: dict[str, Any],
) -> bool:
    if not isinstance(record, dict):
        return False
    recorded_path = _resolve_runtime_path(
        runtime_root,
        record.get("path") or record.get("relative_path"),
    )
    if recorded_path is None or recorded_path.resolve() != source_path.resolve():
        return False
    try:
        recorded_size = int(record.get("size"))
        recorded_rows = int(record.get("row_count"))
    except (TypeError, ValueError):
        return False
    return (
        recorded_size == source_path.stat().st_size
        and recorded_rows == len(source_rows["ordered_emails"])
        and str(record.get("sha256") or "").strip() == sha256_file(source_path)
        and str(record.get("email_fingerprint") or "").strip()
        == str(source_rows["fingerprint"])
    )


def _emergency_queue_progress_match(
    runtime_root: Path,
    *,
    profile: str,
    manifest: dict[str, Any],
    intended_record: dict[str, Any] | None,
    provenance: dict[str, Any],
    queue_state: dict[str, Any],
    generated: dict[str, Any],
    validated: dict[str, Any],
    failed: dict[str, Any],
    summary: dict[str, Any],
    expected_mode: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "safe": False,
        "verified_emergency_queue_progress": False,
        "original_rows": 0,
        "preview_rows": 0,
        "current_rows": 0,
        "removed_rows": 0,
        "terminal_sent_rows": 0,
        "terminal_authoritative_skip_rows": 0,
        "unresolved_terminal_rows": 0,
        "failed_predicates": [],
    }

    if not isinstance(intended_record, dict):
        result["failed_predicates"].append("intended_record_present")
        return result

    intended_path_value = (
        intended_record.get("path")
        or intended_record.get("relative_path")
        or manifest.get("intended_source_path")
    )
    queue_path_value = (
        provenance.get("queue_path")
        or manifest.get("queue_path")
    )

    intended_path = _resolve_runtime_path(runtime_root, intended_path_value)
    queue_path = _resolve_runtime_path(runtime_root, queue_path_value)

    original = _read_ordered_recipient_rows(intended_path)
    current = _read_ordered_recipient_rows(queue_path)
    original_emails = list(original["ordered_emails"])
    current_emails = list(current["ordered_emails"])
    preview_emails = list(generated.get("ordered_emails") or [])

    result["original_rows"] = len(original_emails)
    result["preview_rows"] = len(preview_emails)
    result["current_rows"] = len(current_emails)

    if not original["safe"] or not original_emails:
        result["failed_predicates"].append(
            "immutable_source_rows_valid"
        )
    if not current["safe"] or not current_emails:
        result["failed_predicates"].append(
            "current_queue_rows_valid"
        )

    if result["failed_predicates"]:
        return result

    provenance_sources = provenance.get("generated_sources")
    provenance_intended = (
        provenance_sources.get("intended_source")
        if isinstance(provenance_sources, dict)
        else None
    )
    if not _source_record_matches(
        runtime_root,
        intended_record,
        intended_path,
        original,
    ):
        result["failed_predicates"].append(
            "snapshot_immutable_source_metadata_match"
        )
    if not _source_record_matches(
        runtime_root,
        provenance_intended,
        intended_path,
        original,
    ):
        result["failed_predicates"].append(
            "provenance_immutable_source_metadata_match"
        )
    if (
        str(provenance.get("queue_fingerprint") or "").strip()
        != str(original["fingerprint"])
    ):
        result["failed_predicates"].append(
            "provenance_original_queue_fingerprint_match"
        )
    try:
        provenance_rows = int(provenance.get("queue_row_count"))
    except (TypeError, ValueError):
        provenance_rows = -1
    if provenance_rows != len(original_emails):
        result["failed_predicates"].append(
            "provenance_original_queue_count_match"
        )

    preview_validation_failures = []
    for label, report in (
        ("generated", generated),
        ("validated", validated),
        ("failed", failed),
    ):
        if (
            not report.get("exists")
            or report.get("parse_error")
            or report.get("missing_fields")
            or report.get("duplicate_headers")
            or int(report.get("extra_column_rows") or 0)
            or int(report.get("blank_email_rows") or 0)
            or int(report.get("malformed_email_rows") or 0)
            or int(report.get("conflicting_email_rows") or 0)
            or int(report.get("duplicate_email_rows") or 0)
        ):
            preview_validation_failures.append(label)
    if preview_validation_failures:
        result["failed_predicates"].append(
            "preview_artifacts_structurally_valid"
        )
    if int(validated.get("non_pass_rows") or 0):
        result["failed_predicates"].append(
            "validated_preview_all_pass"
        )
    if int(failed.get("row_count") or 0):
        result["failed_predicates"].append(
            "failed_preview_has_zero_rows"
        )
    if (
        int(generated.get("row_count") or 0)
        != int(validated.get("row_count") or 0)
        or set(generated.get("emails") or set())
        != set(validated.get("emails") or set())
        or str(generated.get("fingerprint") or "")
        != str(validated.get("fingerprint") or "")
        or list(generated.get("ordered_emails") or [])
        != list(validated.get("ordered_emails") or [])
    ):
        result["failed_predicates"].append(
            "generated_validated_preview_match"
        )
    else:
        generated_headers = {
            str(header).casefold(): str(header)
            for header in generated.get("headers") or []
        }
        validated_headers = {
            str(header).casefold(): str(header)
            for header in validated.get("headers") or []
        }
        shared_preview_fields = (
            PREVIEW_GENERATED_REQUIRED_FIELDS
            & set(generated_headers)
            & set(validated_headers)
        )
        generated_rows = generated.get("rows_by_email") or {}
        validated_rows = validated.get("rows_by_email") or {}
        preview_content_mismatch = False
        for email in generated.get("ordered_emails") or []:
            generated_row = generated_rows.get(email)
            validated_row = validated_rows.get(email)
            if not isinstance(generated_row, dict) or not isinstance(
                validated_row,
                dict,
            ):
                preview_content_mismatch = True
                break
            if any(
                str(generated_row.get(generated_headers[field]) or "")
                != str(validated_row.get(validated_headers[field]) or "")
                for field in shared_preview_fields
            ):
                preview_content_mismatch = True
                break
        if preview_content_mismatch:
            result["failed_predicates"].append(
                "generated_validated_preview_match"
            )
    summary_counts = dict(summary.get("counts") or {})
    if (
        not summary.get("exists")
        or summary.get("parse_error")
        or summary.get("missing_fields")
        or summary.get("duplicate_fields")
        or summary_counts.get("total")
        != int(generated.get("row_count") or 0)
        or summary_counts.get("passed")
        != int(validated.get("row_count") or 0)
        or summary_counts.get("failed") != 0
        or str(summary.get("mode") or "") != expected_mode
    ):
        result["failed_predicates"].append(
            "preview_summary_matches_artifacts"
        )

    if len(current_emails) >= len(original_emails):
        result["failed_predicates"].append("queue_was_reduced")

    original_set = set(original_emails)
    current_set = set(current_emails)

    if not current_set.issubset(original_set):
        result["failed_predicates"].append("no_new_recipients_added")

    preview_set = set(preview_emails)
    if not preview_emails or not preview_set.issubset(original_set):
        result["failed_predicates"].append(
            "preview_is_subset_of_immutable_source"
        )
    if not current_set.issubset(preview_set):
        result["failed_predicates"].append(
            "current_queue_is_subset_of_validated_preview"
        )

    ordered_remaining = [
        email for email in original_emails
        if email in current_set
    ]

    if ordered_remaining != current_emails:
        result["failed_predicates"].append(
            "remaining_queue_order_preserved"
        )

    ordered_preview = [
        email for email in original_emails
        if email in preview_set
    ]
    if ordered_preview != preview_emails:
        result["failed_predicates"].append(
            "preview_order_matches_immutable_source"
        )
    ordered_current_preview = [
        email for email in preview_emails
        if email in current_set
    ]
    if ordered_current_preview != current_emails:
        result["failed_predicates"].append(
            "current_queue_order_matches_validated_preview"
        )

    if [
        header.casefold()
        for header in original["headers"]
    ] != [
        header.casefold()
        for header in current["headers"]
    ]:
        result["failed_predicates"].append(
            "surviving_queue_headers_unchanged"
        )
    else:
        original_headers = {
            header.casefold(): header
            for header in original["headers"]
        }
        current_headers = {
            header.casefold(): header
            for header in current["headers"]
        }
        changed_rows = 0
        for email in current_emails:
            if email not in original["rows_by_email"]:
                changed_rows += 1
                continue
            original_row = original["rows_by_email"][email]
            current_row = current["rows_by_email"][email]
            if any(
                original_row[original_headers[key]]
                != current_row[current_headers[key]]
                for key in original_headers
            ):
                changed_rows += 1
        if changed_rows:
            result["failed_predicates"].append(
                "surviving_queue_rows_unchanged"
            )

    removed_emails = [
        email for email in original_emails
        if email not in current_set
    ]
    result["removed_rows"] = len(removed_emails)

    log_path = (
        runtime_root
        / "data"
        / "logs"
        / f"{profile}_log.csv"
    )
    terminal = _emergency_terminal_outcomes(
        log_path,
        removed_emails,
    )
    result["terminal_sent_rows"] = terminal["sent_rows"]
    result["terminal_authoritative_skip_rows"] = terminal[
        "authoritative_skip_rows"
    ]
    result["unresolved_terminal_rows"] = (
        int(terminal["missing_rows"])
        + int(terminal["generic_rows"])
        + int(terminal["ambiguous_rows"])
    )
    if not terminal["safe"]:
        result["failed_predicates"].extend(
            terminal["failed_predicates"]
        )

    try:
        expected_rows = int(queue_state["row_count"])
    except (KeyError, TypeError, ValueError):
        expected_rows = -1

    if len(current_emails) != expected_rows:
        result["failed_predicates"].append(
            "current_queue_count_matches_runtime"
        )

    expected_fingerprint = str(
        queue_state.get("fingerprint") or ""
    ).strip()
    actual_fingerprint = _email_fingerprint(current_emails)

    if actual_fingerprint != expected_fingerprint:
        result["failed_predicates"].append(
            "current_queue_fingerprint_matches_runtime"
        )

    result["failed_predicates"] = list(
        dict.fromkeys(result["failed_predicates"])
    )
    result["safe"] = not result["failed_predicates"]
    result["verified_emergency_queue_progress"] = result["safe"]
    return result

def _preview_campaign_match(
    runtime_root: Path,
    *,
    profile: str,
    queue_state: dict[str, Any],
    preview_paths: Iterable[Path],
    generated: dict[str, Any],
    validated: dict[str, Any],
    failed: dict[str, Any],
    summary: dict[str, Any],
    expected_mode: str,
) -> dict[str, Any]:
    state_path = runtime_root / QUEUE_SAFETY_MANIFEST
    result: dict[str, Any] = {
        "safe": False,
        "snapshot_type": "",
        "takeover_id": "",
        "provenance_path": "",
        "verified_emergency_queue_progress": False,
        "failed_predicates": [],
    }
    if not state_path.is_file():
        result["failed_predicates"].append("active_campaign_state_exists")
        return result
    try:
        manifest = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        result["failed_predicates"].append("active_campaign_state_readable")
        return result
    if not isinstance(manifest, dict):
        result["failed_predicates"].append("active_campaign_state_object")
        return result
    snapshot_type = str(manifest.get("snapshot_type") or "").strip()
    takeover_id = str(manifest.get("takeover_id") or "").strip()
    result["snapshot_type"] = snapshot_type
    result["takeover_id"] = takeover_id
    manifest_profile = str(manifest.get("profile") or "").strip()
    if manifest_profile and manifest_profile != profile:
        result["failed_predicates"].append("active_campaign_profile_match")

    provenance_path: Path | None = None
    provenance: dict[str, Any] = {}
    if snapshot_type == "emergency_takeover":
        if manifest_profile != profile:
            result["failed_predicates"].append(
                "emergency_snapshot_profile_match"
            )
        if str(manifest.get("status") or "").strip() != "awaiting_preview_validation":
            result["failed_predicates"].append(
                "emergency_snapshot_awaiting_preview_validation"
            )
        if not takeover_id:
            result["failed_predicates"].append("emergency_takeover_id_present")
        source_files = manifest.get("files")
        intended_record = (
            source_files.get("intended_source")
            if isinstance(source_files, dict)
            else None
        )
        if not isinstance(intended_record, dict):
            result["failed_predicates"].append(
                "emergency_snapshot_queue_record_present"
            )
        else:
            if (
                str(intended_record.get("email_fingerprint") or "").strip()
                != str(queue_state["fingerprint"])
            ):
                result["failed_predicates"].append(
                    "emergency_snapshot_queue_fingerprint_match"
                )
            try:
                snapshot_queue_rows = int(intended_record.get("row_count"))
            except (TypeError, ValueError):
                snapshot_queue_rows = -1
            if snapshot_queue_rows != int(queue_state["row_count"]):
                result["failed_predicates"].append(
                    "emergency_snapshot_queue_count_match"
                )
        provenance_path = _resolve_runtime_path(
            runtime_root,
            manifest.get("provenance_manifest_path"),
        )
        result["provenance_path"] = str(provenance_path or "")
        if provenance_path is None or not provenance_path.is_file():
            result["failed_predicates"].append("emergency_provenance_exists")
        else:
            try:
                loaded = json.loads(provenance_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                result["failed_predicates"].append("emergency_provenance_readable")
            else:
                if not isinstance(loaded, dict):
                    result["failed_predicates"].append(
                        "emergency_provenance_object"
                    )
                else:
                    provenance = loaded
        if provenance:
            if (
                str(provenance.get("status") or "").strip()
                != "awaiting_preview_validation"
            ):
                result["failed_predicates"].append(
                    "emergency_provenance_awaiting_preview_validation"
                )
            if str(provenance.get("takeover_id") or "").strip() != takeover_id:
                result["failed_predicates"].append(
                    "emergency_provenance_takeover_id_match"
                )
            if str(provenance.get("profile") or "").strip() != profile:
                result["failed_predicates"].append(
                    "emergency_provenance_profile_match"
                )
            try:
                provenance_queue_rows = int(provenance.get("queue_row_count"))
            except (TypeError, ValueError):
                provenance_queue_rows = -1
            if provenance_queue_rows != int(queue_state["row_count"]):
                result["failed_predicates"].append(
                    "emergency_provenance_queue_count_match"
                )
            if (
                str(provenance.get("queue_fingerprint") or "").strip()
                != str(queue_state["fingerprint"])
            ):
                result["failed_predicates"].append(
                    "emergency_provenance_queue_fingerprint_match"
                )
            try:
                expected_mode = _profile_validation_mode(profile)
            except HandoffError:
                result["failed_predicates"].append(
                    "emergency_profile_validation_mode_known"
                )
            else:
                if (
                    str(provenance.get("preview_validation_mode") or "")
                    .strip()
                    .lower()
                    != expected_mode
                ):
                    result["failed_predicates"].append(
                        "emergency_provenance_validation_mode_match"
                    )


        queue_mismatch_predicates = {
            "emergency_snapshot_queue_fingerprint_match",
            "emergency_snapshot_queue_count_match",
            "emergency_provenance_queue_count_match",
            "emergency_provenance_queue_fingerprint_match",
        }

        if any(
            predicate in result["failed_predicates"]
            for predicate in queue_mismatch_predicates
        ):
            progress_match = _emergency_queue_progress_match(
                runtime_root,
                profile=profile,
                manifest=manifest,
                intended_record=(
                    intended_record
                    if isinstance(intended_record, dict)
                    else None
                ),
                provenance=provenance,
                queue_state=queue_state,
                generated=generated,
                validated=validated,
                failed=failed,
                summary=summary,
                expected_mode=expected_mode,
            )
            result["emergency_queue_progress"] = progress_match

            if progress_match["safe"]:
                result["failed_predicates"] = [
                    predicate
                    for predicate in result["failed_predicates"]
                    if predicate not in queue_mismatch_predicates
                ]
            else:
                for predicate in progress_match["failed_predicates"]:
                    decorated = f"emergency_queue_progress:{predicate}"
                    if decorated not in result["failed_predicates"]:
                        result["failed_predicates"].append(decorated)


    ownership_floor = max(
        state_path.stat().st_mtime_ns,
        provenance_path.stat().st_mtime_ns
        if provenance_path is not None and provenance_path.is_file()
        else 0,
    )
    for path in preview_paths:
        if path.is_file() and path.stat().st_mtime_ns < ownership_floor:
            result["failed_predicates"].append(
                f"preview_artifact_current:{path.name}"
            )
    result["safe"] = not result["failed_predicates"]
    progress = result.get("emergency_queue_progress")
    result["verified_emergency_queue_progress"] = bool(
        result["safe"]
        and isinstance(progress, dict)
        and progress.get("verified_emergency_queue_progress") is True
    )
    return result


def _controlled_sendgrid_preview_applicability(
    runtime_root: Path,
    *,
    profile: str,
    queue_path: Path,
    queue_state: dict[str, Any],
) -> dict[str, Any]:
    """Verify the isolated manual test lane without Fresh Cold lineage."""
    result: dict[str, Any] = {
        "safe": False,
        "snapshot_type": "controlled_test",
        "takeover_id": "",
        "provenance_path": "",
        "applicability": "controlled_profile",
        "verified_emergency_queue_progress": False,
        "failed_predicates": [],
    }
    failed = result["failed_predicates"]
    profiles = _profile_runtime_layout()
    config = profiles.get(profile)
    if profile != CONTROLLED_SENDGRID_PROFILE or not isinstance(config, dict):
        failed.append("controlled_profile_exact")
        return result

    exact_values = {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_controlled_test.csv",
        "log": "sendgrid_controlled_test_log.csv",
        "recipient_allowlist": CONTROLLED_SENDGRID_RECIPIENT,
    }
    for field, expected in exact_values.items():
        if str(config.get(field) or "").strip() != expected:
            failed.append(f"controlled_config_{field}_exact")
    for field in (
        "controlled_test",
        "dashboard_manual_only",
        "global_dedupe",
        "suppress_invalid",
    ):
        if config.get(field) is not True:
            failed.append(f"controlled_config_{field}_enabled")
    if config.get("repeat") is not False:
        failed.append("controlled_config_repeat_false")
    for field in ("max_total", "max_per_run", "max_submission_attempts"):
        try:
            value = int(config.get(field))
        except (TypeError, ValueError):
            value = -1
        if value != 1:
            failed.append(f"controlled_config_{field}_one")

    expected_queue = (
        runtime_root
        / "data/shards/recipients_sendgrid_controlled_test.csv"
    )
    if queue_path.resolve() != expected_queue.resolve():
        failed.append("controlled_queue_path_isolated")
    if int(queue_state.get("row_count") or 0) != 1:
        failed.append("controlled_queue_count_one")
    if set(queue_state.get("emails") or set()) != {
        CONTROLLED_SENDGRID_RECIPIENT
    }:
        failed.append("controlled_recipient_allowlist_exact")
    if int(queue_state.get("duplicate_count") or 0):
        failed.append("controlled_queue_unique_recipient")
    if int(queue_state.get("invalid_count") or 0):
        failed.append("controlled_queue_valid_recipient")

    suppression_paths = (
        runtime_root / "data/state/suppressed.csv",
        runtime_root / "data/state/unsubscribed.csv",
        runtime_root / "data/state/sendgrid_suppressions.csv",
    )
    suppressed: set[str] = set()
    for path in suppression_paths:
        if not path.is_file():
            failed.append(
                f"controlled_suppression_source_exists:{path.name}"
            )
            continue
        try:
            values, _diagnostics = load_suppression_email_tokens(path)
        except (OSError, UnicodeError, SuppressionSchemaError):
            failed.append(
                f"controlled_suppression_source_readable:{path.name}"
            )
            continue
        suppressed.update(values)
    queue_emails = set(queue_state.get("emails") or set())
    if queue_emails & suppressed:
        failed.append("controlled_queue_not_suppressed")

    log_path = runtime_root / "data/logs/sendgrid_controlled_test_log.csv"
    if not log_path.is_file():
        failed.append("controlled_log_exists")
    family_logs = _profile_log_paths(runtime_root, profiles, profile)
    if queue_emails & _authoritative_sent_emails(family_logs):
        failed.append("controlled_queue_no_sendgrid_family_sent_history")

    idempotency_path = runtime_root / "data/state/send_idempotency.sqlite3"
    if not idempotency_path.is_file():
        failed.append("controlled_idempotency_state_exists")
    elif _idempotency_overlap(
        runtime_root,
        profile,
        "sendgrid",
        queue_state,
    ):
        failed.append("controlled_queue_no_idempotency_overlap")

    result["failed_predicates"] = list(dict.fromkeys(failed))
    result["safe"] = not result["failed_predicates"]
    return result


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
    generated = _read_preview_csv(
        preview_path,
        required_fields=PREVIEW_GENERATED_REQUIRED_FIELDS,
        require_pass=False,
    )
    validated = _read_preview_csv(
        validated_path,
        required_fields=PREVIEW_VALIDATED_REQUIRED_FIELDS,
        require_pass=True,
    )
    failed = _read_preview_csv(
        failed_path,
        required_fields=PREVIEW_VALIDATED_REQUIRED_FIELDS,
        require_pass=False,
    )
    summary = _read_preview_summary(summary_path)
    try:
        expected_mode = _profile_validation_mode(profile)
    except HandoffError:
        expected_mode = ""
    if profile == CONTROLLED_SENDGRID_PROFILE:
        campaign = _controlled_sendgrid_preview_applicability(
            runtime_root,
            profile=profile,
            queue_path=queue_path,
            queue_state=queue_state,
        )
    else:
        campaign = _preview_campaign_match(
            runtime_root,
            profile=profile,
            queue_state=queue_state,
            preview_paths=(preview_path, validated_path, failed_path, summary_path),
            generated=generated,
            validated=validated,
            failed=failed,
            summary=summary,
            expected_mode=expected_mode,
        )
    failed_predicates: list[str] = []
    for label, report in (
        ("generated", generated),
        ("validated", validated),
        ("failed", failed),
    ):
        if not report["exists"]:
            failed_predicates.append(f"{label}_file_exists")
        if report["parse_error"]:
            failed_predicates.append(
                f"{label}_csv_parse:{report['parse_error']}"
            )
        if report["missing_fields"]:
            failed_predicates.append(
                f"{label}_required_columns:{','.join(report['missing_fields'])}"
            )
        for metric, predicate in (
            ("extra_column_rows", "no_extra_columns"),
            ("blank_email_rows", "no_blank_emails"),
            ("malformed_email_rows", "valid_emails"),
            ("conflicting_email_rows", "email_authoremail_match"),
            ("duplicate_email_rows", "unique_emails"),
        ):
            if int(report[metric]):
                failed_predicates.append(
                    f"{label}_{predicate}:{report[metric]}"
                )
    if int(validated["non_pass_rows"]):
        failed_predicates.append(
            f"validated_all_rows_pass:{validated['non_pass_rows']}"
        )
    if int(generated["row_count"]) != queue_rows:
        failed_predicates.append("generated_row_count_matches_queue")
    if int(validated["row_count"]) != queue_rows:
        failed_predicates.append("validated_row_count_matches_queue")
    if set(generated["emails"]) != queue_emails:
        failed_predicates.append("generated_email_set_matches_queue")
    if set(validated["emails"]) != queue_emails:
        failed_predicates.append("validated_email_set_matches_queue")
    queue_fingerprint = str(queue_state["fingerprint"])
    if str(generated["fingerprint"]) != queue_fingerprint:
        failed_predicates.append("generated_fingerprint_matches_queue")
    if str(validated["fingerprint"]) != queue_fingerprint:
        failed_predicates.append("validated_fingerprint_matches_queue")
    if int(failed["row_count"]) != 0:
        failed_predicates.append("failed_preview_has_zero_rows")
    if not summary["exists"]:
        failed_predicates.append("summary_file_exists")
    if summary["parse_error"]:
        failed_predicates.append(f"summary_parse:{summary['parse_error']}")
    if summary["missing_fields"]:
        failed_predicates.append(
            f"summary_fields_present:{','.join(summary['missing_fields'])}"
        )
    if summary["duplicate_fields"]:
        failed_predicates.append(
            f"summary_fields_unique:{','.join(summary['duplicate_fields'])}"
        )
    summary_counts = dict(summary["counts"])
    if summary_counts:
        if summary_counts["total"] != int(generated["row_count"]):
            failed_predicates.append("summary_total_matches_generated")
        if summary_counts["total"] != int(validated["row_count"]):
            failed_predicates.append("summary_total_matches_validated")
        if summary_counts["passed"] != int(validated["row_count"]):
            failed_predicates.append("summary_passed_matches_validated")
        if summary_counts["failed"] != int(failed["row_count"]):
            failed_predicates.append("summary_failed_matches_failed_preview")
        if summary_counts["failed"] != 0:
            failed_predicates.append("summary_failed_is_zero")
    if summary["mode"] and summary["mode"] != expected_mode:
        failed_predicates.append("summary_pitch_mode_matches_profile")
    if not expected_mode:
        failed_predicates.append("profile_validation_mode_known")
    failed_predicates.extend(campaign["failed_predicates"])
    verified_emergency_queue_progress = bool(
        campaign.get("verified_emergency_queue_progress")
    )
    if verified_emergency_queue_progress:
        progress_compatible_predicates = {
            "generated_row_count_matches_queue",
            "validated_row_count_matches_queue",
            "generated_email_set_matches_queue",
            "validated_email_set_matches_queue",
            "generated_fingerprint_matches_queue",
            "validated_fingerprint_matches_queue",
        }
        failed_predicates = [
            predicate
            for predicate in failed_predicates
            if predicate not in progress_compatible_predicates
        ]
    failed_predicates = list(dict.fromkeys(failed_predicates))
    exact_match = not failed_predicates
    return {
        "safe": exact_match,
        "profile": profile,
        "queue_path": str(queue_path),
        "queue_row_count": queue_rows,
        "queue_fingerprint": queue_state["fingerprint"],
        "preview_path": str(preview_path),
        "preview_row_count": generated["row_count"],
        "preview_fingerprint": generated["fingerprint"],
        "validated_path": str(validated_path),
        "validated_row_count": validated["row_count"],
        "validated_fingerprint": validated["fingerprint"],
        "failed_path": str(failed_path),
        "failed_row_count": failed["row_count"] if failed["exists"] else -1,
        "summary_path": str(summary_path),
        "summary_counts": summary_counts,
        "summary_mode": summary["mode"],
        "expected_summary_mode": expected_mode,
        "verified_emergency_queue_progress": (
            verified_emergency_queue_progress
        ),
        "generated_validation": {
            key: value
            for key, value in generated.items()
            if key not in {"emails", "ordered_emails", "rows_by_email"}
        },
        "validated_validation": {
            key: value
            for key, value in validated.items()
            if key not in {"emails", "ordered_emails", "rows_by_email"}
        },
        "failed_validation": {
            key: value
            for key, value in failed.items()
            if key not in {"emails", "ordered_emails", "rows_by_email"}
        },
        "campaign_match": campaign,
        "failed_predicates": failed_predicates,
        "message": (
            ""
            if exact_match
            else (
                f"profile={profile} queue={queue_path} queue_rows={queue_rows} "
                f"queue_fingerprint={queue_state['fingerprint']} preview={preview_path} "
                f"preview_rows={generated['row_count']} "
                f"preview_fingerprint={generated['fingerprint']} "
                f"validated={validated_path} validated_rows={validated['row_count']} "
                f"validated_fingerprint={validated['fingerprint']} "
                f"failed={failed_path} failed_rows="
                f"{failed['row_count'] if failed['exists'] else -1} "
                f"summary={summary_path} summary_mode={summary['mode'] or 'missing'} "
                f"failed_predicates={','.join(failed_predicates)}"
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
        source_lineage_applicable = profile != CONTROLLED_SENDGRID_PROFILE
        duplicate_across_profiles += len(all_queue_emails & queue_emails)
        all_queue_emails.update(queue_emails)
        duplicate_rows += int(queue_state["duplicate_count"])
        invalid_rows += int(queue_state["invalid_count"])
        if source_lineage_applicable:
            outside_checked = (
                queue_emails - checked_emails
                if checked_emails
                else set(queue_emails)
            )
            outside_intended = (
                queue_emails - intended_emails
                if intended_emails
                else set(queue_emails)
            )
            reject_overlap = queue_emails & reject_emails
        else:
            outside_checked = set()
            outside_intended = set()
            reject_overlap = set()
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
        if source_lineage_applicable and source_fingerprint_mismatches:
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
                "source_lineage_applicable": source_lineage_applicable,
                "source_fingerprint_mismatches": (
                    list(source_fingerprint_mismatches)
                    if source_lineage_applicable
                    else []
                ),
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


def preflight_queue_safety(
    runtime_root: Path,
    *,
    profile: str,
) -> dict[str, Any]:
    """Return the same final queue-safety decision used by activation."""
    safety = recompute_queue_safety(runtime_root)
    matching = [
        report
        for report in safety.get("profiles", [])
        if isinstance(report, dict)
        and str(report.get("profile") or "").strip() == profile
    ]
    if len(matching) != 1:
        return {
            "safe": False,
            "profile": profile,
            "verified_emergency_queue_progress": False,
            "failed_predicates": ["active_profile_report_present"],
            "unsafe_reasons": list(safety.get("unsafe_reasons") or []),
        }
    preview = matching[0].get("preview")
    if not isinstance(preview, dict):
        return {
            "safe": False,
            "profile": profile,
            "verified_emergency_queue_progress": False,
            "failed_predicates": ["profile_preview_report_present"],
            "unsafe_reasons": list(safety.get("unsafe_reasons") or []),
        }
    return {
        "safe": bool(safety.get("safe")),
        "profile": profile,
        "verified_emergency_queue_progress": bool(
            preview.get("verified_emergency_queue_progress")
        ),
        "failed_predicates": list(preview.get("failed_predicates") or []),
        "unsafe_reasons": list(safety.get("unsafe_reasons") or []),
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


def _validate_bundle_metadata_hint(
    manifest: dict[str, Any], bundled_authority: dict[str, Any]
) -> None:
    for field in (
        "bundle_id",
        "source_machine",
        "target_machine",
        "expected_git_commit",
        "runtime_manifest_hash",
    ):
        value = manifest.get(field)
        if not isinstance(value, str) or not value or value != bundled_authority.get(field):
            raise HandoffError(f"Bundle {field} metadata mismatch")
    if not BUNDLE_ID_RE.fullmatch(manifest["bundle_id"]):
        raise HandoffError("Bundle identity is unsafe")
    if (
        manifest["source_machine"] not in MACHINES
        or manifest["target_machine"] not in MACHINES
        or manifest["source_machine"] == manifest["target_machine"]
    ):
        raise HandoffError("Bundle machine direction is invalid")
    if not FULL_GIT_SHA_RE.fullmatch(manifest["expected_git_commit"]):
        raise HandoffError("Bundle expected Git commit is malformed")
    if not SHA256_RE.fullmatch(manifest["runtime_manifest_hash"]):
        raise HandoffError("Bundle runtime manifest hash is malformed")
    source_generation = manifest.get("source_generation")
    if (
        isinstance(source_generation, bool)
        or not isinstance(source_generation, int)
        or source_generation < 1
        or source_generation != bundled_authority.get("generation")
    ):
        raise HandoffError("Bundle generation metadata mismatch")
    if bundled_authority.get("status") != "handoff_in_progress":
        raise HandoffError("Bundled source authority is not handoff_in_progress")
    if bundled_authority.get("authorized_machine") != manifest.get("source_machine"):
        raise HandoffError("Bundled authority is not assigned to its source")


def _receive_generation(source_generation: int, floor: int) -> int:
    if floor == 0:
        return max(1, source_generation)
    return max(source_generation, floor) + 1


def _receive_authority_payload(
    transaction: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    return {
        "authorized_machine": transaction["machine"],
        "generation": transaction["authority_generation"],
        "bundle_id": transaction["bundle_id"],
        "source_machine": transaction["source_machine"],
        "target_machine": transaction["target_machine"],
        "created_utc": transaction["authority_created_utc"],
        "expected_git_commit": transaction["destination_commit"],
        "runtime_manifest_hash": manifest["runtime_manifest_hash"],
        "status": "import_in_progress",
    }


def _active_receive_transactions(repo: Path) -> list[Path]:
    directory = _private_handoff_layout(repo)["transactions"]
    active: list[Path] = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise HandoffError(f"Unsafe receive transaction entry: {path}")
        payload = _load_receive_transaction(path)
        if payload.get("status") not in {"completed", "rolled_back"}:
            active.append(path)
    return active


def _assert_staging_empty(repo: Path) -> None:
    staging = _private_handoff_layout(repo)["staging"]
    residue = list(staging.iterdir())
    if residue:
        raise HandoffError("Receive staging contains residue from a partial transaction")


def _validate_resume_commit(
    interrupted_commit: str,
    current_commit: str,
    compatibility: dict[str, Any],
) -> None:
    if interrupted_commit == current_commit:
        return
    approved = compatibility.get("approved_interrupted_destination_commits", [])
    if compatibility.get("destination_commit") != current_commit or interrupted_commit not in approved:
        raise HandoffError(
            "Interrupted receive commit is not explicitly approved for the current code"
        )


def _prepare_receive_transaction(
    repo: Path,
    bundle: Path,
    manifest: dict[str, Any],
    bundled_authority: dict[str, Any],
    compatibility: dict[str, Any],
    *,
    identity: str,
    resume_expected_bundle_sha256: str | None,
    resume_expected_baseline_fingerprint: str | None,
) -> tuple[dict[str, Any], bool]:
    layout = _private_handoff_layout(repo)
    _assert_staging_empty(repo)
    bundle_id = str(manifest["bundle_id"])
    bundle_sha256 = sha256_file(bundle)
    baseline = _runtime_baseline_fingerprint(repo)
    current_commit = git(repo, "rev-parse", "HEAD")
    transaction_path = _transaction_path(repo, bundle_id)
    backup_path = layout["backups"] / f"pre_import_{bundle_id}.tgz"
    if backup_path.exists() or backup_path.is_symlink():
        raise HandoffError("Receive transaction has a partial or conflicting backup")
    try:
        current_authority = load_authority(repo)
    except AuthorityError:
        current_authority = None

    if transaction_path.exists() or transaction_path.is_symlink():
        transaction = _load_receive_transaction(transaction_path)
        expected = {
            "bundle_id": bundle_id,
            "bundle_sha256": bundle_sha256,
            "manifest_hash": manifest["runtime_manifest_hash"],
            "source_machine": manifest["source_machine"],
            "target_machine": manifest["target_machine"],
            "source_generation": manifest["source_generation"],
            "runtime_baseline_fingerprint": baseline,
            "machine": identity,
        }
        for field, value in expected.items():
            if transaction.get(field) != value:
                raise HandoffError(f"Interrupted receive transaction changed: {field}")
        if transaction.get("backup_created") or transaction.get("replacement_started"):
            raise HandoffError("Interrupted receive already reached mutation state")
        authority_missing = current_authority is None
        if authority_missing:
            if transaction.get("status") != "prepared":
                raise HandoffError("Interrupted receive authority is missing")
        else:
            if current_authority.get("status") != "import_in_progress":
                raise HandoffError("Interrupted receive authority status changed")
            if canonical_hash(current_authority) != transaction.get("authority_fingerprint"):
                raise HandoffError("Interrupted receive authority changed")
        _validate_resume_commit(
            str(transaction["destination_commit"]), current_commit, compatibility
        )
        if current_commit != transaction["destination_commit"]:
            transaction["interrupted_destination_commit"] = transaction[
                "destination_commit"
            ]
            transaction["destination_commit"] = current_commit
        if authority_missing:
            # A crash after the prepared transaction was made durable but before
            # the disabled authority was written is safe to resume. Keep the
            # transaction prepared until the authority write has completed.
            authority_payload = _receive_authority_payload(transaction, manifest)
            transaction["authority_fingerprint"] = canonical_hash(authority_payload)
            transaction["updated_utc"] = utc_now()
            _write_receive_transaction(repo, transaction)
            write_authority(repo, authority_payload)
        # If authority already exists, preserve it exactly. In particular, a
        # compatible code update must not rewrite the original interrupted
        # authority commit before the final active authority write.
        transaction["status"] = "import_in_progress"
        transaction["resume_count"] = int(transaction.get("resume_count", 0)) + 1
        transaction["updated_utc"] = utc_now()
        _write_receive_transaction(repo, transaction)
        return transaction, True

    active_transactions = _active_receive_transactions(repo)
    if active_transactions:
        raise HandoffError("A different interrupted receive transaction already exists")

    legacy_resume = bool(
        current_authority
        and current_authority.get("status") == "import_in_progress"
        and current_authority.get("target_machine") == identity
    )
    if legacy_resume:
        expected_bundle = (
            resume_expected_bundle_sha256
            or os.environ.get(INTERRUPTED_BUNDLE_SHA_ENV, "")
        ).strip().lower()
        expected_baseline = (
            resume_expected_baseline_fingerprint
            or os.environ.get(INTERRUPTED_BASELINE_ENV, "")
        ).strip().lower()
        if not SHA256_RE.fullmatch(expected_bundle) or expected_bundle != bundle_sha256:
            raise HandoffError(
                "Legacy interrupted receive requires the exact reviewed bundle SHA-256"
            )
        if not SHA256_RE.fullmatch(expected_baseline) or expected_baseline != baseline:
            raise HandoffError(
                "Legacy interrupted receive requires the exact reviewed runtime baseline fingerprint"
            )
        if (
            current_authority.get("generation") != 1
            or current_authority.get("authorized_machine") != identity
            or current_authority.get("source_machine") != manifest["source_machine"]
            or current_authority.get("runtime_manifest_hash") != "import-not-verified"
            or load_generation_floor(repo) != 0
        ):
            raise HandoffError("Legacy interrupted receive authority is not resumable")
        _validate_resume_commit(
            str(current_authority.get("expected_git_commit")),
            current_commit,
            compatibility,
        )
        generation = 1
        interrupted_commit = current_authority["expected_git_commit"]
        legacy_authority_fingerprint = canonical_hash(current_authority)
    else:
        if current_authority and current_authority.get("status") == "active":
            raise HandoffError("Target authority is active; refusing runtime replacement")
        generation = _receive_generation(
            int(manifest["source_generation"]), load_generation_floor(repo)
        )
        interrupted_commit = current_commit
        legacy_authority_fingerprint = ""

    transaction = {
        "schema_version": RECEIVE_TRANSACTION_SCHEMA_VERSION,
        "transaction_id": str(uuid.uuid4()),
        "status": "prepared",
        "machine": identity,
        "authority_generation": generation,
        "authority_created_utc": utc_now(),
        "interrupted_destination_commit": interrupted_commit,
        "destination_commit": current_commit,
        "bundle_id": bundle_id,
        "bundle_sha256": bundle_sha256,
        "manifest_hash": manifest["runtime_manifest_hash"],
        "source_machine": manifest["source_machine"],
        "target_machine": manifest["target_machine"],
        "source_generation": manifest["source_generation"],
        "source_commit": manifest["expected_git_commit"],
        "runtime_baseline_fingerprint": baseline,
        "backup_created": False,
        "replacement_started": False,
        "replacement_completed": False,
        "legacy_resume": legacy_resume,
        "legacy_authority_fingerprint": legacy_authority_fingerprint,
        "resume_count": 1 if legacy_resume else 0,
        "created_utc": utc_now(),
        "updated_utc": utc_now(),
    }
    if legacy_resume:
        # The old receiver wrote a placeholder disabled authority before it
        # failed. Preserve that exact state until activation; the reviewed SHA,
        # baseline and compatibility mapping bind it to this transaction.
        transaction["authority_fingerprint"] = legacy_authority_fingerprint
        _write_receive_transaction(repo, transaction)
    else:
        authority_payload = _receive_authority_payload(transaction, manifest)
        transaction["authority_fingerprint"] = canonical_hash(authority_payload)
        _write_receive_transaction(repo, transaction)
        write_authority(repo, authority_payload)
    transaction["status"] = "import_in_progress"
    transaction["updated_utc"] = utc_now()
    _write_receive_transaction(repo, transaction)
    return transaction, legacy_resume


def _archive_existing_runtime(repo: Path, bundle_id: str) -> Path:
    backup_dir = _private_handoff_layout(repo)["backups"]
    destination = backup_dir / f"pre_import_{bundle_id}.tgz"
    if destination.exists() or destination.is_symlink():
        raise HandoffError(f"Target backup already exists: {destination}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise HandoffError("Secure runtime backups require O_NOFOLLOW support")
    descriptor = os.open(destination, flags | nofollow, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            with tarfile.open(fileobj=handle, mode="w:gz") as archive:
                for root_name in ("data", "_important"):
                    root = repo / root_name
                    if root.exists():
                        archive.add(
                            root,
                            arcname=root_name,
                            filter=lambda member: (
                                None
                                if _contains_secret_name(PurePosixPath(member.name))
                                else member
                            ),
                        )
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        _fsync_directory(backup_dir)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    _validate_private_file(destination)
    _fsync_directory(backup_dir)
    return destination


def _atomic_replace_runtime(repo: Path, extracted_runtime: Path) -> None:
    with _private_staging_directory(repo, prefix="swap-") as transaction:
        moved_old: list[tuple[Path, Path]] = []
        installed: list[Path] = []
        try:
            for root_name in ("data", "_important"):
                source = extracted_runtime / root_name
                source.mkdir(parents=True, exist_ok=True, mode=0o700)
                target = repo / root_name
                if target.is_symlink():
                    raise HandoffError(f"Runtime destination is a symlink: {target}")
                if source.stat().st_dev != repo.stat().st_dev:
                    raise HandoffError("Runtime staging and destination cross filesystems")
                old = transaction / f"{root_name}.old"
                if target.exists():
                    os.replace(target, old)
                    moved_old.append((old, target))
                os.replace(source, target)
                installed.append(target)
            _fsync_directory(transaction)
            _fsync_directory(extracted_runtime)
            _fsync_directory(repo)
        except Exception:
            for target in reversed(installed):
                if target.exists():
                    shutil.rmtree(target)
            for old, target in reversed(moved_old):
                if old.exists():
                    os.replace(old, target)
            _fsync_directory(transaction)
            _fsync_directory(repo)
            raise


def _restore_runtime_backup(repo: Path, backup: Path) -> None:
    with _private_staging_directory(repo, prefix="recover-") as staging:
        with _open_private_tar(backup) as archive:
            members = archive.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] not in {"data", "_important"}
                    or _contains_secret_name(path)
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
    expected_git_commit: str | None = None,
    generation: int | None = None,
    created_utc: str | None = None,
) -> dict[str, Any]:
    identity = machine or current_machine()
    floor = load_generation_floor(repo)
    source_generation = int(bundled_authority["generation"])
    new_generation = generation or _receive_generation(source_generation, floor)
    if new_generation < floor:
        raise HandoffError("Import activation generation is below the local floor")
    active = {
        **bundled_authority,
        "authorized_machine": identity,
        "generation": new_generation,
        "created_utc": created_utc or utc_now(),
        "expected_git_commit": expected_git_commit
        or bundled_authority["expected_git_commit"],
        "status": ACTIVE_STATUS,
    }
    # Advancing the floor first can only leave the target disabled if the final
    # authority write fails. The active authority is the last durable write.
    write_generation_floor(repo, new_generation, active["bundle_id"])
    write_authority(repo, active)
    return active


def import_runtime(
    repo: Path,
    bundle: Path,
    *,
    machine: str | None = None,
    replace_hook=None,
    resume_expected_bundle_sha256: str | None = None,
    resume_expected_baseline_fingerprint: str | None = None,
) -> dict[str, Any]:
    identity = machine or current_machine()
    assert_processes_stopped(repo)
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise HandoffError("Tracked target worktree is dirty")
    layout = _private_handoff_layout(repo)
    manifest_hint, authority_hint = read_bundle_metadata(bundle)
    _validate_bundle_metadata_hint(manifest_hint, authority_hint)
    if manifest_hint.get("target_machine") != identity:
        raise HandoffError(
            f"Bundle targets {manifest_hint.get('target_machine')}, not {identity}"
        )
    bundle_id = str(manifest_hint.get("bundle_id") or "")
    used = _read_used_bundles(repo)
    if bundle_id in used:
        raise HandoffError(f"Bundle has already been used: {bundle_id}")
    floor = load_generation_floor(repo)
    source_generation = manifest_hint.get("source_generation")
    if (
        isinstance(source_generation, bool)
        or not isinstance(source_generation, int)
        or source_generation < floor
    ):
        raise HandoffError(
            f"Stale generation {source_generation!r}; local floor is {floor}"
        )
    compatibility = validate_bundle_commit_compatibility(
        repo,
        manifest_hint,
        authority_hint,
        machine=identity,
    )
    transaction, resumed = _prepare_receive_transaction(
        repo,
        bundle,
        manifest_hint,
        authority_hint,
        compatibility,
        identity=identity,
        resume_expected_bundle_sha256=resume_expected_bundle_sha256,
        resume_expected_baseline_fingerprint=resume_expected_baseline_fingerprint,
    )
    backup: Path | None = None
    replacement_attempted = False
    previous_used = set(used)
    stage = "pre_extraction"
    try:
        disk_space = _assert_import_disk_space(repo, bundle)
        with _private_staging_directory(repo, prefix="receive-") as staging:
            stage = "verification"
            manifest, bundled_authority, verification = extract_and_verify(bundle, staging)
            verified_compatibility = validate_bundle_commit_compatibility(
                repo,
                manifest,
                bundled_authority,
                machine=identity,
            )
            if verified_compatibility != compatibility:
                raise HandoffError("Commit compatibility changed during receive")
            if sha256_file(bundle) != transaction["bundle_sha256"]:
                raise HandoffError("Bundle SHA-256 changed during receive")
            if manifest["runtime_manifest_hash"] != transaction["manifest_hash"]:
                raise HandoffError("Runtime manifest hash changed during receive")
            safety = recompute_queue_safety(staging / RUNTIME_ROOT)
            if not safety["safe"]:
                raise HandoffError(
                    "Queue safety failure: " + ", ".join(safety["unsafe_reasons"])
                )
            if _runtime_baseline_fingerprint(repo) != transaction[
                "runtime_baseline_fingerprint"
            ]:
                raise HandoffError("Target runtime baseline changed during receive")
            fsync_runtime(staging / RUNTIME_ROOT)
            stage = "backup"
            backup = _archive_existing_runtime(repo, bundle_id)
            transaction["backup_created"] = True
            transaction["backup_path"] = backup.relative_to(repo).as_posix()
            transaction["backup_sha256"] = sha256_file(backup)
            transaction["updated_utc"] = utc_now()
            _write_receive_transaction(repo, transaction)
            stage = "replacement"
            replacement_attempted = True
            transaction["replacement_started"] = True
            transaction["updated_utc"] = utc_now()
            _write_receive_transaction(repo, transaction)
            if replace_hook is not None:
                replace_hook(repo, staging / RUNTIME_ROOT)
            else:
                _atomic_replace_runtime(repo, staging / RUNTIME_ROOT)
            transaction["replacement_completed"] = True
            transaction["installed_runtime_fingerprint"] = _runtime_baseline_fingerprint(
                repo
            )
            transaction["status"] = "ready_to_activate"
            transaction["updated_utc"] = utc_now()
            _write_receive_transaction(repo, transaction)
            stage = "activation"
            used.add(bundle_id)
            _write_used_bundles(repo, used)
            predicted_authority = {
                **bundled_authority,
                "authorized_machine": identity,
                "generation": transaction["authority_generation"],
                "created_utc": transaction["authority_created_utc"],
                "expected_git_commit": compatibility["destination_commit"],
                "status": ACTIVE_STATUS,
            }
            result = {
                "bundle_id": bundle_id,
                "backup": str(backup),
                "authority": predicted_authority,
                "verification": verification,
                "queue_safety": safety,
                "disk_space": disk_space,
                "resumed": resumed,
                "transaction_id": transaction["transaction_id"],
                "sender_started": False,
            }
            _atomic_private_json_write(layout["root"] / LAST_IMPORT_NAME, result)
            transaction["status"] = "completed"
            transaction["updated_utc"] = utc_now()
            _write_receive_transaction(repo, transaction)
            active = activate_import(
                repo,
                bundled_authority,
                machine=identity,
                expected_git_commit=compatibility["destination_commit"],
                generation=transaction["authority_generation"],
                created_utc=transaction["authority_created_utc"],
            )
            return {
                **result,
                "authority": active,
                "commit_compatibility": compatibility,
            }
    except Exception:
        if replacement_attempted and backup is not None:
            try:
                _restore_runtime_backup(repo, backup)
                _write_used_bundles(repo, previous_used)
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
            transaction["status"] = "import_failed"
            transaction["rollback_completed"] = True
            mark_target_disabled(
                repo,
                status="import_failed",
                metadata=manifest_hint,
                machine=identity,
            )
        else:
            transaction["status"] = "import_in_progress"
        transaction["last_failure_stage"] = stage
        transaction["updated_utc"] = utc_now()
        _write_receive_transaction(repo, transaction)
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
    other = _default_peer_machine(identity)
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
    backup_dir = _private_handoff_layout(repo)["backups"]
    candidates = sorted(backup_dir.glob("pre_import_*.tgz"), key=lambda p: p.stat().st_mtime)
    selected = backup or (candidates[-1] if candidates else None)
    if selected is None or not selected.is_file():
        raise HandoffError("No runtime backup is available for rollback")
    _validate_private_file(selected)
    mark_target_disabled(repo, status="rollback_in_progress")
    with _private_staging_directory(repo, prefix="rollback-") as staging:
        with _open_private_tar(selected) as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] not in {"data", "_important"}
                    or _contains_secret_name(path)
                ):
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
    parser.add_argument("--machine", choices=tuple(sorted(MACHINES)))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    export_parser = commands.add_parser("export")
    export_parser.add_argument(
        "--target",
        required=True,
        choices=tuple(sorted(MACHINES)),
    )
    export_parser.add_argument("--output-dir", type=Path, default=Path("runtime_handoff_bundles"))
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("bundle", type=Path)
    import_parser = commands.add_parser("import")
    import_parser.add_argument("bundle", type=Path)
    import_parser.add_argument("--resume-expected-bundle-sha256")
    import_parser.add_argument("--resume-expected-runtime-baseline-sha256")
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
                    verify_runtime_bundle(
                        repo,
                        args.bundle.resolve(),
                        machine=args.machine,
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif args.command == "import":
            print(
                json.dumps(
                    import_runtime(
                        repo,
                        args.bundle.resolve(),
                        machine=args.machine,
                        resume_expected_bundle_sha256=(
                            args.resume_expected_bundle_sha256
                        ),
                        resume_expected_baseline_fingerprint=(
                            args.resume_expected_runtime_baseline_sha256
                        ),
                    ),
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
