# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import os
import re
import secrets
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import List

try:
    from cryptography.exceptions import InvalidSignature
except Exception:  # pragma: no cover - dependency fallback
    class InvalidSignature(Exception):
        pass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import (
    FastAPI,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import load_workbook
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

try:
    import importlib
    defuse_stdlib = importlib.import_module("defusedxml").defuse_stdlib
except Exception:  # pragma: no cover - dependency fallback
    defuse_stdlib = None

import runtime_control
import runtime_audit
import settings
from dashboard_core import (
    SENDGRID_PROFILES,
    build_dashboard_snapshot,
    load_dashboard_run_settings,
    save_dashboard_send_cap_per_profile,
)
from important_leads_verify import (
    TRIAGE_MODE_FAST,
    TRIAGE_MODE_STRICT,
    TRIAGE_PATHS_STATE_KEY,
    TRIAGE_STATE_KEY,
    _triage_path_state_labels,
    fast_triage_master_leads,
    important_leads_triage_path_state,
    important_leads_verify_path_state,
    important_leads_verify_status,
    verify_master_leads,
)
from important_leads_workflow import (
    DISPATCH_CAP_ALL,
    DISPATCH_SOURCE_CLEANED,
    DISPATCH_SOURCE_STRICT_VERIFIED,
    DISPATCH_SOURCE_TRIAGED_KEEP,
    MASTER_DISPATCH_STATE_KEY,
    STRICT_VERIFIED_PATH,
    TRIAGED_KEEP_PATH,
    ImportantLeadsCheckError,
    check_master_leads,
    confirm_dispatch_preview,
    important_leads_path_state,
    important_leads_status,
    preview_dispatch_master_leads,
    validate_dispatch_preview,
)
from lead_ledger import (
    apply_quarantine_review_action,
    connect_lead_ledger,
    ingest_send_outcome_events,
    list_quarantine_review_lead_ids,
    list_quarantine_review_leads,
    load_quarantine_review_lead,
    load_recent_quarantine_review_actions,
)
from leads_workflow import (
    clean_uploaded_leads,
    iso_utc,
    preview_shard_cleaned_leads,
    save_state,
    save_uploaded_csv,
    shard_cleaned_leads,
    shard_status,
    timestamp_slug,
)
from tools.package_campaign_handoff import pack_archive
from private_bounce_hygiene import (
    PRIVATE_BOUNCE_MONITOR_ENABLED,
    PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS,
    run_private_bounce_monitor_cycle,
)
from provider_pacing import mark_recovery_started, provider_pacing_status
from send_shard import PROFILES
from sendgrid_hygiene import (
    WEBHOOK_EVENTS_JSONL,
    append_events_jsonl,
    dedupe_webhook_events,
    normalize_webhook_events,
    update_suppressions_from_events,
)

if defuse_stdlib is not None:
    try:
        defuse_stdlib()
    except Exception:
        pass


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return max(minimum, int(default))
    try:
        return max(minimum, int(raw))
    except Exception:
        return max(minimum, int(default))


def _lead_ledger_db_path() -> Path:
    return Path(getattr(settings, "LEAD_LEDGER_DB_PATH", settings.STATE_DIR / "lead_ledger.sqlite3"))

STATIC_DIR = settings.STATIC_DIR
SUPPRESSION_CSV = settings.SENDGRID_SUPPRESSIONS_PATH
WEBHOOK_EVENTS_PATH = settings.WEBHOOK_EVENTS_PATH
WEBHOOK_DEDUPE_PATH = settings.WEBHOOK_DEDUPE_PATH
IMPORTANT_LEADS_INPUT = settings.APP_ROOT / "_important" / "leadschecker.csv"
IMPORTANT_LEADS_OUTPUT = settings.APP_ROOT / "_important" / "leads.csv"
IMPORTANT_LEADS_REJECTED = settings.APP_ROOT / "_important" / "leads_rejected.csv"
IMPORTANT_LEADS_CHECK_RUNS = settings.APP_ROOT / "_important" / "check_runs"
IMPORTANT_LEADS_CHECK_JOBS = IMPORTANT_LEADS_CHECK_RUNS / "jobs"
IMPORTANT_LEADS_VERIFY_JOBS = settings.APP_ROOT / "_important" / "verify_jobs"
IMPORTANT_LEADS_DISPATCH_JOBS = settings.APP_ROOT / "_important" / "dispatch_jobs"
IMPORTANT_LEADS_DISPATCH_PREVIEWS = IMPORTANT_LEADS_DISPATCH_JOBS / "previews"
IMPORTANT_LEADS_PASTE_WARNING_ROWS = _int_env("IMPORTANT_LEADS_PASTE_WARNING_ROWS", 250)
IMPORTANT_LEADS_PASTE_MAX_ROWS = max(IMPORTANT_LEADS_PASTE_WARNING_ROWS, _int_env("IMPORTANT_LEADS_PASTE_MAX_ROWS", 1000))
IMPORTANT_LEADS_CHECK_UPLOAD_MAX_BYTES = _int_env("DASHBOARD_CHECK_UPLOAD_MAX_BYTES", 150 * 1024 * 1024)
app = FastAPI(title="Email Automation Live Dashboard")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_AUTH_PUBLIC_PATHS = {
    "/",
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
    "/webhooks/sendgrid/events",
}
_AUTH_PUBLIC_PREFIXES = ("/static/",)
_AUTH_PROTECTED_DOC_PATHS = {"/docs", "/redoc", "/openapi.json"}
_AUTH_SESSION_KEY = "dashboard_authenticated"


class DashboardAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if request.method == "OPTIONS" or path in _AUTH_PUBLIC_PATHS or any(path.startswith(prefix) for prefix in _AUTH_PUBLIC_PREFIXES):
            return await call_next(request)
        if path in _AUTH_PROTECTED_DOC_PATHS or path.startswith("/api/") or path == "/ws":
            if not settings.DASHBOARD_AUTH_PASSWORD:
                return JSONResponse(
                    {"ok": False, "message": "Dashboard auth is not configured."},
                    status_code=503,
                )
            if not bool(request.session.get(_AUTH_SESSION_KEY)):
                return JSONResponse(
                    {"ok": False, "message": "Authentication required."},
                    status_code=401,
                )
        return await call_next(request)


app.add_middleware(DashboardAuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.DASHBOARD_SESSION_SECRET,
    session_cookie=settings.DASHBOARD_AUTH_COOKIE_NAME,
    same_site="lax",
    https_only=False,
)

SENDGRID_EVENT_PUBLIC_KEY = os.environ.get("SENDGRID_EVENT_PUBLIC_KEY", "").strip()
SENDGRID_SIG_HEADER = "X-Twilio-Email-Event-Webhook-Signature"
SENDGRID_TS_HEADER = "X-Twilio-Email-Event-Webhook-Timestamp"
PRIVATE_BOUNCE_PROFILE = "private_jc"
AUTOMATION_LOOP_SECONDS = max(15, min(60, max(30, int(PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS or 120)) // 2))
DASHBOARD_AUTO_START_STATE_PATH = settings.STATE_DIR / "dashboard_auto_start_state.json"
DASHBOARD_TIMER_STATE_PATH = settings.STATE_DIR / "dashboard_timer_state.json"
AUTO_START_RETRY_MINUTES = 10
_PARSER_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


class SendCapPayload(BaseModel):
    send_cap_per_profile: int = Field(..., ge=1, le=100000)


class ColumnMappingPayload(BaseModel):
    email: str = ""
    first_name: str = ""
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


class ImportantLeadPathsPayload(BaseModel):
    input_path: str = ""
    output_path: str = ""
    rejected_path: str = ""
    dispatch_source_mode: str = DISPATCH_SOURCE_TRIAGED_KEEP
    input_text: str = ""


class ImportantLeadVerifyPayload(BaseModel):
    input_path: str = ""
    verified_path: str = ""
    rejected_path: str = ""
    quarantine_path: str = ""
    mode: str = TRIAGE_MODE_FAST


class ImportantLeadDispatchPayload(BaseModel):
    input_path: str = ""
    output_path: str = ""
    rejected_path: str = ""
    dispatch_source_mode: str = DISPATCH_SOURCE_TRIAGED_KEEP
    dispatch_cap: str = DISPATCH_CAP_ALL
    preview_id: str = ""


class QuarantineReviewActionPayload(BaseModel):
    lead_ids: list[str] = Field(default_factory=list)
    excluded_lead_ids: list[str] = Field(default_factory=list)
    action: str = ""
    operator_note: str = ""
    select_all_filtered: bool = False
    reason_code: str = ""
    stage: str = ""
    status: str = "QUARANTINE"
    sort: str = "score_desc"


class DashboardAuthPayload(BaseModel):
    username: str = ""
    password: str = ""


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


def _resolve_dashboard_csv_path(raw_value: str, default_path: Path) -> Path:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return default_path
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", candidate):
        raise ValueError("Leads paths must stay inside this workspace.")
    path = Path(candidate)
    if not path.is_absolute():
        path = settings.APP_ROOT / path
    resolved_root = settings.APP_ROOT.resolve()
    resolved_path = path.resolve(strict=False)
    if resolved_path.suffix.lower() != ".csv":
        raise ValueError("Leads paths must point to .csv files.")
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("Leads paths must stay inside this workspace.")
    return resolved_path


def _resolve_dashboard_csv_path_or_default(raw_value: str, default_path: Path) -> Path:
    try:
        return _resolve_dashboard_csv_path(raw_value, default_path)
    except ValueError:
        return default_path.resolve(strict=False)


def _important_path_labels_for_state(input_path: Path, output_path: Path, rejected_path: Path) -> dict[str, str]:
    root = settings.APP_ROOT.resolve()

    def label(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(root))
        except Exception:
            return str(path)

    return {
        "input_path": label(input_path),
        "output_path": label(output_path),
        "rejected_path": label(rejected_path),
    }


def _important_verify_path_labels_for_state(input_path: Path, verified_path: Path, rejected_path: Path, quarantine_path: Path) -> dict[str, str]:
    root = settings.APP_ROOT.resolve()

    def label(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(root))
        except Exception:
            return str(path)

    return {
        "input_path": label(input_path),
        "verified_path": label(verified_path),
        "rejected_path": label(rejected_path),
        "quarantine_path": label(quarantine_path),
    }


def _important_triage_path_labels_for_state(input_path: Path, keep_path: Path, rejected_path: Path, quarantine_path: Path) -> dict[str, str]:
    root = settings.APP_ROOT.resolve()

    def label(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(root))
        except Exception:
            return str(path)

    return {
        "input_path": label(input_path),
        "keep_path": label(keep_path),
        "rejected_path": label(rejected_path),
        "quarantine_path": label(quarantine_path),
    }


def _important_dispatch_source_labels_for_state(mode: str) -> dict[str, str]:
    normalized = str(mode or "").strip().lower() or DISPATCH_SOURCE_TRIAGED_KEEP
    aliases = {
        "verified": DISPATCH_SOURCE_TRIAGED_KEEP,
        "fast_triage": DISPATCH_SOURCE_TRIAGED_KEEP,
        "fast_triage_keep": DISPATCH_SOURCE_TRIAGED_KEEP,
        "strict": DISPATCH_SOURCE_STRICT_VERIFIED,
        "strict_public_proof": DISPATCH_SOURCE_STRICT_VERIFIED,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {DISPATCH_SOURCE_TRIAGED_KEEP, DISPATCH_SOURCE_STRICT_VERIFIED, DISPATCH_SOURCE_CLEANED}:
        normalized = DISPATCH_SOURCE_TRIAGED_KEEP
    return {"dispatch_source_mode": normalized}


def _important_check_batch_policy() -> dict[str, object]:
    return {
        "paste_mode": "small_manual_only",
        "paste_warning_rows": IMPORTANT_LEADS_PASTE_WARNING_ROWS,
        "paste_max_rows": IMPORTANT_LEADS_PASTE_MAX_ROWS,
        "upload_required_rows": IMPORTANT_LEADS_PASTE_MAX_ROWS,
        "upload_recommended_rows": IMPORTANT_LEADS_PASTE_WARNING_ROWS,
    }


def _important_check_job_path(job_id: str) -> Path:
    return IMPORTANT_LEADS_CHECK_JOBS / f"{job_id}.json"


def _load_important_check_job(job_id: str) -> dict[str, object]:
    path = _important_check_job_path(job_id)
    if not path.exists():
        raise FileNotFoundError(f"Check job not found: {job_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _save_important_check_job(job: dict[str, object]) -> None:
    job_id = str(job.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("Missing check job id.")
    IMPORTANT_LEADS_CHECK_JOBS.mkdir(parents=True, exist_ok=True)
    payload = dict(job)
    payload["updated_at_utc"] = iso_utc()
    write_path = _important_check_job_path(job_id)
    tmp_path = write_path.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(write_path)
    settings.secure_private_file(write_path)


def _important_check_job_with_progress(job: dict[str, object]) -> dict[str, object]:
    payload = dict(job)
    total_rows = max(0, int(payload.get("total_input_rows") or 0))
    processed_rows = max(0, int(payload.get("processed_rows") or 0))
    remaining_rows = max(0, int(payload.get("remaining_rows") or max(0, total_rows - processed_rows)))
    if "progress_percent" not in payload or payload.get("progress_percent") in {"", None}:
        if total_rows > 0:
            payload["progress_percent"] = round(min(100.0, max(0.0, (processed_rows / total_rows) * 100)), 1)
        elif str(payload.get("status") or "") == "completed":
            payload["progress_percent"] = 100
        else:
            payload["progress_percent"] = 0
    payload["processed_rows"] = processed_rows
    payload["remaining_rows"] = remaining_rows
    if payload.get("source_sheet") and not payload.get("current_sheet"):
        payload["current_sheet"] = payload.get("source_sheet")
    return payload


def _find_active_important_check_job() -> dict[str, object] | None:
    if not IMPORTANT_LEADS_CHECK_JOBS.exists():
        return None
    active_statuses = {"queued", "running", "checking", "auto_triage_running"}
    candidates: list[tuple[float, dict[str, object]]] = []
    for path in IMPORTANT_LEADS_CHECK_JOBS.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or job.get("stage") or "").strip().lower()
        if status not in active_statuses:
            continue
        try:
            sort_key = path.stat().st_mtime
        except Exception:
            sort_key = 0.0
        candidates.append((sort_key, _important_check_job_with_progress(job)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _parse_iso_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _check_job_created_sort_key(job: dict[str, object], path: Path | None = None) -> float:
    created = _parse_iso_timestamp(job.get("created_at_utc"))
    if created:
        return created.timestamp()
    if path is not None:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0
    return 0.0


def _has_newer_important_check_job(job: dict[str, object]) -> bool:
    if not IMPORTANT_LEADS_CHECK_JOBS.exists():
        return False
    job_id = str(job.get("job_id") or "").strip()
    current_key = _check_job_created_sort_key(job, _important_check_job_path(job_id) if job_id else None)
    for path in IMPORTANT_LEADS_CHECK_JOBS.glob("*.json"):
        try:
            other = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(other, dict):
            continue
        other_id = str(other.get("job_id") or path.stem).strip()
        if other_id == job_id:
            continue
        if _check_job_created_sort_key(other, path) > current_key:
            return True
    return False


def _auto_triage_already_running(exclude_check_job_id: str = "") -> bool:
    active_verify = _find_active_dashboard_job(IMPORTANT_LEADS_VERIFY_JOBS)
    if active_verify and str(active_verify.get("mode") or "").upper() == TRIAGE_MODE_FAST:
        return True
    if not IMPORTANT_LEADS_CHECK_JOBS.exists():
        return False
    for path in IMPORTANT_LEADS_CHECK_JOBS.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(job, dict):
            continue
        if str(job.get("job_id") or path.stem).strip() == exclude_check_job_id:
            continue
        if str(job.get("auto_triage_status") or "").strip().lower() == "running":
            return True
    return False


def _file_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def _copy_csv_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(f"{destination.suffix}.{os.getpid()}.tmp")
    shutil.copyfile(source, tmp_path)
    tmp_path.replace(destination)
    settings.secure_private_file(destination)


def _promote_auto_triage_outputs(
    *,
    staged_keep_path: Path,
    staged_rejected_path: Path,
    staged_quarantine_path: Path,
    keep_path: Path,
    rejected_path: Path,
    quarantine_path: Path,
) -> None:
    _copy_csv_atomic(staged_keep_path, keep_path)
    _copy_csv_atomic(staged_rejected_path, rejected_path)
    _copy_csv_atomic(staged_quarantine_path, quarantine_path)


def _run_auto_fast_triage_after_check(job: dict[str, object]) -> dict[str, object]:
    job_id = str(job.get("job_id") or "").strip()
    if not job_id:
        return job
    if str(job.get("source_mode") or "").strip() != "uploaded_file":
        job["auto_triage_status"] = "skipped"
        job["auto_triage_skip_reason"] = "not_upload_check"
        return job
    if str(job.get("status") or "").strip().lower() in {"failed", "canceled", "cancelled"} or job.get("cancel_requested"):
        job["auto_triage_status"] = "skipped"
        job["auto_triage_skip_reason"] = "check_not_successful"
        return job
    existing_status = str(job.get("auto_triage_status") or "").strip().lower()
    if existing_status in {"running", "completed", "failed", "skipped"}:
        return job

    output_path = Path(str(job.get("output_path") or ""))
    rejected_path = Path(str(job.get("rejected_path") or ""))
    expected_output = IMPORTANT_LEADS_OUTPUT.resolve(strict=False)
    expected_rejected = IMPORTANT_LEADS_REJECTED.resolve(strict=False)
    if output_path.resolve(strict=False) != expected_output or rejected_path.resolve(strict=False) != expected_rejected:
        job["auto_triage_status"] = "skipped"
        job["auto_triage_skip_reason"] = "non_default_check_outputs"
        return job
    if not output_path.exists() or not rejected_path.exists():
        job["auto_triage_status"] = "skipped"
        job["auto_triage_skip_reason"] = "fresh_check_outputs_missing"
        return job
    if _has_newer_important_check_job(job):
        job["auto_triage_status"] = "skipped"
        job["auto_triage_skip_reason"] = "newer_check_job_started"
        return job
    if _auto_triage_already_running(exclude_check_job_id=job_id):
        job["auto_triage_status"] = "skipped"
        job["auto_triage_skip_reason"] = "triage_already_running"
        return job

    checked_signature = _file_signature(output_path)
    staged_dir = IMPORTANT_LEADS_CHECK_RUNS / "auto_triage" / job_id
    staged_keep_path = staged_dir / "leads_triaged_keep.csv"
    staged_rejected_path = staged_dir / "leads_triaged_reject.csv"
    staged_quarantine_path = staged_dir / "leads_triaged_quarantine.csv"
    keep_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_keep.csv")
    triage_rejected_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_reject.csv")
    quarantine_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_quarantine.csv")

    job["status"] = "auto_triage_running"
    job["stage"] = "auto_triage"
    job["phase"] = "auto_triage"
    job["auto_triage_status"] = "running"
    job["auto_triage_source_check_job_id"] = job_id
    job["auto_triage_started_at_utc"] = iso_utc()
    job["auto_triage_keep_path"] = str(keep_path)
    job["auto_triage_rejected_path"] = str(triage_rejected_path)
    job["auto_triage_quarantine_path"] = str(quarantine_path)
    job["message"] = "Check complete. Auto triage running."
    _save_important_check_job(job)

    started_at = time.monotonic()
    last_progress_save_at = 0.0

    def save_auto_triage_progress(processed_rows: int, total_rows: int) -> None:
        nonlocal job, last_progress_save_at
        now = time.monotonic()
        if processed_rows < total_rows and now - last_progress_save_at < 0.75:
            return
        last_progress_save_at = now
        total = max(0, int(total_rows or 0))
        processed = min(total, max(0, int(processed_rows or 0)))
        remaining = max(0, total - processed)
        elapsed = max(0.001, now - started_at)
        rate = processed / elapsed if processed > 0 else 0.0
        job["auto_triage_total_rows"] = total
        job["auto_triage_processed_rows"] = processed
        job["auto_triage_remaining_rows"] = remaining
        job["auto_triage_progress_percent"] = round(min(100.0, max(0.0, (processed / total) * 100)), 1) if total else 0
        job["auto_triage_eta_seconds"] = int(remaining / rate) if rate > 0 and remaining > 0 else 0
        _save_important_check_job(job)

    def should_cancel_auto_triage() -> bool:
        try:
            latest_job = _load_important_check_job(job_id)
            if latest_job.get("cancel_requested"):
                return True
        except Exception:
            pass
        return _has_newer_important_check_job(job)

    try:
        report = fast_triage_master_leads(
            input_path=output_path,
            keep_path=staged_keep_path,
            rejected_path=staged_rejected_path,
            quarantine_path=staged_quarantine_path,
            persist_state=False,
            progress_callback=save_auto_triage_progress,
            should_cancel=should_cancel_auto_triage,
        )
        if bool(report.get("canceled")) or should_cancel_auto_triage():
            job["status"] = "completed"
            job["stage"] = "done"
            job["phase"] = "done"
            job["auto_triage_status"] = "skipped"
            job["auto_triage_skip_reason"] = "newer_check_job_started" if _has_newer_important_check_job(job) else "canceled"
            job["message"] = "Check complete. Auto triage skipped before publishing outputs."
            return job
        if _file_signature(output_path) != checked_signature:
            job["status"] = "completed"
            job["stage"] = "done"
            job["phase"] = "done"
            job["auto_triage_status"] = "skipped"
            job["auto_triage_skip_reason"] = "checked_output_changed"
            job["message"] = "Check complete. Auto triage skipped because checked output changed."
            return job

        _promote_auto_triage_outputs(
            staged_keep_path=staged_keep_path,
            staged_rejected_path=staged_rejected_path,
            staged_quarantine_path=staged_quarantine_path,
            keep_path=keep_path,
            rejected_path=triage_rejected_path,
            quarantine_path=quarantine_path,
        )
        final_report = dict(report)
        final_report["input_label"] = str(output_path)
        final_report["verified_label"] = str(keep_path)
        final_report["rejected_label"] = str(triage_rejected_path)
        final_report["quarantine_label"] = str(quarantine_path)
        final_report["auto_triage_source_check_job_id"] = job_id
        save_state(
            **{
                TRIAGE_PATHS_STATE_KEY: _triage_path_state_labels(
                    output_path,
                    keep_path,
                    triage_rejected_path,
                    quarantine_path,
                ),
                TRIAGE_STATE_KEY: final_report,
            }
        )
        job["status"] = "completed"
        job["stage"] = "done"
        job["phase"] = "done"
        job["auto_triage_status"] = "completed"
        job["auto_triage_completed_at_utc"] = iso_utc()
        job["auto_triage_report"] = final_report
        job["auto_triage_total_rows"] = int(final_report.get("total_input_rows") or final_report.get("input_rows") or 0)
        job["auto_triage_processed_rows"] = int(final_report.get("processed_rows") or 0)
        job["auto_triage_remaining_rows"] = 0
        job["auto_triage_progress_percent"] = 100
        job["message"] = (
            f"Check complete. Auto triage complete: KEEP {int(final_report.get('keep_count') or 0)}, "
            f"REJECT {int(final_report.get('reject_count') or 0)}, "
            f"QUARANTINE {int(final_report.get('quarantine_count') or 0)}."
        )
    except Exception as exc:
        job["status"] = "triage_failed"
        job["stage"] = "triage_failed"
        job["phase"] = "triage_failed"
        job["auto_triage_status"] = "failed"
        job["auto_triage_error"] = str(exc)
        job["auto_triage_completed_at_utc"] = iso_utc()
        job["message"] = f"Check complete. Auto triage failed: {exc}"
    return job


def _job_path(directory: Path, job_id: str) -> Path:
    return directory / f"{job_id}.json"


def _load_dashboard_job(directory: Path, job_id: str, label: str) -> dict[str, object]:
    path = _job_path(directory, job_id)
    if not path.exists():
        raise FileNotFoundError(f"{label} job not found: {job_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _save_dashboard_job(directory: Path, job: dict[str, object]) -> None:
    job_id = str(job.get("job_id") or "").strip()
    if not job_id:
        raise ValueError("Missing job id.")
    directory.mkdir(parents=True, exist_ok=True)
    payload = dict(job)
    payload["updated_at_utc"] = iso_utc()
    write_path = _job_path(directory, job_id)
    tmp_path = write_path.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(write_path)
    settings.secure_private_file(write_path)


def _job_progress_payload(job: dict[str, object]) -> dict[str, object]:
    payload = dict(job)
    total_rows = max(0, int(payload.get("total_rows") or payload.get("total_input_rows") or 0))
    processed_rows = max(0, int(payload.get("processed_rows") or 0))
    remaining_rows = max(0, int(payload.get("remaining_rows") or max(0, total_rows - processed_rows)))
    if "progress_percent" not in payload or payload.get("progress_percent") in {"", None}:
        if total_rows > 0:
            payload["progress_percent"] = round(min(100.0, max(0.0, (processed_rows / total_rows) * 100)), 1)
        elif str(payload.get("status") or "") == "completed":
            payload["progress_percent"] = 100
        else:
            payload["progress_percent"] = 0
    payload["total_rows"] = total_rows
    payload["processed_rows"] = processed_rows
    payload["remaining_rows"] = remaining_rows
    return payload


def _create_pre_dispatch_archive(job_id: str) -> dict[str, object]:
    safe_job_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(job_id or "dispatch")).strip("_") or "dispatch"
    archive_dir = settings.BACKUPS_DIR / "pre_dispatch_handoffs"
    archive_path = archive_dir / f"{safe_job_id}_{timestamp_slug()}.tar.gz"
    manifest = pack_archive(archive_path, include_check_history=False)
    return {
        "archive_path": str(archive_path),
        "archive_name": archive_path.name,
        "file_count": int(manifest.get("file_count") or 0),
        "created_at_utc": str(manifest.get("created_at_utc") or ""),
        "queue_counts": dict(manifest.get("queue_counts") or {}),
        "state_summaries": dict(manifest.get("state_summaries") or {}),
    }


def _find_active_dashboard_job(directory: Path) -> dict[str, object] | None:
    if not directory.exists():
        return None
    active_statuses = {"queued", "running", "checking", "verifying", "dispatching"}
    candidates: list[tuple[float, dict[str, object]]] = []
    for path in directory.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or job.get("stage") or "").strip().lower()
        if status not in active_statuses:
            continue
        try:
            sort_key = path.stat().st_mtime
        except Exception:
            sort_key = 0.0
        candidates.append((sort_key, _job_progress_payload(job)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if any(str(value or "").strip() for value in row.values()):
                count += 1
    return count


def _normalize_uploaded_check_file(filename: str, content: bytes) -> tuple[str, str, str]:
    extension = Path(str(filename or "").strip()).suffix.lower()
    if extension == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        return ".csv", text if text.endswith("\n") else f"{text}\n", ""
    if extension == ".xlsx":
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise ValueError(f"Failed to read XLSX upload: {exc}") from exc
        try:
            source_sheet = str(workbook.sheetnames[0]) if workbook.sheetnames else ""
            worksheet = workbook[source_sheet] if source_sheet else None
            if worksheet is None:
                raise ValueError("Uploaded XLSX file has no worksheets.")
            rows = []
            for row in worksheet.iter_rows(values_only=True):
                values = ["" if cell is None else str(cell) for cell in row]
                if any(str(value or "").strip() for value in values):
                    rows.append(values)
            if not rows:
                raise ValueError("Uploaded XLSX file has no usable rows.")
            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            for row in rows:
                writer.writerow(row)
            text = buffer.getvalue()
            if text and not text.endswith("\n"):
                text += "\n"
            return ".xlsx", text, source_sheet
        finally:
            workbook.close()
    raise ValueError(f"Unsupported upload file type: {extension or '[none]'}")


def _execute_important_check(
    *,
    input_path: Path,
    output_path: Path,
    rejected_path: Path,
    effective_input_path: Path,
    progress_callback=None,
) -> dict[str, object]:
    save_state(important_leads_paths=_important_path_labels_for_state(input_path, output_path, rejected_path))
    return check_master_leads(
        input_path=effective_input_path,
        output_path=output_path,
        rejected_path=rejected_path,
        progress_callback=progress_callback,
    )


def _check_important_leads_response(
    *,
    input_path: Path,
    output_path: Path,
    rejected_path: Path,
    effective_input_path: Path,
    source_label: str | None = None,
) -> JSONResponse:
    try:
        report = _execute_important_check(
            input_path=input_path,
            output_path=output_path,
            rejected_path=rejected_path,
            effective_input_path=effective_input_path,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ImportantLeadsCheckError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": exc.message,
                "error": exc.code,
                "details": exc.details,
            },
            status_code=400,
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead check failed: {exc}"}, status_code=500)

    prefix = f"Uploaded {source_label} and " if source_label else ""
    return JSONResponse(
        {
            "ok": True,
            "message": (
                f"{prefix}checked {report['input_label']} into {report['output_label']}. "
                f"Kept {int(report['cleaned_rows'] or 0)} row(s), rejected "
                f"{sum(int(report['reason_counts'].get(reason, 0)) for reason in report.get('reason_counts', {}))}."
            ),
            "check": report,
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
        }
    )


def _run_important_check_job(job_id: str) -> None:
    try:
        job = _load_important_check_job(job_id)
    except Exception:
        return
    if str(job.get("status") or "") in {"completed", "failed"}:
        return
    try:
        job["status"] = "running"
        job["stage"] = "checking"
        job["processed_rows"] = 0
        job["remaining_rows"] = int(job.get("total_input_rows") or 0)
        job["eta_seconds"] = ""
        job["progress_percent"] = 0
        _save_important_check_job(job)
        started_at = time.monotonic()
        last_progress_save_at = 0.0

        def save_progress(processed_rows: int, total_rows: int) -> None:
            nonlocal job, last_progress_save_at
            try:
                latest_job = _load_important_check_job(job_id)
                if latest_job.get("cancel_requested"):
                    job["cancel_requested"] = True
            except Exception:
                pass
            now = time.monotonic()
            if processed_rows < total_rows and now - last_progress_save_at < 0.75:
                return
            last_progress_save_at = now
            total = max(0, int(total_rows or 0))
            processed = min(total, max(0, int(processed_rows or 0)))
            elapsed = max(0.001, now - started_at)
            rate = processed / elapsed if processed > 0 else 0.0
            remaining = max(0, total - processed)
            job["processed_rows"] = processed
            job["remaining_rows"] = remaining
            job["progress_percent"] = round(min(100.0, max(0.0, (processed / total) * 100)), 1) if total else 0
            job["eta_seconds"] = int(remaining / rate) if rate > 0 and remaining > 0 else 0
            _save_important_check_job(job)

        report = _execute_important_check(
            input_path=Path(str(job.get("input_path") or "")),
            output_path=Path(str(job.get("output_path") or "")),
            rejected_path=Path(str(job.get("rejected_path") or "")),
            effective_input_path=Path(str(job.get("effective_input_path") or "")),
            progress_callback=save_progress,
        )
        if job.get("cancel_requested"):
            job["status"] = "canceled"
            job["stage"] = "canceled"
            job["phase"] = "canceled"
            job["completed_at_utc"] = iso_utc()
            job["check"] = report
            job["processed_rows"] = int(report.get("total_input_rows") or report.get("input_rows") or job.get("total_input_rows") or 0)
            job["remaining_rows"] = 0
            job["eta_seconds"] = 0
            job["progress_percent"] = 100
            job["auto_triage_status"] = "skipped"
            job["auto_triage_skip_reason"] = "check_canceled"
            job["message"] = "Check completed after cancellation request. Auto triage skipped."
            _save_important_check_job(job)
            return
        job["status"] = "completed"
        job["stage"] = "done"
        job["phase"] = "check_complete"
        job["completed_at_utc"] = iso_utc()
        job["check"] = report
        job["processed_rows"] = int(report.get("total_input_rows") or report.get("input_rows") or job.get("total_input_rows") or 0)
        job["remaining_rows"] = 0
        job["eta_seconds"] = 0
        job["progress_percent"] = 100
        job["message"] = (
            f"Checked {report['input_label']} into {report['output_label']}. "
            f"Kept {int(report['cleaned_rows'] or 0)} row(s), rejected "
            f"{sum(int(report['reason_counts'].get(reason, 0)) for reason in report.get('reason_counts', {}))}."
        )
        job = _run_auto_fast_triage_after_check(job)
        _save_important_check_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["stage"] = "failed"
        job["completed_at_utc"] = iso_utc()
        job["processed_rows"] = 0
        job["remaining_rows"] = int(job.get("total_input_rows") or 0)
        job["progress_percent"] = 0
        job["error"] = str(exc)
        _save_important_check_job(job)


def _start_important_check_job(
    *,
    input_path: Path,
    output_path: Path,
    rejected_path: Path,
    effective_input_path: Path,
    source_label: str,
    source_mode: str,
    original_uploaded_filename: str = "",
    server_received_filename: str = "",
    selected_filename: str = "",
    selected_size_bytes: int = 0,
    selected_extension: str = "",
    source_sheet: str = "",
    total_input_rows: int,
) -> dict[str, object]:
    job_id = f"check_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "created_at_utc": iso_utc(),
        "updated_at_utc": iso_utc(),
        "source_label": source_label,
        "source_mode": str(source_mode or "").strip() or "uploaded_file",
        "original_uploaded_filename": str(original_uploaded_filename or "").strip() or source_label,
        "server_received_filename": str(server_received_filename or "").strip() or source_label,
        "selected_filename": str(selected_filename or "").strip() or source_label,
        "selected_size_bytes": int(selected_size_bytes or 0),
        "selected_extension": str(selected_extension or "").strip(),
        "source_sheet": str(source_sheet or "").strip(),
        "current_sheet": str(source_sheet or "").strip(),
        "input_path": str(input_path),
        "saved_input_path": str(effective_input_path),
        "output_path": str(output_path),
        "rejected_path": str(rejected_path),
        "effective_input_path": str(effective_input_path),
        "total_input_rows": int(total_input_rows or 0),
        "processed_rows": 0,
        "remaining_rows": int(total_input_rows or 0),
        "eta_seconds": "",
        "progress_percent": 0,
    }
    _save_important_check_job(job)
    thread = threading.Thread(target=_run_important_check_job, args=(job_id,), daemon=True)
    thread.start()
    return job


def _resume_pending_important_check_jobs() -> None:
    if not IMPORTANT_LEADS_CHECK_JOBS.exists():
        return
    for path in sorted(IMPORTANT_LEADS_CHECK_JOBS.glob("*.json")):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(job, dict):
            continue
        if str(job.get("status") or "") not in {"queued", "running"}:
            continue
        job_id = str(job.get("job_id") or path.stem).strip()
        if not job_id:
            continue
        thread = threading.Thread(target=_run_important_check_job, args=(job_id,), daemon=True)
        thread.start()


def _load_important_verify_job(job_id: str) -> dict[str, object]:
    return _load_dashboard_job(IMPORTANT_LEADS_VERIFY_JOBS, job_id, "Verify")


def _save_important_verify_job(job: dict[str, object]) -> None:
    _save_dashboard_job(IMPORTANT_LEADS_VERIFY_JOBS, job)


def _load_important_dispatch_job(job_id: str) -> dict[str, object]:
    return _load_dashboard_job(IMPORTANT_LEADS_DISPATCH_JOBS, job_id, "Dispatch")


def _save_important_dispatch_job(job: dict[str, object]) -> None:
    _save_dashboard_job(IMPORTANT_LEADS_DISPATCH_JOBS, job)


def _run_important_verify_job(job_id: str) -> None:
    try:
        job = _load_important_verify_job(job_id)
    except Exception:
        return
    if str(job.get("status") or "") in {"completed", "failed", "canceled", "cancelled"}:
        return
    try:
        mode = str(job.get("mode") or TRIAGE_MODE_FAST).strip().upper()
        is_fast_triage = mode != TRIAGE_MODE_STRICT
        job["status"] = "running"
        job["mode"] = TRIAGE_MODE_FAST if is_fast_triage else TRIAGE_MODE_STRICT
        job["stage"] = "fast_triage" if is_fast_triage else "strict_public_proof"
        job["phase"] = "fast_triage" if is_fast_triage else "strict_public_proof"
        job["eta_seconds"] = ""
        job["progress_percent"] = float(job.get("progress_percent") or 0)
        _save_important_verify_job(job)
        started_at = time.monotonic()
        last_progress_save_at = 0.0

        def save_progress(processed_rows: int, total_rows: int) -> None:
            nonlocal job, last_progress_save_at
            now = time.monotonic()
            if processed_rows < total_rows and now - last_progress_save_at < 0.75:
                return
            last_progress_save_at = now
            total = max(0, int(total_rows or 0))
            processed = min(total, max(0, int(processed_rows or 0)))
            remaining = max(0, total - processed)
            elapsed = max(0.001, now - started_at)
            rate = processed / elapsed if processed > 0 else 0.0
            job["total_rows"] = total
            job["total_input_rows"] = total
            job["processed_rows"] = processed
            job["remaining_rows"] = remaining
            job["progress_percent"] = round(min(100.0, max(0.0, (processed / total) * 100)), 1) if total else 0
            job["eta_seconds"] = int(remaining / rate) if rate > 0 and remaining > 0 else 0
            _save_important_verify_job(job)

        def should_cancel() -> bool:
            try:
                latest_job = _load_important_verify_job(job_id)
            except Exception:
                return bool(job.get("cancel_requested"))
            if latest_job.get("cancel_requested"):
                job["cancel_requested"] = True
                return True
            return bool(job.get("cancel_requested"))

        if is_fast_triage:
            report = fast_triage_master_leads(
                input_path=Path(str(job.get("input_path") or "")),
                keep_path=Path(str(job.get("verified_path") or "")),
                rejected_path=Path(str(job.get("rejected_path") or "")),
                quarantine_path=Path(str(job.get("quarantine_path") or "")),
                progress_callback=save_progress,
                should_cancel=should_cancel,
            )
        else:
            report = verify_master_leads(
                input_path=Path(str(job.get("input_path") or "")),
                verified_path=Path(str(job.get("verified_path") or "")),
                rejected_path=Path(str(job.get("rejected_path") or "")),
                quarantine_path=Path(str(job.get("quarantine_path") or "")),
                progress_callback=save_progress,
                should_cancel=should_cancel,
            )
        total = int(report.get("total_input_rows") or report.get("input_rows") or job.get("total_rows") or 0)
        processed = int(report.get("processed_rows") or total)
        canceled = should_cancel() and processed < total
        job["status"] = "canceled" if canceled else "completed"
        job["stage"] = "canceled" if canceled else "done"
        job["phase"] = "canceled" if canceled else "done"
        job["completed_at_utc"] = iso_utc()
        job["verify"] = report
        job["total_rows"] = total
        job["total_input_rows"] = total
        job["processed_rows"] = processed
        job["remaining_rows"] = max(0, total - processed) if canceled else 0
        job["eta_seconds"] = 0
        job["progress_percent"] = round(min(100.0, max(0.0, (processed / total) * 100)), 1) if total else 0
        if canceled:
            job["message"] = f"Verify stopped safely at row {processed} of {total}. Checkpoint/output files were preserved."
        else:
            job["progress_percent"] = 100
            mode_label = "Fast triaged" if is_fast_triage else "Strict verified"
            job["message"] = (
                f"{mode_label} {report['input_label']} into {report['verified_label']}. "
                f"KEEP {int(report['keep_count'] or 0)}, REJECT {int(report['reject_count'] or 0)}, "
                f"QUARANTINE {int(report['quarantine_count'] or 0)}."
            )
        _save_important_verify_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["stage"] = "failed"
        job["phase"] = "failed"
        job["completed_at_utc"] = iso_utc()
        job["error"] = str(exc)
        _save_important_verify_job(job)


def _start_important_verify_job(
    *,
    input_path: Path,
    verified_path: Path,
    rejected_path: Path,
    quarantine_path: Path,
    mode: str = TRIAGE_MODE_FAST,
) -> dict[str, object]:
    job_id = f"verify_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    total_rows = _count_csv_rows(input_path)
    mode = TRIAGE_MODE_STRICT if str(mode or "").strip().upper() == TRIAGE_MODE_STRICT else TRIAGE_MODE_FAST
    job = {
        "job_id": job_id,
        "mode": mode,
        "status": "queued",
        "stage": "queued",
        "phase": "queued",
        "created_at_utc": iso_utc(),
        "updated_at_utc": iso_utc(),
        "input_path": str(input_path),
        "verified_path": str(verified_path),
        "rejected_path": str(rejected_path),
        "quarantine_path": str(quarantine_path),
        "total_rows": total_rows,
        "total_input_rows": total_rows,
        "processed_rows": 0,
        "remaining_rows": total_rows,
        "eta_seconds": "",
        "progress_percent": 0,
    }
    _save_important_verify_job(job)
    thread = threading.Thread(target=_run_important_verify_job, args=(job_id,), daemon=True)
    thread.start()
    return _job_progress_payload(job)


def _run_important_dispatch_job(job_id: str) -> None:
    try:
        job = _load_important_dispatch_job(job_id)
    except Exception:
        return
    if str(job.get("status") or "") in {"completed", "failed", "canceled", "cancelled"}:
        return
    try:
        job["status"] = "running"
        job["stage"] = "dispatching"
        job["phase"] = "dispatching"
        job["eta_seconds"] = ""
        job["progress_percent"] = float(job.get("progress_percent") or 0)
        job["message"] = "Creating pre-dispatch archive before queue writes."
        _save_important_dispatch_job(job)
        archive = _create_pre_dispatch_archive(job_id)
        job["pre_dispatch_archive"] = archive
        job["pre_dispatch_archive_path"] = archive["archive_path"]
        job["message"] = "Pre-dispatch archive created. Confirming queue write."
        _save_important_dispatch_job(job)
        report = confirm_dispatch_preview(
            str(job.get("preview_id") or ""),
            require_stopped=True,
            backup_root=settings.BACKUPS_DIR,
            report_dir=settings.STATE_DIR,
            persist_state=True,
            preview_dir=IMPORTANT_LEADS_DISPATCH_PREVIEWS,
        )
        report["pre_dispatch_archive"] = archive
        report["pre_dispatch_archive_path"] = archive["archive_path"]
        report_path_text = str(report.get("report_path") or "").strip()
        if report_path_text:
            report_path = Path(report_path_text)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            settings.secure_private_file(report_path)
        save_state(**{MASTER_DISPATCH_STATE_KEY: report})
        assigned_rows = int(report.get("added_astra") or 0) + int(report.get("added_sendgrid") or 0)
        skipped_rows = (
            int(report.get("suppressed_skipped") or 0)
            + int(report.get("duplicate_master_skipped") or 0)
            + int(report.get("skipped_both") or 0)
            + int(report.get("invalid_malformed_skipped") or 0)
        )
        total_rows = int(report.get("dispatch_selected_row_count") or job.get("total_rows") or 0)
        job["status"] = "completed"
        job["stage"] = "done"
        job["phase"] = "done"
        job["completed_at_utc"] = iso_utc()
        job["run_id"] = report.get("run_id")
        job["dispatch"] = report
        job["total_rows"] = total_rows
        job["processed_rows"] = total_rows
        job["assigned_rows"] = assigned_rows
        job["skipped_rows"] = skipped_rows
        job["remaining_rows"] = 0
        job["eta_seconds"] = 0
        job["progress_percent"] = 100
        job["message"] = str(
            report.get("message")
            or (
                f"Dispatch complete. Astra added {report['added_astra']} row(s), SendGrid added "
                f"{report['added_sendgrid']} row(s), skipped both {report['skipped_both']}."
            )
        )
        _save_important_dispatch_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["stage"] = "failed"
        job["phase"] = "failed"
        job["completed_at_utc"] = iso_utc()
        job["error"] = str(exc)
        _save_important_dispatch_job(job)


def _start_important_dispatch_job(
    *,
    preview_id: str,
    dispatch_source_mode: str,
    dispatch_source_name: str,
    dispatch_source_path: str,
    dispatch_cap: str,
    total_source_rows: int,
    eligible_rows: int,
    selected_rows: int,
    total_rows_would_write: int,
) -> dict[str, object]:
    job_id = f"dispatch_{timestamp_slug()}_{uuid.uuid4().hex[:8]}"
    job = {
        "job_id": job_id,
        "preview_id": preview_id,
        "status": "queued",
        "stage": "queued",
        "phase": "queued",
        "created_at_utc": iso_utc(),
        "updated_at_utc": iso_utc(),
        "dispatch_source_mode": dispatch_source_mode,
        "dispatch_source_name": dispatch_source_name,
        "dispatch_source_path": dispatch_source_path,
        "dispatch_cap": dispatch_cap,
        "total_source_rows": max(0, int(total_source_rows or 0)),
        "eligible_rows": max(0, int(eligible_rows or 0)),
        "selected_rows": max(0, int(selected_rows or 0)),
        "total_rows_would_write": max(0, int(total_rows_would_write or 0)),
        "total_rows": max(0, int(selected_rows or 0)),
        "processed_rows": 0,
        "assigned_rows": 0,
        "skipped_rows": 0,
        "remaining_rows": max(0, int(selected_rows or 0)),
        "eta_seconds": "",
        "progress_percent": 0,
    }
    _save_important_dispatch_job(job)
    thread = threading.Thread(target=_run_important_dispatch_job, args=(job_id,), daemon=True)
    thread.start()
    return _job_progress_payload(job)


def _count_pasted_lead_rows(input_text: str) -> int:
    normalized_text = _normalize_pasted_leads_csv(input_text)
    if not normalized_text.strip():
        return 0
    reader = csv.DictReader(io.StringIO(normalized_text))
    count = 0
    for row in reader:
        if any(str(value or "").strip() for value in row.values()):
            count += 1
    return count


def _csv_count_from_status_label(status: dict[str, object], key: str, default_path: Path) -> int:
    raw = str(status.get(key) or "").strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = settings.APP_ROOT / path
        if path.suffix.lower() == ".csv" and path.exists():
            return _count_csv_rows(path)
    path = default_path
    return _count_csv_rows(path)


def _build_leads_pipeline_status(status: dict[str, object]) -> dict[str, object]:
    active_check = status.get("active_important_check_job") if isinstance(status.get("active_important_check_job"), dict) else None
    active_verify = status.get("active_important_verify_job") if isinstance(status.get("active_important_verify_job"), dict) else None
    active_dispatch = status.get("active_important_dispatch_job") if isinstance(status.get("active_important_dispatch_job"), dict) else None
    latest_check = status.get("latest_master_check") if isinstance(status.get("latest_master_check"), dict) else {}
    latest_triage = status.get("latest_lead_triage") if isinstance(status.get("latest_lead_triage"), dict) else {}
    latest_verify = status.get("latest_lead_verify") if isinstance(status.get("latest_lead_verify"), dict) else {}
    latest_dispatch = status.get("latest_dispatch") if isinstance(status.get("latest_dispatch"), dict) else {}
    dispatch_source = status.get("dispatch_source") if isinstance(status.get("dispatch_source"), dict) else {}

    checked_rows = _csv_count_from_status_label(status, "important_output_label", IMPORTANT_LEADS_OUTPUT)
    triaged_rows = _csv_count_from_status_label(status, "important_triage_keep_label", TRIAGED_KEEP_PATH)
    strict_rows = _csv_count_from_status_label(status, "important_verify_keep_label", STRICT_VERIFIED_PATH)
    quarantine_rows = _csv_count_from_status_label(status, "important_triage_quarantine_label", IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_quarantine.csv"))
    eligible_rows = int(dispatch_source.get("dispatch_eligible_row_count") or status.get("dispatch_eligible_row_count") or 0)
    auto_triage_running = bool(active_check and str(active_check.get("auto_triage_status") or "").lower() == "running")
    check_running = bool(active_check and not auto_triage_running)

    steps = [
        {
            "key": "check",
            "label": "Check",
            "state": "active" if check_running else ("done" if checked_rows or latest_check.get("generated_at_utc") or auto_triage_running else "waiting"),
            "count": checked_rows or int(latest_check.get("cleaned_rows") or 0),
            "note": "Cleaning/upload job running." if check_running else "Check complete." if auto_triage_running else "Cleaned leads ready." if checked_rows else "Run Check Leads.",
        },
        {
            "key": "triage",
            "label": "Triage",
            "state": "active" if (auto_triage_running or (active_verify and str(active_verify.get("mode") or "").upper() == TRIAGE_MODE_FAST)) else ("done" if triaged_rows or latest_triage.get("generated_at_utc") else "waiting"),
            "count": triaged_rows or int(active_check.get("auto_triage_processed_rows") or 0) if auto_triage_running else triaged_rows or int(latest_triage.get("keep_count") or latest_triage.get("verified_count") or 0),
            "note": "Auto triage running." if auto_triage_running else "Fast triage running." if active_verify else "Fast triage keep rows ready." if triaged_rows else "Run fast triage.",
        },
        {
            "key": "quarantine",
            "label": "Review",
            "state": "warn" if quarantine_rows else ("done" if triaged_rows else "waiting"),
            "count": quarantine_rows,
            "note": "Review quarantined rows before dispatch." if quarantine_rows else "No triage quarantine rows detected." if triaged_rows else "Waiting for triage.",
        },
        {
            "key": "preview",
            "label": "Preview",
            "state": "done" if eligible_rows else "waiting",
            "count": eligible_rows,
            "note": "Dispatch source has eligible rows." if eligible_rows else "Run Preview Dispatch after source is ready.",
        },
        {
            "key": "dispatch",
            "label": "Dispatch",
            "state": "active" if active_dispatch else ("done" if latest_dispatch.get("generated_at_utc") else "waiting"),
            "count": int(latest_dispatch.get("dispatch_selected_row_count") or latest_dispatch.get("total_rows_would_write") or 0),
            "note": "Dispatch job running." if active_dispatch else "Last dispatch complete." if latest_dispatch.get("generated_at_utc") else "Confirm Dispatch after preview.",
        },
    ]
    active_step = next((step["key"] for step in steps if step["state"] == "active"), "")
    next_step = next((step["key"] for step in steps if step["state"] in {"waiting", "warn"}), "")
    return {
        "steps": steps,
        "active_step": active_step,
        "next_step": active_step or next_step,
        "checked_rows": checked_rows,
        "triaged_keep_rows": triaged_rows,
        "strict_verified_rows": strict_rows,
        "quarantine_rows": quarantine_rows,
        "dispatch_eligible_rows": eligible_rows,
        "latest_pre_dispatch_archive_path": str((latest_dispatch.get("pre_dispatch_archive") or {}).get("archive_path") or latest_dispatch.get("pre_dispatch_archive_path") or ""),
    }


def _combined_leads_status() -> dict[str, object]:
    status = {
        **shard_status(),
        **important_leads_status(),
        **important_leads_verify_status(),
        "active_important_check_job": _find_active_important_check_job(),
        "active_important_verify_job": _find_active_dashboard_job(IMPORTANT_LEADS_VERIFY_JOBS),
        "active_important_dispatch_job": _find_active_dashboard_job(IMPORTANT_LEADS_DISPATCH_JOBS),
    }
    status["pipeline"] = _build_leads_pipeline_status(status)
    return status


def _normalize_pasted_leads_csv(input_text: str) -> str:
    normalized_text = str(input_text or "").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_text.endswith("\n"):
        normalized_text += "\n"

    non_empty_lines = [line for line in normalized_text.splitlines() if line.strip()]
    if not non_empty_lines:
        return normalized_text

    sample = "\n".join(non_empty_lines[:5])
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        delimiter = "," if "," in non_empty_lines[0] else "\t"

    first_row = next(csv.reader([non_empty_lines[0]], delimiter=delimiter), [])
    normalized_headers = {"".join(ch for ch in str(cell or "").strip().lower() if ch.isalnum()) for cell in first_row}
    known_email_headers = {
        "email",
        "emailaddress",
        "email_address",
        "e_mail",
        "mail",
        "authoremail",
        "contactemail",
    }
    if normalized_headers & known_email_headers:
        return normalized_text

    def _safe_email_cell(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        raw = re.sub(r"^\s*mailto:\s*", "", raw, flags=re.IGNORECASE)
        matches = _PARSER_EMAIL_RE.findall(raw)
        if len(matches) > 1:
            return ""
        candidate = matches[0] if matches else raw
        candidate = candidate.strip().strip("<>()[]{}\"'")
        candidate = candidate.rstrip(".,;:!?")
        if candidate.count("@") != 1:
            return ""
        local, domain = candidate.split("@", 1)
        if not local or not domain:
            return ""
        return f"{local}@{domain.lower()}"

    swapped = io.StringIO()
    writer = csv.writer(swapped, delimiter=",", lineterminator="\n")
    writer.writerow(["Email", "FirstName"])

    def _emit(email: str, first_name: str = "") -> None:
        writer.writerow([email, first_name])

    reader = csv.reader(non_empty_lines, delimiter=delimiter)
    for row in reader:
        cells = [str(cell or "").strip() for cell in row if str(cell or "").strip()]
        if not cells:
            continue
        if len(cells) == 1:
            email = _safe_email_cell(cells[0])
            if email:
                _emit(email, "")
            else:
                _emit("", cells[0])
            continue
        if len(cells) == 2:
            first_email = _safe_email_cell(cells[0])
            second_email = _safe_email_cell(cells[1])
            if first_email and not second_email:
                _emit(first_email, cells[1])
                continue
            if second_email and not first_email:
                _emit(second_email, cells[0])
                continue
            if first_email and second_email:
                _emit(first_email, "")
                if second_email != first_email:
                    _emit(second_email, "")
                continue
            _emit("", cells[0])
            continue
        extracted = [_safe_email_cell(cell) for cell in cells]
        emails = [email for email in extracted if email]
        if emails and len(emails) == len(cells):
            for email in emails:
                _emit(email, "")
            continue
        if emails:
            _emit(emails[0], "")
            continue
        _emit("", cells[0])

    normalized_rows = swapped.getvalue()
    if not normalized_rows.endswith("\n"):
        normalized_rows += "\n"
    return normalized_rows


def _load_dashboard_auto_start_state() -> dict[str, str]:
    state = {
        "sendgrid_last_started_local_date": "",
        "sendgrid_last_attempt_utc": "",
        "private_jc_last_started_local_date": "",
        "private_jc_last_attempt_utc": "",
        "private_jc_recovery_last_attempt_utc": "",
        "updated_at_utc": "",
    }
    if not DASHBOARD_AUTO_START_STATE_PATH.exists():
        return state
    try:
        raw = json.loads(DASHBOARD_AUTO_START_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return state
    if not isinstance(raw, dict):
        return state
    for key in state:
        state[key] = str(raw.get(key) or "")
    return state


def _save_dashboard_auto_start_state(state: dict[str, str]) -> None:
    payload = {
        **state,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    DASHBOARD_AUTO_START_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DASHBOARD_AUTO_START_STATE_PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(DASHBOARD_AUTO_START_STATE_PATH)


def _load_dashboard_timer_state() -> dict[str, str]:
    state = {
        "private_jc_recovery_start_at_utc": "",
        "private_jc_recovery_note": "",
        "updated_at_utc": "",
    }
    if not DASHBOARD_TIMER_STATE_PATH.exists():
        return state
    try:
        raw = json.loads(DASHBOARD_TIMER_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return state
    if not isinstance(raw, dict):
        return state
    for key in state:
        state[key] = str(raw.get(key) or "")
    return state


def _save_dashboard_timer_state(state: dict[str, str]) -> None:
    payload = {
        **state,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    DASHBOARD_TIMER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DASHBOARD_TIMER_STATE_PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(DASHBOARD_TIMER_STATE_PATH)


def _clear_dashboard_recovery_timer() -> None:
    _save_dashboard_timer_state(
        {
            "private_jc_recovery_start_at_utc": "",
            "private_jc_recovery_note": "",
        }
    )


def _parse_local_trigger_time(raw: object) -> tuple[int, int]:
    text = str(raw or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except Exception:
        return 18, 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return 18, 0
    return hour, minute


def _auto_start_due(now_local: datetime, trigger_text: object) -> bool:
    hour, minute = _parse_local_trigger_time(trigger_text)
    return (now_local.hour, now_local.minute) >= (hour, minute)


def _retry_due(last_attempt_utc: str) -> bool:
    text = str(last_attempt_utc or "").strip()
    if not text:
        return True
    try:
        previous = datetime.fromisoformat(text)
    except Exception:
        return True
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - previous >= timedelta(minutes=AUTO_START_RETRY_MINUTES)


def _format_local_offset(dt: datetime) -> str:
    offset = dt.utcoffset() or timedelta()
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _format_local_label(dt: datetime) -> str:
    local_dt = dt.astimezone()
    return f"{local_dt.strftime('%Y-%m-%d %H:%M')} {_format_local_offset(local_dt)}"


def _format_local_clock(dt: datetime) -> str:
    local_dt = dt.astimezone()
    return f"{local_dt.strftime('%H:%M')} {_format_local_offset(local_dt)}"


def _next_local_run(now_local: datetime, trigger_text: object) -> datetime:
    hour, minute = _parse_local_trigger_time(trigger_text)
    target = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_local:
        target += timedelta(days=1)
    return target


def _build_automation_status() -> dict[str, object]:
    run_settings = load_dashboard_run_settings()
    auto_state = _load_dashboard_auto_start_state()
    timer_state = _load_dashboard_timer_state()
    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)

    sendgrid_next = _next_local_run(now_local, run_settings.get("auto_start_sendgrid_local_time"))
    jc_daily_next = _next_local_run(now_local, run_settings.get("auto_start_private_jc_local_time"))

    jc_configured_cooldown = max(0, int(PROFILES.get(PRIVATE_BOUNCE_PROFILE, {}).get("cooldown_seconds") or 0))
    jc_pacing = provider_pacing_status(PRIVATE_BOUNCE_PROFILE, "private", jc_configured_cooldown, now=now_utc)

    recovery_target_utc = None
    if jc_pacing.get("recovery_pending"):
        recovery_raw = str(jc_pacing.get("cooldown_until_utc") or "").strip()
    else:
        recovery_raw = str(timer_state.get("private_jc_recovery_start_at_utc") or "").strip()
    if recovery_raw:
        try:
            recovery_target_utc = datetime.fromisoformat(recovery_raw)
            if recovery_target_utc.tzinfo is None:
                recovery_target_utc = recovery_target_utc.replace(tzinfo=timezone.utc)
            else:
                recovery_target_utc = recovery_target_utc.astimezone(timezone.utc)
        except Exception:
            recovery_target_utc = None

    recovery_active = False
    recovery_remaining_seconds = 0
    if recovery_target_utc and not _profile_runtime_active(PRIVATE_BOUNCE_PROFILE):
        recovery_active = True
        recovery_remaining_seconds = max(0, int((recovery_target_utc - now_utc).total_seconds()))

    return {
        "local_timezone_offset": _format_local_offset(now_local),
        "sendgrid_daily": {
            "enabled": bool(run_settings.get("auto_start_sendgrid_enabled")),
            "local_time": str(run_settings.get("auto_start_sendgrid_local_time") or ""),
            "next_run_utc": sendgrid_next.astimezone(timezone.utc).isoformat(),
            "next_run_local_label": _format_local_label(sendgrid_next),
            "next_run_local_clock": _format_local_clock(sendgrid_next),
            "remaining_seconds": max(0, int((sendgrid_next - now_local).total_seconds())),
            "last_started_local_date": str(auto_state.get("sendgrid_last_started_local_date") or ""),
        },
        "private_jc_daily": {
            "enabled": bool(run_settings.get("auto_start_private_jc_enabled")),
            "local_time": str(run_settings.get("auto_start_private_jc_local_time") or ""),
            "next_run_utc": jc_daily_next.astimezone(timezone.utc).isoformat(),
            "next_run_local_label": _format_local_label(jc_daily_next),
            "next_run_local_clock": _format_local_clock(jc_daily_next),
            "remaining_seconds": max(0, int((jc_daily_next - now_local).total_seconds())),
            "last_started_local_date": str(auto_state.get("private_jc_last_started_local_date") or ""),
        },
        "private_jc_recovery": {
            "active": recovery_active,
            "target_utc": recovery_target_utc.isoformat() if recovery_target_utc else "",
            "target_local_label": _format_local_label(recovery_target_utc.astimezone()) if recovery_target_utc else "",
            "target_local_clock": _format_local_clock(recovery_target_utc.astimezone()) if recovery_target_utc else "",
            "remaining_seconds": recovery_remaining_seconds,
            "note": str(
                jc_pacing.get("recovery_reason")
                or jc_pacing.get("last_throttle_reason")
                or timer_state.get("private_jc_recovery_note")
                or ""
            ),
        },
    }


def _build_live_snapshot(activity_hours: int = 24, tail_lines: int = 12) -> dict[str, object]:
    snapshot = build_dashboard_snapshot(activity_hours=activity_hours, tail_lines=tail_lines)
    snapshot["automation"] = _build_automation_status()
    return snapshot


def _active_dashboard_profiles() -> set[str]:
    active_states = {"starting", "running", "cooldown", "sleeping"}
    active: set[str] = set()
    try:
        snapshots = runtime_control.list_sender_snapshots(tail_lines=6)
    except Exception:
        return active
    for snapshot in snapshots:
        name = str(getattr(snapshot, "name", "") or "")
        state = str(getattr(snapshot, "runtime_state", "") or "")
        dead = bool(getattr(snapshot, "tmux_dead", False))
        if name and not dead and state in active_states:
            active.add(name)
    return active


def _run_dashboard_daily_auto_start_once() -> None:
    settings_payload = load_dashboard_run_settings()
    now_local = datetime.now().astimezone()
    today = now_local.date().isoformat()
    now_utc_iso = datetime.now(timezone.utc).isoformat()
    state = _load_dashboard_auto_start_state()
    active_profiles = _active_dashboard_profiles()
    dirty = False

    if bool(settings_payload.get("auto_start_sendgrid_enabled")) and _auto_start_due(now_local, settings_payload.get("auto_start_sendgrid_local_time")):
        if state.get("sendgrid_last_started_local_date") != today:
            if all(name in active_profiles for name in SENDGRID_PROFILES):
                state["sendgrid_last_started_local_date"] = today
                dirty = True
            elif _retry_due(state.get("sendgrid_last_attempt_utc", "")):
                state["sendgrid_last_attempt_utc"] = now_utc_iso
                dirty = True
                all_ready = True
                for profile_name in SENDGRID_PROFILES:
                    if profile_name in active_profiles:
                        continue
                    ok, _message = runtime_control.start_sender(profile_name)
                    if ok:
                        active_profiles.add(profile_name)
                        continue
                    all_ready = False
                if all_ready and all(name in active_profiles for name in SENDGRID_PROFILES):
                    state["sendgrid_last_started_local_date"] = today
                    dirty = True

    if bool(settings_payload.get("auto_start_private_jc_enabled")) and _auto_start_due(now_local, settings_payload.get("auto_start_private_jc_local_time")):
        if state.get("private_jc_last_started_local_date") != today:
            if PRIVATE_BOUNCE_PROFILE in active_profiles:
                state["private_jc_last_started_local_date"] = today
                dirty = True
            elif _retry_due(state.get("private_jc_last_attempt_utc", "")):
                state["private_jc_last_attempt_utc"] = now_utc_iso
                dirty = True
                ok, _message = runtime_control.start_sender(PRIVATE_BOUNCE_PROFILE)
                if ok or _profile_runtime_active(PRIVATE_BOUNCE_PROFILE):
                    state["private_jc_last_started_local_date"] = today
                    dirty = True

    if dirty:
        _save_dashboard_auto_start_state(state)


def _run_private_jc_recovery_auto_start_once() -> None:
    now_utc = datetime.now(timezone.utc)
    state = _load_dashboard_auto_start_state()
    pacing = provider_pacing_status(
        PRIVATE_BOUNCE_PROFILE,
        "private",
        max(0, int(PROFILES.get(PRIVATE_BOUNCE_PROFILE, {}).get("cooldown_seconds") or 0)),
        now=now_utc,
    )

    if bool(pacing.get("recovery_pending")):
        if _profile_runtime_active(PRIVATE_BOUNCE_PROFILE):
            mark_recovery_started(PRIVATE_BOUNCE_PROFILE, now=now_utc)
            return
        if bool(pacing.get("cooldown_active")):
            return
        if not _retry_due(state.get("private_jc_recovery_last_attempt_utc", "")):
            return
        state["private_jc_recovery_last_attempt_utc"] = now_utc.isoformat()
        _save_dashboard_auto_start_state(state)
        ok, _message = runtime_control.start_sender(PRIVATE_BOUNCE_PROFILE)
        if ok or _profile_runtime_active(PRIVATE_BOUNCE_PROFILE):
            mark_recovery_started(PRIVATE_BOUNCE_PROFILE, now=now_utc)
        return

    timer_state = _load_dashboard_timer_state()
    recovery_raw = str(timer_state.get("private_jc_recovery_start_at_utc") or "").strip()
    if not recovery_raw:
        return
    try:
        recovery_target_utc = datetime.fromisoformat(recovery_raw)
    except Exception:
        _clear_dashboard_recovery_timer()
        return
    if recovery_target_utc.tzinfo is None:
        recovery_target_utc = recovery_target_utc.replace(tzinfo=timezone.utc)
    else:
        recovery_target_utc = recovery_target_utc.astimezone(timezone.utc)
    if recovery_target_utc > now_utc or _profile_runtime_active(PRIVATE_BOUNCE_PROFILE):
        return
    if not _retry_due(state.get("private_jc_recovery_last_attempt_utc", "")):
        return
    state["private_jc_recovery_last_attempt_utc"] = now_utc.isoformat()
    _save_dashboard_auto_start_state(state)
    ok, _message = runtime_control.start_sender(PRIVATE_BOUNCE_PROFILE)
    if ok or _profile_runtime_active(PRIVATE_BOUNCE_PROFILE):
        _clear_dashboard_recovery_timer()


def _run_background_automation_once() -> None:
    try:
        _run_dashboard_daily_auto_start_once()
    except Exception:
        pass
    try:
        _run_private_jc_recovery_auto_start_once()
    except Exception:
        pass
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
    runtime_audit.write_app_start()
    if getattr(app.state, "automation_task", None) is None:
        app.state.automation_task = asyncio.create_task(_background_automation_loop())
    _resume_pending_important_check_jobs()


@app.on_event("shutdown")
async def _shutdown_background_automation() -> None:
    runtime_audit.write_app_shutdown()
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


def _dashboard_auth_enabled() -> bool:
    return bool(settings.DASHBOARD_AUTH_PASSWORD)


def _dashboard_is_authenticated(scope: Request | WebSocket) -> bool:
    session = getattr(scope, "session", None)
    if not isinstance(session, dict):
        session = {}
    return bool(session.get(_AUTH_SESSION_KEY))


def _dashboard_auth_response() -> dict[str, object]:
    return {
        "auth_enabled": _dashboard_auth_enabled(),
        "authenticated": False,
        "username": str(settings.DASHBOARD_AUTH_USERNAME or "admin"),
    }


async def _read_upload_bytes_with_limit(file: UploadFile, *, limit: int) -> bytes:
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise ValueError(
            f"Upload too large. Limit is {limit} bytes."
        )
    return content


def _human_upload_limit(limit: int) -> str:
    megabytes = max(1, int(limit or 0) // (1024 * 1024))
    return f"{megabytes} MB"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/status")
def auth_status(request: Request) -> JSONResponse:
    authenticated = bool(request.session.get(_AUTH_SESSION_KEY))
    return JSONResponse(
        {
            "ok": True,
            **_dashboard_auth_response(),
            "authenticated": authenticated,
            "username": str(request.session.get("dashboard_username") or settings.DASHBOARD_AUTH_USERNAME or "admin"),
        }
    )


@app.post("/api/auth/login")
def auth_login(payload: DashboardAuthPayload, request: Request) -> JSONResponse:
    if not _dashboard_auth_enabled():
        return JSONResponse(
            {"ok": False, "message": "Dashboard auth is not configured."},
            status_code=503,
        )
    expected_user = str(settings.DASHBOARD_AUTH_USERNAME or "admin")
    expected_pass = str(settings.DASHBOARD_AUTH_PASSWORD or "")
    if not secrets.compare_digest(str(payload.username or ""), expected_user) or not secrets.compare_digest(str(payload.password or ""), expected_pass):
        return JSONResponse({"ok": False, "message": "Invalid dashboard credentials."}, status_code=401)

    request.session[_AUTH_SESSION_KEY] = True
    request.session["dashboard_username"] = expected_user
    request.session["dashboard_authenticated_at_utc"] = iso_utc()
    return JSONResponse({"ok": True, "message": "Signed in.", **_dashboard_auth_response(), "authenticated": True, "username": expected_user})


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> JSONResponse:
    request.session.clear()
    return JSONResponse({"ok": True, "message": "Signed out.", **_dashboard_auth_response()})


@app.get("/api/snapshot")
def snapshot(
    hours: int = Query(default=24, ge=1, le=168),
    tail_lines: int = Query(default=12, ge=4, le=50),
) -> dict[str, object]:
    return _build_live_snapshot(activity_hours=hours, tail_lines=tail_lines)


@app.post("/api/start")
def start() -> JSONResponse:
    ok, message = runtime_control.start_all_senders()
    time.sleep(0.6)
    return JSONResponse({"ok": ok, "message": message, "snapshot": _build_live_snapshot()})


@app.post("/api/start/{profile_name}")
def start_profile(profile_name: str) -> JSONResponse:
    if not runtime_control.is_known_profile(profile_name):
        return JSONResponse({"ok": False, "message": f"Unknown profile: {profile_name}"}, status_code=404)
    ok, message = runtime_control.start_sender(profile_name)
    time.sleep(0.6)
    return JSONResponse({"ok": ok, "message": message, "snapshot": _build_live_snapshot()})


@app.post("/api/stop")
def stop() -> JSONResponse:
    ok, message = runtime_control.stop_all_senders()
    return JSONResponse({"ok": ok, "message": message, "snapshot": _build_live_snapshot()})


@app.post("/api/stop/{profile_name}")
def stop_profile(profile_name: str) -> JSONResponse:
    if not runtime_control.is_known_profile(profile_name):
        return JSONResponse({"ok": False, "message": f"Unknown profile: {profile_name}"}, status_code=404)
    ok, message = runtime_control.stop_sender(profile_name)
    return JSONResponse({"ok": ok, "message": message, "snapshot": _build_live_snapshot()})


@app.post("/api/archive-reset-logs")
def archive_reset_logs() -> JSONResponse:
    ok, message = runtime_control.archive_reset_logs()
    return JSONResponse({"ok": ok, "message": message, "snapshot": _build_live_snapshot()})


@app.post("/api/settings/send-cap")
def update_send_cap(payload: SendCapPayload) -> JSONResponse:
    settings = save_dashboard_send_cap_per_profile(payload.send_cap_per_profile)
    cap = int(settings.get("send_cap_per_profile") or payload.send_cap_per_profile)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Dashboard SendGrid target saved: {cap} emails from 6 PM to 12 PM.",
            "snapshot": _build_live_snapshot(),
        }
    )


@app.post("/api/leads/upload")
async def upload_leads(file: UploadFile = File(...)) -> JSONResponse:
    filename = (file.filename or "").strip()
    if not filename:
        return JSONResponse({"ok": False, "message": "Missing upload filename."}, status_code=400)
    try:
        content = await _read_upload_bytes_with_limit(file, limit=settings.DASHBOARD_MAX_UPLOAD_BYTES)
    except ValueError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": str(exc),
                "error": "UPLOAD_TOO_LARGE",
                "details": {"max_upload_bytes": settings.DASHBOARD_MAX_UPLOAD_BYTES},
            },
            status_code=413,
        )
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


@app.post("/api/leads/check-important/upload")
async def check_important_leads_upload(
    file: UploadFile | None = File(None),
    client_selected_filename: str = Form(""),
    client_selected_size_bytes: str = Form(""),
    client_selected_extension: str = Form(""),
    output_path: str = Form(""),
    rejected_path: str = Form(""),
) -> JSONResponse:
    current_paths = important_leads_path_state()
    resolved_output_path = _resolve_dashboard_csv_path_or_default(
        output_path or current_paths["output_path"],
        IMPORTANT_LEADS_OUTPUT,
    )
    resolved_rejected_path = _resolve_dashboard_csv_path_or_default(
        rejected_path or current_paths["rejected_path"],
        IMPORTANT_LEADS_REJECTED,
    )
    if file is None:
        return JSONResponse(
            {
                "ok": False,
                "message": "Missing uploaded file. Upload CSV files only.",
                "error": "UPLOAD_FILE_REQUIRED",
                "details": {"allowed_extensions": [".csv"]},
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=400,
        )
    filename = Path(str(file.filename or "").strip()).name
    if not filename:
        return JSONResponse(
            {
                "ok": False,
                "message": "Missing upload filename. Upload CSV files only.",
                "error": "UPLOAD_FILENAME_REQUIRED",
                "details": {"allowed_extensions": [".csv"]},
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=400,
        )
    extension = Path(filename).suffix.lower()
    if extension not in {".csv", ".xlsx"}:
        return JSONResponse(
            {
                "ok": False,
                "message": f"Unsupported upload file type: {extension or '[none]'}. Only .csv and .xlsx files are supported for upload checks.",
                "error": "UPLOAD_UNSUPPORTED_FILE_TYPE",
                "details": {
                    "allowed_extensions": [".csv", ".xlsx"],
                    "server_received_filename": filename,
                    "server_received_extension": extension or "",
                },
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=415,
        )
    selected_filename = Path(str(client_selected_filename or "").strip()).name
    if selected_filename and selected_filename != filename:
        return JSONResponse(
            {
                "ok": False,
                "message": (
                    "Selected filename mismatch. "
                    f"Selected {selected_filename}, server received {filename}."
                ),
                "error": "UPLOAD_FILENAME_MISMATCH",
                "details": {
                    "selected_filename": selected_filename,
                    "server_received_filename": filename,
                    "allowed_extensions": [".csv", ".xlsx"],
                },
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=400,
        )
    try:
        selected_size_bytes = max(0, int(str(client_selected_size_bytes or "0").strip() or 0))
    except Exception:
        selected_size_bytes = 0
    max_upload_bytes = IMPORTANT_LEADS_CHECK_UPLOAD_MAX_BYTES
    if selected_size_bytes > max_upload_bytes:
        return JSONResponse(
            {
                "ok": False,
                "message": f"Upload too large. Upload CSV/XLSX files up to {_human_upload_limit(max_upload_bytes)}.",
                "error": "UPLOAD_TOO_LARGE",
                "details": {"max_upload_bytes": max_upload_bytes, "max_upload_megabytes": max_upload_bytes // (1024 * 1024)},
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=413,
        )
    try:
        content = await _read_upload_bytes_with_limit(file, limit=max_upload_bytes)
    except ValueError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": f"{exc} Upload CSV/XLSX files up to {_human_upload_limit(max_upload_bytes)}.",
                "error": "UPLOAD_TOO_LARGE",
                "details": {"max_upload_bytes": max_upload_bytes, "max_upload_megabytes": max_upload_bytes // (1024 * 1024)},
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=413,
        )
    if not content:
        return JSONResponse(
            {
                "ok": False,
                "message": "Uploaded file is empty.",
                "error": "UPLOAD_FILE_EMPTY",
                "details": {
                    "allowed_extensions": [".csv", ".xlsx"],
                    "server_received_filename": filename,
                    "server_received_extension": extension,
                },
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=400,
        )
    IMPORTANT_LEADS_CHECK_RUNS.mkdir(parents=True, exist_ok=True)
    effective_input_path = IMPORTANT_LEADS_CHECK_RUNS / f"leadschecker_{timestamp_slug()}.csv"
    try:
        normalized_extension, normalized_text, source_sheet = _normalize_uploaded_check_file(filename, content)
    except ValueError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": str(exc),
                "error": "UPLOAD_WORKBOOK_INVALID" if extension == ".xlsx" else "UPLOAD_FILE_INVALID",
                "details": {
                    "allowed_extensions": [".csv", ".xlsx"],
                    "server_received_filename": filename,
                    "server_received_extension": extension,
                },
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=400,
    )
    effective_input_path.write_text(normalized_text, encoding="utf-8")
    settings.secure_private_file(effective_input_path)
    total_input_rows = _count_csv_rows(effective_input_path)
    job = _start_important_check_job(
        input_path=effective_input_path,
        output_path=resolved_output_path,
        rejected_path=resolved_rejected_path,
        effective_input_path=effective_input_path,
        source_label=filename,
        source_mode="uploaded_file",
        original_uploaded_filename=filename,
        server_received_filename=filename,
        selected_filename=selected_filename or filename,
        selected_size_bytes=selected_size_bytes,
        selected_extension=str(client_selected_extension or normalized_extension or extension or "").strip().lower() or normalized_extension or extension,
        source_sheet=source_sheet,
        total_input_rows=total_input_rows,
    )
    return JSONResponse(
        {
            "ok": True,
            "message": f"Queued upload check for {filename} as {job['job_id']}.",
            "server_received_filename": filename,
            "selected_filename": selected_filename or filename,
            "selected_size_bytes": selected_size_bytes,
            "selected_extension": normalized_extension or extension,
            "job": job,
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
        },
        status_code=202,
    )


@app.get("/api/leads/check-important/job/{job_id}")
def get_check_important_leads_job(job_id: str) -> JSONResponse:
    try:
        job = _load_important_check_job(job_id)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "message": f"Check job not found: {job_id}"}, status_code=404)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Failed to load check job: {exc}"}, status_code=500)
    return JSONResponse({"ok": True, "job": _important_check_job_with_progress(job), "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()}})


@app.get("/api/leads/check-important/active")
def get_active_check_important_leads_job() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "job": _find_active_important_check_job(),
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
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
    except ImportantLeadsCheckError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": exc.message,
                "error": exc.code,
                "details": exc.details,
            },
            status_code=400,
        )
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
def check_important_leads(payload: ImportantLeadPathsPayload | None = None) -> JSONResponse:
    current_paths = important_leads_path_state()
    input_path = _resolve_dashboard_csv_path(
        payload.input_path if payload else current_paths["input_path"],
        IMPORTANT_LEADS_INPUT,
    )
    output_path = _resolve_dashboard_csv_path(
        payload.output_path if payload else current_paths["output_path"],
        IMPORTANT_LEADS_OUTPUT,
    )
    rejected_path = _resolve_dashboard_csv_path(
        payload.rejected_path if payload else current_paths["rejected_path"],
        IMPORTANT_LEADS_REJECTED,
    )
    effective_input_path = input_path
    input_text = str(payload.input_text or "") if payload else ""
    if input_text.strip():
        pasted_rows = _count_pasted_lead_rows(input_text)
        if pasted_rows > IMPORTANT_LEADS_PASTE_MAX_ROWS:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "PASTE_TOO_LARGE",
                    "message": (
                        f"Paste intake is limited to {IMPORTANT_LEADS_PASTE_MAX_ROWS} rows. "
                        f"This paste has {pasted_rows} rows; use CSV upload for large batches."
                    ),
                    "details": {
                        "paste_rows": pasted_rows,
                        "paste_max_rows": IMPORTANT_LEADS_PASTE_MAX_ROWS,
                    },
                    "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
                },
                status_code=413,
            )
        IMPORTANT_LEADS_CHECK_RUNS.mkdir(parents=True, exist_ok=True)
        effective_input_path = IMPORTANT_LEADS_CHECK_RUNS / f"leadschecker_{timestamp_slug()}.csv"
        normalized_text = _normalize_pasted_leads_csv(input_text)
        effective_input_path.write_text(normalized_text, encoding="utf-8")
    return _check_important_leads_response(
        input_path=input_path,
        output_path=output_path,
        rejected_path=rejected_path,
        effective_input_path=effective_input_path,
    )


@app.post("/api/leads/verify-important")
def verify_important_leads(payload: ImportantLeadVerifyPayload | None = None) -> JSONResponse:
    try:
        mode = str(payload.mode if payload else TRIAGE_MODE_FAST).strip().upper()
        mode = TRIAGE_MODE_STRICT if mode == TRIAGE_MODE_STRICT else TRIAGE_MODE_FAST
        if mode == TRIAGE_MODE_FAST:
            current_paths = important_leads_triage_path_state()
            default_keep_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_keep.csv")
            default_rejected_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_reject.csv")
            default_quarantine_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_triaged_quarantine.csv")
            current_keep = current_paths["keep_path"]
        else:
            current_paths = important_leads_verify_path_state()
            default_keep_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_verified.csv")
            default_rejected_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_verify_rejected.csv")
            default_quarantine_path = IMPORTANT_LEADS_OUTPUT.with_name("leads_quarantine.csv")
            current_keep = current_paths["verified_path"]
        input_path = _resolve_dashboard_csv_path(
            payload.input_path if payload else current_paths["input_path"],
            IMPORTANT_LEADS_OUTPUT,
        )
        if mode == TRIAGE_MODE_FAST:
            verified_path = default_keep_path.resolve(strict=False)
            rejected_path = default_rejected_path.resolve(strict=False)
            quarantine_path = default_quarantine_path.resolve(strict=False)
        else:
            verified_path = _resolve_dashboard_csv_path(
                payload.verified_path if payload else current_keep,
                default_keep_path,
            )
            rejected_path = _resolve_dashboard_csv_path(
                payload.rejected_path if payload else current_paths["rejected_path"],
                default_rejected_path,
            )
            quarantine_path = _resolve_dashboard_csv_path(
                payload.quarantine_path if payload else current_paths["quarantine_path"],
                default_quarantine_path,
            )
        if mode == TRIAGE_MODE_STRICT:
            save_state(
                important_leads_verify_paths=_important_verify_path_labels_for_state(
                    input_path,
                    verified_path,
                    rejected_path,
                    quarantine_path,
                )
            )
        else:
            save_state(
                important_leads_triage_paths=_important_triage_path_labels_for_state(
                    input_path,
                    verified_path,
                    rejected_path,
                    quarantine_path,
                )
            )
        job = _start_important_verify_job(
            input_path=input_path,
            verified_path=verified_path,
            rejected_path=rejected_path,
            quarantine_path=quarantine_path,
            mode=mode,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead verify failed: {exc}"}, status_code=500)

    return JSONResponse(
        {
            "ok": True,
            "message": f"Queued {'fast triage' if mode == TRIAGE_MODE_FAST else 'strict public proof'} job {job['job_id']}.",
            "job": job,
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
        },
        status_code=202,
    )


@app.get("/api/leads/verify-important/job/{job_id}")
def get_verify_important_leads_job(job_id: str) -> JSONResponse:
    try:
        job = _load_important_verify_job(job_id)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "message": f"Verify job not found: {job_id}"}, status_code=404)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Failed to load verify job: {exc}"}, status_code=500)
    return JSONResponse({"ok": True, "job": _job_progress_payload(job), "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()}})


@app.get("/api/leads/verify-important/active")
def get_active_verify_important_leads_job() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "job": _find_active_dashboard_job(IMPORTANT_LEADS_VERIFY_JOBS),
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
        }
    )


@app.post("/api/leads/verify-important/job/{job_id}/cancel")
def cancel_verify_important_leads_job(job_id: str) -> JSONResponse:
    try:
        job = _load_important_verify_job(job_id)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "message": f"Verify job not found: {job_id}"}, status_code=404)
    status = str(job.get("status") or "").lower()
    if status in {"completed", "failed", "canceled", "cancelled"}:
        return JSONResponse({"ok": True, "message": f"Verify job already terminal: {status}.", "job": _job_progress_payload(job)})
    job["cancel_requested"] = True
    job["stage"] = "cancel_requested"
    job["phase"] = "cancel_requested"
    job["message"] = "Stop requested. Verify will stop after the current row/checkpoint is saved."
    _save_important_verify_job(job)
    return JSONResponse({"ok": True, "message": "Stop requested for Verify Leads.", "job": _job_progress_payload(job)})


@app.post("/api/leads/dispatch-important/preview")
def preview_dispatch_important_leads(payload: ImportantLeadDispatchPayload | None = None) -> JSONResponse:
    try:
        preflight_block = _dispatch_preflight_block_response(snapshot=_build_live_snapshot())
        if preflight_block is not None:
            return preflight_block
        current_paths = important_leads_path_state()
        verify_paths = important_leads_verify_path_state()
        triage_paths = important_leads_triage_path_state()
        input_path = _resolve_dashboard_csv_path(
            getattr(payload, "input_path", current_paths["input_path"]) if payload else current_paths["input_path"],
            IMPORTANT_LEADS_INPUT,
        )
        output_path = _resolve_dashboard_csv_path(
            getattr(payload, "output_path", current_paths["output_path"]) if payload else current_paths["output_path"],
            IMPORTANT_LEADS_OUTPUT,
        )
        rejected_path = _resolve_dashboard_csv_path(
            getattr(payload, "rejected_path", current_paths["rejected_path"]) if payload else current_paths["rejected_path"],
            IMPORTANT_LEADS_REJECTED,
        )
        dispatch_source_mode = str(getattr(payload, "dispatch_source_mode", DISPATCH_SOURCE_TRIAGED_KEEP) if payload else DISPATCH_SOURCE_TRIAGED_KEEP).strip().lower() or DISPATCH_SOURCE_TRIAGED_KEEP
        dispatch_cap = str(getattr(payload, "dispatch_cap", DISPATCH_CAP_ALL) if payload else DISPATCH_CAP_ALL).strip().lower() or DISPATCH_CAP_ALL
        aliases = {
            "verified": DISPATCH_SOURCE_TRIAGED_KEEP,
            "fast_triage": DISPATCH_SOURCE_TRIAGED_KEEP,
            "fast_triage_keep": DISPATCH_SOURCE_TRIAGED_KEEP,
            "strict": DISPATCH_SOURCE_STRICT_VERIFIED,
            "strict_public_proof": DISPATCH_SOURCE_STRICT_VERIFIED,
        }
        dispatch_source_mode = aliases.get(dispatch_source_mode, dispatch_source_mode)
        if dispatch_source_mode not in {DISPATCH_SOURCE_TRIAGED_KEEP, DISPATCH_SOURCE_STRICT_VERIFIED, DISPATCH_SOURCE_CLEANED}:
            raise ValueError("Dispatch source mode must be triaged_keep, strict_verified, or cleaned.")
        save_state(important_leads_paths=_important_path_labels_for_state(input_path, output_path, rejected_path))
        save_state(important_leads_dispatch_source=_important_dispatch_source_labels_for_state(dispatch_source_mode))
        triaged_keep_source_path = _resolve_dashboard_csv_path(
            triage_paths["keep_path"],
            TRIAGED_KEEP_PATH,
        )
        verified_source_path = _resolve_dashboard_csv_path(
            verify_paths["verified_path"],
            STRICT_VERIFIED_PATH,
        )
        preview = preview_dispatch_master_leads(
            master_path=output_path,
            rejected_path=rejected_path,
            verified_path=verified_source_path,
            triaged_keep_path=triaged_keep_source_path,
            dispatch_source_mode=dispatch_source_mode,
            dispatch_cap=dispatch_cap,
            preview_dir=IMPORTANT_LEADS_DISPATCH_PREVIEWS,
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "error": "missing_source", "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": "invalid_dispatch_request", "message": str(exc)}, status_code=400)
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "error": "dispatch_preview_blocked", "message": str(exc)}, status_code=409)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead dispatch preview failed: {exc}"}, status_code=500)

    return JSONResponse(
        {
            "ok": True,
            "message": f"Preview ready for {preview['dispatch_source_name']}.",
            "preview": preview,
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            "snapshot": _build_live_snapshot(),
        }
    )


def _dispatch_preflight_block_response(*, snapshot: dict[str, object] | None = None) -> JSONResponse | None:
    active_profiles = runtime_control.list_active_sender_snapshots(tail_lines=12)
    if not active_profiles:
        return None
    states = {str(item.name): str(item.runtime_state) for item in active_profiles}
    active_names = list(states.keys())
    return JSONResponse(
        {
            "ok": False,
            "blocked": True,
            "reason": "senders_active",
            "error": "senders_active",
            "active_profiles": active_names,
            "active_sender_count": len(active_names),
            "states": states,
            "message": f"Dispatch blocked: stop active senders first. Active: {', '.join(sorted(states))}",
            "snapshot": snapshot or _build_live_snapshot(),
        },
        status_code=409,
    )


def _dispatch_confirm_response(payload: ImportantLeadDispatchPayload | None = None) -> JSONResponse:
    try:
        preflight_block = _dispatch_preflight_block_response(snapshot=_build_live_snapshot())
        if preflight_block is not None:
            return preflight_block
        preview_id = str(getattr(payload, "preview_id", "") if payload else "").strip()
        if not preview_id:
            raise ValueError("Run Preview Dispatch first.")
        preview = validate_dispatch_preview(preview_id, preview_dir=IMPORTANT_LEADS_DISPATCH_PREVIEWS)
        requested_mode = str(getattr(payload, "dispatch_source_mode", preview.get("dispatch_source_mode") or "") if payload else preview.get("dispatch_source_mode") or "").strip().lower()
        if requested_mode:
            aliases = {
                "verified": DISPATCH_SOURCE_TRIAGED_KEEP,
                "fast_triage": DISPATCH_SOURCE_TRIAGED_KEEP,
                "fast_triage_keep": DISPATCH_SOURCE_TRIAGED_KEEP,
                "strict": DISPATCH_SOURCE_STRICT_VERIFIED,
                "strict_public_proof": DISPATCH_SOURCE_STRICT_VERIFIED,
            }
            requested_mode = aliases.get(requested_mode, requested_mode)
            if requested_mode != str(preview.get("dispatch_source_mode") or ""):
                raise RuntimeError("Dispatch preview does not match the selected source. Re-run Preview Dispatch.")
        requested_cap = str(getattr(payload, "dispatch_cap", preview.get("dispatch_cap") or DISPATCH_CAP_ALL) if payload else preview.get("dispatch_cap") or DISPATCH_CAP_ALL).strip().lower()
        if requested_cap and requested_cap != str(preview.get("dispatch_cap") or DISPATCH_CAP_ALL):
            raise RuntimeError("Dispatch preview does not match the selected cap. Re-run Preview Dispatch.")
        job = _start_important_dispatch_job(
            preview_id=preview_id,
            dispatch_source_mode=str(preview.get("dispatch_source_mode") or DISPATCH_SOURCE_TRIAGED_KEEP),
            dispatch_source_name=str(preview.get("dispatch_source_name") or ""),
            dispatch_source_path=str(preview.get("dispatch_source_path") or ""),
            dispatch_cap=str(preview.get("dispatch_cap") or DISPATCH_CAP_ALL),
            total_source_rows=int(preview.get("dispatch_source_row_count") or 0),
            eligible_rows=int(preview.get("dispatch_eligible_row_count") or 0),
            selected_rows=int(preview.get("dispatch_selected_row_count") or 0),
            total_rows_would_write=int(preview.get("total_rows_would_write") or 0),
        )
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "error": "missing_source", "message": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": "invalid_dispatch_request", "message": str(exc)}, status_code=400)
    except RuntimeError as exc:
        error_code = "stale_preview" if "stale" in str(exc).lower() else "dispatch_blocked"
        return JSONResponse({"ok": False, "error": error_code, "message": str(exc)}, status_code=409)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Lead dispatch failed: {exc}"}, status_code=500)

    return JSONResponse(
        {
            "ok": True,
            "message": f"Queued dispatch confirm job {job['job_id']}.",
            "job": job,
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            "snapshot": _build_live_snapshot(),
        },
        status_code=202,
    )


@app.post("/api/leads/dispatch-important/confirm")
def confirm_dispatch_important_leads(payload: ImportantLeadDispatchPayload | None = None) -> JSONResponse:
    return _dispatch_confirm_response(payload)


@app.post("/api/leads/dispatch-important")
def dispatch_important_leads(payload: ImportantLeadDispatchPayload | None = None) -> JSONResponse:
    return _dispatch_confirm_response(payload)


@app.get("/api/leads/dispatch-important/preflight")
def dispatch_important_leads_preflight() -> JSONResponse:
    snapshot = _build_live_snapshot()
    block = _dispatch_preflight_block_response(snapshot=snapshot)
    if block is not None:
        return block
    return JSONResponse(
        {
            "ok": True,
            "blocked": False,
            "reason": "",
            "error": "",
            "active_profiles": [],
            "active_sender_count": 0,
            "states": {},
            "message": "Dispatch preflight clear.",
            "snapshot": snapshot,
        }
    )


@app.get("/api/leads/dispatch-important/job/{job_id}")
def get_dispatch_important_leads_job(job_id: str) -> JSONResponse:
    try:
        job = _load_important_dispatch_job(job_id)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "message": f"Dispatch job not found: {job_id}"}, status_code=404)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Failed to load dispatch job: {exc}"}, status_code=500)
    return JSONResponse({"ok": True, "job": _job_progress_payload(job), "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()}})


@app.get("/api/leads/dispatch-important/active")
def get_active_dispatch_important_leads_job() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "job": _find_active_dashboard_job(IMPORTANT_LEADS_DISPATCH_JOBS),
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
        }
    )


@app.get("/api/leads/quarantine-review")
def quarantine_review_list(
    reason_code: str = Query(default=""),
    stage: str = Query(default=""),
    status: str = Query(default="QUARANTINE"),
    sort: str = Query(default="score_desc"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    try:
        conn = connect_lead_ledger(_lead_ledger_db_path())
        try:
            review = list_quarantine_review_leads(
                conn,
                reason_code=reason_code,
                stage=stage,
                status=status,
                sort=sort,
                limit=limit,
                offset=offset,
            )
            review["recent_actions"] = load_recent_quarantine_review_actions(conn, limit=12)
        finally:
            conn.close()
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Failed to load quarantine review inbox: {exc}"}, status_code=500)
    return JSONResponse({"ok": True, "review": review})


@app.get("/api/leads/quarantine-review/{lead_id}")
def quarantine_review_detail(lead_id: str) -> JSONResponse:
    try:
        conn = connect_lead_ledger(_lead_ledger_db_path())
        try:
            lead = load_quarantine_review_lead(conn, lead_id)
        finally:
            conn.close()
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Failed to load quarantine review lead: {exc}"}, status_code=500)
    if lead is None:
        return JSONResponse({"ok": False, "message": f"Lead not found: {lead_id}"}, status_code=404)
    return JSONResponse({"ok": True, "lead": lead})


@app.post("/api/leads/quarantine-review/action")
def quarantine_review_action(payload: QuarantineReviewActionPayload) -> JSONResponse:
    try:
        conn = connect_lead_ledger(_lead_ledger_db_path())
        try:
            resolved_lead_ids = payload.lead_ids
            if payload.select_all_filtered:
                resolved_lead_ids = list_quarantine_review_lead_ids(
                    conn,
                    reason_code=payload.reason_code,
                    stage=payload.stage,
                    status=payload.status,
                    sort=payload.sort,
                    exclude_lead_ids=payload.excluded_lead_ids,
                )
            result = apply_quarantine_review_action(
                conn,
                lead_ids=resolved_lead_ids,
                action=payload.action,
                operator_note=payload.operator_note,
                run_id=f"quarantine_review_{timestamp_slug()}",
            )
            review = list_quarantine_review_leads(conn)
            review["recent_actions"] = load_recent_quarantine_review_actions(conn, limit=12)
        finally:
            conn.close()
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"Failed to apply quarantine review action: {exc}"}, status_code=500)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Applied {result['action']} to {int(result['updated'] or 0)} lead(s).",
            "result": result,
            "review": review,
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
            "snapshot": _build_live_snapshot(),
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
    return JSONResponse({"ok": True, "status": _combined_leads_status()})


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
    ledger_summary = ingest_send_outcome_events(unique_events, db_path=settings.LEAD_LEDGER_DB_PATH)
    auto_stops = runtime_control.apply_delivery_guards()
    json_safe_summary = {
        "updated_events": int(suppression_summary.get("updated_events", 0) or 0),
        "records_total": int(suppression_summary.get("records_total", 0) or 0),
        "total_perm": int(suppression_summary.get("total_perm", 0) or 0),
        "total_temp_active": int(suppression_summary.get("total_temp_active", 0) or 0),
    }
    json_safe_ledger_summary = {
        "processed_events": int(ledger_summary.get("processed_events", 0) or 0),
        "matched_events": int(ledger_summary.get("matched_events", 0) or 0),
        "unmatched_events": int(ledger_summary.get("unmatched_events", 0) or 0),
        "ignored_events": int(ledger_summary.get("ignored_events", 0) or 0),
        "dispatch_rows_updated": int(ledger_summary.get("dispatch_rows_updated", 0) or 0),
        "lead_rows_updated": int(ledger_summary.get("lead_rows_updated", 0) or 0),
        "suppressed_events": int(ledger_summary.get("suppressed_events", 0) or 0),
        "outcome_counts": {
            str(key): int(value or 0)
            for key, value in dict(ledger_summary.get("outcome_counts", {})).items()
        },
    }
    return JSONResponse(
        {
            "ok": True,
            "received": len(payload),
            "normalized": len(normalized),
            "stored": appended,
            "duplicates_ignored": int(dedupe_result.get("duplicates", 0) or 0),
            "suppression_summary": json_safe_summary,
            "ledger_summary": json_safe_ledger_summary,
            "auto_stops": auto_stops,
        }
    )


@app.websocket("/ws")
async def websocket_snapshot_stream(
    websocket: WebSocket,
    hours: int = Query(default=24, ge=1, le=168),
    tail_lines: int = Query(default=12, ge=4, le=50),
) -> None:
    if not _dashboard_auth_enabled() or not _dashboard_is_authenticated(websocket):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(_build_live_snapshot(activity_hours=hours, tail_lines=tail_lines))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
