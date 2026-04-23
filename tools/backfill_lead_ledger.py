from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lead_ledger import backfill_default_csv_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill the lead ledger from existing important-leads CSV outputs.")
    parser.add_argument("--db-path", default="", help="Optional SQLite ledger path. Defaults to the managed state path.")
    parser.add_argument("--run-id", default="", help="Optional run id to stamp onto import events.")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser() if str(args.db_path or "").strip() else None
    if db_path:
        report = backfill_default_csv_outputs(db_path=db_path, run_id=args.run_id)
    else:
        report = backfill_default_csv_outputs(run_id=args.run_id)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
