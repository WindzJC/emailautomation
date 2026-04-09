from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable


APP_ROOT = Path(__file__).resolve().parent
ENV_FILES = [APP_ROOT / ".env.local", APP_ROOT / ".env"]


def _load_env_files() -> None:
    for path in ENV_FILES:
        if not path.exists():
            continue
        try:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in raw_line:
                    continue
                key, value = raw_line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                value = value.strip()
                if value and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                os.environ[key] = value
        except Exception:
            continue


_load_env_files()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except Exception:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def _resolve_path(raw: str, default: Path | None = None) -> Path:
    text = (raw or "").strip()
    if not text:
        if default is None:
            return APP_ROOT
        return default
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = APP_ROOT / path
    return path.resolve()


def _managed_dir(var_name: str, default_name: str) -> Path:
    return _resolve_path(_env(var_name), DATA_DIR / default_name)


APP_HOST = _env("APP_HOST", _env("LIVE_DASHBOARD_HOST", "127.0.0.1")) or "127.0.0.1"
APP_PORT = _env_int("APP_PORT", _env_int("LIVE_DASHBOARD_PORT", 8001))
DATA_DIR = _resolve_path(_env("DATA_DIR"), APP_ROOT / "data")

UPLOADS_DIR = _managed_dir("UPLOADS_DIR", "uploads")
CLEANED_DIR = _managed_dir("CLEANED_DIR", "cleaned")
SHARDS_DIR = _managed_dir("SHARDS_DIR", "shards")
LOGS_DIR = _managed_dir("LOGS_DIR", "logs")
STATE_DIR = _managed_dir("STATE_DIR", "state")
TMP_DIR = _managed_dir("TMP_DIR", "tmp")

STATIC_DIR = APP_ROOT / "web_dashboard"
ACTIVITY_LOG_PATH = LOGS_DIR / "sendgridlogs"
BACKUPS_DIR = STATE_DIR / "backups"
LEADS_BACKUP_ROOT = BACKUPS_DIR / "leads"
LOG_RESET_BACKUP_ROOT = BACKUPS_DIR

DASHBOARD_RUN_SETTINGS_PATH = STATE_DIR / "dashboard_run_settings.json"
LEADS_STATE_PATH = STATE_DIR / "leads_dashboard_state.json"
LATEST_SHARD_REPORT_PATH = STATE_DIR / "shard_report_latest.json"
SENDGRID_NORMALIZE_REPORT_PATH = STATE_DIR / "sendgrid_shard_normalize_report.json"
WEBHOOK_EVENTS_PATH = LOGS_DIR / "sendgrid_events.jsonl"
WEBHOOK_DEDUPE_PATH = STATE_DIR / "sendgrid_webhook_dedupe.sqlite3"
SENDGRID_SUPPRESSIONS_PATH = STATE_DIR / "sendgrid_suppressions.csv"
SUPPRESSED_PATH = STATE_DIR / "suppressed.csv"
UNSUBSCRIBED_PATH = STATE_DIR / "unsubscribed.csv"
SENDGRID_COUNTERS_PATH = STATE_DIR / "sendgrid_daily_counters.json"

SEND_CAP_DEFAULT = _env_int("SEND_CAP_DEFAULT", 100)
ALLOWED_ORIGINS = tuple(item.strip() for item in _env("ALLOWED_ORIGINS").split(",") if item.strip())
SECRET_KEY = _env("SECRET_KEY", "change-me")
DASHBOARD_SESSION_SECRET = _env("DASHBOARD_SESSION_SECRET", SECRET_KEY)
DASHBOARD_AUTH_USERNAME = _env("DASHBOARD_AUTH_USERNAME", "admin")
DASHBOARD_AUTH_PASSWORD = _env("DASHBOARD_AUTH_PASSWORD", SECRET_KEY)
DASHBOARD_AUTH_COOKIE_NAME = _env("DASHBOARD_AUTH_COOKIE_NAME", "dashboard_session")
DASHBOARD_MAX_UPLOAD_BYTES = _env_int("DASHBOARD_MAX_UPLOAD_BYTES", 25 * 1024 * 1024, minimum=1)
PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700
MANAGED_SHARD_HEADERS = ("Email", "AuthorName", "BookTitle")


def ensure_dirs(paths: Iterable[Path] | None = None) -> None:
    managed_paths = tuple(paths or (
        DATA_DIR,
        UPLOADS_DIR,
        CLEANED_DIR,
        SHARDS_DIR,
        LOGS_DIR,
        STATE_DIR,
        TMP_DIR,
        BACKUPS_DIR,
        LEADS_BACKUP_ROOT,
    ))
    for path in managed_paths:
        path.mkdir(parents=True, exist_ok=True)
        secure_private_dir(path)


def ensure_csv_with_headers(path: Path, headers: Iterable[str]) -> Path:
    ensure_dirs((path.parent,))
    if path.exists() and path.stat().st_size > 0:
        return path
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(headers))
        writer.writeheader()
    secure_private_file(path)
    return path


def app_path(value: str | Path) -> Path:
    path = Path(str(value or "").strip())
    if path.is_absolute():
        return path
    return (APP_ROOT / path).resolve()


def _managed_file(base_dir: Path, value: str | Path) -> Path:
    text = str(value or "").strip()
    if not text:
        return base_dir
    path = Path(text)
    if path.is_absolute():
        return path
    return (base_dir / path.name).resolve()


def shard_path(value: str | Path) -> Path:
    path = _managed_file(SHARDS_DIR, value)
    name = Path(str(value or "").strip()).name
    if name:
        ensure_managed_shard_file(path, name)
    return path


def log_path(value: str | Path) -> Path:
    path = _managed_file(LOGS_DIR, value)
    name = Path(str(value or "").strip()).name
    if name:
        maybe_seed_file(path, name)
    return path


def state_path(value: str | Path) -> Path:
    path = _managed_file(STATE_DIR, value)
    name = Path(str(value or "").strip()).name
    if name:
        maybe_seed_file(path, name)
    return path


def upload_path(value: str | Path) -> Path:
    path = _managed_file(UPLOADS_DIR, value)
    name = Path(str(value or "").strip()).name
    if name:
        maybe_seed_file(path, name)
    return path


def cleaned_path(value: str | Path) -> Path:
    path = _managed_file(CLEANED_DIR, value)
    name = Path(str(value or "").strip()).name
    if name:
        maybe_seed_file(path, name)
    return path


def tmp_path(value: str | Path) -> Path:
    return _managed_file(TMP_DIR, value)


def maybe_seed_file(target: Path, legacy: str | Path | None = None) -> Path:
    ensure_dirs((target.parent,))
    legacy_path = app_path(legacy) if legacy else None
    if target.exists() or legacy_path is None or not legacy_path.exists():
        return target
    if legacy_path.resolve() == target.resolve():
        return target
    shutil.copy2(legacy_path, target)
    return target


def ensure_managed_shard_file(target: Path, legacy: str | Path | None = None) -> Path:
    ensure_dirs((target.parent,))
    legacy_path = app_path(legacy) if legacy else None
    if target.exists() and target.stat().st_size > 0:
        secure_private_file(target)
        return target
    if legacy_path is not None and legacy_path.exists():
        if legacy_path.resolve() != target.resolve() and legacy_path.stat().st_size > 0:
            shutil.copy2(legacy_path, target)
            secure_private_file(target)
            return target
    ensure_csv_with_headers(target, MANAGED_SHARD_HEADERS)
    secure_private_file(target)
    return target


def maybe_seed_dir(target: Path, legacy: str | Path | None = None) -> Path:
    ensure_dirs((target.parent,))
    legacy_path = app_path(legacy) if legacy else None
    if target.exists() or legacy_path is None or not legacy_path.exists():
        return target
    if legacy_path.resolve() == target.resolve():
        return target
    shutil.copytree(legacy_path, target, dirs_exist_ok=True)
    return target


def seed_missing_dir_contents(target: Path, legacy: str | Path | None = None) -> Path:
    ensure_dirs((target,))
    legacy_path = app_path(legacy) if legacy else None
    if legacy_path is None or not legacy_path.exists() or not legacy_path.is_dir():
        return target
    for source in legacy_path.rglob("*"):
        if not source.is_file():
            continue
        destination = target / source.relative_to(legacy_path)
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return target


def secure_private_file(path: Path) -> Path:
    try:
        path.chmod(PRIVATE_FILE_MODE)
    except Exception:
        pass
    return path


def secure_private_dir(path: Path) -> Path:
    try:
        path.chmod(PRIVATE_DIR_MODE)
    except Exception:
        pass
    return path


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    ensure_dirs((path.parent,))
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def _artifact_target(value: object, default_dir: Path, filename_key: str) -> Path | None:
    if isinstance(value, dict):
        filename = str(value.get(filename_key) or "").strip()
    else:
        filename = ""
    if not filename:
        return None
    return (default_dir / Path(filename).name).resolve()


def migrate_seeded_state_paths() -> None:
    if not LEADS_STATE_PATH.exists():
        return
    try:
        raw = json.loads(LEADS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(raw, dict):
        return

    changed = False

    latest_upload = raw.get("latest_upload")
    if isinstance(latest_upload, dict):
        saved_target = _artifact_target(latest_upload, UPLOADS_DIR, "saved_filename")
        saved_path_raw = str(latest_upload.get("saved_path") or "").strip()
        if saved_target is not None:
            legacy_saved = saved_path_raw or str(Path("uploads") / saved_target.name)
            maybe_seed_file(saved_target, legacy_saved)
            saved_target_str = str(saved_target)
            if latest_upload.get("saved_path") != saved_target_str:
                latest_upload["saved_path"] = saved_target_str
                changed = True

    latest_cleaned = raw.get("latest_cleaned")
    if isinstance(latest_cleaned, dict):
        cleaned_target = _artifact_target(latest_cleaned, CLEANED_DIR, "filename")
        cleaned_path_raw = str(latest_cleaned.get("path") or "").strip()
        if cleaned_target is not None:
            legacy_cleaned = cleaned_path_raw or str(Path("cleaned") / cleaned_target.name)
            maybe_seed_file(cleaned_target, legacy_cleaned)
            cleaned_target_str = str(cleaned_target)
            if latest_cleaned.get("path") != cleaned_target_str:
                latest_cleaned["path"] = cleaned_target_str
                changed = True
        report_name = Path(str(latest_cleaned.get("report_path") or "").strip()).name
        if report_name:
            report_target = (STATE_DIR / report_name).resolve()
            legacy_report = str(latest_cleaned.get("report_path") or "") or str(Path("reports") / report_name)
            maybe_seed_file(report_target, legacy_report)
            report_target_str = str(report_target)
            if latest_cleaned.get("report_path") != report_target_str:
                latest_cleaned["report_path"] = report_target_str
                changed = True

    latest_shard_report = raw.get("latest_shard_report")
    if isinstance(latest_shard_report, dict):
        report_name = Path(str(latest_shard_report.get("report_path") or "").strip()).name
        if report_name:
            report_target = (STATE_DIR / report_name).resolve()
            legacy_report = str(latest_shard_report.get("report_path") or "") or str(Path("reports") / report_name)
            maybe_seed_file(report_target, legacy_report)
            report_target_str = str(report_target)
            if latest_shard_report.get("report_path") != report_target_str:
                latest_shard_report["report_path"] = report_target_str
                changed = True

    if changed:
        _write_json_atomic(LEADS_STATE_PATH, raw)


def seed_known_runtime_artifacts() -> None:
    ensure_dirs()
    seed_missing_dir_contents(UPLOADS_DIR, "uploads")
    seed_missing_dir_contents(CLEANED_DIR, "cleaned")
    maybe_seed_file(ACTIVITY_LOG_PATH, "sendgridlogs")
    maybe_seed_file(DASHBOARD_RUN_SETTINGS_PATH, "dashboard_run_settings.json")
    maybe_seed_file(LEADS_STATE_PATH, "leads_dashboard_state.json")
    maybe_seed_file(WEBHOOK_EVENTS_PATH, "sendgrid_events.jsonl")
    maybe_seed_file(WEBHOOK_DEDUPE_PATH, "sendgrid_webhook_dedupe.sqlite3")
    maybe_seed_file(SENDGRID_SUPPRESSIONS_PATH, "sendgrid_suppressions.csv")
    maybe_seed_file(SUPPRESSED_PATH, "suppressed.csv")
    maybe_seed_file(UNSUBSCRIBED_PATH, "unsubscribed.csv")
    maybe_seed_file(SENDGRID_COUNTERS_PATH, "sendgrid_daily_counters.json")
    maybe_seed_file(SENDGRID_NORMALIZE_REPORT_PATH, "sendgrid_shard_normalize_report.json")
    migrate_seeded_state_paths()


seed_known_runtime_artifacts()
