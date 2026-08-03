from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path("/opt/astra/emailautomation")
PARENT = REPO.parent
COMPATIBILITY = Path(
    "/etc/astra-emailautomation/handoff-commit-compatibility.json"
)
sys.path.insert(0, str(REPO))

import runtime_authority  # noqa: E402
from tools import runtime_handoff  # noqa: E402


def run(*args: str, cwd: Path, check: bool = True, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args), cwd=cwd, text=True, capture_output=True, check=check, env=env
    )


def write_preview(repo: Path, emails: list[str]) -> None:
    root = repo / "data/message_previews"
    root.mkdir(parents=True, exist_ok=True)
    generated = (
        "CampaignType,Email,AuthorEmail,AuthorName,FirstName,BookTitle,"
        "PersonalizedOpeningLine,Subject,Body\n"
        + "".join(
            f"cold,{email},{email},Test Author,Test,Book,Opening,Subject,Body\n"
            for email in emails
        )
    )
    validated_header = (
        "Email,AuthorEmail,AuthorName,FirstName,BookTitle,PersonalizedOpeningLine,"
        "Subject,Body,ValidationStatus,FailureReasons\n"
    )
    validated = validated_header + "".join(
        f"{email},{email},Test Author,Test,Book,Opening,Subject,Body,PASS,\n"
        for email in emails
    )
    (root / "private_jc_message_preview.csv").write_text(generated)
    (root / "private_jc_message_preview_validated.csv").write_text(validated)
    (root / "private_jc_message_preview_failed.csv").write_text(validated_header)
    (root / "private_jc_message_preview_summary.txt").write_text(
        "pitch mode: astra_visual\n"
        f"total rows checked: {len(emails)}\n"
        f"passed rows: {len(emails)}\n"
        "failed rows: 0\n"
    )


def write_runtime(repo: Path, emails: list[str], marker: str) -> None:
    shards = repo / "data/shards"
    logs = repo / "data/logs"
    state = repo / "data/state"
    important = repo / "_important"
    for path in (shards, logs, state, important):
        path.mkdir(parents=True, exist_ok=True)
    queue = "Email,FirstName,BookTitle\n" + "".join(
        f"{email},Test,Book\n" for email in emails
    )
    (shards / "recipients_private_jc.csv").write_text(queue)
    for name in ("leads.csv", "leads_triaged_keep.csv"):
        (important / name).write_text(queue)
    (important / "leads_triaged_reject.csv").write_text(
        "Email,FirstName,BookTitle\n"
    )
    (important / "campaign_history.jsonl").write_text(
        json.dumps({"campaign": marker}) + "\n"
    )
    (logs / "private_jc_log.csv").write_text("TimestampUTC,Email,Status,Info\n")
    (state / "suppressed.csv").write_text("Email\n")
    (state / "unsubscribed.csv").write_text("Email\n")
    (state / "sendgrid_suppressions.csv").write_text("Email,Type\n")
    (state / "active_campaign_snapshot.json").write_text(
        json.dumps(
            {
                "checked_path": str(important / "leads.csv"),
                "intended_source_path": str(important / "leads_triaged_keep.csv"),
                "triaged_keep_path": str(important / "leads_triaged_keep.csv"),
                "triaged_reject_path": str(important / "leads_triaged_reject.csv"),
            }
        )
    )
    write_preview(repo, emails)
    with sqlite3.connect(state / "send_idempotency.sqlite3") as db:
        db.execute("CREATE TABLE sends (email TEXT PRIMARY KEY)")
        db.execute("INSERT INTO sends VALUES (?)", (f"{marker}@example.test",))


def materialize_overlay_runtime_roots(repo: Path) -> None:
    """Move tracked empty runtime roots into the container writable layer."""
    for name in ("data", "_important"):
        root = repo / name
        if not root.exists():
            continue
        saved = [
            (path.relative_to(root), path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for path in root.rglob("*")
            if path.is_file()
        ]
        shutil.rmtree(root)
        root.mkdir(mode=0o750)
        for relative, content, mode in saved:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(mode)


def assert_permissions() -> None:
    parent = PARENT.stat()
    repo = REPO.stat()
    local = (REPO / runtime_handoff.LOCAL_STATE_DIR).stat()
    compatibility = COMPATIBILITY.stat()
    assert parent.st_uid == 0 and parent.st_gid == os.getegid()
    assert stat.S_IMODE(parent.st_mode) == 0o750
    assert repo.st_uid == os.geteuid() and repo.st_gid == os.getegid()
    assert stat.S_IMODE(repo.st_mode) == 0o750
    assert local.st_uid == os.geteuid() and stat.S_IMODE(local.st_mode) == 0o700
    assert compatibility.st_uid == 0 and compatibility.st_gid == os.getegid()
    assert stat.S_IMODE(compatibility.st_mode) == 0o640
    probe = PARENT / "must-not-be-created"
    try:
        probe.write_text("refuse")
    except PermissionError:
        pass
    else:
        raise AssertionError("astra unexpectedly wrote directly beneath /opt/astra")
    assert not probe.exists()


def setup_case() -> tuple[Path, Path, str]:
    assert os.geteuid() == 2000 and os.getegid() == 2000
    assert_permissions()
    source = Path("/home/astra/synthetic-source")
    if source.exists():
        shutil.rmtree(source)
    run("git", "clone", "-q", str(REPO), str(source), cwd=Path("/home/astra"))
    write_runtime(source, ["new@example.test"], "source")
    materialize_overlay_runtime_roots(REPO)
    write_runtime(REPO, ["old@example.test"], "target")
    runtime_handoff.initialize_authority(source, machine="mac")
    bundle = runtime_handoff.export_runtime(
        source, Path("/home/astra/bundles"), "cloud", machine="mac"
    )
    bundle.chmod(0o600)
    bundle_mode = stat.S_IMODE(bundle.stat().st_mode)
    assert bundle.stat().st_uid == os.geteuid() and bundle_mode == 0o600
    baseline = runtime_handoff._runtime_baseline_fingerprint(REPO)
    return source, bundle, baseline


def receive_command(bundle: Path) -> tuple[subprocess.CompletedProcess, list[str]]:
    env = os.environ.copy()
    env.update(
        {
            "ASTRA_MACHINE_ID": "cloud",
            "ASTRA_DISABLE_DOTENV": "1",
            "HANDOFF_PYTHON": str(REPO / ".venv/bin/python"),
            "ASTRA_HANDOFF_COMMIT_COMPATIBILITY_FILE": str(COMPATIBILITY),
        }
    )
    process = subprocess.Popen(
        [str(REPO / "handoff"), "receive", str(bundle)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    observed: list[str] = []
    while process.poll() is None:
        try:
            authority = runtime_authority.load_authority(REPO)
        except runtime_authority.AuthorityError:
            authority = None
        if authority:
            observed.append(authority["status"])
            if authority["status"] == "active":
                transaction = next(
                    (REPO / ".runtime_handoff/receive-transactions").glob(
                        "receive_*.json"
                    )
                )
                assert json.loads(transaction.read_text())["status"] == "completed"
        time.sleep(0.002)
    stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr), observed


def verify_success(result: subprocess.CompletedProcess, observed: list[str]) -> None:
    if result.returncode:
        raise AssertionError(result.stderr)
    payload = json.loads(result.stdout)
    authority = runtime_authority.assert_send_authorized(REPO, machine="cloud")
    assert authority["status"] == "active" and authority["generation"] == 1
    assert payload["authority"]["generation"] == 1
    assert payload["sender_started"] is False
    assert "active" not in observed or observed[-1] == "active"
    assert "new@example.test" in (
        REPO / "data/shards/recipients_private_jc.csv"
    ).read_text()
    database = REPO / "data/state/send_idempotency.sqlite3"
    runtime_handoff._sqlite_integrity(database)
    backup = Path(payload["backup"])
    assert backup.is_file() and stat.S_IMODE(backup.stat().st_mode) == 0o600
    with tarfile.open(backup, "r:gz") as archive:
        assert any(member.name.startswith("data/") for member in archive.getmembers())
    layout = runtime_handoff._private_handoff_layout(REPO)
    assert not list(layout["staging"].iterdir())
    assert not list(PARENT.glob("handoff-*"))
    listing = run("ps", "-eo", "args=", cwd=REPO).stdout
    assert "send_shard.py" not in listing and "live_dashboard.py" not in listing


def mode_success() -> None:
    _source, bundle, _baseline = setup_case()
    result, observed = receive_command(bundle)
    verify_success(result, observed)
    print("production_permission_receive=passed")


def mode_resume() -> None:
    _source, bundle, baseline = setup_case()
    real_staging = runtime_handoff._private_staging_directory
    failed = {"value": False}

    @contextmanager
    def controlled(repo: Path, *, prefix: str):
        if prefix == "receive-" and not failed["value"]:
            failed["value"] = True
            raise PermissionError("controlled production-equivalent staging failure")
        with real_staging(repo, prefix=prefix) as staging:
            yield staging

    runtime_handoff._private_staging_directory = controlled
    try:
        runtime_handoff.import_runtime(REPO, bundle, machine="cloud")
    except PermissionError:
        pass
    else:
        raise AssertionError("controlled receive failure did not occur")
    finally:
        runtime_handoff._private_staging_directory = real_staging
    interrupted = runtime_authority.load_authority(REPO)
    assert interrupted["status"] == "import_in_progress"
    assert interrupted["generation"] == 1
    assert runtime_handoff._runtime_baseline_fingerprint(REPO) == baseline
    layout = runtime_handoff._private_handoff_layout(REPO)
    assert not list(layout["staging"].iterdir())
    assert not list(layout["backups"].iterdir())
    result, observed = receive_command(bundle)
    verify_success(result, observed)
    payload = json.loads(result.stdout)
    assert payload["resumed"] is True
    assert payload["authority"]["generation"] == 1
    print("interrupted_receive_resume=passed")


def mode_expected_refusal(mode: str) -> None:
    _source, bundle, _baseline = setup_case()
    result, _observed = receive_command(bundle)
    assert result.returncode != 0
    if mode == "cross-filesystem":
        assert "different filesystem" in result.stderr
    else:
        assert "wrong owner" in result.stderr
    with pytest_raises_authority_missing():
        runtime_authority.load_authority(REPO)
    print(f"{mode}=refused")


@contextmanager
def pytest_raises_authority_missing():
    try:
        yield
    except runtime_authority.AuthorityError:
        return
    raise AssertionError("authority unexpectedly exists")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("success", "resume", "cross-filesystem", "wrong-owner"),
        required=True,
    )
    mode = parser.parse_args().mode
    if mode == "success":
        mode_success()
    elif mode == "resume":
        mode_resume()
    else:
        mode_expected_refusal(mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
