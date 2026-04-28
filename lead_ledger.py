from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import settings
from leads_workflow import iso_utc
from sendgrid_hygiene import norm_email


LEAD_LEDGER_SCHEMA_VERSION = 3
LEAD_LEDGER_DB_PATH = settings.LEAD_LEDGER_DB_PATH

FAST_TRIAGE_STAGE = "FAST_TRIAGE"
STRICT_PUBLIC_PROOF_STAGE = "STRICT_PUBLIC_PROOF"
QUARANTINE_REVIEW_STAGE = "QUARANTINE_REVIEW"
QUARANTINE_STATUS = "QUARANTINE"
DISPATCH_READY_STATUS = "DISPATCH_READY"
PENDING_STRICT_PUBLIC_PROOF_STATUS = "PENDING_STRICT_PUBLIC_PROOF"
REJECTED_STATUS = "REJECT"

QUARANTINE_REVIEW_EVENT_TYPES = {
    "quarantine_promoted_dispatch_ready",
    "quarantine_rejected_permanently",
    "quarantine_sent_to_strict_public_proof",
    "operator_note_updated",
}

QUARANTINE_REVIEW_REASON_CODES = {
    "promote_dispatch_ready": "REVIEW_PROMOTED_DISPATCH_READY",
    "reject_permanently": "REVIEW_REJECTED_PERMANENTLY",
    "send_to_strict_verify": "REVIEW_SENT_TO_STRICT_PUBLIC_PROOF",
}

DEFAULT_BACKFILL_SPECS = (
    {
        "path": settings.APP_ROOT / "_important" / "leads_triaged_keep.csv",
        "stage": FAST_TRIAGE_STAGE,
        "status": "KEEP",
    },
    {
        "path": settings.APP_ROOT / "_important" / "leads_triaged_quarantine.csv",
        "stage": FAST_TRIAGE_STAGE,
        "status": "QUARANTINE",
    },
    {
        "path": settings.APP_ROOT / "_important" / "leads_triaged_reject.csv",
        "stage": FAST_TRIAGE_STAGE,
        "status": "REJECT",
    },
    {
        "path": settings.APP_ROOT / "_important" / "leads_verified.csv",
        "stage": STRICT_PUBLIC_PROOF_STAGE,
        "status": "KEEP",
    },
    {
        "path": settings.APP_ROOT / "_important" / "leads_verify_rejected.csv",
        "stage": STRICT_PUBLIC_PROOF_STAGE,
        "status": "REJECT",
    },
    {
        "path": settings.APP_ROOT / "_important" / "leads_quarantine.csv",
        "stage": STRICT_PUBLIC_PROOF_STAGE,
        "status": "QUARANTINE",
    },
)

FULL_NAME_KEYS = ("FullName", "full_name", "Name", "name", "AuthorName", "author_name", "author")
FIRST_NAME_KEYS = ("FirstName", "first_name", "first name", "AuthorFirstName", "author_first_name")
EMAIL_KEYS = ("Email", "email", "normalized_email")
REASON_CODE_KEYS = ("VerificationReason", "verification_reason", "reject_code")
SUPPRESSION_REASON_KEYS = ("reject_reason", "VerificationReason", "verification_reason")
SEND_OUTCOME_STATUSES = {
    "blocked",
    "bounced",
    "complained",
    "deferred",
    "delivered",
    "dropped",
    "unsubscribed",
}
AUTO_SUPPRESS_OUTCOMES = {"bounced", "complained", "unsubscribed"}


def _strip(value: object) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _workspace_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(settings.APP_ROOT.resolve()))
    except Exception:
        return str(path)


def _normalize_reason_code(value: object) -> str:
    return _strip(value)


def _normalize_reason_codes(values: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        code = _normalize_reason_code(value)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _reason_excerpt(value: object, limit: int = 200) -> str:
    return " ".join(_strip(value).split())[: max(1, int(limit or 200))]


def canonical_provider_message_id(value: object) -> str:
    raw = _strip(value).lower().strip("<>")
    if not raw:
        return ""
    return raw.split(".", 1)[0]


def _queue_target_from_shard(value: object) -> str:
    raw = Path(_strip(value)).name.lower()
    if raw.startswith("recipients_"):
        raw = raw[len("recipients_") :]
    if raw.endswith(".csv"):
        raw = raw[:-4]
    return raw


def _normalize_send_outcome_status(value: object) -> str:
    raw = _strip(value).lower().replace("-", "_").replace(" ", "_")
    if raw in {"bounce", "bounced"}:
        return "bounced"
    if raw in {"unsubscribe", "unsubscribed"}:
        return "unsubscribed"
    if raw in {"spam_report", "spamreport", "complained", "complaint"}:
        return "complained"
    if raw in {"drop", "dropped"}:
        return "dropped"
    if raw in SEND_OUTCOME_STATUSES:
        return raw
    return ""


def _outcome_reason(event: Mapping[str, object]) -> str:
    code = _strip(event.get("code"))
    response = _reason_excerpt(event.get("response") or event.get("reason") or "")
    if code and response and code not in response:
        return f"{code} {response}"[:200]
    return code or response


def _sort_float(value: object) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _lead_dispatch_summary(lead: Mapping[str, object]) -> dict[str, object]:
    return {
        "dispatch_count": int(lead.get("dispatch_count") or 0),
        "last_dispatch_at": _strip(lead.get("last_dispatch_at")),
        "last_profile": _strip(lead.get("last_profile")),
        "last_outcome": _strip(lead.get("last_outcome")),
        "contacted": int(lead.get("dispatch_count") or 0) > 0,
    }


def _lead_review_payload(lead: Mapping[str, object]) -> dict[str, object]:
    payload = dict(lead)
    payload["reason_codes"] = _json_reason_codes(payload.get("reason_codes"))
    payload["suppressed"] = bool(int(payload.get("suppressed") or 0))
    payload["dispatch_count"] = int(payload.get("dispatch_count") or 0)
    payload["score"] = float(payload.get("score") or 0)
    payload["dispatch_summary"] = _lead_dispatch_summary(payload)
    payload["source_provenance"] = {
        "source_file": _strip(payload.get("source_file")),
        "source_row_hash": _strip(payload.get("source_row_hash")),
        "first_seen_at": _strip(payload.get("first_seen_at")),
        "last_seen_at": _strip(payload.get("last_seen_at")),
    }
    payload["suppression_state"] = {
        "suppressed": bool(payload["suppressed"]),
        "suppression_reason": _strip(payload.get("suppression_reason")),
        "last_outcome": _strip(payload.get("last_outcome")),
    }
    return payload


def _normalize_quarantine_review_action(value: object) -> str:
    raw = _strip(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "promote": "promote_dispatch_ready",
        "promote_keep": "promote_dispatch_ready",
        "promote_to_keep": "promote_dispatch_ready",
        "promote_dispatch_ready": "promote_dispatch_ready",
        "dispatch_ready": "promote_dispatch_ready",
        "reject": "reject_permanently",
        "reject_permanently": "reject_permanently",
        "permanent_reject": "reject_permanently",
        "strict_verify": "send_to_strict_verify",
        "send_to_strict": "send_to_strict_verify",
        "send_to_strict_verify": "send_to_strict_verify",
        "strict_public_proof": "send_to_strict_verify",
        "note": "update_operator_note",
        "update_note": "update_operator_note",
        "update_operator_note": "update_operator_note",
    }
    return aliases.get(raw, "")


def _json_reason_codes(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except Exception:
            raw = [text]
    elif isinstance(value, Sequence):
        raw = list(value)
    else:
        raw = []
    return _normalize_reason_codes(raw)


def deterministic_lead_id(email: str) -> str:
    normalized = norm_email(email)
    if not normalized:
        raise ValueError("Lead email is required for deterministic lead id.")
    digest = hashlib.sha256(f"lead:{normalized}".encode("utf-8")).hexdigest()
    return f"lead_{digest}"


def source_row_hash(row: Mapping[str, object]) -> str:
    payload = {
        str(key): _strip(value)
        for key, value in sorted(row.items(), key=lambda item: str(item[0]))
        if str(key).strip()
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _pick_first(row: Mapping[str, object], keys: Sequence[str]) -> str:
    for key in keys:
        if key in row and _strip(row.get(key, "")):
            return _strip(row.get(key, ""))
    return ""


def _score_value(value: object) -> float:
    raw = _strip(value)
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _coerce_bool(value: object, default: bool = False) -> int:
    if value is None:
        return 1 if default else 0
    if isinstance(value, bool):
        return 1 if value else 0
    text = _strip(value).lower()
    if not text:
        return 1 if default else 0
    if text in {"1", "true", "yes", "y", "on"}:
        return 1
    if text in {"0", "false", "no", "n", "off"}:
        return 0
    return 1 if default else 0


def _lead_from_row(
    row: Mapping[str, object],
    *,
    source_file: str,
    stage: str,
    status: str,
    seen_at: str,
) -> dict[str, object] | None:
    email = norm_email(_pick_first(row, EMAIL_KEYS))
    if not email:
        return None
    reason_codes = _normalize_reason_codes(_pick_first(row, REASON_CODE_KEYS).split("|"))
    suppressed = "SUPPRESSED" in {code.upper() for code in reason_codes}
    return {
        "lead_id": deterministic_lead_id(email),
        "email": email,
        "full_name": _pick_first(row, FULL_NAME_KEYS),
        "first_name": _pick_first(row, FIRST_NAME_KEYS),
        "source_file": source_file,
        "source_row_hash": source_row_hash(row),
        "first_seen_at": seen_at,
        "last_seen_at": seen_at,
        "current_stage": stage,
        "current_status": status,
        "score": _score_value(row.get("score") or row.get("Score") or 0),
        "reason_codes": reason_codes,
        "suppressed": suppressed,
        "suppression_reason": _pick_first(row, SUPPRESSION_REASON_KEYS) if suppressed else "",
    }


def connect_lead_ledger(db_path: Path = LEAD_LEDGER_DB_PATH) -> sqlite3.Connection:
    settings.ensure_dirs((db_path.parent,))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    conn.execute("PRAGMA synchronous = FULL")
    ensure_lead_ledger_schema(conn)
    settings.secure_private_file(db_path)
    return conn


def ensure_lead_ledger_schema(conn: sqlite3.Connection) -> None:
    current_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current_version >= LEAD_LEDGER_SCHEMA_VERSION:
        return
    with conn:
        if current_version < 1:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_ledger (
                    lead_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    first_name TEXT NOT NULL DEFAULT '',
                    source_file TEXT NOT NULL DEFAULT '',
                    source_row_hash TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL DEFAULT '',
                    last_seen_at TEXT NOT NULL DEFAULT '',
                    current_stage TEXT NOT NULL DEFAULT '',
                    current_status TEXT NOT NULL DEFAULT '',
                    score REAL NOT NULL DEFAULT 0,
                    reason_codes TEXT NOT NULL DEFAULT '[]',
                    suppressed INTEGER NOT NULL DEFAULT 0,
                    suppression_reason TEXT NOT NULL DEFAULT '',
                    last_dispatch_at TEXT NOT NULL DEFAULT '',
                    dispatch_count INTEGER NOT NULL DEFAULT 0,
                    last_outcome TEXT NOT NULL DEFAULT '',
                    last_profile TEXT NOT NULL DEFAULT '',
                    operator_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_ledger_events (
                    event_id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    stage_before TEXT NOT NULL DEFAULT '',
                    stage_after TEXT NOT NULL DEFAULT '',
                    status_before TEXT NOT NULL DEFAULT '',
                    status_after TEXT NOT NULL DEFAULT '',
                    reason_code TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    run_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (lead_id) REFERENCES lead_ledger(lead_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_ledger_import_rows (
                    source_file TEXT NOT NULL,
                    source_row_hash TEXT NOT NULL,
                    lead_id TEXT NOT NULL,
                    stage_imported TEXT NOT NULL DEFAULT '',
                    status_imported TEXT NOT NULL DEFAULT '',
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY (source_file, source_row_hash),
                    FOREIGN KEY (lead_id) REFERENCES lead_ledger(lead_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lead_ledger_lead_id ON lead_ledger(lead_id)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lead_ledger_email ON lead_ledger(email)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_ledger_stage_status ON lead_ledger(current_stage, current_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_ledger_source_row_hash ON lead_ledger(source_row_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_ledger_events_lead_id_created_at ON lead_ledger_events(lead_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_ledger_import_rows_lead_id ON lead_ledger_import_rows(lead_id)")
        if current_version < 2:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_dispatch_history (
                    dispatch_event_id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    dispatch_source TEXT NOT NULL DEFAULT '',
                    profile TEXT NOT NULL DEFAULT '',
                    queue_target TEXT NOT NULL DEFAULT '',
                    attempt_number INTEGER NOT NULL DEFAULT 0,
                    dispatched_at TEXT NOT NULL DEFAULT '',
                    result_status TEXT NOT NULL DEFAULT '',
                    result_reason TEXT NOT NULL DEFAULT '',
                    provider_message_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (lead_id) REFERENCES lead_ledger(lead_id) ON DELETE CASCADE,
                    UNIQUE (run_id, lead_id, queue_target)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_dispatch_history_lead_id ON lead_dispatch_history(lead_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_dispatch_history_run_id ON lead_dispatch_history(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_dispatch_history_status ON lead_dispatch_history(result_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_dispatch_history_queue_target ON lead_dispatch_history(queue_target)")
        if current_version < 3:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lead_dispatch_history_provider_message_id ON lead_dispatch_history(provider_message_id)"
            )
        conn.execute(f"PRAGMA user_version = {LEAD_LEDGER_SCHEMA_VERSION}")


def load_lead_by_id(conn: sqlite3.Connection, lead_id: str) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM lead_ledger WHERE lead_id = ?", (str(lead_id or "").strip(),)).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["reason_codes"] = _json_reason_codes(payload.get("reason_codes"))
    payload["suppressed"] = bool(int(payload.get("suppressed") or 0))
    payload["dispatch_count"] = int(payload.get("dispatch_count") or 0)
    payload["score"] = float(payload.get("score") or 0)
    return payload


def _merge_text(existing: str, incoming: object) -> str:
    incoming_text = _strip(incoming)
    return incoming_text or existing


def _earliest_timestamp(existing: str, incoming: str) -> str:
    if not existing:
        return incoming
    if not incoming:
        return existing
    return min(existing, incoming)


def _latest_timestamp(existing: str, incoming: str) -> str:
    if not existing:
        return incoming
    if not incoming:
        return existing
    return max(existing, incoming)


def _event_id() -> str:
    return f"event_{uuid.uuid4().hex}"


def _dispatch_event_id() -> str:
    return f"dispatch_{uuid.uuid4().hex}"


def record_transition(
    conn: sqlite3.Connection,
    *,
    lead_id: str,
    event_type: str,
    stage_before: str = "",
    stage_after: str = "",
    status_before: str = "",
    status_after: str = "",
    reason_code: str = "",
    note: str = "",
    run_id: str = "",
    created_at: str | None = None,
) -> str:
    timestamp = created_at or iso_utc()
    event_id = _event_id()
    conn.execute(
        """
        INSERT INTO lead_ledger_events (
            event_id,
            lead_id,
            event_type,
            stage_before,
            stage_after,
            status_before,
            status_after,
            reason_code,
            note,
            run_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            str(lead_id or "").strip(),
            _strip(event_type),
            _strip(stage_before),
            _strip(stage_after),
            _strip(status_before),
            _strip(status_after),
            _strip(reason_code),
            _strip(note),
            _strip(run_id),
            timestamp,
        ),
    )
    return event_id


def upsert_lead(conn: sqlite3.Connection, *, commit: bool = True, **lead: object) -> dict[str, object]:
    email = norm_email(lead.get("email", ""))
    if not email:
        raise ValueError("Lead email is required.")
    lead_id = str(lead.get("lead_id") or deterministic_lead_id(email)).strip()
    now = str(lead.get("updated_at") or iso_utc())
    existing = load_lead_by_id(conn, lead_id)
    existing_reason_codes = existing["reason_codes"] if existing else []
    incoming_reason_codes = _json_reason_codes(lead.get("reason_codes", []))
    merged_reason_codes = _normalize_reason_codes([*existing_reason_codes, *incoming_reason_codes])

    payload = {
        "lead_id": lead_id,
        "email": email,
        "full_name": _merge_text(existing["full_name"] if existing else "", lead.get("full_name", "")),
        "first_name": _merge_text(existing["first_name"] if existing else "", lead.get("first_name", "")),
        "source_file": _merge_text(existing["source_file"] if existing else "", lead.get("source_file", "")),
        "source_row_hash": _merge_text(existing["source_row_hash"] if existing else "", lead.get("source_row_hash", "")),
        "first_seen_at": _earliest_timestamp(
            str(existing["first_seen_at"] if existing else ""),
            _strip(lead.get("first_seen_at")) or now,
        ),
        "last_seen_at": _latest_timestamp(
            str(existing["last_seen_at"] if existing else ""),
            _strip(lead.get("last_seen_at")) or now,
        ),
        "current_stage": _strip(lead.get("current_stage")) or (existing["current_stage"] if existing else ""),
        "current_status": _strip(lead.get("current_status")) or (existing["current_status"] if existing else ""),
        "score": float(lead.get("score") if lead.get("score") not in {None, ""} else (existing["score"] if existing else 0)),
        "reason_codes": json.dumps(merged_reason_codes),
        "suppressed": _coerce_bool(lead.get("suppressed"), default=existing["suppressed"] if existing else False),
        "suppression_reason": _merge_text(existing["suppression_reason"] if existing else "", lead.get("suppression_reason", "")),
        "last_dispatch_at": _merge_text(existing["last_dispatch_at"] if existing else "", lead.get("last_dispatch_at", "")),
        "dispatch_count": int(lead.get("dispatch_count") if lead.get("dispatch_count") not in {None, ""} else (existing["dispatch_count"] if existing else 0)),
        "last_outcome": _merge_text(existing["last_outcome"] if existing else "", lead.get("last_outcome", "")),
        "last_profile": _merge_text(existing["last_profile"] if existing else "", lead.get("last_profile", "")),
        "operator_note": _merge_text(existing["operator_note"] if existing else "", lead.get("operator_note", "")),
        "created_at": existing["created_at"] if existing else (_strip(lead.get("created_at")) or now),
        "updated_at": now,
    }
    def write() -> None:
        conn.execute(
            """
            INSERT INTO lead_ledger (
                lead_id,
                email,
                full_name,
                first_name,
                source_file,
                source_row_hash,
                first_seen_at,
                last_seen_at,
                current_stage,
                current_status,
                score,
                reason_codes,
                suppressed,
                suppression_reason,
                last_dispatch_at,
                dispatch_count,
                last_outcome,
                last_profile,
                operator_note,
                created_at,
                updated_at
            ) VALUES (
                :lead_id,
                :email,
                :full_name,
                :first_name,
                :source_file,
                :source_row_hash,
                :first_seen_at,
                :last_seen_at,
                :current_stage,
                :current_status,
                :score,
                :reason_codes,
                :suppressed,
                :suppression_reason,
                :last_dispatch_at,
                :dispatch_count,
                :last_outcome,
                :last_profile,
                :operator_note,
                :created_at,
                :updated_at
            )
            ON CONFLICT(lead_id) DO UPDATE SET
                email = excluded.email,
                full_name = excluded.full_name,
                first_name = excluded.first_name,
                source_file = excluded.source_file,
                source_row_hash = excluded.source_row_hash,
                first_seen_at = excluded.first_seen_at,
                last_seen_at = excluded.last_seen_at,
                current_stage = excluded.current_stage,
                current_status = excluded.current_status,
                score = excluded.score,
                reason_codes = excluded.reason_codes,
                suppressed = excluded.suppressed,
                suppression_reason = excluded.suppression_reason,
                last_dispatch_at = excluded.last_dispatch_at,
                dispatch_count = excluded.dispatch_count,
                last_outcome = excluded.last_outcome,
                last_profile = excluded.last_profile,
                operator_note = excluded.operator_note,
                updated_at = excluded.updated_at
            """,
            payload,
        )
    if commit:
        with conn:
            write()
    else:
        write()
    return load_lead_by_id(conn, lead_id) or {}


def record_reason_codes(
    conn: sqlite3.Connection,
    lead_id: str,
    reason_codes: Iterable[object],
    *,
    note: str = "",
    run_id: str = "",
    created_at: str | None = None,
) -> list[str]:
    lead = load_lead_by_id(conn, lead_id)
    if lead is None:
        raise KeyError(f"Lead not found: {lead_id}")
    existing_codes = list(lead["reason_codes"])
    merged_codes = _normalize_reason_codes([*existing_codes, *reason_codes])
    added_codes = [code for code in merged_codes if code not in existing_codes]
    if not added_codes:
        return existing_codes
    timestamp = created_at or iso_utc()
    with conn:
        conn.execute(
            "UPDATE lead_ledger SET reason_codes = ?, updated_at = ? WHERE lead_id = ?",
            (json.dumps(merged_codes), timestamp, lead_id),
        )
        for code in added_codes:
            record_transition(
                conn,
                lead_id=lead_id,
                event_type="reason_code_recorded",
                stage_before=str(lead.get("current_stage") or ""),
                stage_after=str(lead.get("current_stage") or ""),
                status_before=str(lead.get("current_status") or ""),
                status_after=str(lead.get("current_status") or ""),
                reason_code=code,
                note=note,
                run_id=run_id,
                created_at=timestamp,
            )
    return merged_codes


def update_stage_status(
    conn: sqlite3.Connection,
    lead_id: str,
    *,
    stage_after: str,
    status_after: str,
    reason_code: str = "",
    note: str = "",
    run_id: str = "",
    event_type: str = "stage_status_updated",
    updated_at: str | None = None,
    commit: bool = True,
) -> dict[str, object]:
    lead = load_lead_by_id(conn, lead_id)
    if lead is None:
        raise KeyError(f"Lead not found: {lead_id}")
    stage_before = str(lead.get("current_stage") or "")
    status_before = str(lead.get("current_status") or "")
    stage_next = _strip(stage_after)
    status_next = _strip(status_after)
    if stage_before == stage_next and status_before == status_next:
        return lead
    timestamp = updated_at or iso_utc()
    def write() -> None:
        conn.execute(
            """
            UPDATE lead_ledger
            SET current_stage = ?, current_status = ?, last_seen_at = ?, updated_at = ?
            WHERE lead_id = ?
            """,
            (stage_next, status_next, timestamp, timestamp, lead_id),
        )
        record_transition(
            conn,
            lead_id=lead_id,
            event_type=event_type,
            stage_before=stage_before,
            stage_after=stage_next,
            status_before=status_before,
            status_after=status_next,
            reason_code=reason_code,
            note=note,
            run_id=run_id,
            created_at=timestamp,
        )
    if commit:
        with conn:
            write()
    else:
        write()
    return load_lead_by_id(conn, lead_id) or {}


def load_lead_events(conn: sqlite3.Connection, lead_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM lead_ledger_events WHERE lead_id = ? ORDER BY created_at ASC, event_id ASC",
        (str(lead_id or "").strip(),),
    ).fetchall()
    return [dict(row) for row in rows]


def load_dispatch_events(conn: sqlite3.Connection, lead_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM lead_dispatch_history WHERE lead_id = ? ORDER BY dispatched_at ASC, dispatch_event_id ASC",
        (str(lead_id or "").strip(),),
    ).fetchall()
    return [dict(row) for row in rows]


def update_operator_note(
    conn: sqlite3.Connection,
    lead_id: str,
    operator_note: object,
    *,
    note: str = "",
    run_id: str = "",
    event_type: str = "operator_note_updated",
    updated_at: str | None = None,
) -> dict[str, object]:
    lead = load_lead_by_id(conn, lead_id)
    if lead is None:
        raise KeyError(f"Lead not found: {lead_id}")
    timestamp = updated_at or iso_utc()
    note_text = _strip(operator_note)
    with conn:
        conn.execute(
            "UPDATE lead_ledger SET operator_note = ?, updated_at = ? WHERE lead_id = ?",
            (note_text, timestamp, str(lead_id or "").strip()),
        )
        record_transition(
            conn,
            lead_id=str(lead_id or "").strip(),
            event_type=event_type,
            stage_before=str(lead.get("current_stage") or ""),
            stage_after=str(lead.get("current_stage") or ""),
            status_before=str(lead.get("current_status") or ""),
            status_after=str(lead.get("current_status") or ""),
            reason_code="",
            note=note or note_text,
            run_id=run_id,
            created_at=timestamp,
        )
    return load_lead_by_id(conn, lead_id) or {}


def list_quarantine_review_leads(
    conn: sqlite3.Connection,
    *,
    reason_code: str = "",
    stage: str = "",
    status: str = QUARANTINE_STATUS,
    sort: str = "score_desc",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    review_rows = _quarantine_review_rows(
        conn,
        reason_code=reason_code,
        stage=stage,
        status=status,
        sort=sort,
    )
    base_status = _strip(status) or QUARANTINE_STATUS
    selected_reason_code = _strip(reason_code)
    total_filtered = len(review_rows)
    start = max(0, int(offset or 0))
    stop = start + max(1, min(500, int(limit or 100)))
    visible_rows = review_rows[start:stop]

    all_quarantine_rows = [
        _lead_review_payload(dict(row))
        for row in conn.execute(
            "SELECT * FROM lead_ledger WHERE current_status = ?",
            (QUARANTINE_STATUS,),
        ).fetchall()
    ]
    reason_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for row in all_quarantine_rows:
        stage_key = _strip(row.get("current_stage")) or "(none)"
        status_key = _strip(row.get("current_status")) or "(none)"
        stage_counts[stage_key] = int(stage_counts.get(stage_key, 0) or 0) + 1
        status_counts[status_key] = int(status_counts.get(status_key, 0) or 0) + 1
        for code in row.get("reason_codes") or []:
            reason_counts[code] = int(reason_counts.get(code, 0) or 0) + 1

    return {
        "filters": {
            "reason_code": selected_reason_code,
            "stage": _strip(stage),
            "status": base_status,
            "sort": "score_asc" if sort == "score_asc" else "score_desc",
            "limit": max(1, min(500, int(limit or 100))),
            "offset": start,
        },
        "counts": {
            "total_quarantined": len(all_quarantine_rows),
            "filtered": total_filtered,
            "displayed": len(visible_rows),
        },
        "stage_counts": stage_counts,
        "status_counts": status_counts,
        "reason_code_counts": reason_counts,
        "stage_options": sorted(stage_counts.keys()),
        "status_options": sorted(status_counts.keys()),
        "reason_code_options": sorted(reason_counts.keys()),
        "leads": visible_rows,
    }


def _quarantine_review_rows(
    conn: sqlite3.Connection,
    *,
    reason_code: str = "",
    stage: str = "",
    status: str = QUARANTINE_STATUS,
    sort: str = "score_desc",
) -> list[dict[str, object]]:
    base_status = _strip(status) or QUARANTINE_STATUS
    params: list[object] = []
    clauses: list[str] = []
    if base_status:
        clauses.append("current_status = ?")
        params.append(base_status)
    if _strip(stage):
        clauses.append("current_stage = ?")
        params.append(_strip(stage))
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM lead_ledger {where_sql}"
    , tuple(params)).fetchall()

    review_rows = [_lead_review_payload(dict(row)) for row in rows]
    selected_reason_code = _strip(reason_code)
    if selected_reason_code:
        review_rows = [
            row for row in review_rows
            if selected_reason_code in set(row.get("reason_codes") or [])
        ]

    reverse = sort != "score_asc"
    review_rows.sort(
        key=lambda row: (
            _sort_float(row.get("score")),
            _strip(row.get("updated_at")),
            _strip(row.get("lead_id")),
        ),
        reverse=reverse,
    )
    return review_rows


def list_quarantine_review_lead_ids(
    conn: sqlite3.Connection,
    *,
    reason_code: str = "",
    stage: str = "",
    status: str = QUARANTINE_STATUS,
    sort: str = "score_desc",
    exclude_lead_ids: Sequence[str] = (),
) -> list[str]:
    excluded = {_strip(value) for value in exclude_lead_ids if _strip(value)}
    review_rows = _quarantine_review_rows(
        conn,
        reason_code=reason_code,
        stage=stage,
        status=status,
        sort=sort,
    )
    return [
        _strip(row.get("lead_id"))
        for row in review_rows
        if _strip(row.get("lead_id")) and _strip(row.get("lead_id")) not in excluded
    ]


def load_quarantine_review_lead(conn: sqlite3.Connection, lead_id: str) -> dict[str, object] | None:
    lead = load_lead_by_id(conn, lead_id)
    if lead is None:
        return None
    dispatch_events = load_dispatch_events(conn, lead_id)
    lead_events = load_lead_events(conn, lead_id)
    payload = _lead_review_payload(lead)
    payload["lead_events"] = lead_events
    payload["dispatch_events"] = dispatch_events
    payload["review_events"] = [event for event in lead_events if _strip(event.get("event_type")) in QUARANTINE_REVIEW_EVENT_TYPES]
    return payload


def load_recent_quarantine_review_actions(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT e.*, l.email, l.full_name
        FROM lead_ledger_events e
        JOIN lead_ledger l ON l.lead_id = e.lead_id
        WHERE e.event_type IN (?, ?, ?, ?)
        ORDER BY e.created_at DESC, e.event_id DESC
        LIMIT ?
        """,
        (
            "quarantine_promoted_dispatch_ready",
            "quarantine_rejected_permanently",
            "quarantine_sent_to_strict_public_proof",
            "operator_note_updated",
            max(1, min(100, int(limit or 10))),
        ),
    ).fetchall()
    return [dict(row) for row in rows]


def apply_quarantine_review_action(
    conn: sqlite3.Connection,
    *,
    lead_ids: Sequence[str],
    action: str,
    operator_note: str = "",
    run_id: str = "",
    updated_at: str | None = None,
) -> dict[str, object]:
    normalized_action = _normalize_quarantine_review_action(action)
    if not normalized_action:
        raise ValueError(f"Unsupported quarantine review action: {action}")
    normalized_ids: list[str] = []
    seen: set[str] = set()
    for value in lead_ids:
        lead_id = _strip(value)
        if not lead_id or lead_id in seen:
            continue
        seen.add(lead_id)
        normalized_ids.append(lead_id)
    if not normalized_ids:
        raise ValueError("Select at least one lead.")
    if normalized_action == "update_operator_note" and not _strip(operator_note):
        raise ValueError("Operator note is required for note-only updates.")

    timestamp = updated_at or iso_utc()
    affected: list[str] = []
    skipped_missing: list[str] = []
    skipped_not_quarantined: list[str] = []

    for lead_id in normalized_ids:
        lead = load_lead_by_id(conn, lead_id)
        if lead is None:
            skipped_missing.append(lead_id)
            continue
        if normalized_action != "update_operator_note" and _strip(lead.get("current_status")) != QUARANTINE_STATUS:
            skipped_not_quarantined.append(lead_id)
            continue

        if normalized_action == "promote_dispatch_ready":
            update_stage_status(
                conn,
                lead_id,
                stage_after=QUARANTINE_REVIEW_STAGE,
                status_after=DISPATCH_READY_STATUS,
                reason_code=QUARANTINE_REVIEW_REASON_CODES[normalized_action],
                note="Promoted from quarantine to dispatch ready.",
                run_id=run_id,
                event_type="quarantine_promoted_dispatch_ready",
                updated_at=timestamp,
            )
            record_reason_codes(
                conn,
                lead_id,
                [QUARANTINE_REVIEW_REASON_CODES[normalized_action]],
                note="Promoted from quarantine to dispatch ready.",
                run_id=run_id,
                created_at=timestamp,
            )
        elif normalized_action == "reject_permanently":
            update_stage_status(
                conn,
                lead_id,
                stage_after=QUARANTINE_REVIEW_STAGE,
                status_after=REJECTED_STATUS,
                reason_code=QUARANTINE_REVIEW_REASON_CODES[normalized_action],
                note="Rejected permanently during quarantine review.",
                run_id=run_id,
                event_type="quarantine_rejected_permanently",
                updated_at=timestamp,
            )
            record_reason_codes(
                conn,
                lead_id,
                [QUARANTINE_REVIEW_REASON_CODES[normalized_action]],
                note="Rejected permanently during quarantine review.",
                run_id=run_id,
                created_at=timestamp,
            )
        elif normalized_action == "send_to_strict_verify":
            update_stage_status(
                conn,
                lead_id,
                stage_after=STRICT_PUBLIC_PROOF_STAGE,
                status_after=PENDING_STRICT_PUBLIC_PROOF_STATUS,
                reason_code=QUARANTINE_REVIEW_REASON_CODES[normalized_action],
                note="Marked for Strict Public Proof review.",
                run_id=run_id,
                event_type="quarantine_sent_to_strict_public_proof",
                updated_at=timestamp,
            )
            record_reason_codes(
                conn,
                lead_id,
                [QUARANTINE_REVIEW_REASON_CODES[normalized_action]],
                note="Marked for Strict Public Proof review.",
                run_id=run_id,
                created_at=timestamp,
            )
        elif normalized_action == "update_operator_note":
            update_operator_note(
                conn,
                lead_id,
                operator_note,
                note="Operator note updated from quarantine review inbox.",
                run_id=run_id,
                updated_at=timestamp,
            )
        if normalized_action != "update_operator_note" and _strip(operator_note):
            update_operator_note(
                conn,
                lead_id,
                operator_note,
                note="Operator note updated with quarantine review action.",
                run_id=run_id,
                updated_at=timestamp,
            )
        affected.append(lead_id)

    return {
        "action": normalized_action,
        "processed": len(normalized_ids),
        "updated": len(affected),
        "affected_lead_ids": affected,
        "skipped_missing": skipped_missing,
        "skipped_not_quarantined": skipped_not_quarantined,
        "operator_note_applied": bool(_strip(operator_note)),
        "updated_at": timestamp,
    }


def next_dispatch_attempt_number(conn: sqlite3.Connection, lead_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(attempt_number), 0) FROM lead_dispatch_history WHERE lead_id = ?",
        (str(lead_id or "").strip(),),
    ).fetchone()
    return max(0, int((row[0] if row is not None else 0) or 0)) + 1


def load_contacted_lead_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT DISTINCT lead_id FROM lead_dispatch_history").fetchall()
    return {str(row[0] or "").strip() for row in rows if str(row[0] or "").strip()}


def dispatch_history_state(conn: sqlite3.Connection) -> dict[str, object]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS dispatch_event_count,
            COUNT(DISTINCT lead_id) AS contacted_lead_count,
            COALESCE(MAX(updated_at), '') AS latest_updated_at
        FROM lead_dispatch_history
        """
    ).fetchone()
    return {
        "dispatch_event_count": int((row["dispatch_event_count"] if row is not None else 0) or 0),
        "contacted_lead_count": int((row["contacted_lead_count"] if row is not None else 0) or 0),
        "latest_updated_at": str((row["latest_updated_at"] if row is not None else "") or ""),
    }


def record_dispatch_event(
    conn: sqlite3.Connection,
    *,
    lead_id: str,
    run_id: str,
    dispatch_source: str,
    profile: str,
    queue_target: str,
    result_status: str,
    result_reason: str = "",
    provider_message_id: str = "",
    dispatched_at: str | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
    manage_transaction: bool = True,
) -> dict[str, object]:
    lead = load_lead_by_id(conn, lead_id)
    if lead is None:
        raise KeyError(f"Lead not found: {lead_id}")
    timestamp = dispatched_at or iso_utc()
    created_timestamp = created_at or timestamp
    updated_timestamp = updated_at or timestamp
    attempt_number = next_dispatch_attempt_number(conn, lead_id)
    dispatch_event_id = _dispatch_event_id()

    def _write() -> None:
        conn.execute(
            """
            INSERT INTO lead_dispatch_history (
                dispatch_event_id,
                lead_id,
                run_id,
                dispatch_source,
                profile,
                queue_target,
                attempt_number,
                dispatched_at,
                result_status,
                result_reason,
                provider_message_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dispatch_event_id,
                str(lead_id or "").strip(),
                _strip(run_id),
                _strip(dispatch_source),
                _strip(profile),
                _strip(queue_target),
                attempt_number,
                timestamp,
                _strip(result_status),
                _strip(result_reason),
                canonical_provider_message_id(provider_message_id),
                created_timestamp,
                updated_timestamp,
            ),
        )
        conn.execute(
            """
            UPDATE lead_ledger
            SET
                last_dispatch_at = ?,
                dispatch_count = COALESCE(dispatch_count, 0) + 1,
                last_profile = ?,
                updated_at = ?
            WHERE lead_id = ?
            """,
            (timestamp, _strip(profile), updated_timestamp, str(lead_id or "").strip()),
        )
        record_transition(
            conn,
            lead_id=str(lead_id or "").strip(),
            event_type="lead_dispatched",
            stage_before=str(lead.get("current_stage") or ""),
            stage_after=str(lead.get("current_stage") or ""),
            status_before=str(lead.get("current_status") or ""),
            status_after=str(lead.get("current_status") or ""),
            reason_code=_strip(result_status),
            note=f"Queued to {_strip(queue_target)} via {_strip(dispatch_source)}",
            run_id=run_id,
            created_at=timestamp,
        )

    if manage_transaction:
        with conn:
            _write()
    else:
        _write()
    row = conn.execute(
        "SELECT * FROM lead_dispatch_history WHERE dispatch_event_id = ?",
        (dispatch_event_id,),
    ).fetchone()
    return dict(row) if row is not None else {}


def _find_dispatch_event_for_outcome(
    conn: sqlite3.Connection,
    *,
    provider_message_id: str = "",
    run_id: str = "",
    lead_id: str = "",
    queue_target: str = "",
) -> dict[str, object] | None:
    canonical_message_id = canonical_provider_message_id(provider_message_id)
    if canonical_message_id:
        row = conn.execute(
            """
            SELECT *
            FROM lead_dispatch_history
            WHERE provider_message_id = ?
            ORDER BY updated_at DESC, dispatched_at DESC, dispatch_event_id DESC
            LIMIT 1
            """,
            (canonical_message_id,),
        ).fetchone()
        if row is not None:
            return dict(row)

    run_id = _strip(run_id)
    lead_id = _strip(lead_id)
    queue_target = _strip(queue_target)

    if run_id and lead_id and queue_target:
        row = conn.execute(
            """
            SELECT *
            FROM lead_dispatch_history
            WHERE run_id = ? AND lead_id = ? AND queue_target = ?
            ORDER BY dispatched_at DESC, dispatch_event_id DESC
            LIMIT 1
            """,
            (run_id, lead_id, queue_target),
        ).fetchone()
        if row is not None:
            return dict(row)

    if run_id and lead_id:
        rows = conn.execute(
            """
            SELECT *
            FROM lead_dispatch_history
            WHERE run_id = ? AND lead_id = ?
            ORDER BY dispatched_at DESC, dispatch_event_id DESC
            """,
            (run_id, lead_id),
        ).fetchall()
        if len(rows) == 1:
            return dict(rows[0])

    if lead_id and queue_target:
        rows = conn.execute(
            """
            SELECT *
            FROM lead_dispatch_history
            WHERE lead_id = ? AND queue_target = ? AND provider_message_id = ''
            ORDER BY dispatched_at DESC, dispatch_event_id DESC
            """,
            (lead_id, queue_target),
        ).fetchall()
        if len(rows) == 1:
            return dict(rows[0])

    if lead_id:
        rows = conn.execute(
            """
            SELECT *
            FROM lead_dispatch_history
            WHERE lead_id = ? AND provider_message_id = ''
            ORDER BY dispatched_at DESC, dispatch_event_id DESC
            """,
            (lead_id,),
        ).fetchall()
        if len(rows) == 1:
            return dict(rows[0])

    return None


def record_dispatch_outcome(
    conn: sqlite3.Connection,
    event: Mapping[str, object],
    *,
    manage_transaction: bool = True,
) -> dict[str, object]:
    outcome = _normalize_send_outcome_status(event.get("status") or event.get("event") or "")
    if not outcome:
        return {
            "matched": False,
            "ignored": True,
            "reason": "unsupported_status",
            "status": _strip(event.get("status") or event.get("event") or ""),
        }

    email = norm_email(_strip(event.get("email")))
    lead_id = _strip(event.get("lead_id"))
    if not lead_id and email:
        try:
            lead_id = deterministic_lead_id(email)
        except ValueError:
            lead_id = ""

    provider_message_id = canonical_provider_message_id(event.get("message_id") or event.get("provider_message_id"))
    run_id = _strip(event.get("astra_run_id") or event.get("run_id"))
    queue_target = _queue_target_from_shard(event.get("shard") or event.get("queue_target"))
    matched = _find_dispatch_event_for_outcome(
        conn,
        provider_message_id=provider_message_id,
        run_id=run_id,
        lead_id=lead_id,
        queue_target=queue_target,
    )
    if matched is None:
        return {
            "matched": False,
            "ignored": False,
            "reason": "unmatched_dispatch_event",
            "status": outcome,
            "provider_message_id": provider_message_id,
            "lead_id": lead_id,
        }

    matched_lead_id = str(matched.get("lead_id") or "").strip()
    lead = load_lead_by_id(conn, matched_lead_id)
    if lead is None:
        return {
            "matched": False,
            "ignored": False,
            "reason": "missing_lead",
            "status": outcome,
            "provider_message_id": provider_message_id,
            "lead_id": matched_lead_id,
        }

    timestamp = _strip(event.get("processed_at_utc") or event.get("received_at_utc")) or iso_utc()
    reason = _outcome_reason(event)
    message_id_to_store = provider_message_id or canonical_provider_message_id(matched.get("provider_message_id"))
    auto_suppress = outcome in AUTO_SUPPRESS_OUTCOMES
    lead_was_suppressed = bool(lead.get("suppressed"))
    suppression_reason = str(lead.get("suppression_reason") or "")
    if auto_suppress:
        suppression_reason = reason or outcome

    def _write() -> None:
        conn.execute(
            """
            UPDATE lead_dispatch_history
            SET
                result_status = ?,
                result_reason = ?,
                provider_message_id = ?,
                updated_at = ?
            WHERE dispatch_event_id = ?
            """,
            (
                outcome,
                reason,
                message_id_to_store,
                timestamp,
                str(matched.get("dispatch_event_id") or "").strip(),
            ),
        )
        conn.execute(
            """
            UPDATE lead_ledger
            SET
                last_outcome = ?,
                suppressed = ?,
                suppression_reason = ?,
                updated_at = ?
            WHERE lead_id = ?
            """,
            (
                outcome,
                1 if (lead_was_suppressed or auto_suppress) else 0,
                suppression_reason if (lead_was_suppressed or auto_suppress) else str(lead.get("suppression_reason") or ""),
                timestamp,
                matched_lead_id,
            ),
        )
        record_transition(
            conn,
            lead_id=matched_lead_id,
            event_type="send_outcome_recorded",
            stage_before=str(lead.get("current_stage") or ""),
            stage_after=str(lead.get("current_stage") or ""),
            status_before=str(lead.get("current_status") or ""),
            status_after=str(lead.get("current_status") or ""),
            reason_code=outcome,
            note=reason or message_id_to_store,
            run_id=str(matched.get("run_id") or ""),
            created_at=timestamp,
        )
        if auto_suppress and not lead_was_suppressed:
            record_transition(
                conn,
                lead_id=matched_lead_id,
                event_type="lead_suppressed",
                stage_before=str(lead.get("current_stage") or ""),
                stage_after=str(lead.get("current_stage") or ""),
                status_before=str(lead.get("current_status") or ""),
                status_after=str(lead.get("current_status") or ""),
                reason_code=outcome,
                note=suppression_reason,
                run_id=str(matched.get("run_id") or ""),
                created_at=timestamp,
            )

    if manage_transaction:
        with conn:
            _write()
    else:
        _write()

    return {
        "matched": True,
        "ignored": False,
        "reason": "",
        "status": outcome,
        "lead_id": matched_lead_id,
        "dispatch_event_id": str(matched.get("dispatch_event_id") or "").strip(),
        "provider_message_id": message_id_to_store,
        "suppressed": bool(lead_was_suppressed or auto_suppress),
        "auto_suppressed": auto_suppress,
    }


def ingest_send_outcome_events(
    events: Iterable[Mapping[str, object]],
    *,
    db_path: Path = LEAD_LEDGER_DB_PATH,
) -> dict[str, object]:
    received = list(events)
    summary = {
        "processed_events": len(received),
        "matched_events": 0,
        "unmatched_events": 0,
        "ignored_events": 0,
        "dispatch_rows_updated": 0,
        "lead_rows_updated": 0,
        "suppressed_events": 0,
        "outcome_counts": {},
    }
    if not received:
        return summary

    conn = connect_lead_ledger(db_path)
    try:
        for event in received:
            result = record_dispatch_outcome(conn, event)
            status = _strip(result.get("status"))
            if status:
                outcome_counts = dict(summary["outcome_counts"])
                outcome_counts[status] = int(outcome_counts.get(status, 0) or 0) + 1
                summary["outcome_counts"] = outcome_counts
            if result.get("ignored"):
                summary["ignored_events"] += 1
                continue
            if result.get("matched"):
                summary["matched_events"] += 1
                summary["dispatch_rows_updated"] += 1
                summary["lead_rows_updated"] += 1
                if result.get("auto_suppressed"):
                    summary["suppressed_events"] += 1
            else:
                summary["unmatched_events"] += 1
    finally:
        conn.close()
    return summary


def _import_row_already_seen(conn: sqlite3.Connection, source_file: str, row_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM lead_ledger_import_rows WHERE source_file = ? AND source_row_hash = ?",
        (source_file, row_hash),
    ).fetchone()
    return row is not None


def _record_import_row(
    conn: sqlite3.Connection,
    *,
    source_file: str,
    row_hash: str,
    lead_id: str,
    stage: str,
    status: str,
    imported_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO lead_ledger_import_rows (
            source_file,
            source_row_hash,
            lead_id,
            stage_imported,
            status_imported,
            imported_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_file, row_hash, lead_id, stage, status, imported_at),
    )


def import_leads_csv(
    conn: sqlite3.Connection,
    csv_path: Path,
    *,
    stage: str,
    status: str,
    run_id: str = "",
    imported_at: str | None = None,
) -> dict[str, object]:
    timestamp = imported_at or iso_utc()
    source_file = _workspace_label(csv_path)
    if not csv_path.exists():
        return {
            "source_file": source_file,
            "stage": stage,
            "status": status,
            "missing": True,
            "processed_rows": 0,
            "imported_rows": 0,
            "skipped_existing_rows": 0,
            "skipped_invalid_rows": 0,
        }

    with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    result = {
        "source_file": source_file,
        "stage": stage,
        "status": status,
        "missing": False,
        "processed_rows": 0,
        "imported_rows": 0,
        "skipped_existing_rows": 0,
        "skipped_invalid_rows": 0,
    }

    for row in rows:
        normalized_row = {str(key or "").strip(): _strip(value) for key, value in row.items() if str(key or "").strip()}
        if not any(normalized_row.values()):
            continue
        result["processed_rows"] += 1
        lead_payload = _lead_from_row(
            normalized_row,
            source_file=source_file,
            stage=stage,
            status=status,
            seen_at=timestamp,
        )
        if lead_payload is None:
            result["skipped_invalid_rows"] += 1
            continue
        row_hash = str(lead_payload["source_row_hash"])
        if _import_row_already_seen(conn, source_file, row_hash):
            result["skipped_existing_rows"] += 1
            continue

        existing = load_lead_by_id(conn, str(lead_payload["lead_id"]))
        with conn:
            lead = upsert_lead(conn, **lead_payload, updated_at=timestamp, created_at=timestamp)
            if existing is None:
                record_transition(
                    conn,
                    lead_id=str(lead["lead_id"]),
                    event_type="lead_imported",
                    stage_before="",
                    stage_after=stage,
                    status_before="",
                    status_after=status,
                    reason_code=next(iter(lead_payload["reason_codes"]), ""),
                    note=f"Imported from {source_file}",
                    run_id=run_id,
                    created_at=timestamp,
                )
            else:
                update_stage_status(
                    conn,
                    str(lead["lead_id"]),
                    stage_after=stage,
                    status_after=status,
                    reason_code=next(iter(lead_payload["reason_codes"]), ""),
                    note=f"Imported from {source_file}",
                    run_id=run_id,
                    event_type="lead_stage_backfilled",
                    updated_at=timestamp,
                )
            if lead_payload["reason_codes"]:
                record_reason_codes(
                    conn,
                    str(lead["lead_id"]),
                    lead_payload["reason_codes"],
                    note=f"Imported from {source_file}",
                    run_id=run_id,
                    created_at=timestamp,
                )
            _record_import_row(
                conn,
                source_file=source_file,
                row_hash=row_hash,
                lead_id=str(lead["lead_id"]),
                stage=stage,
                status=status,
                imported_at=timestamp,
            )
        result["imported_rows"] += 1

    return result


def backfill_lead_ledger(
    conn: sqlite3.Connection,
    *,
    csv_specs: Sequence[Mapping[str, object]] = DEFAULT_BACKFILL_SPECS,
    run_id: str = "",
    imported_at: str | None = None,
) -> dict[str, object]:
    timestamp = imported_at or iso_utc()
    file_reports: list[dict[str, object]] = []
    totals = {
        "processed_rows": 0,
        "imported_rows": 0,
        "skipped_existing_rows": 0,
        "skipped_invalid_rows": 0,
        "missing_files": 0,
    }
    for spec in csv_specs:
        report = import_leads_csv(
            conn,
            Path(str(spec.get("path") or "")),
            stage=str(spec.get("stage") or ""),
            status=str(spec.get("status") or ""),
            run_id=run_id,
            imported_at=timestamp,
        )
        file_reports.append(report)
        totals["processed_rows"] += int(report["processed_rows"])
        totals["imported_rows"] += int(report["imported_rows"])
        totals["skipped_existing_rows"] += int(report["skipped_existing_rows"])
        totals["skipped_invalid_rows"] += int(report["skipped_invalid_rows"])
        totals["missing_files"] += 1 if report["missing"] else 0

    return {
        "run_id": run_id or f"lead_ledger_backfill_{timestamp.replace(':', '').replace('-', '')}",
        "imported_at": timestamp,
        "file_reports": file_reports,
        **totals,
    }


def backfill_default_csv_outputs(
    db_path: Path = LEAD_LEDGER_DB_PATH,
    *,
    csv_specs: Sequence[Mapping[str, object]] = DEFAULT_BACKFILL_SPECS,
    run_id: str = "",
    imported_at: str | None = None,
) -> dict[str, object]:
    conn = connect_lead_ledger(db_path)
    try:
        return backfill_lead_ledger(
            conn,
            csv_specs=csv_specs,
            run_id=run_id,
            imported_at=imported_at,
        )
    finally:
        conn.close()
