from __future__ import annotations

import imaplib
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import controlled_all_sender_test as controlled_all
import private_bounce_hygiene
import protected_profile_env
from private_bounce_hygiene import classify_private_bounce_error, sync_private_bounces
from protected_profile_env import (
    ProtectedProfileEnvError,
    read_protected_profile_env,
    resolve_canonical_jc_credential,
    resolve_protected_profile_credential,
)


FAKE_SECRET = "unit-test-private-jc-secret"


def _profile_dir(tmp_path: Path, profile: str = "private_jc", value: str = FAKE_SECRET) -> Path:
    env_dir = tmp_path / "profiles"
    env_dir.mkdir()
    (env_dir / f"{profile}.env").write_text(
        f"PRIVATE_JC_PASSWORD={value}\n",
        encoding="utf-8",
    )
    return env_dir


class _EmptyFakeIMAP:
    login_password = ""

    def __init__(self, host: str, port: int, timeout: int = 0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, email_addr: str, password: str):
        type(self).login_password = password
        return "OK", [b"logged in"]

    def select(self, folder: str, readonly: bool = True):
        return "OK", [b"0"]

    def uid(self, command: str, *args):
        assert command.lower() == "search"
        return "OK", [b""]

    def logout(self):
        return "BYE", [b"logout"]


def test_private_bounce_uses_protected_credential_when_process_env_absent(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    _EmptyFakeIMAP.login_password = ""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("private_bounce_hygiene.imaplib.IMAP4_SSL", _EmptyFakeIMAP),
    ):
        report = sync_private_bounces(
            profile_name="private_jc",
            folders=["INBOX"],
            state_path=tmp_path / "state.json",
            suppressed_path=tmp_path / "suppressed.csv",
            report_dir=tmp_path / "reports",
            profile_env_dir=env_dir,
        )

    assert report["scanned_messages"] == 0
    assert _EmptyFakeIMAP.login_password == FAKE_SECRET
    assert "PRIVATE_JC_PASSWORD" not in os.environ


@pytest.mark.parametrize("content", ["", "PRIVATE_JC_PASSWORD=\n"])
def test_missing_or_empty_protected_credential_fails_before_imap(
    tmp_path: Path,
    content: str,
) -> None:
    env_dir = tmp_path / "profiles"
    env_dir.mkdir()
    if content:
        (env_dir / "private_jc.env").write_text(content, encoding="utf-8")
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("private_bounce_hygiene.imaplib.IMAP4_SSL") as imap_constructor,
        pytest.raises(ValueError, match="mailbox credential is unavailable"),
    ):
        sync_private_bounces(profile_env_dir=env_dir)
    imap_constructor.assert_not_called()


def test_wrong_password_mapping_fails_closed_before_imap(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    wrong_profiles = {
        "private_jc": {
            "provider": "private",
            "from_email": "jc@astraproductions.co",
            "password_env": "PRIVATE_OTHER_PASSWORD",
        }
    }
    with (
        patch.object(private_bounce_hygiene, "PROFILES", wrong_profiles),
        patch("private_bounce_hygiene.imaplib.IMAP4_SSL") as imap_constructor,
        pytest.raises(ValueError, match="mailbox credential is unavailable"),
    ):
        sync_private_bounces(profile_env_dir=env_dir)
    imap_constructor.assert_not_called()


def test_unknown_or_non_private_profile_cannot_read_jc_credential(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path, profile="sendgrid_alison")
    profiles = {
        "sendgrid_alison": {
            "provider": "sendgrid",
            "from_email": "sender@example.test",
            "password_env": "PRIVATE_JC_PASSWORD",
        }
    }
    with (
        patch.object(private_bounce_hygiene, "PROFILES", profiles),
        patch("private_bounce_hygiene.imaplib.IMAP4_SSL") as imap_constructor,
        pytest.raises(ValueError, match="not a private-email sender"),
    ):
        sync_private_bounces("sendgrid_alison", profile_env_dir=env_dir)
    imap_constructor.assert_not_called()


def test_warm_profile_uses_canonical_jc_credential_not_separate_value(tmp_path: Path) -> None:
    env_dir = tmp_path / "profiles"
    env_dir.mkdir()
    (env_dir / "private_jc.env").write_text(
        f"PRIVATE_JC_PASSWORD={FAKE_SECRET}\n",
        encoding="utf-8",
    )
    (env_dir / "private_jc_warm.env").write_text(
        "PRIVATE_JC_PASSWORD=wrong-separate-secret\n",
        encoding="utf-8",
    )
    _EmptyFakeIMAP.login_password = ""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("private_bounce_hygiene.imaplib.IMAP4_SSL", _EmptyFakeIMAP),
    ):
        sync_private_bounces(
            "private_jc_warm",
            folders=["INBOX"],
            state_path=tmp_path / "warm-state.json",
            suppressed_path=tmp_path / "warm-suppressed.csv",
            report_dir=tmp_path / "warm-reports",
            profile_env_dir=env_dir,
        )
    assert _EmptyFakeIMAP.login_password == FAKE_SECRET
    assert _EmptyFakeIMAP.login_password != "wrong-separate-secret"


def test_canonical_jc_resolver_rejects_wrong_profile_identity(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    canonical = {
        "provider": "private",
        "from_email": "jc@astraproductions.co",
        "password_env": "PRIVATE_JC_PASSWORD",
    }
    wrong_identity = {
        **canonical,
        "from_email": "another-mailbox@example.test",
    }

    with pytest.raises(ProtectedProfileEnvError) as refusal:
        resolve_canonical_jc_credential(
            "private_jc_warm",
            wrong_identity,
            canonical,
            profile_env_dir=env_dir,
        )

    assert refusal.value.code == "credential_identity_mismatch"
    assert FAKE_SECRET not in str(refusal.value)


def test_canonical_jc_resolver_rejects_non_jc_profile(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    canonical = {
        "provider": "private",
        "from_email": "jc@astraproductions.co",
        "password_env": "PRIVATE_JC_PASSWORD",
    }

    with pytest.raises(ProtectedProfileEnvError) as refusal:
        resolve_canonical_jc_credential(
            "private_alison",
            canonical,
            canonical,
            profile_env_dir=env_dir,
        )

    assert refusal.value.code == "credential_identity_mismatch"
    assert FAKE_SECRET not in str(refusal.value)


def test_symlink_profile_file_is_rejected(tmp_path: Path) -> None:
    env_dir = tmp_path / "profiles"
    env_dir.mkdir()
    target = tmp_path / "real.env"
    target.write_text(f"PRIVATE_JC_PASSWORD={FAKE_SECRET}\n", encoding="utf-8")
    (env_dir / "private_jc.env").symlink_to(target)
    with pytest.raises(ProtectedProfileEnvError) as refusal:
        read_protected_profile_env("private_jc", env_dir)
    assert refusal.value.code == "credential_file_unsafe"
    assert FAKE_SECRET not in str(refusal.value)


def test_cloud_unsafe_mode_or_owner_is_rejected_without_secret_disclosure(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    (env_dir / "private_jc.env").chmod(0o666)
    with (
        patch.dict(os.environ, {"ASTRA_MACHINE_ID": "cloud"}, clear=False),
        patch.object(
            protected_profile_env.grp,
            "getgrnam",
            return_value=SimpleNamespace(gr_gid=os.getgid()),
        ),
        pytest.raises(ProtectedProfileEnvError) as refusal,
    ):
        read_protected_profile_env("private_jc", env_dir)
    assert refusal.value.code == "credential_file_unsafe"
    assert FAKE_SECRET not in str(refusal.value)


def test_file_inode_change_is_rejected(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    real_fstat = protected_profile_env.os.fstat

    def changed_file_inode(fd: int):
        metadata = real_fstat(fd)
        if stat.S_ISREG(metadata.st_mode):
            fields = list(metadata)
            fields[1] += 1
            return os.stat_result(fields)
        return metadata

    with (
        patch.object(protected_profile_env.os, "fstat", side_effect=changed_file_inode),
        pytest.raises(ProtectedProfileEnvError) as refusal,
    ):
        read_protected_profile_env("private_jc", env_dir)
    assert refusal.value.code == "credential_file_unsafe"


def test_controlled_jc_uses_shared_protected_resolver(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path)
    with patch.dict(os.environ, {}, clear=True):
        password, source = controlled_all._resolve_private_password(
            "private_jc",
            {"password_env": "PRIVATE_JC_PASSWORD"},
            env_dir,
        )
    assert password == FAKE_SECRET
    assert source == "private_jc.env"


def test_imap_failure_classifications_remain_stable() -> None:
    auth = classify_private_bounce_error(imaplib.IMAP4.error("authentication failed"))
    connection = classify_private_bounce_error(TimeoutError(FAKE_SECRET))
    generic = classify_private_bounce_error(RuntimeError(FAKE_SECRET))
    assert auth == ("imap_auth_failure", "Private JC IMAP bounce sync authentication failed.")
    assert connection == (
        "imap_connection_failure",
        "Private JC IMAP bounce sync connection failed.",
    )
    assert generic == ("imap_sync_failure", "Private JC IMAP bounce sync failed.")
    assert all(FAKE_SECRET not in message for _, message in (auth, connection, generic))


def test_environment_fallback_does_not_export_or_persist_secret(tmp_path: Path) -> None:
    env_dir = _profile_dir(tmp_path, value="")
    environment = {"PRIVATE_JC_PASSWORD": FAKE_SECRET}
    secret, source = resolve_protected_profile_credential(
        "private_jc",
        "PRIVATE_JC_PASSWORD",
        "PRIVATE_JC_PASSWORD",
        profile_env_dir=env_dir,
        environment=environment,
    )
    assert secret == FAKE_SECRET
    assert source == "private_jc.env"
    assert (env_dir / "private_jc.env").read_text(encoding="utf-8") == "PRIVATE_JC_PASSWORD=\n"
