#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sendgrid_hygiene import parse_activity_file, write_events_jsonl


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity-log", required=True)
    ap.add_argument("--out", required=True, help="Parsed events output (.jsonl)")
    ap.add_argument("--source-timezone", default="", help="IANA timezone for processed-at timestamps.")
    args = ap.parse_args()

    events = parse_activity_file(Path(args.activity_log), source_timezone=args.source_timezone)
    out_path = Path(args.out)
    write_events_jsonl(events, out_path)
    print(f"PARSED: events={len(events)} out={out_path}")


if __name__ == "__main__":
    main()
