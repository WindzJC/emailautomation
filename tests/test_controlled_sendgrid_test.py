from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path

import pytest

import controlled_sendgrid_test as controlled
from runtime_authority import AuthorityError


APPROVED = {
    "sendgrid_alison": ("Alison", "alisonaguiar@bnmarketing.info", "SG.alison.secret"),
    "sendgrid_jodi": ("Jodi", "jodihorowitz@bnmarketing.info", "SG.jodi.secret"),
    "sendgrid_jordan": ("Jordan", "jordankendrick@bnmarketing.info", "SG.jordan.secret"),
}
PREVIOUS_TEST_VERSION = "sendgrid-identity-validation-v1"


def _profiles() -> dict[str, dict[str, object]]:
    profiles = {
        profile: {
            "provider": "sendgrid",
            "from_email": from_email,
            "send_enabled": True,
            "csv": f"production-{profile}.csv",
            "unsubscribe_group_id": 363425,
            "groups_to_display": [363425],
        }
        for profile, (_label, from_email, _key) in APPROVED.items()
    }
    profiles.update(
        {
            "sendgrid_annette": {"provider": "sendgrid", "from_email": "annette@bnmarketing.info", "send_enabled": False},
            "sendgrid_fiorela": {"provider": "sendgrid", "from_email": "fiorela@bnmarketing.info", "send_enabled": False},
            "sendgrid_controlled_test": {"provider": "sendgrid", "from_email": "legacy@example.test", "send_enabled": False},
        }
    )
    return profiles


def _env_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "profiles"
    directory.mkdir()
    for profile, (_label, _from_email, key) in APPROVED.items():
        path = directory / f"{profile}.env"
        path.write_text(f"SENDGRID_API_KEY={key}\n", encoding="utf-8")
        path.chmod(0o640)
    return directory


def _execute(tmp_path: Path, profile: str, provider_send, **kwargs):
    return controlled.execute_controlled_sendgrid_test(
        profile,
        profile_env_dir=_env_dir(tmp_path),
        state_path=tmp_path / "controlled.sqlite3",
        profiles=_profiles(),
        authority_check=lambda: {"status": "active", "authorized_machine": "cloud"},
        conflict_check=lambda: [],
        block_classification=lambda: "",
        provider_send=provider_send,
        **kwargs,
    )


@pytest.mark.parametrize("profile", list(APPROVED))
def test_each_approved_identity_uses_exact_profile_credential_and_envelope(tmp_path: Path, profile: str) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def provider(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status_code": "202", "message_id": f"id-{profile}"}

    result = _execute(tmp_path, profile, provider)
    label, from_email, key = APPROVED[profile]
    assert controlled.CONTROLLED_TEST_RECIPIENT == "astraproductionsbyjc@gmail.com"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == key
    assert args[1:4] == (from_email, controlled.CONTROLLED_TEST_RECIPIENT, from_email)
    assert kwargs["custom_args"]["astra_profile"] == profile
    assert result["sender"] == label
    assert result["recipient"] == controlled.CONTROLLED_TEST_RECIPIENT
    assert result["from_email"] == result["reply_to"] == from_email
    assert result["production_queue_used"] is False
    assert result["auto_started"] is False
    assert key not in repr(result)


@pytest.mark.parametrize(
    "profile",
    ["sendgrid_annette", "sendgrid_fiorela", "sendgrid_controlled_test", "private_jc", "", "sendgrid_unknown"],
)
def test_unapproved_identity_is_refused_before_provider(tmp_path: Path, profile: str) -> None:
    calls: list[object] = []
    with pytest.raises(controlled.ControlledSendGridTestRefused, match="not approved") as refusal:
        _execute(tmp_path, profile, lambda *args, **kwargs: calls.append(args))
    assert refusal.value.code == "sender_not_approved"
    assert calls == []


def test_client_cannot_supply_recipient_or_from_values() -> None:
    public = controlled.controlled_test_public_config()
    assert public["recipient"] == "astraproductionsbyjc@gmail.com"
    assert set(controlled.CONTROLLED_TEST_IDENTITIES) == set(APPROVED)
    assert all(set(row) == {"profile", "label", "from_email", "reply_to"} for row in public["profiles"])


def test_corrected_recipient_version_preserves_historical_alison_and_allows_one_new_attempt(tmp_path: Path) -> None:
    assert controlled.CONTROLLED_TEST_VERSION == "sendgrid-identity-validation-corrected-recipient-v2"
    assert controlled.CONTROLLED_TEST_VERSION != PREVIOUS_TEST_VERSION

    state = tmp_path / "controlled.sqlite3"
    with controlled._open_state(state) as connection:
        connection.execute(
            """
            INSERT INTO controlled_sendgrid_tests (
                test_version, profile, recipient, from_email, reply_to,
                payload_fingerprint, status, reserved_at_utc, updated_at_utc,
                provider_status, provider_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                PREVIOUS_TEST_VERSION,
                "sendgrid_alison",
                "astraprouctionsbyjc@gmail.com",
                "alisonaguiar@bnmarketing.info",
                "alisonaguiar@bnmarketing.info",
                "historical-v1-fingerprint",
                "accepted",
                "2026-08-29T00:00:00Z",
                "2026-08-29T00:00:00Z",
                "202",
                "o-iUyYNQQmiEtqEVpStyhg",
            ),
        )

    calls: list[tuple[object, ...]] = []
    env_dir = _env_dir(tmp_path)

    def execute_alison() -> dict[str, object]:
        return controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison",
            profile_env_dir=env_dir,
            state_path=state,
            profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"},
            conflict_check=lambda: [],
            block_classification=lambda: "",
            provider_send=lambda *args, **kwargs: calls.append(args) or {"status_code": "202", "message_id": "corrected-v2"},
        )

    result = execute_alison()
    assert result["recipient"] == "astraproductionsbyjc@gmail.com"
    assert len(calls) == 1

    with sqlite3.connect(state) as connection:
        rows = connection.execute(
            """
            SELECT test_version, recipient, status, provider_message_id
            FROM controlled_sendgrid_tests
            WHERE profile = 'sendgrid_alison'
            ORDER BY reserved_at_utc
            """
        ).fetchall()
    assert rows == [
        (
            PREVIOUS_TEST_VERSION,
            "astraprouctionsbyjc@gmail.com",
            "accepted",
            "o-iUyYNQQmiEtqEVpStyhg",
        ),
        (
            controlled.CONTROLLED_TEST_VERSION,
            "astraproductionsbyjc@gmail.com",
            "accepted",
            "corrected-v2",
        ),
    ]

    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        execute_alison()
    assert refusal.value.code == "controlled_test_already_attempted"
    assert len(calls) == 1


def test_same_sender_is_reserved_once_and_never_resubmitted(tmp_path: Path) -> None:
    calls: list[object] = []

    def provider(*args, **kwargs):
        calls.append(args)
        return {"status_code": "202", "message_id": "first"}

    _execute(tmp_path, "sendgrid_alison", provider)
    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison",
            profile_env_dir=tmp_path / "profiles",
            state_path=tmp_path / "controlled.sqlite3",
            profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"},
            conflict_check=lambda: [],
            block_classification=lambda: "",
            provider_send=provider,
        )
    assert refusal.value.code == "controlled_test_already_attempted"
    assert len(calls) == 1


def test_three_sender_tests_have_independent_idempotency_keys(tmp_path: Path) -> None:
    env_dir = _env_dir(tmp_path)
    calls: list[str] = []
    state = tmp_path / "controlled.sqlite3"
    for profile in APPROVED:
        controlled.execute_controlled_sendgrid_test(
            profile,
            profile_env_dir=env_dir,
            state_path=state,
            profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"},
            conflict_check=lambda: [],
            block_classification=lambda: "",
            provider_send=lambda *args, profile=profile, **kwargs: calls.append(profile) or {"status_code": "202", "message_id": profile},
        )
    assert calls == list(APPROVED)
    with sqlite3.connect(state) as connection:
        rows = connection.execute(
            "SELECT test_version, profile, status FROM controlled_sendgrid_tests ORDER BY profile"
        ).fetchall()
    assert rows == sorted(
        (controlled.CONTROLLED_TEST_VERSION, profile, "accepted") for profile in APPROVED
    )


@pytest.mark.parametrize("classification", ["unsubscribed", "global_suppression", "sendgrid_suppression", "bad_outcome", "ledger_blocked"])
def test_suppression_and_bad_history_are_fail_closed(tmp_path: Path, classification: str) -> None:
    calls: list[object] = []
    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison",
            profile_env_dir=_env_dir(tmp_path),
            state_path=tmp_path / "controlled.sqlite3",
            profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"},
            conflict_check=lambda: [],
            block_classification=lambda: classification,
            provider_send=lambda *args, **kwargs: calls.append(args),
        )
    assert refusal.value.code == "recipient_blocked"
    assert calls == []


def test_missing_authority_is_refused_before_provider(tmp_path: Path) -> None:
    calls: list[object] = []

    def refuse_authority():
        raise AuthorityError("synthetic refusal")

    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison",
            profile_env_dir=_env_dir(tmp_path),
            state_path=tmp_path / "controlled.sqlite3",
            profiles=_profiles(),
            authority_check=refuse_authority,
            conflict_check=lambda: [],
            block_classification=lambda: "",
            provider_send=lambda *args, **kwargs: calls.append(args),
        )
    assert refusal.value.code == "authority_invalid"
    assert calls == []


def test_active_non_cloud_authority_is_refused_before_provider(tmp_path: Path) -> None:
    calls: list[object] = []
    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison",
            profile_env_dir=_env_dir(tmp_path),
            state_path=tmp_path / "controlled.sqlite3",
            profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "mac"},
            conflict_check=lambda: [],
            block_classification=lambda: "",
            provider_send=lambda *args, **kwargs: calls.append(args),
        )
    assert refusal.value.code == "authority_invalid"
    assert calls == []


def test_active_runtime_conflict_is_refused_before_provider(tmp_path: Path) -> None:
    calls: list[object] = []
    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison",
            profile_env_dir=_env_dir(tmp_path),
            state_path=tmp_path / "controlled.sqlite3",
            profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"},
            conflict_check=lambda: ["active sender(s): private_jc"],
            block_classification=lambda: "",
            provider_send=lambda *args, **kwargs: calls.append(args),
        )
    assert refusal.value.code == "runtime_conflict"
    assert calls == []


def test_concurrent_duplicate_is_refused_while_first_provider_call_is_pending(tmp_path: Path) -> None:
    entered = threading.Event()
    release = threading.Event()
    first_error: list[BaseException] = []
    env_dir = _env_dir(tmp_path)
    state = tmp_path / "controlled.sqlite3"

    def provider(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return {"status_code": "202", "message_id": "one"}

    def first():
        try:
            controlled.execute_controlled_sendgrid_test(
                "sendgrid_alison", profile_env_dir=env_dir, state_path=state, profiles=_profiles(),
                authority_check=lambda: {"status": "active", "authorized_machine": "cloud"}, conflict_check=lambda: [], block_classification=lambda: "", provider_send=provider,
            )
        except BaseException as exc:  # pragma: no cover - assertion aid
            first_error.append(exc)

    thread = threading.Thread(target=first)
    thread.start()
    assert entered.wait(5)
    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison", profile_env_dir=env_dir, state_path=state, profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"}, conflict_check=lambda: [], block_classification=lambda: "", provider_send=provider,
        )
    assert refusal.value.code == "controlled_test_active"
    release.set()
    thread.join(5)
    assert first_error == []


def test_provider_failure_is_audited_ambiguous_and_never_retried(tmp_path: Path) -> None:
    calls = 0

    def provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic provider failure")

    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        _execute(tmp_path, "sendgrid_jodi", provider)
    assert refusal.value.code == "provider_submission_failed"
    assert calls == 1
    with sqlite3.connect(tmp_path / "controlled.sqlite3") as connection:
        status, error_code = connection.execute(
            "SELECT status, error_code FROM controlled_sendgrid_tests WHERE profile = 'sendgrid_jodi'"
        ).fetchone()
    assert status == "provider_attempt_ambiguous"
    assert error_code == "RuntimeError"


def test_production_queue_files_remain_byte_identical(tmp_path: Path) -> None:
    queues = []
    for index in range(2, 5):
        path = tmp_path / f"recipients_sendgrid_{index}.csv"
        path.write_bytes(f"Email,FirstName\nrecipient-{index}@example.test,Test\n".encode())
        queues.append(path)
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in queues}
    _execute(tmp_path, "sendgrid_jordan", lambda *args, **kwargs: {"status_code": "202", "message_id": "safe"})
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in queues}
    assert after == before


def test_profile_env_must_be_regular_non_symlink(tmp_path: Path) -> None:
    env_dir = tmp_path / "profiles"
    env_dir.mkdir()
    target = tmp_path / "real.env"
    target.write_text("SENDGRID_API_KEY=SG.real.secret\n", encoding="utf-8")
    (env_dir / "sendgrid_alison.env").symlink_to(target)
    with pytest.raises(controlled.ControlledSendGridTestRefused) as refusal:
        controlled.execute_controlled_sendgrid_test(
            "sendgrid_alison", profile_env_dir=env_dir, state_path=tmp_path / "state.sqlite3", profiles=_profiles(),
            authority_check=lambda: {"status": "active", "authorized_machine": "cloud"}, conflict_check=lambda: [], block_classification=lambda: "", provider_send=lambda *a, **k: {},
        )
    assert refusal.value.code == "credential_file_unsafe"
