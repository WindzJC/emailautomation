from __future__ import annotations

import asyncio
import base64
import csv
import json
import os
import io
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Form, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from openpyxl import load_workbook
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

try:
    from defusedxml import defuse_stdlib
except Exception:  # pragma: no cover - dependency fallback
    defuse_stdlib = None

import settings
import runtime_control
from dashboard_core import (
    SENDGRID_PROFILES,
    build_dashboard_snapshot,
    load_dashboard_run_settings,
    save_dashboard_send_cap_per_profile,
)
from important_leads_workflow import (
    ImportantLeadsCheckError,
    check_master_leads,
    dispatch_master_leads,
    important_leads_status,
    important_leads_path_state,
)
from important_leads_verify import (
    important_leads_verify_path_state,
    important_leads_verify_status,
    verify_master_leads,
)
from private_bounce_hygiene import (
    PRIVATE_BOUNCE_MONITOR_ENABLED,
    PRIVATE_BOUNCE_SYNC_INTERVAL_SECONDS,
    run_private_bounce_monitor_cycle,
)
from provider_pacing import mark_recovery_started, provider_pacing_status
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
    iso_utc,
    save_state,
    preview_shard_cleaned_leads,
    save_uploaded_csv,
    shard_cleaned_leads,
    shard_status,
    timestamp_slug,
)
from send_shard import PROFILES


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

STATIC_DIR = settings.STATIC_DIR
SUPPRESSION_CSV = settings.SENDGRID_SUPPRESSIONS_PATH
WEBHOOK_EVENTS_PATH = settings.WEBHOOK_EVENTS_PATH
WEBHOOK_DEDUPE_PATH = settings.WEBHOOK_DEDUPE_PATH
IMPORTANT_LEADS_INPUT = settings.APP_ROOT / "_important" / "leadschecker.csv"
IMPORTANT_LEADS_OUTPUT = settings.APP_ROOT / "_important" / "leads.csv"
IMPORTANT_LEADS_REJECTED = settings.APP_ROOT / "_important" / "leads_rejected.csv"
IMPORTANT_LEADS_CHECK_RUNS = settings.APP_ROOT / "_important" / "check_runs"
IMPORTANT_LEADS_CHECK_JOBS = IMPORTANT_LEADS_CHECK_RUNS / "jobs"
IMPORTANT_LEADS_PASTE_WARNING_ROWS = _int_env("IMPORTANT_LEADS_PASTE_WARNING_ROWS", 250)
IMPORTANT_LEADS_PASTE_MAX_ROWS = max(IMPORTANT_LEADS_PASTE_WARNING_ROWS, _int_env("IMPORTANT_LEADS_PASTE_MAX_ROWS", 1000))
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
    dispatch_source_mode: str = "verified"
    input_text: str = ""


class ImportantLeadVerifyPayload(BaseModel):
    input_path: str = ""
    verified_path: str = ""
    rejected_path: str = ""
    quarantine_path: str = ""


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


def _important_dispatch_source_labels_for_state(mode: str) -> dict[str, str]:
    normalized = str(mode or "").strip().lower() or "verified"
    if normalized not in {"verified", "cleaned"}:
        normalized = "verified"
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


def _normalize_uploaded_check_file(filename: str, content: bytes) -> tuple[str, str]:
    extension = Path(str(filename or "").strip()).suffix.lower()
    if extension == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        return ".csv", text if text.endswith("\n") else f"{text}\n"
    if extension == ".xlsx":
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise ValueError(f"Failed to read XLSX upload: {exc}") from exc
        try:
            worksheet = workbook[workbook.sheetnames[0]] if workbook.sheetnames else None
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
            return ".xlsx", text
        finally:
            workbook.close()
    raise ValueError(f"Unsupported upload file type: {extension or '[none]'}")


def _execute_important_check(
    *,
    input_path: Path,
    output_path: Path,
    rejected_path: Path,
    effective_input_path: Path,
) -> dict[str, object]:
    save_state(important_leads_paths=_important_path_labels_for_state(input_path, output_path, rejected_path))
    return check_master_leads(
        input_path=effective_input_path,
        output_path=output_path,
        rejected_path=rejected_path,
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
        _save_important_check_job(job)
        report = _execute_important_check(
            input_path=Path(str(job.get("input_path") or "")),
            output_path=Path(str(job.get("output_path") or "")),
            rejected_path=Path(str(job.get("rejected_path") or "")),
            effective_input_path=Path(str(job.get("effective_input_path") or "")),
        )
        job["status"] = "completed"
        job["stage"] = "done"
        job["completed_at_utc"] = iso_utc()
        job["check"] = report
        job["processed_rows"] = int(report.get("total_input_rows") or report.get("input_rows") or job.get("total_input_rows") or 0)
        job["remaining_rows"] = 0
        job["eta_seconds"] = 0
        job["message"] = (
            f"Checked {report['input_label']} into {report['output_label']}. "
            f"Kept {int(report['cleaned_rows'] or 0)} row(s), rejected "
            f"{sum(int(report['reason_counts'].get(reason, 0)) for reason in report.get('reason_counts', {}))}."
        )
        _save_important_check_job(job)
    except Exception as exc:
        job["status"] = "failed"
        job["stage"] = "failed"
        job["completed_at_utc"] = iso_utc()
        job["processed_rows"] = 0
        job["remaining_rows"] = int(job.get("total_input_rows") or 0)
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
        "input_path": str(input_path),
        "saved_input_path": str(effective_input_path),
        "output_path": str(output_path),
        "rejected_path": str(rejected_path),
        "effective_input_path": str(effective_input_path),
        "total_input_rows": int(total_input_rows or 0),
        "processed_rows": 0,
        "remaining_rows": int(total_input_rows or 0),
        "eta_seconds": "",
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
    if getattr(app.state, "automation_task", None) is None:
        app.state.automation_task = asyncio.create_task(_background_automation_loop())
    _resume_pending_important_check_jobs()


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
            "message": f"Dashboard send cap saved: {cap} per sender.",
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
    resolved_output_path = _resolve_dashboard_csv_path(
        output_path or current_paths["output_path"],
        IMPORTANT_LEADS_OUTPUT,
    )
    resolved_rejected_path = _resolve_dashboard_csv_path(
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
    if selected_size_bytes > settings.DASHBOARD_MAX_UPLOAD_BYTES:
        return JSONResponse(
            {
                "ok": False,
                "message": f"Upload too large. Limit is {settings.DASHBOARD_MAX_UPLOAD_BYTES} bytes.",
                "error": "UPLOAD_TOO_LARGE",
                "details": {"max_upload_bytes": settings.DASHBOARD_MAX_UPLOAD_BYTES},
                "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            },
            status_code=413,
        )
    try:
        content = await _read_upload_bytes_with_limit(file, limit=settings.DASHBOARD_MAX_UPLOAD_BYTES)
    except ValueError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": str(exc),
                "error": "UPLOAD_TOO_LARGE",
                "details": {"max_upload_bytes": settings.DASHBOARD_MAX_UPLOAD_BYTES},
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
        normalized_extension, normalized_text = _normalize_uploaded_check_file(filename, content)
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
    return JSONResponse({"ok": True, "job": job, "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()}})


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
        current_paths = important_leads_verify_path_state()
        input_path = _resolve_dashboard_csv_path(
            payload.input_path if payload else current_paths["input_path"],
            IMPORTANT_LEADS_OUTPUT,
        )
        verified_path = _resolve_dashboard_csv_path(
            payload.verified_path if payload else current_paths["verified_path"],
            IMPORTANT_LEADS_OUTPUT.with_name("leads_verified.csv"),
        )
        rejected_path = _resolve_dashboard_csv_path(
            payload.rejected_path if payload else current_paths["rejected_path"],
            IMPORTANT_LEADS_OUTPUT.with_name("leads_verify_rejected.csv"),
        )
        quarantine_path = _resolve_dashboard_csv_path(
            payload.quarantine_path if payload else current_paths["quarantine_path"],
            IMPORTANT_LEADS_OUTPUT.with_name("leads_quarantine.csv"),
        )
        save_state(
            important_leads_verify_paths=_important_verify_path_labels_for_state(
                input_path,
                verified_path,
                rejected_path,
                quarantine_path,
            )
        )
        report = verify_master_leads(
            input_path=input_path,
            verified_path=verified_path,
            rejected_path=rejected_path,
            quarantine_path=quarantine_path,
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
            "message": (
                f"Verified {report['input_label']} into {report['verified_label']}. "
                f"KEEP {int(report['keep_count'] or 0)}, REJECT {int(report['reject_count'] or 0)}, "
                f"QUARANTINE {int(report['quarantine_count'] or 0)}."
            ),
            "verify": report,
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
        }
    )


@app.post("/api/leads/dispatch-important")
def dispatch_important_leads(payload: ImportantLeadPathsPayload | None = None) -> JSONResponse:
    try:
        current_paths = important_leads_path_state()
        verify_paths = important_leads_verify_path_state()
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
        dispatch_source_mode = str(payload.dispatch_source_mode if payload else "verified").strip().lower() or "verified"
        if dispatch_source_mode not in {"verified", "cleaned"}:
            raise ValueError("Dispatch source mode must be verified or cleaned.")
        save_state(important_leads_paths=_important_path_labels_for_state(input_path, output_path, rejected_path))
        save_state(important_leads_dispatch_source=_important_dispatch_source_labels_for_state(dispatch_source_mode))
        verified_source_path = _resolve_dashboard_csv_path(
            verify_paths["verified_path"],
            IMPORTANT_LEADS_OUTPUT.with_name("leads_verified.csv"),
        )
        report = dispatch_master_leads(
            master_path=output_path,
            verified_path=verified_source_path,
            dispatch_source_mode=dispatch_source_mode,
            rejected_path=rejected_path,
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
            "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()},
            "snapshot": _build_live_snapshot(),
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
    return JSONResponse({"ok": True, "status": {**shard_status(), **important_leads_status(), **important_leads_verify_status()}})


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
