"""Persistent guard for interrupted multi-file dispatch confirmation."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import settings
from durable_io import atomic_write_json, durable_replace, secure_private_dir, secure_private_file


JOURNAL_FILENAME = "dispatch_transaction_journal.json"
INCOMPLETE_STATUSES = {"prepared", "replacing", "committing"}


class DispatchTransactionError(RuntimeError):
    """A prior dispatch transaction did not reach a terminal state."""


def iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def journal_path(state_dir: Path | None = None) -> Path:
    return Path(state_dir or settings.STATE_DIR) / JOURNAL_FILENAME


def load_dispatch_transaction_journal(path: Path | None = None) -> dict[str, Any]:
    target = Path(path or journal_path())
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise DispatchTransactionError(f"Dispatch transaction journal is unreadable: {target}") from exc
    if not isinstance(payload, dict):
        raise DispatchTransactionError(f"Dispatch transaction journal is malformed: {target}")
    return payload


def active_dispatch_transaction(path: Path | None = None) -> dict[str, Any]:
    payload = load_dispatch_transaction_journal(path)
    status = str(payload.get("status") or "").strip().lower()
    return payload if status in INCOMPLETE_STATUSES else {}


def assert_no_incomplete_dispatch_transaction(path: Path | None = None) -> None:
    payload = active_dispatch_transaction(path)
    if not payload:
        return
    transaction_id = str(payload.get("transaction_id") or "unknown")
    phase = str(payload.get("phase") or payload.get("status") or "unknown")
    raise DispatchTransactionError(
        "An interrupted dispatch confirmation is unresolved "
        f"(transaction={transaction_id}, phase={phase}). "
        "Do not send or confirm another campaign until it is recovered."
    )


def write_dispatch_transaction_journal(
    payload: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    target = Path(path or journal_path())
    document = dict(payload)
    document["updated_at_utc"] = iso_utc()
    atomic_write_json(target, document, mode=0o600)
    return document


def begin_dispatch_transaction(
    *,
    transaction_id: str,
    preview_id: str,
    run_id: str,
    backup_dir: Path,
    queue_paths: list[Path],
    campaign_type: str,
    recovery_files: list[dict[str, Any]] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    assert_no_incomplete_dispatch_transaction(path)
    now = iso_utc()
    return write_dispatch_transaction_journal(
        {
            "schema_version": 1,
            "transaction_id": transaction_id,
            "preview_id": preview_id,
            "run_id": run_id,
            "campaign_type": campaign_type,
            "status": "prepared",
            "phase": "prepared",
            "created_at_utc": now,
            "updated_at_utc": now,
            "backup_dir": str(backup_dir),
            "queue_paths": [str(item) for item in queue_paths],
            "recovery_files": list(recovery_files or []),
            "replaced_paths": [],
            "error": "",
        },
        path,
    )


def update_dispatch_transaction(
    *,
    status: str,
    phase: str,
    path: Path | None = None,
    replaced_paths: list[str] | None = None,
    error: str = "",
) -> dict[str, Any]:
    payload = load_dispatch_transaction_journal(path)
    if not payload:
        return {}
    payload["status"] = status
    payload["phase"] = phase
    if replaced_paths is not None:
        payload["replaced_paths"] = list(replaced_paths)
    if error:
        payload["error"] = error[:2000]
    return write_dispatch_transaction_journal(payload, path)


def mark_dispatch_transaction_terminal(
    status: str,
    *,
    path: Path | None = None,
    error: str = "",
) -> dict[str, Any]:
    if status not in {"committed", "rolled_back"}:
        raise ValueError(f"Unsupported terminal dispatch status: {status}")
    return update_dispatch_transaction(
        status=status,
        phase=status,
        path=path,
        error=error,
    )


def create_recovery_file_backups(
    paths: list[Path],
    backup_dir: Path,
) -> list[dict[str, Any]]:
    """Persist pre-transaction copies of non-queue state needed for rollback."""
    recovery_dir = backup_dir / "recovery_files"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    secure_private_dir(recovery_dir, strict=True)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source in enumerate(paths, start=1):
        source = Path(source).expanduser().resolve()
        key = str(source)
        if key in seen:
            continue
        seen.add(key)
        existed = source.is_file() and not source.is_symlink()
        backup = recovery_dir / f"{index:03d}_{source.name}"
        record: dict[str, Any] = {
            "path": str(source),
            "existed": bool(existed),
            "backup_path": str(backup) if existed else "",
            "sqlite": bool(source.suffix.lower() in {".sqlite", ".sqlite3", ".db"}),
        }
        if existed:
            if record["sqlite"]:
                source_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
                try:
                    backup_conn = sqlite3.connect(str(backup))
                    try:
                        source_conn.backup(backup_conn)
                    finally:
                        backup_conn.close()
                finally:
                    source_conn.close()
                secure_private_file(backup, strict=True)
            else:
                with source.open("rb") as src, tempfile.NamedTemporaryFile(
                    "wb",
                    dir=recovery_dir,
                    prefix=f".{backup.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    shutil.copyfileobj(src, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    durable_replace(temporary, backup, mode=0o600)
                finally:
                    temporary.unlink(missing_ok=True)
        records.append(record)
    return records


def _restore_recovery_file(record: dict[str, Any], backup_dir: Path) -> str:
    target = Path(str(record.get("path") or "")).expanduser()
    if not target.is_absolute():
        raise DispatchTransactionError(f"Unsafe recovery target path: {target}")
    existed = bool(record.get("existed"))
    if not existed:
        target.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
        return str(target)

    backup_text = str(record.get("backup_path") or "").strip()
    backup = Path(backup_text).expanduser()
    if not backup.is_absolute():
        raise DispatchTransactionError(f"Unsafe recovery backup path: {backup}")
    backup_root = backup_dir.resolve()
    try:
        backup.resolve().relative_to(backup_root)
    except ValueError as exc:
        raise DispatchTransactionError(f"Recovery backup escapes transaction directory: {backup}") from exc
    if not backup.is_file() or backup.is_symlink():
        raise DispatchTransactionError(f"Required recovery backup is missing: {backup}")

    target.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("rb") as src, tempfile.NamedTemporaryFile(
        "wb",
        dir=target.parent,
        prefix=f".{target.name}.recovery.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        shutil.copyfileobj(src, handle)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        durable_replace(temporary, target, mode=0o600)
    finally:
        temporary.unlink(missing_ok=True)
    if bool(record.get("sqlite")):
        for suffix in ("-wal", "-shm", "-journal"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
    return str(target)


def rollback_incomplete_dispatch_transaction(
    path: Path | None = None,
) -> dict[str, Any]:
    target = Path(path or journal_path())
    payload = active_dispatch_transaction(target)
    if not payload:
        raise DispatchTransactionError("No incomplete dispatch transaction requires recovery.")

    backup_dir = Path(str(payload.get("backup_dir") or "")).expanduser()
    queue_paths = [Path(str(item)).expanduser() for item in payload.get("queue_paths", [])]
    if not backup_dir.is_absolute() or not queue_paths:
        raise DispatchTransactionError("Dispatch recovery journal has invalid backup or queue paths.")
    if not backup_dir.is_dir() or backup_dir.is_symlink():
        raise DispatchTransactionError(f"Dispatch backup directory is unavailable: {backup_dir}")

    restored: list[str] = []
    for queue_path in queue_paths:
        if not queue_path.is_absolute() or queue_path.name in {"", ".", ".."}:
            raise DispatchTransactionError(f"Unsafe queue path in dispatch recovery journal: {queue_path}")
        backup = backup_dir / queue_path.name
        if not backup.is_file() or backup.is_symlink():
            raise DispatchTransactionError(f"Required dispatch backup is missing: {backup}")

    for queue_path in queue_paths:
        backup = backup_dir / queue_path.name
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=queue_path.parent,
            prefix=f".{queue_path.name}.recovery.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            with backup.open("rb") as source:
                shutil.copyfileobj(source, handle)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            durable_replace(temporary, queue_path, mode=0o600)
            secure_private_file(queue_path, strict=True)
            restored.append(str(queue_path))
        finally:
            temporary.unlink(missing_ok=True)

    recovered_state: list[str] = []
    for record in list(payload.get("recovery_files") or []):
        if not isinstance(record, dict):
            raise DispatchTransactionError("Dispatch recovery journal contains malformed recovery metadata.")
        recovered_state.append(_restore_recovery_file(record, backup_dir))

    result = mark_dispatch_transaction_terminal(
        "rolled_back",
        path=target,
        error="Recovered explicitly from persistent dispatch journal.",
    )
    result["recovered_paths"] = restored
    result["recovered_state_paths"] = recovered_state
    return result
