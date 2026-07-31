from __future__ import annotations

import os
import re
import subprocess
from dataclasses import replace
from typing import List

import dashboard_core
from send_shard import PROFILES


SYSTEMCTL_BIN = os.environ.get(
    "ASTRA_SYSTEMCTL_BIN",
    "/usr/bin/systemctl",
).strip()
PROFILE_RE = re.compile(r"^[a-z0-9_]+$")


def backend_name() -> str:
    return "systemd"


def sendgrid_profiles() -> List[str]:
    return list(dashboard_core.SENDGRID_PROFILES)


def configured_profiles() -> List[str]:
    return sorted(PROFILES)


def is_known_profile(profile_name: str) -> bool:
    return (
        isinstance(profile_name, str)
        and PROFILE_RE.fullmatch(profile_name) is not None
        and profile_name in PROFILES
    )


def unit_name(profile_name: str) -> str:
    if not is_known_profile(profile_name):
        raise ValueError(f"Unknown profile: {profile_name}")
    return f"astra-sender@{profile_name}.service"


def lock_name(profile_name: str) -> str:
    if not is_known_profile(profile_name):
        raise ValueError(f"Unknown profile: {profile_name}")
    return f"/run/astra-emailautomation/sender-{profile_name}.lock"


def _control(
    action: str,
    profile_name: str,
) -> subprocess.CompletedProcess[str]:
    if action not in {"start", "stop", "is-active", "is-failed"}:
        raise ValueError(f"Unsupported systemd sender action: {action}")
    unit_name(profile_name)
    command = [SYSTEMCTL_BIN, action, unit_name(profile_name)]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            command,
            returncode=127,
            stdout="",
            stderr=f"systemd control unavailable: {type(exc).__name__}",
        )


def _is_active(profile_name: str) -> bool:
    return _control("is-active", profile_name).returncode == 0


def _is_failed(profile_name: str) -> bool:
    return _control("is-failed", profile_name).returncode == 0


def _profile_snapshot(profile_name: str, pane_index: int, tail_lines: int):
    snapshot = dashboard_core.load_profile_snapshot(
        profile_name,
        pane_index,
        {},
        tail_lines=tail_lines,
        session="systemd",
    )
    unit = unit_name(profile_name)
    if _is_active(profile_name):
        return replace(
            snapshot,
            tmux_running=True,
            tmux_dead=False,
            tmux_command=unit,
            tmux_tail="",
            runtime_state="running",
            runtime_label="Running",
            runtime_note=f"Managed by {unit}.",
        )
    if _is_failed(profile_name):
        return replace(
            snapshot,
            tmux_running=False,
            tmux_dead=True,
            tmux_command=unit,
            tmux_tail="",
            runtime_state="error",
            runtime_label="Error",
            runtime_note=f"{unit} is in the failed state.",
        )
    return replace(
        snapshot,
        tmux_running=False,
        tmux_dead=False,
        tmux_command=unit,
        tmux_tail="",
        runtime_state="stopped",
        runtime_label="Stopped",
        runtime_note=f"{unit} is inactive.",
    )


def list_sender_snapshots(
    tail_lines: int = 12,
    session: str = "systemd",
) -> list[object]:
    del session
    return [
        _profile_snapshot(profile_name, index, tail_lines)
        for index, profile_name in enumerate(configured_profiles())
    ]


def list_active_sender_snapshots(
    tail_lines: int = 12,
    session: str = "systemd",
) -> list[object]:
    return [
        snapshot
        for snapshot in list_sender_snapshots(
            tail_lines=tail_lines,
            session=session,
        )
        if dashboard_core.profile_is_active(snapshot)
    ]


def snapshot_runtime_status(
    tail_lines: int = 12,
    session: str = "systemd",
) -> dict[str, object]:
    snapshots = list_sender_snapshots(tail_lines=tail_lines, session=session)
    return {
        "backend": backend_name(),
        "session": "systemd",
        "session_label": dashboard_core.session_status(snapshots),
        "profiles": snapshots,
        "active_profiles": [
            snapshot.name
            for snapshot in snapshots
            if dashboard_core.profile_is_active(snapshot)
        ],
    }


def start_all_senders() -> tuple[bool, str]:
    return (
        False,
        "Bulk cloud sender startup is disabled; select one configured profile.",
    )


def stop_all_senders(session: str = "systemd") -> tuple[bool, str]:
    del session
    failures: list[str] = []
    stopped: list[str] = []
    for profile_name in configured_profiles():
        ok, message = stop_sender(profile_name)
        if ok:
            stopped.append(profile_name)
        else:
            failures.append(f"{profile_name}: {message}")
    if failures:
        return False, " | ".join(failures)
    return True, f"Stopped {len(stopped)} configured systemd sender instance(s)."


def start_sender(
    profile_name: str,
    session: str = "systemd",
) -> tuple[bool, str]:
    del session
    if not is_known_profile(profile_name):
        return False, f"Unknown profile: {profile_name}"
    if _is_active(profile_name):
        return False, f"{unit_name(profile_name)} is already active."
    result = _control("start", profile_name)
    if result.returncode != 0:
        return (
            False,
            f"Unable to start {unit_name(profile_name)} "
            f"(systemctl exit {result.returncode}).",
        )
    if not _is_active(profile_name):
        return False, f"{unit_name(profile_name)} did not become active."
    return True, f"Started {unit_name(profile_name)}."


def stop_sender(
    profile_name: str,
    session: str = "systemd",
) -> tuple[bool, str]:
    del session
    if not is_known_profile(profile_name):
        return False, f"Unknown profile: {profile_name}"
    if not _is_active(profile_name):
        return True, f"{unit_name(profile_name)} is already stopped."
    result = _control("stop", profile_name)
    if result.returncode != 0:
        return (
            False,
            f"Unable to stop {unit_name(profile_name)} "
            f"(systemctl exit {result.returncode}).",
        )
    if _is_active(profile_name):
        return False, f"{unit_name(profile_name)} remained active."
    return True, f"Stopped {unit_name(profile_name)}."


def archive_reset_logs(session: str = "systemd") -> tuple[bool, str]:
    del session
    return False, "Cloud log reset is disabled; use the reviewed offline workflow."


def apply_delivery_guards(
    session: str = "systemd",
) -> list[dict[str, object]]:
    del session
    snapshots = [
        snapshot
        for snapshot in list_sender_snapshots(tail_lines=12)
        if snapshot.name in dashboard_core.SENDGRID_PROFILES
    ]
    return dashboard_core.evaluate_and_apply_profile_delivery_guards(
        session="systemd",
        snapshots=snapshots,
        stop_profile=stop_sender,
    )
