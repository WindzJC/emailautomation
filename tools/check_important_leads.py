#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from important_leads_workflow import (  # noqa: E402
    MASTER_INPUT_PATH,
    MASTER_OUTPUT_PATH,
    MASTER_REJECTED_PATH,
    check_master_leads,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check _important/leadschecker.csv into the cleaned master leads file."
    )
    parser.add_argument("--in", dest="input_path", default=str(MASTER_INPUT_PATH), help="Input CSV path.")
    parser.add_argument("--out", dest="output_path", default=str(MASTER_OUTPUT_PATH), help="Cleaned master output path.")
    parser.add_argument(
        "--rejected",
        dest="rejected_path",
        default=str(MASTER_REJECTED_PATH),
        help="Rejected rows output path.",
    )
    parser.add_argument(
        "--no_mx",
        action="store_true",
        help="Accepted for compatibility. MX checks are not used in this workflow.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        report = check_master_leads(
            input_path=Path(args.input_path),
            output_path=Path(args.output_path),
            rejected_path=Path(args.rejected_path),
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"INPUT: {report['input_label']}")
    print(f"OUTPUT: {report['output_label']}")
    print(f"REJECTED: {report['rejected_label']}")
    print(
        "SUMMARY:"
        f" input_rows={report['input_rows']}"
        f" cleaned_rows={report['cleaned_rows']}"
        f" duplicates_removed={report['duplicates_removed']}"
        f" invalid_removed={report['invalid_removed']}"
        f" suppressed_removed={report['suppressed_removed']}"
        f" suspicious_flagged={report['suspicious_flagged']}"
        f" safe_fixes_applied={report['safe_fixes_applied']}"
    )
    if report.get("reason_counts"):
        print("REASONS:")
        for reason, count in sorted(report["reason_counts"].items(), key=lambda item: (-item[1], item[0])):
            print(f"  {count:6}  {reason}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
