from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import settings
from recipient_file_lock import lock_files
from send_shard import PROFILES, ROLE_LOCALPART_BLOCKLIST, is_role_recipient
from sendgrid_hygiene import domain_from_email, load_active_suppressed_emails, norm_email


ROOT = settings.APP_ROOT
UPLOADS_DIR = settings.UPLOADS_DIR
CLEANED_DIR = settings.CLEANED_DIR
REPORTS_DIR = settings.STATE_DIR
BACKUP_ROOT = settings.LEADS_BACKUP_ROOT
LEADS_STATE_PATH = settings.LEADS_STATE_PATH
LATEST_SHARD_REPORT_PATH = settings.LATEST_SHARD_REPORT_PATH
SENDGRID_SUPPRESSIONS_PATH = settings.SENDGRID_SUPPRESSIONS_PATH

CANONICAL_HEADERS = ["Email", "AuthorName", "BookTitle"]
PREVIEW_ROWS = 25
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

EMAIL_HEADER_CANDIDATES = (
    "email",
    "authoremail",
    "author_email",
    "e_mail",
    "e-mail",
    "mail",
    "address",
)
AUTHOR_HEADER_CANDIDATES = (
    "authorname",
    "author_name",
    "author",
    "name",
    "firstname",
    "first_name",
)
BOOK_HEADER_CANDIDATES = (
    "booktitle",
    "book_title",
    "title",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: Optional[datetime] = None) -> str:
    return (dt or utcnow()).replace(microsecond=0).isoformat()


def ensure_runtime_dirs() -> None:
    settings.ensure_dirs((UPLOADS_DIR, CLEANED_DIR, REPORTS_DIR, BACKUP_ROOT))


def normalize_header(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum())


def sanitize_filename(value: str) -> str:
    raw = Path(value or "").name or "upload.csv"
    cleaned = SAFE_FILENAME_RE.sub("_", raw).strip("._")
    return cleaned or "upload.csv"


def timestamp_slug(reference: Optional[datetime] = None) -> str:
    return (reference or utcnow()).strftime("%Y%m%d_%H%M%S")


def write_json_atomic(path: Path, payload: Dict[str, object]) -> None:
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
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)
    settings.secure_private_file(path)


def load_state() -> Dict[str, object]:
    if not LEADS_STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(LEADS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def save_state(**updates: object) -> Dict[str, object]:
    state = load_state()
    state.update(updates)
    write_json_atomic(LEADS_STATE_PATH, state)
    return state


def _pick_header(fieldnames: Sequence[str], candidates: Sequence[str]) -> str:
    normalized = {normalize_header(name): name for name in fieldnames if name}
    for candidate in candidates:
        match = normalized.get(normalize_header(candidate))
        if match:
            return match
    return ""


def detect_column_mapping(fieldnames: Sequence[str]) -> Dict[str, object]:
    mapping = {
        "email": _pick_header(fieldnames, EMAIL_HEADER_CANDIDATES),
        "author_name": _pick_header(fieldnames, AUTHOR_HEADER_CANDIDATES),
        "book_title": _pick_header(fieldnames, BOOK_HEADER_CANDIDATES),
    }
    return {
        "fieldnames": list(fieldnames),
        "mapping": mapping,
        "mapping_required": not bool(mapping["email"]),
    }


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:25])
    if not sample.strip():
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        if "\t" in first_line:
            return "\t"
        return ","


def _trim_preview(rows: Sequence[Dict[str, str]], fieldnames: Sequence[str], limit: int = PREVIEW_ROWS) -> List[Dict[str, str]]:
    preview: List[Dict[str, str]] = []
    for row in rows[:limit]:
        preview.append({field: str(row.get(field, "") or "") for field in fieldnames})
    return preview


def _load_csv_rows(path: Path) -> Dict[str, object]:
    raw_text = path.read_text(encoding="utf-8-sig", errors="replace") if path.exists() else ""
    if not raw_text.strip():
        return {
            "fieldnames": [],
            "rows": [],
            "delimiter": ",",
        }

    delimiter = sniff_delimiter(raw_text)
    reader = csv.DictReader(StringIO(raw_text), delimiter=delimiter)
    fieldnames = [str(name or "").lstrip("\ufeff") for name in (reader.fieldnames or [])]
    rows: List[Dict[str, str]] = []
    for row in reader:
        cleaned_row = {field: str(row.get(field, "") or "") for field in fieldnames}
        if any(str(value or "").strip() for value in cleaned_row.values()):
            rows.append(cleaned_row)
    return {
        "fieldnames": fieldnames,
        "rows": rows,
        "delimiter": delimiter,
    }


def preview_uploaded_csv(path: Path) -> Dict[str, object]:
    loaded = _load_csv_rows(path)
    fieldnames = list(loaded["fieldnames"])
    rows = list(loaded["rows"])
    detection = detect_column_mapping(fieldnames)
    return {
        "saved_filename": path.name,
        "saved_path": str(path),
        "fieldnames": fieldnames,
        "row_count": len(rows),
        "preview_rows": _trim_preview(rows, fieldnames),
        "mapping": detection["mapping"],
        "mapping_required": detection["mapping_required"],
    }


def save_uploaded_csv(original_filename: str, content: bytes) -> Dict[str, object]:
    ensure_runtime_dirs()
    filename = f"leads_{timestamp_slug()}_{sanitize_filename(original_filename)}"
    path = UPLOADS_DIR / filename
    path.write_bytes(content)
    settings.secure_private_file(path)
    preview = preview_uploaded_csv(path)
    preview["original_filename"] = original_filename
    preview["uploaded_at_utc"] = iso_utc()
    save_state(latest_upload=preview)
    return preview


def _resolve_artifact_path(base_dir: Path, filename: str) -> Path:
    candidate = (base_dir / Path(filename).name).resolve()
    base = base_dir.resolve()
    if candidate.parent != base or not candidate.exists():
        raise FileNotFoundError(f"Artifact not found: {filename}")
    return candidate


def _normalize_mapping(fieldnames: Sequence[str], requested_mapping: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    detection = detect_column_mapping(fieldnames)["mapping"]
    mapping = {
        "email": str((requested_mapping or {}).get("email") or detection["email"] or "").strip(),
        "author_name": str((requested_mapping or {}).get("author_name") or detection["author_name"] or "").strip(),
        "book_title": str((requested_mapping or {}).get("book_title") or detection["book_title"] or "").strip(),
    }
    valid_fields = set(fieldnames)
    for key, value in list(mapping.items()):
        if value and value not in valid_fields:
            raise ValueError(f"Selected column does not exist for {key}: {value}")
    if not mapping["email"]:
        raise ValueError("An email column must be selected before cleaning.")
    return mapping


def _clean_name_token(value: str) -> str:
    return re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", (value or "").strip())


def first_name_only(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    token = _clean_name_token(raw.split()[0])
    return token or raw.split()[0].strip()


def collect_canary_emails() -> List[str]:
    seen: List[str] = []
    for _, cfg in PROFILES.items():
        if str(cfg.get("provider") or "") != "sendgrid":
            continue
        email = norm_email(str(cfg.get("always_send") or ""))
        if email and email not in seen:
            seen.append(email)
    return seen


def _role_blocklist() -> set[str]:
    return set(ROLE_LOCALPART_BLOCKLIST)


def build_clean_row(raw_row: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, str]:
    email = norm_email(raw_row.get(mapping["email"], ""))
    author_name = first_name_only(raw_row.get(mapping["author_name"], "")) if mapping.get("author_name") else ""
    book_title = str(raw_row.get(mapping["book_title"], "") or "").strip() if mapping.get("book_title") else ""
    return {
        "Email": email,
        "AuthorName": author_name,
        "BookTitle": book_title,
    }


def _write_csv_rows(path: Path, rows: Iterable[Dict[str, str]], fieldnames: Sequence[str]) -> None:
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
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(row_list)
    tmp_path.replace(path)
    settings.secure_private_file(path)


def clean_uploaded_leads(
    upload_filename: str,
    mapping: Optional[Dict[str, str]] = None,
    remove_invalid_emails: bool = True,
    dedupe_by_email: bool = True,
    remove_suppressed: bool = True,
    drop_role_emails: bool = False,
    exclude_domains: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    ensure_runtime_dirs()
    upload_path = _resolve_artifact_path(UPLOADS_DIR, upload_filename)
    loaded = _load_csv_rows(upload_path)
    fieldnames = list(loaded["fieldnames"])
    rows = list(loaded["rows"])
    resolved_mapping = _normalize_mapping(fieldnames, mapping)
    exclude_domain_set = {str(item or "").strip().lower() for item in (exclude_domains or []) if str(item or "").strip()}
    canary_emails = set(collect_canary_emails())
    suppressed_emails = set()
    suppression_summary: Dict[str, object] = {}
    if remove_suppressed:
        suppressed_emails, suppression_summary = load_active_suppressed_emails(SENDGRID_SUPPRESSIONS_PATH)
        suppressed_emails -= canary_emails

    seen: set[str] = set()
    kept_rows: List[Dict[str, str]] = []
    reason_counts: Counter[str] = Counter()
    removed_domains: Counter[str] = Counter()
    kept_domains: Counter[str] = Counter()
    role_blocklist = _role_blocklist()

    for raw_row in rows:
        clean_row = build_clean_row(raw_row, resolved_mapping)
        email = clean_row["Email"]
        domain = domain_from_email(email)
        is_canary = email in canary_emails
        reason = ""

        if not email:
            reason = "missing_email"
        elif not is_canary and remove_invalid_emails and not EMAIL_RE.match(email):
            reason = "invalid_email"
        elif not is_canary and domain and domain in exclude_domain_set:
            reason = "excluded_domain"
        elif not is_canary and drop_role_emails and is_role_recipient(email, role_blocklist):
            reason = "role_email"
        elif not is_canary and remove_suppressed and email in suppressed_emails:
            reason = "suppressed"
        elif not is_canary and dedupe_by_email and email in seen:
            reason = "duplicate_email"

        if reason:
            reason_counts[reason] += 1
            if domain:
                removed_domains[domain] += 1
            continue

        kept_rows.append(clean_row)
        if domain:
            kept_domains[domain] += 1
        if email and dedupe_by_email and not is_canary:
            seen.add(email)

    cleaned_filename = f"cleaned_{timestamp_slug()}.csv"
    cleaned_path = CLEANED_DIR / cleaned_filename
    _write_csv_rows(cleaned_path, kept_rows, CANONICAL_HEADERS)

    clean_report = {
        "source_upload_filename": upload_path.name,
        "cleaned_filename": cleaned_filename,
        "cleaned_path": str(cleaned_path),
        "generated_at_utc": iso_utc(),
        "input_rows": len(rows),
        "output_rows": len(kept_rows),
        "removed_rows": len(rows) - len(kept_rows),
        "mapping": resolved_mapping,
        "reason_counts": dict(reason_counts),
        "removed_domains_top": [
            {"domain": domain, "count": count}
            for domain, count in removed_domains.most_common(10)
        ],
        "kept_domains_top": [
            {"domain": domain, "count": count}
            for domain, count in kept_domains.most_common(10)
        ],
        "suppression_summary": {
            "total_perm": int(suppression_summary.get("total_perm", 0) or 0),
            "total_temp_active": int(suppression_summary.get("total_temp_active", 0) or 0),
        },
        "protected_canaries": sorted(canary_emails),
        "preview_rows": _trim_preview(kept_rows, CANONICAL_HEADERS),
    }

    report_path = REPORTS_DIR / f"clean_report_{timestamp_slug()}.json"
    write_json_atomic(report_path, clean_report)
    clean_report["report_path"] = str(report_path)

    latest_upload = load_state().get("latest_upload", {})
    save_state(
        latest_cleaned={
            "filename": cleaned_filename,
            "path": str(cleaned_path),
            "generated_at_utc": clean_report["generated_at_utc"],
            "source_upload_filename": upload_path.name,
            "source_original_filename": str((latest_upload or {}).get("original_filename") or ""),
            "report_path": str(report_path),
            "input_rows": clean_report["input_rows"],
            "output_rows": clean_report["output_rows"],
            "removed_rows": clean_report["removed_rows"],
            "reason_counts": clean_report["reason_counts"],
            "preview_rows": clean_report["preview_rows"],
        }
    )
    return clean_report


def _load_cleaned_rows(cleaned_filename: str) -> List[Dict[str, str]]:
    cleaned_path = _resolve_artifact_path(CLEANED_DIR, cleaned_filename)
    with cleaned_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [
            {
                "Email": norm_email(row.get("Email") or ""),
                "AuthorName": str(row.get("AuthorName") or "").strip(),
                "BookTitle": str(row.get("BookTitle") or "").strip(),
            }
            for row in reader
            if any(str(value or "").strip() for value in row.values())
        ]


def _sendgrid_profile_names() -> List[str]:
    return [
        name
        for name, cfg in PROFILES.items()
        if str(cfg.get("provider") or "") == "sendgrid"
    ]


def shard_file_paths(shard_count: int) -> List[Path]:
    profiles = _sendgrid_profile_names()
    if shard_count < 1 or shard_count > len(profiles):
        raise ValueError(f"shard_count must be between 1 and {len(profiles)}")
    return [settings.shard_path(str(PROFILES[name]["csv"])) for name in profiles[:shard_count]]


def _load_existing_canary_rows(paths: Sequence[Path]) -> Dict[str, Dict[str, str]]:
    rows_by_email: Dict[str, Dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                email = norm_email(row.get("Email") or row.get("email") or "")
                if not email or email in rows_by_email:
                    continue
                rows_by_email[email] = {
                    "Email": email,
                    "AuthorName": str(row.get("AuthorName") or row.get("name") or "").strip(),
                    "BookTitle": str(row.get("BookTitle") or row.get("title") or "").strip(),
                }
    return rows_by_email


def canary_rows_for_shards(paths: Sequence[Path]) -> List[Optional[Dict[str, str]]]:
    existing = _load_existing_canary_rows(paths)
    rows: List[Optional[Dict[str, str]]] = []
    for profile_name in _sendgrid_profile_names()[: len(paths)]:
        email = norm_email(str(PROFILES[profile_name].get("always_send") or ""))
        if not email:
            rows.append(None)
            continue
        row = dict(existing.get(email, {"Email": email, "AuthorName": "", "BookTitle": ""}))
        row["Email"] = email
        rows.append(row)
    return rows


def _round_robin_distribute(rows: Sequence[Dict[str, str]], shard_count: int) -> List[List[Dict[str, str]]]:
    buckets: List[List[Dict[str, str]]] = [[] for _ in range(shard_count)]
    for index, row in enumerate(rows):
        buckets[index % shard_count].append(row)
    return buckets


def _domain_balanced_distribute(rows: Sequence[Dict[str, str]], shard_count: int) -> List[List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[domain_from_email(row.get("Email", "")) or "(unknown)"].append(row)

    buckets: List[List[Dict[str, str]]] = [[] for _ in range(shard_count)]
    bucket_sizes = [0] * shard_count
    bucket_cursor = 0

    for _, group_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        local_cursor = bucket_cursor
        for row in group_rows:
            order = list(range(local_cursor, shard_count)) + list(range(0, local_cursor))
            target = min(order, key=lambda idx: (bucket_sizes[idx], idx))
            buckets[target].append(row)
            bucket_sizes[target] += 1
            local_cursor = (target + 1) % shard_count
        bucket_cursor = (bucket_cursor + 1) % shard_count
    return buckets


def _shard_domain_summary(rows: Sequence[Dict[str, str]]) -> List[Dict[str, object]]:
    counter = Counter(domain_from_email(row.get("Email", "")) for row in rows if row.get("Email"))
    return [
        {"domain": domain, "count": count}
        for domain, count in counter.most_common(5)
        if domain
    ]


def _copy_existing_shards(paths: Sequence[Path], backup_root: Path) -> None:
    backup_root.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            shutil.copy2(path, backup_root / path.name)


def _load_shard_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [
            {
                "Email": norm_email(row.get("Email") or ""),
                "AuthorName": str(row.get("AuthorName") or "").strip(),
                "BookTitle": str(row.get("BookTitle") or "").strip(),
            }
            for row in reader
            if norm_email(row.get("Email") or "")
        ]


def _build_shard_plan(
    cleaned_filename: str,
    shard_count: int = 5,
    strategy: str = "domain_balanced",
) -> Dict[str, object]:
    ensure_runtime_dirs()
    if strategy not in {"domain_balanced", "simple_round_robin"}:
        raise ValueError("strategy must be domain_balanced or simple_round_robin")

    _resolve_artifact_path(CLEANED_DIR, cleaned_filename)
    shard_paths = shard_file_paths(shard_count)
    canary_rows = canary_rows_for_shards(shard_paths)
    canary_emails = {row["Email"] for row in canary_rows if row and row.get("Email")}

    all_rows = _load_cleaned_rows(cleaned_filename)
    distributable_rows = [row for row in all_rows if row.get("Email") and row["Email"] not in canary_emails]

    if strategy == "domain_balanced":
        buckets = _domain_balanced_distribute(distributable_rows, shard_count)
    else:
        buckets = _round_robin_distribute(distributable_rows, shard_count)

    state = load_state()
    latest_upload = state.get("latest_upload", {})
    latest_cleaned = state.get("latest_cleaned", {})
    clean_summary = {}
    if str((latest_cleaned or {}).get("filename") or "") == cleaned_filename:
        clean_summary = {
            "input_rows": int(latest_cleaned.get("input_rows", 0) or 0),
            "output_rows": int(latest_cleaned.get("output_rows", 0) or len(all_rows)),
            "removed_rows": int(latest_cleaned.get("removed_rows", 0) or 0),
            "reason_counts": dict(latest_cleaned.get("reason_counts", {}) or {}),
        }
    else:
        clean_summary = {
            "input_rows": len(all_rows),
            "output_rows": len(all_rows),
            "removed_rows": 0,
            "reason_counts": {},
        }

    per_shard = []
    write_rows_by_index: List[List[Dict[str, str]]] = []
    for index, shard_path in enumerate(shard_paths):
        current_rows = _load_shard_rows(shard_path)
        shard_rows: List[Dict[str, str]] = []
        canary_row = canary_rows[index]
        if canary_row:
            shard_rows.append(dict(canary_row))
        shard_rows.extend(dict(row) for row in buckets[index])
        write_rows_by_index.append(shard_rows)
        per_shard.append(
            {
                "name": shard_path.name,
                "path": str(shard_path),
                "current_count": len(current_rows),
                "count": len(shard_rows),
                "delta": len(shard_rows) - len(current_rows),
                "top_domains": _shard_domain_summary(shard_rows),
                "contains_canary": bool(canary_row),
            }
        )

    return {
        "generated_at_utc": iso_utc(),
        "preview_only": True,
        "source_upload_filename": str((latest_upload or {}).get("saved_filename") or ""),
        "source_original_filename": str((latest_upload or {}).get("original_filename") or ""),
        "source_cleaned_filename": cleaned_filename,
        "strategy": strategy,
        "shard_count": shard_count,
        "input_rows": len(all_rows),
        "distributable_rows": len(distributable_rows),
        "canary_rows_injected": sum(1 for row in canary_rows if row),
        "canary_present": all(bool(row) for row in canary_rows),
        "per_shard": per_shard,
        "total_rows": sum(int(item["count"]) for item in per_shard),
        "clean_summary": clean_summary,
        "_shard_paths": shard_paths,
        "_write_rows": write_rows_by_index,
    }


def preview_shard_cleaned_leads(
    cleaned_filename: str,
    shard_count: int = 5,
    strategy: str = "domain_balanced",
) -> Dict[str, object]:
    plan = _build_shard_plan(cleaned_filename, shard_count=shard_count, strategy=strategy)
    return {key: value for key, value in plan.items() if not str(key).startswith("_")}


def shard_cleaned_leads(
    cleaned_filename: str,
    shard_count: int = 5,
    strategy: str = "domain_balanced",
) -> Dict[str, object]:
    plan = _build_shard_plan(cleaned_filename, shard_count=shard_count, strategy=strategy)
    timestamp = timestamp_slug()
    backup_dir = BACKUP_ROOT / timestamp

    shard_paths = list(plan["_shard_paths"])
    with lock_files(shard_paths):
        _copy_existing_shards(shard_paths, backup_dir)
        for shard_path, shard_rows in zip(shard_paths, plan["_write_rows"]):
            _write_csv_rows(shard_path, shard_rows, CANONICAL_HEADERS)

    report = {key: value for key, value in plan.items() if not str(key).startswith("_")}
    report["preview_only"] = False
    report["generated_at_utc"] = iso_utc()
    report["backup_dir"] = str(backup_dir)
    report_path = REPORTS_DIR / f"shard_report_{timestamp}.json"
    write_json_atomic(report_path, report)
    write_json_atomic(LATEST_SHARD_REPORT_PATH, report)
    report["report_path"] = str(report_path)

    latest_cleaned = load_state().get("latest_cleaned", {})
    save_state(
        latest_cleaned=latest_cleaned,
        latest_shard_report={
            "report_path": str(report_path),
            "generated_at_utc": report["generated_at_utc"],
            "source_upload_filename": report["source_upload_filename"],
            "source_original_filename": report["source_original_filename"],
            "source_cleaned_filename": cleaned_filename,
            "strategy": strategy,
            "backup_dir": str(backup_dir),
            "per_shard": report["per_shard"],
            "total_rows": report["total_rows"],
        },
    )
    return report


def shard_status() -> Dict[str, object]:
    ensure_runtime_dirs()
    shard_paths = shard_file_paths(len(_sendgrid_profile_names()))
    shards = []
    for shard_path in shard_paths:
        if not shard_path.exists():
            shards.append(
                {
                    "name": shard_path.name,
                    "path": str(shard_path),
                    "count": 0,
                    "top_domains": [],
                    "last_updated_utc": "",
                }
            )
            continue
        with shard_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = [
                {
                    "Email": norm_email(row.get("Email") or ""),
                }
                for row in reader
                if norm_email(row.get("Email") or "")
            ]
        last_updated = datetime.fromtimestamp(shard_path.stat().st_mtime, tz=timezone.utc)
        shards.append(
            {
                "name": shard_path.name,
                "path": str(shard_path),
                "count": len(rows),
                "top_domains": _shard_domain_summary(rows),
                "last_updated_utc": iso_utc(last_updated),
            }
        )

    state = load_state()
    latest_report_path = str((state.get("latest_shard_report") or {}).get("report_path") or "")
    latest_report = {}
    if latest_report_path:
        candidate = Path(latest_report_path)
        if candidate.exists():
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                latest_report = raw if isinstance(raw, dict) else {}
            except Exception:
                latest_report = {}

    latest_updated = max(
        [item["last_updated_utc"] for item in shards if item["last_updated_utc"]],
        default="",
    )
    return {
        "generated_at_utc": iso_utc(),
        "current_shards": shards,
        "total_rows": sum(int(item["count"]) for item in shards),
        "last_updated_utc": latest_updated,
        "latest_upload": state.get("latest_upload", {}),
        "latest_cleaned": state.get("latest_cleaned", {}),
        "latest_shard_report": state.get("latest_shard_report", {}),
        "latest_shard_report_summary": latest_report,
    }
