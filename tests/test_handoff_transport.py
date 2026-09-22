from pathlib import Path

import pytest

from tools import handoff_transport as ht


HEAD = "a" * 40


def test_windows_repo_default_matches_real_wsl_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = ht.load_config(repo, environ={"HOME": str(tmp_path / "home")})
    assert cfg["HANDOFF_WINDOWS_REPO"] == "/home/jc/src/emailautomation"


def test_local_config_overrides_global_and_env_overrides_local(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    global_file = home / ".config/astra/handoff.env"
    global_file.parent.mkdir(parents=True)
    global_file.write_text(
        "HANDOFF_MAC_HOST=global-mac\nHANDOFF_WINDOWS_HOST=global-win\n",
        encoding="utf-8",
    )
    (repo / ".handoff.local").write_text(
        "HANDOFF_MAC_HOST=local-mac\nHANDOFF_WINDOWS_HOST=local-win\n",
        encoding="utf-8",
    )
    cfg = ht.load_config(
        repo,
        environ={
            "HOME": str(home),
            "HANDOFF_WINDOWS_HOST": "env-win",
        },
        home=home,
    )
    assert cfg["HANDOFF_MAC_HOST"] == "local-mac"
    assert cfg["HANDOFF_WINDOWS_HOST"] == "env-win"


def test_endpoint_requires_safe_ssh_host(tmp_path: Path) -> None:
    cfg = ht.load_config(tmp_path, environ={"HOME": str(tmp_path)})
    with pytest.raises(ht.TransportError, match="No SSH host"):
        ht.endpoint(cfg, "windows-wsl")

    cfg["HANDOFF_WINDOWS_HOST"] = "jc@host;bad"
    with pytest.raises(ht.TransportError, match="Unsafe SSH host"):
        ht.endpoint(cfg, "windows-wsl")


def test_preflight_refuses_already_active_target() -> None:
    status = {
        "head": HEAD,
        "process_blockers": [],
        "active_job_files": [],
        "authority_error": "",
        "authority": {"status": "active"},
    }
    with pytest.raises(ht.TransportError, match="already active"):
        ht.validate_preflight_status(status, HEAD)


def test_activation_requires_exact_commit_and_authority() -> None:
    status = {
        "head": HEAD,
        "process_blockers": [],
        "active_job_files": [],
        "real_send_authorized": True,
        "authority": {
            "expected_git_commit": HEAD,
            "authorized_machine": "windows-wsl",
            "status": "active",
        },
    }
    ht.validate_activation_status(status, "windows-wsl", HEAD)

    status["authority"] = dict(status["authority"], expected_git_commit="b" * 40)
    with pytest.raises(ht.TransportError, match="authority commit"):
        ht.validate_activation_status(status, "windows-wsl", HEAD)


def test_source_identity_requires_published_head(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = {"HANDOFF_PYTHON": "python3"}
    def fake_git(_repo: Path, *args: str) -> str:
        if args[:2] == ("status", "--porcelain"):
            return ""
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("rev-parse", "HEAD"):
            return HEAD
        if args[:2] == ("ls-remote", "origin"):
            return f'{"b" * 40}\trefs/heads/main'
        raise AssertionError(args)

    monkeypatch.setattr(ht, "_git", fake_git)
    monkeypatch.setattr(
        ht,
        "_runtime_status",
        lambda *_args, **_kwargs: {
            "process_blockers": [],
            "active_job_files": [],
            "real_send_authorized": True,
        },
    )
    with pytest.raises(ht.TransportError, match="not published"):
        ht.source_identity(repo, cfg)


def test_switch_preflights_before_export(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    bundle = tmp_path / "bundle.tgz"
    bundle.write_bytes(b"bundle")
    events: list[str] = []
    monkeypatch.setattr(ht, "endpoint", lambda *_args: ("jc@target", "/repo"))
    monkeypatch.setattr(ht, "source_identity", lambda *_args: ("main", HEAD))

    def preflight(*_args):
        events.append("preflight")
        return {
            "head": HEAD,
            "process_blockers": [],
            "active_job_files": [],
            "authority_error": "",
            "authority": {"status": "handoff_in_progress"},
        }

    monkeypatch.setattr(ht, "_remote_sync_status", preflight)

    def export(*_args):
        events.append("export")
        return bundle

    monkeypatch.setattr(ht, "_export_bundle", export)
    monkeypatch.setattr(
        ht,
        "_remote_receive",
        lambda *_args: events.append("receive") or "/tmp/bundle.tgz",
    )
    monkeypatch.setattr(
        ht,
        "_remote_status",
        lambda *_args: {
            "head": HEAD,
            "process_blockers": [],
            "active_job_files": [],
            "real_send_authorized": True,
            "authority": {
                "expected_git_commit": HEAD,
                "authorized_machine": "windows-wsl",
                "status": "active",
            },
        },
    )
    monkeypatch.setattr(ht, "_ssh", lambda *_args, **_kwargs: events.append("cleanup"))

    ht.switch(repo, {"HANDOFF_BUNDLE_DIR": str(tmp_path)}, "windows-wsl")
    assert events[:2] == ["preflight", "export"]
    assert events == ["preflight", "export", "receive", "cleanup"]


def test_handoff_entrypoint_routes_switches_through_transport() -> None:
    script = Path("handoff").read_text(encoding="utf-8")
    assert "tools/handoff_transport.py" in script
    assert "transport_handoff switch --target mac" in script
    assert "transport_handoff switch --target windows-wsl" in script
    assert "transport_handoff takeover --source mac --target windows-wsl" in script
    assert "transport_handoff prepare-export --target" in script
    assert "runtime_handoff import" in script


def test_takeover_from_mac_preflights_before_remote_export(
    monkeypatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    bundle_dir = tmp_path / "bundles"
    events: list[str] = []

    monkeypatch.setattr(
        ht,
        "endpoint",
        lambda *_args: ("windelle@mac", "/repo"),
    )
    monkeypatch.setattr(
        ht,
        "_remote_source_identity",
        lambda *_args: (
            "main",
            HEAD,
            {
                "head": HEAD,
                "process_blockers": [],
                "active_job_files": [],
                "real_send_authorized": True,
                "authority": {
                    "expected_git_commit": HEAD,
                    "authorized_machine": "mac",
                    "status": "active",
                },
            },
        ),
    )

    def sync(*_args, **_kwargs):
        events.append("local-sync")
        return {}

    monkeypatch.setattr(ht, "_sync_local_target", sync)

    def remote_export(*_args, **_kwargs):
        events.append("remote-export")
        return "/tmp/runtime_handoff.tgz"

    monkeypatch.setattr(ht, "_remote_prepare_export", remote_export)

    def pull(*_args, **_kwargs):
        events.append("pull")
        destination = _args[2]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"bundle")
    monkeypatch.setattr(ht, "_pull_remote_bundle", pull)
    monkeypatch.setattr(
        ht,
        "_local_receive",
        lambda *_args, **_kwargs: events.append("local-receive"),
    )
    monkeypatch.setattr(
        ht,
        "_runtime_status",
        lambda *_args, **_kwargs: {
            "head": HEAD,
            "process_blockers": [],
            "active_job_files": [],
            "real_send_authorized": True,
            "authority": {
                "expected_git_commit": HEAD,
                "authorized_machine": "windows-wsl",
                "status": "active",
            },
        },
    )
    monkeypatch.setattr(
        ht,
        "_ssh",
        lambda *_args, **_kwargs: events.append("remote-cleanup"),
    )
    ht.takeover_from(
        repo,
        {"HANDOFF_BUNDLE_DIR": str(bundle_dir), "HANDOFF_PYTHON": "python3"},
        source="mac",
        target="windows-wsl",
    )

    assert events == [
        "local-sync",
        "remote-export",
        "pull",
        "local-receive",
        "remote-cleanup",
    ]


def test_takeover_rejects_source_not_authorized(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(
        ht,
        "endpoint",
        lambda *_args: ("windelle@mac", "/repo"),
    )
    monkeypatch.setattr(
        ht,
        "_remote_source_identity",
        lambda *_args: (
            "main",
            HEAD,
            {
                "head": HEAD,
                "process_blockers": [],
                "active_job_files": [],
                "real_send_authorized": False,
                "authority": {
                    "expected_git_commit": HEAD,
                    "authorized_machine": "mac",
                    "status": "handoff_in_progress",
                },
            },
        ),
    )
    with pytest.raises(ht.TransportError, match="authority status|real-send"):
        ht.takeover_from(
            repo,
            {"HANDOFF_BUNDLE_DIR": str(tmp_path), "HANDOFF_PYTHON": "python3"},
            source="mac",
            target="windows-wsl",
        )
