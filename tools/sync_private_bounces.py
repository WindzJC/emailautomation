#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from private_bounce_hygiene import sync_private_bounces


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="private_jc")
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--lookback-days", type=int, default=14)
    args = parser.parse_args()

    report = sync_private_bounces(
        profile_name=args.profile,
        folder=args.folder,
        lookback_days=args.lookback_days,
    )
    print(
        "PRIVATE BOUNCES:"
        f" scanned={report['scanned_messages']}"
        f" probable_bounces={report['probable_bounce_messages']}"
        f" matched={report['matched_messages']}"
        f" extracted={report['extracted_recipients']}"
        f" added_suppressed={report['added_suppressed']}"
        f" already_suppressed={report['already_suppressed']}"
    )
    print(f"REPORT: {report['report_path']}")


if __name__ == "__main__":
    main()
