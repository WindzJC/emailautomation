from __future__ import annotations

from typing import List

import dashboard_core


def backend_name() -> str:
    return "tmux"


def sendgrid_profiles() -> List[str]:
    return list(dashboard_core.DASHBOARD_PROFILES)


def is_known_profile(profile_name: str) -> bool:
    return profile_name in dashboard_core.DASHBOARD_PROFILES


def list_sender_snapshots(
    tail_lines: int = 12,
    session: str = dashboard_core.TMUX_SESSION_NAME,
) -> List[dashboard_core.ProfileSnapshot]:
    return dashboard_core.load_dashboard_profile_snapshots(tail_lines=tail_lines)


def list_active_sender_snapshots(
    tail_lines: int = 12,
    session: str = dashboard_core.TMUX_SESSION_NAME,
) -> List[dashboard_core.ProfileSnapshot]:
    return dashboard_core.active_dashboard_profile_snapshots(tail_lines=tail_lines)


def snapshot_runtime_status(
    tail_lines: int = 12,
    session: str = dashboard_core.TMUX_SESSION_NAME,
) -> dict[str, object]:
    snapshots = list_sender_snapshots(tail_lines=tail_lines, session=session)
    return {
        "backend": backend_name(),
        "session": session,
        "session_label": dashboard_core.session_status(snapshots),
        "profiles": snapshots,
        "active_profiles": [snapshot.name for snapshot in snapshots if dashboard_core.profile_is_active(snapshot)],
    }


def start_all_senders() -> tuple[bool, str]:
    return dashboard_core.run_sendgrid_launcher()


def stop_all_senders(session: str = dashboard_core.TMUX_SESSION_NAME) -> tuple[bool, str]:
    messages: List[str] = []
    ok = True
    sessions = {dashboard_core.profile_session_name(name) for name in dashboard_core.DASHBOARD_PROFILES}
    tmux_messages: List[str] = []
    for profile_session in sorted(sessions):
        stopped, message = dashboard_core.stop_sendgrid_session(session=profile_session)
        if stopped:
            tmux_messages.append(message)
        elif "is not running" not in message.lower():
            tmux_messages.append(message)

    direct = dashboard_core.stop_sender_processes(dashboard_core.DASHBOARD_PROFILES)
    found = len(direct.get("found", []))
    stopped = len(direct.get("stopped", []))
    killed = len(direct.get("killed", []))
    still_running = len(direct.get("still_running", []))
    if still_running:
        ok = False

    tmux_result = "; ".join(tmux_messages) if tmux_messages else "No dashboard tmux sender sessions were running."
    direct_result = (
        f"Direct sender process stop: found={found}, stopped={stopped}, "
        f"sigkill={killed}, still_running={still_running}."
    )
    messages.append(f"tmux stop: {tmux_result}")
    messages.append(direct_result)
    return ok, " | ".join(messages)


def start_sender(profile_name: str, session: str = dashboard_core.TMUX_SESSION_NAME) -> tuple[bool, str]:
    if profile_name not in dashboard_core.DASHBOARD_PROFILES:
        return False, f"Unknown profile: {profile_name}"
    profile_session = dashboard_core.profile_session_name(profile_name)
    if profile_name in dashboard_core.SENDGRID_PROFILES:
        pane_index = dashboard_core.profile_pane_index(profile_name)
        return dashboard_core.start_sendgrid_profile(profile_name, pane_index, session=profile_session)
    return dashboard_core.start_private_profile(profile_name, session=profile_session)


def stop_sender(profile_name: str, session: str = dashboard_core.TMUX_SESSION_NAME) -> tuple[bool, str]:
    if profile_name not in dashboard_core.DASHBOARD_PROFILES:
        return False, f"Unknown profile: {profile_name}"
    profile_session = dashboard_core.profile_session_name(profile_name)
    if profile_name in dashboard_core.SENDGRID_PROFILES:
        pane_index = dashboard_core.profile_pane_index(profile_name)
        return dashboard_core.stop_sendgrid_profile(profile_name, pane_index, session=profile_session)
    return dashboard_core.stop_private_profile(profile_name, session=profile_session)


def archive_reset_logs(session: str = dashboard_core.TMUX_SESSION_NAME) -> tuple[bool, str]:
    return dashboard_core.archive_reset_sender_logs(session=session)


def apply_delivery_guards(session: str = dashboard_core.TMUX_SESSION_NAME) -> List[dict[str, object]]:
    return dashboard_core.evaluate_and_apply_profile_delivery_guards(session=session)
