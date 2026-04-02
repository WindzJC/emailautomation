from __future__ import annotations

import asyncio
import base64
import csv
import json
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import settings
import runtime_control
from dashboard_core import (
    build_dashboard_snapshot,
    save_dashboard_send_cap_per_profile,
)
from important_leads_workflow import (
    check_master_leads,
    dispatch_master_leads,
    important_leads_status,
)
from private_bounce_hygiene import (
    PRIVATE_BOUNCE_MONITOR_ENABLED,
    PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS,
    run_private_bounce_monitor_cycle,
)
from sendgrid_hygiene import (
    WEBHOOK_DEDUPE_DB,
    WEBHOOK_EVENTS_JSONL,
    append_events_jsonl,
    dedupe_webhook_events,
    normalize_webhook_events,
    update_suppressions_from_events,
)
from leads_workflow import (
    clean_uploaded_leads,
    preview_shard_cleaned_leads,
    save_uploaded_csv,
    shard_cleaned_leads,
    shard_status,
)

STATIC_DIR = settings.STATIC_DIR
SUPPRESSION_CSV = settings.SENDGRID_SUPPRESSIONS_PATH
WEBHOOK_EVENTS_PATH = settings.WEBHOOK_EVENTS_PATH
WEBHOOK_DEDUPE_PATH = settings.WEBHOOK_DEDUPE_PATH
IMPORTANT_LEADS_INPUT = settings.APP_ROOT / "_important" / "leadschecker.csv"
IMPORTANT_LEADS_OUTPUT = settings.APP_ROOT / "_important" / "leads.csv"
IMPORTANT_LEADS_REJECTED = settings.APP_ROOT / "_important" / "leads_rejected.csv"
app = FastAPI(title="Email Automation Live Dashboard")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SENDGRID_EVENT_PUBLIC_KEY = os.environ.get("SENDGRID_EVENT_PUBLIC_KEY", "").strip()
SENDGRID_SIG_HEADER = "X-Twilio-Email-Event-Webhook-Signature"
SENDGRID_TS_HEADER = "X-Twilio-Email-Event-Webhook-Timestamp"
PRIVATE_BOUNCE_PROFILE = "private_jc"
AUTOMATION_LOOP_SECONDS = max(15, min(60, max(30, int(PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS or 120)) // 2))


class SendCapPayload(BaseModel):
    send_cap_per_profile: int = Field(..., ge=1, le=100000)


class ColumnMappingPayload(BaseModel):
    email: str = ""
    author_name: str = ""
    book_title: str = ""


class CleanLeadsPayload(BaseModel):
    upload_filename: str
    mapping: ColumnMappingPayload | None = None
    remove_invalid_emails: bool = True
    dedupe_by_email: bool = True
    remove_suppressed: bool = True
    drop_role_emails: bool = False
    exclude_domains: List[str] = Field(default_factory=list)


class ShardLeadsPayload(BaseModel):
    cleaned_filename: str
    shard_count: int = Field(default=5, ge=1, le=5)
    strategy: str = Field(default="domain_balanced")


def _profile_runtime_active(profile_name: str) -> bool:
    try:
        snapshots = runtime_control.list_sender_snapshots(tail_lines=8)
    except Exception:
        return False
    active_states = {"starting", "running", "cooldown", "sleeping"}
    for snapshot in snapshots:
        if getattr(snapshot, "name", "") != profile_name:
            continue
        if getattr(snapshot, "tmux_dead", False):
            return False
        return str(getattr(snapshot, "runtime_state", "") or "") in active_states
    return False


def _run_background_automation_once() -> None:
    try:
        runtime_control.apply_delivery_guards()
    except Exception:
        pass
    if not PRIVATE_BOUNCE_MONITOR_ENABLED:
        return
    profile_active = _profile_runtime_active(PRIVATE_BOUNCE_PROFILE)
    try:
        run_private_bounce_monitor_cycle(
            profile_name=PRIVATE_BOUNCE_PROFILE,
            profile_active=profile_active,
            stop_profile=runtime_control.stop_sender,
            start_profile=runtime_control.start_sender,
        )
    except Exception:
        return


async def _background_automation_loop() -> None:
    while True:
        await asyncio.to_thread(_run_background_automation_once)
        await asyncio.sleep(AUTOMATION_LOOP_SECONDS)


@app.on_event("startup")
async def _startup_background_automation() -> None:
    if getattr(app.state, "automation_task", None) is None:
        app.state.automation_task = asyncio.create_task(_background_automation_loop())


@app.on_event("shutdown")
async def _shutdown_background_automation() -> None:
    task = getattr(app.state, "automation_task", None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    app.state.automation_task = None


def _csv_preview(path: Path, limit: int = 8) -> dict[str, object]:
    if not path.exists():
        return {"fieldnames": [], "preview_rows": [], "row_count": 0}
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(name or "").lstrip("\ufeff") for name in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        total = 0
        for row in reader:
            cleaned = {field: str(row.get(field, "") or "") for field in fieldnames}
            if not any(value.strip() for value in cleaned.values()):
                continue
            total += 1
            if len(rows) < limit:
                rows.append(cleaned)
    return {"fieldnames": fieldnames, "preview_rows": rows, "row_count": total}


@lru_cache(maxsize=1)
def _load_sendgrid_public_key():
    if not SENDGRID_EVENT_PUBLIC_KEY:
        return None
    key_bytes = base64.b64decode(SENDGRID_EVENT_PUBLIC_KEY)
    return serialization.load_der_public_key(key_bytes)


def _verify_sendgrid_signature(raw_body: bytes, signature_b64: str, timestamp: str) -> bool:
    public_key = _load_sendgrid_public_key()
    if public_key is None:
        return True
    signature = base64.b64decode((signature_b64 or "").strip())
    signed_payload = (timestamp or "").encode("utf-8") + raw_body
    try:
        public_key.verify(signature, signed_payload, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/snapshot")
def snapshot(
    hours: int = Query(default=24, ge=1, le=168),
    tail_lines: int = Query(default=12, ge=4, le=50),
) -> dict[str, object]:
    return build_dashboard_snapshot(activity_hours=hours, tail_lines=tail_lines)


@app.post("/api/start")
def start() -> JSONResponse:
    ok, message = runtime_control.start_all_senders()
    time.sleep(0.6)
    return JSONResponse({"ok": ok, "message": message, "snapshot": build_dashboard_snapshot()})


@app.post("/api/start/{profile_name}")
def start_profile(profile_name: str) -> JSONResponse:
    if not runtime_control.is_known_profile(profile_name):
        return JSONResponse({"ok": False, "message": f"Unknown profile: {profile_name}"}, status_code=404)
    ok, message = runtime_control.start_sender(profile_name)
    time.sleep(0.6)
    return JSONResponse({"ok": ok, "message": message, "snapshot": build_dashboard_snapshot()})


@app.post("/api/stop")
def stop() -> JSONResponse:
    ok, message = runtime_control.stop_all_senders()
    return JSONResponse({"ok": ok, "message": message, "snapshot": build_dashboard_snapshot()})


@app.post("/api/stop/{profile_name}")
def stop_profile(profile_name: str) -> JSONResponse:
    if not runtime_control.is_known_profile(profile_name):
        return JSONResponse({"ok": False, "message": f"Unknown profile: {profile_name}"}, status_code=404)
    ok, message = runtime_control.stop_sender(profile_name)
    return JSONResponse({"ok": ok, "message": message, "snapshot": build_dashboard_snapshot()})


@app.post("/api/archive-reset-logs")
def archive_reset_logs() -> JSONResponse:
    ok, message = runtime_control.archive_reset_logs()
    return JSONResponse({"ok": ok, "message": message, "snapshot": build_dashboard_snapshot()})


@app.post("/api/settings/send-cap")
def update_send_cap(payload: SendCapPayload) -> JSONResponse:
    settings = save_dashboard_send_cap_per_profile(payload.send_cap_per_profile)
    cap = int(settings.get("send_cap_per_profile") or payload.send_cap_per_profile)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Dashboard send cap saved: {cap} per sender.",
            "snapshot": build_dashboard_snapshot(),
        }
    )


@app.post("/api/leads/upload")
async def upload_leads(file: UploadFile = File(...)) -> JSONResponse:
    filename = (file.filename or "").strip()
    if not filename:
        return JSONResponse({"ok": False, "message": "Missing upload filename."}, status_code=400)
    content = await file.read()
    if not content:
        return JSONResponse({"ok": False, "message": "Uploaded file is empty."}, status_code=400)
    try:
        preview = save_uploaded_csv(filename, content)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Upload failed: {exc}"}, status_code=400)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Uploaded {preview['original_filename']} ({preview['row_count']} row(s)).",
            "upload": preview,
            "status": shard_status(),
        }
    )


@app.post("/api/leads/clean")
def clean_leads(payload: CleanLeadsPayload) -> JSONResponse:
    mapping = payload.mapping.model_dump() if payload.mapping else None
    try:
        report = clean_uploaded_leads(
            upload_filename=payload.upload_filename,
            mapping=mapping,
            remove_invalid_emails=payload.remove_invalid_emails,
            dedupe_by_email=payload.dedupe_by_email,
            remove_suppressed=payload.remove_suppressed,
            drop_role_emails=payload.drop_role_emails,
            exclude_domains=payload.exclude_domains,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead clean failed: {exc}"}, status_code=500)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Cleaned leads written to {report['cleaned_filename']} ({report['output_rows']} row(s) kept).",
            "clean": report,
            "status": shard_status(),
        }
    )


@app.post("/api/leads/check-important")
def check_important_leads() -> JSONResponse:
    try:
        report = check_master_leads(
            input_path=IMPORTANT_LEADS_INPUT,
            output_path=IMPORTANT_LEADS_OUTPUT,
            rejected_path=IMPORTANT_LEADS_REJECTED,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead check failed: {exc}"}, status_code=500)

    return JSONResponse(
        {
            "ok": True,
            "message": (
                f"Checked {IMPORTANT_LEADS_INPUT.name} into {IMPORTANT_LEADS_OUTPUT.name}. "
                f"Kept {int(report['cleaned_rows'] or 0)} row(s), rejected "
                f"{sum(int(report['reason_counts'].get(reason, 0)) for reason in report.get('reason_counts', {}))}."
            ),
            "check": report,
            "status": {**shard_status(), **important_leads_status()},
        }
    )


@app.post("/api/leads/dispatch-important")
def dispatch_important_leads() -> JSONResponse:
    try:
        report = dispatch_master_leads(
            master_path=IMPORTANT_LEADS_OUTPUT,
            rejected_path=IMPORTANT_LEADS_REJECTED,
            require_stopped=True,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=409)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead dispatch failed: {exc}"}, status_code=500)

    return JSONResponse(
        {
            "ok": True,
            "message": (
                f"Dispatch complete. Astra added {report['added_astra']} row(s), SendGrid added "
                f"{report['added_sendgrid']} row(s), skipped both {report['skipped_both']}."
            ),
            "dispatch": report,
            "status": {**shard_status(), **important_leads_status()},
            "snapshot": build_dashboard_snapshot(),
        }
    )


@app.post("/api/leads/shard")
def shard_leads(payload: ShardLeadsPayload) -> JSONResponse:
    active_snapshots = runtime_control.list_active_sender_snapshots(tail_lines=12)
    if active_snapshots:
        states = {snapshot.name: snapshot.runtime_state for snapshot in active_snapshots}
        return JSONResponse(
            {
                "ok": False,
                "error": "senders_active",
                "active_profiles": list(states.keys()),
                "states": states,
                "message": "Stop all senders before overwriting shards.",
            },
            status_code=409,
        )
    try:
        report = shard_cleaned_leads(
            cleaned_filename=payload.cleaned_filename,
            shard_count=payload.shard_count,
            strategy=payload.strategy,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Sharding failed: {exc}"}, status_code=500)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Shards updated from {report['source_cleaned_filename']} using {report['strategy']}.",
            "shard": report,
            "status": shard_status(),
            "snapshot": build_dashboard_snapshot(),
        }
    )


@app.post("/api/leads/shard/preview")
def preview_shard(payload: ShardLeadsPayload) -> JSONResponse:
    try:
        preview = preview_shard_cleaned_leads(
            cleaned_filename=payload.cleaned_filename,
            shard_count=payload.shard_count,
            strategy=payload.strategy,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Preview failed: {exc}"}, status_code=500)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Preview ready for {preview['source_cleaned_filename']}.",
            "preview": preview,
            "status": shard_status(),
        }
    )


@app.get("/api/leads/status")
def leads_status() -> JSONResponse:
    return JSONResponse({"ok": True, "status": {**shard_status(), **important_leads_status()}})


@app.post("/webhooks/sendgrid/events")
async def sendgrid_event_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    if SENDGRID_EVENT_PUBLIC_KEY:
        signature = request.headers.get(SENDGRID_SIG_HEADER, "")
        timestamp = request.headers.get(SENDGRID_TS_HEADER, "")
        if not signature or not timestamp:
            return JSONResponse({"ok": False, "message": "Missing SendGrid signature headers."}, status_code=401)
        try:
            verified = _verify_sendgrid_signature(raw_body, signature, timestamp)
        except Exception:
            return JSONResponse({"ok": False, "message": "Invalid SendGrid verification key or signature payload."}, status_code=400)
        if not verified:
            return JSONResponse({"ok": False, "message": "Invalid SendGrid webhook signature."}, status_code=401)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return JSONResponse({"ok": False, "message": "Invalid JSON payload."}, status_code=400)

    if not isinstance(payload, list):
        return JSONResponse({"ok": False, "message": "Expected JSON array."}, status_code=400)

    received_at = datetime.now(timezone.utc)
    normalized = normalize_webhook_events(
        [item for item in payload if isinstance(item, dict)],
        source_log=WEBHOOK_EVENTS_JSONL,
        received_at_utc=received_at,
    )
    dedupe_result = dedupe_webhook_events(normalized, WEBHOOK_DEDUPE_PATH, reference_utc=received_at)
    unique_events = list(dedupe_result.get("unique_events", []))
    appended = append_events_jsonl(unique_events, WEBHOOK_EVENTS_PATH)
    suppression_summary = update_suppressions_from_events(unique_events, SUPPRESSION_CSV)
    auto_stops = runtime_control.apply_delivery_guards()
    json_safe_summary = {
        "updated_events": int(suppression_summary.get("updated_events", 0) or 0),
        "records_total": int(suppression_summary.get("records_total", 0) or 0),
        "total_perm": int(suppression_summary.get("total_perm", 0) or 0),
        "total_temp_active": int(suppression_summary.get("total_temp_active", 0) or 0),
    }
    return JSONResponse(
        {
            "ok": True,
            "received": len(payload),
            "normalized": len(normalized),
            "stored": appended,
            "duplicates_ignored": int(dedupe_result.get("duplicates", 0) or 0),
            "suppression_summary": json_safe_summary,
            "auto_stops": auto_stops,
        }
    )


@app.websocket("/ws")
async def websocket_snapshot_stream(
    websocket: WebSocket,
    hours: int = Query(default=24, ge=1, le=168),
    tail_lines: int = Query(default=12, ge=4, le=50),
) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(build_dashboard_snapshot(activity_hours=hours, tail_lines=tail_lines))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
