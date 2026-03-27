#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sendgrid_hygiene import load_events_jsonl, update_suppressions_from_events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed-events", required=True)
    ap.add_argument("--suppression-csv", required=True)
    ap.add_argument("--ttl-blocked-days", type=int, default=30)
    ap.add_argument("--ttl-default-days", type=int, default=14)
    args = ap.parse_args()

    events = load_events_jsonl(Path(args.parsed_events))
    summary = update_suppressions_from_events(
        events,
        Path(args.suppression_csv),
        ttl_blocked_days=args.ttl_blocked_days,
        ttl_default_days=args.ttl_default_days,
    )
    print(
        "SUPPRESSIONS:"
        f" updated_events={summary['updated_events']}"
        f" records_total={summary['records_total']}"
        f" total_perm={summary['total_perm']}"
        f" total_temp_active={summary['total_temp_active']}"
    )


if __name__ == "__main__":
    main()
