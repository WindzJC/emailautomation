"""Durable, permission-safe filesystem primitives for critical runtime state."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700


def fsync_directory(path: Path) -> None:
    """Persist directory metadata after an atomic rename when supported."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def secure_private_file(path: Path, *, strict: bool = True) -> Path:
    try:
        path.chmod(PRIVATE_FILE_MODE)
    except OSError:
        if strict:
            raise
    return path


def secure_private_dir(path: Path, *, strict: bool = True) -> Path:
    try:
        path.chmod(PRIVATE_DIR_MODE)
    except OSError:
        if strict:
            raise
    return path


def durable_replace(
    temporary: Path,
    target: Path,
    *,
    mode: int = PRIVATE_FILE_MODE,
) -> Path:
    """Atomically replace target and fsync both file contents and parent metadata."""
    target.parent.mkdir(parents=True, exist_ok=True)
    secure_private_dir(target.parent, strict=False)
    os.chmod(temporary, mode)
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    os.chmod(target, mode)
    fsync_directory(target.parent)
    return target


def atomic_write_bytes(path: Path, payload: bytes, *, mode: int = PRIVATE_FILE_MODE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    secure_private_dir(path.parent, strict=False)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return durable_replace(temporary, path, mode=mode)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int = PRIVATE_FILE_MODE,
) -> Path:
    return atomic_write_bytes(path, text.encode(encoding), mode=mode)


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
    *,
    mode: int = PRIVATE_FILE_MODE,
) -> Path:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return atomic_write_text(path, text, mode=mode)
