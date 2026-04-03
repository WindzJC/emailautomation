# =========================
# BEFORE PITCHES (TOP PART)
# =========================

import argparse
import base64
import csv
import html
import json
import random
import re
import ssl
import smtplib
import tempfile
import time
import os
import fcntl
import sys
from collections import deque
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from getpass import getpass
from pathlib import Path
from typing import Optional, Tuple, Set, Dict, List, Deque, Sequence
from urllib.parse import quote

import settings
from recipient_file_lock import lock_files
from provider_pacing import (
    mark_recovery_started,
    provider_pacing_status,
    record_provider_throttle,
    throttle_pause_seconds,
)
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

PROVIDER_LIMIT_DEFAULTS = {
    "private": {"max_messages_1h": 80},
    "gmail": {"max_messages_24h": 100, "max_unique_external_24h": 100},
    "sendgrid": {"max_messages_1h": 180},
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
        "interval": 90,
        "batch_size": 1,
        "cooldown_seconds": 90,
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

        #SEND GRID
    "sendgrid_annette": {
        "provider": "sendgrid",
        "csv": "recipients_sendgrid_1.csv",
        "log": "sendgrid_annette_log.csv",
        "pitch": "pitch1",
        "from_email": "annettedanek-akey@barnesnoblemarketing.com",
        "my_domains": "barnesnoblemarketing.com,astraproductionsbyjc.com",
        "interval": 45,
        "batch_size": 1,
        "cooldown_seconds": 45,
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
        "interval": 45,
        "batch_size": 1,
        "cooldown_seconds": 45,
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
        "interval": 45,
        "batch_size": 1,
        "cooldown_seconds": 45,
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
        "interval": 45,
        "batch_size": 1,
        "cooldown_seconds": 45,
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
        "interval": 45,
        "batch_size": 1,
        "cooldown_seconds": 45,
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
    settings.maybe_seed_file(path, Path(str(value or "")).name)
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

# ===== SIGNATURES (inline image via CID) =====
SIGNATURE_CID = "sigimg"

SIGNATURE_BY_FROM: Dict[str, str] = {
    # --- Gmail 4 accounts (each different) ---
    "corporate@barnesnobleinfo.com": "sig_gmail_corporate.png",
    "sally@littlebrowncoinfo.com":     "sig_gmail_sally.png",
    "jordan@barnesnobleinfo.com":    "sig_gmail_jordan.png",
    "josefina@barnesnobleinfo.com":  "sig_gmail_josefina.png",

    # --- Astra 7 accounts (ALL SAME image) ---
    "megan@astraproductionsbyjc.com":   "sig_astra.png",
    "alex@astraproductionsbyjc.com":    "sig_astra.png",
    "kentc@astraproductionsbyjc.com":   "sig_astra.png",
    "zachking@astraproductionsbyjc.com":"sig_astra.png",
    "jc@astraproductionsbyjc.com":      "sig_astra.png",
    "jordanA@astraproductionsbyjc.com": "sig_astra.png",
    "astra@astraproductionsbyjc.com":   "sig_astra.png",

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

PITCH_1_5_BODY = """Hi {AuthorName},

Hope you’re having a great day. I’m reaching out after seeing your work and wanted to personally invite you in our Barnes Noble Consignment Program. We’re selective with what we stock, and we believe your work has strong shelf potential with the right readers.

We’re opening a few consignment spots. In a store, people buy differently: they notice the cover, pick it up, flip through a few pages, and decide.

We accept a limited number of titles and review each one for content fit, print/production quality, and retail-ready pricing.

Before we move forward, we require two things to be in place for placement and promotion once your book is stocked:
1) a book teaser/trailer for promotion, and
2) a clean author/book page so readers can find the book online, join your list, and go straight to your retailer links.

If you already have a teaser and author/book page, send them over (links are fine). I’ll review them and let you know what’s ready to use and what needs adjusting before placement.

Consignment terms
- You earn 85% of the sale price (example: $8.50 on a $10.00 book)
- You cover shipping to our store(s)
- Sales reporting + payouts quarterly (within 90 days after quarter-end)
- You choose the stocking option that fits your budget—no additional consignment fees beyond shipping

Stocking options (choose one)
- $250 — 750 copies
- $500 — 1,500 copies
- $750 — 2,500 copies
- $1,000 — 3,500 copies

If you need us to build the required assets:
- Book teaser + promo clips — $999
- Author/book page — $499
- Bundle (teaser + website) — $1,299 (save $199)

If you’d like to move forward, reply “Interested” and send the link for the title you want us to review (or the ISBN) and your retail price. I’ll confirm fit and send the next steps along with a straightforward agreement for your review.

We’d be glad to work with you.

Regards,
{SIGIMG}

P.S. If you’d prefer I don’t reach out again, click here: {UnsubMailto}
(or just reply “unsubscribe”).
"""

PITCH_JC_BODY = """Hi {AuthorName},

I’m reaching out because I work specifically with authors on the visual side of promotion.

A strong book can still lose attention online when the hook does not land fast enough. At Astra Productions, I help fix that with hook-first trailers that feel closer to a film preview, premium author pages, and launch visuals built to make the story clearer, build trust faster, and turn more interest into clicks.

I’ve spent 6+ years helping authors strengthen how their books are presented online. You can review the work at astraproductions.co. Trailer projects start at $999, author websites at $499, and the launch bundle at $1299.

If that sounds aligned, reply and I’ll send one concise idea for how I’d approach it.

Windelle JC
Creative Director, Astra Productions
{SIGIMG}

P.S. If you’d rather not hear from me again, just reply unsub.
"""

PITCHES = {
    "pitch1": {
        "subject": "Final Call: Consignment Consideration",
        "body": PITCH_1_5_BODY,
            },

    "pitch2": {
        "subject": "Final Call: Consignment Consideration",
        "body": PITCH_1_5_BODY,
    },

    "pitch3": {
        "subject": "Final Call: Consignment Consideration",
        "body": PITCH_1_5_BODY,
    },

    "pitch4": {
        "subject": "Final Call: Consignment Consideration",
        "body": PITCH_1_5_BODY,
    },

    "pitch5": {
        "subject": "Final Call: Consignment Consideration",
        "body": PITCH_1_5_BODY,

  },
    "pitch_jc": {
        "subject": "Quick thought on your book",
        "body": PITCH_JC_BODY,
    },

}


def norm_email(s: str) -> str:
    _, addr = parseaddr(s or "")
    return addr.strip().lower()


def make_unsub_mailto(unsub_email: str) -> str:
    return f"mailto:{unsub_email}?subject={quote('unsubscribe')}&body={quote('unsubscribe')}"


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


def prioritize_always_send_rows(rows: List[Dict[str, str]], always_send_set: Set[str]) -> List[Dict[str, str]]:
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
        if name in lower_row:
            return lower_row[name]
    return ""


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


def load_already_done(sent_log: Path) -> Set[str]:
    if not sent_log.exists():
        return set()
    out: Set[str] = set()
    with sent_log.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = (r.get("Status") or "").strip().upper()
            if st not in ("SENT", "INVALID"):
                continue
            e = norm_email(r.get("Email") or "")
            if e:
                out.add(e)
    return out


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
    if name == "recipients_private_jc.csv":
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
            return name == "recipients_private_jc.csv"
        return name == "private_jc_log.csv"
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
            fieldnames = reader.fieldnames or ["Email", "AuthorName", "BookTitle"]
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


def remove_email_from_csv(csv_path: Path, email_addr: str) -> bool:
    if not email_addr or not csv_path.exists():
        return False
    removed = 0
    with lock_files([csv_path]):
        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ["Email", "AuthorName", "BookTitle"]
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
    unsub_mailto_override: Optional[str] = None,
) -> Tuple[str, str, str, Optional[str]]:
    unsub_mailto = unsub_mailto_override or make_unsub_mailto(unsub_email)

    author = (author or GENERIC_SALUTATION).strip()
    first_name = author.split()[0] if author else GENERIC_SALUTATION
    book_title = (book_title or "").strip() or "your book"

    format_args = {
        "AuthorName": author,
        "FirstName": first_name,
        "BookTitle": book_title,
        "UnsubEmail": unsub_email,
        "UnsubMailto": unsub_mailto,
        "SIGIMG": "{SIGIMG}",   # keep marker for HTML rendering
    }

    body_text = body_template.format(**format_args)
    subject_text = subject.format(
        AuthorName=author,
        FirstName=first_name,
        BookTitle=book_title,
        UnsubEmail=unsub_email,
        UnsubMailto=unsub_mailto,
        SIGIMG="",
    )

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
    unsub_mailto_override: Optional[str] = None,
) -> Tuple[EmailMessage, str, str, str, Optional[str]]:
    subject_text, body_text, html_body, cid = render_message_parts(
        author,
        book_title,
        subject,
        body_template,
        unsub_email,
        signature_file,
        unsub_mailto_override,
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
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail,
            Content,
            ReplyTo,
            Attachment,
            FileContent,
            FileName,
            FileType,
            Disposition,
            ContentId,
            Header,
            Asm,
            CustomArg,
        )
    except Exception as exc:
        raise RuntimeError(
            "sendgrid library not installed; add 'sendgrid' to requirements and install it"
        ) from exc

    asm_enabled = int(unsubscribe_group_id or 0) > 0
    unsub_token = "<%asm_group_unsubscribe_url%>" if asm_enabled else ""

    text_content = body_text.replace("{SIGIMG}", "").strip()
    if unsub_token and unsub_token not in text_content:
        text_content = (text_content + "\n\nP.S. Unsubscribe: <%asm_group_unsubscribe_url%>").strip()

    html_content = html_body
    if unsub_token and unsub_token not in html_content:
        unsub_html = f'<br><br><a href="{unsub_token}">Unsubscribe</a>'
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{unsub_html}</body>", 1)
        elif "</html>" in html_content:
            html_content = html_content.replace("</html>", f"{unsub_html}</html>", 1)
        else:
            html_content = f"{html_content}{unsub_html}"

    mail = Mail(from_email=from_email, to_emails=to_email, subject=subject_text)
    mail.add_content(Content("text/plain", text_content))
    mail.add_content(Content("text/html", html_content))
    mail.reply_to = ReplyTo(reply_to)
    mail.add_header(Header("List-Unsubscribe", f"<mailto:{unsub_email}?subject=unsubscribe>"))
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


def domain_wait_for_slot(domain_log_path: Path, max_messages_1h: int, jitter_sec: int = 5) -> None:
    """
    Domain-wide rolling 60-min limiter using a file lock.
    Counts SENT in the last hour plus only *active* SLOT reservations.
    SLOT rows are short-lived reservations used to prevent races across panes.
    """
    if max_messages_1h <= 0:
        return

    domain_log_path.parent.mkdir(parents=True, exist_ok=True)

    if not domain_log_path.exists():
        with domain_log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
            w.writeheader()

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
                if st not in ("SENT", "SLOT"):
                    continue
                t = _parse_ts_safe(r.get("TimestampUTC") or "")
                if not t:
                    continue
                if st == "SENT" and t >= cutoff:
                    expiry_times.append(t + timedelta(hours=1))
                    continue
                if st == "SLOT" and t >= slot_cutoff:
                    expiry_times.append(t + timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS))

            expiry_times.sort()
            used = len(expiry_times)

            if used < max_messages_1h:
                f.seek(0, os.SEEK_END)
                w = csv.DictWriter(f, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
                w.writerow({
                    "TimestampUTC": now.isoformat(),
                    "Email": "",
                    "Status": "SLOT",
                    "Info": "reserve",
                })
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return

            earliest = expiry_times[0] if expiry_times else (now + timedelta(seconds=30))
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        wait_s = max(1, int((earliest - datetime.now(timezone.utc)).total_seconds())) + random.randint(0, jitter_sec)
        time.sleep(wait_s)


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
    ap.add_argument("--preflight", action="store_true")
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

    if profile_defaults:
        ap.set_defaults(**profile_defaults)
    ap.set_defaults(block_role_recipients=True)

    args = ap.parse_args()
    if args.list_profiles:
        print("Profiles available:")
        for name, cfg in sorted(PROFILES.items()):
            print(f" - {name}")
            for k, v in sorted(cfg.items()):
                print(f"    {k}: {v}")
        return
    if args.profile and not args.status:
        print(f"PROFILE: {args.profile}")

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

    if args.provider == "sendgrid" and not args.dry_run and not sendgrid_api_key:
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
    body_template = (pitch.get("body") or "").strip()

    csv_path = _resolve_shard_path(args.csv)
    log_path = _resolve_log_path(args.log)
    unsub_csv_path = _resolve_state_path(args.unsub_csv)
    suppress_csv_path = _resolve_state_path(args.suppress_csv)
    sendgrid_suppression_csv_path = _resolve_state_path(args.sendgrid_suppression_csv)

    if not csv_path.exists():
        print("ERROR missing:", csv_path)
        return

    my_domains: Set[str] = {d.strip().lower() for d in (args.my_domains or "").split(",") if d.strip()}
    if not my_domains:
        my_domains = {DEFAULT_DOMAIN}

    rows = read_rows(csv_path)
    already_done = load_already_done(log_path)
    unsubbed = load_emails_from_csv(unsub_csv_path)
    suppressed = load_emails_from_csv(suppress_csv_path)
    always_send_set = parse_email_list(getattr(args, "always_send", ""))
    sendgrid_suppressed_active: Set[str] = set()
    sendgrid_suppressed_perm = 0
    sendgrid_suppressed_temp_active = 0
    if args.provider == "sendgrid":
        sendgrid_suppressed_active, sendgrid_suppression_summary = load_active_suppressed_emails(
            sendgrid_suppression_csv_path
        )
        sendgrid_suppressed_active -= always_send_set
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

    if args.prune_sent:
        sent_for_prune = set(already_done)
        if args.global_dedupe:
            sent_for_prune |= global_done
        sent_for_prune -= always_send_set
        removed = prune_sent_from_csv(csv_path, sent_for_prune)
        if removed:
            print(f"PRUNE: removed {removed} from {csv_path.name}")
            rows = read_rows(csv_path)

    pending: List[Dict[str, str]] = []
    seen_in_input: Set[str] = set()
    skipped_dupes = 0
    skipped_global_logs = 0
    skipped_global_recipients = 0
    skipped_role_recipients = 0
    skipped_unverified = 0
    skipped_risky_rows = 0
    skipped_sendgrid_suppressed = 0
    for r in rows:
        email_addr = norm_email(r.get("Email") or "")
        if not email_addr:
            continue
        if email_addr in seen_in_input:
            skipped_dupes += 1
            continue
        seen_in_input.add(email_addr)
        if args.provider == "sendgrid" and email_addr in sendgrid_suppressed_active:
            skipped_sendgrid_suppressed += 1
            log_row(log_path, email_addr, "SKIP", "skip_reason=suppressed")
            continue
        if email_addr in unsubbed or email_addr in suppressed:
            continue
        is_always_send = email_addr in always_send_set
        if args.block_role_recipients and role_block_set and not is_always_send:
            if is_role_recipient(email_addr, role_block_set):
                skipped_role_recipients += 1
                continue
        if args.require_valid_status and not is_always_send:
            status_val = get_row_value_ci(r, status_cols)
            status_tokens = split_canonical_tokens(status_val)
            if not status_tokens or not (status_tokens & valid_status_values):
                skipped_unverified += 1
                continue
        if args.block_risky_rows and not is_always_send:
            risk_val = get_row_value_ci(r, risk_cols)
            risk_tokens = split_canonical_tokens(risk_val)
            if risk_tokens & blocked_risk_values:
                skipped_risky_rows += 1
                continue
        if not is_always_send:
            if email_addr in already_done:
                continue
            if args.global_dedupe and email_addr in global_done:
                skipped_global_logs += 1
                continue
            if args.global_dedupe and email_addr in other_recipients:
                skipped_global_recipients += 1
                continue
        pending.append(r)
    pending = prioritize_always_send_rows(pending, always_send_set)

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
    if not pending:
        print("Nothing to send.")
        return

    domain_log_path = _resolve_log_path(args.domain_log) if args.domain_log else log_path
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
    if args.provider == "sendgrid":
        print(
            "SENDGRID SUPPRESSIONS:"
            f" file={sendgrid_suppression_csv_path.name}"
            f" suppressed_loaded: total_perm={sendgrid_suppressed_perm}"
            f" total_temp_active={sendgrid_suppressed_temp_active}"
            f" skipped={skipped_sendgrid_suppressed}"
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
    if not args.dry_run and args.provider != "sendgrid":
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
    sendgrid_custom_args = {
        "profile": (args.profile or "").strip(),
        "from_email": from_user,
        "shard": csv_path.name,
        "provider": "sendgrid" if args.provider == "sendgrid" else "",
    }
    unsub_mailto_override = (
        "<%asm_group_unsubscribe_url%>"
        if args.provider == "sendgrid" and sendgrid_unsub_group_id > 0
        else None
    )

    sendgrid_counters: Dict[str, Dict[str, object]] = {}
    sendgrid_counter_key = ""
    sendgrid_sent_today = 0
    sendgrid_account_sent_today = 0
    sendgrid_effective_cap = SENDGRID_DAILY_CAP
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
        if not args.dry_run and sendgrid_cap_enabled and sendgrid_sent_today >= sendgrid_effective_cap:
            log_row(
                log_path,
                "",
                "DAILY_CAP_REACHED",
                f"global_sent_today={sendgrid_sent_today} cap={sendgrid_effective_cap}",
            )
            print(
                f"STOP: DAILY_CAP_REACHED global_sent_today={sendgrid_sent_today} "
                f"account_sent_today={sendgrid_account_sent_today} cap={sendgrid_effective_cap}"
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
    if repeat_mode and batch_size <= 0:
        print("ERROR: --batch_size must be > 0 when --repeat is set.")
        return

    def record_sendgrid_success() -> None:
        nonlocal sendgrid_sent_today, sendgrid_account_sent_today
        if args.provider != "sendgrid" or args.dry_run:
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

    try:
        if not args.dry_run and args.provider == "gmail":
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
            stop_reason = None
            next_index = pending_index

            for idx in range(pending_index, len(pending)):
                if stop_at_reached():
                    print("STOP: schedule_end reached (--stop_at_local).")
                    stop_reason = "schedule_end"
                    break
                i = idx + 1
                r = pending[idx]
                to_email = norm_email(r.get("Email") or "")
                if not to_email:
                    next_index = idx + 1
                    continue

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
                    if sendgrid_cap_enabled and sendgrid_sent_today >= sendgrid_effective_cap:
                        if not args.dry_run:
                            log_row(
                                log_path,
                                "",
                                "DAILY_CAP_REACHED",
                                f"global_sent_today={sendgrid_sent_today} cap={sendgrid_effective_cap}",
                            )
                        print(
                            f"STOP: DAILY_CAP_REACHED global_sent_today={sendgrid_sent_today} "
                            f"account_sent_today={sendgrid_account_sent_today} cap={sendgrid_effective_cap}"
                        )
                        stop_reason = "daily_cap"
                        break

                raw_author = get_row_value_ci(
                    r,
                    ["authorname", "author_name", "firstname", "first_name", "first name", "author", "name"],
                )
                author = choose_salutation_name(raw_author, to_email)
                book_title = (r.get("BookTitle") or r.get("Title") or "").strip()

                msg, subject_text, body_text, html_body, cid = build_message(
                    from_user, to_email, author, book_title,
                    subject, body_template, unsub_email,
                    signature_file=sig_path,
                    unsub_mailto_override=unsub_mailto_override,
                )

                next_index = idx + 1
                try:
                    total_sent_attempted += 1
                    if args.dry_run:
                        log_row(log_path, to_email, "DRYRUN", "not_sent")
                        print(f"[{i}/{len(pending)}] DRYRUN {to_email}")
                    else:
                        if args.provider in ("private", "sendgrid") and args.max_messages_1h:
                            domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                        send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                        send_info = ""
                        if args.provider == "sendgrid" and send_result.get("message_id"):
                            send_info = f"sg_message_id={send_result['message_id']}"

                        log_row(log_path, to_email, "SENT", send_info)
                        print(f"[{i}/{len(pending)}] SENT {to_email}")
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

                        if args.provider in ("private", "sendgrid") and args.max_messages_1h and domain_log_path != log_path:
                            log_row(domain_log_path, to_email, "SENT")

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
                            log_row(log_path, to_email, "INVALID", f"{code} {text}")
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

                        log_row(log_path, to_email, "ERROR", f"{code} {text}")
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

                    log_row(log_path, to_email, "ERROR", str(e))
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
                    log_row(log_path, to_email, "ERROR", f"auth_failed: {e}")
                    error_count += 1
                    note_error()
                    print(f"[{i}/{len(pending)}] AUTH ERROR (stop) {to_email} :: {single_line(str(e))}")
                    stop_reason = "auth_error"
                    break

                except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPHeloError) as e:
                    log_row(log_path, to_email, "ERROR", f"disconnected: {e}")
                    error_count += 1
                    circuit_reason = note_error(is_throttle=True)
                    print(f"[{i}/{len(pending)}] DISCONNECTED {to_email} :: reconnecting and retrying once")
                    if circuit_reason:
                        print(f"STOP: {circuit_reason} after disconnects")
                        stop_reason = circuit_reason
                        break

                    smtp_close(smtp)
                    smtp = None
                    sleep_with_jitter(max(args.interval, 60), jitter=10)

                    try:
                        if args.provider in ("private", "sendgrid") and args.max_messages_1h:
                            domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                            send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                            send_info = "reconnect_ok"
                            if args.provider == "sendgrid" and send_result.get("message_id"):
                                send_info = f"reconnect_ok sg_message_id={send_result['message_id']}"

                            log_row(log_path, to_email, "SENT", send_info)
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

                        if args.provider in ("private", "sendgrid") and args.max_messages_1h and domain_log_path != log_path:
                            log_row(domain_log_path, to_email, "SENT")

                        if quality_reason:
                            print(f"STOP: {quality_reason}")
                            stop_reason = "invalid_rate_1h"
                            break

                        if repeat_mode and args.max_total and sent_this_run >= args.max_total:
                            print(f"STOP: reached --max_total={args.max_total}")
                            stop_reason = "max_total"

                    except Exception as e2:
                        code2, text2 = extract_code_text_from_exception(e2)
                        log_row(log_path, to_email, "ERROR", f"reconnect_failed: {code2} {text2}")
                        error_count += 1
                        note_error(is_throttle=True)
                        print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{code2} {text2}')}")
                        stop_reason = "reconnect_failed"
                        break

                except (smtplib.SMTPDataError, smtplib.SMTPResponseException) as e:
                    code, text = extract_code_text_from_exception(e)
                    cls = classify_smtp(code, text)

                    if cls == "BAD_RECIPIENT":
                        log_row(log_path, to_email, "INVALID", f"{code} {text}")
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
                        log_row(log_path, to_email, "ERROR", f"{code} {text}")
                        wait_s = backoff_seconds()
                        error_count += 1
                        circuit_reason = note_error(is_throttle=True)
                        print(f"[{i}/{len(pending)}] THROTTLED {to_email} :: backoff {wait_s}s then retry")
                        if circuit_reason:
                            print(f"STOP: {circuit_reason} after throttles")
                            stop_reason = circuit_reason
                            break

                        time.sleep(wait_s)
                        smtp_close(smtp)
                        smtp = None
                        sleep_with_jitter(max(args.interval, 60), jitter=10)

                        try:
                            if args.provider in ("private", "sendgrid") and args.max_messages_1h:
                                domain_wait_for_slot(domain_log_path, args.max_messages_1h)

                            send_result = send_one(msg, to_email, subject_text, body_text, html_body, cid)
                            send_info = "throttle_retry_ok"
                            if args.provider == "sendgrid" and send_result.get("message_id"):
                                send_info = f"throttle_retry_ok sg_message_id={send_result['message_id']}"

                            log_row(log_path, to_email, "SENT", send_info)
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

                            if args.provider in ("private", "sendgrid") and args.max_messages_1h and domain_log_path != log_path:
                                log_row(domain_log_path, to_email, "SENT")

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
                            log_row(log_path, to_email, "ERROR", f"retry_failed: {code2} {text2}")
                            error_count += 1
                            note_error(is_throttle=True)
                            print(f"[{i}/{len(pending)}] ERROR (stop) {to_email} :: {single_line(f'{code2} {text2}')}")
                            stop_reason = "retry_failed"
                            break

                    log_row(log_path, to_email, "ERROR", f"{code} {text}")
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
                    log_row(log_path, to_email, "ERROR", err_text)
                    error_count += 1
                    print(f"[{i}/{len(pending)}] ERROR {to_email} :: {single_line(err_text)}")
                    sendgrid_err_cls = "OTHER"
                    if args.provider == "sendgrid":
                        sendgrid_err_cls = classify_sendgrid_runtime_error(err_text)
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
                            time.sleep(wait_s)
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
                    if not stop_reason and circuit_reason:
                        print(f"STOP: {circuit_reason} after errors")
                        stop_reason = circuit_reason

                if stop_reason:
                    break
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
                            time.sleep(max(1, remaining))
                            stop_reason = "schedule_end"
                            print("STOP: schedule_end reached (--stop_at_local).")
                            break
                    sleep_with_jitter(args.interval, jitter=10)

            pending_index = next_index

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
                            time.sleep(max(1, remaining))
                            print("STOP: schedule_end reached (--stop_at_local).")
                            break
                    if human_mode_active:
                        sleep_s = humanized_cooldown_sleep_seconds(cooldown_seconds, sent_this_run, human_state, args)
                        time.sleep(sleep_s)
                    else:
                        time.sleep(cooldown_seconds)
            else:
                break

        print(
            "DONE:"
            f" sent={sent_this_run}"
            f" invalid={invalid_count}"
            f" errors={error_count}"
            f" total_skipped_suppressed={skipped_sendgrid_suppressed if args.provider == 'sendgrid' else 0}"
            f" total_sent_attempted={total_sent_attempted}"
        )
        if args.prune_sent and sent_this_run_emails:
            prunable = sent_this_run_emails - always_send_set
            removed = prune_sent_from_csv(csv_path, prunable)
            if removed:
                print(f"PRUNE: removed {removed} from {csv_path.name}")

    finally:
        smtp_close(smtp)

if __name__ == "__main__":
    main()
