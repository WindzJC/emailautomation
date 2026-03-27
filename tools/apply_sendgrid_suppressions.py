#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sendgrid_hygiene import clean_recipient_shards, parse_activity_file, update_suppressions_from_events


def parse_email_list(value: str) -> set[str]:
    return {str(raw or "").strip().lower() for raw in (value or "").split(",") if str(raw or "").strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity-log", required=True)
    ap.add_argument("--suppression-csv", required=True)
    ap.add_argument("--shards-glob", required=True)
    ap.add_argument("--backup-dir", default="backups")
    ap.add_argument("--ttl-blocked-days", type=int, default=30)
    ap.add_argument("--ttl-default-days", type=int, default=14)
    ap.add_argument("--report-path", default="cleaning_report.json")
    ap.add_argument("--source-timezone", default="", help="IANA timezone for processed-at timestamps.")
    ap.add_argument("--always-send", default="astraproductionsbyjc@gmail.com")
    args = ap.parse_args()

    activity_log = Path(args.activity_log)
    suppression_csv = Path(args.suppression_csv)
    shard_paths = [Path(path) for path in sorted(glob.glob(args.shards_glob))]

    events = parse_activity_file(activity_log, source_timezone=args.source_timezone)
    suppression_summary = update_suppressions_from_events(
        events,
        suppression_csv,
        ttl_blocked_days=args.ttl_blocked_days,
        ttl_default_days=args.ttl_default_days,
    )
    cleaning_report = clean_recipient_shards(
        suppression_csv,
        shard_paths,
        Path(args.backup_dir),
        Path(args.report_path),
        preserve_emails=parse_email_list(args.always_send),
    )
    print(
        "APPLIED:"
        f" parsed_events={len(events)}"
        f" records_total={suppression_summary['records_total']}"
        f" total_perm={suppression_summary['total_perm']}"
        f" total_temp_active={suppression_summary['total_temp_active']}"
        f" total_removed={cleaning_report['total_removed']}"
        f" report={args.report_path}"
    )


if __name__ == "__main__":
    main()
