from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator


def lock_path_for(path: Path) -> Path:
    resolved = path.resolve()
    return resolved.with_name(f"{resolved.name}.lock")


@contextmanager
def lock_files(paths: Iterable[Path]) -> Iterator[None]:
    handles = []
    unique_paths = sorted({Path(path).resolve() for path in paths}, key=lambda path: str(path))
    try:
        for path in unique_paths:
            lock_path = lock_path_for(path)
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = lock_path.open("a+", encoding="utf-8")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
