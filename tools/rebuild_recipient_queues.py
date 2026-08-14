#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import settings


QUEUE_FILENAMES = (
    "recipients_private_jc.csv",
    "recipients_sendgrid_1.csv",
    "recipients_sendgrid_2.csv",
    "recipients_sendgrid_3.csv",
    "recipients_sendgrid_4.csv",
    "recipients_sendgrid_5.csv",
)
ACTIVE_CAMPAIGN_MANIFEST_NAME = "active_campaign_snapshot.json"
SENDGRID_QUEUE_FILENAMES = tuple(name for name in QUEUE_FILENAMES if name.startswith("recipients_sendgrid_"))
DEFAULT_LIVE_QUEUE_DIR = settings.APP_ROOT
SENDGRID_LOG_FILENAMES = (
    "sendgrid_annette_log.csv",
    "sendgrid_jordan_log.csv",
    "sendgrid_jodi_log.csv",
    "sendgrid_alison_log.csv",
    "sendgrid_fiorela_log.csv",
)
SENDGRID_DOMAIN_LOG_FILENAMES = (
    "sendgrid_domain_log.csv",
)
SENDGRID_REQUIRED_HEADERS = ("Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle")
EMAIL_HEADER_CANDIDATES = ("email", "authoremail", "author_email", "e_mail", "e-mail", "mail", "address")
FIRST_NAME_CANDIDATES = ("firstname", "first_name", "first name", "authorname", "author_name", "author")
TRIAGE_REJECT_REASON_HEADERS = ("VerificationReason", "reject_code", "RejectReason", "Reason", "Status")
RECONTACT_COLD_CAMPAIGN_TYPE = "recontact_cold"
RECONTACT_COLD_ALLOWED_TRIAGE_REJECT_REASONS = {
    "MISSING_FULL_NAME",
    "MISSING_USABLE_PERSON_NAME",
    "WEAK_FIRST_NAME",
    "WEAK_FULL_NAME",
}
RECONTACT_BLOCKED_REJECT_OVERLAP_EXPORT = settings.APP_ROOT / "_important" / "current_recontact_blocked_reject_overlap.csv"
EMAIL_SYNTAX_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BRACE_PLACEHOLDER_TOKEN_RE = re.compile(r"{([A-Za-z][A-Za-z0-9_]*)}")
SQUARE_PLACEHOLDER_TOKEN_RE = re.compile(r"\[([^\[\]\r\n]+)\]")
ANGLE_PLACEHOLDER_TOKEN_RE = re.compile(r"<<([^<>\r\n]+)>>")
PLACEHOLDER_LIKE_TOKEN_RE = re.compile(r"{[A-Za-z][A-Za-z0-9_]*}|\[[^\[\]\r\n]+\]|<<[^<>\r\n]+>>")
RENDER_NORMALIZED_FIELDS = ("FirstName", "AuthorName", "BookTitle", "PersonalizedOpeningLine")


def normalize_header(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def find_header(headers: Sequence[str], candidates: Sequence[str]) -> str | None:
    normalized = {normalize_header(header): header for header in headers if str(header or "").strip()}
    for candidate in candidates:
        match = normalized.get(normalize_header(candidate))
        if match:
            return match
    return None


def norm_email(value: object) -> str:
    return str(value or "").strip().lower()


def placeholder_like_tokens(value: object) -> List[str]:
    return PLACEHOLDER_LIKE_TOKEN_RE.findall(str(value or ""))


def normalize_render_field_value(value: object) -> Tuple[str, List[str]]:
    raw = str(value or "").strip()
    notes: List[str] = []
    if not raw:
        return "", notes

    cleaned = BRACE_PLACEHOLDER_TOKEN_RE.sub(lambda match: match.group(1), raw)
    if cleaned != raw:
        notes.append("removed_brace_placeholder_punctuation")

    before_square = cleaned
    cleaned = SQUARE_PLACEHOLDER_TOKEN_RE.sub(lambda match: f"({match.group(1).strip()})", cleaned)
    if cleaned != before_square:
        notes.append("converted_square_brackets_to_parentheses")

    before_angle = cleaned
    cleaned = ANGLE_PLACEHOLDER_TOKEN_RE.sub(lambda match: match.group(1).strip(), cleaned)
    if cleaned != before_angle:
        notes.append("removed_angle_placeholder_punctuation")

    return cleaned.strip(), notes


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists() or path.stat().st_size <= 0:
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv_atomic(path: Path, headers: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
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
        writer = csv.DictWriter(handle, fieldnames=list(headers), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)
    settings.secure_private_file(path)


def email_set(path: Path) -> set[str]:
    headers, rows = read_csv(path)
    email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
    if not email_header:
        return set()
    return {email for email in (norm_email(row.get(email_header)) for row in rows) if email}


def sent_email_set(path: Path) -> set[str]:
    headers, rows = read_csv(path)
    email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
    status_header = find_header(headers, ("status", "event", "result"))
    info_header = find_header(headers, ("info", "details", "message"))
    if not email_header:
        return set()
    sent: set[str] = set()
    for row in rows:
        if status_header:
            status = str(row.get(status_header) or "").strip().upper()
            info = str(row.get(info_header or "") or "").strip().lower()
            if status != "SENT" and not (status == "ATTEMPT" and "outcome=sent" in info):
                continue
        email = norm_email(row.get(email_header))
        if email:
            sent.add(email)
    return sent


def _queue_profile_name(path: Path) -> str:
    name = path.stem
    if name.startswith("recipients_"):
        return name.removeprefix("recipients_")
    return name


def _reject_reason(row: Dict[str, str]) -> str:
    for header in TRIAGE_REJECT_REASON_HEADERS:
        value = str(row.get(header) or "").strip()
        if value:
            return value
    return ""


def _reject_reason_summary(row: Dict[str, str]) -> str:
    parts = []
    for header in ("Status", "VerificationReason", "TriageWarning", "KeepReason", "VerificationEvidence"):
        value = str(row.get(header) or "").strip()
        if value:
            parts.append(f"{header}={value}")
    return "; ".join(parts)


def triaged_reject_rows_by_email(path: Path) -> Dict[str, List[Dict[str, str]]]:
    headers, rows = read_csv(path)
    email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
    if not email_header:
        return {}
    by_email: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        email = norm_email(row.get(email_header))
        if email:
            by_email.setdefault(email, []).append(row)
    return by_email


def _recontact_reject_overlap_allowed(rows: Sequence[Dict[str, str]]) -> bool:
    if not rows:
        return False
    reasons = {_reject_reason(row) for row in rows}
    return bool(reasons) and reasons <= RECONTACT_COLD_ALLOWED_TRIAGE_REJECT_REASONS


def _write_recontact_blocked_reject_overlap_export(
    *,
    path: Path,
    blocked_emails: Iterable[str],
    planned_profiles_by_email: Dict[str, set[str]],
    reject_rows_by_email: Dict[str, List[Dict[str, str]]],
    campaign_type: str,
    triaged_reject_path: Path,
) -> None:
    rows: List[Dict[str, str]] = []
    for email in sorted(set(blocked_emails)):
        reject_rows = reject_rows_by_email.get(email) or [{}]
        first = reject_rows[0]
        rows.append(
            {
                "Email": email,
                "PlannedProfiles": ",".join(sorted(planned_profiles_by_email.get(email) or set())),
                "RejectReason": _reject_reason_summary(first),
                "AuthorName": str(first.get("AuthorName") or first.get("FullName") or first.get("FirstName") or "").strip(),
                "BookTitle": str(first.get("BookTitle") or "").strip(),
                "CampaignType": campaign_type,
                "Source": str(triaged_reject_path),
            }
        )
    write_csv_atomic(
        path,
        ["Email", "PlannedProfiles", "RejectReason", "AuthorName", "BookTitle", "CampaignType", "Source"],
        rows,
    )


def row_count(path: Path) -> int:
    _headers, rows = read_csv(path)
    return len(rows)


def set_fingerprint(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(set(values)):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


class QueueSafetyScanCache:
    """Per-report-build cache for stable, read-only queue-safety CSV facts.

    The dashboard renders combined, SendGrid, and Private JC safety views from
    heavily overlapping files.  Without a shared cache, each view reparses the
    same queues and source CSVs.  This cache is intentionally scoped to one
    dashboard snapshot build: it never carries stale safety evidence across
    snapshots, and every cached access is invalidated by a file signature
    change.  A source that changes while it is being scanned raises so callers
    fail closed rather than mixing file versions.
    """

    def __init__(self) -> None:
        self._queue_summaries: Dict[str, Tuple[Tuple[object, ...], Dict[str, object]]] = {}
        self._email_sets: Dict[str, Tuple[Tuple[object, ...], set[str]]] = {}
        self._log_evidence: Dict[str, Tuple[Tuple[object, ...], Dict[str, set[str]]]] = {}
        self._reject_rows: Dict[str, Tuple[Tuple[object, ...], Dict[str, List[Dict[str, str]]]]] = {}

    @staticmethod
    def _signature(path: Path) -> Tuple[object, ...]:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return ("missing",)
        return (
            int(stat.st_dev),
            int(stat.st_ino),
            int(stat.st_size),
            int(stat.st_mtime_ns),
        )

    def _stable_read_csv(self, path: Path) -> Tuple[List[str], List[Dict[str, str]], Tuple[object, ...]]:
        before = self._signature(path)
        headers, rows = read_csv(path)
        after = self._signature(path)
        if before != after:
            raise RuntimeError(f"Queue-safety source changed during scan: {path}")
        return headers, rows, after

    def queue_summary(self, path: Path) -> Dict[str, object]:
        marker = str(path)
        signature = self._signature(path)
        cached = self._queue_summaries.get(marker)
        if cached is not None and cached[0] == signature:
            return cached[1]

        headers, rows, stable_signature = self._stable_read_csv(path)
        email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
        emails = {
            email
            for email in (norm_email(row.get(email_header or "")) for row in rows)
            if email
        }
        summary: Dict[str, object] = {
            "headers": tuple(headers),
            "row_count": len(rows),
            "emails": emails,
            "missing_or_empty": stable_signature == ("missing",) or (path.exists() and path.stat().st_size <= 0),
        }
        self._queue_summaries[marker] = (stable_signature, summary)
        self._email_sets[marker] = (stable_signature, emails)
        return summary

    def email_set(self, path: Path) -> set[str]:
        marker = str(path)
        signature = self._signature(path)
        cached = self._email_sets.get(marker)
        if cached is not None and cached[0] == signature:
            return cached[1]
        queue_cached = self._queue_summaries.get(marker)
        if queue_cached is not None and queue_cached[0] == signature:
            emails = queue_cached[1].get("emails")
            if isinstance(emails, set):
                self._email_sets[marker] = (signature, emails)
                return emails

        headers, rows, stable_signature = self._stable_read_csv(path)
        email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
        emails = {email for email in (norm_email(row.get(email_header or "")) for row in rows) if email}
        self._email_sets[marker] = (stable_signature, emails)
        return emails

    def delivery_log_evidence(self, path: Path) -> Dict[str, set[str]]:
        """Scan one stable log version and derive all safety evidence at once."""

        marker = str(path)
        signature = self._signature(path)
        cached = self._log_evidence.get(marker)
        if cached is not None and cached[0] == signature:
            return cached[1]

        headers, rows, stable_signature = self._stable_read_csv(path)
        email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
        status_header = find_header(headers, ("status", "event", "result"))
        info_header = find_header(headers, ("info", "details", "message"))
        queue_sent: set[str] = set()
        accounted_exact: set[str] = set()
        authoritative_sent_exact: set[str] = set()

        if email_header:
            for row in rows:
                email = norm_email(row.get(email_header))
                if not email:
                    continue

                # Preserve sent_email_set() semantics used by the queue rebuild
                # safety checker, including its conservative no-status-column
                # behavior.
                if status_header:
                    status = str(row.get(status_header) or "").strip().upper()
                    info = str(row.get(info_header or "") or "").strip().lower()
                    queue_marks_sent = status == "SENT" or (
                        status == "ATTEMPT" and "outcome=sent" in info
                    )
                else:
                    queue_marks_sent = True
                if queue_marks_sent:
                    queue_sent.add(email)

                # Preserve dashboard_core's exact historical-log semantics.
                exact_status = str(row.get("Status") or "").strip().upper()
                exact_info = str(row.get("Info") or "").strip().lower()
                exact_marks_sent = exact_status == "SENT" or (
                    exact_status == "ATTEMPT"
                    and (
                        "outcome=sent" in exact_info
                        or '"outcome":"sent"' in exact_info
                        or "'outcome': 'sent'" in exact_info
                    )
                )
                if exact_status in {"SENT", "SKIP"} or exact_marks_sent:
                    accounted_exact.add(email)
                if exact_marks_sent:
                    authoritative_sent_exact.add(email)

        evidence = {
            "queue_sent": queue_sent,
            "accounted_exact": accounted_exact,
            "authoritative_sent_exact": authoritative_sent_exact,
        }
        self._log_evidence[marker] = (stable_signature, evidence)
        return evidence

    def sent_email_set(self, path: Path) -> set[str]:
        return self.delivery_log_evidence(path)["queue_sent"]

    def accounted_email_set_exact(self, path: Path) -> set[str]:
        return self.delivery_log_evidence(path)["accounted_exact"]

    def authoritative_sent_email_set_exact(self, path: Path) -> set[str]:
        return self.delivery_log_evidence(path)["authoritative_sent_exact"]

    def reject_rows_by_email(self, path: Path) -> Dict[str, List[Dict[str, str]]]:
        marker = str(path)
        signature = self._signature(path)
        cached = self._reject_rows.get(marker)
        if cached is not None and cached[0] == signature:
            return cached[1]

        headers, rows, stable_signature = self._stable_read_csv(path)
        email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
        by_email: Dict[str, List[Dict[str, str]]] = {}
        if email_header:
            for row in rows:
                email = norm_email(row.get(email_header))
                if email:
                    by_email.setdefault(email, []).append(row)
        self._reject_rows[marker] = (stable_signature, by_email)
        return by_email


def active_campaign_manifest_path(state_dir: Path | None = None) -> Path:
    return (state_dir or settings.STATE_DIR) / ACTIVE_CAMPAIGN_MANIFEST_NAME


def _path_stats(path: Path) -> Dict[str, object]:
    emails = email_set(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "row_count": row_count(path),
        "unique_email_count": len(emails),
        "email_fingerprint": set_fingerprint(emails) if emails else "",
    }


def write_active_campaign_manifest(
    *,
    checked_path: Path,
    triaged_keep_path: Path,
    triaged_reject_path: Path,
    intended_source_path: Path,
    state_dir: Path | None = None,
    extra: Dict[str, object] | None = None,
) -> Path:
    now = datetime.now(timezone.utc).isoformat()
    manifest_path = active_campaign_manifest_path(state_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, object] = {
        "created_at": now,
        "created_at_utc": now,
        "checked_path": str(checked_path),
        "triaged_keep_path": str(triaged_keep_path),
        "triaged_reject_path": str(triaged_reject_path),
        "intended_source_path": str(intended_source_path),
        "files": {
            "checked": _path_stats(checked_path),
            "triaged_keep": _path_stats(triaged_keep_path),
            "triaged_reject": _path_stats(triaged_reject_path),
            "intended_source": _path_stats(intended_source_path),
        },
    }
    if extra:
        payload.update(extra)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    settings.secure_private_file(manifest_path)
    return manifest_path


def default_queue_paths(shards_dir: Path | None = None) -> List[Path]:
    queue_dir = shards_dir or DEFAULT_LIVE_QUEUE_DIR
    return [queue_dir / name for name in QUEUE_FILENAMES]


def default_sendgrid_queue_paths(shards_dir: Path | None = None) -> List[Path]:
    queue_dir = shards_dir or DEFAULT_LIVE_QUEUE_DIR
    return [queue_dir / name for name in SENDGRID_QUEUE_FILENAMES]


def default_sendgrid_log_paths(log_dir: Path = settings.LOGS_DIR) -> List[Path]:
    return [log_dir / name for name in (*SENDGRID_LOG_FILENAMES, *SENDGRID_DOMAIN_LOG_FILENAMES)]


def _is_sendgrid_queue_path(path: Path) -> bool:
    return path.name in SENDGRID_QUEUE_FILENAMES


def _missing_required_headers(headers: Sequence[str], required: Sequence[str] = SENDGRID_REQUIRED_HEADERS) -> List[str]:
    present = {normalize_header(header) for header in headers}
    return [header for header in required if normalize_header(header) not in present]


def _missing_rebuild_source_headers(headers: Sequence[str]) -> List[str]:
    required = [header for header in SENDGRID_REQUIRED_HEADERS if header != "AuthorEmail"]
    return _missing_required_headers(headers, required=required)


def _nonempty_file(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 0
    except Exception:
        return False


def _resolve_app_path(value: object) -> Path:
    path = Path(str(value or "").strip())
    if path.is_absolute():
        return path
    return settings.APP_ROOT / path


def _read_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _staged_archive_source_paths(archive_dir: Path, origin: str) -> Dict[str, object] | None:
    keep = archive_dir / "leads_triaged_keep.csv"
    if not _nonempty_file(keep):
        return None
    checked = archive_dir / "leads.csv"
    reject = archive_dir / "leads_triaged_reject.csv"
    return {
        "origin": origin,
        "intended": keep,
        "checked": checked if _nonempty_file(checked) else settings.APP_ROOT / "_important" / "leads.csv",
        "triaged_keep": keep,
        "triaged_reject": reject if _nonempty_file(reject) else settings.APP_ROOT / "_important" / "leads_triaged_reject.csv",
    }


def _source_paths_from_dispatch_state(state_path: Path, origin: str) -> Dict[str, object] | None:
    state = _read_json(state_path)
    latest_dispatch = state.get("latest_dispatch")
    if not isinstance(latest_dispatch, dict):
        return None
    archive_text = str(latest_dispatch.get("staged_batch_archive_path") or "").strip()
    if not archive_text:
        return None
    return _staged_archive_source_paths(_resolve_app_path(archive_text), origin)


def _active_campaign_manifest_source_paths(state_dir: Path = settings.STATE_DIR) -> Dict[str, object] | None:
    manifest_path = active_campaign_manifest_path(state_dir)
    manifest = _read_json(manifest_path)
    if not manifest:
        return None
    intended_text = str(manifest.get("intended_source_path") or manifest.get("triaged_keep_path") or "").strip()
    checked_text = str(manifest.get("checked_path") or "").strip()
    if not intended_text or not checked_text:
        return None
    intended = _resolve_app_path(intended_text)
    checked = _resolve_app_path(checked_text)
    triaged_keep = _resolve_app_path(manifest.get("triaged_keep_path") or intended)
    triaged_reject = _resolve_app_path(
        manifest.get("triaged_reject_path") or settings.APP_ROOT / "_important" / "leads_triaged_reject.csv"
    )
    if not _nonempty_file(intended) or not _nonempty_file(checked):
        return None
    return {
        "origin": "active_campaign_manifest",
        "intended": intended,
        "checked": checked,
        "triaged_keep": triaged_keep,
        "triaged_reject": triaged_reject,
        "active_campaign_manifest_path": manifest_path,
    }


def _latest_queue_rebuild_source_paths() -> Dict[str, object] | None:
    root = default_archive_root()
    if not root.exists():
        return None
    manifests = sorted(root.glob("queue_rebuild_*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for manifest_path in manifests:
        manifest = _read_json(manifest_path)
        source_paths = manifest.get("queue_safety_source_paths")
        if isinstance(source_paths, dict):
            keep_text = str(source_paths.get("triaged_keep_path") or source_paths.get("intended_source_path") or "").strip()
            if keep_text:
                keep = _resolve_app_path(keep_text)
                if _nonempty_file(keep):
                    checked = _resolve_app_path(source_paths.get("checked_path") or settings.APP_ROOT / "_important" / "leads.csv")
                    reject = _resolve_app_path(source_paths.get("triaged_reject_path") or settings.APP_ROOT / "_important" / "leads_triaged_reject.csv")
                    return {
                        "origin": "latest_queue_rebuild_manifest",
                        "intended": keep,
                        "checked": checked,
                        "triaged_keep": keep,
                        "triaged_reject": reject,
                    }
        archived_state = manifest_path.parent / "data" / "state" / "leads_dashboard_state.json"
        resolved = _source_paths_from_dispatch_state(archived_state, "latest_queue_rebuild_archived_dispatch_state")
        if resolved:
            return resolved
    return None


def default_queue_safety_sources(important_dir: Path = settings.APP_ROOT / "_important") -> Dict[str, object]:
    checked = important_dir / "leads.csv"
    keep = important_dir / "leads_triaged_keep.csv"
    reject = important_dir / "leads_triaged_reject.csv"
    resolved = _active_campaign_manifest_source_paths(settings.STATE_DIR)
    if resolved:
        return resolved

    if _nonempty_file(keep):
        return {
            "origin": "current_important_triaged_keep",
            "intended": keep,
            "checked": checked,
            "triaged_keep": keep,
            "triaged_reject": reject,
        }

    resolved = _latest_queue_rebuild_source_paths()
    if resolved:
        return resolved

    resolved = _source_paths_from_dispatch_state(settings.STATE_DIR / "leads_dashboard_state.json", "latest_dispatch_staged_batch_archive")
    if resolved:
        return resolved

    return {
        "origin": "current_important_fallback",
        "intended": checked,
        "checked": checked,
        "triaged_keep": keep,
        "triaged_reject": reject,
    }


def default_intended_source(important_dir: Path = settings.APP_ROOT / "_important") -> Path:
    return Path(default_queue_safety_sources(important_dir)["intended"])


def default_archive_root() -> Path:
    return settings.BACKUPS_DIR / "queue_rebuild"


def build_queue_safety_report(
    *,
    shard_paths: Sequence[Path] | None = None,
    intended_source_path: Path | None = None,
    checked_path: Path | None = None,
    triaged_keep_path: Path | None = None,
    triaged_reject_path: Path | None = None,
    sendgrid_log_paths: Sequence[Path] | None = None,
    allow_sendgrid_already_sent: bool = False,
    campaign_type: str = "",
    recontact_blocked_overlap_export_path: Path | None = None,
    scan_cache: QueueSafetyScanCache | None = None,
    sendgrid_sent_emails: set[str] | None = None,
) -> Dict[str, object]:
    important_dir = settings.APP_ROOT / "_important"
    default_sources = default_queue_safety_sources(important_dir)
    intended = intended_source_path or Path(default_sources["intended"])
    checked = checked_path or Path(default_sources["checked"])
    triaged_keep = triaged_keep_path or Path(default_sources["triaged_keep"])
    triaged_reject = triaged_reject_path or Path(default_sources["triaged_reject"])
    queues = list(shard_paths or default_queue_paths())
    cache = scan_cache or QueueSafetyScanCache()

    per_shard = []
    shard_emails: set[str] = set()
    sendgrid_shard_emails: set[str] = set()
    planned_profiles_by_email: Dict[str, set[str]] = {}
    duplicate_rows_across_shards = 0
    seen: set[str] = set()
    for path in queues:
        summary = cache.queue_summary(path)
        headers = list(summary.get("headers") or [])
        emails = set(summary.get("emails") or set())
        rows = int(summary.get("row_count") or 0)
        missing_required_headers = _missing_required_headers(headers) if _is_sendgrid_queue_path(path) else []
        per_shard.append(
            {
                "path": str(path),
                "name": path.name,
                "row_count": rows,
                "unique_emails": len(emails),
                "missing_or_empty": bool(summary.get("missing_or_empty")),
                "missing_required_headers": missing_required_headers,
                "required_headers_present": not missing_required_headers,
            }
        )
        duplicate_rows_across_shards += len(seen & emails)
        seen.update(emails)
        shard_emails.update(emails)
        profile_name = _queue_profile_name(path)
        for email in emails:
            planned_profiles_by_email.setdefault(email, set()).add(profile_name)
        if _is_sendgrid_queue_path(path):
            sendgrid_shard_emails.update(emails)

    intended_emails = cache.email_set(intended)
    checked_emails = cache.email_set(checked)
    keep_emails = cache.email_set(triaged_keep)
    reject_emails = cache.email_set(triaged_reject)
    effective_sendgrid_sent_emails = set(sendgrid_sent_emails or set())
    if sendgrid_shard_emails and sendgrid_sent_emails is None:
        for log_path in list(sendgrid_log_paths or default_sendgrid_log_paths()):
            effective_sendgrid_sent_emails.update(cache.sent_email_set(log_path))

    outside_intended = shard_emails - intended_emails if intended_emails else set(shard_emails)
    outside_checked = shard_emails - checked_emails if checked_emails else set(shard_emails)
    reject_overlap = shard_emails & reject_emails
    sendgrid_sent_overlap = sendgrid_shard_emails & effective_sendgrid_sent_emails
    source_reject_overlap = intended_emails & reject_emails
    normalized_campaign_type = str(campaign_type or "").strip().lower()
    allow_name_quality_reject_overlap = normalized_campaign_type == RECONTACT_COLD_CAMPAIGN_TYPE
    reject_rows_by_email: Dict[str, List[Dict[str, str]]] = {}
    if allow_name_quality_reject_overlap:
        reject_rows_by_email = cache.reject_rows_by_email(triaged_reject)
        allowed_reject_overlap = {
            email
            for email in reject_overlap
            if _recontact_reject_overlap_allowed(reject_rows_by_email.get(email) or [])
        }
        blocked_reject_overlap = reject_overlap - allowed_reject_overlap
        allowed_source_reject_overlap = {
            email
            for email in source_reject_overlap
            if _recontact_reject_overlap_allowed(reject_rows_by_email.get(email) or [])
        }
        blocked_source_reject_overlap = source_reject_overlap - allowed_source_reject_overlap
    else:
        allowed_reject_overlap = set()
        blocked_reject_overlap = set(reject_overlap)
        allowed_source_reject_overlap = set()
        blocked_source_reject_overlap = set(source_reject_overlap)
    if allow_name_quality_reject_overlap:
        _write_recontact_blocked_reject_overlap_export(
            path=recontact_blocked_overlap_export_path or RECONTACT_BLOCKED_REJECT_OVERLAP_EXPORT,
            blocked_emails=blocked_reject_overlap,
            planned_profiles_by_email=planned_profiles_by_email,
            reject_rows_by_email=reject_rows_by_email,
            campaign_type=normalized_campaign_type,
            triaged_reject_path=triaged_reject,
        )
    missing_required_header_shards = [
        {"name": str(item["name"]), "missing_required_headers": list(item["missing_required_headers"])}
        for item in per_shard
        if item.get("missing_required_headers")
    ]

    unsafe_reasons = []
    if missing_required_header_shards:
        unsafe_reasons.append("MISSING_REQUIRED_HEADERS")
    if blocked_reject_overlap:
        unsafe_reasons.append("TRIAGED_REJECT_OVERLAP")
    if outside_checked:
        unsafe_reasons.append("OUTSIDE_CHECKED_OUTPUT")
    if outside_intended:
        unsafe_reasons.append("OUTSIDE_INTENDED_SOURCE")
    if blocked_source_reject_overlap:
        unsafe_reasons.append("INTENDED_SOURCE_OVERLAPS_REJECT")
    # Successful history is informational. Suppression, invalidity, queue
    # duplication and current-campaign idempotency remain separate blockers.

    return {
        "safe": not unsafe_reasons,
        "unsafe_reasons": unsafe_reasons,
        "source_resolution": str(default_sources.get("origin") or "explicit") if not any((intended_source_path, checked_path, triaged_keep_path, triaged_reject_path)) else "explicit",
        "intended_source_path": str(intended),
        "checked_path": str(checked),
        "triaged_keep_path": str(triaged_keep),
        "triaged_reject_path": str(triaged_reject),
        "shards": per_shard,
        "shard_row_count_total": sum(int(item["row_count"]) for item in per_shard),
        "unique_shard_emails": len(shard_emails),
        "duplicate_email_overlap_across_shards": duplicate_rows_across_shards,
        "intended_source_unique_emails": len(intended_emails),
        "checked_unique_emails": len(checked_emails),
        "triaged_keep_unique_emails": len(keep_emails),
        "triaged_reject_unique_emails": len(reject_emails),
        "overlap_with_checked_output": len(shard_emails & checked_emails),
        "overlap_with_triaged_keep": len(shard_emails & keep_emails),
        "overlap_with_triaged_reject": len(reject_overlap),
        "sendgrid_already_sent_overlap_count": len(sendgrid_sent_overlap),
        "sendgrid_already_sent_overlap_allowed": bool(sendgrid_sent_overlap),
        "outside_intended_source_count": len(outside_intended),
        "outside_checked_output_count": len(outside_checked),
        "intended_source_reject_overlap_count": len(source_reject_overlap),
        "allowed_triaged_reject_overlap_count": len(allowed_reject_overlap),
        "blocked_triaged_reject_overlap_count": len(blocked_reject_overlap),
        "allowed_intended_source_reject_overlap_count": len(allowed_source_reject_overlap),
        "blocked_intended_source_reject_overlap_count": len(blocked_source_reject_overlap),
        "missing_required_header_shards": missing_required_header_shards,
        "missing_required_header_shard_count": len(missing_required_header_shards),
        "outside_intended_source_fingerprint": set_fingerprint(outside_intended) if outside_intended else "",
        "outside_checked_output_fingerprint": set_fingerprint(outside_checked) if outside_checked else "",
        "triaged_reject_overlap_fingerprint": set_fingerprint(reject_overlap) if reject_overlap else "",
        "blocked_triaged_reject_overlap_fingerprint": set_fingerprint(blocked_reject_overlap) if blocked_reject_overlap else "",
        "sendgrid_already_sent_overlap_fingerprint": set_fingerprint(sendgrid_sent_overlap) if sendgrid_sent_overlap else "",
    }


def quarantine_malformed_stale_shard(
    *,
    shard_path: Path,
    intended_source_path: Path,
    checked_path: Path,
    triaged_reject_path: Path,
    archive_root: Path | None = None,
    replacement_headers: Sequence[str] = SENDGRID_REQUIRED_HEADERS,
) -> Dict[str, object]:
    headers, rows = read_csv(shard_path)
    missing_required = _missing_required_headers(headers)
    email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
    emails = {email for email in (norm_email(row.get(email_header or "")) for row in rows) if email}
    checked_emails = email_set(checked_path)
    intended_emails = email_set(intended_source_path)
    reject_emails = email_set(triaged_reject_path)
    outside_checked = emails - checked_emails if checked_emails else set(emails)
    outside_intended = emails - intended_emails if intended_emails else set(emails)
    reject_overlap = emails & reject_emails

    if not shard_path.exists():
        raise FileNotFoundError(shard_path)
    if not missing_required:
        raise ValueError(f"Shard is not missing required headers: {shard_path}")
    if emails != outside_checked or emails != outside_intended:
        raise ValueError("Refusing quarantine: shard contains email(s) still present in current source.")
    if reject_overlap:
        raise ValueError("Refusing quarantine: shard overlaps triaged reject.")

    timestamp = datetime.now(timezone.utc).strftime("queue_quarantine_%Y%m%d_%H%M%S_%f")
    archive_dir = (archive_root or (settings.BACKUPS_DIR / "queue_quarantine")) / timestamp
    archive_dir.mkdir(parents=True, exist_ok=False)
    settings.secure_private_dir(archive_dir)

    archived_shard = archive_dir / shard_path.name
    shutil.copy2(shard_path, archived_shard)
    settings.secure_private_file(archived_shard)

    fingerprint = set_fingerprint(emails) if emails else ""
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": str(shard_path),
        "archived_file": str(archived_shard),
        "row_count": len(rows),
        "unique_emails": len(emails),
        "reason": "outside_current_source_and_missing_required_headers",
        "missing_required_headers": missing_required,
        "outside_checked_output_count": len(outside_checked),
        "outside_intended_source_count": len(outside_intended),
        "overlap_with_triaged_reject": len(reject_overlap),
        "fingerprint": fingerprint,
        "replacement_headers": list(replacement_headers),
    }
    report_json = archive_dir / "quarantine_report.json"
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    settings.secure_private_file(report_json)

    report_csv = archive_dir / "quarantine_report.csv"
    write_csv_atomic(
        report_csv,
        [
            "source_file",
            "archived_file",
            "row_count",
            "unique_emails",
            "reason",
            "missing_required_headers",
            "outside_checked_output_count",
            "outside_intended_source_count",
            "overlap_with_triaged_reject",
            "fingerprint",
        ],
        [
            {
                **report,
                "missing_required_headers": "|".join(missing_required),
            }
        ],
    )

    write_csv_atomic(shard_path, replacement_headers, [])
    after = build_queue_safety_report(
        shard_paths=[shard_path],
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=intended_source_path,
        triaged_reject_path=triaged_reject_path,
    )
    report["report_json"] = str(report_json)
    report["report_csv"] = str(report_csv)
    report["after"] = after
    return report


def archive_inputs(
    *,
    archive_root: Path | None = None,
    shard_paths: Sequence[Path] | None = None,
    log_dir: Path = settings.LOGS_DIR,
    state_dir: Path = settings.STATE_DIR,
    protected_paths: Sequence[Path] | None = None,
) -> Path:
    root = archive_root or default_archive_root()
    archive_dir = root / datetime.now(timezone.utc).strftime("queue_rebuild_%Y%m%d_%H%M%S_%f")
    archive_dir.mkdir(parents=True, exist_ok=False)
    settings.secure_private_dir(archive_dir)

    paths: List[Path] = []
    paths.extend(path for path in (shard_paths or default_queue_paths()) if path.exists())
    paths.extend(sorted(log_dir.glob("*_log.csv")) if log_dir.exists() else [])
    default_protected_paths = (
        state_dir / "leads_dashboard_state.json",
        settings.LEAD_LEDGER_DB_PATH,
        settings.SENDGRID_SUPPRESSIONS_PATH,
        settings.SUPPRESSED_PATH,
        settings.UNSUBSCRIBED_PATH,
        settings.WEBHOOK_EVENTS_PATH,
        settings.WEBHOOK_DEDUPE_PATH,
        settings.SENDGRID_WEBHOOK_RECEIVER_DB_PATH,
    )
    for path in protected_paths if protected_paths is not None else default_protected_paths:
        if path.exists():
            paths.append(path)

    manifest_files = []
    for source in dict.fromkeys(paths):
        try:
            relative = source.resolve().relative_to(settings.APP_ROOT)
        except Exception:
            relative = Path(source.name)
        target = archive_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        settings.secure_private_file(target)
        manifest_files.append(
            {
                "source": str(source),
                "archive_path": str(target),
                "size_bytes": source.stat().st_size,
                "mtime_utc": datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
        )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "recipient_queue_rebuild_archive",
        "files": manifest_files,
    }
    (archive_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    settings.secure_private_file(archive_dir / "manifest.json")
    return archive_dir


def _record_queue_rebuild_source_paths(
    archive_dir: Path,
    *,
    intended_source_path: Path,
    checked_path: Path | None,
    triaged_keep_path: Path | None,
    triaged_reject_path: Path | None,
) -> None:
    manifest_path = archive_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    manifest["queue_safety_source_paths"] = {
        "intended_source_path": str(intended_source_path),
        "checked_path": str(checked_path or settings.APP_ROOT / "_important" / "leads.csv"),
        "triaged_keep_path": str(triaged_keep_path or intended_source_path),
        "triaged_reject_path": str(triaged_reject_path or settings.APP_ROOT / "_important" / "leads_triaged_reject.csv"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    settings.secure_private_file(manifest_path)


def _first_name(row: Dict[str, str], headers: Sequence[str]) -> str:
    first_header = find_header(headers, FIRST_NAME_CANDIDATES)
    value = str(row.get(first_header or "", "") or "").strip()
    if value:
        return value.split()[0].strip()
    full = str(row.get("FullName", "") or row.get("AuthorName", "") or "").strip()
    return full.split()[0].strip() if full else ""


def _field_value(row: Dict[str, str], headers: Sequence[str], name: str) -> str:
    normalized_name = normalize_header(name)
    for header in headers:
        if normalize_header(header) == normalized_name:
            return str(row.get(header, "") or "").strip()
    return ""


def _append_exclusion(
    excluded_rows: List[Dict[str, str]],
    *,
    email: str,
    reason: str,
    source: str,
    shard_name: str = "",
) -> None:
    excluded_rows.append(
        {
            "Email": email,
            "exclusion_reason": reason,
            "source": source,
            "shard_name": shard_name,
        }
    )


def _source_rows_for_safe_rebuild(
    *,
    intended_source_path: Path,
    checked_path: Path | None,
    triaged_reject_path: Path | None,
    existing_shard_paths: Sequence[Path],
    sendgrid_sent_emails: set[str] | None = None,
) -> Tuple[List[str], List[Dict[str, str]], List[Dict[str, str]]]:
    headers, rows = read_csv(intended_source_path)
    email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
    if not email_header:
        raise ValueError(f"Intended source has no email column: {intended_source_path}")
    missing_source_headers = _missing_rebuild_source_headers(headers)
    if missing_source_headers:
        raise ValueError(f"Intended source is missing required SendGrid headers: {', '.join(missing_source_headers)}")

    output_headers = list(headers)
    if "Email" not in output_headers:
        output_headers.insert(0, "Email")
    if "FirstName" not in output_headers:
        output_headers.append("FirstName")
    for header in SENDGRID_REQUIRED_HEADERS:
        if header not in output_headers:
            output_headers.append(header)
    for header in SENDGRID_REQUIRED_HEADERS:
        if header not in output_headers:
            output_headers.append(header)
    for header in SENDGRID_REQUIRED_HEADERS:
        if header not in output_headers:
            output_headers.append(header)
    if "normalization_note" not in output_headers:
        output_headers.append("normalization_note")

    checked_emails = email_set(checked_path) if checked_path else set()
    reject_emails = email_set(triaged_reject_path) if triaged_reject_path else set()
    intended_emails = {
        email
        for email in (norm_email(row.get(email_header)) for row in rows)
        if email
    }
    excluded_rows: List[Dict[str, str]] = []
    seen: set[str] = set()
    safe_rows: List[Dict[str, str]] = []
    already_sent = sendgrid_sent_emails or set()

    for shard_path in existing_shard_paths:
        shard_headers, shard_rows = read_csv(shard_path)
        shard_email_header = find_header(shard_headers, EMAIL_HEADER_CANDIDATES)
        missing_headers = _missing_required_headers(shard_headers) if _is_sendgrid_queue_path(shard_path) else []
        if missing_headers:
            _append_exclusion(
                excluded_rows,
                email="",
                reason="missing_required_headers:" + "|".join(missing_headers),
                source="existing_queue",
                shard_name=shard_path.name,
            )
        for shard_row in shard_rows:
            email = norm_email(shard_row.get(shard_email_header or ""))
            if not email:
                continue
            reasons = []
            if email not in intended_emails:
                reasons.append("outside_intended_source")
            if checked_emails and email not in checked_emails:
                reasons.append("outside_checked_output")
            if email in reject_emails:
                reasons.append("triaged_reject_overlap")
            if reasons:
                _append_exclusion(
                    excluded_rows,
                    email=email,
                    reason="|".join(reasons),
                    source="existing_queue",
                    shard_name=shard_path.name,
                )

    for row in rows:
        email = norm_email(row.get(email_header))
        reasons = []
        if not email or not EMAIL_SYNTAX_RE.match(email):
            reasons.append("invalid_email")
        if email and email in seen:
            reasons.append("duplicate_email")
        if checked_emails and email not in checked_emails:
            reasons.append("outside_checked_output")
        if email in reject_emails:
            reasons.append("triaged_reject_overlap")
        if email in already_sent:
            reasons.append("sendgrid_already_sent")
        for header in SENDGRID_REQUIRED_HEADERS:
            if header == "AuthorEmail":
                if not (_field_value(row, headers, header) or email):
                    reasons.append(f"missing_required_field:{header}")
                continue
            if not _field_value(row, headers, header) and header not in {"Email", "FirstName"}:
                reasons.append(f"missing_required_field:{header}")
        if reasons:
            _append_exclusion(
                excluded_rows,
                email=email,
                reason="|".join(dict.fromkeys(reasons)),
                source="intended_source",
            )
            continue
        seen.add(email)
        normalized = {header: str(row.get(header, "") or "").strip() for header in output_headers}
        normalized["Email"] = email
        if not normalized.get("AuthorEmail"):
            normalized["AuthorEmail"] = email
        if not normalized.get("FirstName"):
            normalized["FirstName"] = _first_name(row, headers)
        normalization_notes: List[str] = []
        for field in RENDER_NORMALIZED_FIELDS:
            normalized_value, notes = normalize_render_field_value(normalized.get(field, ""))
            normalized[field] = normalized_value
            normalization_notes.extend(f"{field}:{note}" for note in notes)
            if placeholder_like_tokens(normalized_value):
                reasons.append(f"unsafe_render_field:{field}")
        if reasons:
            _append_exclusion(
                excluded_rows,
                email=email,
                reason="|".join(dict.fromkeys(reasons)),
                source="intended_source",
            )
            continue
        if normalization_notes:
            existing_note = str(normalized.get("normalization_note") or "").strip()
            normalized["normalization_note"] = "|".join(
                note for note in [existing_note, *normalization_notes] if note
            )
        safe_rows.append(normalized)
    return output_headers, safe_rows, excluded_rows


def load_rebuild_source_rows(source_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    headers, rows = read_csv(source_path)
    email_header = find_header(headers, EMAIL_HEADER_CANDIDATES)
    if not email_header:
        raise ValueError(f"Intended source has no email column: {source_path}")

    output_headers = list(headers)
    if "Email" not in output_headers:
        output_headers.insert(0, "Email")
    if "FirstName" not in output_headers:
        output_headers.append("FirstName")
    for required_header in SENDGRID_REQUIRED_HEADERS:
        if required_header not in output_headers:
            output_headers.append(required_header)

    seen: set[str] = set()
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        email = norm_email(row.get(email_header))
        if not email or email in seen:
            continue
        seen.add(email)
        normalized = {header: str(row.get(header, "") or "").strip() for header in output_headers}
        normalized["Email"] = email
        if not normalized.get("AuthorEmail"):
            normalized["AuthorEmail"] = email
        if not normalized.get("FirstName"):
            normalized["FirstName"] = _first_name(row, headers)
        normalized_rows.append(normalized)
    return output_headers, normalized_rows


def rebuild_recipient_queues(
    *,
    intended_source_path: Path,
    shard_paths: Sequence[Path] | None = None,
    archive_root: Path | None = None,
    checked_path: Path | None = None,
    triaged_keep_path: Path | None = None,
    triaged_reject_path: Path | None = None,
    log_dir: Path = settings.LOGS_DIR,
    state_dir: Path = settings.STATE_DIR,
    protected_paths: Sequence[Path] | None = None,
) -> Dict[str, object]:
    queues = list(shard_paths or default_queue_paths())
    if len(queues) != len(QUEUE_FILENAMES):
        raise ValueError(f"Expected {len(QUEUE_FILENAMES)} recipient queue paths.")
    before = build_queue_safety_report(
        shard_paths=queues,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
    )
    if int(before.get("intended_source_reject_overlap_count") or 0) > 0:
        raise RuntimeError("Refusing rebuild: intended source overlaps triaged_reject.")

    headers, rows = load_rebuild_source_rows(intended_source_path)
    buckets: List[List[Dict[str, str]]] = [[] for _ in queues]
    for index, row in enumerate(rows):
        buckets[index % len(queues)].append(row)

    temp_root = Path(tempfile.mkdtemp(prefix="recipient_queue_plan_"))
    planned_paths = [temp_root / path.name for path in queues]
    for path, bucket in zip(planned_paths, buckets):
        write_csv_atomic(path, headers, bucket)
    planned_after = build_queue_safety_report(
        shard_paths=planned_paths,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
    )
    if not bool(planned_after.get("safe")):
        reasons = ", ".join(str(reason) for reason in (planned_after.get("unsafe_reasons") or [])) or "unknown unsafe planned state"
        raise RuntimeError(f"Refusing live recipient rebuild: planned queue safety is unsafe ({reasons}).")

    archive_dir = archive_inputs(
        archive_root=archive_root,
        shard_paths=queues,
        log_dir=log_dir,
        state_dir=state_dir,
        protected_paths=protected_paths,
    )
    _record_queue_rebuild_source_paths(
        archive_dir,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
    )
    for path, bucket in zip(queues, buckets):
        write_csv_atomic(path, headers, bucket)

    after = build_queue_safety_report(
        shard_paths=queues,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
    )
    manifest_path = write_active_campaign_manifest(
        checked_path=checked_path or settings.APP_ROOT / "_important" / "leads.csv",
        triaged_keep_path=triaged_keep_path or intended_source_path,
        triaged_reject_path=triaged_reject_path or settings.APP_ROOT / "_important" / "leads_triaged_reject.csv",
        intended_source_path=intended_source_path,
        state_dir=state_dir,
        extra={"source": "recipient_queue_rebuild", "archive_dir": str(archive_dir)},
    )
    return {
        "ok": True,
        "archive_dir": str(archive_dir),
        "active_campaign_manifest_path": str(manifest_path),
        "source_rows_written": len(rows),
        "rows_written_per_shard": {path.name: len(bucket) for path, bucket in zip(queues, buckets)},
        "before": before,
        "after": after,
    }


def rebuild_sendgrid_recipient_queues(
    *,
    intended_source_path: Path,
    shard_paths: Sequence[Path] | None = None,
    archive_root: Path | None = None,
    checked_path: Path | None = None,
    triaged_keep_path: Path | None = None,
    triaged_reject_path: Path | None = None,
    quarantine_path: Path | None = None,
    sendgrid_log_paths: Sequence[Path] | None = None,
    apply: bool = False,
) -> Dict[str, object]:
    queues = list(shard_paths or default_sendgrid_queue_paths())
    if len(queues) != len(SENDGRID_QUEUE_FILENAMES):
        raise ValueError(f"Expected {len(SENDGRID_QUEUE_FILENAMES)} SendGrid queue paths.")
    before = build_queue_safety_report(
        shard_paths=queues,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
    )
    log_paths = list(sendgrid_log_paths or default_sendgrid_log_paths())
    sendgrid_sent_emails: set[str] = set()
    for log_path in log_paths:
        sendgrid_sent_emails.update(sent_email_set(log_path))
    headers, safe_rows, excluded_rows = _source_rows_for_safe_rebuild(
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_reject_path=triaged_reject_path,
        existing_shard_paths=queues,
        sendgrid_sent_emails=sendgrid_sent_emails,
    )
    buckets: List[List[Dict[str, str]]] = [[] for _ in queues]
    for index, row in enumerate(safe_rows):
        buckets[index % len(queues)].append(row)

    temp_root = Path(tempfile.mkdtemp(prefix="sendgrid_queue_plan_"))
    planned_paths = [temp_root / path.name for path in queues]
    for path, bucket in zip(planned_paths, buckets):
        write_csv_atomic(path, headers, bucket)
    planned_quarantine = temp_root / "sendgrid_queue_excluded.csv"
    quarantine_headers = ["Email", "exclusion_reason", "source", "shard_name"]
    write_csv_atomic(planned_quarantine, quarantine_headers, excluded_rows)
    after = build_queue_safety_report(
        shard_paths=planned_paths,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
        sendgrid_log_paths=log_paths,
    )

    archive_dir = ""
    output_quarantine_path = str(planned_quarantine)
    manifest_path: Path | None = None
    if apply:
        if not bool(after.get("safe")):
            reasons = ", ".join(str(reason) for reason in (after.get("unsafe_reasons") or [])) or "unknown unsafe planned state"
            raise RuntimeError(f"Refusing live SendGrid rebuild: planned queue safety is unsafe ({reasons}).")
        archive_dir_path = archive_inputs(
            archive_root=archive_root,
            shard_paths=queues,
            protected_paths=[],
        )
        _record_queue_rebuild_source_paths(
            archive_dir_path,
            intended_source_path=intended_source_path,
            checked_path=checked_path,
            triaged_keep_path=triaged_keep_path,
            triaged_reject_path=triaged_reject_path,
        )
        for path, bucket in zip(queues, buckets):
            write_csv_atomic(path, headers, bucket)
        output_quarantine = quarantine_path or queues[0].parent / "sendgrid_queue_excluded.csv"
        write_csv_atomic(output_quarantine, quarantine_headers, excluded_rows)
        output_quarantine_path = str(output_quarantine)
        archive_dir = str(archive_dir_path)
        after = build_queue_safety_report(
            shard_paths=queues,
            intended_source_path=intended_source_path,
            checked_path=checked_path,
            triaged_keep_path=triaged_keep_path,
            triaged_reject_path=triaged_reject_path,
            sendgrid_log_paths=log_paths,
        )
        manifest_path = write_active_campaign_manifest(
            checked_path=checked_path or settings.APP_ROOT / "_important" / "leads.csv",
            triaged_keep_path=triaged_keep_path or intended_source_path,
            triaged_reject_path=triaged_reject_path or settings.APP_ROOT / "_important" / "leads_triaged_reject.csv",
            intended_source_path=intended_source_path,
            extra={"source": "sendgrid_queue_rebuild", "archive_dir": str(archive_dir_path)},
        )

    excluded_by_reason: Dict[str, int] = {}
    for row in excluded_rows:
        for reason in str(row.get("exclusion_reason") or "").split("|"):
            if reason:
                excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1
    return {
        "ok": True,
        "mode": "rebuild" if apply else "dry-run",
        "archive_dir": archive_dir,
        "active_campaign_manifest_path": str(manifest_path) if manifest_path else "",
        "quarantine_path": output_quarantine_path,
        "included_rows": len(safe_rows),
        "excluded_rows": len(excluded_rows),
        "excluded_by_reason": excluded_by_reason,
        "rows_written_per_shard": {path.name: len(bucket) for path, bucket in zip(queues, buckets)},
        "before": before,
        "after": after,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or rebuild recipient queue shards from the current campaign source.")
    parser.add_argument("--source", type=Path, default=None, help="Intended campaign source CSV. Defaults to _important/leads_triaged_keep.csv when present.")
    parser.add_argument("--checked", type=Path, default=None)
    parser.add_argument("--triaged-keep", type=Path, default=None)
    parser.add_argument("--triaged-reject", type=Path, default=None)
    parser.add_argument("--shards-dir", type=Path, default=None, help="Override live queue directory. Defaults to project-root recipient queues.")
    parser.add_argument("--archive-root", type=Path, default=default_archive_root())
    parser.add_argument("--rebuild", action="store_true", help="Rewrite recipient shard CSVs after archiving protected files.")
    parser.add_argument("--confirm-rebuild", action="store_true", help="Required with --rebuild.")
    parser.add_argument("--sendgrid-only", action="store_true", help="Validate/rebuild only SendGrid recipient shard CSVs.")
    parser.add_argument("--quarantine-output", type=Path, default=DEFAULT_LIVE_QUEUE_DIR / "sendgrid_queue_excluded.csv")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    default_sources = default_queue_safety_sources(settings.APP_ROOT / "_important")
    source = args.source or Path(default_sources["intended"])
    checked = args.checked or Path(default_sources["checked"])
    triaged_keep = args.triaged_keep or Path(default_sources["triaged_keep"])
    triaged_reject = args.triaged_reject or Path(default_sources["triaged_reject"])
    shard_paths = default_sendgrid_queue_paths(args.shards_dir) if args.sendgrid_only else default_queue_paths(args.shards_dir)
    if args.sendgrid_only:
        if args.rebuild and not args.confirm_rebuild:
            raise SystemExit("--rebuild requires --confirm-rebuild")
        result = rebuild_sendgrid_recipient_queues(
            intended_source_path=source,
            shard_paths=shard_paths,
            archive_root=args.archive_root,
            checked_path=checked,
            triaged_keep_path=triaged_keep,
            triaged_reject_path=triaged_reject,
            quarantine_path=args.quarantine_output,
            apply=bool(args.rebuild and args.confirm_rebuild),
        )
    elif args.rebuild:
        if not args.confirm_rebuild:
            raise SystemExit("--rebuild requires --confirm-rebuild")
        result = rebuild_recipient_queues(
            intended_source_path=source,
            shard_paths=shard_paths,
            archive_root=args.archive_root,
            checked_path=checked,
            triaged_keep_path=triaged_keep,
            triaged_reject_path=triaged_reject,
        )
    else:
        result = {
            "ok": True,
            "mode": "dry-run",
            "report": build_queue_safety_report(
                shard_paths=shard_paths,
                intended_source_path=source,
                checked_path=checked,
                triaged_keep_path=triaged_keep,
                triaged_reject_path=triaged_reject,
            ),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
