#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dispatch_transaction_guard import (  # noqa: E402
    DispatchTransactionError,
    rollback_incomplete_dispatch_transaction,
)


def main() -> int:
    try:
        result = rollback_incomplete_dispatch_transaction()
    except DispatchTransactionError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
