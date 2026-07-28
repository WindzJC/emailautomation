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
    for name in ("leads.csv", "leads_triaged_keep.csv"):
        (important / name).write_text(
            "Email,FirstName,BookTitle\n"
            + "".join(f"{email},Test,Book\n" for email in emails),
            encoding="utf-8",
        )
    (important / "leads_triaged_reject.csv").write_text(
        "Email,FirstName,BookTitle\n",
        encoding="utf-8",
    )
    preview_header = "Email,AuthorEmail,AuthorName,FirstName,BookTitle,Subject,Body\n"
    preview_rows = "".join(
        f"{email},{email},Test Author,Test,Book,Subject,Body\n"
        for email in emails
    )
    for name in (
        "private_jc_message_preview.csv",
        "private_jc_message_preview_validated.csv",
    ):
        (previews / name).write_text(
            preview_header + preview_rows,
            encoding="utf-8",
        )
    (previews / "private_jc_message_preview_failed.csv").write_text(
        preview_header,
        encoding="utf-8",
    )
    (previews / "private_jc_message_preview_summary.txt").write_text(
        f"total rows: {len(emails)}\npassed rows: {len(emails)}\nfailed rows: 0\n",
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
    (state / "active_campaign_snapshot.json").write_text(
        json.dumps(
            {
                "checked_path": str(important / "leads.csv"),
                "intended_source_path": str(important / "leads_triaged_keep.csv"),
                "triaged_keep_path": str(important / "leads_triaged_keep.csv"),
                "triaged_reject_path": str(important / "leads_triaged_reject.csv"),
            }
        ),
        encoding="utf-8",
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


def test_fresh_queue_safety_ignores_contradictory_stale_dashboard_state(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    (repo / "data/state/leads_dashboard_state.json").write_text(
        json.dumps(
            {
                "lead_check_status": {
                    "preview_block_reason": (
                        "Check state mismatch: Latest check result does not match the current upload."
                    )
                },
                "private_queue_safety": {
                    "outside_checked_output_count": 1,
                    "outside_intended_source_count": 1,
                    "safe": False,
                },
            }
        ),
        encoding="utf-8",
    )

    safety = runtime_handoff.recompute_queue_safety(repo)

    assert safety["safe"] is True
    assert safety["active_intended_profiles"] == ["private_jc"]
    assert safety["profiles"][0]["outside_checked_output_count"] == 0
    assert safety["profiles"][0]["outside_intended_source_count"] == 0
    assert safety["source_origin"] == "active_campaign_manifest"


def test_inactive_profiles_without_previews_do_not_block(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    for index in range(1, 6):
        (repo / f"data/shards/recipients_sendgrid_{index}.csv").write_text(
            "Email,FirstName,AuthorEmail,AuthorName,BookTitle\n",
            encoding="utf-8",
        )
    (repo / "data/shards/recipients_private_jc_warm.csv").write_text(
        "AuthorEmail,EmailSubject,EmailBody,ContactPath\n",
        encoding="utf-8",
    )

    safety = runtime_handoff.recompute_queue_safety(repo)

    assert safety["safe"] is True
    assert safety["active_intended_profiles"] == ["private_jc"]
    assert [item["profile"] for item in safety["profiles"]] == ["private_jc"]


def test_active_profile_stale_preview_is_precise_and_failed_initialize_is_read_only(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["one@example.test", "two@example.test"])
    preview = repo / "data/message_previews/private_jc_message_preview.csv"
    validated = repo / "data/message_previews/private_jc_message_preview_validated.csv"
    for path in (preview, validated):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    before = {
        path.relative_to(repo): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    monkeypatch.setattr(runtime_handoff, "git", lambda _repo, *args: "abc123")

    safety = runtime_handoff.recompute_queue_safety(repo)
    with pytest.raises(
        runtime_handoff.HandoffError,
        match=r"profile=private_jc.*queue_rows=2.*preview_rows=1",
    ):
        runtime_handoff.initialize_authority(repo, machine="windows-wsl")

    assert safety["unsafe_reasons"] == ["active profile preview is stale or invalid"]
    assert safety["profiles"][0]["preview"]["queue_row_count"] == 2
    assert safety["profiles"][0]["preview"]["preview_row_count"] == 1
    after = {
        path.relative_to(repo): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not runtime_authority.authority_path(repo).exists()
    assert not runtime_authority.generation_floor_path(repo).exists()


def test_historical_campaign_metadata_does_not_become_sent_overlap(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    (repo / "data/logs/campaign_history.csv").write_text(
        "Email,Status,Campaign\ncurrent@example.test,SENT,historical-only\n",
        encoding="utf-8",
    )

    safety = runtime_handoff.recompute_queue_safety(repo)

    assert safety["safe"] is True
    assert safety["queue_sent_overlap"] == 0


def test_authoritative_sent_log_overlap_blocks_with_exact_profile_details(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    (repo / "data/logs/private_jc_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n"
        "2026-01-01T00:00:00Z,current@example.test,SENT,ok\n",
        encoding="utf-8",
    )

    safety = runtime_handoff.recompute_queue_safety(repo)

    assert safety["safe"] is False
    assert safety["queue_sent_overlap"] == 1
    assert safety["profiles"][0]["sent_overlap_count"] == 1
    assert "profile=private_jc" in safety["failure_details"][0]
    assert "private_jc_log.csv" in safety["failure_details"][0]


def test_suppression_overlap_remains_fail_closed(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    (repo / "data/state/unsubscribed.csv").write_text(
        "Email\ncurrent@example.test\n",
        encoding="utf-8",
    )

    safety = runtime_handoff.recompute_queue_safety(repo)

    assert safety["safe"] is False
    assert safety["queue_suppression_overlap"] == 1
    assert safety["profiles"][0]["suppression_overlap_count"] == 1
    assert "unsubscribed.csv" in safety["failure_details"][0]


def test_current_idempotency_overlap_blocks_but_old_campaign_does_not(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    database = repo / "data/state/send_idempotency.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute(
            """
            CREATE TABLE send_reservations (
                campaign_id TEXT,
                provider TEXT,
                email TEXT,
                profile TEXT
            )
            """
        )
        db.execute(
            "INSERT INTO send_reservations VALUES (?, ?, ?, ?)",
            ("older-campaign", "private", "current@example.test", "private_jc"),
        )

    old_only = runtime_handoff.recompute_queue_safety(repo)
    assert old_only["safe"] is True
    assert old_only["queue_idempotency_overlap"] == 0

    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO send_reservations VALUES (?, ?, ?, ?)",
            ("cold", "private", "current@example.test", "private_jc"),
        )

    current = runtime_handoff.recompute_queue_safety(repo)
    assert current["safe"] is False
    assert current["queue_idempotency_overlap"] == 1
    assert current["profiles"][0]["idempotency_overlap_count"] == 1
    assert "send_idempotency.sqlite3" in current["failure_details"][0]


def test_safe_current_queue_initializes_after_matching_validated_preview(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    monkeypatch.setattr(runtime_handoff, "git", lambda _repo, *args: "abc123")

    result = runtime_handoff.initialize_authority(
        repo,
        machine="windows-wsl",
    )

    assert result["status"] == runtime_authority.ACTIVE_STATUS
    assert result["authorized_machine"] == "windows-wsl"
    assert runtime_authority.load_authority(repo)["bundle_id"] == result["bundle_id"]


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
