from __future__ import annotations

import asyncio
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import live_dashboard
import runtime_authority
import send_shard
import settings
from dispatch_transaction_guard import (
    active_dispatch_transaction,
    assert_no_incomplete_dispatch_transaction,
    begin_dispatch_transaction,
    create_recovery_file_backups,
    rollback_incomplete_dispatch_transaction,
)
from durable_io import atomic_write_text
from sendgrid_hygiene import (
    dedupe_webhook_events,
    mark_webhook_events_applied,
    mark_webhook_events_failed,
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)

def test_durable_write_is_private_and_atomic(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic_write_text(target, "one\n")
    assert target.read_text(encoding="utf-8") == "one\n"
    assert _mode(target) == 0o600

    atomic_write_text(target, "two\n")
    assert target.read_text(encoding="utf-8") == "two\n"
    assert _mode(target) == 0o600


def test_runtime_manifest_detects_critical_code_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    critical = tmp_path / "critical.py"
    critical.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(runtime_authority, "CRITICAL_CODE_FILES", ("critical.py",))
    before = runtime_authority.critical_code_manifest_hash(tmp_path)
    critical.write_text("VALUE = 2\n", encoding="utf-8")
    after = runtime_authority.critical_code_manifest_hash(tmp_path)
    assert before != after

def test_interrupted_dispatch_requires_explicit_rollback(tmp_path: Path) -> None:
    state = tmp_path / "state"
    backup = tmp_path / "backup"
    queues = tmp_path / "queues"
    backup.mkdir()
    queues.mkdir()
    queue_paths = [queues / "a.csv", queues / "b.csv"]
    for index, queue in enumerate(queue_paths, start=1):
        queue.write_text(f"new-{index}\n", encoding="utf-8")
        (backup / queue.name).write_text(f"old-{index}\n", encoding="utf-8")

    state_file = tmp_path / "dashboard_state.json"
    state_file.write_text('{"campaign":"old"}\n', encoding="utf-8")
    ledger = tmp_path / "ledger.sqlite3"
    conn = __import__("sqlite3").connect(ledger)
    try:
        conn.execute("CREATE TABLE state(value TEXT NOT NULL)")
        conn.execute("INSERT INTO state(value) VALUES ('old')")
        conn.commit()
    finally:
        conn.close()

    recovery_files = create_recovery_file_backups([state_file, ledger], backup)
    journal = state / "dispatch_transaction_journal.json"
    begin_dispatch_transaction(
        transaction_id="txn-test",
        preview_id="preview-test",
        run_id="run-test",
        backup_dir=backup,
        queue_paths=queue_paths,
        campaign_type="cold",
        recovery_files=recovery_files,
        path=journal,
    )
    queue_paths[0].write_text("new-mutated-1\n", encoding="utf-8")
    state_file.write_text('{"campaign":"new"}\n', encoding="utf-8")
    conn = __import__("sqlite3").connect(ledger)
    try:
        conn.execute("UPDATE state SET value = 'new'")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(Exception):
        assert_no_incomplete_dispatch_transaction(journal)
    result = rollback_incomplete_dispatch_transaction(journal)
    assert result["status"] == "rolled_back"
    assert not active_dispatch_transaction(journal)
    assert queue_paths[0].read_text(encoding="utf-8") == "old-1\n"
    assert queue_paths[1].read_text(encoding="utf-8") == "old-2\n"
    assert state_file.read_text(encoding="utf-8") == '{"campaign":"old"}\n'
    conn = __import__("sqlite3").connect(ledger)
    try:
        assert conn.execute("SELECT value FROM state").fetchone()[0] == "old"
    finally:
        conn.close()
    assert all(_mode(path) == 0o600 for path in queue_paths)
    assert _mode(state_file) == 0o600
    assert _mode(ledger) == 0o600


def test_failed_webhook_event_is_retryable_then_deduped(tmp_path: Path) -> None:
    db = tmp_path / "webhook.sqlite3"
    event = {
        "dedupe_key": "sg_event_id:event-1",
        "event_id": "event-1",
        "message_id": "message-1",
        "email": "user@example.test",
        "status": "bounce",
        "processed_at_utc": "2026-09-23T12:00:00+00:00",
        "received_at_utc": "2026-09-23T12:00:01+00:00",
    }
    first = dedupe_webhook_events([dict(event)], db)
    assert first["stored"] == 1
    mark_webhook_events_failed(first["unique_events"], db, "synthetic failure")

    retry = dedupe_webhook_events([dict(event)], db)
    assert retry["retries"] == 1
    assert len(retry["unique_events"]) == 1
    mark_webhook_events_applied(retry["unique_events"], db)
    duplicate = dedupe_webhook_events([dict(event)], db)
    assert duplicate["duplicates"] == 1
    assert duplicate["unique_events"] == []
    assert _mode(db) == 0o600


def test_webhook_timestamp_freshness() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    current = str(int(now.timestamp()))
    stale = str(int(now.timestamp()) - live_dashboard.SENDGRID_WEBHOOK_MAX_AGE_SECONDS - 1)
    future = str(int(now.timestamp()) + live_dashboard.SENDGRID_WEBHOOK_MAX_AGE_SECONDS + 1)
    assert live_dashboard._sendgrid_webhook_timestamp_fresh(current, reference_utc=now)
    assert not live_dashboard._sendgrid_webhook_timestamp_fresh(stale, reference_utc=now)
    assert not live_dashboard._sendgrid_webhook_timestamp_fresh(future, reference_utc=now)


def test_limited_request_body_rejects_oversize() -> None:
    class RequestStub:
        headers: dict[str, str] = {}

        async def body(self) -> bytes:
            return b"x" * 11

    with pytest.raises(OverflowError):
        asyncio.run(live_dashboard._read_request_body_limited(RequestStub(), 10))


def test_managed_runtime_permissions_are_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = [tmp_path / name for name in ("state", "shards", "logs", "uploads", "cleaned", "tmp")]
    for root in roots:
        root.mkdir()
        child = root / "artifact.txt"
        child.write_text("private\n", encoding="utf-8")
        child.chmod(0o755)
    for attr, root in zip(
        ("STATE_DIR", "SHARDS_DIR", "LOGS_DIR", "UPLOADS_DIR", "CLEANED_DIR", "TMP_DIR"),
        roots,
    ):
        monkeypatch.setattr(settings, attr, root)
    settings.harden_managed_runtime_permissions()
    assert all(_mode(root) == 0o700 for root in roots)
    assert all(_mode(root / "artifact.txt") == 0o600 for root in roots)


def test_login_failure_backoff_locks_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DASHBOARD_LOGIN_MAX_FAILURES", 2)
    monkeypatch.setattr(settings, "DASHBOARD_LOGIN_LOCK_SECONDS", 60)
    key = "127.0.0.1|admin"
    live_dashboard._dashboard_clear_login_failures(key)
    assert live_dashboard._dashboard_record_login_failure(key, now=100.0) == 0
    retry_after = live_dashboard._dashboard_record_login_failure(key, now=101.0)
    assert retry_after == 60
    assert live_dashboard._dashboard_login_retry_after(key, now=102.0) == 59
    live_dashboard._dashboard_clear_login_failures(key)


def test_mutation_origin_guard_allows_same_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DASHBOARD_REQUIRE_MUTATION_ORIGIN", True)
    request = SimpleNamespace(
        headers={"origin": "https://dashboard.example", "host": "dashboard.example"},
        url=SimpleNamespace(scheme="https", netloc="dashboard.example"),
    )
    assert live_dashboard._dashboard_mutation_origin_allowed(request)
    request.headers["origin"] = "https://evil.example"
    assert not live_dashboard._dashboard_mutation_origin_allowed(request)


def test_runtime_authority_enforces_sealed_critical_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    critical = tmp_path / "critical.py"
    critical.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(runtime_authority, "CRITICAL_CODE_FILES", ("critical.py",))
    sealed_hash = runtime_authority.critical_code_manifest_hash(tmp_path)
    payload = {
        "authorized_machine": "windows-wsl",
        "generation": 1,
        "bundle_id": "bundle-test",
        "source_machine": "mac",
        "target_machine": "windows-wsl",
        "created_utc": "2026-09-24T00:00:00+00:00",
        "expected_git_commit": "deadbeef",
        "runtime_manifest_hash": "runtime-test",
        "critical_code_manifest_hash": sealed_hash,
        "status": "active",
    }
    runtime_authority.write_authority(tmp_path, payload)
    runtime_authority.write_generation_floor(tmp_path, 1, payload["bundle_id"])
    fake_git = SimpleNamespace(returncode=0, stdout="deadbeef\n", stderr="")
    monkeypatch.setattr(runtime_authority.subprocess, "run", lambda *args, **kwargs: fake_git)

    runtime_authority.assert_send_authorized(tmp_path, machine="windows-wsl")
    critical.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(runtime_authority.AuthorityError, match="Critical runtime code differs"):
        runtime_authority.assert_send_authorized(tmp_path, machine="windows-wsl")


def test_runtime_authority_can_require_legacy_authority_to_be_sealed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    critical = tmp_path / "critical.py"
    critical.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(runtime_authority, "CRITICAL_CODE_FILES", ("critical.py",))
    payload = {
        "authorized_machine": "windows-wsl",
        "generation": 1,
        "bundle_id": "bundle-legacy",
        "source_machine": "mac",
        "target_machine": "windows-wsl",
        "created_utc": "2026-09-24T00:00:00+00:00",
        "expected_git_commit": "deadbeef",
        "runtime_manifest_hash": "runtime-test",
        "status": "active",
    }
    runtime_authority.write_authority(tmp_path, payload)
    runtime_authority.write_generation_floor(tmp_path, 1, payload["bundle_id"])
    fake_git = SimpleNamespace(returncode=0, stdout="deadbeef\n", stderr="")
    monkeypatch.setattr(runtime_authority.subprocess, "run", lambda *args, **kwargs: fake_git)
    monkeypatch.setenv("ASTRA_REQUIRE_CRITICAL_CODE_SEAL", "1")

    with pytest.raises(runtime_authority.AuthorityError, match="not sealed"):
        runtime_authority.assert_send_authorized(tmp_path, machine="windows-wsl")


def test_send_idempotency_database_is_private(tmp_path: Path) -> None:
    database = tmp_path / "send_idempotency.sqlite3"
    ok, reason = send_shard._ensure_send_idempotency_schema(database)
    assert ok, reason
    assert _mode(database) == 0o600


def test_limited_request_stream_rejects_oversize() -> None:
    class RequestStub:
        headers: dict[str, str] = {}

        async def stream(self):
            yield b"x" * 6
            yield b"y" * 6

    with pytest.raises(OverflowError):
        asyncio.run(live_dashboard._read_request_body_limited(RequestStub(), 10))


def test_limited_request_rejects_oversized_content_length_before_body() -> None:
    class RequestStub:
        headers = {"content-length": "11"}

        async def body(self) -> bytes:
            raise AssertionError("body must not be read after oversized Content-Length")

    with pytest.raises(OverflowError):
        asyncio.run(live_dashboard._read_request_body_limited(RequestStub(), 10))


def test_webhook_endpoint_rejects_stale_timestamp_before_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = str(
        int(datetime.now(timezone.utc).timestamp())
        - live_dashboard.SENDGRID_WEBHOOK_MAX_AGE_SECONDS
        - 1
    )

    class RequestStub:
        headers = {
            live_dashboard.SENDGRID_SIG_HEADER: "synthetic-signature",
            live_dashboard.SENDGRID_TS_HEADER: stale,
        }

        async def body(self) -> bytes:
            raise AssertionError("stale webhook body must not be read")

    monkeypatch.setattr(live_dashboard, "SENDGRID_EVENT_PUBLIC_KEY", "configured")
    response = asyncio.run(live_dashboard.sendgrid_event_webhook(RequestStub()))
    assert response.status_code == 401


def test_webhook_endpoint_rejects_too_many_events_without_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b'[{"event":"delivered"},{"event":"delivered"}]'
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))

    class RequestStub:
        headers = {
            live_dashboard.SENDGRID_SIG_HEADER: "synthetic-signature",
            live_dashboard.SENDGRID_TS_HEADER: timestamp,
            "content-length": str(len(raw)),
        }

        async def body(self) -> bytes:
            return raw

    monkeypatch.setattr(live_dashboard, "SENDGRID_EVENT_PUBLIC_KEY", "configured")
    monkeypatch.setattr(live_dashboard, "SENDGRID_WEBHOOK_MAX_EVENTS", 1)
    monkeypatch.setattr(live_dashboard, "_verify_sendgrid_signature", lambda *args: True)
    with patch.object(
        live_dashboard,
        "_process_sendgrid_webhook_payload_async",
        side_effect=AssertionError("oversized event batch must not be processed"),
    ):
        response = asyncio.run(live_dashboard.sendgrid_event_webhook(RequestStub()))
    assert response.status_code == 413
