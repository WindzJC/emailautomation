"""Runtime-process policy for cloud sender verification."""

from __future__ import annotations

import re
from collections.abc import Iterable

_ALLOWED_DURING_SENDER_VERIFICATION = frozenset(
    {
        "dashboard",
        "tunnel",
    }
)

_BLOCKER_PATTERN = re.compile(
    r"^\s*\d+\s+([a-z][a-z0-9_-]*):\s+.+\s*$"
)


def unsafe_runtime_blockers(blockers: Iterable[str]) -> list[str]:
    """Return processes unsafe during sender startup verification."""

    unsafe: list[str] = []

    for blocker in blockers:
        if not isinstance(blocker, str):
            raise ValueError("blocker entries must be strings")

        match = _BLOCKER_PATTERN.fullmatch(blocker)

        if match is None:
            raise ValueError("blocker entry has an unexpected format")

        category = match.group(1)

        if category not in _ALLOWED_DURING_SENDER_VERIFICATION:
            unsafe.append(blocker)

    return unsafe
