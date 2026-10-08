from __future__ import annotations

from typing import List

import dashboard_core


def backend_name() -> str:
    return "tmux"


def sendgrid_profiles() -> List[str]:
    return list(dashboard_core.SENDGRID_PROFILES)


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
    """Stop active profiles cooperatively without destroying their tmux sessions."""
    active = sorted(
        dashboard_core.active_or_locked_sender_profiles(
            dashboard_core.DASHBOARD_PROFILES
        )
    )
    if not active:
        return True, "No sender workers are running."

    messages: List[str] = []
    ok = True
    for profile_name in active:
        stopped, message = stop_sender(profile_name, session=session)
        ok = ok and stopped
        messages.append(message)

    remaining = sorted(
        dashboard_core.active_or_locked_sender_profiles(
            dashboard_core.DASHBOARD_PROFILES
        )
    )
    if remaining:
        ok = False
        messages.append(
            "Still active after safe stop verification: " + ", ".join(remaining) + "."
        )
    return ok, " | ".join(messages)


def stop_profiles_cooperatively(
    profile_names: list[str],
    session: str = dashboard_core.TMUX_SESSION_NAME,
    *,
    graceful_wait_seconds: float = 3.0,
    terminate_wait_seconds: float = 75.0,
) -> dict[str, object]:
    """Request cooperative shutdown for a batch, then verify with one shared window."""
    targets = [
        profile for profile in dict.fromkeys(profile_names)
        if profile in dashboard_core.DASHBOARD_PROFILES
    ]
    results: list[dict[str, object]] = []
    if not targets:
        return {"ok": True, "results": results, "remaining": []}

    active_before = dashboard_core.active_or_locked_sender_profiles(targets)
    for profile_name in targets:
        if profile_name not in active_before:
            results.append({
                "profile": profile_name,
                "status": "SKIPPED",
                "reason": "Profile was not active or locked when stop verification began.",
            })
            continue
        profile_session = dashboard_core.profile_session_name(profile_name)
        pane_index = dashboard_core.profile_pane_index(profile_name)
        tmux_proc = dashboard_core.subprocess.run(
            ["tmux", "send-keys", "-t", f"{profile_session}:run.{pane_index}", "C-c"],
            cwd=dashboard_core.ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        tmux_output = "\n".join(
            part for part in [tmux_proc.stdout.strip(), tmux_proc.stderr.strip()] if part
        ).strip()
        results.append({
            "profile": profile_name,
            "status": "STOPPING",
            "reason": tmux_output or "Cooperative Ctrl+C requested.",
        })

    remaining_after_grace, locked_after_grace = dashboard_core._wait_for_sender_stop(
        active_before,
        timeout_seconds=graceful_wait_seconds,
    )
    still_after_grace = {
        str(proc.get("profile") or "")
        for proc in remaining_after_grace
        if str(proc.get("profile") or "")
    } | set(locked_after_grace)
    if still_after_grace:
        direct = dashboard_core.stop_sender_processes(
            still_after_grace,
            terminate_wait_seconds=terminate_wait_seconds,
            force_kill=False,
        )
        still_running = {
            str(proc.get("profile") or "")
            for proc in list(direct.get("still_running", []))
            if str(proc.get("profile") or "")
        }
        locked_after = {str(profile) for profile in list(direct.get("locked_profiles", []))}
        remaining = still_running | locked_after
    else:
        remaining = set()

    for item in results:
        profile_name = str(item.get("profile") or "")
        if item.get("status") == "SKIPPED":
            continue
        if profile_name in remaining:
            item["status"] = "FAILED"
            item["reason"] = (
                "Still active after the safe shutdown window. No SIGKILL was used; "
                "forced termination remains blocked at the provider boundary."
            )
        else:
            item["status"] = "STOPPED"
            item["reason"] = "Stopped and verified."

    return {
        "ok": not remaining,
        "results": results,
        "remaining": sorted(remaining),
    }


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
