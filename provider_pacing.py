from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import settings


PROVIDER_PACING_STATE_PATH = settings.STATE_DIR / "provider_pacing_state.json"
PRIVATE_THROTTLE_WINDOW_24H = timedelta(hours=24)
PRIVATE_THROTTLE_WINDOW_6H = timedelta(hours=6)
PRIVATE_TEMP_FAILURE_WINDOW_24H = timedelta(hours=24)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_utc(raw: object) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text)
    except Exception:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    settings.ensure_dirs((path.parent,))
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def _default_state() -> dict[str, object]:
    return {
        "profiles": {},
        "updated_at_utc": "",
    }


def _normalize_entry(raw: object) -> dict[str, object]:
    data = raw if isinstance(raw, dict) else {}
    throttle_events = [
        ts.isoformat()
        for ts in (_parse_iso_utc(item) for item in data.get("throttle_events_utc", []))
        if ts is not None
    ]
    temporary_failure_events = [
        ts.isoformat()
        for ts in (_parse_iso_utc(item) for item in data.get("temporary_failure_events_utc", []))
        if ts is not None
    ]
    cooldown_until = _parse_iso_utc(data.get("cooldown_until_utc"))
    last_throttle = _parse_iso_utc(data.get("last_throttle_at_utc"))
    last_temporary_failure = _parse_iso_utc(data.get("last_temporary_failure_at_utc"))
    last_recovery = _parse_iso_utc(data.get("last_recovery_started_utc"))
    return {
        "profile_name": str(data.get("profile_name") or ""),
        "provider": str(data.get("provider") or ""),
        "cooldown_until_utc": cooldown_until.isoformat() if cooldown_until else "",
        "recovery_kind": str(data.get("recovery_kind") or ""),
        "recovery_reason": str(data.get("recovery_reason") or ""),
        "last_throttle_at_utc": last_throttle.isoformat() if last_throttle else "",
        "last_throttle_reason": str(data.get("last_throttle_reason") or ""),
        "last_temporary_failure_at_utc": last_temporary_failure.isoformat() if last_temporary_failure else "",
        "last_temporary_failure_reason": str(data.get("last_temporary_failure_reason") or ""),
        "last_recovery_started_utc": last_recovery.isoformat() if last_recovery else "",
        "recovery_pending": bool(data.get("recovery_pending")),
        "throttle_events_utc": throttle_events,
        "temporary_failure_events_utc": temporary_failure_events,
        "adaptive_cooldown_seconds": max(0, int(data.get("adaptive_cooldown_seconds") or 0)),
        "updated_at_utc": str(data.get("updated_at_utc") or ""),
    }


def load_provider_pacing_state() -> dict[str, object]:
    state = _default_state()
    if not PROVIDER_PACING_STATE_PATH.exists():
        return state
    try:
        raw = json.loads(PROVIDER_PACING_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return state
    if not isinstance(raw, dict):
        return state
    profiles_raw = raw.get("profiles")
    profiles: Dict[str, dict[str, object]] = {}
    if isinstance(profiles_raw, dict):
        for profile_name, entry in profiles_raw.items():
            profiles[str(profile_name)] = _normalize_entry(entry)
    state["profiles"] = profiles
    state["updated_at_utc"] = str(raw.get("updated_at_utc") or "")
    return state


def save_provider_pacing_state(state: dict[str, object]) -> dict[str, object]:
    profiles_raw = state.get("profiles")
    payload_profiles: Dict[str, dict[str, object]] = {}
    if isinstance(profiles_raw, dict):
        for profile_name, entry in profiles_raw.items():
            payload_profiles[str(profile_name)] = _normalize_entry(entry)
    payload = {
        "profiles": payload_profiles,
        "updated_at_utc": _now_utc().isoformat(),
    }
    _atomic_write_json(PROVIDER_PACING_STATE_PATH, payload)
    return payload


def _recent_throttle_events(entry: dict[str, object], now: datetime) -> List[datetime]:
    return _recent_event_times(entry, "throttle_events_utc", now, PRIVATE_THROTTLE_WINDOW_24H)


def _recent_event_times(entry: dict[str, object], key: str, now: datetime, window: timedelta) -> List[datetime]:
    recent: List[datetime] = []
    for ts in (_parse_iso_utc(item) for item in entry.get(key, [])):
        if ts is None:
            continue
        if now - ts <= window:
            recent.append(ts)
    recent.sort()
    return recent


def throttle_pause_seconds(provider: str, throttle_count_24h_after_event: int) -> int:
    provider_name = str(provider or "").strip().lower()
    if provider_name != "private":
        return 15 * 60
    if throttle_count_24h_after_event >= 2:
        return 90 * 60
    return 75 * 60


def temporary_failure_pause_seconds(provider: str, failure_count_24h_after_event: int) -> int:
    provider_name = str(provider or "").strip().lower()
    if provider_name != "private":
        return 10 * 60
    if failure_count_24h_after_event >= 3:
        return 30 * 60
    return 15 * 60


def recommended_cooldown_seconds(
    provider: str,
    configured_cooldown_seconds: int,
    recent_throttle_count_24h: int,
    last_throttle_at_utc: datetime | None,
    *,
    now: datetime | None = None,
) -> int:
    provider_name = str(provider or "").strip().lower()
    configured = max(0, int(configured_cooldown_seconds or 0))
    if provider_name != "private" or last_throttle_at_utc is None:
        return configured

    current_time = now or _now_utc()
    age = current_time - last_throttle_at_utc
    if recent_throttle_count_24h >= 3:
        return max(configured, 150)
    if age <= PRIVATE_THROTTLE_WINDOW_6H:
        return max(configured, 120)
    if age <= PRIVATE_THROTTLE_WINDOW_24H:
        return max(configured, 105)
    return configured


def provider_pacing_status(
    profile_name: str,
    provider: str,
    configured_cooldown_seconds: int,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    current_time = now or _now_utc()
    state = load_provider_pacing_state()
    profiles = state.get("profiles")
    entry = _normalize_entry(profiles.get(profile_name, {})) if isinstance(profiles, dict) else _normalize_entry({})
    recent_events = _recent_throttle_events(entry, current_time)
    recent_temporary_failures = _recent_event_times(
        entry,
        "temporary_failure_events_utc",
        current_time,
        PRIVATE_TEMP_FAILURE_WINDOW_24H,
    )
    last_throttle = recent_events[-1] if recent_events else _parse_iso_utc(entry.get("last_throttle_at_utc"))
    cooldown_until = _parse_iso_utc(entry.get("cooldown_until_utc"))
    cooldown_active = bool(cooldown_until and cooldown_until > current_time)
    remaining_seconds = max(0, int((cooldown_until - current_time).total_seconds())) if cooldown_active and cooldown_until else 0
    recommended = recommended_cooldown_seconds(
        provider,
        configured_cooldown_seconds,
        len(recent_events),
        last_throttle,
        now=current_time,
    )
    return {
        "profile_name": str(profile_name or ""),
        "provider": str(provider or ""),
        "cooldown_active": cooldown_active,
        "cooldown_until_utc": cooldown_until.isoformat() if cooldown_until else "",
        "cooldown_remaining_seconds": remaining_seconds,
        "recovery_kind": str(entry.get("recovery_kind") or ""),
        "recovery_reason": str(entry.get("recovery_reason") or ""),
        "last_throttle_at_utc": last_throttle.isoformat() if last_throttle else "",
        "last_throttle_reason": str(entry.get("last_throttle_reason") or ""),
        "last_temporary_failure_at_utc": str(entry.get("last_temporary_failure_at_utc") or ""),
        "last_temporary_failure_reason": str(entry.get("last_temporary_failure_reason") or ""),
        "recovery_pending": bool(entry.get("recovery_pending")),
        "recent_throttle_count_24h": len(recent_events),
        "recent_temporary_failure_count_24h": len(recent_temporary_failures),
        "recommended_cooldown_seconds": recommended,
        "adaptive_cooldown_seconds": max(0, int(entry.get("adaptive_cooldown_seconds") or 0)),
        "last_recovery_started_utc": str(entry.get("last_recovery_started_utc") or ""),
    }


def record_provider_throttle(
    profile_name: str,
    provider: str,
    wait_seconds: int,
    configured_cooldown_seconds: int,
    reason: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    current_time = now or _now_utc()
    state = load_provider_pacing_state()
    profiles = state.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        state["profiles"] = profiles
    entry = _normalize_entry(profiles.get(profile_name, {}))
    recent = _recent_throttle_events(entry, current_time)
    recent.append(current_time)
    recommended = recommended_cooldown_seconds(
        provider,
        configured_cooldown_seconds,
        len(recent),
        recent[-1],
        now=current_time,
    )
    cooldown_until = current_time + timedelta(seconds=max(0, int(wait_seconds or 0)))
    entry.update(
        {
            "profile_name": str(profile_name or ""),
            "provider": str(provider or ""),
            "cooldown_until_utc": cooldown_until.isoformat(),
            "recovery_kind": "provider_throttle",
            "recovery_reason": str(reason or ""),
            "last_throttle_at_utc": current_time.isoformat(),
            "last_throttle_reason": str(reason or ""),
            "recovery_pending": True,
            "throttle_events_utc": [ts.isoformat() for ts in recent],
            "adaptive_cooldown_seconds": recommended,
            "updated_at_utc": current_time.isoformat(),
        }
    )
    profiles[str(profile_name)] = entry
    save_provider_pacing_state(state)
    return provider_pacing_status(
        profile_name,
        provider,
        configured_cooldown_seconds,
        now=current_time,
    )


def record_provider_temporary_failure(
    profile_name: str,
    provider: str,
    wait_seconds: int,
    configured_cooldown_seconds: int,
    reason: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    current_time = now or _now_utc()
    state = load_provider_pacing_state()
    profiles = state.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        state["profiles"] = profiles
    entry = _normalize_entry(profiles.get(profile_name, {}))
    recent_failures = _recent_event_times(
        entry,
        "temporary_failure_events_utc",
        current_time,
        PRIVATE_TEMP_FAILURE_WINDOW_24H,
    )
    recent_failures.append(current_time)
    recommended = recommended_cooldown_seconds(
        provider,
        configured_cooldown_seconds,
        len(_recent_throttle_events(entry, current_time)),
        _parse_iso_utc(entry.get("last_throttle_at_utc")),
        now=current_time,
    )
    cooldown_until = current_time + timedelta(seconds=max(0, int(wait_seconds or 0)))
    entry.update(
        {
            "profile_name": str(profile_name or ""),
            "provider": str(provider or ""),
            "cooldown_until_utc": cooldown_until.isoformat(),
            "recovery_kind": "temporary_auth_failure",
            "recovery_reason": str(reason or ""),
            "last_temporary_failure_at_utc": current_time.isoformat(),
            "last_temporary_failure_reason": str(reason or ""),
            "recovery_pending": True,
            "temporary_failure_events_utc": [ts.isoformat() for ts in recent_failures],
            "adaptive_cooldown_seconds": recommended,
            "updated_at_utc": current_time.isoformat(),
        }
    )
    profiles[str(profile_name)] = entry
    save_provider_pacing_state(state)
    return provider_pacing_status(
        profile_name,
        provider,
        configured_cooldown_seconds,
        now=current_time,
    )


def mark_recovery_started(profile_name: str, *, now: datetime | None = None) -> dict[str, object]:
    current_time = now or _now_utc()
    state = load_provider_pacing_state()
    profiles = state.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        state["profiles"] = profiles
    entry = _normalize_entry(profiles.get(profile_name, {}))
    entry["recovery_pending"] = False
    entry["recovery_kind"] = ""
    entry["recovery_reason"] = ""
    entry["last_recovery_started_utc"] = current_time.isoformat()
    entry["updated_at_utc"] = current_time.isoformat()
    profiles[str(profile_name)] = entry
    save_provider_pacing_state(state)
    return entry
