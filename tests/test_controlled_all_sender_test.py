from __future__ import annotations

import inspect
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import controlled_all_sender_test as controlled


EXPECTED = [
    ("private_jc", "JC", "private", "jc@astraproductions.co"),
    (
        "sendgrid_annette",
        "Annette",
        "sendgrid",
        "annettedanek-akey@bnmarketing.info",
    ),
    (
        "sendgrid_jordan",
        "Jordan",
        "sendgrid",
        "jordankendrick@bnmarketing.info",
    ),
    (
        "sendgrid_jodi",
        "Jodi",
        "sendgrid",
        "jodihorowitz@bnmarketing.info",
    ),
    (
        "sendgrid_alison",
        "Alison",
        "sendgrid",
        "alisonaguiar@bnmarketing.info",
    ),
    (
        "sendgrid_fiorela",
        "Fiorela",
        "sendgrid",
        "fiorelladelima@bnmarketing.info",
    ),
]


def test_public_config_is_exactly_six_locked_identities():
    public = controlled.controlled_all_sender_public_config()

    assert public["maximum_messages"] == 6
    assert public["recipient"] == (
        "astraproductionsbyjc+allsendersv1@gmail.com"
    )

    actual = [
        (
            item["profile"],
            item["label"],
            item["provider"],
            item["from_email"],
        )
        for item in public["profiles"]
    ]

    assert actual == EXPECTED


def test_authority_is_windows_wsl_only():
    authority = {
        "status": "active",
        "authorized_machine": "windows-wsl",
    }

    with patch.dict(
        os.environ,
        {"ASTRA_MACHINE_ID": "windows-wsl"},
        clear=False,
    ):
        assert (
            controlled._require_windows_wsl_authority(authority)
            is authority
        )

    with patch.dict(
        os.environ,
        {"ASTRA_MACHINE_ID": "cloud"},
        clear=False,
    ):
        with pytest.raises(
            controlled.ControlledAllSenderTestRefused
        ) as refusal:
            controlled._require_windows_wsl_authority(authority)

    assert refusal.value.code == "authority_invalid"


def _fake_png(path: Path) -> Path:
    path.write_bytes(b"\x89PNG\r\n\x1a\ncontrolled-test")
    return path


def test_sendgrid_path_uses_only_sendgrid_provider():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        state = base / "state.sqlite3"
        signature = _fake_png(base / "sig.png")

        sendgrid_provider = Mock(
            return_value={
                "status_code": "202",
                "message_id": "sg-test-1",
            }
        )
        private_provider = Mock()

        config = {
            "provider": "sendgrid",
            "from_email":
                "annettedanek-akey@bnmarketing.info",
            "send_enabled": True,
            "unsubscribe_group_id": 1,
            "groups_to_display": [1],
        }

        with (
            patch.dict(
                os.environ,
                {"ASTRA_MACHINE_ID": "windows-wsl"},
                clear=False,
            ),
            patch.object(
                controlled,
                "_resolve_signature",
                return_value=signature,
            ),
            patch.object(
                controlled,
                "_resolve_sendgrid_key",
                return_value=(
                    "SG.fake",
                    "sendgrid_annette.env",
                ),
            ),
        ):
            result = controlled.execute_controlled_sender_test(
                "sendgrid_annette",
                state_path=state,
                profiles={
                    "sendgrid_annette": config,
                },
                authority_check=lambda: {
                    "status": "active",
                    "authorized_machine": "windows-wsl",
                },
                conflict_check=lambda: [],
                block_classification=lambda: "",
                sendgrid_provider_send=sendgrid_provider,
                private_provider_send=private_provider,
            )

        assert result["ok"] is True
        assert result["provider"] == "sendgrid"
        assert result["production_queue_used"] is False
        assert result["production_queue_written"] is False
        assert result["auto_started"] is False
        assert sendgrid_provider.call_count == 1
        private_provider.assert_not_called()


def test_private_jc_path_uses_only_smtp_provider():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        state = base / "state.sqlite3"
        signature = _fake_png(base / "sig.png")

        sendgrid_provider = Mock()
        private_provider = Mock(
            return_value={
                "status_code": "SMTP_ACCEPTED",
                "message_id": "",
            }
        )

        config = {
            "provider": "private",
            "from_email": "jc@astraproductions.co",
            "send_enabled": True,
            "password_env": "PRIVATE_JC_PASSWORD",
        }

        with (
            patch.dict(
                os.environ,
                {"ASTRA_MACHINE_ID": "windows-wsl"},
                clear=False,
            ),
            patch.object(
                controlled,
                "_resolve_signature",
                return_value=signature,
            ),
            patch.object(
                controlled,
                "_resolve_private_password",
                return_value=(
                    "not-a-real-password",
                    "private_jc.env",
                ),
            ),
        ):
            result = controlled.execute_controlled_sender_test(
                "private_jc",
                state_path=state,
                profiles={"private_jc": config},
                authority_check=lambda: {
                    "status": "active",
                    "authorized_machine": "windows-wsl",
                },
                conflict_check=lambda: [],
                block_classification=lambda: "",
                sendgrid_provider_send=sendgrid_provider,
                private_provider_send=private_provider,
            )

        assert result["ok"] is True
        assert result["provider"] == "private"
        assert result["provider_status"] == "SMTP_ACCEPTED"
        assert result["production_queue_used"] is False
        assert result["production_queue_written"] is False
        assert private_provider.call_count == 1
        sendgrid_provider.assert_not_called()


def test_same_version_profile_cannot_be_attempted_twice():
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state.sqlite3"

        controlled._reserve(
            state,
            "private_jc",
            "private",
            "jc@astraproductions.co",
            "fingerprint-one",
        )

        with pytest.raises(
            controlled.ControlledAllSenderTestRefused
        ) as refusal:
            controlled._reserve(
                state,
                "private_jc",
                "private",
                "jc@astraproductions.co",
                "fingerprint-one",
            )

        assert (
            refusal.value.code
            == "controlled_test_already_attempted"
        )


def test_batch_is_hard_limited_to_six_profiles():
    calls = []

    def fake_single(profile, **kwargs):
        calls.append(profile)
        spec = controlled.CONTROLLED_ALL_IDENTITIES[profile]

        return {
            "ok": True,
            "profile": profile,
            "sender": spec["label"],
            "provider": spec["provider"],
            "production_queue_used": False,
            "production_queue_written": False,
            "auto_started": False,
        }

    with (
        patch.dict(
            os.environ,
            {"ASTRA_MACHINE_ID": "windows-wsl"},
            clear=False,
        ),
        patch.object(
            controlled,
            "execute_controlled_sender_test",
            side_effect=fake_single,
        ),
    ):
        result = controlled.execute_controlled_all_sender_test(
            authority_check=lambda: {
                "status": "active",
                "authorized_machine": "windows-wsl",
            },
            conflict_check=lambda: [],
            block_classification=lambda: "",
        )

    assert calls == [item[0] for item in EXPECTED]
    assert len(calls) == 6
    assert result["accepted"] == 6
    assert result["failed"] == 0
    assert result["all_passed"] is True
    assert result["maximum_messages"] == 6


def test_module_has_no_production_queue_or_worker_start_path():
    source = inspect.getsource(controlled)

    for forbidden in (
        "SHARDS_DIR",
        "recipients_private_jc.csv",
        "recipients_sendgrid_1.csv",
        "recipients_sendgrid_2.csv",
        "recipients_sendgrid_3.csv",
        "recipients_sendgrid_4.csv",
        "recipients_sendgrid_5.csv",
        "systemctl",
        "subprocess",
        "/api/start",
        "send_shard.py",
    ):
        assert forbidden not in source
