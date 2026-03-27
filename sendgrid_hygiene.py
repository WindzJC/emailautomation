from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo


TIMESTAMP_RE = re.compile(r"^[A-Za-z]+ \d{1,2}, \d{4} \d{2}:\d{2}:\d{2} [AP]M$")
MULTILINE_TS_FORMATS = ("%B %d, %Y %I:%M:%S %p", "%b %d, %Y %I:%M:%S %p")

EVENT_HEADERS = [
    "processed_at_raw",
    "processed_at_utc",
    "received_at_utc",
    "message_id",
    "event_id",
    "dedupe_key",
    "email",
    "domain",
    "subject",
    "status",
    "bounce_classification",
    "code",
    "response",
    "url",
    "attempt",
    "source_log",
]

WEBHOOK_EVENTS_JSONL = "sendgrid_events.jsonl"
WEBHOOK_DEDUPE_DB = "sendgrid_webhook_dedupe.sqlite3"
WEBHOOK_DEDUPE_TTL_DAYS = 30

SUPPRESSION_HEADERS = [
    "email",
    "status",
    "code",
    "reason",
    "last_seen_utc",
    "is_permanent",
    "ttl_until_utc",
]

PERMANENT_BLOCK_PATTERNS = (
    "mailbox disabled",
    "recipient not found",
    "user unknown",
)

TEMPORARY_BLOCK_PATTERNS = (
    "mailbox full",
    "over quota",
    "quota exceeded",
)

PERMANENT_FAILURE_STATUSES = {
    "bounce",
    "bounced",
    "dropped",
    "drop",
    "spam report",
    "spam_report",
    "spamreport",
    "unsubscribe",
    "unsubscribed",
}

POSITIVE_STATUSES = {
    "delivered",
    "opened",
    "open",
    "clicked",
    "click",
}

NON_SUPPRESSION_STATUSES = {
    "processed",
    "deferred",
    "group_resubscribe",
    "resubscribe",
}


def norm_email(value: str) -> str:
    return (value or "").strip().lower()


def domain_from_email(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_utc(value: str) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _local_timezone() -> ZoneInfo:
    local = datetime.now().astimezone().tzinfo
    if isinstance(local, ZoneInfo):
        return local
    key = getattr(local, "key", None)
    if key:
        return ZoneInfo(key)
    return ZoneInfo("UTC")


def resolve_timezone(value: str = "") -> ZoneInfo:
    raw = (value or "").strip()
    if not raw:
        return _local_timezone()
    return ZoneInfo(raw)


def parse_processed_at(raw: str, source_tz: ZoneInfo) -> datetime:
    text = (raw or "").strip()
    for fmt in MULTILINE_TS_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=source_tz).astimezone(timezone.utc)
        except ValueError:
            continue
    parsed = parse_iso_utc(text)
    if parsed:
        return parsed
    raise ValueError(f"Unsupported processed-at timestamp: {raw}")


def _event_record(
    processed_at_raw: str,
    processed_at_utc: datetime,
    message_id: str,
    email: str,
    subject: str,
    status: str,
    code: str,
    response: str,
    source_log: str,
) -> Dict[str, str]:
    email_norm = norm_email(email)
    response_text = (response or "").strip()
    return {
        "processed_at_raw": (processed_at_raw or "").strip(),
        "processed_at_utc": iso_utc(processed_at_utc),
        "message_id": (message_id or "").strip(),
        "email": email_norm,
        "domain": domain_from_email(email_norm),
        "subject": (subject or "").strip(),
        "status": (status or "").strip(),
        "code": (code or "").strip(),
        "response": response_text,
        "source_log": (source_log or "").strip(),
    }


def _first_present(row: Dict[str, str], aliases: Sequence[str]) -> str:
    normalized = {normalize_header(k): v for k, v in row.items()}
    for alias in aliases:
        value = normalized.get(alias)
        if value is not None:
            return str(value).strip()
    return ""


def _extract_code(code_value: str, response_value: str) -> str:
    code = (code_value or "").strip()
    if code:
        return code
    match = re.search(r"\b(\d{3})\b", response_value or "")
    return match.group(1) if match else ""


def parse_activity_csv(path: Path, source_tz: ZoneInfo) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            processed_at_raw = _first_present(row, ("processedat", "processed_at"))
            email = _first_present(row, ("recipientemail", "recipient", "to"))
            if not processed_at_raw or not email:
                continue
            response = _first_present(row, ("response", "reason"))
            processed_at_utc = parse_processed_at(processed_at_raw, source_tz)
            code = _extract_code(
                _first_present(row, ("smtpcode", "smtpresponsecode", "responsecode", "code")),
                response,
            )
            events.append(
                _event_record(
                    processed_at_raw=processed_at_raw,
                    processed_at_utc=processed_at_utc,
                    message_id=_first_present(row, ("messageid", "message_id", "msgid")),
                    email=email,
                    subject=_first_present(row, ("subjectline", "subject")),
                    status=_first_present(row, ("status",)),
                    code=code,
                    response=response,
                    source_log=path.name,
                )
            )
    return events


def parse_activity_multiline_text(
    text: str,
    source_log: str,
    source_tz: ZoneInfo,
) -> List[Dict[str, str]]:
    lines = [line.rstrip("\r") for line in text.splitlines()]
    events: List[Dict[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip().lstrip("\ufeff")
        if not line or line.lower() == "processed at":
            index += 1
            continue
        if not TIMESTAMP_RE.match(line):
            index += 1
            continue
        processed_at_raw = line
        processed_at_utc = parse_processed_at(processed_at_raw, source_tz)
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break
        metadata_line = lines[index]
        index += 1
        metadata_parts = metadata_line.split("\t")
        if len(metadata_parts) < 2:
            continue
        message_id = metadata_parts[0].strip()
        email = metadata_parts[1].strip()
        subject = "\t".join(metadata_parts[2:]).strip()
        while index < len(lines) and not lines[index].strip():
            index += 1
        status = lines[index].strip() if index < len(lines) else ""
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        code = lines[index].strip() if index < len(lines) else ""
        index += 1
        response_lines: List[str] = []
        while index < len(lines):
            candidate = lines[index].strip()
            if TIMESTAMP_RE.match(candidate):
                break
            if candidate and candidate.lower() != "processed at":
                response_lines.append(lines[index].strip())
            index += 1
        response = "\n".join(response_lines).strip()
        events.append(
            _event_record(
                processed_at_raw=processed_at_raw,
                processed_at_utc=processed_at_utc,
                message_id=message_id,
                email=email,
                subject=subject,
                status=status,
                code=code,
                response=response,
                source_log=source_log,
            )
        )
    return events


def parse_activity_file(path: Path, source_timezone: str = "") -> List[Dict[str, str]]:
    source_tz = resolve_timezone(source_timezone)
    if path.suffix.lower() == ".csv":
        return parse_activity_csv(path, source_tz)
    text = path.read_text(encoding="utf-8-sig")
    stripped = [line.strip() for line in text.splitlines() if line.strip()]
    if stripped:
        first = stripped[0].lstrip("\ufeff")
        second = stripped[1] if len(stripped) > 1 else ""
        if first.lower().startswith("processed at\t") and TIMESTAMP_RE.match(second):
            return parse_activity_multiline_text(text, path.name, source_tz)
        if first.lower().startswith("processed at,"):
            temp = Path(str(path) + ".csv-probe")
            try:
                return parse_activity_csv(path, source_tz)
            except Exception:
                pass
    return parse_activity_multiline_text(text, path.name, source_tz)


def _parse_epoch_timestamp(value: object) -> Optional[datetime]:
    try:
        if value is None:
            return None
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except Exception:
        return None


def _webhook_dedupe_fingerprint(event: Dict[str, str]) -> str:
    payload = {
        "message_id": (event.get("message_id") or "").strip(),
        "status": (event.get("status") or "").strip().lower(),
        "email": norm_email(event.get("email") or ""),
        "processed_at_utc": (event.get("processed_at_utc") or "").strip(),
        "response": re.sub(r"\s+", " ", (event.get("response") or "").strip()),
        "url": (event.get("url") or "").strip(),
        "attempt": (event.get("attempt") or "").strip(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compute_webhook_dedupe_key(event: Dict[str, str]) -> str:
    event_id = (event.get("event_id") or "").strip()
    if event_id:
        return f"sg_event_id:{event_id}"
    return f"fp:{_webhook_dedupe_fingerprint(event)}"


def normalize_webhook_event(
    event: Dict[str, object],
    source_log: str = WEBHOOK_EVENTS_JSONL,
    received_at_utc: Optional[datetime] = None,
) -> Optional[Dict[str, str]]:
    email = norm_email(str(event.get("email") or ""))
    if not email:
        return None
    raw_event = str(event.get("event") or "").strip()
    if not raw_event:
        return None
    processed_dt = _parse_epoch_timestamp(event.get("timestamp")) or now_utc()
    response = str(
        event.get("reason")
        or event.get("response")
        or event.get("status")
        or event.get("smtp-id")
        or ""
    ).strip()
    code = _extract_code(str(event.get("status") or ""), response)
    record = _event_record(
        processed_at_raw=str(event.get("timestamp") or ""),
        processed_at_utc=processed_dt,
        message_id=str(event.get("sg_message_id") or event.get("smtp-id") or ""),
        email=email,
        subject=str(event.get("subject") or ""),
        status=raw_event,
        code=code,
        response=response,
        source_log=source_log,
    )
    record["received_at_utc"] = iso_utc(received_at_utc or now_utc())
    event_id = str(event.get("sg_event_id") or event.get("event_id") or "").strip()
    url = str(event.get("url") or "").strip()
    attempt = str(event.get("attempt") or "").strip()
    if event_id:
        record["event_id"] = event_id
    if url:
        record["url"] = url
    if attempt:
        record["attempt"] = attempt
    bounce_classification = str(event.get("bounce_classification") or event.get("bounce classification") or "").strip()
    if bounce_classification:
        record["bounce_classification"] = bounce_classification
    profile = ""
    from_email = ""
    shard = ""
    provider = ""
    arg_sources = [source for source in (event.get("custom_args"), event.get("unique_args"), event) if isinstance(source, dict)]
    for source in arg_sources:
        if not profile:
            profile = str(source.get("profile") or "").strip()
        if not from_email:
            from_email = norm_email(str(source.get("from_email") or source.get("from") or ""))
        if not shard:
            shard = str(source.get("shard") or "").strip()
        if not provider:
            provider = str(source.get("provider") or "").strip()
    if profile:
        record["profile"] = profile
    if from_email:
        record["from_email"] = from_email
    if shard:
        record["shard"] = shard
    if provider:
        record["provider"] = provider
    record["dedupe_key"] = compute_webhook_dedupe_key(record)
    return record

def normalize_webhook_events(
    events: Iterable[Dict[str, object]],
    source_log: str = WEBHOOK_EVENTS_JSONL,
    received_at_utc: Optional[datetime] = None,
) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for event in events:
        row = normalize_webhook_event(event, source_log=source_log, received_at_utc=received_at_utc)
        if row:
            normalized.append(row)
    return normalized


def write_events_jsonl(events: Iterable[Dict[str, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def append_events_jsonl(events: Iterable[Dict[str, str]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")
            count += 1
    return count


def load_events_jsonl(path: Path) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    if not path.exists():
        return events
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            events.append(json.loads(raw))
    return events


def _connect_webhook_dedupe_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_event_dedupe (
            dedupe_key TEXT PRIMARY KEY,
            event_id TEXT NOT NULL DEFAULT '',
            message_id TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            processed_at_utc TEXT NOT NULL DEFAULT '',
            first_received_utc TEXT NOT NULL,
            last_received_utc TEXT NOT NULL,
            expires_at_utc TEXT NOT NULL,
            duplicate_hits INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_duplicate_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedupe_key TEXT NOT NULL,
            seen_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_event_dedupe_expires_at ON webhook_event_dedupe(expires_at_utc)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_duplicate_hits_seen_at ON webhook_duplicate_hits(seen_at_utc)"
    )
    return conn


def _prune_webhook_dedupe_store(
    conn: sqlite3.Connection,
    reference_utc: datetime,
    ttl_days: int = WEBHOOK_DEDUPE_TTL_DAYS,
) -> None:
    expiry_cutoff = iso_utc(reference_utc)
    duplicate_cutoff = iso_utc(reference_utc - timedelta(days=max(1, ttl_days)))
    conn.execute("DELETE FROM webhook_event_dedupe WHERE expires_at_utc < ?", (expiry_cutoff,))
    conn.execute("DELETE FROM webhook_duplicate_hits WHERE seen_at_utc < ?", (duplicate_cutoff,))


def dedupe_webhook_events(
    events: Iterable[Dict[str, str]],
    path: Path,
    ttl_days: int = WEBHOOK_DEDUPE_TTL_DAYS,
    reference_utc: Optional[datetime] = None,
) -> Dict[str, object]:
    reference = reference_utc or now_utc()
    expires_at = iso_utc(reference + timedelta(days=max(1, ttl_days)))
    received_events = list(events)
    unique_events: List[Dict[str, str]] = []
    duplicates = 0

    with _connect_webhook_dedupe_db(path) as conn:
        _prune_webhook_dedupe_store(conn, reference, ttl_days=ttl_days)
        for event in received_events:
            dedupe_key = (event.get("dedupe_key") or "").strip() or compute_webhook_dedupe_key(event)
            event["dedupe_key"] = dedupe_key
            received_at = (event.get("received_at_utc") or "").strip() or iso_utc(reference)
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO webhook_event_dedupe (
                    dedupe_key,
                    event_id,
                    message_id,
                    email,
                    status,
                    processed_at_utc,
                    first_received_utc,
                    last_received_utc,
                    expires_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    (event.get("event_id") or "").strip(),
                    (event.get("message_id") or "").strip(),
                    norm_email(event.get("email") or ""),
                    (event.get("status") or "").strip(),
                    (event.get("processed_at_utc") or "").strip(),
                    received_at,
                    received_at,
                    expires_at,
                ),
            )
            if cursor.rowcount:
                unique_events.append(event)
                continue

            duplicates += 1
            conn.execute(
                """
                UPDATE webhook_event_dedupe
                SET last_received_utc = ?, duplicate_hits = duplicate_hits + 1, expires_at_utc = ?
                WHERE dedupe_key = ?
                """,
                (received_at, expires_at, dedupe_key),
            )
            conn.execute(
                "INSERT INTO webhook_duplicate_hits (dedupe_key, seen_at_utc) VALUES (?, ?)",
                (dedupe_key, received_at),
            )

    return {
        "unique_events": unique_events,
        "received": len(received_events),
        "stored": len(unique_events),
        "duplicates": duplicates,
    }


def load_webhook_dedupe_stats(
    path: Path,
    selected_hours: int,
    reference_utc: Optional[datetime] = None,
) -> Dict[str, object]:
    reference = reference_utc or now_utc()
    empty = {
        "last_received_iso": "",
        "duplicate_hits_5m": 0,
        "duplicate_hits_1h": 0,
        "duplicate_hits_selected_window": 0,
        "duplicate_hits_total": 0,
    }
    if not path.exists():
        return empty

    with _connect_webhook_dedupe_db(path) as conn:
        _prune_webhook_dedupe_store(conn, reference)
        last_received_iso = (
            conn.execute("SELECT MAX(last_received_utc) FROM webhook_event_dedupe").fetchone()[0] or ""
        )
        dupes_5m = int(
            conn.execute(
                "SELECT COUNT(*) FROM webhook_duplicate_hits WHERE seen_at_utc >= ?",
                (iso_utc(reference - timedelta(minutes=5)),),
            ).fetchone()[0]
            or 0
        )
        dupes_1h = int(
            conn.execute(
                "SELECT COUNT(*) FROM webhook_duplicate_hits WHERE seen_at_utc >= ?",
                (iso_utc(reference - timedelta(hours=1)),),
            ).fetchone()[0]
            or 0
        )
        dupes_selected = int(
            conn.execute(
                "SELECT COUNT(*) FROM webhook_duplicate_hits WHERE seen_at_utc >= ?",
                (iso_utc(reference - timedelta(hours=max(1, selected_hours))),),
            ).fetchone()[0]
            or 0
        )
        dupes_total = int(conn.execute("SELECT COUNT(*) FROM webhook_duplicate_hits").fetchone()[0] or 0)

    return {
        "last_received_iso": last_received_iso,
        "duplicate_hits_5m": dupes_5m,
        "duplicate_hits_1h": dupes_1h,
        "duplicate_hits_selected_window": dupes_selected,
        "duplicate_hits_total": dupes_total,
    }


def _reason_excerpt(response: str) -> str:
    return re.sub(r"\s+", " ", (response or "").strip())[:200]


def is_actionable_suppression_status(status: str) -> bool:
    status_lower = (status or "").strip().lower()
    if not status_lower:
        return False
    return status_lower not in POSITIVE_STATUSES and status_lower not in NON_SUPPRESSION_STATUSES


def classify_suppression_event(
    event: Dict[str, str],
    ttl_blocked_days: int = 30,
    ttl_default_days: int = 14,
    reference_utc: Optional[datetime] = None,
) -> Optional[Dict[str, str]]:
    status = (event.get("status") or "").strip()
    status_lower = status.lower()
    if not is_actionable_suppression_status(status):
        return None
    reference = reference_utc or now_utc()
    response_lower = (event.get("response") or "").lower()
    is_permanent = False
    ttl_until_utc = ""
    if status_lower == "bounced":
        is_permanent = True
    elif status_lower == "blocked":
        if any(token in response_lower for token in PERMANENT_BLOCK_PATTERNS):
            is_permanent = True
        else:
            is_permanent = False
            ttl_days = ttl_blocked_days if any(token in response_lower for token in TEMPORARY_BLOCK_PATTERNS) else ttl_default_days
            ttl_until_utc = iso_utc(reference + timedelta(days=max(0, ttl_days)))
    elif status_lower in PERMANENT_FAILURE_STATUSES:
        is_permanent = True
    elif status_lower not in POSITIVE_STATUSES:
        is_permanent = True
    else:
        return None
    return {
        "email": norm_email(event.get("email") or ""),
        "status": status,
        "code": (event.get("code") or "").strip(),
        "reason": _reason_excerpt(event.get("response") or ""),
        "last_seen_utc": (event.get("processed_at_utc") or "").strip(),
        "is_permanent": "true" if is_permanent else "false",
        "ttl_until_utc": "" if is_permanent else ttl_until_utc,
    }


def load_suppression_records(path: Path) -> Dict[str, Dict[str, str]]:
    records: Dict[str, Dict[str, str]] = {}
    if not path.exists():
        return records
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            email = norm_email(row.get("email") or row.get("Email") or "")
            if not email:
                continue
            record = {field: (row.get(field, "") or "").strip() for field in SUPPRESSION_HEADERS}
            record["email"] = email
            if not record.get("last_seen_utc"):
                record["last_seen_utc"] = ""
            records[email] = record
    return records


def _is_true(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def is_suppression_active(record: Dict[str, str], reference_utc: Optional[datetime] = None) -> bool:
    if _is_true(record.get("is_permanent", "")):
        return True
    ttl_until = parse_iso_utc(record.get("ttl_until_utc", ""))
    if not ttl_until:
        return False
    return ttl_until >= (reference_utc or now_utc())


def suppression_summary(
    records: Dict[str, Dict[str, str]],
    reference_utc: Optional[datetime] = None,
) -> Dict[str, object]:
    reference = reference_utc or now_utc()
    blocked: Set[str] = set()
    perm_count = 0
    temp_active_count = 0
    for email, record in records.items():
        if not is_actionable_suppression_status(record.get("status", "")):
            continue
        if _is_true(record.get("is_permanent", "")):
            perm_count += 1
            blocked.add(email)
        elif is_suppression_active(record, reference):
            temp_active_count += 1
            blocked.add(email)
    return {
        "blocked_emails": blocked,
        "total_perm": perm_count,
        "total_temp_active": temp_active_count,
    }


def load_active_suppressed_emails(
    path: Path,
    reference_utc: Optional[datetime] = None,
) -> Tuple[Set[str], Dict[str, object]]:
    records = load_suppression_records(path)
    summary = suppression_summary(records, reference_utc)
    return set(summary["blocked_emails"]), summary


def _merge_record(existing: Optional[Dict[str, str]], incoming: Dict[str, str]) -> Dict[str, str]:
    if not existing:
        return dict(incoming)
    result = dict(existing)
    existing_perm = _is_true(existing.get("is_permanent", ""))
    incoming_perm = _is_true(incoming.get("is_permanent", ""))
    result["is_permanent"] = "true" if (existing_perm or incoming_perm) else "false"
    if _is_true(result["is_permanent"]):
        result["ttl_until_utc"] = ""
    else:
        existing_ttl = parse_iso_utc(existing.get("ttl_until_utc", ""))
        incoming_ttl = parse_iso_utc(incoming.get("ttl_until_utc", ""))
        chosen_ttl = incoming_ttl
        if existing_ttl and (not chosen_ttl or existing_ttl > chosen_ttl):
            chosen_ttl = existing_ttl
        result["ttl_until_utc"] = iso_utc(chosen_ttl) if chosen_ttl else ""
    existing_seen = parse_iso_utc(existing.get("last_seen_utc", ""))
    incoming_seen = parse_iso_utc(incoming.get("last_seen_utc", ""))
    if incoming_seen and (not existing_seen or incoming_seen >= existing_seen):
        for field in ("status", "code", "reason", "last_seen_utc"):
            result[field] = incoming.get(field, "")
    return result


def update_suppressions_from_events(
    events: Iterable[Dict[str, str]],
    suppression_csv: Path,
    ttl_blocked_days: int = 30,
    ttl_default_days: int = 14,
    reference_utc: Optional[datetime] = None,
) -> Dict[str, object]:
    reference = reference_utc or now_utc()
    records = load_suppression_records(suppression_csv)
    updated = 0
    for event in events:
        suppression = classify_suppression_event(
            event,
            ttl_blocked_days=ttl_blocked_days,
            ttl_default_days=ttl_default_days,
            reference_utc=reference,
        )
        if not suppression:
            continue
        email = suppression["email"]
        if not email:
            continue
        records[email] = _merge_record(records.get(email), suppression)
        updated += 1
    write_suppression_records(suppression_csv, records)
    summary = suppression_summary(records, reference)
    summary["updated_events"] = updated
    summary["records_total"] = len(records)
    return summary


def write_suppression_records(path: Path, records: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPRESSION_HEADERS)
        writer.writeheader()
        for email in sorted(records.keys()):
            record = dict(records[email])
            row = {field: record.get(field, "") for field in SUPPRESSION_HEADERS}
            row["email"] = email
            writer.writerow(row)


def _detect_email_column(fieldnames: Sequence[str]) -> Optional[str]:
    if not fieldnames:
        return None
    for name in fieldnames:
        if normalize_header(name) in {"email", "emails", "recipientemail", "recipient"}:
            return name
    return fieldnames[0]


def clean_recipient_shards(
    suppression_csv: Path,
    shard_paths: Iterable[Path],
    backup_dir: Path,
    report_path: Path,
    preserve_emails: Optional[Iterable[str]] = None,
    reference_utc: Optional[datetime] = None,
) -> Dict[str, object]:
    records = load_suppression_records(suppression_csv)
    summary = suppression_summary(records, reference_utc)
    preserved = {norm_email(email) for email in (preserve_emails or []) if norm_email(email)}
    blocked = set(summary["blocked_emails"]) - preserved
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = backup_dir / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)
    report: Dict[str, object] = {
        "generated_at_utc": iso_utc(reference_utc or now_utc()),
        "suppression_csv": str(suppression_csv),
        "backup_dir": str(backup_root),
        "total_removed": 0,
        "preserved_emails": sorted(preserved),
        "removed_count_per_shard": {},
        "removed_by_status": {},
        "removed_by_domain": {},
        "top_failure_reasons": [],
        "blocked_total": len(blocked),
    }
    domain_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    reason_counter: Counter[str] = Counter()
    for shard_path in sorted(shard_paths):
        removed_emails: List[str] = []
        with shard_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            email_col = _detect_email_column(fieldnames)
            rows_to_keep: List[Dict[str, str]] = []
            for row in reader:
                email = norm_email((row.get(email_col or "") or "") if email_col else "")
                if email and email in blocked:
                    removed_emails.append(email)
                    domain_counter[domain_from_email(email)] += 1
                    status = (records.get(email, {}).get("status", "") or "").strip()
                    if status:
                        status_counter[status.lower()] += 1
                    reason = records.get(email, {}).get("reason", "")
                    if reason:
                        reason_counter[reason] += 1
                    continue
                rows_to_keep.append(row)
        backup_path = backup_root / shard_path.name
        shutil.copy2(shard_path, backup_path)
        with shard_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows_to_keep:
                writer.writerow(row)
        removed_list_path = backup_root / f"removed_{shard_path.stem}.txt"
        removed_list_path.write_text("\n".join(removed_emails) + ("\n" if removed_emails else ""), encoding="utf-8")
        report["removed_count_per_shard"][shard_path.name] = len(removed_emails)
        report["total_removed"] += len(removed_emails)
    report["removed_by_status"] = dict(status_counter.most_common())
    report["removed_by_domain"] = dict(domain_counter.most_common())
    report["top_failure_reasons"] = [
        {"reason": reason, "count": count}
        for reason, count in reason_counter.most_common(10)
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
