#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sendgrid_hygiene import (  # noqa: E402
    WEBHOOK_DEDUPE_DB,
    WEBHOOK_EVENTS_JSONL,
    compute_webhook_dedupe_key,
    dedupe_webhook_events,
    load_events_jsonl,
    parse_iso_utc,
    write_events_jsonl,
)


def backup_if_exists(path: Path, backup_root: Path) -> Path | None:
    if not path.exists():
        return None
    backup_root.mkdir(parents=True, exist_ok=True)
    dest = backup_root / path.name
    shutil.copy2(path, dest)
    return dest


def rebuild(source_jsonl: Path, out_jsonl: Path, out_db: Path) -> dict[str, object]:
    events = load_events_jsonl(source_jsonl)
    if out_db.exists():
        out_db.unlink()

    deduped_events = []
    duplicates = 0
    for event in events:
        if not (event.get("dedupe_key") or "").strip():
            event["dedupe_key"] = compute_webhook_dedupe_key(event)
        reference = (
            parse_iso_utc(event.get("received_at_utc", ""))
            or parse_iso_utc(event.get("processed_at_utc", ""))
            or datetime.now(timezone.utc)
        )
        result = dedupe_webhook_events([event], out_db, reference_utc=reference)
        deduped_events.extend(result["unique_events"])
        duplicates += int(result["duplicates"] or 0)

    write_events_jsonl(deduped_events, out_jsonl)
    return {
        "source_events": len(events),
        "deduped_events": len(deduped_events),
        "duplicates_removed": duplicates,
        "out_jsonl": str(out_jsonl),
        "out_db": str(out_db),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Rebuild a deduped SendGrid webhook event store from JSONL history.")
    ap.add_argument("--source-jsonl", default=WEBHOOK_EVENTS_JSONL)
    ap.add_argument("--out-jsonl", default="sendgrid_events.deduped.jsonl")
    ap.add_argument("--out-dedupe-db", default="sendgrid_webhook_dedupe.rebuilt.sqlite3")
    ap.add_argument("--backup-dir", default="backups/webhook_rebuild")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Replace the live JSONL and dedupe SQLite DB after rebuilding. Existing live files are backed up first.",
    )
    args = ap.parse_args()

    source_jsonl = ROOT / args.source_jsonl
    out_jsonl = ROOT / args.out_jsonl
    out_db = ROOT / args.out_dedupe_db
    backup_root = ROOT / args.backup_dir / datetime.now().strftime("%Y%m%d_%H%M%S")

    result = rebuild(source_jsonl, out_jsonl, out_db)

    if args.apply:
        live_jsonl = ROOT / WEBHOOK_EVENTS_JSONL
        live_db = ROOT / WEBHOOK_DEDUPE_DB
        backup_if_exists(live_jsonl, backup_root)
        backup_if_exists(live_db, backup_root)
        shutil.copy2(out_jsonl, live_jsonl)
        shutil.copy2(out_db, live_db)
        result["applied"] = True
        result["backup_dir"] = str(backup_root)
    else:
        result["applied"] = False

    print(
        "REBUILT:"
        f" source_events={result['source_events']}"
        f" deduped_events={result['deduped_events']}"
        f" duplicates_removed={result['duplicates_removed']}"
        f" out_jsonl={result['out_jsonl']}"
        f" out_db={result['out_db']}"
        f" applied={result['applied']}"
    )
    if result.get("backup_dir"):
        print(f"Backup: {result['backup_dir']}")


if __name__ == "__main__":
    main()
