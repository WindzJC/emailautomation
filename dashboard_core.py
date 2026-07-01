from __future__ import annotations

import csv
import json
import math
import os
import re
import signal
import shlex
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo

import settings
from private_bounce_hygiene import private_bounce_guard_status
from provider_pacing import provider_pacing_status
from send_shard import DOMAIN_SLOT_TTL_SECONDS, PROFILES, PROVIDER_LIMIT_DEFAULTS, profile_runtime_lock_status
from sendgrid_hygiene import (
    WEBHOOK_DEDUPE_DB as SENDGRID_WEBHOOK_DEDUPE_DB,
    WEBHOOK_EVENTS_JSONL,
    domain_from_email,
    load_events_jsonl,
    load_suppression_records,
    load_webhook_dedupe_stats,
    parse_activity_file,
    parse_iso_utc,
)
from sendgrid_launch_auth import resolve_sendgrid_api_key
from tools.rebuild_recipient_queues import build_queue_safety_report, default_queue_paths, default_sendgrid_queue_paths, email_set, set_fingerprint

ROOT = settings.APP_ROOT
PYTHON_BIN = ROOT / ".venv" / "bin" / "python"
SHARDS_DIR = settings.SHARDS_DIR
LOGS_DIR = settings.LOGS_DIR
STATE_DIR = settings.STATE_DIR
AUTO_STOP_EVENTS_PATH = STATE_DIR / "auto_stop_events.jsonl"
ACTIVITY_LOG_PATH = settings.ACTIVITY_LOG_PATH
SUPPRESSION_CSV = settings.SENDGRID_SUPPRESSIONS_PATH
NORMALIZE_REPORT_PATH = settings.SENDGRID_NORMALIZE_REPORT_PATH
CAMPAIGN_RUN_HISTORY_PATH = settings.LOGS_DIR / "campaign_run_history.jsonl"
WEBHOOK_EVENTS_PATH = settings.WEBHOOK_EVENTS_PATH
WEBHOOK_DEDUPE_DB = SENDGRID_WEBHOOK_DEDUPE_DB
WEBHOOK_DEDUPE_PATH = settings.WEBHOOK_DEDUPE_PATH
SENDGRID_WEBHOOK_RECEIVER_URL = settings.SENDGRID_WEBHOOK_RECEIVER_URL
SENDGRID_WEBHOOK_RECEIVER_API_TOKEN = settings.SENDGRID_WEBHOOK_RECEIVER_API_TOKEN
SENDGRID_WEBHOOK_RECEIVER_TIMEOUT_SECONDS = settings.SENDGRID_WEBHOOK_RECEIVER_TIMEOUT_SECONDS
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
    for name in SENDGRID_PROFILES
    if not bool(PROFILES.get(name, {}).get("dashboard_manual_only"))
]
SENDGRID_TARGET_WINDOW_HOURS = 18
SENDGRID_SEND_TARGET_OPTIONS = (5000, 10000)
MESSAGE_PREVIEW_DIR = settings.APP_ROOT / "data" / "message_previews"
EMAIL_SYNTAX_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
START_ALL_PARTIAL_PREFIX = "PARTIALLY_STARTED"

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
_WEBHOOK_RECEIVER_CACHE_LOCK = threading.Lock()
_WEBHOOK_RECEIVER_CACHE: Dict[str, object] = {
    "cache_key": "",
    "fetched_at": datetime.min.replace(tzinfo=timezone.utc),
    "payload": None,
}


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
RUNTIME_STALLED_MIN_SECONDS = _env_int("DASHBOARD_RUNTIME_STALLED_SECONDS", 300)
PROFILE_GUARD_ENABLED = _env_bool("DASHBOARD_PROFILE_GUARD_ENABLED", True)
PROFILE_GUARD_BOUNCE_THRESHOLD = _env_int("DASHBOARD_PROFILE_GUARD_BOUNCES", 4)
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
    last_timestamp_utc: str
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
    interval_seconds: int = 0
    effective_spacing_seconds: int = 0
    effective_pace_per_hour: int = 0
    last_sent_timestamp_utc: str = ""
    sendgrid_hourly_cap_waiting: bool = False
    sendgrid_hourly_cap_remaining_seconds: int = 0


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
    if name and not bool(cfg.get("pre_rendered_message")):
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
    return SENDGRID_SEND_TARGET_OPTIONS[0]


def _normalize_sendgrid_target_total(value: object) -> int:
    try:
        numeric = int(value or 0)
    except Exception:
        numeric = 0
    if numeric in SENDGRID_SEND_TARGET_OPTIONS:
        return numeric
    return SENDGRID_SEND_TARGET_OPTIONS[0]


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
    settings["send_cap_per_profile"] = _normalize_sendgrid_target_total(
        raw.get("send_cap_per_profile") or defaults["send_cap_per_profile"]
    )
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
        "send_cap_per_profile": _normalize_sendgrid_target_total(
            patch.get("send_cap_per_profile", current["send_cap_per_profile"])
        ),
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
        "send_cap_per_profile": _normalize_sendgrid_target_total(send_cap_per_profile),
    })


def dashboard_send_target_total() -> int:
    settings = load_dashboard_run_settings()
    return _normalize_sendgrid_target_total(settings.get("send_cap_per_profile"))


def dashboard_send_cap_per_profile() -> int:
    return max(1, math.ceil(dashboard_send_target_total() / max(1, len(START_ALL_PROFILES))))


def dashboard_sendgrid_hourly_target_cap() -> int:
    return max(1, math.ceil(dashboard_send_target_total() / SENDGRID_TARGET_WINDOW_HOURS))


def sendgrid_hourly_cap_limit() -> int:
    for profile_name in SENDGRID_PROFILES:
        cfg = PROFILES.get(profile_name, {})
        try:
            value = int(cfg.get("max_messages_1h") or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    try:
        return max(1, int(PROVIDER_LIMIT_DEFAULTS.get("sendgrid", {}).get("max_messages_1h") or 1000))
    except Exception:
        return 1000


def build_sendgrid_hourly_cap_status(now: Optional[datetime] = None) -> Dict[str, object]:
    """Expose the dashboard-selected rolling 1h SendGrid pacing target."""
    limit = dashboard_sendgrid_hourly_target_cap()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)
    slot_cutoff = now - timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS)
    domain_log_name = ""
    for profile_name in SENDGRID_PROFILES:
        domain_log_name = str(PROFILES.get(profile_name, {}).get("domain_log") or "").strip()
        if domain_log_name:
            break
    domain_log_name = domain_log_name or "sendgrid_domain_log.csv"
    domain_log_path = _managed_path(LOGS_DIR, domain_log_name)

    expiry_times: List[datetime] = []
    if domain_log_path.exists():
        for row in read_csv_rows(domain_log_path):
            status = (row.get("Status") or "").strip().upper()
            if status not in {"ATTEMPT", "SENT", "SLOT"}:
                continue
            ts = parse_log_timestamp(row.get("TimestampUTC", ""))
            if not ts:
                continue
            if status in {"ATTEMPT", "SENT"} and ts >= cutoff:
                expiry_times.append(ts + timedelta(hours=1))
            elif status == "SLOT" and ts >= slot_cutoff:
                expiry_times.append(ts + timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS))

    expiry_times.sort()
    used = len(expiry_times)
    remaining = max(0, limit - used)
    waiting = used >= limit and limit > 0
    next_slot_at = expiry_times[0] if waiting and expiry_times else None
    next_slot_seconds = max(0, int((next_slot_at - now).total_seconds())) if next_slot_at else 0
    return {
        "cap": limit,
        "used": used,
        "remaining": remaining,
        "waiting": waiting,
        "next_slot_available_at_utc": next_slot_at.isoformat() if next_slot_at else "",
        "next_slot_seconds": next_slot_seconds,
        "domain_log": domain_log_path.name,
    }


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


def iso_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except Exception:
        return ""


def profile_expected_pitch_mode(profile_name: str) -> str:
    if profile_name == "private_jc_warm":
        return "astra_warm"
    return "astra_visual" if profile_name == "private_jc" else "consignment"


def profile_actual_pitch_mode(profile_name: str) -> str:
    pitch_key = str(PROFILES.get(profile_name, {}).get("pitch") or "").strip()
    if pitch_key == "pitch_jc":
        return "astra_visual"
    if pitch_key == "pitch_warm":
        return "astra_warm"
    if pitch_key in {"pitch1", "pitch2", "pitch3", "pitch4", "pitch5"}:
        return "consignment"
    return pitch_key or "unknown"


def message_preview_path_for_profile(profile_name: str) -> Path:
    safe_profile = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(profile_name or "sender").strip() or "sender")
    return MESSAGE_PREVIEW_DIR / f"{safe_profile}_message_preview.csv"


def message_preview_output_paths(input_path: Path) -> Tuple[Path, Path, Path]:
    stem = input_path.stem
    base = stem[: -len("_message_preview")] if stem.endswith("_message_preview") else stem
    return (
        input_path.parent / f"{base}_message_preview_validated.csv",
        input_path.parent / f"{base}_message_preview_failed.csv",
        input_path.parent / f"{base}_message_preview_summary.txt",
    )


def _csv_row_count_with_fieldnames(path: Path) -> Tuple[List[str], int, List[Dict[str, str]]]:
    if not path.exists():
        return [], 0, []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(field or "").lstrip("\ufeff").strip() for field in (reader.fieldnames or [])]
        rows = [{field: str(row.get(field, "") or "").strip() for field in fieldnames} for row in reader]
    return fieldnames, len(rows), rows


def _normalized_email_for_readiness(row: Dict[str, str]) -> str:
    lower = {str(key or "").strip().lower(): str(value or "").strip() for key, value in row.items()}
    _, addr = parseaddr(lower.get("email") or lower.get("authoremail") or "")
    return addr.strip().lower()


def _validation_failed_count(failed_path: Path, summary_path: Path) -> Optional[int]:
    if failed_path.exists():
        _, row_count, _rows = _csv_row_count_with_fieldnames(failed_path)
        return row_count
    if summary_path.exists():
        try:
            text = summary_path.read_text(encoding="utf-8")
        except Exception:
            return None
        match = re.search(r"(?im)^failed rows:\s*(\d+)\s*$", text)
        if match:
            return int(match.group(1))
    return None


def build_profile_message_readiness(profile_name: str) -> Dict[str, object]:
    cfg = PROFILES.get(profile_name, {})
    csv_path = _profile_csv_path(cfg)
    fieldnames, row_count, rows = _csv_row_count_with_fieldnames(csv_path)
    field_by_lower = {field.lower(): field for field in fieldnames}
    pre_rendered_message = bool(cfg.get("pre_rendered_message"))
    book_title_field = field_by_lower.get("booktitle", "")
    book_title_present = bool(book_title_field)
    rows_with_book_title = sum(1 for row in rows if book_title_field and str(row.get(book_title_field) or "").strip())
    fallback_rows = max(0, row_count - rows_with_book_title)

    seen: Set[str] = set()
    duplicate_count = 0
    invalid_count = 0
    for row in rows:
        email = _normalized_email_for_readiness(row)
        if not email or not EMAIL_SYNTAX_RE.match(email):
            invalid_count += 1
            continue
        if email in seen:
            duplicate_count += 1
        else:
            seen.add(email)

    preview_path = message_preview_path_for_profile(profile_name)
    validated_path, failed_path, summary_path = message_preview_output_paths(preview_path)
    _preview_fields, preview_row_count, _preview_rows = _csv_row_count_with_fieldnames(preview_path)
    preview_exists = preview_path.exists() or (pre_rendered_message and row_count > 0)
    validation_artifacts = [path for path in (validated_path, failed_path, summary_path) if path.exists()]
    validation_time_utc = max((iso_mtime(path) for path in validation_artifacts), default="")
    preview_time_utc = iso_mtime(preview_path) if preview_exists else ""
    queue_time_utc = iso_mtime(csv_path)
    preview_mtime = safe_path_mtime(preview_path)
    queue_mtime = safe_path_mtime(csv_path)
    validation_mtime = max((safe_path_mtime(path) for path in validation_artifacts), default=0.0)
    failed_count = _validation_failed_count(failed_path, summary_path)

    expected_mode = profile_expected_pitch_mode(profile_name)
    actual_mode = profile_actual_pitch_mode(profile_name)
    reasons: List[str] = []
    validation_status = "PASS" if pre_rendered_message and row_count > 0 else "NOT RUN"
    if preview_exists and failed_count is not None:
        validation_status = "FAIL" if failed_count > 0 else "PASS"

    status = "PASS"
    if pre_rendered_message:
        required = {"authoremail", "emailsubject", "emailbody", "contactpath"}
        missing = sorted(required - set(field_by_lower))
        if missing:
            status = "FAIL"
            reasons.append("Warm queue is missing previewed message columns: " + ", ".join(missing) + ".")
        for row in rows:
            subject_field = field_by_lower.get("emailsubject", "")
            body_field = field_by_lower.get("emailbody", "")
            if not str(row.get(subject_field) or "").strip() or not str(row.get(body_field) or "").strip():
                status = "FAIL"
                reasons.append("Warm queue contains a row without previewed subject/body.")
                break
    elif not book_title_present:
        status = "FAIL"
        reasons.append("BookTitle column is missing.")
    if invalid_count > 0:
        status = "FAIL"
        reasons.append("Recipient queue has invalid email rows.")
    if duplicate_count > 0:
        status = "FAIL"
        reasons.append("Recipient queue has duplicate email rows.")
    if expected_mode != actual_mode:
        status = "FAIL"
        reasons.append("Profile pitch mode does not match expected mode.")
    if validation_status == "FAIL":
        status = "FAIL"
        reasons.append("Preview validation failed.")
    if status == "PASS" and not preview_exists:
        status = "NOT RUN"
        reasons.append("Rendered message preview CSV is missing.")
    if status == "PASS" and validation_status == "NOT RUN":
        status = "NOT RUN"
        reasons.append("Preview validation has not run.")
    if status == "PASS" and preview_exists and queue_mtime and preview_mtime and preview_mtime < queue_mtime:
        status = "STALE"
        reasons.append("Preview CSV is older than the recipient queue.")
    if status == "PASS" and validation_mtime and preview_mtime and validation_mtime < preview_mtime:
        status = "STALE"
        reasons.append("Validation is older than the preview CSV.")

    return {
        "status": status,
        "recipient_file": csv_path.name,
        "recipient_row_count": row_count,
        "book_title_column_present": book_title_present,
        "pre_rendered_message": pre_rendered_message,
        "rows_with_book_title": rows_with_book_title,
        "fallback_row_count": fallback_rows,
        "invalid_email_count": invalid_count,
        "duplicate_email_count": duplicate_count,
        "preview_csv_exists": preview_exists,
        "preview_row_count": preview_row_count,
        "preview_validation_status": validation_status,
        "last_preview_generated_utc": preview_time_utc,
        "last_validation_time_utc": validation_time_utc,
        "queue_updated_utc": queue_time_utc,
        "pitch_mode_expected": expected_mode,
        "actual_profile_mode": actual_mode,
        "preview_csv_name": preview_path.name,
        "reasons": reasons,
    }


def safe_path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _profile_from_snapshot(snapshot: Optional[Dict[str, object]], profile_name: str) -> Dict[str, object]:
    profiles = snapshot.get("profiles") if isinstance(snapshot, dict) else []
    if not isinstance(profiles, list):
        return {}
    for profile in profiles:
        if isinstance(profile, dict) and str(profile.get("name") or "") == profile_name:
            return profile
    return {}


def campaign_history_record(
    event_type: str,
    *,
    profile: str = "",
    snapshot: Optional[Dict[str, object]] = None,
    queue_safety: Optional[Dict[str, object]] = None,
    blocked_reasons: Optional[Sequence[object]] = None,
    preview_file: str = "",
    preview_row_count: Optional[int] = None,
    validation_status: str = "",
) -> Dict[str, object]:
    profile_name = str(profile or "").strip()
    profile_snapshot = _profile_from_snapshot(snapshot, profile_name)
    readiness = dict(profile_snapshot.get("message_readiness") or {}) if profile_snapshot else {}
    if not readiness and profile_name and profile_name != "all":
        readiness = build_profile_message_readiness(profile_name)
    cfg = PROFILES.get(profile_name, {}) if profile_name and profile_name != "all" else {}
    recipient_file = str(cfg.get("csv") or readiness.get("recipient_file") or "")
    queue_report = queue_safety or ((snapshot or {}).get("queue_safety") if isinstance(snapshot, dict) else {}) or {}
    safe_value = queue_report.get("safe") if isinstance(queue_report, dict) else None
    queue_safety_status = "safe" if safe_value is True else "unsafe" if safe_value is False else "unknown"
    sent_count = profile_snapshot.get("run_sent_display", profile_snapshot.get("run_sent", ""))
    failed_count = profile_snapshot.get("run_errors", "")
    reasons = [str(reason) for reason in (blocked_reasons or []) if str(reason or "").strip()]
    if not reasons and isinstance(queue_report, dict) and safe_value is False:
        raw_reasons = queue_report.get("unsafe_reasons")
        if isinstance(raw_reasons, list):
            reasons = [str(reason) for reason in raw_reasons]
        elif queue_report.get("message"):
            reasons = [str(queue_report.get("message"))]
    return {
        "event_type": str(event_type or "").strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile_name,
        "pitch_mode": profile_expected_pitch_mode(profile_name) if profile_name and profile_name != "all" else "",
        "recipient_file": Path(recipient_file).name if recipient_file else "",
        "recipient_row_count": int(readiness.get("recipient_row_count") or 0),
        "BookTitle_column_present": bool(readiness.get("book_title_column_present")),
        "BookTitle_populated_count": int(readiness.get("rows_with_book_title") or 0),
        "fallback_blank_BookTitle_count": int(readiness.get("fallback_row_count") or 0),
        "preview_file": str(preview_file or readiness.get("preview_csv_name") or ""),
        "preview_row_count": int(preview_row_count if preview_row_count is not None else readiness.get("preview_row_count") or 0),
        "validation_status": str(validation_status or readiness.get("preview_validation_status") or ""),
        "message_readiness_status": str(readiness.get("status") or ""),
        "queue_safety_status": queue_safety_status,
        "blocked_reasons": reasons,
        "sent_count": int(sent_count or 0) if str(sent_count or "").isdigit() else sent_count,
        "failed_count": int(failed_count or 0) if str(failed_count or "").isdigit() else failed_count,
    }


def append_campaign_run_history(record: Dict[str, object], path: Path = CAMPAIGN_RUN_HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    try:
        settings.secure_private_file(path)
    except Exception:
        pass


def load_campaign_run_history(limit: int = 25, path: Path = CAMPAIGN_RUN_HISTORY_PATH) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    records: List[Dict[str, object]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            records.append(payload)
        if len(records) >= limit:
            break
    return records


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


def _runtime_stalled_threshold_seconds(effective_cooldown_seconds: int) -> int:
    return max(RUNTIME_STALLED_MIN_SECONDS, max(0, int(effective_cooldown_seconds or 0)) * 3)


def _runtime_looks_stalled(
    *,
    runtime_state: str,
    pane_dead: bool,
    current_cmd: str,
    last_timestamp: Optional[datetime],
    cooldown_remaining_seconds: int,
    provider_cooldown_remaining_seconds: int,
    effective_cooldown_seconds: int,
) -> bool:
    if runtime_state != "cooldown" or pane_dead:
        return False
    if (current_cmd or "").strip() in SHELL_COMMANDS:
        return False
    if cooldown_remaining_seconds > 0 or provider_cooldown_remaining_seconds > 0:
        return False
    if last_timestamp is None:
        return False
    elapsed_seconds = max(0, int((datetime.now(timezone.utc) - last_timestamp).total_seconds()))
    return elapsed_seconds >= _runtime_stalled_threshold_seconds(effective_cooldown_seconds)


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
    return [load_profile_snapshot(name, idx, pane_info, tail_lines=tail_lines, session=session) for idx, name in enumerate(SENDGRID_PROFILES)]


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
        snapshots.append(load_profile_snapshot(profile_name, profile_pane_index(profile_name), pane_info, tail_lines=tail_lines, session=session))
    return snapshots


def _detect_running_send_shard_profiles(*, include_preview: bool = False) -> set:
    """Return a set of profile names that have a running send_shard.py process.

    This is a best-effort fallback for cases where senders were started
    outside the tmux session the dashboard manages.
    """
    out = set()
    try:
        ps = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        return out
    for line in ps.splitlines():
        if "send_shard.py" not in line:
            continue
        if not include_preview and "--preview_messages" in line:
            continue
        m = re.search(r"--profile\s+(\S+)", line)
        if m:
            out.add(m.group(1))
    return out


def _running_sender_processes(
    profile_names: Optional[Iterable[str]] = None,
    *,
    include_preview: bool = True,
) -> List[Dict[str, object]]:
    allowed_profiles = set(profile_names or DASHBOARD_PROFILES)
    processes: List[Dict[str, object]] = []
    try:
        ps = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
    except Exception:
        return processes
    current_pid = os.getpid()
    for line in ps.splitlines():
        text = line.strip()
        if not text or "send_shard.py" not in text or "--profile" not in text:
            continue
        parts = text.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except Exception:
            continue
        if pid == current_pid:
            continue
        command = parts[1]
        if not include_preview and "--preview_messages" in command:
            continue
        match = re.search(r"--profile(?:=|\s+)([^\s]+)", command)
        profile = match.group(1) if match else ""
        if profile not in allowed_profiles or profile not in DASHBOARD_PROFILES:
            continue
        processes.append({"pid": pid, "profile": profile, "command": command})
    return processes


def detect_running_preview_profiles(profile_names: Optional[Iterable[str]] = None) -> set[str]:
    profiles: set[str] = set()
    for proc in _running_sender_processes(profile_names, include_preview=True):
        if "--preview_messages" in str(proc.get("command") or ""):
            profiles.add(str(proc.get("profile") or ""))
    return {profile for profile in profiles if profile}


def detect_running_sender_profiles(profile_names: Optional[Iterable[str]] = None) -> set[str]:
    profiles: set[str] = set()
    for proc in _running_sender_processes(profile_names, include_preview=False):
        profiles.add(str(proc.get("profile") or ""))
    return {profile for profile in profiles if profile}


def locked_sender_profiles(profile_names: Optional[Iterable[str]] = None) -> set[str]:
    allowed_profiles = set(profile_names or DASHBOARD_PROFILES)
    profiles: set[str] = set()
    for profile in allowed_profiles:
        if profile not in DASHBOARD_PROFILES:
            continue
        try:
            status = profile_runtime_lock_status(profile)
        except Exception:
            continue
        if bool(status.get("locked")):
            profiles.add(profile)
    return profiles


def active_or_locked_sender_profiles(profile_names: Optional[Iterable[str]] = None) -> set[str]:
    allowed_profiles = set(profile_names or DASHBOARD_PROFILES)
    return (detect_running_sender_profiles(allowed_profiles) | locked_sender_profiles(allowed_profiles)) & allowed_profiles


def _redact_launcher_output(text: str) -> str:
    redacted = re.sub(r"SG\.[A-Za-z0-9_.-]+", "[redacted-sendgrid-key]", str(text or ""))
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", redacted)


def _compact_launcher_output(text: str, limit: int = 600) -> str:
    cleaned = _redact_launcher_output(text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _wait_for_started_profiles(profiles: Sequence[str], wait_seconds: float = 5.0) -> set[str]:
    expected = {str(profile) for profile in profiles}
    deadline = time.monotonic() + max(0.0, wait_seconds)
    active: set[str] = set()
    while True:
        active = active_or_locked_sender_profiles(expected)
        if expected.issubset(active) or time.monotonic() >= deadline:
            return active
        time.sleep(0.25)


def stop_sender_processes(
    profile_names: Optional[Iterable[str]] = None,
    *,
    terminate_wait_seconds: float = 2.0,
) -> Dict[str, object]:
    """Stop only known dashboard send_shard.py profile processes."""
    found = _running_sender_processes(profile_names)
    if not found:
        return {"found": [], "stopped": [], "killed": [], "still_running": []}

    for proc in found:
        try:
            os.kill(int(proc["pid"]), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as exc:
            proc["term_error"] = str(exc)

    deadline = time.monotonic() + max(0.1, terminate_wait_seconds)
    remaining = list(found)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.1)
        remaining = [proc for proc in remaining if _process_exists(int(proc["pid"]))]

    killed: List[Dict[str, object]] = []
    for proc in remaining:
        try:
            os.kill(int(proc["pid"]), signal.SIGKILL)
            killed.append(proc)
        except ProcessLookupError:
            pass
        except Exception as exc:
            proc["kill_error"] = str(exc)

    time.sleep(0.2)
    still_running = [proc for proc in found if _process_exists(int(proc["pid"]))]
    stopped = [proc for proc in found if proc not in still_running]
    return {
        "found": found,
        "stopped": stopped,
        "killed": killed,
        "still_running": still_running,
    }


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def active_dashboard_profile_snapshots(tail_lines: int = 12) -> List[ProfileSnapshot]:
    return [snapshot for snapshot in load_dashboard_profile_snapshots(tail_lines=tail_lines) if profile_is_active(snapshot)]


def _apply_process_runtime_fallback(snapshot: ProfileSnapshot) -> None:
    snapshot.tmux_running = True
    snapshot.tmux_dead = False
    last_send_timestamp = parse_log_timestamp(snapshot.last_sent_timestamp_utc)
    if last_send_timestamp and snapshot.effective_spacing_seconds > 0:
        elapsed_seconds = max(0, int((datetime.now(timezone.utc) - last_send_timestamp).total_seconds()))
        remaining_seconds = max(0, int(snapshot.effective_spacing_seconds) - elapsed_seconds)
        if remaining_seconds > 0:
            snapshot.runtime_state = "cooldown"
            snapshot.runtime_label = "Cooldown"
            snapshot.cooldown_remaining_seconds = remaining_seconds
            snapshot.runtime_note = f"Cooling down between sends: {remaining_seconds}s remaining."
            return
    snapshot.runtime_state = "running"
    snapshot.runtime_label = "Running"
    snapshot.runtime_note = "Sender is actively processing recipients."


def run_sendgrid_launcher() -> tuple[bool, str]:
    env = os.environ.copy()
    profiles = [profile for profile in START_ALL_PROFILES if profile in SENDGRID_PROFILES]
    if not profiles:
        return False, "No SendGrid profiles are configured for Start All."
    active_profiles = active_or_locked_sender_profiles(profiles)
    if active_profiles:
        return False, f"Start All blocked; profiles already running or locked: {', '.join(sorted(active_profiles))}."
    key_resolution = resolve_sendgrid_api_key(env=env, env_files=SENDGRID_ENV_FILES)
    if not key_resolution.ok:
        return False, key_resolution.error
    env["SENDGRID_API_KEY"] = key_resolution.key
    python_bin = _python_runtime_bin()
    if not python_bin:
        return False, "Missing Python runtime for SendGrid preflight."
    preflight_outputs: Dict[str, str] = {}
    for profile in profiles:
        active_profiles = active_or_locked_sender_profiles([profile])
        if active_profiles:
            return False, f"Start All blocked; profile already running or locked: {profile}."
        preflight = subprocess.run(
            [str(python_bin), "send_shard.py", "--profile", profile, "--preflight"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = "\n".join(part for part in [preflight.stdout.strip(), preflight.stderr.strip()] if part).strip()
        preflight_outputs[profile] = _compact_launcher_output(output or "Preflight passed with no output.")
        if preflight.returncode != 0:
            return False, preflight_outputs[profile] or f"Preflight failed for {profile}."
    env["TMUX_SENDGRID_ATTACH"] = "0"
    env["SENDGRID_DASHBOARD_MAX_TOTAL"] = str(dashboard_send_cap_per_profile())
    env["SENDGRID_DASHBOARD_MAX_MESSAGES_1H"] = str(dashboard_sendgrid_hourly_target_cap())
    active_profiles = active_or_locked_sender_profiles(profiles)
    if active_profiles:
        return False, f"Start All blocked; profiles already running or locked: {', '.join(sorted(active_profiles))}."
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
    output = _compact_launcher_output(output or "(no output)", limit=1200)
    if proc.returncode != 0:
        if START_ALL_PARTIAL_PREFIX in output:
            return False, f"{START_ALL_PARTIAL_PREFIX}: {output}"
        return False, output

    active = _wait_for_started_profiles(profiles)
    missing = [profile for profile in profiles if profile not in active]
    if missing:
        missing_details = []
        for profile in missing:
            missing_details.append(f"{profile}: preflight={preflight_outputs.get(profile) or '(missing)'}")
        detail_text = "; ".join(missing_details)
        return (
            False,
            f"{START_ALL_PARTIAL_PREFIX}: missing profiles: {', '.join(missing)}. "
            f"Active profiles: {', '.join(sorted(active)) or 'none'}. "
            f"Launcher output: {output}. Last preflight output: {detail_text}",
        )
    return True, output


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
    direct = stop_sender_processes([profile_name])
    found = len(direct.get("found", []))
    stopped = len(direct.get("stopped", []))
    still_running = len(direct.get("still_running", []))
    if stopped and not still_running:
        return True, f"{output or f'Unable to stop {profile_name} via tmux.'} Direct process stop: found={found}, stopped={stopped}."
    if found:
        return False, f"{output or f'Unable to stop {profile_name} via tmux.'} Direct process stop: found={found}, stopped={stopped}, still_running={still_running}."
    return False, output or f"Unable to stop {profile_name}."


def start_private_profile(profile_name: str, session: str) -> tuple[bool, str]:
    if profile_name not in DASHBOARD_PROFILES:
        return False, f"Unknown profile: {profile_name}"
    if profile_name in active_or_locked_sender_profiles([profile_name]):
        return False, f"{profile_name} is already running or locked."
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
    if profile_name in active_or_locked_sender_profiles([profile_name]):
        return False, f"{profile_name} is already running or locked."

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
    if profile_name in active_or_locked_sender_profiles([profile_name]):
        return False, f"{profile_name} is already running or locked."
    if not PYTHON_BIN.exists():
        return False, f"Missing Python venv at {PYTHON_BIN}"

    key_resolution = resolve_sendgrid_api_key(env=os.environ, env_files=SENDGRID_ENV_FILES)
    if not key_resolution.ok:
        return False, key_resolution.error
    api_key = key_resolution.key

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
    hourly_cap_override = dashboard_sendgrid_hourly_target_cap()
    preflight = subprocess.run(
        [
            str(PYTHON_BIN),
            "send_shard.py",
            "--profile",
            profile_name,
            "--preflight",
            "--max_total",
            str(max_total_override),
            "--max_messages_1h",
            str(hourly_cap_override),
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
    if profile_name in active_or_locked_sender_profiles([profile_name]):
        return False, f"{profile_name} is already running or locked."

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
        f"--max_total {max_total_override} --max_messages_1h {hourly_cap_override}"
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


def load_profile_snapshot(
    profile_name: str,
    pane_index: int,
    pane_info: Dict[str, Dict[str, str]],
    tail_lines: int = 16,
    session: str = TMUX_SESSION_NAME,
) -> ProfileSnapshot:
    cfg = PROFILES[profile_name]
    csv_path = _profile_csv_path(cfg)
    log_path = _profile_log_path(cfg)
    configured_max_total = int(cfg.get("max_total") or 0)
    effective_max_total = dashboard_send_cap_per_profile() if profile_name in SENDGRID_PROFILES else configured_max_total
    interval_seconds = max(0, int(cfg.get("interval") or 0))
    cooldown_seconds = max(0, int(cfg.get("cooldown_seconds") or 0))
    effective_spacing_seconds = cooldown_seconds if bool(cfg.get("repeat")) and cooldown_seconds > 0 else interval_seconds
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
    last_sent_timestamp: Optional[datetime] = None
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
        if ts and status == "SENT" and (last_sent_timestamp is None or ts >= last_sent_timestamp):
            last_sent_timestamp = ts

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
    tmux_tail = tmux_capture_tail(pane_index, session=session, lines=tail_lines) if pane else ""
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
    if runtime_state == "cooldown":
        cooldown_remaining_seconds = latest_batch_sleep_seconds(tmux_tail)
        if cooldown_remaining_seconds <= 0 and effective_spacing_seconds > 0 and last_sent_timestamp is not None:
            elapsed = max(0, int((datetime.now(timezone.utc) - last_sent_timestamp).total_seconds()))
            cooldown_remaining_seconds = max(0, effective_spacing_seconds - elapsed)
        runtime_note = f"Cooling down between sends: {cooldown_remaining_seconds}s remaining."
    elif restart_blocked and runtime_state not in ACTIVE_RUNTIME_STATES:
        runtime_state = "paused"
        runtime_label = "Paused"
        runtime_note = restart_block_reason
    if _runtime_looks_stalled(
        runtime_state=runtime_state,
        pane_dead=pane_dead,
        current_cmd=current_cmd,
        last_timestamp=last_timestamp,
        cooldown_remaining_seconds=cooldown_remaining_seconds,
        provider_cooldown_remaining_seconds=provider_cooldown_remaining_seconds,
        effective_cooldown_seconds=effective_cooldown_seconds,
    ):
        runtime_state = "stalled"
        runtime_label = "Stalled"
        runtime_note = (
            f"No fresh sender activity for {format_age(last_timestamp)} after the last cooldown marker. "
            "Process is still alive, but this sender appears idle-stale."
        )
    running = runtime_state in ACTIVE_RUNTIME_STATES and not pane_dead
    effective_pace_per_hour = max(1, round(3600 / effective_spacing_seconds)) if effective_spacing_seconds > 0 else 0
    return ProfileSnapshot(
        name=profile_name,
        pane_index=pane_index,
        csv_path=csv_path.name,
        log_path=log_path.name,
        configured_max_total=configured_max_total,
        max_total=effective_max_total,
        interval_seconds=interval_seconds,
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
        last_timestamp_utc=last_timestamp.astimezone(timezone.utc).isoformat() if last_timestamp else "",
        last_sent_timestamp_utc=last_sent_timestamp.astimezone(timezone.utc).isoformat() if last_sent_timestamp else "",
        last_age=format_age(last_timestamp),
        tmux_running=running,
        tmux_dead=pane_dead,
        tmux_command=current_cmd,
        tmux_tail=tmux_tail,
        runtime_state=runtime_state,
        runtime_label=runtime_label,
        runtime_note=runtime_note,
        effective_cooldown_seconds=effective_cooldown_seconds,
        effective_spacing_seconds=effective_spacing_seconds,
        effective_pace_per_hour=effective_pace_per_hour,
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
    snapshots: Sequence[object],
    recent_failures: int,
    historical_errors_today: int,
    auto_stop_events: Optional[Sequence[Dict[str, object]]] = None,
) -> List[str]:
    def profile_value(profile: object, key: str, default: object = "") -> object:
        if isinstance(profile, dict):
            return profile.get(key, default)
        return getattr(profile, key, default)

    items: List[str] = []
    auto_stop_events = list(auto_stop_events or [])
    dead = [str(profile_value(s, "name", "")).replace("sendgrid_", "") for s in snapshots if bool(profile_value(s, "tmux_dead", False))]
    errored = [str(profile_value(s, "name", "")).replace("sendgrid_", "") for s in snapshots if str(profile_value(s, "runtime_state", "")) == "error"]
    scheduled = [str(profile_value(s, "name", "")).replace("sendgrid_", "") for s in snapshots if str(profile_value(s, "runtime_state", "")) == "scheduled_stop"]
    finished = [str(profile_value(s, "name", "")).replace("sendgrid_", "") for s in snapshots if str(profile_value(s, "runtime_state", "")) == "finished"]
    active_issues = [
        str(profile_value(s, "name", "")).replace("sendgrid_", "")
        for s in snapshots
        if str(profile_value(s, "run_issue_state", "")) == "active"
    ]
    recovered_issues = [
        str(profile_value(s, "name", "")).replace("sendgrid_", "")
        for s in snapshots
        if str(profile_value(s, "run_issue_state", "")) == "recovered"
    ]
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
    if active_issues:
        items.append(f"Active sender issues now: {', '.join(active_issues)}.")
    if recovered_issues:
        items.append(f"Recovered earlier in this run: {', '.join(recovered_issues)}.")
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


def _profile_evidence_text(profile: Dict[str, object]) -> str:
    parts = [
        profile.get("runtime_note"),
        profile.get("last_info"),
        profile.get("last_status"),
        profile.get("tmux_tail"),
        profile.get("restart_block_reason"),
    ]
    return "\n".join(str(part or "") for part in parts).lower()


def _looks_like_auth_401(evidence: str) -> bool:
    return "401" in evidence and "unauthorized" in evidence


def _looks_like_auth_403(evidence: str) -> bool:
    return "403" in evidence or "forbidden" in evidence


def _looks_like_account_block(evidence: str) -> bool:
    return any(token in evidence for token in ("account-level error", "credits/region", "account_error"))


def _looks_like_transient_smtp_auth(evidence: str) -> bool:
    return any(
        token in evidence
        for token in (
            "temporary authentication failure",
            "connection lost to authentication server",
            "454",
            "4.7.0",
        )
    )


def _looks_like_dns_error(evidence: str) -> bool:
    return any(
        token in evidence
        for token in (
            "nodename nor servname provided",
            "[errno 8]",
            "temporary failure in name resolution",
        )
    )


def _webhook_is_stale(webhook_health: Dict[str, object]) -> bool:
    if str(webhook_health.get("last_received_age") or "").strip() == "never":
        return True
    last_received = parse_iso_utc(webhook_health.get("last_received_iso"))
    if not last_received:
        return True
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=ALERT_WEBHOOK_STALE_MINUTES)
    return ALERT_WEBHOOK_STALE_MINUTES > 0 and last_received < stale_cutoff


def _profile_uses_sendgrid(profile: Dict[str, object]) -> bool:
    name = str(profile.get("name") or "").strip().lower()
    csv_path = str(profile.get("csv_path") or "").strip().lower()
    log_path = str(profile.get("log_path") or "").strip().lower()
    return name in SENDGRID_PROFILES or name.startswith("sendgrid_") or "sendgrid" in csv_path or "sendgrid" in log_path


def _profile_uses_private(profile: Dict[str, object]) -> bool:
    name = str(profile.get("name") or "").strip().lower()
    csv_path = str(profile.get("csv_path") or "").strip().lower()
    log_path = str(profile.get("log_path") or "").strip().lower()
    return name.startswith("private_") or "private" in csv_path or "private" in log_path


def _run_issue_state(profile: Dict[str, object]) -> str:
    run_errors = int(profile.get("run_errors", 0) or 0)
    if run_errors <= 0:
        return "none"
    runtime_state = str(profile.get("runtime_state") or "")
    last_status = str(profile.get("last_status") or "").strip().upper()
    if runtime_state in {"error", "dead"}:
        return "active"
    if runtime_state in ACTIVE_RUNTIME_STATES and last_status not in {"SENT", "SKIP"}:
        return "active"
    if last_status == "SENT" or runtime_state in {"finished", "stopped", "scheduled_stop"}:
        return "recovered"
    return "historical"


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
    evidence = _profile_evidence_text(profile)
    run_issue_state = _run_issue_state(profile)
    is_sendgrid = _profile_uses_sendgrid(profile)
    is_private = _profile_uses_private(profile)

    if is_sendgrid and (_looks_like_auth_401(evidence) or ("auth_error" in evidence and "sendgrid" in evidence)):
        return {
            "label": "Blocked",
            "tone": "bad",
            "note": "SendGrid auth failed with 401 Unauthorized.",
            "reason_code": "AUTH_401",
            "reason_note": "SendGrid auth failed with 401 Unauthorized.",
            "readiness_label": "Blocked",
            "readiness_tone": "bad",
            "readiness_note": "Cannot send until the SendGrid key/account context is fixed.",
            "telemetry_label": "Low",
            "telemetry_tone": "warn",
            "telemetry_note": "Runtime status is current, but delivery telemetry is not trustworthy until auth is fixed.",
            "run_issue_state": "active",
        }

    if is_sendgrid and (_looks_like_auth_403(evidence) or _looks_like_account_block(evidence)):
        return {
            "label": "Blocked",
            "tone": "bad",
            "note": "SendGrid account access is blocked or forbidden for this sender.",
            "reason_code": "ACCOUNT_BLOCKED",
            "reason_note": "SendGrid account access is blocked or forbidden for this sender.",
            "readiness_label": "Blocked",
            "readiness_tone": "bad",
            "readiness_note": "Cannot send until the provider account issue is resolved.",
            "telemetry_label": "Low",
            "telemetry_tone": "warn",
            "telemetry_note": "Runtime status is current, but account-level failures block useful delivery telemetry.",
            "run_issue_state": "active",
        }

    if provider_cooldown > 0 or bool(profile.get("restart_blocked")) or runtime_state == "paused":
        remaining_minutes = max(1, int((provider_cooldown + 59) / 60)) if provider_cooldown else 0
        paused_note = str(profile.get("restart_block_reason") or f"Provider cooldown active for about {remaining_minutes} minute(s).")
        reason_code = "THROTTLE_COOLDOWN" if "throttle" in evidence else "PROVIDER_COOLDOWN"
        return {
            "label": "Paused",
            "tone": "paused",
            "note": paused_note,
            "reason_code": reason_code,
            "reason_note": paused_note,
            "readiness_label": "Cooling Down",
            "readiness_tone": "warn",
            "readiness_note": paused_note,
            "telemetry_label": "Medium",
            "telemetry_tone": "neutral",
            "telemetry_note": "Runtime state is current; sender is paused by a provider cooldown.",
            "run_issue_state": run_issue_state,
        }

    if name == "private_jc" and bool(private_bounce_guard.get("cooldown_active")):
        remaining_seconds = max(0, int(private_bounce_guard.get("cooldown_remaining_seconds", 0) or 0))
        remaining_minutes = max(1, int((remaining_seconds + 59) / 60)) if remaining_seconds else 0
        return {
            "label": "Paused",
            "tone": "paused",
            "note": f"Bounce guard cooldown active for about {remaining_minutes} minute(s).",
            "reason_code": "BOUNCE_GUARD",
            "reason_note": f"Bounce guard cooldown active for about {remaining_minutes} minute(s).",
            "readiness_label": "Paused",
            "readiness_tone": "warn",
            "readiness_note": "Resume after the private bounce guard cooldown ends.",
            "telemetry_label": "Medium",
            "telemetry_tone": "neutral",
            "telemetry_note": "Private sender telemetry is current, but JC is paused by bounce guard protection.",
            "run_issue_state": run_issue_state,
        }

    if runtime_state in {"error", "dead"}:
        if is_private and _looks_like_transient_smtp_auth(evidence):
            return {
                "label": "Watch",
                "tone": "warn",
                "note": "Temporary SMTP authentication trouble needs operator review.",
                "reason_code": "TRANSIENT_SMTP_AUTH",
                "reason_note": "Temporary SMTP authentication trouble needs operator review.",
                "readiness_label": "Not Ready",
                "readiness_tone": "warn",
                "readiness_note": "Wait for the temporary auth condition to clear before restarting.",
                "telemetry_label": "Medium",
                "telemetry_tone": "neutral",
                "telemetry_note": "Runtime state is current; delivery telemetry still depends on sender logs.",
                "run_issue_state": "active",
            }
        return {
            "label": "Watch",
            "tone": "warn",
            "note": str(profile.get("runtime_note") or "Sender is currently failing and needs review."),
            "reason_code": "ACTIVE_RUNTIME_ERROR",
            "reason_note": str(profile.get("runtime_note") or "Sender is currently failing and needs review."),
            "readiness_label": "Not Ready",
            "readiness_tone": "bad",
            "readiness_note": "Sender is not ready until the current runtime issue is cleared.",
            "telemetry_label": "Low",
            "telemetry_tone": "warn",
            "telemetry_note": "Status is inferred mostly from pane output while the sender is failing.",
            "run_issue_state": "active",
        }

    if name == "private_jc" and bool(private_bounce_guard.get("sync_error_active")):
        return {
            "label": "Watch",
            "tone": "bad",
            "note": str(private_bounce_guard.get("last_error") or "Private bounce sync error detected."),
            "reason_code": "BOUNCE_SYNC_ERROR",
            "reason_note": str(private_bounce_guard.get("last_error") or "Private bounce sync error detected."),
            "readiness_label": "Blocked",
            "readiness_tone": "bad",
            "readiness_note": "Private JC is blocked until private bounce sync succeeds.",
            "telemetry_label": "Low",
            "telemetry_tone": "warn",
            "telemetry_note": "Private bounce sync is currently failing.",
            "run_issue_state": run_issue_state,
        }

    if runtime_state == "stalled":
        stalled_note = str(profile.get("runtime_note") or "Sender process is alive, but no fresh send/log activity has arrived.")
        return {
            "label": "Watch",
            "tone": "warn",
            "note": stalled_note,
            "reason_code": "RUNTIME_STALLED",
            "reason_note": stalled_note,
            "readiness_label": "Needs Review",
            "readiness_tone": "warn",
            "readiness_note": "Process is still alive, but this sender has gone idle beyond its expected cooldown window.",
            "telemetry_label": "Medium",
            "telemetry_tone": "warn",
            "telemetry_note": "Pane output still shows a cooldown marker, but sender activity appears stale.",
            "run_issue_state": run_issue_state,
        }

    if name == "private_jc" and bool(private_bounce_guard.get("sync_stale")) and bool(private_bounce_guard.get("profile_active")):
        return {
            "label": "Watch",
            "tone": "warn",
            "note": "Private bounce sync is stale while JC is active.",
            "reason_code": "BOUNCE_SYNC_STALE",
            "reason_note": "Private bounce sync is stale while JC is active.",
            "readiness_label": "Telemetry Degraded",
            "readiness_tone": "warn",
            "readiness_note": "Sender can run, but private bounce telemetry is stale.",
            "telemetry_label": "Low",
            "telemetry_tone": "warn",
            "telemetry_note": "Private bounce sync is stale while JC is active.",
            "run_issue_state": run_issue_state,
        }

    if is_sendgrid and _webhook_is_stale(webhook_health):
        return {
            "label": "Watch",
            "tone": "warn",
            "note": "Webhook intake is stale for the current active window.",
            "reason_code": "WEBHOOK_STALE",
            "reason_note": "Webhook intake is stale for the current active window.",
            "readiness_label": "Telemetry Degraded",
            "readiness_tone": "warn",
            "readiness_note": "Sending can continue, but delivery outcomes are stale or missing.",
            "telemetry_label": str("Low" if str(webhook_health.get("last_received_age") or "").strip() == "never" else "Medium"),
            "telemetry_tone": "warn",
            "telemetry_note": (
                "No recent SendGrid webhook intake detected."
                if str(webhook_health.get("last_received_age") or "").strip() == "never"
                else "SendGrid webhook intake is stale for the current active window."
            ),
            "run_issue_state": run_issue_state,
        }

    if is_sendgrid and int(profile.get("awaiting_outcome", 0) or 0) >= ALERT_PROFILE_AWAITING_THRESHOLD > 0:
        return {
            "label": "Watch",
            "tone": "warn",
            "note": "Accepted recipients are backing up without final outcomes.",
            "reason_code": "BACKLOG_HIGH",
            "reason_note": "Accepted recipients are backing up without final outcomes.",
            "readiness_label": "Ready",
            "readiness_tone": "good",
            "readiness_note": "Sender can still send, but delivery follow-through needs attention.",
            "telemetry_label": "Medium",
            "telemetry_tone": "warn",
            "telemetry_note": "Runtime is current, but delivery outcomes are lagging behind accepted sends.",
            "run_issue_state": run_issue_state,
        }

    if run_errors > 0:
        if run_issue_state == "recovered":
            if is_private and _looks_like_dns_error(evidence):
                reason_code = "RECOVERED_DNS_ERROR"
                reason_note = "Recovered from a transient DNS/network resolution failure earlier in this run."
            elif is_private and _looks_like_transient_smtp_auth(evidence):
                reason_code = "TRANSIENT_SMTP_AUTH"
                reason_note = "Recovered from a temporary SMTP authentication issue earlier in this run."
            else:
                reason_code = "RECOVERED_RUN_ERROR"
                reason_note = "Recovered from an earlier sender error in this run."
            return {
                "label": "Recovered",
                "tone": "neutral",
                "note": reason_note,
                "reason_code": reason_code,
                "reason_note": reason_note,
                "readiness_label": "Ready",
                "readiness_tone": "good",
                "readiness_note": "Sender is currently able to send, but this run had a recovered issue.",
                "telemetry_label": "Medium" if is_private else "High",
                "telemetry_tone": "neutral",
                "telemetry_note": (
                    "Current sender state looks stable, but this run already recorded a recovered issue."
                ),
                "run_issue_state": run_issue_state,
            }
        if run_issue_state == "historical":
            return {
                "label": "Watch",
                "tone": "warn",
                "note": "This run recorded an earlier issue, but it is not the dominant live condition now.",
                "reason_code": "RUN_ERROR_HISTORY",
                "reason_note": "This run recorded an earlier issue, but it is not the dominant live condition now.",
                "readiness_label": "Ready",
                "readiness_tone": "good",
                "readiness_note": "Sender appears ready, with earlier current-run error history retained for review.",
                "telemetry_label": "Medium" if is_private else "High",
                "telemetry_tone": "neutral",
                "telemetry_note": "Runtime is current; review the run history if the sender degrades again.",
                "run_issue_state": run_issue_state,
            }

    if runtime_state == "stopped" and str(profile.get("runtime_note") or "").lower().startswith("stop:"):
        return {
            "label": "Healthy",
            "tone": "good",
            "note": str(profile.get("runtime_note") or "Stopped manually."),
            "reason_code": "MANUAL_STOP",
            "reason_note": "Sender is idle after a manual stop.",
            "readiness_label": "Ready",
            "readiness_tone": "good",
            "readiness_note": "Safe to start again when you want this sender live.",
            "telemetry_label": "Medium" if is_private else "High",
            "telemetry_tone": "neutral",
            "telemetry_note": "No meaningful current issue is active for this sender.",
            "run_issue_state": run_issue_state,
        }

    if runtime_state == "finished":
        return {
            "label": "Healthy",
            "tone": "good",
            "note": str(profile.get("runtime_note") or "Sender finished cleanly."),
            "reason_code": "FINISHED_CLEAN",
            "reason_note": "Sender finished the current run target cleanly.",
            "readiness_label": "Ready",
            "readiness_tone": "good",
            "readiness_note": "Safe to start again when more recipients are queued.",
            "telemetry_label": "Medium" if is_private else "High",
            "telemetry_tone": "neutral",
            "telemetry_note": "No meaningful current issue is active for this sender.",
            "run_issue_state": run_issue_state,
        }

    return {
        "label": "Healthy",
        "tone": "good",
        "note": "No live sender risk detected right now.",
        "reason_code": "READY",
        "reason_note": "No dominant sender issue is active right now.",
        "readiness_label": "Ready",
        "readiness_tone": "good",
        "readiness_note": "Sender is clear to run with current controls.",
        "telemetry_label": "Medium" if is_private else "High",
        "telemetry_tone": "neutral",
        "telemetry_note": (
            "Private sender state is inferred from sender logs and mailbox-side signals."
            if is_private
            else "Runtime state and delivery telemetry are aligned."
        ),
        "run_issue_state": run_issue_state,
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
        if str(profile.get("run_issue_state") or "").strip() == "active"
        or (
            not str(profile.get("run_issue_state") or "").strip()
            and int(profile.get("run_errors", 0) or 0) > 0
            and str(profile.get("runtime_state") or "").strip() in ACTIVE_RUNTIME_STATES
        )
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

    for alert in alerts:
        alert.setdefault("source_function", "dashboard_core.build_threshold_alerts")
        alert.setdefault("blocks_sending", False)
        alert.setdefault("blocking_label", "Non-blocking")
    return alerts


def _private_queue_paths() -> List[Path]:
    return [SHARDS_DIR / "recipients_private_jc.csv"]


def _queue_safety_provider_paths(provider: str) -> tuple[str, Optional[List[Path]]]:
    normalized = str(provider or "all").strip().lower()
    if normalized in {"sendgrid", "sg"}:
        return "sendgrid", default_sendgrid_queue_paths(SHARDS_DIR)
    if normalized in {"private", "private_jc", "jc"}:
        return "private_jc", _private_queue_paths()
    return "all", default_queue_paths(SHARDS_DIR)


def _dashboard_sendgrid_log_paths() -> List[Path]:
    paths: List[Path] = []
    seen: set[str] = set()
    for cfg in PROFILES.values():
        if str(cfg.get("provider") or "") != "sendgrid":
            continue
        for key in ("log", "domain_log"):
            value = str(cfg.get(key) or "").strip()
            if not value:
                continue
            path = settings.log_path(value)
            marker = str(path)
            if marker not in seen:
                seen.add(marker)
                paths.append(path)
    return paths


def _read_dashboard_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _active_campaign_preview_payload() -> Dict[str, object]:
    manifest = _read_dashboard_json(STATE_DIR / "active_campaign_snapshot.json")
    preview_id = str(manifest.get("preview_id") or "").strip()
    if not preview_id:
        return {}

    candidates = [
        ROOT / "_important" / "dispatch_jobs" / "previews" / f"{preview_id}.json",
        STATE_DIR / "dispatch_previews" / f"{preview_id}.json",
    ]
    short_id = "_".join(preview_id.split("_")[:3])
    if short_id and short_id != preview_id:
        candidates.append(STATE_DIR / "dispatch_previews" / f"{short_id}.json")

    for path in candidates:
        payload = _read_dashboard_json(path)
        if payload:
            return payload

    for directory in (ROOT / "_important" / "dispatch_jobs" / "previews", STATE_DIR / "dispatch_previews"):
        try:
            matches = sorted(directory.glob(f"{preview_id}*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        except Exception:
            matches = []
        for path in matches:
            payload = _read_dashboard_json(path)
            if payload:
                return payload
    return {}


def _planned_preview_email_set(preview: Dict[str, object], provider: str) -> set[str] | None:
    rows_by_queue = preview.get("plan_rows_by_queue")
    rows: List[Dict[str, object]] = []
    normalized = str(provider or "all").strip().lower()
    if isinstance(rows_by_queue, dict):
        for key, value in rows_by_queue.items():
            queue_name = str(key or "")
            if normalized == "sendgrid" and not queue_name.startswith("sendgrid_"):
                continue
            if normalized == "private_jc" and queue_name != "private_jc":
                continue
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
    if not rows:
        fallback_key = "sendgrid_planned_rows" if normalized == "sendgrid" else "private_jc_planned_rows" if normalized == "private_jc" else ""
        fallback = preview.get(fallback_key) if fallback_key else None
        if isinstance(fallback, list):
            rows.extend(row for row in fallback if isinstance(row, dict))
    if not rows and preview:
        return set()
    if not preview:
        return None
    return {
        str(row.get("Email") or row.get("AuthorEmail") or "").strip().lower()
        for row in rows
        if str(row.get("Email") or row.get("AuthorEmail") or "").strip()
    }


def _preview_campaign_id(preview: Dict[str, object]) -> str:
    return (
        str(preview.get("campaign_id") or "").strip()
        or str(preview.get("preview_id") or "").strip()
        or str(preview.get("campaign_type") or "").strip()
    )


def _log_info_marks_sent(info: object) -> bool:
    text = str(info or "").strip().lower()
    return "outcome=sent" in text or '"outcome":"sent"' in text or "'outcome': 'sent'" in text


def _authoritative_sent_log_row(row: Dict[str, str]) -> bool:
    status = str(row.get("Status") or "").strip().upper()
    return status == "SENT" or (status == "ATTEMPT" and _log_info_marks_sent(row.get("Info") or ""))


def _provider_profile_names(provider: str) -> list[str]:
    normalized = str(provider or "").strip().lower()
    if normalized == "private_jc":
        return [name for name in ("private_jc", "private_jc_warm") if name in PROFILES]
    if normalized == "sendgrid":
        return list(SENDGRID_PROFILES)
    return list(DASHBOARD_PROFILES)


def _provider_log_paths(provider: str) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for profile_name in _provider_profile_names(provider):
        cfg = PROFILES.get(profile_name, {})
        keys = ("log", "domain_log") if str(cfg.get("provider") or "").strip().lower() == "sendgrid" else ("log",)
        for key in keys:
            value = str(cfg.get(key) or "").strip()
            if not value:
                continue
            path = settings.log_path(value)
            marker = str(path)
            if marker not in seen:
                seen.add(marker)
                paths.append(path)
    if provider == "sendgrid":
        for path in _dashboard_sendgrid_log_paths():
            marker = str(path)
            if marker not in seen:
                seen.add(marker)
                paths.append(path)
    return paths


def _provider_log_accounted_missing_emails(provider: str) -> set[str]:
    accounted: set[str] = set()
    for path in _provider_log_paths(provider):
        for row in read_csv_rows(path):
            status = str(row.get("Status") or "").strip().upper()
            if status not in {"SENT", "SKIP"} and not (status == "ATTEMPT" and _log_info_marks_sent(row.get("Info") or "")):
                continue
            email = str(row.get("Email") or "").strip().lower()
            if email:
                accounted.add(email)
    return accounted


def _provider_authoritative_sent_emails(provider: str) -> set[str]:
    sent: set[str] = set()
    for path in _provider_log_paths(provider):
        for row in read_csv_rows(path):
            if not _authoritative_sent_log_row(row):
                continue
            email = str(row.get("Email") or "").strip().lower()
            if email:
                sent.add(email)
    return sent


def _provider_idempotency_accounted_emails(provider: str, campaign_id: str = "") -> set[str]:
    path = STATE_DIR / "send_idempotency.sqlite3"
    if not path.exists():
        return set()
    normalized_provider = str(provider or "").strip().lower()
    provider_values = ["private"] if normalized_provider == "private_jc" else ["sendgrid"] if normalized_provider == "sendgrid" else ["private", "sendgrid"]
    accounted: set[str] = set()
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ",".join("?" for _ in provider_values)
            rows = conn.execute(
                f"""
                SELECT campaign_id, provider, email, status, outcome
                FROM send_reservations
                WHERE provider IN ({placeholders})
                """,
                provider_values,
            ).fetchall()
    except Exception:
        return set()
    expected_campaign = str(campaign_id or "").strip()
    for row in rows:
        row_campaign = str(row["campaign_id"] or "").strip()
        if expected_campaign and row_campaign and row_campaign != expected_campaign:
            continue
        status = str(row["status"] or "").strip().lower()
        outcome = str(row["outcome"] or "").strip().lower()
        if not (status or outcome):
            continue
        # A reservation means the row left the live queue under the runtime
        # idempotency lock; later outcome updates refine the state.
        email = str(row["email"] or "").strip().lower()
        if email:
            accounted.add(email)
    return accounted


def _apply_preview_queue_match(report: Dict[str, object], provider: str, shard_paths: Optional[List[Path]]) -> None:
    preview = _active_campaign_preview_payload()
    expected = _planned_preview_email_set(preview, provider)
    if expected is None:
        return
    paths = list(shard_paths or default_sendgrid_queue_paths(SHARDS_DIR) + _private_queue_paths())
    live: set[str] = set()
    for path in paths:
        live.update(email_set(path))

    missing = expected - live
    extra = live - expected
    campaign_id = _preview_campaign_id(preview)
    accounted_missing = set()
    live_sent_overlap: set[str] = set()
    if provider in {"private_jc", "sendgrid", "all"}:
        accounted_missing = missing & (
            _provider_log_accounted_missing_emails(provider)
            | _provider_idempotency_accounted_emails(provider, campaign_id=campaign_id)
        )
        live_sent_overlap = live & _provider_authoritative_sent_emails(provider)
    unaccounted_missing = missing - accounted_missing
    report["preview_id"] = str(preview.get("preview_id") or "")
    report["preview_campaign_id"] = campaign_id
    report["expected_preview_unique_emails"] = len(expected)
    report["live_preview_unique_emails"] = len(live)
    report["missing_from_preview_expected_count"] = len(missing)
    report["accounted_missing_from_preview_expected_count"] = len(accounted_missing)
    report["unaccounted_missing_from_preview_expected_count"] = len(unaccounted_missing)
    report["extra_vs_preview_expected_count"] = len(extra)
    report["missing_from_preview_expected_fingerprint"] = set_fingerprint(missing) if missing else ""
    report["accounted_missing_from_preview_expected_fingerprint"] = set_fingerprint(accounted_missing) if accounted_missing else ""
    report["unaccounted_missing_from_preview_expected_fingerprint"] = set_fingerprint(unaccounted_missing) if unaccounted_missing else ""
    report["extra_vs_preview_expected_fingerprint"] = set_fingerprint(extra) if extra else ""
    report["live_already_sent_overlap_count"] = len(live_sent_overlap)
    report["live_already_sent_overlap_fingerprint"] = set_fingerprint(live_sent_overlap) if live_sent_overlap else ""
    if missing and not unaccounted_missing and not extra and not live_sent_overlap:
        report["partial_consumption_verified"] = True
        report["message"] = "Queue partially consumed — remaining recipients verified safe."
    if unaccounted_missing or extra or live_sent_overlap:
        reasons = list(report.get("unsafe_reasons") or [])
        if unaccounted_missing:
            reasons.append("MISSING_PREVIEW_PLANNED_ROWS")
        if extra:
            reasons.append("EXTRA_ROWS_NOT_IN_PREVIEW")
        if live_sent_overlap:
            reasons.append("LIVE_ALREADY_SENT_OVERLAP")
        report["unsafe_reasons"] = reasons
        report["safe"] = False


def build_dashboard_queue_safety_report(provider: str = "all") -> Dict[str, object]:
    provider_name, shard_paths = _queue_safety_provider_paths(provider)
    try:
        report = build_queue_safety_report(
            shard_paths=shard_paths,
            sendgrid_log_paths=_dashboard_sendgrid_log_paths(),
        )
    except Exception as exc:
        return {
            "safe": False,
            "unsafe_reasons": ["QUEUE_SAFETY_CHECK_FAILED"],
            "message": f"Queue safety check failed: {exc}",
            "provider": provider_name,
            "affected_provider": provider_name,
            "validated_shard_paths": [str(path) for path in shard_paths] if shard_paths is not None else [],
        }
    report["provider"] = provider_name
    report["affected_provider"] = provider_name
    report["validated_shard_paths"] = [str(item.get("path") or "") for item in report.get("shards", []) if isinstance(item, dict)]
    _apply_preview_queue_match(report, provider_name, shard_paths)
    return report


def queue_safety_alert(report: Dict[str, object]) -> Dict[str, str] | None:
    if bool(report.get("safe")):
        return None
    reject_overlap = int(report.get("blocked_triaged_reject_overlap_count") if "blocked_triaged_reject_overlap_count" in report else report.get("overlap_with_triaged_reject") or 0)
    outside_checked = int(report.get("outside_checked_output_count") or 0)
    outside_intended = int(report.get("outside_intended_source_count") or 0)
    source_reject_overlap = int(report.get("blocked_intended_source_reject_overlap_count") if "blocked_intended_source_reject_overlap_count" in report else report.get("intended_source_reject_overlap_count") or 0)
    sendgrid_sent_overlap = int(report.get("sendgrid_already_sent_overlap_count") or 0)
    if "unaccounted_missing_from_preview_expected_count" in report:
        preview_missing = int(report.get("unaccounted_missing_from_preview_expected_count") or 0)
    else:
        preview_missing = int(report.get("missing_from_preview_expected_count") or 0)
    preview_extra = int(report.get("extra_vs_preview_expected_count") or 0)
    live_sent_overlap = int(report.get("live_already_sent_overlap_count") or 0)
    sendgrid_sent_allowed = bool(report.get("sendgrid_already_sent_overlap_allowed"))
    missing_header_shards = report.get("missing_required_header_shards")
    missing_header_count = len(missing_header_shards) if isinstance(missing_header_shards, list) else 0
    missing_header_text = ""
    if isinstance(missing_header_shards, list) and missing_header_shards:
        parts = []
        for item in missing_header_shards:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            missing = item.get("missing_required_headers")
            missing_text = ", ".join(str(value) for value in missing) if isinstance(missing, list) else str(missing or "")
            if name:
                parts.append(f"{name} missing {missing_text}")
        if parts:
            missing_header_text = " Required header issue(s): " + "; ".join(parts) + "."
    explicit_message = str(report.get("message") or "").strip()
    unsafe_reasons = {str(reason) for reason in (report.get("unsafe_reasons") or []) if str(reason or "").strip()}
    count_violations = reject_overlap + outside_checked + outside_intended + source_reject_overlap + missing_header_count + preview_missing + preview_extra + live_sent_overlap
    if "SENDGRID_ALREADY_SENT_OVERLAP" in unsafe_reasons and not sendgrid_sent_allowed:
        count_violations += sendgrid_sent_overlap
    real_error_reasons = unsafe_reasons - {
        "TRIAGED_REJECT_OVERLAP",
        "OUTSIDE_CHECKED_OUTPUT",
        "OUTSIDE_INTENDED_SOURCE",
        "INTENDED_SOURCE_OVERLAPS_REJECT",
        "SENDGRID_ALREADY_SENT_OVERLAP",
        "MISSING_REQUIRED_HEADERS",
        "LIVE_ALREADY_SENT_OVERLAP",
    }
    if count_violations <= 0 and not explicit_message and not real_error_reasons:
        return None
    if explicit_message:
        message = explicit_message
    else:
        message = (
            "Live recipient queue is not safe to send. "
            f"{reject_overlap} email(s) overlap triaged_reject, "
            f"{outside_checked} are outside the latest checked output, and "
            f"{outside_intended} are outside the intended source. "
            f"{preview_missing} expected preview row(s) are missing without accounting, "
            f"{preview_extra} live row(s) are not in the selected preview, and "
            f"{live_sent_overlap} live row(s) already appear in authoritative sent logs."
            f"{missing_header_text} "
            "Freeze sending and rebuild queues from the current campaign source."
        )
    return {
        "severity": "critical",
        "title": "Recipient queue unsafe" if str(report.get("affected_provider") or "all") == "all" else f"{str(report.get('affected_provider')).replace('_', ' ').title()} queue unsafe",
        "message": message,
        "source_function": "dashboard_core.queue_safety_alert",
        "blocks_sending": True,
        "blocking_label": "Blocks sending",
        "affected_provider": str(report.get("affected_provider") or report.get("provider") or "all"),
    }


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


def fetch_sendgrid_receiver_summary(selected_hours: int) -> Optional[Dict[str, object]]:
    base_url = str(SENDGRID_WEBHOOK_RECEIVER_URL or "").strip()
    if not base_url:
        return None
    normalized_base = base_url.rstrip("/")
    cache_key = f"{normalized_base}|{int(selected_hours)}"
    with _WEBHOOK_RECEIVER_CACHE_LOCK:
        cached_key = str(_WEBHOOK_RECEIVER_CACHE.get("cache_key") or "")
        cached_at = _WEBHOOK_RECEIVER_CACHE.get("fetched_at")
        if (
            cached_key == cache_key
            and isinstance(cached_at, datetime)
            and datetime.now(timezone.utc) - cached_at < timedelta(seconds=15)
        ):
            cached_payload = _WEBHOOK_RECEIVER_CACHE.get("payload")
            if isinstance(cached_payload, dict):
                return cached_payload
    url = f"{normalized_base}/api/summary?{urllib.parse.urlencode({'hours': int(selected_hours)})}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if SENDGRID_WEBHOOK_RECEIVER_API_TOKEN:
        request.add_header("Authorization", f"Bearer {SENDGRID_WEBHOOK_RECEIVER_API_TOKEN}")
    try:
        with urllib.request.urlopen(request, timeout=max(1, int(SENDGRID_WEBHOOK_RECEIVER_TIMEOUT_SECONDS or 2))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    with _WEBHOOK_RECEIVER_CACHE_LOCK:
        _WEBHOOK_RECEIVER_CACHE["cache_key"] = cache_key
        _WEBHOOK_RECEIVER_CACHE["fetched_at"] = datetime.now(timezone.utc)
        _WEBHOOK_RECEIVER_CACHE["payload"] = payload
    return payload


def build_profile_webhook_panels_from_receiver(
    receiver_summary: Dict[str, object],
    profile_names: Iterable[str],
) -> Dict[str, Dict[str, object]]:
    profiles = receiver_summary.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    out: Dict[str, Dict[str, object]] = {}
    for profile_name in profile_names:
        raw = profiles.get(profile_name)
        if not isinstance(raw, dict):
            raw = {}
        summary = {
            "processed": int(raw.get("processed", 0) or 0),
            "delivered": int(raw.get("delivered", 0) or 0),
            "open": int(raw.get("open", 0) or 0),
            "open_unique": int(raw.get("open_unique", 0) or 0),
            "click": int(raw.get("click", 0) or 0),
            "click_unique": int(raw.get("click_unique", 0) or 0),
            "deferred": int(raw.get("deferred", 0) or 0),
            "bounce": int(raw.get("bounced", raw.get("bounce", 0)) or 0),
            "blocked": int(raw.get("blocked", 0) or 0),
            "dropped": int(raw.get("dropped", 0) or 0),
            "spamreport": int(raw.get("spamreport", 0) or 0),
            "unsubscribe": int(raw.get("unsubscribe", 0) or 0),
        }
        summary["failed"] = (
            summary["bounce"]
            + summary["blocked"]
            + summary["dropped"]
            + summary["spamreport"]
        )
        counts: Dict[str, int] = {}
        for key in ("processed", "delivered", "deferred", "bounce", "blocked", "dropped", "spamreport", "unsubscribe"):
            if summary.get(key):
                counts[key] = int(summary[key])
        out[profile_name] = {
            "counts": counts,
            "recent": list(raw.get("recent", [])) if isinstance(raw.get("recent"), list) else [],
            "total": int(raw.get("mapped_events_24h", 0) or 0),
            "summary": summary,
            "latest_event": raw.get("latest_event") if isinstance(raw.get("latest_event"), dict) else {},
            "last_received_iso": str(raw.get("last_webhook_received_at") or ""),
            "last_received_at": format_when(parse_iso_utc(raw.get("last_webhook_received_at"))),
            "mapped_events_24h": int(raw.get("mapped_events_24h", 0) or 0),
            "unmapped_events_24h": int(raw.get("unmapped_events_24h", 0) or 0),
        }
    return out


def build_webhook_health_from_receiver(
    receiver_summary: Dict[str, object],
    selected_hours: int,
) -> Dict[str, object]:
    last_received = parse_iso_utc(receiver_summary.get("last_received_iso"))
    return {
        "signature_verification": bool(receiver_summary.get("signature_verification", False)),
        "last_received_iso": last_received.isoformat() if last_received else "",
        "last_received_at": format_when(last_received),
        "last_received_age": format_age(last_received),
        "events_5m": int(receiver_summary.get("events_5m", 0) or 0),
        "events_1h": int(receiver_summary.get("events_1h", 0) or 0),
        "unmapped_selected_window": int(receiver_summary.get("unmapped_events_24h", 0) or 0),
        "selected_window_hours": int(receiver_summary.get("selected_window_hours", selected_hours) or selected_hours),
        "bounces_with_bounce_classification": 0,
        "bounces_missing_bounce_classification": 0,
        "duplicate_hits_5m": 0,
        "duplicate_hits_1h": 0,
        "duplicate_hits_selected_window": 0,
        "duplicate_hits_total": 0,
    }


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
                    # debug fields for instrumentation
                    "spamreport_count": len(spamreports),
                    "bounce_count": len(bounced),
                    "accepted_recent_count": len(window_attempts),
                    "recent_emails": ", ".join(a.email for a in window_attempts),
                    "awaiting_count": sum(
                        1
                        for a in attempts_by_profile.get(snapshot.name, [])
                        if not attempt_has_final_outcome(a, final_by_message_id, final_by_profile_email)
                    ),
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
                    # debug fields for instrumentation
                    "spamreport_count": len(spamreports),
                    "bounce_count": len(bounced),
                    "accepted_recent_count": len(window_attempts),
                    "recent_emails": recent_emails,
                    "awaiting_count": sum(
                        1
                        for a in attempts_by_profile.get(snapshot.name, [])
                        if not attempt_has_final_outcome(a, final_by_message_id, final_by_profile_email)
                    ),
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
        # include any debug fields from the decision for persistent instrumentation
        for key in ("bounce_count", "spamreport_count", "accepted_recent_count", "recent_emails", "awaiting_count"):
            if key in decision:
                event_payload[key] = decision.get(key)
        # persist a record of the applied auto-stop for post-mortem proof
        try:
            AUTO_STOP_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with AUTO_STOP_EVENTS_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event_payload, sort_keys=True, ensure_ascii=False) + "\n")
        except Exception:
            # best-effort instrumentation; don't interrupt normal flow if write fails
            pass
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
    # Fallback: if send_shard processes were started outside the dashboard's
    # tmux session, detect them via the process table and mark the matching
    # snapshots as running so the UI reflects actual live senders.
    try:
        running_profiles = _detect_running_send_shard_profiles() | locked_sender_profiles()
        if running_profiles:
            for s in snapshots:
                if s.name in running_profiles:
                    if not profile_is_active(s):
                        _apply_process_runtime_fallback(s)
    except Exception:
        # best-effort only; don't let detection failures break snapshot build
        pass
    controls = load_dashboard_run_settings()
    send_target_total = dashboard_send_target_total()
    send_cap_per_profile = dashboard_send_cap_per_profile()
    sendgrid_hourly_target_cap = dashboard_sendgrid_hourly_target_cap()
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
    receiver_summary = fetch_sendgrid_receiver_summary(activity_hours)
    if receiver_summary:
        receiver_panels = build_profile_webhook_panels_from_receiver(receiver_summary, SENDGRID_PROFILES)
        if receiver_panels:
            webhook_panels.update(receiver_panels)
        webhook_health = build_webhook_health_from_receiver(receiver_summary, activity_hours)

    sendgrid_hourly_cap = build_sendgrid_hourly_cap_status()
    if bool(sendgrid_hourly_cap.get("waiting")):
        remaining_seconds = max(0, int(sendgrid_hourly_cap.get("next_slot_seconds") or 0))
        for snapshot in snapshots:
            if snapshot.name in SENDGRID_PROFILES:
                snapshot.sendgrid_hourly_cap_waiting = profile_is_active(snapshot)
                snapshot.sendgrid_hourly_cap_remaining_seconds = remaining_seconds

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
    if receiver_summary:
        recent_unmapped = int(receiver_summary.get("unmapped_events_24h", recent_unmapped) or 0)
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
        profile["reason_code"] = str(health.get("reason_code") or "")
        profile["reason_note"] = str(health.get("reason_note") or profile["health_note"])
        profile["readiness_label"] = str(health.get("readiness_label") or "")
        profile["readiness_tone"] = str(health.get("readiness_tone") or "neutral")
        profile["readiness_note"] = str(health.get("readiness_note") or "")
        profile["telemetry_quality_label"] = str(health.get("telemetry_label") or "")
        profile["telemetry_quality_tone"] = str(health.get("telemetry_tone") or "neutral")
        profile["telemetry_quality_note"] = str(health.get("telemetry_note") or "")
        profile["run_issue_state"] = str(health.get("run_issue_state") or "")
        profile["message_readiness"] = build_profile_message_readiness(str(profile.get("name") or ""))

    # Expose a UI-only display fallback when webhook intake is stale.
    # Keep canonical `run_sent` unchanged; provide `run_sent_display` for the client.
    try:
        webhook_stale = _webhook_is_stale(webhook_health)
    except Exception:
        webhook_stale = False

    for profile in profile_dicts:
        try:
            accepted_recent = int(profile.get("accepted_recent", 0) or 0)
            run_sent = int(profile.get("run_sent", 0) or 0)
            # Default display value is the canonical run_sent.
            display_val = run_sent
            if str(profile.get("name") or "") == "private_jc_warm":
                display_val = max(display_val, int(profile.get("sent_today", 0) or 0))
            # When webhook intake is stale, prefer the attempts-derived accepted_recent
            # if it is larger than the anchored run_sent. This is strictly a display
            # fallback and does not mutate the canonical `run_sent` field.
            if webhook_stale and accepted_recent > display_val:
                display_val = accepted_recent
            profile["run_sent_display"] = display_val
        except Exception:
            # best-effort fallback to canonical run_sent
            try:
                profile["run_sent_display"] = int(profile.get("run_sent", 0) or 0)
            except Exception:
                profile["run_sent_display"] = 0

    queue_safety = build_dashboard_queue_safety_report("all")
    sendgrid_queue_safety = build_dashboard_queue_safety_report("sendgrid")
    private_queue_safety = build_dashboard_queue_safety_report("private_jc")
    run_status_items = build_run_status_items(
        session_label,
        profile_dicts,
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
    for provider_report in (private_queue_safety, sendgrid_queue_safety):
        if bool(provider_report.get("safe")) and bool(provider_report.get("partial_consumption_verified")):
            provider_label = str(provider_report.get("affected_provider") or provider_report.get("provider") or "queue").replace("_", " ").title()
            alerts.append(
                {
                    "severity": "info",
                    "title": f"{provider_label} queue verified",
                    "message": (
                        str(provider_report.get("message") or "Queue partially consumed — remaining recipients verified safe.")
                        + " "
                        + f"Original planned: {int(provider_report.get('expected_preview_unique_emails') or 0):,}. "
                        + f"Accounted sent/skipped: {int(provider_report.get('accounted_missing_from_preview_expected_count') or 0):,}. "
                        + f"Remaining: {int(provider_report.get('live_preview_unique_emails') or 0):,}. "
                        + f"Unsafe extras: {int(provider_report.get('extra_vs_preview_expected_count') or 0):,}. "
                        + f"Already-sent overlap in live queue: {int(provider_report.get('live_already_sent_overlap_count') or 0):,}."
                    ),
                    "source_function": "dashboard_core.build_dashboard_snapshot",
                    "blocks_sending": False,
                    "blocking_label": "Info",
                    "affected_provider": str(provider_report.get("affected_provider") or provider_report.get("provider") or ""),
                }
            )
    for provider_report in (private_queue_safety, sendgrid_queue_safety):
        queue_alert = queue_safety_alert(provider_report)
        if queue_alert:
            alerts.insert(0, queue_alert)
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
            "send_target_total": send_target_total,
            "send_target_per_profile": send_cap_per_profile,
            "send_target_window_hours": SENDGRID_TARGET_WINDOW_HOURS,
            "send_target_hourly_cap": sendgrid_hourly_target_cap,
            "send_target_options": list(SENDGRID_SEND_TARGET_OPTIONS),
            "active_sender_count": active_start_all_profiles,
            "available_sender_count": len(START_ALL_PROFILES),
            "fleet_total_for_active_senders": send_cap_per_profile * active_start_all_profiles,
            "estimated_total_if_start_all": send_target_total,
            "updated_at_utc": str(controls.get("updated_at_utc") or ""),
        },
        "health": {"state": banner_state, "message": banner_message},
        "private_bounce_guard": private_bounce_guard,
        "sendgrid_hourly_cap": sendgrid_hourly_cap,
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
        "queue_safety": queue_safety,
        "combined_queue_safety": queue_safety,
        "sendgrid_queue_safety": sendgrid_queue_safety,
        "private_queue_safety": private_queue_safety,
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
        "campaign_run_history": load_campaign_run_history(limit=25),
    }
