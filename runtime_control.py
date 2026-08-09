from __future__ import annotations

import os
from typing import List, Protocol


class RuntimeBackend(Protocol):
    def backend_name(self) -> str: ...
    def sendgrid_profiles(self) -> List[str]: ...
    def is_known_profile(self, profile_name: str) -> bool: ...
    def list_sender_snapshots(self, tail_lines: int = 12, session: str = ...) -> list[object]: ...
    def list_active_sender_snapshots(self, tail_lines: int = 12, session: str = ...) -> list[object]: ...
    def snapshot_runtime_status(self, tail_lines: int = 12, session: str = ...) -> dict[str, object]: ...
    def runtime_profile_overlays(self, profile_names: list[str] | None = None) -> dict[str, dict[str, object]]: ...
    def start_all_senders(self) -> tuple[bool, str]: ...
    def stop_all_senders(self, session: str = ...) -> tuple[bool, str]: ...
    def start_sender(self, profile_name: str, session: str = ...) -> tuple[bool, str]: ...
    def stop_sender(self, profile_name: str, session: str = ...) -> tuple[bool, str]: ...
    def archive_reset_logs(self, session: str = ...) -> tuple[bool, str]: ...
    def apply_delivery_guards(self, session: str = ...) -> list[dict[str, object]]: ...


def _load_backend() -> RuntimeBackend:
    backend_name = os.environ.get("RUNTIME_BACKEND", "tmux").strip().lower() or "tmux"
    if backend_name == "tmux":
        import runtime_backend_tmux

        return runtime_backend_tmux
    if backend_name == "systemd":
        import runtime_backend_systemd

        return runtime_backend_systemd
    raise ValueError(f"Unsupported runtime backend: {backend_name}")


_BACKEND = _load_backend()


def backend_name() -> str:
    return _BACKEND.backend_name()


def sendgrid_profiles() -> List[str]:
    return list(_BACKEND.sendgrid_profiles())


def is_known_profile(profile_name: str) -> bool:
    return _BACKEND.is_known_profile(profile_name)


def list_sender_snapshots(tail_lines: int = 12, session: str | None = None) -> list[object]:
    if session is None:
        return _BACKEND.list_sender_snapshots(tail_lines=tail_lines)
    return _BACKEND.list_sender_snapshots(tail_lines=tail_lines, session=session)


def list_active_sender_snapshots(tail_lines: int = 12, session: str | None = None) -> list[object]:
    if session is None:
        return _BACKEND.list_active_sender_snapshots(tail_lines=tail_lines)
    return _BACKEND.list_active_sender_snapshots(tail_lines=tail_lines, session=session)


def snapshot_runtime_status(tail_lines: int = 12, session: str | None = None) -> dict[str, object]:
    if session is None:
        return _BACKEND.snapshot_runtime_status(tail_lines=tail_lines)
    return _BACKEND.snapshot_runtime_status(tail_lines=tail_lines, session=session)


def runtime_profile_overlays(
    profile_names: list[str] | None = None,
) -> dict[str, dict[str, object]]:
    loader = getattr(_BACKEND, "runtime_profile_overlays", None)
    if not callable(loader):
        return {}
    overlays = loader(profile_names=profile_names)
    return overlays if isinstance(overlays, dict) else {}


def start_all_senders() -> tuple[bool, str]:
    return _BACKEND.start_all_senders()


def stop_all_senders(session: str | None = None) -> tuple[bool, str]:
    if session is None:
        return _BACKEND.stop_all_senders()
    return _BACKEND.stop_all_senders(session=session)


def start_sender(profile_name: str, session: str | None = None) -> tuple[bool, str]:
    if session is None:
        return _BACKEND.start_sender(profile_name)
    return _BACKEND.start_sender(profile_name, session=session)


def stop_sender(profile_name: str, session: str | None = None) -> tuple[bool, str]:
    if session is None:
        return _BACKEND.stop_sender(profile_name)
    return _BACKEND.stop_sender(profile_name, session=session)


def archive_reset_logs(session: str | None = None) -> tuple[bool, str]:
    if session is None:
        return _BACKEND.archive_reset_logs()
    return _BACKEND.archive_reset_logs(session=session)


def apply_delivery_guards(session: str | None = None) -> list[dict[str, object]]:
    if session is None:
        return _BACKEND.apply_delivery_guards()
    return _BACKEND.apply_delivery_guards(session=session)
