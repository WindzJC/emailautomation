from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from dataclasses import replace
from typing import List

import dashboard_core
from send_shard import PROFILES


SYSTEMCTL_BIN = os.environ.get(
    "ASTRA_SYSTEMCTL_BIN",
    "/usr/bin/systemctl",
).strip()
PROFILE_RE = re.compile(r"^[a-z0-9_]+$")
START_VERIFY_ATTEMPTS = 20
START_VERIFY_INTERVAL_SECONDS = 0.1
RUNTIME_OVERLAY_CACHE_TTL_SECONDS = 5.0
RUNTIME_OVERLAY_STALE_SECONDS = 60.0
RUNTIME_OVERLAY_SYSTEMCTL_TIMEOUT_SECONDS = 10

_RUNTIME_OVERLAY_CACHE_LOCK = threading.Lock()
_RUNTIME_OVERLAY_CACHE: dict[str, dict[str, object]] = {}
_RUNTIME_OVERLAY_CACHE_AT = 0.0
_RUNTIME_OVERLAY_REFRESHING = False


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
    if action not in {
        "start",
        "stop",
        "is-active",
        "is-failed",
        "show-active",
    }:
        raise ValueError(f"Unsupported systemd sender action: {action}")

    unit = unit_name(profile_name)

    if action == "start":
        command = [
            SYSTEMCTL_BIN,
            "--no-block",
            "start",
            unit,
        ]
    elif action == "show-active":
        command = [
            SYSTEMCTL_BIN,
            "show",
            unit,
            "--property=ActiveState",
            "--value",
        ]
    else:
        command = [SYSTEMCTL_BIN, action, unit]
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


def _active_state(profile_name: str) -> str:
    result = _control("show-active", profile_name)
    if result.returncode != 0:
        return "unknown"
    return str(result.stdout or "").strip().lower() or "unknown"


def _is_active(profile_name: str) -> bool:
    return _control("is-active", profile_name).returncode == 0


def _is_failed(profile_name: str) -> bool:
    return _control("is-failed", profile_name).returncode == 0


def _runtime_fields_from_active_state(
    profile_name: str,
    active_state: str,
) -> dict[str, object]:
    unit = unit_name(profile_name)

    if active_state == "activating":
        return {
            "tmux_running": True,
            "tmux_dead": False,
            "tmux_command": unit,
            "tmux_tail": "",
            "runtime_state": "starting",
            "runtime_label": "Starting",
            "runtime_note": f"{unit} is running startup verification.",
        }

    if active_state in {"active", "reloading"}:
        return {
            "tmux_running": True,
            "tmux_dead": False,
            "tmux_command": unit,
            "tmux_tail": "",
            "runtime_state": "running",
            "runtime_label": "Running",
            "runtime_note": f"Managed by {unit}.",
        }

    if active_state == "failed":
        return {
            "tmux_running": False,
            "tmux_dead": True,
            "tmux_command": unit,
            "tmux_tail": "",
            "runtime_state": "error",
            "runtime_label": "Error",
            "runtime_note": f"{unit} is in the failed state.",
        }

    return {
        "tmux_running": False,
        "tmux_dead": False,
        "tmux_command": unit,
        "tmux_tail": "",
        "runtime_state": "stopped",
        "runtime_label": "Stopped",
        "runtime_note": f"{unit} is inactive.",
    }


def _unresolved_runtime_fields(
    profile_name: str,
) -> dict[str, object]:
    unit = unit_name(profile_name)
    return {
        "tmux_running": False,
        "tmux_dead": True,
        "tmux_command": unit,
        "tmux_tail": "",
        "runtime_state": "error",
        "runtime_label": "Unknown",
        "runtime_note": f"Unable to determine current state of {unit}.",
    }


def _batch_active_states(
    profile_names: list[str],
) -> dict[str, str] | None:
    if not profile_names:
        return {}

    unit_to_profile = {
        unit_name(profile_name): profile_name
        for profile_name in profile_names
    }
    command = [
        SYSTEMCTL_BIN,
        "show",
        *unit_to_profile,
        "--property=Id",
        "--property=ActiveState",
        "--no-pager",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=RUNTIME_OVERLAY_SYSTEMCTL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    states: dict[str, str] = {}
    for block in str(result.stdout or "").split("\n\n"):
        properties: dict[str, str] = {}
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()

        profile_name = unit_to_profile.get(properties.get("Id", ""))
        active_state = properties.get("ActiveState", "").strip().lower()
        if profile_name and active_state:
            states[profile_name] = active_state

    return states


def _reset_runtime_overlay_cache_for_tests() -> None:
    global _RUNTIME_OVERLAY_CACHE
    global _RUNTIME_OVERLAY_CACHE_AT
    global _RUNTIME_OVERLAY_REFRESHING

    with _RUNTIME_OVERLAY_CACHE_LOCK:
        _RUNTIME_OVERLAY_CACHE = {}
        _RUNTIME_OVERLAY_CACHE_AT = 0.0
        _RUNTIME_OVERLAY_REFRESHING = False


def _verify_started_state(profile_name: str) -> tuple[bool, str]:
    unit = unit_name(profile_name)
    last_state = "unknown"
    for attempt in range(START_VERIFY_ATTEMPTS):
        last_state = _active_state(profile_name)
        if last_state in {"active", "reloading"}:
            return True, f"STARTED: {unit}; verified state={last_state}."
        if last_state == "failed":
            return False, f"FAILED: {unit} entered the failed state during startup."
        if last_state == "deactivating":
            return False, f"REFUSED: {unit} entered the deactivating state during startup."
        if attempt + 1 < START_VERIFY_ATTEMPTS:
            time.sleep(START_VERIFY_INTERVAL_SECONDS)

    if last_state == "activating":
        return (
            True,
            f"STARTING: {unit}; state is still activating after bounded verification.",
        )
    if last_state in {"inactive", "dead"}:
        return (
            False,
            f"REFUSED: start was skipped for {unit}; "
            f"state remained {last_state} after bounded verification.",
        )
    if last_state == "unknown":
        return (
            False,
            f"VERIFICATION_TIMEOUT: unable to verify start of {unit}; "
            "systemd state remained unknown until verification timed out.",
        )
    return (
        False,
        f"VERIFICATION_TIMEOUT: unable to verify start of {unit}; "
        f"unexpected state={last_state} after bounded verification.",
    )


def _profile_runtime_fields(profile_name: str) -> dict[str, object]:
    unit = unit_name(profile_name)
    active_state = _active_state(profile_name)

    if active_state == "activating":
        return {
            "tmux_running": True,
            "tmux_dead": False,
            "tmux_command": unit,
            "tmux_tail": "",
            "runtime_state": "starting",
            "runtime_label": "Starting",
            "runtime_note": f"{unit} is running startup verification.",
        }

    if active_state in {"active", "reloading"}:
        return {
            "tmux_running": True,
            "tmux_dead": False,
            "tmux_command": unit,
            "tmux_tail": "",
            "runtime_state": "running",
            "runtime_label": "Running",
            "runtime_note": f"Managed by {unit}.",
        }

    if _is_failed(profile_name):
        return {
            "tmux_running": False,
            "tmux_dead": True,
            "tmux_command": unit,
            "tmux_tail": "",
            "runtime_state": "error",
            "runtime_label": "Error",
            "runtime_note": f"{unit} is in the failed state.",
        }

    return {
        "tmux_running": False,
        "tmux_dead": False,
        "tmux_command": unit,
        "tmux_tail": "",
        "runtime_state": "stopped",
        "runtime_label": "Stopped",
        "runtime_note": f"{unit} is inactive.",
    }


def runtime_profile_overlays(
    profile_names: list[str] | None = None,
) -> dict[str, dict[str, object]]:
    """Return current systemd-only fields without loading queue/log metrics.

    Dashboard runtime reads are batched and briefly cached so concurrent
    snapshot requests cannot create a systemctl subprocess storm. Sender
    control and startup verification continue to use the direct control path.
    """
    global _RUNTIME_OVERLAY_CACHE
    global _RUNTIME_OVERLAY_CACHE_AT
    global _RUNTIME_OVERLAY_REFRESHING

    requested = configured_profiles() if profile_names is None else profile_names
    selected = list(dict.fromkeys(
        profile_name
        for profile_name in requested
        if is_known_profile(profile_name)
    ))

    if not selected:
        return {}

    now = time.monotonic()
    with _RUNTIME_OVERLAY_CACHE_LOCK:
        cache_complete = all(
            profile_name in _RUNTIME_OVERLAY_CACHE
            for profile_name in selected
        )
        cache_age = (
            now - _RUNTIME_OVERLAY_CACHE_AT
            if _RUNTIME_OVERLAY_CACHE_AT > 0
            else float("inf")
        )

        if cache_complete and cache_age <= RUNTIME_OVERLAY_CACHE_TTL_SECONDS:
            return {
                profile_name: dict(_RUNTIME_OVERLAY_CACHE[profile_name])
                for profile_name in selected
            }

        if _RUNTIME_OVERLAY_REFRESHING:
            if cache_complete and cache_age <= RUNTIME_OVERLAY_STALE_SECONDS:
                return {
                    profile_name: dict(_RUNTIME_OVERLAY_CACHE[profile_name])
                    for profile_name in selected
                }
            return {
                profile_name: _unresolved_runtime_fields(profile_name)
                for profile_name in selected
            }

        _RUNTIME_OVERLAY_REFRESHING = True

    try:
        refresh_names = list(dict.fromkeys(
            profile_name
            for profile_name in configured_profiles()
            if is_known_profile(profile_name)
        ))
        states = _batch_active_states(refresh_names)

        if states is None:
            now = time.monotonic()
            with _RUNTIME_OVERLAY_CACHE_LOCK:
                cache_complete = all(
                    profile_name in _RUNTIME_OVERLAY_CACHE
                    for profile_name in selected
                )
                cache_age = (
                    now - _RUNTIME_OVERLAY_CACHE_AT
                    if _RUNTIME_OVERLAY_CACHE_AT > 0
                    else float("inf")
                )
                if (
                    cache_complete
                    and cache_age <= RUNTIME_OVERLAY_STALE_SECONDS
                ):
                    return {
                        profile_name: dict(_RUNTIME_OVERLAY_CACHE[profile_name])
                        for profile_name in selected
                    }
            return {
                profile_name: _unresolved_runtime_fields(profile_name)
                for profile_name in selected
            }

        refreshed = {
            profile_name: (
                _runtime_fields_from_active_state(
                    profile_name,
                    states[profile_name],
                )
                if profile_name in states
                else _unresolved_runtime_fields(profile_name)
            )
            for profile_name in refresh_names
        }

        with _RUNTIME_OVERLAY_CACHE_LOCK:
            _RUNTIME_OVERLAY_CACHE = refreshed
            _RUNTIME_OVERLAY_CACHE_AT = time.monotonic()
            return {
                profile_name: dict(
                    refreshed.get(
                        profile_name,
                        _unresolved_runtime_fields(profile_name),
                    )
                )
                for profile_name in selected
            }
    finally:
        with _RUNTIME_OVERLAY_CACHE_LOCK:
            _RUNTIME_OVERLAY_REFRESHING = False


def _profile_snapshot(profile_name: str, pane_index: int, tail_lines: int):
    snapshot = dashboard_core.load_profile_snapshot(
        profile_name,
        pane_index,
        {},
        tail_lines=tail_lines,
        session="systemd",
    )
    return replace(snapshot, **_profile_runtime_fields(profile_name))


def list_sender_snapshots(
    tail_lines: int = 12,
    session: str = "systemd",
) -> list[object]:
    del session
    profile_names = configured_profiles()
    overlays = runtime_profile_overlays(profile_names)
    snapshots: list[object] = []

    for index, profile_name in enumerate(profile_names):
        snapshot = dashboard_core.load_profile_snapshot(
            profile_name,
            index,
            {},
            tail_lines=tail_lines,
            session="systemd",
        )
        runtime_fields = overlays.get(profile_name)
        if runtime_fields is None:
            runtime_fields = _unresolved_runtime_fields(profile_name)
        snapshots.append(replace(snapshot, **runtime_fields))

    return snapshots


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

    state = _active_state(profile_name)
    unit = unit_name(profile_name)

    if state in {"active", "reloading"}:
        return False, f"{unit} is already active."

    if state == "activating":
        return False, f"{unit} is already starting."

    if state == "unknown":
        return False, f"Unable to determine the state of {unit}."

    result = _control("start", profile_name)

    if result.returncode != 0:
        return (
            False,
            f"Unable to start {unit} "
            f"(systemctl exit {result.returncode}).",
        )

    return _verify_started_state(profile_name)


def stop_sender(
    profile_name: str,
    session: str = "systemd",
) -> tuple[bool, str]:
    del session

    if not is_known_profile(profile_name):
        return False, f"Unknown profile: {profile_name}"

    state = _active_state(profile_name)
    unit = unit_name(profile_name)

    if state == "unknown":
        return False, f"Unable to determine the state of {unit}."

    if state in {"inactive", "failed"}:
        return True, f"{unit} is already stopped."

    result = _control("stop", profile_name)

    if result.returncode != 0:
        return (
            False,
            f"Unable to stop {unit} "
            f"(systemctl exit {result.returncode}).",
        )

    final_state = _active_state(profile_name)

    if final_state in {
        "active",
        "activating",
        "reloading",
        "deactivating",
    }:
        return False, f"{unit} remained active."

    return True, f"Stopped {unit}."


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
