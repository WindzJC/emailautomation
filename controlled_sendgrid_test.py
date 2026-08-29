from __future__ import annotations

import hashlib
import html
import json
import os
import grp
import re
import sqlite3
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

import settings
from runtime_authority import AuthorityError, assert_send_authorized
from send_shard import (
    GlobalBlockRefresher,
    PROFILES,
    norm_email,
    send_via_sendgrid,
)
from sendgrid_launch_auth import resolve_sendgrid_api_key


CONTROLLED_TEST_RECIPIENT = "astraprouctionsbyjc@gmail.com"
CONTROLLED_TEST_VERSION = "sendgrid-identity-validation-v1"
CONTROLLED_TEST_IDENTITIES = {
    "sendgrid_alison": "alisonaguiar@bnmarketing.info",
    "sendgrid_jodi": "jodihorowitz@bnmarketing.info",
    "sendgrid_jordan": "jordankendrick@bnmarketing.info",
}
CONTROLLED_TEST_LABELS = {
    "sendgrid_alison": "Alison",
    "sendgrid_jodi": "Jodi",
    "sendgrid_jordan": "Jordan",
}
CONTROLLED_TEST_STATE_PATH = settings.STATE_DIR / "controlled_sendgrid_self_test.sqlite3"
CONTROLLED_TEST_PROFILE_ENV_DIR = Path("/etc/astra-emailautomation/profiles")
_CONTROLLED_TEST_LOCK = threading.Lock()


class ControlledSendGridTestRefused(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_cloud_authority(authority: object) -> Mapping[str, object]:
    if not isinstance(authority, Mapping) or str(authority.get("status") or "") != "active" or str(
        authority.get("authorized_machine") or ""
    ) != "cloud":
        raise ControlledSendGridTestRefused(
            "authority_invalid",
            "Active Cloud runtime authority is required.",
        )
    return authority


def controlled_test_public_config() -> dict[str, object]:
    return {
        "recipient": CONTROLLED_TEST_RECIPIENT,
        "profiles": [
            {
                "profile": profile,
                "label": CONTROLLED_TEST_LABELS[profile],
                "from_email": from_email,
                "reply_to": from_email,
            }
            for profile, from_email in CONTROLLED_TEST_IDENTITIES.items()
        ],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _payload_fingerprint(profile: str, from_email: str) -> str:
    payload = {
        "version": CONTROLLED_TEST_VERSION,
        "profile": profile,
        "recipient": CONTROLLED_TEST_RECIPIENT,
        "from_email": from_email,
        "reply_to": from_email,
        "subject": "Astra controlled SendGrid identity validation",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_profile(profile: str, profiles: Mapping[str, Mapping[str, object]]) -> tuple[Mapping[str, object], str]:
    expected_from = CONTROLLED_TEST_IDENTITIES.get(profile)
    if not expected_from:
        raise ControlledSendGridTestRefused("sender_not_approved", "Selected sender is not approved for controlled testing.")
    config = profiles.get(profile)
    if not isinstance(config, Mapping):
        raise ControlledSendGridTestRefused("profile_missing", "Selected sender configuration is unavailable.")
    actual_from = norm_email(str(config.get("from_email") or ""))
    if str(config.get("provider") or "").strip().lower() != "sendgrid" or actual_from != expected_from:
        raise ControlledSendGridTestRefused(
            "sender_identity_mismatch",
            "Selected sender configuration does not match the approved controlled-test identity.",
        )
    if not bool(config.get("send_enabled", True)):
        raise ControlledSendGridTestRefused("sender_disabled", "Selected sender is not enabled for production sending.")
    return config, actual_from


def _profile_env_path(profile: str, profile_env_dir: Path) -> Path:
    path = Path(profile_env_dir) / f"{profile}.env"
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ControlledSendGridTestRefused("credential_unavailable", "Selected sender credential file is unavailable.") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ControlledSendGridTestRefused("credential_file_unsafe", "Selected sender credential must be a regular non-symlink file.")
    if os.environ.get("ASTRA_MACHINE_ID", "").strip().lower() == "cloud":
        try:
            astra_gid = grp.getgrnam("astra").gr_gid
        except KeyError as exc:
            raise ControlledSendGridTestRefused("credential_file_unsafe", "The astra credential group is unavailable.") from exc
        if metadata.st_uid != 0 or metadata.st_gid != astra_gid or stat.S_IMODE(metadata.st_mode) != 0o640:
            raise ControlledSendGridTestRefused(
                "credential_file_unsafe",
                "Selected sender credential file has unsafe production ownership or permissions.",
            )
    return path


def _read_profile_env(path: Path) -> dict[str, str]:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ControlledSendGridTestRefused("credential_file_unsafe", "Credential verification requires O_NOFOLLOW support.")
    before = path.lstat()
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ControlledSendGridTestRefused("credential_file_unsafe", "Selected sender credential changed while opening.")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    values: dict[str, str] = {}
    for raw_line in b"".join(chunks).decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        name, value = raw_line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def _resolve_profile_key(profile: str, profile_env_dir: Path) -> tuple[str, str, str]:
    path = _profile_env_path(profile, profile_env_dir)
    values = _read_profile_env(path)
    resolution = resolve_sendgrid_api_key(env={"SENDGRID_API_KEY": values.get("SENDGRID_API_KEY", "")}, env_files=[])
    if not resolution.ok:
        raise ControlledSendGridTestRefused("credential_invalid", "Selected sender credential is missing or invalid.")
    return resolution.key, path.name, str(values.get("ASTRA_EXPECTED_GIT_COMMIT") or "").strip()


def _authoritative_send_log_paths_read_only() -> list[Path]:
    paths: list[Path] = []
    for config in PROFILES.values():
        if str(config.get("provider") or "").strip().lower() != "sendgrid":
            continue
        for key in ("log", "domain_log"):
            name = Path(str(config.get(key) or "")).name
            if not name:
                continue
            path = settings.LOGS_DIR / name
            if path not in paths:
                paths.append(path)
    return paths


def _block_classification() -> str:
    refresher = GlobalBlockRefresher(
        unsubscribed_path=settings.UNSUBSCRIBED_PATH,
        suppressed_path=settings.SUPPRESSED_PATH,
        sendgrid_suppression_path=settings.SENDGRID_SUPPRESSIONS_PATH,
        sendgrid_events_path=settings.WEBHOOK_EVENTS_PATH,
        authoritative_log_paths=_authoritative_send_log_paths_read_only(),
        ledger_path=settings.LEAD_LEDGER_DB_PATH,
        include_sendgrid_sources=True,
    )
    try:
        return refresher.classification(CONTROLLED_TEST_RECIPIENT)
    except Exception as exc:
        raise ControlledSendGridTestRefused(
            "safety_sources_unavailable",
            "Controlled-test suppression and history safety sources could not be verified.",
        ) from exc


def _open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ControlledSendGridTestRefused("audit_state_unsafe", "Controlled-test audit state must be a regular non-symlink file.")
    connection = sqlite3.connect(path, timeout=5)
    os.chmod(path, 0o600)
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS controlled_sendgrid_tests (
            test_version TEXT NOT NULL,
            profile TEXT NOT NULL,
            recipient TEXT NOT NULL,
            from_email TEXT NOT NULL,
            reply_to TEXT NOT NULL,
            payload_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            reserved_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            provider_status TEXT NOT NULL DEFAULT '',
            provider_message_id TEXT NOT NULL DEFAULT '',
            error_code TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (test_version, profile)
        )
        """
    )
    return connection


def _reserve(path: Path, profile: str, from_email: str, fingerprint: str) -> str:
    now = _utc_now()
    with _open_state(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT status FROM controlled_sendgrid_tests WHERE test_version = ? AND profile = ?",
            (CONTROLLED_TEST_VERSION, profile),
        ).fetchone()
        if existing:
            raise ControlledSendGridTestRefused(
                "controlled_test_already_attempted",
                f"The {CONTROLLED_TEST_LABELS[profile]} controlled test was already reserved or attempted.",
            )
        connection.execute(
            """
            INSERT INTO controlled_sendgrid_tests (
                test_version, profile, recipient, from_email, reply_to,
                payload_fingerprint, status, reserved_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?, ?)
            """,
            (
                CONTROLLED_TEST_VERSION,
                profile,
                CONTROLLED_TEST_RECIPIENT,
                from_email,
                from_email,
                fingerprint,
                now,
                now,
            ),
        )
    return now


def _update_state(path: Path, profile: str, *, status: str, provider_status: str = "", message_id: str = "", error_code: str = "") -> None:
    with _open_state(path) as connection:
        connection.execute(
            """
            UPDATE controlled_sendgrid_tests
            SET status = ?, updated_at_utc = ?, provider_status = ?,
                provider_message_id = ?, error_code = ?
            WHERE test_version = ? AND profile = ?
            """,
            (status, _utc_now(), provider_status, message_id, error_code, CONTROLLED_TEST_VERSION, profile),
        )


def execute_controlled_sendgrid_test(
    profile: str,
    *,
    profile_env_dir: Path = CONTROLLED_TEST_PROFILE_ENV_DIR,
    state_path: Path = CONTROLLED_TEST_STATE_PATH,
    profiles: Mapping[str, Mapping[str, object]] = PROFILES,
    authority_check: Callable[[], object] = lambda: assert_send_authorized(settings.APP_ROOT),
    conflict_check: Callable[[], list[str]] = lambda: [],
    block_classification: Callable[[], str] = _block_classification,
    provider_send: Callable[..., dict[str, str]] = send_via_sendgrid,
) -> dict[str, object]:
    profile = str(profile or "").strip()
    config, from_email = _validate_profile(profile, profiles)
    if not _CONTROLLED_TEST_LOCK.acquire(blocking=False):
        raise ControlledSendGridTestRefused("controlled_test_active", "Another controlled send test is already running.")
    reserved = False
    try:
        conflicts = [str(item) for item in conflict_check() if str(item or "").strip()]
        if conflicts:
            raise ControlledSendGridTestRefused("runtime_conflict", "Controlled test blocked: " + "; ".join(conflicts))
        try:
            authority = _require_cloud_authority(authority_check())
        except AuthorityError as exc:
            raise ControlledSendGridTestRefused("authority_invalid", "Active Cloud runtime authority is required.") from exc
        classification = block_classification()
        if classification:
            raise ControlledSendGridTestRefused(
                "recipient_blocked",
                f"Controlled test recipient is blocked by {classification.replace('_', ' ')} safety state.",
            )
        api_key, credential_source, profile_expected_commit = _resolve_profile_key(profile, Path(profile_env_dir))
        if os.environ.get("ASTRA_MACHINE_ID", "").strip().lower() == "cloud":
            authority_commit = str(authority.get("expected_git_commit") or "") if isinstance(authority, Mapping) else ""
            if not re.fullmatch(r"[0-9a-f]{40}", profile_expected_commit) or profile_expected_commit != authority_commit:
                raise ControlledSendGridTestRefused(
                    "profile_commit_pin_mismatch",
                    "Selected sender protected expected-commit pin does not match active authority.",
                )
        fingerprint = _payload_fingerprint(profile, from_email)
        reserved_at = _reserve(Path(state_path), profile, from_email, fingerprint)
        reserved = True

        # Recheck all volatile safety gates immediately before the one provider call.
        conflicts = [str(item) for item in conflict_check() if str(item or "").strip()]
        if conflicts:
            raise ControlledSendGridTestRefused("runtime_conflict", "Controlled test blocked: " + "; ".join(conflicts))
        try:
            _require_cloud_authority(authority_check())
        except AuthorityError as exc:
            raise ControlledSendGridTestRefused("authority_invalid", "Active Cloud runtime authority is required.") from exc
        classification = block_classification()
        if classification:
            raise ControlledSendGridTestRefused(
                "recipient_blocked",
                f"Controlled test recipient is blocked by {classification.replace('_', ' ')} safety state.",
            )

        subject = "Astra controlled SendGrid identity validation"
        body = (
            f"This is the one controlled Astra SendGrid identity validation for {CONTROLLED_TEST_LABELS[profile]}.\n\n"
            "No production recipient queue was used."
        )
        result = provider_send(
            api_key,
            from_email,
            CONTROLLED_TEST_RECIPIENT,
            from_email,
            subject,
            body,
            f"<p>{html.escape(body).replace(chr(10), '<br>')}</p>",
            from_email,
            None,
            None,
            int(config.get("unsubscribe_group_id") or 0),
            [int(value) for value in (config.get("groups_to_display") or [])],
            custom_args={
                "astra_operation": CONTROLLED_TEST_VERSION,
                "astra_profile": profile,
                "astra_fingerprint": fingerprint,
            },
        )
        provider_status = str(result.get("status_code") or "")
        message_id = str(result.get("message_id") or "")
        _update_state(Path(state_path), profile, status="accepted", provider_status=provider_status, message_id=message_id)
        return {
            "ok": True,
            "status": "ACCEPTED",
            "profile": profile,
            "sender": CONTROLLED_TEST_LABELS[profile],
            "recipient": CONTROLLED_TEST_RECIPIENT,
            "from_email": from_email,
            "reply_to": from_email,
            "provider_status": provider_status,
            "provider_message_id": message_id,
            "submitted_at_utc": reserved_at,
            "credential_source": credential_source,
            "payload_fingerprint": fingerprint,
            "production_queue_used": False,
            "auto_started": False,
        }
    except ControlledSendGridTestRefused as exc:
        if reserved:
            _update_state(Path(state_path), profile, status="refused_after_reservation", error_code=exc.code)
        raise
    except Exception as exc:
        if reserved:
            _update_state(Path(state_path), profile, status="provider_attempt_ambiguous", error_code=type(exc).__name__)
        raise ControlledSendGridTestRefused(
            "provider_submission_failed",
            "Controlled SendGrid submission failed or returned an ambiguous outcome; it will not be retried.",
        ) from exc
    finally:
        _CONTROLLED_TEST_LOCK.release()
