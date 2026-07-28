from __future__ import annotations

import json
import io
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

import runtime_authority
import send_shard
from tools import runtime_handoff


def _run(repo: Path, *args: str) -> str:
    result = subprocess.run(
        list(args), cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _write_runtime(repo: Path, emails: list[str], *, sent: list[str] | None = None) -> None:
    shards = repo / "data/shards"
    logs = repo / "data/logs"
    state = repo / "data/state"
    previews = repo / "data/message_previews"
    important = repo / "_important"
    for path in (shards, logs, state, previews, important):
        path.mkdir(parents=True, exist_ok=True)
    (shards / "recipients_private_jc.csv").write_text(
        "Email,FirstName,BookTitle\n"
        + "".join(f"{email},Test,Book\n" for email in emails),
        encoding="utf-8",
    )
    (logs / "private_jc_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n"
        + "".join(f"2026-01-01T00:00:00Z,{email},SENT,ok\n" for email in (sent or [])),
        encoding="utf-8",
    )
    (state / "suppressed.csv").write_text("Email\n", encoding="utf-8")
    (state / "unsubscribed.csv").write_text("Email\n", encoding="utf-8")
    (state / "sendgrid_suppressions.csv").write_text("Email,Type\n", encoding="utf-8")
    (important / "campaign_history.jsonl").write_text(
        '{"campaign":"fixture"}\n', encoding="utf-8"
    )
    with sqlite3.connect(state / "send_idempotency.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS sends (email TEXT PRIMARY KEY)")
        for email in sent or []:
            db.execute("INSERT OR IGNORE INTO sends(email) VALUES (?)", (email,))


def _set_inactive(repo: Path, machine: str, generation: int = 1) -> None:
    other = "windows-wsl" if machine == "mac" else "mac"
    payload = {
        "authorized_machine": machine,
        "generation": generation,
        "bundle_id": f"inactive-{machine}-{generation}",
        "source_machine": other,
        "target_machine": machine,
        "created_utc": runtime_authority.utc_now(),
        "expected_git_commit": _run(repo, "git", "rev-parse", "HEAD"),
        "runtime_manifest_hash": "inactive-runtime",
        "status": "inactive",
    }
    runtime_authority.write_authority(repo, payload)
    runtime_authority.write_generation_floor(repo, generation, payload["bundle_id"])


@pytest.fixture
def repos(tmp_path: Path, monkeypatch):
    seed = tmp_path / "seed"
    seed.mkdir()
    _run(seed, "git", "init", "-q")
    _run(seed, "git", "config", "user.email", "test@example.test")
    _run(seed, "git", "config", "user.name", "Test")
    (seed / "README.md").write_text("fixture\n", encoding="utf-8")
    _run(seed, "git", "add", "README.md")
    _run(seed, "git", "commit", "-qm", "fixture")
    windows = tmp_path / "windows"
    mac = tmp_path / "mac"
    _run(tmp_path, "git", "clone", "-q", str(seed), str(windows))
    _run(tmp_path, "git", "clone", "-q", str(seed), str(mac))
    _write_runtime(
        windows,
        ["pending-one@example.test", "pending-two@example.test"],
        sent=["already-sent@example.test"],
    )
    _write_runtime(mac, ["old-mac@example.test"])
    runtime_handoff.initialize_authority(windows, machine="windows-wsl")
    _set_inactive(mac, "mac")
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    return windows, mac


def _export(repo: Path, tmp_path: Path, target: str, machine: str) -> Path:
    return runtime_handoff.export_runtime(
        repo, tmp_path / "bundles", target, machine=machine
    )


def _rewrite_bundle(
    bundle: Path,
    output: Path,
    mutate,
) -> Path:
    stage = output.parent / f"stage-{output.stem}"
    with tarfile.open(bundle, "r:gz") as archive:
        archive.extractall(stage, filter="data")
    mutate(stage)
    with tarfile.open(output, "w:gz") as archive:
        archive.add(stage / runtime_handoff.MANIFEST_NAME, arcname=runtime_handoff.MANIFEST_NAME)
        archive.add(
            stage / runtime_handoff.BUNDLE_AUTHORITY_NAME,
            arcname=runtime_handoff.BUNDLE_AUTHORITY_NAME,
        )
        archive.add(stage / runtime_handoff.RUNTIME_ROOT, arcname=runtime_handoff.RUNTIME_ROOT)
    return output


def test_windows_to_mac_handoff_carries_changed_queue_logs_suppressions_and_db(
    repos, tmp_path
):
    windows, mac = repos
    _write_runtime(
        windows,
        ["pending-two@example.test"],
        sent=["already-sent@example.test", "pending-one@example.test"],
    )
    (windows / "data/state/suppressed.csv").write_text(
        "Email\nblocked@example.test\n", encoding="utf-8"
    )
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")

    result = runtime_handoff.import_runtime(mac, bundle, machine="mac")

    assert result["sender_started"] is False
    assert result["authority"]["authorized_machine"] == "mac"
    assert result["authority"]["generation"] == 2
    assert runtime_authority.load_authority(windows)["status"] == "handoff_in_progress"
    assert "pending-two@example.test" in (
        mac / "data/shards/recipients_private_jc.csv"
    ).read_text(encoding="utf-8")
    assert "pending-one@example.test" in (
        mac / "data/logs/private_jc_log.csv"
    ).read_text(encoding="utf-8")
    assert "blocked@example.test" in (
        mac / "data/state/suppressed.csv"
    ).read_text(encoding="utf-8")
    with sqlite3.connect(mac / "data/state/send_idempotency.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM sends").fetchone()[0] == 2


def test_mac_to_windows_return_handoff_increments_generation(repos, tmp_path):
    windows, mac = repos
    first = _export(windows, tmp_path, "mac", "windows-wsl")
    runtime_handoff.import_runtime(mac, first, machine="mac")
    (mac / "data/state/unsubscribed.csv").write_text(
        "Email\noptout@example.test\n", encoding="utf-8"
    )

    second = _export(mac, tmp_path, "windows-wsl", "mac")
    result = runtime_handoff.import_runtime(windows, second, machine="windows-wsl")

    assert result["authority"]["generation"] == 3
    assert result["authority"]["authorized_machine"] == "windows-wsl"
    assert "optout@example.test" in (
        windows / "data/state/unsubscribed.csv"
    ).read_text(encoding="utf-8")
    assert runtime_authority.load_authority(mac)["status"] == "handoff_in_progress"


def test_export_refuses_source_process_and_does_not_revoke(repos, tmp_path, monkeypatch):
    windows, _ = repos
    monkeypatch.setattr(
        runtime_handoff, "process_blockers", lambda: ["123 sender: send_shard.py"]
    )
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        _export(windows, tmp_path, "mac", "windows-wsl")
    assert runtime_authority.load_authority(windows)["status"] == "active"


def test_import_refuses_target_process(repos, tmp_path, monkeypatch):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    monkeypatch.setattr(
        runtime_handoff, "process_blockers", lambda: ["456 dashboard: live_dashboard.py"]
    )
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_stale_generation_is_rejected_and_target_is_disabled(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    runtime_authority.write_generation_floor(mac, 2, "newer")
    with pytest.raises(runtime_handoff.HandoffError, match="Stale generation"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_reused_bundle_is_rejected_and_cannot_create_duplicate_authority(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    runtime_handoff.import_runtime(mac, bundle, machine="mac")
    with pytest.raises(runtime_handoff.HandoffError, match="already been used"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"
    assert runtime_authority.load_authority(windows)["status"] != "active"


def test_wrong_target_is_rejected(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    with pytest.raises(runtime_handoff.HandoffError, match="targets mac"):
        runtime_handoff.import_runtime(mac, bundle, machine="windows-wsl")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_wrong_git_commit_is_rejected(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    _run(mac, "git", "config", "user.email", "test@example.test")
    _run(mac, "git", "config", "user.name", "Test")
    (mac / "README.md").write_text("different\n", encoding="utf-8")
    _run(mac, "git", "add", "README.md")
    _run(mac, "git", "commit", "-qm", "different")
    with pytest.raises(runtime_handoff.HandoffError, match="Git commit"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_corrupt_checksum_is_rejected_and_both_sides_remain_disabled(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")

    def corrupt(stage: Path) -> None:
        queue = stage / "runtime/data/shards/recipients_private_jc.csv"
        queue.write_bytes(queue.read_bytes() + b"corrupt")

    bad = _rewrite_bundle(bundle, tmp_path / "bad-checksum.tgz", corrupt)
    with pytest.raises(runtime_handoff.HandoffError, match="Checksum mismatch"):
        runtime_handoff.import_runtime(mac, bad, machine="mac")
    assert runtime_authority.load_authority(windows)["status"] == "handoff_in_progress"
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_sqlite_integrity_failure_is_rejected_even_with_matching_checksum(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")

    def corrupt_sqlite_and_rehash(stage: Path) -> None:
        manifest_path = stage / runtime_handoff.MANIFEST_NAME
        authority_path = stage / runtime_handoff.BUNDLE_AUTHORITY_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["files"] if item["path"].endswith(".sqlite3"))
        db_path = stage / "runtime" / entry["path"]
        db_path.write_bytes(b"not a sqlite database")
        entry["size"] = db_path.stat().st_size
        entry["sha256"] = runtime_handoff.sha256_file(db_path)
        new_hash = runtime_handoff.manifest_hash(manifest["files"])
        manifest["runtime_manifest_hash"] = new_hash
        authority["runtime_manifest_hash"] = new_hash
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        authority_path.write_text(json.dumps(authority), encoding="utf-8")

    bad = _rewrite_bundle(bundle, tmp_path / "bad-sqlite.tgz", corrupt_sqlite_and_rehash)
    with pytest.raises(runtime_handoff.HandoffError, match="SQLite integrity"):
        runtime_handoff.import_runtime(mac, bad, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_partial_restore_rolls_back_target_runtime_and_stays_disabled(repos, tmp_path):
    windows, mac = repos
    original = (mac / "data/shards/recipients_private_jc.csv").read_bytes()
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")

    def partial(repo: Path, _runtime: Path) -> None:
        (repo / "data/shards/recipients_private_jc.csv").write_text(
            "Email\npartial@example.test\n", encoding="utf-8"
        )
        raise OSError("synthetic partial restore")

    with pytest.raises(OSError, match="synthetic partial"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac", replace_hook=partial)
    assert (mac / "data/shards/recipients_private_jc.csv").read_bytes() == original
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_queue_safety_failure_refuses_activation(repos, tmp_path):
    windows, mac = repos
    _write_runtime(
        windows,
        ["duplicate@example.test", "duplicate@example.test"],
    )
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    with pytest.raises(runtime_handoff.HandoffError, match="Queue safety failure"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "import_failed"


def test_sender_authority_enforcement_and_preflight_inspection(repos):
    windows, mac = repos
    assert runtime_authority.assert_send_authorized(
        windows, machine="windows-wsl"
    )["status"] == "active"
    with pytest.raises(runtime_authority.AuthorityError, match="authorized for"):
        runtime_authority.assert_send_authorized(windows, machine="mac")
    with pytest.raises(runtime_authority.AuthorityError, match="inactive"):
        runtime_authority.assert_send_authorized(mac, machine="mac")


def test_send_shard_real_send_refuses_missing_authority_but_preflight_skips_gate(
    tmp_path,
):
    output = io.StringIO()
    with (
        patch.object(send_shard, "ROOT", tmp_path),
        patch.object(
            sys,
            "argv",
            ["send_shard.py", "--profile", "sendgrid_annette"],
        ),
        redirect_stdout(output),
    ):
        send_shard.main()
    assert "REFUSED: real send is not authorized" in output.getvalue()

    with (
        patch.object(
            send_shard,
            "assert_send_authorized",
            side_effect=AssertionError("preflight must not require send authority"),
        ),
        patch.object(
            sys,
            "argv",
            ["send_shard.py", "--preflight"],
        ),
        redirect_stdout(io.StringIO()),
    ):
        send_shard.main()


def test_import_never_invokes_process_start(repos, tmp_path, monkeypatch):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    expected_head = _run(windows, "git", "rev-parse", "HEAD")
    starts: list[object] = []

    def observe_run(*args, **kwargs):
        starts.append(args)
        raise AssertionError("No subprocess should start during verified import")

    monkeypatch.setattr(runtime_handoff.subprocess, "run", observe_run)
    # Commit matching was already read before the patch in production, so patch
    # only the git helper for this unit isolation.
    monkeypatch.setattr(
        runtime_handoff,
        "git",
        lambda _repo, *args: "" if args and args[0] == "status" else expected_head,
    )
    result = runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert starts == []
    assert result["sender_started"] is False
