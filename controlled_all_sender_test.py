from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

import settings
from protected_profile_env import (
    ProtectedProfileEnvError,
    read_protected_profile_env,
    resolve_protected_profile_credential,
)
from runtime_authority import AuthorityError, assert_send_authorized
from send_shard import (
    GlobalBlockRefresher,
    PROFILES,
    REPLY_UNSUBSCRIBE_FOOTER,
    SIGNATURE_BY_FROM,
    SIGNATURE_CID,
    SMTP_PRESETS,
    build_message,
    norm_email,
    render_message_parts,
    send_via_sendgrid,
    smtp_close,
    smtp_login,
)
from sendgrid_launch_auth import resolve_sendgrid_api_key


CONTROLLED_ALL_RECIPIENT = "astraproductionsbyjc+allsendersv1@gmail.com"
CONTROLLED_ALL_VERSION = "all-sender-identity-validation-v1"

CONTROLLED_ALL_IDENTITIES: dict[str, dict[str, str]] = {
    "private_jc": {
        "label": "JC",
        "provider": "private",
        "from_email": "jc@astraproductions.co",
        "signature": "LOGO ASTRA bg.png",
    },
    "sendgrid_annette": {
        "label": "Annette",
        "provider": "sendgrid",
        "from_email": "annettedanek-akey@bnmarketing.info",
        "signature": "sig_sendgrid_annette_bnmarketing.png",
    },
    "sendgrid_jordan": {
        "label": "Jordan",
        "provider": "sendgrid",
        "from_email": "jordankendrick@bnmarketing.info",
        "signature": "sig_sendgrid_jordan_bnmarketing.png",
    },
    "sendgrid_jodi": {
        "label": "Jodi",
        "provider": "sendgrid",
        "from_email": "jodihorowitz@bnmarketing.info",
        "signature": "sig_sendgrid_jodi_bnmarketing.png",
    },
    "sendgrid_alison": {
        "label": "Alison",
        "provider": "sendgrid",
        "from_email": "alisonaguiar@bnmarketing.info",
        "signature": "sig_sendgrid_alison_bnmarketing.png",
    },
    "sendgrid_fiorela": {
        "label": "Fiorela",
        "provider": "sendgrid",
        "from_email": "fiorelladelima@bnmarketing.info",
        "signature": "sig_sendgrid_fiorela_bnmarketing.png",
    },
}

CONTROLLED_ALL_STATE_PATH = (
    settings.STATE_DIR / "controlled_all_sender_self_test.sqlite3"
)
CONTROLLED_ALL_PROFILE_ENV_DIR = Path("/etc/astra-emailautomation/profiles")

_CONTROLLED_SINGLE_LOCK = threading.Lock()
_CONTROLLED_BATCH_LOCK = threading.Lock()


class ControlledAllSenderTestRefused(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _require_windows_wsl_authority(authority: object) -> Mapping[str, object]:
    machine = str(os.environ.get("ASTRA_MACHINE_ID") or "").strip().lower()

    if (
        machine != "windows-wsl"
        or not isinstance(authority, Mapping)
        or str(authority.get("status") or "").strip().lower() != "active"
        or str(authority.get("authorized_machine") or "").strip().lower()
        != "windows-wsl"
    ):
        raise ControlledAllSenderTestRefused(
            "authority_invalid",
            "Active Windows/WSL runtime authority is required.",
        )

    return authority


def controlled_all_sender_public_config() -> dict[str, object]:
    return {
        "recipient": CONTROLLED_ALL_RECIPIENT,
        "version": CONTROLLED_ALL_VERSION,
        "maximum_messages": 6,
        "profiles": [
            {
                "profile": profile,
                "label": spec["label"],
                "provider": spec["provider"],
                "from_email": spec["from_email"],
                "reply_to": spec["from_email"],
            }
            for profile, spec in CONTROLLED_ALL_IDENTITIES.items()
        ],
    }


def _payload_fingerprint(
    profile: str,
    provider: str,
    from_email: str,
) -> str:
    payload = {
        "version": CONTROLLED_ALL_VERSION,
        "profile": profile,
        "provider": provider,
        "recipient": CONTROLLED_ALL_RECIPIENT,
        "from_email": from_email,
        "reply_to": from_email,
        "subject": "Astra controlled all-sender identity validation",
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _validate_profile(
    profile: str,
    profiles: Mapping[str, Mapping[str, object]],
) -> tuple[Mapping[str, object], Mapping[str, str], str]:
    spec = CONTROLLED_ALL_IDENTITIES.get(profile)

    if not isinstance(spec, Mapping):
        raise ControlledAllSenderTestRefused(
            "sender_not_approved",
            "Selected sender is not approved for the all-sender controlled test.",
        )

    config = profiles.get(profile)

    if not isinstance(config, Mapping):
        raise ControlledAllSenderTestRefused(
            "profile_missing",
            "Selected sender configuration is unavailable.",
        )

    expected_provider = str(spec["provider"])
    expected_from = norm_email(str(spec["from_email"]))

    actual_provider = str(config.get("provider") or "").strip().lower()
    actual_from = norm_email(str(config.get("from_email") or ""))

    if (
        actual_provider != expected_provider
        or actual_from != expected_from
    ):
        raise ControlledAllSenderTestRefused(
            "sender_identity_mismatch",
            "Selected sender configuration does not match the locked "
            "controlled-test identity.",
        )

    if not bool(config.get("send_enabled", True)):
        raise ControlledAllSenderTestRefused(
            "sender_disabled",
            "Selected sender is not enabled for production sending.",
        )

    return config, spec, actual_from


def _resolve_signature(
    profile: str,
    spec: Mapping[str, str],
    from_email: str,
) -> Path:
    expected_name = str(spec.get("signature") or "").strip()
    configured_name = str(SIGNATURE_BY_FROM.get(from_email) or "").strip()

    if not expected_name or configured_name != expected_name:
        raise ControlledAllSenderTestRefused(
            "signature_identity_mismatch",
            f"{profile} signature does not match the locked sender identity.",
        )

    path = settings.app_path(configured_name)

    try:
        path.resolve().relative_to(settings.APP_ROOT.resolve())
        metadata = path.lstat()

        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
        ):
            raise OSError("signature is not a regular file")

        signature_bytes = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise ControlledAllSenderTestRefused(
            "signature_unavailable",
            f"{profile} signature is unavailable or unreadable.",
        ) from exc

    if not signature_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ControlledAllSenderTestRefused(
            "signature_invalid",
            f"{profile} signature is not a valid PNG asset.",
        )

    return path


def _resolve_sendgrid_key(
    profile: str,
    profile_env_dir: Path,
) -> tuple[str, str]:
    try:
        values, source = read_protected_profile_env(profile, profile_env_dir)
    except ProtectedProfileEnvError as exc:
        raise ControlledAllSenderTestRefused(exc.code, str(exc)) from exc

    resolution = resolve_sendgrid_api_key(
        env={"SENDGRID_API_KEY": values.get("SENDGRID_API_KEY", "")},
        env_files=[],
    )

    if not resolution.ok:
        raise ControlledAllSenderTestRefused(
            "credential_invalid",
            f"{profile} SendGrid credential is missing or invalid.",
        )

    return resolution.key, source


def _resolve_private_password(
    profile: str,
    config: Mapping[str, object],
    profile_env_dir: Path,
) -> tuple[str, str]:
    password_env = str(config.get("password_env") or "").strip()
    try:
        return resolve_protected_profile_credential(
            profile,
            password_env,
            "PRIVATE_JC_PASSWORD",
            profile_env_dir=profile_env_dir,
        )
    except ProtectedProfileEnvError as exc:
        raise ControlledAllSenderTestRefused(exc.code, str(exc)) from exc


def _authoritative_log_paths_read_only() -> list[Path]:
    paths: list[Path] = []

    for profile, config in PROFILES.items():
        if profile == "sendgrid_controlled_test":
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
        authoritative_log_paths=_authoritative_log_paths_read_only(),
        ledger_path=settings.LEAD_LEDGER_DB_PATH,
        include_sendgrid_sources=True,
    )

    try:
        return refresher.classification(CONTROLLED_ALL_RECIPIENT)
    except Exception as exc:
        raise ControlledAllSenderTestRefused(
            "safety_sources_unavailable",
            "Controlled-test suppression safety sources could not be verified.",
        ) from exc


def _open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        metadata = path.lstat()

        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(
            metadata.st_mode
        ):
            raise ControlledAllSenderTestRefused(
                "audit_state_unsafe",
                "All-sender controlled-test audit state must be a regular "
                "non-symlink file.",
            )

    connection = sqlite3.connect(path, timeout=5)
    os.chmod(path, 0o600)
    connection.execute("PRAGMA busy_timeout = 5000")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS controlled_all_sender_tests (
            test_version TEXT NOT NULL,
            profile TEXT NOT NULL,
            provider TEXT NOT NULL,
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


def _reserve(
    path: Path,
    profile: str,
    provider: str,
    from_email: str,
    fingerprint: str,
) -> str:
    now = _utc_now()

    with _open_state(path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT status
            FROM controlled_all_sender_tests
            WHERE test_version = ? AND profile = ?
            """,
            (CONTROLLED_ALL_VERSION, profile),
        ).fetchone()

        if existing:
            raise ControlledAllSenderTestRefused(
                "controlled_test_already_attempted",
                f"The {CONTROLLED_ALL_IDENTITIES[profile]['label']} "
                "controlled test was already reserved or attempted.",
            )

        connection.execute(
            """
            INSERT INTO controlled_all_sender_tests (
                test_version,
                profile,
                provider,
                recipient,
                from_email,
                reply_to,
                payload_fingerprint,
                status,
                reserved_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?)
            """,
            (
                CONTROLLED_ALL_VERSION,
                profile,
                provider,
                CONTROLLED_ALL_RECIPIENT,
                from_email,
                from_email,
                fingerprint,
                now,
                now,
            ),
        )

    return now


def _update_state(
    path: Path,
    profile: str,
    *,
    status: str,
    provider_status: str = "",
    message_id: str = "",
    error_code: str = "",
) -> None:
    with _open_state(path) as connection:
        connection.execute(
            """
            UPDATE controlled_all_sender_tests
            SET
                status = ?,
                updated_at_utc = ?,
                provider_status = ?,
                provider_message_id = ?,
                error_code = ?
            WHERE test_version = ? AND profile = ?
            """,
            (
                status,
                _utc_now(),
                provider_status,
                message_id,
                error_code,
                CONTROLLED_ALL_VERSION,
                profile,
            ),
        )


def _send_via_private_smtp(
    password: str,
    from_email: str,
    to_email: str,
    message: object,
) -> dict[str, str]:
    host, port = SMTP_PRESETS["private"]
    smtp = None

    try:
        smtp = smtp_login(host, int(port), from_email, password)
        smtp.send_message(message)
    finally:
        smtp_close(smtp)

    return {
        "status_code": "SMTP_ACCEPTED",
        "message_id": str(
            getattr(message, "get", lambda *_: "")("Message-ID") or ""
        ).strip(),
    }


def execute_controlled_sender_test(
    profile: str,
    *,
    profile_env_dir: Path = CONTROLLED_ALL_PROFILE_ENV_DIR,
    state_path: Path = CONTROLLED_ALL_STATE_PATH,
    profiles: Mapping[str, Mapping[str, object]] = PROFILES,
    authority_check: Callable[[], object] = lambda: assert_send_authorized(
        settings.APP_ROOT
    ),
    conflict_check: Callable[[], list[str]] = lambda: [],
    block_classification: Callable[[], str] = _block_classification,
    sendgrid_provider_send: Callable[..., dict[str, str]] = send_via_sendgrid,
    private_provider_send: Callable[..., dict[str, str]] = (
        _send_via_private_smtp
    ),
) -> dict[str, object]:
    profile = str(profile or "").strip()

    config, spec, from_email = _validate_profile(profile, profiles)
    provider = str(spec["provider"])

    if not _CONTROLLED_SINGLE_LOCK.acquire(blocking=False):
        raise ControlledAllSenderTestRefused(
            "controlled_test_active",
            "Another all-sender controlled test submission is active.",
        )

    reserved = False

    try:
        conflicts = [
            str(item)
            for item in conflict_check()
            if str(item or "").strip()
        ]

        if conflicts:
            raise ControlledAllSenderTestRefused(
                "runtime_conflict",
                "Controlled test blocked: " + "; ".join(conflicts),
            )

        try:
            _require_windows_wsl_authority(authority_check())
        except AuthorityError as exc:
            raise ControlledAllSenderTestRefused(
                "authority_invalid",
                "Active Windows/WSL runtime authority is required.",
            ) from exc

        classification = block_classification()

        if classification:
            raise ControlledAllSenderTestRefused(
                "recipient_blocked",
                "Controlled test recipient is blocked by "
                f"{classification.replace('_', ' ')} safety state.",
            )

        signature_file = _resolve_signature(
            profile,
            spec,
            from_email,
        )

        credential_source = ""
        api_key = ""
        password = ""

        if provider == "sendgrid":
            api_key, credential_source = _resolve_sendgrid_key(
                profile,
                Path(profile_env_dir),
            )
        elif provider == "private":
            password, credential_source = _resolve_private_password(
                profile,
                config,
                Path(profile_env_dir),
            )
        else:
            raise ControlledAllSenderTestRefused(
                "provider_invalid",
                "Controlled-test provider is not approved.",
            )

        fingerprint = _payload_fingerprint(
            profile,
            provider,
            from_email,
        )

        reserved_at = _reserve(
            Path(state_path),
            profile,
            provider,
            from_email,
            fingerprint,
        )
        reserved = True

        conflicts = [
            str(item)
            for item in conflict_check()
            if str(item or "").strip()
        ]

        if conflicts:
            raise ControlledAllSenderTestRefused(
                "runtime_conflict",
                "Controlled test blocked: " + "; ".join(conflicts),
            )

        try:
            _require_windows_wsl_authority(authority_check())
        except AuthorityError as exc:
            raise ControlledAllSenderTestRefused(
                "authority_invalid",
                "Active Windows/WSL runtime authority is required.",
            ) from exc

        classification = block_classification()

        if classification:
            raise ControlledAllSenderTestRefused(
                "recipient_blocked",
                "Controlled test recipient is blocked by "
                f"{classification.replace('_', ' ')} safety state.",
            )

        provider_label = (
            "PrivateEmail SMTP"
            if provider == "private"
            else "SendGrid"
        )

        subject = (
            f"Astra controlled sender validation — "
            f"{CONTROLLED_ALL_IDENTITIES[profile]['label']}"
        )

        body = (
            "This is one controlled Astra sender identity validation.\n\n"
            f"Sender: {CONTROLLED_ALL_IDENTITIES[profile]['label']}\n"
            f"Transport: {provider_label}\n\n"
            "No production recipient queue was read or modified.\n\n"
            "{SIGIMG}\n\n"
            f"{REPLY_UNSUBSCRIBE_FOOTER}"
        )

        if provider == "sendgrid":
            subject_text, body_text, html_body, cid = (
                render_message_parts(
                    "",
                    "",
                    subject,
                    body,
                    from_email,
                    signature_file,
                )
            )

            if (
                cid != SIGNATURE_CID
                or f"cid:{SIGNATURE_CID}" not in html_body
            ):
                raise ControlledAllSenderTestRefused(
                    "signature_render_failed",
                    "Sender signature could not be embedded in the "
                    "controlled-test message.",
                )

            result = sendgrid_provider_send(
                api_key,
                from_email,
                CONTROLLED_ALL_RECIPIENT,
                from_email,
                subject_text,
                body_text,
                html_body,
                from_email,
                signature_file,
                cid,
                int(config.get("unsubscribe_group_id") or 0),
                [
                    int(value)
                    for value in (
                        config.get("groups_to_display") or []
                    )
                ],
                custom_args={
                    "astra_operation": CONTROLLED_ALL_VERSION,
                    "astra_profile": profile,
                    "astra_fingerprint": fingerprint,
                },
            )
        else:
            message, _, _, html_body, cid = build_message(
                from_email,
                CONTROLLED_ALL_RECIPIENT,
                "",
                "",
                subject,
                body,
                from_email,
                signature_file,
            )

            if (
                cid != SIGNATURE_CID
                or f"cid:{SIGNATURE_CID}" not in html_body
            ):
                raise ControlledAllSenderTestRefused(
                    "signature_render_failed",
                    "JC signature could not be embedded in the "
                    "controlled-test message.",
                )

            result = private_provider_send(
                password,
                from_email,
                CONTROLLED_ALL_RECIPIENT,
                message,
            )

        provider_status = str(
            result.get("status_code") or ""
        )
        message_id = str(
            result.get("message_id") or ""
        )

        _update_state(
            Path(state_path),
            profile,
            status="accepted",
            provider_status=provider_status,
            message_id=message_id,
        )

        return {
            "ok": True,
            "status": "ACCEPTED",
            "profile": profile,
            "sender": CONTROLLED_ALL_IDENTITIES[profile]["label"],
            "provider": provider,
            "recipient": CONTROLLED_ALL_RECIPIENT,
            "from_email": from_email,
            "reply_to": from_email,
            "provider_status": provider_status,
            "provider_message_id": message_id,
            "submitted_at_utc": reserved_at,
            "credential_source": credential_source,
            "payload_fingerprint": fingerprint,
            "production_queue_used": False,
            "production_queue_written": False,
            "auto_started": False,
        }

    except ControlledAllSenderTestRefused as exc:
        if reserved:
            _update_state(
                Path(state_path),
                profile,
                status="refused_after_reservation",
                error_code=exc.code,
            )
        raise

    except Exception as exc:
        if reserved:
            _update_state(
                Path(state_path),
                profile,
                status="provider_attempt_ambiguous",
                error_code=type(exc).__name__,
            )

        raise ControlledAllSenderTestRefused(
            "provider_submission_failed",
            "Controlled sender submission failed or returned an ambiguous "
            "outcome; it will not be retried.",
        ) from exc

    finally:
        _CONTROLLED_SINGLE_LOCK.release()


def execute_controlled_all_sender_test(
    *,
    authority_check: Callable[[], object] = lambda: assert_send_authorized(
        settings.APP_ROOT
    ),
    conflict_check: Callable[[], list[str]] = lambda: [],
    block_classification: Callable[[], str] = _block_classification,
) -> dict[str, object]:
    if len(CONTROLLED_ALL_IDENTITIES) != 6:
        raise ControlledAllSenderTestRefused(
            "sender_count_invalid",
            "All-sender controlled test is hard-locked to six identities.",
        )

    if not _CONTROLLED_BATCH_LOCK.acquire(blocking=False):
        raise ControlledAllSenderTestRefused(
            "controlled_test_active",
            "An all-sender controlled test is already active.",
        )

    try:
        conflicts = [
            str(item)
            for item in conflict_check()
            if str(item or "").strip()
        ]

        if conflicts:
            raise ControlledAllSenderTestRefused(
                "runtime_conflict",
                "Controlled test blocked: " + "; ".join(conflicts),
            )

        try:
            _require_windows_wsl_authority(authority_check())
        except AuthorityError as exc:
            raise ControlledAllSenderTestRefused(
                "authority_invalid",
                "Active Windows/WSL runtime authority is required.",
            ) from exc

        classification = block_classification()

        if classification:
            raise ControlledAllSenderTestRefused(
                "recipient_blocked",
                "Controlled test recipient is blocked by "
                f"{classification.replace('_', ' ')} safety state.",
            )

        results: list[dict[str, object]] = []

        for profile in CONTROLLED_ALL_IDENTITIES:
            try:
                result = execute_controlled_sender_test(
                    profile,
                    authority_check=authority_check,
                    conflict_check=conflict_check,
                    block_classification=block_classification,
                )
                results.append(result)

            except ControlledAllSenderTestRefused as exc:
                results.append(
                    {
                        "ok": False,
                        "status": "FAILED",
                        "profile": profile,
                        "sender": CONTROLLED_ALL_IDENTITIES[
                            profile
                        ]["label"],
                        "provider": CONTROLLED_ALL_IDENTITIES[
                            profile
                        ]["provider"],
                        "recipient": CONTROLLED_ALL_RECIPIENT,
                        "error": exc.code,
                        "message": str(exc),
                        "production_queue_used": False,
                        "production_queue_written": False,
                        "auto_started": False,
                    }
                )

        accepted = sum(
            1 for result in results if result.get("ok") is True
        )
        failed = len(results) - accepted

        return {
            "ok": True,
            "all_passed": failed == 0,
            "status": "PASS" if failed == 0 else "PARTIAL_FAILURE",
            "recipient": CONTROLLED_ALL_RECIPIENT,
            "maximum_messages": 6,
            "attempted_profiles": len(results),
            "accepted": accepted,
            "failed": failed,
            "results": results,
            "production_queue_used": False,
            "production_queue_written": False,
            "auto_started": False,
        }

    finally:
        _CONTROLLED_BATCH_LOCK.release()
