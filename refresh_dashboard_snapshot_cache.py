from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from time import perf_counter

import live_dashboard as dashboard

CACHE_PATH = dashboard.DASHBOARD_SNAPSHOT_CACHE_PATH


def main() -> None:
    started = perf_counter()

    snapshot = dashboard._build_live_snapshot(
        activity_hours=24,
        tail_lines=12,
    )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hours": 24,
        "tail_lines": 12,
        "snapshot": snapshot,
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = CACHE_PATH.with_name(
        f".{CACHE_PATH.name}.{os.getpid()}.tmp"
    )

    temporary_path.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )

    temporary_path.replace(CACHE_PATH)

    elapsed = perf_counter() - started
    profiles = len(snapshot.get("profiles", []))

    print(
        f"CACHE REFRESHED: {CACHE_PATH} "
        f"BUILD_TIME={elapsed:.3f}s PROFILES={profiles}",
        flush=True,
    )


if __name__ == "__main__":
    main()
