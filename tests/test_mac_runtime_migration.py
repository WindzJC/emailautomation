import io
import json
import tarfile
from pathlib import Path

import pytest

from tools import mac_runtime_migration as migration


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes = b"") -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def _add_directory(archive: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    archive.addfile(info)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "data/shards").mkdir(parents=True)
    (repo / "data/state").mkdir(parents=True)
    (repo / "_important").mkdir()
    (repo / "data/shards/recipients_private_jc.csv").write_text(
        "Email,FirstName\none@example.test,One\n", encoding="utf-8"
    )
    (repo / "data/state/dashboard_run_settings.json").write_text(
        json.dumps({"path": f"{repo}/data/shards/recipients_private_jc.csv"}),
        encoding="utf-8",
    )
    return repo


def test_candidates_exclude_secrets_locks_backups_and_caches(tmp_path):
    repo = _repo(tmp_path)
    for relative in (
        ".env",
        "data/shards/queue.lock",
        "data/shards/old.tgz",
        "data/shards/recipients.csv.bak",
        "data/state/cache-wal",
    ):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("secret-or-stale", encoding="utf-8")

    names = {
        path.relative_to(repo).as_posix()
        for path, _ in migration.candidate_files(repo)
    }

    assert "data/shards/recipients_private_jc.csv" in names
    assert ".env" not in names
    assert not any(
        name.endswith((".lock", ".tgz", ".bak", "-wal")) for name in names
    )
    for relative in (
        Path("KEYS"),
        Path("ACC GMAIL"),
        Path("nested/.env"),
        Path("nested/.env.cloud"),
        Path("nested/KEYS"),
        Path("nested/ACC GMAIL"),
    ):
        assert migration.excluded(relative)


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
def test_legacy_archive_refuses_sensitive_members(tmp_path, relative):
    bundle = tmp_path / "sensitive-member.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_bytes(archive, migration.ARCHIVE_MANIFEST_NAME, b'{"files":[]}')
        _add_directory(archive, migration.ARCHIVE_RUNTIME_ROOT)
        _add_bytes(
            archive,
            f"{migration.ARCHIVE_RUNTIME_ROOT}/{relative}",
            b"synthetic-test-value",
        )

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(
            migration.MigrationError,
            match="Sensitive archive member is forbidden",
        ):
            migration.safe_members(archive)


def test_manifest_remaps_json_without_changing_source(tmp_path):
    repo = _repo(tmp_path)
    staging = tmp_path / "stage"
    target = Path("/Users/test/emailautomation")
    source_path = repo / "data/state/dashboard_run_settings.json"
    source = source_path.read_bytes()

    manifest = migration.build_manifest(repo, staging, target, "abc123")

    entry = next(
        item
        for item in manifest["files"]
        if item["path"].endswith("dashboard_run_settings.json")
    )
    staged = staging / "runtime" / entry["path"]
    assert str(target) in staged.read_text(encoding="utf-8")
    assert source_path.read_bytes() == source
    assert entry["sha256"] == migration.sha256_file(staged)
    assert entry["source_sha256"] == migration.sha256_file(source_path)


def test_only_current_referenced_important_run_is_included(tmp_path):
    repo = _repo(tmp_path)
    current = repo / "_important/runs/current/leads.csv"
    old = repo / "_important/runs/old/leads.csv"
    current.parent.mkdir(parents=True)
    old.parent.mkdir(parents=True)
    current.write_text("Email\ncurrent@example.test\n", encoding="utf-8")
    old.write_text("Email\nold@example.test\n", encoding="utf-8")
    (repo / "data/state/leads_dashboard_state.json").write_text(
        json.dumps({"output_path": str(current)}), encoding="utf-8"
    )

    names = {
        path.relative_to(repo).as_posix()
        for path, _ in migration.candidate_files(repo)
    }

    assert "_important/runs/current/leads.csv" in names
    assert "_important/runs/old/leads.csv" not in names


def test_bundle_refuses_runtime_process(monkeypatch, tmp_path):
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        migration, "process_blockers", lambda: ["123 send_shard.py --profile"]
    )

    with pytest.raises(migration.MigrationError, match="blocking processes"):
        migration.assert_frozen(repo, require_clean_git=False)


def test_current_active_job_blocks_but_backup_does_not(tmp_path):
    repo = _repo(tmp_path)
    jobs = repo / "_important/check_runs/jobs"
    jobs.mkdir(parents=True)
    (jobs / "old.json.bak").write_text('{"status":"running"}', encoding="utf-8")
    assert migration.active_job_files(repo) == []
    (jobs / "current.json").write_text(
        '{"status":"checking"}', encoding="utf-8"
    )
    assert migration.active_job_files(repo) == [
        "_important/check_runs/jobs/current.json"
    ]


def test_old_malformed_job_is_reported_but_does_not_block(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    jobs = repo / "_important/check_runs/jobs"
    jobs.mkdir(parents=True)
    path = jobs / "old.json"
    path.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(
        migration.time,
        "time",
        lambda: path.stat().st_mtime + migration.CURRENT_JOB_MAX_AGE_SECONDS + 1,
    )

    active, stale = migration.job_file_status(repo)

    assert active == []
    assert stale == ["_important/check_runs/jobs/old.json"]


def test_verify_rejects_checksum_mismatch(tmp_path):
    bundle = tmp_path / "bad.tgz"
    payload = b"changed"
    manifest = {
        "files": [
            {
                "path": "data/state/state.json",
                "size": len(payload),
                "sha256": "0" * 64,
            }
        ]
    }
    with tarfile.open(bundle, "w:gz") as archive:
        manifest_bytes = json.dumps(manifest).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_bytes)
        archive.addfile(info, io.BytesIO(manifest_bytes))
        info = tarfile.TarInfo("runtime/data/state/state.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(migration.MigrationError, match="Checksum mismatch"):
        migration.verify_bundle(bundle)


def test_bundle_created_by_bundler_verifies(monkeypatch, tmp_path):
    repo = _repo(tmp_path)
    output_dir = tmp_path / "bundles"
    monkeypatch.setattr(migration, "assert_frozen", lambda _repo: "abc123")

    bundle = migration.bundle(
        repo,
        output_dir,
        Path("/Users/test/emailautomation"),
    )

    manifest = migration.verify_bundle(bundle)
    assert manifest["expected_commit"] == "abc123"
    assert len(manifest["files"]) == 2


def test_exact_runtime_directory_and_valid_descendants_are_accepted(tmp_path):
    bundle = tmp_path / "valid-layout.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_bytes(archive, "manifest.json", b'{"files":[]}')
        _add_directory(archive, "runtime")
        _add_directory(archive, "runtime/data")
        _add_bytes(archive, "runtime/data/state.json", b"{}")

    with tarfile.open(bundle, "r:gz") as archive:
        names = [member.name for member in migration.safe_members(archive)]

    assert names == [
        "manifest.json",
        "runtime",
        "runtime/data",
        "runtime/data/state.json",
    ]


def test_regular_file_named_runtime_is_rejected(tmp_path):
    bundle = tmp_path / "runtime-file.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_bytes(archive, "manifest.json", b'{"files":[]}')
        _add_bytes(archive, "runtime", b"not-a-directory")

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="runtime root must be a directory"):
            migration.safe_members(archive)


def test_symlink_named_runtime_is_rejected(tmp_path):
    bundle = tmp_path / "runtime-link.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_bytes(archive, "manifest.json", b'{"files":[]}')
        info = tarfile.TarInfo("runtime")
        info.type = tarfile.SYMTYPE
        info.linkname = "elsewhere"
        archive.addfile(info)

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="Unsafe archive member type"):
            migration.safe_members(archive)


@pytest.mark.parametrize("name", ["/absolute", "runtime/../../outside"])
def test_absolute_and_parent_traversal_members_are_rejected(tmp_path, name):
    bundle = tmp_path / "unsafe-path.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_bytes(archive, name, b"x")

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="Unsafe archive member"):
            migration.safe_members(archive)


@pytest.mark.parametrize("name", ["runtime-other", "unexpected.json"])
def test_unknown_top_level_members_are_rejected(tmp_path, name):
    bundle = tmp_path / "unexpected-top.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_bytes(archive, name, b"x")

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="Unexpected archive member"):
            migration.safe_members(archive)


def test_duplicate_archive_members_are_rejected(tmp_path):
    bundle = tmp_path / "duplicate.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_directory(archive, "runtime")
        _add_directory(archive, "runtime")

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="Duplicate archive member"):
            migration.safe_members(archive)


def test_conflicting_archive_members_are_rejected(tmp_path):
    bundle = tmp_path / "conflict.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        _add_directory(archive, "runtime")
        _add_bytes(archive, "runtime/data", b"not-a-directory")
        _add_bytes(archive, "runtime/data/state.json", b"{}")

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="Conflicting archive members"):
            migration.safe_members(archive)


def test_archive_path_traversal_is_rejected(tmp_path):
    bundle = tmp_path / "unsafe.tgz"
    with tarfile.open(bundle, "w:gz") as archive:
        info = tarfile.TarInfo("../outside")
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))

    with tarfile.open(bundle, "r:gz") as archive:
        with pytest.raises(migration.MigrationError, match="Unsafe archive member"):
            migration.safe_members(archive)


def test_restore_refuses_to_overwrite_existing_runtime_file(monkeypatch, tmp_path):
    source = _repo(tmp_path / "source")
    monkeypatch.setattr(migration, "assert_frozen", lambda _repo: "abc123")
    bundle = migration.bundle(
        source,
        tmp_path / "bundles",
        Path("/Users/test/emailautomation"),
    )
    target = tmp_path / "target"
    existing = target / "data/shards/recipients_private_jc.csv"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"original target bytes\n")
    monkeypatch.setattr(migration, "process_blockers", lambda: [])
    monkeypatch.setattr(
        migration,
        "git",
        lambda _repo, *args: "" if args[:2] == ("status", "--porcelain") else "abc123",
    )

    with pytest.raises(migration.MigrationError, match="Refusing to overwrite"):
        migration.restore(target, bundle)

    assert existing.read_bytes() == b"original target bytes\n"


def test_profile_inventory_uses_static_profiles_and_queue_counts(tmp_path):
    repo = _repo(tmp_path)
    (repo / "send_shard.py").write_text(
        "PROFILES: dict[str, dict[str, object]] = {\n"
        '  "private_jc": {"csv": "recipients_private_jc.csv"},\n'
        '  "sendgrid_annette": {"csv": "recipients_sendgrid_1.csv"},\n'
        "}\n",
        encoding="utf-8",
    )

    result = migration.profile_inventory(repo)

    assert result["profiles"]["private_jc"] == "recipients_private_jc.csv"
    assert result["active_intended_profiles"] == ["private_jc"]
