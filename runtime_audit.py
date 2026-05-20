from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import settings


SGT = timezone(timedelta(hours=8))
HEARTBEAT_PATH = settings.STATE_DIR / "runtime_heartbeat.json"
RESUME_AUDIT_PATH = settings.STATE_DIR / "resume_audit_latest.json"
LIFECYCLE_PATH = settings.STATE_DIR / "runtime_lifecycle.jsonl"
STALE_HEARTBEAT_SECONDS = 120


def now_sgt() -> datetime:
    return datetime.now(SGT)


def iso_sgt() -> str:
    return now_sgt().replace(microsecond=0).isoformat()


def redact_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if "@" not in email:
        return ""
    local, domain = email.rsplit("@", 1)
    if not local or not domain:
        return ""
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:10]
    return f"{local[:1]}***@{domain}#{digest}"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        Path(tmp_name).replace(path)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass


def write_lifecycle_event(event_type: str, **fields: Any) -> None:
    event = {
        "event_type": str(event_type or "").strip().upper(),
        "timestamp_sgt": iso_sgt(),
        "pid": os.getpid(),
    }
    for key, value in fields.items():
        if value is None:
            continue
        if key in {"email", "recipient", "to_email", "last_recipient"}:
            event[key] = redact_email(str(value))
        else:
            event[key] = value
    LIFECYCLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LIFECYCLE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def write_app_start() -> None:
    generate_resume_audit()
    write_lifecycle_event("APP_START")


def write_app_shutdown() -> None:
    write_lifecycle_event("APP_SHUTDOWN")
    heartbeat = _read_json(HEARTBEAT_PATH)
    heartbeat["last_action"] = "APP_SHUTDOWN"
    heartbeat["timestamp_sgt"] = iso_sgt()
    heartbeat["pid"] = os.getpid()
    heartbeat["current_worker_status"] = heartbeat.get("current_worker_status") or {}
    _write_json_atomic(HEARTBEAT_PATH, heartbeat)


def update_worker_heartbeat(
    *,
    profile: str,
    status: str,
    app_started_monotonic: float,
    sent_this_run: int = 0,
    errors_this_run: int = 0,
    last_recipient: str = "",
    last_action: str = "",
    queue_file: str = "",
    pending_count: Optional[int] = None,
    terminal: bool = False,
) -> None:
    profile_name = str(profile or "").strip() or "unknown"
    heartbeat = _read_json(HEARTBEAT_PATH)
    workers = heartbeat.get("current_worker_status")
    if not isinstance(workers, dict):
        workers = {}

    worker = {
        "profile": profile_name,
        "pid": os.getpid(),
        "status": str(status or "").strip(),
        "updated_sgt": iso_sgt(),
        "sent_this_run": int(sent_this_run or 0),
        "errors_this_run": int(errors_this_run or 0),
        "last_recipient_hash_or_redacted_email": redact_email(last_recipient),
        "last_action": str(last_action or "").strip(),
        "queue_file": str(queue_file or "").strip(),
    }
    if pending_count is not None:
        worker["starting_pending_count"] = int(pending_count or 0)
    workers[profile_name] = worker

    active_profiles = [
        name
        for name, item in workers.items()
        if isinstance(item, dict) and str(item.get("status") or "").lower() not in {"done", "stopped", "error", "interrupted"}
    ]

    heartbeat.update(
        {
            "timestamp_sgt": iso_sgt(),
            "pid": os.getpid(),
            "active_profiles": sorted(active_profiles),
            "current_worker_status": workers,
            "sent_this_run": {
                name: int(item.get("sent_this_run") or 0)
                for name, item in workers.items()
                if isinstance(item, dict)
            },
            "errors_this_run": {
                name: int(item.get("errors_this_run") or 0)
                for name, item in workers.items()
                if isinstance(item, dict)
            },
            "last_action": str(last_action or status or "").strip(),
            "app_uptime_seconds": max(0, int(time.monotonic() - app_started_monotonic)),
        }
    )
    _write_json_atomic(HEARTBEAT_PATH, heartbeat)
    if terminal:
        event_type = "WORKER_DONE" if str(status or "").lower() in {"done", "stopped"} else "WORKER_INTERRUPTED"
        write_lifecycle_event(
            event_type,
            profile=profile_name,
            reason=str(last_action or status or "").strip(),
            sent_this_run=int(sent_this_run or 0),
            error_count=int(errors_this_run or 0),
        )


def generate_resume_audit() -> Dict[str, Any]:
    heartbeat = _read_json(HEARTBEAT_PATH)
    if not heartbeat:
        return {}
    timestamp_raw = str(heartbeat.get("timestamp_sgt") or "").strip()
    try:
        last_heartbeat = datetime.fromisoformat(timestamp_raw)
    except Exception:
        last_heartbeat = None
    age_seconds = int((now_sgt() - last_heartbeat).total_seconds()) if last_heartbeat else None
    active_profiles = list(heartbeat.get("active_profiles") or [])
    interrupted = bool(active_profiles) and (age_seconds is None or age_seconds > STALE_HEARTBEAT_SECONDS)
    previous_clean = not interrupted
    reasons = []
    if interrupted:
        reasons.append("Last heartbeat is stale while profiles were marked active.")
    if not active_profiles:
        reasons.append("No active profiles were recorded in the last heartbeat.")
    if str(heartbeat.get("last_action") or "").upper() == "APP_SHUTDOWN":
        reasons.append("Previous app shutdown marker was recorded.")

    audit = {
        "generated_at_sgt": iso_sgt(),
        "last_heartbeat_time_sgt": timestamp_raw,
        "heartbeat_age_seconds": age_seconds,
        "previous_run_appears_clean": previous_clean,
        "last_known_active_profiles": active_profiles,
        "last_known_worker_status": heartbeat.get("current_worker_status") or {},
        "recommendation": {
            "safe_to_resume": previous_clean,
            "reasons": reasons,
        },
    }
    _write_json_atomic(RESUME_AUDIT_PATH, audit)
    return audit
