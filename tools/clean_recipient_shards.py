#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sendgrid_hygiene import clean_recipient_shards


def parse_email_list(value: str) -> set[str]:
    return {str(raw or "").strip().lower() for raw in (value or "").split(",") if str(raw or "").strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suppression-csv", required=True)
    ap.add_argument("--shards-glob", required=True)
    ap.add_argument("--backup-dir", default="backups")
    ap.add_argument("--report-path", default="cleaning_report.json")
    ap.add_argument("--always-send", default="astraproductionsbyjc@gmail.com")
    args = ap.parse_args()

    shard_paths = [Path(path) for path in sorted(glob.glob(args.shards_glob))]
    report = clean_recipient_shards(
        Path(args.suppression_csv),
        shard_paths,
        Path(args.backup_dir),
        Path(args.report_path),
        preserve_emails=parse_email_list(args.always_send),
    )
    print(
        f"CLEANED: shards={len(shard_paths)} total_removed={report['total_removed']} "
        f"report={args.report_path}"
    )


if __name__ == "__main__":
    main()
