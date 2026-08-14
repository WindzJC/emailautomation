from __future__ import annotations

import csv
import json
import io
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import uuid
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

import runtime_authority
import send_shard
import settings
from sendgrid_hygiene import load_suppression_email_tokens
from tools import runtime_handoff


def _run(repo: Path, *args: str) -> str:
    result = subprocess.run(
        list(args), cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _write_preview_fixture(
    repo: Path,
    emails: list[str],
    *,
    mode: str = "astra_visual",
) -> None:
    previews = repo / "data/message_previews"
    previews.mkdir(parents=True, exist_ok=True)
    generated_header = (
        "CampaignType,Email,AuthorEmail,AuthorName,FirstName,BookTitle,"
        "PersonalizedOpeningLine,Subject,Body\n"
    )
    generated_rows = "".join(
        f"cold,{email},{email},Test Author,Test,Book,Opening,Subject,Body\n"
        for email in emails
    )
    validated_header = (
        "Email,AuthorEmail,AuthorName,FirstName,BookTitle,"
        "PersonalizedOpeningLine,Subject,Body,ValidationStatus,FailureReasons\n"
    )
    validated_rows = "".join(
        f"{email},{email},Test Author,Test,Book,Opening,Subject,Body,PASS,\n"
        for email in emails
    )
    (previews / "private_jc_message_preview.csv").write_text(
        generated_header + generated_rows,
        encoding="utf-8",
    )
    (previews / "private_jc_message_preview_validated.csv").write_text(
        validated_header + validated_rows,
        encoding="utf-8",
    )
    (previews / "private_jc_message_preview_failed.csv").write_text(
        validated_header,
        encoding="utf-8",
    )
    (previews / "private_jc_message_preview_summary.txt").write_text(
        f"pitch mode: {mode}\n"
        f"total rows checked: {len(emails)}\n"
        f"passed rows: {len(emails)}\n"
        "failed rows: 0\n",
        encoding="utf-8",
    )


def _write_profile_preview_fixture(
    repo: Path,
    profile: str,
    emails: list[str],
    *,
    mode: str = "consignment",
) -> None:
    previews = repo / "data/message_previews"
    previews.mkdir(parents=True, exist_ok=True)
    generated_header = (
        "CampaignType,Email,AuthorEmail,AuthorName,FirstName,BookTitle,"
        "PersonalizedOpeningLine,Subject,Body\n"
    )
    generated_rows = "".join(
        f"cold,{email},{email},Test Author,Test,Book,Opening,Subject,Body\n"
        for email in emails
    )
    validated_header = (
        "Email,AuthorEmail,AuthorName,FirstName,BookTitle,"
        "PersonalizedOpeningLine,Subject,Body,ValidationStatus,FailureReasons\n"
    )
    validated_rows = "".join(
        f"{email},{email},Test Author,Test,Book,Opening,Subject,Body,PASS,\n"
        for email in emails
    )
    (previews / f"{profile}_message_preview.csv").write_text(
        generated_header + generated_rows,
        encoding="utf-8",
    )
    (previews / f"{profile}_message_preview_validated.csv").write_text(
        validated_header + validated_rows,
        encoding="utf-8",
    )
    (previews / f"{profile}_message_preview_failed.csv").write_text(
        validated_header,
        encoding="utf-8",
    )
    (previews / f"{profile}_message_preview_summary.txt").write_text(
        f"pitch mode: {mode}\n"
        f"total rows checked: {len(emails)}\n"
        f"passed rows: {len(emails)}\n"
        "failed rows: 0\n",
        encoding="utf-8",
    )


def _write_controlled_sendgrid_runtime(
    repo: Path,
    emails: list[str],
) -> Path:
    shards = repo / "data/shards"
    logs = repo / "data/logs"
    state = repo / "data/state"
    for path in (shards, logs, state):
        path.mkdir(parents=True, exist_ok=True)
    queue = shards / "recipients_sendgrid_controlled_test.csv"
    queue.write_text(
        "Email,FirstName,BookTitle,CampaignType\n"
        + "".join(f"{email},Test,Book,cold\n" for email in emails),
        encoding="utf-8",
    )
    (logs / "sendgrid_controlled_test_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n",
        encoding="utf-8",
    )
    (state / "suppressed.csv").write_text("Email\n", encoding="utf-8")
    (state / "unsubscribed.csv").write_text("Email\n", encoding="utf-8")
    (state / "sendgrid_suppressions.csv").write_text(
        "Email,Type\n",
        encoding="utf-8",
    )
    with sqlite3.connect(state / "send_idempotency.sqlite3") as db:
        db.execute(
            "CREATE TABLE send_reservations ("
            "campaign_id TEXT, provider TEXT, email TEXT, profile TEXT)"
        )
    _write_profile_preview_fixture(
        repo,
        "sendgrid_controlled_test",
        emails,
    )
    return queue


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
    _write_preview_fixture(repo, emails)
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
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    runtime_handoff.initialize_authority(windows, machine="windows-wsl")
    _set_inactive(mac, "mac")
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


def _rewrite_bundle_identity(
    bundle: Path,
    output: Path,
    *,
    source_machine: str = "mac",
    target_machine: str = "cloud",
    source_commit: str = "14c3eaf79507cc33fab06ba107fe128ba251a9dc",
) -> Path:
    def mutate(stage: Path) -> None:
        manifest_path = stage / runtime_handoff.MANIFEST_NAME
        authority_path = stage / runtime_handoff.BUNDLE_AUTHORITY_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        manifest["source_machine"] = source_machine
        manifest["target_machine"] = target_machine
        manifest["expected_git_commit"] = source_commit
        authority["source_machine"] = source_machine
        authority["target_machine"] = target_machine
        authority["authorized_machine"] = source_machine
        authority["expected_git_commit"] = source_commit
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        authority_path.write_text(json.dumps(authority), encoding="utf-8")

    return _rewrite_bundle(bundle, output, mutate)


def _write_commit_compatibility(
    path: Path,
    mappings: list[dict[str, str]],
) -> Path:
    path.write_text(
        json.dumps(
            {runtime_handoff.COMMIT_COMPATIBILITY_ROOT_KEY: mappings},
            indent=2,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _approved_mapping(
    destination_commit: str,
    **overrides: str,
) -> dict[str, str]:
    mapping = {
        **runtime_handoff.APPROVED_LEGACY_SOURCE_IDENTITY,
        "approved_destination_commit": destination_commit,
    }
    mapping.update(overrides)
    return mapping


def _cloud_target(repos, tmp_path: Path) -> tuple[Path, Path]:
    windows, _mac = repos
    cloud = tmp_path / "cloud"
    _run(tmp_path, "git", "clone", "-q", str(windows), str(cloud))
    _write_runtime(cloud, ["old-cloud@example.test"])
    _set_inactive(cloud, "cloud")
    bundle = _export(windows, tmp_path, "cloud", "windows-wsl")
    return cloud, bundle


def _use_approved_source_tree_git(monkeypatch, cloud: Path) -> None:
    real_git = runtime_handoff.git

    def compatible_git(repo: Path, *args: str) -> str:
        if repo == cloud and args == (
            "rev-parse",
            f"{runtime_handoff.APPROVED_LEGACY_CLEANED_EQUIVALENT_COMMIT}^{{tree}}",
        ):
            return runtime_handoff.APPROVED_LEGACY_SOURCE_IDENTITY["source_tree"]
        return real_git(repo, *args)

    monkeypatch.setattr(runtime_handoff, "git", compatible_git)


def test_process_classifier_ignores_networkd_dispatcher_service():
    assert (
        runtime_handoff.classify_process_command(
            "/usr/bin/networkd-dispatcher --run-startup-triggers"
        )
        is None
    )
    assert (
        runtime_handoff.classify_process_command(
            "/usr/lib/systemd/networkd-dispatcher.service"
        )
        is None
    )


def test_process_classifier_ignores_unrelated_dispatch_text():
    command = (
        "/usr/local/bin/report-dispatch-health "
        "--service networkd-dispatcher.service "
        "--user dispatch --directory /srv/dispatch --environment=dispatch"
    )

    assert runtime_handoff.classify_process_command(command) is None


@pytest.mark.parametrize(
    ("command", "category"),
    [
        (
            "/opt/astra/emailautomation/.venv/bin/python "
            "/opt/astra/emailautomation/dispatch.py",
            "dispatch",
        ),
        ("python3 /opt/astra/emailautomation/check_pending.py", "check"),
        ("python3 /opt/astra/emailautomation/triage.py", "triage"),
        (
            "python3 /opt/astra/emailautomation/important_leads_verify.py",
            "verification",
        ),
        (
            "python3 /opt/astra/emailautomation/important_leads_workflow.py",
            "workflow",
        ),
        (
            "python3 /opt/astra/emailautomation/tools/runtime_handoff.py status",
            "handoff",
        ),
        (
            "python3 /opt/astra/emailautomation/send_shard.py --profile private_jc",
            "sender",
        ),
        (
            "python3 -m uvicorn live_dashboard:app --host 127.0.0.1",
            "dashboard",
        ),
        ("/usr/bin/cloudflared tunnel run astra", "tunnel"),
        ("bash /opt/astra/emailautomation/run_tunnel_tmux.sh", "tunnel"),
    ],
)
def test_process_classifier_detects_exact_astra_entrypoints(command, category):
    assert runtime_handoff.classify_process_command(command) == category


def test_process_blockers_classifies_entrypoints_not_incidental_text(monkeypatch):
    process_listing = "\n".join(
        [
            "1 0 /sbin/init",
            "50 1 bash -lc python3 tools/runtime_handoff.py status",
            "100 50 python3 tools/runtime_handoff.py status",
            "200 1 /usr/bin/networkd-dispatcher --run-startup-triggers",
            "201 1 /usr/local/bin/report-dispatch-health --user dispatch",
            "202 1 python3 /opt/astra/emailautomation/dispatch.py",
        ]
    )
    completed = subprocess.CompletedProcess(
        args=["ps"],
        returncode=0,
        stdout=process_listing,
        stderr="",
    )
    monkeypatch.setattr(runtime_handoff.subprocess, "run", lambda *args, **kwargs: completed)
    monkeypatch.setattr(runtime_handoff.os, "getpid", lambda: 100)
    monkeypatch.setattr(runtime_handoff.os, "getppid", lambda: 50)

    assert runtime_handoff.process_blockers() == [
        "202 dispatch: python3 /opt/astra/emailautomation/dispatch.py"
    ]


@pytest.fixture
def legacy_compatibility_case(repos, tmp_path: Path, monkeypatch):
    cloud, bundle = _cloud_target(repos, tmp_path)
    destination_commit = runtime_handoff.git(cloud, "rev-parse", "HEAD")
    legacy_bundle = _rewrite_bundle_identity(
        bundle,
        tmp_path / "legacy-mac-to-cloud.tgz",
    )
    _use_approved_source_tree_git(monkeypatch, cloud)
    config = tmp_path / "commit-compatibility.json"
    monkeypatch.setenv(
        runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV,
        str(config),
    )
    return {
        "cloud": cloud,
        "bundle": legacy_bundle,
        "config": config,
        "destination_commit": destination_commit,
    }


@pytest.mark.parametrize(
    "relative",
    [
        "data/state/KEYS",
        "data/state/ACC GMAIL",
        "data/state/nested/.env",
        "data/state/nested/.env.cloud",
        "data/state/nested/KEYS",
        "data/state/nested/ACC GMAIL",
    ],
)
def test_runtime_files_exclude_sensitive_names(
    tmp_path: Path,
    relative: str,
) -> None:
    allowed = tmp_path / "data/state/allowed.json"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text("{}\n", encoding="utf-8")
    sensitive = tmp_path / relative
    sensitive.parent.mkdir(parents=True, exist_ok=True)
    sensitive.write_text("synthetic-test-value", encoding="utf-8")

    names = {
        path.relative_to(tmp_path).as_posix()
        for path in runtime_handoff.runtime_files(tmp_path)
    }

    assert "data/state/allowed.json" in names
    assert relative not in names


@pytest.mark.parametrize(
    "relative",
    [
        "data/state/KEYS",
        "data/state/ACC GMAIL",
        "data/state/nested/.env",
        "data/state/nested/.env.cloud",
        "data/state/nested/KEYS",
        "data/state/nested/ACC GMAIL",
    ],
)
def test_handoff_archive_refuses_sensitive_members(
    tmp_path: Path,
    relative: str,
) -> None:
    bundle = tmp_path / "sensitive-member.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        for name, payload in (
            (runtime_handoff.MANIFEST_NAME, b"{}"),
            (runtime_handoff.BUNDLE_AUTHORITY_NAME, b"{}"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        runtime = tarfile.TarInfo(runtime_handoff.RUNTIME_ROOT)
        runtime.type = tarfile.DIRTYPE
        archive.addfile(runtime)
        payload = b"synthetic-test-value"
        member = tarfile.TarInfo(
            f"{runtime_handoff.RUNTIME_ROOT}/{relative}"
        )
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(
            runtime_handoff.HandoffError,
            match="Sensitive archive member is forbidden",
        ):
            runtime_handoff.safe_members(archive)


def test_pre_import_backup_excludes_sensitive_names(tmp_path: Path) -> None:
    allowed = tmp_path / "data/state/allowed.json"
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text("{}\n", encoding="utf-8")
    for relative in (
        "data/state/KEYS",
        "data/state/ACC GMAIL",
        "data/state/nested/.env",
        "data/state/nested/.env.cloud",
        "data/state/nested/KEYS",
        "data/state/nested/ACC GMAIL",
    ):
        sensitive = tmp_path / relative
        sensitive.parent.mkdir(parents=True, exist_ok=True)
        sensitive.write_text("synthetic-test-value", encoding="utf-8")

    backup = runtime_handoff._archive_existing_runtime(
        tmp_path,
        "synthetic-bundle",
    )

    with tarfile.open(backup, "r:gz") as archive:
        names = {member.name for member in archive.getmembers()}
    assert "data/state/allowed.json" in names
    assert not any(
        runtime_handoff._contains_secret_name(Path(name))
        for name in names
    )


def _legacy_bundle(
    tmp_path: Path,
    queue_bytes: bytes,
    *,
    expected_commit: str = "legacy-source-commit",
) -> tuple[Path, str]:
    bundle = tmp_path / "legacy-runtime.tgz"
    queue_relative = "data/shards/recipients_private_jc.csv"
    queue_rows = max(0, len(queue_bytes.decode("utf-8").splitlines()) - 1)
    manifest = {
        "schema_version": 1,
        "created_at_utc": "2026-07-28T21:10:05+00:00",
        "source_root": "/home/jc/email-automation",
        "target_root": "/Users/test/emailautomation",
        "expected_commit": expected_commit,
        "files": [
            {
                "path": queue_relative,
                "classification": "REQUIRED_RUNTIME",
                "size": len(queue_bytes),
                "sha256": runtime_handoff.hashlib.sha256(queue_bytes).hexdigest(),
                "source_sha256": runtime_handoff.hashlib.sha256(queue_bytes).hexdigest(),
                "method": "byte_copy",
            }
        ],
        "queue_row_counts": {"recipients_private_jc.csv": queue_rows},
    }
    with tarfile.open(bundle, "w:gz") as archive:
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest_bytes)
        archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
        for name in ("runtime", "runtime/data", "runtime/data/shards"):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
        queue_info = tarfile.TarInfo(f"runtime/{queue_relative}")
        queue_info.size = len(queue_bytes)
        archive.addfile(queue_info, io.BytesIO(queue_bytes))
    return bundle, runtime_handoff.sha256_file(bundle)


@pytest.fixture
def emergency_fixture(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.test")
    _run(repo, "git", "config", "user.name", "Test")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "fixture")
    emails = [
        "one@example.test",
        "two@example.test",
        "three@example.test",
    ]
    _write_runtime(repo, emails)
    stale_snapshot = {
        "checked_path": (
            "data/state/backups/staged_batches/dispatch_20260720_194207/leads.csv"
        ),
        "intended_source_path": (
            "data/state/backups/staged_batches/dispatch_20260720_194207/"
            "leads_triaged_keep.csv"
        ),
        "triaged_keep_path": (
            "data/state/backups/staged_batches/dispatch_20260720_194207/"
            "leads_triaged_keep.csv"
        ),
        "triaged_reject_path": (
            "data/state/backups/staged_batches/dispatch_20260720_194207/"
            "leads_triaged_reject.csv"
        ),
        "preview_id": "stale-preview",
    }
    snapshot_path = repo / "data/state/active_campaign_snapshot.json"
    snapshot_path.write_text(json.dumps(stale_snapshot), encoding="utf-8")
    for name in (
        "private_jc_message_preview.csv",
        "private_jc_message_preview_validated.csv",
    ):
        path = repo / "data/message_previews" / name
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    (repo / "data/message_previews/private_jc_message_preview_summary.txt").write_text(
        "total rows: 1\npassed rows: 1\nfailed rows: 0\n",
        encoding="utf-8",
    )
    queue_path = repo / "data/shards/recipients_private_jc.csv"
    bundle, bundle_sha = _legacy_bundle(tmp_path, queue_path.read_bytes())
    fingerprint = runtime_handoff._read_queue_state(
        queue_path, "private_jc"
    )["fingerprint"]
    monkeypatch.setenv("ASTRA_MACHINE_ID", "mac")
    monkeypatch.setattr(runtime_handoff.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    return {
        "repo": repo,
        "bundle": bundle,
        "bundle_sha": bundle_sha,
        "commit": "legacy-source-commit",
        "rows": len(emails),
        "fingerprint": fingerprint,
        "queue_path": queue_path,
        "snapshot_path": snapshot_path,
        "stale_snapshot": stale_snapshot,
    }


def _emergency_run(fixture: dict, **overrides):
    arguments = {
        "machine": "mac",
        "profile": "private_jc",
        "reason": "WSL source machine inaccessible",
        "expected_bundle_sha256": fixture["bundle_sha"],
        "expected_source_commit": fixture["commit"],
        "expected_rows": fixture["rows"],
        "expected_queue_fingerprint": fixture["fingerprint"],
    }
    arguments.update(overrides)
    return runtime_handoff.emergency_takeover(
        fixture["repo"],
        fixture["bundle"],
        **arguments,
    )


def _write_emergency_progress_runtime(
    tmp_path: Path,
    *,
    source_rows: int = 8,
    preview_removed: int = 1,
    progress_removed: int = 2,
) -> dict[str, object]:
    repo = tmp_path / "emergency-progress-repo"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.test")
    _run(repo, "git", "config", "user.name", "Test")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "fixture")

    emails = [
        f"recipient-{index:04d}@example.test"
        for index in range(source_rows)
    ]
    _write_runtime(repo, emails)
    queue_path = repo / "data/shards/recipients_private_jc.csv"
    source_bytes = queue_path.read_bytes()
    takeover_id = "emergency_progress_fixture"
    takeover_root = (
        repo
        / "data/state/emergency_takeovers"
        / takeover_id
    )
    takeover_root.mkdir(parents=True)
    source_paths = {
        "checked": takeover_root / "checked.csv",
        "intended_source": takeover_root / "intended_source.csv",
        "triaged_keep": takeover_root / "triaged_keep.csv",
        "triaged_reject": takeover_root / "triaged_reject.csv",
    }
    for key in ("checked", "intended_source", "triaged_keep"):
        source_paths[key].write_bytes(source_bytes)
    source_paths["triaged_reject"].write_text(
        "Email,FirstName,BookTitle\n",
        encoding="utf-8",
    )

    def source_record(path: Path) -> dict[str, object]:
        return {
            "path": path.relative_to(repo).as_posix(),
            "sha256": runtime_handoff.sha256_file(path),
            "size": path.stat().st_size,
            "row_count": runtime_handoff._csv_count(path),
            "email_fingerprint": runtime_handoff._email_fingerprint(
                runtime_handoff._read_email_set(path)
            ),
        }

    source_files = {
        key: source_record(path)
        for key, path in source_paths.items()
    }
    provenance_path = takeover_root / "provenance_manifest.json"
    provenance = {
        "schema_version": 1,
        "takeover_id": takeover_id,
        "machine_id": "mac",
        "profile": "private_jc",
        "status": "awaiting_preview_validation",
        "preview_validation_mode": "astra_visual",
        "queue_path": "data/shards/recipients_private_jc.csv",
        "queue_row_count": source_rows,
        "queue_unique_count": source_rows,
        "queue_fingerprint": source_files["intended_source"][
            "email_fingerprint"
        ],
        "generated_sources": source_files,
    }
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    snapshot = {
        "schema_version": 2,
        "snapshot_type": "emergency_takeover",
        "takeover_id": takeover_id,
        "profile": "private_jc",
        "status": "awaiting_preview_validation",
        "checked_path": source_files["checked"]["path"],
        "intended_source_path": source_files["intended_source"]["path"],
        "triaged_keep_path": source_files["triaged_keep"]["path"],
        "triaged_reject_path": source_files["triaged_reject"]["path"],
        "provenance_manifest_path": (
            provenance_path.relative_to(repo).as_posix()
        ),
        "files": source_files,
    }
    (repo / "data/state/active_campaign_snapshot.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    preview_emails = emails[preview_removed:]
    current_emails = preview_emails[progress_removed:]
    _write_preview_fixture(repo, preview_emails)
    queue_path.write_text(
        "Email,FirstName,BookTitle\n"
        + "".join(
            f"{email},Test,Book\n"
            for email in current_emails
        ),
        encoding="utf-8",
    )
    removed_emails = emails[: preview_removed + progress_removed]
    terminal_lines = []
    for index, email in enumerate(removed_emails):
        if index >= len(removed_emails) - 2:
            terminal_lines.append(
                "2026-07-30T18:10:05Z,"
                f"{email},SKIP,"
                "event_type=SKIPPED_ALREADY_SENT_AUTHORITATIVE\n"
            )
        else:
            terminal_lines.append(
                f"2026-07-30T18:10:04Z,{email},SENT,"
                "campaign_type=cold\n"
            )
    (repo / "data/logs/private_jc_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n"
        + "".join(terminal_lines),
        encoding="utf-8",
    )
    return {
        "repo": repo,
        "emails": emails,
        "preview_emails": preview_emails,
        "current_emails": current_emails,
        "removed_emails": removed_emails,
        "queue_path": queue_path,
        "preview_dir": repo / "data/message_previews",
        "log_path": repo / "data/logs/private_jc_log.csv",
    }


def _run_private_jc_preflight(repo: Path) -> str:
    shards = repo / "data/shards"
    logs = repo / "data/logs"
    state = repo / "data/state"
    output = io.StringIO()
    with (
        patch.object(settings, "APP_ROOT", repo),
        patch.object(settings, "SHARDS_DIR", shards),
        patch.object(settings, "LOGS_DIR", logs),
        patch.object(settings, "STATE_DIR", state),
        patch.object(send_shard, "ROOT", repo),
        patch.object(send_shard, "SHARDS_DIR", shards),
        patch.object(send_shard, "LOGS_DIR", logs),
        patch.object(send_shard, "STATE_DIR", state),
        patch.object(
            send_shard,
            "DEFAULT_UNSUB_CSV",
            state / "unsubscribed.csv",
        ),
        patch.object(
            send_shard,
            "DEFAULT_SUPPRESS_CSV",
            state / "suppressed.csv",
        ),
        patch.object(
            send_shard,
            "DEFAULT_SENDGRID_SUPPRESSION_CSV",
            state / "sendgrid_suppressions.csv",
        ),
        patch.object(
            send_shard,
            "send_via_sendgrid",
            side_effect=AssertionError("preflight must not submit"),
        ),
        patch.object(
            send_shard,
            "smtp_login",
            side_effect=AssertionError("preflight must not authenticate"),
        ),
        patch.object(
            sys,
            "argv",
            ["send_shard.py", "--profile", "private_jc", "--preflight"],
        ),
        redirect_stdout(output),
    ):
        send_shard.main()
    return output.getvalue()


def test_emergency_verified_bundle_matching_queue_creates_immutable_source_snapshot(
    emergency_fixture,
):
    fixture = emergency_fixture
    queue_bytes = fixture["queue_path"].read_bytes()
    log_before = (fixture["repo"] / "data/logs/private_jc_log.csv").read_bytes()
    suppressed_before = (fixture["repo"] / "data/state/suppressed.csv").read_bytes()

    result = _emergency_run(fixture)

    assert result["status"] == "awaiting_preview_validation"
    assert result["authority_initialized"] is False
    assert result["sender_started"] is False
    assert result["activation_allowed"] is False
    assert "--profile private_jc" in result["next_required_action"]
    assert "--pitch-mode astra_visual" in result["next_required_action"]
    assert "--pitch-mode consignment" not in result["next_required_action"]
    takeover_root = Path(result["takeover_root"])
    snapshot = json.loads(fixture["snapshot_path"].read_text(encoding="utf-8"))
    assert snapshot["snapshot_type"] == "emergency_takeover"
    assert snapshot["status"] == "awaiting_preview_validation"
    for key in (
        "checked_path",
        "intended_source_path",
        "triaged_keep_path",
    ):
        assert (fixture["repo"] / snapshot[key]).read_bytes() == queue_bytes
        assert str(snapshot[key]).startswith(
            "data/state/emergency_takeovers/"
        )
    reject = fixture["repo"] / snapshot["triaged_reject_path"]
    assert reject.read_text(encoding="utf-8") == "Email\n"
    provenance = json.loads(
        (takeover_root / "provenance_manifest.json").read_text(encoding="utf-8")
    )
    assert provenance["status"] == "awaiting_preview_validation"
    assert provenance["preview_validation_mode"] == "astra_visual"
    assert provenance["queue_match_mode"] == "byte_for_byte"
    assert provenance["previous_campaign_snapshot_fingerprint"]
    assert (
        takeover_root / "previous_campaign/active_campaign_snapshot.json"
    ).is_file()
    assert not runtime_authority.authority_path(fixture["repo"]).exists()
    assert (fixture["repo"] / "data/logs/private_jc_log.csv").read_bytes() == log_before
    assert (fixture["repo"] / "data/state/suppressed.csv").read_bytes() == suppressed_before


def test_actual_legacy_suppression_schema_loads_with_aggregate_diagnostics(
    tmp_path,
):
    path = tmp_path / "suppressed.csv"
    path.write_text(
        "Email\n"
        "blocked@example.test\n"
        "legacy-opaque-suppression-token\n"
        "local@internal\n",
        encoding="utf-8",
    )

    emails, diagnostics = load_suppression_email_tokens(path)

    assert emails == {"blocked@example.test", "local@internal"}
    assert diagnostics == {
        "schema": {
            "headers": ["Email"],
            "email_field": "Email",
            "metadata_fields": [],
        },
        "total_rows": 3,
        "valid_suppression_emails": 2,
        "blank_email_rows": 0,
        "malformed_email_rows": 0,
        "non_address_legacy_rows": 1,
        "duplicate_email_rows": 0,
    }


def test_suppression_metadata_and_blank_email_cells_are_not_email_values(tmp_path):
    path = tmp_path / "suppressed.csv"
    path.write_text(
        "Email,TimestampUTC,Reason,Provider,Hash,Status\n"
        "blocked@example.test,2026-07-30T00:00:00Z,bad@@metadata,sendgrid,"
        "not-an-email,SUPPRESSED\n"
        ",2026-07-30T00:01:00Z,manual,private,opaque-hash,ACTIVE\n",
        encoding="utf-8",
    )

    emails, diagnostics = load_suppression_email_tokens(path)

    assert emails == {"blocked@example.test"}
    assert diagnostics["schema"]["metadata_fields"] == [
        "TimestampUTC",
        "Reason",
        "Provider",
        "Hash",
        "Status",
    ]
    assert diagnostics["total_rows"] == 2
    assert diagnostics["valid_suppression_emails"] == 1
    assert diagnostics["blank_email_rows"] == 1
    assert diagnostics["malformed_email_rows"] == 0


def test_malformed_value_in_suppression_email_column_blocks_without_writes(
    emergency_fixture,
):
    fixture = emergency_fixture
    suppression_path = fixture["repo"] / "data/state/suppressed.csv"
    suppression_path.write_text("Email\nbad@@example.test\n", encoding="utf-8")
    snapshot_before = fixture["snapshot_path"].read_bytes()
    suppression_before = suppression_path.read_bytes()

    with pytest.raises(runtime_handoff.HandoffError, match="malformed email row"):
        _emergency_run(fixture)

    assert fixture["snapshot_path"].read_bytes() == snapshot_before
    assert suppression_path.read_bytes() == suppression_before
    assert not runtime_authority.authority_path(fixture["repo"]).exists()
    assert not (fixture["repo"] / runtime_handoff.EMERGENCY_TAKEOVER_ROOT).exists()


@pytest.mark.parametrize(
    "payload",
    [
        "TimestampUTC,Reason\n2026-07-30T00:00:00Z,manual\n",
        "Email,email\nblocked@example.test,other@example.test\n",
        'Email,Reason\n"unterminated,manual\n',
    ],
)
def test_structurally_invalid_suppression_csv_blocks_takeover(
    emergency_fixture,
    payload,
):
    fixture = emergency_fixture
    suppression_path = fixture["repo"] / "data/state/suppressed.csv"
    suppression_path.write_text(payload, encoding="utf-8")
    snapshot_before = fixture["snapshot_path"].read_bytes()

    with pytest.raises(runtime_handoff.HandoffError, match="structurally invalid"):
        _emergency_run(fixture)

    assert fixture["snapshot_path"].read_bytes() == snapshot_before
    assert not runtime_authority.authority_path(fixture["repo"]).exists()


def test_unreadable_suppression_path_blocks_takeover(emergency_fixture):
    fixture = emergency_fixture
    suppression_path = fixture["repo"] / "data/state/suppressed.csv"
    suppression_path.unlink()
    suppression_path.mkdir()
    snapshot_before = fixture["snapshot_path"].read_bytes()

    with pytest.raises(runtime_handoff.HandoffError, match="structurally invalid"):
        _emergency_run(fixture)

    assert fixture["snapshot_path"].read_bytes() == snapshot_before
    assert not runtime_authority.authority_path(fixture["repo"]).exists()


def test_preview_validation_mode_is_derived_from_profile_pitch():
    assert runtime_handoff._profile_validation_mode("private_jc") == "astra_visual"
    assert runtime_handoff._profile_validation_mode("sendgrid_annette") == "consignment"
    assert "--pitch-mode astra_visual" in runtime_handoff._emergency_next_action(
        "private_jc"
    )
    assert "--pitch-mode consignment" in runtime_handoff._emergency_next_action(
        "sendgrid_annette"
    )


def test_controlled_sendgrid_profile_is_literal_eval_handoff_safe():
    profile = runtime_handoff._profile_runtime_layout()["sendgrid_controlled_test"]

    assert profile["recipient_allowlist"] == "bebelyndcuriana@gmail.com"
    assert profile["csv"] == "recipients_sendgrid_controlled_test.csv"
    assert profile["log"] == "sendgrid_controlled_test_log.csv"
    assert profile["max_total"] == 1
    assert profile["max_per_run"] == 1
    assert profile["repeat"] is False
    assert profile["dashboard_manual_only"] is True


def test_controlled_sendgrid_preview_uses_exact_manual_lane_safety(tmp_path):
    recipient = "bebelyndcuriana@gmail.com"
    queue = _write_controlled_sendgrid_runtime(tmp_path, [recipient])
    queue_state = runtime_handoff._read_queue_state(
        queue,
        "sendgrid_controlled_test",
    )

    preview = runtime_handoff._preview_safety(
        tmp_path,
        "sendgrid_controlled_test",
        queue,
        queue_state,
    )

    assert preview["safe"] is True
    assert preview["failed_predicates"] == []
    assert preview["campaign_match"]["safe"] is True
    assert preview["campaign_match"]["applicability"] == "controlled_profile"
    assert preview["campaign_match"]["snapshot_type"] == "controlled_test"
    assert preview["verified_emergency_queue_progress"] is False


def test_controlled_sendgrid_recompute_skips_only_campaign_source_lineage(
    tmp_path,
):
    recipient = "bebelyndcuriana@gmail.com"
    _write_controlled_sendgrid_runtime(tmp_path, [recipient])

    safety = runtime_handoff.recompute_queue_safety(tmp_path)

    assert safety["safe"] is True
    assert safety["unsafe_reasons"] == []
    assert safety["active_intended_profiles"] == [
        "sendgrid_controlled_test"
    ]
    profile = safety["profiles"][0]
    assert profile["source_lineage_applicable"] is False
    assert profile["outside_checked_output_count"] == 0
    assert profile["outside_intended_source_count"] == 0
    assert profile["reject_overlap_count"] == 0
    assert profile["preview"]["safe"] is True


def test_controlled_sendgrid_preview_rejects_wrong_recipient(tmp_path):
    queue = _write_controlled_sendgrid_runtime(
        tmp_path,
        ["wrong@example.test"],
    )
    queue_state = runtime_handoff._read_queue_state(
        queue,
        "sendgrid_controlled_test",
    )

    preview = runtime_handoff._preview_safety(
        tmp_path,
        "sendgrid_controlled_test",
        queue,
        queue_state,
    )

    assert preview["safe"] is False
    assert "controlled_recipient_allowlist_exact" in preview["failed_predicates"]


def test_controlled_sendgrid_preview_rejects_queue_count_other_than_one(tmp_path):
    queue = _write_controlled_sendgrid_runtime(
        tmp_path,
        [
            "bebelyndcuriana@gmail.com",
            "second@example.test",
        ],
    )
    queue_state = runtime_handoff._read_queue_state(
        queue,
        "sendgrid_controlled_test",
    )

    preview = runtime_handoff._preview_safety(
        tmp_path,
        "sendgrid_controlled_test",
        queue,
        queue_state,
    )

    assert preview["safe"] is False
    assert "controlled_queue_count_one" in preview["failed_predicates"]


@pytest.mark.parametrize(
    ("emails", "expected_predicate"),
    [
        (["wrong@example.test"], "controlled_recipient_allowlist_exact"),
        (
            [
                "bebelyndcuriana@gmail.com",
                "second@example.test",
            ],
            "controlled_queue_count_one",
        ),
    ],
)
def test_controlled_sendgrid_recompute_retains_exact_queue_invariants(
    tmp_path,
    emails,
    expected_predicate,
):
    _write_controlled_sendgrid_runtime(tmp_path, emails)

    safety = runtime_handoff.recompute_queue_safety(tmp_path)

    assert safety["safe"] is False
    assert expected_predicate in safety["profiles"][0]["preview"][
        "failed_predicates"
    ]


@pytest.mark.parametrize(
    ("blocked_by", "expected_predicate"),
    [
        ("suppression", "controlled_queue_not_suppressed"),
        (
            "sent_history",
            "controlled_queue_no_sendgrid_family_sent_history",
        ),
        ("idempotency", "controlled_queue_no_idempotency_overlap"),
    ],
)
def test_controlled_sendgrid_preview_preserves_runtime_blocks(
    tmp_path,
    blocked_by,
    expected_predicate,
):
    recipient = "bebelyndcuriana@gmail.com"
    queue = _write_controlled_sendgrid_runtime(tmp_path, [recipient])
    if blocked_by == "suppression":
        (tmp_path / "data/state/suppressed.csv").write_text(
            f"Email\n{recipient}\n",
            encoding="utf-8",
        )
    elif blocked_by == "sent_history":
        (tmp_path / "data/logs/sendgrid_controlled_test_log.csv").write_text(
            "TimestampUTC,Email,Status,Info\n"
            f"2026-08-10T00:00:00Z,{recipient},SENT,controlled test\n",
            encoding="utf-8",
        )
    else:
        with sqlite3.connect(
            tmp_path / "data/state/send_idempotency.sqlite3"
        ) as db:
            db.execute(
                "INSERT INTO send_reservations "
                "(campaign_id, provider, email, profile) VALUES (?, ?, ?, ?)",
                ("cold", "sendgrid", recipient, "sendgrid_controlled_test"),
            )
    queue_state = runtime_handoff._read_queue_state(
        queue,
        "sendgrid_controlled_test",
    )

    preview = runtime_handoff._preview_safety(
        tmp_path,
        "sendgrid_controlled_test",
        queue,
        queue_state,
    )

    assert preview["safe"] is False
    assert expected_predicate in preview["failed_predicates"]


def test_normal_sendgrid_preview_still_requires_campaign_lineage(tmp_path):
    recipient = "normal@example.test"
    queue = tmp_path / "data/shards/recipients_sendgrid_1.csv"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(
        "Email,FirstName,BookTitle,CampaignType\n"
        f"{recipient},Test,Book,cold\n",
        encoding="utf-8",
    )
    _write_profile_preview_fixture(
        tmp_path,
        "sendgrid_annette",
        [recipient],
    )
    queue_state = runtime_handoff._read_queue_state(
        queue,
        "sendgrid_annette",
    )

    preview = runtime_handoff._preview_safety(
        tmp_path,
        "sendgrid_annette",
        queue,
        queue_state,
    )

    assert preview["safe"] is False
    assert "active_campaign_state_exists" in preview["failed_predicates"]


def test_normal_sendgrid_recompute_still_requires_campaign_source_lineage(
    tmp_path,
):
    recipient = "normal@example.test"
    queue = tmp_path / "data/shards/recipients_sendgrid_1.csv"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(
        "Email,FirstName,BookTitle,CampaignType\n"
        f"{recipient},Test,Book,cold\n",
        encoding="utf-8",
    )
    _write_profile_preview_fixture(
        tmp_path,
        "sendgrid_annette",
        [recipient],
    )

    safety = runtime_handoff.recompute_queue_safety(tmp_path)

    assert safety["safe"] is False
    assert "queue source validation failures" in safety["unsafe_reasons"]
    profile = safety["profiles"][0]
    assert profile["source_lineage_applicable"] is True
    assert profile["outside_checked_output_count"] == 1
    assert profile["outside_intended_source_count"] == 1


def test_unknown_profile_pitch_validation_mode_refuses(monkeypatch):
    monkeypatch.setattr(
        runtime_handoff,
        "_profile_runtime_layout",
        lambda: {"custom": {"pitch": "unmapped_pitch"}},
    )

    with pytest.raises(runtime_handoff.HandoffError, match="no known mode mapping"):
        runtime_handoff._emergency_next_action("custom")


def test_emergency_bundle_checksum_mismatch_refuses_without_writes(emergency_fixture):
    fixture = emergency_fixture
    snapshot_before = fixture["snapshot_path"].read_bytes()
    with pytest.raises(runtime_handoff.HandoffError, match="SHA-256 mismatch"):
        _emergency_run(fixture, expected_bundle_sha256="0" * 64)
    assert fixture["snapshot_path"].read_bytes() == snapshot_before
    assert not (fixture["repo"] / runtime_handoff.EMERGENCY_TAKEOVER_ROOT).exists()


def test_emergency_current_queue_differs_from_verified_bundle(emergency_fixture):
    fixture = emergency_fixture
    fixture["queue_path"].write_text(
        "Email,FirstName,BookTitle\n"
        "one@example.test,Test,Book\n"
        "two@example.test,Test,Book\n"
        "different@example.test,Test,Book\n",
        encoding="utf-8",
    )
    with pytest.raises(runtime_handoff.HandoffError, match="fingerprint mismatch"):
        _emergency_run(fixture)
    assert not (fixture["repo"] / runtime_handoff.EMERGENCY_TAKEOVER_ROOT).exists()


def test_emergency_authority_already_exists_refuses(emergency_fixture):
    fixture = emergency_fixture
    path = runtime_authority.authority_path(fixture["repo"])
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(runtime_handoff.HandoffError, match="authority already exists"):
        _emergency_run(fixture)


def test_emergency_process_blocker_refuses(emergency_fixture, monkeypatch):
    fixture = emergency_fixture
    monkeypatch.setattr(
        runtime_handoff,
        "process_blockers",
        lambda: ["123 workflow: important_leads_workflow.py"],
    )
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        _emergency_run(fixture)


def test_emergency_duplicate_recipient_refuses(emergency_fixture, tmp_path):
    fixture = emergency_fixture
    duplicate = (
        "Email,FirstName,BookTitle\n"
        "one@example.test,Test,Book\n"
        "one@example.test,Test,Book\n"
        "three@example.test,Test,Book\n"
    ).encode("utf-8")
    fixture["queue_path"].write_bytes(duplicate)
    bundle, bundle_sha = _legacy_bundle(tmp_path, duplicate)
    fixture["bundle"] = bundle
    fixture["bundle_sha"] = bundle_sha
    fixture["fingerprint"] = runtime_handoff._read_queue_state(
        fixture["queue_path"], "private_jc"
    )["fingerprint"]
    with pytest.raises(runtime_handoff.HandoffError, match="unique recipient rows"):
        _emergency_run(fixture)


@pytest.mark.parametrize(
    ("state_file", "error_field"),
    [
        ("suppressed.csv", "suppression_overlap_count=1"),
        ("unsubscribed.csv", "unsubscribe_overlap_count=1"),
    ],
)
def test_emergency_suppression_and_unsubscribe_overlap_refuse(
    emergency_fixture,
    state_file,
    error_field,
):
    fixture = emergency_fixture
    (fixture["repo"] / "data/state" / state_file).write_text(
        "Email\none@example.test\n",
        encoding="utf-8",
    )
    with pytest.raises(runtime_handoff.HandoffError, match=error_field):
        _emergency_run(fixture)


def test_emergency_authoritative_sent_log_overlap_refuses(emergency_fixture):
    fixture = emergency_fixture
    (fixture["repo"] / "data/logs/private_jc_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n"
        "2026-07-01T00:00:00Z,one@example.test,SENT,ok\n",
        encoding="utf-8",
    )
    with pytest.raises(
        runtime_handoff.HandoffError,
        match="authoritative_sent_overlap_count=1",
    ):
        _emergency_run(fixture)


def test_emergency_current_idempotency_and_active_reservation_refuse(
    emergency_fixture,
):
    fixture = emergency_fixture
    database = fixture["repo"] / "data/state/send_idempotency.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute(
            """
            CREATE TABLE send_reservations (
                campaign_id TEXT,
                provider TEXT,
                email TEXT,
                profile TEXT,
                status TEXT
            )
            """
        )
        db.execute(
            "INSERT INTO send_reservations VALUES (?, ?, ?, ?, ?)",
            ("cold", "private", "one@example.test", "private_jc", "reserved"),
        )
    with pytest.raises(
        runtime_handoff.HandoffError,
        match=(
            "current_campaign_idempotency_overlap_count=1.*"
            "active_reservation_overlap_count=1"
        ),
    ):
        _emergency_run(fixture)


def test_emergency_role_filter_violation_refuses(emergency_fixture, tmp_path):
    fixture = emergency_fixture
    role_queue = (
        "Email,FirstName,BookTitle\n"
        "info@example.test,Test,Book\n"
        "two@example.test,Test,Book\n"
        "three@example.test,Test,Book\n"
    ).encode("utf-8")
    fixture["queue_path"].write_bytes(role_queue)
    bundle, bundle_sha = _legacy_bundle(tmp_path, role_queue)
    fixture["bundle"] = bundle
    fixture["bundle_sha"] = bundle_sha
    fixture["fingerprint"] = runtime_handoff._read_queue_state(
        fixture["queue_path"], "private_jc"
    )["fingerprint"]
    with pytest.raises(
        runtime_handoff.HandoffError,
        match="role_filter_violation_count=1",
    ):
        _emergency_run(fixture)


def test_emergency_valid_reject_source_overlap_refuses(emergency_fixture):
    fixture = emergency_fixture
    (fixture["repo"] / "_important/leads_triaged_reject.csv").write_text(
        "Email\none@example.test\n",
        encoding="utf-8",
    )
    with pytest.raises(runtime_handoff.HandoffError, match="reject_overlap_count=1"):
        _emergency_run(fixture)


def test_emergency_success_leaves_stale_preview_as_only_blocker(emergency_fixture):
    fixture = emergency_fixture
    result = _emergency_run(fixture)
    safety = runtime_handoff.recompute_queue_safety(fixture["repo"])
    assert safety["unsafe_reasons"] == [
        "active profile preview is stale or invalid"
    ]
    assert safety["profiles"][0]["preview"]["queue_row_count"] == fixture["rows"]
    assert safety["profiles"][0]["preview"]["preview_row_count"] == 1
    assert result["activation_allowed"] is False


def test_emergency_partial_write_failure_rolls_back_snapshot_and_directory(
    emergency_fixture,
):
    fixture = emergency_fixture
    snapshot_before = fixture["snapshot_path"].read_bytes()

    def fail_after_snapshot(phase, _path):
        if phase == "after_snapshot_replace":
            raise OSError("synthetic emergency partial write")

    with pytest.raises(OSError, match="synthetic emergency partial"):
        _emergency_run(fixture, write_hook=fail_after_snapshot)
    assert fixture["snapshot_path"].read_bytes() == snapshot_before
    takeover_parent = fixture["repo"] / runtime_handoff.EMERGENCY_TAKEOVER_ROOT
    assert not takeover_parent.exists() or not list(takeover_parent.iterdir())
    assert not runtime_authority.authority_path(fixture["repo"]).exists()


def test_emergency_never_starts_sender_or_initializes_authority(
    emergency_fixture,
    monkeypatch,
):
    fixture = emergency_fixture
    initialize = patch.object(
        runtime_handoff,
        "initialize_authority",
        side_effect=AssertionError("must not initialize authority"),
    )
    write_authority = patch.object(
        runtime_handoff,
        "write_authority",
        side_effect=AssertionError("must not write authority"),
    )
    with initialize as initialize_mock, write_authority as write_mock:
        result = _emergency_run(fixture)
    initialize_mock.assert_not_called()
    write_mock.assert_not_called()
    assert result["sender_started"] is False
    assert not runtime_authority.authority_path(fixture["repo"]).exists()


def test_verify_normal_exact_commit_succeeds_without_compatibility_mapping(
    repos,
    tmp_path,
    monkeypatch,
):
    windows, mac = repos
    monkeypatch.setenv(
        runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV,
        "relative-path-must-not-be-read.json",
    )
    monkeypatch.setattr(
        runtime_handoff,
        "_load_commit_compatibility_mappings",
        lambda: (_ for _ in ()).throw(
            AssertionError("exact commit must not read compatibility configuration")
        ),
    )
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")

    result = runtime_handoff.verify_runtime_bundle(mac, bundle, machine="mac")

    assert result["commit_compatibility"]["mode"] == "exact_commit"


def test_legacy_compatibility_blank_environment_refuses(
    legacy_compatibility_case,
    monkeypatch,
):
    case = legacy_compatibility_case
    monkeypatch.setenv(runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV, "   ")

    with pytest.raises(runtime_handoff.HandoffError, match="not configured"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_relative_path_refuses(
    legacy_compatibility_case,
    monkeypatch,
):
    case = legacy_compatibility_case
    monkeypatch.setenv(
        runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV,
        "relative-compatibility.json",
    )

    with pytest.raises(runtime_handoff.HandoffError, match="path must be absolute"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_directory_path_refuses(
    legacy_compatibility_case,
    tmp_path,
    monkeypatch,
):
    case = legacy_compatibility_case
    monkeypatch.setenv(runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV, str(tmp_path))

    with pytest.raises(runtime_handoff.HandoffError, match="regular file"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_direct_symlink_refuses(
    legacy_compatibility_case,
    tmp_path,
):
    case = legacy_compatibility_case
    target = _write_commit_compatibility(
        tmp_path / "secure-target.json",
        [_approved_mapping(case["destination_commit"])],
    )
    case["config"].symlink_to(target)

    with pytest.raises(runtime_handoff.HandoffError, match="unavailable or unsafe"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


@pytest.mark.parametrize(
    "mode",
    [0o620, 0o610, 0o604],
    ids=["group-writable", "group-executable", "world-accessible"],
)
def test_legacy_compatibility_insecure_permissions_refuse(
    legacy_compatibility_case,
    mode,
):
    case = legacy_compatibility_case
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(case["destination_commit"])],
    )
    case["config"].chmod(mode)

    with pytest.raises(runtime_handoff.HandoffError, match="group-writable"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_requires_o_nofollow(
    legacy_compatibility_case,
    monkeypatch,
):
    case = legacy_compatibility_case
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(case["destination_commit"])],
    )
    monkeypatch.delattr(runtime_handoff.os, "O_NOFOLLOW")

    with pytest.raises(runtime_handoff.HandoffError, match="O_NOFOLLOW support"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_path_replacement_uses_same_open_file_object(
    legacy_compatibility_case,
    tmp_path,
    monkeypatch,
):
    case = legacy_compatibility_case
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(case["destination_commit"])],
    )
    replacement = tmp_path / "replacement.json"
    replacement.write_text("{malformed replacement", encoding="utf-8")
    replacement.chmod(0o666)
    real_open = runtime_handoff.os.open
    opened_descriptors: list[int] = []

    def open_then_replace(path, flags, *args, **kwargs):
        if Path(path) != case["config"]:
            return real_open(path, flags, *args, **kwargs)
        descriptor = real_open(path, flags, *args, **kwargs)
        opened_descriptors.append(descriptor)
        case["config"].unlink()
        case["config"].symlink_to(replacement)
        return descriptor

    monkeypatch.setattr(runtime_handoff.os, "open", open_then_replace)

    result = runtime_handoff.verify_runtime_bundle(
        case["cloud"], case["bundle"], machine="cloud"
    )

    assert result["commit_compatibility"]["mode"] == "approved_legacy_source"
    assert case["config"].is_symlink()
    assert len(opened_descriptors) == 1
    with pytest.raises(OSError):
        runtime_handoff.os.fstat(opened_descriptors[0])


def test_verify_normal_commit_mismatch_refuses_without_mapping(
    repos,
    tmp_path,
    monkeypatch,
):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    real_git = runtime_handoff.git

    def mismatched_git(repo: Path, *args: str) -> str:
        if repo == mac and args == ("rev-parse", "HEAD"):
            return "f" * 40
        return real_git(repo, *args)

    monkeypatch.setattr(runtime_handoff, "git", mismatched_git)
    monkeypatch.delenv(runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV, raising=False)

    with pytest.raises(runtime_handoff.HandoffError, match="not configured"):
        runtime_handoff.verify_runtime_bundle(mac, bundle, machine="mac")


def test_approved_legacy_source_with_valid_secure_file_uses_identical_rules(
    legacy_compatibility_case,
    monkeypatch,
):
    case = legacy_compatibility_case
    real_run = runtime_handoff.subprocess.run
    commands: list[object] = []

    def recording_run(command, *args, **kwargs):
        commands.append(command)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(runtime_handoff.subprocess, "run", recording_run)
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(case["destination_commit"])],
    )

    verified = runtime_handoff.verify_runtime_bundle(
        case["cloud"],
        case["bundle"],
        machine="cloud",
    )
    received = runtime_handoff.import_runtime(
        case["cloud"],
        case["bundle"],
        machine="cloud",
    )

    assert verified["commit_compatibility"] == received["commit_compatibility"]
    assert received["commit_compatibility"]["mode"] == "approved_legacy_source"
    assert received["authority"]["expected_git_commit"] == case["destination_commit"]
    assert received["sender_started"] is False
    rendered_commands = "\n".join(
        " ".join(str(part) for part in command)
        if isinstance(command, (list, tuple))
        else str(command)
        for command in commands
    )
    assert "send_shard.py" not in rendered_commands
    assert "live_dashboard" not in rendered_commands
    assert "systemctl start" not in rendered_commands
    audit = json.loads(
        (
            case["cloud"]
            / runtime_handoff.LOCAL_STATE_DIR
            / runtime_handoff.LAST_IMPORT_NAME
        ).read_text(encoding="utf-8")
    )
    assert "commit_compatibility" not in audit


def test_legacy_interrupted_destination_requires_explicit_compatibility(
    legacy_compatibility_case,
):
    case = legacy_compatibility_case
    interrupted_commit = "e" * 40
    _write_commit_compatibility(
        case["config"],
        [
            _approved_mapping(
                case["destination_commit"],
                approved_interrupted_destination_commits=[interrupted_commit],
            )
        ],
    )
    runtime_authority.authority_path(case["cloud"]).unlink(missing_ok=True)
    runtime_authority.generation_floor_path(case["cloud"]).unlink(missing_ok=True)
    manifest, _authority = runtime_handoff.read_bundle_metadata(case["bundle"])
    runtime_authority.write_authority(
        case["cloud"],
        {
            "authorized_machine": "cloud",
            "generation": 1,
            "bundle_id": "legacy-placeholder-transaction",
            "source_machine": manifest["source_machine"],
            "target_machine": "cloud",
            "created_utc": runtime_authority.utc_now(),
            "expected_git_commit": interrupted_commit,
            "runtime_manifest_hash": "import-not-verified",
            "status": "import_in_progress",
        },
    )
    bundle_sha = runtime_handoff.sha256_file(case["bundle"])
    baseline = runtime_handoff._runtime_baseline_fingerprint(case["cloud"])

    result = runtime_handoff.import_runtime(
        case["cloud"],
        case["bundle"],
        machine="cloud",
        resume_expected_bundle_sha256=bundle_sha,
        resume_expected_baseline_fingerprint=baseline,
    )

    assert result["resumed"] is True
    assert result["authority"]["generation"] == 1
    assert result["authority"]["expected_git_commit"] == case["destination_commit"]
    assert result["commit_compatibility"][
        "approved_interrupted_destination_commits"
    ] == [interrupted_commit]


@pytest.mark.parametrize(
    "invalid",
    ["not-a-list", ["short"], ["e" * 40, "e" * 40]],
)
def test_interrupted_destination_compatibility_is_strict(
    legacy_compatibility_case,
    invalid,
):
    case = legacy_compatibility_case
    _write_commit_compatibility(
        case["config"],
        [
            _approved_mapping(
                case["destination_commit"],
                approved_interrupted_destination_commits=invalid,
            )
        ],
    )
    with pytest.raises(runtime_handoff.HandoffError):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


@pytest.mark.parametrize(
    "configured_destination",
    [
        "7649cc2f30924188636914e189b7798d1b08b09a",
        "f" * 40,
    ],
    ids=["old-hardcoded-destination", "different-destination"],
)
def test_legacy_compatibility_destination_must_equal_current_head(
    legacy_compatibility_case,
    configured_destination,
):
    case = legacy_compatibility_case
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(configured_destination)],
    )

    with pytest.raises(runtime_handoff.HandoffError, match="current HEAD"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"],
            case["bundle"],
            machine="cloud",
        )


@pytest.mark.parametrize(
    ("mapping_overrides", "bundle_overrides", "error"),
    [
        ({}, {"source_commit": "f" * 40}, "does not match"),
        ({"source_tree": "f" * 40}, {}, "source identity is not approved"),
        ({"source_machine": "windows-wsl"}, {}, "source identity is not approved"),
        ({"target_machine": "windows-wsl"}, {}, "source identity is not approved"),
        (
            {"source_machine": "cloud", "target_machine": "mac"},
            {},
            "source identity is not approved",
        ),
    ],
    ids=[
        "wrong-source-commit",
        "wrong-source-tree",
        "wrong-source-machine",
        "wrong-target-machine",
        "wrong-direction",
    ],
)
def test_legacy_compatibility_requires_every_exact_mapping_value(
    legacy_compatibility_case,
    tmp_path,
    mapping_overrides,
    bundle_overrides,
    error,
):
    case = legacy_compatibility_case
    bundle = case["bundle"]
    if bundle_overrides:
        bundle = _rewrite_bundle_identity(
            bundle,
            tmp_path / "wrong-bundle-identity.tgz",
            **bundle_overrides,
        )
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(case["destination_commit"], **mapping_overrides)],
    )

    with pytest.raises(runtime_handoff.HandoffError, match=error):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"],
            bundle,
            machine="cloud",
        )


def test_legacy_compatibility_absent_mapping_refuses(
    legacy_compatibility_case,
):
    case = legacy_compatibility_case
    _write_commit_compatibility(case["config"], [])

    with pytest.raises(runtime_handoff.HandoffError, match="mapping is absent"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


@pytest.mark.parametrize(
    "missing_field",
    ["source_tree", "approved_destination_commit"],
    ids=["missing-source-tree", "missing-destination"],
)
def test_legacy_compatibility_incomplete_mapping_refuses(
    legacy_compatibility_case,
    missing_field,
):
    case = legacy_compatibility_case
    mapping = _approved_mapping(case["destination_commit"])
    del mapping[missing_field]
    _write_commit_compatibility(case["config"], [mapping])

    with pytest.raises(runtime_handoff.HandoffError, match="incomplete or malformed"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_extra_json_field_refuses(
    legacy_compatibility_case,
):
    case = legacy_compatibility_case
    mapping = _approved_mapping(case["destination_commit"])
    mapping["unexpected_field"] = "refuse"
    _write_commit_compatibility(case["config"], [mapping])

    with pytest.raises(runtime_handoff.HandoffError, match="incomplete or malformed"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


@pytest.mark.parametrize(
    ("sha_field", "malformed_sha"),
    [
        ("source_commit", "14c3eaf79507"),
        ("approved_destination_commit", "14c3eaf79507"),
        ("approved_destination_commit", "A" * 40),
    ],
    ids=["partial-source-commit", "partial-destination", "uppercase-destination"],
)
def test_legacy_compatibility_malformed_sha_refuses(
    legacy_compatibility_case,
    sha_field,
    malformed_sha,
):
    case = legacy_compatibility_case
    mapping = _approved_mapping(
        case["destination_commit"],
        **{sha_field: malformed_sha},
    )
    _write_commit_compatibility(case["config"], [mapping])

    with pytest.raises(runtime_handoff.HandoffError, match="full lowercase Git SHA"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_malformed_mapping_refuses(
    legacy_compatibility_case,
):
    case = legacy_compatibility_case
    case["config"].write_text("{not-json", encoding="utf-8")
    case["config"].chmod(0o600)

    with pytest.raises(runtime_handoff.HandoffError, match="malformed"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_legacy_compatibility_duplicate_json_key_refuses(
    legacy_compatibility_case,
):
    case = legacy_compatibility_case
    mapping = json.dumps(_approved_mapping(case["destination_commit"]))
    case["config"].write_text(
        "{"
        f'"{runtime_handoff.COMMIT_COMPATIBILITY_ROOT_KEY}":[{mapping}],'
        f'"{runtime_handoff.COMMIT_COMPATIBILITY_ROOT_KEY}":[{mapping}]'
        "}",
        encoding="utf-8",
    )
    case["config"].chmod(0o600)

    with pytest.raises(runtime_handoff.HandoffError, match="duplicate key"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


@pytest.mark.parametrize(
    ("mapping_overrides", "error"),
    [
        ([{}, {}], "duplicated"),
        (
            [
                {},
                {"source_tree": "f" * 40},
            ],
            "conflict",
        ),
    ],
    ids=["duplicated-mapping", "conflicting-mapping"],
)
def test_legacy_compatibility_duplicate_or_conflicting_mapping_refuses(
    legacy_compatibility_case,
    mapping_overrides,
    error,
):
    case = legacy_compatibility_case
    mappings = [
        _approved_mapping(case["destination_commit"], **overrides)
        for overrides in mapping_overrides
    ]
    _write_commit_compatibility(case["config"], mappings)

    with pytest.raises(runtime_handoff.HandoffError, match=error):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], case["bundle"], machine="cloud"
        )


def test_arbitrary_same_tree_source_commit_refuses(
    legacy_compatibility_case,
    tmp_path,
):
    case = legacy_compatibility_case
    arbitrary_commit = "f" * 40
    bundle = _rewrite_bundle_identity(
        case["bundle"],
        tmp_path / "arbitrary-same-tree.tgz",
        source_commit=arbitrary_commit,
    )
    _write_commit_compatibility(
        case["config"],
        [
            _approved_mapping(
                case["destination_commit"],
                source_commit=arbitrary_commit,
            )
        ],
    )

    with pytest.raises(runtime_handoff.HandoffError, match="not approved"):
        runtime_handoff.verify_runtime_bundle(
            case["cloud"], bundle, machine="cloud"
        )


def test_approved_legacy_receive_rolls_back_runtime_if_activation_fails(
    legacy_compatibility_case,
    monkeypatch,
):
    case = legacy_compatibility_case
    original = (case["cloud"] / "data/shards/recipients_private_jc.csv").read_bytes()
    _write_commit_compatibility(
        case["config"],
        [_approved_mapping(case["destination_commit"])],
    )
    monkeypatch.setattr(
        runtime_handoff,
        "activate_import",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic activation failure")
        ),
    )

    with pytest.raises(RuntimeError, match="synthetic activation failure"):
        runtime_handoff.import_runtime(
            case["cloud"], case["bundle"], machine="cloud"
        )

    assert (
        case["cloud"] / "data/shards/recipients_private_jc.csv"
    ).read_bytes() == original
    assert runtime_authority.load_authority(case["cloud"])["status"] == "import_failed"


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


def test_windows_to_cloud_handoff_activates_only_cloud_authority(repos, tmp_path):
    windows, _mac = repos
    cloud = tmp_path / "cloud"
    _run(tmp_path, "git", "clone", "-q", str(windows), str(cloud))
    _write_runtime(cloud, ["old-cloud@example.test"])
    _set_inactive(cloud, "cloud")

    bundle = _export(windows, tmp_path, "cloud", "windows-wsl")
    result = runtime_handoff.import_runtime(cloud, bundle, machine="cloud")

    assert result["sender_started"] is False
    assert result["authority"]["authorized_machine"] == "cloud"
    assert result["authority"]["generation"] == 2
    assert runtime_authority.load_authority(windows)["status"] == (
        "handoff_in_progress"
    )
    with pytest.raises(runtime_authority.AuthorityError, match="handoff_in_progress"):
        runtime_authority.assert_send_authorized(
            windows,
            machine="windows-wsl",
        )
    assert runtime_authority.assert_send_authorized(
        cloud,
        machine="cloud",
    )["status"] == "active"


def _fresh_cloud_receive_target(repos, tmp_path: Path) -> tuple[Path, Path, bytes]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    windows, _mac = repos
    cloud = tmp_path / "fresh-cloud"
    _run(tmp_path, "git", "clone", "-q", str(windows), str(cloud))
    _write_runtime(cloud, ["old-cloud@example.test"])
    original = (cloud / "data/shards/recipients_private_jc.csv").read_bytes()
    runtime_authority.authority_path(cloud).unlink(missing_ok=True)
    runtime_authority.generation_floor_path(cloud).unlink(missing_ok=True)
    bundle = _export(windows, tmp_path, "cloud", "windows-wsl")
    return cloud, bundle, original


def _force_pre_extraction_failure(monkeypatch):
    real_staging = runtime_handoff._private_staging_directory
    failed = {"value": False}

    @contextmanager
    def controlled(repo: Path, *, prefix: str):
        if prefix == "receive-" and not failed["value"]:
            failed["value"] = True
            raise PermissionError("synthetic pre-extraction staging failure")
        with real_staging(repo, prefix=prefix) as staging:
            yield staging

    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", controlled)
    return real_staging


def test_interrupted_receive_resumes_same_transaction_and_generation(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, original = _fresh_cloud_receive_target(repos, tmp_path)
    real_staging = _force_pre_extraction_failure(monkeypatch)

    with pytest.raises(PermissionError, match="pre-extraction"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")

    interrupted = runtime_authority.load_authority(cloud)
    assert interrupted["status"] == "import_in_progress"
    assert interrupted["generation"] == 1
    with pytest.raises(runtime_authority.AuthorityError, match="import_in_progress"):
        runtime_authority.assert_send_authorized(cloud, machine="cloud")
    assert (cloud / "data/shards/recipients_private_jc.csv").read_bytes() == original
    layout = runtime_handoff._private_handoff_layout(cloud)
    assert not list(layout["staging"].iterdir())
    assert not list(layout["backups"].iterdir())
    transaction_path = runtime_handoff._transaction_path(
        cloud, interrupted["bundle_id"]
    )
    transaction = runtime_handoff._load_receive_transaction(transaction_path)
    transaction_id = transaction["transaction_id"]
    baseline = transaction["runtime_baseline_fingerprint"]

    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)
    result = runtime_handoff.import_runtime(cloud, bundle, machine="cloud")

    assert result["resumed"] is True
    assert result["transaction_id"] == transaction_id
    assert result["authority"]["status"] == "active"
    assert result["authority"]["generation"] == 1
    assert runtime_authority.assert_send_authorized(
        cloud, machine="cloud"
    )["status"] == "active"
    final_transaction = runtime_handoff._load_receive_transaction(transaction_path)
    assert final_transaction["status"] == "completed"
    assert final_transaction["runtime_baseline_fingerprint"] == baseline
    assert final_transaction["backup_created"] is True
    assert final_transaction["replacement_completed"] is True
    assert not list(layout["staging"].iterdir())
    assert Path(result["backup"]).is_file()


def test_legacy_interrupted_receive_requires_reviewed_bundle_and_baseline(
    repos, tmp_path
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    head = _run(cloud, "git", "rev-parse", "HEAD")
    manifest, _bundled = runtime_handoff.read_bundle_metadata(bundle)
    legacy_authority = {
        "authorized_machine": "cloud",
        "generation": 1,
        "bundle_id": "legacy-placeholder-transaction",
        "source_machine": manifest["source_machine"],
        "target_machine": "cloud",
        "created_utc": runtime_authority.utc_now(),
        "expected_git_commit": head,
        "runtime_manifest_hash": "import-not-verified",
        "status": "import_in_progress",
    }
    runtime_authority.write_authority(cloud, legacy_authority)
    bundle_sha = runtime_handoff.sha256_file(bundle)
    baseline = runtime_handoff._runtime_baseline_fingerprint(cloud)

    with pytest.raises(runtime_handoff.HandoffError, match="reviewed bundle SHA"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    assert runtime_authority.load_authority(cloud)["status"] == "import_in_progress"

    authority_during_replacement = {}

    def replace(repo: Path, extracted: Path) -> None:
        authority_during_replacement.update(runtime_authority.load_authority(repo))
        runtime_handoff._atomic_replace_runtime(repo, extracted)

    result = runtime_handoff.import_runtime(
        cloud,
        bundle,
        machine="cloud",
        replace_hook=replace,
        resume_expected_bundle_sha256=bundle_sha,
        resume_expected_baseline_fingerprint=baseline,
    )
    assert result["resumed"] is True
    assert result["authority"]["generation"] == 1
    assert result["authority"]["status"] == "active"
    assert authority_during_replacement == legacy_authority


def test_interrupted_receive_rejects_different_or_changed_bundle(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    real_staging = _force_pre_extraction_failure(monkeypatch)
    with pytest.raises(PermissionError):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)

    changed_sha = tmp_path / "same-identity-changed-sha.tgz"
    changed_sha.write_bytes(bundle.read_bytes() + b"synthetic trailing change")
    changed_sha.chmod(0o600)
    with pytest.raises(runtime_handoff.HandoffError, match="bundle_sha256"):
        runtime_handoff.import_runtime(cloud, changed_sha, machine="cloud")

    def change_bundle_id(stage: Path) -> None:
        for name in (
            runtime_handoff.MANIFEST_NAME,
            runtime_handoff.BUNDLE_AUTHORITY_NAME,
        ):
            path = stage / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["bundle_id"] = "different-synthetic-bundle"
            path.write_text(json.dumps(payload), encoding="utf-8")

    different = _rewrite_bundle(
        bundle, tmp_path / "different-bundle.tgz", change_bundle_id
    )
    with pytest.raises(runtime_handoff.HandoffError, match="different interrupted"):
        runtime_handoff.import_runtime(cloud, different, machine="cloud")


def test_receive_rejects_bundle_identity_path_traversal(repos, tmp_path):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)

    def unsafe_bundle_id(stage: Path) -> None:
        for name in (
            runtime_handoff.MANIFEST_NAME,
            runtime_handoff.BUNDLE_AUTHORITY_NAME,
        ):
            path = stage / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["bundle_id"] = "../../outside"
            path.write_text(json.dumps(payload), encoding="utf-8")

    unsafe = _rewrite_bundle(bundle, tmp_path / "unsafe-bundle-id.tgz", unsafe_bundle_id)
    with pytest.raises(runtime_handoff.HandoffError, match="identity is unsafe"):
        runtime_handoff.import_runtime(cloud, unsafe, machine="cloud")
    assert not (cloud.parent / "outside").exists()


def test_interrupted_receive_rejects_changed_manifest_generation_and_runtime(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    real_staging = _force_pre_extraction_failure(monkeypatch)
    with pytest.raises(PermissionError):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)

    def change_manifest(stage: Path) -> None:
        manifest_path = stage / runtime_handoff.MANIFEST_NAME
        authority_path = stage / runtime_handoff.BUNDLE_AUTHORITY_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        manifest["runtime_manifest_hash"] = "f" * 64
        authority["runtime_manifest_hash"] = "f" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        authority_path.write_text(json.dumps(authority), encoding="utf-8")

    changed_manifest = _rewrite_bundle(
        bundle, tmp_path / "changed-manifest.tgz", change_manifest
    )
    interrupted = runtime_authority.load_authority(cloud)
    transaction_path = runtime_handoff._transaction_path(
        cloud, interrupted["bundle_id"]
    )
    transaction = runtime_handoff._load_receive_transaction(transaction_path)
    original_bundle_sha = transaction["bundle_sha256"]
    transaction["bundle_sha256"] = runtime_handoff.sha256_file(changed_manifest)
    runtime_handoff._write_receive_transaction(cloud, transaction)
    with pytest.raises(runtime_handoff.HandoffError, match="manifest_hash"):
        runtime_handoff.import_runtime(cloud, changed_manifest, machine="cloud")

    def change_generation(stage: Path) -> None:
        manifest_path = stage / runtime_handoff.MANIFEST_NAME
        authority_path = stage / runtime_handoff.BUNDLE_AUTHORITY_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        manifest["source_generation"] += 1
        authority["generation"] += 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        authority_path.write_text(json.dumps(authority), encoding="utf-8")

    changed_generation = _rewrite_bundle(
        bundle, tmp_path / "changed-generation.tgz", change_generation
    )
    transaction["bundle_sha256"] = runtime_handoff.sha256_file(changed_generation)
    runtime_handoff._write_receive_transaction(cloud, transaction)
    with pytest.raises(runtime_handoff.HandoffError, match="source_generation"):
        runtime_handoff.import_runtime(cloud, changed_generation, machine="cloud")

    transaction["bundle_sha256"] = original_bundle_sha
    runtime_handoff._write_receive_transaction(cloud, transaction)
    (cloud / "data/state/synthetic-change.txt").write_text(
        "changed\n", encoding="utf-8"
    )
    with pytest.raises(runtime_handoff.HandoffError, match="runtime_baseline"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")


def test_interrupted_receive_rejects_changed_authority(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    real_staging = _force_pre_extraction_failure(monkeypatch)
    with pytest.raises(PermissionError):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)

    authority = runtime_authority.load_authority(cloud)
    authority["created_utc"] = "2099-01-01T00:00:00Z"
    runtime_authority.write_authority(cloud, authority)

    with pytest.raises(runtime_handoff.HandoffError, match="authority changed"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")


def test_interrupted_receive_rejects_changed_transaction_metadata(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    real_staging = _force_pre_extraction_failure(monkeypatch)
    with pytest.raises(PermissionError):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)

    interrupted = runtime_authority.load_authority(cloud)
    transaction_path = runtime_handoff._transaction_path(
        cloud, interrupted["bundle_id"]
    )
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    transaction["transaction_id"] = str(uuid.uuid4())
    transaction_path.write_text(json.dumps(transaction), encoding="utf-8")

    with pytest.raises(runtime_handoff.HandoffError, match="integrity check failed"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    assert runtime_authority.load_authority(cloud)["status"] == "import_in_progress"


def test_authority_and_generation_metadata_require_private_owner_and_mode(
    repos, monkeypatch
):
    repo, _mac = repos
    authority = runtime_authority.authority_path(repo)
    floor = runtime_authority.generation_floor_path(repo)

    authority.chmod(0o644)
    with pytest.raises(runtime_authority.AuthorityError, match="mode 0600"):
        runtime_authority.load_authority(repo)
    authority.chmod(0o600)

    floor.chmod(0o640)
    with pytest.raises(runtime_authority.AuthorityError, match="mode 0600"):
        runtime_authority.load_generation_floor(repo)
    floor.chmod(0o600)

    owner = authority.stat().st_uid
    monkeypatch.setattr(runtime_authority.os, "geteuid", lambda: owner + 1)
    with pytest.raises(runtime_authority.AuthorityError, match="wrong owner"):
        runtime_authority.load_authority(repo)
    with pytest.raises(runtime_authority.AuthorityError, match="wrong owner"):
        runtime_authority.load_generation_floor(repo)


def test_preimport_backup_is_mode_0600_from_creation(repos, tmp_path, monkeypatch):
    cloud, _bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    real_tar_open = runtime_handoff.tarfile.open
    observed_modes: list[int] = []

    def inspect_tar_open(*args, **kwargs):
        file_object = kwargs.get("fileobj")
        if file_object is not None and kwargs.get("mode") == "w:gz":
            observed_modes.append(stat.S_IMODE(os.fstat(file_object.fileno()).st_mode))
        return real_tar_open(*args, **kwargs)

    monkeypatch.setattr(runtime_handoff.tarfile, "open", inspect_tar_open)
    backup = runtime_handoff._archive_existing_runtime(
        cloud, "synthetic-private-backup"
    )

    assert observed_modes == [0o600]
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_receive_rejects_partial_backup_staging_residue_and_insecure_root(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    real_staging = _force_pre_extraction_failure(monkeypatch)
    with pytest.raises(PermissionError):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)
    manifest, _authority = runtime_handoff.read_bundle_metadata(bundle)
    layout = runtime_handoff._private_handoff_layout(cloud)
    backup = layout["backups"] / f"pre_import_{manifest['bundle_id']}.tgz"
    backup.write_bytes(b"partial")
    backup.chmod(0o600)
    with pytest.raises(runtime_handoff.HandoffError, match="partial or conflicting backup"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    backup.unlink()

    interrupted = runtime_authority.load_authority(cloud)
    transaction_path = runtime_handoff._transaction_path(
        cloud, interrupted["bundle_id"]
    )
    transaction = runtime_handoff._load_receive_transaction(transaction_path)
    transaction["replacement_started"] = True
    runtime_handoff._write_receive_transaction(cloud, transaction)
    with pytest.raises(runtime_handoff.HandoffError, match="mutation state"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    transaction["replacement_started"] = False
    runtime_handoff._write_receive_transaction(cloud, transaction)

    residue = layout["staging"] / "partial-residue"
    residue.mkdir(mode=0o700)
    with pytest.raises(runtime_handoff.HandoffError, match="staging contains residue"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    residue.rmdir()

    layout["root"].chmod(0o755)
    with pytest.raises(runtime_handoff.HandoffError, match="mode 0700"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")


def test_receive_rejects_cross_filesystem_staging_and_incompatible_resume_commit(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    layout = runtime_handoff._private_handoff_layout(cloud)
    with pytest.raises(runtime_handoff.HandoffError, match="different filesystem"):
        runtime_handoff._secure_directory(
            layout["staging"],
            create=False,
            expected_device=cloud.stat().st_dev + 1,
        )

    real_staging = _force_pre_extraction_failure(monkeypatch)
    with pytest.raises(PermissionError):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    monkeypatch.setattr(runtime_handoff, "_private_staging_directory", real_staging)
    _run(cloud, "git", "config", "user.email", "test@example.test")
    _run(cloud, "git", "config", "user.name", "Test")
    marker = cloud / "resume-code-change.txt"
    marker.write_text("synthetic code change\n", encoding="utf-8")
    _run(cloud, "git", "add", marker.name)
    _run(cloud, "git", "commit", "-qm", "synthetic incompatible receive code")
    monkeypatch.delenv(runtime_handoff.COMMIT_COMPATIBILITY_FILE_ENV, raising=False)
    with pytest.raises(runtime_handoff.HandoffError, match="not configured"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    assert runtime_authority.load_authority(cloud)["status"] == "import_in_progress"


def test_receive_rejects_symlink_root_insufficient_space_and_process_blocker(
    repos, tmp_path, monkeypatch
):
    cloud, bundle, _original = _fresh_cloud_receive_target(repos, tmp_path)
    root = cloud / runtime_handoff.LOCAL_STATE_DIR
    if root.exists():
        shutil.rmtree(root)
    outside = tmp_path / "outside-handoff"
    outside.mkdir(mode=0o700)
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(runtime_handoff.HandoffError, match="regular directory"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    root.unlink()

    root.mkdir(mode=0o700)
    staging_outside = tmp_path / "outside-staging"
    staging_outside.mkdir(mode=0o700)
    (root / runtime_handoff.IMPORT_STAGING_DIR_NAME).symlink_to(
        staging_outside, target_is_directory=True
    )
    with pytest.raises(runtime_handoff.HandoffError, match="regular directory"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    (root / runtime_handoff.IMPORT_STAGING_DIR_NAME).unlink()
    root.rmdir()

    real_disk_usage = runtime_handoff.shutil.disk_usage
    monkeypatch.setattr(
        runtime_handoff.shutil,
        "disk_usage",
        lambda _path: shutil._ntuple_diskusage(total=1, used=1, free=0),
    )
    with pytest.raises(runtime_handoff.HandoffError, match="Insufficient free space"):
        runtime_handoff.import_runtime(cloud, bundle, machine="cloud")
    assert runtime_authority.load_authority(cloud)["status"] == "import_in_progress"

    monkeypatch.setattr(runtime_handoff.shutil, "disk_usage", real_disk_usage)
    windows, _mac = repos
    blocked_parent = tmp_path / "blocked-case"
    blocked_parent.mkdir()
    blocked = blocked_parent / "fresh-cloud"
    _run(blocked_parent, "git", "clone", "-q", str(windows), str(blocked))
    _write_runtime(blocked, ["old-cloud@example.test"])
    runtime_authority.authority_path(blocked).unlink(missing_ok=True)
    runtime_authority.generation_floor_path(blocked).unlink(missing_ok=True)
    monkeypatch.setattr(
        runtime_handoff, "process_blockers", lambda: ["123 sender: send_shard.py"]
    )
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        runtime_handoff.import_runtime(blocked, bundle, machine="cloud")
    with pytest.raises(runtime_authority.AuthorityError, match="missing"):
        runtime_authority.load_authority(blocked)


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
    assert runtime_authority.load_authority(mac)["status"] == "inactive"


def test_blocker_result_is_shared_by_status_export_verify_and_receive(
    repos,
    tmp_path,
    monkeypatch,
):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    blocker = "202 dispatch: python3 /opt/astra/emailautomation/dispatch.py"
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [blocker])

    assert runtime_handoff.status(mac, machine="mac")["process_blockers"] == [
        blocker
    ]
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        runtime_handoff.export_runtime(
            mac,
            tmp_path / "blocked-export",
            "windows-wsl",
            machine="mac",
        )
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        runtime_handoff.verify_runtime_bundle(mac, bundle, machine="mac")
    with pytest.raises(runtime_handoff.HandoffError, match="still running"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")


def test_stale_generation_is_rejected_and_target_is_disabled(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    runtime_authority.write_generation_floor(mac, 2, "newer")
    with pytest.raises(runtime_handoff.HandoffError, match="Stale generation"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "inactive"


def test_reused_bundle_is_rejected_and_cannot_create_duplicate_authority(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    runtime_handoff.import_runtime(mac, bundle, machine="mac")
    with pytest.raises(runtime_handoff.HandoffError, match="already been used"):
        runtime_handoff.import_runtime(mac, bundle, machine="mac")
    assert runtime_authority.load_authority(mac)["status"] == "active"
    assert runtime_authority.load_authority(windows)["status"] != "active"


def test_wrong_target_is_rejected(repos, tmp_path):
    windows, mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")
    with pytest.raises(runtime_handoff.HandoffError, match="targets mac"):
        runtime_handoff.import_runtime(mac, bundle, machine="windows-wsl")
    assert runtime_authority.load_authority(mac)["status"] == "inactive"


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
    assert runtime_authority.load_authority(mac)["status"] == "inactive"


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
    assert runtime_authority.load_authority(mac)["status"] == "import_in_progress"


def test_sqlite_integrity_is_non_mutating_for_wal_mode_database(tmp_path):
    database = tmp_path / "wal-mode.sqlite3"
    db = sqlite3.connect(database)
    try:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        db.execute("CREATE TABLE items (value TEXT)")
        db.execute("INSERT INTO items VALUES (?)", ("intact",))
        db.commit()
    finally:
        db.close()

    sidecars = [
        database.with_name(database.name + suffix)
        for suffix in ("-wal", "-shm", "-journal")
    ]
    assert not any(path.exists() for path in sidecars)

    runtime_handoff._sqlite_integrity(database)

    assert not any(path.exists() for path in sidecars)


def test_complete_bundle_verifier_preserves_extracted_inventory(repos, tmp_path):
    windows, _mac = repos
    exported = _export(windows, tmp_path, "mac", "windows-wsl")

    def set_wal_mode_and_rehash(stage: Path) -> None:
        manifest_path = stage / runtime_handoff.MANIFEST_NAME
        authority_path = stage / runtime_handoff.BUNDLE_AUTHORITY_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        entry = next(
            item for item in manifest["files"] if item["path"].endswith(".sqlite3")
        )
        database = stage / runtime_handoff.RUNTIME_ROOT / entry["path"]
        db = sqlite3.connect(database)
        try:
            assert db.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        finally:
            db.close()
        entry["size"] = database.stat().st_size
        entry["sha256"] = runtime_handoff.sha256_file(database)
        runtime_hash = runtime_handoff.manifest_hash(manifest["files"])
        manifest["runtime_manifest_hash"] = runtime_hash
        authority["runtime_manifest_hash"] = runtime_hash
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        authority_path.write_text(json.dumps(authority), encoding="utf-8")

    bundle = _rewrite_bundle(
        exported,
        tmp_path / "wal-mode-bundle.tgz",
        set_wal_mode_and_rehash,
    )
    with tarfile.open(bundle, "r:gz") as archive:
        expected = {
            member.name
            for member in archive.getmembers()
            if member.isfile()
        }

    staging = tmp_path / "verified-extraction"
    runtime_handoff.extract_and_verify(bundle, staging)
    actual = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file()
    }

    assert actual == expected
    assert not any(
        name.endswith(("-wal", "-shm", "-journal"))
        for name in actual
    )


def test_bundle_verifier_rejects_archived_sqlite_sidecar(repos, tmp_path):
    windows, _mac = repos
    bundle = _export(windows, tmp_path, "mac", "windows-wsl")

    def add_unexpected_sidecar(stage: Path) -> None:
        sidecar = stage / "runtime/data/state/send_idempotency.sqlite3-shm"
        sidecar.write_bytes(b"unexpected archived SQLite sidecar")

    bad = _rewrite_bundle(
        bundle,
        tmp_path / "unexpected-sidecar.tgz",
        add_unexpected_sidecar,
    )

    with pytest.raises(
        runtime_handoff.HandoffError,
        match=r"Unexpected runtime file: .*send_idempotency\.sqlite3-shm",
    ):
        runtime_handoff.extract_and_verify(bad, tmp_path / "sidecar-extraction")


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
    assert runtime_authority.load_authority(mac)["status"] == "import_in_progress"


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
    assert runtime_authority.load_authority(mac)["status"] == "import_in_progress"


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


def test_authoritative_sent_log_overlap_is_reported_without_blocking_future_campaign(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])
    (repo / "data/logs/private_jc_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n"
        "2026-01-01T00:00:00Z,current@example.test,SENT,ok\n",
        encoding="utf-8",
    )

    safety = runtime_handoff.recompute_queue_safety(repo)

    assert safety["safe"] is True
    assert safety["queue_sent_overlap"] == 1
    assert safety["profiles"][0]["sent_overlap_count"] == 1
    assert safety["failure_details"] == []


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


def test_real_preview_schema_with_2574_matching_recipients_is_safe(tmp_path):
    repo = tmp_path / "repo"
    emails = [f"recipient-{index:04d}@example.test" for index in range(2574)]
    _write_runtime(repo, emails)

    safety = runtime_handoff.recompute_queue_safety(repo)
    preview = safety["profiles"][0]["preview"]

    assert safety["safe"] is True
    assert preview["safe"] is True
    assert preview["preview_row_count"] == 2574
    assert preview["validated_row_count"] == 2574
    assert preview["failed_row_count"] == 0
    assert preview["queue_fingerprint"] == preview["preview_fingerprint"]
    assert preview["queue_fingerprint"] == preview["validated_fingerprint"]
    assert preview["summary_counts"] == {
        "total": 2574,
        "passed": 2574,
        "failed": 0,
    }
    assert preview["summary_mode"] == "astra_visual"
    assert preview["failed_predicates"] == []


def test_preview_email_and_author_email_same_normalized_recipient_is_safe(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["recipient@example.test"])
    for name in (
        "private_jc_message_preview.csv",
        "private_jc_message_preview_validated.csv",
    ):
        path = repo / "data/message_previews" / name
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "recipient@example.test,recipient@example.test",
                "RECIPIENT@EXAMPLE.TEST,recipient@example.test",
            ),
            encoding="utf-8",
        )

    preview = runtime_handoff.recompute_queue_safety(repo)["profiles"][0]["preview"]

    assert preview["safe"] is True
    assert preview["generated_validation"]["conflicting_email_rows"] == 0
    assert preview["validated_validation"]["conflicting_email_rows"] == 0


@pytest.mark.parametrize(
    ("case", "expected_predicate"),
    [
        ("conflicting_emails", "generated_email_authoremail_match:1"),
        ("validated_fingerprint", "validated_fingerprint_matches_queue"),
        ("non_pass", "validated_all_rows_pass:1"),
        ("failed_data", "failed_preview_has_zero_rows"),
        ("summary_count", "summary_total_matches_generated"),
        ("wrong_mode", "summary_pitch_mode_matches_profile"),
        ("missing_column", "validated_required_columns:validationstatus"),
        ("malformed_email", "generated_valid_emails:1"),
        ("duplicate_email", "generated_unique_emails:1"),
    ],
)
def test_invalid_preview_predicate_refuses_without_runtime_writes(
    tmp_path,
    monkeypatch,
    case,
    expected_predicate,
):
    repo = tmp_path / "repo"
    emails = ["first@example.test", "second@example.test"]
    _write_runtime(repo, emails)
    preview_dir = repo / "data/message_previews"
    generated = preview_dir / "private_jc_message_preview.csv"
    validated = preview_dir / "private_jc_message_preview_validated.csv"
    failed = preview_dir / "private_jc_message_preview_failed.csv"
    summary = preview_dir / "private_jc_message_preview_summary.txt"

    if case == "conflicting_emails":
        generated.write_text(
            generated.read_text(encoding="utf-8").replace(
                "first@example.test,first@example.test",
                "first@example.test,other@example.test",
                1,
            ),
            encoding="utf-8",
        )
    elif case == "validated_fingerprint":
        validated.write_text(
            validated.read_text(encoding="utf-8").replace(
                "first@example.test,first@example.test",
                "other@example.test,other@example.test",
                1,
            ),
            encoding="utf-8",
        )
    elif case == "non_pass":
        validated.write_text(
            validated.read_text(encoding="utf-8").replace(",PASS,", ",FAIL,", 1),
            encoding="utf-8",
        )
    elif case == "failed_data":
        failed.write_text(
            failed.read_text(encoding="utf-8")
            + "first@example.test,first@example.test,Test Author,Test,Book,"
            "Opening,Subject,Body,FAIL,synthetic\n",
            encoding="utf-8",
        )
    elif case == "summary_count":
        summary.write_text(
            summary.read_text(encoding="utf-8").replace(
                "total rows checked: 2",
                "total rows checked: 1",
            ),
            encoding="utf-8",
        )
    elif case == "wrong_mode":
        summary.write_text(
            summary.read_text(encoding="utf-8").replace(
                "pitch mode: astra_visual",
                "pitch mode: consignment",
            ),
            encoding="utf-8",
        )
    elif case == "missing_column":
        validated.write_text(
            validated.read_text(encoding="utf-8").replace(
                ",ValidationStatus,FailureReasons",
                ",FailureReasons",
                1,
            ),
            encoding="utf-8",
        )
    elif case == "malformed_email":
        generated.write_text(
            generated.read_text(encoding="utf-8").replace(
                "first@example.test,first@example.test",
                "invalid@@example.test,invalid@@example.test",
                1,
            ),
            encoding="utf-8",
        )
    elif case == "duplicate_email":
        generated.write_text(
            generated.read_text(encoding="utf-8").replace(
                "second@example.test,second@example.test",
                "first@example.test,first@example.test",
                1,
            ),
            encoding="utf-8",
        )

    before = {
        path.relative_to(repo): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])

    with pytest.raises(runtime_handoff.HandoffError, match=expected_predicate):
        runtime_handoff.initialize_authority(repo, machine="mac")

    after = {
        path.relative_to(repo): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not runtime_authority.authority_path(repo).exists()
    assert not runtime_authority.generation_floor_path(repo).exists()


def test_valid_emergency_takeover_preview_allows_initialization(emergency_fixture):
    fixture = emergency_fixture
    _emergency_run(fixture)
    with fixture["queue_path"].open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        emails = [str(row["Email"]).strip() for row in csv.DictReader(handle)]
    _write_preview_fixture(fixture["repo"], emails)

    result = runtime_handoff.initialize_authority(
        fixture["repo"],
        machine="mac",
    )

    assert result["status"] == runtime_authority.ACTIVE_STATUS
    assert result["authorized_machine"] == "mac"
    safety = runtime_handoff.recompute_queue_safety(fixture["repo"])
    assert safety["safe"] is True
    assert safety["profiles"][0]["preview"]["campaign_match"]["safe"] is True
    assert safety["profiles"][0]["preview"]["failed_predicates"] == []


def test_verified_emergency_progress_2574_to_2508_allows_activation_and_preflight(
    tmp_path,
    monkeypatch,
):
    fixture = _write_emergency_progress_runtime(
        tmp_path,
        source_rows=2574,
        preview_removed=2,
        progress_removed=64,
    )
    repo = fixture["repo"]
    queue_before = fixture["queue_path"].read_bytes()
    preview_before = {
        path.name: path.read_bytes()
        for path in fixture["preview_dir"].iterdir()
        if path.is_file()
    }
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    monkeypatch.setenv("ASTRA_MACHINE_ID", "mac")

    safety = runtime_handoff.recompute_queue_safety(repo)
    preview = safety["profiles"][0]["preview"]
    progress = preview["campaign_match"]["emergency_queue_progress"]

    assert safety["safe"] is True
    assert preview["safe"] is True
    assert preview["verified_emergency_queue_progress"] is True
    assert preview["failed_predicates"] == []
    assert progress["verified_emergency_queue_progress"] is True
    assert progress["original_rows"] == 2574
    assert progress["preview_rows"] == 2572
    assert progress["current_rows"] == 2508
    assert progress["removed_rows"] == 66
    assert progress["terminal_sent_rows"] == 64
    assert progress["terminal_authoritative_skip_rows"] == 2
    assert progress["unresolved_terminal_rows"] == 0

    authority = runtime_handoff.initialize_authority(
        repo,
        machine="mac",
    )
    status = runtime_handoff.status(repo, machine="mac")
    preflight = _run_private_jc_preflight(repo)

    assert authority["authorized_machine"] == "mac"
    assert status["real_send_authorized"] is True
    assert status["process_blockers"] == []
    assert "verified_emergency_queue_progress=true" in preflight
    assert "PREFLIGHT: ok (no sending)." in preflight
    assert fixture["queue_path"].read_bytes() == queue_before
    assert {
        path.name: path.read_bytes()
        for path in fixture["preview_dir"].iterdir()
        if path.is_file()
    } == preview_before


@pytest.mark.parametrize(
    ("case", "expected_predicate"),
    [
        (
            "missing_terminal",
            "every_removed_recipient_has_terminal_result",
        ),
        (
            "generic_skip",
            "no_generic_or_non_authoritative_results",
        ),
        (
            "changed_survivor",
            "surviving_queue_rows_unchanged",
        ),
        (
            "reordered_survivor",
            "remaining_queue_order_preserved",
        ),
        (
            "inserted_recipient",
            "no_new_recipients_added",
        ),
        (
            "generated_validated_mismatch",
            "generated_validated_preview_match",
        ),
        (
            "failed_preview_row",
            "failed_preview_has_zero_rows",
        ),
    ],
)
def test_invalid_emergency_progress_refuses_activation(
    tmp_path,
    monkeypatch,
    case,
    expected_predicate,
):
    fixture = _write_emergency_progress_runtime(tmp_path)
    repo = fixture["repo"]
    queue_path = fixture["queue_path"]
    log_path = fixture["log_path"]
    preview_dir = fixture["preview_dir"]

    if case == "missing_terminal":
        lines = log_path.read_text(encoding="utf-8").splitlines()
        log_path.write_text(
            "\n".join([lines[0], *lines[2:]]) + "\n",
            encoding="utf-8",
        )
    elif case == "generic_skip":
        lines = log_path.read_text(encoding="utf-8").splitlines()
        fields = lines[1].split(",", 3)
        lines[1] = ",".join(
            [fields[0], fields[1], "SKIP", "event_type=SKIPPED_SUPPRESSED"]
        )
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif case == "changed_survivor":
        queue_path.write_text(
            queue_path.read_text(encoding="utf-8").replace(
                ",Test,Book\n",
                ",Changed,Book\n",
                1,
            ),
            encoding="utf-8",
        )
    elif case == "reordered_survivor":
        lines = queue_path.read_text(encoding="utf-8").splitlines()
        lines[1], lines[2] = lines[2], lines[1]
        queue_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif case == "inserted_recipient":
        queue_path.write_text(
            queue_path.read_text(encoding="utf-8")
            + "inserted@example.test,Test,Book\n",
            encoding="utf-8",
        )
    elif case == "generated_validated_mismatch":
        validated = (
            preview_dir
            / "private_jc_message_preview_validated.csv"
        )
        validated.write_text(
            validated.read_text(encoding="utf-8").replace(
                ",Opening,Subject,Body,PASS,",
                ",Opening,Subject,Changed body,PASS,",
                1,
            ),
            encoding="utf-8",
        )
    elif case == "failed_preview_row":
        failed = preview_dir / "private_jc_message_preview_failed.csv"
        failed.write_text(
            failed.read_text(encoding="utf-8")
            + "recipient-0001@example.test,recipient-0001@example.test,"
            "Test Author,Test,Book,Opening,Subject,Body,FAIL,synthetic\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    before = {
        path.relative_to(repo): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file()
    }

    safety = runtime_handoff.recompute_queue_safety(repo)
    preview = safety["profiles"][0]["preview"]
    progress = preview["campaign_match"].get(
        "emergency_queue_progress",
        {},
    )

    assert safety["safe"] is False
    assert runtime_handoff.preflight_queue_safety(
        repo,
        profile="private_jc",
    )["safe"] is False
    assert preview["verified_emergency_queue_progress"] is False
    assert expected_predicate in ",".join(
        [
            *preview["failed_predicates"],
            *progress.get("failed_predicates", []),
        ]
    )
    with pytest.raises(runtime_handoff.HandoffError):
        runtime_handoff.initialize_authority(repo, machine="mac")

    after = {
        path.relative_to(repo): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not runtime_authority.authority_path(repo).exists()


def test_non_emergency_queue_preview_mismatch_remains_fail_closed(tmp_path):
    repo = tmp_path / "repo"
    emails = ["first@example.test", "second@example.test"]
    _write_runtime(repo, emails)
    (repo / "data/shards/recipients_private_jc.csv").write_text(
        "Email,FirstName,BookTitle\n"
        "second@example.test,Test,Book\n",
        encoding="utf-8",
    )
    (repo / "data/logs/private_jc_log.csv").write_text(
        "TimestampUTC,Email,Status,Info\n"
        "2026-07-30T18:10:04Z,first@example.test,SENT,"
        "campaign_type=cold\n",
        encoding="utf-8",
    )

    preview = runtime_handoff.recompute_queue_safety(repo)["profiles"][0][
        "preview"
    ]

    assert preview["safe"] is False
    assert preview["verified_emergency_queue_progress"] is False
    assert "generated_row_count_matches_queue" in preview["failed_predicates"]


def test_exact_match_behavior_does_not_claim_emergency_progress(tmp_path):
    repo = tmp_path / "repo"
    _write_runtime(repo, ["current@example.test"])

    safety = runtime_handoff.recompute_queue_safety(repo)
    preview = safety["profiles"][0]["preview"]
    preflight = runtime_handoff.preflight_queue_safety(
        repo,
        profile="private_jc",
    )

    assert safety["safe"] is True
    assert preview["safe"] is True
    assert preview["verified_emergency_queue_progress"] is False
    assert preflight["safe"] is True
    assert preflight["verified_emergency_queue_progress"] is False


def test_sender_authority_enforcement_and_preflight_inspection(repos):
    windows, mac = repos
    assert runtime_authority.assert_send_authorized(
        windows, machine="windows-wsl"
    )["status"] == "active"
    with pytest.raises(runtime_authority.AuthorityError, match="authorized for"):
        runtime_authority.assert_send_authorized(windows, machine="mac")
    with pytest.raises(runtime_authority.AuthorityError, match="inactive"):
        runtime_authority.assert_send_authorized(mac, machine="mac")


def test_cloud_machine_can_hold_single_valid_runtime_authority(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "cloud"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.test")
    _run(repo, "git", "config", "user.name", "Test")
    (repo / "README.md").write_text("cloud fixture\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "fixture")
    _write_runtime(repo, ["cloud-recipient@example.test"])
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])

    authority = runtime_handoff.initialize_authority(repo, machine="cloud")

    assert runtime_authority.current_machine(
        {"ASTRA_MACHINE_ID": "cloud"}
    ) == "cloud"
    assert authority["authorized_machine"] == "cloud"
    assert authority["source_machine"] == "mac"
    assert authority["target_machine"] == "cloud"
    assert runtime_authority.assert_send_authorized(
        repo,
        machine="cloud",
    )["status"] == "active"
    with pytest.raises(runtime_authority.AuthorityError, match="authorized for cloud"):
        runtime_authority.assert_send_authorized(repo, machine="mac")


def test_mac_authority_rejects_simultaneous_cloud_authority(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "mac"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.test")
    _run(repo, "git", "config", "user.name", "Test")
    (repo / "README.md").write_text("mac fixture\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "fixture")
    _write_runtime(repo, ["mac-recipient@example.test"])
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    runtime_handoff.initialize_authority(repo, machine="mac")

    with pytest.raises(runtime_authority.AuthorityError, match="authorized for mac"):
        runtime_authority.assert_send_authorized(repo, machine="cloud")


def test_cloud_authority_refuses_checkout_at_different_git_commit(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "cloud"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.test")
    _run(repo, "git", "config", "user.name", "Test")
    (repo / "README.md").write_text("first\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "first")
    _write_runtime(repo, ["cloud-recipient@example.test"])
    monkeypatch.setattr(runtime_handoff, "process_blockers", lambda: [])
    monkeypatch.setattr(runtime_handoff, "active_job_files", lambda _repo: [])
    runtime_handoff.initialize_authority(repo, machine="cloud")
    (repo / "README.md").write_text("second\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "second")

    with pytest.raises(
        runtime_authority.AuthorityError,
        match="expected Git commit",
    ):
        runtime_authority.assert_send_authorized(repo, machine="cloud")


def test_sender_refuses_real_start_when_cloud_authority_is_invalid(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.email", "test@example.test")
    _run(repo, "git", "config", "user.name", "Test")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _run(repo, "git", "add", "README.md")
    _run(repo, "git", "commit", "-qm", "fixture")
    payload = {
        "authorized_machine": "mac",
        "generation": 1,
        "bundle_id": "mac-only",
        "source_machine": "windows-wsl",
        "target_machine": "mac",
        "created_utc": runtime_authority.utc_now(),
        "expected_git_commit": _run(repo, "git", "rev-parse", "HEAD"),
        "runtime_manifest_hash": "fixture",
        "status": "active",
    }
    runtime_authority.write_authority(repo, payload)
    runtime_authority.write_generation_floor(repo, 1, payload["bundle_id"])
    output = io.StringIO()
    monkeypatch.setenv("ASTRA_MACHINE_ID", "cloud")

    with (
        patch.object(send_shard, "ROOT", repo),
        patch.object(
            send_shard,
            "send_via_sendgrid",
            side_effect=AssertionError("invalid cloud authority must not submit"),
        ) as submit,
        patch.object(
            sys,
            "argv",
            ["send_shard.py", "--profile", "private_jc"],
        ),
        redirect_stdout(output),
    ):
        send_shard.main()

    submit.assert_not_called()
    assert "REFUSED: real send is not authorized" in output.getvalue()
    assert "authorized for mac, not cloud" in output.getvalue()


def test_cloud_preflight_succeeds_without_authority_or_submission(
    tmp_path,
    monkeypatch,
):
    _write_runtime(tmp_path, ["cloud-preflight@example.test"])
    shards = tmp_path / "data/shards"
    logs = tmp_path / "data/logs"
    state = tmp_path / "data/state"
    output = io.StringIO()
    monkeypatch.setenv("ASTRA_MACHINE_ID", "cloud")

    with (
        patch.object(settings, "APP_ROOT", tmp_path),
        patch.object(settings, "SHARDS_DIR", shards),
        patch.object(settings, "LOGS_DIR", logs),
        patch.object(settings, "STATE_DIR", state),
        patch.object(send_shard, "ROOT", tmp_path),
        patch.object(send_shard, "SHARDS_DIR", shards),
        patch.object(send_shard, "LOGS_DIR", logs),
        patch.object(send_shard, "STATE_DIR", state),
        patch.object(
            send_shard,
            "DEFAULT_UNSUB_CSV",
            state / "unsubscribed.csv",
        ),
        patch.object(
            send_shard,
            "DEFAULT_SUPPRESS_CSV",
            state / "suppressed.csv",
        ),
        patch.object(
            send_shard,
            "DEFAULT_SENDGRID_SUPPRESSION_CSV",
            state / "sendgrid_suppressions.csv",
        ),
        patch.object(
            send_shard,
            "assert_send_authorized",
            side_effect=AssertionError("preflight must not require authority"),
        ),
        patch.object(
            send_shard,
            "send_via_sendgrid",
            side_effect=AssertionError("preflight must not submit"),
        ) as submit,
        patch.object(send_shard, "smtp_login") as smtp_login,
        patch.object(
            sys,
            "argv",
            ["send_shard.py", "--profile", "private_jc", "--preflight"],
        ),
        redirect_stdout(output),
    ):
        send_shard.main()

    submit.assert_not_called()
    smtp_login.assert_not_called()
    assert "PREFLIGHT: ok (no sending)." in output.getvalue()


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


def test_authoritative_already_sent_skip_counts_as_completed(tmp_path):
    log_path = tmp_path / "private_jc_log.csv"
    log_path.write_text(
        "TimestampUTC,Email,Status,Info\n"
        "2026-07-30T18:10:04Z,sent@example.com,SENT,"
        "campaign_type=cold\n"
        "2026-07-30T18:10:05Z,prior@example.com,SKIP,"
        "campaign_type=cold "
        "event_type=SKIPPED_ALREADY_SENT_AUTHORITATIVE\n"
        "2026-07-30T18:10:06Z,suppressed@example.com,SKIP,"
        "campaign_type=cold event_type=SKIPPED_SUPPRESSED\n",
        encoding="utf-8",
    )

    assert runtime_handoff._read_successfully_sent_emails(log_path) == {
        "sent@example.com",
        "prior@example.com",
    }
