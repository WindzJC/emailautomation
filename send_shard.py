# =========================
# BEFORE PITCHES (TOP PART)
# =========================

import argparse
import base64
import csv
import fcntl
import hashlib
import html
import json
import os
import random
import re
import signal
import smtplib
import sqlite3
import ssl
import tempfile
import time
import traceback
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from getpass import getpass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote

import settings
import runtime_audit
from provider_pacing import (
    mark_recovery_started,
    provider_pacing_status,
    record_provider_temporary_failure,
    record_provider_throttle,
    temporary_failure_pause_seconds,
    throttle_pause_seconds,
)
from recipient_file_lock import lock_files
from sendgrid_hygiene import load_active_suppressed_emails

# ===== SMTP PRESETS =====
SMTP_PRESETS = {
    "private": ("mail.privateemail.com", 587),  # Namecheap PrivateEmail
    "gmail": ("smtp.gmail.com", 587),           # Google Workspace / Gmail SMTP
}

DEFAULT_DOMAIN = "barnesnoblemarketing.com"
DEFAULT_UNSUB_EMAIL = f"unsubscribe@{DEFAULT_DOMAIN}"
ROOT = settings.APP_ROOT
SHARDS_DIR = settings.SHARDS_DIR
LOGS_DIR = settings.LOGS_DIR
STATE_DIR = settings.STATE_DIR
TMP_DIR = settings.TMP_DIR
DEFAULT_UNSUB_CSV = settings.UNSUBSCRIBED_PATH     # optional, header: Email
DEFAULT_SUPPRESS_CSV = settings.SUPPRESSED_PATH    # optional, header: Email
DEFAULT_SENDGRID_SUPPRESSION_CSV = settings.state_path(
    os.environ.get("SENDGRID_SUPPRESSION_CSV", settings.SENDGRID_SUPPRESSIONS_PATH.name)
)
SENDGRID_DAILY_CAP = 0  # 0 = disabled (no global daily cap)
SENDGRID_COUNTERS_PATH = settings.SENDGRID_COUNTERS_PATH
SENDGRID_GLOBAL_COUNTER_KEY = "__global__"
DOMAIN_SLOT_TTL_SECONDS = max(30, int(os.environ.get("DOMAIN_SLOT_TTL_SECONDS", "300")))
ASTRA_PHYSICAL_MAILING_ADDRESS = os.environ.get("ASTRA_PHYSICAL_MAILING_ADDRESS", "").strip()
SENDGRID_SKIP_PRUNE_ON_STARTUP = os.environ.get("SENDGRID_SKIP_PRUNE_ON_STARTUP", "").strip() == "1"
RUNTIME_LOCKS_DIR = STATE_DIR / "locks"
SEND_IDEMPOTENCY_DB_PATH = STATE_DIR / "send_idempotency.sqlite3"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except Exception:
        return default


SENDGRID_MAX_MESSAGES_1H = max(1, _env_int("SENDGRID_MAX_MESSAGES_1H", 180))

PROVIDER_LIMIT_DEFAULTS = {
    "private": {"max_messages_1h": 80},
    "gmail": {"max_messages_24h": 100, "max_unique_external_24h": 100},
    # App-side SendGrid reputation/pacing guard. This rolling hourly cap is
    # separate from the dashboard per-run cap/max_total and from SendGrid's
    # account-level limits.
    "sendgrid": {"max_messages_1h": SENDGRID_MAX_MESSAGES_1H},
}

ROLE_LOCALPART_BLOCKLIST = {
    "abuse",
    "admin",
    "billing",
    "compliance",
    "contact",
    "devnull",
    "finance",
    "help",
    "hello",
    "hr",
    "info",
    "inquiries",
    "legal",
    "mailer-daemon",
    "marketing",
    "noreply",
    "no-reply",
    "office",
    "postmaster",
    "privacy",
    "sales",
    "security",
    "support",
    "team",
    "webmaster",
}


def _short_sha256(*parts: object, length: int = 24) -> str:
    payload = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[: max(8, int(length or 24))]


CAMPAIGN_TYPE_COLD = "cold"
CAMPAIGN_TYPE_RECONTACT_COLD = "recontact_cold"
CAMPAIGN_TYPE_WARM_PRIVATE_JC = "warm_private_jc"
BAD_SENDGRID_EVENT_STATUSES = {
    "blocked",
    "bounce",
    "bounced",
    "dropped",
    "drop",
    "group_unsubscribe",
    "invalid",
    "spam_report",
    "spamreport",
    "unsubscribe",
    "unsubscribed",
}


def normalize_campaign_type(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"recontact", "recontact_cold", "cold_recontact", "followup_cold"}:
        return CAMPAIGN_TYPE_RECONTACT_COLD
    if text in {"warm", "warm_private_jc", "private_jc_warm"}:
        return CAMPAIGN_TYPE_WARM_PRIVATE_JC
    return CAMPAIGN_TYPE_COLD


def is_recontact_cold_campaign(value: object) -> bool:
    return normalize_campaign_type(value) == CAMPAIGN_TYPE_RECONTACT_COLD


def build_sendgrid_astra_custom_args(
    *,
    profile_name: str,
    run_id: str,
    recipient_email: str,
    queue_name: str,
    message_ordinal: int,
    campaign_type: str = CAMPAIGN_TYPE_COLD,
) -> Dict[str, str]:
    recipient_id = _short_sha256("recipient", profile_name, recipient_email.lower())
    message_key = _short_sha256("message", profile_name, run_id, recipient_id, queue_name, message_ordinal)
    normalized_campaign_type = normalize_campaign_type(campaign_type)
    return {
        "profile": str(profile_name or "").strip(),
        "shard": str(queue_name or "").strip(),
        "provider": "sendgrid",
        "campaign_type": normalized_campaign_type,
        "astra_campaign_type": normalized_campaign_type,
        "astra_profile": str(profile_name or "").strip(),
        "astra_run_id": str(run_id or "").strip(),
        "astra_recipient_id": recipient_id,
        "astra_message_key": message_key,
    }

GENERIC_SALUTATION = "there"

NONPERSON_NAME_TOKENS = {
    "admin",
    "author",
    "books",
    "contact",
    "corporate",
    "hello",
    "info",
    "marketing",
    "media",
    "office",
    "press",
    "read",
    "sales",
    "service",
    "services",
    "shop",
    "staff",
    "store",
    "studio",
    "support",
    "team",
    "webmaster",
    "works",
}

BUSINESS_LOCALPART_HINTS = {
    "agency",
    "arts",
    "author",
    "books",
    "coaching",
    "consult",
    "design",
    "designs",
    "digital",
    "fitness",
    "herbs",
    "lounge",
    "media",
    "ministries",
    "nwcc",
    "press",
    "pressco",
    "publishing",
    "services",
    "solutions",
    "studio",
    "works",
}

PROFILES: Dict[str, Dict[str, object]] = {

    # Private mailboxes (staggered pacing, domain-wide hourly cap controlled by PROVIDER_LIMIT_DEFAULTS)
    "private_annette": {
        "provider": "private",
        "csv": "recipients_1.csv",
        "log": "private_annette_log.csv",
        "pitch": "pitch1",
        "from_email": "annettedanek-akey@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 90,
        "batch_size": 1,
        "cooldown_seconds": 0,
        "repeat": True,
        "human_mode": True,
        "max_total": 100,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "prune_sent": True,
        "password_env": "PRIVATE_ANNETTE_APP_PW",
    },
    "private_jordan": {
        "provider": "private",
        "csv": "recipients_2.csv",
        "log": "private_jordan_kendrick_log.csv",
        "pitch": "pitch2",
        "from_email": "jordankendrick@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 90,
        "batch_size": 1,
        "cooldown_seconds": 0,
        "repeat": True,
        "human_mode": True,
        "max_total": 100,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "prune_sent": True,
        "password_env": "PRIVATE_JORDAN_APP_PW",
    },
    "private_jodi": {
        "provider": "private",
        "csv": "recipients_3.csv",
        "log": "private_jodi_horowitz_log.csv",
        "pitch": "pitch3",
        "from_email": "jodihorowitz@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 90,
        "batch_size": 1,
        "cooldown_seconds": 0,
        "repeat": True,
        "human_mode": True,
        "max_total": 100,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "prune_sent": True,
        "password_env": "PRIVATE_JODI_APP_PW",
    },
    "private_alison": {
        "provider": "private",
        "csv": "recipients_4.csv",
        "log": "private_alison_log.csv",
        "pitch": "pitch4",
        "from_email": "alisonaguair@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 90,
        "batch_size": 1,
        "cooldown_seconds": 0,
        "repeat": True,
        "human_mode": True,
        "max_total": 100,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "prune_sent": True,
        "password_env": "PRIVATE_ALISON_APP_PW",
    },
    "private_fiorela": {
        "provider": "private",
        "csv": "recipients_5.csv",
        "log": "private_fiorela_log.csv",
        "pitch": "pitch5",
        "from_email": "fiorelladelima@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 90,
        "batch_size": 1,
        "cooldown_seconds": 0,
        "repeat": True,
        "human_mode": True,
        "max_total": 100,
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "prune_sent": True,
        "password_env": "PRIVATE_FIORELA_APP_PW",
    },
    "private_jc": {
        "provider": "private",
        "csv": "recipients_private_jc.csv",
        "log": "private_jc_log.csv",
        "pitch": "pitch_jc",
        "from_email": "jc@astraproductions.co",
        "my_domains": "astraproductions.co,astraproductionsbyjc.com",
        "interval": 60,
        "batch_size": 1,
        "cooldown_seconds": 60,
        "max_messages_1h": 30,
        "repeat": True,
        "human_mode": True,
        "max_total": 0,
        "stop_at_local": "12:00",
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": False,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "prune_sent": True,
        "password_env": "PRIVATE_JC_PASSWORD",
        "dashboard_enabled": True,
        "dashboard_manual_only": True,
        "tmux_session": "private_jc",
    },
    "private_jc_warm": {
        "provider": "private",
        "csv": "recipients_private_jc_warm.csv",
        "log": "private_jc_warm_log.csv",
        "pitch": "pitch_warm",
        "from_email": "jc@astraproductions.co",
        "my_domains": "astraproductions.co,astraproductionsbyjc.com",
        "interval": 60,
        "batch_size": 1,
        "cooldown_seconds": 60,
        "max_messages_1h": 30,
        "repeat": True,
        "human_mode": True,
        "max_total": 10,
        "stop_at_local": "12:00",
        "domain_log": "private_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "",
        "prune_sent": True,
        "password_env": "PRIVATE_JC_PASSWORD",
        "dashboard_enabled": True,
        "dashboard_manual_only": True,
        "tmux_session": "private_jc_warm",
        "pre_rendered_message": True,
        "allow_confirmed_warm_role_recipients": True,
    },

        #SEND GRID
    "sendgrid_annette": {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_1.csv",
        "log": "sendgrid_annette_log.csv",
        "pitch": "pitch1",
        "from_email": "annettedanek-akey@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 35,
        "batch_size": 1,
        "cooldown_seconds": 35,
        "repeat": True,
        "stop_at_local": "12:00",
        "max_total": 201,
        "domain_log": "sendgrid_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "daily_target": 200,
        "prune_sent": True,
        "unsubscribe_group_id": 363425,
        "groups_to_display": [363425],
    },
    "sendgrid_jordan": {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_2.csv",
        "log": "sendgrid_jordan_log.csv",
        "pitch": "pitch2",
        "from_email": "jordankendrick@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 35,
        "batch_size": 1,
        "cooldown_seconds": 35,
        "repeat": True,
        "stop_at_local": "12:00",
        "max_total": 201,
        "domain_log": "sendgrid_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "daily_target": 200,
        "prune_sent": True,
        "unsubscribe_group_id": 363425,
        "groups_to_display": [363425],
    },
    "sendgrid_jodi": {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_3.csv",
        "log": "sendgrid_jodi_log.csv",
        "pitch": "pitch3",
        "from_email": "jodihorowitz@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 35,
        "batch_size": 1,
        "cooldown_seconds": 35,
        "repeat": True,
        "stop_at_local": "12:00",
        "max_total": 201,
        "domain_log": "sendgrid_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "daily_target": 200,
        "prune_sent": True,
        "unsubscribe_group_id": 363425,
        "groups_to_display": [363425],
    },
    "sendgrid_alison": {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_4.csv",
        "log": "sendgrid_alison_log.csv",
        "pitch": "pitch4",
        "from_email": "alisonaguair@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 35,
        "batch_size": 1,
        "cooldown_seconds": 35,
        "repeat": True,
        "stop_at_local": "12:00",
        "max_total": 201,
        "domain_log": "sendgrid_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "daily_target": 200,
        "prune_sent": True,
        "unsubscribe_group_id": 363425,
        "groups_to_display": [363425],
    },
    "sendgrid_fiorela": {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_5.csv",
        "log": "sendgrid_fiorela_log.csv",
        "pitch": "pitch5",
        "from_email": "fiorelladelima@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 35,
        "batch_size": 1,
        "cooldown_seconds": 35,
        "repeat": True,
        "stop_at_local": "12:00",
        "max_total": 201,
        "domain_log": "sendgrid_domain_log.csv",
        "suppress_invalid": True,
        "global_dedupe": True,
        "account_map": "account_map_private_sendgrid.csv",
        "always_send": "astraproductionsbyjc@gmail.com",
        "daily_target": 200,
        "prune_sent": True,
        "unsubscribe_group_id": 363425,
        "groups_to_display": [363425],
    },


}


def _managed_path(base_dir: Path, value: object) -> Path:
    text = str(value or "").strip()
    if not text:
        return base_dir
    path = Path(text)
    if path.is_absolute():
        return path
    return base_dir / path.name


def _resolve_shard_path(value: object) -> Path:
    path = _managed_path(SHARDS_DIR, value)
    settings.ensure_managed_shard_file(path, Path(str(value or "")).name)
    return path


def _resolve_log_path(value: object) -> Path:
    path = _managed_path(LOGS_DIR, value)
    settings.maybe_seed_file(path, Path(str(value or "")).name)
    return path


def _resolve_state_path(value: object) -> Path:
    path = _managed_path(STATE_DIR, value)
    settings.maybe_seed_file(path, Path(str(value or "")).name)
    return path


def _resolve_app_path(value: object) -> Path:
    return settings.app_path(str(value or "").strip())


def managed_dashboard_queue_path_allowed(profile_name: str, csv_path: Path) -> bool:
    configured_csv_name = Path(str(PROFILES.get(profile_name, {}).get("csv") or "")).name
    if not (configured_csv_name.startswith("recipients_") and configured_csv_name.endswith(".csv")):
        return True
    try:
        csv_path.resolve().relative_to(SHARDS_DIR.resolve())
        return True
    except ValueError:
        return False


def _safe_lock_name(value: object) -> str:
    text = str(value or "").strip() or "sender"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)


def profile_runtime_lock_path(profile_name: str) -> Path:
    return (STATE_DIR / "locks") / f"send_shard_{_safe_lock_name(profile_name)}.lock"


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def profile_runtime_lock_status(profile_name: str) -> Dict[str, object]:
    lock_path = profile_runtime_lock_path(profile_name)
    if not lock_path.exists():
        return {"locked": False, "path": str(lock_path), "pid": 0}
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                handle.seek(0)
                payload = json.loads(handle.read() or "{}")
            except Exception:
                payload = {}
            pid = _safe_int(payload.get("pid"))
            return {
                "locked": True,
                "path": str(lock_path),
                "pid": pid,
                "profile": str(payload.get("profile") or profile_name),
                "started_at_utc": str(payload.get("started_at_utc") or ""),
                "process_exists": _process_exists(pid),
            }
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"locked": False, "path": str(lock_path), "pid": 0}


@contextmanager
def acquire_profile_runtime_lock(profile_name: str, *, enabled: bool = True):
    if not enabled:
        yield None
        return
    lock_path = profile_runtime_lock_path(profile_name)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            status = profile_runtime_lock_status(profile_name)
            pid = int(status.get("pid") or 0)
            raise RuntimeError(
                f"Profile {profile_name} is already locked/running"
                + (f" by pid {pid}" if pid else "")
                + f" ({lock_path})."
            ) from exc
        handle.seek(0)
        handle.truncate()
        json.dump(
            {
                "profile": profile_name,
                "pid": os.getpid(),
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            handle,
            sort_keys=True,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        yield handle
    finally:
        try:
            handle.seek(0)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
        except Exception:
            pass
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _log_info_marks_sent(info: object) -> bool:
    text = str(info or "").strip().lower()
    return "outcome=sent" in text or '"outcome":"sent"' in text or "'outcome': 'sent'" in text


def _log_row_is_authoritative_sent(row: Dict[str, str]) -> bool:
    status = str(row.get("Status") or "").strip().upper()
    if status == "SENT":
        return True
    return status == "ATTEMPT" and _log_info_marks_sent(row.get("Info") or "")


def authoritative_send_log_paths(*extra_paths: Path) -> List[Path]:
    paths: List[Path] = []
    for path in extra_paths:
        if path and path not in paths:
            paths.append(path)
    for cfg in PROFILES.values():
        provider = str(cfg.get("provider") or "").strip().lower()
        if provider not in {"private", "sendgrid"}:
            continue
        for key in ("log", "domain_log"):
            raw = cfg.get(key) or ""
            if not raw:
                continue
            path = _resolve_log_path(raw)
            if path not in paths:
                paths.append(path)
    return paths


def email_logged_authoritative_sent(log_path: Path, email_addr: str) -> bool:
    email = norm_email(email_addr)
    if not email or not log_path.exists():
        return False
    try:
        with log_path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if norm_email(row.get("Email") or "") == email and _log_row_is_authoritative_sent(row):
                    return True
    except Exception:
        return False
    return False


def email_logged_authoritative_sent_any(paths: Sequence[Path], email_addr: str) -> bool:
    return any(email_logged_authoritative_sent(path, email_addr) for path in paths)


def send_idempotency_db_path() -> Path:
    return STATE_DIR / "send_idempotency.sqlite3"


def _init_send_idempotency_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS send_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            email TEXT NOT NULL,
            profile TEXT NOT NULL DEFAULT '',
            queue_file TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'reserved',
            reserved_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            outcome TEXT NOT NULL DEFAULT '',
            info TEXT NOT NULL DEFAULT '',
            UNIQUE(campaign_id, provider, email)
        )
        """
    )
    conn.commit()


def reserve_send_idempotency(
    *,
    campaign_id: str,
    provider: str,
    email: str,
    profile: str,
    queue_file: str,
    db_path: Path | None = None,
) -> tuple[bool, str]:
    clean_email = norm_email(email)
    clean_campaign = str(campaign_id or "").strip() or CAMPAIGN_TYPE_COLD
    clean_provider = str(provider or "").strip().lower() or "unknown"
    path = db_path or send_idempotency_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path, timeout=30) as conn:
        _init_send_idempotency_db(conn)
        conn.execute("BEGIN IMMEDIATE")
        clean_profile = str(profile or "").strip()
        if clean_profile == "private_jc_warm":
            cross_lane = conn.execute(
                "SELECT 1 FROM send_reservations WHERE email = ? LIMIT 1",
                (clean_email,),
            ).fetchone()
        else:
            cross_lane = conn.execute(
                "SELECT 1 FROM send_reservations WHERE email = ? AND profile = 'private_jc_warm' LIMIT 1",
                (clean_email,),
            ).fetchone()
        if cross_lane:
            return False, "cross_lane_reservation"
        try:
            conn.execute(
                """
                INSERT INTO send_reservations
                    (campaign_id, provider, email, profile, queue_file, status, reserved_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, 'reserved', ?, ?)
                """,
                (clean_campaign, clean_provider, clean_email, clean_profile, str(queue_file or ""), now, now),
            )
            conn.commit()
            return True, "reserved"
        except sqlite3.IntegrityError:
            return False, "duplicate_reservation"


def record_send_idempotency_outcome(
    *,
    campaign_id: str,
    provider: str,
    email: str,
    outcome: str,
    info: str = "",
    db_path: Path | None = None,
) -> None:
    clean_email = norm_email(email)
    clean_campaign = str(campaign_id or "").strip() or CAMPAIGN_TYPE_COLD
    clean_provider = str(provider or "").strip().lower() or "unknown"
    path = db_path or send_idempotency_db_path()
    if not path.exists():
        return
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path, timeout=30) as conn:
        _init_send_idempotency_db(conn)
        conn.execute(
            """
            UPDATE send_reservations
            SET status = ?, outcome = ?, info = ?, updated_at_utc = ?
            WHERE campaign_id = ? AND provider = ? AND email = ?
            """,
            (
                str(outcome or "").strip() or "unknown",
                str(outcome or "").strip()[:100],
                str(info or "").strip()[:500],
                now,
                clean_campaign,
                clean_provider,
                clean_email,
            ),
        )
        conn.commit()


def campaign_id_for_row(row: Dict[str, str], fallback_campaign_type: str) -> str:
    return (
        get_row_value_ci(row, ["campaign_id", "CampaignId", "CampaignID", "dispatch_id", "DispatchId", "preview_id", "PreviewId"])
        or normalize_campaign_type(get_row_value_ci(row, ["campaign_type", "CampaignType", "campaign type"]) or fallback_campaign_type)
    )


def claim_queue_row(csv_path: Path, email_addr: str) -> bool:
    target = norm_email(email_addr)
    if not target or not csv_path.exists():
        return False
    with lock_files([csv_path]):
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ["Email", "FirstName", "BookTitle"]
            kept_rows: List[Dict[str, str]] = []
            claimed = False
            for row in reader:
                clean_row = {k: v for k, v in row.items() if k is not None}
                if not claimed and norm_email(resolve_recipient_email(clean_row) or clean_row.get("Email") or "") == target:
                    claimed = True
                    continue
                kept_rows.append(clean_row)
        if claimed:
            rewrite_csv_rows(csv_path, fieldnames, kept_rows)
        return claimed

# ===== SIGNATURES =====
SIGNATURE_CID = "sigimg"

SIGNATURE_BY_FROM: Dict[str, str] = {
    # --- PrivateEmail 5 accounts (each different) ---
    "jordankendrick@barnesnoblemarketing.com":"sig_private_jordan.png",
    "jodihorowitz@barnesnoblemarketing.com":  "sig_private_jodi.png",
    "alisonaguair@barnesnoblemarketing.com": "sig_private_alison.png",
    "fiorelladelima@barnesnoblemarketing.com": "sig_private_fiorela.png",
    "annettedanek-akey@barnesnoblemarketing.com": "sig_private_annette.png",
    "jc@astraproductions.co": "LOGO ASTRA bg.png",
    "astraproductionsbyjc@gmail.com": "LOGO ASTRA bg.png",
}
SIGNATURE_BY_PITCH = {
    }


# ===== SENDGRID / BOOKSTORE PITCH COPY =====
SENDGRID_BOOK_TITLE_OPENING = (
"Our team came across {BookTitle} and thought it may be a good fit for readers "
"browsing independent books this summer."
)

SENDGRID_BOOK_TITLE_SUBJECT = "Shelf review opportunity for {BookTitle}"

BOOK_TITLE_GENERIC_SUBJECT = "Independent author shelf review opportunity"

BOOK_TITLE_GENERIC_OPENING = (
"Our team came across your author profile and thought your work may be a good fit "
"for readers browsing independent books this summer."
)

BOOK_TITLE_MISSING_FALLBACK_OPENING = BOOK_TITLE_GENERIC_OPENING

PITCH_1_5_BODY = f"""Hi {{FirstName}},

{SENDGRID_BOOK_TITLE_OPENING}

We’re currently reviewing a limited number of independent books for possible consignment placement on our physical bookstore shelves.

We’d like to take a look at {{BookTitle}} for the next available shelf review slot. This is not a publishing offer, and approval is not guaranteed. Each title is reviewed for quality, presentation, genre fit, pricing, retail suitability, and reader interest.


If approved, your book would be stocked under a consignment arrangement. You would receive 85% of total book sales, with quarterly sales reports and payouts.

As part of our mid-year author promotion, approved authors will also receive a free premium author website built by our web development team. A strong book can still lose attention if the reader’s first impression does not feel clear, polished, and credible, so this bonus is designed to help selected authors present their work professionally and turn more reader interest into clicks.

For approved titles, the author-covered stocking and distribution packages are:

750 copies — $250
1,500 copies — $500
2,500 copies — $750
3,500 copies — $1,000

Each package supports the physical stocking and distribution process. Final approval depends on our review and whether the title is a suitable fit for our shelves.

If you have another title you’d prefer us to consider, you’re welcome to send that instead.

Would you like us to take a look and see if {{BookTitle}} is a fit for the next available shelf review slot?

Best regards,
{{SIGIMG}}

If this is not a fit, no problem — just reply “no” and we will not follow up.
"""

PITCH_1_5_GENERIC_BODY = f"""Hi {{FirstName}},

{BOOK_TITLE_GENERIC_OPENING}

We’re currently reviewing a limited number of independent books for possible consignment placement on our physical bookstore shelves.

We’d be happy to take a look at one of your titles for the next available shelf review slot. This is not a publishing offer, and approval is not guaranteed. Each title is reviewed for quality, presentation, genre fit, pricing, retail suitability, and reader interest.


If approved, your book would be stocked under a consignment arrangement. You would receive 85% of total book sales, with quarterly sales reports and payouts.

As part of our mid-year author promotion, approved authors will also receive a free premium author website built by our web development team. A strong book can still lose attention if the reader’s first impression does not feel clear, polished, and credible, so this bonus is designed to help selected authors present their work professionally and turn more reader interest into clicks.

For approved titles, the author-covered stocking and distribution packages are:

750 copies — $250
1,500 copies — $500
2,500 copies — $750
3,500 copies — $1,000

Each package supports the physical stocking and distribution process. Final approval depends on our review and whether the title is a suitable fit for our shelves.

If you have a specific title you’d like us to consider first, you’re welcome to send it for review.

Would you like us to take a look at one of your titles for the next available shelf review slot?

Best regards,
{{SIGIMG}}

If this is not a fit, no problem — just reply “no” and we will not follow up.
"""


# ===== JC / ASTRA PRIVATE PITCH COPY =====
# Edit this section to change the private JC Astra outreach email.
# Keep {BookTitle} and {{FirstName}} exactly formatted.

PRIVATE_JC_BOOK_TITLE_OPENING = (
    "I came across {BookTitle} and thought it deserved a sharper online presence: "
    "one that makes the book easier to understand, easier to trust, "
    "and easier for the right reader to take seriously."
)

PRIVATE_JC_GENERIC_OPENING = (
    "I came across your author profile and thought your work deserved a sharper online presence: "
    "one that makes your books easier to understand, easier to trust, "
    "and easier for the right reader to take seriously."
)

PITCH_JC_SUBJECT = "Website direction for {BookTitle}"
PITCH_JC_SUBJECT_FALLBACK = "Website direction for your author brand"

PITCH_JC_BODY = f"""Hi {{FirstName}},

{PRIVATE_JC_BOOK_TITLE_OPENING}

That online first impression matters. Before a reader, reviewer, publisher, bookstore, or media contact takes the next step, they usually look the author up first.

Astra Productions helps authors turn that moment into a stronger sales and credibility asset through polished author websites, book landing pages, book trailers, and launch visuals built around clarity, trust, and presentation.

If useful, I can send over a clean website direction for how {{BookTitle}} could be positioned more strongly online.

Windelle JC
Founder & CEO, Astra Productions
astraproductions.co

If you would rather not hear from me again, reply “unsubscribe.”
"""

PITCH_JC_GENERIC_BODY = f"""Hi {{FirstName}},

{PRIVATE_JC_GENERIC_OPENING}

That online first impression matters. Before a reader, reviewer, publisher, bookstore, or media contact takes the next step, they usually look the author up first.

Astra Productions helps authors turn that moment into a stronger sales and credibility asset through polished author websites, book landing pages, book trailers, and launch visuals built around clarity, trust, and presentation.

If useful, I can send over a clean website direction for how your author brand could be positioned more strongly online.

Windelle JC
Founder & CEO, Astra Productions
astraproductions.co

If you would rather not hear from me again, reply “unsubscribe.”
"""

PITCH_WARM_SUBJECT = "Quick idea for {BookTitleOrProject}"
PITCH_WARM_SUBJECT_FALLBACK = "Quick idea for your book launch"
PITCH_WARM_BODY = """Hi {FirstName},

I came across {BookTitleOrProject} and noticed you’ve been building momentum around the launch, including: {NeedSignal}

I’m reaching out because if this is still active, Astra Productions could help strengthen how the book is presented online before more readers, backers, or media opportunities see it.

Based on what I saw, the strongest direction would be {RecommendedService} — a cleaner, more cinematic presentation that makes the project feel polished and easier to understand at first glance.

A strong creative direction here would be:
{OutreachAngle}

If this is already handled, no worries. But if you’re still looking at ways to improve the launch presentation, I’d be happy to send over a simple direction for how this could look.

Windelle JC
Creative Director, Astra Productions

Examples: astraproductions.co

P.S. If you’d rather not hear from me again, just reply unsub.
"""


# ===== PITCH REGISTRY =====
PITCHES = {
    "pitch1": {
        "subject": SENDGRID_BOOK_TITLE_SUBJECT,
        "subject_fallback": BOOK_TITLE_GENERIC_SUBJECT,
        "body": PITCH_1_5_BODY,
        "body_fallback": PITCH_1_5_GENERIC_BODY,
    },

    "pitch2": {
        "subject": SENDGRID_BOOK_TITLE_SUBJECT,
        "subject_fallback": BOOK_TITLE_GENERIC_SUBJECT,
        "body": PITCH_1_5_BODY,
        "body_fallback": PITCH_1_5_GENERIC_BODY,
    },

    "pitch3": {
        "subject": SENDGRID_BOOK_TITLE_SUBJECT,
        "subject_fallback": BOOK_TITLE_GENERIC_SUBJECT,
        "body": PITCH_1_5_BODY,
        "body_fallback": PITCH_1_5_GENERIC_BODY,
    },

    "pitch4": {
        "subject": SENDGRID_BOOK_TITLE_SUBJECT,
        "subject_fallback": BOOK_TITLE_GENERIC_SUBJECT,
        "body": PITCH_1_5_BODY,
        "body_fallback": PITCH_1_5_GENERIC_BODY,
    },

    "pitch5": {
        "subject": SENDGRID_BOOK_TITLE_SUBJECT,
        "subject_fallback": BOOK_TITLE_GENERIC_SUBJECT,
        "body": PITCH_1_5_BODY,
        "body_fallback": PITCH_1_5_GENERIC_BODY,
    },

    "pitch_jc": {
        "subject": PITCH_JC_SUBJECT,
        "subject_fallback": PITCH_JC_SUBJECT_FALLBACK,
        "body": PITCH_JC_BODY,
        "body_fallback": PITCH_JC_GENERIC_BODY,
    },
    "pitch_warm": {
        "subject": PITCH_WARM_SUBJECT,
        "subject_fallback": PITCH_WARM_SUBJECT_FALLBACK,
        "body": PITCH_WARM_BODY,
        "pre_rendered_message": True,
    },
}


# ===== RENDER SAFETY / PLACEHOLDER RULES =====
BOOK_TITLE_FALLBACK_OPENINGS = (
    PRIVATE_JC_BOOK_TITLE_OPENING,
    SENDGRID_BOOK_TITLE_OPENING,
)
UNRESOLVED_PLACEHOLDER_RE = re.compile(r"{[A-Za-z][A-Za-z0-9_]*}")
BLOCKED_RENDER_PLACEHOLDER_RE = re.compile(r"{{?\s*(?:BookTitle|Title|FirstName|AuthorName)\s*}}?")
PLACEHOLDER_LIKE_TOKEN_RE = re.compile(r"{[A-Za-z][A-Za-z0-9_]*}|\[[^\[\]\r\n]+\]|<<[^<>\r\n]+>>")
BRACE_PLACEHOLDER_TOKEN_RE = re.compile(r"{([A-Za-z][A-Za-z0-9_]*)}")
SQUARE_PLACEHOLDER_TOKEN_RE = re.compile(r"\[([^\[\]\r\n]+)\]")
ANGLE_PLACEHOLDER_TOKEN_RE = re.compile(r"<<([^<>\r\n]+)>>")
ALLOWED_RENDER_PLACEHOLDERS = {"{SIGIMG}"}
BOOK_TITLE_SOURCE_COLUMNS = (
    "BookTitle",
    "book_title",
    "book title",
    "Title",
    "title",
    "Publication Title",
    "PublicationTitle",
    "publication_title",
    "Product Title",
    "product_title",
    "Work Title",
    "work_title",
    "Manuscript Title",
    "manuscript_title",
    "Book Name",
    "book_name",
    "Project Title",
    "project_title",
)


def placeholder_like_tokens(value: object) -> List[str]:
    return PLACEHOLDER_LIKE_TOKEN_RE.findall(str(value or ""))


def normalize_render_field_value(value: object) -> Tuple[str, List[str]]:
    raw = str(value or "").strip()
    notes: List[str] = []
    if not raw:
        return "", notes

    cleaned = BRACE_PLACEHOLDER_TOKEN_RE.sub(lambda match: match.group(1), raw)
    if cleaned != raw:
        notes.append("removed_brace_placeholder_punctuation")

    before_square = cleaned
    cleaned = SQUARE_PLACEHOLDER_TOKEN_RE.sub(lambda match: f"({match.group(1).strip()})", cleaned)
    if cleaned != before_square:
        notes.append("converted_square_brackets_to_parentheses")

    before_angle = cleaned
    cleaned = ANGLE_PLACEHOLDER_TOKEN_RE.sub(lambda match: match.group(1).strip(), cleaned)
    if cleaned != before_angle:
        notes.append("removed_angle_placeholder_punctuation")

    return cleaned.strip(), notes


def norm_email(s: str) -> str:
    _, addr = parseaddr(s or "")
    return addr.strip().lower()


def make_unsub_mailto(unsub_email: str) -> str:
    return f"mailto:{unsub_email}?subject={quote('unsubscribe')}&body={quote('unsubscribe')}"


def invalid_subject_book_title(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    normalized = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if raw.startswith("{") and raw.endswith("}"):
        return True
    return normalized in {"booktitle", "title", "none", "nan", "null", "yourbook"}


BAD_BOOK_TITLE_KEYS = {
    "approved",
    "archway",
    "authorhouse",
    "authorhouseuk",
    "balboa",
    "bookbaby",
    "booktrailer",
    "canceled",
    "cancelled",
    "complete",
    "completed",
    "ebook",
    "hardcover",
    "illustrationpackage",
    "inprogress",
    "iuniverse",
    "launchpackage",
    "lulu",
    "marketingpackage",
    "na",
    "notstarted",
    "paperback",
    "pending",
    "publishingpackage",
    "rejected",
    "resubmission",
    "submission",
    "tbd",
    "trafford",
    "unknown",
    "website",
    "websitepackage",
    "westbow",
    "xlibris",
}
BOOK_TITLE_PHONE_RE = re.compile(r"^[+()\d\s.\-]{7,}$")
BOOK_TITLE_PERCENT_RE = re.compile(r"^\s*\d+(?:\.\d+)?\s*%\s*$")
BOOK_TITLE_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
BOOK_TITLE_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
BOOK_TITLE_PRICE_RE = re.compile(r"(?i)^\s*(?:[$€£]\s*\d+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?\s*(?:usd|eur|gbp|php|cad|aud))\s*$")
BOOK_TITLE_DATE_RE = re.compile(r"^\s*(?:\d{1,4}[-/]\d{1,2}(?:[-/]\d{1,4})?|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s*$")


def invalid_campaign_book_title(
    value: str,
    *,
    author_name: str = "",
    first_name: str = "",
    last_name: str = "",
) -> bool:
    raw = str(value or "").strip()
    if invalid_subject_book_title(raw):
        return True
    normalized = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if normalized in BAD_BOOK_TITLE_KEYS:
        return True
    blocked_person_values = {
        re.sub(r"[^a-z0-9]+", "", text.lower())
        for text in (author_name, first_name, last_name, f"{first_name} {last_name}".strip())
        if str(text or "").strip()
    }
    if normalized and normalized in blocked_person_values:
        return True
    digits = re.sub(r"\D+", "", raw)
    if BOOK_TITLE_PHONE_RE.match(raw) and len(digits) >= 7:
        return True
    if BOOK_TITLE_PERCENT_RE.match(raw):
        return True
    if BOOK_TITLE_PRICE_RE.match(raw):
        return True
    if BOOK_TITLE_DATE_RE.match(raw):
        return True
    if BOOK_TITLE_EMAIL_RE.match(raw.lower()):
        return True
    if BOOK_TITLE_URL_RE.search(raw):
        return True
    lowered = raw.lower()
    return any(term in lowered for term in ("package", "book trailer", "website"))


def template_requires_book_title(subject: str, body_template: str) -> bool:
    return "{BookTitle}" in (subject or "") or "{BookTitle}" in (body_template or "")


def _book_title_body_without_fallback_opening(body_template: str) -> str:
    text = body_template or ""
    for opening in BOOK_TITLE_FALLBACK_OPENINGS:
        text = text.replace(opening, "")
    return text


def _unresolved_placeholders(*values: str) -> Set[str]:
    placeholders: Set[str] = set()
    for value in values:
        placeholders.update(UNRESOLVED_PLACEHOLDER_RE.findall(value or ""))
    return placeholders - ALLOWED_RENDER_PLACEHOLDERS

def book_title_fallback_supported(subject: str, body_template: str, subject_fallback: str, body_fallback: str = "") -> bool:
    if not template_requires_book_title(subject, body_template):
        return False
    if "{BookTitle}" in (subject or "") and not str(subject_fallback or "").strip():
        return False
    fallback_body_template = str(body_fallback or "").strip() or (
        PITCH_1_5_GENERIC_BODY if str(body_template or "").strip() == PITCH_1_5_BODY.strip() else body_template
    )
    if "{BookTitle}" in _book_title_body_without_fallback_opening(fallback_body_template):
        return False
    subject_text, body_text, _html_body, _cid = render_message_parts(
        GENERIC_SALUTATION,
        "",
        subject,
        fallback_body_template,
        DEFAULT_UNSUB_EMAIL,
        signature_file=None,
        subject_fallback=subject_fallback,
        body_fallback=fallback_body_template,
    )
    if _unresolved_placeholders(subject_text, body_text):
        return False
    if "{BookTitle}" in body_text:
        return False
    return True


def csv_fieldnames(path: Path) -> List[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [str(field or "").strip().lstrip("\ufeff") for field in (reader.fieldnames or [])]


def validate_book_title_queue_contract(
    *,
    csv_path: Path,
    rows: Sequence[Dict[str, str]],
    subject: str,
    body_template: str,
    profile_name: str,
    subject_fallback: str = "",
    body_fallback: str = "",
    strict_book_title_required: bool = False,
) -> bool:
    if not template_requires_book_title(subject, body_template):
        return True

    fallback_supported = (
        not strict_book_title_required
        and book_title_fallback_supported(subject, body_template, subject_fallback, body_fallback=body_fallback)
    )
    fieldnames = csv_fieldnames(csv_path)
    has_book_title = any((field or "").strip().lower() == "booktitle" for field in fieldnames)
    if not has_book_title and not fallback_supported:
        print(
            "ERROR: BookTitle-personalized profile requires a BookTitle column: "
            f"profile={profile_name or '-'} csv={csv_path}"
        )
        return False

    bad_rows: List[str] = []
    unresolved_rows: List[str] = []
    for index, row in enumerate(rows, start=1):
        book_title = resolve_book_title(row, get_row_value_ci(row, ["BookTitle"]))
        if not fallback_supported and not book_title:
            bad_rows.append(f"row={index} BookTitle=blank_or_unsafe")
            if len(bad_rows) >= 5:
                break
        if fallback_supported:
            normalized_book_title, normalization_notes = normalize_render_field_value(book_title)
            email_addr = resolve_recipient_email(row)
            raw_author = get_personalization_name(row)
            author = choose_salutation_name(raw_author, email_addr)
            first_name = author.split()[0] if author else GENERIC_SALUTATION
            merge_fields = row_merge_fields(row, email_addr, first_name, normalized_book_title)
            normalized_book_title = merge_fields.get("BookTitle", normalized_book_title)
            subject_text, body_text, _html_body, _cid = render_message_parts(
                author,
                normalized_book_title,
                subject,
                body_template,
                DEFAULT_UNSUB_EMAIL,
                signature_file=None,
                merge_fields=merge_fields,
                subject_fallback=subject_fallback,
                body_fallback=body_fallback,
            )
            unresolved = sorted(_unresolved_placeholders(subject_text, body_text))
            remaining_tokens = [
                token
                for token in placeholder_like_tokens(subject_text + "\n" + body_text)
                if token not in ALLOWED_RENDER_PLACEHOLDERS
            ]
            if unresolved or "{BookTitle}" in body_text or remaining_tokens:
                tokens = unresolved or remaining_tokens or ["{BookTitle}"]
                token_text = ",".join(tokens[:3])
                note_text = f" normalization_note={'+'.join(normalization_notes)}" if normalization_notes else ""
                unresolved_rows.append(f"row={index} field=BookTitle token={token_text} reason=unresolved_placeholder{note_text}")
                if len(unresolved_rows) >= 5:
                    break
    if bad_rows:
        print(
            "ERROR: BookTitle-personalized profile cannot use this queue because BookTitle is blank or unsafe. "
            f"profile={profile_name or '-'} csv={csv_path}"
        )
        for item in bad_rows:
            print(f" - {item}")
        return False
    if unresolved_rows:
        print(
            "ERROR: BookTitle fallback rendering would leave unresolved placeholders. "
            f"profile={profile_name or '-'} csv={csv_path}"
        )
        for item in unresolved_rows:
            print(f" - {item}")
        return False
    return True


SENDGRID_ASM_GROUP_UNSUB_RAW_URL = "<%asm_group_unsubscribe_raw_url%>"


def build_sendgrid_list_unsubscribe_header(unsub_email: str) -> str:
    mailto_target = make_unsub_mailto(unsub_email)
    https_target = SENDGRID_ASM_GROUP_UNSUB_RAW_URL
    return f"<{mailto_target}>, <{https_target}>"


def parse_ts(ts: str) -> Optional[datetime]:
    ts = (ts or "").strip()
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def single_line(text: str) -> str:
    return " ".join((text or "").split())


def clean_name_token(value: str) -> str:
    token = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", (value or "").strip())
    return token


def choose_salutation_name(author_name: str, email_addr: str) -> str:
    raw_name = (author_name or "").strip()
    if not raw_name:
        return GENERIC_SALUTATION
    first_token = clean_name_token(raw_name.split()[0])
    if not first_token or len(first_token) <= 1:
        return GENERIC_SALUTATION
    if not first_token[0].isupper():
        return GENERIC_SALUTATION

    token_low = first_token.lower()
    if token_low in NONPERSON_NAME_TOKENS:
        return GENERIC_SALUTATION

    localpart = ""
    if "@" in (email_addr or ""):
        localpart = email_addr.split("@", 1)[0].strip().lower()
    business_hit = any(hint in localpart for hint in BUSINESS_LOCALPART_HINTS)
    if business_hit and (localpart.startswith(token_low) or token_low in localpart):
        return GENERIC_SALUTATION

    return first_token


def is_external(addr: str, my_domains: Set[str]) -> bool:
    if "@" not in addr:
        return False
    return addr.split("@", 1)[1] not in my_domains


def read_rows(path: Path) -> List[Dict[str, str]]:
    def clean(v) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return " ".join(str(x).strip() for x in v if x is not None).strip()
        return str(v).strip()

    rows: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            row: Dict[str, str] = {}
            for k, v in r.items():
                if k is None:
                    continue
                key = str(k).strip().lstrip("\ufeff")
                row[key] = clean(v)
            rows.append(row)
    return rows


def load_emails_from_csv(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    out: Set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def local_today_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def parse_stop_at_local(stop_at_local: str) -> Optional[datetime]:
    raw = (stop_at_local or "").strip()
    if not raw:
        return None
    try:
        hh, mm = raw.split(":", 1)
        hour = int(hh)
        minute = int(mm)
    except Exception:
        raise ValueError("stop_at_local must be HH:MM (24-hour format).")
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("stop_at_local hour/minute out of range.")

    now_local = datetime.now().astimezone()
    target = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_local:
        target = target + timedelta(days=1)
    return target


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def load_sendgrid_counters(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_sendgrid_counters_unlocked(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_sendgrid_counters(path: Path, counters: Dict[str, Dict[str, object]]) -> None:
    tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
    lock_path = path.with_suffix(".lock")
    payload = json.dumps(counters, indent=2, sort_keys=True, ensure_ascii=True)
    with lock_path.open("a", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            tmp_path.replace(path)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            fcntl.flock(lockf, fcntl.LOCK_UN)


def get_sendgrid_sent_today(
    counters: Dict[str, Dict[str, object]],
    key: str,
) -> Tuple[int, str]:
    entry = counters.get(key, {})
    if not isinstance(entry, dict):
        return 0, ""
    today = local_today_str()
    if entry.get("date") != today:
        return 0, entry.get("last_success") or ""
    return _safe_int(entry.get("sent")), entry.get("last_success") or ""


def increment_sendgrid_counter(
    counters: Dict[str, Dict[str, object]],
    key: str,
    path: Path,
) -> int:
    today = local_today_str()
    entry = counters.get(key, {})
    if not isinstance(entry, dict):
        entry = {}
    if entry.get("date") != today:
        entry = {"date": today, "sent": 0, "last_success": entry.get("last_success") or ""}
    entry["sent"] = _safe_int(entry.get("sent")) + 1
    entry["last_success"] = datetime.now().astimezone().isoformat()
    counters[key] = entry
    save_sendgrid_counters(path, counters)
    return _safe_int(entry.get("sent"))


def get_sendgrid_sent_today_live(path: Path, key: str) -> Tuple[int, str]:
    if not key:
        return 0, ""
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            counters = _load_sendgrid_counters_unlocked(path)
            return get_sendgrid_sent_today(counters, key)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def increment_sendgrid_counters_live(path: Path, keys: List[str]) -> Dict[str, int]:
    clean_keys: List[str] = []
    seen: Set[str] = set()
    for raw in keys:
        key = (raw or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        clean_keys.append(key)
    if not clean_keys:
        return {}

    lock_path = path.with_suffix(".lock")
    tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
    today = local_today_str()
    now_iso = datetime.now().astimezone().isoformat()
    result: Dict[str, int] = {}
    with lock_path.open("a", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            counters = _load_sendgrid_counters_unlocked(path)
            for key in clean_keys:
                entry = counters.get(key, {})
                if not isinstance(entry, dict):
                    entry = {}
                if entry.get("date") != today:
                    entry = {"date": today, "sent": 0, "last_success": entry.get("last_success") or ""}
                entry["sent"] = _safe_int(entry.get("sent")) + 1
                entry["last_success"] = now_iso
                counters[key] = entry
                result[key] = _safe_int(entry.get("sent"))
            payload = json.dumps(counters, indent=2, sort_keys=True, ensure_ascii=True)
            tmp_path.write_text(payload, encoding="utf-8")
            tmp_path.replace(path)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            fcntl.flock(lockf, fcntl.LOCK_UN)
    return result


def load_log_statuses(log_path: Path) -> Tuple[Set[str], Set[str], Optional[datetime]]:
    sent: Set[str] = set()
    failed: Set[str] = set()
    last_success: Optional[datetime] = None
    if not log_path.exists():
        return sent, failed, last_success
    with log_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            status = (r.get("Status") or "").strip().upper()
            email_addr = norm_email(r.get("Email") or "")
            if status == "SENT":
                if email_addr:
                    sent.add(email_addr)
                ts = parse_ts(r.get("TimestampUTC") or "")
                if ts and (last_success is None or ts > last_success):
                    last_success = ts
            elif status in ("ERROR", "INVALID"):
                if email_addr:
                    failed.add(email_addr)
    return sent, failed, last_success


def count_sent_today_from_log(log_path: Path) -> int:
    if not log_path.exists():
        return 0
    today = datetime.now().astimezone().date()
    count = 0
    with log_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            status = (r.get("Status") or "").strip().upper()
            if status != "SENT":
                continue
            ts = parse_ts(r.get("TimestampUTC") or "")
            if ts and ts.astimezone().date() == today:
                count += 1
    return count


def parse_email_list(value: str) -> Set[str]:
    out: Set[str] = set()
    for raw in (value or "").split(","):
        email_addr = norm_email(raw)
        if email_addr:
            out.add(email_addr)
    return out


def prioritize_always_send_rows(
    rows: List[Dict[str, str]],
    always_send_set: Set[str],
    *,
    allow_missing_rows: bool = True,
) -> List[Dict[str, str]]:
    if not always_send_set:
        return list(rows)

    prioritized: List[Dict[str, str]] = []
    remaining: List[Dict[str, str]] = []
    emitted: Set[str] = set()

    for email_addr in sorted(always_send_set):
        for row in rows:
            if norm_email(row.get("Email") or "") == email_addr:
                prioritized.append(row)
                emitted.add(email_addr)
                break
        else:
            if not allow_missing_rows:
                continue
            prioritized.append({"Email": email_addr})
            emitted.add(email_addr)

    for row in rows:
        email_addr = norm_email(row.get("Email") or "")
        if email_addr in emitted:
            continue
        remaining.append(row)

    return prioritized + remaining


def parse_token_list(value: str) -> Set[str]:
    out: Set[str] = set()
    for raw in (value or "").split(","):
        token = (raw or "").strip().lower()
        if token:
            out.add(token)
    return out


def parse_name_list(value: str) -> List[str]:
    return [x.strip().lower() for x in (value or "").split(",") if x.strip()]


def canonical_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def split_canonical_tokens(value: str) -> Set[str]:
    raw = (value or "").strip()
    if not raw:
        return set()
    parts = re.split(r"[;,/|]+", raw)
    out: Set[str] = set()
    for p in parts:
        tok = canonical_token(p)
        if tok:
            out.add(tok)
    return out


def get_row_value_ci(row: Dict[str, str], col_names: List[str]) -> str:
    if not row or not col_names:
        return ""
    lower_row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
    for name in col_names:
        key = str(name or "").strip().lower()
        if key in lower_row:
            return lower_row[key]
    return ""


def resolve_recipient_email(row: Dict[str, str]) -> str:
    email = norm_email(get_row_value_ci(row, ["Email"]))
    if email:
        return email
    return norm_email(get_row_value_ci(row, ["AuthorEmail", "author_email"]))


def get_personalization_name(row: Dict[str, str]) -> str:
    lower_keys = {(key or "").strip().lower() for key in row}
    if "personalization_allowed" in lower_keys:
        allowed = get_row_value_ci(row, ["personalization_allowed"]).strip().lower()
        if allowed not in {"true", "1", "yes"}:
            return ""
    return get_row_value_ci(
        row,
        ["first_name_clean", "firstname", "first_name", "first name", "authorname", "author_name", "author", "name"],
    )


def resolve_book_title(row: Dict[str, str], explicit_book_title: str = "") -> str:
    author_name = get_row_value_ci(row, ["AuthorName", "author_name", "FullName", "full_name", "author", "name"])
    first_name = get_row_value_ci(row, ["FirstName", "first_name", "first name", "first_name_clean", "firstname"])
    last_name = get_row_value_ci(row, ["LastName", "last_name", "last name", "last_name_clean", "lastname"])
    candidates = [explicit_book_title]
    candidates.extend(get_row_value_ci(row, [column]) for column in BOOK_TITLE_SOURCE_COLUMNS)
    seen: Set[str] = set()
    for candidate in candidates:
        normalized_title, _notes = normalize_render_field_value(candidate)
        key = normalized_title.casefold()
        if not normalized_title or key in seen:
            continue
        seen.add(key)
        if not invalid_campaign_book_title(
            normalized_title,
            author_name=author_name,
            first_name=first_name,
            last_name=last_name,
        ):
            return normalized_title
    return ""


def row_merge_fields(row: Dict[str, str], to_email: str, first_name: str, book_title: str) -> Dict[str, str]:
    resolved_book_title = resolve_book_title(row, book_title)
    return {
        "FirstName": (first_name or GENERIC_SALUTATION).strip() or GENERIC_SALUTATION,
        "AuthorName": get_row_value_ci(row, ["AuthorName", "author_name", "FullName", "full_name", "author", "name"]),
        "AuthorEmail": get_row_value_ci(row, ["AuthorEmail", "author_email"]) or to_email,
        "BookTitle": resolved_book_title,
        "PersonalizedOpeningLine": get_row_value_ci(
            row,
            ["PersonalizedOpeningLine", "personalized_opening_line", "personalized opening line"],
        ),
    }


def localpart(email_addr: str) -> str:
    if "@" not in (email_addr or ""):
        return ""
    return email_addr.split("@", 1)[0].strip().lower()


def domainpart(email_addr: str) -> str:
    if "@" not in (email_addr or ""):
        return ""
    return email_addr.split("@", 1)[1].strip().lower()


def is_role_recipient(email_addr: str, role_set: Set[str]) -> bool:
    lp = localpart(email_addr)
    if not lp:
        return False
    return lp in role_set


def should_block_role_recipient_for_runtime(
    email_addr: str,
    role_set: Set[str],
    *,
    profile_name: str,
    queue_path: Path,
    block_role_recipients: bool,
    allow_confirmed_warm_role_recipients: bool,
) -> bool:
    if not block_role_recipients or not role_set:
        return False
    confirmed_warm_queue = (
        profile_name == "private_jc_warm"
        and Path(queue_path).name == "recipients_private_jc_warm.csv"
        and allow_confirmed_warm_role_recipients
    )
    if confirmed_warm_queue:
        return False
    return is_role_recipient(email_addr, role_set)


def load_already_done(sent_log: Path) -> Set[str]:
    if not sent_log.exists():
        return set()
    out: Set[str] = set()
    with sent_log.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = (r.get("Status") or "").strip().upper()
            if st == "ATTEMPT" and _log_info_marks_sent(r.get("Info") or ""):
                st = "SENT"
            if st not in ("SENT", "INVALID"):
                continue
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def load_log_status_emails(sent_log: Path, statuses: Set[str]) -> Set[str]:
    if not sent_log.exists():
        return set()
    wanted = {str(status or "").strip().upper() for status in statuses if str(status or "").strip()}
    out: Set[str] = set()
    with sent_log.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = (r.get("Status") or "").strip().upper()
            if st not in wanted:
                continue
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


def load_done_statuses_from_logs(paths: Sequence[Path], statuses: Set[str]) -> Set[str]:
    out: Set[str] = set()
    for path in paths:
        out |= load_log_status_emails(path, statuses)
    return out


def load_bad_sendgrid_event_emails(path: Path = settings.WEBHOOK_EVENTS_PATH) -> Set[str]:
    if not path.exists():
        return set()
    out: Set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except Exception:
                continue
            status = str(event.get("status") or event.get("event") or "").strip().lower().replace("-", "_").replace(" ", "_")
            if status not in BAD_SENDGRID_EVENT_STATUSES:
                continue
            email = norm_email(event.get("email") or "")
            if email:
                out.add(email)
    return out


def email_logged_sent(sent_log: Path, email_addr: str) -> bool:
    email = norm_email(email_addr)
    if not email or not sent_log.exists():
        return False
    try:
        with sent_log.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if norm_email(r.get("Email") or "") != email:
                    continue
                if _log_row_is_authoritative_sent(r):
                    return True
    except Exception:
        return False
    return False


def resolve_map_path(base: Path, value: str) -> Path:
    p = Path((value or "").strip())
    if not p:
        return p
    if p.is_absolute():
        return p
    name = p.name.lower()
    if name.startswith("recipients") and name.endswith(".csv"):
        return _resolve_shard_path(p)
    if name.endswith("_log.csv") or name.endswith("domain_log.csv"):
        return _resolve_log_path(p)
    p = base / p
    return p


def load_account_map(map_path: Path) -> List[Tuple[Path, Path]]:
    if not map_path.exists():
        return []
    out: List[Tuple[Path, Path]] = []
    with map_path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items() if k}
            rec = row.get("recipientscsv") or row.get("recipients") or row.get("recipients_csv")
            log = row.get("logcsv") or row.get("log") or row.get("log_csv")
            if not rec or not log:
                continue
            out.append((resolve_map_path(map_path.parent, rec), resolve_map_path(map_path.parent, log)))
    return out


def dedupe_scope_for_runtime(provider: str, current_csv: Path) -> str:
    name = current_csv.name.lower()
    if str(provider or "").strip().lower() == "sendgrid":
        return "sendgrid"
    if name in {"recipients_private_jc.csv", "recipients_private_jc_warm.csv"}:
        return "astra"
    return "global"


def _path_matches_dedupe_scope(path: Path, scope: str, kind: str) -> bool:
    name = path.name.lower()
    if scope == "sendgrid":
        if kind == "recipient":
            return name.startswith("recipients_sendgrid_")
        return name.startswith("sendgrid_")
    if scope == "astra":
        if kind == "recipient":
            return name in {"recipients_private_jc.csv", "recipients_private_jc_warm.csv"}
        return name in {"private_jc_log.csv", "private_jc_warm_log.csv"}
    return True


def filter_account_map_entries_for_runtime_dedupe(
    map_entries: Sequence[Tuple[Path, Path]],
    provider: str,
    current_csv: Path,
) -> List[Tuple[Path, Path]]:
    scope = dedupe_scope_for_runtime(provider, current_csv)
    if scope == "global":
        return list(map_entries)
    out: List[Tuple[Path, Path]] = []
    for recipient_path, log_path in map_entries:
        if not _path_matches_dedupe_scope(recipient_path, scope, "recipient"):
            continue
        if not _path_matches_dedupe_scope(log_path, scope, "log"):
            continue
        out.append((recipient_path, log_path))
    return out


def load_done_from_logs(paths: List[Path]) -> Set[str]:
    out: Set[str] = set()
    for p in paths:
        out |= load_already_done(p)
    return out


def fmt_ts(dt: Optional[datetime]) -> str:
    if not dt:
        return "n/a"
    manila = dt + timedelta(hours=8)
    return f"{dt.isoformat()}Z | Manila: {manila.strftime('%Y-%m-%d %H:%M:%S')}"


def remaining_str(resume_dt: Optional[datetime]) -> str:
    if not resume_dt:
        return "n/a"
    now = datetime.now(timezone.utc)
    sec = int((resume_dt - now).total_seconds())
    if sec <= 0:
        return "now"
    h, rem = divmod(sec, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m}m"


def rolling_24h_stats(log_path: Path, my_domains: Set[str], now: datetime) -> Dict[str, object]:
    cutoff = now - timedelta(hours=24)
    sent_times: List[datetime] = []
    ext_last: Dict[str, datetime] = {}

    if not log_path.exists():
        return {
            "messages": 0,
            "unique_external": 0,
            "unique_external_set": set(),
            "resume_messages": None,
            "resume_unique_external": None,
        }

    with log_path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("Status") or "").strip().upper() != "SENT":
                continue
            t = parse_ts(r.get("TimestampUTC") or "")
            if not t or t < cutoff:
                continue
            sent_times.append(t)
            email_addr = norm_email(r.get("Email") or "")
            if is_external(email_addr, my_domains):
                prev = ext_last.get(email_addr)
                if prev is None or t > prev:
                    ext_last[email_addr] = t

    sent_times.sort()
    resume_messages = (sent_times[0] + timedelta(hours=24)) if sent_times else None
    resume_unique_external = (min(ext_last.values()) + timedelta(hours=24)) if ext_last else None

    return {
        "messages": len(sent_times),
        "unique_external": len(ext_last),
        "unique_external_set": set(ext_last.keys()),
        "resume_messages": resume_messages,
        "resume_unique_external": resume_unique_external,
    }


def log_row(sent_log: Path, email: str, status: str, info: str = "") -> None:
    new_file = not sent_log.exists()
    sent_log.parent.mkdir(parents=True, exist_ok=True)
    with sent_log.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
        if new_file:
            w.writeheader()
        w.writerow({
            "TimestampUTC": datetime.now(timezone.utc).isoformat(),
            "Email": email,
            "Status": status,
            "Info": (info or "")[:300],
        })


def campaign_log_info(info: str = "", campaign_type: str = CAMPAIGN_TYPE_COLD) -> str:
    normalized = normalize_campaign_type(campaign_type)
    prefix = f"campaign_type={normalized}"
    text = str(info or "").strip()
    if not text:
        return prefix
    if "campaign_type=" in text:
        return text
    return f"{prefix} {text}"


MESSAGE_PREVIEW_FIELDS = [
    "CampaignType",
    "Email",
    "AuthorEmail",
    "AuthorName",
    "FirstName",
    "BookTitle",
    "PersonalizedOpeningLine",
    "Subject",
    "Body",
]


def message_preview_path(profile: str) -> Path:
    safe_profile = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(profile or "sender").strip() or "sender")
    return settings.APP_ROOT / "data" / "message_previews" / f"{safe_profile}_message_preview.csv"


def write_message_preview_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MESSAGE_PREVIEW_FIELDS)
        writer.writeheader()


def append_message_preview_row(path: Path, row: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MESSAGE_PREVIEW_FIELDS, extrasaction="ignore")
        writer.writerow({field: row.get(field, "") for field in MESSAGE_PREVIEW_FIELDS})


def worker_log_path(sent_log: Path) -> Path:
    return sent_log.with_name(f"{sent_log.stem}_worker.jsonl")


def log_worker_event(
    event_log: Path,
    *,
    profile: str,
    event_type: str,
    reason: str,
    pid: int,
    **fields: object,
) -> None:
    event_log.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, object] = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "profile": str(profile or "").strip(),
        "event_type": str(event_type or "").strip().upper(),
        "reason": str(reason or "").strip()[:500],
        "pid": int(pid),
    }
    for key, value in fields.items():
        if value is None:
            continue
        payload[str(key)] = value
    line = json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n"
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def rewrite_csv_rows(csv_path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8",
        dir=csv_path.parent,
        prefix=f".{csv_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(csv_path)


def prune_sent_from_csv(csv_path: Path, sent_emails: Set[str]) -> int:
    if not sent_emails or not csv_path.exists():
        return 0
    removed = 0
    with lock_files([csv_path]):
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ["Email", "FirstName", "BookTitle"]
            kept_rows = []
            for row in reader:
                clean_row = {k: v for k, v in row.items() if k is not None}
                email_addr = norm_email(clean_row.get("Email") or "")
                if email_addr and email_addr in sent_emails:
                    removed += 1
                    continue
                kept_rows.append(clean_row)
        if removed:
            rewrite_csv_rows(csv_path, fieldnames, kept_rows)
    return removed


def count_prunable_rows(csv_path: Path, sent_emails: Set[str]) -> int:
    if not sent_emails or not csv_path.exists():
        return 0
    removed = 0
    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email_addr = norm_email((row or {}).get("Email") or "")
            if email_addr and email_addr in sent_emails:
                removed += 1
    return removed


def should_skip_sendgrid_prune_on_startup(args: argparse.Namespace) -> bool:
    return bool(
        SENDGRID_SKIP_PRUNE_ON_STARTUP
        and not bool(getattr(args, "preflight", False))
        and str(getattr(args, "provider", "") or "").strip().lower() == "sendgrid"
    )


def remove_email_from_csv(csv_path: Path, email_addr: str) -> bool:
    if not email_addr or not csv_path.exists():
        return False
    removed = 0
    with lock_files([csv_path]):
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ["Email", "FirstName", "BookTitle"]
            kept_rows = []
            target = norm_email(email_addr)
            for row in reader:
                clean_row = {k: v for k, v in row.items() if k is not None}
                email_val = norm_email(clean_row.get("Email") or "")
                if email_val and email_val == target:
                    removed += 1
                    continue
                kept_rows.append(clean_row)
        if removed:
            rewrite_csv_rows(csv_path, fieldnames, kept_rows)
    return removed > 0


def text_to_html(body_text: str, unsub_mailto: str, cid: Optional[str]) -> str:
    """
    HTML version:
    - converts {UnsubMailto} into a clickable link
    - replaces {SIGIMG} with an inline CID image IF cid is provided
    - removes {SIGIMG} if cid is not provided
    """
    safe = html.escape(body_text)

    # clickable unsubscribe
    if "<%asm_group_unsubscribe_url%" in unsub_mailto:
        unsub_href = unsub_mailto
        unsub_text = unsub_mailto
    else:
        unsub_href = html.escape(unsub_mailto)
        unsub_text = "unsubscribe"
    safe = safe.replace(html.escape(unsub_mailto), f"<a href='{unsub_href}'>{unsub_text}</a>")
    # keep ASM token unescaped if present
    safe = safe.replace("&lt;%asm_group_unsubscribe_url%&gt;", "<%asm_group_unsubscribe_url%>")

    # signature marker replacement
    if cid:
        sig_tag = (
            f"<img src='cid:{cid}' alt='Signature' "
            "style='max-width:320px;height:auto;display:block;margin-top:10px;'>"
        )
        safe = safe.replace("{SIGIMG}", sig_tag)
    else:
        safe = safe.replace("{SIGIMG}", "")

    safe = safe.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<html><body><p>{safe}</p></body></html>"


def render_message_parts(
    author: str,
    book_title: str,
    subject: str,
    body_template: str,
    unsub_email: str,
    signature_file: Optional[Path],
    merge_fields: Optional[Dict[str, str]] = None,
    subject_fallback: str = "",
    body_fallback: str = "",
) -> Tuple[str, str, str, Optional[str]]:
    unsub_mailto = make_unsub_mailto(unsub_email)
    if re.search(r"{{?\s*Title\s*}}?", subject or "") or re.search(r"{{?\s*Title\s*}}?", body_template or ""):
        raise ValueError("Email template contains blocked unresolved placeholder.")
    author = (author or GENERIC_SALUTATION).strip()
    first_name = author.split()[0] if author else GENERIC_SALUTATION
    raw_book_title, _book_title_normalization_notes = normalize_render_field_value(book_title or "")

    format_args = {
        "FirstName": first_name,
        "AuthorName": "",
        "AuthorEmail": "",
        "BookTitle": raw_book_title,
        "PersonalizedOpeningLine": "",
        "UnsubEmail": unsub_email,
        "UnsubMailto": unsub_mailto,
        "SIGIMG": "{SIGIMG}",   # keep marker for HTML rendering
        "AstraPhysicalMailingAddress": ASTRA_PHYSICAL_MAILING_ADDRESS,
    }
    if merge_fields:
        for key in ("FirstName", "AuthorName", "AuthorEmail", "BookTitle", "PersonalizedOpeningLine"):
            if key in merge_fields:
                format_args[key] = str(merge_fields.get(key) or "")
        for key in ("FirstName", "AuthorName", "PersonalizedOpeningLine"):
            normalized_value, _notes = normalize_render_field_value(format_args.get(key) or "")
            format_args[key] = normalized_value
        format_args["FirstName"] = format_args["FirstName"] or GENERIC_SALUTATION
        raw_book_title, _book_title_normalization_notes = normalize_render_field_value(format_args.get("BookTitle") or "")
        format_args["BookTitle"] = raw_book_title

    missing_or_unsafe_book_title = invalid_campaign_book_title(
        raw_book_title,
        author_name=str(format_args.get("AuthorName") or ""),
        first_name=str(format_args.get("FirstName") or ""),
    )
    if not missing_or_unsafe_book_title:
        for opening in (BOOK_TITLE_GENERIC_OPENING, BOOK_TITLE_MISSING_FALLBACK_OPENING):
            body_template = body_template.replace(opening, SENDGRID_BOOK_TITLE_OPENING)
    if missing_or_unsafe_book_title:
        format_args["BookTitle"] = ""
        if str(body_fallback or "").strip():
            body_template = str(body_fallback or "").strip()
        elif str(body_template or "").strip() == PITCH_1_5_BODY.strip():
            body_template = PITCH_1_5_GENERIC_BODY
        else:
            for opening in BOOK_TITLE_FALLBACK_OPENINGS:
                body_template = body_template.replace(opening, BOOK_TITLE_MISSING_FALLBACK_OPENING)
    body_text = body_template.format(**format_args)
    subject_args = dict(format_args)
    subject_args["SIGIMG"] = ""
    if subject_fallback and "{BookTitle}" in subject and missing_or_unsafe_book_title:
        subject_text = subject_fallback
    else:
        subject_text = subject.format(**subject_args)
    if BLOCKED_RENDER_PLACEHOLDER_RE.search(subject_text) or BLOCKED_RENDER_PLACEHOLDER_RE.search(body_text):
        raise ValueError("Rendered email contains unresolved placeholder.")

    cid = SIGNATURE_CID if (signature_file and signature_file.exists()) else None
    html_body = text_to_html(body_text, unsub_mailto, cid=cid)
    return subject_text, body_text, html_body, cid


def build_message(
    from_email: str,
    to_email: str,
    author: str,
    book_title: str,
    subject: str,
    body_template: str,
    unsub_email: str,
    signature_file: Optional[Path] = None,
    merge_fields: Optional[Dict[str, str]] = None,
    subject_fallback: str = "",
    body_fallback: str = "",
) -> Tuple[EmailMessage, str, str, str, Optional[str]]:
    subject_text, body_text, html_body, cid = render_message_parts(
        author,
        book_title,
        subject,
        body_template,
        unsub_email,
        signature_file,
        merge_fields=merge_fields,
        subject_fallback=subject_fallback,
        body_fallback=body_fallback,
    )

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject_text
    msg["Reply-To"] = from_email
    msg["List-Unsubscribe"] = f"<mailto:{unsub_email}?subject=unsubscribe>"

    # Plain text: remove marker so recipients don't see "{SIGIMG}"
    msg.set_content(body_text.replace("{SIGIMG}", "").strip())

    msg.add_alternative(html_body, subtype="html")

    # Attach inline signature only if pitch contains {SIGIMG} AND signature_file exists
    if cid and signature_file and signature_file.exists() and "{SIGIMG}" in body_text:
        img_bytes = signature_file.read_bytes()
        msg.get_payload()[-1].add_related(
            img_bytes,
            maintype="image",
            subtype="png",
            cid=f"<{cid}>",
            filename=signature_file.name,
            disposition="inline",
        )

    return msg, subject_text, body_text, html_body, cid


WARM_QUEUE_REQUIRED_HEADERS = {
    "AuthorName",
    "AuthorEmail",
    "BookTitleOrProject",
    "EmailSubject",
    "EmailBody",
    "NeedSignal",
    "RecommendedService",
    "OutreachAngle",
    "SourceURL",
    "ContactPath",
    "ResearchStatus",
}

WARM_CONFIRMATION_PROTECTED_FIELDS = (
    "Email",
    "AuthorEmail",
    "FirstName",
    "AuthorName",
    "BookTitleOrProject",
    "EmailSubject",
    "EmailBody",
    "NeedSignal",
    "RecommendedService",
    "OutreachAngle",
    "SourceURL",
    "ContactPath",
    "ResearchStatus",
    "campaign_type",
    "campaign_id",
)


def normalized_warm_confirmation_payload(row: Dict[str, str]) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for field in WARM_CONFIRMATION_PROTECTED_FIELDS:
        value = str(row.get(field) or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if field in {"Email", "AuthorEmail"}:
            value = norm_email(value)
        payload[field] = value
    return payload


def warm_confirmation_payload_hash(payload_or_row: Dict[str, str]) -> str:
    payload = normalized_warm_confirmation_payload(payload_or_row)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _masked_warm_email(value: str) -> str:
    email = norm_email(value)
    if "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def validate_warm_confirmed_queue(
    rows: Sequence[Dict[str, str]],
    manifest: Dict[str, object],
) -> Dict[str, object]:
    if not bool(manifest.get("confirmed")):
        return {"valid": False, "reason": "warm_confirmation_required", "message": "Warm Private JC requires explicit confirmation."}
    approved_rows = manifest.get("approved_rows")
    if not isinstance(approved_rows, dict) or not approved_rows:
        return {
            "valid": False,
            "reason": "warm_confirmation_manifest_upgrade_required",
            "message": "Warm confirmation metadata is missing per-row payload hashes. Re-confirm the reviewed warm preview.",
        }

    seen: Set[str] = set()
    required_values = {"Email", "AuthorEmail", "FirstName", "EmailSubject", "EmailBody", "campaign_type", "campaign_id"}
    for row in rows:
        payload = normalized_warm_confirmation_payload(row)
        email = payload["Email"] or payload["AuthorEmail"]
        for field in WARM_CONFIRMATION_PROTECTED_FIELDS:
            if field not in row:
                return {
                    "valid": False,
                    "reason": "warm_queue_missing_required_field",
                    "message": f"Warm queue row is missing required field {field}.",
                    "email": _masked_warm_email(email),
                    "field": field,
                }
        for field in required_values:
            if not payload[field]:
                return {
                    "valid": False,
                    "reason": "warm_queue_missing_required_field",
                    "message": f"Warm queue row is missing required field {field}.",
                    "email": _masked_warm_email(email),
                    "field": field,
                }
        if email in seen:
            return {
                "valid": False,
                "reason": "warm_queue_duplicate_email",
                "message": "Warm queue contains a duplicate confirmed recipient.",
                "email": _masked_warm_email(email),
            }
        seen.add(email)
        approved = approved_rows.get(email)
        if not isinstance(approved, dict):
            return {
                "valid": False,
                "reason": "warm_queue_unconfirmed_email",
                "message": "Warm queue contains a recipient outside the confirmed preview.",
                "email": _masked_warm_email(email),
            }
        approved_payload = approved.get("payload")
        approved_hash = str(approved.get("payload_sha256") or "")
        if not isinstance(approved_payload, dict) or not approved_hash:
            return {
                "valid": False,
                "reason": "warm_confirmation_manifest_upgrade_required",
                "message": "Warm confirmation metadata is missing a protected row payload. Re-confirm the reviewed warm preview.",
                "email": _masked_warm_email(email),
            }
        expected_payload = normalized_warm_confirmation_payload(approved_payload)
        for field in WARM_CONFIRMATION_PROTECTED_FIELDS:
            if payload[field] != expected_payload[field]:
                return {
                    "valid": False,
                    "reason": "warm_queue_payload_mismatch",
                    "message": f"Warm queue payload no longer matches confirmed field {field}.",
                    "email": _masked_warm_email(email),
                    "field": field,
                }
        actual_hash = warm_confirmation_payload_hash(payload)
        if actual_hash != approved_hash or warm_confirmation_payload_hash(expected_payload) != approved_hash:
            return {
                "valid": False,
                "reason": "warm_queue_payload_mismatch",
                "message": "Warm queue payload hash no longer matches confirmation.",
                "email": _masked_warm_email(email),
                "field": "payload_sha256",
            }
    return {"valid": True, "reason": "", "message": "Warm confirmed queue payload is valid.", "remaining": len(rows)}


def load_warm_confirmation_manifest(path: Optional[Path] = None) -> Dict[str, object]:
    manifest_path = Path(path) if path is not None else STATE_DIR / "warm_private_jc_confirmation.json"
    if not manifest_path.exists():
        return {}
    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def validate_warm_queue_contract(csv_path: Path, rows: Sequence[Dict[str, str]]) -> bool:
    fieldnames = set(rows[0].keys()) if rows else set()
    if not rows:
        print(f"ERROR: warm queue is empty: {csv_path}")
        return False
    missing = sorted(WARM_QUEUE_REQUIRED_HEADERS - fieldnames)
    if missing:
        print("ERROR: warm queue is missing required columns: " + ", ".join(missing))
        return False
    for index, row in enumerate(rows, start=1):
        email = resolve_recipient_email(row)
        subject_text = str(row.get("EmailSubject") or "").strip()
        body_text = str(row.get("EmailBody") or "").strip()
        contact_path = str(row.get("ContactPath") or "").strip().lower()
        if not email or email not in contact_path:
            print(f"ERROR: warm queue row {index} is not a direct-email row.")
            return False
        if not subject_text or not body_text:
            print(f"ERROR: warm queue row {index} is missing previewed subject/body.")
            return False
        if UNRESOLVED_PLACEHOLDER_RE.search(subject_text) or UNRESOLVED_PLACEHOLDER_RE.search(body_text):
            print(f"ERROR: warm queue row {index} contains unresolved placeholders.")
            return False
    return True


def build_pre_rendered_message(
    from_email: str,
    to_email: str,
    row: Dict[str, str],
    unsub_email: str,
) -> Tuple[EmailMessage, str, str, str, Optional[str]]:
    subject_text = str(row.get("EmailSubject") or "").strip()
    body_text = str(row.get("EmailBody") or "").strip()
    if not subject_text or not body_text:
        raise ValueError("Warm queue row is missing previewed EmailSubject or EmailBody.")
    if UNRESOLVED_PLACEHOLDER_RE.search(subject_text) or UNRESOLVED_PLACEHOLDER_RE.search(body_text):
        raise ValueError("Warm queue row contains an unresolved recipient placeholder.")
    unsub_mailto = make_unsub_mailto(unsub_email)
    html_body = text_to_html(body_text, unsub_mailto, cid=None)
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject_text
    msg["Reply-To"] = from_email
    msg["List-Unsubscribe"] = f"<mailto:{unsub_email}?subject=unsubscribe>"
    msg.set_content(body_text)
    msg.add_alternative(html_body, subtype="html")
    return msg, subject_text, body_text, html_body, None


def append_sendgrid_unsubscribe_footer(
    text_content: str,
    html_content: str,
    unsub_email: str,
) -> Tuple[str, str]:
    label = "Unsubscribe from this list"
    href = SENDGRID_ASM_GROUP_UNSUB_RAW_URL
    if not href:
        return text_content, html_content

    if label.lower() not in text_content.lower():
        text_content = (text_content.rstrip() + f"\n\nP.S. {label}: {href}").strip()

    if label.lower() not in html_content.lower():
        footer_html = f'<br><br><a href="{href}">{html.escape(label)}</a>'
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{footer_html}</body>", 1)
        elif "</html>" in html_content:
            html_content = html_content.replace("</html>", f"{footer_html}</html>", 1)
        else:
            html_content = f"{html_content}{footer_html}"

    return text_content, html_content


def send_via_sendgrid(
    api_key: str,
    from_email: str,
    to_email: str,
    reply_to: str,
    subject_text: str,
    body_text: str,
    html_body: str,
    unsub_email: str,
    signature_file: Optional[Path],
    cid: Optional[str],
    unsubscribe_group_id: int,
    groups_to_display: List[int],
    custom_args: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    try:
        import importlib
        sg = importlib.import_module("sendgrid")
        SendGridAPIClient = getattr(sg, "SendGridAPIClient")
        helpers_mail = importlib.import_module("sendgrid.helpers.mail")
        Mail = getattr(helpers_mail, "Mail")
        Content = getattr(helpers_mail, "Content")
        ReplyTo = getattr(helpers_mail, "ReplyTo")
        Attachment = getattr(helpers_mail, "Attachment")
        FileContent = getattr(helpers_mail, "FileContent")
        FileName = getattr(helpers_mail, "FileName")
        FileType = getattr(helpers_mail, "FileType")
        Disposition = getattr(helpers_mail, "Disposition")
        ContentId = getattr(helpers_mail, "ContentId")
        Header = getattr(helpers_mail, "Header")
        Asm = getattr(helpers_mail, "Asm")
        CustomArg = getattr(helpers_mail, "CustomArg")
    except Exception as exc:
        raise RuntimeError(
            "sendgrid library not installed; add 'sendgrid' to requirements and install it"
        ) from exc

    asm_enabled = int(unsubscribe_group_id or 0) > 0

    text_content = body_text.replace("{SIGIMG}", "").strip()
    html_content = html_body
    text_content, html_content = append_sendgrid_unsubscribe_footer(text_content, html_content, unsub_email)

    mail = Mail(from_email=from_email, to_emails=to_email, subject=subject_text)
    mail.add_content(Content("text/plain", text_content))
    mail.add_content(Content("text/html", html_content))
    mail.reply_to = ReplyTo(reply_to)
    mail.add_header(Header("List-Unsubscribe", build_sendgrid_list_unsubscribe_header(unsub_email)))
    mail.add_header(Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"))
    if asm_enabled:
        groups_list = [int(x) for x in (groups_to_display or [unsubscribe_group_id]) if int(x) > 0]
        if not groups_list:
            groups_list = [int(unsubscribe_group_id)]
        mail.asm = Asm(group_id=int(unsubscribe_group_id), groups_to_display=groups_list)
    for key, value in (custom_args or {}).items():
        k = str(key or "").strip()
        v = str(value or "").strip()
        if k and v:
            mail.add_custom_arg(CustomArg(k, v))

    if cid and signature_file and signature_file.exists() and "{SIGIMG}" in body_text:
        img_bytes = signature_file.read_bytes()
        encoded = base64.b64encode(img_bytes).decode("ascii")
        mail.add_attachment(
            Attachment(
                FileContent(encoded),
                FileName(signature_file.name),
                FileType("image/png"),
                Disposition("inline"),
                ContentId(cid),
            )
        )

    try:
        response = SendGridAPIClient(api_key).send(mail)
    except Exception as exc:
        # Surface SendGrid API error payload (when present) to avoid opaque 401s.
        body = getattr(exc, "body", None)
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8", errors="replace")
        detail = str(exc)
        if body:
            detail = f"{detail} body={body}"
        raise RuntimeError(f"sendgrid_error: {detail}") from exc
    if response.status_code != 202:
        body = response.body
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        raise RuntimeError(f"sendgrid_error: status={response.status_code} body={body}")
    headers = getattr(response, "headers", {}) or {}
    message_id = (
        headers.get("X-Message-Id")
        or headers.get("x-message-id")
        or headers.get("X-Message-id")
        or ""
    )
    return {
        "status_code": str(response.status_code),
        "message_id": str(message_id or "").strip(),
    }

# ===== SMTP session =====
def smtp_login(host: str, port: int, user: str, pw: str) -> smtplib.SMTP:
    s = smtplib.SMTP(host, port, timeout=30)
    s.ehlo()
    s.starttls(context=ssl.create_default_context())
    s.ehlo()
    s.login(user, pw)
    return s


def smtp_close(s: Optional[smtplib.SMTP]) -> None:
    if not s:
        return
    try:
        s.quit()
    except Exception:
        try:
            s.close()
        except Exception:
            pass


# ===== Error classification =====
def _decode_smtp_err(x) -> str:
    if isinstance(x, (bytes, bytearray)):
        return x.decode(errors="ignore")
    return str(x)


def classify_smtp(code: Optional[int], text: str) -> str:
    t = (text or "").lower()

    if ("5.4.5" in t) or ("daily user sending limit exceeded" in t) or ("too many unique external" in t) or ("has exceeded the gmail sending limit" in t):
        return "HARD_LIMIT"

    if code is not None and 400 <= int(code) <= 499:
        return "TEMP_THROTTLE"
    if ("rate" in t and "limit" in t) or ("try again later" in t) or ("temporarily" in t and "limit" in t):
        return "TEMP_THROTTLE"

    if ("5.1.1" in t) or ("user unknown" in t) or ("no such user" in t) or ("recipient address rejected" in t and "unknown" in t):
        return "BAD_RECIPIENT"

    return "OTHER"


def extract_code_text_from_exception(e: Exception) -> Tuple[Optional[int], str]:
    code = getattr(e, "smtp_code", None)
    raw = getattr(e, "smtp_error", "")
    text = _decode_smtp_err(raw)
    try:
        if code is not None:
            code = int(code)
    except Exception:
        code = None
    return code, text


def is_temporary_auth_failure(code: Optional[int], text: str) -> bool:
    smtp_text = (text or "").lower()
    if code == 454:
        return True
    if "4.7.0" in smtp_text and "auth" in smtp_text:
        return True
    if "temporary authentication failure" in smtp_text:
        return True
    if "connection lost to authentication server" in smtp_text:
        return True
    return False


def is_sendgrid_forbidden(code: Optional[int], text: str) -> bool:
    if code == 403:
        return True
    t = (text or "").lower()
    if "status=403" in t:
        return True
    if "http error 403" in t:
        return True
    if "403" in t and "forbidden" in t:
        return True
    return False


def classify_sendgrid_runtime_error(text: str) -> str:
    t = (text or "").lower()
    if (
        "http error 401" in t
        or "unauthorized" in t
        or "maximum credits exceeded" in t
        or "regional attribute" in t
        or "api key" in t and "invalid" in t
        or "from address does not match a verified sender identity" in t
        or '"field":"from"' in t
    ):
        return "ACCOUNT_STOP"
    if "status=429" in t or "http error 429" in t or "rate limit" in t:
        return "TEMP_THROTTLE"
    if "status=403" in t or "http error 403" in t:
        return "FORBIDDEN"
    return "OTHER"


# ===== Rolling 1h guard (PrivateEmail shared bucket) =====
def _parse_ts_safe(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((ts or "").strip().replace("Z", "+00:00"))
    except Exception:
        return None


def _domain_log_fieldnames() -> List[str]:
    return ["TimestampUTC", "Email", "Status", "Info"]


def _write_domain_log_rows(handle, rows: List[Dict[str, str]]) -> None:
    handle.seek(0)
    writer = csv.DictWriter(handle, fieldnames=_domain_log_fieldnames())
    writer.writeheader()
    writer.writerows(rows)
    handle.truncate()
    handle.flush()
    os.fsync(handle.fileno())


def _domain_attempt_info(reservation_token: str, outcome: str, info: str = "") -> str:
    details = f"token={reservation_token} outcome={outcome}".strip()
    extra = (info or "").strip()
    if extra:
        details = f"{details} {extra}".strip()
    return details[:300]


def domain_wait_for_slot(domain_log_path: Path, max_messages_1h: int, jitter_sec: int = 5) -> str:
    """
    Domain-wide rolling 60-min limiter using a file lock.
    Counts ATTEMPT rows in the last hour plus only active SLOT reservations.
    Legacy SENT rows are still counted during the transition away from SENT-based
    limiting so the rolling window stays conservative until old rows age out.
    """
    if max_messages_1h <= 0:
        return ""

    domain_log_path.parent.mkdir(parents=True, exist_ok=True)

    if not domain_log_path.exists():
        with domain_log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_domain_log_fieldnames())
            w.writeheader()

    reservation_token = uuid.uuid4().hex
    while True:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        slot_cutoff = now - timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS)

        with domain_log_path.open("r+", newline="", encoding="utf-8-sig") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            f.seek(0)
            rows = list(csv.DictReader(f))

            expiry_times: List[datetime] = []
            for r in rows:
                st = (r.get("Status") or "").strip().upper()
                if st not in ("ATTEMPT", "SENT", "SLOT"):
                    continue
                t = _parse_ts_safe(r.get("TimestampUTC") or "")
                if not t:
                    continue
                if st in {"ATTEMPT", "SENT"} and t >= cutoff:
                    expiry_times.append(t + timedelta(hours=1))
                    continue
                if st == "SLOT" and t >= slot_cutoff:
                    expiry_times.append(t + timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS))

            expiry_times.sort()
            used = len(expiry_times)

            if used < max_messages_1h:
                f.seek(0, os.SEEK_END)
                w = csv.DictWriter(f, fieldnames=_domain_log_fieldnames())
                w.writerow({
                    "TimestampUTC": now.isoformat(),
                    "Email": "",
                    "Status": "SLOT",
                    "Info": f"token={reservation_token}",
                })
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return reservation_token

            earliest = expiry_times[0] if expiry_times else (now + timedelta(seconds=30))
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        wait_s = max(1, int((earliest - datetime.now(timezone.utc)).total_seconds())) + random.randint(0, jitter_sec)
        time.sleep(wait_s)


def domain_finalize_attempt(domain_log_path: Path, reservation_token: str, email: str, outcome: str, info: str = "") -> None:
    if not reservation_token:
        return
    domain_log_path.parent.mkdir(parents=True, exist_ok=True)
    if not domain_log_path.exists():
        with domain_log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_domain_log_fieldnames())
            w.writeheader()

    with domain_log_path.open("r+", newline="", encoding="utf-8-sig") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        rows = list(csv.DictReader(handle))
        matched = False
        slot_marker = f"token={reservation_token}"
        for row in rows:
            status = (row.get("Status") or "").strip().upper()
            info_text = str(row.get("Info") or "")
            if status == "SLOT" and slot_marker in info_text:
                row["Email"] = email
                row["Status"] = "ATTEMPT"
                row["Info"] = _domain_attempt_info(reservation_token, outcome, info)
                matched = True
                break
        if not matched:
            rows.append(
                {
                    "TimestampUTC": datetime.now(timezone.utc).isoformat(),
                    "Email": email,
                    "Status": "ATTEMPT",
                    "Info": _domain_attempt_info(reservation_token, outcome, info),
                }
            )
        _write_domain_log_rows(handle, rows)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sleep_with_jitter(seconds: int, jitter: int = 10) -> None:
    time.sleep(max(1, int(seconds)) + random.randint(0, max(0, int(jitter))))


def humanized_cooldown_sleep_seconds(base_seconds: int, sent_total: int, human_state: Dict[str, int], args) -> int:
    base_seconds = max(1, int(base_seconds))
    jitter_minus = max(0, int(getattr(args, "human_jitter_minus", 2) or 0))
    jitter_plus = max(0, int(getattr(args, "human_jitter_plus", 2) or 0))
    sleep_s = max(1, base_seconds + random.randint(-jitter_minus, jitter_plus))

    next_break_at = int(human_state.get("next_break_at", 0))
    if sent_total > 0 and next_break_at > 0 and sent_total >= next_break_at:
        break_min = max(0, int(getattr(args, "human_break_seconds_min", 6) or 0))
        break_max = max(break_min, int(getattr(args, "human_break_seconds_max", 18) or break_min))
        extra_break = random.randint(break_min, break_max)
        sleep_s += extra_break

        every_min = max(1, int(getattr(args, "human_break_every_min", 120) or 120))
        every_max = max(every_min, int(getattr(args, "human_break_every_max", 240) or every_min))
        human_state["next_break_at"] = sent_total + random.randint(every_min, every_max)
        print(
            f"HUMAN: microbreak +{extra_break}s "
            f"(next around send #{human_state['next_break_at']})"
        )

    return sleep_s


def append_suppressed_email(suppress_csv_path: Path, email_addr: str) -> None:
    if not email_addr:
        return
    if not suppress_csv_path.exists():
        with suppress_csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Email"])
            w.writeheader()
            w.writerow({"Email": email_addr})
    else:
        with suppress_csv_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Email"])
            w.writerow({"Email": email_addr})


def main():
    profile_parser = argparse.ArgumentParser(add_help=False)
    profile_parser.add_argument("--profile", choices=sorted(PROFILES.keys()), help="Load a preset configuration.")
    profile_parser.add_argument("--list_profiles", action="store_true", help="List available profiles.")

    pre_args, _ = profile_parser.parse_known_args()
    if pre_args.list_profiles and not pre_args.profile:
        print("Profiles available:")
        for name in sorted(PROFILES.keys()):
            print(f" - {name}")
        return
    profile_defaults = PROFILES.get(pre_args.profile or "", {})

    ap = argparse.ArgumentParser(parents=[profile_parser])
    ap.add_argument("--csv")
    ap.add_argument("--log")
    ap.add_argument("--pitch", choices=sorted(PITCHES.keys()))
    ap.add_argument("--provider", choices=["private", "gmail", "sendgrid"], default="")
    ap.add_argument("--sendgrid", action="store_true", help="Use SendGrid Email API backend.")

    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--unsub", default=DEFAULT_UNSUB_EMAIL)
    ap.add_argument("--unsub_csv", default=str(DEFAULT_UNSUB_CSV))
    ap.add_argument("--suppress_csv", default=str(DEFAULT_SUPPRESS_CSV))
    ap.add_argument(
        "--sendgrid_suppression_csv",
        default=str(DEFAULT_SENDGRID_SUPPRESSION_CSV),
        help="SendGrid activity-driven suppression CSV (provider=sendgrid only).",
    )
    ap.add_argument("--my_domains", default=DEFAULT_DOMAIN)
    ap.add_argument("--always_send", default="")

    ap.add_argument("--max_unique_external_24h", type=int, default=None)
    ap.add_argument("--max_messages_24h", type=int, default=None)

    ap.add_argument("--max_per_run", type=int, default=0)
    ap.add_argument("--repeat", action="store_true")
    ap.add_argument("--batch_size", type=int, default=10)
    ap.add_argument("--cooldown_seconds", type=int, default=0)
    ap.add_argument("--max_total", type=int, default=0)
    ap.add_argument("--stop_at_local", default="", help="Stop automatically at local time HH:MM (24h).")
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--preview_messages", action="store_true", help="Render message preview CSV without sending.")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument(
        "--strict_book_title_required",
        action="store_true",
        help="Require every row to have a safe BookTitle even when the pitch has fallback rendering.",
    )
    ap.add_argument("--human_mode", action="store_true", help="Add light random pacing and rare microbreaks.")
    ap.add_argument("--no-human_mode", dest="human_mode", action="store_false", help="Disable human pacing.")
    ap.add_argument("--human_jitter_minus", type=int, default=2)
    ap.add_argument("--human_jitter_plus", type=int, default=2)
    ap.add_argument("--human_break_every_min", type=int, default=120)
    ap.add_argument("--human_break_every_max", type=int, default=240)
    ap.add_argument("--human_break_seconds_min", type=int, default=6)
    ap.add_argument("--human_break_seconds_max", type=int, default=18)
    ap.add_argument("--block_role_recipients", dest="block_role_recipients", action="store_true")
    ap.add_argument("--allow_role_recipients", dest="block_role_recipients", action="store_false")
    ap.add_argument(
        "--role_localparts",
        default=",".join(sorted(ROLE_LOCALPART_BLOCKLIST)),
        help="Comma-separated local parts to block (e.g. info,admin,support).",
    )
    ap.add_argument("--max_consecutive_errors", type=int, default=6)
    ap.add_argument("--max_throttle_errors", type=int, default=3)
    ap.add_argument(
        "--max_invalid_rate_1h",
        type=float,
        default=0.0,
        help="Hard-stop if INVALID ratio in rolling 1h exceeds this value (e.g. 0.05). 0 disables.",
    )
    ap.add_argument(
        "--invalid_rate_min_events",
        type=int,
        default=20,
        help="Minimum attempted outcomes in rolling 1h before invalid-rate stop is evaluated.",
    )
    ap.add_argument(
        "--require_valid_status",
        action="store_true",
        help="Only send rows whose status column matches --valid_status_values.",
    )
    ap.add_argument(
        "--status_col",
        default="status",
        help="CSV column name(s) for verification status (comma-separated).",
    )
    ap.add_argument(
        "--valid_status_values",
        default="valid,deliverable,ok",
        help="Allowed status values for --require_valid_status (comma-separated).",
    )
    ap.add_argument(
        "--block_risky_rows",
        action="store_true",
        help="Skip rows marked risky/catch-all using --risk_col and --blocked_risk_values.",
    )
    ap.add_argument(
        "--risk_col",
        default="risk",
        help="CSV column name(s) for risk flags (comma-separated).",
    )
    ap.add_argument(
        "--blocked_risk_values",
        default="risky,catch-all,catch_all,accept_all,unknown,invalid",
        help="Risk values to block when --block_risky_rows is enabled (comma-separated).",
    )

    ap.add_argument("--max_messages_1h", type=int, default=None)
    ap.add_argument("--domain_log", default="")
    ap.add_argument("--suppress_invalid", action="store_true")
    ap.add_argument("--from_email", "--from", dest="from_email", default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--password_env", default="")
    ap.add_argument("--daily_target", type=int, default=0)
    ap.add_argument("--unsubscribe_group_id", type=int, default=0)
    ap.add_argument("--groups_to_display", type=int, nargs="*", default=None)
    ap.add_argument("--campaign_type", default=CAMPAIGN_TYPE_COLD)
    ap.add_argument("--prune_sent", action="store_true", help="Remove already-sent emails from CSV before sending.")
    ap.add_argument("--no-prune_sent", dest="prune_sent", action="store_false", help="Disable prune of sent emails.")
    ap.add_argument("--account_map", default="account_map.csv")
    ap.add_argument("--global_dedupe", action="store_true")
    ap.add_argument("--global_dedupe_logs_pattern", default="*_log.csv")
    ap.add_argument("--global_dedupe_recipients_pattern", default="recipients_*.csv")
    ap.add_argument("--status", action="store_true", help="Show status for private/sendgrid profiles.")
    ap.add_argument("--status-sendgrid", action="store_true", help="Show status for sendgrid profiles only.")
    ap.add_argument(
        "--resync-sendgrid",
        action="store_true",
        help="Rebuild sendgrid_daily_counters.json from sendgrid logs for today.",
    )

    ap.set_defaults(
        block_role_recipients=True,
        allow_confirmed_warm_role_recipients=False,
    )
    if profile_defaults:
        ap.set_defaults(**profile_defaults)

    args = ap.parse_args()
    args.campaign_type = normalize_campaign_type(getattr(args, "campaign_type", CAMPAIGN_TYPE_COLD))
    no_send_mode = bool(getattr(args, "dry_run", False) or getattr(args, "preview_messages", False))
    if args.list_profiles:
        print("Profiles available:")
        for name, cfg in sorted(PROFILES.items()):
            print(f" - {name}")
            for k, v in sorted(cfg.items()):
                print(f"    {k}: {v}")
        return
    if args.profile and not args.status:
        print(f"PROFILE: {args.profile}")

    configured_interval_seconds = max(0, int(getattr(profile_defaults, "get", lambda *_: 0)("interval", 0) or getattr(args, "interval", 0) or 0))
    configured_cooldown_seconds = max(0, int(getattr(profile_defaults, "get", lambda *_: 0)("cooldown_seconds", 0) or getattr(args, "cooldown_seconds", 0) or 0))

    provider_guard = provider_pacing_status(
        str(args.profile or ""),
        str(args.provider or ""),
        int(getattr(args, "cooldown_seconds", 0) or 0),
    )
    if args.profile:
        recommended_cooldown_seconds = max(
            0,
            int(provider_guard.get("recommended_cooldown_seconds") or 0),
        )
        if recommended_cooldown_seconds > int(getattr(args, "cooldown_seconds", 0) or 0):
            args.cooldown_seconds = recommended_cooldown_seconds
            if str(args.provider or "").strip().lower() == "private":
                args.interval = max(int(getattr(args, "interval", 0) or 0), recommended_cooldown_seconds)
            pace_per_hour = max(1, round(3600 / recommended_cooldown_seconds))
            print(
                "PACE ADJUST: provider guard raised cooldown to "
                f"{recommended_cooldown_seconds}s (~{pace_per_hour}/h)"
            )

    if str(args.profile or "").strip() == "private_jc" and str(args.provider or "").strip().lower() == "private":
        resolved_private_spacing_seconds = max(
            0,
            int(getattr(args, "interval", 0) or 0),
            int(getattr(args, "cooldown_seconds", 0) or 0),
        )
        if resolved_private_spacing_seconds > 0:
            if int(getattr(args, "interval", 0) or 0) != resolved_private_spacing_seconds:
                print(
                    "PACE NORMALIZE: private_jc raised interval to "
                    f"{resolved_private_spacing_seconds}s to match the effective send spacing"
                )
            if bool(getattr(args, "repeat", False)) and int(getattr(args, "cooldown_seconds", 0) or 0) != resolved_private_spacing_seconds:
                print(
                    "PACE NORMALIZE: private_jc raised cooldown to "
                    f"{resolved_private_spacing_seconds}s to match the effective send spacing"
                )
            args.interval = resolved_private_spacing_seconds
            if bool(getattr(args, "repeat", False)):
                args.cooldown_seconds = resolved_private_spacing_seconds

    if args.resync_sendgrid:
        candidates: Dict[str, Dict[str, object]] = {}
        if args.profile:
            cfg = PROFILES.get(args.profile)
            if not cfg:
                print(f"ERROR: unknown profile {args.profile}")
                return
            provider = str(cfg.get("provider") or "")
            if provider != "sendgrid":
                print("RESYNC: only available for sendgrid profiles.")
                return
            candidates[args.profile] = cfg
        else:
            for name, cfg in sorted(PROFILES.items()):
                provider = str(cfg.get("provider") or "")
                if provider == "sendgrid":
                    candidates[name] = cfg

        counters = load_sendgrid_counters(SENDGRID_COUNTERS_PATH)
        today = datetime.now().astimezone().strftime("%Y-%m-%d")
        updated = 0
        global_sent_today = 0
        global_last_success: Optional[datetime] = None
        for name, cfg in candidates.items():
            log_path = _resolve_log_path(cfg.get("log") or "")
            sent_today = count_sent_today_from_log(log_path)
            _, _, last_success = load_log_statuses(log_path)
            from_email = norm_email(str(cfg.get("from_email") or ""))
            counter_key = from_email or name
            entry = counters.get(counter_key, {})
            if not entry and name in counters:
                entry = counters.get(name, {})
            entry["date"] = today
            entry["sent"] = int(sent_today)
            entry["last_success"] = last_success.astimezone().isoformat() if last_success else ""
            counters[counter_key] = entry
            global_sent_today += int(sent_today)
            if last_success and (global_last_success is None or last_success > global_last_success):
                global_last_success = last_success
            updated += 1
        counters[SENDGRID_GLOBAL_COUNTER_KEY] = {
            "date": today,
            "sent": int(global_sent_today),
            "last_success": global_last_success.astimezone().isoformat() if global_last_success else "",
        }
        save_sendgrid_counters(SENDGRID_COUNTERS_PATH, counters)
        print(f"RESYNC: updated {updated} sendgrid account(s).")
        if not (args.status or args.status_sendgrid):
            return

    if args.status or args.status_sendgrid:
        candidates: Dict[str, Dict[str, object]] = {}
        if args.profile:
            cfg = PROFILES.get(args.profile)
            if not cfg:
                print(f"ERROR: unknown profile {args.profile}")
                return
            provider = str(cfg.get("provider") or "")
            if provider not in ("private", "sendgrid"):
                print("STATUS: only available for providers private/sendgrid.")
                return
            if args.status_sendgrid and provider != "sendgrid":
                print("STATUS: --status-sendgrid requires a sendgrid profile.")
                return
            candidates[args.profile] = cfg
        else:
            for name, cfg in sorted(PROFILES.items()):
                provider = str(cfg.get("provider") or "")
                if args.status_sendgrid:
                    if provider == "sendgrid":
                        candidates[name] = cfg
                elif provider in ("private", "sendgrid"):
                    candidates[name] = cfg

        counters = load_sendgrid_counters(SENDGRID_COUNTERS_PATH)
        global_sendgrid_sent_today, _ = get_sendgrid_sent_today(counters, SENDGRID_GLOBAL_COUNTER_KEY)
        cap_enabled = SENDGRID_DAILY_CAP > 0
        global_sendgrid_remaining = max(0, SENDGRID_DAILY_CAP - global_sendgrid_sent_today) if cap_enabled else -1
        total_sendgrid_accounts = 0
        for name, cfg in candidates.items():
            provider = str(cfg.get("provider") or "")
            if args.status_sendgrid and provider == "sendgrid":
                from_email = norm_email(str(cfg.get("from_email") or ""))
                counter_key = from_email or name
                if counter_key not in counters and name in counters:
                    counter_key = name
                account_sent_today, _ = get_sendgrid_sent_today(counters, counter_key)
                status_label = "OK" if (not cap_enabled or global_sendgrid_sent_today < SENDGRID_DAILY_CAP) else "NOT"
                cap_display = str(SENDGRID_DAILY_CAP) if cap_enabled else "off"
                remaining_display = str(global_sendgrid_remaining) if cap_enabled else "off"
                total_sendgrid_accounts += 1
                print(
                    f"{name}: sent_today={account_sent_today} global_sent_today={global_sendgrid_sent_today} "
                    f"global_remaining_today={remaining_display} cap={cap_display} status={status_label}"
                )
                continue
            csv_path = _resolve_shard_path(cfg.get("csv") or "")
            log_path = _resolve_log_path(cfg.get("log") or "")

            recipients = load_emails_from_csv(csv_path) if csv_path.exists() else set()
            sent_set, failed_set, last_success = load_log_statuses(log_path)
            failed_only = failed_set - sent_set

            total_recipients = len(recipients)
            sent_total = len(sent_set)
            failed_total = len(failed_only)
            pending_total = max(0, total_recipients - sent_total)

            last_success_str = "n/a"
            if last_success:
                last_success_str = last_success.astimezone().isoformat()

            sent_today = 0
            daily_cap = "n/a"
            remaining_today = "n/a"
            if provider == "sendgrid":
                from_email = norm_email(str(cfg.get("from_email") or ""))
                counter_key = from_email or name
                if counter_key not in counters and name in counters:
                    counter_key = name
                sent_today, _ = get_sendgrid_sent_today(counters, counter_key)
                daily_cap = str(SENDGRID_DAILY_CAP) if cap_enabled else "off"
                remaining_today = str(global_sendgrid_remaining) if cap_enabled else "off"
            elif provider == "private":
                sent_today = count_sent_today_from_log(log_path)

            print(f"PROFILE: {name}")
            print(f"  provider={provider} csv={csv_path.name} log={log_path.name}")
            print(
                "  total_recipients={total} sent_success_total={sent} failed_total={failed} pending_total={pending}"
                .format(total=total_recipients, sent=sent_total, failed=failed_total, pending=pending_total)
            )
            print(
                "  sent_success_today={sent_today} daily_cap={daily_cap} remaining_today={remaining_today}"
                .format(sent_today=sent_today, daily_cap=daily_cap, remaining_today=remaining_today)
            )
            print(f"  last_success_timestamp={last_success_str}")
        if args.status_sendgrid and not args.profile and total_sendgrid_accounts:
            cap_display = str(SENDGRID_DAILY_CAP) if cap_enabled else "off"
            remaining_display = str(global_sendgrid_remaining) if cap_enabled else "off"
            print(
                "TOTAL: sent_today={sent} remaining_today={remaining} cap={cap}".format(
                    sent=global_sendgrid_sent_today,
                    remaining=remaining_display,
                    cap=cap_display,
                )
            )
        return

    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    if args.sendgrid:
        if args.provider and args.provider != "sendgrid":
            print("ERROR: --sendgrid cannot be combined with --provider that is not sendgrid.")
            return
        args.provider = "sendgrid"
    if not args.provider and sendgrid_api_key:
        args.provider = "sendgrid"

    required_missing = [name for name, val in [
        ("provider", args.provider),
        ("csv", args.csv),
        ("log", args.log),
        ("pitch", args.pitch),
    ] if not val]
    if required_missing:
        print("ERROR missing required args:", ", ".join(required_missing))
        print("Provide them via flags or set a --profile that includes them.")
        return

    if args.provider == "sendgrid" and not no_send_mode and not sendgrid_api_key:
        print("ERROR: SENDGRID_API_KEY is required for --provider sendgrid.")
        return

    provider_defaults = PROVIDER_LIMIT_DEFAULTS.get(args.provider, {})
    if args.provider in ("private", "sendgrid") and args.max_messages_1h is None:
        args.max_messages_1h = int(provider_defaults.get("max_messages_1h", 0))
    if args.provider == "gmail":
        if args.max_messages_24h is None:
            args.max_messages_24h = int(provider_defaults.get("max_messages_24h", 0))
        if args.max_unique_external_24h is None:
            args.max_unique_external_24h = int(provider_defaults.get("max_unique_external_24h", 0))

    host, port = SMTP_PRESETS.get(args.provider, ("sendgrid", "api"))
    pitch = PITCHES[args.pitch]
    subject = (pitch.get("subject") or "").strip()
    subject_fallback = (pitch.get("subject_fallback") or "").strip()
    body_template = (pitch.get("body") or "").strip()
    body_fallback = (pitch.get("body_fallback") or "").strip()

    csv_path = _resolve_shard_path(args.csv)
    log_path = _resolve_log_path(args.log)
    unsub_csv_path = _resolve_state_path(args.unsub_csv)
    suppress_csv_path = _resolve_state_path(args.suppress_csv)
    sendgrid_suppression_csv_path = _resolve_state_path(args.sendgrid_suppression_csv)
    if args.profile and not managed_dashboard_queue_path_allowed(str(args.profile), csv_path):
        print(
            "ERROR: managed dashboard profiles must use data/shards queues; "
            f"refusing stale/root queue path {csv_path}"
        )
        return
    preview_messages_path = message_preview_path(str(args.profile or Path(str(args.csv or "sender")).stem))
    if args.preview_messages:
        write_message_preview_header(preview_messages_path)
    should_log_worker = bool(args.profile) and not any(
        (
            bool(args.list_profiles),
            bool(args.preflight),
            bool(args.status),
            bool(args.status_sendgrid),
            bool(args.resync_sendgrid),
        )
    )
    worker_event_log_path = worker_log_path(log_path) if should_log_worker else None
    worker_pid = os.getpid()
    worker_started_monotonic = time.monotonic()
    last_heartbeat_monotonic = 0.0
    last_recipient_for_audit = ""
    runtime_lock_context = None

    def emit_worker_event(event_type: str, reason: str, **fields: object) -> None:
        if not worker_event_log_path:
            return
        log_worker_event(
            worker_event_log_path,
            profile=str(args.profile or ""),
            event_type=event_type,
            reason=reason,
            pid=worker_pid,
            csv_path=csv_path.name,
            recipient_log=log_path.name,
            **fields,
        )

    def audit_worker(
        status: str,
        *,
        sent: int = 0,
        errors: int = 0,
        last_recipient: str = "",
        action: str = "",
        pending_count: Optional[int] = None,
        terminal: bool = False,
        force: bool = False,
    ) -> None:
        nonlocal last_heartbeat_monotonic
        now_mono = time.monotonic()
        if not force and not terminal and now_mono - last_heartbeat_monotonic < 30:
            return
        last_heartbeat_monotonic = now_mono
        try:
            runtime_audit.update_worker_heartbeat(
                profile=str(args.profile or ""),
                status=status,
                app_started_monotonic=worker_started_monotonic,
                sent_this_run=sent,
                errors_this_run=errors,
                last_recipient=last_recipient,
                last_action=action or status,
                queue_file=csv_path.name,
                pending_count=pending_count,
                terminal=terminal,
            )
        except Exception:
            pass

    def request_stop(signum, _frame) -> None:
        audit_worker(
            "interrupted",
            sent=0,
            errors=0,
            last_recipient=last_recipient_for_audit,
            action=f"signal_{int(signum)}",
            terminal=False,
            force=True,
        )
        raise KeyboardInterrupt

    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    if should_log_worker:
        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)

    if not csv_path.exists():
        emit_worker_event("ERROR", "missing_csv", missing_path=str(csv_path))
        print("ERROR missing:", csv_path)
        return

    my_domains: Set[str] = {d.strip().lower() for d in (args.my_domains or "").split(",") if d.strip()}
    if not my_domains:
        my_domains = {DEFAULT_DOMAIN}

    rows = read_rows(csv_path)
    pre_rendered_message = bool(pitch.get("pre_rendered_message"))
    warm_confirmation_manifest: Dict[str, object] = {}
    if pre_rendered_message:
        if str(args.profile or "").strip() == "private_jc_warm":
            warm_confirmation_manifest = load_warm_confirmation_manifest()
            warm_integrity = validate_warm_confirmed_queue(rows, warm_confirmation_manifest)
            if not bool(warm_integrity.get("valid")):
                reason = str(warm_integrity.get("reason") or "warm_queue_payload_mismatch")
                message = str(warm_integrity.get("message") or "Warm confirmed queue integrity validation failed.")
                emit_worker_event(
                    "ERROR",
                    reason,
                    csv_path=str(csv_path),
                    field=str(warm_integrity.get("field") or ""),
                )
                print(f"ERROR: {reason}: {message}")
                return
        if not validate_warm_queue_contract(csv_path, rows):
            emit_worker_event("ERROR", "invalid_warm_queue", csv_path=str(csv_path))
            return
    elif not validate_book_title_queue_contract(
        csv_path=csv_path,
        rows=rows,
        subject=subject,
        body_template=body_template,
        profile_name=str(args.profile or ""),
        subject_fallback=subject_fallback,
        body_fallback=body_fallback,
        strict_book_title_required=bool(getattr(args, "strict_book_title_required", False) or pitch.get("require_book_title")),
    ):
        emit_worker_event("ERROR", "invalid_booktitle_queue", csv_path=str(csv_path))
        return
    already_done = load_already_done(log_path)
    unsubbed = load_emails_from_csv(unsub_csv_path)
    suppressed = load_emails_from_csv(suppress_csv_path)
    always_send_set = parse_email_list(getattr(args, "always_send", ""))
    sendgrid_suppressed_active: Set[str] = set()
    sendgrid_bad_event_emails: Set[str] = set()
    sendgrid_suppressed_perm = 0
    sendgrid_suppressed_temp_active = 0
    if args.provider in {"private", "sendgrid"}:
        sendgrid_suppressed_active, sendgrid_suppression_summary = load_active_suppressed_emails(
            sendgrid_suppression_csv_path
        )
        sendgrid_bad_event_emails = load_bad_sendgrid_event_emails(settings.WEBHOOK_EVENTS_PATH)
        sendgrid_suppressed_perm = int(sendgrid_suppression_summary.get("total_perm", 0) or 0)
        sendgrid_suppressed_temp_active = int(
            sendgrid_suppression_summary.get("total_temp_active", 0) or 0
        )
    role_block_set = parse_token_list(getattr(args, "role_localparts", ""))
    status_cols = parse_name_list(getattr(args, "status_col", "status"))
    risk_cols = parse_name_list(getattr(args, "risk_col", "risk"))
    valid_status_values = {canonical_token(x) for x in parse_token_list(getattr(args, "valid_status_values", ""))}
    blocked_risk_values = {canonical_token(x) for x in parse_token_list(getattr(args, "blocked_risk_values", ""))}
    row_keys: Set[str] = set()
    for row in rows:
        for k in row.keys():
            row_keys.add((k or "").strip().lower())
    if args.require_valid_status and status_cols and not any(c in row_keys for c in status_cols):
        print(
            "ERROR: --require_valid_status enabled but none of --status_col found in CSV header: "
            + ",".join(status_cols)
        )
        return
    if args.block_risky_rows and risk_cols and not any(c in row_keys for c in risk_cols):
        print(
            "ERROR: --block_risky_rows enabled but none of --risk_col found in CSV header: "
            + ",".join(risk_cols)
        )
        return

    global_done: Set[str] = set()
    other_recipients: Set[str] = set()
    dedupe_scope = dedupe_scope_for_runtime(args.provider, csv_path)
    if args.global_dedupe:
        map_entries = load_account_map(_resolve_app_path(args.account_map))
        map_entries = filter_account_map_entries_for_runtime_dedupe(map_entries, args.provider, csv_path)
        if map_entries:
            log_paths = [log_p for _, log_p in map_entries]
            recipient_paths = [rec_p for rec_p, _ in map_entries]
        else:
            base_dir = csv_path.parent
            log_paths = sorted(base_dir.glob(args.global_dedupe_logs_pattern))
            recipient_paths = sorted(base_dir.glob(args.global_dedupe_recipients_pattern))
            log_paths = [p for p in log_paths if _path_matches_dedupe_scope(p, dedupe_scope, "log")]
            recipient_paths = [p for p in recipient_paths if _path_matches_dedupe_scope(p, dedupe_scope, "recipient")]

        global_done = load_done_from_logs(log_paths)

        current_csv = csv_path.resolve()
        for p in recipient_paths:
            if p.resolve() == current_csv:
                continue
            other_recipients |= load_emails_from_csv(p)

    if args.prune_sent and not is_recontact_cold_campaign(args.campaign_type):
        sent_for_prune = set(already_done)
        if args.global_dedupe:
            sent_for_prune |= global_done
        sent_for_prune -= always_send_set
        if args.preflight or args.preview_messages or should_skip_sendgrid_prune_on_startup(args):
            prune_fn = count_prunable_rows
        else:
            prune_fn = prune_sent_from_csv
        removed = prune_fn(csv_path, sent_for_prune)
        if removed:
            if args.preview_messages:
                print(f"PRUNE: would remove {removed} from {csv_path.name} (preview only)")
            elif args.preflight:
                print(f"PRUNE: would remove {removed} from {csv_path.name} (preflight only)")
            elif should_skip_sendgrid_prune_on_startup(args):
                print(f"PRUNE: startup would remove {removed} from {csv_path.name} (guard active)")
            else:
                print(f"PRUNE: removed {removed} from {csv_path.name}")
                rows = read_rows(csv_path)

    def build_pending_snapshot(
        current_rows: Optional[List[Dict[str, str]]] = None,
        *,
        emit_suppressed_logs: bool,
        allow_missing_always_send_rows: bool = True,
        exclude_logged_always_send: bool = False,
    ) -> tuple[List[Dict[str, str]], Dict[str, int], int, int]:
        candidate_rows = list(current_rows) if current_rows is not None else read_rows(csv_path)
        current_already_done = load_already_done(log_path)
        current_unsubbed = load_emails_from_csv(unsub_csv_path)
        current_suppressed = load_emails_from_csv(suppress_csv_path)
        current_sendgrid_suppressed_active: Set[str] = set(sendgrid_suppressed_active)
        current_sendgrid_bad_event_emails: Set[str] = set(sendgrid_bad_event_emails)
        if args.provider in {"private", "sendgrid"}:
            current_sendgrid_suppressed_active, _ = load_active_suppressed_emails(
                sendgrid_suppression_csv_path
            )

        snapshot_pending: List[Dict[str, str]] = []
        snapshot_seen_in_input: Set[str] = set()
        snapshot_stats = {
            "skipped_dupes": 0,
            "skipped_global_logs": 0,
            "skipped_global_recipients": 0,
            "skipped_role_recipients": 0,
            "skipped_unverified": 0,
            "skipped_risky_rows": 0,
            "skipped_sendgrid_suppressed": 0,
            "skipped_bad_events": 0,
        }

        for row in candidate_rows:
            email_addr = resolve_recipient_email(row)
            if not email_addr:
                continue
            if email_addr in snapshot_seen_in_input:
                snapshot_stats["skipped_dupes"] += 1
                continue
            snapshot_seen_in_input.add(email_addr)
            if args.provider in {"private", "sendgrid"} and email_addr in current_sendgrid_suppressed_active:
                snapshot_stats["skipped_sendgrid_suppressed"] += 1
                if emit_suppressed_logs:
                    log_row(log_path, email_addr, "SKIP", campaign_log_info("skip_reason=suppressed", get_row_value_ci(row, ["campaign_type", "CampaignType"]) or args.campaign_type))
                continue
            if args.provider in {"private", "sendgrid"} and email_addr in current_sendgrid_bad_event_emails:
                snapshot_stats["skipped_bad_events"] += 1
                if emit_suppressed_logs:
                    log_row(log_path, email_addr, "SKIP", campaign_log_info("skip_reason=bad_sendgrid_event", get_row_value_ci(row, ["campaign_type", "CampaignType"]) or args.campaign_type))
                continue
            if email_addr in current_unsubbed or email_addr in current_suppressed:
                continue
            is_always_send = email_addr in always_send_set
            row_campaign_type = normalize_campaign_type(get_row_value_ci(row, ["campaign_type", "CampaignType", "campaign type"]) or args.campaign_type)
            is_recontact_row = is_recontact_cold_campaign(row_campaign_type)
            if exclude_logged_always_send and is_always_send and email_addr in current_already_done:
                continue
            if not is_always_send:
                if should_block_role_recipient_for_runtime(
                    email_addr,
                    role_block_set,
                    profile_name=str(args.profile or ""),
                    queue_path=csv_path,
                    block_role_recipients=bool(args.block_role_recipients),
                    allow_confirmed_warm_role_recipients=bool(
                        getattr(args, "allow_confirmed_warm_role_recipients", False)
                    ),
                ):
                    snapshot_stats["skipped_role_recipients"] += 1
                    continue
            if args.require_valid_status and not is_always_send:
                status_val = get_row_value_ci(row, status_cols)
                status_tokens = split_canonical_tokens(status_val)
                if not status_tokens or not (status_tokens & valid_status_values):
                    snapshot_stats["skipped_unverified"] += 1
                    continue
            if args.block_risky_rows and not is_always_send:
                risk_val = get_row_value_ci(row, risk_cols)
                risk_tokens = split_canonical_tokens(risk_val)
                if risk_tokens & blocked_risk_values:
                    snapshot_stats["skipped_risky_rows"] += 1
                    continue
            if not is_always_send and not is_recontact_row:
                if email_addr in current_already_done:
                    continue
                if args.global_dedupe and email_addr in global_done:
                    snapshot_stats["skipped_global_logs"] += 1
                    continue
                if args.global_dedupe and email_addr in other_recipients:
                    snapshot_stats["skipped_global_recipients"] += 1
                    continue
            snapshot_pending.append(row)
        eligible_pending_count = len(snapshot_pending)
        snapshot_pending = prioritize_always_send_rows(
            snapshot_pending,
            always_send_set,
            allow_missing_rows=allow_missing_always_send_rows,
        )
        return snapshot_pending, snapshot_stats, len(candidate_rows), eligible_pending_count

    pending, pending_stats, source_row_count, eligible_pending_count = build_pending_snapshot(
        rows,
        emit_suppressed_logs=True,
    )
    skipped_dupes = pending_stats["skipped_dupes"]
    skipped_global_logs = pending_stats["skipped_global_logs"]
    skipped_global_recipients = pending_stats["skipped_global_recipients"]
    skipped_role_recipients = pending_stats["skipped_role_recipients"]
    skipped_unverified = pending_stats["skipped_unverified"]
    skipped_risky_rows = pending_stats["skipped_risky_rows"]
    skipped_sendgrid_suppressed = pending_stats["skipped_sendgrid_suppressed"]

    print(f"RUN: provider={args.provider} host={host}:{port} pitch={args.pitch}")
    print(f"FILES: csv={csv_path.name} log={log_path.name} pending={len(pending)} interval={args.interval}s")
    if args.global_dedupe:
        print(
            "CHANNEL DEDUPE:"
            f" scope={dedupe_scope} |"
            f" logs={len(global_done)} | other_recipients={len(other_recipients)} |"
            f" skipped_logs={skipped_global_logs} | skipped_recipients={skipped_global_recipients}"
        )
    if args.block_role_recipients:
        print(f"ROLE FILTER: blocked={skipped_role_recipients} (list_size={len(role_block_set)})")
    if args.require_valid_status:
        print(
            "VERIFIED FILTER:"
            f" skipped={skipped_unverified} status_col={','.join(status_cols)}"
            f" allow={','.join(sorted(valid_status_values))}"
        )
    if args.block_risky_rows:
        print(
            "RISK FILTER:"
            f" skipped={skipped_risky_rows} risk_col={','.join(risk_cols)}"
            f" blocked={','.join(sorted(blocked_risk_values))}"
        )
    if skipped_dupes:
        print(f"CSV DUPES: skipped={skipped_dupes}")
    if args.dry_run:
        print("DRY RUN: no emails will be sent.")
    if args.preview_messages:
        print("PREVIEW MESSAGES: no emails will be sent.")
    if eligible_pending_count == 0:
        if repeat_mode := bool(getattr(args, "repeat", False)):
            refreshed_pending, _, refreshed_row_count, refreshed_eligible_count = build_pending_snapshot(
                emit_suppressed_logs=False,
                allow_missing_always_send_rows=False,
                exclude_logged_always_send=True,
            )
            if refreshed_eligible_count > 0:
                pending = refreshed_pending
                source_row_count = refreshed_row_count
                eligible_pending_count = refreshed_eligible_count
                emit_worker_event(
                    "REFRESH",
                    "queue_refreshed_after_empty_start",
                    pending_count=len(pending),
                    source_rows=source_row_count,
                )
            else:
                emit_worker_event(
                    "DONE",
                    "queue_exhausted_no_eligible_rows",
                    pending_count=refreshed_eligible_count,
                    source_rows=refreshed_row_count,
                )
                print("Nothing to send.")
                return
        else:
            emit_worker_event(
                "DONE",
                "queue_exhausted_no_eligible_rows",
                pending_count=0,
                source_rows=source_row_count,
            )
            print("Nothing to send.")
            return

    domain_log_path = _resolve_log_path(args.domain_log) if args.domain_log else log_path
    authoritative_sent_paths = authoritative_send_log_paths(log_path, domain_log_path)
    if args.provider in ("private", "sendgrid") and args.max_messages_1h:
        print(
            f"{args.provider.upper()} 1H CAP: {args.max_messages_1h} "
            f"(domain_log={domain_log_path.name})"
        )
    if args.provider == "gmail" and (args.max_messages_24h or args.max_unique_external_24h):
        print(
            "GMAIL LIMITS:"
            f" max_messages_24h={args.max_messages_24h or 'off'}"
            f" max_unique_external_24h={args.max_unique_external_24h or 'off'}"
        )
    if args.provider in ("private", "sendgrid"):
        print(
            "CIRCUIT BREAKER:"
            f" max_consecutive_errors={max(0, int(args.max_consecutive_errors or 0)) or 'off'}"
            f" max_throttle_errors={max(0, int(args.max_throttle_errors or 0)) or 'off'}"
        )
        invalid_rate_cfg = float(getattr(args, "max_invalid_rate_1h", 0) or 0.0)
        if invalid_rate_cfg > 0:
            print(
                "INVALID RATE GUARD:"
                f" threshold={invalid_rate_cfg:.2%}"
                f" min_events={max(1, int(getattr(args, 'invalid_rate_min_events', 20) or 20))}"
            )
    if args.provider in {"private", "sendgrid"}:
        print(
            "SENDGRID SUPPRESSIONS:"
            f" file={sendgrid_suppression_csv_path.name}"
            f" suppressed_loaded: total_perm={sendgrid_suppressed_perm}"
            f" total_temp_active={sendgrid_suppressed_temp_active}"
            f" skipped={skipped_sendgrid_suppressed}"
        )
    if str(args.profile or "").strip() == "private_jc":
        preflight_effective_spacing_seconds = (
            max(0, int(getattr(args, "cooldown_seconds", 0) or 0))
            if bool(getattr(args, "repeat", False)) and int(getattr(args, "cooldown_seconds", 0) or 0) > 0
            else max(0, int(getattr(args, "interval", 0) or 0))
        )
        if preflight_effective_spacing_seconds > 0:
            preflight_pace_per_hour = max(1, round(3600 / preflight_effective_spacing_seconds))
            print(
                "PACE RESOLVED: profile=private_jc"
                f" configured_interval={configured_interval_seconds}s"
                f" configured_cooldown={configured_cooldown_seconds}s"
                f" provider_recommended={max(0, int(provider_guard.get('recommended_cooldown_seconds') or 0))}s"
                f" effective_spacing={preflight_effective_spacing_seconds}s (~{preflight_pace_per_hour}/h)"
            )
    elif args.provider == "sendgrid":
        preflight_effective_spacing_seconds = (
            max(0, int(getattr(args, "cooldown_seconds", 0) or 0))
            if bool(getattr(args, "repeat", False)) and int(getattr(args, "cooldown_seconds", 0) or 0) > 0
            else max(0, int(getattr(args, "interval", 0) or 0))
        )
        if preflight_effective_spacing_seconds > 0:
            preflight_pace_per_hour = max(1, round(3600 / preflight_effective_spacing_seconds))
            print(
                f"PACE RESOLVED: profile={str(args.profile or 'sendgrid').strip()}"
                f" configured_interval={configured_interval_seconds}s"
                f" configured_cooldown={configured_cooldown_seconds}s"
                f" effective_spacing={preflight_effective_spacing_seconds}s (~{preflight_pace_per_hour}/h)"
            )

    gmail_messages_24h = 0
    gmail_unique_ext: Set[str] = set()
    gmail_resume_messages: Optional[datetime] = None
    gmail_resume_unique: Optional[datetime] = None
    if args.provider == "gmail" and (args.max_messages_24h or args.max_unique_external_24h):
        now = datetime.now(timezone.utc)
        stats = rolling_24h_stats(log_path, my_domains, now)
        gmail_messages_24h = int(stats["messages"])
        gmail_unique_ext = set(stats["unique_external_set"])
        gmail_resume_messages = stats["resume_messages"]
        gmail_resume_unique = stats["resume_unique_external"]
        print(f"GMAIL 24H: messages={gmail_messages_24h} unique_external={len(gmail_unique_ext)}")

        if args.max_messages_24h and gmail_messages_24h >= args.max_messages_24h:
            print(
                "STOP: max_messages_24h reached. "
                f"Resume: {fmt_ts(gmail_resume_messages)} | remaining: {remaining_str(gmail_resume_messages)}"
            )
            return
        if args.max_unique_external_24h and len(gmail_unique_ext) >= args.max_unique_external_24h:
            print(
                "STOP: max_unique_external_24h reached. "
                f"Resume: {fmt_ts(gmail_resume_unique)} | remaining: {remaining_str(gmail_resume_unique)}"
            )
            return

    if args.preflight:
        if args.provider in ("private", "sendgrid") and args.max_messages_1h:
            print(f"DOMAIN LOG: {domain_log_path.name} | cap_1h={args.max_messages_1h}")
        print("PREFLIGHT: ok (no sending).")
        return

    from_user = norm_email(args.from_email) or norm_email(input("From (email address you are logging in as): "))
    pw = ""
    if not no_send_mode and args.provider != "sendgrid":
        if args.password_env:
            pw = os.environ.get(args.password_env, "").strip()
        if not pw and args.password:
            pw = args.password.strip()
        if not pw:
            pw = getpass("Password (Gmail uses App Password): ").strip()
    unsub_email = norm_email(args.unsub) or from_user
    sendgrid_unsub_group_id = int(getattr(args, "unsubscribe_group_id", 0) or 0)
    raw_groups = getattr(args, "groups_to_display", None) or []
    sendgrid_groups_to_display = [int(x) for x in raw_groups if int(x) > 0]
    if sendgrid_unsub_group_id > 0 and not sendgrid_groups_to_display:
        sendgrid_groups_to_display = [sendgrid_unsub_group_id]
    sendgrid_run_id = ""
    if args.provider == "sendgrid":
        sendgrid_run_id = (
            f"{(args.profile or 'sendgrid').strip()}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{uuid.uuid4().hex[:10]}"
        )
    sendgrid_custom_args: Dict[str, str] = {}

    sendgrid_counters: Dict[str, Dict[str, object]] = {}
    sendgrid_counter_key = ""
    sendgrid_sent_today = 0
    sendgrid_account_sent_today = 0
    sendgrid_effective_cap = SENDGRID_DAILY_CAP
    # If the dashboard defines a per-profile send cap, prefer that as the
    # effective per-account daily cap so the sender honors the dashboard UI.
    try:
        dashboard_cap = 0
        if settings.DASHBOARD_RUN_SETTINGS_PATH.exists():
            try:
                raw = json.loads(settings.DASHBOARD_RUN_SETTINGS_PATH.read_text(encoding="utf-8"))
                dashboard_cap = int(raw.get("send_cap_per_profile") or 0)
            except Exception:
                dashboard_cap = 0
        if dashboard_cap and int(dashboard_cap) > int(sendgrid_effective_cap or 0):
            sendgrid_effective_cap = int(dashboard_cap)
        # Ensure per-run max_total won't stop the sender below the dashboard cap
        try:
            if dashboard_cap and (not getattr(args, "max_total", 0) or int(getattr(args, "max_total", 0) or 0) < int(dashboard_cap)):
                args.max_total = int(dashboard_cap)
        except Exception:
            pass
    except Exception:
        # best-effort: don't fail startup if reading dashboard settings fails
        pass
    sendgrid_cap_enabled = sendgrid_effective_cap > 0
    if args.provider == "sendgrid":
        sendgrid_counter_key = norm_email(from_user) or (args.profile or "")
        sendgrid_counters = load_sendgrid_counters(SENDGRID_COUNTERS_PATH)
        if args.profile and sendgrid_counter_key not in sendgrid_counters and args.profile in sendgrid_counters:
            sendgrid_counters[sendgrid_counter_key] = sendgrid_counters[args.profile]
            save_sendgrid_counters(SENDGRID_COUNTERS_PATH, sendgrid_counters)
        sendgrid_account_sent_today, _ = get_sendgrid_sent_today_live(SENDGRID_COUNTERS_PATH, sendgrid_counter_key)
        sendgrid_sent_today, _ = get_sendgrid_sent_today_live(
            SENDGRID_COUNTERS_PATH, SENDGRID_GLOBAL_COUNTER_KEY
        )
        # Enforce per-account daily cap (prefer per-account counter over global)
        if not no_send_mode and sendgrid_cap_enabled and sendgrid_account_sent_today >= sendgrid_effective_cap:
            log_row(
                log_path,
                "",
                "DAILY_CAP_REACHED",
                f"account_sent_today={sendgrid_account_sent_today} cap={sendgrid_effective_cap}",
            )
            print(
                f"STOP: DAILY_CAP_REACHED account_sent_today={sendgrid_account_sent_today} "
                f"global_sent_today={sendgrid_sent_today} cap={sendgrid_effective_cap}"
            )
            return

    try:
        stop_at_dt_local = parse_stop_at_local(args.stop_at_local)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return
    if stop_at_dt_local:
        print(
            "SCHEDULE STOP: "
            f"{stop_at_dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

    # Choose signature file:
    # - only applies if the pitch body contains {SIGIMG}
    pitch_key = args.pitch
    sig_name = (SIGNATURE_BY_PITCH.get(pitch_key) or SIGNATURE_BY_FROM.get(from_user) or "")
    sig_name = sig_name.strip()
    sig_path = _resolve_app_path(sig_name) if (sig_name and "{SIGIMG}" in body_template) else None

    smtp: Optional[smtplib.SMTP] = None
    sent_this_run = 0
    sent_this_run_emails: Set[str] = set()
    invalid_count = 0
    error_count = 0
    total_sent_attempted = 0
    consecutive_errors = 0
    consecutive_throttle_errors = 0
    # Observability: record most-recent OTHER-class sendgrid error per profile
    # and append simple CSV rows to this file for offline inspection.
    OBSERVABILITY_LOG_PATH = os.path.join(STATE_DIR, "sendgrid_other_observability.csv")
    recent_other_error: Dict[str, Dict[str, object]] = {}
    max_consecutive_errors = max(0, int(getattr(args, "max_consecutive_errors", 0) or 0))
    max_throttle_errors = max(0, int(getattr(args, "max_throttle_errors", 0) or 0))
    max_invalid_rate_1h = float(getattr(args, "max_invalid_rate_1h", 0) or 0.0)
    invalid_rate_min_events = max(1, int(getattr(args, "invalid_rate_min_events", 20) or 20))
    quality_events_1h: Deque[Tuple[datetime, bool]] = deque()
    repeat_mode = args.repeat
    cooldown_seconds = max(0, int(args.cooldown_seconds))
    batch_size = max(0, int(args.batch_size))
    human_mode_active = bool(getattr(args, "human_mode", False)) and args.provider == "private" and repeat_mode
    human_state: Dict[str, int] = {}
    provider_recovery_pending = bool(provider_guard.get("recovery_pending"))
    last_success_sent_at_utc: Optional[datetime] = None

    def audit_sleep(seconds: float, action: str = "SLEEP") -> None:
        remaining_sleep = max(0.0, float(seconds or 0))
        while remaining_sleep > 0:
            chunk = min(30.0, remaining_sleep)
            time.sleep(chunk)
            remaining_sleep -= chunk
            audit_worker(
                "running",
                sent=sent_this_run,
                errors=error_count,
                last_recipient=last_recipient_for_audit,
                action=action,
                pending_count=len(pending),
                force=True,
            )

    def audit_sleep_with_jitter(seconds: int, jitter: int = 10) -> None:
        audit_sleep(max(1, int(seconds)) + random.randint(0, max(0, int(jitter))), action="SLEEP")

    if human_mode_active:
        every_min = max(1, int(getattr(args, "human_break_every_min", 120) or 120))
        every_max = max(every_min, int(getattr(args, "human_break_every_max", 240) or every_min))
        human_state["next_break_at"] = random.randint(every_min, every_max)
        print(
            "HUMAN MODE: on "
            f"(jitter=-{int(getattr(args, 'human_jitter_minus', 2) or 0)}/+{int(getattr(args, 'human_jitter_plus', 2) or 0)}s, "
            f"microbreak={int(getattr(args, 'human_break_seconds_min', 6) or 0)}-{int(getattr(args, 'human_break_seconds_max', 18) or 0)}s "
            f"every {every_min}-{every_max} sends, first≈#{human_state['next_break_at']})"
        )
    if str(args.profile or "").strip() == "private_jc":
        effective_spacing_seconds = cooldown_seconds if repeat_mode and cooldown_seconds > 0 else max(0, int(getattr(args, "interval", 0) or 0))
        if effective_spacing_seconds > 0:
            pace_per_hour = max(1, round(3600 / effective_spacing_seconds))
            print(
                "PACE RESOLVED: profile=private_jc"
                f" configured_interval={configured_interval_seconds}s"
                f" configured_cooldown={configured_cooldown_seconds}s"
                f" provider_recommended={max(0, int(provider_guard.get('recommended_cooldown_seconds') or 0))}s"
                f" effective_spacing={effective_spacing_seconds}s (~{pace_per_hour}/h)"
            )
    elif args.provider == "sendgrid":
        effective_spacing_seconds = cooldown_seconds if repeat_mode and cooldown_seconds > 0 else max(0, int(getattr(args, "interval", 0) or 0))
        if effective_spacing_seconds > 0:
            pace_per_hour = max(1, round(3600 / effective_spacing_seconds))
            print(
                f"PACE RESOLVED: profile={str(args.profile or 'sendgrid').strip()}"
                f" configured_interval={configured_interval_seconds}s"
                f" configured_cooldown={configured_cooldown_seconds}s"
                f" effective_spacing={effective_spacing_seconds}s (~{pace_per_hour}/h)"
            )
    if repeat_mode and batch_size <= 0:
        print("ERROR: --batch_size must be > 0 when --repeat is set.")
        return

    def record_sendgrid_success() -> None:
        nonlocal sendgrid_sent_today, sendgrid_account_sent_today
        if args.provider != "sendgrid" or no_send_mode:
            return
        keys = [SENDGRID_GLOBAL_COUNTER_KEY]
        if sendgrid_counter_key:
            keys.append(sendgrid_counter_key)
        counts = increment_sendgrid_counters_live(SENDGRID_COUNTERS_PATH, keys)
        sendgrid_sent_today = _safe_int(counts.get(SENDGRID_GLOBAL_COUNTER_KEY))
        sendgrid_account_sent_today = _safe_int(
            counts.get(sendgrid_counter_key, sendgrid_account_sent_today)
        )

    def note_provider_recovery_started() -> None:
        nonlocal provider_recovery_pending
        if not provider_recovery_pending or not args.profile:
            return
        try:
            mark_recovery_started(str(args.profile))
        except Exception:
            pass
        provider_recovery_pending = False

    def reserve_domain_attempt_slot() -> str:
        if no_send_mode:
            return ""
        if args.provider not in ("private", "sendgrid") or not args.max_messages_1h:
            return ""
        return domain_wait_for_slot(domain_log_path, args.max_messages_1h)

    def finalize_domain_attempt_slot(reservation_token: str, email: str, outcome: str, info: str = "") -> None:
        if not reservation_token:
            return
        try:
            domain_finalize_attempt(domain_log_path, reservation_token, email, outcome, info)
        except Exception:
            pass

    def ensure_smtp() -> smtplib.SMTP:
        nonlocal smtp
        if smtp is None:
            smtp = smtp_login(host, port, from_user, pw)
        return smtp

    def send_one(
        msg: EmailMessage,
        to_email: str,
        subject_text: str,
        body_text: str,
        html_body: str,
        cid: Optional[str],
    ) -> Dict[str, str]:
        """
        PrivateEmail: connect per message (reduces DISCONNECTED loops)
        Gmail: keep connection open
        """
        nonlocal smtp
        if args.provider == "sendgrid":
            return send_via_sendgrid(
                sendgrid_api_key,
                from_user,
                to_email,
                from_user,
                subject_text,
                body_text,
                html_body,
                unsub_email,
                sig_path,
                cid,
                sendgrid_unsub_group_id,
                sendgrid_groups_to_display,
                sendgrid_custom_args,
            )
        result: Dict[str, str] = {}
        if args.provider == "private":
            smtp_close(smtp)
            smtp = None
            s = ensure_smtp()
            s.send_message(msg)
            smtp_close(s)
            smtp = None
        else:
            ensure_smtp().send_message(msg)
        return result

    def backoff_seconds() -> int:
        base = max(180, int(args.interval) * 4)
        return base + random.randint(0, 45)

    def note_error(is_throttle: bool = False) -> Optional[str]:
        nonlocal consecutive_errors, consecutive_throttle_errors
        consecutive_errors += 1
        if is_throttle:
            consecutive_throttle_errors += 1
        else:
            consecutive_throttle_errors = 0

        if max_throttle_errors > 0 and consecutive_throttle_errors >= max_throttle_errors:
            return "circuit_throttle"
        if max_consecutive_errors > 0 and consecutive_errors >= max_consecutive_errors:
            return "circuit_errors"
        return None

    def note_quality_event(is_invalid: bool) -> Optional[str]:
        if max_invalid_rate_1h <= 0:
            return None
        now = datetime.now(timezone.utc)
        quality_events_1h.append((now, bool(is_invalid)))
        cutoff = now - timedelta(hours=1)
        while quality_events_1h and quality_events_1h[0][0] < cutoff:
            quality_events_1h.popleft()
        attempts = len(quality_events_1h)
        if attempts < invalid_rate_min_events:
            return None
        invalids = sum(1 for _, bad in quality_events_1h if bad)
        rate = (invalids / attempts) if attempts else 0.0
        if rate > max_invalid_rate_1h:
            return (
                "invalid_rate_1h_exceeded "
                f"invalid={invalids}/{attempts} "
                f"rate={rate:.2%} "
                f"threshold={max_invalid_rate_1h:.2%}"
            )
        return None

    def stop_at_reached() -> bool:
        if not stop_at_dt_local:
            return False
        return datetime.now().astimezone() >= stop_at_dt_local

    emit_worker_event(
        "START",
        "worker_start",
        pending_count=len(pending),
        source_rows=source_row_count,
        skipped_sendgrid_suppressed=skipped_sendgrid_suppressed,
        repeat=bool(repeat_mode),
        batch_size=int(batch_size),
        max_total=int(args.max_total or 0),
    )
    stop_reason = ""
    try:
        if args.profile and not no_send_mode:
            runtime_lock_context = acquire_profile_runtime_lock(str(args.profile), enabled=True)
            runtime_lock_context.__enter__()
        runtime_audit.write_lifecycle_event(
            "WORKER_START",
            profile=str(args.profile or ""),
            queue_file=csv_path.name,
            starting_pending_count=len(pending),
        )
        audit_worker(
            "running",
            sent=0,
            errors=0,
            action="WORKER_START",
            pending_count=len(pending),
            force=True,
        )
        if not no_send_mode and args.provider == "gmail":
            ensure_smtp()

        pending_index = 0
        while True:
            if stop_at_reached():
                print("STOP: schedule_end reached (--stop_at_local).")
                break
            if repeat_mode:
                if args.max_total and sent_this_run >= args.max_total:
                    print(f"STOP: reached --max_total={args.max_total}")
                    break
                if args.max_per_run and sent_this_run >= args.max_per_run:
                    print(f"STOP: reached --max_per_run={args.max_per_run}")
                    break

                batch_limit = batch_size
                if args.max_per_run:
                    batch_limit = min(batch_limit, args.max_per_run)
                if args.max_total:
                    batch_limit = min(batch_limit, max(0, args.max_total - sent_this_run))
                if batch_limit <= 0:
                    break
            else:
                batch_limit = len(pending)

            batch_sent = 0
            stop_reason = ""
            next_index = pending_index

            for idx in range(pending_index, len(pending)):
                if stop_at_reached():
                    print("STOP: schedule_end reached (--stop_at_local).")
                    stop_reason = "schedule_end"
                    break
                i = idx + 1
                r = pending[idx]
                to_email = resolve_recipient_email(r)
                if not to_email:
                    next_index = idx + 1
                    continue
                if str(args.profile or "").strip() == "private_jc_warm":
                    current_warm_rows = read_rows(csv_path)
                    warm_integrity = validate_warm_confirmed_queue(current_warm_rows, warm_confirmation_manifest)
                    if not bool(warm_integrity.get("valid")):
                        reason = str(warm_integrity.get("reason") or "warm_queue_payload_mismatch")
                        message = str(warm_integrity.get("message") or "Warm confirmed queue integrity validation failed.")
                        emit_worker_event(
                            "ERROR",
                            reason,
                            csv_path=str(csv_path),
                            field=str(warm_integrity.get("field") or ""),
                        )
                        print(f"ERROR: {reason}: {message}")
                        stop_reason = reason
                        break
                row_campaign_type = normalize_campaign_type(get_row_value_ci(r, ["campaign_type", "CampaignType", "campaign type"]) or args.campaign_type)
                row_campaign_id = campaign_id_for_row(r, row_campaign_type)
                idempotency_reserved = False
                last_recipient_for_audit = to_email
                audit_worker(
                    "running",
                    sent=sent_this_run,
                    errors=error_count,
                    last_recipient=last_recipient_for_audit,
                    action="BEFORE_SEND",
                    pending_count=len(pending),
                )
                if args.provider in {"private", "sendgrid"} and to_email in sendgrid_bad_event_emails:
                    if not args.preview_messages:
                        log_row(log_path, to_email, "SKIP", campaign_log_info("event_type=SKIPPED_BAD_SENDGRID_EVENT", row_campaign_type))
                    next_index = idx + 1
                    continue

                if not is_recontact_cold_campaign(row_campaign_type) and email_logged_sent(log_path, to_email):
                    if not args.preview_messages:
                        log_row(log_path, to_email, "SKIP", campaign_log_info("event_type=SKIPPED_ALREADY_SENT", row_campaign_type))
                        runtime_audit.write_lifecycle_event(
                            "SKIPPED_ALREADY_SENT",
                            profile=str(args.profile or ""),
                            recipient=to_email,
                            queue_file=csv_path.name,
                            campaign_type=row_campaign_type,
                        )
                    next_index = idx + 1
                    continue

                if not no_send_mode and args.provider in {"private", "sendgrid"}:
                    if email_logged_authoritative_sent_any(authoritative_sent_paths, to_email):
                        log_row(
                            log_path,
                            to_email,
                            "SKIP",
                            campaign_log_info("event_type=SKIPPED_ALREADY_SENT_AUTHORITATIVE", row_campaign_type),
                        )
                        if to_email not in always_send_set:
                            remove_email_from_csv(csv_path, to_email)
                        next_index = idx + 1
                        continue
                    if not claim_queue_row(csv_path, to_email):
                        log_row(
                            log_path,
                            to_email,
                            "SKIP",
                            campaign_log_info("event_type=SKIPPED_QUEUE_ROW_ALREADY_CLAIMED", row_campaign_type),
                        )
                        next_index = idx + 1
                        continue
                    if email_logged_authoritative_sent_any(authoritative_sent_paths, to_email):
                        log_row(
                            log_path,
                            to_email,
                            "SKIP",
                            campaign_log_info("event_type=SKIPPED_ALREADY_SENT_AUTHORITATIVE_AFTER_CLAIM", row_campaign_type),
                        )
                        next_index = idx + 1
                        continue
                    reserved, reserve_reason = reserve_send_idempotency(
                        campaign_id=row_campaign_id,
                        provider=args.provider,
                        email=to_email,
                        profile=str(args.profile or ""),
                        queue_file=csv_path.name,
                    )
                    if not reserved:
                        log_row(
                            log_path,
                            to_email,
                            "SKIP",
                            campaign_log_info(f"event_type=SKIPPED_IDEMPOTENCY_DUPLICATE reason={reserve_reason}", row_campaign_type),
                        )
                        next_index = idx + 1
                        continue
                    idempotency_reserved = True

                if args.provider == "gmail" and (args.max_messages_24h or args.max_unique_external_24h):
                    if args.max_messages_24h and gmail_messages_24h >= args.max_messages_24h:
                        print(
                            "STOP: max_messages_24h reached. "
                            f"Resume: {fmt_ts(gmail_resume_messages)} | remaining: {remaining_str(gmail_resume_messages)}"
                        )
                        stop_reason = "max_messages_24h"
                        break
                    if (
                        args.max_unique_external_24h
                        and is_external(to_email, my_domains)
                        and to_email not in gmail_unique_ext
                        and len(gmail_unique_ext) >= args.max_unique_external_24h
                    ):
                        print(
                            "STOP: max_unique_external_24h reached. "
                            f"Resume: {fmt_ts(gmail_resume_unique)} | remaining: {remaining_str(gmail_resume_unique)}"
                        )
                        stop_reason = "max_unique_external_24h"
                        break

                if args.max_per_run and sent_this_run >= args.max_per_run:
                    print(f"STOP: reached --max_per_run={args.max_per_run}")
                    stop_reason = "max_per_run"
                    break

                if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                    print(f"STOP: reached --max_total={args.max_total}")
                    stop_reason = "max_total"
                    break

                if args.provider == "sendgrid":
                    sendgrid_sent_today, _ = get_sendgrid_sent_today_live(
                        SENDGRID_COUNTERS_PATH, SENDGRID_GLOBAL_COUNTER_KEY
                    )
                    sendgrid_account_sent_today, _ = get_sendgrid_sent_today_live(
                        SENDGRID_COUNTERS_PATH, sendgrid_counter_key
                    )
                    if not no_send_mode and sendgrid_cap_enabled and sendgrid_account_sent_today >= sendgrid_effective_cap:
                        if not no_send_mode:
                            log_row(
                                log_path,
                                "",
                                "DAILY_CAP_REACHED",
                                f"account_sent_today={sendgrid_account_sent_today} cap={sendgrid_effective_cap}",
                            )
                        print(
                            f"STOP: DAILY_CAP_REACHED account_sent_today={sendgrid_account_sent_today} "
                            f"global_sent_today={sendgrid_sent_today} cap={sendgrid_effective_cap}"
                        )
                        stop_reason = "daily_cap"
                        break

                raw_author = get_personalization_name(r)
                author = choose_salutation_name(raw_author, to_email)
                book_title = get_row_value_ci(r, ["BookTitle"])
                first_name = author.split()[0] if author else GENERIC_SALUTATION
                merge_fields = row_merge_fields(r, to_email, first_name, book_title)

                if pre_rendered_message:
                    msg, subject_text, body_text, html_body, cid = build_pre_rendered_message(
                        from_user,
                        to_email,
                        r,
                        unsub_email,
                    )
                else:
                    msg, subject_text, body_text, html_body, cid = build_message(
                        from_user, to_email, author, book_title,
                        subject, body_template, unsub_email,
                        signature_file=sig_path,
                        merge_fields=merge_fields,
                        subject_fallback=subject_fallback,
                        body_fallback=body_fallback,
                    )

                next_index = idx + 1
                attempt_slot_token = ""
                try:
                    total_sent_attempted += 1
                    if args.preview_messages:
                        append_message_preview_row(
                            preview_messages_path,
                            {
                                "Email": to_email,
                                "CampaignType": row_campaign_type,
                                "AuthorEmail": merge_fields.get("AuthorEmail", ""),
                                "AuthorName": merge_fields.get("AuthorName", ""),
                                "FirstName": merge_fields.get("FirstName", ""),
                                "BookTitle": merge_fields.get("BookTitle", ""),
                                "PersonalizedOpeningLine": merge_fields.get("PersonalizedOpeningLine", ""),
                                "Subject": subject_text,
                                "Body": body_text.replace("{SIGIMG}", "").strip(),
                            },
                        )
                        print(f"[{i}/{len(pending)}] PREVIEW {to_email}")
                        continue
                    elif args.dry_run:
                        log_row(log_path, to_email, "DRYRUN", campaign_log_info("not_sent", row_campaign_type))
                        print(f"[{i}/{len(pending)}] DRYRUN {to_email}")
                    else:
                        attempt_slot_token = reserve_domain_attempt_slot()
                        sendgrid_custom_args = (
                            build_sendgrid_astra_custom_args(
                                profile_name=str(args.profile or "").strip(),
                                run_id=sendgrid_run_id,
                                recipient_email=to_email,
                                queue_name=csv_path.name,
                                message_ordinal=next_index,
                                campaign_type=row_campaign_type,
                            )
                            if args.provider == "sendgrid"
                            else {}
                        )
                        send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                        send_info = ""
                        if args.provider == "sendgrid" and send_result.get("message_id"):
                            send_info = f"sg_message_id={send_result['message_id']}"
                        now_sent_utc = datetime.now(timezone.utc)
                        if str(args.profile or "").strip() == "private_jc":
                            if last_success_sent_at_utc is None:
                                print(f"SEND GAP: first_success_utc={now_sent_utc.isoformat()}")
                            else:
                                observed_gap_seconds = (now_sent_utc - last_success_sent_at_utc).total_seconds()
                                print(
                                    "SEND GAP:"
                                    f" previous_success_utc={last_success_sent_at_utc.isoformat()}"
                                    f" current_success_utc={now_sent_utc.isoformat()}"
                                    f" gap_seconds={observed_gap_seconds:.1f}"
                                )
                            last_success_sent_at_utc = now_sent_utc

                        log_row(log_path, to_email, "SENT", campaign_log_info(send_info, row_campaign_type))
                        if idempotency_reserved:
                            record_send_idempotency_outcome(
                                campaign_id=row_campaign_id,
                                provider=args.provider,
                                email=to_email,
                                outcome="sent",
                                info=send_info,
                            )
                        finalize_domain_attempt_slot(attempt_slot_token, to_email, "sent", send_info)
                        print(f"[{i}/{len(pending)}] SENT {to_email}")
                        sent_this_run += 1
                        sent_this_run_emails.add(to_email)
                        # Observability: if we recorded a recent OTHER-class error for this profile,
                        # record a resume row indicating whether sending resumed on the next successful attempt.
                        if args.provider == "sendgrid":
                            try:
                                profile = str(args.profile or "").strip()
                                entry = recent_other_error.get(profile)
                                if entry:
                                    resumed = False
                                    try:
                                        err_dt = datetime.fromisoformat(entry.get("ts"))
                                        delta = (now_sent_utc - err_dt).total_seconds()
                                        if delta is not None and 0 <= delta <= 120:
                                            resumed = True
                                    except Exception:
                                        # if parsing fails, leave resumed as False
                                        pass
                                    try:
                                        with open(OBSERVABILITY_LOG_PATH, "a", newline="") as _of:
                                            csv.writer(_of).writerow([now_sent_utc.isoformat(), profile, entry.get("classification"), entry.get("consec"), f"resumed:{str(resumed).lower()}"])
                                    except Exception:
                                        pass
                                    try:
                                        del recent_other_error[profile]
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        consecutive_errors = 0
                        consecutive_throttle_errors = 0
                        note_provider_recovery_started()
                        record_sendgrid_success()
                        quality_reason = note_quality_event(is_invalid=False)
                        if args.provider in ("sendgrid", "private"):
                            if to_email not in always_send_set and remove_email_from_csv(csv_path, to_email):
                                print(f"CSV: removed {to_email} from {csv_path.name}")
                        batch_sent += 1
                        if args.provider == "gmail":
                            gmail_messages_24h += 1
                            if is_external(to_email, my_domains):
                                gmail_unique_ext.add(to_email)

                        if quality_reason:
                            print(f"STOP: {quality_reason}")
                            stop_reason = "invalid_rate_1h"
                            break

                        if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                            print(f"STOP: reached --max_total={args.max_total}")
                            stop_reason = "max_total"

                except smtplib.SMTPRecipientsRefused as e:
                    rec = e.recipients.get(to_email) or next(iter(e.recipients.values()), None)
                    if rec:
                        code = rec[0]
                        text = _decode_smtp_err(rec[1])
                        cls = classify_smtp(int(code) if code is not None else None, text)

                        if cls == "BAD_RECIPIENT":
                            finalize_domain_attempt_slot(attempt_slot_token, to_email, "invalid", f"{code} {text}")
                            log_row(log_path, to_email, "INVALID", campaign_log_info(f"{code} {text}", row_campaign_type))
                            invalid_count += 1
                            print(f"[{i}/{len(pending)}] INVALID {to_email} :: {single_line(f'{code} {text}')}")
                            if args.suppress_invalid:
                                append_suppressed_email(suppress_csv_path, to_email)
                            quality_reason = note_quality_event(is_invalid=True)
                            if quality_reason:
                                print(f"STOP: {quality_reason}")
                                stop_reason = "invalid_rate_1h"
                                break
                            continue

                        finalize_domain_attempt_slot(attempt_slot_token, to_email, "recipient_error", f"{code} {text}")
                        log_row(log_path, to_email, "ERROR", campaign_log_info(f"{code} {text}", row_campaign_type))
                        error_count += 1
                        print(f"[{i}/{len(pending)}] RECIPIENT ERROR {to_email} :: {single_line(f'{code} {text}')}")
                        circuit_reason = note_error()
                        if circuit_reason:
                            print(f"STOP: {circuit_reason} after recipient errors")
                            stop_reason = circuit_reason
                            break
                        if args.provider == "private":
                            t = (f"{code} {text}").lower()
                            if "4.7.1" in t and "sending limit" in t:
                                throttle_count_after = max(1, int(provider_guard.get("recent_throttle_count_24h") or 0) + 1)
                                wait_seconds = throttle_pause_seconds(args.provider, throttle_count_after)
                                guard_status = record_provider_throttle(
                                    str(args.profile or ""),
                                    str(args.provider or ""),
                                    wait_seconds,
                                    cooldown_seconds,
                                    f"{code} {text}",
                                )
                                cooldown_until = str(guard_status.get("cooldown_until_utc") or "")
                                recommended = max(0, int(guard_status.get("recommended_cooldown_seconds") or cooldown_seconds))
                                print(
                                    "PAUSE: private throttle detected; provider cooldown until "
                                    f"{cooldown_until or '-'} with {recommended}s pacing on recovery"
                                )
                                print("STOP: provider_throttle_cooldown")
                                stop_reason = "provider_throttle_cooldown"
                            break
                        continue

                    finalize_domain_attempt_slot(attempt_slot_token, to_email, "recipient_error", str(e))
                    log_row(log_path, to_email, "ERROR", campaign_log_info(str(e), row_campaign_type))
                    error_count += 1
                    print(f"[{i}/{len(pending)}] RECIPIENT ERROR {to_email} :: {single_line(str(e))}")
                    circuit_reason = note_error()
                    if circuit_reason:
                        print(f"STOP: {circuit_reason} after recipient errors")
                        stop_reason = circuit_reason
                        break
                    if args.provider == "private":
                        t = str(e).lower()
                        if "4.7.1" in t and "sending limit" in t:
                            throttle_count_after = max(1, int(provider_guard.get("recent_throttle_count_24h") or 0) + 1)
                            wait_seconds = throttle_pause_seconds(args.provider, throttle_count_after)
                            guard_status = record_provider_throttle(
                                str(args.profile or ""),
                                str(args.provider or ""),
                                wait_seconds,
                                cooldown_seconds,
                                str(e),
                            )
                            cooldown_until = str(guard_status.get("cooldown_until_utc") or "")
                            recommended = max(0, int(guard_status.get("recommended_cooldown_seconds") or cooldown_seconds))
                            print(
                                "PAUSE: private throttle detected; provider cooldown until "
                                f"{cooldown_until or '-'} with {recommended}s pacing on recovery"
                            )
                            print("STOP: provider_throttle_cooldown")
                            stop_reason = "provider_throttle_cooldown"
                            break
                    continue

                except smtplib.SMTPAuthenticationError as e:
                    code, text = extract_code_text_from_exception(e)
                    if is_temporary_auth_failure(code, text):
                        finalize_domain_attempt_slot(attempt_slot_token, to_email, "temporary_auth_failure", f"{code} {text}")
                        log_row(log_path, to_email, "ERROR", campaign_log_info(f"temporary_auth_failure: {code} {text}", row_campaign_type))
                        error_count += 1
                        circuit_reason = note_error(is_throttle=True)
                        retry_wait_s = min(180, max(30, int(args.interval or 0), 60))
                        print(
                            f"[{i}/{len(pending)}] TEMP AUTH FAILURE {to_email} :: "
                            f"backoff {retry_wait_s}s then retry"
                        )
                        if circuit_reason:
                            print(f"STOP: {circuit_reason} after temporary auth failures")
                            stop_reason = circuit_reason
                            break

                        smtp_close(smtp)
                        smtp = None
                        audit_sleep(retry_wait_s, action="AUTH_RETRY_WAIT")

                        retry_slot_token = ""
                        try:
                            retry_slot_token = reserve_domain_attempt_slot()
                            send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                            send_info = "auth_retry_ok"
                            if args.provider == "sendgrid" and send_result.get("message_id"):
                                send_info = f"auth_retry_ok sg_message_id={send_result['message_id']}"
                            now_sent_utc = datetime.now(timezone.utc)
                            if str(args.profile or "").strip() == "private_jc":
                                if last_success_sent_at_utc is None:
                                    print(f"SEND GAP: first_success_utc={now_sent_utc.isoformat()}")
                                else:
                                    observed_gap_seconds = (now_sent_utc - last_success_sent_at_utc).total_seconds()
                                    print(
                                        "SEND GAP:"
                                        f" previous_success_utc={last_success_sent_at_utc.isoformat()}"
                                        f" current_success_utc={now_sent_utc.isoformat()}"
                                        f" gap_seconds={observed_gap_seconds:.1f}"
                                    )
                                last_success_sent_at_utc = now_sent_utc

                            log_row(log_path, to_email, "SENT", campaign_log_info(send_info, row_campaign_type))
                            if idempotency_reserved:
                                record_send_idempotency_outcome(
                                    campaign_id=row_campaign_id,
                                    provider=args.provider,
                                    email=to_email,
                                    outcome="sent",
                                    info=send_info,
                                )
                            finalize_domain_attempt_slot(retry_slot_token, to_email, "sent", send_info)
                            print(f"[{i}/{len(pending)}] SENT (auth retry) {to_email}")
                            sent_this_run += 1
                            sent_this_run_emails.add(to_email)
                            consecutive_errors = 0
                            consecutive_throttle_errors = 0
                            note_provider_recovery_started()
                            record_sendgrid_success()
                            quality_reason = note_quality_event(is_invalid=False)
                            if args.provider in ("sendgrid", "private"):
                                if to_email not in always_send_set and remove_email_from_csv(csv_path, to_email):
                                    print(f"CSV: removed {to_email} from {csv_path.name}")
                            batch_sent += 1
                            if args.provider == "gmail":
                                gmail_messages_24h += 1
                                if is_external(to_email, my_domains):
                                    gmail_unique_ext.add(to_email)

                            if quality_reason:
                                print(f"STOP: {quality_reason}")
                                stop_reason = "invalid_rate_1h"
                                break

                            if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                                print(f"STOP: reached --max_total={args.max_total}")
                                stop_reason = "max_total"
                            continue
                        except smtplib.SMTPAuthenticationError as retry_exc:
                            retry_code, retry_text = extract_code_text_from_exception(retry_exc)
                            if not is_temporary_auth_failure(retry_code, retry_text):
                                finalize_domain_attempt_slot(
                                    retry_slot_token,
                                    to_email,
                                    "auth_retry_failed",
                                    f"{retry_code} {retry_text}",
                                )
                                log_row(log_path, to_email, "ERROR", campaign_log_info(f"auth_retry_failed: {retry_code} {retry_text}", row_campaign_type))
                                if idempotency_reserved:
                                    record_send_idempotency_outcome(
                                        campaign_id=row_campaign_id,
                                        provider=args.provider,
                                        email=to_email,
                                        outcome="error",
                                        info=f"auth_retry_failed: {retry_code} {retry_text}",
                                    )
                                error_count += 1
                                note_error()
                                print(f"[{i}/{len(pending)}] AUTH ERROR (stop) {to_email} :: {single_line(f'{retry_code} {retry_text}')}")
                                stop_reason = "auth_error"
                                break
                            finalize_domain_attempt_slot(
                                retry_slot_token,
                                to_email,
                                "temporary_auth_failure",
                                f"{retry_code} {retry_text}",
                            )
                            pause_seconds = temporary_failure_pause_seconds(
                                args.provider,
                                max(1, int(provider_guard.get("recent_temporary_failure_count_24h") or 0) + 1),
                            )
                            guard_status = record_provider_temporary_failure(
                                str(args.profile or ""),
                                str(args.provider or ""),
                                pause_seconds,
                                cooldown_seconds,
                                f"{retry_code} {retry_text}",
                            )
                            provider_recovery_pending = True
                            cooldown_until = str(guard_status.get("cooldown_until_utc") or "")
                            log_row(
                                log_path,
                                to_email,
                                "ERROR",
                                campaign_log_info(f"temporary_auth_failure: {retry_code} {retry_text}", row_campaign_type),
                            )
                            if idempotency_reserved:
                                record_send_idempotency_outcome(
                                    campaign_id=row_campaign_id,
                                    provider=args.provider,
                                    email=to_email,
                                    outcome="error",
                                    info=f"temporary_auth_failure: {retry_code} {retry_text}",
                                )
                            error_count += 1
                            print(
                                "PAUSE: temporary auth failure; dashboard recovery scheduled until "
                                f"{cooldown_until or '-'}"
                            )
                            print(
                                f"[{i}/{len(pending)}] TEMP AUTH FAILURE (pause) {to_email} :: "
                                f"{single_line(f'{retry_code} {retry_text}')}"
                            )
                            stop_reason = "temporary_auth_failure"
                            break
                        except Exception as retry_exc:
                            retry_code, retry_text = extract_code_text_from_exception(retry_exc)
                            finalize_domain_attempt_slot(
                                retry_slot_token,
                                to_email,
                                "auth_retry_failed",
                                f"{retry_code} {retry_text or retry_exc}",
                            )
                            log_row(log_path, to_email, "ERROR", campaign_log_info(f"auth_retry_failed: {retry_code} {retry_text or retry_exc}", row_campaign_type))
                            if idempotency_reserved:
                                record_send_idempotency_outcome(
                                    campaign_id=row_campaign_id,
                                    provider=args.provider,
                                    email=to_email,
                                    outcome="error",
                                    info=f"auth_retry_failed: {retry_code} {retry_text or retry_exc}",
                                )
                            error_count += 1
                            note_error(is_throttle=True)
                            print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{retry_code} {retry_text or retry_exc}')}")
                            stop_reason = "auth_retry_failed"
                            break

                    finalize_domain_attempt_slot(attempt_slot_token, to_email, "auth_error", str(e))
                    log_row(log_path, to_email, "ERROR", campaign_log_info(f"auth_failed: {e}", row_campaign_type))
                    error_count += 1
                    note_error()
                    print(f"[{i}/{len(pending)}] AUTH ERROR (stop) {to_email} :: {single_line(str(e))}")
                    stop_reason = "auth_error"
                    break

                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPHeloError) as e:
                    finalize_domain_attempt_slot(attempt_slot_token, to_email, "disconnect", str(e))
                    log_row(log_path, to_email, "ERROR", campaign_log_info(f"disconnected: {e}", row_campaign_type))
                    error_count += 1
                    circuit_reason = note_error(is_throttle=True)
                    print(f"[{i}/{len(pending)}] DISCONNECTED {to_email} :: reconnecting and retrying once")
                    if circuit_reason:
                        print(f"STOP: {circuit_reason} after disconnects")
                        stop_reason = circuit_reason
                        break

                    smtp_close(smtp)
                    smtp = None
                    audit_sleep_with_jitter(max(args.interval, 60), jitter=10)

                    retry_slot_token = ""
                    try:
                        retry_slot_token = reserve_domain_attempt_slot()

                        send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                        send_info = "reconnect_ok"
                        if args.provider == "sendgrid" and send_result.get("message_id"):
                            send_info = f"reconnect_ok sg_message_id={send_result['message_id']}"
                        now_sent_utc = datetime.now(timezone.utc)
                        if str(args.profile or "").strip() == "private_jc":
                            if last_success_sent_at_utc is None:
                                print(f"SEND GAP: first_success_utc={now_sent_utc.isoformat()}")
                            else:
                                observed_gap_seconds = (now_sent_utc - last_success_sent_at_utc).total_seconds()
                                print(
                                    "SEND GAP:"
                                    f" previous_success_utc={last_success_sent_at_utc.isoformat()}"
                                    f" current_success_utc={now_sent_utc.isoformat()}"
                                    f" gap_seconds={observed_gap_seconds:.1f}"
                                )
                            last_success_sent_at_utc = now_sent_utc

                        log_row(log_path, to_email, "SENT", campaign_log_info(send_info, row_campaign_type))
                        if idempotency_reserved:
                            record_send_idempotency_outcome(
                                campaign_id=row_campaign_id,
                                provider=args.provider,
                                email=to_email,
                                outcome="sent",
                                info=send_info,
                            )
                        finalize_domain_attempt_slot(retry_slot_token, to_email, "sent", send_info)
                        print(f"[{i}/{len(pending)}] SENT (reconnect) {to_email}")
                        sent_this_run += 1
                        sent_this_run_emails.add(to_email)
                        consecutive_errors = 0
                        consecutive_throttle_errors = 0
                        note_provider_recovery_started()
                        record_sendgrid_success()
                        quality_reason = note_quality_event(is_invalid=False)
                        if args.provider in ("sendgrid", "private"):
                            if to_email not in always_send_set and remove_email_from_csv(csv_path, to_email):
                                print(f"CSV: removed {to_email} from {csv_path.name}")
                        batch_sent += 1
                        if args.provider == "gmail":
                            gmail_messages_24h += 1
                            if is_external(to_email, my_domains):
                                gmail_unique_ext.add(to_email)

                        if quality_reason:
                            print(f"STOP: {quality_reason}")
                            stop_reason = "invalid_rate_1h"
                            break

                        if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                            print(f"STOP: reached --max_total={args.max_total}")
                            stop_reason = "max_total"

                    except Exception as e2:
                        code2, text2 = extract_code_text_from_exception(e2)
                        finalize_domain_attempt_slot(retry_slot_token, to_email, "reconnect_failed", f"{code2} {text2}")
                        log_row(log_path, to_email, "ERROR", campaign_log_info(f"reconnect_failed: {code2} {text2}", row_campaign_type))
                        error_count += 1
                        note_error(is_throttle=True)
                        print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{code2} {text2}')}")
                        stop_reason = "reconnect_failed"
                        break

                except (smtplib.SMTPDataError, smtplib.SMTPResponseException) as e:
                    code, text = extract_code_text_from_exception(e)
                    cls = classify_smtp(code, text)

                    if cls == "BAD_RECIPIENT":
                        finalize_domain_attempt_slot(attempt_slot_token, to_email, "invalid", f"{code} {text}")
                        log_row(log_path, to_email, "INVALID", campaign_log_info(f"{code} {text}", row_campaign_type))
                        invalid_count += 1
                        print(f"[{i}/{len(pending)}] INVALID {to_email} :: {single_line(f'{code} {text}')}")
                        if args.suppress_invalid:
                            append_suppressed_email(suppress_csv_path, to_email)
                        quality_reason = note_quality_event(is_invalid=True)
                        if quality_reason:
                            print(f"STOP: {quality_reason}")
                            stop_reason = "invalid_rate_1h"
                            break
                        continue

                    if cls == "TEMP_THROTTLE":
                        finalize_domain_attempt_slot(attempt_slot_token, to_email, "temp_throttle", f"{code} {text}")
                        log_row(log_path, to_email, "ERROR", campaign_log_info(f"{code} {text}", row_campaign_type))
                        wait_s = backoff_seconds()
                        error_count += 1
                        circuit_reason = note_error(is_throttle=True)
                        print(f"[{i}/{len(pending)}] THROTTLED {to_email} :: backoff {wait_s}s then retry")
                        if circuit_reason:
                            print(f"STOP: {circuit_reason} after throttles")
                            stop_reason = circuit_reason
                            break

                        audit_sleep(wait_s, action="THROTTLE_WAIT")
                        smtp_close(smtp)
                        smtp = None
                        audit_sleep_with_jitter(max(args.interval, 60), jitter=10)

                        retry_slot_token = ""
                        try:
                            retry_slot_token = reserve_domain_attempt_slot()

                            send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                            send_info = "throttle_retry_ok"
                            if args.provider == "sendgrid" and send_result.get("message_id"):
                                send_info = f"throttle_retry_ok sg_message_id={send_result['message_id']}"
                            now_sent_utc = datetime.now(timezone.utc)
                            if str(args.profile or "").strip() == "private_jc":
                                if last_success_sent_at_utc is None:
                                    print(f"SEND GAP: first_success_utc={now_sent_utc.isoformat()}")
                                else:
                                    observed_gap_seconds = (now_sent_utc - last_success_sent_at_utc).total_seconds()
                                    print(
                                        "SEND GAP:"
                                        f" previous_success_utc={last_success_sent_at_utc.isoformat()}"
                                        f" current_success_utc={now_sent_utc.isoformat()}"
                                        f" gap_seconds={observed_gap_seconds:.1f}"
                                    )
                                last_success_sent_at_utc = now_sent_utc

                            log_row(log_path, to_email, "SENT", campaign_log_info(send_info, row_campaign_type))
                            if idempotency_reserved:
                                record_send_idempotency_outcome(
                                    campaign_id=row_campaign_id,
                                    provider=args.provider,
                                    email=to_email,
                                    outcome="sent",
                                    info=send_info,
                                )
                            finalize_domain_attempt_slot(retry_slot_token, to_email, "sent", send_info)
                            print(f"[{i}/{len(pending)}] SENT (retry) {to_email}")
                            sent_this_run += 1
                            sent_this_run_emails.add(to_email)
                            consecutive_errors = 0
                            consecutive_throttle_errors = 0
                            note_provider_recovery_started()
                            record_sendgrid_success()
                            quality_reason = note_quality_event(is_invalid=False)
                            if args.provider in ("sendgrid", "private"):
                                if to_email not in always_send_set and remove_email_from_csv(csv_path, to_email):
                                    print(f"CSV: removed {to_email} from {csv_path.name}")
                            batch_sent += 1
                            if args.provider == "gmail":
                                gmail_messages_24h += 1
                                if is_external(to_email, my_domains):
                                    gmail_unique_ext.add(to_email)

                            if quality_reason:
                                print(f"STOP: {quality_reason}")
                                stop_reason = "invalid_rate_1h"
                                break

                            if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                                print(f"STOP: reached --max_total={args.max_total}")
                                stop_reason = "max_total"
                                break
                            if repeat_mode and batch_sent >= batch_limit:
                                break
                            continue
                        except Exception as e2:
                            code2, text2 = extract_code_text_from_exception(e2)
                            finalize_domain_attempt_slot(retry_slot_token, to_email, "retry_failed", f"{code2} {text2}")
                            log_row(log_path, to_email, "ERROR", campaign_log_info(f"retry_failed: {code2} {text2}", row_campaign_type))
                            error_count += 1
                            note_error(is_throttle=True)
                            print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{code2} {text2}')}")
                            stop_reason = "retry_failed"
                            break

                    finalize_domain_attempt_slot(attempt_slot_token, to_email, "smtp_error", f"{code} {text}")
                    log_row(log_path, to_email, "ERROR", campaign_log_info(f"{code} {text}", row_campaign_type))
                    error_count += 1
                    print(f"[{i}/{len(pending)}] ERROR {to_email} :: {single_line(f'{code} {text}')}")
                    circuit_reason = note_error()
                    if circuit_reason:
                        print(f"STOP: {circuit_reason} after smtp errors")
                        stop_reason = circuit_reason
                        break

                except Exception as e:
                    err_text = str(e)
                    code, text = extract_code_text_from_exception(e)
                    if not text:
                        text = err_text
                    finalize_domain_attempt_slot(attempt_slot_token, to_email, "error", text or err_text)
                    log_row(log_path, to_email, "ERROR", campaign_log_info(err_text, row_campaign_type))
                    if idempotency_reserved:
                        record_send_idempotency_outcome(
                            campaign_id=row_campaign_id,
                            provider=args.provider,
                            email=to_email,
                            outcome="error",
                            info=err_text,
                        )
                    error_count += 1
                    print(f"[{i}/{len(pending)}] ERROR {to_email} :: {single_line(err_text)}")
                    sendgrid_err_cls = "OTHER"
                    if args.provider == "sendgrid":
                        sendgrid_err_cls = classify_sendgrid_runtime_error(err_text)
                        # Minimal observability: append a single CSV row (UTC ts, profile, classifier,
                        # consecutive_errors, short error text). Keep this best-effort and do not
                        # change runtime behavior if logging fails.
                        try:
                            profile = str(args.profile or "").strip()
                            err_ts = datetime.now(timezone.utc).isoformat()
                            short_err = single_line(err_text)[:200]
                            consec = consecutive_errors
                            try:
                                with open(OBSERVABILITY_LOG_PATH, "a", newline="", encoding="utf-8") as _of:
                                    csv.writer(_of).writerow([err_ts, profile, sendgrid_err_cls, consec, short_err])
                            except Exception:
                                # swallow any file/write errors to avoid changing send behavior
                                pass
                        except Exception:
                            pass
                        if sendgrid_err_cls == "ACCOUNT_STOP":
                            if "verified sender identity" in err_text.lower():
                                print(
                                    "STOP: sendgrid sender identity error. "
                                    "Use a verified From address or verify this sender first."
                                )
                            else:
                                print("STOP: sendgrid account-level error (auth/credits/region).")
                            stop_reason = "sendgrid_account_error"
                        elif sendgrid_err_cls == "TEMP_THROTTLE":
                            wait_s = backoff_seconds()
                            print(f"SENDGRID THROTTLE: sleeping {wait_s}s before next attempt.")
                            audit_sleep(wait_s, action="SENDGRID_THROTTLE_WAIT")
                    if (
                        args.provider == "sendgrid"
                        and args.suppress_invalid
                        and is_sendgrid_forbidden(code, text)
                        and sendgrid_err_cls != "ACCOUNT_STOP"
                    ):
                        append_suppressed_email(suppress_csv_path, to_email)
                        if to_email not in always_send_set and remove_email_from_csv(csv_path, to_email):
                            print(f"CSV: removed {to_email} from {csv_path.name}")
                        print(f"SUPPRESS: {to_email} (sendgrid_403)")
                        quality_reason = note_quality_event(is_invalid=True)
                        if quality_reason:
                            print(f"STOP: {quality_reason}")
                            stop_reason = "invalid_rate_1h"
                    circuit_reason = note_error(is_throttle=(sendgrid_err_cls == "TEMP_THROTTLE"))
                    # Observability: record OTHER-class sendgrid errors to a CSV for debugging
                    if args.provider == "sendgrid" and sendgrid_err_cls == "OTHER":
                        try:
                            profile = str(args.profile or "").strip()
                            err_ts = datetime.now(timezone.utc).isoformat()
                            consec = consecutive_errors
                            try:
                                with open(OBSERVABILITY_LOG_PATH, "a", newline="") as _of:
                                    csv.writer(_of).writerow([err_ts, profile, sendgrid_err_cls, consec, "resumed:false"])
                            except Exception:
                                pass
                            recent_other_error[profile] = {"ts": err_ts, "classification": sendgrid_err_cls, "consec": consec}
                        except Exception:
                            pass
                    if not stop_reason and circuit_reason:
                        print(f"STOP: {circuit_reason} after errors")
                        stop_reason = circuit_reason

                if stop_reason:
                    break
                audit_worker(
                    "running",
                    sent=sent_this_run,
                    errors=error_count,
                    last_recipient=last_recipient_for_audit,
                    action="LOOP",
                    pending_count=len(pending),
                )
                if repeat_mode and batch_sent >= batch_limit:
                    break
                if idx < len(pending) - 1:
                    if stop_at_dt_local:
                        remaining = int((stop_at_dt_local - datetime.now().astimezone()).total_seconds())
                        if remaining <= 0:
                            stop_reason = "schedule_end"
                            print("STOP: schedule_end reached (--stop_at_local).")
                            break
                        if remaining < int(args.interval):
                            audit_sleep(max(1, remaining), action="SCHEDULE_END_WAIT")
                            stop_reason = "schedule_end"
                            print("STOP: schedule_end reached (--stop_at_local).")
                            break
                    audit_sleep_with_jitter(args.interval, jitter=10)

            pending_index = next_index

            if args.preview_messages:
                break

            if repeat_mode:
                remaining_pending = max(0, len(pending) - pending_index)
                if args.max_total > 0:
                    remaining_allowed = max(0, args.max_total - sent_this_run)
                    remaining_estimate = min(remaining_pending, remaining_allowed)
                else:
                    remaining_estimate = remaining_pending

                next_sleep_seconds = 0
                if (
                    not stop_reason
                    and pending_index < len(pending)
                    and not (args.max_total and sent_this_run >= args.max_total)
                    and not (args.max_per_run and sent_this_run >= args.max_per_run)
                ):
                    next_sleep_seconds = cooldown_seconds

                print(
                    f"BATCH: sent={batch_sent} total={sent_this_run} "
                    f"remaining_estimate={remaining_estimate} next_sleep_seconds={next_sleep_seconds}"
                )

                if not stop_reason and pending_index >= len(pending):
                    refreshed_pending, _, refreshed_row_count, refreshed_eligible_count = build_pending_snapshot(
                        emit_suppressed_logs=False,
                        allow_missing_always_send_rows=False,
                        exclude_logged_always_send=True,
                    )
                    if refreshed_eligible_count > 0:
                        pending = refreshed_pending
                        pending_index = 0
                        source_row_count = refreshed_row_count
                        eligible_pending_count = refreshed_eligible_count
                        emit_worker_event(
                            "REFRESH",
                            "queue_refreshed_after_batch_exhaustion",
                            pending_count=len(pending),
                            source_rows=source_row_count,
                            sent_this_run=sent_this_run,
                        )

                if (
                    stop_reason
                    or pending_index >= len(pending)
                    or (args.max_total and sent_this_run >= args.max_total)
                    or (args.max_per_run and sent_this_run >= args.max_per_run)
                ):
                    break

                if cooldown_seconds > 0:
                    if stop_at_dt_local:
                        remaining = int((stop_at_dt_local - datetime.now().astimezone()).total_seconds())
                        if remaining <= 0:
                            print("STOP: schedule_end reached (--stop_at_local).")
                            break
                        if remaining < cooldown_seconds:
                            audit_sleep(max(1, remaining), action="SCHEDULE_END_WAIT")
                            print("STOP: schedule_end reached (--stop_at_local).")
                            break
                    if human_mode_active:
                        sleep_s = humanized_cooldown_sleep_seconds(cooldown_seconds, sent_this_run, human_state, args)
                        audit_sleep(sleep_s, action="COOLDOWN_WAIT")
                    else:
                        audit_sleep(cooldown_seconds, action="COOLDOWN_WAIT")
            else:
                break

        final_reason = stop_reason or "queue_exhausted"
        emit_worker_event(
            "STOP" if stop_reason else "DONE",
            final_reason,
            sent_this_run=sent_this_run,
            invalid_count=invalid_count,
            error_count=error_count,
            pending_index=pending_index,
            pending_count=len(pending),
            total_sent_attempted=total_sent_attempted,
            total_skipped_suppressed=skipped_sendgrid_suppressed if args.provider in {"private", "sendgrid"} else 0,
        )
        audit_worker(
            "stopped" if stop_reason else "done",
            sent=sent_this_run,
            errors=error_count,
            last_recipient=last_recipient_for_audit,
            action=final_reason,
            pending_count=len(pending),
            terminal=True,
            force=True,
        )
        print(
            "DONE:"
            f" sent={sent_this_run}"
            f" invalid={invalid_count}"
            f" errors={error_count}"
            f" total_skipped_suppressed={skipped_sendgrid_suppressed if args.provider in {'private', 'sendgrid'} else 0}"
            f" total_sent_attempted={total_sent_attempted}"
        )
        if args.preview_messages:
            print(f"PREVIEW FILE: {preview_messages_path}")
        if args.prune_sent and sent_this_run_emails:
            prunable = sent_this_run_emails - always_send_set
            removed = prune_sent_from_csv(csv_path, prunable)
            if removed:
                print(f"PRUNE: removed {removed} from {csv_path.name}")

    except KeyboardInterrupt:
        emit_worker_event(
            "STOP",
            "interrupted",
            pending_index=locals().get("pending_index", 0),
            pending_count=len(pending),
            sent_this_run=sent_this_run,
            error_count=error_count,
        )
        audit_worker(
            "interrupted",
            sent=sent_this_run,
            errors=error_count,
            last_recipient=last_recipient_for_audit,
            action="INTERRUPTED",
            pending_count=len(pending),
            terminal=True,
            force=True,
        )
        raise
    except Exception as exc:
        emit_worker_event(
            "ERROR",
            type(exc).__name__,
            pending_index=locals().get("pending_index", 0),
            pending_count=len(pending),
            traceback=traceback.format_exc(),
        )
        audit_worker(
            "error",
            sent=sent_this_run,
            errors=error_count,
            last_recipient=last_recipient_for_audit,
            action=type(exc).__name__,
            pending_count=len(pending),
            terminal=True,
            force=True,
        )
        raise
    finally:
        if runtime_lock_context is not None:
            try:
                runtime_lock_context.__exit__(None, None, None)
            except Exception:
                pass
        if should_log_worker:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
        smtp_close(smtp)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
