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

    # Lead Ops reconstruction is intentionally performed here, outside the
    # HTTP request path. In production this can be expensive because it
    # reconciles staged-run metadata, source CSVs, queues, progress and
    # safety state.
    leads_status = dict(dashboard._combined_leads_status())

    generated_at_utc = datetime.now(timezone.utc).isoformat()

    leads_status["status_cache_ready"] = True
    leads_status["status_cache_source"] = "persisted_dashboard_refresh"
    leads_status["status_cache_generated_at_utc"] = generated_at_utc

    payload = {
        "generated_at_utc": generated_at_utc,
        "hours": 24,
        "tail_lines": 12,
        "snapshot": snapshot,
        "leads_status": leads_status,
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
    recontact_rows = int(
        leads_status.get("dispatch_eligible_row_count") or 0
    )
    source_mode = str(
        leads_status.get("dispatch_source_mode") or ""
    )

    print(
        f"CACHE REFRESHED: {CACHE_PATH} "
        f"BUILD_TIME={elapsed:.3f}s "
        f"PROFILES={profiles} "
        f"LEADS_MODE={source_mode} "
        f"LEADS_ELIGIBLE={recontact_rows}",
        flush=True,
    )


if __name__ == "__main__":
    main()
