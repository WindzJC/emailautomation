from __future__ import annotations

import csv
import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from send_shard import PROFILES
from sendgrid_hygiene import load_suppression_records, parse_activity_file, parse_iso_utc


ROOT = Path(__file__).resolve().parent
SENDGRID_PROFILES = [
    "sendgrid_annette",
    "sendgrid_jordan",
    "sendgrid_jodi",
    "sendgrid_alison",
    "sendgrid_fiorela",
]


@dataclass
class ProfileSnapshot:
    name: str
    pane_index: int
    csv_path: Path
    log_path: Path
    max_total: int
    pending_count: int
    run_started_at: Optional[datetime]
    run_sent: int
    run_errors: int
    run_skipped: int
    sent_today: int
    errors_today: int
    skipped_today: int
    last_status: str
    last_email: str
    last_info: str
    last_timestamp: Optional[datetime]
    tmux_running: bool
    tmux_dead: bool
    tmux_command: str
    tmux_tail: str


def render_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 1.6rem;}
        .status-chip {
            display: inline-block;
            padding: 0.22rem 0.65rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            margin: 0.15rem 0 0.7rem 0;
        }
        .status-running {background:#e8f7ee; color:#137333;}
        .status-stopped {background:#f3f4f6; color:#4b5563;}
        .status-dead {background:#fdecec; color:#b42318;}
        .minor-label {color:#6b7280; font-size:0.82rem;}
        .health-banner {
            padding: 0.8rem 1rem;
            border-radius: 0.9rem;
            margin: 0.4rem 0 1rem 0;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .health-green {background:#e8f7ee; color:#137333; border-color:#b7dfc8;}
        .health-yellow {background:#fff7e6; color:#9a6700; border-color:#f3d899;}
        .health-red {background:#fdecec; color:#b42318; border-color:#f2b8b5;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_log_timestamp(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def local_today_bounds() -> tuple[datetime, datetime]:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def count_pending(path: Path) -> int:
    return max(0, len(read_csv_rows(path)))


def format_when(ts: Optional[datetime]) -> str:
    if not ts:
        return "-"
    return ts.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_age(ts: Optional[datetime]) -> str:
    if not ts:
        return "-"
    now = datetime.now().astimezone()
    delta = now - ts
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def tmux_pane_map(session: str = "sendgrid") -> Dict[str, Dict[str, str]]:
    try:
        out = subprocess.check_output(
            [
                "tmux",
                "list-panes",
                "-t",
                f"{session}:run",
                "-F",
                "#{pane_index}\t#{pane_dead}\t#{pane_current_command}",
            ],
            cwd=ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return {}
    panes: Dict[str, Dict[str, str]] = {}
    for line in out.splitlines():
        idx, dead, cmd = (line.split("\t", 2) + ["", ""])[:3]
        panes[idx] = {"dead": dead, "cmd": cmd}
    return panes


def tmux_capture_tail(pane_index: int, session: str = "sendgrid", lines: int = 16) -> str:
    try:
        out = subprocess.check_output(
            ["tmux", "capture-pane", "-p", "-t", f"{session}:run.{pane_index}"],
            cwd=ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return ""
    return "\n".join(out.splitlines()[-lines:]).strip()


def run_sendgrid_launcher() -> tuple[bool, str]:
    env = os.environ.copy()
    env["TMUX_SENDGRID_ATTACH"] = "0"
    try:
        proc = subprocess.run(
            ["bash", "./run_sendgrid_tmux.sh"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Launcher timed out while starting sendgrid session."
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
    return proc.returncode == 0, output or "(no output)"


def stop_sendgrid_session(session: str = "sendgrid") -> tuple[bool, str]:
    proc = subprocess.run(
        ["tmux", "kill-session", "-t", session],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True, f"Stopped tmux session: {session}"
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
    return False, output or f"tmux session {session} is not running."


def stop_sendgrid_profile(profile_name: str, pane_index: int, session: str = "sendgrid") -> tuple[bool, str]:
    proc = subprocess.run(
        ["tmux", "send-keys", "-t", f"{session}:run.{pane_index}", "C-c"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True, f"Stop signal sent to {profile_name} (pane {pane_index})."
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
    return False, output or f"Unable to stop {profile_name}."


def archive_reset_sender_logs(session: str = "sendgrid") -> tuple[bool, str]:
    pane_info = tmux_pane_map(session)
    if any((pane.get("cmd") or "").strip() not in {"", "bash", "sh", "zsh", "fish"} for pane in pane_info.values()):
        return False, "Stop the sendgrid session before archiving/resetting logs."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"log_reset_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    reset_count = 0
    for name in SENDGRID_PROFILES:
        log_path = ROOT / str(PROFILES[name]["log"])
        backup_path = backup_root / log_path.name
        if log_path.exists():
            shutil.copy2(log_path, backup_path)
            header = "TimestampUTC,Email,Status,Info\n"
            log_path.write_text(header, encoding="utf-8", newline="")
        else:
            backup_path.write_text("", encoding="utf-8")
            log_path.write_text("TimestampUTC,Email,Status,Info\n", encoding="utf-8", newline="")
        reset_count += 1
    return True, f"Archived and reset {reset_count} sender log(s) to {backup_root}."


def load_profile_snapshot(profile_name: str, pane_index: int, pane_info: Dict[str, Dict[str, str]]) -> ProfileSnapshot:
    cfg = PROFILES[profile_name]
    csv_path = ROOT / cfg["csv"]
    log_path = ROOT / cfg["log"]
    rows = read_csv_rows(log_path)
    start, end = local_today_bounds()
    always_send_email = (cfg.get("always_send") or "").strip().lower()

    sent_today = 0
    errors_today = 0
    skipped_today = 0
    run_sent = 0
    run_errors = 0
    run_skipped = 0
    last_status = ""
    last_email = ""
    last_info = ""
    last_timestamp: Optional[datetime] = None
    run_started_at: Optional[datetime] = None

    for row in rows:
        ts = parse_log_timestamp(row.get("TimestampUTC", ""))
        status = (row.get("Status") or "").strip()
        email = (row.get("Email") or "").strip().lower()
        if ts and start <= ts < end:
            if status == "SENT":
                sent_today += 1
            elif status == "SKIP":
                skipped_today += 1
            else:
                errors_today += 1
        if ts and always_send_email and email == always_send_email and status == "SENT":
            if run_started_at is None or ts >= run_started_at:
                run_started_at = ts
        if ts and (last_timestamp is None or ts >= last_timestamp):
            last_timestamp = ts
            last_status = status
            last_email = (row.get("Email") or "").strip()
            last_info = (row.get("Info") or "").strip()

    if run_started_at is not None:
        for row in rows:
            ts = parse_log_timestamp(row.get("TimestampUTC", ""))
            if not ts or ts < run_started_at:
                continue
            status = (row.get("Status") or "").strip()
            if status == "SENT":
                run_sent += 1
            elif status == "SKIP":
                run_skipped += 1
            else:
                run_errors += 1

    pane = pane_info.get(str(pane_index), {})
    current_cmd = (pane.get("cmd") or "").strip()
    running = bool(pane) and current_cmd not in {"", "bash", "sh", "zsh", "fish"}
    return ProfileSnapshot(
        name=profile_name,
        pane_index=pane_index,
        csv_path=csv_path,
        log_path=log_path,
        max_total=int(cfg.get("max_total") or 0),
        pending_count=count_pending(csv_path),
        run_started_at=run_started_at,
        run_sent=run_sent,
        run_errors=run_errors,
        run_skipped=run_skipped,
        sent_today=sent_today,
        errors_today=errors_today,
        skipped_today=skipped_today,
        last_status=last_status,
        last_email=last_email,
        last_info=last_info,
        last_timestamp=last_timestamp,
        tmux_running=running,
        tmux_dead=(pane.get("dead") == "1"),
        tmux_command=current_cmd,
        tmux_tail=tmux_capture_tail(pane_index) if pane else "",
    )


def latest_send_profile_by_email(profile_names: Iterable[str]) -> Dict[str, str]:
    latest: Dict[str, tuple[datetime, str]] = {}
    for profile_name in profile_names:
        cfg = PROFILES[profile_name]
        for row in read_csv_rows(ROOT / cfg["log"]):
            email = (row.get("Email") or "").strip().lower()
            ts = parse_log_timestamp(row.get("TimestampUTC", ""))
            if not email or not ts:
                continue
            current = latest.get(email)
            if current is None or ts >= current[0]:
                latest[email] = (ts, profile_name)
    return {email: profile for email, (_, profile) in latest.items()}


def load_activity_events(path: Path, email_to_profile: Dict[str, str]) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    events = parse_activity_file(path)
    for event in events:
        email = (event.get("email") or "").strip().lower()
        event["profile"] = email_to_profile.get(email, "")
    events.sort(
        key=lambda e: parse_iso_utc(e.get("processed_at_utc", "")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return events


def summarize_activity(events: List[Dict[str, str]], hours: int = 24) -> Dict[str, object]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = [e for e in events if (parse_iso_utc(e.get("processed_at_utc", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]
    return {
        "recent": recent,
        "by_status": Counter((e.get("status") or "").strip() for e in recent),
        "by_profile": Counter((e.get("profile") or "unmapped") for e in recent),
        "by_domain": Counter((e.get("domain") or "").strip() for e in recent if e.get("domain")),
    }


def load_suppression_summary(path: Path) -> Dict[str, int]:
    records = load_suppression_records(path)
    now = datetime.now(timezone.utc)
    perm = 0
    temp_active = 0
    for record in records.values():
        is_perm = (record.get("is_permanent") or "").strip().lower() in {"1", "true", "yes", "y"}
        if is_perm:
            perm += 1
            continue
        ttl = parse_iso_utc(record.get("ttl_until_utc", ""))
        if ttl and ttl >= now:
            temp_active += 1
    return {"perm": perm, "temp_active": temp_active, "total": len(records)}


def load_json_report(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def session_status(snapshots: List[ProfileSnapshot]) -> str:
    if any(s.tmux_dead for s in snapshots):
        return "dead"
    if any(s.tmux_running for s in snapshots):
        return "running"
    return "stopped"


def recent_failure_count(activity: Dict[str, object]) -> int:
    bad_statuses = {"blocked", "bounced", "dropped", "spam report", "spam_report", "spamreport"}
    by_status: Counter[str] = activity["by_status"]  # type: ignore[assignment]
    return sum(count for status, count in by_status.items() if status.strip().lower() in bad_statuses)


def build_attention_items(
    session_label: str,
    snapshots: List[ProfileSnapshot],
    recent_failures: int,
    historical_errors_today: int,
) -> List[str]:
    items: List[str] = []
    dead = [s.name.replace("sendgrid_", "") for s in snapshots if s.tmux_dead]
    stopped = [s.name.replace("sendgrid_", "") for s in snapshots if not s.tmux_running and not s.tmux_dead]
    live_errors = [s.name.replace("sendgrid_", "") for s in snapshots if s.run_errors > 0]
    if session_label == "stopped":
        items.append("Session is not running.")
    if dead:
        items.append(f"Dead pane(s): {', '.join(dead)}.")
    if stopped and session_label == "running":
        items.append(f"Stopped pane(s): {', '.join(stopped)}.")
    if live_errors:
        items.append(f"Current run errors on: {', '.join(live_errors)}.")
    if recent_failures > 0:
        items.append(f"Recent SendGrid failures in selected window: {recent_failures}.")
    if historical_errors_today > 0:
        items.append(f"Older same-day sender errors still exist in logs: {historical_errors_today}.")
    if not items:
        items.append("No immediate issues detected.")
    return items


def health_banner_state(
    session_label: str,
    active_profiles: int,
    live_run_errors: int,
    recent_failures: int,
) -> tuple[str, str]:
    if session_label == "dead" or live_run_errors > 0:
        return "red", f"Attention needed: {live_run_errors} live run error(s); check profile cards and latest failures."
    if recent_failures > 0:
        return "yellow", f"Caution: {recent_failures} recent SendGrid failure event(s) in the selected activity window."
    if session_label == "running" and active_profiles > 0:
        return "green", f"Healthy run: {active_profiles} active profile(s), no live sender errors detected."
    return "yellow", "Idle: session is not running."


def render_health_banner(state: str, message: str) -> None:
    css = {"green": "health-green", "yellow": "health-yellow", "red": "health-red"}.get(state, "health-yellow")
    st.markdown(f'<div class="health-banner {css}">{message}</div>', unsafe_allow_html=True)


def enable_auto_refresh(seconds: int) -> None:
    if seconds <= 0:
        return
    ms = int(seconds * 1000)
    components.html(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {ms});
        </script>
        """,
        height=0,
    )


def current_auto_refresh_value(options: List[int]) -> int:
    raw = st.query_params.get("refresh", "0")
    if isinstance(raw, list):
        raw = raw[0] if raw else "0"
    try:
        value = int(raw)
    except Exception:
        value = 0
    return value if value in options else 0


def render_status_chip(label: str, status: str) -> None:
    css = {
        "running": "status-running",
        "dead": "status-dead",
        "stopped": "status-stopped",
    }.get(status, "status-stopped")
    st.markdown(f'<span class="status-chip {css}">{label}</span>', unsafe_allow_html=True)


def render_profile_card(snapshot: ProfileSnapshot, detailed: bool = False) -> None:
    status = "dead" if snapshot.tmux_dead else "running" if snapshot.tmux_running else "stopped"
    with st.container(border=True):
        head_left, head_right = st.columns([4, 1])
        head_left.markdown(f"### {snapshot.name.replace('sendgrid_', '').title()}")
        if head_right.button("Stop", key=f"stop_{snapshot.name}", use_container_width=True):
            ok, output = stop_sendgrid_profile(snapshot.name, snapshot.pane_index)
            if ok:
                st.success(output)
            else:
                st.warning(output)
            st.rerun()
        render_status_chip(status.upper(), status)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pending", snapshot.pending_count)
        c2.metric("Run Sent", snapshot.run_sent)
        c3.metric("Run Errors", snapshot.run_errors)
        c4.metric("Run Skipped", snapshot.run_skipped)
        if snapshot.max_total > 0:
            progress = min(1.0, snapshot.run_sent / snapshot.max_total)
            st.progress(progress, text=f"Run progress: {snapshot.run_sent}/{snapshot.max_total}")
        st.caption(
            f"Last: {snapshot.last_status or '-'} | {snapshot.last_email or '-'} | "
            f"{format_when(snapshot.last_timestamp)}"
        )
        if snapshot.run_started_at:
            st.caption(f"Current run anchor: {format_when(snapshot.run_started_at)}")
        if snapshot.errors_today > snapshot.run_errors:
            st.caption(f"Historical errors earlier today: {snapshot.errors_today - snapshot.run_errors}")
        meta1, meta2, meta3 = st.columns(3)
        meta1.markdown(f"<div class='minor-label'>CSV</div><div><code>{snapshot.csv_path.name}</code></div>", unsafe_allow_html=True)
        meta2.markdown(f"<div class='minor-label'>Log</div><div><code>{snapshot.log_path.name}</code></div>", unsafe_allow_html=True)
        meta3.markdown(
            f"<div class='minor-label'>Pane</div><div><code>{snapshot.pane_index}</code> / <code>{snapshot.tmux_command or '-'}</code></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Last activity age: {format_age(snapshot.last_timestamp)}")
        if snapshot.last_info:
            st.code(snapshot.last_info, language="text")
        if detailed and snapshot.tmux_tail:
            with st.expander("Pane tail", expanded=False):
                st.code(snapshot.tmux_tail, language="text")


def render_recent_sender_table(snapshots: List[ProfileSnapshot]) -> None:
    rows = []
    for snap in snapshots:
        rows.append(
            {
                "profile": snap.name.replace("sendgrid_", ""),
                "status": snap.last_status,
                "email": snap.last_email,
                "details": snap.last_info[:160],
                "last_seen": snap.last_timestamp.strftime("%Y-%m-%d %H:%M:%S %Z") if snap.last_timestamp else "",
                "pending": snap.pending_count,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_activity_tables(activity: Dict[str, object], hours: int) -> None:
    st.subheader(f"SendGrid Activity ({hours}h)")
    a1, a2, a3 = st.columns(3)
    a1.dataframe(
        [{"status": k, "count": v} for k, v in activity["by_status"].most_common()],
        use_container_width=True,
        hide_index=True,
    )
    a2.dataframe(
        [{"profile": k, "count": v} for k, v in activity["by_profile"].most_common()],
        use_container_width=True,
        hide_index=True,
    )
    a3.dataframe(
        [{"domain": k, "count": v} for k, v in activity["by_domain"].most_common(15)],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Recent activity events")
    status_filter = st.selectbox(
        "Activity filter",
        ["all", "failures only", "delivered only"],
        index=0,
        key="activity_filter",
    )
    recent_rows = []
    for event in activity["recent"][:75]:
        status = event.get("status", "")
        status_norm = status.strip().lower()
        is_failure = status_norm in {"blocked", "bounced", "dropped", "spam report", "spam_report", "spamreport"}
        if status_filter == "failures only" and not is_failure:
            continue
        if status_filter == "delivered only" and status_norm != "delivered":
            continue
        recent_rows.append(
            {
                "time_utc": event.get("processed_at_utc", ""),
                "profile": event.get("profile", ""),
                "status": status,
                "email": event.get("email", ""),
                "code": event.get("code", ""),
                "reason": (event.get("response", "") or "")[:160],
            }
        )
    st.dataframe(recent_rows, use_container_width=True, hide_index=True)


def render_compact_failures(activity: Dict[str, object], limit: int = 8) -> None:
    failure_rows = []
    for event in activity["recent"]:
        status_norm = (event.get("status") or "").strip().lower()
        if status_norm not in {"blocked", "bounced", "dropped", "spam report", "spam_report", "spamreport"}:
            continue
        failure_rows.append(
            {
                "time": event.get("processed_at_utc", ""),
                "profile": event.get("profile", "") or "-",
                "status": event.get("status", ""),
                "email": event.get("email", ""),
                "reason": (event.get("response", "") or "")[:120],
            }
        )
        if len(failure_rows) >= limit:
            break
    if failure_rows:
        st.dataframe(failure_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No recent failure events in the selected window.")


def render_operations_panel(suppression: Dict[str, int], normalize_report: Dict[str, object]) -> None:
    op1, op2 = st.columns(2)
    if op1.button("Start SendGrid", use_container_width=True):
        ok, output = run_sendgrid_launcher()
        if ok:
            st.success(output)
        else:
            st.error(output)
    if op2.button("Stop SendGrid", use_container_width=True):
        ok, output = stop_sendgrid_session()
        if ok:
            st.success(output)
        else:
            st.warning(output)
    if st.button("Archive + Reset Sender Logs", use_container_width=True):
        ok, output = archive_reset_sender_logs()
        if ok:
            st.success(output)
        else:
            st.warning(output)

    st.markdown("#### Launcher")
    st.code('cd "/mnt/d/VS/email automation"\n./run_sendgrid_tmux.sh', language="bash")

    with st.expander("Suppression summary", expanded=False):
        st.json(suppression)
    with st.expander("Latest shard normalize report", expanded=False):
        st.json(normalize_report or {"report": "No normalize report found."})
    with st.expander("Profile configuration", expanded=False):
        config_rows = []
        for name in SENDGRID_PROFILES:
            cfg = PROFILES[name]
            config_rows.append(
                {
                    "profile": name,
                    "csv": cfg["csv"],
                    "log": cfg["log"],
                    "interval": cfg.get("interval"),
                    "cooldown_seconds": cfg.get("cooldown_seconds"),
                    "max_total": cfg.get("max_total"),
                    "stop_at_local": cfg.get("stop_at_local"),
                    "domain_log": cfg.get("domain_log"),
                }
            )
        st.dataframe(config_rows, use_container_width=True, hide_index=True)


def render_sidebar(activity_hours: int, session_label: str, activity_path: Path, suppression_path: Path, normalize_report_path: Path) -> None:
    st.sidebar.header("Monitor")
    st.sidebar.write(f"Session: `{session_label}`")
    st.sidebar.write(f"Activity window: `{activity_hours}h`")
    st.sidebar.divider()
    st.sidebar.header("Files")
    st.sidebar.write(f"Activity log: `{activity_path.name}`")
    st.sidebar.write(f"Suppressions: `{suppression_path.name}`")
    st.sidebar.write(f"Normalize report: `{normalize_report_path.name}`")
    st.sidebar.divider()
    st.sidebar.header("Use")
    st.sidebar.write("`Start All` launches tmux sender session.")
    st.sidebar.write("`Stop All` kills the whole tmux session.")
    st.sidebar.write("Each profile card has its own `Stop` button.")


def main() -> None:
    st.set_page_config(page_title="Email Automation Monitor", layout="wide")
    render_styles()

    st.title("SendGrid Monitor")
    st.caption("Live view of shard readiness, tmux session state, sender logs, suppressions, and SendGrid activity export.")

    activity_path = ROOT / "sendgridlogs"
    suppression_path = ROOT / "sendgrid_suppressions.csv"
    normalize_report_path = ROOT / "sendgrid_shard_normalize_report.json"

    toolbar_left, toolbar_mid, toolbar_refresh, toolbar_start, toolbar_stop, _ = st.columns([1, 1.2, 1.2, 1.2, 1.2, 2.2])
    if toolbar_left.button("Refresh", use_container_width=True):
        st.rerun()
    activity_hours = toolbar_mid.selectbox("Activity window", [6, 12, 24, 72, 168], index=2)
    auto_refresh_options = [0, 1, 2, 5, 10, 30]
    auto_refresh_current = current_auto_refresh_value(auto_refresh_options)
    auto_refresh_seconds = toolbar_refresh.selectbox(
        "Auto-refresh",
        auto_refresh_options,
        index=auto_refresh_options.index(auto_refresh_current),
        key="auto_refresh_select",
        format_func=lambda x: "Off" if x == 0 else f"{x}s",
    )
    if str(auto_refresh_seconds) != str(auto_refresh_current):
        st.query_params["refresh"] = str(auto_refresh_seconds)
    if toolbar_start.button("Start All", use_container_width=True):
        ok, output = run_sendgrid_launcher()
        if ok:
            st.success(output)
        else:
            st.error(output)
        st.rerun()
    if toolbar_stop.button("Stop All", use_container_width=True):
        ok, output = stop_sendgrid_session()
        if ok:
            st.success(output)
        else:
            st.warning(output)
        st.rerun()

    pane_info = tmux_pane_map()
    snapshots = [load_profile_snapshot(name, idx, pane_info) for idx, name in enumerate(SENDGRID_PROFILES)]
    email_to_profile = latest_send_profile_by_email(SENDGRID_PROFILES)
    events = load_activity_events(activity_path, email_to_profile)
    activity = summarize_activity(events, hours=activity_hours)
    suppression = load_suppression_summary(suppression_path)
    normalize_report = load_json_report(normalize_report_path)

    session_label = session_status(snapshots)
    render_sidebar(activity_hours, session_label, activity_path, suppression_path, normalize_report_path)

    total_pending = sum(s.pending_count for s in snapshots)
    total_sent_today = sum(s.run_sent for s in snapshots)
    total_errors_today = sum(s.run_errors for s in snapshots)
    total_skipped_today = sum(s.run_skipped for s in snapshots)
    historical_errors_today = sum(max(0, s.errors_today - s.run_errors) for s in snapshots)
    recent_failures = recent_failure_count(activity)
    active_profiles = sum(1 for s in snapshots if s.tmux_running and not s.tmux_dead)
    attention_items = build_attention_items(session_label, snapshots, recent_failures, historical_errors_today)
    banner_state, banner_message = health_banner_state(session_label, active_profiles, total_errors_today, recent_failures)
    enable_auto_refresh(auto_refresh_seconds)

    render_health_banner(banner_state, banner_message)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Session", session_label.upper())
    m2.metric("Active Profiles", active_profiles)
    m3.metric("Pending", total_pending)
    m4.metric("Run Sent", total_sent_today)
    m5.metric("Run Errors", total_errors_today)
    m6.metric("Run Skipped", total_skipped_today)
    st.caption(f"Last refresh: {format_when(datetime.now().astimezone())}")

    if session_label == "running":
        st.success("SendGrid tmux session is running.")
    elif session_label == "dead":
        st.error("At least one tmux pane is marked dead.")
    else:
        st.warning("SendGrid tmux session is not running.")

    if recent_failures > 0:
        st.warning(f"Recent SendGrid activity shows {recent_failures} failure event(s) in the selected window.")
    if total_errors_today > 0:
        st.warning(f"Sender logs show {total_errors_today} error event(s) today.")
    elif historical_errors_today > 0:
        st.info(f"Current run is clean; {historical_errors_today} older error event(s) remain in today's logs from earlier attempts.")

    overview_tab, profiles_tab, activity_tab, ops_tab = st.tabs(["Overview", "Profiles", "Activity", "Operations"])

    with overview_tab:
        left, right = st.columns([1.15, 1])
        with left:
            st.subheader("Session overview")
            summary_rows = []
            for snap in snapshots:
                summary_rows.append(
                    {
                        "profile": snap.name.replace("sendgrid_", ""),
                        "pane": "running" if snap.tmux_running and not snap.tmux_dead else "dead" if snap.tmux_dead else "stopped",
                        "pending": snap.pending_count,
                        "run_sent": snap.run_sent,
                        "run_errors": snap.run_errors,
                        "run_skipped": snap.run_skipped,
                        "historical_errors_today": max(0, snap.errors_today - snap.run_errors),
                        "last_seen_age": format_age(snap.last_timestamp),
                        "last_status": snap.last_status,
                    }
                )
            st.dataframe(summary_rows, use_container_width=True, hide_index=True)
            st.markdown("#### Latest sender rows")
            render_recent_sender_table(snapshots)
        with right:
            st.subheader("Needs attention")
            for item in attention_items:
                st.write(f"- {item}")
            st.markdown("#### Latest failures")
            render_compact_failures(activity)
            st.markdown("#### Recent activity mix")
            st.dataframe(
                [{"status": k, "count": v} for k, v in activity["by_status"].most_common()],
                use_container_width=True,
                hide_index=True,
            )
            st.dataframe(
                [{"profile": k, "count": v} for k, v in activity["by_profile"].most_common()],
                use_container_width=True,
                hide_index=True,
            )

    with profiles_tab:
        profile_tabs = st.tabs([name.replace("sendgrid_", "").title() for name in SENDGRID_PROFILES])
        for tab, snap in zip(profile_tabs, snapshots):
            with tab:
                render_profile_card(snap, detailed=True)

    with activity_tab:
        render_activity_tables(activity, activity_hours)

    with ops_tab:
        render_operations_panel(suppression, normalize_report)


if __name__ == "__main__":
    main()
