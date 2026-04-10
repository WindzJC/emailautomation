from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import parse_qs, unquote, urlparse

import requests
from email_validator import EmailNotValidError, EmailSyntaxError, EmailUndeliverableError, validate_email

import settings
from leads_workflow import iso_utc, load_state, save_state, timestamp_slug, write_json_atomic
from sendgrid_hygiene import norm_email


IMPORTANT_DIR = settings.APP_ROOT / "_important"
DEFAULT_INPUT_PATH = IMPORTANT_DIR / "leads.csv"
DEFAULT_VERIFIED_PATH = IMPORTANT_DIR / "leads_verified.csv"
DEFAULT_REJECTED_PATH = IMPORTANT_DIR / "leads_verify_rejected.csv"
DEFAULT_QUARANTINE_PATH = IMPORTANT_DIR / "leads_quarantine.csv"

VERIFY_STATE_PATH = settings.STATE_DIR / "important_leads_verify_state.json"
VERIFY_STATE_KEY = "latest_lead_verify"
VERIFY_PATHS_STATE_KEY = "important_leads_verify_paths"
VERIFY_CHECKPOINT_ROWS = max(1, int(os.environ.get("IMPORTANT_LEADS_VERIFY_CHECKPOINT_ROWS", "25") or 25))
VERIFY_AUDIT_HEADERS = ("Status", "VerificationReason", "VerificationEvidence", "VerifiedAtUtc")

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
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


def _save_checkpoint_state(payload: dict[str, object]) -> None:
    write_json_atomic(VERIFY_STATE_PATH, payload)


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


def important_leads_verify_status() -> dict[str, object]:
    state = load_state()
    checkpoint = _load_checkpoint_state()
    paths = important_leads_verify_path_state()
    latest_verify = state.get(VERIFY_STATE_KEY, {})
    if not isinstance(latest_verify, dict):
        latest_verify = {}
    return {
        "important_verify_input_label": paths["input_path"],
        "important_verify_keep_label": paths["verified_path"],
        "important_verify_rejected_label": paths["rejected_path"],
        "important_verify_quarantine_label": paths["quarantine_path"],
        "latest_lead_verify": latest_verify,
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


def _build_evidence_queries(full_name: str, first_name: str, email: str, book_title: str) -> list[str]:
    queries: list[str] = []
    if full_name and email:
        queries.extend([
            f"\"{full_name}\" \"{email}\"",
            f"\"{email}\" \"{full_name}\"",
        ])
    elif full_name:
        queries.append(f"\"{full_name}\"")
    if first_name and email and first_name.lower() not in {full_name.split()[0].lower() if full_name else ""}:
        queries.append(f"\"{first_name}\" \"{email}\"")
    if book_title and full_name:
        queries.append(f"\"{full_name}\" \"{book_title}\"")
    if email:
        queries.append(f"\"{email}\"")
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
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; EmailAutomationVerify/1.0)",
    }

    def searcher(query: str) -> list[object]:
        try:
            response = requests.get(
                "https://duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
                timeout=timeout_seconds,
            )
        except Exception:
            return []
        if not response.ok:
            return []

        results: list[object] = []
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
        return results

    return searcher


def _default_fetcher_factory(timeout_seconds: int) -> Callable[[str], object]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; EmailAutomationVerify/1.0)",
    }

    def fetcher(url: str) -> object:
        try:
            response = requests.get(url, headers=headers, timeout=timeout_seconds)
        except Exception as exc:
            return {"url": url, "error": str(exc), "text": ""}
        return {
            "url": url,
            "final_url": str(response.url or url),
            "status_code": int(response.status_code),
            "text": response.text or "",
        }

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

    evidence_text, evidence_emails = _evidence_snapshot(
        searcher=searcher,
        fetcher=fetcher,
        queries=queries,
        max_pages_per_lead=max(1, max_pages_per_lead),
        timeout_seconds=max(1, timeout_seconds),
        retries=max(0, retries),
    )
    normalized_evidence = _normalize(evidence_text)
    full_name_norm = _normalize(full_name)
    first_name_norm = _normalize(first_name)
    email_norm = _normalize(email)
    full_name_present = bool(full_name_norm and full_name_norm in normalized_evidence)
    first_name_present = bool(first_name_norm and first_name_norm in normalized_evidence)
    email_present = bool(email_norm and email_norm in normalized_evidence)
    other_email_present = any(found != email_norm for found in evidence_emails if found)

    if other_email_present and not email_present:
        return "REJECT", "PROOF_MISMATCH", "Public evidence showed a different email address."
    if email_present and full_name_present:
        if allow_social_proof:
            return "KEEP", "FULL_NAME_AND_EMAIL_MATCH", "Public evidence contained the full name and email."
        return "QUARANTINE", "PROOF_POLICY_BLOCKED", "Proof policy blocked the match."
    if email_present and not full_name_present:
        if first_name_present and not allow_social_proof:
            return "QUARANTINE", "FIRST_NAME_ONLY", "First name proof is too weak."
        return "QUARANTINE", "INSUFFICIENT_PROOF", "Email was visible, but the full name was not proven."
    if full_name_present and not email_present:
        return "QUARANTINE", "INSUFFICIENT_PROOF", "Full name was visible, but the email was not proven."
    if first_name_present:
        return "QUARANTINE", "FIRST_NAME_ONLY", "First name proof is too weak."
    if evidence_emails:
        return "REJECT", "PROOF_MISMATCH", "Public evidence showed a different email address."
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
) -> dict[str, object]:
    del max_workers, respect_robots

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

    verify_searcher = searcher or _default_searcher_factory(timeout_seconds)
    verify_fetcher = fetcher or _default_fetcher_factory(timeout_seconds)
    checkpoint = _load_checkpoint_state()
    input_fingerprint = _hash_input_file(input_path)
    resume_ok = (
        str(checkpoint.get("input_fingerprint") or "") == input_fingerprint
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

    for chunk_start in range(start_index, len(input_rows), checkpoint_rows):
        chunk_end = min(chunk_start + checkpoint_rows, len(input_rows))
        chunk_changed = False
        for index in range(chunk_start, chunk_end):
            row = input_rows[index]
            signature = _row_signature(row, base_headers)
            if signature in verified_signatures or signature in rejected_signatures or signature in quarantine_signatures:
                continue
            status, reason, evidence = _classify_row(
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
            chunk_changed = True

        _csv_atomic_write(verified_path, verified_headers, verified_rows)
        _csv_atomic_write(rejected_path, rejected_headers, rejected_rows)
        _csv_atomic_write(quarantine_path, quarantine_headers, quarantine_rows)

        checkpoint_payload = {
            "input_path": str(input_path),
            "input_fingerprint": input_fingerprint,
            "verified_path": str(verified_path),
            "rejected_path": str(rejected_path),
            "quarantine_path": str(quarantine_path),
            "base_headers": list(base_headers),
            "next_row_index": chunk_end,
            "total_input_rows": len(input_rows),
            "completed": chunk_end >= len(input_rows),
            "resume_supported": True,
            "updated_at_utc": iso_utc(),
            "last_chunk_changed": chunk_changed,
        }
        if persist_state:
            _save_checkpoint_state(checkpoint_payload)

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
        "reason_counts": dict(reason_counts),
        "keep_preview_rows": _derive_preview(verified_rows),
        "reject_preview_rows": _derive_preview(rejected_rows),
        "quarantine_preview_rows": _derive_preview(quarantine_rows),
        "resume_supported": True,
        "checkpoint_path": str(VERIFY_STATE_PATH),
        "checkpoint_next_row_index": len(input_rows),
        "checkpoint_total_input_rows": len(input_rows),
        "checkpoint_completed": True,
        "checkpoint_input_fingerprint": input_fingerprint,
    }
    report_path = settings.STATE_DIR / f"important_leads_verify_{timestamp_slug()}.json"
    write_json_atomic(report_path, report)
    report["report_path"] = str(report_path)

    if persist_state:
        _save_checkpoint_state(
            {
                "input_path": str(input_path),
                "input_fingerprint": input_fingerprint,
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

    return report
