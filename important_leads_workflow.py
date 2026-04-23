from __future__ import annotations

import csv
import difflib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence

import settings
import runtime_control
from email_validator import EmailNotValidError, EmailSyntaxError, EmailUndeliverableError, validate_email
from lead_ledger import connect_lead_ledger, deterministic_lead_id, dispatch_history_state, load_contacted_lead_ids, load_lead_by_id, record_dispatch_event, source_row_hash, upsert_lead
from leads_workflow import iso_utc, load_state, save_state, timestamp_slug, write_json_atomic
from recipient_file_lock import lock_files
from important_leads_verify import important_leads_triage_path_state, important_leads_verify_path_state
from send_shard import PROFILES, ROLE_LOCALPART_BLOCKLIST, is_role_recipient, load_already_done
from sendgrid_hygiene import load_active_suppressed_emails, norm_email


IMPORTANT_DIR = settings.APP_ROOT / "_important"
CHECK_RUNS_DIR = IMPORTANT_DIR / "check_runs"
MASTER_INPUT_PATH = IMPORTANT_DIR / "leadschecker.csv"
MASTER_OUTPUT_PATH = IMPORTANT_DIR / "leads.csv"
MASTER_REJECTED_PATH = IMPORTANT_DIR / "leads_rejected.csv"
DISPOSABLE_DOMAINS_PATH = settings.APP_ROOT / "data" / "reference" / "disposable_domains.txt"

STATE_DIR = settings.STATE_DIR
BACKUP_ROOT = settings.BACKUPS_DIR

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_IN_TEXT_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
SAFE_SPLIT_RE = re.compile(r"[;,/|]+")

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
STRICT_VERIFIED_PATH = IMPORTANT_DIR / "leads_verified.csv"
DISPATCH_PREVIEWS_DIR = STATE_DIR / "dispatch_previews"
DISPATCH_RUN_HISTORY_PATH = STATE_DIR / "dispatch_run_history.json"
DISPATCH_RUN_HISTORY_LIMIT = 100
CHECK_PREVIEW_ROWS = 8
DISPATCH_PREVIEW_ROWS = 8
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


def _detect_core_headers(fieldnames: Sequence[str]) -> Dict[str, str]:
    return {
        "Email": _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES),
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
    output_headers = ["FullName", "FirstName", "Email"]
    used.update(output_headers)
    source_to_output: Dict[str, str] = {}

    full_source = core_headers.get("FullName", "")
    first_source = core_headers.get("FirstName", "")
    email_source = core_headers.get("Email", "")
    book_source = core_headers.get("BookTitle", "")

    if full_source:
        source_to_output[full_source] = "FullName"
    if first_source:
        source_to_output[first_source] = "FirstName"
    if email_source:
        source_to_output[email_source] = "Email"
    if book_source:
        output_headers.append("BookTitle")
        used.add("BookTitle")
        source_to_output[book_source] = "BookTitle"

    for source in fieldnames:
        if source in source_to_output:
            continue
        source_to_output[source] = _unique_header(source, used)
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


def load_dispatch_preview(preview_id: str, preview_dir: Path = DISPATCH_PREVIEWS_DIR) -> Dict[str, object]:
    path = _dispatch_preview_path(preview_id, preview_dir)
    if not path.exists():
        raise FileNotFoundError(f"Dispatch preview not found: {preview_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Dispatch preview is invalid: {preview_id}")
    return raw


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
        "source_file_path": str(payload.get("dispatch_source_path") or ""),
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
            key: int(rows_written_per_queue_map.get(key) or 0)
            for key in [f"sendgrid_{index}" for index in range(1, 6)]
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


def _dispatch_queue_key(path: Path, jc_path: Path, sendgrid_paths: Sequence[Path]) -> str:
    if path == jc_path:
        return "private_jc"
    for index, candidate in enumerate(sendgrid_paths, start=1):
        if path == candidate:
            return f"sendgrid_{index}"
    return path.name


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


def _restore_queue_backups(paths: Sequence[Path], backup_dir: Path) -> None:
    for path in paths:
        backup_path = backup_dir / path.name
        if backup_path.exists():
            shutil.copy2(backup_path, path)


def _record_dispatch_history_from_preview(
    preview: Dict[str, object],
    *,
    run_id: str,
    dispatched_at: str,
) -> tuple[int, Dict[str, int]]:
    dispatch_source_mode = str(preview.get("dispatch_source_mode") or DISPATCH_SOURCE_TRIAGED_KEEP)
    dispatch_source_path = Path(str(preview.get("dispatch_source_path") or ""))
    plan_dispatch_events_by_queue = preview.get("plan_dispatch_events_by_queue") or {}
    if not isinstance(plan_dispatch_events_by_queue, dict):
        raise RuntimeError("Dispatch preview is missing lead dispatch history metadata. Re-run Preview Dispatch.")
    explicit_db_path = Path(str(preview.get("lead_ledger_db_path") or "")) if str(preview.get("lead_ledger_db_path") or "").strip() else None
    conn = connect_lead_ledger(_lead_ledger_db_path(explicit_db_path))
    try:
        rows_created = 0
        rows_created_per_queue = {
            "private_jc": 0,
            "sendgrid_1": 0,
            "sendgrid_2": 0,
            "sendgrid_3": 0,
            "sendgrid_4": 0,
            "sendgrid_5": 0,
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
    default_jc_path, default_sendgrid_paths, default_jc_log_path, default_sendgrid_log_paths = _dispatch_profile_paths()
    jc_path = jc_queue_path or default_jc_path
    sendgrid_paths = list(sendgrid_queue_paths or default_sendgrid_paths)
    if len(sendgrid_paths) != 5:
        raise ValueError("Dispatch requires exactly 5 SendGrid queue files.")
    jc_log = jc_log_path or default_jc_log_path
    sg_logs = list(sendgrid_log_paths or default_sendgrid_log_paths)
    if len(sg_logs) != len(sendgrid_paths):
        raise ValueError("Dispatch requires one SendGrid log file per SendGrid queue.")
    queue_paths = [jc_path, *sendgrid_paths]
    log_paths = [jc_log, *sg_logs]
    ledger_conn = connect_lead_ledger(_lead_ledger_db_path(lead_ledger_db_path))

    try:
        source_mode = _normalize_dispatch_source_mode(dispatch_source_mode)
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

        queue_headers_by_path: Dict[Path, List[str]] = {}
        queue_rows_by_path: Dict[Path, List[Dict[str, str]]] = {}
        for path in queue_paths:
            headers, rows = _read_queue_rows(path)
            queue_headers_by_path[path] = headers
            queue_rows_by_path[path] = rows

        jc_sent = _sent_email_set([jc_log])
        sendgrid_sent = _sent_email_set(sg_logs)
        jc_queued = _existing_queue_email_set({jc_path: queue_rows_by_path[jc_path]})
        sendgrid_queued = _existing_queue_email_set({path: queue_rows_by_path[path] for path in sendgrid_paths})
        contacted_lead_ids = load_contacted_lead_ids(ledger_conn)
        ledger_state = dispatch_history_state(ledger_conn)

        eligible_rows_total = len(source_rows)
        normalized_cap = _normalize_dispatch_cap(dispatch_cap)
        selected_limit = _dispatch_cap_limit(normalized_cap, eligible_rows_total)
        selected_rows = list(source_rows[:selected_limit])

        sg_assign_cursor = 0
        added_astra_rows: List[Dict[str, str]] = []
        added_sendgrid_rows_by_index: List[List[Dict[str, str]]] = [[] for _ in sendgrid_paths]
        master_seen: set[str] = set()
        suppressed_skipped = 0
        duplicate_master_skipped = 0
        invalid_malformed_skipped = 0
        already_contacted_skipped = 0
        added_astra = 0
        added_sendgrid = 0
        skipped_astra_already_sent = 0
        skipped_astra_already_queued = 0
        skipped_sendgrid_already_sent = 0
        skipped_sendgrid_already_queued = 0
        skipped_both = 0
        outcome_counts: Counter[str] = Counter()
        exclusion_reason_counts: Counter[str] = Counter()
        plan_dispatch_events_by_queue: Dict[str, List[Dict[str, str]]] = {
            "private_jc": [],
            "sendgrid_1": [],
            "sendgrid_2": [],
            "sendgrid_3": [],
            "sendgrid_4": [],
            "sendgrid_5": [],
        }

        total_dispatch_rows = len(selected_rows)
        for row in selected_rows:
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
            if lead_id in contacted_lead_ids:
                already_contacted_skipped += 1
                exclusion_reason_counts["already_contacted"] += 1
                continue

            if email in blocked_emails:
                suppressed_skipped += 1
                exclusion_reason_counts["suppressed"] += 1
                continue

            normalized = {header: _strip_cell(row.get(header, "")) for header in source_headers}
            normalized["Email"] = email

            added_to_astra = False
            added_to_sendgrid = False

            if email in jc_sent:
                skipped_astra_already_sent += 1
            elif email in jc_queued:
                skipped_astra_already_queued += 1
            else:
                added_astra_rows.append(normalized)
                jc_queued.add(email)
                added_astra += 1
                added_to_astra = True
                plan_dispatch_events_by_queue["private_jc"].append(
                    {
                        "lead_id": lead_id,
                        "email": email,
                        "queue_target": "private_jc",
                        "profile": "private_jc",
                        "full_name": _strip_cell(normalized.get("FullName", "")),
                        "first_name": _trimmed_first_name(normalized.get("FirstName", "") or normalized.get("FullName", "")),
                        "source_row_hash": source_row_hash(normalized),
                    }
                )

            if email in sendgrid_sent:
                skipped_sendgrid_already_sent += 1
            elif email in sendgrid_queued:
                skipped_sendgrid_already_queued += 1
            else:
                bucket_index = sg_assign_cursor % len(sendgrid_paths)
                sg_assign_cursor += 1
                added_sendgrid_rows_by_index[bucket_index].append(normalized)
                sendgrid_queued.add(email)
                added_sendgrid += 1
                added_to_sendgrid = True
                queue_key = f"sendgrid_{bucket_index + 1}"
                plan_dispatch_events_by_queue[queue_key].append(
                    {
                        "lead_id": lead_id,
                        "email": email,
                        "queue_target": queue_key,
                        "profile": queue_key,
                        "full_name": _strip_cell(normalized.get("FullName", "")),
                        "first_name": _trimmed_first_name(normalized.get("FirstName", "") or normalized.get("FullName", "")),
                        "source_row_hash": source_row_hash(normalized),
                    }
                )

            if not added_to_astra and (email in jc_sent or email in jc_queued):
                exclusion_reason_counts["already_sent" if email in jc_sent else "already_queued"] += 1
            if not added_to_sendgrid and (email in sendgrid_sent or email in sendgrid_queued):
                exclusion_reason_counts["already_sent" if email in sendgrid_sent else "already_queued"] += 1

            if added_to_astra and added_to_sendgrid:
                outcome_counts["added_astra_and_sendgrid"] += 1
            elif added_to_astra:
                outcome_counts["added_astra_only"] += 1
            elif added_to_sendgrid:
                outcome_counts["added_sendgrid_only"] += 1
            else:
                outcome_counts["skipped_both"] += 1
                skipped_both += 1

        queue_headers = _queue_output_headers(queue_headers_by_path.values(), source_headers)
        if "BookTitle" in master_headers and "BookTitle" not in queue_headers:
            queue_headers.append("BookTitle")

        plan_rows_by_path: Dict[Path, List[Dict[str, str]]] = {path: [] for path in queue_paths}
        plan_rows_by_path[jc_path] = [_master_row_to_queue_row(row, queue_headers) for row in added_astra_rows]
        for path, rows in zip(sendgrid_paths, added_sendgrid_rows_by_index):
            plan_rows_by_path[path] = [_master_row_to_queue_row(row, queue_headers) for row in rows]

        rows_written_per_queue = {
            _dispatch_queue_key(path, jc_path, sendgrid_paths): len(rows)
            for path, rows in plan_rows_by_path.items()
        }
        dependency_fingerprints = _collect_dispatch_input_fingerprints(
            source_path=source_path,
            queue_paths=queue_paths,
            log_paths=log_paths,
            sendgrid_suppressions_path=sendgrid_suppressions_path,
            suppressed_path=suppressed_path,
            unsubscribed_path=unsubscribed_path,
        )

        plan = {
            "dispatch_source_mode": source_mode,
            "dispatch_source_name": str(source_state["dispatch_source_name"]),
            "dispatch_source_path": str(source_path),
            "dispatch_source_label": str(source_state["dispatch_source_label"]),
            "dispatch_source_row_count": int(source_state["dispatch_source_row_count"]),
            "dispatch_eligible_row_count": eligible_rows_total,
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
            "queue_paths": {
                "private_jc": str(jc_path),
                "sendgrid_1": str(sendgrid_paths[0]),
                "sendgrid_2": str(sendgrid_paths[1]),
                "sendgrid_3": str(sendgrid_paths[2]),
                "sendgrid_4": str(sendgrid_paths[3]),
                "sendgrid_5": str(sendgrid_paths[4]),
            },
            "queue_existing_counts": {
                "private_jc": len(queue_rows_by_path[jc_path]),
                "sendgrid_1": len(queue_rows_by_path[sendgrid_paths[0]]),
                "sendgrid_2": len(queue_rows_by_path[sendgrid_paths[1]]),
                "sendgrid_3": len(queue_rows_by_path[sendgrid_paths[2]]),
                "sendgrid_4": len(queue_rows_by_path[sendgrid_paths[3]]),
                "sendgrid_5": len(queue_rows_by_path[sendgrid_paths[4]]),
            },
            "skipped_invalid_malformed": invalid_malformed_skipped,
            "invalid_malformed_skipped": invalid_malformed_skipped,
            "skipped_invalid_source_row": invalid_malformed_skipped,
            "skipped_suppressed": suppressed_skipped,
            "suppressed_skipped": suppressed_skipped,
            "skipped_already_contacted": already_contacted_skipped,
            "duplicate_master_skipped": duplicate_master_skipped,
            "skipped_astra_already_sent": skipped_astra_already_sent,
            "skipped_astra_already_queued": skipped_astra_already_queued,
            "skipped_sendgrid_already_sent": skipped_sendgrid_already_sent,
            "skipped_sendgrid_already_queued": skipped_sendgrid_already_queued,
            "skipped_already_sent": skipped_astra_already_sent + skipped_sendgrid_already_sent,
            "skipped_already_queued": skipped_astra_already_queued + skipped_sendgrid_already_queued,
            "rows_to_add_private_jc": added_astra,
            "added_astra": added_astra,
            "rows_to_add_sendgrid": added_sendgrid,
            "added_sendgrid": added_sendgrid,
            "rows_to_add_sendgrid_1": len(plan_rows_by_path[sendgrid_paths[0]]),
            "rows_to_add_sendgrid_2": len(plan_rows_by_path[sendgrid_paths[1]]),
            "rows_to_add_sendgrid_3": len(plan_rows_by_path[sendgrid_paths[2]]),
            "rows_to_add_sendgrid_4": len(plan_rows_by_path[sendgrid_paths[3]]),
            "rows_to_add_sendgrid_5": len(plan_rows_by_path[sendgrid_paths[4]]),
            "assigned_sg1": len(plan_rows_by_path[sendgrid_paths[0]]),
            "assigned_sg2": len(plan_rows_by_path[sendgrid_paths[1]]),
            "assigned_sg3": len(plan_rows_by_path[sendgrid_paths[2]]),
            "assigned_sg4": len(plan_rows_by_path[sendgrid_paths[3]]),
            "assigned_sg5": len(plan_rows_by_path[sendgrid_paths[4]]),
            "skipped_both": skipped_both,
            "outcome_counts": dict(outcome_counts),
            "exclusion_reason_counts": dict(exclusion_reason_counts),
            "total_rows_would_write": added_astra + added_sendgrid,
            "dispatch_source_preview_rows": source_state["dispatch_source_preview_rows"],
            "dispatch_source_headers": source_state["dispatch_source_headers"],
            "assigned_preview_rows": _preview_rows(
                [row for path in queue_paths for row in plan_rows_by_path[path]],
                queue_headers,
                DISPATCH_PREVIEW_ROWS,
            ),
            "suppression_summary": suppression_summary,
            "plan_rows_by_queue": {
                "private_jc": plan_rows_by_path[jc_path],
                "sendgrid_1": plan_rows_by_path[sendgrid_paths[0]],
                "sendgrid_2": plan_rows_by_path[sendgrid_paths[1]],
                "sendgrid_3": plan_rows_by_path[sendgrid_paths[2]],
                "sendgrid_4": plan_rows_by_path[sendgrid_paths[3]],
                "sendgrid_5": plan_rows_by_path[sendgrid_paths[4]],
            },
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
    )
    preview_id = f"dispatch_preview_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
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


def confirm_dispatch_preview(
    preview_id: str,
    *,
    require_stopped: bool = True,
    backup_root: Path = BACKUP_ROOT,
    report_dir: Path = STATE_DIR,
    persist_state: bool = True,
    preview_dir: Path = DISPATCH_PREVIEWS_DIR,
) -> Dict[str, object]:
    preview = validate_dispatch_preview(preview_id, preview_dir=preview_dir)
    active_states = _active_sender_states() if require_stopped else {}
    if active_states:
        raise RuntimeError(f"Stop all senders before dispatching leads. Active: {', '.join(sorted(active_states))}")

    queue_paths_map = preview.get("queue_paths") or {}
    if not isinstance(queue_paths_map, dict):
        raise RuntimeError("Dispatch preview is missing queue paths. Re-run Preview Dispatch.")
    queue_keys = ["private_jc", "sendgrid_1", "sendgrid_2", "sendgrid_3", "sendgrid_4", "sendgrid_5"]
    queue_paths = [Path(str(queue_paths_map.get(key) or "")) for key in queue_keys]
    queue_headers = [str(value or "").strip() for value in (preview.get("queue_headers") or []) if str(value or "").strip()]
    if len(queue_paths) != 6 or not all(str(path).strip() for path in queue_paths):
        raise RuntimeError("Dispatch preview is missing queue files. Re-run Preview Dispatch.")
    if not queue_headers:
        raise RuntimeError("Dispatch preview is missing queue headers. Re-run Preview Dispatch.")

    plan_rows_by_queue = preview.get("plan_rows_by_queue") or {}
    if not isinstance(plan_rows_by_queue, dict):
        raise RuntimeError("Dispatch preview is missing planned queue rows. Re-run Preview Dispatch.")

    run_id = f"dispatch_run_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    started_at_utc = iso_utc()
    backup_dir = backup_root / f"dispatch_{timestamp_slug()}"

    with lock_files(queue_paths):
        preview = validate_dispatch_preview(preview_id, preview_dir=preview_dir)
        active_states = _active_sender_states() if require_stopped else {}
        if active_states:
            raise RuntimeError(f"Stop all senders before dispatching leads. Active: {', '.join(sorted(active_states))}")
        existing_rows_by_path: Dict[Path, List[Dict[str, str]]] = {}
        for path in queue_paths:
            _headers, rows = _read_queue_rows(path)
            existing_rows_by_path[path] = rows
        _copy_queue_backups(queue_paths, backup_dir)
        final_rows_by_path: Dict[Path, List[Dict[str, str]]] = {}
        for key, path in zip(queue_keys, queue_paths):
            new_rows = [
                {str(header): _strip_cell(row.get(str(header), "")) for header in queue_headers}
                for row in (plan_rows_by_queue.get(key) or [])
                if isinstance(row, dict)
            ]
            final_rows_by_path[path] = list(existing_rows_by_path[path]) + new_rows
            _write_csv_atomic(path, queue_headers, final_rows_by_path[path])
        try:
            dispatch_history_rows_created, dispatch_history_rows_per_queue = _record_dispatch_history_from_preview(
                preview,
                run_id=run_id,
                dispatched_at=started_at_utc,
            )
        except Exception:
            _restore_queue_backups(queue_paths, backup_dir)
            raise

    final_queue_counts = {
        "jc": len(final_rows_by_path[queue_paths[0]]),
        "sg1": len(final_rows_by_path[queue_paths[1]]),
        "sg2": len(final_rows_by_path[queue_paths[2]]),
        "sg3": len(final_rows_by_path[queue_paths[3]]),
        "sg4": len(final_rows_by_path[queue_paths[4]]),
        "sg5": len(final_rows_by_path[queue_paths[5]]),
    }

    completed_at_utc = iso_utc()
    report = {
        "run_id": run_id,
        "status": "completed",
        "started_at_utc": started_at_utc,
        "started_at": started_at_utc,
        "completed_at_utc": completed_at_utc,
        "completed_at": completed_at_utc,
        "generated_at_utc": completed_at_utc,
        "preview_id": preview_id,
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
        "added_astra": int(preview.get("added_astra") or 0),
        "skipped_astra_already_sent": int(preview.get("skipped_astra_already_sent") or 0),
        "skipped_astra_already_queued": int(preview.get("skipped_astra_already_queued") or 0),
        "added_sendgrid": int(preview.get("added_sendgrid") or 0),
        "skipped_sendgrid_already_sent": int(preview.get("skipped_sendgrid_already_sent") or 0),
        "skipped_sendgrid_already_queued": int(preview.get("skipped_sendgrid_already_queued") or 0),
        "skipped_already_sent": int(preview.get("skipped_already_sent") or 0),
        "skipped_already_queued": int(preview.get("skipped_already_queued") or 0),
        "suppressed_skipped": int(preview.get("suppressed_skipped") or 0),
        "skipped_suppressed": int(preview.get("skipped_suppressed") or 0),
        "invalid_malformed_skipped": int(preview.get("invalid_malformed_skipped") or 0),
        "skipped_invalid_malformed": int(preview.get("skipped_invalid_malformed") or 0),
        "duplicate_master_skipped": int(preview.get("duplicate_master_skipped") or 0),
        "assigned_sg1": int(preview.get("assigned_sg1") or 0),
        "assigned_sg2": int(preview.get("assigned_sg2") or 0),
        "assigned_sg3": int(preview.get("assigned_sg3") or 0),
        "assigned_sg4": int(preview.get("assigned_sg4") or 0),
        "assigned_sg5": int(preview.get("assigned_sg5") or 0),
        "skipped_both": int(preview.get("skipped_both") or 0),
        "rows_written_per_queue": dict(preview.get("rows_written_per_queue") or {}),
        "final_queue_counts": final_queue_counts,
        "queue_headers": queue_headers,
        "outcome_counts": dict(preview.get("outcome_counts") or {}),
        "exclusion_reason_counts": dict(preview.get("exclusion_reason_counts") or {}),
        "assigned_preview_rows": list(preview.get("assigned_preview_rows") or []),
        "dispatch_source_preview_rows": list(preview.get("dispatch_source_preview_rows") or []),
        "total_rows_would_write": int(preview.get("total_rows_would_write") or 0),
        "skipped_already_contacted": int(preview.get("skipped_already_contacted") or 0),
        "skipped_invalid_source_row": int(preview.get("skipped_invalid_source_row") or 0),
        "dispatch_history_rows_created": int(dispatch_history_rows_created or 0),
        "dispatch_history_rows_per_queue": dict(dispatch_history_rows_per_queue),
    }
    report.update(_dispatch_alias_fields(report))

    report_path = report_dir / f"important_leads_dispatch_{timestamp_slug()}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = dict(report)
    report_payload["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    _append_dispatch_run_history(report, history_path=report_dir / DISPATCH_RUN_HISTORY_PATH.name)
    if persist_state:
        save_state(**{MASTER_DISPATCH_STATE_KEY: report})

    preview["status"] = "confirmed"
    preview["confirmed_at_utc"] = report["completed_at_utc"]
    preview["confirmed_run_id"] = run_id
    _save_dispatch_preview(preview, preview_dir)
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
        normalized_row["FullName"] = _full_identity_value(raw_row, core_headers)
        normalized_row["FirstName"] = _trimmed_first_name(normalized_row["FullName"])
        if core_headers["FirstName"]:
            first_raw = _strip_cell(raw_row.get(core_headers["FirstName"], ""))
            if first_raw:
                normalized_row["FirstName"] = _trimmed_first_name(first_raw)
                if not normalized_row["FullName"]:
                    normalized_row["FullName"] = first_raw

        validation = _email_validation_result(
            raw_row.get(core_headers["Email"], ""),
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
    sendgrid_profiles = [
        name for name, cfg in PROFILES.items()
        if str(cfg.get("provider") or "") == "sendgrid"
    ]
    shard_paths = [settings.shard_path(str(PROFILES[name]["csv"])) for name in sendgrid_profiles]
    jc_log_path = settings.log_path(str(PROFILES["private_jc"]["log"]))
    sendgrid_log_paths = [settings.log_path(str(PROFILES[name]["log"])) for name in sendgrid_profiles]
    return jc_path, shard_paths, jc_log_path, sendgrid_log_paths


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
    for path in log_paths:
        sent |= load_already_done(path)
    return sent


def _queue_output_headers(existing_headers: Iterable[Sequence[str]], master_headers: Sequence[str]) -> List[str]:
    output = ["Email", "FirstName"]
    seen = set(output)

    def maybe_add(value: str) -> None:
        key = "FirstName" if value in {"FirstName", "AuthorName"} else value
        if key == "FullName":
            return
        if not key or key in seen or key == "Email":
            return
        seen.add(key)
        output.append(key)

    for header in master_headers:
        if header == "Email":
            continue
        if header in {"FirstName", "FullName", "AuthorName"}:
            continue
        maybe_add(header)

    for headers in existing_headers:
        for header in headers:
            maybe_add(str(header or "").strip())

    return output


def _master_row_to_queue_row(row: Dict[str, str], queue_headers: Sequence[str]) -> Dict[str, str]:
    queue_row = {header: "" for header in queue_headers}
    queue_row["Email"] = norm_email(row.get("Email", ""))
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
    for index, path in enumerate(sendgrid_paths, start=1):
        _, rows = _read_queue_rows(path)
        sendgrid_status.append({"name": f"SG{index}", "path": str(path), "count": len(rows)})

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
