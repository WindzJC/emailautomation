from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from email_validator import EmailNotValidError, EmailSyntaxError, EmailUndeliverableError, validate_email

import settings
from lead_ledger import connect_lead_ledger, deterministic_lead_id, load_lead_by_id, record_transition, source_row_hash, upsert_lead, update_stage_status
from leads_workflow import iso_utc, load_state, save_state, timestamp_slug, write_json_atomic
from sendgrid_hygiene import norm_email
from send_shard import ROLE_LOCALPART_BLOCKLIST, is_role_recipient


IMPORTANT_DIR = settings.APP_ROOT / "_important"
DEFAULT_INPUT_PATH = IMPORTANT_DIR / "leads.csv"
DEFAULT_VERIFIED_PATH = IMPORTANT_DIR / "leads_verified.csv"
DEFAULT_REJECTED_PATH = IMPORTANT_DIR / "leads_verify_rejected.csv"
DEFAULT_QUARANTINE_PATH = IMPORTANT_DIR / "leads_quarantine.csv"
DEFAULT_TRIAGE_KEEP_PATH = IMPORTANT_DIR / "leads_triaged_keep.csv"
DEFAULT_TRIAGE_REJECTED_PATH = IMPORTANT_DIR / "leads_triaged_reject.csv"
DEFAULT_TRIAGE_QUARANTINE_PATH = IMPORTANT_DIR / "leads_triaged_quarantine.csv"

VERIFY_STATE_PATH = settings.STATE_DIR / "important_leads_verify_state.json"
TRIAGE_STATE_PATH = settings.STATE_DIR / "important_leads_triage_state.json"
VERIFY_STATE_KEY = "latest_lead_verify"
TRIAGE_STATE_KEY = "latest_lead_triage"
VERIFY_PATHS_STATE_KEY = "important_leads_verify_paths"
TRIAGE_PATHS_STATE_KEY = "important_leads_triage_paths"
VERIFY_CHECKPOINT_ROWS = max(1, int(os.environ.get("IMPORTANT_LEADS_VERIFY_CHECKPOINT_ROWS", "100") or 100))
FAST_TRIAGE_CHECKPOINT_ROWS = max(1, int(os.environ.get("IMPORTANT_LEADS_FAST_TRIAGE_CHECKPOINT_ROWS", "5000") or 5000))
FAST_TRIAGE_CANCEL_POLL_ROWS = max(1, int(os.environ.get("IMPORTANT_LEADS_FAST_TRIAGE_CANCEL_POLL_ROWS", "1000") or 1000))
VERIFY_DEFAULT_MAX_WORKERS = max(1, int(os.environ.get("IMPORTANT_LEADS_VERIFY_MAX_WORKERS", "12") or 12))
VERIFY_HTTP_RETRIES = max(0, int(os.environ.get("IMPORTANT_LEADS_VERIFY_HTTP_RETRIES", "1") or 1))
VERIFY_CACHE_MAX_ITEMS = max(0, int(os.environ.get("IMPORTANT_LEADS_VERIFY_CACHE_MAX_ITEMS", "5000") or 5000))
VERIFY_HTTP_CONNECT_TIMEOUT_SECONDS = max(0.2, float(os.environ.get("IMPORTANT_LEADS_VERIFY_CONNECT_TIMEOUT_SECONDS", "1.5") or 1.5))
VERIFY_HTTP_READ_TIMEOUT_SECONDS = max(0.5, float(os.environ.get("IMPORTANT_LEADS_VERIFY_READ_TIMEOUT_SECONDS", "3.0") or 3.0))
VERIFY_CANCEL_POLL_SECONDS = max(0.1, float(os.environ.get("IMPORTANT_LEADS_VERIFY_CANCEL_POLL_SECONDS", "0.5") or 0.5))
VERIFY_AUDIT_HEADERS = ("Status", "VerificationReason", "VerificationEvidence", "VerifiedAtUtc")

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
TRIAGE_MODE_FAST = "FAST_TRIAGE"
TRIAGE_MODE_STRICT = "STRICT_PUBLIC_PROOF"
TRIAGE_ROLE_BLOCKLIST = set(ROLE_LOCALPART_BLOCKLIST) | {"admin", "contact", "hello", "info", "sales", "support"}
TRIAGE_JUNK_NAME_TOKENS = {
    "admin",
    "asdf",
    "author",
    "book",
    "books",
    "by",
    "contact",
    "customer",
    "dr",
    "dummy",
    "fake",
    "firstname",
    "hello",
    "info",
    "junk",
    "lastname",
    "na",
    "none",
    "null",
    "sample",
    "spam",
    "test",
    "testing",
    "unknown",
    "user",
}
TRIAGE_WEAK_FIRST_NAME_TOKENS = TRIAGE_JUNK_NAME_TOKENS | {
    "about",
    "account",
    "author",
    "business",
    "company",
    "editor",
    "enquiry",
    "guest",
    "inquiry",
    "marketing",
    "media",
    "newsletter",
    "office",
    "press",
    "service",
    "team",
    "the",
    "webmaster",
}
TRIAGE_BAD_DOMAINS = {"example.com", "example.org", "example.net", "test.com", "invalid.com", "localhost"}
TRIAGE_BAD_LOCAL_MARKERS = {
    "bad",
    "blacklist",
    "block",
    "blocked",
    "bounce",
    "bounced",
    "complaint",
    "dead",
    "deceased",
    "defer",
    "deferred",
    "disposable",
    "do_not_contact",
    "donotcontact",
    "dnc",
    "dropped",
    "duplicate",
    "hard_bounce",
    "hardbounce",
    "invalid",
    "opt_out",
    "optout",
    "reject",
    "rejected",
    "spam",
    "spamreport",
    "suppressed",
    "suppression",
    "undeliverable",
    "unsubscribe",
    "unsubscribed",
}
TRIAGE_BAD_LOCAL_HEADER_MARKERS = {
    "bounce",
    "complaint",
    "dead",
    "do_not_contact",
    "dnc",
    "duplicate",
    "invalid",
    "suppression",
    "suppressed",
    "undeliverable",
    "unsubscribe",
}
TRIAGE_DISPOSABLE_DOMAINS_PATH = settings.APP_ROOT / "data" / "reference" / "disposable_domains.txt"
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
BOOK_TITLE_HEADER_CANDIDATES = (
    "booktitle",
    "book_title",
    "title",
)


def _normalize(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").strip().split()).lower()


def _normalize_header_key(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum())


def _pick_header(fieldnames: Sequence[str], candidates: Sequence[str]) -> str:
    normalized = {_normalize_header_key(name): name for name in fieldnames if name}
    for candidate in candidates:
        match = normalized.get(_normalize_header_key(candidate))
        if match:
            return match
    return ""


def _strip_cell(value: object) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _display_path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(settings.APP_ROOT.resolve()))
    except Exception:
        return str(path)


def _canonical_workspace_label(path: Path) -> str:
    try:
        return str(path.relative_to(settings.APP_ROOT))
    except Exception:
        return str(path)


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Important verify input not found: {path}")
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(name or "").lstrip("\ufeff").strip() for name in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned = {field: str(row.get(field, "") or "") for field in fieldnames}
            if any(str(value or "").strip() for value in cleaned.values()):
                rows.append(cleaned)
    return fieldnames, rows


def _row_signature(row: dict[str, str], fieldnames: Sequence[str]) -> str:
    payload = {field: _normalize(row.get(field, "")) for field in fieldnames}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _csv_atomic_write(path: Path, headers: Sequence[str], rows: Iterable[dict[str, str]]) -> None:
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
        writer = csv.DictWriter(handle, fieldnames=list(headers))
        writer.writeheader()
        writer.writerows(list(rows))
    tmp_path.replace(path)
    settings.secure_private_file(path)


def _load_checkpoint_state() -> dict[str, object]:
    if not VERIFY_STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(VERIFY_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_triage_checkpoint_state() -> dict[str, object]:
    if not TRIAGE_STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(TRIAGE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_checkpoint_state(payload: dict[str, object]) -> None:
    write_json_atomic(VERIFY_STATE_PATH, payload)


def _save_triage_checkpoint_state(payload: dict[str, object]) -> None:
    write_json_atomic(TRIAGE_STATE_PATH, payload)


def _verify_path_state_labels(
    input_path: Path,
    verified_path: Path,
    rejected_path: Path,
    quarantine_path: Path,
) -> dict[str, str]:
    return {
        "input_path": _display_path_label(input_path),
        "verified_path": _display_path_label(verified_path),
        "rejected_path": _display_path_label(rejected_path),
        "quarantine_path": _display_path_label(quarantine_path),
    }


def _triage_path_state_labels(
    input_path: Path,
    keep_path: Path,
    rejected_path: Path,
    quarantine_path: Path,
) -> dict[str, str]:
    return {
        "input_path": _display_path_label(input_path),
        "keep_path": _display_path_label(keep_path),
        "rejected_path": _display_path_label(rejected_path),
        "quarantine_path": _display_path_label(quarantine_path),
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


def important_leads_verify_path_state() -> dict[str, str]:
    state = load_state()
    raw = state.get(VERIFY_PATHS_STATE_KEY, {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        "input_path": _saved_path_label_or_default(raw.get("input_path"), DEFAULT_INPUT_PATH),
        "verified_path": _saved_path_label_or_default(raw.get("verified_path"), DEFAULT_VERIFIED_PATH),
        "rejected_path": _saved_path_label_or_default(raw.get("rejected_path"), DEFAULT_REJECTED_PATH),
        "quarantine_path": _saved_path_label_or_default(raw.get("quarantine_path"), DEFAULT_QUARANTINE_PATH),
    }


def important_leads_triage_path_state() -> dict[str, str]:
    state = load_state()
    raw = state.get(TRIAGE_PATHS_STATE_KEY, {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        "input_path": _saved_path_label_or_default(raw.get("input_path"), DEFAULT_INPUT_PATH),
        "keep_path": _saved_path_label_or_default(raw.get("keep_path"), DEFAULT_TRIAGE_KEEP_PATH),
        "rejected_path": _saved_path_label_or_default(raw.get("rejected_path"), DEFAULT_TRIAGE_REJECTED_PATH),
        "quarantine_path": _saved_path_label_or_default(raw.get("quarantine_path"), DEFAULT_TRIAGE_QUARANTINE_PATH),
    }


def important_leads_verify_status() -> dict[str, object]:
    state = load_state()
    checkpoint = _load_checkpoint_state()
    triage_checkpoint = _load_triage_checkpoint_state()
    paths = important_leads_verify_path_state()
    triage_paths = important_leads_triage_path_state()
    latest_verify = state.get(VERIFY_STATE_KEY, {})
    if not isinstance(latest_verify, dict):
        latest_verify = {}
    latest_triage = state.get(TRIAGE_STATE_KEY, {})
    if not isinstance(latest_triage, dict):
        latest_triage = {}
    return {
        "important_verify_input_label": paths["input_path"],
        "important_verify_keep_label": paths["verified_path"],
        "important_verify_rejected_label": paths["rejected_path"],
        "important_verify_quarantine_label": paths["quarantine_path"],
        "important_triage_input_label": triage_paths["input_path"],
        "important_triage_keep_label": triage_paths["keep_path"],
        "important_triage_rejected_label": triage_paths["rejected_path"],
        "important_triage_quarantine_label": triage_paths["quarantine_path"],
        "latest_lead_verify": latest_verify,
        "latest_lead_triage": latest_triage,
        "verify_checkpoint": {
            "path": str(VERIFY_STATE_PATH),
            "exists": VERIFY_STATE_PATH.exists(),
            "input_fingerprint": str(checkpoint.get("input_fingerprint") or ""),
            "next_row_index": int(checkpoint.get("next_row_index") or 0),
            "total_input_rows": int(checkpoint.get("total_input_rows") or 0),
            "completed": bool(checkpoint.get("completed")),
            "resume_supported": True,
            "updated_at_utc": str(checkpoint.get("updated_at_utc") or ""),
        },
        "triage_checkpoint": {
            "path": str(TRIAGE_STATE_PATH),
            "exists": TRIAGE_STATE_PATH.exists(),
            "input_fingerprint": str(triage_checkpoint.get("input_fingerprint") or ""),
            "next_row_index": int(triage_checkpoint.get("next_row_index") or 0),
            "total_input_rows": int(triage_checkpoint.get("total_input_rows") or 0),
            "completed": bool(triage_checkpoint.get("completed")),
            "resume_supported": True,
            "updated_at_utc": str(triage_checkpoint.get("updated_at_utc") or ""),
        },
    }


def _normalize_row_value(row: dict[str, str], field: str) -> str:
    return _strip_cell(row.get(field, ""))


def _full_name_value(row: dict[str, str], fieldnames: Sequence[str]) -> str:
    full_header = _pick_header(fieldnames, FULL_NAME_HEADER_CANDIDATES)
    first_header = _pick_header(fieldnames, FIRST_NAME_HEADER_CANDIDATES)
    last_header = _pick_header(fieldnames, LAST_NAME_HEADER_CANDIDATES)

    if full_header and _normalize_row_value(row, full_header):
        return _normalize_row_value(row, full_header)
    if first_header and last_header:
        first = _normalize_row_value(row, first_header)
        last = _normalize_row_value(row, last_header)
        if first and last:
            return f"{first} {last}".strip()
    if first_header and _normalize_row_value(row, first_header):
        return _normalize_row_value(row, first_header)
    return ""


def _first_name_value(row: dict[str, str], fieldnames: Sequence[str], full_name: str) -> str:
    first_header = _pick_header(fieldnames, FIRST_NAME_HEADER_CANDIDATES)
    if first_header and _normalize_row_value(row, first_header):
        return _normalize_row_value(row, first_header).split()[0]
    if full_name:
        return full_name.split()[0]
    return ""


def _book_title_value(row: dict[str, str], fieldnames: Sequence[str]) -> str:
    book_header = _pick_header(fieldnames, BOOK_TITLE_HEADER_CANDIDATES)
    return _normalize_row_value(row, book_header) if book_header else ""


def _email_value(row: dict[str, str], fieldnames: Sequence[str]) -> str:
    email_header = _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES)
    if email_header:
        return _strip_cell(row.get(email_header, ""))
    return ""


def _load_triage_disposable_domains(path: Path = TRIAGE_DISPOSABLE_DOMAINS_PATH) -> set[str]:
    if not path.exists():
        return set()
    domains: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip().lower()
        if line and not line.startswith("#"):
            domains.add(line)
    return domains


def _triage_name_tokens(name: str) -> list[str]:
    return [token for token in re.findall(r"[a-z]+", _normalize(name)) if token]


def _is_junk_name(name: str) -> bool:
    normalized = _normalize(name)
    if not normalized:
        return False
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if compact in TRIAGE_JUNK_NAME_TOKENS:
        return True
    if len(set(compact)) <= 2 and len(compact) >= 4:
        return True
    tokens = set(_triage_name_tokens(name))
    return bool(tokens and tokens.issubset(TRIAGE_JUNK_NAME_TOKENS))


def _has_usable_full_name(name: str) -> bool:
    tokens = _triage_name_tokens(name)
    if len(tokens) < 2:
        return False
    if any(token in TRIAGE_JUNK_NAME_TOKENS for token in tokens):
        return False
    if tokens[0] in TRIAGE_WEAK_FIRST_NAME_TOKENS:
        return False
    return all(len(token) >= 2 for token in tokens[:2])


def _fast_triage_identity_rejection(row: dict[str, str], fieldnames: Sequence[str]) -> tuple[str, str] | None:
    full_header = _pick_header(fieldnames, FULL_NAME_HEADER_CANDIDATES)
    first_header = _pick_header(fieldnames, FIRST_NAME_HEADER_CANDIDATES)
    full_name = _full_name_value(row, fieldnames)
    first_name = _first_name_value(row, fieldnames, full_name)
    full_tokens = _triage_name_tokens(full_name)
    first_tokens = _triage_name_tokens(first_name)
    first_token = first_tokens[0] if first_tokens else (full_tokens[0] if full_tokens else "")

    if not full_header and len(full_tokens) < 2:
        return "MISSING_FULL_NAME", "No FullName or first/last name pair was available for fast triage."
    if full_header and not _normalize_row_value(row, full_header):
        return "MISSING_FULL_NAME", "FullName is missing."
    if not full_name.strip():
        return "MISSING_USABLE_PERSON_NAME", "No usable person name was available for fast triage."
    if first_token in TRIAGE_WEAK_FIRST_NAME_TOKENS:
        return "WEAK_FIRST_NAME", f"FirstName `{first_name or first_token}` is generic or not a usable person name."
    if first_header and _normalize_row_value(row, first_header):
        explicit_first = _triage_name_tokens(_normalize_row_value(row, first_header))
        if explicit_first and explicit_first[0] in TRIAGE_WEAK_FIRST_NAME_TOKENS:
            return "WEAK_FIRST_NAME", f"FirstName `{_normalize_row_value(row, first_header)}` is generic or not a usable person name."
    if _is_junk_name(full_name):
        return "JUNK_NAME", "Name looks like a test, junk, or placeholder value."
    if len(full_tokens) < 2:
        return "WEAK_FULL_NAME", "FullName has fewer than two real name tokens."
    if not _has_usable_full_name(full_name):
        return "MISSING_USABLE_PERSON_NAME", "FullName does not contain a strong usable person identity."
    return None


def _is_bad_domain(domain: str) -> bool:
    normalized = str(domain or "").strip().lower().rstrip(".")
    if not normalized or normalized in TRIAGE_BAD_DOMAINS:
        return True
    if "." not in normalized or "_" in normalized or ".." in normalized:
        return True
    labels = normalized.split(".")
    if any(not label or label.startswith("-") or label.endswith("-") for label in labels):
        return True
    if len(labels[-1]) < 2 or not labels[-1].isalpha():
        return True
    return False


def _row_has_bad_local_indicator(row: dict[str, str], fieldnames: Sequence[str]) -> tuple[bool, str]:
    for field in fieldnames:
        header = _normalize_header_key(field)
        value = _normalize(row.get(field, ""))
        if not value:
            continue
        compact_value = re.sub(r"[^a-z0-9]+", "", value)
        value_tokens = set(re.findall(r"[a-z0-9]+", value))
        header_has_bad_marker = any(marker in header for marker in TRIAGE_BAD_LOCAL_HEADER_MARKERS)
        value_has_bad_marker = (
            compact_value in TRIAGE_BAD_LOCAL_MARKERS
            or bool(value_tokens & TRIAGE_BAD_LOCAL_MARKERS)
            or any(marker in compact_value for marker in TRIAGE_BAD_LOCAL_MARKERS if len(marker) >= 7)
        )
        if value_has_bad_marker:
            return True, f"Local row marker `{field}`={_strip_cell(row.get(field, ''))} indicates bounce/suppression risk."
        if header_has_bad_marker and value not in {"0", "false", "n", "no", "none", "ok", "valid"}:
            return True, f"Local row field `{field}` indicates bounce/suppression risk."
    return False, ""


def _classify_fast_triage_row(
    row: dict[str, str],
    fieldnames: Sequence[str],
    *,
    disposable_domains: set[str] | None = None,
) -> tuple[str, str, str]:
    email_raw = _email_value(row, fieldnames)
    if not email_raw.strip():
        return "REJECT", "MISSING_EMAIL", "Row is missing an email address."

    try:
        validated = validate_email(email_raw, check_deliverability=False)
        email = norm_email(validated.normalized)
    except EmailSyntaxError:
        return "REJECT", "INVALID_EMAIL_SYNTAX", "Email failed syntax validation."
    except EmailNotValidError:
        return "REJECT", "INVALID_EMAIL_SYNTAX", "Email failed validation."

    local_part, domain = email.split("@", 1) if "@" in email else ("", "")
    if not local_part or _is_bad_domain(domain):
        return "REJECT", "BAD_DOMAIN", "Email domain is malformed or clearly unsafe."

    disposable_domain_set = disposable_domains or set()
    if domain in disposable_domain_set:
        return "REJECT", "DISPOSABLE_DOMAIN", "Disposable email domain rejected."

    has_bad_local_indicator, bad_local_evidence = _row_has_bad_local_indicator(row, fieldnames)
    if has_bad_local_indicator:
        return "REJECT", "LOCAL_BOUNCE_RISK", bad_local_evidence

    if is_role_recipient(email, TRIAGE_ROLE_BLOCKLIST):
        return "REJECT", "ROLE_ACCOUNT", "Role-based inbox rejected by fast triage."

    identity_rejection = _fast_triage_identity_rejection(row, fieldnames)
    if identity_rejection:
        reason, evidence = identity_rejection
        return "REJECT", reason, evidence

    return "KEEP", "FAST_TRIAGE_LOCAL_CONFIDENCE", "Valid full name, valid email syntax, and normal-looking domain."


def _verify_worker_count(max_workers: int | None) -> int:
    if max_workers is None:
        return VERIFY_DEFAULT_MAX_WORKERS
    try:
        return max(1, int(max_workers))
    except Exception:
        return VERIFY_DEFAULT_MAX_WORKERS


def _classification_cache_key(row: dict[str, str], fieldnames: Sequence[str]) -> tuple[str, str, str, str]:
    full_name_raw = _full_name_value(row, fieldnames)
    first_name_raw = _first_name_value(row, fieldnames, full_name_raw)
    full_name = _normalize(full_name_raw)
    first_name = _normalize(first_name_raw)
    email = norm_email(_email_value(row, fieldnames))
    book_title = _normalize(_book_title_value(row, fieldnames))
    return full_name, first_name, email, book_title


class _VerifyNetworkClient:
    def __init__(self, timeout_seconds: int, max_workers: int) -> None:
        connect_timeout = min(max(0.2, float(timeout_seconds or 1)), VERIFY_HTTP_CONNECT_TIMEOUT_SECONDS)
        read_timeout = min(max(0.5, float(timeout_seconds or 1)), VERIFY_HTTP_READ_TIMEOUT_SECONDS)
        pool_size = max(16, int(max_workers or 1) * 4)
        self.client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (compatible; EmailAutomationVerify/1.0)"},
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=read_timeout,
                pool=connect_timeout,
            ),
            limits=httpx.Limits(
                max_connections=pool_size,
                max_keepalive_connections=max(8, int(max_workers or 1) * 2),
                keepalive_expiry=30.0,
            ),
            follow_redirects=True,
        )
        self.search_cache: dict[str, list[object]] = {}
        self.fetch_cache: dict[str, object] = {}
        self.lock = threading.Lock()

    def close(self) -> None:
        self.client.close()

    def _cache_get(self, cache: dict[str, object], key: str) -> object | None:
        if VERIFY_CACHE_MAX_ITEMS <= 0:
            return None
        with self.lock:
            return cache.get(key)

    def _cache_set(self, cache: dict[str, object], key: str, value: object) -> None:
        if VERIFY_CACHE_MAX_ITEMS <= 0:
            return
        with self.lock:
            if len(cache) < VERIFY_CACHE_MAX_ITEMS:
                cache[key] = value

    def search(self, query: str) -> list[object]:
        query_key = str(query or "").strip()
        cached = self._cache_get(self.search_cache, query_key)
        if isinstance(cached, list):
            return cached
        response: httpx.Response | None = None
        for _attempt in range(VERIFY_HTTP_RETRIES + 1):
            try:
                response = self.client.get("https://duckduckgo.com/html/", params={"q": query})
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
            except Exception:
                response = None
        if response is None:
            results: list[object] = []
            self._cache_set(self.search_cache, query_key, results)
            return results
        if not response.ok:
            results = []
            self._cache_set(self.search_cache, query_key, results)
            return results

        results = []
        for raw_href in re.findall(r'href="([^"]+)"', response.text):
            href = raw_href.strip()
            if not href:
                continue
            url = href
            if "uddg=" in href:
                try:
                    parsed = urlparse(href)
                    query_params = parse_qs(parsed.query)
                    url = unquote(query_params.get("uddg", [""])[0])
                except Exception:
                    url = ""
            if url.startswith("http"):
                results.append({"url": url})
            if len(results) >= 5:
                break
        self._cache_set(self.search_cache, query_key, results)
        return results

    def fetch(self, url: str) -> object:
        url_key = str(url or "").strip()
        cached = self._cache_get(self.fetch_cache, url_key)
        if cached is not None:
            return cached
        response: httpx.Response | None = None
        last_error = ""
        for _attempt in range(VERIFY_HTTP_RETRIES + 1):
            try:
                response = self.client.get(url)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
            except Exception as exc:
                last_error = str(exc)
                response = None
        if response is None:
            payload: object = {"url": url, "error": last_error, "text": ""}
            self._cache_set(self.fetch_cache, url_key, payload)
            return payload
        payload = {
            "url": url,
            "final_url": str(response.url or url),
            "status_code": int(response.status_code),
            "text": response.text or "",
        }
        self._cache_set(self.fetch_cache, url_key, payload)
        return payload


def _build_evidence_queries(full_name: str, first_name: str, email: str, book_title: str) -> list[str]:
    del book_title
    queries: list[str] = []
    if email:
        queries.append(f"\"{email}\"")
    if full_name and email:
        queries.append(f"\"{full_name}\" \"{email}\"")
    elif full_name:
        queries.append(f"\"{full_name}\"")
    if first_name and email:
        queries.append(f"\"{first_name}\" \"{email}\"")
    return [query for query in dict.fromkeys(queries) if query.strip()]


def _coerce_search_url(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("url", "href", "link", "final_url"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
    return ""


def _coerce_fetch_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("html_text", "text", "body", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _default_searcher_factory(timeout_seconds: int) -> Callable[[str], list[object]]:
    network = _VerifyNetworkClient(timeout_seconds, VERIFY_DEFAULT_MAX_WORKERS)

    def searcher(query: str) -> list[object]:
        return network.search(query)

    return searcher


def _default_fetcher_factory(timeout_seconds: int) -> Callable[[str], object]:
    network = _VerifyNetworkClient(timeout_seconds, VERIFY_DEFAULT_MAX_WORKERS)

    def fetcher(url: str) -> object:
        return network.fetch(url)

    return fetcher


def _evidence_snapshot(
    *,
    searcher: Callable[[str], object],
    fetcher: Callable[[str], object],
    queries: Sequence[str],
    max_pages_per_lead: int,
    timeout_seconds: int,
    retries: int,
) -> tuple[str, set[str]]:
    collected: list[str] = []
    seen_urls: list[str] = []
    for query in queries:
        try:
            search_results = searcher(query)
        except Exception:
            continue
        urls = [_coerce_search_url(item) for item in (search_results or [])]
        for url in urls:
            if not url or url in seen_urls:
                continue
            seen_urls.append(url)
            payload: object = ""
            for _attempt in range(max(0, retries) + 1):
                try:
                    payload = fetcher(url)
                except TypeError:
                    payload = fetcher(url, timeout_seconds=timeout_seconds)  # type: ignore[misc]
                except Exception:
                    payload = ""
                if _coerce_fetch_text(payload).strip():
                    break
            text = _coerce_fetch_text(payload)
            if text:
                collected.append(text)
            if len(collected) >= max_pages_per_lead:
                break
        if len(collected) >= max_pages_per_lead:
            break
    return "\n".join(collected), set(EMAIL_RE.findall("\n".join(collected)))


def _assess_evidence(
    *,
    evidence_text: str,
    evidence_emails: set[str],
    full_name: str,
    first_name: str,
    email: str,
    allow_social_proof: bool,
) -> tuple[str, str, str, bool] | None:
    normalized_evidence = _normalize(evidence_text)
    full_name_norm = _normalize(full_name)
    first_name_norm = _normalize(first_name)
    email_norm = _normalize(email)
    normalized_evidence_emails = {norm_email(found) for found in evidence_emails if found}
    full_name_present = bool(full_name_norm and full_name_norm in normalized_evidence)
    first_name_present = bool(first_name_norm and first_name_norm in normalized_evidence)
    email_present = bool(email_norm and email_norm in normalized_evidence)
    other_email_present = any(found != email_norm for found in normalized_evidence_emails if found)

    if other_email_present and not email_present:
        return "REJECT", "PROOF_MISMATCH", "Public evidence showed a different email address.", True
    if email_present and full_name_present:
        if allow_social_proof:
            return "KEEP", "FULL_NAME_AND_EMAIL_MATCH", "Public evidence contained the full name and email.", True
        return "QUARANTINE", "PROOF_POLICY_BLOCKED", "Proof policy blocked the match.", True
    if email_present and not full_name_present:
        if first_name_present and not allow_social_proof:
            return "QUARANTINE", "FIRST_NAME_ONLY", "First name proof is too weak.", False
        return "QUARANTINE", "INSUFFICIENT_PROOF", "Email was visible, but the full name was not proven.", False
    if full_name_present and not email_present:
        return "QUARANTINE", "INSUFFICIENT_PROOF", "Full name was visible, but the email was not proven.", False
    if first_name_present:
        return "QUARANTINE", "FIRST_NAME_ONLY", "First name proof is too weak.", False
    if normalized_evidence_emails:
        return "REJECT", "PROOF_MISMATCH", "Public evidence showed a different email address.", True
    return None


def _classify_row(
    row: dict[str, str],
    fieldnames: Sequence[str],
    *,
    searcher: Callable[[str], object],
    fetcher: Callable[[str], object],
    max_pages_per_lead: int,
    timeout_seconds: int,
    retries: int,
    allow_social_proof: bool,
    validate_deliverability: bool,
) -> tuple[str, str, str]:
    email_raw = _email_value(row, fieldnames)
    if not email_raw.strip():
        return "REJECT", "MISSING_EMAIL", "Row is missing an email address."

    try:
        validated = validate_email(email_raw, check_deliverability=validate_deliverability)
        email = norm_email(validated.normalized)
    except EmailSyntaxError:
        return "REJECT", "INVALID_EMAIL_SYNTAX", "Email failed syntax validation."
    except EmailUndeliverableError:
        return "REJECT", "UNDELIVERABLE_DOMAIN", "Email domain could not be delivered."
    except EmailNotValidError:
        return "REJECT", "INVALID_EMAIL_SYNTAX", "Email failed validation."

    full_name = _full_name_value(row, fieldnames)
    first_name = _first_name_value(row, fieldnames, full_name)
    book_title = _book_title_value(row, fieldnames)
    queries = _build_evidence_queries(full_name, first_name, email, book_title)
    if not queries:
        return "QUARANTINE", "INSUFFICIENT_PROOF", "No useful public-proof query could be built."

    best_weak_result: tuple[str, str, str] | None = None
    for query in queries:
        evidence_text, evidence_emails = _evidence_snapshot(
            searcher=searcher,
            fetcher=fetcher,
            queries=[query],
            max_pages_per_lead=max(1, max_pages_per_lead),
            timeout_seconds=max(1, timeout_seconds),
            retries=max(0, retries),
        )
        assessed = _assess_evidence(
            evidence_text=evidence_text,
            evidence_emails=evidence_emails,
            full_name=full_name,
            first_name=first_name,
            email=email,
            allow_social_proof=allow_social_proof,
        )
        if not assessed:
            continue
        status, reason, evidence, decisive = assessed
        if decisive:
            return status, reason, evidence
        if best_weak_result is None:
            best_weak_result = status, reason, evidence
    if best_weak_result is not None:
        return best_weak_result
    return "QUARANTINE", "NO_PUBLIC_PROOF", "No public proof was found."


def _load_output_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(name or "").lstrip("\ufeff").strip() for name in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned = {field: str(row.get(field, "") or "") for field in fieldnames}
            if any(str(value or "").strip() for value in cleaned.values()):
                rows.append(cleaned)
    return fieldnames, rows


def _output_headers(input_headers: Sequence[str]) -> list[str]:
    headers = [header for header in input_headers if header not in VERIFY_AUDIT_HEADERS]
    for audit_header in VERIFY_AUDIT_HEADERS:
        if audit_header not in headers:
            headers.append(audit_header)
    return headers


def _build_output_row(
    row: dict[str, str],
    input_headers: Sequence[str],
    *,
    status: str,
    reason: str,
    evidence: str,
) -> dict[str, str]:
    output = {header: _strip_cell(row.get(header, "")) for header in input_headers}
    output["Status"] = status
    output["VerificationReason"] = reason
    output["VerificationEvidence"] = evidence[:1000]
    output["VerifiedAtUtc"] = iso_utc()
    return output


def _derive_preview(rows: Sequence[dict[str, str]], limit: int = 8) -> list[dict[str, str]]:
    preview: list[dict[str, str]] = []
    for row in rows[:limit]:
        preview.append(dict(row))
    return preview


def _hash_input_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lead_ledger_db_path() -> Path:
    configured = Path(getattr(settings, "LEAD_LEDGER_DB_PATH", settings.STATE_DIR / "lead_ledger.sqlite3"))
    state_dir = Path(getattr(settings, "STATE_DIR", configured.parent))
    return state_dir / configured.name


def _normalized_selected_lead_ids(selected_lead_ids: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in selected_lead_ids or ():
        lead_id = str(value or "").strip()
        if not lead_id or lead_id in seen:
            continue
        seen.add(lead_id)
        normalized.append(lead_id)
    return normalized


def _selected_lead_ids_fingerprint(selected_lead_ids: Sequence[str] | None) -> str:
    normalized = _normalized_selected_lead_ids(selected_lead_ids)
    if not normalized:
        return ""
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _filter_rows_for_selected_lead_ids(
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str],
    *,
    selected_lead_ids: Sequence[str] | None,
) -> list[dict[str, str]]:
    selected = set(_normalized_selected_lead_ids(selected_lead_ids))
    if not selected:
        return list(rows)
    filtered: list[dict[str, str]] = []
    for row in rows:
        email = norm_email(_email_value(row, fieldnames))
        if not email:
            continue
        try:
            lead_id = deterministic_lead_id(email)
        except ValueError:
            continue
        if lead_id in selected:
            filtered.append(row)
    return filtered


def _lead_score(status: str) -> float:
    normalized = str(status or "").strip().upper()
    if normalized == "KEEP":
        return 100.0
    if normalized == "QUARANTINE":
        return 50.0
    if normalized == "REJECT":
        return 0.0
    return 0.0


def _ledger_event_type(stage: str) -> str:
    return "fast_triage_stage_updated" if stage == TRIAGE_MODE_FAST else "strict_public_proof_stage_updated"


def _sync_row_to_lead_ledger(
    conn,
    row: dict[str, str],
    fieldnames: Sequence[str],
    *,
    input_path: Path,
    stage: str,
    status: str,
    reason: str,
    processed_at: str,
    commit: bool = True,
) -> None:
    email = norm_email(_email_value(row, fieldnames))
    if not email:
        return
    try:
        lead_id = deterministic_lead_id(email)
    except ValueError:
        return

    full_name = _full_name_value(row, fieldnames)
    first_name = _first_name_value(row, fieldnames, full_name)
    source_file = _canonical_workspace_label(input_path)
    source_payload = {header: _strip_cell(row.get(header, "")) for header in fieldnames if header not in VERIFY_AUDIT_HEADERS}
    existing = load_lead_by_id(conn, lead_id)
    current_stage = stage if existing is None else str(existing.get("current_stage") or "")
    current_status = status if existing is None else str(existing.get("current_status") or "")

    upsert_lead(
        conn,
        lead_id=lead_id,
        email=email,
        full_name=full_name,
        first_name=first_name,
        source_file=source_file,
        source_row_hash=source_row_hash(source_payload),
        first_seen_at=processed_at,
        last_seen_at=processed_at,
        current_stage=current_stage,
        current_status=current_status,
        score=_lead_score(status),
        reason_codes=[reason] if reason else [],
        updated_at=processed_at,
        created_at=processed_at,
        commit=commit,
    )

    if existing is None:
        if commit:
            with conn:
                record_transition(
                    conn,
                    lead_id=lead_id,
                    event_type="lead_observed",
                    stage_before="",
                    stage_after=stage,
                    status_before="",
                    status_after=status,
                    reason_code=reason,
                    note=f"Observed via {_display_path_label(input_path)}",
                    created_at=processed_at,
                )
        else:
            record_transition(
                conn,
                lead_id=lead_id,
                event_type="lead_observed",
                stage_before="",
                stage_after=stage,
                status_before="",
                status_after=status,
                reason_code=reason,
                note=f"Observed via {_display_path_label(input_path)}",
                created_at=processed_at,
            )
        return

    update_stage_status(
        conn,
        lead_id,
        stage_after=stage,
        status_after=status,
        reason_code=reason,
        note=f"Processed via {_display_path_label(input_path)}",
        event_type=_ledger_event_type(stage),
        updated_at=processed_at,
        commit=commit,
    )


def fast_triage_master_leads(
    input_path: Path = DEFAULT_INPUT_PATH,
    keep_path: Path = DEFAULT_TRIAGE_KEEP_PATH,
    rejected_path: Path = DEFAULT_TRIAGE_REJECTED_PATH,
    quarantine_path: Path = DEFAULT_TRIAGE_QUARANTINE_PATH,
    *,
    persist_state: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    disposable_domains: set[str] | None = None,
) -> dict[str, object]:
    input_path = Path(input_path)
    keep_path = Path(keep_path)
    rejected_path = Path(rejected_path)
    quarantine_path = Path(quarantine_path)
    input_headers, input_rows = _load_csv_rows(input_path)
    if not input_headers:
        raise ValueError(f"Fast triage input is empty: {input_path}")

    base_headers = [header for header in input_headers if header not in VERIFY_AUDIT_HEADERS]
    if not base_headers:
        raise ValueError("Fast triage input must include at least one data column.")

    checkpoint = _load_triage_checkpoint_state()
    input_fingerprint = _hash_input_file(input_path)
    resume_ok = (
        str(checkpoint.get("input_fingerprint") or "") == input_fingerprint
        and str(checkpoint.get("input_path") or "") == str(input_path)
        and str(checkpoint.get("keep_path") or "") == str(keep_path)
        and str(checkpoint.get("rejected_path") or "") == str(rejected_path)
        and str(checkpoint.get("quarantine_path") or "") == str(quarantine_path)
    )

    keep_headers, keep_rows = _load_output_rows(keep_path) if resume_ok else ([], [])
    rejected_headers, rejected_rows = _load_output_rows(rejected_path) if resume_ok else ([], [])
    quarantine_headers, quarantine_rows = _load_output_rows(quarantine_path) if resume_ok else ([], [])
    checkpoint_next_index = int(checkpoint.get("next_row_index") or 0) if resume_ok else 0
    output_row_count = len(keep_rows) + len(rejected_rows) + len(quarantine_rows)
    if resume_ok and checkpoint_next_index > 0 and output_row_count == 0:
        # Output CSVs were likely deleted while the old checkpoint remained; restart instead of resuming at EOF.
        resume_ok = False
        keep_headers, keep_rows = [], []
        rejected_headers, rejected_rows = [], []
        quarantine_headers, quarantine_rows = [], []
    if not resume_ok:
        keep_rows = []
        rejected_rows = []
        quarantine_rows = []

    if not keep_headers:
        keep_headers = _output_headers(base_headers)
    if not rejected_headers:
        rejected_headers = _output_headers(base_headers)
    if not quarantine_headers:
        quarantine_headers = _output_headers(base_headers)

    keep_signatures = {_row_signature(row, base_headers) for row in keep_rows}
    rejected_signatures = {_row_signature(row, base_headers) for row in rejected_rows}
    quarantine_signatures = {_row_signature(row, base_headers) for row in quarantine_rows}
    seen_triage_emails = {
        email
        for row in [*keep_rows, *rejected_rows, *quarantine_rows]
        if (email := norm_email(_email_value(row, base_headers)))
    }

    if not resume_ok:
        _csv_atomic_write(keep_path, keep_headers, keep_rows)
        _csv_atomic_write(rejected_path, rejected_headers, rejected_rows)
        _csv_atomic_write(quarantine_path, quarantine_headers, quarantine_rows)

    disposable_domain_set = disposable_domains if disposable_domains is not None else _load_triage_disposable_domains()
    start_index = checkpoint_next_index if resume_ok else 0
    start_index = max(0, min(start_index, len(input_rows)))
    checkpoint_rows = FAST_TRIAGE_CHECKPOINT_ROWS
    cancel_poll_rows = FAST_TRIAGE_CANCEL_POLL_ROWS
    canceled = False
    last_checkpoint_payload: dict[str, object] | None = None
    ledger_conn = connect_lead_ledger(_lead_ledger_db_path())

    try:
        for chunk_start in range(start_index, len(input_rows), checkpoint_rows):
            if should_cancel and should_cancel():
                canceled = True
                break
            chunk_end = min(chunk_start + checkpoint_rows, len(input_rows))
            chunk_changed = False
            chunk_complete = True
            with ledger_conn:
                for index in range(chunk_start, chunk_end):
                    if should_cancel and index > chunk_start and (index - chunk_start) % cancel_poll_rows == 0 and should_cancel():
                        canceled = True
                        chunk_complete = False
                        break
                    row = input_rows[index]
                    signature = _row_signature(row, base_headers)
                    row_email = norm_email(_email_value(row, base_headers))
                    is_duplicate_email = bool(row_email and row_email in seen_triage_emails)
                    if is_duplicate_email:
                        status, reason, evidence = "REJECT", "DUPLICATE_EMAIL", "Email already appeared earlier in Fast Triage input/output."
                        output_row = _build_output_row(
                            row,
                            base_headers,
                            status=status,
                            reason=reason,
                            evidence=evidence,
                        )
                        rejected_rows.append(output_row)
                        rejected_signatures.add(signature)
                        _sync_row_to_lead_ledger(
                            ledger_conn,
                            row,
                            base_headers,
                            input_path=input_path,
                            stage=TRIAGE_MODE_FAST,
                            status=status,
                            reason=reason,
                            processed_at=str(output_row.get("VerifiedAtUtc") or iso_utc()),
                            commit=False,
                        )
                        chunk_changed = True
                        if progress_callback:
                            try:
                                progress_callback(index + 1, len(input_rows))
                            except Exception:
                                pass
                        continue
                    if signature in keep_signatures or signature in rejected_signatures or signature in quarantine_signatures:
                        if progress_callback:
                            try:
                                progress_callback(index + 1, len(input_rows))
                            except Exception:
                                pass
                        continue
                    status, reason, evidence = _classify_fast_triage_row(
                        row,
                        base_headers,
                        disposable_domains=disposable_domain_set,
                    )
                    output_row = _build_output_row(
                        row,
                        base_headers,
                        status=status,
                        reason=reason,
                        evidence=evidence,
                    )
                    if status == "KEEP":
                        keep_rows.append(output_row)
                        keep_signatures.add(signature)
                    elif status == "REJECT":
                        rejected_rows.append(output_row)
                        rejected_signatures.add(signature)
                    else:
                        quarantine_rows.append(output_row)
                        quarantine_signatures.add(signature)
                    if row_email:
                        seen_triage_emails.add(row_email)
                    _sync_row_to_lead_ledger(
                        ledger_conn,
                        row,
                        base_headers,
                        input_path=input_path,
                        stage=TRIAGE_MODE_FAST,
                        status=status,
                        reason=reason,
                        processed_at=str(output_row.get("VerifiedAtUtc") or iso_utc()),
                        commit=False,
                    )
                    chunk_changed = True
                    if progress_callback:
                        try:
                            progress_callback(index + 1, len(input_rows))
                        except Exception:
                            pass

            _csv_atomic_write(keep_path, keep_headers, keep_rows)
            _csv_atomic_write(rejected_path, rejected_headers, rejected_rows)
            _csv_atomic_write(quarantine_path, quarantine_headers, quarantine_rows)

            checkpoint_next_index = chunk_end if chunk_complete else chunk_start
            checkpoint_payload = {
                "mode": TRIAGE_MODE_FAST,
                "input_path": str(input_path),
                "input_fingerprint": input_fingerprint,
                "keep_path": str(keep_path),
                "rejected_path": str(rejected_path),
                "quarantine_path": str(quarantine_path),
                "base_headers": list(base_headers),
                "next_row_index": checkpoint_next_index,
                "total_input_rows": len(input_rows),
                "completed": chunk_complete and chunk_end >= len(input_rows),
                "resume_supported": True,
                "updated_at_utc": iso_utc(),
                "last_chunk_changed": chunk_changed,
            }
            last_checkpoint_payload = checkpoint_payload
            if persist_state:
                _save_triage_checkpoint_state(checkpoint_payload)
            if canceled:
                break
    finally:
        ledger_conn.close()

    if progress_callback and not canceled:
        try:
            progress_callback(len(input_rows), len(input_rows))
        except Exception:
            pass

    keep_headers, keep_rows = _load_output_rows(keep_path)
    rejected_headers, rejected_rows = _load_output_rows(rejected_path)
    quarantine_headers, quarantine_rows = _load_output_rows(quarantine_path)
    reason_counts = Counter()
    for row in rejected_rows + quarantine_rows:
        reason = str(row.get("VerificationReason") or "").strip()
        if reason:
            reason_counts[reason] += 1

    report = {
        "mode": TRIAGE_MODE_FAST,
        "generated_at_utc": iso_utc(),
        "input_label": _display_path_label(input_path),
        "verified_label": _display_path_label(keep_path),
        "rejected_label": _display_path_label(rejected_path),
        "quarantine_label": _display_path_label(quarantine_path),
        "input_rows": len(input_rows),
        "total_input_rows": len(input_rows),
        "processed_rows": len(keep_rows) + len(rejected_rows) + len(quarantine_rows),
        "keep_count": len(keep_rows),
        "reject_count": len(rejected_rows),
        "quarantine_count": len(quarantine_rows),
        "reason_counts": dict(reason_counts),
        "keep_preview_rows": _derive_preview(keep_rows),
        "reject_preview_rows": _derive_preview(rejected_rows),
        "quarantine_preview_rows": _derive_preview(quarantine_rows),
        "resume_supported": True,
        "checkpoint_path": str(TRIAGE_STATE_PATH),
        "checkpoint_next_row_index": int((last_checkpoint_payload or checkpoint).get("next_row_index") or start_index) if canceled else len(input_rows),
        "checkpoint_total_input_rows": len(input_rows),
        "checkpoint_completed": not canceled,
        "checkpoint_input_fingerprint": input_fingerprint,
        "canceled": canceled,
    }
    report_path = settings.STATE_DIR / f"important_leads_triage_{timestamp_slug()}.json"
    write_json_atomic(report_path, report)
    report["report_path"] = str(report_path)

    if persist_state and not canceled:
        _save_triage_checkpoint_state(
            {
                "mode": TRIAGE_MODE_FAST,
                "input_path": str(input_path),
                "input_fingerprint": input_fingerprint,
                "keep_path": str(keep_path),
                "rejected_path": str(rejected_path),
                "quarantine_path": str(quarantine_path),
                "base_headers": list(base_headers),
                "next_row_index": len(input_rows),
                "total_input_rows": len(input_rows),
                "completed": True,
                "resume_supported": True,
                "updated_at_utc": iso_utc(),
            }
        )
    if persist_state:
        save_state(
            **{
                TRIAGE_PATHS_STATE_KEY: _triage_path_state_labels(
                    input_path,
                    keep_path,
                    rejected_path,
                    quarantine_path,
                ),
                TRIAGE_STATE_KEY: report,
            }
        )

    return report


def verify_master_leads(
    input_path: Path = DEFAULT_INPUT_PATH,
    verified_path: Path = DEFAULT_VERIFIED_PATH,
    rejected_path: Path = DEFAULT_REJECTED_PATH,
    quarantine_path: Path = DEFAULT_QUARANTINE_PATH,
    *,
    persist_state: bool = True,
    searcher: Callable[[str], object] | None = None,
    fetcher: Callable[[str], object] | None = None,
    max_workers: int = 8,
    timeout_seconds: int = 5,
    max_pages_per_lead: int = 1,
    retries: int = 1,
    respect_robots: bool = False,
    allow_social_proof: bool = True,
    validate_deliverability: bool = False,
    selected_lead_ids: Sequence[str] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, object]:
    del respect_robots

    input_path = Path(input_path)
    verified_path = Path(verified_path)
    rejected_path = Path(rejected_path)
    quarantine_path = Path(quarantine_path)
    input_headers, input_rows = _load_csv_rows(input_path)
    if not input_headers:
        raise ValueError(f"Verify input is empty: {input_path}")

    base_headers = [header for header in input_headers if header not in VERIFY_AUDIT_HEADERS]
    if not base_headers:
        raise ValueError("Verify input must include at least one data column.")
    normalized_selected_lead_ids = _normalized_selected_lead_ids(selected_lead_ids)
    selected_lead_ids_fingerprint = _selected_lead_ids_fingerprint(normalized_selected_lead_ids)
    input_rows = _filter_rows_for_selected_lead_ids(
        input_rows,
        base_headers,
        selected_lead_ids=normalized_selected_lead_ids,
    )

    worker_count = _verify_worker_count(max_workers)
    network_client: _VerifyNetworkClient | None = None
    if searcher is None or fetcher is None:
        network_client = _VerifyNetworkClient(timeout_seconds, worker_count)
    verify_searcher = searcher or network_client.search  # type: ignore[union-attr]
    verify_fetcher = fetcher or network_client.fetch  # type: ignore[union-attr]
    checkpoint = _load_checkpoint_state()
    input_fingerprint = _hash_input_file(input_path)
    resume_ok = (
        str(checkpoint.get("input_fingerprint") or "") == input_fingerprint
        and str(checkpoint.get("selected_lead_ids_fingerprint") or "") == selected_lead_ids_fingerprint
        and str(checkpoint.get("input_path") or "") == str(input_path)
        and str(checkpoint.get("verified_path") or "") == str(verified_path)
        and str(checkpoint.get("rejected_path") or "") == str(rejected_path)
        and str(checkpoint.get("quarantine_path") or "") == str(quarantine_path)
    )

    verified_headers, verified_rows = _load_output_rows(verified_path) if resume_ok else ([], [])
    rejected_headers, rejected_rows = _load_output_rows(rejected_path) if resume_ok else ([], [])
    quarantine_headers, quarantine_rows = _load_output_rows(quarantine_path) if resume_ok else ([], [])
    if not resume_ok:
        verified_rows = []
        rejected_rows = []
        quarantine_rows = []

    if not verified_headers:
        verified_headers = _output_headers(base_headers)
    if not rejected_headers:
        rejected_headers = _output_headers(base_headers)
    if not quarantine_headers:
        quarantine_headers = _output_headers(base_headers)

    verified_signatures = {_row_signature(row, base_headers) for row in verified_rows}
    rejected_signatures = {_row_signature(row, base_headers) for row in rejected_rows}
    quarantine_signatures = {_row_signature(row, base_headers) for row in quarantine_rows}

    if not resume_ok:
        _csv_atomic_write(verified_path, verified_headers, verified_rows)
        _csv_atomic_write(rejected_path, rejected_headers, rejected_rows)
        _csv_atomic_write(quarantine_path, quarantine_headers, quarantine_rows)

    start_index = int(checkpoint.get("next_row_index") or 0) if resume_ok else 0
    start_index = max(0, min(start_index, len(input_rows)))
    checkpoint_rows = VERIFY_CHECKPOINT_ROWS
    canceled = False
    last_checkpoint_payload: dict[str, object] | None = None
    classification_cache: dict[tuple[str, str, str, str], tuple[str, str, str]] = {}
    classification_cache_lock = threading.Lock()
    ledger_conn = connect_lead_ledger(_lead_ledger_db_path())

    def classify_cached(row: dict[str, str]) -> tuple[str, str, str]:
        cache_key = _classification_cache_key(row, base_headers)
        with classification_cache_lock:
            cached = classification_cache.get(cache_key)
        if cached is not None:
            return cached
        result = _classify_row(
            row,
            base_headers,
            searcher=verify_searcher,
            fetcher=verify_fetcher,
            max_pages_per_lead=max_pages_per_lead,
            timeout_seconds=timeout_seconds,
            retries=retries,
            allow_social_proof=allow_social_proof,
            validate_deliverability=validate_deliverability,
        )
        with classification_cache_lock:
            if len(classification_cache) < VERIFY_CACHE_MAX_ITEMS:
                classification_cache[cache_key] = result
        return result

    def classify_task(index: int, row: dict[str, str], signature: str) -> tuple[int, dict[str, str], str, str, str, str]:
        status, reason, evidence = classify_cached(row)
        return index, row, signature, status, reason, evidence

    try:
        for chunk_start in range(start_index, len(input_rows), checkpoint_rows):
            if should_cancel and should_cancel():
                canceled = True
                break
            chunk_end = min(chunk_start + checkpoint_rows, len(input_rows))
            chunk_changed = False
            pending_tasks: list[tuple[int, dict[str, str], str]] = []
            pending_signatures: set[str] = set()
            for index in range(chunk_start, chunk_end):
                row = input_rows[index]
                signature = _row_signature(row, base_headers)
                if (
                    signature in verified_signatures
                    or signature in rejected_signatures
                    or signature in quarantine_signatures
                    or signature in pending_signatures
                ):
                    if progress_callback:
                        try:
                            progress_callback(index + 1, len(input_rows))
                        except Exception:
                            pass
                    continue
                pending_signatures.add(signature)
                pending_tasks.append((index, row, signature))

            classified: dict[int, tuple[int, dict[str, str], str, str, str, str]] = {}
            chunk_tasks_completed = False
            if worker_count <= 1 or len(pending_tasks) <= 1:
                for index, row, signature in pending_tasks:
                    if should_cancel and should_cancel():
                        canceled = True
                        break
                    classified[index] = classify_task(index, row, signature)
                chunk_tasks_completed = len(classified) == len(pending_tasks)
            else:
                executor = ThreadPoolExecutor(max_workers=min(worker_count, len(pending_tasks)))
                try:
                    futures = {
                        executor.submit(classify_task, index, row, signature): index
                        for index, row, signature in pending_tasks
                    }
                    pending = set(futures)
                    while pending:
                        if should_cancel and should_cancel():
                            canceled = True
                            for future in pending:
                                future.cancel()
                            break
                        done, pending = wait(pending, timeout=VERIFY_CANCEL_POLL_SECONDS, return_when=FIRST_COMPLETED)
                        for future in done:
                            result = future.result()
                            classified[result[0]] = result
                    chunk_tasks_completed = not pending and len(classified) == len(pending_tasks)
                finally:
                    if canceled or (should_cancel and should_cancel()):
                        canceled = True
                        executor.shutdown(wait=False, cancel_futures=True)
                    else:
                        executor.shutdown(wait=True)

            chunk_applied_all = True
            for index in sorted(classified):
                if should_cancel and should_cancel():
                    canceled = True
                    chunk_applied_all = False
                    break
                _index, row, signature, status, reason, evidence = classified[index]
                output_row = _build_output_row(
                    row,
                    base_headers,
                    status=status,
                    reason=reason,
                    evidence=evidence,
                )
                if status == "KEEP":
                    verified_rows.append(output_row)
                    verified_signatures.add(signature)
                elif status == "REJECT":
                    rejected_rows.append(output_row)
                    rejected_signatures.add(signature)
                else:
                    quarantine_rows.append(output_row)
                    quarantine_signatures.add(signature)
                _sync_row_to_lead_ledger(
                    ledger_conn,
                    row,
                    base_headers,
                    input_path=input_path,
                    stage=TRIAGE_MODE_STRICT,
                    status=status,
                    reason=reason,
                    processed_at=str(output_row.get("VerifiedAtUtc") or iso_utc()),
                )
                chunk_changed = True
                if progress_callback:
                    try:
                        progress_callback(index + 1, len(input_rows))
                    except Exception:
                        pass

            _csv_atomic_write(verified_path, verified_headers, verified_rows)
            _csv_atomic_write(rejected_path, rejected_headers, rejected_rows)
            _csv_atomic_write(quarantine_path, quarantine_headers, quarantine_rows)

            chunk_complete = chunk_tasks_completed and chunk_applied_all
            checkpoint_next_index = chunk_end if chunk_complete else chunk_start
            checkpoint_payload = {
                "input_path": str(input_path),
                "input_fingerprint": input_fingerprint,
                "selected_lead_ids_fingerprint": selected_lead_ids_fingerprint,
                "selected_lead_ids_count": len(normalized_selected_lead_ids),
                "verified_path": str(verified_path),
                "rejected_path": str(rejected_path),
                "quarantine_path": str(quarantine_path),
                "base_headers": list(base_headers),
                "next_row_index": checkpoint_next_index,
                "total_input_rows": len(input_rows),
                "completed": chunk_complete and chunk_end >= len(input_rows),
                "resume_supported": True,
                "updated_at_utc": iso_utc(),
                "last_chunk_changed": chunk_changed,
            }
            last_checkpoint_payload = checkpoint_payload
            if persist_state:
                _save_checkpoint_state(checkpoint_payload)

            if should_cancel and should_cancel():
                canceled = True
                break
    finally:
        ledger_conn.close()

    if progress_callback and not canceled:
        try:
            progress_callback(len(input_rows), len(input_rows))
        except Exception:
            pass

    verified_headers, verified_rows = _load_output_rows(verified_path)
    rejected_headers, rejected_rows = _load_output_rows(rejected_path)
    quarantine_headers, quarantine_rows = _load_output_rows(quarantine_path)
    reason_counts = Counter()
    for row in rejected_rows + quarantine_rows:
        reason = str(row.get("VerificationReason") or "").strip()
        if reason:
            reason_counts[reason] += 1

    report = {
        "generated_at_utc": iso_utc(),
        "input_label": _display_path_label(input_path),
        "verified_label": _display_path_label(verified_path),
        "rejected_label": _display_path_label(rejected_path),
        "quarantine_label": _display_path_label(quarantine_path),
        "input_rows": len(input_rows),
        "total_input_rows": len(input_rows),
        "processed_rows": len(verified_rows) + len(rejected_rows) + len(quarantine_rows),
        "keep_count": len(verified_rows),
        "reject_count": len(rejected_rows),
        "quarantine_count": len(quarantine_rows),
        "selected_lead_ids_count": len(normalized_selected_lead_ids),
        "reason_counts": dict(reason_counts),
        "keep_preview_rows": _derive_preview(verified_rows),
        "reject_preview_rows": _derive_preview(rejected_rows),
        "quarantine_preview_rows": _derive_preview(quarantine_rows),
        "resume_supported": True,
        "checkpoint_path": str(VERIFY_STATE_PATH),
        "checkpoint_next_row_index": int((last_checkpoint_payload or checkpoint).get("next_row_index") or start_index) if canceled else len(input_rows),
        "checkpoint_total_input_rows": len(input_rows),
        "checkpoint_completed": not canceled,
        "checkpoint_input_fingerprint": input_fingerprint,
        "canceled": canceled,
    }
    report_path = settings.STATE_DIR / f"important_leads_verify_{timestamp_slug()}.json"
    write_json_atomic(report_path, report)
    report["report_path"] = str(report_path)

    if persist_state and not canceled:
        _save_checkpoint_state(
            {
                "input_path": str(input_path),
                "input_fingerprint": input_fingerprint,
                "selected_lead_ids_fingerprint": selected_lead_ids_fingerprint,
                "selected_lead_ids_count": len(normalized_selected_lead_ids),
                "verified_path": str(verified_path),
                "rejected_path": str(rejected_path),
                "quarantine_path": str(quarantine_path),
                "base_headers": list(base_headers),
                "next_row_index": len(input_rows),
                "total_input_rows": len(input_rows),
                "completed": True,
                "resume_supported": True,
                "updated_at_utc": iso_utc(),
            }
        )
        save_state(
            **{
                VERIFY_PATHS_STATE_KEY: _verify_path_state_labels(
                    input_path,
                    verified_path,
                    rejected_path,
                    quarantine_path,
                ),
                VERIFY_STATE_KEY: report,
            }
        )
    elif persist_state:
        save_state(
            **{
                VERIFY_PATHS_STATE_KEY: _verify_path_state_labels(
                    input_path,
                    verified_path,
                    rejected_path,
                    quarantine_path,
                ),
                VERIFY_STATE_KEY: report,
            }
        )

    if network_client is not None:
        network_client.close()

    return report
