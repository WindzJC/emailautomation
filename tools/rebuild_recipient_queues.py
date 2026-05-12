#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
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
EMAIL_HEADER_CANDIDATES = ("email", "authoremail", "author_email", "e_mail", "e-mail", "mail", "address")
FIRST_NAME_CANDIDATES = ("firstname", "first_name", "first name", "authorname", "author_name", "author")


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
        writer = csv.DictWriter(handle, fieldnames=list(headers), extrasaction="ignore")
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


def row_count(path: Path) -> int:
    _headers, rows = read_csv(path)
    return len(rows)


def set_fingerprint(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in sorted(set(values)):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def default_queue_paths(shards_dir: Path = settings.SHARDS_DIR) -> List[Path]:
    return [shards_dir / name for name in QUEUE_FILENAMES]


def default_intended_source(important_dir: Path = settings.APP_ROOT / "_important") -> Path:
    triaged_keep = important_dir / "leads_triaged_keep.csv"
    if triaged_keep.exists() and triaged_keep.stat().st_size > 0:
        return triaged_keep
    return important_dir / "leads.csv"


def default_archive_root() -> Path:
    return settings.BACKUPS_DIR / "queue_rebuild"


def build_queue_safety_report(
    *,
    shard_paths: Sequence[Path] | None = None,
    intended_source_path: Path | None = None,
    checked_path: Path | None = None,
    triaged_keep_path: Path | None = None,
    triaged_reject_path: Path | None = None,
) -> Dict[str, object]:
    important_dir = settings.APP_ROOT / "_important"
    intended = intended_source_path or default_intended_source(important_dir)
    checked = checked_path or important_dir / "leads.csv"
    triaged_keep = triaged_keep_path or important_dir / "leads_triaged_keep.csv"
    triaged_reject = triaged_reject_path or important_dir / "leads_triaged_reject.csv"
    queues = list(shard_paths or default_queue_paths())

    per_shard = []
    shard_emails: set[str] = set()
    duplicate_rows_across_shards = 0
    seen: set[str] = set()
    for path in queues:
        emails = email_set(path)
        rows = row_count(path)
        per_shard.append(
            {
                "path": str(path),
                "name": path.name,
                "row_count": rows,
                "unique_emails": len(emails),
                "missing_or_empty": not path.exists() or path.stat().st_size <= 0,
            }
        )
        duplicate_rows_across_shards += len(seen & emails)
        seen.update(emails)
        shard_emails.update(emails)

    intended_emails = email_set(intended)
    checked_emails = email_set(checked)
    keep_emails = email_set(triaged_keep)
    reject_emails = email_set(triaged_reject)

    outside_intended = shard_emails - intended_emails if intended_emails else set(shard_emails)
    outside_checked = shard_emails - checked_emails if checked_emails else set(shard_emails)
    reject_overlap = shard_emails & reject_emails
    source_reject_overlap = intended_emails & reject_emails

    unsafe_reasons = []
    if reject_overlap:
        unsafe_reasons.append("TRIAGED_REJECT_OVERLAP")
    if outside_checked:
        unsafe_reasons.append("OUTSIDE_CHECKED_OUTPUT")
    if outside_intended:
        unsafe_reasons.append("OUTSIDE_INTENDED_SOURCE")
    if source_reject_overlap:
        unsafe_reasons.append("INTENDED_SOURCE_OVERLAPS_REJECT")

    return {
        "safe": not unsafe_reasons,
        "unsafe_reasons": unsafe_reasons,
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
        "outside_intended_source_count": len(outside_intended),
        "outside_checked_output_count": len(outside_checked),
        "intended_source_reject_overlap_count": len(source_reject_overlap),
        "outside_intended_source_fingerprint": set_fingerprint(outside_intended) if outside_intended else "",
        "outside_checked_output_fingerprint": set_fingerprint(outside_checked) if outside_checked else "",
        "triaged_reject_overlap_fingerprint": set_fingerprint(reject_overlap) if reject_overlap else "",
    }


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


def _first_name(row: Dict[str, str], headers: Sequence[str]) -> str:
    first_header = find_header(headers, FIRST_NAME_CANDIDATES)
    value = str(row.get(first_header or "", "") or "").strip()
    if value:
        return value.split()[0].strip()
    full = str(row.get("FullName", "") or row.get("AuthorName", "") or "").strip()
    return full.split()[0].strip() if full else ""


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

    seen: set[str] = set()
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        email = norm_email(row.get(email_header))
        if not email or email in seen:
            continue
        seen.add(email)
        normalized = {header: str(row.get(header, "") or "").strip() for header in output_headers}
        normalized["Email"] = email
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

    archive_dir = archive_inputs(
        archive_root=archive_root,
        shard_paths=queues,
        log_dir=log_dir,
        state_dir=state_dir,
        protected_paths=protected_paths,
    )
    headers, rows = load_rebuild_source_rows(intended_source_path)
    buckets: List[List[Dict[str, str]]] = [[] for _ in queues]
    for index, row in enumerate(rows):
        buckets[index % len(queues)].append(row)
    for path, bucket in zip(queues, buckets):
        write_csv_atomic(path, headers, bucket)

    after = build_queue_safety_report(
        shard_paths=queues,
        intended_source_path=intended_source_path,
        checked_path=checked_path,
        triaged_keep_path=triaged_keep_path,
        triaged_reject_path=triaged_reject_path,
    )
    return {
        "ok": True,
        "archive_dir": str(archive_dir),
        "source_rows_written": len(rows),
        "rows_written_per_shard": {path.name: len(bucket) for path, bucket in zip(queues, buckets)},
        "before": before,
        "after": after,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or rebuild recipient queue shards from the current campaign source.")
    parser.add_argument("--source", type=Path, default=None, help="Intended campaign source CSV. Defaults to _important/leads_triaged_keep.csv when present.")
    parser.add_argument("--checked", type=Path, default=settings.APP_ROOT / "_important" / "leads.csv")
    parser.add_argument("--triaged-keep", type=Path, default=settings.APP_ROOT / "_important" / "leads_triaged_keep.csv")
    parser.add_argument("--triaged-reject", type=Path, default=settings.APP_ROOT / "_important" / "leads_triaged_reject.csv")
    parser.add_argument("--shards-dir", type=Path, default=settings.SHARDS_DIR)
    parser.add_argument("--archive-root", type=Path, default=default_archive_root())
    parser.add_argument("--rebuild", action="store_true", help="Rewrite recipient shard CSVs after archiving protected files.")
    parser.add_argument("--confirm-rebuild", action="store_true", help="Required with --rebuild.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source or default_intended_source(settings.APP_ROOT / "_important")
    shard_paths = default_queue_paths(args.shards_dir)
    if args.rebuild:
        if not args.confirm_rebuild:
            raise SystemExit("--rebuild requires --confirm-rebuild")
        result = rebuild_recipient_queues(
            intended_source_path=source,
            shard_paths=shard_paths,
            archive_root=args.archive_root,
            checked_path=args.checked,
            triaged_keep_path=args.triaged_keep,
            triaged_reject_path=args.triaged_reject,
        )
    else:
        result = {
            "ok": True,
            "mode": "dry-run",
            "report": build_queue_safety_report(
                shard_paths=shard_paths,
                intended_source_path=source,
                checked_path=args.checked,
                triaged_keep_path=args.triaged_keep,
                triaged_reject_path=args.triaged_reject,
            ),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
