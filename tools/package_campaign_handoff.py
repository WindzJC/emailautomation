#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IMPORTANT_DIR = ROOT / "_important"
DATA_DIR = ROOT / "data"
SHARDS_DIR = DATA_DIR / "shards"
LOGS_DIR = DATA_DIR / "logs"
STATE_DIR = DATA_DIR / "state"

QUEUE_FILES = [
    SHARDS_DIR / "recipients_private_jc.csv",
    SHARDS_DIR / "recipients_sendgrid_1.csv",
    SHARDS_DIR / "recipients_sendgrid_2.csv",
    SHARDS_DIR / "recipients_sendgrid_3.csv",
    SHARDS_DIR / "recipients_sendgrid_4.csv",
    SHARDS_DIR / "recipients_sendgrid_5.csv",
]

QUEUE_LOG_FILES = [
    LOGS_DIR / "private_jc_log.csv",
    LOGS_DIR / "private_annette_log.csv",
    LOGS_DIR / "private_jordan_kendrick_log.csv",
    LOGS_DIR / "private_jodi_horowitz_log.csv",
    LOGS_DIR / "private_alison_log.csv",
    LOGS_DIR / "private_fiorela_log.csv",
    LOGS_DIR / "sendgrid_annette_log.csv",
    LOGS_DIR / "sendgrid_jordan_log.csv",
    LOGS_DIR / "sendgrid_jodi_log.csv",
    LOGS_DIR / "sendgrid_alison_log.csv",
    LOGS_DIR / "sendgrid_fiorela_log.csv",
    LOGS_DIR / "private_domain_log.csv",
    LOGS_DIR / "sendgrid_domain_log.csv",
    LOGS_DIR / "sendgridlogs",
]

STATE_FILES = [
    ROOT / ".env",
    ROOT / ".env.local",
    STATE_DIR / "dashboard_run_settings.json",
    STATE_DIR / "dashboard_auto_start_state.json",
    STATE_DIR / "dashboard_timer_state.json",
    STATE_DIR / "leads_dashboard_state.json",
    STATE_DIR / "important_leads_verify_state.json",
    STATE_DIR / "provider_pacing_state.json",
    STATE_DIR / "sendgrid_daily_counters.json",
    STATE_DIR / "sendgrid_suppressions.csv",
    STATE_DIR / "suppressed.csv",
    STATE_DIR / "unsubscribed.csv",
    STATE_DIR / "shard_report_latest.json",
    STATE_DIR / "sendgrid_shard_normalize_report.json",
    STATE_DIR / "private_bounce_state.json",
    STATE_DIR / "private_bounce_monitor.json",
    STATE_DIR / "sendgrid_webhook_dedupe.sqlite3",
    STATE_DIR / "sendgrid_webhook_dedupe.sqlite3-shm",
    STATE_DIR / "sendgrid_webhook_dedupe.sqlite3-wal",
    STATE_DIR / "sendgrid_webhook_receiver.sqlite3",
    STATE_DIR / "sendgrid_webhook_receiver.sqlite3-shm",
    STATE_DIR / "sendgrid_webhook_receiver.sqlite3-wal",
    LOGS_DIR / "sendgrid_events.jsonl",
]

IMPORTANT_FILES = [
    IMPORTANT_DIR / "leadschecker.csv",
    IMPORTANT_DIR / "leads.csv",
    IMPORTANT_DIR / "leads_rejected.csv",
    IMPORTANT_DIR / "leads_verified.csv",
    IMPORTANT_DIR / "leads_verify_rejected.csv",
    IMPORTANT_DIR / "leads_quarantine.csv",
]

CHECK_JOB_DIR = IMPORTANT_DIR / "check_runs" / "jobs"


def _csv_rows(path: Path) -> int:
    if not path.exists() or path.suffix.lower() not in {".csv", ".jsonl"}:
        return 0
    if path.suffix.lower() == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gather_paths(include_check_history: bool = False) -> list[Path]:
    paths: list[Path] = []
    for path in [*QUEUE_FILES, *QUEUE_LOG_FILES, *STATE_FILES, *IMPORTANT_FILES]:
        if path.exists():
            paths.append(path)
    if CHECK_JOB_DIR.exists():
        paths.extend(sorted(path for path in CHECK_JOB_DIR.glob("*.json") if path.is_file()))
    if include_check_history:
        history_root = IMPORTANT_DIR / "check_runs"
        if history_root.exists():
            for path in sorted(history_root.glob("*")):
                if path.is_file() and path.name != "jobs":
                    paths.append(path)
    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)
    return unique_paths


def _manifest_for(paths: list[Path], archive_name: str) -> dict[str, object]:
    queue_counts = {}
    state_summaries: dict[str, object] = {}
    manifest_files: list[dict[str, object]] = []
    existing_paths: list[Path] = []

    for path in paths:
        if not path.exists():
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue

        rel = str(path.relative_to(ROOT))
        existing_paths.append(path)
        manifest_files.append(
            {
                "path": rel,
                "size_bytes": stat.st_size,
                "sha256": _sha256(path),
            }
        )

        if path.suffix.lower() == ".csv" and (rel.startswith("data/shards/") or rel.startswith("_important/")):
            queue_counts[rel] = _csv_rows(path)
        if path.name == "sendgrid_daily_counters.json" and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            if isinstance(raw, dict):
                global_entry = raw.get("__global__", {}) if isinstance(raw.get("__global__"), dict) else {}
                state_summaries["sendgrid_daily_counters"] = {
                    "date": str(global_entry.get("date") or ""),
                    "global_sent": int(global_entry.get("sent") or 0),
                    "profiles": sorted(key for key in raw.keys() if key != "__global__"),
                }
        elif path.name == "important_leads_verify_state.json" and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            if isinstance(raw, dict):
                state_summaries["verify_checkpoint"] = {
                    "input_path": str(raw.get("input_path") or ""),
                    "next_row_index": int(raw.get("next_row_index") or 0),
                    "total_input_rows": int(raw.get("total_input_rows") or 0),
                    "completed": bool(raw.get("completed")),
                    "updated_at_utc": str(raw.get("updated_at_utc") or ""),
                }
        elif path.name == "leads_dashboard_state.json" and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            if isinstance(raw, dict):
                state_summaries["leads_dashboard_state"] = {
                    "input_path": str((raw.get("important_leads_paths") or {}).get("input_path") or ""),
                    "output_path": str((raw.get("important_leads_paths") or {}).get("output_path") or ""),
                    "rejected_path": str((raw.get("important_leads_paths") or {}).get("rejected_path") or ""),
                    "dispatch_source_mode": str((raw.get("important_leads_dispatch_source") or {}).get("dispatch_source_mode") or ""),
                }

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(ROOT),
        "archive_name": archive_name,
        "file_count": len(existing_paths),
        "files": manifest_files,
        "queue_counts": queue_counts,
        "state_summaries": state_summaries,
    }


def pack_archive(archive_path: Path, include_check_history: bool = False) -> dict[str, object]:
    paths = _gather_paths(include_check_history=include_check_history)
    if not paths:
        raise FileNotFoundError("No runtime files found to package.")
    manifest = _manifest_for(paths, archive_path.name)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    with tarfile.open(archive_path, "w:gz") as tar:
        for file_info in manifest["files"]:
            rel = str(file_info.get("path") or "").strip()
            if not rel:
                continue
            path = ROOT / rel
            if not path.exists():
                continue
            try:
                tar.add(path, arcname=rel, recursive=False)
            except FileNotFoundError:
                continue
        info = tarfile.TarInfo("runtime_handoff_manifest.json")
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        tar.addfile(info, fileobj=io.BytesIO(manifest_bytes))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package the runtime state needed to resume a send campaign on another machine.")
    parser.add_argument(
        "--archive",
        required=True,
        help="Output .tar.gz archive path.",
    )
    parser.add_argument(
        "--include-check-history",
        action="store_true",
        help="Include historical _important/check_runs artifacts in addition to the current runtime state.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_path = Path(args.archive).expanduser().resolve()
    manifest = pack_archive(archive_path, include_check_history=args.include_check_history)
    print(f"Created archive: {archive_path}")
    print(f"Included files: {manifest['file_count']}")
    print("Queue counts:")
    for path, count in sorted((manifest.get("queue_counts") or {}).items()):
        print(f"  {path}: {count}")
    verify = (manifest.get("state_summaries") or {}).get("verify_checkpoint", {})
    if verify:
        print(
            "Verify checkpoint: "
            f"next_row_index={verify.get('next_row_index')} "
            f"total_input_rows={verify.get('total_input_rows')} "
            f"completed={verify.get('completed')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
