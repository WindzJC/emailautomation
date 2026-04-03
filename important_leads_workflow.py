from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import settings
import runtime_control
from leads_workflow import iso_utc, load_state, save_state, timestamp_slug
from recipient_file_lock import lock_files
from send_shard import PROFILES, load_already_done
from sendgrid_hygiene import load_active_suppressed_emails, norm_email


IMPORTANT_DIR = settings.APP_ROOT / "_important"
MASTER_INPUT_PATH = IMPORTANT_DIR / "leadschecker.csv"
MASTER_OUTPUT_PATH = IMPORTANT_DIR / "leads.csv"
MASTER_REJECTED_PATH = IMPORTANT_DIR / "leads_rejected.csv"

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
)
FIRST_NAME_HEADER_CANDIDATES = (
    "firstname",
    "first_name",
    "first name",
    "name",
    "authorname",
    "author_name",
    "author",
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
CHECK_PREVIEW_ROWS = 8
DISPATCH_PREVIEW_ROWS = 8


def _normalize_header_key(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum())


def _strip_cell(value: object) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _trimmed_first_name(value: str) -> str:
    raw = _strip_cell(value)
    if not raw:
        return ""
    token = raw.split()[0]
    return re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", token) or token


def _pick_header(fieldnames: Sequence[str], candidates: Sequence[str]) -> str:
    normalized = {_normalize_header_key(name): name for name in fieldnames if name}
    for candidate in candidates:
        match = normalized.get(_normalize_header_key(candidate))
        if match:
            return match
    return ""


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:25])
    if not sample.strip():
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return "\t" if "\t" in sample else ","


def _read_csv_rows(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    raw_text = path.read_text(encoding="utf-8-sig", errors="replace") if path.exists() else ""
    if not raw_text.strip():
        return [], []
    delimiter = _sniff_delimiter(raw_text)
    reader = csv.DictReader(StringIO(raw_text), delimiter=delimiter)
    fieldnames = [str(name or "").lstrip("\ufeff").strip() for name in (reader.fieldnames or [])]
    rows: List[Dict[str, str]] = []
    for row in reader:
        cleaned = {field: _strip_cell(row.get(field, "")) for field in fieldnames}
        if any(value for value in cleaned.values()):
            rows.append(cleaned)
    return fieldnames, rows


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


def _detect_core_headers(fieldnames: Sequence[str]) -> Dict[str, str]:
    return {
        "Email": _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES),
        "FirstName": _pick_header(fieldnames, FIRST_NAME_HEADER_CANDIDATES),
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
    output_headers = ["FirstName", "Email"]
    used.update(output_headers)
    source_to_output: Dict[str, str] = {}

    first_source = core_headers.get("FirstName", "")
    email_source = core_headers.get("Email", "")
    book_source = core_headers.get("BookTitle", "")

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


def _normalize_email_cell(value: str) -> tuple[str, str, bool]:
    raw = _strip_cell(value)
    if not raw:
        return "", "invalid_email", False

    candidate_text = re.sub(r"^\s*mailto:\s*", "", raw, flags=re.IGNORECASE)
    matches = EMAIL_IN_TEXT_RE.findall(candidate_text)
    if len(matches) > 1:
        return "", "suspicious_multiple_emails", False

    if matches:
        candidate = matches[0]
    else:
        candidate = candidate_text

    candidate = candidate.strip().strip("<>()[]{}\"'")
    candidate = candidate.rstrip(".,;:!?")
    candidate = candidate.replace(" ", "").lower()

    if candidate.count("@") != 1:
        if SAFE_SPLIT_RE.search(raw):
            return "", "suspicious_multiple_emails", False
        return "", "invalid_email", False

    local, domain = candidate.split("@", 1)
    fixed = False
    fixed_domain = COMMON_DOMAIN_FIXES.get(domain, domain)
    if fixed_domain != domain:
        fixed = True
    candidate = f"{local}@{fixed_domain}"

    if not EMAIL_RE.match(candidate):
        return "", "invalid_email", fixed
    return candidate, "", fixed


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


def check_master_leads(
    input_path: Path = MASTER_INPUT_PATH,
    output_path: Path = MASTER_OUTPUT_PATH,
    rejected_path: Path = MASTER_REJECTED_PATH,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    report_dir: Path = STATE_DIR,
    persist_state: bool = True,
) -> Dict[str, object]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    fieldnames, rows = _read_csv_rows(input_path)
    core_headers = _detect_core_headers(fieldnames)
    if not core_headers["Email"]:
        raise ValueError(f"Could not detect an email column in {input_path.name}")

    output_headers, source_to_output = _master_output_headers(fieldnames, core_headers)
    blocked_emails, suppression_summary = _blocked_email_set(
        sendgrid_suppressions_path=sendgrid_suppressions_path,
        suppressed_path=suppressed_path,
        unsubscribed_path=unsubscribed_path,
    )

    kept_rows: List[Dict[str, str]] = []
    rejected_rows: List[Dict[str, str]] = []
    seen_emails: set[str] = set()
    reason_counts: Counter[str] = Counter()
    safe_fixes_applied = 0

    for raw_row in rows:
        normalized_row = {header: "" for header in output_headers}
        for source, target in source_to_output.items():
            normalized_row[target] = _strip_cell(raw_row.get(source, ""))

        if core_headers["FirstName"]:
            normalized_row["FirstName"] = _trimmed_first_name(raw_row.get(core_headers["FirstName"], ""))
        else:
            normalized_row["FirstName"] = ""

        email, email_reason, fixed = _normalize_email_cell(raw_row.get(core_headers["Email"], ""))
        normalized_row["Email"] = email
        if fixed:
            safe_fixes_applied += 1

        reason = ""
        if email_reason.startswith("suspicious_"):
            reason = email_reason
        elif not email:
            reason = email_reason or "invalid_email"
        elif email in blocked_emails:
            reason = "suppressed"
        elif email in seen_emails:
            reason = "duplicate_email"

        if reason:
            reason_counts[reason] += 1
            rejected_row = dict(normalized_row)
            rejected_row["Reason"] = reason
            rejected_rows.append(rejected_row)
            continue

        kept_rows.append(normalized_row)
        seen_emails.add(email)

    rejected_headers = list(output_headers) + ["Reason"]
    _write_csv_atomic(output_path, output_headers, kept_rows)
    _write_csv_atomic(rejected_path, rejected_headers, rejected_rows)

    duplicates_removed = int(reason_counts.get("duplicate_email", 0))
    invalid_removed = sum(
        int(reason_counts.get(key, 0))
        for key in ("invalid_email", "missing_email")
    )
    suppressed_removed = int(reason_counts.get("suppressed", 0))
    suspicious_flagged = sum(count for reason, count in reason_counts.items() if reason.startswith("suspicious_"))

    report = {
        "input_label": "_important/leadschecker.csv",
        "output_label": "_important/leads.csv",
        "rejected_label": "_important/leads_rejected.csv",
        "generated_at_utc": iso_utc(),
        "input_rows": len(rows),
        "cleaned_rows": len(kept_rows),
        "duplicates_removed": duplicates_removed,
        "invalid_removed": invalid_removed,
        "suppressed_removed": suppressed_removed,
        "suspicious_flagged": suspicious_flagged,
        "safe_fixes_applied": safe_fixes_applied,
        "output_fieldnames": output_headers,
        "output_preview_rows": _preview_rows(kept_rows, output_headers, CHECK_PREVIEW_ROWS),
        "rejected_preview_rows": _preview_rows(rejected_rows, rejected_headers, CHECK_PREVIEW_ROWS),
        "reason_counts": dict(reason_counts),
        "suppression_summary": suppression_summary,
    }

    report_path = report_dir / f"important_leads_check_{timestamp_slug()}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = dict(report)
    report_payload["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            if "AuthorName" in cleaned:
                cleaned["AuthorName"] = _strip_cell(cleaned.get("AuthorName", ""))
            rows.append(cleaned)
    return fieldnames, rows


def _sent_email_set(log_paths: Sequence[Path]) -> set[str]:
    sent: set[str] = set()
    for path in log_paths:
        sent |= load_already_done(path)
    return sent


def _queue_output_headers(existing_headers: Iterable[Sequence[str]], master_headers: Sequence[str]) -> List[str]:
    output = ["Email", "AuthorName"]
    seen = set(output)

    def maybe_add(value: str) -> None:
        key = "AuthorName" if value == "FirstName" else value
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

    return output


def _master_row_to_queue_row(row: Dict[str, str], queue_headers: Sequence[str]) -> Dict[str, str]:
    queue_row = {header: "" for header in queue_headers}
    queue_row["Email"] = norm_email(row.get("Email", ""))
    queue_row["AuthorName"] = _trimmed_first_name(row.get("FirstName", ""))
    for header in queue_headers:
        if header in {"Email", "AuthorName"}:
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
    require_stopped: bool = True,
    jc_queue_path: Path | None = None,
    sendgrid_queue_paths: Sequence[Path] | None = None,
    jc_log_path: Path | None = None,
    sendgrid_log_paths: Sequence[Path] | None = None,
    sendgrid_suppressions_path: Path = settings.SENDGRID_SUPPRESSIONS_PATH,
    suppressed_path: Path = settings.SUPPRESSED_PATH,
    unsubscribed_path: Path = settings.UNSUBSCRIBED_PATH,
    backup_root: Path = BACKUP_ROOT,
    report_dir: Path = STATE_DIR,
    persist_state: bool = True,
) -> Dict[str, object]:
    if not master_path.exists():
        raise FileNotFoundError(f"Master leads file not found: {master_path}")

    active_states = _active_sender_states() if require_stopped else {}
    if active_states:
        raise RuntimeError(f"Stop all senders before dispatching leads. Active: {', '.join(sorted(active_states))}")

    master_headers, master_rows = _read_csv_rows(master_path)
    if not master_headers:
        raise ValueError("Master leads file is empty.")
    if "Email" not in master_headers:
        raise ValueError("Master leads file must contain an Email column.")

    blocked_emails, _ = _blocked_email_set(
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

    sg_assign_cursor = 0
    added_astra_rows: List[Dict[str, str]] = []
    added_sendgrid_rows_by_index: List[List[Dict[str, str]]] = [[] for _ in sendgrid_paths]
    master_seen: set[str] = set()
    suppressed_skipped = 0
    duplicate_master_skipped = 0
    added_astra = 0
    added_sendgrid = 0
    skipped_astra_already_sent = 0
    skipped_astra_already_queued = 0
    skipped_sendgrid_already_sent = 0
    skipped_sendgrid_already_queued = 0
    skipped_both = 0
    outcome_counts: Counter[str] = Counter()

    for row in master_rows:
        email = norm_email(row.get("Email", ""))
        if not email:
            continue
        if email in master_seen:
            duplicate_master_skipped += 1
            continue
        master_seen.add(email)

        if email in blocked_emails:
            suppressed_skipped += 1
            continue

        normalized = {header: _strip_cell(row.get(header, "")) for header in master_headers}
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

        if added_to_astra and added_to_sendgrid:
            outcome_counts["added_astra_and_sendgrid"] += 1
        elif added_to_astra:
            outcome_counts["added_astra_only"] += 1
        elif added_to_sendgrid:
            outcome_counts["added_sendgrid_only"] += 1
        else:
            outcome_counts["skipped_both"] += 1
            skipped_both += 1

    queue_headers = _queue_output_headers(queue_headers_by_path.values(), master_headers)
    if "BookTitle" in master_headers and "BookTitle" not in queue_headers:
        queue_headers.append("BookTitle")

    new_rows_by_path: Dict[Path, List[Dict[str, str]]] = {path: list(rows) for path, rows in queue_rows_by_path.items()}
    new_rows_by_path[jc_path].extend(_master_row_to_queue_row(row, queue_headers) for row in added_astra_rows)
    for path, rows in zip(sendgrid_paths, added_sendgrid_rows_by_index):
        new_rows_by_path[path].extend(_master_row_to_queue_row(row, queue_headers) for row in rows)

    backup_dir = backup_root / f"dispatch_{timestamp_slug()}"
    with lock_files(queue_paths):
        _copy_queue_backups(queue_paths, backup_dir)
        for path in queue_paths:
            _write_csv_atomic(path, queue_headers, new_rows_by_path[path])

    final_queue_counts = {
        "jc": len(new_rows_by_path[jc_path]),
        "sg1": len(new_rows_by_path[sendgrid_paths[0]]),
        "sg2": len(new_rows_by_path[sendgrid_paths[1]]),
        "sg3": len(new_rows_by_path[sendgrid_paths[2]]),
        "sg4": len(new_rows_by_path[sendgrid_paths[3]]),
        "sg5": len(new_rows_by_path[sendgrid_paths[4]]),
    }

    report = {
        "generated_at_utc": iso_utc(),
        "master_label": "_important/leads.csv",
        "rejected_label": "_important/leads_rejected.csv",
        "backup_dir": str(backup_dir),
        "master_read": len(master_rows),
        "added_astra": added_astra,
        "skipped_astra_already_sent": skipped_astra_already_sent,
        "skipped_astra_already_queued": skipped_astra_already_queued,
        "added_sendgrid": added_sendgrid,
        "skipped_sendgrid_already_sent": skipped_sendgrid_already_sent,
        "skipped_sendgrid_already_queued": skipped_sendgrid_already_queued,
        "suppressed_skipped": suppressed_skipped,
        "duplicate_master_skipped": duplicate_master_skipped,
        "assigned_sg1": len(added_sendgrid_rows_by_index[0]),
        "assigned_sg2": len(added_sendgrid_rows_by_index[1]),
        "assigned_sg3": len(added_sendgrid_rows_by_index[2]),
        "assigned_sg4": len(added_sendgrid_rows_by_index[3]),
        "assigned_sg5": len(added_sendgrid_rows_by_index[4]),
        "skipped_both": skipped_both,
        "final_queue_counts": final_queue_counts,
        "queue_headers": queue_headers,
        "outcome_counts": dict(outcome_counts),
        "assigned_preview_rows": _preview_rows(
            [_master_row_to_queue_row(row, queue_headers) for row in (added_astra_rows + [row for bucket in added_sendgrid_rows_by_index for row in bucket])],
            queue_headers,
            DISPATCH_PREVIEW_ROWS,
        ),
    }

    report_path = report_dir / f"important_leads_dispatch_{timestamp_slug()}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = dict(report)
    report_payload["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    if persist_state:
        save_state(**{MASTER_DISPATCH_STATE_KEY: report})
    return report


def important_leads_status() -> Dict[str, object]:
    state = load_state()
    jc_path, sendgrid_paths, _, _ = _dispatch_profile_paths()
    jc_headers, jc_rows = _read_queue_rows(jc_path)
    sendgrid_status = []
    for index, path in enumerate(sendgrid_paths, start=1):
        _, rows = _read_queue_rows(path)
        sendgrid_status.append({"name": f"SG{index}", "path": str(path), "count": len(rows)})

    return {
        "important_input_label": "_important/leadschecker.csv",
        "important_output_label": "_important/leads.csv",
        "important_rejected_label": "_important/leads_rejected.csv",
        "latest_master_check": state.get(MASTER_CHECK_STATE_KEY, {}),
        "latest_dispatch": state.get(MASTER_DISPATCH_STATE_KEY, {}),
        "jc_queue": {
            "path": str(jc_path),
            "count": len(jc_rows),
            "fieldnames": jc_headers,
        },
        "sendgrid_queues": sendgrid_status,
    }
