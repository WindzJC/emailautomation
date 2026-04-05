from __future__ import annotations

import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo

import settings
from private_bounce_hygiene import private_bounce_guard_status
from provider_pacing import provider_pacing_status
from send_shard import PROFILES
from sendgrid_hygiene import (
    WEBHOOK_DEDUPE_DB,
    WEBHOOK_EVENTS_JSONL,
    domain_from_email,
    load_events_jsonl,
    load_suppression_records,
    load_webhook_dedupe_stats,
    parse_activity_file,
    parse_iso_utc,
)


ROOT = settings.APP_ROOT
PYTHON_BIN = ROOT / ".venv" / "bin" / "python"
SHARDS_DIR = settings.SHARDS_DIR
LOGS_DIR = settings.LOGS_DIR
STATE_DIR = settings.STATE_DIR
ACTIVITY_LOG_PATH = settings.ACTIVITY_LOG_PATH
SUPPRESSION_CSV = settings.SENDGRID_SUPPRESSIONS_PATH
NORMALIZE_REPORT_PATH = settings.SENDGRID_NORMALIZE_REPORT_PATH
WEBHOOK_EVENTS_PATH = settings.WEBHOOK_EVENTS_PATH
WEBHOOK_DEDUPE_PATH = settings.WEBHOOK_DEDUPE_PATH
LOG_RESET_BACKUP_ROOT = settings.LOG_RESET_BACKUP_ROOT
TMUX_SESSION_NAME = os.environ.get("TMUX_SENDGRID_SESSION", "sendgrid").strip() or "sendgrid"
DASHBOARD_TIMEZONE_NAME = os.environ.get("DASHBOARD_TIMEZONE", "America/Los_Angeles").strip() or "America/Los_Angeles"
DASHBOARD_RUN_SETTINGS_PATH = settings.DASHBOARD_RUN_SETTINGS_PATH
DASHBOARD_TIMER_STATE_PATH = settings.STATE_DIR / "dashboard_timer_state.json"
SHELL_COMMANDS = {"", "bash", "sh", "zsh", "fish"}
SENDGRID_ENV_FILES = settings.ENV_FILES
DEFAULT_AUTO_START_LOCAL_TIME = "18:00"
SENDGRID_PROFILES = [
    name for name, cfg in PROFILES.items() if str(cfg.get("provider") or "") == "sendgrid"
]
DASHBOARD_PROFILES = [
    name
    for name, cfg in PROFILES.items()
    if str(cfg.get("provider") or "") == "sendgrid" or bool(cfg.get("dashboard_enabled"))
]
START_ALL_PROFILES = [
    name
    for name in DASHBOARD_PROFILES
    if not bool(PROFILES.get(name, {}).get("dashboard_manual_only"))
]

STATUS_ALIASES = {
    "processed": "processed",
    "delivered": "delivered",
    "open": "open",
    "opened": "open",
    "click": "click",
    "clicked": "click",
    "deferred": "deferred",
    "bounce": "bounce",
    "bounced": "bounce",
    "blocked": "blocked",
    "drop": "dropped",
    "dropped": "dropped",
    "spamreport": "spamreport",
    "unsubscribe": "unsubscribe",
    "unsubscribed": "unsubscribe",
    "groupunsubscribe": "group_unsubscribe",
}

FAILURE_STATUS_KEYS = {"bounce", "blocked", "dropped", "spamreport"}
ACTIVE_RUNTIME_STATES = {"starting", "running", "cooldown", "sleeping"}
BATCH_SLEEP_RE = re.compile(r"next_sleep_seconds=(\d+)")
FINAL_OUTCOME_STATUS_KEYS = {
    "delivered",
    "open",
    "click",
    "bounce",
    "blocked",
    "dropped",
    "spamreport",
    "unsubscribe",
    "group_unsubscribe",
}
WEBHOOK_SIGNATURE_ENABLED = bool(os.environ.get("SENDGRID_EVENT_PUBLIC_KEY", "").strip())
TREND_METRIC_KEYS = ("accepted", "delivered", "failures", "opened")
AWAITING_BUCKET_ORDER = ("lt_10m", "m10_to_60", "h1_to_24", "gt_24h")
AWAITING_BUCKET_LABELS = {
    "lt_10m": "<10m",
    "m10_to_60": "10-60m",
    "h1_to_24": "1-24h",
    "gt_24h": ">24h",
}
AUTO_STOP_EVENT_LOCK = threading.Lock()
AUTO_STOP_EVENTS: Dict[str, Dict[str, object]] = {}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


ALERT_RECENT_FAILURES_THRESHOLD = _env_int("DASHBOARD_ALERT_RECENT_FAILURES", 1)
ALERT_TOTAL_AWAITING_THRESHOLD = _env_int("DASHBOARD_ALERT_TOTAL_AWAITING", 10)
ALERT_PROFILE_AWAITING_THRESHOLD = _env_int("DASHBOARD_ALERT_PROFILE_AWAITING", 5)
ALERT_UNMAPPED_THRESHOLD = _env_int("DASHBOARD_ALERT_UNMAPPED", 10)
ALERT_WEBHOOK_STALE_MINUTES = _env_int("DASHBOARD_ALERT_WEBHOOK_STALE_MINUTES", 20)
PROFILE_GUARD_ENABLED = _env_bool("DASHBOARD_PROFILE_GUARD_ENABLED", True)
PROFILE_GUARD_BOUNCE_THRESHOLD = _env_int("DASHBOARD_PROFILE_GUARD_BOUNCES", 3)
PROFILE_GUARD_RECENT_ACCEPT_WINDOW = _env_int("DASHBOARD_PROFILE_GUARD_RECENT_ACCEPT_WINDOW", 10)
PROFILE_GUARD_NOTICE_HOURS = _env_int("DASHBOARD_PROFILE_GUARD_NOTICE_HOURS", 12)
PROFILE_GUARD_SPAMREPORT_ENABLED = _env_bool("DASHBOARD_PROFILE_GUARD_SPAMREPORT", True)


def _resolve_dashboard_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(DASHBOARD_TIMEZONE_NAME)
    except Exception:
        return ZoneInfo("UTC")


DASHBOARD_TIMEZONE = _resolve_dashboard_timezone()


@dataclass
class ProfileSnapshot:
    name: str
    pane_index: int
    csv_path: str
    log_path: str
    max_total: int
    cooldown_seconds: int
    cooldown_remaining_seconds: int
    pending_count: int
    run_started_at: str
    run_sent: int
    run_errors: int
    run_skipped: int
    sent_today: int
    errors_today: int
    skipped_today: int
    last_status: str
    last_email: str
    last_info: str
    last_timestamp: str
    last_age: str
    tmux_running: bool
    tmux_dead: bool
    tmux_command: str
    tmux_tail: str
    runtime_state: str
    runtime_label: str
    runtime_note: str
    configured_max_total: int = 0
    effective_cooldown_seconds: int = 0
    provider_cooldown_remaining_seconds: int = 0
    provider_cooldown_until: str = ""
    restart_blocked: bool = False
    restart_block_reason: str = ""
    health_label: str = ""
    health_tone: str = ""
    health_note: str = ""


@dataclass(frozen=True)
class SendAttempt:
    profile: str
    email: str
    timestamp: datetime
    message_id: str


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _managed_path(base_dir: Path, value: object) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return base_dir / path.name


def _profile_csv_path(cfg: Dict[str, object]) -> Path:
    path = _managed_path(SHARDS_DIR, cfg.get("csv") or "")
    name = Path(str(cfg.get("csv") or "")).name
    if name:
        settings.ensure_managed_shard_file(path, name)
    return path


def _profile_log_path(cfg: Dict[str, object]) -> Path:
    path = _managed_path(LOGS_DIR, cfg.get("log") or "")
    name = Path(str(cfg.get("log") or "")).name
    if name:
        settings.maybe_seed_file(path, name)
    return path


def profile_session_name(profile_name: str) -> str:
    cfg = PROFILES.get(profile_name, {})
    return str(cfg.get("tmux_session") or TMUX_SESSION_NAME).strip() or TMUX_SESSION_NAME


def profile_pane_index(profile_name: str) -> int:
    if profile_name in SENDGRID_PROFILES:
        return SENDGRID_PROFILES.index(profile_name)
    return int(PROFILES.get(profile_name, {}).get("tmux_pane_index") or 0)


def default_dashboard_send_cap_per_profile() -> int:
    for profile_name in START_ALL_PROFILES:
        cfg = PROFILES.get(profile_name, {})
        try:
            value = int(cfg.get("max_total") or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    return max(1, int(settings.SEND_CAP_DEFAULT))


def _normalize_dashboard_local_time(value: object, default: str = DEFAULT_AUTO_START_LOCAL_TIME) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return default
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return default
    return f"{hour:02d}:{minute:02d}"


def _default_dashboard_run_settings() -> Dict[str, object]:
    default_cap = default_dashboard_send_cap_per_profile()
    return {
        "send_cap_per_profile": default_cap,
        "auto_start_sendgrid_enabled": True,
        "auto_start_sendgrid_local_time": DEFAULT_AUTO_START_LOCAL_TIME,
        "auto_start_private_jc_enabled": True,
        "auto_start_private_jc_local_time": DEFAULT_AUTO_START_LOCAL_TIME,
        "updated_at_utc": "",
    }


def load_dashboard_run_settings() -> Dict[str, object]:
    defaults = _default_dashboard_run_settings()
    settings: Dict[str, object] = dict(defaults)
    if not DASHBOARD_RUN_SETTINGS_PATH.exists():
        return settings
    try:
        raw = json.loads(DASHBOARD_RUN_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return settings
    if not isinstance(raw, dict):
        return settings
    try:
        send_cap = int(raw.get("send_cap_per_profile") or defaults["send_cap_per_profile"])
    except Exception:
        send_cap = int(defaults["send_cap_per_profile"])
    settings["send_cap_per_profile"] = max(1, send_cap)
    settings["auto_start_sendgrid_enabled"] = bool(raw.get("auto_start_sendgrid_enabled", defaults["auto_start_sendgrid_enabled"]))
    settings["auto_start_sendgrid_local_time"] = _normalize_dashboard_local_time(
        raw.get("auto_start_sendgrid_local_time"),
        default=str(defaults["auto_start_sendgrid_local_time"]),
    )
    settings["auto_start_private_jc_enabled"] = bool(raw.get("auto_start_private_jc_enabled", defaults["auto_start_private_jc_enabled"]))
    settings["auto_start_private_jc_local_time"] = _normalize_dashboard_local_time(
        raw.get("auto_start_private_jc_local_time"),
        default=str(defaults["auto_start_private_jc_local_time"]),
    )
    settings["updated_at_utc"] = str(raw.get("updated_at_utc") or "")
    return settings


def save_dashboard_run_settings_patch(patch: Dict[str, object]) -> Dict[str, object]:
    current = load_dashboard_run_settings()
    payload = {
        "send_cap_per_profile": max(1, int(patch.get("send_cap_per_profile", current["send_cap_per_profile"]))),
        "auto_start_sendgrid_enabled": bool(patch.get("auto_start_sendgrid_enabled", current["auto_start_sendgrid_enabled"])),
        "auto_start_sendgrid_local_time": _normalize_dashboard_local_time(
            patch.get("auto_start_sendgrid_local_time", current["auto_start_sendgrid_local_time"]),
            default=str(current["auto_start_sendgrid_local_time"]),
        ),
        "auto_start_private_jc_enabled": bool(patch.get("auto_start_private_jc_enabled", current["auto_start_private_jc_enabled"])),
        "auto_start_private_jc_local_time": _normalize_dashboard_local_time(
            patch.get("auto_start_private_jc_local_time", current["auto_start_private_jc_local_time"]),
            default=str(current["auto_start_private_jc_local_time"]),
        ),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    DASHBOARD_RUN_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DASHBOARD_RUN_SETTINGS_PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(DASHBOARD_RUN_SETTINGS_PATH)
    return payload


def save_dashboard_send_cap_per_profile(send_cap_per_profile: int) -> Dict[str, object]:
    return save_dashboard_run_settings_patch({
        "send_cap_per_profile": max(1, int(send_cap_per_profile)),
    })


def dashboard_send_cap_per_profile() -> int:
    settings = load_dashboard_run_settings()
    try:
        return max(1, int(settings.get("send_cap_per_profile") or default_dashboard_send_cap_per_profile()))
    except Exception:
        return default_dashboard_send_cap_per_profile()


def parse_log_timestamp(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def load_dashboard_recovery_timer() -> Dict[str, str]:
    state = {
        "private_jc_recovery_start_at_utc": "",
        "private_jc_recovery_note": "",
        "updated_at_utc": "",
    }
    if not DASHBOARD_TIMER_STATE_PATH.exists():
        return state
    try:
        raw = json.loads(DASHBOARD_TIMER_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return state
    if not isinstance(raw, dict):
        return state
    for key in state:
        state[key] = str(raw.get(key) or "")
    return state


def dashboard_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(DASHBOARD_TIMEZONE)


def count_pending(path: Path) -> int:
    return max(0, len(read_csv_rows(path)))


def format_when(ts: Optional[datetime]) -> str:
    if not ts:
        return ""
    return ts.astimezone(DASHBOARD_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %Z")


def format_age(ts: Optional[datetime]) -> str:
    if not ts:
        return "-"
    now = dashboard_now()
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


def canonical_event_status(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())
    if not compact:
        return ""
    return STATUS_ALIASES.get(compact, compact)


def local_today_bounds() -> tuple[datetime, datetime]:
    now = dashboard_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _nonempty_tail_lines(tail: str) -> List[str]:
    return [line.strip() for line in (tail or "").splitlines() if line.strip()]


def _last_line_with(lines: Sequence[str], token: str) -> str:
    token_lower = token.lower()
    for line in reversed(lines):
        if token_lower in line.lower():
            return line
    return ""


def _last_line_startswith(lines: Sequence[str], prefix: str) -> str:
    prefix_lower = prefix.lower()
    for line in reversed(lines):
        if line.lower().startswith(prefix_lower):
            return line
    return ""


def latest_batch_sleep_seconds(tail: str) -> int:
    matches = BATCH_SLEEP_RE.findall(tail or "")
    if not matches:
        return 0
    try:
        return max(0, int(matches[-1]))
    except Exception:
        return 0


def infer_runtime_state(current_cmd: str, pane_dead: bool, tail: str) -> Tuple[str, str, str]:
    lines = _nonempty_tail_lines(tail)
    tail_lower = "\n".join(line.lower() for line in lines)
    shell_idle = (current_cmd or "").strip() in SHELL_COMMANDS

    if pane_dead:
        return "dead", "Dead", "tmux pane terminated unexpectedly."

    if not shell_idle:
        if "traceback (most recent call last)" in tail_lower and "keyboardinterrupt" not in tail_lower:
            return "error", "Error", _last_line_with(lines, "error") or "Sender raised an exception."
        if "sendgrid throttle: sleeping" in tail_lower or ("pause:" in tail_lower and "sleeping" in tail_lower):
            return (
                "sleeping",
                "Sleeping",
                _last_line_with(lines, "sleeping") or "Sender is backing off before the next attempt.",
            )
        next_sleep_seconds = latest_batch_sleep_seconds(tail)
        if next_sleep_seconds > 0:
            return "cooldown", "Cooldown", f"Cooling down between sends: {next_sleep_seconds}s."
        if ("profile:" in tail_lower or "preflight" in tail_lower) and "batch:" not in tail_lower:
            return "starting", "Starting", _last_line_with(lines, "profile:") or "Sender is starting up."
        return "running", "Running", "Sender is actively processing recipients."

    stop_line = _last_line_startswith(lines, "STOP:")
    done_line = _last_line_startswith(lines, "DONE:")
    error_line = _last_line_with(lines, "error")

    if "keyboardinterrupt" in tail_lower:
        if "time.sleep" in tail_lower or "cooldown_seconds" in tail_lower:
            return "stopped", "Stopped", "Interrupted manually during cooldown."
        return "stopped", "Stopped", "Interrupted manually."
    if stop_line:
        stop_lower = stop_line.lower()
        if "schedule_end" in stop_lower:
            return "scheduled_stop", "Scheduled Stop", "Stopped by the configured schedule window."
        if "max_total" in stop_lower or "daily_cap" in stop_lower:
            return "finished", "Finished", stop_line
        if "provider_throttle_cooldown" in stop_lower:
            return "paused", "Paused", "Provider cooldown is active before the next safe restart."
        if "auth_error" in stop_lower or "account_error" in stop_lower or "reconnect_failed" in stop_lower:
            return "error", "Error", stop_line
        return "stopped", "Stopped", stop_line
    if done_line:
        return "finished", "Finished", done_line
    if "traceback (most recent call last)" in tail_lower or error_line:
        return "error", "Error", error_line or "Sender exited after an error."
    return "stopped", "Stopped", "Pane is idle."


def profile_is_active(snapshot: ProfileSnapshot) -> bool:
    return snapshot.runtime_state in ACTIVE_RUNTIME_STATES and not snapshot.tmux_dead


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
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return {}
    panes: Dict[str, Dict[str, str]] = {}
    for line in out.splitlines():
        idx, dead, cmd = (line.split("\t", 2) + ["", ""])[:3]
        panes[idx] = {"dead": dead, "cmd": cmd}
    return panes


def _tmux_target_exists(target: str) -> bool:
    proc = subprocess.run(
        ["tmux", "has-session", "-t", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _load_env_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=\s*(.+?)\s*$")
    for path in SENDGRID_ENV_FILES:
        if not path.exists():
            continue
        try:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                match = pattern.match(raw_line)
                if not match:
                    continue
                raw_value = match.group(1).strip()
                if raw_value and raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'}:
                    raw_value = raw_value[1:-1]
                return raw_value.strip()
        except Exception:
            continue
    return ""


def ensure_sendgrid_session_layout(session: str = TMUX_SESSION_NAME) -> tuple[bool, str]:
    target = f"{session}:run"
    if _tmux_target_exists(target):
        pane_info = tmux_pane_map(session)
        if len(pane_info) >= len(SENDGRID_PROFILES):
            return True, f"tmux layout ready: {target}"
        return False, f"tmux layout incomplete for {target}; use Start All to rebuild the session."

    if _tmux_target_exists(session):
        proc = subprocess.run(
            ["tmux", "new-window", "-d", "-t", session, "-n", "run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
            return False, output or f"Unable to create tmux window {target}."
    else:
        proc = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-n", "run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
            return False, output or f"Unable to create tmux session {session}."

    split_commands = [
        ["tmux", "split-window", "-h", "-t", target],
        ["tmux", "split-window", "-v", "-t", f"{target}.0"],
        ["tmux", "split-window", "-v", "-t", f"{target}.1"],
        ["tmux", "split-window", "-v", "-t", f"{target}.2"],
        ["tmux", "select-layout", "-t", target, "tiled"],
    ]
    for command in split_commands:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
            return False, output or f"Unable to prepare tmux layout for {target}."
    return True, f"tmux layout created: {target}"


def ensure_single_profile_session(session: str) -> tuple[bool, str]:
    target = f"{session}:run"
    if _tmux_target_exists(target):
        return True, f"tmux layout ready: {target}"
    if _tmux_target_exists(session):
        proc = subprocess.run(
            ["tmux", "new-window", "-d", "-t", session, "-n", "run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
            return False, output or f"Unable to create tmux window {target}."
        return True, f"tmux layout ready: {target}"
    proc = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-n", "run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
        return False, output or f"Unable to create tmux session {session}."
    return True, f"tmux layout created: {target}"


def tmux_capture_tail(pane_index: int, session: str = "sendgrid", lines: int = 16) -> str:
    try:
        out = subprocess.check_output(
            ["tmux", "capture-pane", "-p", "-t", f"{session}:run.{pane_index}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""
    return "\n".join(out.splitlines()[-lines:]).strip()


def load_sendgrid_profile_snapshots(session: str = "sendgrid", tail_lines: int = 12) -> List[ProfileSnapshot]:
    pane_info = tmux_pane_map(session)
    return [load_profile_snapshot(name, idx, pane_info, tail_lines=tail_lines) for idx, name in enumerate(SENDGRID_PROFILES)]


def active_sendgrid_profile_snapshots(session: str = "sendgrid", tail_lines: int = 12) -> List[ProfileSnapshot]:
    return [snapshot for snapshot in load_sendgrid_profile_snapshots(session=session, tail_lines=tail_lines) if profile_is_active(snapshot)]


def load_dashboard_profile_snapshots(tail_lines: int = 12) -> List[ProfileSnapshot]:
    snapshots: List[ProfileSnapshot] = []
    pane_maps: Dict[str, Dict[str, Dict[str, str]]] = {}
    for profile_name in DASHBOARD_PROFILES:
        session = profile_session_name(profile_name)
        pane_info = pane_maps.get(session)
        if pane_info is None:
            pane_info = tmux_pane_map(session)
            pane_maps[session] = pane_info
        snapshots.append(load_profile_snapshot(profile_name, profile_pane_index(profile_name), pane_info, tail_lines=tail_lines))
    return snapshots


def active_dashboard_profile_snapshots(tail_lines: int = 12) -> List[ProfileSnapshot]:
    return [snapshot for snapshot in load_dashboard_profile_snapshots(tail_lines=tail_lines) if profile_is_active(snapshot)]


def run_sendgrid_launcher() -> tuple[bool, str]:
    env = os.environ.copy()
    env["TMUX_SENDGRID_ATTACH"] = "0"
    env["SENDGRID_DASHBOARD_MAX_TOTAL"] = str(dashboard_send_cap_per_profile())
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


def _python_runtime_bin() -> Path:
    if PYTHON_BIN.exists():
        return PYTHON_BIN
    return Path(shutil.which("python3") or "")


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


def start_private_profile(profile_name: str, session: str) -> tuple[bool, str]:
    if profile_name not in DASHBOARD_PROFILES:
        return False, f"Unknown profile: {profile_name}"
    cfg = PROFILES.get(profile_name, {})
    provider = str(cfg.get("provider") or "").strip().lower()
    cooldown_seconds = max(0, int(cfg.get("cooldown_seconds") or 0))
    pacing = provider_pacing_status(profile_name, provider, cooldown_seconds)
    remaining_seconds = max(0, int(pacing.get("cooldown_remaining_seconds") or 0))
    if remaining_seconds <= 0 and profile_name == "private_jc":
        timer_state = load_dashboard_recovery_timer()
        recovery_target = parse_iso_utc(timer_state.get("private_jc_recovery_start_at_utc"))
        if recovery_target and recovery_target > datetime.now(timezone.utc):
            remaining_seconds = max(0, int((recovery_target - datetime.now(timezone.utc)).total_seconds()))
            pacing = {
                **pacing,
                "cooldown_until_utc": recovery_target.isoformat(),
            }
    if remaining_seconds > 0:
        cooldown_until = str(pacing.get("cooldown_until_utc") or "")
        next_safe_start = format_when(parse_iso_utc(cooldown_until)) or cooldown_until
        remaining_minutes = max(1, int((remaining_seconds + 59) / 60))
        return (
            False,
            f"{profile_name} is paused by provider cooldown for about {remaining_minutes} minute(s). "
            f"Next safe start {next_safe_start}.",
        )
    password_env = str(cfg.get("password_env") or "").strip()
    if provider in {"private", "gmail"}:
        if not password_env:
            return False, f"{profile_name} is missing password_env for dashboard launches."
        if not _load_env_value(password_env):
            return False, f"{password_env} is not available in the dashboard environment."
    python_bin = _python_runtime_bin()
    if not python_bin:
        return False, "Missing Python runtime for dashboard launches."

    ok, message = ensure_single_profile_session(session)
    if not ok:
        return False, message

    pane_index = profile_pane_index(profile_name)
    pane_info = tmux_pane_map(session)
    pane = pane_info.get(str(pane_index), {})
    current_cmd = (pane.get("cmd") or "").strip()
    if pane and current_cmd not in SHELL_COMMANDS:
        return False, f"{profile_name} is already running in pane {pane_index}."

    preflight = subprocess.run(
        [str(python_bin), "send_shard.py", "--profile", profile_name, "--preflight"],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if preflight.returncode != 0:
        output = "\n".join(part for part in [preflight.stdout.strip(), preflight.stderr.strip()] if part).strip()
        return False, output or f"Preflight failed for {profile_name}."

    target = f"{session}:run.{pane_index}"
    command = f"cd {shlex.quote(str(ROOT))} && {shlex.quote(str(python_bin))} send_shard.py --profile {shlex.quote(profile_name)}"
    subprocess.run(
        ["tmux", "send-keys", "-t", target, "C-c"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    proc = subprocess.run(
        ["tmux", "send-keys", "-t", target, command, "C-m"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
        return False, output or f"Unable to start {profile_name} in pane {pane_index}."
    return True, f"Started {profile_name} in pane {pane_index}."


def stop_private_profile(profile_name: str, session: str) -> tuple[bool, str]:
    pane_index = profile_pane_index(profile_name)
    return stop_sendgrid_profile(profile_name, pane_index, session=session)


def start_sendgrid_profile(profile_name: str, pane_index: int, session: str = TMUX_SESSION_NAME) -> tuple[bool, str]:
    if profile_name not in SENDGRID_PROFILES:
        return False, f"Unknown profile: {profile_name}"
    if not PYTHON_BIN.exists():
        return False, f"Missing Python venv at {PYTHON_BIN}"

    api_key = _load_env_value("SENDGRID_API_KEY")
    if not api_key:
        return False, "SENDGRID_API_KEY is not available in the dashboard environment."

    ok, message = ensure_sendgrid_session_layout(session)
    if not ok:
        return False, message

    pane_info = tmux_pane_map(session)
    pane = pane_info.get(str(pane_index), {})
    current_cmd = (pane.get("cmd") or "").strip()
    if pane and current_cmd not in SHELL_COMMANDS:
        return False, f"{profile_name} is already running in pane {pane_index}."

    env = os.environ.copy()
    env["SENDGRID_API_KEY"] = api_key
    max_total_override = dashboard_send_cap_per_profile()
    preflight = subprocess.run(
        [
            str(PYTHON_BIN),
            "send_shard.py",
            "--profile",
            profile_name,
            "--preflight",
            "--max_total",
            str(max_total_override),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if preflight.returncode != 0:
        output = "\n".join(part for part in [preflight.stdout.strip(), preflight.stderr.strip()] if part).strip()
        return False, output or f"Preflight failed for {profile_name}."

    proc = subprocess.run(
        ["tmux", "set-environment", "-t", session, "SENDGRID_API_KEY", api_key],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
        return False, output or f"Unable to set SENDGRID_API_KEY for tmux session {session}."

    target = f"{session}:run.{pane_index}"
    command = (
        f"cd {shlex.quote(str(ROOT))} && "
        f"export SENDGRID_API_KEY={shlex.quote(api_key)} && "
        f"{shlex.quote(str(PYTHON_BIN))} send_shard.py --profile {shlex.quote(profile_name)} "
        f"--max_total {max_total_override}"
    )
    subprocess.run(
        ["tmux", "send-keys", "-t", target, "C-c"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    proc = subprocess.run(
        ["tmux", "send-keys", "-t", target, command, "C-m"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
        return False, output or f"Unable to start {profile_name} in pane {pane_index}."
    return True, f"Started {profile_name} in pane {pane_index}."


def archive_reset_sender_logs(session: str = "sendgrid") -> tuple[bool, str]:
    for profile_name in DASHBOARD_PROFILES:
        profile_session = profile_session_name(profile_name)
        pane_info = tmux_pane_map(profile_session)
        if any((pane.get("cmd") or "").strip() not in {"", "bash", "sh", "zsh", "fish"} for pane in pane_info.values()):
            return False, "Stop all dashboard sender sessions before archiving/resetting logs."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = LOG_RESET_BACKUP_ROOT / f"log_reset_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    reset_count = 0
    for name in DASHBOARD_PROFILES:
        log_path = _profile_log_path(PROFILES[name])
        backup_path = backup_root / log_path.name
        if log_path.exists():
            shutil.copy2(log_path, backup_path)
        else:
            backup_path.write_text("", encoding="utf-8")
        log_path.write_text("TimestampUTC,Email,Status,Info\n", encoding="utf-8", newline="")
        reset_count += 1
    return True, f"Archived and reset {reset_count} sender log(s) to {backup_root}."


def load_profile_snapshot(profile_name: str, pane_index: int, pane_info: Dict[str, Dict[str, str]], tail_lines: int = 16) -> ProfileSnapshot:
    cfg = PROFILES[profile_name]
    csv_path = _profile_csv_path(cfg)
    log_path = _profile_log_path(cfg)
    configured_max_total = int(cfg.get("max_total") or 0)
    effective_max_total = dashboard_send_cap_per_profile() if profile_name in SENDGRID_PROFILES else configured_max_total
    cooldown_seconds = max(0, int(cfg.get("cooldown_seconds") or 0))
    provider_name = str(cfg.get("provider") or "").strip().lower()
    pacing = provider_pacing_status(profile_name, provider_name, cooldown_seconds)
    effective_cooldown_seconds = max(cooldown_seconds, int(pacing.get("recommended_cooldown_seconds") or 0))
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
    pane_dead = pane.get("dead") == "1"
    tmux_tail = tmux_capture_tail(pane_index, lines=tail_lines) if pane else ""
    runtime_state, runtime_label, runtime_note = infer_runtime_state(current_cmd, pane_dead, tmux_tail)
    cooldown_remaining_seconds = 0
    provider_cooldown_remaining_seconds = max(0, int(pacing.get("cooldown_remaining_seconds") or 0))
    provider_cooldown_until = str(pacing.get("cooldown_until_utc") or "")
    if provider_cooldown_remaining_seconds <= 0 and profile_name == "private_jc":
        timer_state = load_dashboard_recovery_timer()
        recovery_target = parse_iso_utc(timer_state.get("private_jc_recovery_start_at_utc"))
        if recovery_target and recovery_target > datetime.now(timezone.utc):
            provider_cooldown_until = recovery_target.isoformat()
            provider_cooldown_remaining_seconds = max(0, int((recovery_target - datetime.now(timezone.utc)).total_seconds()))
    restart_blocked = provider_cooldown_remaining_seconds > 0
    restart_block_reason = ""
    if restart_blocked:
        restart_block_reason = (
            f"Provider cooldown active for about {max(1, int((provider_cooldown_remaining_seconds + 59) / 60))} minute(s). "
            f"Next safe start {format_when(parse_iso_utc(provider_cooldown_until)) or provider_cooldown_until}."
        )
    if runtime_state == "cooldown" and effective_cooldown_seconds > 0 and last_timestamp is not None:
        elapsed = max(0, int((datetime.now(timezone.utc) - last_timestamp).total_seconds()))
        cooldown_remaining_seconds = max(0, effective_cooldown_seconds - elapsed)
        runtime_note = f"Cooling down between sends: {cooldown_remaining_seconds}s remaining."
    elif restart_blocked and runtime_state not in ACTIVE_RUNTIME_STATES:
        runtime_state = "paused"
        runtime_label = "Paused"
        runtime_note = restart_block_reason
    running = runtime_state in ACTIVE_RUNTIME_STATES and not pane_dead
    return ProfileSnapshot(
        name=profile_name,
        pane_index=pane_index,
        csv_path=csv_path.name,
        log_path=log_path.name,
        configured_max_total=configured_max_total,
        max_total=effective_max_total,
        cooldown_seconds=cooldown_seconds,
        cooldown_remaining_seconds=cooldown_remaining_seconds,
        pending_count=count_pending(csv_path),
        run_started_at=format_when(run_started_at),
        run_sent=run_sent,
        run_errors=run_errors,
        run_skipped=run_skipped,
        sent_today=sent_today,
        errors_today=errors_today,
        skipped_today=skipped_today,
        last_status=last_status,
        last_email=last_email,
        last_info=last_info,
        last_timestamp=format_when(last_timestamp),
        last_age=format_age(last_timestamp),
        tmux_running=running,
        tmux_dead=pane_dead,
        tmux_command=current_cmd,
        tmux_tail=tmux_tail,
        runtime_state=runtime_state,
        runtime_label=runtime_label,
        runtime_note=runtime_note,
        effective_cooldown_seconds=effective_cooldown_seconds,
        provider_cooldown_remaining_seconds=provider_cooldown_remaining_seconds,
        provider_cooldown_until=provider_cooldown_until,
        restart_blocked=restart_blocked,
        restart_block_reason=restart_block_reason,
    )


def collect_send_attempts(profile_names: Iterable[str]) -> List[SendAttempt]:
    attempts: List[SendAttempt] = []
    for profile_name in profile_names:
        cfg = PROFILES[profile_name]
        for row in read_csv_rows(_profile_log_path(cfg)):
            if (row.get("Status") or "").strip() != "SENT":
                continue
            email = (row.get("Email") or "").strip().lower()
            ts = parse_log_timestamp(row.get("TimestampUTC", ""))
            if not email or not ts:
                continue
            attempts.append(
                SendAttempt(
                    profile=profile_name,
                    email=email,
                    timestamp=ts,
                    message_id=extract_message_id_from_info(row.get("Info", "")),
                )
            )
    return attempts


def unique_send_profile_by_email(attempts: Sequence[SendAttempt]) -> Dict[str, str]:
    latest: Dict[str, tuple[datetime, str]] = {}
    candidates: Dict[str, Set[str]] = {}
    for attempt in attempts:
        candidates.setdefault(attempt.email, set()).add(attempt.profile)
        current = latest.get(attempt.email)
        if current is None or attempt.timestamp >= current[0]:
            latest[attempt.email] = (attempt.timestamp, attempt.profile)
    return {
        email: profile
        for email, (_, profile) in latest.items()
        if len(candidates.get(email, set())) == 1
    }


def canonical_message_id(value: str) -> str:
    raw = (value or "").strip().lower().strip("<>")
    if not raw:
        return ""
    return raw.split(".", 1)[0]


def extract_message_id_from_info(info: str) -> str:
    match = re.search(r"sg_message_id=([^\s]+)", info or "")
    return canonical_message_id(match.group(1)) if match else ""


def latest_send_profile_by_message_id(attempts: Sequence[SendAttempt]) -> Dict[str, str]:
    latest: Dict[str, tuple[datetime, str]] = {}
    for attempt in attempts:
        if not attempt.message_id:
            continue
        current = latest.get(attempt.message_id)
        if current is None or attempt.timestamp >= current[0]:
            latest[attempt.message_id] = (attempt.timestamp, attempt.profile)
    return {message_id: profile for message_id, (_, profile) in latest.items()}


def profile_lookup_by_from_email(profile_names: Iterable[str]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for profile_name in profile_names:
        from_email = str(PROFILES[profile_name].get("from_email") or "").strip().lower()
        if from_email:
            lookup[from_email] = profile_name
    return lookup


def profile_lookup_by_shard(profile_names: Iterable[str]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for profile_name in profile_names:
        shard = Path(str(PROFILES[profile_name].get("csv") or "")).name.strip().lower()
        if shard:
            lookup[shard] = profile_name
    return lookup


def send_attempts_by_email(attempts: Sequence[SendAttempt]) -> Dict[str, List[SendAttempt]]:
    grouped: Dict[str, List[SendAttempt]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt.email, []).append(attempt)
    for email in grouped:
        grouped[email].sort(key=lambda attempt: attempt.timestamp)
    return grouped


def match_profile_by_email_and_time(
    email: str,
    processed_at: Optional[datetime],
    attempts_for_email: Dict[str, List[SendAttempt]],
    tolerance_seconds: int = 180,
) -> str:
    if not email or not processed_at:
        return ""
    candidates = [
        attempt
        for attempt in attempts_for_email.get(email, [])
        if abs((attempt.timestamp - processed_at).total_seconds()) <= tolerance_seconds
    ]
    profiles = {attempt.profile for attempt in candidates}
    if len(profiles) == 1:
        return next(iter(profiles))
    return ""


def resolve_event_profile(
    event: Dict[str, str],
    email_to_profile: Dict[str, str],
    message_id_to_profile: Dict[str, str],
    from_email_to_profile: Dict[str, str],
    shard_to_profile: Dict[str, str],
    attempts_for_email: Dict[str, List[SendAttempt]],
) -> Tuple[str, str]:
    email = (event.get("email") or "").strip().lower()
    from_email = (event.get("from_email") or "").strip().lower()
    shard = (event.get("shard") or "").strip().lower()
    message_id = canonical_message_id(event.get("message_id", ""))
    explicit_profile = (event.get("profile") or "").strip()
    processed_at = parse_iso_utc(event.get("processed_at_utc", ""))
    if explicit_profile:
        return explicit_profile, "profile"
    if from_email and from_email in from_email_to_profile:
        return from_email_to_profile[from_email], "from_email"
    if shard and shard in shard_to_profile:
        return shard_to_profile[shard], "shard"
    if message_id and message_id in message_id_to_profile:
        return message_id_to_profile[message_id], "message_id"
    if email and email in email_to_profile:
        return email_to_profile[email], "email_unique"
    timestamp_profile = match_profile_by_email_and_time(email, processed_at, attempts_for_email)
    if timestamp_profile:
        return timestamp_profile, "email_time"
    return "", ""


def load_activity_events(
    path: Path,
    email_to_profile: Dict[str, str],
    message_id_to_profile: Dict[str, str],
    from_email_to_profile: Dict[str, str],
    shard_to_profile: Dict[str, str],
    attempts_for_email: Dict[str, List[SendAttempt]],
) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    if path.exists() and path.stat().st_size > 0:
        events.extend(parse_activity_file(path))
    webhook_path = WEBHOOK_EVENTS_PATH
    if webhook_path.exists() and webhook_path.stat().st_size > 0:
        events.extend(load_events_jsonl(webhook_path))
    for event in events:
        profile, source = resolve_event_profile(
            event,
            email_to_profile,
            message_id_to_profile,
            from_email_to_profile,
            shard_to_profile,
            attempts_for_email,
        )
        event["profile"] = profile
        event["attribution_source"] = source or "unmapped"
    events.sort(
        key=lambda e: parse_iso_utc(e.get("processed_at_utc", "")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return events


def is_sendgrid_test_event(event: Dict[str, str]) -> bool:
    email = (event.get("email") or "").strip().lower()
    if email == "example@test.com":
        return True
    message_id = (event.get("message_id") or "").strip().lower()
    response = (event.get("response") or "").strip().lower()
    return bool(message_id and "filter0001" in message_id and "ismtpd-555" in response)


def summarize_activity(events: List[Dict[str, str]], hours: int = 24) -> Dict[str, object]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = [
        e
        for e in events
        if (parse_iso_utc(e.get("processed_at_utc", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
        and not is_sendgrid_test_event(e)
    ]
    return {
        "recent": recent,
        "by_status": Counter(canonical_event_status(e.get("status", "")) for e in recent),
        "by_profile": Counter((e.get("profile") or "unmapped") for e in recent),
        "by_attribution_source": Counter((e.get("attribution_source") or "unmapped") for e in recent),
        "by_domain": Counter((e.get("domain") or "").strip() for e in recent if e.get("domain")),
        "unmapped_count": sum(1 for e in recent if not (e.get("profile") or "").strip()),
    }


def build_webhook_health(
    events: Sequence[Dict[str, str]],
    selected_hours: int,
    dedupe_stats: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    filtered = [event for event in events if not is_sendgrid_test_event(event)]
    now = datetime.now(timezone.utc)
    dedupe_stats = dedupe_stats or {}

    def received_time(event: Dict[str, str]) -> Optional[datetime]:
        return (
            parse_iso_utc(event.get("received_at_utc", ""))
            or parse_iso_utc(event.get("processed_at_utc", ""))
        )

    last_received = max(
        (received_time(event) for event in filtered),
        default=None,
    )
    dedupe_last_received = parse_iso_utc(str(dedupe_stats.get("last_received_iso") or ""))
    if dedupe_last_received and (not last_received or dedupe_last_received > last_received):
        last_received = dedupe_last_received
    events_5m = 0
    events_1h = 0
    unmapped_selected = 0
    bounces_with_bounce_classification = 0
    bounces_missing_bounce_classification = 0
    selected_cutoff = now - timedelta(hours=selected_hours)
    for event in filtered:
        received_at = received_time(event)
        if not received_at:
            continue
        if received_at >= now - timedelta(minutes=5):
            events_5m += 1
        if received_at >= now - timedelta(hours=1):
            events_1h += 1
        selected_time = received_at or parse_iso_utc(event.get("processed_at_utc", ""))
        if selected_time >= selected_cutoff and not (event.get("profile") or "").strip():
            unmapped_selected += 1
        if selected_time >= selected_cutoff and canonical_event_status(event.get("status", "")) == "bounce":
            if (event.get("bounce_classification") or "").strip():
                bounces_with_bounce_classification += 1
            else:
                bounces_missing_bounce_classification += 1
    return {
        "signature_verification": WEBHOOK_SIGNATURE_ENABLED,
        "last_received_iso": last_received.isoformat() if last_received else "",
        "last_received_at": format_when(last_received),
        "last_received_age": format_age(last_received),
        "events_5m": events_5m,
        "events_1h": events_1h,
        "unmapped_selected_window": unmapped_selected,
        "selected_window_hours": selected_hours,
        "bounces_with_bounce_classification": bounces_with_bounce_classification,
        "bounces_missing_bounce_classification": bounces_missing_bounce_classification,
        "duplicate_hits_5m": int(dedupe_stats.get("duplicate_hits_5m", 0) or 0),
        "duplicate_hits_1h": int(dedupe_stats.get("duplicate_hits_1h", 0) or 0),
        "duplicate_hits_selected_window": int(dedupe_stats.get("duplicate_hits_selected_window", 0) or 0),
        "duplicate_hits_total": int(dedupe_stats.get("duplicate_hits_total", 0) or 0),
    }


def _final_events_by_message_id(events: Sequence[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for event in events:
        status = canonical_event_status(event.get("status", ""))
        if status not in FINAL_OUTCOME_STATUS_KEYS:
            continue
        message_id = canonical_message_id(event.get("message_id", ""))
        if not message_id:
            continue
        grouped.setdefault(message_id, []).append(event)
    return grouped


def _final_events_by_profile_email(events: Sequence[Dict[str, str]]) -> Dict[Tuple[str, str], List[Tuple[datetime, str]]]:
    grouped: Dict[Tuple[str, str], List[Tuple[datetime, str]]] = {}
    for event in events:
        status = canonical_event_status(event.get("status", ""))
        if status not in FINAL_OUTCOME_STATUS_KEYS:
            continue
        profile = (event.get("profile") or "").strip()
        email = (event.get("email") or "").strip().lower()
        processed_at = parse_iso_utc(event.get("processed_at_utc", ""))
        if not profile or not email or not processed_at:
            continue
        grouped.setdefault((profile, email), []).append((processed_at, status))
    for key in grouped:
        grouped[key].sort(key=lambda item: item[0])
    return grouped


def attempt_final_outcome_statuses(
    attempt: SendAttempt,
    final_by_message_id: Dict[str, List[Dict[str, str]]],
    final_by_profile_email: Dict[Tuple[str, str], List[Tuple[datetime, str]]],
    tolerance_seconds: int = 300,
) -> Set[str]:
    statuses: Set[str] = set()
    if attempt.message_id and final_by_message_id.get(attempt.message_id):
        statuses.update(
            canonical_event_status(event.get("status", ""))
            for event in final_by_message_id.get(attempt.message_id, [])
        )
        return {status for status in statuses if status}

    threshold = attempt.timestamp - timedelta(seconds=max(0, tolerance_seconds))
    for event_time, status in final_by_profile_email.get((attempt.profile, attempt.email), []):
        if event_time >= threshold and status:
            statuses.add(status)
    return statuses


def attempt_has_final_outcome(
    attempt: SendAttempt,
    final_by_message_id: Dict[str, List[Dict[str, str]]],
    final_by_profile_email: Dict[Tuple[str, str], List[Tuple[datetime, str]]],
    tolerance_seconds: int = 300,
) -> bool:
    return bool(
        attempt_final_outcome_statuses(
            attempt,
            final_by_message_id,
            final_by_profile_email,
            tolerance_seconds=tolerance_seconds,
        )
    )


def build_awaiting_outcome_metrics(
    attempts: Sequence[SendAttempt],
    recent_events: Sequence[Dict[str, str]],
    profile_names: Sequence[str],
    hours: int,
) -> Dict[str, Dict[str, int]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    final_by_message_id = _final_events_by_message_id(recent_events)
    final_by_profile_email = _final_events_by_profile_email(recent_events)
    metrics: Dict[str, Dict[str, int]] = {
        name: {"accepted_recent": 0, "awaiting_outcome": 0, "final_outcome": 0}
        for name in profile_names
    }
    always_send_lookup = {
        name: str(PROFILES[name].get("always_send") or "").strip().lower()
        for name in profile_names
    }
    for attempt in attempts:
        if attempt.profile not in metrics or attempt.timestamp < cutoff:
            continue
        if attempt.email and attempt.email == always_send_lookup.get(attempt.profile, ""):
            continue
        metrics[attempt.profile]["accepted_recent"] += 1
        if attempt_has_final_outcome(attempt, final_by_message_id, final_by_profile_email):
            metrics[attempt.profile]["final_outcome"] += 1
        else:
            metrics[attempt.profile]["awaiting_outcome"] += 1
    return metrics


def _bucket_floor(ts: datetime, unit: str) -> datetime:
    local = ts.astimezone(DASHBOARD_TIMEZONE)
    if unit == "hour":
        return local.replace(minute=0, second=0, microsecond=0)
    if unit == "day":
        return local.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported bucket unit: {unit}")


def _bucket_labels(bucket_starts: Sequence[datetime], unit: str) -> List[str]:
    if unit == "hour":
        return [bucket.strftime("%H:%M") for bucket in bucket_starts]
    if unit == "day":
        return [bucket.strftime("%b %d") for bucket in bucket_starts]
    raise ValueError(f"Unsupported bucket unit: {unit}")


def build_trend_window(
    attempts: Sequence[SendAttempt],
    events: Sequence[Dict[str, str]],
    *,
    bucket_unit: str,
    bucket_count: int,
    label: str,
) -> Dict[str, object]:
    now_local = dashboard_now()
    bucket_end = _bucket_floor(now_local, bucket_unit)
    delta = timedelta(hours=1) if bucket_unit == "hour" else timedelta(days=1)
    bucket_starts = [bucket_end - delta * offset for offset in range(bucket_count - 1, -1, -1)]
    bucket_lookup = {bucket.isoformat(): index for index, bucket in enumerate(bucket_starts)}
    metrics = {
        key: {"points": [0] * bucket_count, "total": 0}
        for key in TREND_METRIC_KEYS
    }
    window_start = bucket_starts[0]
    always_send_lookup = {
        name: str(PROFILES[name].get("always_send") or "").strip().lower()
        for name in SENDGRID_PROFILES
    }

    for attempt in attempts:
        if attempt.profile not in always_send_lookup:
            continue
        if attempt.email and attempt.email == always_send_lookup.get(attempt.profile, ""):
            continue
        bucket = _bucket_floor(attempt.timestamp, bucket_unit)
        if bucket < window_start:
            continue
        index = bucket_lookup.get(bucket.isoformat())
        if index is None:
            continue
        metrics["accepted"]["points"][index] += 1

    for event in events:
        if is_sendgrid_test_event(event):
            continue
        processed_at = parse_iso_utc(event.get("processed_at_utc", ""))
        if not processed_at:
            continue
        bucket = _bucket_floor(processed_at, bucket_unit)
        if bucket < window_start:
            continue
        index = bucket_lookup.get(bucket.isoformat())
        if index is None:
            continue
        status = canonical_event_status(event.get("status", ""))
        if status == "delivered":
            metrics["delivered"]["points"][index] += 1
        elif status == "open":
            metrics["opened"]["points"][index] += 1
        elif status in FAILURE_STATUS_KEYS:
            metrics["failures"]["points"][index] += 1

    for metric in metrics.values():
        metric["total"] = sum(metric["points"])

    return {
        "label": label,
        "bucket_unit": bucket_unit,
        "bucket_labels": _bucket_labels(bucket_starts, bucket_unit),
        "metrics": metrics,
    }


def build_trend_panels(
    attempts: Sequence[SendAttempt],
    events: Sequence[Dict[str, str]],
) -> Dict[str, Dict[str, object]]:
    return {
        "24h": build_trend_window(attempts, events, bucket_unit="hour", bucket_count=24, label="24h"),
        "7d": build_trend_window(attempts, events, bucket_unit="day", bucket_count=7, label="7d"),
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
    if any(profile_is_active(s) for s in snapshots):
        return "running"
    return "stopped"


def recent_failure_count(activity: Dict[str, object]) -> int:
    by_status: Counter[str] = activity["by_status"]  # type: ignore[assignment]
    return sum(count for status, count in by_status.items() if canonical_event_status(status) in FAILURE_STATUS_KEYS)


def build_run_status_items(
    session_label: str,
    snapshots: List[ProfileSnapshot],
    recent_failures: int,
    historical_errors_today: int,
    auto_stop_events: Optional[Sequence[Dict[str, object]]] = None,
) -> List[str]:
    items: List[str] = []
    auto_stop_events = list(auto_stop_events or [])
    dead = [s.name.replace("sendgrid_", "") for s in snapshots if s.tmux_dead]
    errored = [s.name.replace("sendgrid_", "") for s in snapshots if s.runtime_state == "error"]
    scheduled = [s.name.replace("sendgrid_", "") for s in snapshots if s.runtime_state == "scheduled_stop"]
    finished = [s.name.replace("sendgrid_", "") for s in snapshots if s.runtime_state == "finished"]
    live_errors = [s.name.replace("sendgrid_", "") for s in snapshots if s.run_errors > 0]
    for event in auto_stop_events:
        if not event.get("ok"):
            continue
        profile = str(event.get("profile") or "").replace("sendgrid_", "")
        title = str(event.get("title") or "Delivery guard")
        items.append(f"Auto-stopped {profile}: {title}.")
    if session_label == "stopped":
        items.append("Session is not running.")
    if dead:
        items.append(f"Dead pane(s): {', '.join(dead)}.")
    if errored:
        items.append(f"Profiles in error: {', '.join(errored)}.")
    if scheduled:
        items.append(f"Stopped by schedule: {', '.join(scheduled)}.")
    if finished:
        items.append(f"Finished current run target: {', '.join(finished)}.")
    if live_errors:
        items.append(f"Current run errors on: {', '.join(live_errors)}.")
    if recent_failures > 0:
        items.append(f"Recent SendGrid failures in selected window: {recent_failures}.")
    if historical_errors_today > 0:
        items.append(f"Older same-day sender errors still exist in logs: {historical_errors_today}.")
    if not items:
        items.append("No operational issues detected.")
    return items


def build_telemetry_notes(unmapped_events: int) -> List[str]:
    items: List[str] = []
    if unmapped_events > 0:
        items.append(
            "Webhook events without a reliable profile match in selected window: "
            f"{unmapped_events}. Shared recipients and missing custom args can hide per-profile delivery data."
        )
    if not items:
        items.append("Webhook attribution looks clean in the selected window.")
    return items


def build_profile_health_status(
    profile: Dict[str, object],
    *,
    webhook_health: Dict[str, object],
    private_bounce_guard: Dict[str, object],
) -> Dict[str, str]:
    name = str(profile.get("name") or "")
    runtime_state = str(profile.get("runtime_state") or "")
    run_errors = int(profile.get("run_errors", 0) or 0)
    provider_cooldown = max(0, int(profile.get("provider_cooldown_remaining_seconds", 0) or 0))
    if provider_cooldown > 0 or bool(profile.get("restart_blocked")) or runtime_state == "paused":
        remaining_minutes = max(1, int((provider_cooldown + 59) / 60))
        return {
            "label": "Paused",
            "tone": "paused",
            "note": str(profile.get("restart_block_reason") or f"Provider cooldown active for about {remaining_minutes} minute(s)."),
        }

    if name == "private_jc" and bool(private_bounce_guard.get("cooldown_active")):
        remaining_seconds = max(0, int(private_bounce_guard.get("cooldown_remaining_seconds", 0) or 0))
        remaining_minutes = max(1, int((remaining_seconds + 59) / 60)) if remaining_seconds else 0
        return {
            "label": "Paused",
            "tone": "paused",
            "note": f"Bounce guard cooldown active for about {remaining_minutes} minute(s).",
        }

    if runtime_state in {"error", "dead"} or run_errors > 0:
        return {
            "label": "Risk",
            "tone": "bad",
            "note": "Sender has current-run errors and needs review.",
        }

    if name == "private_jc" and bool(private_bounce_guard.get("sync_error_active")):
        return {
            "label": "Watch",
            "tone": "warn",
            "note": str(private_bounce_guard.get("last_error") or "Private bounce sync error detected."),
        }

    if name == "private_jc" and bool(private_bounce_guard.get("sync_stale")) and bool(private_bounce_guard.get("profile_active")):
        return {
            "label": "Watch",
            "tone": "warn",
            "note": "Private bounce sync is stale while JC is active.",
        }

    if name in SENDGRID_PROFILES and str(webhook_health.get("last_received_age") or "").strip() == "never":
        return {
            "label": "Watch",
            "tone": "warn",
            "note": "No recent webhook intake; delivery outcomes may lag or be stale.",
        }

    if name in SENDGRID_PROFILES:
        last_received = parse_iso_utc(webhook_health.get("last_received_iso"))
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=ALERT_WEBHOOK_STALE_MINUTES)
        if ALERT_WEBHOOK_STALE_MINUTES > 0 and last_received and last_received < stale_cutoff:
            return {
                "label": "Watch",
                "tone": "warn",
                "note": "Webhook intake is stale for the current active window.",
            }

    if name in SENDGRID_PROFILES and int(profile.get("awaiting_outcome", 0) or 0) >= ALERT_PROFILE_AWAITING_THRESHOLD > 0:
        return {
            "label": "Watch",
            "tone": "warn",
            "note": "Accepted recipients are backing up without final outcomes.",
        }

    return {
        "label": "Healthy",
        "tone": "good",
        "note": "No live sender risk detected right now.",
    }


def build_threshold_alerts(
    *,
    session_label: str,
    active_profiles: int,
    recent_failures: int,
    recent_unmapped: int,
    total_awaiting_outcome: int,
    webhook_health: Dict[str, object],
    profile_dicts: Sequence[Dict[str, object]],
    auto_stop_events: Optional[Sequence[Dict[str, object]]] = None,
    private_bounce_guard: Optional[Dict[str, object]] = None,
) -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []
    for event in auto_stop_events or []:
        if not event.get("ok"):
            continue
        alerts.append(
            {
                "severity": str(event.get("severity") or "critical"),
                "title": str(event.get("title") or "Auto-stopped profile"),
                "message": str(event.get("message") or "A profile was auto-stopped by the delivery guard."),
            }
        )

    if recent_failures >= ALERT_RECENT_FAILURES_THRESHOLD > 0:
        alerts.append(
            {
                "severity": "critical",
                "title": "Recent delivery failures",
                "message": (
                    f"{recent_failures} SendGrid failure event(s) landed in the selected activity window "
                    f"(threshold {ALERT_RECENT_FAILURES_THRESHOLD})."
                ),
            }
        )

    if total_awaiting_outcome >= ALERT_TOTAL_AWAITING_THRESHOLD > 0:
        alerts.append(
            {
                "severity": "warn",
                "title": "Awaiting outcome backlog",
                "message": (
                    f"{total_awaiting_outcome} accepted recipients still do not have a final outcome "
                    f"(threshold {ALERT_TOTAL_AWAITING_THRESHOLD})."
                ),
            }
        )

    profile_backlog = [
        f"{str(profile.get('name', '')).replace('sendgrid_', '')}: {int(profile.get('awaiting_outcome', 0) or 0)}"
        for profile in profile_dicts
        if int(profile.get("awaiting_outcome", 0) or 0) >= ALERT_PROFILE_AWAITING_THRESHOLD > 0
    ]
    if profile_backlog:
        alerts.append(
            {
                "severity": "warn",
                "title": "Profile backlog concentration",
                "message": (
                    f"Profiles above awaiting threshold {ALERT_PROFILE_AWAITING_THRESHOLD}: "
                    f"{', '.join(profile_backlog)}."
                ),
            }
        )

    if recent_unmapped >= ALERT_UNMAPPED_THRESHOLD > 0:
        alerts.append(
            {
                "severity": "warn",
                "title": "Webhook attribution gap",
                "message": (
                    f"{recent_unmapped} webhook event(s) in the selected window are still unmapped "
                    f"(threshold {ALERT_UNMAPPED_THRESHOLD})."
                ),
            }
        )

    last_received_iso = str(webhook_health.get("last_received_iso") or "").strip()
    last_received = parse_iso_utc(last_received_iso)
    if (
        session_label == "running"
        and active_profiles > 0
        and ALERT_WEBHOOK_STALE_MINUTES > 0
    ):
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=ALERT_WEBHOOK_STALE_MINUTES)
        if not last_received or last_received < stale_cutoff:
            last_seen = str(webhook_health.get("last_received_age") or "never")
            alerts.append(
                {
                    "severity": "warn",
                    "title": "Webhook intake stale",
                    "message": (
                        f"No webhook received within the last {ALERT_WEBHOOK_STALE_MINUTES} minute(s) while "
                        f"{active_profiles} profile(s) are active. Last seen: {last_seen}."
                    ),
                }
            )

    active_error_profiles = [
        str(profile.get("name", "")).replace("sendgrid_", "")
        for profile in profile_dicts
        if int(profile.get("run_errors", 0) or 0) > 0
        and str(profile.get("runtime_state") or "").strip() in ACTIVE_RUNTIME_STATES
    ]
    if active_error_profiles:
        alerts.append(
            {
                "severity": "critical",
                "title": "Sender API errors",
                "message": f"Current run errors detected on: {', '.join(active_error_profiles)}.",
            }
        )

    guard = private_bounce_guard or {}
    if bool(guard.get("cooldown_active")):
        remaining_seconds = max(0, int(guard.get("cooldown_remaining_seconds", 0) or 0))
        remaining_minutes = max(1, int((remaining_seconds + 59) / 60)) if remaining_seconds else 0
        alerts.append(
            {
                "severity": "warn",
                "title": "JC private bounce cooldown",
                "message": (
                    f"JC is paused for clustered private bounces. Resume in about {remaining_minutes} minute(s). "
                    f"Recent bounces: {int(guard.get('recent_bounces_window', 0) or 0)}/"
                    f"{int(guard.get('bounce_threshold', 0) or 0)} in "
                    f"{int(guard.get('window_minutes', 0) or 0)}m."
                ),
            }
        )
    elif bool(guard.get("sync_error_active")):
        alerts.append(
            {
                "severity": "warn",
                "title": "JC private bounce sync error",
                "message": str(guard.get("last_error") or "Private bounce sync failed."),
            }
        )
    elif bool(guard.get("profile_active")) and bool(guard.get("sync_stale")):
        interval_seconds = max(0, int(guard.get("interval_seconds", 0) or 0))
        alerts.append(
            {
                "severity": "warn",
                "title": "JC private bounce sync stale",
                "message": (
                    f"JC is running but private bounce sync has not succeeded within the last "
                    f"{max(1, int((interval_seconds * 3 + 59) / 60))} minute(s)."
                ),
            }
        )

    return alerts


def health_banner_state(
    session_label: str,
    active_profiles: int,
    runtime_issues: int,
    recent_failures: int,
    alerts: Sequence[Dict[str, str]],
) -> tuple[str, str]:
    if session_label == "dead" or runtime_issues > 0:
        return "red", f"Attention needed: {runtime_issues} profile(s) in an error state; check profile detail and latest failures."
    critical_alerts = [alert for alert in alerts if str(alert.get("severity") or "") == "critical"]
    warn_alerts = [alert for alert in alerts if str(alert.get("severity") or "") == "warn"]
    if critical_alerts:
        return "red", f"Critical thresholds active: {len(critical_alerts)}. {critical_alerts[0].get('title', 'Check alerts panel')}."
    if recent_failures > 0:
        return "yellow", f"Caution: {recent_failures} recent SendGrid failure event(s) in the selected activity window."
    if warn_alerts:
        return "yellow", f"Threshold warnings active: {len(warn_alerts)}. {warn_alerts[0].get('title', 'Check alerts panel')}."
    if session_label == "running" and active_profiles > 0:
        return "green", f"Healthy run: {active_profiles} active profile(s), no live sender errors detected."
    return "yellow", "Idle: session is not running."


def latest_failures(activity: Dict[str, object], limit: int = 10) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for event in activity["recent"]:
        status_norm = canonical_event_status(event.get("status", ""))
        if status_norm not in FAILURE_STATUS_KEYS:
            continue
        rows.append(
            {
                "time": event.get("processed_at_utc", ""),
                "profile": event.get("profile", "") or "-",
                "status": status_norm,
                "email": event.get("email", ""),
                "reason": (event.get("response", "") or "")[:160],
            }
        )
        if len(rows) >= limit:
            break
    return rows


def build_profile_webhook_panels(
    activity: Dict[str, object],
    profile_names: Iterable[str],
    limit: int = 6,
) -> Dict[str, Dict[str, object]]:
    status_order = [
        "processed",
        "delivered",
        "open",
        "click",
        "deferred",
        "blocked",
        "bounce",
        "dropped",
        "spamreport",
        "unsubscribe",
        "group_unsubscribe",
    ]
    grouped: Dict[str, List[Dict[str, str]]] = {name: [] for name in profile_names}
    for event in activity["recent"]:
        profile = (event.get("profile") or "").strip()
        if profile in grouped:
            grouped[profile].append(event)

    out: Dict[str, Dict[str, object]] = {}
    for profile_name in profile_names:
        events = grouped.get(profile_name, [])
        counts = Counter(canonical_event_status(e.get("status", "")) for e in events)
        open_unique = len(
            {
                event_uniqueness_key(event, profile_hint=profile_name)
                for event in events
                if canonical_event_status(event.get("status", "")) == "open"
                and event_uniqueness_key(event, profile_hint=profile_name)
            }
        )
        click_unique = len(
            {
                event_uniqueness_key(event, profile_hint=profile_name)
                for event in events
                if canonical_event_status(event.get("status", "")) == "click"
                and event_uniqueness_key(event, profile_hint=profile_name)
            }
        )
        ordered_counts: Dict[str, int] = {}
        for status in status_order:
            count = counts.get(status, 0)
            if count:
                ordered_counts[status] = count
        recent_events = [
            {
                "time": event.get("processed_at_utc", ""),
                "status": canonical_event_status(event.get("status", "")),
                "email": event.get("email", ""),
                "reason": (event.get("response", "") or "")[:120],
            }
            for event in events[:limit]
        ]
        summary = {
            "processed": counts.get("processed", 0),
            "delivered": counts.get("delivered", 0),
            "open": counts.get("open", 0),
            "open_unique": open_unique,
            "click": counts.get("click", 0),
            "click_unique": click_unique,
            "deferred": counts.get("deferred", 0),
            "bounce": counts.get("bounce", 0),
            "blocked": counts.get("blocked", 0),
            "dropped": counts.get("dropped", 0),
            "spamreport": counts.get("spamreport", 0),
            "unsubscribe": counts.get("unsubscribe", 0) + counts.get("group_unsubscribe", 0),
        }
        summary["failed"] = (
            summary["bounce"]
            + summary["blocked"]
            + summary["dropped"]
            + summary["spamreport"]
        )
        out[profile_name] = {
            "counts": ordered_counts,
            "recent": recent_events,
            "total": len(events),
            "summary": summary,
            "latest_event": recent_events[0] if recent_events else {},
        }
    return out


def event_uniqueness_key(event: Dict[str, str], profile_hint: str = "") -> str:
    message_id = canonical_message_id(event.get("message_id", ""))
    if message_id:
        return f"message:{message_id}"
    email = (event.get("email") or "").strip().lower()
    profile = (event.get("profile") or "").strip() or profile_hint
    if email and profile:
        return f"profile_email:{profile}:{email}"
    if email:
        return f"email:{email}"
    return ""


def build_domain_breakdown(
    attempts: Sequence[SendAttempt],
    events: Sequence[Dict[str, str]],
    hours: int,
    limit: int = 12,
) -> List[Dict[str, object]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    always_send_lookup = {
        name: str(PROFILES[name].get("always_send") or "").strip().lower()
        for name in SENDGRID_PROFILES
    }
    rows: Dict[str, Dict[str, object]] = {}
    open_uniques: Dict[str, Set[str]] = {}
    click_uniques: Dict[str, Set[str]] = {}

    def get_row(domain: str) -> Dict[str, object]:
        row = rows.get(domain)
        if row is None:
            row = {
                "domain": domain,
                "accepted": 0,
                "processed": 0,
                "delivered": 0,
                "deferred": 0,
                "bounce": 0,
                "blocked": 0,
                "dropped": 0,
                "spamreport": 0,
                "failures": 0,
                "open_total": 0,
                "open_unique": 0,
                "click_total": 0,
                "click_unique": 0,
                "bounce_rate": None,
                "delivered_rate": None,
            }
            rows[domain] = row
        return row

    for attempt in attempts:
        if attempt.profile not in always_send_lookup or attempt.timestamp < cutoff:
            continue
        if attempt.email and attempt.email == always_send_lookup.get(attempt.profile, ""):
            continue
        domain = domain_from_email(attempt.email)
        if not domain:
            continue
        row = get_row(domain)
        row["accepted"] = int(row["accepted"]) + 1

    for event in events:
        if is_sendgrid_test_event(event):
            continue
        processed_at = parse_iso_utc(event.get("processed_at_utc", ""))
        if not processed_at or processed_at < cutoff:
            continue
        domain = (event.get("domain") or "").strip().lower() or domain_from_email(event.get("email", ""))
        if not domain:
            continue
        row = get_row(domain)
        status = canonical_event_status(event.get("status", ""))
        if status == "processed":
            row["processed"] = int(row["processed"]) + 1
        elif status == "delivered":
            row["delivered"] = int(row["delivered"]) + 1
        elif status == "deferred":
            row["deferred"] = int(row["deferred"]) + 1
        elif status == "bounce":
            row["bounce"] = int(row["bounce"]) + 1
        elif status == "blocked":
            row["blocked"] = int(row["blocked"]) + 1
        elif status == "dropped":
            row["dropped"] = int(row["dropped"]) + 1
        elif status == "spamreport":
            row["spamreport"] = int(row["spamreport"]) + 1
        elif status == "open":
            row["open_total"] = int(row["open_total"]) + 1
            unique_key = event_uniqueness_key(event)
            if unique_key:
                open_uniques.setdefault(domain, set()).add(unique_key)
        elif status == "click":
            row["click_total"] = int(row["click_total"]) + 1
            unique_key = event_uniqueness_key(event)
            if unique_key:
                click_uniques.setdefault(domain, set()).add(unique_key)

    for domain, row in rows.items():
        row["open_unique"] = len(open_uniques.get(domain, set()))
        row["click_unique"] = len(click_uniques.get(domain, set()))
        row["failures"] = int(row["bounce"]) + int(row["blocked"]) + int(row["dropped"]) + int(row["spamreport"])
        accepted = int(row["accepted"])
        if accepted > 0:
            row["bounce_rate"] = int(row["bounce"]) / accepted
            row["delivered_rate"] = int(row["delivered"]) / accepted

    ordered = sorted(
        rows.values(),
        key=lambda row: (
            -int(row.get("accepted", 0) or 0),
            -int(row.get("failures", 0) or 0),
            -int(row.get("delivered", 0) or 0),
            str(row.get("domain") or ""),
        ),
    )
    return ordered[:limit]


def empty_awaiting_buckets() -> Dict[str, int]:
    return {bucket: 0 for bucket in AWAITING_BUCKET_ORDER}


def awaiting_bucket_name(age: timedelta) -> str:
    seconds = max(0, int(age.total_seconds()))
    if seconds < 10 * 60:
        return "lt_10m"
    if seconds < 60 * 60:
        return "m10_to_60"
    if seconds < 24 * 60 * 60:
        return "h1_to_24"
    return "gt_24h"


def build_awaiting_age_buckets(
    attempts: Sequence[SendAttempt],
    events: Sequence[Dict[str, str]],
    profile_names: Sequence[str],
    lookback_hours: int = 168,
) -> Dict[str, Dict[str, int]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(24, lookback_hours))
    final_by_message_id = _final_events_by_message_id(events)
    final_by_profile_email = _final_events_by_profile_email(events)
    metrics: Dict[str, Dict[str, int]] = {
        name: empty_awaiting_buckets() for name in profile_names
    }
    metrics["__total__"] = empty_awaiting_buckets()
    always_send_lookup = {
        name: str(PROFILES[name].get("always_send") or "").strip().lower()
        for name in profile_names
    }

    now = datetime.now(timezone.utc)
    for attempt in attempts:
        if attempt.profile not in metrics or attempt.timestamp < cutoff:
            continue
        if attempt.email and attempt.email == always_send_lookup.get(attempt.profile, ""):
            continue
        if attempt_has_final_outcome(attempt, final_by_message_id, final_by_profile_email):
            continue
        bucket = awaiting_bucket_name(now - attempt.timestamp)
        metrics[attempt.profile][bucket] += 1
        metrics["__total__"][bucket] += 1
    return metrics


def current_run_anchor_by_profile(
    attempts: Sequence[SendAttempt],
    profile_names: Sequence[str],
) -> Dict[str, datetime]:
    anchors: Dict[str, datetime] = {}
    always_send_lookup = {
        name: str(PROFILES[name].get("always_send") or "").strip().lower()
        for name in profile_names
    }
    for attempt in attempts:
        always_send = always_send_lookup.get(attempt.profile, "")
        if not always_send or attempt.email != always_send:
            continue
        current = anchors.get(attempt.profile)
        if current is None or attempt.timestamp >= current:
            anchors[attempt.profile] = attempt.timestamp
    return anchors


def recent_auto_stop_events() -> List[Dict[str, object]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, PROFILE_GUARD_NOTICE_HOURS))
    rows: List[Dict[str, object]] = []
    with AUTO_STOP_EVENT_LOCK:
        stale_profiles = []
        for profile, payload in AUTO_STOP_EVENTS.items():
            stopped_at = parse_iso_utc(str(payload.get("stopped_at_iso") or ""))
            if stopped_at and stopped_at < cutoff:
                stale_profiles.append(profile)
                continue
            rows.append(dict(payload))
        for profile in stale_profiles:
            AUTO_STOP_EVENTS.pop(profile, None)
    rows.sort(key=lambda item: str(item.get("stopped_at_iso") or ""), reverse=True)
    return rows


def evaluate_profile_delivery_guards(
    snapshots: Sequence[ProfileSnapshot],
    attempts: Sequence[SendAttempt],
    events: Sequence[Dict[str, str]],
) -> List[Dict[str, object]]:
    if (
        not PROFILE_GUARD_ENABLED
        or PROFILE_GUARD_BOUNCE_THRESHOLD <= 0
        or PROFILE_GUARD_RECENT_ACCEPT_WINDOW <= 0
    ):
        return []

    anchors = current_run_anchor_by_profile(attempts, [snapshot.name for snapshot in snapshots])
    final_by_message_id = _final_events_by_message_id(events)
    final_by_profile_email = _final_events_by_profile_email(events)
    always_send_lookup = {
        snapshot.name: str(PROFILES[snapshot.name].get("always_send") or "").strip().lower()
        for snapshot in snapshots
    }
    attempts_by_profile: Dict[str, List[SendAttempt]] = {snapshot.name: [] for snapshot in snapshots}
    for attempt in attempts:
        anchor = anchors.get(attempt.profile)
        if anchor is None or attempt.timestamp < anchor:
            continue
        if attempt.email == always_send_lookup.get(attempt.profile, ""):
            continue
        attempts_by_profile.setdefault(attempt.profile, []).append(attempt)

    decisions: List[Dict[str, object]] = []
    for snapshot in snapshots:
        if not profile_is_active(snapshot):
            continue
        run_attempts = sorted(
            attempts_by_profile.get(snapshot.name, []),
            key=lambda attempt: attempt.timestamp,
            reverse=True,
        )
        if not run_attempts:
            continue
        window_attempts = run_attempts[:PROFILE_GUARD_RECENT_ACCEPT_WINDOW]
        bounced: List[SendAttempt] = []
        spamreports: List[SendAttempt] = []
        for attempt in window_attempts:
            statuses = attempt_final_outcome_statuses(
                attempt,
                final_by_message_id,
                final_by_profile_email,
            )
            if "spamreport" in statuses:
                spamreports.append(attempt)
            if "bounce" in statuses:
                bounced.append(attempt)

        if PROFILE_GUARD_SPAMREPORT_ENABLED and spamreports:
            attempt = spamreports[0]
            fingerprint = f"{snapshot.name}|spamreport|{anchors.get(snapshot.name, attempt.timestamp).isoformat()}|{attempt.message_id or attempt.email}"
            decisions.append(
                {
                    "profile": snapshot.name,
                    "pane_index": snapshot.pane_index,
                    "severity": "critical",
                    "title": "Spam report guard",
                    "message": (
                        f"Auto-stopping {snapshot.name.replace('sendgrid_', '')}: spam report received for "
                        f"{attempt.email} in the current run."
                    ),
                    "fingerprint": fingerprint,
                }
            )
            continue

        if len(bounced) >= PROFILE_GUARD_BOUNCE_THRESHOLD:
            recent_emails = ", ".join(attempt.email for attempt in bounced[:PROFILE_GUARD_BOUNCE_THRESHOLD])
            anchor = anchors.get(snapshot.name, window_attempts[-1].timestamp)
            fingerprint = (
                f"{snapshot.name}|bounce|{anchor.isoformat()}|"
                f"{len(bounced)}|{','.join((attempt.message_id or attempt.email) for attempt in bounced)}"
            )
            decisions.append(
                {
                    "profile": snapshot.name,
                    "pane_index": snapshot.pane_index,
                    "severity": "critical",
                    "title": "Hard bounce guard",
                    "message": (
                        f"Auto-stopping {snapshot.name.replace('sendgrid_', '')}: {len(bounced)} bounce event(s) "
                        f"matched the last {len(window_attempts)} accepted recipients. Recent bounced address(es): {recent_emails}."
                    ),
                    "fingerprint": fingerprint,
                }
            )
    return decisions


def apply_profile_delivery_guards(
    snapshots: Sequence[ProfileSnapshot],
    attempts: Sequence[SendAttempt],
    events: Sequence[Dict[str, str]],
    session: str = TMUX_SESSION_NAME,
) -> List[Dict[str, object]]:
    decisions = evaluate_profile_delivery_guards(snapshots, attempts, events)
    applied: List[Dict[str, object]] = []
    for decision in decisions:
        profile = str(decision.get("profile") or "")
        fingerprint = str(decision.get("fingerprint") or "")
        with AUTO_STOP_EVENT_LOCK:
            current = AUTO_STOP_EVENTS.get(profile)
            if current and str(current.get("fingerprint") or "") == fingerprint:
                applied.append(dict(current))
                continue
        pane_index = int(decision.get("pane_index") or 0)
        ok, stop_message = stop_sendgrid_profile(profile, pane_index, session=session)
        event_payload = {
            "profile": profile,
            "severity": str(decision.get("severity") or "critical"),
            "title": str(decision.get("title") or "Profile guard"),
            "message": str(decision.get("message") or stop_message),
            "stop_result": stop_message,
            "ok": bool(ok),
            "fingerprint": fingerprint,
            "stopped_at_iso": datetime.now(timezone.utc).isoformat(),
        }
        with AUTO_STOP_EVENT_LOCK:
            AUTO_STOP_EVENTS[profile] = event_payload
        applied.append(event_payload)
    return applied


def evaluate_and_apply_profile_delivery_guards(session: str = TMUX_SESSION_NAME) -> List[Dict[str, object]]:
    snapshots = load_sendgrid_profile_snapshots(session=session, tail_lines=12)
    attempts = collect_send_attempts(SENDGRID_PROFILES)
    email_to_profile = unique_send_profile_by_email(attempts)
    message_id_to_profile = latest_send_profile_by_message_id(attempts)
    from_email_to_profile = profile_lookup_by_from_email(SENDGRID_PROFILES)
    shard_to_profile = profile_lookup_by_shard(SENDGRID_PROFILES)
    attempts_for_email = send_attempts_by_email(attempts)
    events = load_activity_events(
        ACTIVITY_LOG_PATH,
        email_to_profile,
        message_id_to_profile,
        from_email_to_profile,
        shard_to_profile,
        attempts_for_email,
    )
    return apply_profile_delivery_guards(snapshots, attempts, events, session=session)


def build_dashboard_snapshot(activity_hours: int = 24, tail_lines: int = 12) -> Dict[str, object]:
    activity_path = ACTIVITY_LOG_PATH
    suppression_path = SUPPRESSION_CSV
    normalize_report_path = NORMALIZE_REPORT_PATH

    snapshots = load_dashboard_profile_snapshots(tail_lines=tail_lines)
    controls = load_dashboard_run_settings()
    send_cap_per_profile = dashboard_send_cap_per_profile()
    attempts = collect_send_attempts(SENDGRID_PROFILES)
    email_to_profile = unique_send_profile_by_email(attempts)
    message_id_to_profile = latest_send_profile_by_message_id(attempts)
    from_email_to_profile = profile_lookup_by_from_email(SENDGRID_PROFILES)
    shard_to_profile = profile_lookup_by_shard(SENDGRID_PROFILES)
    attempts_for_email = send_attempts_by_email(attempts)
    events = load_activity_events(
        activity_path,
        email_to_profile,
        message_id_to_profile,
        from_email_to_profile,
        shard_to_profile,
        attempts_for_email,
    )
    activity = summarize_activity(events, hours=activity_hours)
    suppression = load_suppression_summary(suppression_path)
    normalize_report = load_json_report(normalize_report_path)
    webhook_panels = build_profile_webhook_panels(activity, SENDGRID_PROFILES)
    awaiting_metrics = build_awaiting_outcome_metrics(attempts, activity["recent"], SENDGRID_PROFILES, activity_hours)
    awaiting_age_buckets = build_awaiting_age_buckets(attempts, events, SENDGRID_PROFILES)
    domain_breakdown = build_domain_breakdown(attempts, events, activity_hours)
    trends = build_trend_panels(attempts, events)
    webhook_events = [event for event in events if (event.get("source_log") or "").strip() == WEBHOOK_EVENTS_JSONL]
    webhook_dedupe_stats = load_webhook_dedupe_stats(
        WEBHOOK_DEDUPE_PATH,
        activity_hours,
        reference_utc=datetime.now(timezone.utc),
    )
    webhook_health = build_webhook_health(webhook_events, activity_hours, dedupe_stats=webhook_dedupe_stats)

    session_label = session_status(snapshots)
    total_pending = sum(s.pending_count for s in snapshots)
    sendgrid_pending = sum(s.pending_count for s in snapshots if s.name in SENDGRID_PROFILES)
    astra_pending = max(0, total_pending - sendgrid_pending)
    total_run_sent = sum(s.run_sent for s in snapshots)
    total_run_errors = sum(s.run_errors for s in snapshots)
    total_run_skipped = sum(s.run_skipped for s in snapshots)
    total_awaiting_outcome = sum(int(awaiting_metrics.get(s.name, {}).get("awaiting_outcome", 0) or 0) for s in snapshots)
    historical_errors_today = sum(max(0, s.errors_today - s.run_errors) for s in snapshots)
    recent_failures = recent_failure_count(activity)
    recent_unmapped = int(activity.get("unmapped_count", 0) or 0)
    active_profiles = sum(1 for s in snapshots if profile_is_active(s))
    active_start_all_profiles = sum(1 for s in snapshots if s.name in START_ALL_PROFILES and profile_is_active(s))
    runtime_issues = sum(1 for s in snapshots if s.runtime_state in {"dead", "error"})
    auto_stop_events = recent_auto_stop_events()
    jc_snapshot = next((snapshot for snapshot in snapshots if snapshot.name == "private_jc"), None)
    private_bounce_guard = private_bounce_guard_status(
        profile_name="private_jc",
        profile_active=profile_is_active(jc_snapshot) if jc_snapshot else False,
        now=datetime.now(timezone.utc),
    )

    profile_dicts = [asdict(s) for s in snapshots]
    for profile in profile_dicts:
        profile["webhook"] = webhook_panels.get(profile["name"], {"counts": {}, "recent": [], "total": 0})
        profile["awaiting_outcome"] = int(awaiting_metrics.get(profile["name"], {}).get("awaiting_outcome", 0) or 0)
        profile["accepted_recent"] = int(awaiting_metrics.get(profile["name"], {}).get("accepted_recent", 0) or 0)
        profile["final_outcome"] = int(awaiting_metrics.get(profile["name"], {}).get("final_outcome", 0) or 0)
        profile["awaiting_age_buckets"] = dict(awaiting_age_buckets.get(profile["name"], empty_awaiting_buckets()))
        health = build_profile_health_status(
            profile,
            webhook_health=webhook_health,
            private_bounce_guard=private_bounce_guard,
        )
        profile["health_label"] = str(health.get("label") or "")
        profile["health_tone"] = str(health.get("tone") or "")
        profile["health_note"] = str(health.get("note") or "")

    run_status_items = build_run_status_items(
        session_label,
        snapshots,
        recent_failures,
        historical_errors_today,
        auto_stop_events=auto_stop_events,
    )
    telemetry_notes = build_telemetry_notes(recent_unmapped)
    alerts = build_threshold_alerts(
        session_label=session_label,
        active_profiles=active_profiles,
        recent_failures=recent_failures,
        recent_unmapped=recent_unmapped,
        total_awaiting_outcome=total_awaiting_outcome,
        webhook_health=webhook_health,
        profile_dicts=profile_dicts,
        auto_stop_events=auto_stop_events,
        private_bounce_guard=private_bounce_guard,
    )
    banner_state, banner_message = health_banner_state(
        session_label,
        active_profiles,
        runtime_issues,
        recent_failures,
        alerts,
    )

    return {
        "generated_at": dashboard_now().isoformat(),
        "display_timezone": getattr(DASHBOARD_TIMEZONE, "key", DASHBOARD_TIMEZONE_NAME),
        "session_label": session_label,
        "activity_hours": activity_hours,
        "controls": {
            "send_cap_per_profile": send_cap_per_profile,
            "active_sender_count": active_start_all_profiles,
            "available_sender_count": len(START_ALL_PROFILES),
            "fleet_total_for_active_senders": send_cap_per_profile * active_start_all_profiles,
            "estimated_total_if_start_all": send_cap_per_profile * len(START_ALL_PROFILES),
            "updated_at_utc": str(controls.get("updated_at_utc") or ""),
        },
        "health": {"state": banner_state, "message": banner_message},
        "private_bounce_guard": private_bounce_guard,
        "summary": {
            "active_profiles": active_profiles,
            "total_pending": total_pending,
            "astra_pending": astra_pending,
            "sendgrid_pending": sendgrid_pending,
            "total_run_sent": total_run_sent,
            "total_run_errors": total_run_errors,
            "total_run_skipped": total_run_skipped,
            "total_awaiting_outcome": total_awaiting_outcome,
            "historical_errors_today": historical_errors_today,
            "recent_failures": recent_failures,
            "recent_unmapped": recent_unmapped,
            "active_alerts": len(alerts),
        },
        "attention_items": run_status_items + telemetry_notes,
        "run_status_items": run_status_items,
        "telemetry_notes": telemetry_notes,
        "alerts": alerts,
        "webhook_health": webhook_health,
        "awaiting_age_buckets": {
            "labels": dict(AWAITING_BUCKET_LABELS),
            "total": dict(awaiting_age_buckets.get("__total__", empty_awaiting_buckets())),
        },
        "domain_breakdown": domain_breakdown,
        "trends": trends,
        "suppression": suppression,
        "normalize_report": normalize_report,
        "activity_summary": {
            "by_status": dict(activity["by_status"].most_common()),
            "by_profile": dict(activity["by_profile"].most_common()),
            "by_attribution_source": dict(activity["by_attribution_source"].most_common()),
            "by_domain": dict(activity["by_domain"].most_common(15)),
        },
        "latest_failures": latest_failures(activity),
        "auto_stop_events": auto_stop_events,
        "profiles": profile_dicts,
    }
