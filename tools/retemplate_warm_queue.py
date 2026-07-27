#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import settings
from important_leads_workflow import WARM_PRIVATE_JC_QUEUE_HEADERS, _write_csv_atomic
from leads_workflow import write_json_atomic
from recipient_file_lock import lock_files
from send_shard import (
    PITCH_WARM_BODY,
    PITCH_WARM_SUBJECT,
    PITCH_WARM_SUBJECT_FALLBACK,
    norm_email,
    normalized_warm_confirmation_payload,
    validate_warm_confirmed_queue,
    warm_confirmation_payload_hash,
)


EXPECTED_PENDING_RECORDS = 22
DEFAULT_QUEUE_PATH = settings.SHARDS_DIR / "recipients_private_jc_warm.csv"
DEFAULT_CONFIRMATION_PATH = settings.STATE_DIR / "warm_private_jc_confirmation.json"
DEFAULT_BACKUP_ROOT = settings.APP_ROOT / "_important" / "backups"
OLD_COPY_MARKERS = (
    "Quick idea for",
    "Creative Director, Astra Productions",
    "noticed you’ve been building momentum",
    "A strong creative direction here would be",
    "Examples: astraproductions.co",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_queue(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _load_manifest(path: Path) -> Dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Warm confirmation manifest must contain a JSON object.")
    return loaded


def _warm_worker_pids() -> List[int]:
    matches: List[int] = []
    proc_root = Path("/proc")
    if not proc_root.exists():
        raise RuntimeError("Cannot verify private_jc_warm process state because /proc is unavailable.")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            tokens = (entry / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        decoded = [token.decode("utf-8", errors="replace") for token in tokens if token]
        if not any(Path(token).name == "send_shard.py" for token in decoded):
            continue
        for index, token in enumerate(decoded[:-1]):
            if token == "--profile" and decoded[index + 1] == "private_jc_warm":
                matches.append(int(entry.name))
                break
    return sorted(matches)


def _render_pending_rows(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    rendered: List[Dict[str, str]] = []
    for index, original in enumerate(rows, start=1):
        row = dict(original)
        first_name = str(row.get("FirstName") or "").strip()
        if not first_name:
            raise ValueError(f"Warm queue row {index} is missing FirstName.")
        book_title = str(row.get("BookTitleOrProject") or "").strip()
        recommended_service = str(row.get("RecommendedService") or "").strip() or "a focused launch presentation"
        merge_values = {
            "FirstName": first_name,
            "BookTitleOrProject": book_title or "your book",
            "RecommendedService": recommended_service,
        }
        row["EmailSubject"] = (
            PITCH_WARM_SUBJECT.format(**merge_values)
            if book_title
            else PITCH_WARM_SUBJECT_FALLBACK
        )
        row["EmailBody"] = PITCH_WARM_BODY.format(**merge_values)
        rendered.append(row)
    return rendered


def _build_manifest(
    original: Dict[str, object],
    rows: Sequence[Dict[str, str]],
    *,
    queue_sha256: str,
    repaired_at_utc: str,
    backup_path: str,
) -> Dict[str, object]:
    manifest = dict(original)
    manifest.update(
        {
            "confirmed": True,
            "profile": "private_jc_warm",
            "queue_sha256": queue_sha256,
            "row_count": len(rows),
            "protected_fields": list(WARM_PRIVATE_JC_QUEUE_HEADERS),
            "approved_rows": {
                normalized_warm_confirmation_payload(row)["Email"]: {
                    "payload": normalized_warm_confirmation_payload(row),
                    "payload_sha256": warm_confirmation_payload_hash(row),
                }
                for row in rows
            },
            "retemplated_at_utc": repaired_at_utc,
            "retemplate_backup_path": backup_path,
        }
    )
    return manifest


def _validate_repair(
    original_rows: Sequence[Dict[str, str]],
    repaired_rows: Sequence[Dict[str, str]],
    manifest: Dict[str, object],
) -> Dict[str, object]:
    if len(original_rows) != EXPECTED_PENDING_RECORDS or len(repaired_rows) != EXPECTED_PENDING_RECORDS:
        raise ValueError(
            f"Warm retemplate requires exactly {EXPECTED_PENDING_RECORDS} pending records; "
            f"found {len(original_rows)}."
        )
    original_emails = [norm_email(row.get("Email") or row.get("AuthorEmail")) for row in original_rows]
    repaired_emails = [norm_email(row.get("Email") or row.get("AuthorEmail")) for row in repaired_rows]
    if original_emails != repaired_emails:
        raise ValueError("Warm queue recipient order or email set changed during retemplate.")
    if any(not email for email in repaired_emails) or len(set(repaired_emails)) != len(repaired_emails):
        raise ValueError("Warm queue contains a blank or duplicate normalized email.")
    for index, (original, repaired) in enumerate(zip(original_rows, repaired_rows), start=1):
        for field, value in original.items():
            if field not in {"EmailSubject", "EmailBody"} and repaired.get(field) != value:
                raise ValueError(f"Warm queue row {index} changed protected non-message field {field}.")
        subject = str(repaired.get("EmailSubject") or "")
        body = str(repaired.get("EmailBody") or "")
        if not subject.startswith("A presentation direction for"):
            raise ValueError(f"Warm queue row {index} has an unexpected subject.")
        if "Founder & CEO, Astra Productions" not in body:
            raise ValueError(f"Warm queue row {index} is missing the approved signature.")
        if any(marker in subject or marker in body for marker in OLD_COPY_MARKERS):
            raise ValueError(f"Warm queue row {index} still contains obsolete template copy.")
    approved_rows = manifest.get("approved_rows")
    if not isinstance(approved_rows, dict) or len(approved_rows) != len(repaired_rows):
        raise ValueError("Warm confirmation does not approve exactly the repaired pending rows.")
    integrity = validate_warm_confirmed_queue(repaired_rows, manifest)
    if not bool(integrity.get("valid")):
        raise ValueError(str(integrity.get("message") or "Warm confirmation payload validation failed."))
    return {
        "queue_records": len(repaired_rows),
        "confirmation_approved_records": len(approved_rows),
        "duplicate_normalized_emails": len(repaired_emails) - len(set(repaired_emails)),
        "queue_confirmation_hashes_match": True,
    }


def repair_warm_queue(
    *,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    confirmation_path: Path = DEFAULT_CONFIRMATION_PATH,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    apply: bool,
    worker_pids: Callable[[], List[int]] = _warm_worker_pids,
) -> Dict[str, object]:
    queue_path = Path(queue_path)
    confirmation_path = Path(confirmation_path)
    if worker_pids():
        raise RuntimeError("private_jc_warm is running; stop it before repairing the warm queue.")
    if not queue_path.exists() or not confirmation_path.exists():
        raise FileNotFoundError("Warm queue and confirmation manifest must both exist.")

    original_queue_sha256 = _sha256(queue_path)
    original_confirmation_sha256 = _sha256(confirmation_path)
    fieldnames, original_rows = _read_queue(queue_path)
    if fieldnames != list(WARM_PRIVATE_JC_QUEUE_HEADERS):
        raise ValueError("Warm queue headers do not match the production queue contract.")
    original_manifest = _load_manifest(confirmation_path)
    current_integrity = validate_warm_confirmed_queue(original_rows, original_manifest)
    if not bool(current_integrity.get("valid")):
        raise ValueError(str(current_integrity.get("message") or "Current warm queue confirmation is invalid."))

    repaired_rows = _render_pending_rows(original_rows)
    repaired_at_utc = datetime.now(timezone.utc).isoformat()
    placeholder_manifest = _build_manifest(
        original_manifest,
        repaired_rows,
        queue_sha256="pending",
        repaired_at_utc=repaired_at_utc,
        backup_path="",
    )
    _validate_repair(original_rows, repaired_rows, placeholder_manifest)

    result: Dict[str, object] = {
        "repair_status": "DRY_RUN" if not apply else "APPLIED",
        "worker_running_before": False,
        "original_pending_records": len(original_rows),
        "repaired_pending_records": len(repaired_rows),
        "confirmation_approved_records": len(placeholder_manifest["approved_rows"]),
        "backup_path": "",
        "template_updated": True,
        "old_template_matches_remaining": 0,
        "queue_confirmation_hashes_match": True,
    }
    if not apply:
        return result

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / f"warm_retemplate_{timestamp}"
    with lock_files([queue_path, confirmation_path]):
        if worker_pids():
            raise RuntimeError("private_jc_warm started while the repair was being prepared; no files were changed.")
        if _sha256(queue_path) != original_queue_sha256 or _sha256(confirmation_path) != original_confirmation_sha256:
            raise RuntimeError("Warm queue or confirmation changed during repair preparation; no files were changed.")
        backup_dir.mkdir(parents=True, exist_ok=False)
        queue_backup = backup_dir / queue_path.name
        confirmation_backup = backup_dir / confirmation_path.name
        shutil.copy2(queue_path, queue_backup)
        shutil.copy2(confirmation_path, confirmation_backup)
        try:
            _write_csv_atomic(queue_path, fieldnames, repaired_rows)
            queue_sha256 = _sha256(queue_path)
            manifest = _build_manifest(
                original_manifest,
                repaired_rows,
                queue_sha256=queue_sha256,
                repaired_at_utc=repaired_at_utc,
                backup_path=str(backup_dir),
            )
            write_json_atomic(confirmation_path, manifest)
            _headers, written_rows = _read_queue(queue_path)
            written_manifest = _load_manifest(confirmation_path)
            validation = _validate_repair(original_rows, written_rows, written_manifest)
            if str(written_manifest.get("queue_sha256") or "") != _sha256(queue_path):
                raise ValueError("Warm confirmation queue SHA-256 does not match the repaired queue file.")
        except Exception:
            shutil.copy2(queue_backup, queue_path)
            shutil.copy2(confirmation_backup, confirmation_path)
            raise

    result.update(validation)
    result["backup_path"] = str(backup_dir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-render only the current pending Warm Outreach queue.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate and report without writing live files.")
    mode.add_argument("--apply", action="store_true", help="Back up and atomically repair the live warm queue.")
    args = parser.parse_args()
    try:
        result = repair_warm_queue(apply=bool(args.apply))
    except Exception as exc:
        print(json.dumps({"repair_status": "FAILED", "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
