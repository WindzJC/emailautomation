from __future__ import annotations

import csv
import difflib
import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence

import settings
import runtime_control
from email_validator import EmailNotValidError, EmailSyntaxError, EmailUndeliverableError, validate_email
from lead_ledger import connect_lead_ledger, deterministic_lead_id, dispatch_history_state, load_lead_by_id, record_dispatch_event, source_row_hash, upsert_lead
from leads_workflow import iso_utc, load_state, save_state, timestamp_slug, write_json_atomic
from recipient_file_lock import lock_files
from important_leads_verify import important_leads_triage_path_state, important_leads_verify_path_state
from send_shard import (
    CAMPAIGN_TYPE_COLD,
    PROFILES,
    PRODUCTION_SENDGRID_PROFILES,
    RECONTACT_CAMPAIGN_ID_RE,
    RECONTACT_SOURCE_KIND_FULL,
    RECONTACT_SOURCE_KIND_SAFER,
    ROLE_LOCALPART_BLOCKLIST,
    is_recontact_cold_campaign,
    is_role_recipient,
    load_already_done,
    load_bad_sendgrid_event_emails,
    load_done_statuses_from_logs,
    normalize_campaign_type,
    normalize_warm_personalization_line,
    normalized_warm_confirmation_payload,
    render_warm_email_copy,
    validate_warm_confirmed_queue,
    warm_confirmation_payload_hash,
)

from sendgrid_hygiene import load_active_suppressed_emails, norm_email
from tools.rebuild_recipient_queues import (
    SENDGRID_REQUIRED_HEADERS,
    active_campaign_manifest_path,
    build_queue_safety_report,
    default_sendgrid_log_paths,
    write_active_campaign_manifest,
)


IMPORTANT_DIR = settings.APP_ROOT / "_important"
CHECK_RUNS_DIR = IMPORTANT_DIR / "check_runs"
MASTER_INPUT_PATH = IMPORTANT_DIR / "leadschecker.csv"
MASTER_OUTPUT_PATH = IMPORTANT_DIR / "leads.csv"
MASTER_REJECTED_PATH = IMPORTANT_DIR / "leads_rejected.csv"
DISPOSABLE_DOMAINS_PATH = settings.APP_ROOT / "data" / "reference" / "disposable_domains.txt"

STATE_DIR = settings.STATE_DIR
BACKUP_ROOT = settings.BACKUPS_DIR
RECONTACT_RECENCY_HIGH_RISK_RATIO = 0.5
RECONTACT_RECENCY_YELLOW_FOUND_RATIO = 0.10
RECONTACT_RECENCY_YELLOW_MONTH_RATIO = 0.05
RECONTACT_RECENCY_RED_FOUND_RATIO = 0.30
RECONTACT_RECENCY_RED_MONTH_RATIO = 0.15
AUTHORITATIVE_CONTACT_HISTORY_STATUSES = {
    "accepted",
    "blocked",
    "bounce",
    "bounced",
    "click",
    "clicked",
    "complained",
    "complaint",
    "deferred",
    "delivered",
    "drop",
    "dropped",
    "invalid",
    "open",
    "opened",
    "processed",
    "sent",
    "spam_report",
    "spamreport",
    "unsubscribe",
    "unsubscribed",
}
NON_AUTHORITATIVE_HISTORY_STATUSES = {
    "",
    "planned",
    "preview",
    "previewed",
    "queued",
    "staged",
}
GLOBAL_BAD_CONTACT_HISTORY_STATUSES = {
    "blocked",
    "bounce",
    "bounced",
    "complained",
    "complaint",
    "drop",
    "dropped",
    "invalid",
    "spam_report",
    "spamreport",
    "unsubscribe",
    "unsubscribed",
}

DISPATCH_HISTORY_POLICY_VERSION = 2
FRESH_COLD_PRIOR_SUCCESS_POLICY = "block_global"
RECONTACT_PRIOR_SUCCESS_POLICY = "allow_informational"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_IN_TEXT_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
SAFE_SPLIT_RE = re.compile(r"[;,/|]+")
FIRST_NAME_PHONE_RE = re.compile(r"^[+()\d\s.\-]{5,}$")
FIRST_NAME_EMAIL_LIKE_RE = re.compile(r"^[^\s@]+@[^\s@]+$")

EMAIL_HEADER_CANDIDATES = (
    "email",
    "emailaddress",
    "email_address",
    "e_mail",
    "e-mail",
    "mail",
    "authoremail",
    "author_email",
    "contactemail",
    "contact_email",
)
FULL_NAME_HEADER_CANDIDATES = (
    "fullname",
    "full_name",
    "name",
    "authorname",
    "author_name",
    "author",
)
FIRST_NAME_HEADER_CANDIDATES = (
    "firstname",
    "first_name",
    "first name",
    "author_first_name",
)
LAST_NAME_HEADER_CANDIDATES = (
    "lastname",
    "last_name",
    "last name",
    "author_last_name",
)
BOOK_TITLE_HEADER_CANDIDATES = (
    "booktitle",
    "book_title",
    "title",
)
AUTHOR_EMAIL_HEADER_CANDIDATES = (
    "authoremail",
    "author_email",
)
AUTHOR_OUTREACH_HEADERS = (
    "AuthorEmail",
    "AuthorName",
    "Website",
    "SourceURL",
    "Location",
    "BookTitle",
    "BookURL",
    "RecentSignal",
    "IndieOrSmallPressSignal",
    "WebsitePresentationIssue",
    "WhyAstraFit",
    "PersonalizedOpeningLine",
    "ConfidenceScore",
)
AUTHOR_OUTREACH_HEADER_BY_KEY = {
    "".join(ch for ch in header.strip().lower() if ch.isalnum()): header
    for header in AUTHOR_OUTREACH_HEADERS
}

WARM_RESEARCH_HEADERS = (
    "AuthorName",
    "BookTitleOrProject",
    "NeedSignal",
    "SourcePlatform",
    "SourceURL",
    "ContactPath",
    "RecommendedService",
    "OutreachAngle",
)
WARM_RESEARCH_OPTIONAL_HEADERS = ("PersonalizationLine",)
WARM_RESEARCH_OUTPUT_HEADERS = (*WARM_RESEARCH_HEADERS, *WARM_RESEARCH_OPTIONAL_HEADERS, "ResearchStatus")
WARM_EMAIL_READY_HEADERS = (*WARM_RESEARCH_OUTPUT_HEADERS, "AuthorEmail", "ContactMethod")
WARM_CONTACT_FORM_HEADERS = (*WARM_RESEARCH_OUTPUT_HEADERS, "ContactMethod")
WARM_REJECTED_HEADERS = (
    *WARM_RESEARCH_OUTPUT_HEADERS,
    "AuthorEmail",
    "ContactMethod",
    "reject_code",
    "reject_reason",
)
WARM_EMAIL_PREVIEW_HEADERS = (
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
)
WARM_PRIVATE_JC_QUEUE_HEADERS = (
    "Email",
    "FirstName",
    *WARM_EMAIL_PREVIEW_HEADERS,
    "campaign_type",
    "campaign_id",
)
WARM_PRIVATE_JC_QUEUE_PATH = settings.SHARDS_DIR / "recipients_private_jc_warm.csv"
WARM_PRIVATE_JC_CONFIRMATION_PATH = settings.STATE_DIR / "warm_private_jc_confirmation.json"

COMMON_DOMAIN_FIXES = {
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "hotnail.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "outllok.com": "outlook.com",
    "outlok.com": "outlook.com",
    "yahho.com": "yahoo.com",
    "yaho.com": "yahoo.com",
    "yhoo.com": "yahoo.com",
}

MASTER_CHECK_STATE_KEY = "latest_master_check"
MASTER_DISPATCH_STATE_KEY = "latest_dispatch"
IMPORTANT_PATHS_STATE_KEY = "important_leads_paths"
IMPORTANT_DISPATCH_SOURCE_STATE_KEY = "important_leads_dispatch_source"
DISPATCH_SOURCE_TRIAGED_KEEP = "triaged_keep"
DISPATCH_SOURCE_STRICT_VERIFIED = "strict_verified"
DISPATCH_SOURCE_CLEANED = "cleaned"
DISPATCH_CAP_ALL = "all"
DISPATCH_CAP_OPTIONS = ("100", "500", "1000", DISPATCH_CAP_ALL)
TRIAGED_KEEP_PATH = IMPORTANT_DIR / "leads_triaged_keep.csv"
TRIAGED_REJECT_PATH = IMPORTANT_DIR / "leads_triaged_reject.csv"
TRIAGED_QUARANTINE_PATH = IMPORTANT_DIR / "leads_triaged_quarantine.csv"
STRICT_VERIFIED_PATH = IMPORTANT_DIR / "leads_verified.csv"
DISPATCH_PREVIEWS_DIR = STATE_DIR / "dispatch_previews"
DISPATCH_CONFIRMED_DIR = STATE_DIR / "dispatch_confirmed"
DISPATCH_RUN_HISTORY_PATH = STATE_DIR / "dispatch_run_history.json"
SAFER_RECONTACT_SUMMARY_PATH = STATE_DIR / "safer_recontact_source_summary.json"
SAFER_RECONTACT_SOURCE_FILENAME = "leads_safer_recontact_not_seen_active_history.csv"
DISPATCH_RUN_HISTORY_LIMIT = 100
CHECK_PREVIEW_ROWS = 8
DISPATCH_PREVIEW_ROWS = 8
AUTHOR_NAME_COUNT_HEADERS = ("AuthorName", "FullName", "FirstName")
BOOK_TITLE_COUNT_HEADERS = ("BookTitle", "Title", "booktitle", "book_title")
REQUIRED_DISPATCH_FIELDS = ("Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle")
AUDIT_OUTPUT_HEADERS = ("normalized_email", "correction_applied", "correction_reason")
ROLE_ACCOUNT_BLOCKLIST = set(ROLE_LOCALPART_BLOCKLIST) | {
    "admin",
    "contact",
    "hello",
    "info",
    "no-reply",
    "noreply",
    "office",
    "sales",
    "support",
    "team",
}
FIRST_NAME_HONORIFICS = {
    "dr",
    "doctor",
    "rev",
    "reverend",
    "pastor",
    "prof",
    "professor",
    "mr",
    "mrs",
    "ms",
    "miss",
}
FIRST_NAME_CREDENTIALS = {
    "cpa",
    "dds",
    "dmd",
    "do",
    "esq",
    "jd",
    "mba",
    "md",
    "phd",
    "rn",
}
FIRST_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
FIRST_NAME_ROLE_TITLES = {
    "author",
    "ceo",
    "chair",
    "coach",
    "cofounder",
    "consultant",
    "director",
    "founder",
    "manager",
    "owner",
    "president",
    "speaker",
    "writer",
}
FIRST_NAME_GENERIC_BUSINESS = {
    "admin",
    "billing",
    "contact",
    "customerservice",
    "help",
    "hello",
    "info",
    "inquiries",
    "marketing",
    "office",
    "sales",
    "service",
    "support",
    "team",
    "unknown",
}
KNOWN_COMMON_DOMAINS = sorted(set(COMMON_DOMAIN_FIXES.values()) | {
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "outlook.com",
    "yahoo.com",
})
REJECT_REASON_TEXT = {
    "BLANK_ROW": "Row was blank after parsing.",
    "DISPOSABLE_DOMAIN": "Disposable email domain rejected.",
    "DUPLICATE_IN_BATCH": "Duplicate normalized email within this batch.",
    "INVALID_EMAIL_SYNTAX": "Email failed syntax validation.",
    "MISSING_EMAIL": "Email cell is empty.",
    "MULTIPLE_EMAILS_IN_CELL": "Cell appears to contain more than one email address.",
    "NO_EMAIL_HEADER": "No usable email column could be inferred.",
    "ROLE_ACCOUNT": "Role-based inbox rejected by policy.",
    "SUPPRESSED": "Email is already suppressed or unsubscribed.",
    "UNDELIVERABLE_DOMAIN": "Email domain is not configured to receive mail.",
    "UNKNOWN_DOMAIN_TYPO": "Domain looks mistyped but is not on the approved correction list.",
    "UNREADABLE_CSV": "CSV content could not be parsed safely.",
}


class ImportantLeadsCheckError(ValueError):
    def __init__(self, code: str, message: str, *, details: Dict[str, object] | None = None):
        super().__init__(message)
        self.code = str(code or "UNREADABLE_CSV").strip().upper()
        self.message = str(message or "").strip()
        self.details = details or {}


def _normalize_header_key(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum())


def _strip_cell(value: object) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _bool_env(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return max(minimum, int(default))
    try:
        return max(minimum, int(raw))
    except Exception:
        return max(minimum, int(default))


@lru_cache(maxsize=1)
def _dns_support_available() -> bool:
    try:
        import dns.resolver  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def _should_validate_deliverability() -> bool:
    return _bool_env("CHECK_LEADS_VALIDATE_DELIVERABILITY", True) and _dns_support_available()


def _should_reject_role_accounts() -> bool:
    return _bool_env("CHECK_LEADS_REJECT_ROLE_ACCOUNTS", True)


def _should_reject_disposable() -> bool:
    return _bool_env("CHECK_LEADS_REJECT_DISPOSABLE", True)


def _reject_reason_text(code: str, fallback: str = "") -> str:
    normalized = str(code or "").strip().upper()
    if fallback:
        return fallback.strip()
    return REJECT_REASON_TEXT.get(normalized, normalized.replace("_", " ").title())


@lru_cache(maxsize=16)
def _load_disposable_domains(path_value: str) -> frozenset[str]:
    path = Path(path_value)
    if not path.exists():
        return frozenset()
    domains: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        domains.add(line)
    return frozenset(domains)


def _trimmed_first_name(value: str) -> str:
    raw = _strip_cell(value)
    if not raw:
        return ""
    token = raw.split()[0]
    return re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", token) or token


def _normalize_name_whitespace(value: object) -> str:
    return re.sub(r"\s+", " ", _strip_cell(value)).strip()


def _strip_balanced_name_wrappers(value: str) -> str:
    text = _normalize_name_whitespace(value)
    changed = True
    while changed and text:
        changed = False
        if len(text) >= 2 and text[0] in "\"“”‘’" and text[-1] in "\"“”‘’":
            text = _normalize_name_whitespace(text[1:-1])
            changed = True
        if len(text) >= 2 and text[0] == "(" and text[-1] == ")":
            text = _normalize_name_whitespace(text[1:-1])
            changed = True
    return text.strip(" \t\r\n,;")


def _name_lookup_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")).lower()


def _name_has_letter(value: str) -> bool:
    return any(ch.isalpha() for ch in value or "")


def _name_letter_count(value: str) -> int:
    return sum(1 for ch in value or "" if ch.isalpha())


def _name_punctuation_ratio(value: str) -> float:
    text = value or ""
    meaningful = [ch for ch in text if not ch.isspace()]
    if not meaningful:
        return 1.0
    punctuation = [ch for ch in meaningful if not ch.isalnum()]
    return len(punctuation) / len(meaningful)


def _looks_like_mojibake(value: str) -> bool:
    text = value or ""
    if "\ufffd" in text:
        return True
    return any(token in text for token in ("Ã", "Â", "â€", "â€™", "ðŸ", "�"))


def _first_name_candidate(value: object) -> str:
    text = _strip_balanced_name_wrappers(str(value or ""))
    if not text:
        return ""
    parts = text.split()
    if len(parts) > 1 and all(len(part.strip(".")) == 1 for part in parts):
        return text
    return text


def _first_name_hygiene(value: object) -> Dict[str, str]:
    raw = _normalize_name_whitespace(value)
    candidate = _first_name_candidate(raw)
    result = {
        "first_name_clean": "",
        "first_name_status": "",
        "personalization_allowed": "false",
        "cleanup_notes": "",
    }

    def invalid(status: str) -> Dict[str, str]:
        result["first_name_status"] = status
        result["cleanup_notes"] = f"first_name:{status}"
        return result

    if not candidate:
        return invalid("blank")
    if raw and raw[0] in {":", "'", "’"}:
        return invalid("surrounding_punctuation")
    if _looks_like_mojibake(candidate):
        return invalid("mojibake")
    if FIRST_NAME_EMAIL_LIKE_RE.match(candidate) or "@" in candidate:
        return invalid("email_like")
    if FIRST_NAME_PHONE_RE.match(candidate):
        return invalid("phone_like")
    if _name_punctuation_ratio(candidate) >= 0.6:
        return invalid("mostly_punctuation")
    if not _name_has_letter(candidate):
        return invalid("blank")

    no_period = candidate.replace(".", "")
    letters_only = "".join(ch for ch in no_period if ch.isalpha())
    compact_lookup = _name_lookup_key(candidate)
    if compact_lookup in FIRST_NAME_HONORIFICS:
        return invalid("honorific_only")
    if compact_lookup in FIRST_NAME_CREDENTIALS:
        return invalid("credential_only")
    if compact_lookup in FIRST_NAME_SUFFIXES:
        return invalid("suffix_only")
    if compact_lookup in FIRST_NAME_ROLE_TITLES:
        return invalid("role_title_only")
    if compact_lookup in FIRST_NAME_GENERIC_BUSINESS:
        return invalid("generic_business")
    if re.fullmatch(r"(?:[A-Za-z]\.){1,4}", candidate.replace(" ", "")):
        return invalid("dotted_initials")
    if _name_letter_count(candidate) <= 1:
        return invalid("one_character")
    if re.fullmatch(r"[A-Za-z](?:\s+[A-Za-z])+", candidate):
        return invalid("initials_only")
    if letters_only and letters_only.isupper() and len(letters_only) <= 3:
        return invalid("initials_only")

    result["first_name_clean"] = candidate
    result["first_name_status"] = "valid"
    result["personalization_allowed"] = "true"
    result["cleanup_notes"] = "" if candidate == raw else "first_name:normalized_wrappers"
    return result


def _last_name_clean(value: object) -> str:
    return _strip_balanced_name_wrappers(str(value or ""))


def _first_name_source(raw_row: Dict[str, str], normalized_row: Dict[str, str], core_headers: Dict[str, str]) -> str:
    if core_headers.get("FirstName"):
        first_raw = _strip_cell(raw_row.get(core_headers["FirstName"], ""))
        if first_raw:
            return first_raw
    full_name = _normalize_name_whitespace(normalized_row.get("FullName", ""))
    if full_name:
        return full_name.split()[0]
    return ""


def _full_identity_value(row: Dict[str, str], core_headers: Dict[str, str]) -> str:
    full_header = core_headers.get("FullName", "")
    first_header = core_headers.get("FirstName", "")
    last_header = core_headers.get("LastName", "")
    if full_header and _strip_cell(row.get(full_header, "")):
        return _strip_cell(row.get(full_header, ""))
    if first_header and last_header:
        first = _strip_cell(row.get(first_header, ""))
        last = _strip_cell(row.get(last_header, ""))
        if first and last:
            return f"{first} {last}".strip()
    if first_header and _strip_cell(row.get(first_header, "")):
        return _strip_cell(row.get(first_header, ""))
    return ""


def _pick_header(fieldnames: Sequence[str], candidates: Sequence[str]) -> str:
    normalized = {_normalize_header_key(name): name for name in fieldnames if name}
    for candidate in candidates:
        match = normalized.get(_normalize_header_key(candidate))
        if match:
            return match
    return ""


def _normalize_csv_text(raw_text: str) -> str:
    text = str(raw_text or "").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    return text


def _sniff_csv_format(text: str) -> Dict[str, object]:
    sample = "\n".join(text.splitlines()[:25])
    if not sample.strip():
        return {"delimiter": ",", "quotechar": '"', "skipinitialspace": False, "has_header_guess": False}
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        try:
            has_header = csv.Sniffer().has_header(sample)
        except csv.Error:
            has_header = False
        return {
            "delimiter": dialect.delimiter,
            "quotechar": getattr(dialect, "quotechar", '"') or '"',
            "skipinitialspace": bool(getattr(dialect, "skipinitialspace", False)),
            "has_header_guess": bool(has_header),
        }
    except csv.Error:
        delimiter = "\t" if "\t" in sample else (";" if ";" in sample else ",")
        return {"delimiter": delimiter, "quotechar": '"', "skipinitialspace": False, "has_header_guess": False}


def _read_csv_document(path: Path) -> Dict[str, object]:
    raw_text = _normalize_csv_text(path.read_text(encoding="utf-8-sig", errors="replace")) if path.exists() else ""
    if not raw_text.strip():
        return {
            "fieldnames": [],
            "rows": [],
            "blank_rows": 0,
            "delimiter": ",",
            "quotechar": '"',
        }

    fmt = _sniff_csv_format(raw_text)
    try:
        reader = csv.reader(
            StringIO(raw_text),
            delimiter=str(fmt["delimiter"]),
            quotechar=str(fmt["quotechar"]),
            skipinitialspace=bool(fmt["skipinitialspace"]),
        )
        parsed_rows = [[_strip_cell(cell) for cell in row] for row in reader]
    except csv.Error as exc:
        raise ImportantLeadsCheckError("UNREADABLE_CSV", f"Could not parse {path.name}: {exc}") from exc

    non_blank_rows: List[List[str]] = []
    blank_rows = 0
    for row in parsed_rows:
        if any(value for value in row):
            non_blank_rows.append(row)
        else:
            blank_rows += 1

    if not non_blank_rows:
        return {
            "fieldnames": [],
            "rows": [],
            "blank_rows": blank_rows,
            "delimiter": str(fmt["delimiter"]),
            "quotechar": str(fmt["quotechar"]),
        }

    first_row = non_blank_rows[0]
    header_detection = _detect_core_headers(first_row)
    has_header = bool(header_detection["Email"] or header_detection["FirstName"] or header_detection["BookTitle"])
    if not has_header and bool(fmt["has_header_guess"]):
        has_header = True

    if has_header:
        raw_headers = [str(cell or "").lstrip("\ufeff").strip() or f"Column_{index + 1}" for index, cell in enumerate(first_row)]
        fieldnames = list(raw_headers)
        data_rows = non_blank_rows[1:]
    elif len(first_row) == 2:
        fieldnames = ["FirstName", "Email"]
        data_rows = non_blank_rows
    else:
        raise ImportantLeadsCheckError(
            "NO_EMAIL_HEADER",
            f"Could not detect an email column in {path.name}",
            details={"first_row": first_row},
        )

    max_columns = max((len(row) for row in data_rows), default=len(fieldnames))
    while len(fieldnames) < max_columns:
        fieldnames.append(f"Column_{len(fieldnames) + 1}")

    rows: List[Dict[str, str]] = []
    for raw_row in data_rows:
        row = {
            fieldnames[index]: _strip_cell(raw_row[index]) if index < len(raw_row) else ""
            for index in range(len(fieldnames))
        }
        rows.append(row)

    return {
        "fieldnames": fieldnames,
        "rows": rows,
        "blank_rows": blank_rows,
        "delimiter": str(fmt["delimiter"]),
        "quotechar": str(fmt["quotechar"]),
    }


def _read_csv_rows(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    document = _read_csv_document(path)
    return list(document["fieldnames"]), list(document["rows"])


def _write_csv_atomic(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    row_list = list(rows)
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
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(row_list)
    tmp_path.replace(path)
    settings.secure_private_file(path)


def _stage_csv_payload(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.dispatch.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(list(rows))
            handle.flush()
            os.fsync(handle.fileno())
        return tmp_path
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


FileSnapshot = tuple[bytes, int, int, int] | None


def _snapshot_file(path: Path, snapshots: Dict[Path, FileSnapshot]) -> None:
    if path not in snapshots:
        if path.exists():
            metadata = path.stat()
            snapshots[path] = (
                path.read_bytes(),
                metadata.st_atime_ns,
                metadata.st_mtime_ns,
                metadata.st_mode,
            )
        else:
            snapshots[path] = None


def _restore_file_snapshots(snapshots: Dict[Path, FileSnapshot]) -> None:
    for path, original in reversed(list(snapshots.items())):
        if original is None:
            path.unlink(missing_ok=True)
            continue
        content, atime_ns, mtime_ns, mode = original
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.rollback.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            restore_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        restore_path.replace(path)
        os.chmod(path, mode & 0o7777)
        os.utime(path, ns=(atime_ns, mtime_ns))


def _detect_core_headers(fieldnames: Sequence[str]) -> Dict[str, str]:
    return {
        "Email": _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES),
        "AuthorEmail": _pick_header(fieldnames, AUTHOR_EMAIL_HEADER_CANDIDATES),
        "FullName": _pick_header(fieldnames, FULL_NAME_HEADER_CANDIDATES),
        "FirstName": _pick_header(fieldnames, FIRST_NAME_HEADER_CANDIDATES),
        "LastName": _pick_header(fieldnames, LAST_NAME_HEADER_CANDIDATES),
        "BookTitle": _pick_header(fieldnames, BOOK_TITLE_HEADER_CANDIDATES),
    }


def _unique_header(value: str, used: set[str]) -> str:
    base = SAFE_FILENAME_RE.sub("_", (value or "").strip()).strip("._") or "Column"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _master_output_headers(fieldnames: Sequence[str], core_headers: Dict[str, str]) -> tuple[List[str], Dict[str, str]]:
    used: set[str] = set()
    output_headers = [
        "FullName",
        "FirstName",
        "Email",
        "first_name_clean",
        "last_name_clean",
        "first_name_status",
        "personalization_allowed",
        "cleanup_notes",
        "last_name",
    ]
    used.update(output_headers)
    source_to_output: Dict[str, str] = {}

    full_source = core_headers.get("FullName", "")
    first_source = core_headers.get("FirstName", "")
    last_source = core_headers.get("LastName", "")
    email_source = core_headers.get("Email", "")

    if full_source:
        source_to_output[full_source] = "FullName"
    if first_source:
        source_to_output[first_source] = "FirstName"
    if last_source:
        source_to_output[last_source] = "last_name"
    if email_source:
        source_to_output[email_source] = "Email"

    for source in fieldnames:
        canonical = AUTHOR_OUTREACH_HEADER_BY_KEY.get(_normalize_header_key(source))
        if not canonical:
            continue
        if canonical not in used:
            output_headers.append(canonical)
            used.add(canonical)
        # If AuthorEmail or AuthorName were also used as core Email/FullName,
        # keep the original author outreach column in addition to normalized Email/FullName.
        if source not in source_to_output:
            source_to_output[source] = canonical

    for source in fieldnames:
        if source in source_to_output:
            continue
        canonical = AUTHOR_OUTREACH_HEADER_BY_KEY.get(_normalize_header_key(source))
        source_to_output[source] = canonical if canonical else _unique_header(source, used)
        output_headers.append(source_to_output[source])
    return output_headers, source_to_output


def _disposable_domain_set(path: Path) -> set[str]:
    return set(_load_disposable_domains(str(path.resolve())))


def _normalize_email_candidate(raw_value: str) -> Dict[str, str]:
    raw = _strip_cell(raw_value)
    result = {
        "raw_email": raw,
        "candidate_email": "",
        "normalized_email": "",
        "correction_applied": "",
        "correction_reason": "",
        "reject_code": "",
        "reject_reason": "",
    }
    if not raw:
        result["reject_code"] = "MISSING_EMAIL"
        result["reject_reason"] = _reject_reason_text("MISSING_EMAIL")
        return result

    candidate_text = re.sub(r"^\s*mailto:\s*", "", raw, flags=re.IGNORECASE)
    matches = EMAIL_IN_TEXT_RE.findall(candidate_text)
    if len(matches) > 1:
        result["reject_code"] = "MULTIPLE_EMAILS_IN_CELL"
        result["reject_reason"] = _reject_reason_text("MULTIPLE_EMAILS_IN_CELL")
        return result

    candidate = matches[0] if matches else candidate_text
    candidate = candidate.strip().strip("<>()[]{}\"'")
    candidate = candidate.rstrip(".,;:!?")
    candidate = candidate.replace(" ", "")
    candidate = candidate.lower()
    result["candidate_email"] = candidate

    if candidate.count("@") != 1:
        result["reject_code"] = "MULTIPLE_EMAILS_IN_CELL" if SAFE_SPLIT_RE.search(raw) else "INVALID_EMAIL_SYNTAX"
        result["reject_reason"] = _reject_reason_text(result["reject_code"])
        return result

    local, domain = candidate.split("@", 1)
    if not local or not domain:
        result["reject_code"] = "INVALID_EMAIL_SYNTAX"
        result["reject_reason"] = _reject_reason_text("INVALID_EMAIL_SYNTAX")
        return result

    fixed_domain = COMMON_DOMAIN_FIXES.get(domain, domain)
    if fixed_domain != domain:
        result["correction_applied"] = "true"
        result["correction_reason"] = f"allowlisted_domain_fix:{domain}->{fixed_domain}"
        candidate = f"{local}@{fixed_domain}"
    else:
        close_match = difflib.get_close_matches(domain, KNOWN_COMMON_DOMAINS, n=1, cutoff=0.88)
        if close_match and close_match[0] != domain:
            result["reject_code"] = "UNKNOWN_DOMAIN_TYPO"
            result["reject_reason"] = _reject_reason_text(
                "UNKNOWN_DOMAIN_TYPO",
                f"Domain looks mistyped ({domain}); closest known domain is {close_match[0]}.",
            )
            return result

    result["candidate_email"] = candidate
    return result


def _validated_email_result(candidate: str, *, check_deliverability: bool) -> Dict[str, str]:
    try:
        validated = validate_email(candidate, check_deliverability=check_deliverability)
    except EmailSyntaxError as exc:
        return {
            "normalized_email": "",
            "reject_code": "INVALID_EMAIL_SYNTAX",
            "reject_reason": _reject_reason_text("INVALID_EMAIL_SYNTAX", str(exc)),
        }
    except EmailUndeliverableError as exc:
        return {
            "normalized_email": "",
            "reject_code": "UNDELIVERABLE_DOMAIN",
            "reject_reason": _reject_reason_text("UNDELIVERABLE_DOMAIN", str(exc)),
        }
    except EmailNotValidError as exc:
        return {
            "normalized_email": "",
            "reject_code": "INVALID_EMAIL_SYNTAX",
            "reject_reason": _reject_reason_text("INVALID_EMAIL_SYNTAX", str(exc)),
        }
    except Exception as exc:
        if check_deliverability:
            return _validated_email_result(candidate, check_deliverability=False)
        return {
            "normalized_email": "",
            "reject_code": "INVALID_EMAIL_SYNTAX",
            "reject_reason": _reject_reason_text("INVALID_EMAIL_SYNTAX", str(exc)),
        }

    return {
        "normalized_email": norm_email(getattr(validated, "normalized", candidate)),
        "reject_code": "",
        "reject_reason": "",
    }


def _email_validation_result(raw_value: str, *, check_deliverability: bool) -> Dict[str, str]:
    prepped = _normalize_email_candidate(raw_value)
    if prepped["reject_code"]:
        return prepped
    validation = _validated_email_result(prepped["candidate_email"], check_deliverability=check_deliverability)
    prepped.update(validation)
    return prepped


def _row_richness(row: Dict[str, str]) -> int:
    score = 0
    for key, value in row.items():
        if key == "Email":
            continue
        if _strip_cell(value):
            score += 1
    return score


def _rejected_row(
    row: Dict[str, str],
    *,
    reject_code: str,
    reject_reason: str,
    normalized_email: str = "",
    correction_applied: str = "",
    correction_reason: str = "",
) -> Dict[str, str]:
    rejected = {key: _strip_cell(value) for key, value in row.items()}
    rejected["normalized_email"] = _strip_cell(normalized_email)
    rejected["correction_applied"] = _strip_cell(correction_applied)
    rejected["correction_reason"] = _strip_cell(correction_reason)
    rejected["reject_code"] = str(reject_code or "").strip().upper()
    rejected["reject_reason"] = _strip_cell(reject_reason or _reject_reason_text(rejected["reject_code"]))
    return rejected


def _load_simple_email_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    fieldnames, rows = _read_csv_rows(path)
    email_header = _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES)
    if not email_header:
        return set()
    out: set[str] = set()
    for row in rows:
        email = norm_email(row.get(email_header, ""))
        if email:
            out.add(email)
    return out


def _blocked_email_set(
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
) -> tuple[set[str], Dict[str, object]]:
    sendgrid_blocked, suppression_summary = load_active_suppressed_emails(sendgrid_suppressions_path)
    local_suppressed = _load_simple_email_set(suppressed_path)
    local_unsubscribed = _load_simple_email_set(unsubscribed_path)
    blocked = set(sendgrid_blocked) | local_suppressed | local_unsubscribed
    return blocked, {
        "total_perm": int(suppression_summary.get("total_perm", 0) or 0),
        "total_temp_active": int(suppression_summary.get("total_temp_active", 0) or 0),
    }


def _warm_research_rows(path: Path) -> tuple[List[Dict[str, str]], int]:
    text = _normalize_csv_text(path.read_text(encoding="utf-8-sig", errors="replace"))
    if not text.strip():
        raise ImportantLeadsCheckError("WARM_UPLOAD_EMPTY", "Warm Research upload is empty.")
    fmt = _sniff_csv_format(text)
    reader = csv.DictReader(
        StringIO(text),
        delimiter=str(fmt["delimiter"]),
        quotechar=str(fmt["quotechar"]),
        skipinitialspace=bool(fmt["skipinitialspace"]),
    )
    raw_headers = [str(value or "").lstrip("\ufeff").strip() for value in (reader.fieldnames or [])]
    header_by_key = {_normalize_header_key(header): header for header in raw_headers if header}
    missing = [header for header in WARM_RESEARCH_HEADERS if _normalize_header_key(header) not in header_by_key]
    if missing:
        raise ImportantLeadsCheckError(
            "WARM_HEADERS_MISSING",
            "Warm Research upload is missing required columns: " + ", ".join(missing),
            details={"required_headers": list(WARM_RESEARCH_HEADERS), "missing_headers": missing},
        )

    rows: List[Dict[str, str]] = []
    blank_rows = 0
    status_header = header_by_key.get(_normalize_header_key("Status"), "")
    research_status_header = header_by_key.get(_normalize_header_key("ResearchStatus"), "")
    for raw_row in reader:
        row = {
            header: _strip_cell(raw_row.get(header_by_key[_normalize_header_key(header)], ""))
            for header in WARM_RESEARCH_HEADERS
        }
        for header in WARM_RESEARCH_OPTIONAL_HEADERS:
            source_header = header_by_key.get(_normalize_header_key(header), "")
            row[header] = _strip_cell(raw_row.get(source_header, "")) if source_header else ""
        status_value = _strip_cell(raw_row.get(status_header, "")) if status_header else ""
        research_status_value = _strip_cell(raw_row.get(research_status_header, "")) if research_status_header else ""
        if not any(row.values()) and not status_value and not research_status_value:
            blank_rows += 1
            continue
        row["ResearchStatus"] = research_status_value or status_value or "New"
        rows.append(row)
    return rows, blank_rows


def check_warm_research_leads(
    *,
    input_path: Path,
    email_ready_path: Path,
    contact_form_review_path: Path,
    rejected_path: Path,
    log_paths: Sequence[Path] | None = None,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    bad_events_path: Path = settings.WEBHOOK_EVENTS_PATH,
    lead_ledger_db_path: Path | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Dict[str, object]:
    """Validate a warm-research upload without feeding cold dispatch state."""
    rows, blank_rows = _warm_research_rows(input_path)
    authoritative_logs = list(log_paths) if log_paths is not None else _warm_authoritative_log_paths()
    already_contacted = _sent_email_set(authoritative_logs)
    log_blocked = load_done_statuses_from_logs(
        authoritative_logs,
        {"INVALID", "BOUNCE", "BOUNCED", "DROPPED", "SPAMREPORT", "UNSUBSCRIBE", "UNSUBSCRIBED", "BLOCKED"},
    )
    blocked, suppression_summary = _blocked_email_set(
        sendgrid_suppressions_path,
        suppressed_path,
        unsubscribed_path,
    )
    bad_event_emails = load_bad_sendgrid_event_emails(bad_events_path)
    blocked |= log_blocked | bad_event_emails

    parsed: List[tuple[Dict[str, str], str, str, str, str]] = []
    source_lead_ids: set[str] = set()
    for row in rows:
        contact_path = _strip_cell(row.get("ContactPath", ""))
        matches = list(dict.fromkeys(norm_email(value) for value in EMAIL_IN_TEXT_RE.findall(contact_path)))
        matches = [value for value in matches if value]
        email = ""
        contact_method = ""
        reject_code = ""
        reject_reason = ""
        if len(matches) > 1:
            reject_code = "MULTIPLE_EMAILS_IN_CONTACT_PATH"
            reject_reason = "ContactPath contains more than one email address."
        elif matches:
            validation = _email_validation_result(matches[0], check_deliverability=False)
            email = norm_email(validation.get("normalized_email", ""))
            if validation.get("reject_code") or not email:
                reject_code = str(validation.get("reject_code") or "INVALID_EMAIL_SYNTAX")
                reject_reason = str(validation.get("reject_reason") or "ContactPath contains an invalid email address.")
            else:
                contact_method = "email"
                source_lead_ids.add(deterministic_lead_id(email))
        elif "@" in contact_path:
            reject_code = "INVALID_EMAIL_SYNTAX"
            reject_reason = "ContactPath contains an invalid email address."
        elif re.search(r"https?://", contact_path, flags=re.IGNORECASE):
            contact_method = "contact_form"
        else:
            reject_code = "MISSING_CONTACT_PATH"
            reject_reason = "ContactPath must contain a direct email or contact-form URL."
        parsed.append((row, email, contact_method, reject_code, reject_reason))

    ledger_contacted: set[str] = set()
    ledger_path = _lead_ledger_db_path(lead_ledger_db_path)
    ledger_conn = connect_lead_ledger(ledger_path)
    try:
        astra_ids, astra_warm_ids, _sendgrid_ids, global_bad_ids, _ignored_ids = _dispatch_history_contact_sets(
            ledger_conn,
            source_lead_ids,
        )
        authoritative_ids = astra_ids | astra_warm_ids | global_bad_ids
        ledger_contacted = {
            email
            for _row, email, _method, _code, _reason in parsed
            if email and deterministic_lead_id(email) in authoritative_ids
        }
    finally:
        ledger_conn.close()
    already_contacted |= ledger_contacted

    email_ready: List[Dict[str, str]] = []
    contact_forms: List[Dict[str, str]] = []
    rejected: List[Dict[str, str]] = []
    reason_counts: Counter[str] = Counter()
    seen_emails: set[str] = set()
    seen_contact_paths: set[str] = set()
    total = len(parsed)
    for index, (row, email, contact_method, reject_code, reject_reason) in enumerate(parsed, start=1):
        code = reject_code
        reason = reject_reason
        if not code and contact_method == "email":
            if email in seen_emails:
                code, reason = "DUPLICATE_IN_BATCH", "Duplicate direct email in this Warm Research upload."
            else:
                seen_emails.add(email)
                if email in blocked:
                    code, reason = "SUPPRESSED", "Email is blocked by suppression, unsubscribe, or bad-event history."
                elif email in already_contacted:
                    code, reason = "ALREADY_CONTACTED", "Email appears in authoritative Private JC, SendGrid, or contact history."
                else:
                    personalization_line = normalize_warm_personalization_line(
                        row.get("PersonalizationLine", "")
                    )
                    if not personalization_line:
                        code = "PERSONALIZATION_REVIEW_REQUIRED"
                        reason = "Manual review required: missing or invalid PersonalizationLine."
                    else:
                        row["PersonalizationLine"] = personalization_line
        elif not code and contact_method == "contact_form":
            contact_key = _strip_cell(row.get("ContactPath", "")).lower().rstrip("/")
            if contact_key in seen_contact_paths:
                code, reason = "DUPLICATE_IN_BATCH", "Duplicate contact-form path in this Warm Research upload."
            else:
                seen_contact_paths.add(contact_key)

        if code:
            reason_counts[code] += 1
            rejected.append({
                **row,
                "AuthorEmail": email,
                "ContactMethod": contact_method,
                "reject_code": code,
                "reject_reason": reason,
            })
        elif contact_method == "email":
            email_ready.append({**row, "AuthorEmail": email, "ContactMethod": "email"})
        else:
            contact_forms.append({**row, "ContactMethod": "contact_form"})
        if progress_callback:
            progress_callback(index, total)

    _write_csv_atomic(email_ready_path, WARM_EMAIL_READY_HEADERS, email_ready)
    _write_csv_atomic(contact_form_review_path, WARM_CONTACT_FORM_HEADERS, contact_forms)
    _write_csv_atomic(rejected_path, WARM_REJECTED_HEADERS, rejected)
    return {
        "upload_type": "warm_research",
        "upload_type_label": "Warm Research",
        "generated_at_utc": iso_utc(),
        "input_label": _display_path_label(input_path),
        "email_ready_label": _display_path_label(email_ready_path),
        "contact_form_review_label": _display_path_label(contact_form_review_path),
        "rejected_label": _display_path_label(rejected_path),
        "input_rows": len(rows),
        "total_input_rows": len(rows),
        "warm_email_ready_rows": len(email_ready),
        "warm_contact_form_rows": len(contact_forms),
        "warm_rejected_rows": len(rejected),
        "already_contacted_rows": int(reason_counts.get("ALREADY_CONTACTED", 0)),
        "duplicates_removed": int(reason_counts.get("DUPLICATE_IN_BATCH", 0)),
        "invalid_removed": int(reason_counts.get("INVALID_EMAIL_SYNTAX", 0)) + int(reason_counts.get("MULTIPLE_EMAILS_IN_CONTACT_PATH", 0)),
        "suppressed_removed": int(reason_counts.get("SUPPRESSED", 0)),
        "blank_rows": blank_rows,
        "reason_counts": dict(reason_counts),
        "suppression_summary": suppression_summary,
        "output_fieldnames": list(WARM_EMAIL_READY_HEADERS),
        "output_preview_rows": [],
        "message": "Warm upload checked. Generate Warm Draft Preview before explicit Warm Private JC confirmation.",
        "dispatch_enabled": False,
    }



def _clean_warm_outreach_angle(value: str) -> str:
    text = _strip_cell(value)
    text = re.sub(r"^\s*pitch\s+", "", text, flags=re.IGNORECASE)
    return text[:1].lower() + text[1:] if text else text

EXPECTED_WARM_PREVIEW_FILENAME = "warm_email_preview.csv"

def generate_warm_email_preview(
    *,
    email_ready_path: Path,
    preview_path: Path,
) -> Dict[str, object]:
    preview_path = Path(preview_path)
    if preview_path.name != EXPECTED_WARM_PREVIEW_FILENAME:
        raise ValueError(
            f"Warm preview output filename must be {EXPECTED_WARM_PREVIEW_FILENAME}"
        )

    fieldnames, rows = _read_csv_rows(email_ready_path)
    required = {"AuthorName", "AuthorEmail", "BookTitleOrProject", "NeedSignal", "RecommendedService", "OutreachAngle"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise ImportantLeadsCheckError(
            "WARM_EMAIL_READY_HEADERS_MISSING",
            "Warm email-ready source is missing required columns: " + ", ".join(missing),
            details={"missing_headers": missing},
        )

    preview_rows: List[Dict[str, str]] = []
    for row in rows:
        email = norm_email(row.get("AuthorEmail", ""))
        if not email or str(row.get("ContactMethod") or "email").strip().lower() != "email":
            continue
        first_name = _trimmed_first_name(row.get("AuthorName", "")) or "there"
        book_title = _strip_cell(row.get("BookTitleOrProject", ""))
        rendered_copy = render_warm_email_copy(
            first_name=first_name,
            book_title_or_project=book_title,
            recommended_service=_strip_cell(row.get("RecommendedService", "")),
            personalization_line=_strip_cell(row.get("PersonalizationLine", "")),
        )
        preview_rows.append({
            "AuthorName": _strip_cell(row.get("AuthorName", "")),
            "AuthorEmail": email,
            "BookTitleOrProject": book_title,
            "EmailSubject": str(rendered_copy["subject"]),
            "EmailBody": str(rendered_copy["body"]),
            "NeedSignal": _strip_cell(row.get("NeedSignal", "")),
            "RecommendedService": _strip_cell(row.get("RecommendedService", "")),
            "OutreachAngle": _clean_warm_outreach_angle(row.get("OutreachAngle", "")),
            "SourceURL": _strip_cell(row.get("SourceURL", "")),
            "ContactPath": _strip_cell(row.get("ContactPath", "")),
            "ResearchStatus": _strip_cell(row.get("ResearchStatus", "")) or "New",
        })

    _write_csv_atomic(preview_path, WARM_EMAIL_PREVIEW_HEADERS, preview_rows)
    return {
        "generated_at_utc": iso_utc(),
        "source_label": _display_path_label(email_ready_path),
        "output_label": _display_path_label(preview_path),
        "warm_email_preview_rows": len(preview_rows),
        "dispatch_enabled": False,
        "warm_confirmation_enabled": True,
        "message": "Warm draft preview generated. Explicit Warm Private JC confirmation is required before queue creation.",
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _warm_authoritative_log_paths() -> List[Path]:
    paths: List[Path] = []
    for cfg in PROFILES.values():
        if str(cfg.get("provider") or "").strip().lower() not in {"private", "sendgrid"}:
            continue
        for key in ("log", "domain_log"):
            value = str(cfg.get(key) or "").strip()
            if not value:
                continue
            path = settings.log_path(value)
            if path not in paths:
                paths.append(path)
    return paths


def _warm_cold_queue_paths() -> List[Path]:
    paths: List[Path] = []
    for name, cfg in PROFILES.items():
        if name == "private_jc_warm":
            continue
        value = str(cfg.get("csv") or "").strip()
        if not value or not value.startswith("recipients_"):
            continue
        path = settings.shard_path(value)
        if path not in paths:
            paths.append(path)
    return paths


def warm_private_jc_lane_status(
    *,
    queue_path: Path = WARM_PRIVATE_JC_QUEUE_PATH,
    confirmation_path: Path = WARM_PRIVATE_JC_CONFIRMATION_PATH,
) -> Dict[str, object]:
    manifest: Dict[str, object] = {}
    if confirmation_path.exists():
        try:
            loaded = json.loads(confirmation_path.read_text(encoding="utf-8"))
            manifest = loaded if isinstance(loaded, dict) else {}
        except Exception:
            manifest = {}
    _headers, rows = _read_csv_rows(queue_path)
    queue_fingerprint = _file_sha256(queue_path) if queue_path.exists() else ""
    source_value = str(manifest.get("source_path") or "").strip()
    source_path = Path(source_value) if source_value else Path("__missing_warm_preview__")
    source_matches = source_path.is_file() and _file_sha256(source_path) == str(manifest.get("source_sha256") or "")
    integrity = validate_warm_confirmed_queue(rows, manifest) if manifest else {
        "valid": False,
        "reason": "warm_confirmation_required",
        "message": "Generate and explicitly confirm a warm draft preview before starting.",
    }
    original_count = int(manifest.get("row_count") or 0)
    confirmed = bool(manifest.get("confirmed")) and source_matches and bool(integrity.get("valid"))
    reason = "" if confirmed else (
        "warm_confirmation_source_mismatch"
        if bool(manifest.get("confirmed")) and not source_matches
        else str(integrity.get("reason") or "warm_confirmation_required")
    )
    message = (
        "Warm Private JC confirmed and ready."
        if confirmed and rows
        else "Warm Private JC complete."
        if confirmed and not rows
        else "Warm confirmation source no longer matches the reviewed preview. Re-confirm before starting."
        if bool(manifest.get("confirmed")) and not source_matches
        else str(integrity.get("message") or "Generate and explicitly confirm a warm draft preview before starting.")
    )
    return {
        "profile": "private_jc_warm",
        "queue_path": str(queue_path),
        "confirmation_path": str(confirmation_path),
        "confirmed": confirmed,
        "ready": confirmed and bool(rows),
        "remaining": len(rows),
        "confirmed_rows": original_count,
        "confirmation_id": str(manifest.get("confirmation_id") or ""),
        "source_path": str(manifest.get("source_path") or ""),
        "source_sha256": str(manifest.get("source_sha256") or ""),
        "queue_sha256": queue_fingerprint,
        "integrity_valid": bool(integrity.get("valid")),
        "integrity_reason": reason,
        "integrity_email": str(integrity.get("email") or ""),
        "integrity_field": str(integrity.get("field") or ""),
        "message": message,
    }


def confirm_warm_private_jc_preview(
    *,
    preview_path: Path,
    queue_path: Path = WARM_PRIVATE_JC_QUEUE_PATH,
    confirmation_path: Path = WARM_PRIVATE_JC_CONFIRMATION_PATH,
    log_paths: Sequence[Path] | None = None,
    cold_queue_paths: Sequence[Path] | None = None,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    bad_events_path: Path = settings.WEBHOOK_EVENTS_PATH,
    lead_ledger_db_path: Path | None = None,
) -> Dict[str, object]:
    preview_path = Path(preview_path)
    if preview_path.name != EXPECTED_WARM_PREVIEW_FILENAME:
        raise ValueError(f"Warm confirmation source must be {EXPECTED_WARM_PREVIEW_FILENAME}.")
    fieldnames, rows = _read_csv_rows(preview_path)
    missing = sorted(set(WARM_EMAIL_PREVIEW_HEADERS) - set(fieldnames))
    if missing:
        raise ValueError("Warm preview is missing required columns: " + ", ".join(missing))
    if not rows:
        raise ValueError("Warm preview has no email-ready rows to confirm.")
    if queue_path.exists():
        _queue_headers, existing_warm_rows = _read_csv_rows(queue_path)
        if existing_warm_rows:
            raise RuntimeError("Warm Private JC queue already contains rows. Finish it before confirming another warm preview.")

    authoritative_logs = list(log_paths) if log_paths is not None else _warm_authoritative_log_paths()
    already_sent = _sent_email_set(authoritative_logs)
    blocked, _suppression_summary = _blocked_email_set(
        sendgrid_suppressions_path,
        suppressed_path,
        unsubscribed_path,
    )
    blocked |= load_done_statuses_from_logs(
        authoritative_logs,
        {"INVALID", "BOUNCE", "BOUNCED", "DROPPED", "SPAMREPORT", "UNSUBSCRIBE", "UNSUBSCRIBED", "BLOCKED"},
    )
    blocked |= load_bad_sendgrid_event_emails(bad_events_path)
    cold_queued: set[str] = set()
    for path in list(cold_queue_paths) if cold_queue_paths is not None else _warm_cold_queue_paths():
        _headers, queued_rows = _read_queue_rows(Path(path))
        cold_queued |= {norm_email(row.get("Email", "")) for row in queued_rows if norm_email(row.get("Email", ""))}

    source_emails = {norm_email(row.get("AuthorEmail", "")) for row in rows if norm_email(row.get("AuthorEmail", ""))}
    ledger_contacted: set[str] = set()
    ledger_conn = connect_lead_ledger(_lead_ledger_db_path(lead_ledger_db_path))
    try:
        lead_id_by_email = {email: deterministic_lead_id(email) for email in source_emails}
        astra_contacted_ids, astra_warm_contacted_ids, _sendgrid_contacted_ids, global_bad_ids, _ignored_ids = (
            _dispatch_history_contact_sets(ledger_conn, set(lead_id_by_email.values()))
        )
        blocked_astra_ids = astra_contacted_ids | astra_warm_contacted_ids | global_bad_ids
        ledger_contacted = {email for email, lead_id in lead_id_by_email.items() if lead_id in blocked_astra_ids}
    finally:
        ledger_conn.close()

    seen: set[str] = set()
    queue_rows: List[Dict[str, str]] = []
    violations: Counter[str] = Counter()
    confirmation_id = f"warm_private_jc_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    for row in rows:
        email = norm_email(row.get("AuthorEmail", ""))
        contact_emails = {norm_email(value) for value in EMAIL_IN_TEXT_RE.findall(_strip_cell(row.get("ContactPath", "")))}
        if not email or not EMAIL_RE.match(email):
            violations["invalid_email"] += 1
            continue
        if email in seen:
            violations["duplicate_email"] += 1
            continue
        seen.add(email)
        if email not in contact_emails:
            violations["not_direct_email"] += 1
            continue
        if not _strip_cell(row.get("EmailSubject", "")) or not _strip_cell(row.get("EmailBody", "")):
            violations["missing_preview_copy"] += 1
            continue
        if re.search(r"{[A-Za-z][A-Za-z0-9_]*}", _strip_cell(row.get("EmailSubject", "")) + _strip_cell(row.get("EmailBody", ""))):
            violations["unresolved_preview_placeholder"] += 1
            continue
        if email in blocked:
            violations["suppressed_or_bad_outcome"] += 1
            continue
        if email in already_sent or email in ledger_contacted:
            violations["already_contacted"] += 1
            continue
        if email in cold_queued:
            violations["already_queued_cold"] += 1
            continue
        queue_rows.append({
            "Email": email,
            "FirstName": _trimmed_first_name(row.get("AuthorName", "")) or "there",
            **{header: _strip_cell(row.get(header, "")) for header in WARM_EMAIL_PREVIEW_HEADERS},
            "campaign_type": "warm_private_jc",
            "campaign_id": confirmation_id,
        })

    if violations:
        details = ", ".join(f"{key}={value}" for key, value in sorted(violations.items()))
        raise RuntimeError(f"Warm preview is no longer safe to confirm ({details}). Regenerate the Warm Research check and draft preview.")

    queue_path.parent.mkdir(parents=True, exist_ok=True)
    confirmation_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_files([queue_path]):
        _write_csv_atomic(queue_path, WARM_PRIVATE_JC_QUEUE_HEADERS, queue_rows)
        manifest = {
            "schema_version": 2,
            "confirmation_id": confirmation_id,
            "confirmed": True,
            "confirmed_at_utc": iso_utc(),
            "profile": "private_jc_warm",
            "source_path": str(preview_path),
            "source_sha256": _file_sha256(preview_path),
            "queue_path": str(queue_path),
            "queue_sha256": _file_sha256(queue_path),
            "row_count": len(queue_rows),
            "protected_fields": list(WARM_PRIVATE_JC_QUEUE_HEADERS),
            "approved_rows": {
                normalized_warm_confirmation_payload(row)["Email"]: {
                    "payload": normalized_warm_confirmation_payload(row),
                    "payload_sha256": warm_confirmation_payload_hash(row),
                }
                for row in queue_rows
            },
        }
        write_json_atomic(confirmation_path, manifest)
    return {
        **manifest,
        "ok": True,
        "warm_private_jc_confirmed": True,
        "warm_private_jc_remaining": len(queue_rows),
        "message": f"Warm Private JC confirmed with {len(queue_rows)} previewed recipient(s).",
    }


def _preview_rows(rows: Sequence[Dict[str, str]], fieldnames: Sequence[str], limit: int) -> List[Dict[str, str]]:
    preview: List[Dict[str, str]] = []
    for row in rows[:limit]:
        preview.append({field: _strip_cell(row.get(field, "")) for field in fieldnames})
    return preview


def _display_path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(settings.APP_ROOT.resolve()))
    except Exception:
        try:
            return str(path.relative_to(settings.APP_ROOT))
        except Exception:
            return str(path)


def _canonical_workspace_label(path: Path) -> str:
    try:
        return str(path.relative_to(settings.APP_ROOT))
    except Exception:
        return str(path)


def important_leads_default_paths() -> Dict[str, str]:
    return {
        "input_path": _canonical_workspace_label(MASTER_INPUT_PATH),
        "output_path": _canonical_workspace_label(MASTER_OUTPUT_PATH),
        "rejected_path": _canonical_workspace_label(MASTER_REJECTED_PATH),
    }


def _looks_like_foreign_absolute_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        return os.name != "nt"
    if re.match(r"^/mnt/[A-Za-z]/", normalized):
        return os.name != "nt"
    return False


def _saved_path_label_or_default(value: object, default_path: Path) -> str:
    default_label = _canonical_workspace_label(default_path)
    text = str(value or "").strip()
    if not text or _looks_like_foreign_absolute_path(text):
        return default_label

    path = Path(text)
    resolved = path if path.is_absolute() else settings.APP_ROOT / path
    if not resolved.exists():
        return default_label
    try:
        resolved.relative_to(IMPORTANT_DIR)
    except Exception:
        return default_label
    return _canonical_workspace_label(resolved)


def important_leads_path_state() -> Dict[str, str]:
    defaults = important_leads_default_paths()
    state = load_state()
    raw = state.get(IMPORTANT_PATHS_STATE_KEY, {})
    if not isinstance(raw, dict):
        return defaults
    return {
        "input_path": _saved_path_label_or_default(raw.get("input_path"), MASTER_INPUT_PATH),
        "output_path": _saved_path_label_or_default(raw.get("output_path"), MASTER_OUTPUT_PATH),
        "rejected_path": _saved_path_label_or_default(raw.get("rejected_path"), MASTER_REJECTED_PATH),
    }


def _normalize_dispatch_source_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower() or DISPATCH_SOURCE_TRIAGED_KEEP
    aliases = {
        "verified": DISPATCH_SOURCE_TRIAGED_KEEP,
        "fast_triage": DISPATCH_SOURCE_TRIAGED_KEEP,
        "fast_triage_keep": DISPATCH_SOURCE_TRIAGED_KEEP,
        "strict": DISPATCH_SOURCE_STRICT_VERIFIED,
        "strict_public_proof": DISPATCH_SOURCE_STRICT_VERIFIED,
    }
    mode = aliases.get(mode, mode)
    if mode in {DISPATCH_SOURCE_TRIAGED_KEEP, DISPATCH_SOURCE_STRICT_VERIFIED, DISPATCH_SOURCE_CLEANED}:
        return mode
    return DISPATCH_SOURCE_TRIAGED_KEEP


def important_leads_dispatch_source_state() -> Dict[str, str]:
    state = load_state()
    raw = state.get(IMPORTANT_DISPATCH_SOURCE_STATE_KEY, {})
    mode = DISPATCH_SOURCE_TRIAGED_KEEP
    if isinstance(raw, dict):
        mode = _normalize_dispatch_source_mode(raw.get("dispatch_source_mode"))
    elif isinstance(raw, str):
        mode = _normalize_dispatch_source_mode(raw)
    return {
        "dispatch_source_mode": mode,
    }


def _workspace_path_from_label(label: str, default: Path) -> Path:
    text = str(label or "").strip()
    if not text:
        return default
    path = Path(text)
    if path.is_absolute():
        return path
    return settings.APP_ROOT / path


def _source_path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(settings.APP_ROOT.resolve()))
    except Exception:
        return str(path)


def _dispatch_source_snapshot(
    *,
    source_mode: str,
    cleaned_path: Path,
    triaged_keep_path: Path,
    strict_verified_path: Path,
) -> Dict[str, object]:
    mode = _normalize_dispatch_source_mode(source_mode)
    source_path = _dispatch_source_path_for_mode(
        mode,
        cleaned_path=cleaned_path,
        triaged_keep_path=triaged_keep_path,
        strict_verified_path=strict_verified_path,
    )
    status_keep_filter = mode in {DISPATCH_SOURCE_TRIAGED_KEEP, DISPATCH_SOURCE_STRICT_VERIFIED}
    source_exists = source_path.exists()
    source_headers: List[str] = []
    source_rows: List[Dict[str, str]] = []
    if source_exists:
        source_headers, source_rows = _read_csv_rows(source_path)
    source_row_count = len(source_rows)
    eligible_rows = list(source_rows)
    if status_keep_filter:
        if source_exists and source_headers and "Status" in source_headers:
            eligible_rows = [
                row
                for row in source_rows
                if str(row.get("Status", "")).strip().upper() == "KEEP"
            ]
        else:
            eligible_rows = list(source_rows)
    eligible_row_count = len(eligible_rows)
    block_reason = ""
    source_label = _dispatch_source_display_name(mode)
    if mode in {DISPATCH_SOURCE_TRIAGED_KEEP, DISPATCH_SOURCE_STRICT_VERIFIED}:
        if not source_exists:
            block_reason = f"{source_label} dispatch source missing: {_source_path_label(source_path)}"
        elif source_row_count == 0:
            block_reason = f"{source_label} dispatch source is empty: {_source_path_label(source_path)}"
        elif source_headers and "Status" in source_headers and eligible_row_count == 0:
            block_reason = f"{source_label} dispatch source has no KEEP rows: {_source_path_label(source_path)}"
    else:
        if not source_exists:
            block_reason = f"Cleaned dispatch source missing: {_source_path_label(source_path)}"
        elif source_row_count == 0:
            block_reason = f"Cleaned dispatch source is empty: {_source_path_label(source_path)}"
    verification_file_mtime = ""
    if mode in {DISPATCH_SOURCE_TRIAGED_KEEP, DISPATCH_SOURCE_STRICT_VERIFIED} and source_exists:
        try:
            verification_file_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc).isoformat()
        except Exception:
            verification_file_mtime = ""
    return {
        "dispatch_source_mode": mode,
        "dispatch_source_name": source_label,
        "dispatch_source_path": str(source_path),
        "dispatch_source_label": _source_path_label(source_path),
        "dispatch_source_exists": source_exists,
        "dispatch_source_row_count": source_row_count,
        "dispatch_eligible_row_count": eligible_row_count,
        "dispatch_block_reason": block_reason,
        "verification_required": mode == DISPATCH_SOURCE_STRICT_VERIFIED,
        "status_keep_filter": status_keep_filter,
        "verification_file_mtime": verification_file_mtime,
        "dispatch_source_preview_rows": _preview_rows(eligible_rows, source_headers or ["Email"], DISPATCH_PREVIEW_ROWS),
        "dispatch_source_headers": source_headers,
    }


def _active_staged_batch_source_path(preview: Dict[str, object]) -> Path | None:
    if _normalize_dispatch_source_mode(preview.get("dispatch_source_mode")) != DISPATCH_SOURCE_TRIAGED_KEEP:
        return None
    source_path = Path(str(preview.get("dispatch_source_path") or ""))
    if not str(source_path).strip():
        return TRIAGED_KEEP_PATH
    return source_path


def _assert_active_staged_batch(preview: Dict[str, object]) -> None:
    source_path = _active_staged_batch_source_path(preview)
    if source_path is None:
        return
    if not source_path.exists():
        raise RuntimeError(
            f"No active staged Fast Triage batch found. Run Check Leads and Fast Triage before Confirm Dispatch: "
            f"{_source_path_label(source_path)}"
        )
    headers, rows = _read_csv_rows(source_path)
    if not headers or not rows:
        raise RuntimeError(
            f"Active staged Fast Triage batch is empty. Run Check Leads and Fast Triage before Confirm Dispatch: "
            f"{_source_path_label(source_path)}"
        )


def _path_from_staged_label(label: object, default: Path) -> Path:
    text = str(label or "").strip()
    if not text:
        return default
    path = Path(text)
    if path.is_absolute():
        return path
    return settings.APP_ROOT / path


def _staged_batch_paths_for_cleanup(preview: Dict[str, object]) -> Dict[str, Path]:
    keep_path = _active_staged_batch_source_path(preview) or TRIAGED_KEEP_PATH
    return {
        "cleaned": _path_from_staged_label(preview.get("master_label"), MASTER_OUTPUT_PATH),
        "rejected": _path_from_staged_label(preview.get("rejected_label"), MASTER_REJECTED_PATH),
        "triaged_keep": keep_path,
        "triaged_reject": keep_path.with_name(TRIAGED_REJECT_PATH.name),
        "triaged_quarantine": keep_path.with_name(TRIAGED_QUARANTINE_PATH.name),
    }


def _staged_batch_archive_dir(backup_root: Path, run_id: str) -> Path:
    match = re.search(r"(\d{8}_\d{6})", str(run_id or ""))
    slug = match.group(1) if match else timestamp_slug()
    archive_dir = backup_root / "staged_batches" / f"dispatch_{slug}"
    if archive_dir.exists():
        archive_dir = backup_root / "staged_batches" / f"dispatch_{slug}_{uuid.uuid4().hex[:8]}"
    return archive_dir


def _archive_and_clear_staged_batch(
    *,
    preview: Dict[str, object],
    report: Dict[str, object],
    backup_root: Path,
    archive_dir: Path | None = None,
) -> Dict[str, object]:
    if _normalize_dispatch_source_mode(preview.get("dispatch_source_mode")) != DISPATCH_SOURCE_TRIAGED_KEEP:
        return {
            "archived": False,
            "cleared": False,
            "reason": "dispatch_source_not_fast_triage_keep",
            "archive_path": "",
            "files": [],
        }

    paths_by_key = _staged_batch_paths_for_cleanup(preview)
    existing = [(key, path) for key, path in paths_by_key.items() if path.exists()]
    archive_dir = archive_dir or _staged_batch_archive_dir(backup_root, str(report.get("run_id") or ""))
    archived_files: List[Dict[str, object]] = []
    archive_dir.mkdir(parents=True, exist_ok=True)

    for key, path in existing:
        target = archive_dir / path.name
        shutil.copy2(path, target)
        archived_files.append(
            {
                "key": key,
                "source_path": str(path),
                "archive_path": str(target),
                "size": int(target.stat().st_size),
            }
        )

    metadata = {
        "dispatch_id": str(report.get("run_id") or ""),
        "timestamp": iso_utc(),
        "source_path": str(report.get("dispatch_source_path") or preview.get("dispatch_source_path") or ""),
        "source_row_count": int(report.get("dispatch_source_row_count") or preview.get("dispatch_source_row_count") or 0),
        "added_astra": int(report.get("added_astra") or 0),
        "added_sendgrid": int(report.get("added_sendgrid") or 0),
        "skipped_rows": (
            int(report.get("suppressed_skipped") or 0)
            + int(report.get("duplicate_master_skipped") or 0)
            + int(report.get("skipped_both") or 0)
            + int(report.get("invalid_malformed_skipped") or 0)
        ),
        "archive_path": str(archive_dir),
        "files": archived_files,
    }
    (archive_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for _key, path in existing:
        path.unlink()

    metadata["archived"] = bool(archived_files)
    metadata["cleared"] = bool(archived_files)
    return metadata


def _dispatch_source_display_name(mode: str) -> str:
    normalized = _normalize_dispatch_source_mode(mode)
    if normalized == DISPATCH_SOURCE_TRIAGED_KEEP:
        return "Fast Triage Keep"
    if normalized == DISPATCH_SOURCE_STRICT_VERIFIED:
        return "Strict Public Proof Verified"
    return "Cleaned"


def _normalize_dispatch_cap(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return DISPATCH_CAP_ALL
    aliases = {
        "all eligible": DISPATCH_CAP_ALL,
        "eligible": DISPATCH_CAP_ALL,
        "*": DISPATCH_CAP_ALL,
    }
    text = aliases.get(text, text)
    if text == DISPATCH_CAP_ALL:
        return DISPATCH_CAP_ALL
    try:
        numeric = int(text)
    except Exception:
        return DISPATCH_CAP_ALL
    if numeric in {100, 500, 1000}:
        return str(numeric)
    return DISPATCH_CAP_ALL


def _dispatch_cap_limit(dispatch_cap: str, eligible_count: int) -> int:
    normalized = _normalize_dispatch_cap(dispatch_cap)
    if normalized == DISPATCH_CAP_ALL:
        return max(0, int(eligible_count or 0))
    return min(max(0, int(eligible_count or 0)), int(normalized))


def _dispatch_cap_label(dispatch_cap: str) -> str:
    normalized = _normalize_dispatch_cap(dispatch_cap)
    if normalized == DISPATCH_CAP_ALL:
        return "All eligible"
    return normalized


def _dispatch_source_path_for_mode(
    mode: str,
    *,
    cleaned_path: Path,
    triaged_keep_path: Path,
    strict_verified_path: Path,
) -> Path:
    normalized = _normalize_dispatch_source_mode(mode)
    if normalized == DISPATCH_SOURCE_TRIAGED_KEEP:
        return triaged_keep_path
    if normalized == DISPATCH_SOURCE_STRICT_VERIFIED:
        return strict_verified_path
    return cleaned_path


def _dispatch_source_stage_for_mode(mode: str) -> str:
    normalized = _normalize_dispatch_source_mode(mode)
    if normalized == DISPATCH_SOURCE_TRIAGED_KEEP:
        return "FAST_TRIAGE"
    if normalized == DISPATCH_SOURCE_STRICT_VERIFIED:
        return "STRICT_PUBLIC_PROOF"
    return "DISPATCH_SOURCE"


def _row_has_any_value(row: Dict[str, str], headers: Sequence[str]) -> bool:
    return any(_strip_cell(row.get(header, "")) for header in headers)


def _lead_ledger_db_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        return Path(explicit_path)
    return Path(getattr(settings, "LEAD_LEDGER_DB_PATH", settings.STATE_DIR / "lead_ledger.sqlite3"))


def _path_fingerprint(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False, "size": 0, "mtime_ns": 0}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
    }


def _collect_dispatch_input_fingerprints(
    *,
    source_path: Path,
    queue_paths: Sequence[Path],
    log_paths: Sequence[Path],
    sendgrid_suppressions_path: Path,
    suppressed_path: Path,
    unsubscribed_path: Path,
) -> Dict[str, Dict[str, object]]:
    items = {
        "source": source_path,
        "sendgrid_suppressions": sendgrid_suppressions_path,
        "suppressed": suppressed_path,
        "unsubscribed": unsubscribed_path,
    }
    for index, path in enumerate(queue_paths, start=1):
        items[f"queue_{index}"] = path
    for index, path in enumerate(log_paths, start=1):
        items[f"log_{index}"] = path
    return {key: _path_fingerprint(path) for key, path in items.items()}


def _history_status_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _is_authoritative_contact_history_status(value: object) -> bool:
    return _history_status_key(value) in AUTHORITATIVE_CONTACT_HISTORY_STATUSES


def _sendgrid_attempt_info_is_sent(value: object) -> bool:
    info = str(value or "").strip().lower()
    if not info:
        return False
    return "outcome=sent" in info or '"outcome":"sent"' in info or "'outcome': 'sent'" in info


def _log_row_is_authoritative_sent(row: Dict[str, str]) -> bool:
    status = str(row.get("Status") or row.get("status") or "").strip().upper()
    if status == "SENT":
        return True
    if status == "ATTEMPT" and _sendgrid_attempt_info_is_sent(row.get("Info") or row.get("info")):
        return True
    return False


def _is_non_authoritative_history_path(path: Path) -> bool:
    label = _canonical_workspace_label(path).replace("\\", "/").lower()
    name = path.name.lower()
    if label.startswith("data/state/backups/staged_batches/") or "/data/state/backups/staged_batches/" in label:
        return True
    if label.startswith("data/state/dispatch_previews/") or "/data/state/dispatch_previews/" in label:
        return True
    if label.startswith("_important/dispatch_jobs/previews/") or "/_important/dispatch_jobs/previews/" in label:
        return True
    if "/dispatch_previews/" in label:
        return True
    if "debug_backups/" in label or "/debug_backups/" in label:
        return True
    if (label.startswith("data/state/backups/") or "/data/state/backups/" in label) and name.startswith("recipients_"):
        return True
    if (label.startswith("data/shards/") or "/data/shards/" in label) and name.startswith("recipients_"):
        return True
    if (label.startswith("_important/runs/") or "/_important/runs/" in label) and (
        name.startswith("leads")
        or name.startswith("recipients_")
        or "preview" in name
    ):
        return True
    return False


def _authoritative_history_paths(paths: Sequence[Path]) -> tuple[List[Path], List[Path]]:
    authoritative: List[Path] = []
    ignored: List[Path] = []
    for path in paths:
        if _is_non_authoritative_history_path(path):
            ignored.append(path)
        else:
            authoritative.append(path)
    return authoritative, ignored


def _source_email_matches_in_paths(source_emails: set[str], paths: Sequence[Path]) -> set[str]:
    matches: set[str] = set()
    if not source_emails:
        return matches
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            fieldnames, rows = _read_csv_rows(path)
        except Exception:
            continue
        email_header = _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES)
        if not email_header:
            continue
        for row in rows:
            email = norm_email(row.get(email_header, ""))
            if email in source_emails:
                matches.add(email)
    return matches


def _dispatch_history_contact_sets(
    conn,
    source_lead_ids: set[str],
) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    astra_contacted: set[str] = set()
    astra_warm_contacted: set[str] = set()
    sendgrid_contacted: set[str] = set()
    global_bad_contact: set[str] = set()
    non_authoritative_seen: set[str] = set()
    sorted_ids = sorted(lead_id for lead_id in source_lead_ids if str(lead_id or "").strip())
    for index in range(0, len(sorted_ids), 500):
        chunk = sorted_ids[index : index + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""
            SELECT lead_id, profile, queue_target, result_status
            FROM lead_dispatch_history
            WHERE lead_id IN ({placeholders})
            """,
            chunk,
        ).fetchall()
        for row in rows:
            lead_id = str(row["lead_id"] if hasattr(row, "keys") else row[0] or "").strip()
            profile = row["profile"] if hasattr(row, "keys") else row[1]
            queue_target = row["queue_target"] if hasattr(row, "keys") else row[2]
            status = row["result_status"] if hasattr(row, "keys") else row[3]
            if not lead_id:
                continue
            status_key = _history_status_key(status)
            if status_key in GLOBAL_BAD_CONTACT_HISTORY_STATUSES:
                global_bad_contact.add(lead_id)
            elif status_key in AUTHORITATIVE_CONTACT_HISTORY_STATUSES:
                lane_label = f"{profile or ''} {queue_target or ''}".strip().lower()
                if "private_jc_warm" in lane_label or ("warm" in lane_label and "jc" in lane_label):
                    astra_warm_contacted.add(lead_id)
                elif "private_jc" in lane_label:
                    astra_contacted.add(lead_id)
                elif "sendgrid" in lane_label:
                    sendgrid_contacted.add(lead_id)
                else:
                    # Legacy events without a route cannot be safely attributed.
                    astra_contacted.add(lead_id)
                    sendgrid_contacted.add(lead_id)
            elif status_key in NON_AUTHORITATIVE_HISTORY_STATUSES:
                non_authoritative_seen.add(lead_id)
    authoritative = astra_contacted | astra_warm_contacted | sendgrid_contacted | global_bad_contact
    return (
        astra_contacted,
        astra_warm_contacted,
        sendgrid_contacted,
        global_bad_contact,
        non_authoritative_seen - authoritative,
    )


def _recontact_recency_summary(
    conn,
    plan_rows_by_queue: Dict[str, List[Dict[str, str]]],
) -> Dict[str, object]:
    emails: set[str] = set()
    for rows in plan_rows_by_queue.values():
        for row in rows:
            email = norm_email(row.get("Email", ""))
            if email:
                emails.add(email)

    lead_ids = {deterministic_lead_id(email) for email in emails}
    planned_unique = len(lead_ids)
    if not planned_unique:
        return {
            "planned_unique": 0,
            "found_in_active_history": 0,
            "seen_this_month": 0,
            "not_found_in_active_history": 0,
            "history_overlap_ratio": 0.0,
            "seen_this_month_ratio": 0.0,
            "not_found_in_active_history_ratio": 0.0,
            "risk_level": "green",
            "high_risk": False,
            "safer_leads_count": 0,
            "warning": "",
        }

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    found: set[str] = set()
    seen_this_month: set[str] = set()
    sorted_ids = sorted(lead_ids)
    for index in range(0, len(sorted_ids), 500):
        chunk = sorted_ids[index : index + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""
            SELECT lead_id, MAX(dispatched_at) AS last_seen
            FROM lead_dispatch_history
            WHERE lead_id IN ({placeholders})
              AND LOWER(REPLACE(REPLACE(COALESCE(result_status, ''), '-', '_'), ' ', '_')) IN ({",".join("?" for _ in AUTHORITATIVE_CONTACT_HISTORY_STATUSES)})
            GROUP BY lead_id
            """,
            [*chunk, *sorted(AUTHORITATIVE_CONTACT_HISTORY_STATUSES)],
        ).fetchall()
        for row in rows:
            raw_lead_id = row["lead_id"] if hasattr(row, "keys") else row[0]
            raw_last_seen = row["last_seen"] if hasattr(row, "keys") else row[1]
            lead_id = str(raw_lead_id or "").strip()
            last_seen = str(raw_last_seen or "").strip()
            if not lead_id:
                continue
            found.add(lead_id)
            if last_seen and last_seen >= month_start:
                seen_this_month.add(lead_id)

    found_count = len(found)
    seen_count = len(seen_this_month)
    not_found = max(0, planned_unique - found_count)
    overlap_ratio = found_count / planned_unique if planned_unique else 0.0
    month_ratio = seen_count / planned_unique if planned_unique else 0.0
    risk_level = _recontact_risk_level(overlap_ratio, month_ratio)
    high_risk = risk_level == "red" or overlap_ratio >= RECONTACT_RECENCY_HIGH_RISK_RATIO
    return {
        "planned_unique": planned_unique,
        "found_in_active_history": found_count,
        "seen_this_month": seen_count,
        "not_found_in_active_history": not_found,
        "history_overlap_ratio": round(overlap_ratio, 4),
        "seen_this_month_ratio": round(month_ratio, 4),
        "not_found_in_active_history_ratio": round((not_found / planned_unique) if planned_unique else 0.0, 4),
        "risk_level": risk_level,
        "high_risk": high_risk,
        "safer_leads_count": not_found,
        "warning": "Not recommended: most leads were contacted recently." if high_risk else "",
    }


def _recontact_risk_level(found_ratio: float, seen_this_month_ratio: float) -> str:
    if found_ratio >= RECONTACT_RECENCY_RED_FOUND_RATIO or seen_this_month_ratio >= RECONTACT_RECENCY_RED_MONTH_RATIO:
        return "red"
    if found_ratio >= RECONTACT_RECENCY_YELLOW_FOUND_RATIO or seen_this_month_ratio >= RECONTACT_RECENCY_YELLOW_MONTH_RATIO:
        return "yellow"
    return "green"


def _empty_recontact_recency_summary(planned_unique: int = 0) -> Dict[str, object]:
    return {
        "planned_unique": int(planned_unique),
        "found_in_active_history": 0,
        "seen_this_month": 0,
        "not_found_in_active_history": int(planned_unique),
        "history_overlap_ratio": 0.0,
        "seen_this_month_ratio": 0.0,
        "not_found_in_active_history_ratio": 1.0 if planned_unique else 0.0,
        "risk_level": "green",
        "high_risk": False,
        "safer_leads_count": int(planned_unique),
        "warning": "",
    }


def _extract_email_strings(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            found.update(_extract_email_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_extract_email_strings(child))
    elif value is not None:
        for match in EMAIL_IN_TEXT_RE.findall(str(value)):
            email = norm_email(match)
            if email:
                found.add(email)
    return found


def _extract_timestamp_strings(value: object) -> List[str]:
    timestamps: List[str] = []
    timestamp_keys = {
        "timestamp",
        "created_at",
        "created_at_utc",
        "updated_at",
        "updated_at_utc",
        "dispatched_at",
        "completed_at",
        "completed_at_utc",
        "confirmed_at",
        "confirmed_at_utc",
        "event_at",
        "time",
        "date",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().lower() in timestamp_keys and child is not None:
                timestamps.append(str(child))
            timestamps.extend(_extract_timestamp_strings(child))
    elif isinstance(value, list):
        for child in value:
            timestamps.extend(_extract_timestamp_strings(child))
    return timestamps


def _json_active_history_email_sets(value: object, *, month_prefix: str) -> tuple[set[str], set[str]]:
    active: set[str] = set()
    seen_this_month: set[str] = set()
    if isinstance(value, list):
        for child in value:
            child_active, child_seen = _json_active_history_email_sets(child, month_prefix=month_prefix)
            active.update(child_active)
            seen_this_month.update(child_seen)
        return active, seen_this_month
    if isinstance(value, dict):
        local_emails = _extract_email_strings(value)
        active.update(local_emails)
        if any(_timestamp_seen_this_month(timestamp, month_prefix=month_prefix) for timestamp in _extract_timestamp_strings(value)):
            seen_this_month.update(local_emails)
        return active, seen_this_month
    active.update(_extract_email_strings(value))
    return active, seen_this_month


def _timestamp_seen_this_month(raw_value: str, *, month_prefix: str) -> bool:
    text = str(raw_value or "").strip()
    return bool(text and text.startswith(month_prefix))


def _active_history_paths(
    *,
    logs_dir: Path | None = None,
    state_dir: Path | None = None,
) -> List[Path]:
    logs_root = logs_dir or (settings.APP_ROOT / "data" / "logs")
    state_root = state_dir or STATE_DIR
    paths: List[Path] = []
    if logs_root.exists():
        paths.extend(sorted(logs_root.glob("*.csv")))
    paths.extend(sorted(state_root.glob("important_leads_dispatch_*.json")))
    confirmed_dir = state_root / "dispatch_confirmed"
    if confirmed_dir.exists():
        paths.extend(sorted(confirmed_dir.glob("dispatch_confirmed_*.json")))
    history_path = state_root / "dispatch_run_history.json"
    if history_path.exists():
        paths.append(history_path)
    return paths


def _active_history_email_sets(
    *,
    logs_dir: Path | None = None,
    state_dir: Path | None = None,
) -> tuple[set[str], set[str]]:
    active_history: set[str] = set()
    seen_this_month: set[str] = set()
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    for path in _active_history_paths(logs_dir=logs_dir, state_dir=state_dir):
        try:
            if path.suffix.lower() == ".csv":
                headers, rows = _read_csv_rows(path)
                for row in rows:
                    row_emails = _extract_email_strings(row)
                    active_history.update(row_emails)
                    timestamp_values = [
                        str(row.get(header, ""))
                        for header in headers
                        if str(header).strip().lower() in {
                            "timestamp",
                            "created_at",
                            "created_at_utc",
                            "updated_at",
                            "updated_at_utc",
                            "dispatched_at",
                            "event_at",
                            "time",
                            "date",
                        }
                    ]
                    if any(_timestamp_seen_this_month(value, month_prefix=month_prefix) for value in timestamp_values):
                        seen_this_month.update(row_emails)
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        json_emails, json_seen_this_month = _json_active_history_email_sets(raw, month_prefix=month_prefix)
        active_history.update(json_emails)
        seen_this_month.update(json_seen_this_month)
    return active_history, seen_this_month


def _latest_valid_recontact_preview(*preview_dirs: Path) -> Dict[str, object]:
    candidates: List[Path] = []
    seen_paths: set[Path] = set()
    for preview_dir in preview_dirs:
        if not preview_dir.exists():
            continue
        for path in sorted(preview_dir.glob("dispatch_preview_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            candidates.append(path)
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "").strip().lower() not in {"previewed", "ready"}:
            continue
        if is_recontact_cold_campaign(raw.get("campaign_type")):
            return raw
    raise FileNotFoundError("No valid recontact preview found. Run Preview Dispatch for Recontact first.")


def _find_preview_by_id_in_dir(preview_id: str, preview_dir: Path) -> Dict[str, object]:
    target = str(preview_id or "").strip()
    if not target or not preview_dir.exists():
        raise FileNotFoundError(f"Dispatch preview not found: {preview_id}")
    for path in sorted(preview_dir.glob("dispatch_preview_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(raw, dict) and str(raw.get("preview_id") or "").strip() == target:
            return raw
    raise FileNotFoundError(f"Dispatch preview not found: {preview_id}")


def _planned_preview_emails(preview: Dict[str, object]) -> set[str]:
    planned: set[str] = set()
    rows_by_queue = preview.get("plan_rows_by_queue")
    if isinstance(rows_by_queue, dict):
        for rows in rows_by_queue.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    email = norm_email(row.get("Email", ""))
                    if email:
                        planned.add(email)
    if planned:
        return planned
    for key in ("private_jc_planned_rows", "sendgrid_planned_rows"):
        rows = preview.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                email = norm_email(row.get("Email", ""))
                if email:
                    planned.add(email)
    return planned


def create_safer_recontact_pool_from_preview(
    preview_id: str = "",
    *,
    preview_dir: Path = DISPATCH_PREVIEWS_DIR,
    summary_path: Path = SAFER_RECONTACT_SUMMARY_PATH,
    logs_dir: Path | None = None,
    state_dir: Path | None = None,
) -> Dict[str, object]:
    if str(preview_id or "").strip():
        try:
            preview = load_dispatch_preview(preview_id, preview_dir=preview_dir)
        except FileNotFoundError:
            try:
                preview = _find_preview_by_id_in_dir(preview_id, preview_dir)
            except FileNotFoundError:
                if preview_dir.resolve() == DISPATCH_PREVIEWS_DIR.resolve():
                    raise
                try:
                    preview = load_dispatch_preview(preview_id, preview_dir=DISPATCH_PREVIEWS_DIR)
                except FileNotFoundError:
                    preview = _find_preview_by_id_in_dir(preview_id, DISPATCH_PREVIEWS_DIR)
    else:
        preview = _latest_valid_recontact_preview(preview_dir, DISPATCH_PREVIEWS_DIR)
    if not is_recontact_cold_campaign(preview.get("campaign_type")):
        raise ValueError("Safer recontact pool requires a recontact preview.")
    source_path = Path(str(preview.get("dispatch_source_path") or ""))
    if not source_path.exists():
        raise FileNotFoundError(f"Recontact source file not found: {source_path}")

    source_headers, source_rows = _read_csv_rows(source_path)
    planned_emails = _planned_preview_emails(preview)
    active_history, seen_this_month_emails = _active_history_email_sets(logs_dir=logs_dir, state_dir=state_dir)
    planned_unique = len(planned_emails)
    found_emails = planned_emails & active_history
    seen_this_month = planned_emails & seen_this_month_emails
    not_found_emails = planned_emails - active_history
    found_count = len(found_emails)
    seen_count = len(seen_this_month)
    not_found_count = len(not_found_emails)
    found_ratio = found_count / planned_unique if planned_unique else 0.0
    seen_ratio = seen_count / planned_unique if planned_unique else 0.0
    not_found_ratio = not_found_count / planned_unique if planned_unique else 0.0

    output_rows: List[Dict[str, str]] = []
    seen_output: set[str] = set()
    for row in source_rows:
        email = norm_email(row.get("Email", ""))
        if not email or email not in not_found_emails or email in seen_output:
            continue
        output_rows.append(row)
        seen_output.add(email)

    if not output_rows and not_found_emails:
        plan_rows: List[Dict[str, str]] = []
        rows_by_queue = preview.get("plan_rows_by_queue") if isinstance(preview.get("plan_rows_by_queue"), dict) else {}
        for rows in rows_by_queue.values():
            if isinstance(rows, list):
                plan_rows.extend(row for row in rows if isinstance(row, dict))
        if plan_rows:
            source_headers = list(plan_rows[0].keys())
            for row in plan_rows:
                email = norm_email(row.get("Email", ""))
                if email and email in not_found_emails and email not in seen_output:
                    output_rows.append(row)
                    seen_output.add(email)

    output_path = source_path.with_name(SAFER_RECONTACT_SOURCE_FILENAME)
    _write_csv_atomic(output_path, source_headers, output_rows)
    summary = {
        "preview_id": str(preview.get("preview_id") or ""),
        "campaign_type": str(preview.get("campaign_type") or ""),
        "dispatch_source_mode": str(preview.get("dispatch_source_mode") or ""),
        "source_path": str(source_path),
        "original_source_rows": int(preview.get("dispatch_source_row_count") or len(source_rows)),
        "planned_unique": planned_unique,
        "found_in_active_history": found_count,
        "found_in_active_history_pct": round(found_ratio * 100, 1),
        "seen_this_month": seen_count,
        "seen_this_month_pct": round(seen_ratio * 100, 1),
        "not_found_in_active_history": not_found_count,
        "not_found_in_active_history_pct": round(not_found_ratio * 100, 1),
        "risk_level": _recontact_risk_level(found_ratio, seen_ratio),
        "safer_found_in_active_history": 0,
        "safer_rows_written": len(output_rows),
        "output_path": str(output_path),
        "created_at": iso_utc(),
    }
    write_json_atomic(summary_path, summary)
    return summary


def is_safer_recontact_source_path(path: object) -> bool:
    return SAFER_RECONTACT_SOURCE_FILENAME in str(path or "").replace("\\", "/").lower()


def _changed_dispatch_fingerprints(
    expected: Dict[str, Dict[str, object]],
    current: Dict[str, Dict[str, object]],
) -> List[str]:
    changed: List[str] = []
    for key, expected_entry in expected.items():
        current_entry = current.get(key, {})
        if (
            bool(expected_entry.get("exists")) != bool(current_entry.get("exists"))
            or int(expected_entry.get("size") or 0) != int(current_entry.get("size") or 0)
            or int(expected_entry.get("mtime_ns") or 0) != int(current_entry.get("mtime_ns") or 0)
        ):
            changed.append(str(expected_entry.get("path") or current_entry.get("path") or key))
    return changed


def _dispatch_preview_path(preview_id: str, preview_dir: Path) -> Path:
    return preview_dir / f"{preview_id}.json"


def _save_dispatch_preview(preview: Dict[str, object], preview_dir: Path) -> Path:
    preview_id = str(preview.get("preview_id") or "").strip()
    if not preview_id:
        raise ValueError("Missing dispatch preview id.")
    preview_dir.mkdir(parents=True, exist_ok=True)
    path = _dispatch_preview_path(preview_id, preview_dir)
    payload = dict(preview)
    payload["updated_at_utc"] = iso_utc()
    write_json_atomic(path, payload)
    return path


def _unique_dispatch_archive_path(directory: Path, prefix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{prefix}_{timestamp_slug()}"
    candidate = directory / f"{base}.json"
    index = 2
    while candidate.exists():
        candidate = directory / f"{base}_{index}.json"
        index += 1
    return candidate


def _archive_assigned_dispatch_preview(
    preview: Dict[str, object],
    archive_dir: Path = DISPATCH_PREVIEWS_DIR,
    *,
    archive_path: Path | None = None,
) -> Path:
    path = archive_path or _unique_dispatch_archive_path(archive_dir, "dispatch_preview")
    queue_rows = preview.get("plan_rows_by_queue") if isinstance(preview.get("plan_rows_by_queue"), dict) else {}
    planned_summary = _planned_queue_row_summary(queue_rows)
    sendgrid_shard_planned_counts = {
        f"sendgrid_{index}": int(preview.get(f"rows_to_add_sendgrid_{index}") or preview.get(f"assigned_sg{index}") or 0)
        for index in range(1, 6)
    }
    queue_keys = _dispatch_queue_keys(preview)
    sendgrid_queue_keys = [key for key in queue_keys if key.startswith("sendgrid_")]
    payload = {
        "archived_at_utc": iso_utc(),
        "preview_id": str(preview.get("preview_id") or ""),
        "status": str(preview.get("status") or ""),
        "campaign_type": str(preview.get("campaign_type") or ""),
        "dispatch_source_mode": str(preview.get("dispatch_source_mode") or ""),
        "source_path": str(preview.get("dispatch_source_path") or ""),
        "source_row_count": int(preview.get("dispatch_source_row_count") or 0),
        "eligible_row_count": int(preview.get("dispatch_eligible_row_count") or 0),
        "selected_row_count": int(preview.get("dispatch_selected_row_count") or 0),
        **planned_summary,
        "rows_to_add_private_jc": int(preview.get("rows_to_add_private_jc") or preview.get("added_astra") or 0),
        "rows_to_add_sendgrid": int(preview.get("rows_to_add_sendgrid") or preview.get("added_sendgrid") or 0),
        "rows_to_add_sendgrid_1": sendgrid_shard_planned_counts["sendgrid_1"],
        "rows_to_add_sendgrid_2": sendgrid_shard_planned_counts["sendgrid_2"],
        "rows_to_add_sendgrid_3": sendgrid_shard_planned_counts["sendgrid_3"],
        "rows_to_add_sendgrid_4": sendgrid_shard_planned_counts["sendgrid_4"],
        "rows_to_add_sendgrid_5": sendgrid_shard_planned_counts["sendgrid_5"],
        "sendgrid_shard_planned_counts": sendgrid_shard_planned_counts,
        "sendgrid_profile_planned_counts": dict(preview.get("sendgrid_profile_planned_counts") or {}),
        "sendgrid_profile_order": list(preview.get("sendgrid_profile_order") or []),
        "sendgrid_profile_labels": dict(preview.get("sendgrid_profile_labels") or {}),
        "sendgrid_zero_reason": str(preview.get("sendgrid_zero_reason") or ""),
        "recontact_recency": dict(preview.get("recontact_recency") or {}),
        "recontact_planned_unique": int(preview.get("recontact_planned_unique") or 0),
        "recontact_found_in_active_history": int(preview.get("recontact_found_in_active_history") or 0),
        "recontact_seen_this_month": int(preview.get("recontact_seen_this_month") or 0),
        "recontact_not_found_in_active_history": int(preview.get("recontact_not_found_in_active_history") or 0),
        "recontact_recency_high_risk": bool(preview.get("recontact_recency_high_risk")),
        "recontact_recency_risk_level": str(preview.get("recontact_recency_risk_level") or ""),
        "private_jc_planned_rows": list(queue_rows.get("private_jc") or []),
        "sendgrid_planned_rows": [
            row
            for key in sendgrid_queue_keys
            for row in list(queue_rows.get(key) or [])
        ],
        "per_shard_planned_rows": {
            key: list(queue_rows.get(key) or [])
            for key in queue_keys
        },
        "skipped_rows": int(
            preview.get("skipped_rows")
            or sum(int(value or 0) for value in dict(preview.get("exclusion_reason_counts") or {}).values())
        ),
        "skipped_reasons": dict(preview.get("exclusion_reason_counts") or {}),
        "suppressed_rows": int(preview.get("suppressed_skipped") or preview.get("skipped_suppressed") or 0),
        "duplicate_or_already_queued_rows": int(preview.get("duplicate_master_skipped") or 0)
        + int(preview.get("skipped_already_queued") or 0),
        "counts": {
            "private_jc": int(preview.get("rows_to_add_private_jc") or preview.get("added_astra") or 0),
            "sendgrid": int(preview.get("rows_to_add_sendgrid") or preview.get("added_sendgrid") or 0),
            "sg1": int(preview.get("rows_to_add_sendgrid_1") or preview.get("assigned_sg1") or 0),
            "sg2": int(preview.get("rows_to_add_sendgrid_2") or preview.get("assigned_sg2") or 0),
            "sg3": int(preview.get("rows_to_add_sendgrid_3") or preview.get("assigned_sg3") or 0),
            "sg4": int(preview.get("rows_to_add_sendgrid_4") or preview.get("assigned_sg4") or 0),
            "sg5": int(preview.get("rows_to_add_sendgrid_5") or preview.get("assigned_sg5") or 0),
            "total_planned_unique": int(planned_summary["total_planned_unique_count"]),
            "total_planned_queue_rows": int(planned_summary["total_planned_queue_rows"]),
        },
    }
    write_json_atomic(path, payload)
    return path


def _archive_confirmed_dispatch_summary(
    report: Dict[str, object],
    archive_dir: Path = DISPATCH_CONFIRMED_DIR,
    *,
    archive_path: Path | None = None,
) -> Path:
    path = archive_path or _unique_dispatch_archive_path(archive_dir, "dispatch_confirmed")
    payload = {
        "confirmed_at": str(report.get("completed_at_utc") or report.get("generated_at_utc") or ""),
        "confirmed_at_utc": str(report.get("completed_at_utc") or report.get("generated_at_utc") or ""),
        "run_id": str(report.get("run_id") or ""),
        "preview_id": str(report.get("preview_id") or ""),
        "preview_path": str(report.get("preview_path") or ""),
        "source_path": str(report.get("dispatch_source_path") or ""),
        "source_rows": int(report.get("dispatch_source_row_count") or 0),
        "eligible_rows": int(report.get("dispatch_eligible_row_count") or 0),
        "selected_rows": int(report.get("dispatch_selected_row_count") or 0),
        "private_jc_added": int(report.get("added_astra") or 0),
        "sendgrid_added": int(report.get("added_sendgrid") or 0),
        "sg1_added": int(report.get("assigned_sg1") or 0),
        "sg2_added": int(report.get("assigned_sg2") or 0),
        "sg3_added": int(report.get("assigned_sg3") or 0),
        "sg4_added": int(report.get("assigned_sg4") or 0),
        "sg5_added": int(report.get("assigned_sg5") or 0),
        "skipped_both": int(report.get("skipped_both") or 0),
        "suppressed": int(report.get("suppressed_skipped") or report.get("skipped_suppressed") or 0),
        "backup_path": str(report.get("backup_dir") or ""),
        "queue_paths_written": dict(report.get("queue_paths") or {}),
        "assigned_preview_archive_path": str(report.get("assigned_preview_archive_path") or ""),
        "report": report,
    }
    write_json_atomic(path, payload)
    return path


def _zero_add_dispatch_message(report: Dict[str, object]) -> str:
    reasons = report.get("exclusion_reason_counts") if isinstance(report.get("exclusion_reason_counts"), dict) else {}
    parts: List[str] = []
    already_queued = int(report.get("skipped_already_queued") or reasons.get("already_queued") or 0)
    already_sent = int(report.get("skipped_already_sent") or reasons.get("already_sent") or 0)
    already_contacted = int(report.get("skipped_already_contacted") or reasons.get("already_contacted") or 0)
    suppressed = int(report.get("suppressed_skipped") or report.get("skipped_suppressed") or reasons.get("suppressed") or 0)
    invalid = int(report.get("invalid_malformed_skipped") or report.get("skipped_invalid_malformed") or reasons.get("invalid_source_row") or 0)
    if already_queued:
        parts.append(f"{already_queued} already queued")
    if already_sent:
        parts.append(f"{already_sent} already sent")
    if already_contacted:
        parts.append(f"{already_contacted} already contacted")
    if suppressed:
        parts.append(f"{suppressed} suppressed")
    if invalid:
        parts.append(f"{invalid} invalid or malformed")
    suffix = f": {', '.join(parts)}." if parts else "."
    return f"Zero-add dispatch confirmed. No new queue rows were written because all eligible rows were already queued/skipped{suffix}"


def load_dispatch_preview(preview_id: str, preview_dir: Path = DISPATCH_PREVIEWS_DIR) -> Dict[str, object]:
    path = _dispatch_preview_path(preview_id, preview_dir)
    if not path.exists():
        raise FileNotFoundError(f"Dispatch preview not found: {preview_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Dispatch preview is invalid: {preview_id}")
    return raw


def _missing_required_dispatch_fields(row: Dict[str, object]) -> List[str]:
    return [
        field
        for field in REQUIRED_DISPATCH_FIELDS
        if not str(row.get(field) or "").strip()
    ]


def _validate_recontact_source_classification(preview: Dict[str, object]) -> bool:
    source_path = Path(str(preview.get("dispatch_source_path") or ""))
    safer_recontact = is_safer_recontact_source_path(source_path)
    expected_source_kind = (
        RECONTACT_SOURCE_KIND_SAFER
        if safer_recontact
        else _normalize_dispatch_source_mode(preview.get("dispatch_source_mode"))
    )
    actual_source_kind = str(preview.get("dispatch_source_kind") or "").strip()
    if actual_source_kind != expected_source_kind:
        raise RuntimeError(
            "Recontact preview source classification does not match its server-classified source path. "
            "Re-run Preview Dispatch."
        )
    expected_sendgrid_only = not safer_recontact
    if bool(preview.get("full_recontact_sendgrid_only")) != expected_sendgrid_only:
        raise RuntimeError("Recontact preview routing classification is inconsistent. Re-run Preview Dispatch.")
    return safer_recontact


def _validate_recontact_campaign_identity(preview: Dict[str, object]) -> None:
    if not is_recontact_cold_campaign(preview.get("campaign_type")):
        return

    safer_recontact = _validate_recontact_source_classification(preview)
    campaign_id = str(preview.get("campaign_id") or "").strip()
    preview_id = str(preview.get("preview_id") or "").strip()
    queue_headers = [str(value or "").strip() for value in (preview.get("queue_headers") or [])]
    plan_rows_by_queue = preview.get("plan_rows_by_queue")
    if not isinstance(plan_rows_by_queue, dict):
        raise RuntimeError("Recontact preview is missing planned queue rows. Re-run Preview Dispatch.")

    if safer_recontact:
        if campaign_id or "campaign_id" in queue_headers:
            raise RuntimeError("Safer Recontact preview must retain its existing campaign identity semantics.")
        for queue_name, planned_rows in plan_rows_by_queue.items():
            if not isinstance(planned_rows, list):
                raise RuntimeError(f"Safer Recontact preview has invalid planned rows for {queue_name}. Re-run Preview Dispatch.")
            for index, row in enumerate(planned_rows, start=1):
                if not isinstance(row, dict):
                    raise RuntimeError(f"Safer Recontact preview has invalid planned row {index} in {queue_name}. Re-run Preview Dispatch.")
                if str(row.get("campaign_id") or "").strip() or str(row.get("dispatch_source_kind") or "").strip() == RECONTACT_SOURCE_KIND_FULL:
                    raise RuntimeError("Safer Recontact preview contains Full Recontact campaign metadata.")
        return

    if "dispatch_source_kind" not in queue_headers:
        raise RuntimeError("Full Recontact preview is missing the dispatch source kind queue field. Re-run Preview Dispatch.")
    for queue_name, planned_rows in plan_rows_by_queue.items():
        if not isinstance(planned_rows, list):
            raise RuntimeError(f"Full Recontact preview has invalid planned rows for {queue_name}. Re-run Preview Dispatch.")
        for index, row in enumerate(planned_rows, start=1):
            if not isinstance(row, dict):
                raise RuntimeError(f"Full Recontact preview has invalid planned row {index} in {queue_name}. Re-run Preview Dispatch.")
            if str(row.get("dispatch_source_kind") or "").strip() != RECONTACT_SOURCE_KIND_FULL:
                raise RuntimeError(
                    f"Full Recontact preview planned row {index} in {queue_name} has a missing or mismatched dispatch source kind. "
                    "Re-run Preview Dispatch."
                )

    if not campaign_id:
        raise RuntimeError("Full Recontact preview is missing its campaign ID. Re-run Preview Dispatch.")
    if not RECONTACT_CAMPAIGN_ID_RE.fullmatch(campaign_id):
        raise RuntimeError("Full Recontact preview has a malformed campaign ID. Re-run Preview Dispatch.")
    if campaign_id != preview_id:
        raise RuntimeError("Full Recontact preview campaign ID does not match its server preview ID. Re-run Preview Dispatch.")

    if "campaign_id" not in queue_headers:
        raise RuntimeError("Full Recontact preview is missing the campaign ID queue field. Re-run Preview Dispatch.")

    private_rows = plan_rows_by_queue.get("private_jc") or []
    if private_rows:
        raise RuntimeError("Full Recontact preview must route recipients only to enabled SendGrid profiles.")
    for queue_name, planned_rows in plan_rows_by_queue.items():
        for index, row in enumerate(planned_rows, start=1):
            row_campaign_id = str(row.get("campaign_id") or "").strip()
            if row_campaign_id != campaign_id:
                reason = "missing" if not row_campaign_id else "mixed or mismatched"
                raise RuntimeError(
                    f"Full Recontact preview planned row {index} in {queue_name} has a {reason} campaign ID. "
                    "Re-run Preview Dispatch."
                )


def _validate_dispatch_preview_contract(preview: Dict[str, object]) -> None:
    required_text_fields = {
        "campaign_type": "campaign type",
        "dispatch_source_mode": "dispatch source mode",
        "dispatch_source_path": "dispatch source path",
        "preview_id": "preview id",
    }
    for key, label in required_text_fields.items():
        if not str(preview.get(key) or "").strip():
            raise RuntimeError(f"Dispatch preview is missing {label}. Re-run Preview Dispatch.")
    if normalize_campaign_type(preview.get("campaign_type")) != str(preview.get("campaign_type") or "").strip():
        raise RuntimeError("Dispatch preview has an invalid campaign type. Re-run Preview Dispatch.")
    if _normalize_dispatch_source_mode(preview.get("dispatch_source_mode")) != str(preview.get("dispatch_source_mode") or "").strip().lower():
        raise RuntimeError("Dispatch preview has an invalid dispatch source mode. Re-run Preview Dispatch.")
    campaign_type = normalize_campaign_type(preview.get("campaign_type"))
    _validate_recontact_campaign_identity(preview)
    if campaign_type == CAMPAIGN_TYPE_COLD:
        if int(preview.get("history_policy_version") or 0) != DISPATCH_HISTORY_POLICY_VERSION:
            raise RuntimeError(
                "Fresh Cold dispatch preview does not establish the current global prior-success policy. "
                "Re-run Preview Dispatch."
            )
        if str(preview.get("prior_success_policy") or "") != FRESH_COLD_PRIOR_SUCCESS_POLICY:
            raise RuntimeError(
                "Fresh Cold dispatch preview has an ambiguous prior-success policy. Re-run Preview Dispatch."
            )

    plan_rows_by_queue = preview.get("plan_rows_by_queue")
    if not isinstance(plan_rows_by_queue, dict):
        raise RuntimeError("Dispatch preview is missing planned queue rows. Re-run Preview Dispatch.")
    planned_summary = _planned_queue_row_summary(plan_rows_by_queue)
    expected_private = int(preview.get("private_jc_planned_count") or preview.get("rows_to_add_private_jc") or 0)
    expected_sendgrid = int(preview.get("sendgrid_planned_count") or preview.get("rows_to_add_sendgrid") or 0)
    expected_unique = int(preview.get("total_planned_unique_count") or 0)
    expected_total = int(preview.get("total_rows_would_write") or preview.get("total_planned_queue_rows") or 0)
    if int(planned_summary["duplicate_planned_email_count"]) > 0:
        raise RuntimeError("Dispatch preview contains duplicate planned recipients across queues. Re-run Preview Dispatch.")
    if expected_private != int(planned_summary["private_jc_planned_count"]):
        raise RuntimeError("Dispatch preview private JC planned count does not match stored queue rows. Re-run Preview Dispatch.")
    if expected_sendgrid != int(planned_summary["sendgrid_planned_count"]):
        raise RuntimeError("Dispatch preview SendGrid planned count does not match stored queue rows. Re-run Preview Dispatch.")
    if expected_unique != int(planned_summary["total_planned_unique_count"]):
        raise RuntimeError("Dispatch preview unique planned recipient count does not match stored queue rows. Re-run Preview Dispatch.")
    if expected_total != int(planned_summary["total_planned_queue_rows"]):
        raise RuntimeError("Dispatch preview total planned count does not match stored queue rows. Re-run Preview Dispatch.")
    planned_rows_by_queue = preview.get("plan_rows_by_queue") if isinstance(preview.get("plan_rows_by_queue"), dict) else {}
    for queue_name, planned_rows in planned_rows_by_queue.items():
        if not isinstance(planned_rows, list):
            continue
        for index, row in enumerate(planned_rows, start=1):
            if not isinstance(row, dict):
                raise RuntimeError(f"Dispatch preview has invalid planned row {index} in {queue_name}. Re-run Preview Dispatch.")
            missing_required = _missing_required_dispatch_fields(row)
            if missing_required:
                missing_label = ", ".join(missing_required)
                raise RuntimeError(
                    f"Dispatch preview planned row {index} in {queue_name} is missing required field(s): {missing_label}. Re-run Preview Dispatch."
                )
    reasons = preview.get("exclusion_reason_counts") if isinstance(preview.get("exclusion_reason_counts"), dict) else {}
    if "skipped_rows" in preview:
        skipped_rows = int(preview.get("skipped_rows") or 0)
        skipped_reason_total = sum(int(value or 0) for value in reasons.values())
        if skipped_rows != skipped_reason_total:
            raise RuntimeError("Dispatch preview skipped row count does not match skipped reasons. Re-run Preview Dispatch.")
def load_dispatch_run_history(history_path: Path = DISPATCH_RUN_HISTORY_PATH) -> List[Dict[str, object]]:
    if not history_path.exists():
        return []
    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _dispatch_sendgrid_shard_counts(payload: Dict[str, object], prefix: str) -> Dict[str, int]:
    return {
        f"sendgrid_{index}": int(payload.get(f"{prefix}_sendgrid_{index}") or 0)
        for index in range(1, 6)
    }


def _dispatch_alias_fields(payload: Dict[str, object]) -> Dict[str, object]:
    rows_written_per_queue = payload.get("rows_written_per_queue")
    if isinstance(rows_written_per_queue, dict):
        rows_written_per_queue_map = {
            str(key): int(value or 0)
            for key, value in rows_written_per_queue.items()
        }
    else:
        rows_written_per_queue_map = {}
    return {
        "active_source_key": str(payload.get("dispatch_source_mode") or DISPATCH_SOURCE_TRIAGED_KEEP),
        "source_label": str(payload.get("dispatch_source_name") or ""),
        "source_path": str(payload.get("dispatch_source_path") or ""),
        "source_file_path": str(payload.get("dispatch_source_path") or ""),
        "source_row_count": int(payload.get("dispatch_source_row_count") or 0),
        "total_source_rows": int(payload.get("dispatch_source_row_count") or 0),
        "eligible_rows": int(payload.get("dispatch_eligible_row_count") or 0),
        "selected_rows": int(payload.get("dispatch_selected_row_count") or 0),
        "skipped_already_contacted": int(payload.get("skipped_already_contacted") or 0),
        "skipped_already_sent": int(payload.get("skipped_already_sent") or 0),
        "skipped_already_queued": int(payload.get("skipped_already_queued") or 0),
        "skipped_suppressed": int(payload.get("skipped_suppressed") or payload.get("suppressed_skipped") or 0),
        "skipped_invalid_malformed": int(payload.get("skipped_invalid_malformed") or payload.get("invalid_malformed_skipped") or 0),
        "skipped_invalid_source_row": int(payload.get("skipped_invalid_source_row") or payload.get("skipped_invalid_malformed") or payload.get("invalid_malformed_skipped") or 0),
        "rows_to_add_private_jc": int(payload.get("rows_to_add_private_jc") or payload.get("added_astra") or 0),
        "rows_to_add_sendgrid_shards": _dispatch_sendgrid_shard_counts(payload, "rows_to_add"),
        "rows_written_sendgrid_shards": {
            f"sendgrid_{index}": int(
                rows_written_per_queue_map.get(f"sendgrid_{index}")
                or payload.get(f"assigned_sg{index}")
                or 0
            )
            for index in range(1, 6)
        },
        "rows_written_private_jc": int(rows_written_per_queue_map.get("private_jc") or 0),
        "total_rows_that_would_be_written": int(payload.get("total_rows_would_write") or 0),
        "started_at": str(payload.get("started_at") or payload.get("started_at_utc") or ""),
        "completed_at": str(payload.get("completed_at") or payload.get("completed_at_utc") or ""),
    }


def _dispatch_history_entry(report: Dict[str, object]) -> Dict[str, object]:
    alias = _dispatch_alias_fields(report)
    rows_written_per_queue = report.get("rows_written_per_queue")
    rows_written = dict(rows_written_per_queue) if isinstance(rows_written_per_queue, dict) else {}
    return {
        "run_id": str(report.get("run_id") or ""),
        "campaign_type": str(report.get("campaign_type") or CAMPAIGN_TYPE_COLD),
        "source_key": alias["active_source_key"],
        "source_label": alias["source_label"],
        "source_file_path": alias["source_file_path"],
        "total_source_rows": alias["total_source_rows"],
        "eligible_rows": alias["eligible_rows"],
        "skipped_counts": {
            "already_sent": alias["skipped_already_sent"],
            "already_contacted": alias["skipped_already_contacted"],
            "already_queued": alias["skipped_already_queued"],
            "suppressed": alias["skipped_suppressed"],
            "invalid_malformed": alias["skipped_invalid_malformed"],
        },
        "rows_written_per_queue": rows_written,
        "started_at": alias["started_at"],
        "completed_at": alias["completed_at"],
        "status": str(report.get("status") or ""),
        "report_path": str(report.get("report_path") or ""),
    }


def _append_dispatch_run_history(
    report: Dict[str, object],
    *,
    history_path: Path = DISPATCH_RUN_HISTORY_PATH,
    limit: int = DISPATCH_RUN_HISTORY_LIMIT,
) -> None:
    history = load_dispatch_run_history(history_path)
    history.insert(0, _dispatch_history_entry(report))
    write_json_atomic(history_path, history[: max(1, int(limit or 1))])


def _registered_sendgrid_profiles() -> List[str]:
    return [
        name
        for name, cfg in PROFILES.items()
        if str(cfg.get("provider") or "") == "sendgrid"
    ]


def _enabled_sendgrid_dispatch_profiles() -> List[str]:
    return [
        name
        for name in PRODUCTION_SENDGRID_PROFILES
        if name in PROFILES
        and str(PROFILES[name].get("provider") or "") == "sendgrid"
        and not bool(PROFILES[name].get("controlled_test"))
    ]


def _sendgrid_profile_label(profile_name: str) -> str:
    return str(profile_name or "").removeprefix("sendgrid_").replace("_", " ").title()


def _legacy_sendgrid_queue_key(path: Path) -> str:
    match = re.fullmatch(r"recipients_sendgrid_([1-5])\.csv", path.name)
    return f"sendgrid_{match.group(1)}" if match else ""


def _dispatch_queue_key(path: Path, jc_path: Path, sendgrid_paths: Sequence[Path]) -> str:
    if path == jc_path:
        return "private_jc"
    for index, candidate in enumerate(sendgrid_paths, start=1):
        if path == candidate:
            return f"sendgrid_{index}"
    return path.name


DISPATCH_QUEUE_KEYS = ("private_jc", "sendgrid_1", "sendgrid_2", "sendgrid_3", "sendgrid_4", "sendgrid_5")


def _dispatch_queue_keys(payload: Dict[str, object]) -> List[str]:
    queue_paths = payload.get("queue_paths")
    plan_rows = payload.get("plan_rows_by_queue")
    known = queue_paths if isinstance(queue_paths, dict) else plan_rows if isinstance(plan_rows, dict) else {}
    requested = payload.get("queue_key_order")
    if isinstance(requested, list):
        ordered = [str(key) for key in requested if str(key) in known]
        if ordered and ordered[0] == "private_jc":
            return ordered
    legacy = [key for key in DISPATCH_QUEUE_KEYS if key in known]
    if legacy and legacy[0] == "private_jc":
        return legacy
    sendgrid_keys = sorted(
        (str(key) for key in known if str(key).startswith("sendgrid_")),
        key=str,
    )
    return ["private_jc", *sendgrid_keys] if "private_jc" in known else sendgrid_keys


def _confirmation_queue_lock_paths(
    preview: Dict[str, object],
    destination_queue_paths: Sequence[Path],
) -> List[Path]:
    safety_queue_paths: List[Path] = []
    if int(preview.get("history_policy_version") or 0) == DISPATCH_HISTORY_POLICY_VERSION:
        raw_safety_queue_paths = preview.get("queue_safety_paths")
        if not isinstance(raw_safety_queue_paths, list) or not raw_safety_queue_paths:
            raise RuntimeError(
                "Dispatch preview is missing queue safety paths. Re-run Preview Dispatch."
            )
        if any(not str(path or "").strip() for path in raw_safety_queue_paths):
            raise RuntimeError(
                "Dispatch preview has invalid queue safety paths. Re-run Preview Dispatch."
            )
        safety_queue_paths = [Path(str(path)) for path in raw_safety_queue_paths]
        dependency_fingerprints = preview.get("dependency_fingerprints")
        if not isinstance(dependency_fingerprints, dict):
            raise RuntimeError(
                "Dispatch preview is missing dependency state. Re-run Preview Dispatch."
            )
        fingerprinted_paths = {
            Path(str(entry.get("path") or "")).resolve()
            for entry in dependency_fingerprints.values()
            if isinstance(entry, dict) and str(entry.get("path") or "").strip()
        }
        if any(path.resolve() not in fingerprinted_paths for path in safety_queue_paths):
            raise RuntimeError(
                "Dispatch preview queue safety paths are not fully fingerprinted. Re-run Preview Dispatch."
            )

    return list(dict.fromkeys([*destination_queue_paths, *safety_queue_paths]))


def _planned_queue_row_summary(plan_rows_by_queue: Dict[str, object]) -> Dict[str, int]:
    private_count = 0
    sendgrid_count = 0
    total_rows = 0
    email_counts: Counter[str] = Counter()
    for key, rows in (plan_rows_by_queue.items() if isinstance(plan_rows_by_queue, dict) else []):
        if not isinstance(rows, list):
            rows = []
        row_count = len(rows)
        total_rows += row_count
        if key == "private_jc":
            private_count += row_count
        elif key.startswith("sendgrid_"):
            sendgrid_count += row_count
        for row in rows:
            if not isinstance(row, dict):
                continue
            email = norm_email(row.get("Email", ""))
            if email:
                email_counts[email] += 1
    duplicate_email_count = sum(1 for count in email_counts.values() if count > 1)
    return {
        "private_jc_planned_count": private_count,
        "sendgrid_planned_count": sendgrid_count,
        "total_planned_queue_rows": total_rows,
        "total_planned_unique_count": len(email_counts),
        "duplicate_planned_email_count": duplicate_email_count,
    }


def _lead_dispatch_payload(
    row: Dict[str, str],
    *,
    dispatch_source_mode: str,
    source_path: Path,
) -> dict[str, object] | None:
    email = norm_email(row.get("Email", ""))
    if not email:
        return None
    lead_id = deterministic_lead_id(email)
    full_name = _strip_cell(row.get("FullName", ""))
    first_name = _trimmed_first_name(row.get("FirstName", "") or full_name or row.get("AuthorName", ""))
    return {
        "lead_id": lead_id,
        "email": email,
        "full_name": full_name,
        "first_name": first_name,
        "source_file": _canonical_workspace_label(source_path),
        "source_row_hash": source_row_hash(row),
        "current_stage": _dispatch_source_stage_for_mode(dispatch_source_mode),
        "current_status": "QUEUED",
        "last_seen_at": iso_utc(),
    }


def _record_dispatch_history_from_preview(
    preview: Dict[str, object],
    *,
    run_id: str,
    dispatched_at: str,
) -> tuple[int, Dict[str, int]]:
    dispatch_source_mode = str(preview.get("dispatch_source_mode") or DISPATCH_SOURCE_TRIAGED_KEEP)
    dispatch_source_path = Path(str(preview.get("dispatch_source_path") or ""))
    campaign_type = normalize_campaign_type(preview.get("campaign_type") or CAMPAIGN_TYPE_COLD)
    result_reason = f"campaign_type={campaign_type}" if campaign_type != CAMPAIGN_TYPE_COLD else ""
    plan_dispatch_events_by_queue = preview.get("plan_dispatch_events_by_queue") or {}
    if not isinstance(plan_dispatch_events_by_queue, dict):
        raise RuntimeError("Dispatch preview is missing lead dispatch history metadata. Re-run Preview Dispatch.")
    explicit_db_path = Path(str(preview.get("lead_ledger_db_path") or "")) if str(preview.get("lead_ledger_db_path") or "").strip() else None
    conn = connect_lead_ledger(_lead_ledger_db_path(explicit_db_path))
    try:
        rows_created = 0
        rows_created_per_queue = {
            str(queue_key): 0
            for queue_key in plan_dispatch_events_by_queue
        }
        with conn:
            for queue_key, raw_events in plan_dispatch_events_by_queue.items():
                if not isinstance(raw_events, list):
                    continue
                for raw_event in raw_events:
                    if not isinstance(raw_event, dict):
                        continue
                    email = norm_email(raw_event.get("email", ""))
                    if not email:
                        continue
                    lead_id = str(raw_event.get("lead_id") or deterministic_lead_id(email)).strip()
                    lead = load_lead_by_id(conn, lead_id)
                    if lead is None:
                        upsert_lead(
                            conn,
                            lead_id=lead_id,
                            email=email,
                            full_name=raw_event.get("full_name", ""),
                            first_name=raw_event.get("first_name", ""),
                            source_file=_canonical_workspace_label(dispatch_source_path) if str(dispatch_source_path) else "",
                            source_row_hash=raw_event.get("source_row_hash", ""),
                            first_seen_at=dispatched_at,
                            last_seen_at=dispatched_at,
                            current_stage=_dispatch_source_stage_for_mode(dispatch_source_mode),
                            current_status="QUEUED",
                            updated_at=dispatched_at,
                            created_at=dispatched_at,
                        )
                    record_dispatch_event(
                        conn,
                        lead_id=lead_id,
                        run_id=run_id,
                        dispatch_source=dispatch_source_mode,
                        profile=str(raw_event.get("profile") or queue_key),
                        queue_target=str(raw_event.get("queue_target") or queue_key),
                        result_status="queued",
                        result_reason=result_reason,
                        dispatched_at=dispatched_at,
                        created_at=dispatched_at,
                        updated_at=dispatched_at,
                        manage_transaction=False,
                    )
                    rows_created += 1
                    if queue_key in rows_created_per_queue:
                        rows_created_per_queue[queue_key] += 1
        return rows_created, rows_created_per_queue
    finally:
        conn.close()


def _build_dispatch_plan(
    *,
    master_path: Path,
    rejected_path: Path,
    verified_path: Path,
    triaged_keep_path: Path,
    dispatch_source_mode: str,
    dispatch_cap: str = DISPATCH_CAP_ALL,
    jc_queue_path: Path | None = None,
    sendgrid_queue_paths: Sequence[Path] | None = None,
    jc_log_path: Path | None = None,
    sendgrid_log_paths: Sequence[Path] | None = None,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    lead_ledger_db_path: Path | None = None,
    sendgrid_events_path: Path = settings.WEBHOOK_EVENTS_PATH,
    campaign_type: str = CAMPAIGN_TYPE_COLD,
) -> Dict[str, object]:
    if not master_path.exists():
        raise FileNotFoundError(f"Master leads file not found: {master_path}")

    master_headers, _master_rows = _read_csv_rows(master_path)
    if not master_headers:
        raise ValueError("Master leads file is empty.")
    if "Email" not in master_headers:
        raise ValueError("Master leads file must contain an Email column.")

    blocked_emails, suppression_summary = _blocked_email_set(
        sendgrid_suppressions_path=sendgrid_suppressions_path,
        suppressed_path=suppressed_path,
        unsubscribed_path=unsubscribed_path,
    )
    configured_sendgrid_routing = sendgrid_queue_paths is None
    default_jc_path: Path | None = None
    default_sendgrid_paths: List[Path] | None = None
    default_jc_log_path: Path | None = None
    default_sendgrid_log_paths: List[Path] | None = None
    if (
        jc_queue_path is None
        or sendgrid_queue_paths is None
        or jc_log_path is None
        or sendgrid_log_paths is None
    ):
        default_jc_path, default_sendgrid_paths, default_jc_log_path, default_sendgrid_log_paths = _dispatch_profile_paths()
    jc_path = jc_queue_path or default_jc_path
    if jc_path is None:
        raise ValueError("Dispatch requires a Private JC queue file.")
    sendgrid_paths = list(sendgrid_queue_paths or default_sendgrid_paths or [])
    if not sendgrid_paths:
        raise ValueError("Dispatch requires at least one enabled production SendGrid profile.")
    if configured_sendgrid_routing:
        sendgrid_profile_order = _enabled_sendgrid_dispatch_profiles()
        if len(sendgrid_profile_order) != len(sendgrid_paths):
            raise ValueError("Enabled SendGrid profile configuration does not match its queue files.")
        sendgrid_queue_keys = list(sendgrid_profile_order)
    else:
        sendgrid_profile_order = []
        sendgrid_queue_keys = [f"sendgrid_{index}" for index in range(1, len(sendgrid_paths) + 1)]
    jc_log = jc_log_path or default_jc_log_path
    if jc_log is None:
        raise ValueError("Dispatch requires a Private JC log file.")
    sg_logs = list(sendgrid_log_paths or default_sendgrid_log_paths or [])
    if not sg_logs:
        raise ValueError("Dispatch requires authoritative SendGrid history logs.")
    queue_paths = [jc_path, *sendgrid_paths]
    if configured_sendgrid_routing:
        safety_queue_paths = [
            jc_path,
            settings.shard_path(str(PROFILES["private_jc_warm"]["csv"])),
            *[
                settings.shard_path(str(PROFILES[name]["csv"]))
                for name in _registered_sendgrid_profiles()
            ],
        ]
    else:
        safety_queue_paths = [
            jc_path,
            jc_path.with_name("recipients_private_jc_warm.csv"),
            *sendgrid_paths,
        ]
    safety_queue_paths = list(dict.fromkeys(safety_queue_paths))
    log_paths = [jc_log, *sg_logs]
    ledger_conn = connect_lead_ledger(_lead_ledger_db_path(lead_ledger_db_path))

    try:
        source_mode = _normalize_dispatch_source_mode(dispatch_source_mode)
        normalized_campaign_type = normalize_campaign_type(campaign_type)
        # Recontact treats successful delivery as informational history. Fresh
        # Cold blocks it globally before routing. Queue and campaign
        # idempotency remain fail-closed for both modes.
        allow_previously_sent = is_recontact_cold_campaign(normalized_campaign_type)
        source_state = _dispatch_source_snapshot(
            source_mode=source_mode,
            cleaned_path=master_path,
            triaged_keep_path=triaged_keep_path,
            strict_verified_path=verified_path,
        )
        if source_state["dispatch_block_reason"]:
            raise ValueError(str(source_state["dispatch_block_reason"]))
        source_path = Path(str(source_state["dispatch_source_path"]))
        source_headers, raw_source_rows = _read_csv_rows(source_path)
        source_rows = list(raw_source_rows)
        if bool(source_state.get("status_keep_filter")) and "Status" in source_headers:
            source_rows = [row for row in raw_source_rows if str(row.get("Status", "")).strip().upper() == "KEEP"]
        if not source_headers:
            raise ValueError(f"{source_state['dispatch_source_name']} dispatch source is empty: {source_path}")
        if not source_rows:
            raise ValueError(f"{source_state['dispatch_source_name']} dispatch source has no eligible rows: {source_path}")
        safer_recontact_source = is_safer_recontact_source_path(source_path)
        full_recontact_sendgrid_only = (
            is_recontact_cold_campaign(normalized_campaign_type)
            and not safer_recontact_source
        )
        dispatch_source_name = "Safer Recontact Pool" if safer_recontact_source else str(source_state["dispatch_source_name"])
        dispatch_source_detail = "Safer recontact CSV — not found in active history" if safer_recontact_source else dispatch_source_name

        queue_headers_by_path: Dict[Path, List[str]] = {}
        queue_rows_by_path: Dict[Path, List[Dict[str, str]]] = {}
        for path in safety_queue_paths:
            headers, rows = _read_queue_rows(path)
            queue_headers_by_path[path] = headers
            queue_rows_by_path[path] = rows

        warm_cfg = PROFILES.get("private_jc_warm", {})
        warm_log_value = str(warm_cfg.get("log") or "").strip()
        private_history_paths = [jc_log]
        if warm_log_value:
            private_history_paths.append(settings.log_path(warm_log_value))
        authoritative_jc_logs, ignored_jc_logs = _authoritative_history_paths(private_history_paths)
        authoritative_sg_logs, ignored_sg_logs = _authoritative_history_paths(sg_logs)
        authoritative_log_paths = [*authoritative_jc_logs, *authoritative_sg_logs]
        ignored_history_paths = [*ignored_jc_logs, *ignored_sg_logs]
        jc_sent = _sent_email_set(authoritative_jc_logs)
        sendgrid_sent = _sent_email_set(authoritative_sg_logs)
        bad_event_emails = load_bad_sendgrid_event_emails(sendgrid_events_path) | load_done_statuses_from_logs(authoritative_log_paths, {"INVALID"})
        global_queue_block_emails = _existing_queue_email_set(queue_rows_by_path)
        source_email_by_lead_id: Dict[str, str] = {}
        source_emails: set[str] = set()
        for row in source_rows:
            email = norm_email(row.get("Email", ""))
            if not email:
                continue
            try:
                lead_id = deterministic_lead_id(email)
            except ValueError:
                continue
            source_email_by_lead_id[lead_id] = email
            source_emails.add(email)
        (
            astra_contacted_lead_ids,
            astra_warm_contacted_lead_ids,
            sendgrid_contacted_lead_ids,
            global_bad_contact_lead_ids,
            ignored_contact_history_lead_ids,
        ) = _dispatch_history_contact_sets(ledger_conn, set(source_email_by_lead_id))
        astra_lane_contacted_lead_ids = astra_contacted_lead_ids | astra_warm_contacted_lead_ids
        ignored_history_emails = {
            source_email_by_lead_id[lead_id]
            for lead_id in ignored_contact_history_lead_ids
            if lead_id in source_email_by_lead_id
        }
        ignored_history_emails |= _source_email_matches_in_paths(source_emails, ignored_history_paths)
        ledger_state = dispatch_history_state(ledger_conn)

        eligible_rows_total = len(source_rows)
        rows_with_booktitle = sum(1 for row in source_rows if _row_has_any_value(row, BOOK_TITLE_COUNT_HEADERS))
        rows_with_author_name = sum(1 for row in source_rows if _row_has_any_value(row, AUTHOR_NAME_COUNT_HEADERS))
        normalized_cap = _normalize_dispatch_cap(dispatch_cap)
        selected_limit = _dispatch_cap_limit(normalized_cap, eligible_rows_total)
        selected_rows_scanned = 0

        sg_assign_cursor = 0
        added_astra_rows: List[Dict[str, str]] = []
        added_sendgrid_rows_by_index: List[List[Dict[str, str]]] = [[] for _ in sendgrid_paths]
        master_seen: set[str] = set()
        suppressed_skipped = 0
        duplicate_master_skipped = 0
        invalid_malformed_skipped = 0
        bad_event_skipped = 0
        already_contacted_skipped = 0
        previously_sent_allowed = 0
        other_family_sent_history_allowed = 0
        already_contacted_allowed = 0
        added_astra = 0
        added_sendgrid = 0
        skipped_astra_already_sent = 0
        skipped_astra_already_queued = 0
        skipped_sendgrid_already_sent = 0
        skipped_sendgrid_already_queued = 0
        route_sendgrid_already_sent = 0
        route_sendgrid_already_queued = 0
        skipped_both = 0
        outcome_counts: Counter[str] = Counter()
        exclusion_reason_counts: Counter[str] = Counter()
        already_contacted_evidence: List[Dict[str, str]] = []
        plan_dispatch_events_by_queue: Dict[str, List[Dict[str, str]]] = {
            key: [] for key in ["private_jc", *sendgrid_queue_keys]
        }
        successful_contact_lead_ids = astra_lane_contacted_lead_ids | sendgrid_contacted_lead_ids
        successful_send_emails = jc_sent | sendgrid_sent

        for row in source_rows:
            if normalized_cap != DISPATCH_CAP_ALL and (added_astra + added_sendgrid) >= selected_limit:
                break
            selected_rows_scanned += 1
            email = norm_email(row.get("Email", ""))
            if not email or not EMAIL_RE.match(email):
                invalid_malformed_skipped += 1
                exclusion_reason_counts["invalid_source_row"] += 1
                continue
            if email in master_seen:
                duplicate_master_skipped += 1
                exclusion_reason_counts["duplicate_source_row"] += 1
                continue
            master_seen.add(email)

            lead_id = deterministic_lead_id(email)
            if email in blocked_emails:
                suppressed_skipped += 1
                exclusion_reason_counts["suppressed"] += 1
                continue
            if email in bad_event_emails:
                bad_event_skipped += 1
                exclusion_reason_counts["bad_sendgrid_event"] += 1
                continue

            if email in global_queue_block_emails:
                skipped_astra_already_queued += 1
                skipped_sendgrid_already_queued += 1
                exclusion_reason_counts["already_queued"] += 1
                continue

            if lead_id in global_bad_contact_lead_ids:
                bad_event_skipped += 1
                exclusion_reason_counts["bad_contact_history"] += 1
                if len(already_contacted_evidence) < DISPATCH_PREVIEW_ROWS:
                    already_contacted_evidence.append(_dispatch_history_evidence_for_lead(ledger_conn, lead_id, email))
                continue
            if not allow_previously_sent and email in successful_send_emails:
                skipped_astra_already_sent += 1
                skipped_sendgrid_already_sent += 1
                already_contacted_skipped += 1
                exclusion_reason_counts["already_sent"] += 1
                if len(already_contacted_evidence) < DISPATCH_PREVIEW_ROWS:
                    already_contacted_evidence.append(_dispatch_history_evidence_for_lead(ledger_conn, lead_id, email))
                continue
            if not allow_previously_sent and lead_id in successful_contact_lead_ids:
                already_contacted_skipped += 1
                exclusion_reason_counts["already_contacted"] += 1
                if len(already_contacted_evidence) < DISPATCH_PREVIEW_ROWS:
                    already_contacted_evidence.append(_dispatch_history_evidence_for_lead(ledger_conn, lead_id, email))
                continue
            if lead_id in successful_contact_lead_ids and allow_previously_sent:
                already_contacted_allowed += 1
            normalized = {header: _strip_cell(row.get(header, "")) for header in source_headers}
            normalized["Email"] = email
            normalized["campaign_type"] = normalized_campaign_type
            if full_recontact_sendgrid_only:
                normalized["dispatch_source_kind"] = RECONTACT_SOURCE_KIND_FULL
            missing_required = _missing_required_dispatch_fields(normalized)
            if missing_required:
                invalid_malformed_skipped += 1
                exclusion_reason_counts["missing_required_dispatch_field"] += 1
                continue

            added_to_astra = False
            added_to_sendgrid = False
            route_failure_reasons: List[str] = []

            if email in (jc_sent | sendgrid_sent) and allow_previously_sent:
                previously_sent_allowed += 1

            # Full Recontact is the SendGrid resend lane. Fresh Cold and the
            # separately generated Safer Recontact pool retain their existing
            # balanced routing behavior.
            prefer_sendgrid = added_astra > added_sendgrid

            def add_to_astra() -> bool:
                nonlocal added_astra, other_family_sent_history_allowed
                if email in sendgrid_sent and email not in jc_sent:
                    other_family_sent_history_allowed += 1
                added_astra_rows.append(normalized)
                global_queue_block_emails.add(email)
                added_astra += 1
                plan_dispatch_events_by_queue["private_jc"].append(
                    {
                        "lead_id": lead_id,
                        "email": email,
                        "queue_target": "private_jc",
                        "profile": "private_jc",
                        "full_name": _strip_cell(normalized.get("FullName", "")),
                        "first_name": _trimmed_first_name(normalized.get("FirstName", "") or normalized.get("FullName", "")),
                        "source_row_hash": source_row_hash(normalized),
                        "campaign_type": normalized_campaign_type,
                    }
                )
                return True

            def add_to_sendgrid() -> bool:
                nonlocal added_sendgrid, sg_assign_cursor, route_sendgrid_already_sent, route_sendgrid_already_queued, other_family_sent_history_allowed
                if email in jc_sent and email not in sendgrid_sent:
                    other_family_sent_history_allowed += 1
                bucket_index = sg_assign_cursor % len(sendgrid_paths)
                sg_assign_cursor += 1
                added_sendgrid_rows_by_index[bucket_index].append(normalized)
                global_queue_block_emails.add(email)
                added_sendgrid += 1
                queue_key = sendgrid_queue_keys[bucket_index]
                plan_dispatch_events_by_queue[queue_key].append(
                    {
                        "lead_id": lead_id,
                        "email": email,
                        "queue_target": queue_key,
                        "profile": sendgrid_profile_order[bucket_index] if sendgrid_profile_order else queue_key,
                        "full_name": _strip_cell(normalized.get("FullName", "")),
                        "first_name": _trimmed_first_name(normalized.get("FirstName", "") or normalized.get("FullName", "")),
                        "source_row_hash": source_row_hash(normalized),
                        "campaign_type": normalized_campaign_type,
                    }
                )
                return True

            if full_recontact_sendgrid_only:
                added_to_sendgrid = add_to_sendgrid()
            elif prefer_sendgrid:
                added_to_sendgrid = add_to_sendgrid()
                if not added_to_sendgrid:
                    added_to_astra = add_to_astra()
            else:
                added_to_astra = add_to_astra()
                if not added_to_astra:
                    added_to_sendgrid = add_to_sendgrid()

            if added_to_astra and added_to_sendgrid:
                outcome_counts["added_astra_and_sendgrid"] += 1
            elif added_to_astra:
                outcome_counts["added_astra_only"] += 1
            elif added_to_sendgrid:
                outcome_counts["added_sendgrid_only"] += 1
            else:
                outcome_counts["skipped_both"] += 1
                skipped_both += 1
                reason_set = set(route_failure_reasons)
                if "astra_already_sent" in reason_set:
                    skipped_astra_already_sent += 1
                if "sendgrid_already_sent" in reason_set:
                    skipped_sendgrid_already_sent += 1
                if "astra_already_queued" in reason_set:
                    skipped_astra_already_queued += 1
                if "sendgrid_already_queued" in reason_set:
                    skipped_sendgrid_already_queued += 1
                if any(reason.endswith("_already_sent") for reason in reason_set):
                    exclusion_reason_counts["already_sent"] += 1
                elif any(reason.endswith("_already_queued") for reason in reason_set):
                    exclusion_reason_counts["already_queued"] += 1
                elif any(reason.endswith("_already_contacted") for reason in reason_set):
                    already_contacted_skipped += 1
                    exclusion_reason_counts["already_contacted"] += 1
                    if len(already_contacted_evidence) < DISPATCH_PREVIEW_ROWS:
                        already_contacted_evidence.append(_dispatch_history_evidence_for_lead(ledger_conn, lead_id, email))
                else:
                    exclusion_reason_counts["not_routed"] += 1

        total_dispatch_rows = selected_rows_scanned

        queue_headers = _queue_output_headers(
            (queue_headers_by_path[path] for path in queue_paths),
            source_headers,
        )
        if "BookTitle" in master_headers and "BookTitle" not in queue_headers:
            queue_headers.append("BookTitle")
        if normalized_campaign_type != CAMPAIGN_TYPE_COLD and "campaign_type" not in queue_headers:
            queue_headers.append("campaign_type")
        if full_recontact_sendgrid_only and "dispatch_source_kind" not in queue_headers:
            queue_headers.append("dispatch_source_kind")

        plan_rows_by_path: Dict[Path, List[Dict[str, str]]] = {path: [] for path in queue_paths}
        plan_rows_by_path[jc_path] = [_master_row_to_queue_row(row, queue_headers) for row in added_astra_rows]
        for path, rows in zip(sendgrid_paths, added_sendgrid_rows_by_index):
            plan_rows_by_path[path] = [_master_row_to_queue_row(row, queue_headers) for row in rows]

        plan_rows_by_queue = {"private_jc": plan_rows_by_path[jc_path]}
        plan_rows_by_queue.update(
            {
                key: plan_rows_by_path[path]
                for key, path in zip(sendgrid_queue_keys, sendgrid_paths)
            }
        )
        rows_written_per_queue = {
            key: len(rows)
            for key, rows in plan_rows_by_queue.items()
        }
        planned_summary = _planned_queue_row_summary(plan_rows_by_queue)
        planned_authoritative_sent_overlap: set[str] = set()
        for queue_rows in plan_rows_by_queue.values():
            planned_authoritative_sent_overlap |= {
                norm_email(row.get("Email", ""))
                for row in queue_rows
                if isinstance(row, dict) and norm_email(row.get("Email", "")) in (jc_sent | sendgrid_sent)
            }
        planned_authoritative_sent_overlap_count = len(planned_authoritative_sent_overlap)
        sendgrid_profile_planned_counts = {
            key: len(plan_rows_by_path[path])
            for key, path in zip(sendgrid_queue_keys, sendgrid_paths)
        }
        legacy_sendgrid_planned_counts = {f"sendgrid_{index}": 0 for index in range(1, 6)}
        for key, path in zip(sendgrid_queue_keys, sendgrid_paths):
            legacy_key = _legacy_sendgrid_queue_key(path)
            if legacy_key:
                legacy_sendgrid_planned_counts[legacy_key] = int(sendgrid_profile_planned_counts.get(key) or 0)
        sendgrid_zero_reason = ""
        if added_sendgrid == 0 and int(planned_summary["total_planned_queue_rows"]):
            if route_sendgrid_already_sent:
                sendgrid_zero_reason = (
                    "SendGrid received 0 rows because its candidate rows were already sent."
                )
            elif route_sendgrid_already_queued:
                sendgrid_zero_reason = (
                    "SendGrid received 0 rows because its candidate rows were already queued."
                )
            else:
                sendgrid_zero_reason = (
                    "SendGrid received 0 rows after route fallback and safety filtering."
                )
        recontact_recency = (
            _recontact_recency_summary(ledger_conn, plan_rows_by_queue)
            if is_recontact_cold_campaign(normalized_campaign_type)
            else _empty_recontact_recency_summary(int(planned_summary["total_planned_unique_count"]))
        )
        history_source_category_counts = {
            "already_sent_from_actual_send_log": int(exclusion_reason_counts.get("already_sent") or 0),
            "already_contacted_from_contact_history": already_contacted_skipped,
            "suppressed_unsubscribe": 0,
            "suppressed_bounce": 0,
            "skipped_from_non_authoritative_history_ignored": len(ignored_history_emails),
        }
        dependency_fingerprints = _collect_dispatch_input_fingerprints(
            source_path=source_path,
            queue_paths=safety_queue_paths,
            log_paths=log_paths,
            sendgrid_suppressions_path=sendgrid_suppressions_path,
            suppressed_path=suppressed_path,
            unsubscribed_path=unsubscribed_path,
        )
        skipped_rows = int(sum(int(value or 0) for value in exclusion_reason_counts.values()))

        plan = {
            "campaign_type": normalized_campaign_type,
            "history_policy_version": DISPATCH_HISTORY_POLICY_VERSION,
            "prior_success_policy": (
                RECONTACT_PRIOR_SUCCESS_POLICY
                if allow_previously_sent
                else FRESH_COLD_PRIOR_SUCCESS_POLICY
            ),
            "allow_previously_sent": allow_previously_sent,
            "allow_previously_contacted": allow_previously_sent,
            "dispatch_source_mode": source_mode,
            "dispatch_source_kind": "safer_recontact" if safer_recontact_source else source_mode,
            "full_recontact_sendgrid_only": full_recontact_sendgrid_only,
            "dispatch_source_name": dispatch_source_name,
            "dispatch_source_detail": dispatch_source_detail,
            "dispatch_source_path": str(source_path),
            "dispatch_source_label": str(source_state["dispatch_source_label"]),
            "dispatch_source_exists": bool(source_state["dispatch_source_exists"]),
            "dispatch_source_row_count": int(source_state["dispatch_source_row_count"]),
            "dispatch_eligible_row_count": eligible_rows_total,
            "input_rows": eligible_rows_total,
            "rows_with_booktitle": rows_with_booktitle,
            "rows_missing_booktitle": max(0, eligible_rows_total - rows_with_booktitle),
            "rows_with_author_name": rows_with_author_name,
            "rows_missing_author_name": max(0, eligible_rows_total - rows_with_author_name),
            "dispatch_selected_row_count": total_dispatch_rows,
            "dispatch_cap": normalized_cap,
            "dispatch_cap_label": _dispatch_cap_label(normalized_cap),
            "dispatch_block_reason": "",
            "verification_required": bool(source_state["verification_required"]),
            "verification_file_mtime": str(source_state["verification_file_mtime"] or ""),
            "master_label": _display_path_label(master_path),
            "rejected_label": _display_path_label(rejected_path),
            "source_headers": source_headers,
            "queue_headers": queue_headers,
            "queue_key_order": ["private_jc", *sendgrid_queue_keys],
            "queue_paths": {
                "private_jc": str(jc_path),
                **{
                    key: str(path)
                    for key, path in zip(sendgrid_queue_keys, sendgrid_paths)
                },
            },
            "queue_safety_paths": [str(path) for path in safety_queue_paths],
            "sendgrid_profile_order": list(sendgrid_profile_order),
            "sendgrid_profile_labels": {
                profile_name: _sendgrid_profile_label(profile_name)
                for profile_name in sendgrid_profile_order
            },
            "sendgrid_log_paths": [str(path) for path in sg_logs],
            "authoritative_send_log_paths": [str(path) for path in authoritative_log_paths],
            "ignored_non_authoritative_history_paths": [str(path) for path in ignored_history_paths],
            "history_source_category_counts": history_source_category_counts,
            "history_audit_counts": history_source_category_counts,
            "planned_authoritative_sent_overlap_count": planned_authoritative_sent_overlap_count,
            "planned_sent_log_overlap_count": planned_authoritative_sent_overlap_count,
            "queue_existing_counts": {
                "private_jc": len(queue_rows_by_path[jc_path]),
                **{
                    key: len(queue_rows_by_path[path])
                    for key, path in zip(sendgrid_queue_keys, sendgrid_paths)
                },
            },
            "queue_safety_existing_counts": {
                _canonical_workspace_label(path): len(queue_rows_by_path[path])
                for path in safety_queue_paths
            },
            "skipped_invalid_malformed": invalid_malformed_skipped,
            "invalid_malformed_skipped": invalid_malformed_skipped,
            "skipped_invalid_source_row": invalid_malformed_skipped,
            "skipped_bad_sendgrid_event": bad_event_skipped,
            "bad_sendgrid_event_skipped": bad_event_skipped,
            "skipped_suppressed": suppressed_skipped,
            "suppressed_skipped": suppressed_skipped,
            "bad_suppressed_removed_count": bad_event_skipped + suppressed_skipped,
            "skipped_already_contacted": already_contacted_skipped,
            "previously_sent_allowed_count": previously_sent_allowed,
            "already_sent_other_family_allowed": other_family_sent_history_allowed,
            "skipped_already_sent_same_family": skipped_astra_already_sent + skipped_sendgrid_already_sent,
            "already_contacted_allowed_count": already_contacted_allowed,
            "already_contacted_evidence": already_contacted_evidence,
            "duplicate_master_skipped": duplicate_master_skipped,
            "skipped_astra_already_sent": skipped_astra_already_sent,
            "skipped_astra_already_queued": skipped_astra_already_queued,
            "skipped_sendgrid_already_sent": skipped_sendgrid_already_sent,
            "skipped_sendgrid_already_queued": skipped_sendgrid_already_queued,
            "skipped_already_sent": int(exclusion_reason_counts.get("already_sent") or 0),
            "skipped_already_queued": int(exclusion_reason_counts.get("already_queued") or 0),
            "skipped_rows": skipped_rows,
            "rows_to_add_private_jc": added_astra,
            "added_astra": added_astra,
            "rows_to_add_sendgrid": added_sendgrid,
            "added_sendgrid": added_sendgrid,
            "rows_to_add_sendgrid_1": legacy_sendgrid_planned_counts["sendgrid_1"],
            "rows_to_add_sendgrid_2": legacy_sendgrid_planned_counts["sendgrid_2"],
            "rows_to_add_sendgrid_3": legacy_sendgrid_planned_counts["sendgrid_3"],
            "rows_to_add_sendgrid_4": legacy_sendgrid_planned_counts["sendgrid_4"],
            "rows_to_add_sendgrid_5": legacy_sendgrid_planned_counts["sendgrid_5"],
            "sendgrid_shard_planned_counts": legacy_sendgrid_planned_counts,
            "sendgrid_profile_planned_counts": sendgrid_profile_planned_counts,
            "sendgrid_zero_reason": sendgrid_zero_reason,
            "assigned_sg1": legacy_sendgrid_planned_counts["sendgrid_1"],
            "assigned_sg2": legacy_sendgrid_planned_counts["sendgrid_2"],
            "assigned_sg3": legacy_sendgrid_planned_counts["sendgrid_3"],
            "assigned_sg4": legacy_sendgrid_planned_counts["sendgrid_4"],
            "assigned_sg5": legacy_sendgrid_planned_counts["sendgrid_5"],
            "skipped_both": skipped_both,
            "outcome_counts": dict(outcome_counts),
            "exclusion_reason_counts": dict(exclusion_reason_counts),
            "total_rows_would_write": added_astra + added_sendgrid,
            **planned_summary,
            "recontact_recency": recontact_recency,
            "recontact_planned_unique": int(recontact_recency["planned_unique"]),
            "recontact_found_in_active_history": int(recontact_recency["found_in_active_history"]),
            "recontact_seen_this_month": int(recontact_recency["seen_this_month"]),
            "recontact_not_found_in_active_history": int(recontact_recency["not_found_in_active_history"]),
            "recontact_recency_high_risk": bool(recontact_recency["high_risk"]),
            "recontact_recency_risk_level": str(recontact_recency.get("risk_level") or ""),
            "recontact_recency_warning": str(recontact_recency["warning"]),
            "dispatch_source_preview_rows": source_state["dispatch_source_preview_rows"],
            "dispatch_source_headers": source_state["dispatch_source_headers"],
            "assigned_preview_rows": _preview_rows(
                [row for path in queue_paths for row in plan_rows_by_path[path]],
                queue_headers,
                DISPATCH_PREVIEW_ROWS,
            ),
            "suppression_summary": suppression_summary,
            "bad_event_summary": {"bad_sendgrid_event_emails": len(bad_event_emails)},
            "plan_rows_by_queue": plan_rows_by_queue,
            "plan_dispatch_events_by_queue": plan_dispatch_events_by_queue,
            "rows_written_per_queue": rows_written_per_queue,
            "dependency_fingerprints": dependency_fingerprints,
            "lead_dispatch_history_state": ledger_state,
        }
        plan.update(_dispatch_alias_fields(plan))
        return plan
    finally:
        ledger_conn.close()


def preview_dispatch_master_leads(
    *,
    master_path: Path = MASTER_OUTPUT_PATH,
    rejected_path: Path = MASTER_REJECTED_PATH,
    verified_path: Path = STRICT_VERIFIED_PATH,
    triaged_keep_path: Path = TRIAGED_KEEP_PATH,
    dispatch_source_mode: str = DISPATCH_SOURCE_TRIAGED_KEEP,
    dispatch_cap: str = DISPATCH_CAP_ALL,
    jc_queue_path: Path | None = None,
    sendgrid_queue_paths: Sequence[Path] | None = None,
    jc_log_path: Path | None = None,
    sendgrid_log_paths: Sequence[Path] | None = None,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    lead_ledger_db_path: Path | None = None,
    sendgrid_events_path: Path = settings.WEBHOOK_EVENTS_PATH,
    campaign_type: str = CAMPAIGN_TYPE_COLD,
    preview_dir: Path = DISPATCH_PREVIEWS_DIR,
) -> Dict[str, object]:
    plan = _build_dispatch_plan(
        master_path=master_path,
        rejected_path=rejected_path,
        verified_path=verified_path,
        triaged_keep_path=triaged_keep_path,
        dispatch_source_mode=dispatch_source_mode,
        dispatch_cap=dispatch_cap,
        jc_queue_path=jc_queue_path,
        sendgrid_queue_paths=sendgrid_queue_paths,
        jc_log_path=jc_log_path,
        sendgrid_log_paths=sendgrid_log_paths,
        sendgrid_suppressions_path=sendgrid_suppressions_path,
        suppressed_path=suppressed_path,
        unsubscribed_path=unsubscribed_path,
        lead_ledger_db_path=lead_ledger_db_path,
        sendgrid_events_path=sendgrid_events_path,
        campaign_type=campaign_type,
    )
    preview_id = f"dispatch_preview_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    if (
        is_recontact_cold_campaign(plan.get("campaign_type"))
        and not _validate_recontact_source_classification(plan)
    ):
        campaign_id = preview_id
        queue_headers = [str(value or "").strip() for value in (plan.get("queue_headers") or []) if str(value or "").strip()]
        if "campaign_id" not in queue_headers:
            queue_headers.append("campaign_id")
        plan["queue_headers"] = queue_headers
        plan["campaign_id"] = campaign_id
        plan_rows_by_queue = plan.get("plan_rows_by_queue")
        if not isinstance(plan_rows_by_queue, dict):
            raise RuntimeError("Full Recontact plan is missing queue rows.")
        for planned_rows in plan_rows_by_queue.values():
            if not isinstance(planned_rows, list):
                raise RuntimeError("Full Recontact plan has invalid queue rows.")
            for row in planned_rows:
                if not isinstance(row, dict):
                    raise RuntimeError("Full Recontact plan has an invalid queue row.")
                row["campaign_id"] = campaign_id
        plan_dispatch_events_by_queue = plan.get("plan_dispatch_events_by_queue")
        if isinstance(plan_dispatch_events_by_queue, dict):
            for events in plan_dispatch_events_by_queue.values():
                if not isinstance(events, list):
                    continue
                for event in events:
                    if isinstance(event, dict):
                        event["campaign_id"] = campaign_id
        queue_key_order = [str(value) for value in (plan.get("queue_key_order") or [])]
        plan["assigned_preview_rows"] = _preview_rows(
            [
                row
                for queue_key in queue_key_order
                for row in (plan_rows_by_queue.get(queue_key) or [])
                if isinstance(row, dict)
            ],
            queue_headers,
            DISPATCH_PREVIEW_ROWS,
        )
    preview = {
        **plan,
        "preview_id": preview_id,
        "status": "previewed",
        "created_at_utc": iso_utc(),
        "updated_at_utc": iso_utc(),
        "created_at": "",
        "started_at": "",
        "completed_at": "",
        "preview_path": str(_dispatch_preview_path(preview_id, preview_dir)),
        "lead_ledger_db_path": str(_lead_ledger_db_path(lead_ledger_db_path)),
    }
    assigned_preview_archive_path = _archive_assigned_dispatch_preview(preview)
    preview["assigned_preview_archive_path"] = str(assigned_preview_archive_path)
    _save_dispatch_preview(preview, preview_dir)
    return preview


def validate_dispatch_preview(
    preview_id: str,
    *,
    preview_dir: Path = DISPATCH_PREVIEWS_DIR,
) -> Dict[str, object]:
    preview = load_dispatch_preview(preview_id, preview_dir=preview_dir)
    status = str(preview.get("status") or "").strip().lower()
    if status not in {"previewed", "ready"}:
        raise RuntimeError("Dispatch preview was already used or is no longer valid. Re-run Preview Dispatch.")
    _validate_dispatch_preview_contract(preview)
    _assert_active_staged_batch(preview)

    dependency_paths = preview.get("dependency_fingerprints") or {}
    if not isinstance(dependency_paths, dict):
        raise RuntimeError("Dispatch preview is missing dependency state. Re-run Preview Dispatch.")
    current_fingerprints = {
        key: _path_fingerprint(Path(str(entry.get("path") or "")))
        for key, entry in dependency_paths.items()
        if isinstance(entry, dict)
    }
    changed = _changed_dispatch_fingerprints(
        {key: value for key, value in dependency_paths.items() if isinstance(value, dict)},
        current_fingerprints,
    )
    if changed:
        changed_label = ", ".join(_source_path_label(Path(path)) for path in changed[:4])
        suffix = "..." if len(changed) > 4 else ""
        raise RuntimeError(
            f"Dispatch preview is stale. Re-run Preview Dispatch. Changed inputs: {changed_label}{suffix}"
        )
    expected_dispatch_state = preview.get("lead_dispatch_history_state") or {}
    if isinstance(expected_dispatch_state, dict):
        ledger_db_path = _lead_ledger_db_path(Path(str(preview.get("lead_ledger_db_path") or "")) if str(preview.get("lead_ledger_db_path") or "").strip() else None)
        ledger_conn = connect_lead_ledger(ledger_db_path)
        try:
            current_dispatch_state = dispatch_history_state(ledger_conn)
        finally:
            ledger_conn.close()
        if (
            int(expected_dispatch_state.get("dispatch_event_count") or 0) != int(current_dispatch_state.get("dispatch_event_count") or 0)
            or str(expected_dispatch_state.get("latest_updated_at") or "") != str(current_dispatch_state.get("latest_updated_at") or "")
        ):
            raise RuntimeError("Dispatch preview is stale. Re-run Preview Dispatch. Lead dispatch history changed.")
    return preview


def _confirm_sendgrid_log_paths(preview: Dict[str, object]) -> List[Path]:
    raw_paths = preview.get("sendgrid_log_paths")
    if isinstance(raw_paths, list):
        paths = [Path(str(path)) for path in raw_paths if str(path or "").strip()]
        if paths:
            return paths
    try:
        _jc_path, _sendgrid_paths, _jc_log_path, sendgrid_log_paths = _dispatch_profile_paths()
        if sendgrid_log_paths:
            return list(sendgrid_log_paths)
    except Exception:
        pass
    return list(default_sendgrid_log_paths())


def _confirm_plan_rows_by_queue(
    *,
    plan_rows_by_queue: Dict[str, object],
    queue_headers: Sequence[str],
    sendgrid_sent_emails: set[str],
    allow_sendgrid_already_sent: bool = False,
) -> tuple[Dict[str, List[Dict[str, str]]], Dict[str, int]]:
    filtered: Dict[str, List[Dict[str, str]]] = {}
    removed: Dict[str, int] = {}
    for key in plan_rows_by_queue:
        rows: List[Dict[str, str]] = []
        removed_count = 0
        for row in (plan_rows_by_queue.get(key) or []):
            if not isinstance(row, dict):
                continue
            normalized = {str(header): _strip_cell(row.get(str(header), "")) for header in queue_headers}
            email = norm_email(normalized.get("Email", ""))
            if email and email in sendgrid_sent_emails and not allow_sendgrid_already_sent:
                removed_count += 1
                continue
            rows.append(normalized)
        filtered[key] = rows
        if removed_count:
            removed[key] = removed_count
    return filtered, removed



def assert_dispatch_destination_queues_empty(
    queue_paths: Sequence[Path],
) -> Dict[Path, List[Dict[str, str]]]:
    """Fail closed if a cold-dispatch destination queue still has recipients."""
    existing_rows_by_path: Dict[Path, List[Dict[str, str]]] = {}
    nonempty: List[str] = []

    for path in queue_paths:
        _headers, rows = _read_queue_rows(path)
        existing_rows_by_path[path] = rows
        if rows:
            nonempty.append(f"{path.name}={len(rows)}")

    if nonempty:
        raise RuntimeError(
            "Refusing to confirm dispatch: recipient queues are not empty. "
            "Finish the current recipient queues before confirming a new dispatch. "
            f"Nonempty queues: {', '.join(nonempty)}"
        )

    return existing_rows_by_path


def confirm_dispatch_preview(
    preview_id: str,
    *,
    require_stopped: bool = True,
    allow_high_risk_recontact: bool = False,
    backup_root: Path = BACKUP_ROOT,
    report_dir: Path = STATE_DIR,
    persist_state: bool = True,
    preview_dir: Path = DISPATCH_PREVIEWS_DIR,
    _fault_injector: Callable[[str], None] | None = None,
) -> Dict[str, object]:
    snapshots: Dict[Path, FileSnapshot] = {}
    rollback_dirs: List[Path] = []
    temporary_paths: List[Path] = []
    temporary_dirs: List[Path] = []
    with ExitStack() as lock_stack:
        try:
            return _confirm_dispatch_preview_impl(
                preview_id,
                require_stopped=require_stopped,
                allow_high_risk_recontact=allow_high_risk_recontact,
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=persist_state,
                preview_dir=preview_dir,
                _fault_injector=_fault_injector,
                _lock_stack=lock_stack,
                _snapshots=snapshots,
                _rollback_dirs=rollback_dirs,
                _temporary_paths=temporary_paths,
                _temporary_dirs=temporary_dirs,
            )
        except Exception:
            for directory in reversed(rollback_dirs):
                if directory.exists():
                    shutil.rmtree(directory)
            _restore_file_snapshots(snapshots)
            raise
        finally:
            for path in temporary_paths:
                path.unlink(missing_ok=True)
            for directory in temporary_dirs:
                if directory.exists():
                    shutil.rmtree(directory)


def _confirm_dispatch_preview_impl(
    preview_id: str,
    *,
    require_stopped: bool,
    allow_high_risk_recontact: bool,
    backup_root: Path,
    report_dir: Path,
    persist_state: bool,
    preview_dir: Path,
    _fault_injector: Callable[[str], None] | None,
    _lock_stack: ExitStack,
    _snapshots: Dict[Path, FileSnapshot],
    _rollback_dirs: List[Path],
    _temporary_paths: List[Path],
    _temporary_dirs: List[Path],
) -> Dict[str, object]:
    preview = validate_dispatch_preview(preview_id, preview_dir=preview_dir)
    active_states = _active_sender_states() if require_stopped else {}
    if active_states:
        raise RuntimeError(f"Stop all senders before dispatching leads. Active: {', '.join(sorted(active_states))}")

    queue_paths_map = preview.get("queue_paths") or {}
    if not isinstance(queue_paths_map, dict):
        raise RuntimeError("Dispatch preview is missing queue paths. Re-run Preview Dispatch.")
    queue_keys = _dispatch_queue_keys(preview)
    queue_paths = [Path(str(queue_paths_map.get(key) or "")) for key in queue_keys]
    queue_headers = [str(value or "").strip() for value in (preview.get("queue_headers") or []) if str(value or "").strip()]
    if len(queue_paths) < 2 or not all(str(path).strip() for path in queue_paths):
        raise RuntimeError("Dispatch preview is missing queue files. Re-run Preview Dispatch.")
    if not queue_headers:
        raise RuntimeError("Dispatch preview is missing queue headers. Re-run Preview Dispatch.")
    queue_lock_paths = _confirmation_queue_lock_paths(preview, queue_paths)

    plan_rows_by_queue = preview.get("plan_rows_by_queue") or {}
    if not isinstance(plan_rows_by_queue, dict):
        raise RuntimeError("Dispatch preview is missing planned queue rows. Re-run Preview Dispatch.")
    planned_row_count = sum(
        len(value)
        for value in plan_rows_by_queue.values()
        if isinstance(value, list)
    )
    expected_write_count = int(preview.get("total_rows_would_write") or 0)
    if expected_write_count > 0 and planned_row_count <= 0:
        raise RuntimeError("Dispatch preview has no stored assigned rows. Re-run Preview Dispatch before confirming again.")
    if expected_write_count == 0 and planned_row_count != 0:
        raise RuntimeError("Dispatch preview count mismatch. Re-run Preview Dispatch before confirming again.")
    if expected_write_count == 0 and not isinstance(preview.get("exclusion_reason_counts"), dict):
        raise RuntimeError("Dispatch preview has no stored assigned rows or explicit zero-add reasons. Re-run Preview Dispatch before confirming again.")

    sendgrid_log_paths = _confirm_sendgrid_log_paths(preview)
    raw_authoritative_log_paths = preview.get("authoritative_send_log_paths")
    authoritative_log_paths = (
        [Path(str(path)) for path in raw_authoritative_log_paths if str(path or "").strip()]
        if isinstance(raw_authoritative_log_paths, list)
        else sendgrid_log_paths
    )
    authoritative_sent_emails = _sent_email_set(authoritative_log_paths)
    campaign_type = normalize_campaign_type(preview.get("campaign_type") or CAMPAIGN_TYPE_COLD)
    is_recontact_campaign = is_recontact_cold_campaign(campaign_type)
    allow_previously_sent = is_recontact_campaign
    recontact_recency = preview.get("recontact_recency") if isinstance(preview.get("recontact_recency"), dict) else {}
    effective_plan_rows_by_queue, confirm_filtered_sendgrid_already_sent = _confirm_plan_rows_by_queue(
        plan_rows_by_queue=plan_rows_by_queue,
        queue_headers=queue_headers,
        sendgrid_sent_emails=authoritative_sent_emails,
        allow_sendgrid_already_sent=allow_previously_sent,
    )
    effective_rows_written_per_queue = {
        key: len(effective_plan_rows_by_queue.get(key) or [])
        for key in queue_keys
    }
    confirm_filtered_sendgrid_already_sent_count = sum(confirm_filtered_sendgrid_already_sent.values())
    raw_dispatch_events_by_queue = preview.get("plan_dispatch_events_by_queue")
    if isinstance(raw_dispatch_events_by_queue, dict):
        effective_dispatch_events_by_queue: Dict[str, List[Dict[str, str]]] = {}
        for key in queue_keys:
            events: List[Dict[str, str]] = []
            for event in (raw_dispatch_events_by_queue.get(key) or []):
                if not isinstance(event, dict):
                    continue
                email = norm_email(event.get("email", ""))
                if email and email in authoritative_sent_emails and not allow_previously_sent:
                    continue
                events.append(dict(event))
            effective_dispatch_events_by_queue[key] = events
    else:
        effective_dispatch_events_by_queue = {}
    effective_preview = dict(preview)
    effective_preview["plan_rows_by_queue"] = effective_plan_rows_by_queue
    effective_preview["plan_dispatch_events_by_queue"] = effective_dispatch_events_by_queue
    _validate_recontact_campaign_identity(effective_preview)

    planned_temp_dir = Path(tempfile.mkdtemp(prefix="dispatch_queue_plan_"))
    _temporary_dirs.append(planned_temp_dir)
    planned_queue_paths = [planned_temp_dir / path.name for path in queue_paths]
    for key, path in zip(queue_keys, planned_queue_paths):
        planned_rows = effective_plan_rows_by_queue.get(key) or []
        _write_csv_atomic(path, queue_headers, planned_rows)
    source_path = Path(str(preview.get("dispatch_source_path") or ""))
    cleanup_paths = _staged_batch_paths_for_cleanup(preview)
    checked_path = cleanup_paths.get("cleaned") or MASTER_OUTPUT_PATH
    triaged_keep_path = cleanup_paths.get("triaged_keep") or source_path
    triaged_reject_path = cleanup_paths.get("triaged_reject") or TRIAGED_REJECT_PATH
    planned_safety = build_queue_safety_report(
        shard_paths=planned_queue_paths,
        intended_source_path=source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
        sendgrid_log_paths=sendgrid_log_paths,
        allow_sendgrid_already_sent=allow_previously_sent,
        campaign_type=campaign_type,
    )
    if not bool(planned_safety.get("safe")):
        reasons = ", ".join(str(reason) for reason in (planned_safety.get("unsafe_reasons") or [])) or "unknown unsafe planned state"
        raise RuntimeError(f"Refusing to confirm dispatch: planned queue safety is unsafe ({reasons}).")

    run_id = f"dispatch_run_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    started_at_utc = iso_utc()
    backup_dir = backup_root / f"dispatch_{timestamp_slug()}"
    if backup_dir.exists():
        backup_dir = backup_root / f"{backup_dir.name}_{uuid.uuid4().hex[:8]}"
    _lock_stack.enter_context(lock_files(queue_lock_paths))
    preview = validate_dispatch_preview(preview_id, preview_dir=preview_dir)
    active_states = _active_sender_states() if require_stopped else {}
    if active_states:
        raise RuntimeError(f"Stop all senders before dispatching leads. Active: {', '.join(sorted(active_states))}")
    existing_rows_by_path = assert_dispatch_destination_queues_empty(queue_paths)
    staged_queue_paths: List[Path] = []
    for key, path in zip(queue_keys, queue_paths):
        staged_path = _stage_csv_payload(path, queue_headers, effective_plan_rows_by_queue.get(key) or [])
        staged_queue_paths.append(staged_path)
        _temporary_paths.append(staged_path)
    for path in queue_paths:
        _snapshot_file(path, _snapshots)
    _rollback_dirs.append(backup_dir)
    _copy_queue_backups(queue_paths, backup_dir)
    final_rows_by_path: Dict[Path, List[Dict[str, str]]] = {}
    if _fault_injector:
        _fault_injector("before_first_replacement")
    for position, (key, path, staged_path) in enumerate(
        zip(queue_keys, queue_paths, staged_queue_paths),
        start=1,
    ):
        final_rows_by_path[path] = list(effective_plan_rows_by_queue.get(key) or [])
        staged_path.replace(path)
        settings.secure_private_file(path)
        if _fault_injector:
            _fault_injector(f"queue_replacement_{position}")
    if _fault_injector:
        _fault_injector("after_sixth_replacement" if len(queue_paths) == 6 else "after_all_replacements")

    ledger_path_text = str(effective_preview.get("lead_ledger_db_path") or "").strip()
    ledger_path = _lead_ledger_db_path(Path(ledger_path_text) if ledger_path_text else None)
    for path in (
        ledger_path,
        Path(f"{ledger_path}-journal"),
        Path(f"{ledger_path}-wal"),
        Path(f"{ledger_path}-shm"),
    ):
        _snapshot_file(path, _snapshots)
    dispatch_history_rows_created, dispatch_history_rows_per_queue = _record_dispatch_history_from_preview(
        effective_preview,
        run_id=run_id,
        dispatched_at=started_at_utc,
    )
    if _fault_injector:
        _fault_injector("ledger_recording")

    final_queue_counts = {
        key: len(final_rows_by_path[path])
        for key, path in zip(queue_keys, queue_paths)
    }
    legacy_rows_written = {f"sendgrid_{index}": 0 for index in range(1, 6)}
    for key, path in zip(queue_keys, queue_paths):
        if key == "private_jc":
            continue
        legacy_key = _legacy_sendgrid_queue_key(path)
        if legacy_key:
            legacy_rows_written[legacy_key] = int(effective_rows_written_per_queue.get(key) or 0)

    completed_at_utc = iso_utc()
    added_astra_count = int(effective_rows_written_per_queue.get("private_jc") or 0)
    added_sendgrid_count = sum(
        int(value or 0)
        for key, value in effective_rows_written_per_queue.items()
        if key.startswith("sendgrid_")
    )
    exclusion_reason_counts = dict(preview.get("exclusion_reason_counts") or {})
    if confirm_filtered_sendgrid_already_sent_count:
        exclusion_reason_counts["already_sent"] = int(exclusion_reason_counts.get("already_sent") or 0) + confirm_filtered_sendgrid_already_sent_count
    report = {
        "run_id": run_id,
        "status": "completed",
        "started_at_utc": started_at_utc,
        "started_at": started_at_utc,
        "completed_at_utc": completed_at_utc,
        "completed_at": completed_at_utc,
        "generated_at_utc": completed_at_utc,
        "preview_id": preview_id,
        "campaign_id": str(preview.get("campaign_id") or ""),
        "preview_path": str(preview.get("preview_path") or _dispatch_preview_path(preview_id, preview_dir)),
        "campaign_type": campaign_type,
        "allow_previously_sent": allow_previously_sent,
        "allow_previously_contacted": allow_previously_sent,
        "recontact_recency": dict(recontact_recency),
        "recontact_recency_override": False,
        "recontact_planned_unique": int(recontact_recency.get("planned_unique") or preview.get("recontact_planned_unique") or 0),
        "recontact_found_in_active_history": int(recontact_recency.get("found_in_active_history") or preview.get("recontact_found_in_active_history") or 0),
        "recontact_seen_this_month": int(recontact_recency.get("seen_this_month") or preview.get("recontact_seen_this_month") or 0),
        "recontact_not_found_in_active_history": int(recontact_recency.get("not_found_in_active_history") or preview.get("recontact_not_found_in_active_history") or 0),
        "recontact_recency_risk_level": str(recontact_recency.get("risk_level") or preview.get("recontact_recency_risk_level") or ""),
        "master_label": str(preview.get("master_label") or ""),
        "rejected_label": str(preview.get("rejected_label") or ""),
        "backup_dir": str(backup_dir),
        "master_read": int(preview.get("dispatch_source_row_count") or 0),
        "dispatch_source_mode": str(preview.get("dispatch_source_mode") or DISPATCH_SOURCE_TRIAGED_KEEP),
        "dispatch_source_name": str(preview.get("dispatch_source_name") or ""),
        "dispatch_source_path": str(preview.get("dispatch_source_path") or ""),
        "dispatch_source_row_count": int(preview.get("dispatch_source_row_count") or 0),
        "dispatch_eligible_row_count": int(preview.get("dispatch_eligible_row_count") or 0),
        "dispatch_selected_row_count": int(preview.get("dispatch_selected_row_count") or 0),
        "dispatch_cap": str(preview.get("dispatch_cap") or DISPATCH_CAP_ALL),
        "dispatch_cap_label": str(preview.get("dispatch_cap_label") or _dispatch_cap_label(DISPATCH_CAP_ALL)),
        "dispatch_block_reason": "",
        "verification_required": bool(preview.get("verification_required")),
        "verification_file_mtime": str(preview.get("verification_file_mtime") or ""),
        "added_astra": added_astra_count,
        "skipped_astra_already_sent": int(preview.get("skipped_astra_already_sent") or 0),
        "skipped_astra_already_queued": int(preview.get("skipped_astra_already_queued") or 0),
        "added_sendgrid": added_sendgrid_count,
        "skipped_sendgrid_already_sent": int(preview.get("skipped_sendgrid_already_sent") or 0) + confirm_filtered_sendgrid_already_sent_count,
        "skipped_sendgrid_already_queued": int(preview.get("skipped_sendgrid_already_queued") or 0),
        "confirm_filtered_sendgrid_already_sent": confirm_filtered_sendgrid_already_sent_count,
        "confirm_filtered_sendgrid_already_sent_by_queue": dict(confirm_filtered_sendgrid_already_sent),
        "skipped_already_sent": int(preview.get("skipped_already_sent") or 0) + confirm_filtered_sendgrid_already_sent_count,
        "skipped_already_sent_same_family": int(preview.get("skipped_already_sent_same_family") or 0) + confirm_filtered_sendgrid_already_sent_count,
        "already_sent_other_family_allowed": int(preview.get("already_sent_other_family_allowed") or 0),
        "skipped_already_queued": int(preview.get("skipped_already_queued") or 0),
        "suppressed_skipped": int(preview.get("suppressed_skipped") or 0),
        "skipped_suppressed": int(preview.get("skipped_suppressed") or 0),
        "invalid_malformed_skipped": int(preview.get("invalid_malformed_skipped") or 0),
        "skipped_invalid_malformed": int(preview.get("skipped_invalid_malformed") or 0),
        "skipped_bad_sendgrid_event": int(preview.get("skipped_bad_sendgrid_event") or 0),
        "bad_sendgrid_event_skipped": int(preview.get("bad_sendgrid_event_skipped") or 0),
        "bad_suppressed_removed_count": int(preview.get("bad_suppressed_removed_count") or 0),
        "duplicate_master_skipped": int(preview.get("duplicate_master_skipped") or 0),
        "input_rows": int(preview.get("input_rows") or preview.get("dispatch_eligible_row_count") or 0),
        "rows_with_booktitle": int(preview.get("rows_with_booktitle") or 0),
        "rows_missing_booktitle": int(preview.get("rows_missing_booktitle") or 0),
        "rows_with_author_name": int(preview.get("rows_with_author_name") or 0),
        "rows_missing_author_name": int(preview.get("rows_missing_author_name") or 0),
        "previously_sent_allowed_count": int(preview.get("previously_sent_allowed_count") or 0),
        "already_contacted_allowed_count": int(preview.get("already_contacted_allowed_count") or 0),
        "assigned_sg1": legacy_rows_written["sendgrid_1"],
        "assigned_sg2": legacy_rows_written["sendgrid_2"],
        "assigned_sg3": legacy_rows_written["sendgrid_3"],
        "assigned_sg4": legacy_rows_written["sendgrid_4"],
        "assigned_sg5": legacy_rows_written["sendgrid_5"],
        "sendgrid_profile_order": list(preview.get("sendgrid_profile_order") or []),
        "sendgrid_profile_labels": dict(preview.get("sendgrid_profile_labels") or {}),
        "sendgrid_profile_planned_counts": {
            key: int(effective_rows_written_per_queue.get(key) or 0)
            for key in queue_keys
            if key.startswith("sendgrid_")
        },
        "skipped_both": int(preview.get("skipped_both") or 0),
        "rows_written_per_queue": dict(effective_rows_written_per_queue),
        "queue_paths": dict(preview.get("queue_paths") or {}),
        "final_queue_counts": final_queue_counts,
        "queue_headers": queue_headers,
        "outcome_counts": dict(preview.get("outcome_counts") or {}),
        "exclusion_reason_counts": exclusion_reason_counts,
        "assigned_preview_rows": list(preview.get("assigned_preview_rows") or []),
        "assigned_preview_archive_path": str(preview.get("assigned_preview_archive_path") or ""),
        "dispatch_source_preview_rows": list(preview.get("dispatch_source_preview_rows") or []),
        "total_rows_would_write": added_astra_count + added_sendgrid_count,
        "skipped_already_contacted": int(preview.get("skipped_already_contacted") or 0),
        "already_contacted_evidence": list(preview.get("already_contacted_evidence") or []),
        "skipped_invalid_source_row": int(preview.get("skipped_invalid_source_row") or 0),
        "dispatch_history_rows_created": int(dispatch_history_rows_created or 0),
        "dispatch_history_rows_per_queue": dict(dispatch_history_rows_per_queue),
    }
    report.update(_dispatch_alias_fields(report))
    staged_paths = _staged_batch_paths_for_cleanup(preview)
    for path in staged_paths.values():
        _snapshot_file(path, _snapshots)
    staged_archive_root = backup_root / "staged_batches"
    if not staged_archive_root.exists():
        _rollback_dirs.append(staged_archive_root)
    staged_archive_dir = _staged_batch_archive_dir(backup_root, run_id)
    _rollback_dirs.append(staged_archive_dir)
    staged_batch_cleanup = _archive_and_clear_staged_batch(
        preview=preview,
        report=report,
        backup_root=backup_root,
        archive_dir=staged_archive_dir,
    )
    report["staged_batch_cleanup"] = staged_batch_cleanup
    report["staged_batch_archive_path"] = str(staged_batch_cleanup.get("archive_path") or "")
    archived_by_key = {
        str(item.get("key") or ""): Path(str(item.get("archive_path") or ""))
        for item in staged_batch_cleanup.get("files", [])
        if isinstance(item, dict) and str(item.get("archive_path") or "").strip()
    }
    manifest_checked_path = archived_by_key.get("cleaned") or cleanup_paths.get("cleaned") or MASTER_OUTPUT_PATH
    manifest_keep_path = archived_by_key.get("triaged_keep") or cleanup_paths.get("triaged_keep") or Path(str(preview.get("dispatch_source_path") or ""))
    manifest_reject_path = archived_by_key.get("triaged_reject") or cleanup_paths.get("triaged_reject") or TRIAGED_REJECT_PATH
    manifest_source_path = manifest_keep_path if _normalize_dispatch_source_mode(preview.get("dispatch_source_mode")) == DISPATCH_SOURCE_TRIAGED_KEEP else Path(str(preview.get("dispatch_source_path") or manifest_checked_path))
    active_manifest_target = active_campaign_manifest_path(report_dir)
    _snapshot_file(active_manifest_target, _snapshots)
    active_manifest_path = write_active_campaign_manifest(
        checked_path=manifest_checked_path,
        triaged_keep_path=manifest_keep_path,
        triaged_reject_path=manifest_reject_path,
        intended_source_path=manifest_source_path,
        state_dir=report_dir,
        extra={
            "source": "confirm_dispatch",
            "run_id": run_id,
            "preview_id": preview_id,
            "campaign_id": str(preview.get("campaign_id") or ""),
        },
    )
    report["active_campaign_manifest_path"] = str(active_manifest_path)
    if int(report.get("total_rows_would_write") or 0) == 0:
        report["message"] = _zero_add_dispatch_message(report)
    else:
        report["message"] = (
            "Dispatch confirmed. Staged batch archived and cleared. Run Check Leads and Fast Triage before previewing another batch."
            if bool(staged_batch_cleanup.get("cleared"))
            else "Dispatch confirmed."
        )
    if not str(report.get("assigned_preview_archive_path") or "").strip():
        assigned_preview_archive_path = _unique_dispatch_archive_path(report_dir / "dispatch_previews", "dispatch_preview")
        _snapshot_file(assigned_preview_archive_path, _snapshots)
        assigned_preview_archive_path = _archive_assigned_dispatch_preview(
            preview,
            report_dir / "dispatch_previews",
            archive_path=assigned_preview_archive_path,
        )
        report["assigned_preview_archive_path"] = str(assigned_preview_archive_path)
    report["private_jc_added"] = int(report.get("added_astra") or 0)
    report["sendgrid_added"] = int(report.get("added_sendgrid") or 0)
    report["sg1_added"] = int(report.get("assigned_sg1") or 0)
    report["sg2_added"] = int(report.get("assigned_sg2") or 0)
    report["sg3_added"] = int(report.get("assigned_sg3") or 0)
    report["sg4_added"] = int(report.get("assigned_sg4") or 0)
    report["sg5_added"] = int(report.get("assigned_sg5") or 0)
    confirmed_summary_path = _unique_dispatch_archive_path(report_dir / "dispatch_confirmed", "dispatch_confirmed")
    _snapshot_file(confirmed_summary_path, _snapshots)
    confirmed_summary_path = _archive_confirmed_dispatch_summary(
        report,
        report_dir / "dispatch_confirmed",
        archive_path=confirmed_summary_path,
    )
    report["confirmed_summary_path"] = str(confirmed_summary_path)
    report["confirmed_summary_archive_path"] = str(confirmed_summary_path)

    report_path = report_dir / f"important_leads_dispatch_{timestamp_slug()}.json"
    _snapshot_file(report_path, _snapshots)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = dict(report)
    report_payload["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    history_path = report_dir / DISPATCH_RUN_HISTORY_PATH.name
    _snapshot_file(history_path, _snapshots)
    _append_dispatch_run_history(report, history_path=history_path)
    if _fault_injector:
        _fault_injector("campaign_history_recording")
    if persist_state:
        _snapshot_file(settings.LEADS_STATE_PATH, _snapshots)
        save_state(**{MASTER_DISPATCH_STATE_KEY: report})

    preview_path = _dispatch_preview_path(preview_id, preview_dir)
    _snapshot_file(preview_path, _snapshots)
    preview["status"] = "confirmed"
    preview["confirmed_at_utc"] = report["completed_at_utc"]
    preview["confirmed_run_id"] = run_id
    _save_dispatch_preview(preview, preview_dir)
    if _fault_injector:
        _fault_injector("final_confirmation_state")
    return report


def check_master_leads(
    input_path: Path = MASTER_INPUT_PATH,
    output_path: Path = MASTER_OUTPUT_PATH,
    rejected_path: Path = MASTER_REJECTED_PATH,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    report_dir: Path = STATE_DIR,
    summary_dir: Path = CHECK_RUNS_DIR,
    validate_deliverability: bool | None = None,
    reject_role_accounts: bool | None = None,
    reject_disposable: bool | None = None,
    disposable_domains_path: Path = DISPOSABLE_DOMAINS_PATH,
    persist_state: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Dict[str, object]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    document = _read_csv_document(input_path)
    fieldnames = list(document["fieldnames"])
    rows = list(document["rows"])
    blank_rows = int(document.get("blank_rows", 0) or 0)
    total_input_rows = len(rows) + blank_rows
    core_headers = _detect_core_headers(fieldnames)
    if not core_headers["Email"]:
        raise ImportantLeadsCheckError(
            "NO_EMAIL_HEADER",
            f"Could not detect an email column in {input_path.name}",
            details={"fieldnames": fieldnames},
        )

    output_headers, source_to_output = _master_output_headers(fieldnames, core_headers)
    blocked_emails, suppression_summary = _blocked_email_set(
        sendgrid_suppressions_path=sendgrid_suppressions_path,
        suppressed_path=suppressed_path,
        unsubscribed_path=unsubscribed_path,
    )
    deliverability_enabled = (
        _should_validate_deliverability() if validate_deliverability is None else bool(validate_deliverability) and _dns_support_available()
    )
    role_filter_enabled = _should_reject_role_accounts() if reject_role_accounts is None else bool(reject_role_accounts)
    disposable_filter_enabled = _should_reject_disposable() if reject_disposable is None else bool(reject_disposable)
    disposable_domains = _disposable_domain_set(disposable_domains_path) if disposable_filter_enabled else set()

    kept_rows: List[Dict[str, str]] = []
    rejected_rows: List[Dict[str, str]] = []
    kept_index_by_email: Dict[str, int] = {}
    reason_counts: Counter[str] = Counter()
    corrected_rows = 0

    rejected_headers = list(output_headers) + list(AUDIT_OUTPUT_HEADERS) + ["reject_code", "reject_reason"]

    for _ in range(blank_rows):
        blank_row = {header: "" for header in output_headers}
        rejected_rows.append(
            _rejected_row(
                blank_row,
                reject_code="BLANK_ROW",
                reject_reason=_reject_reason_text("BLANK_ROW"),
            )
        )
        reason_counts["BLANK_ROW"] += 1

    for row_index, raw_row in enumerate(rows, start=1):
        if progress_callback:
            try:
                progress_callback(min(total_input_rows, blank_rows + row_index), total_input_rows)
            except Exception:
                pass
        normalized_row = {header: "" for header in output_headers}
        for source, target in source_to_output.items():
            normalized_row[target] = _strip_cell(raw_row.get(source, ""))
        for source in fieldnames:
            canonical = AUTHOR_OUTREACH_HEADER_BY_KEY.get(_normalize_header_key(source))
            if canonical and canonical in normalized_row:
                normalized_row[canonical] = _strip_cell(raw_row.get(source, ""))
        normalized_row["FullName"] = _full_identity_value(raw_row, core_headers)
        first_name_source = _first_name_source(raw_row, normalized_row, core_headers)
        first_name_hygiene = _first_name_hygiene(first_name_source)
        normalized_row["FirstName"] = first_name_hygiene["first_name_clean"]
        normalized_row["first_name_clean"] = first_name_hygiene["first_name_clean"]
        normalized_row["first_name_status"] = first_name_hygiene["first_name_status"]
        normalized_row["personalization_allowed"] = first_name_hygiene["personalization_allowed"]
        normalized_row["cleanup_notes"] = first_name_hygiene["cleanup_notes"]
        normalized_row["last_name_clean"] = _last_name_clean(raw_row.get(core_headers["LastName"], "")) if core_headers["LastName"] else ""
        if core_headers["FirstName"]:
            first_raw = _strip_cell(raw_row.get(core_headers["FirstName"], ""))
            if first_raw and not normalized_row["FullName"]:
                normalized_row["FullName"] = first_raw

        email_raw = _strip_cell(raw_row.get(core_headers["Email"], "")) if core_headers.get("Email") else ""
        if not email_raw and core_headers.get("AuthorEmail"):
            email_raw = _strip_cell(raw_row.get(core_headers["AuthorEmail"], ""))
        validation = _email_validation_result(
            email_raw,
            check_deliverability=deliverability_enabled,
        )
        normalized_email = validation["normalized_email"]
        correction_applied = validation["correction_applied"]
        correction_reason = validation["correction_reason"]
        reject_code = validation["reject_code"]
        reject_reason = validation["reject_reason"]

        if correction_applied:
            corrected_rows += 1

        if not reject_code and normalized_email:
            normalized_row["Email"] = normalized_email
            email_domain = normalized_email.split("@", 1)[1] if "@" in normalized_email else ""
            if role_filter_enabled and is_role_recipient(normalized_email, ROLE_ACCOUNT_BLOCKLIST):
                reject_code = "ROLE_ACCOUNT"
                reject_reason = _reject_reason_text("ROLE_ACCOUNT")
            elif disposable_filter_enabled and email_domain in disposable_domains:
                reject_code = "DISPOSABLE_DOMAIN"
                reject_reason = _reject_reason_text("DISPOSABLE_DOMAIN")
            elif normalized_email in blocked_emails:
                reject_code = "SUPPRESSED"
                reject_reason = _reject_reason_text("SUPPRESSED")
        elif not reject_code:
            reject_code = "MISSING_EMAIL"
            reject_reason = _reject_reason_text("MISSING_EMAIL")

        if reject_code:
            reason_counts[reject_code] += 1
            rejected_rows.append(
                _rejected_row(
                    normalized_row,
                    reject_code=reject_code,
                    reject_reason=reject_reason,
                    normalized_email=normalized_email,
                    correction_applied=correction_applied,
                    correction_reason=correction_reason,
                )
            )
            continue

        existing_index = kept_index_by_email.get(normalized_email)
        if existing_index is not None:
            reason_counts["DUPLICATE_IN_BATCH"] += 1
            existing_row = kept_rows[existing_index]
            if _row_richness(normalized_row) > _row_richness(existing_row):
                rejected_rows.append(
                    _rejected_row(
                        existing_row,
                        reject_code="DUPLICATE_IN_BATCH",
                        reject_reason=_reject_reason_text(
                            "DUPLICATE_IN_BATCH",
                            "Duplicate normalized email within this batch; replaced by richer row.",
                        ),
                        normalized_email=normalized_email,
                    )
                )
                kept_rows[existing_index] = normalized_row
            else:
                rejected_rows.append(
                    _rejected_row(
                        normalized_row,
                        reject_code="DUPLICATE_IN_BATCH",
                        reject_reason=_reject_reason_text("DUPLICATE_IN_BATCH"),
                        normalized_email=normalized_email,
                        correction_applied=correction_applied,
                        correction_reason=correction_reason,
                    )
                )
            continue

        kept_index_by_email[normalized_email] = len(kept_rows)
        kept_rows.append(normalized_row)

    _write_csv_atomic(output_path, output_headers, kept_rows)
    _write_csv_atomic(rejected_path, rejected_headers, rejected_rows)

    if progress_callback:
        try:
            progress_callback(total_input_rows, total_input_rows)
        except Exception:
            pass
    duplicates_removed = int(reason_counts.get("DUPLICATE_IN_BATCH", 0))
    invalid_syntax_removed = int(reason_counts.get("INVALID_EMAIL_SYNTAX", 0)) + int(reason_counts.get("MISSING_EMAIL", 0))
    undeliverable_removed = int(reason_counts.get("UNDELIVERABLE_DOMAIN", 0))
    suppressed_removed = int(reason_counts.get("SUPPRESSED", 0))
    role_accounts_removed = int(reason_counts.get("ROLE_ACCOUNT", 0))
    disposable_removed = int(reason_counts.get("DISPOSABLE_DOMAIN", 0))
    suspicious_flagged = int(reason_counts.get("UNKNOWN_DOMAIN_TYPO", 0)) + int(reason_counts.get("MULTIPLE_EMAILS_IN_CELL", 0))

    summary = {
        "generated_at_utc": iso_utc(),
        "input_label": _display_path_label(input_path),
        "output_label": _display_path_label(output_path),
        "rejected_label": _display_path_label(rejected_path),
        "total_input_rows": total_input_rows,
        "valid_rows": len(kept_rows),
        "rejected_rows": len(rejected_rows),
        "corrected_rows": corrected_rows,
        "duplicates_removed": duplicates_removed,
        "suppressed_removed": suppressed_removed,
        "role_accounts_removed": role_accounts_removed,
        "disposable_removed": disposable_removed,
        "invalid_syntax_removed": invalid_syntax_removed,
        "undeliverable_removed": undeliverable_removed,
        "blank_rows": blank_rows,
        "deliverability_enabled": deliverability_enabled,
        "role_account_filter_enabled": role_filter_enabled,
        "disposable_filter_enabled": disposable_filter_enabled,
        "reason_counts": dict(reason_counts),
    }
    summary_path = summary_dir / f"check_summary_{timestamp_slug()}.json"
    write_json_atomic(summary_path, summary)

    report = {
        "input_label": _display_path_label(input_path),
        "output_label": _display_path_label(output_path),
        "rejected_label": _display_path_label(rejected_path),
        "generated_at_utc": iso_utc(),
        "input_rows": total_input_rows,
        "total_input_rows": total_input_rows,
        "cleaned_rows": len(kept_rows),
        "valid_rows": len(kept_rows),
        "rejected_rows": len(rejected_rows),
        "duplicates_removed": duplicates_removed,
        "invalid_removed": invalid_syntax_removed,
        "invalid_syntax_removed": invalid_syntax_removed,
        "undeliverable_removed": undeliverable_removed,
        "suppressed_removed": suppressed_removed,
        "role_accounts_removed": role_accounts_removed,
        "disposable_removed": disposable_removed,
        "suspicious_flagged": suspicious_flagged,
        "safe_fixes_applied": corrected_rows,
        "corrected_rows": corrected_rows,
        "blank_rows": blank_rows,
        "output_fieldnames": output_headers,
        "output_preview_rows": _preview_rows(kept_rows, output_headers, CHECK_PREVIEW_ROWS),
        "rejected_preview_rows": _preview_rows(rejected_rows, rejected_headers, CHECK_PREVIEW_ROWS),
        "reason_counts": dict(reason_counts),
        "suppression_summary": suppression_summary,
        "deliverability_enabled": deliverability_enabled,
        "role_account_filter_enabled": role_filter_enabled,
        "disposable_filter_enabled": disposable_filter_enabled,
        "summary_path": str(summary_path),
        "summary_label": _display_path_label(summary_path),
    }

    report_path = report_dir / f"important_leads_check_{timestamp_slug()}.json"
    report_payload = dict(report)
    report_payload["report_path"] = str(report_path)
    write_json_atomic(report_path, report_payload)
    report["report_path"] = str(report_path)
    if persist_state:
        save_state(**{MASTER_CHECK_STATE_KEY: report})
    return report


def _dispatch_profile_paths() -> tuple[Path, List[Path], Path, List[Path]]:
    jc_path = settings.shard_path(str(PROFILES["private_jc"]["csv"]))
    enabled_sendgrid_profiles = _enabled_sendgrid_dispatch_profiles()
    registered_sendgrid_profiles = _registered_sendgrid_profiles()
    shard_paths = [settings.shard_path(str(PROFILES[name]["csv"])) for name in enabled_sendgrid_profiles]
    jc_log_path = settings.log_path(str(PROFILES["private_jc"]["log"]))
    sendgrid_log_paths = [settings.log_path(str(PROFILES[name]["log"])) for name in registered_sendgrid_profiles]
    sendgrid_domain_logs = [
        settings.log_path(str(cfg.get("domain_log")))
        for name, cfg in PROFILES.items()
        if str(cfg.get("provider") or "") == "sendgrid" and str(cfg.get("domain_log") or "").strip()
    ]
    for path in sendgrid_domain_logs:
        if path not in sendgrid_log_paths:
            sendgrid_log_paths.append(path)
    return jc_path, shard_paths, jc_log_path, sendgrid_log_paths


def _dispatch_history_evidence_for_lead(conn, lead_id: str, email: str) -> dict[str, str]:
    try:
        placeholders = ",".join("?" for _ in AUTHORITATIVE_CONTACT_HISTORY_STATUSES)
        row = conn.execute(
            f"""
            SELECT run_id, dispatch_source, profile, queue_target, dispatched_at, result_status, result_reason, updated_at
            FROM lead_dispatch_history
            WHERE lead_id = ?
              AND LOWER(REPLACE(REPLACE(COALESCE(result_status, ''), '-', '_'), ' ', '_')) IN ({placeholders})
            ORDER BY dispatched_at DESC, updated_at DESC
            LIMIT 1
            """,
            [str(lead_id or "").strip(), *sorted(AUTHORITATIVE_CONTACT_HISTORY_STATUSES)],
        ).fetchone()
    except Exception:
        row = None
    if row is None:
        return {
            "matched_email": email,
            "normalized_matched_email": email,
            "contact_ledger_source_file": str(_lead_ledger_db_path()),
            "matching_rule": "exact_normalized_email",
        }
    return {
        "matched_email": email,
        "normalized_matched_email": email,
        "contact_ledger_source_file": str(_lead_ledger_db_path()),
        "sent_at": str(row["dispatched_at"] or ""),
        "contacted_at": str(row["dispatched_at"] or row["updated_at"] or ""),
        "channel": str(row["queue_target"] or row["profile"] or ""),
        "campaign": str(row["run_id"] or row["dispatch_source"] or ""),
        "subject": "",
        "matching_rule": "exact_normalized_email",
        "result_status": str(row["result_status"] or ""),
        "result_reason": str(row["result_reason"] or ""),
    }


def _read_queue_rows(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(name or "").lstrip("\ufeff").strip() for name in (reader.fieldnames or [])]
        rows: List[Dict[str, str]] = []
        for row in reader:
            cleaned = {field: _strip_cell(row.get(field, "")) for field in fieldnames}
            email = norm_email(cleaned.get("Email", ""))
            if not email:
                continue
            cleaned["Email"] = email
            if "FirstName" not in cleaned and "AuthorName" in cleaned:
                cleaned["FirstName"] = _strip_cell(cleaned.get("AuthorName", ""))
            if "FirstName" in cleaned:
                cleaned["FirstName"] = _strip_cell(cleaned.get("FirstName", ""))
            rows.append(cleaned)
    return fieldnames, rows


def _sent_email_set(log_paths: Sequence[Path]) -> set[str]:
    sent: set[str] = set()
    authoritative_paths, _ignored_paths = _authoritative_history_paths(log_paths)
    for path in authoritative_paths:
        if not path.exists():
            continue
        try:
            with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
                for row in csv.DictReader(handle):
                    if not _log_row_is_authoritative_sent(row):
                        continue
                    email = norm_email(row.get("Email") or row.get("email") or "")
                    if email:
                        sent.add(email)
        except Exception:
            sent |= load_already_done(path)
    return sent


def _queue_output_headers(existing_headers: Iterable[Sequence[str]], master_headers: Sequence[str]) -> List[str]:
    output = ["Email", "FirstName"]
    seen = set(output)

    def maybe_add(value: str) -> None:
        key = value
        if not key or key in seen or key == "Email":
            return
        seen.add(key)
        output.append(key)

    for header in master_headers:
        if header == "Email":
            continue
        if header == "FirstName":
            continue
        maybe_add(header)

    for headers in existing_headers:
        for header in headers:
            maybe_add(str(header or "").strip())

    for header in REQUIRED_DISPATCH_FIELDS:
        maybe_add(str(header or "").strip())

    for header in SENDGRID_REQUIRED_HEADERS:
        maybe_add(str(header or "").strip())

    return output


def _master_row_to_queue_row(row: Dict[str, str], queue_headers: Sequence[str]) -> Dict[str, str]:
    queue_row = {header: "" for header in queue_headers}
    queue_row["Email"] = norm_email(row.get("Email", ""))
    personalization_allowed = str(row.get("personalization_allowed", "")).strip().lower()
    if personalization_allowed in {"true", "1", "yes"}:
        queue_row["FirstName"] = _trimmed_first_name(row.get("first_name_clean", "") or row.get("FirstName", ""))
    elif "personalization_allowed" in row:
        queue_row["FirstName"] = ""
    else:
        queue_row["FirstName"] = _trimmed_first_name(
            row.get("FirstName", "") or row.get("FullName", "") or row.get("AuthorName", "")
        )
    for header in queue_headers:
        if header in {"Email", "FirstName"}:
            continue
        queue_row[header] = _strip_cell(row.get(header, ""))
    return queue_row


def _existing_queue_email_set(queue_rows_by_path: Dict[Path, List[Dict[str, str]]]) -> set[str]:
    out: set[str] = set()
    for rows in queue_rows_by_path.values():
        for row in rows:
            email = norm_email(row.get("Email", ""))
            if email:
                out.add(email)
    return out


def _active_sender_states() -> Dict[str, str]:
    active = runtime_control.list_active_sender_snapshots(tail_lines=12)
    return {str(item.name): str(item.runtime_state) for item in active}


def _copy_queue_backups(paths: Sequence[Path], backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)


def dispatch_master_leads(
    master_path: Path = MASTER_OUTPUT_PATH,
    rejected_path: Path = MASTER_REJECTED_PATH,
    verified_path: Path = STRICT_VERIFIED_PATH,
    triaged_keep_path: Path = TRIAGED_KEEP_PATH,
    dispatch_source_mode: str = DISPATCH_SOURCE_TRIAGED_KEEP,
    require_stopped: bool = True,
    jc_queue_path: Path | None = None,
    sendgrid_queue_paths: Sequence[Path] | None = None,
    jc_log_path: Path | None = None,
    sendgrid_log_paths: Sequence[Path] | None = None,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    lead_ledger_db_path: Path | None = None,
    sendgrid_events_path: Path = settings.WEBHOOK_EVENTS_PATH,
    campaign_type: str = CAMPAIGN_TYPE_COLD,
    dispatch_cap: str = DISPATCH_CAP_ALL,
    backup_root: Path = BACKUP_ROOT,
    report_dir: Path = STATE_DIR,
    persist_state: bool = True,
    progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> Dict[str, object]:
    preview = preview_dispatch_master_leads(
        master_path=master_path,
        rejected_path=rejected_path,
        verified_path=verified_path,
        triaged_keep_path=triaged_keep_path,
        dispatch_source_mode=dispatch_source_mode,
        dispatch_cap=dispatch_cap,
        jc_queue_path=jc_queue_path,
        sendgrid_queue_paths=sendgrid_queue_paths,
        jc_log_path=jc_log_path,
        sendgrid_log_paths=sendgrid_log_paths,
        sendgrid_suppressions_path=sendgrid_suppressions_path,
        suppressed_path=suppressed_path,
        unsubscribed_path=unsubscribed_path,
        lead_ledger_db_path=lead_ledger_db_path,
        sendgrid_events_path=sendgrid_events_path,
        campaign_type=campaign_type,
        preview_dir=report_dir / "_dispatch_previews_legacy",
    )
    total_rows = int(preview.get("dispatch_selected_row_count") or 0)
    if progress_callback:
        try:
            progress_callback(
                {
                    "processed_rows": total_rows,
                    "total_rows": total_rows,
                    "assigned_rows": int(preview.get("added_astra") or 0) + int(preview.get("added_sendgrid") or 0),
                    "skipped_rows": (
                        int(preview.get("suppressed_skipped") or 0)
                        + int(preview.get("duplicate_master_skipped") or 0)
                        + int(preview.get("skipped_both") or 0)
                        + int(preview.get("invalid_malformed_skipped") or 0)
                    ),
                }
            )
        except Exception:
            pass
    return confirm_dispatch_preview(
        str(preview.get("preview_id") or ""),
        require_stopped=require_stopped,
        backup_root=backup_root,
        report_dir=report_dir,
        persist_state=persist_state,
        preview_dir=report_dir / "_dispatch_previews_legacy",
    )


def important_leads_status() -> Dict[str, object]:
    state = load_state()
    path_state = important_leads_path_state()
    verify_path_state = important_leads_verify_path_state()
    triage_path_state = important_leads_triage_path_state()
    dispatch_state = important_leads_dispatch_source_state()
    jc_path, sendgrid_paths, _, _ = _dispatch_profile_paths()
    jc_headers, jc_rows = _read_queue_rows(jc_path)
    sendgrid_status = []
    for profile_name, path in zip(_enabled_sendgrid_dispatch_profiles(), sendgrid_paths):
        _, rows = _read_queue_rows(path)
        sendgrid_status.append(
            {
                "name": _sendgrid_profile_label(profile_name),
                "profile": profile_name,
                "path": str(path),
                "count": len(rows),
            }
        )

    cleaned_source_path = _workspace_path_from_label(path_state["output_path"], MASTER_OUTPUT_PATH)
    verified_source_path = _workspace_path_from_label(
        verify_path_state["verified_path"],
        STRICT_VERIFIED_PATH,
    )
    triaged_keep_source_path = _workspace_path_from_label(
        triage_path_state["keep_path"],
        TRIAGED_KEEP_PATH,
    )
    source_state = _dispatch_source_snapshot(
        source_mode=dispatch_state["dispatch_source_mode"],
        cleaned_path=cleaned_source_path,
        triaged_keep_path=triaged_keep_source_path,
        strict_verified_path=verified_source_path,
    )
    source_options = {
        DISPATCH_SOURCE_TRIAGED_KEEP: _dispatch_source_snapshot(
            source_mode=DISPATCH_SOURCE_TRIAGED_KEEP,
            cleaned_path=cleaned_source_path,
            triaged_keep_path=triaged_keep_source_path,
            strict_verified_path=verified_source_path,
        ),
        DISPATCH_SOURCE_STRICT_VERIFIED: _dispatch_source_snapshot(
            source_mode=DISPATCH_SOURCE_STRICT_VERIFIED,
            cleaned_path=cleaned_source_path,
            triaged_keep_path=triaged_keep_source_path,
            strict_verified_path=verified_source_path,
        ),
        DISPATCH_SOURCE_CLEANED: _dispatch_source_snapshot(
            source_mode=DISPATCH_SOURCE_CLEANED,
            cleaned_path=cleaned_source_path,
            triaged_keep_path=triaged_keep_source_path,
            strict_verified_path=verified_source_path,
        ),
    }

    return {
        "check_paste_policy": {
            "mode": "small_manual_only",
            "paste_warning_rows": _int_env("IMPORTANT_LEADS_PASTE_WARNING_ROWS", 250),
            "paste_max_rows": _int_env("IMPORTANT_LEADS_PASTE_MAX_ROWS", 1000),
            "upload_required_rows": _int_env("IMPORTANT_LEADS_PASTE_MAX_ROWS", 1000),
            "upload_recommended_rows": _int_env("IMPORTANT_LEADS_PASTE_WARNING_ROWS", 250),
        },
        "important_input_label": path_state["input_path"],
        "important_output_label": path_state["output_path"],
        "important_rejected_label": path_state["rejected_path"],
        "dispatch_source_mode": source_state["dispatch_source_mode"],
        "dispatch_source_path": source_state["dispatch_source_label"],
        "dispatch_source_exists": source_state["dispatch_source_exists"],
        "dispatch_source_row_count": source_state["dispatch_source_row_count"],
        "dispatch_eligible_row_count": source_state["dispatch_eligible_row_count"],
        "dispatch_block_reason": source_state["dispatch_block_reason"],
        "verification_required": source_state["verification_required"],
        "verification_file_mtime": source_state["verification_file_mtime"],
        "dispatch_source_preview_rows": source_state["dispatch_source_preview_rows"],
        "dispatch_source": source_state,
        "dispatch_source_options": source_options,
        "latest_master_check": state.get(MASTER_CHECK_STATE_KEY, {}),
        "latest_dispatch": state.get(MASTER_DISPATCH_STATE_KEY, {}),
        "jc_queue": {
            "path": str(jc_path),
            "count": len(jc_rows),
            "fieldnames": jc_headers,
        },
        "sendgrid_queues": sendgrid_status,
    }
