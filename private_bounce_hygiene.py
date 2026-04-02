from __future__ import annotations

import csv
import imaplib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from email import policy
from email.header import decode_header
from email.message import Message
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import settings
from send_shard import PROFILES
from sendgrid_hygiene import norm_email


PRIVATE_IMAP_HOST = "mail.privateemail.com"
PRIVATE_IMAP_PORT = 993
PRIVATE_BOUNCE_STATE_PATH = settings.STATE_DIR / "private_bounce_state.json"
PRIVATE_BOUNCE_MONITOR_PATH = settings.STATE_DIR / "private_bounce_monitor.json"
PRIVATE_BOUNCE_REPORT_PREFIX = "private_bounce_sync_"

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
FINAL_RECIPIENT_RE = re.compile(r"final-recipient:\s*(?:[^;]+;)?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
ORIGINAL_RECIPIENT_RE = re.compile(r"original-recipient:\s*(?:[^;]+;)?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
FAILED_RECIPIENTS_RE = re.compile(r"x-failed-recipients:\s*([^\r\n]+)", re.IGNORECASE)

BOUNCE_SUBJECT_HINTS = (
    "undelivered mail returned to sender",
    "delivery status notification",
    "mail delivery failed",
    "returned mail",
    "failure notice",
    "delivery has failed",
)
BOUNCE_FROM_HINTS = (
    "mailer-daemon",
    "mail delivery system",
    "mail delivery subsystem",
    "postmaster",
)
SYSTEM_LOCALPARTS = {
    "mailer-daemon",
    "postmaster",
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


def _env_csv(name: str, default: Sequence[str]) -> Tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return tuple(default)
    items = [item.strip() for item in raw.split(",")]
    cleaned = [item for item in items if item]
    return tuple(cleaned or list(default))


PRIVATE_BOUNCE_MONITOR_ENABLED = _env_bool("PRIVATE_BOUNCE_MONITOR_ENABLED", True)
PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS = _env_int("PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS", 120)
PRIVATE_BOUNCE_CLUSTER_WINDOW_MINUTES = _env_int("PRIVATE_BOUNCE_CLUSTER_WINDOW_MINUTES", 15)
PRIVATE_BOUNCE_CLUSTER_THRESHOLD = _env_int("PRIVATE_BOUNCE_CLUSTER_THRESHOLD", 3)
PRIVATE_BOUNCE_COOLDOWN_MINUTES = _env_int("PRIVATE_BOUNCE_COOLDOWN_MINUTES", 15)
PRIVATE_BOUNCE_LOOKBACK_DAYS = _env_int("PRIVATE_BOUNCE_LOOKBACK_DAYS", 14)
PRIVATE_BOUNCE_IMAP_TIMEOUT_SECONDS = _env_int("PRIVATE_BOUNCE_IMAP_TIMEOUT_SECONDS", 30)
PRIVATE_BOUNCE_EVENT_HISTORY_LIMIT = _env_int("PRIVATE_BOUNCE_EVENT_HISTORY_LIMIT", 50)
PRIVATE_BOUNCE_FOLDERS = _env_csv("PRIVATE_BOUNCE_FOLDERS", ("INBOX", "Spam"))


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_utc(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        handle.write(text)
    tmp_path.replace(path)


def _write_json_atomic(path: Path, payload: Dict[str, object]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read_simple_email_rows(path: Path) -> tuple[str, List[str]]:
    if not path.exists():
        return "Email", []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return "Email", []
        header_map = {str(name or "").strip().lower(): name for name in reader.fieldnames}
        email_header = header_map.get("email") or "Email"
        rows: List[str] = []
        for row in reader:
            email_addr = norm_email(row.get(email_header, ""))
            if email_addr:
                rows.append(email_addr)
        return email_header, rows


def _write_simple_email_rows(path: Path, header: str, emails: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=[header or "Email"])
        writer.writeheader()
        field = header or "Email"
        for email_addr in emails:
            writer.writerow({field: email_addr})
    tmp_path.replace(path)


def _decode_header_value(value: str) -> str:
    out: List[str] = []
    for part, charset in decode_header(value or ""):
        if isinstance(part, bytes):
            try:
                out.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                out.append(part.decode("utf-8", errors="replace"))
        else:
            out.append(str(part))
    return "".join(out).strip()


def _message_header_text(msg: Message, name: str) -> str:
    return _decode_header_value(msg.get(name, ""))


def _message_detected_at_utc(msg: Message) -> str:
    raw_date = _message_header_text(msg, "Date")
    if not raw_date:
        return ""
    try:
        dt = parsedate_to_datetime(raw_date)
    except Exception:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return iso_utc(dt.astimezone(timezone.utc))


def is_probable_bounce_message(msg: Message) -> bool:
    subject = _message_header_text(msg, "Subject").lower()
    from_text = _message_header_text(msg, "From").lower()
    content_type = (msg.get_content_type() or "").lower()
    if any(token in subject for token in BOUNCE_SUBJECT_HINTS):
        return True
    if any(token in from_text for token in BOUNCE_FROM_HINTS):
        return True
    if content_type == "multipart/report":
        return True
    for part in msg.walk():
        if (part.get_content_type() or "").lower() in {"message/delivery-status", "message/rfc822"}:
            return True
    return False


def _collect_text_parts(msg: Message) -> List[str]:
    texts: List[str] = []
    for part in msg.walk():
        ctype = (part.get_content_type() or "").lower()
        if ctype == "message/rfc822":
            payload = part.get_payload()
            nested_messages = payload if isinstance(payload, list) else [payload]
            for nested in nested_messages:
                if isinstance(nested, Message):
                    texts.extend(_collect_text_parts(nested))
                    for header_name in ("To", "Cc", "Delivered-To", "X-Failed-Recipients"):
                        header_text = _message_header_text(nested, header_name)
                        if header_text:
                            texts.append(f"{header_name}: {header_text}")
            continue
        if ctype not in {"text/plain", "text/html", "message/delivery-status"}:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            raw = part.get_payload()
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, Message):
                        texts.extend(_collect_text_parts(item))
            else:
                text = str(raw or "").strip()
                if text:
                    texts.append(text)
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except Exception:
            text = payload.decode("utf-8", errors="replace")
        if text.strip():
            texts.append(text)
    return texts


def _extract_emails_from_text(text: str) -> Set[str]:
    extracted: Set[str] = set()
    for pattern in (FINAL_RECIPIENT_RE, ORIGINAL_RECIPIENT_RE):
        extracted.update(norm_email(match) for match in pattern.findall(text or ""))
    for raw_value in FAILED_RECIPIENTS_RE.findall(text or ""):
        extracted.update(norm_email(match) for match in EMAIL_RE.findall(raw_value or ""))
    return {email for email in extracted if email}


def extract_bounced_recipients_from_message(msg: Message, mailbox_email: str = "") -> Set[str]:
    mailbox_norm = norm_email(mailbox_email)
    candidates: Set[str] = set()
    texts = _collect_text_parts(msg)
    for text in texts:
        candidates |= _extract_emails_from_text(text)

    if not candidates and is_probable_bounce_message(msg):
        fallback: Set[str] = set()
        for text in texts:
            fallback.update(norm_email(match) for match in EMAIL_RE.findall(text or ""))
        from_text = _message_header_text(msg, "From")
        fallback.discard(norm_email(from_text))
        candidates |= fallback

    filtered: Set[str] = set()
    for email_addr in candidates:
        if not email_addr or email_addr == mailbox_norm:
            continue
        localpart = email_addr.split("@", 1)[0]
        if localpart in SYSTEM_LOCALPARTS:
            continue
        filtered.add(email_addr)
    return filtered


def load_private_bounce_state(path: Path = PRIVATE_BOUNCE_STATE_PATH) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_private_bounce_state(path: Path, payload: Dict[str, object]) -> None:
    _write_json_atomic(path, payload)


def load_private_bounce_monitor_state(path: Path = PRIVATE_BOUNCE_MONITOR_PATH) -> Dict[str, object]:
    return load_private_bounce_state(path)


def save_private_bounce_monitor_state(path: Path, payload: Dict[str, object]) -> None:
    save_private_bounce_state(path, payload)


def load_simple_email_set(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return set()
        header_map = {str(name or "").strip().lower(): name for name in reader.fieldnames}
        email_header = header_map.get("email")
        if not email_header:
            return set()
        out: Set[str] = set()
        for row in reader:
            email_addr = norm_email(row.get(email_header, ""))
            if email_addr:
                out.add(email_addr)
        return out


def append_unique_suppressed_emails(path: Path, emails: Iterable[str]) -> Dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    header, existing_rows = _read_simple_email_rows(path)
    existing = {norm_email(email) for email in existing_rows if norm_email(email)}
    to_add: List[str] = []
    seen_new: Set[str] = set()
    for email in emails:
        email_addr = norm_email(email)
        if not email_addr or email_addr in existing or email_addr in seen_new:
            continue
        seen_new.add(email_addr)
        to_add.append(email_addr)
    if to_add or not path.exists():
        _write_simple_email_rows(path, header, existing_rows + to_add)
    return {
        "existing_before": len(existing),
        "added": len(to_add),
        "added_addresses": list(to_add),
        "existing_after": len(existing) + len(to_add),
    }


def _report_path(report_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return report_dir / f"{PRIVATE_BOUNCE_REPORT_PREFIX}{ts}.json"


def normalize_private_bounce_folders(folders: Optional[Sequence[str]] = None) -> List[str]:
    raw_items = list(folders or PRIVATE_BOUNCE_FOLDERS or ("INBOX",))
    normalized: List[str] = []
    seen: Set[str] = set()
    for raw in raw_items:
        for piece in str(raw or "").split(","):
            folder = piece.strip()
            if not folder:
                continue
            folded = folder.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            normalized.append(folder)
    return normalized or ["INBOX"]


def _imap_uids_after(imap: imaplib.IMAP4_SSL, last_uid: int, lookback_days: int) -> List[int]:
    if last_uid > 0:
        status, data = imap.uid("search", None, f"{last_uid + 1}:*")
    else:
        since_text = (datetime.now() - timedelta(days=max(1, lookback_days))).strftime("%d-%b-%Y")
        status, data = imap.uid("search", None, "SINCE", since_text)
    if status != "OK":
        raise RuntimeError("IMAP search failed.")
    raw = data[0] if data else b""
    return [int(token) for token in (raw or b"").split() if token]


def _fetch_message_by_uid(imap: imaplib.IMAP4_SSL, uid: int) -> Message:
    status, data = imap.uid("fetch", str(uid), "(RFC822)")
    if status != "OK" or not data:
        raise RuntimeError(f"IMAP fetch failed for UID {uid}.")
    for item in data:
        if not isinstance(item, tuple) or len(item) < 2:
            continue
        payload = item[1]
        if isinstance(payload, bytes):
            return BytesParser(policy=policy.default).parsebytes(payload)
    raise RuntimeError(f"Missing RFC822 payload for UID {uid}.")


def sync_private_bounces(
    profile_name: str = "private_jc",
    folder: str = "",
    folders: Optional[Sequence[str]] = None,
    lookback_days: int = 14,
    state_path: Path = PRIVATE_BOUNCE_STATE_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    report_dir: Path = settings.STATE_DIR,
    imap_host: str = PRIVATE_IMAP_HOST,
    imap_port: int = PRIVATE_IMAP_PORT,
    imap_timeout_seconds: int = PRIVATE_BOUNCE_IMAP_TIMEOUT_SECONDS,
    persist_state: bool = True,
) -> Dict[str, object]:
    profile = PROFILES.get(profile_name)
    if not profile:
        raise ValueError(f"Unknown profile: {profile_name}")
    if str(profile.get("provider") or "").strip().lower() != "private":
        raise ValueError(f"Profile {profile_name} is not a private-email sender.")

    mailbox_email = norm_email(str(profile.get("from_email") or ""))
    if not mailbox_email:
        raise ValueError(f"Profile {profile_name} is missing from_email.")
    password_env = str(profile.get("password_env") or "").strip()
    password = os.environ.get(password_env, "").strip()
    if not password:
        raise ValueError(f"{password_env or 'password env'} is not configured.")

    state = load_private_bounce_state(state_path)
    profile_state = state.get(profile_name, {}) if isinstance(state.get(profile_name), dict) else {}
    scan_folders = normalize_private_bounce_folders(folders if folders is not None else ([folder] if folder else None))
    legacy_last_uid = int(profile_state.get("last_uid", 0) or 0)
    raw_last_uid_by_folder = profile_state.get("last_uid_by_folder")
    last_uid_by_folder = dict(raw_last_uid_by_folder) if isinstance(raw_last_uid_by_folder, dict) else {}
    last_uid_before_map: Dict[str, int] = {}
    last_uid_after_map: Dict[str, int] = {}

    scanned_messages = 0
    probable_bounces = 0
    extracted_recipients: Set[str] = set()
    matched_messages: List[Dict[str, object]] = []
    extracted_recipient_events: List[Dict[str, object]] = []

    with imaplib.IMAP4_SSL(imap_host, imap_port, timeout=max(1, int(imap_timeout_seconds or 1))) as imap:
        login_status, _ = imap.login(mailbox_email, password)
        if login_status != "OK":
            raise RuntimeError("IMAP login failed.")
        for folder_name in scan_folders:
            folder_last_uid_before = int(last_uid_by_folder.get(folder_name, 0) or 0)
            if folder_last_uid_before <= 0 and folder_name == "INBOX" and legacy_last_uid > 0:
                folder_last_uid_before = legacy_last_uid
            last_uid_before_map[folder_name] = folder_last_uid_before

            select_status, _ = imap.select(folder_name, readonly=True)
            if select_status != "OK":
                raise RuntimeError(f"Unable to open mailbox folder: {folder_name}")

            max_uid_seen = folder_last_uid_before
            uids = _imap_uids_after(imap, folder_last_uid_before, lookback_days)
            for uid in uids:
                max_uid_seen = max(max_uid_seen, uid)
                msg = _fetch_message_by_uid(imap, uid)
                scanned_messages += 1
                is_bounce = is_probable_bounce_message(msg)
                recipients = extract_bounced_recipients_from_message(msg, mailbox_email=mailbox_email)
                if is_bounce:
                    probable_bounces += 1
                if not recipients:
                    continue
                extracted_recipients |= recipients
                detected_at_utc = _message_detected_at_utc(msg)
                matched_messages.append(
                    {
                        "folder": folder_name,
                        "uid": uid,
                        "subject": _message_header_text(msg, "Subject"),
                        "from": _message_header_text(msg, "From"),
                        "date": _message_header_text(msg, "Date"),
                        "detected_at_utc": detected_at_utc,
                        "recipients": sorted(recipients),
                    }
                )
                for email_addr in sorted(recipients):
                    extracted_recipient_events.append(
                        {
                            "email": email_addr,
                            "folder": folder_name,
                            "uid": uid,
                            "detected_at_utc": detected_at_utc,
                        }
                    )
            last_uid_after_map[folder_name] = max_uid_seen
        try:
            imap.logout()
        except Exception:
            pass

    suppress_result = append_unique_suppressed_emails(suppressed_path, extracted_recipients)

    report = {
        "generated_at_utc": iso_utc(datetime.now(timezone.utc)),
        "profile_name": profile_name,
        "mailbox_email": mailbox_email,
        "folder": folder,
        "folders": list(scan_folders),
        "imap_host": imap_host,
        "last_uid_before": max(last_uid_before_map.values(), default=legacy_last_uid),
        "last_uid_after": max(last_uid_after_map.values(), default=legacy_last_uid),
        "last_uid_before_by_folder": last_uid_before_map,
        "last_uid_after_by_folder": last_uid_after_map,
        "scanned_messages": scanned_messages,
        "probable_bounce_messages": probable_bounces,
        "matched_messages": len(matched_messages),
        "extracted_recipients": len(extracted_recipients),
        "extracted_recipient_list": sorted(extracted_recipients),
        "extracted_recipient_events": extracted_recipient_events,
        "added_suppressed": suppress_result["added"],
        "added_suppressed_addresses": list(suppress_result.get("added_addresses") or []),
        "already_suppressed": max(0, len(extracted_recipients) - suppress_result["added"]),
        "suppressed_total": suppress_result["existing_after"],
        "matched_message_preview": matched_messages[:8],
    }

    report_path = _report_path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(report_path)
    _write_json_atomic(report_path, report)

    if persist_state:
        state[profile_name] = {
            "last_uid": last_uid_after_map.get("INBOX", legacy_last_uid),
            "last_uid_by_folder": last_uid_after_map,
            "last_sync_utc": report["generated_at_utc"],
            "last_report_path": str(report_path),
        }
        save_private_bounce_state(state_path, state)

    return report


def _default_monitor_profile_state(profile_name: str) -> Dict[str, object]:
    return {
        "profile_name": profile_name,
        "enabled": True,
        "interval_seconds": PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS,
        "window_minutes": PRIVATE_BOUNCE_CLUSTER_WINDOW_MINUTES,
        "bounce_threshold": PRIVATE_BOUNCE_CLUSTER_THRESHOLD,
        "cooldown_minutes": PRIVATE_BOUNCE_COOLDOWN_MINUTES,
        "lookback_days": PRIVATE_BOUNCE_LOOKBACK_DAYS,
        "last_sync_utc": "",
        "last_success_utc": "",
        "last_error": "",
        "last_error_utc": "",
        "last_report_path": "",
        "last_scanned_messages": 0,
        "last_probable_bounce_messages": 0,
        "last_matched_messages": 0,
        "last_extracted_recipients": 0,
        "last_added_suppressed": 0,
        "last_suppressed_addresses": [],
        "recent_events": [],
        "events": [],
        "window_reset_utc": "",
        "cooldown_active": False,
        "cooldown_started_utc": "",
        "cooldown_until_utc": "",
        "last_cluster_count": 0,
        "last_cluster_preview": [],
        "last_cluster_at_utc": "",
        "last_action": "",
        "last_action_message": "",
        "last_action_utc": "",
    }


def _coerce_monitor_profile_state(state: Dict[str, object], profile_name: str) -> Dict[str, object]:
    current = state.get(profile_name)
    payload = dict(current) if isinstance(current, dict) else {}
    for key, value in _default_monitor_profile_state(profile_name).items():
        payload.setdefault(key, value)
    payload["profile_name"] = profile_name
    state[profile_name] = payload
    return payload


def _recent_event_retention_hours(window_minutes: int, cooldown_minutes: int) -> int:
    return max(24, int((max(1, window_minutes) * 6) / 60), int((max(1, cooldown_minutes) * 6) / 60))


def _prune_recent_events(
    events: Sequence[Dict[str, object]],
    *,
    now: datetime,
    window_minutes: int,
    cooldown_minutes: int,
) -> List[Dict[str, object]]:
    cutoff = now - timedelta(hours=_recent_event_retention_hours(window_minutes, cooldown_minutes))
    pruned: List[Dict[str, object]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        email = norm_email(str(event.get("email") or ""))
        detected_at = parse_iso_utc(str(event.get("detected_at_utc") or ""))
        if not email or not detected_at or detected_at < cutoff:
            continue
        pruned.append(
            {
                "email": email,
                "detected_at_utc": iso_utc(detected_at),
                "report_path": str(event.get("report_path") or ""),
            }
        )
    pruned.sort(key=lambda item: str(item.get("detected_at_utc") or ""), reverse=True)
    return pruned


def _append_recent_bounce_events(profile_state: Dict[str, object], report: Dict[str, object]) -> None:
    detected_at = str(report.get("generated_at_utc") or "").strip()
    if not detected_at:
        return
    events = profile_state.get("recent_events")
    if not isinstance(events, list):
        events = []
    existing = {
        (norm_email(str(item.get("email") or "")), str(item.get("detected_at_utc") or ""))
        for item in events
        if isinstance(item, dict)
    }
    recipient_events = list(report.get("extracted_recipient_events") or [])
    if recipient_events:
        candidate_rows = recipient_events
    else:
        candidate_rows = [{"email": raw_email, "detected_at_utc": detected_at} for raw_email in (report.get("extracted_recipient_list", []) or [])]
    for row in candidate_rows:
        email_addr = norm_email(str((row or {}).get("email") or ""))
        if not email_addr:
            continue
        event_detected_at = str((row or {}).get("detected_at_utc") or detected_at).strip() or detected_at
        fingerprint = (email_addr, event_detected_at)
        if fingerprint in existing:
            continue
        existing.add(fingerprint)
        events.append(
            {
                "email": email_addr,
                "detected_at_utc": event_detected_at,
                "report_path": str(report.get("report_path") or ""),
            }
        )
    profile_state["recent_events"] = events


def _clear_cooldown(profile_state: Dict[str, object]) -> None:
    profile_state["cooldown_active"] = False
    profile_state["cooldown_started_utc"] = ""
    profile_state["cooldown_until_utc"] = ""


def _append_monitor_event(
    profile_state: Dict[str, object],
    *,
    event_type: str,
    title: str,
    message: str,
    severity: str = "info",
    occurred_at: Optional[datetime] = None,
    addresses: Optional[Sequence[str]] = None,
    report_path: str = "",
    cooldown_until_utc: str = "",
) -> None:
    events = profile_state.get("events")
    if not isinstance(events, list):
        events = []
    at_utc = iso_utc((occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc))
    event = {
        "event_type": event_type,
        "title": title,
        "message": message,
        "severity": severity,
        "occurred_at_utc": at_utc,
        "addresses": [norm_email(str(item or "")) for item in (addresses or []) if norm_email(str(item or ""))],
        "report_path": report_path,
        "cooldown_until_utc": cooldown_until_utc,
    }
    events.insert(0, event)
    profile_state["events"] = events[: max(10, PRIVATE_BOUNCE_EVENT_HISTORY_LIMIT)]


def _active_bounce_window_events(
    profile_state: Dict[str, object],
    *,
    now: datetime,
    window_minutes: int,
) -> List[Dict[str, object]]:
    reset_at = parse_iso_utc(str(profile_state.get("window_reset_utc") or ""))
    cutoff = now - timedelta(minutes=max(1, window_minutes))
    if reset_at and reset_at > cutoff:
        cutoff = reset_at
    recent_events = profile_state.get("recent_events")
    if not isinstance(recent_events, list):
        return []
    active_events: List[Dict[str, object]] = []
    for event in recent_events:
        if not isinstance(event, dict):
            continue
        detected_at = parse_iso_utc(str(event.get("detected_at_utc") or ""))
        if detected_at and detected_at >= cutoff:
            active_events.append(event)
    active_events.sort(key=lambda item: str(item.get("detected_at_utc") or ""), reverse=True)
    return active_events


def private_bounce_guard_status(
    profile_name: str = "private_jc",
    *,
    monitor_path: Path = PRIVATE_BOUNCE_MONITOR_PATH,
    profile_active: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    now_dt = now or datetime.now(timezone.utc)
    state = load_private_bounce_monitor_state(monitor_path)
    profile_state = _coerce_monitor_profile_state(state, profile_name)
    window_minutes = max(1, int(profile_state.get("window_minutes") or PRIVATE_BOUNCE_CLUSTER_WINDOW_MINUTES))
    cooldown_minutes = max(1, int(profile_state.get("cooldown_minutes") or PRIVATE_BOUNCE_COOLDOWN_MINUTES))
    interval_seconds = max(30, int(profile_state.get("interval_seconds") or PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS))
    bounce_threshold = max(1, int(profile_state.get("bounce_threshold") or PRIVATE_BOUNCE_CLUSTER_THRESHOLD))
    profile_state["recent_events"] = _prune_recent_events(
        profile_state.get("recent_events", []),  # type: ignore[arg-type]
        now=now_dt,
        window_minutes=window_minutes,
        cooldown_minutes=cooldown_minutes,
    )
    raw_events = profile_state.get("events")
    event_rows = list(raw_events) if isinstance(raw_events, list) else []
    recent_window_events = _active_bounce_window_events(profile_state, now=now_dt, window_minutes=window_minutes)

    last_sync = parse_iso_utc(str(profile_state.get("last_sync_utc") or ""))
    last_success = parse_iso_utc(str(profile_state.get("last_success_utc") or ""))
    last_error = str(profile_state.get("last_error") or "").strip()
    last_error_utc = parse_iso_utc(str(profile_state.get("last_error_utc") or ""))
    cooldown_until = parse_iso_utc(str(profile_state.get("cooldown_until_utc") or ""))
    cooldown_active = bool(profile_state.get("cooldown_active")) and bool(cooldown_until and cooldown_until > now_dt)
    sync_error_active = bool(last_error) and bool(last_error_utc and (not last_success or last_error_utc >= last_success))
    last_sync_age_seconds = int((now_dt - last_sync).total_seconds()) if last_sync else None
    sync_stale = last_sync_age_seconds is None or last_sync_age_seconds > interval_seconds * 3
    cooldown_remaining_seconds = max(0, int((cooldown_until - now_dt).total_seconds())) if cooldown_active and cooldown_until else 0

    if not bool(profile_state.get("enabled", True)):
        status = "disabled"
        status_label = "Off"
        status_note = "Automatic private bounce sync is disabled."
    elif cooldown_active:
        status = "cooldown"
        status_label = "Cooldown"
        status_note = (
            f"JC is paused for clustered private bounces. Resume in about "
            f"{max(1, int((cooldown_remaining_seconds + 59) / 60))} minute(s)."
        )
    elif sync_error_active:
        status = "error"
        status_label = "Sync Error"
        status_note = last_error or "Private bounce sync failed."
    elif profile_active:
        status = "watching"
        status_label = "Watching"
        status_note = "Automatic private bounce sync is active while JC is running."
    else:
        status = "idle"
        status_label = "Idle"
        status_note = "Automatic private bounce sync is armed and waiting for the next interval."

    return {
        "profile_name": profile_name,
        "enabled": bool(profile_state.get("enabled", True)),
        "status": status,
        "status_label": status_label,
        "status_note": status_note,
        "profile_active": profile_active,
        "interval_seconds": interval_seconds,
        "window_minutes": window_minutes,
        "bounce_threshold": bounce_threshold,
        "cooldown_minutes": cooldown_minutes,
        "cooldown_active": cooldown_active,
        "cooldown_until_utc": iso_utc(cooldown_until) if cooldown_until else "",
        "cooldown_remaining_seconds": cooldown_remaining_seconds,
        "last_sync_utc": iso_utc(last_sync) if last_sync else "",
        "last_success_utc": iso_utc(last_success) if last_success else "",
        "last_sync_age_seconds": last_sync_age_seconds,
        "last_error": last_error,
        "last_error_utc": iso_utc(last_error_utc) if last_error_utc else "",
        "sync_error_active": sync_error_active,
        "sync_stale": sync_stale,
        "last_report_path": str(profile_state.get("last_report_path") or ""),
        "last_scanned_messages": int(profile_state.get("last_scanned_messages") or 0),
        "last_probable_bounce_messages": int(profile_state.get("last_probable_bounce_messages") or 0),
        "last_matched_messages": int(profile_state.get("last_matched_messages") or 0),
        "last_extracted_recipients": int(profile_state.get("last_extracted_recipients") or 0),
        "last_added_suppressed": int(profile_state.get("last_added_suppressed") or 0),
        "last_suppressed_addresses": list(profile_state.get("last_suppressed_addresses") or []),
        "recent_bounces_window": len(recent_window_events),
        "recent_bounce_preview": [str(event.get("email") or "") for event in recent_window_events[:5]],
        "last_cluster_count": int(profile_state.get("last_cluster_count") or 0),
        "last_cluster_preview": list(profile_state.get("last_cluster_preview") or []),
        "last_cluster_at_utc": str(profile_state.get("last_cluster_at_utc") or ""),
        "last_action": str(profile_state.get("last_action") or ""),
        "last_action_message": str(profile_state.get("last_action_message") or ""),
        "last_action_utc": str(profile_state.get("last_action_utc") or ""),
        "events": list(event_rows[:10]),
    }


def run_private_bounce_monitor_cycle(
    profile_name: str = "private_jc",
    *,
    monitor_path: Path = PRIVATE_BOUNCE_MONITOR_PATH,
    sync_state_path: Path = PRIVATE_BOUNCE_STATE_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    report_dir: Path = settings.STATE_DIR,
    enabled: bool = PRIVATE_BOUNCE_MONITOR_ENABLED,
    interval_seconds: int = PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS,
    window_minutes: int = PRIVATE_BOUNCE_CLUSTER_WINDOW_MINUTES,
    bounce_threshold: int = PRIVATE_BOUNCE_CLUSTER_THRESHOLD,
    cooldown_minutes: int = PRIVATE_BOUNCE_COOLDOWN_MINUTES,
    lookback_days: int = PRIVATE_BOUNCE_LOOKBACK_DAYS,
    profile_active: bool = False,
    now: Optional[datetime] = None,
    sync_func=sync_private_bounces,
    stop_profile=None,
    start_profile=None,
) -> Dict[str, object]:
    now_dt = now or datetime.now(timezone.utc)
    state = load_private_bounce_monitor_state(monitor_path)
    profile_state = _coerce_monitor_profile_state(state, profile_name)
    profile_state["enabled"] = bool(enabled)
    profile_state["interval_seconds"] = max(30, int(interval_seconds or PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS))
    profile_state["window_minutes"] = max(1, int(window_minutes or PRIVATE_BOUNCE_CLUSTER_WINDOW_MINUTES))
    profile_state["bounce_threshold"] = max(1, int(bounce_threshold or PRIVATE_BOUNCE_CLUSTER_THRESHOLD))
    profile_state["cooldown_minutes"] = max(1, int(cooldown_minutes or PRIVATE_BOUNCE_COOLDOWN_MINUTES))
    profile_state["lookback_days"] = max(1, int(lookback_days or PRIVATE_BOUNCE_LOOKBACK_DAYS))

    last_sync = parse_iso_utc(str(profile_state.get("last_sync_utc") or ""))
    sync_due = bool(enabled) and (
        last_sync is None
        or (now_dt - last_sync).total_seconds() >= int(profile_state["interval_seconds"])
    )

    if sync_due:
        try:
            report = sync_func(
                profile_name=profile_name,
                lookback_days=int(profile_state["lookback_days"]),
                state_path=sync_state_path,
                suppressed_path=suppressed_path,
                report_dir=report_dir,
            )
            profile_state["last_sync_utc"] = str(report.get("generated_at_utc") or iso_utc(now_dt))
            profile_state["last_success_utc"] = profile_state["last_sync_utc"]
            profile_state["last_error"] = ""
            profile_state["last_error_utc"] = ""
            profile_state["last_report_path"] = str(report.get("report_path") or "")
            profile_state["last_scanned_messages"] = int(report.get("scanned_messages", 0) or 0)
            profile_state["last_probable_bounce_messages"] = int(report.get("probable_bounce_messages", 0) or 0)
            profile_state["last_matched_messages"] = int(report.get("matched_messages", 0) or 0)
            profile_state["last_extracted_recipients"] = int(report.get("extracted_recipients", 0) or 0)
            profile_state["last_added_suppressed"] = int(report.get("added_suppressed", 0) or 0)
            profile_state["last_suppressed_addresses"] = list(report.get("added_suppressed_addresses") or [])
            _append_recent_bounce_events(profile_state, report)
            _append_monitor_event(
                profile_state,
                event_type="sync_completed",
                title="Sync completed",
                message=(
                    f"Scanned {int(report.get('scanned_messages', 0) or 0)} message(s); "
                    f"matched {int(report.get('matched_messages', 0) or 0)} bounce(s)."
                ),
                occurred_at=parse_iso_utc(str(report.get("generated_at_utc") or "")) or now_dt,
                report_path=str(report.get("report_path") or ""),
            )
            added_addresses = list(report.get("added_suppressed_addresses") or [])
            if added_addresses:
                _append_monitor_event(
                    profile_state,
                    event_type="suppression_added",
                    title="Suppression added",
                    message=(
                        f"Suppressed {len(added_addresses)} bounced address(es) from the JC mailbox sync."
                    ),
                    severity="warn",
                    occurred_at=parse_iso_utc(str(report.get("generated_at_utc") or "")) or now_dt,
                    addresses=added_addresses,
                    report_path=str(report.get("report_path") or ""),
                )
        except Exception as exc:
            profile_state["last_sync_utc"] = iso_utc(now_dt)
            profile_state["last_error"] = str(exc)
            profile_state["last_error_utc"] = iso_utc(now_dt)
            profile_state["last_scanned_messages"] = 0
            profile_state["last_probable_bounce_messages"] = 0
            profile_state["last_matched_messages"] = 0
            profile_state["last_extracted_recipients"] = 0
            profile_state["last_added_suppressed"] = 0
            profile_state["last_suppressed_addresses"] = []
            _append_monitor_event(
                profile_state,
                event_type="sync_error",
                title="Sync error",
                message=str(exc),
                severity="error",
                occurred_at=now_dt,
            )

    profile_state["recent_events"] = _prune_recent_events(
        profile_state.get("recent_events", []),  # type: ignore[arg-type]
        now=now_dt,
        window_minutes=int(profile_state["window_minutes"]),
        cooldown_minutes=int(profile_state["cooldown_minutes"]),
    )
    recent_window_events = _active_bounce_window_events(
        profile_state,
        now=now_dt,
        window_minutes=int(profile_state["window_minutes"]),
    )

    cooldown_until = parse_iso_utc(str(profile_state.get("cooldown_until_utc") or ""))
    cooldown_active = bool(profile_state.get("cooldown_active")) and bool(cooldown_until and cooldown_until > now_dt)
    if bool(profile_state.get("cooldown_active")) and cooldown_until and cooldown_until <= now_dt:
        if profile_active:
            _clear_cooldown(profile_state)
            profile_state["window_reset_utc"] = iso_utc(now_dt)
            profile_state["last_action"] = "cooldown_cleared"
            profile_state["last_action_message"] = "JC was already running when the automatic cooldown ended."
            profile_state["last_action_utc"] = iso_utc(now_dt)
            _append_monitor_event(
                profile_state,
                event_type="cooldown_ended",
                title="Cooldown ended",
                message="JC cooldown window ended while the sender was already running.",
                severity="info",
                occurred_at=now_dt,
            )
        elif start_profile is not None:
            ok, message = start_profile(profile_name)
            profile_state["last_action"] = "auto_resumed" if ok or "already running" in message.lower() else "auto_resume_failed"
            profile_state["last_action_message"] = message
            profile_state["last_action_utc"] = iso_utc(now_dt)
            if ok or "already running" in message.lower():
                _clear_cooldown(profile_state)
                profile_state["window_reset_utc"] = iso_utc(now_dt)
                profile_active = True
                _append_monitor_event(
                    profile_state,
                    event_type="cooldown_ended",
                    title="Cooldown ended",
                    message=message or "JC resumed automatically after private bounce cooldown.",
                    severity="info",
                    occurred_at=now_dt,
                )
            else:
                profile_state["last_error"] = message
                profile_state["last_error_utc"] = iso_utc(now_dt)
                _append_monitor_event(
                    profile_state,
                    event_type="resume_error",
                    title="Auto-resume failed",
                    message=message,
                    severity="error",
                    occurred_at=now_dt,
                )
        cooldown_until = parse_iso_utc(str(profile_state.get("cooldown_until_utc") or ""))
        cooldown_active = bool(profile_state.get("cooldown_active")) and bool(cooldown_until and cooldown_until > now_dt)
        recent_window_events = _active_bounce_window_events(
            profile_state,
            now=now_dt,
            window_minutes=int(profile_state["window_minutes"]),
        )

    if cooldown_active and profile_active and stop_profile is not None:
        ok, message = stop_profile(profile_name)
        profile_state["last_action"] = "cooldown_enforced" if ok else "cooldown_enforce_failed"
        profile_state["last_action_message"] = message
        profile_state["last_action_utc"] = iso_utc(now_dt)
        if not ok:
            profile_state["last_error"] = message
            profile_state["last_error_utc"] = iso_utc(now_dt)
            _append_monitor_event(
                profile_state,
                event_type="cooldown_enforce_error",
                title="Cooldown enforcement failed",
                message=message,
                severity="error",
                occurred_at=now_dt,
            )

    if (
        bool(enabled)
        and not cooldown_active
        and profile_active
        and len(recent_window_events) >= int(profile_state["bounce_threshold"])
    ):
        preview = [str(event.get("email") or "") for event in recent_window_events[:5]]
        if stop_profile is not None:
            ok, message = stop_profile(profile_name)
        else:
            ok, message = False, "Automatic cooldown requested but no stop callback is configured."
        profile_state["last_cluster_count"] = len(recent_window_events)
        profile_state["last_cluster_preview"] = preview
        profile_state["last_cluster_at_utc"] = iso_utc(now_dt)
        profile_state["last_action_utc"] = iso_utc(now_dt)
        if ok:
            profile_state["cooldown_active"] = True
            profile_state["cooldown_started_utc"] = iso_utc(now_dt)
            profile_state["cooldown_until_utc"] = iso_utc(now_dt + timedelta(minutes=int(profile_state["cooldown_minutes"])))
            profile_state["last_action"] = "cooldown_started"
            profile_state["last_action_message"] = (
                f"{message} Private bounce cluster detected: {len(recent_window_events)} bounce(s) in "
                f"{int(profile_state['window_minutes'])} minute(s)."
            ).strip()
            _append_monitor_event(
                profile_state,
                event_type="cooldown_started",
                title="Cooldown started",
                message=profile_state["last_action_message"],
                severity="warn",
                occurred_at=now_dt,
                addresses=preview,
                cooldown_until_utc=str(profile_state.get("cooldown_until_utc") or ""),
            )
        else:
            profile_state["last_action"] = "cooldown_failed"
            profile_state["last_action_message"] = message
            profile_state["last_error"] = message
            profile_state["last_error_utc"] = iso_utc(now_dt)
            _append_monitor_event(
                profile_state,
                event_type="cooldown_error",
                title="Cooldown start failed",
                message=message,
                severity="error",
                occurred_at=now_dt,
                addresses=preview,
            )

    save_private_bounce_monitor_state(monitor_path, state)
    return private_bounce_guard_status(
        profile_name=profile_name,
        monitor_path=monitor_path,
        profile_active=profile_active,
        now=now_dt,
    )
