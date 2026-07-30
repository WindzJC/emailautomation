from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path

import pytest

from tools import package_campaign_handoff
from tools import runtime_handoff


ROOT = Path(__file__).resolve().parents[1]
CLOUD = ROOT / "deploy/cloud"


def test_cloud_identity_is_available_to_handoff_cli() -> None:
    args = runtime_handoff.parse_args(["--machine", "cloud", "status"])
    export_args = runtime_handoff.parse_args(
        ["--machine", "mac", "export", "--target", "cloud"]
    )

    assert args.machine == "cloud"
    assert export_args.target == "cloud"
    handoff = (ROOT / "handoff").read_text(encoding="utf-8")
    assert "ASTRA_MACHINE_ID='${target}' ./handoff receive" in handoff


def test_cloud_shell_scripts_are_syntax_valid() -> None:
    scripts = [
        ROOT / "handoff",
        CLOUD / "bootstrap.sh",
        CLOUD / "verify.sh",
        CLOUD / "backup.sh",
    ]
    for script in scripts:
        result = subprocess.run(
            ["bash", "-n", str(script)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_dashboard_unit_is_loopback_only_and_uses_external_secrets() -> None:
    unit = (CLOUD / "astra-dashboard.service").read_text(encoding="utf-8")

    assert "EnvironmentFile=/etc/astra-emailautomation/astra.env" in unit
    assert "Environment=ASTRA_MACHINE_ID=cloud" in unit
    assert "Environment=ASTRA_DISABLE_DOTENV=1" in unit
    assert "Environment=DASHBOARD_ENABLE_LIVE_ACTIONS=1" in unit
    assert "Environment=DASHBOARD_ALLOW_AUTO_START=0" in unit
    assert "--host 127.0.0.1 --port 8000" in unit
    assert "--host 0.0.0.0" not in unit
    assert "Restart=on-failure" in unit


def test_sender_unit_is_cloud_locked_and_never_auto_enabled_by_bootstrap() -> None:
    unit = (CLOUD / "astra-sender.service").read_text(encoding="utf-8")
    bootstrap = (CLOUD / "bootstrap.sh").read_text(encoding="utf-8")

    assert "After=network-online.target" in unit
    assert "Environment=ASTRA_MACHINE_ID=cloud" in unit
    assert "EnvironmentFile=/etc/astra-emailautomation/astra.env" in unit
    assert "verify.sh --require-authority" in unit
    assert "/usr/bin/flock --nonblock --conflict-exit-code 75" in unit
    assert "send_shard.py --profile private_jc" in unit
    assert "Restart=on-failure" in unit
    assert "RestartPreventExitStatus=75" in unit
    assert "systemctl enable" not in bootstrap
    assert "systemctl start" not in bootstrap


def test_bootstrap_creates_required_runtime_directories_before_units() -> None:
    bootstrap = (CLOUD / "bootstrap.sh").read_text(encoding="utf-8")
    unit_install = bootstrap.index("for unit in")
    expected = {
        "data": "0750",
        "_important": "0750",
        ".runtime_handoff": "0700",
    }

    for relative, mode in expected.items():
        command = (
            'install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" '
            f'-m {mode} "${{REPO_ROOT}}/{relative}"'
        )
        assert command in bootstrap
        assert bootstrap.index(command) < unit_install


def test_runtime_directory_install_commands_are_restrictive_and_idempotent(
    tmp_path: Path,
) -> None:
    bootstrap = (CLOUD / "bootstrap.sh").read_text(encoding="utf-8")
    declarations = re.findall(
        r'install -d -o "\$\{SERVICE_USER\}" -g "\$\{SERVICE_GROUP\}" '
        r'-m (0[0-7]{3}) "\$\{REPO_ROOT\}/([^"]+)"',
        bootstrap,
    )
    modes_by_path = {relative: mode for mode, relative in declarations}

    assert modes_by_path == {
        "data": "0750",
        "_important": "0750",
        ".runtime_handoff": "0700",
    }
    runtime = tmp_path / ".runtime_handoff"
    for relative, mode in modes_by_path.items():
        subprocess.run(
            ["install", "-d", "-m", mode, str(tmp_path / relative)],
            check=True,
        )
    marker = runtime / "preserved"
    marker.write_text("fixture\n", encoding="utf-8")
    runtime.chmod(0o755)
    for relative, mode in modes_by_path.items():
        subprocess.run(
            ["install", "-d", "-m", mode, str(tmp_path / relative)],
            check=True,
        )

    assert marker.read_text(encoding="utf-8") == "fixture\n"
    assert stat.S_IMODE(runtime.stat().st_mode) == 0o700


def test_every_service_writable_path_is_created_or_managed_by_systemd() -> None:
    bootstrap = (CLOUD / "bootstrap.sh").read_text(encoding="utf-8")
    units = {
        path.name: path.read_text(encoding="utf-8")
        for path in CLOUD.glob("*.service")
    }

    for unit_name, unit in units.items():
        runtime_directories = {
            value.strip()
            for value in re.findall(r"^RuntimeDirectory=(.+)$", unit, re.MULTILINE)
        }
        writable_paths = re.findall(
            r"^ReadWritePaths=(.+)$",
            unit,
            re.MULTILINE,
        )
        for writable in writable_paths:
            writable = writable.strip()
            if writable.startswith("/opt/astra/emailautomation/"):
                relative = writable.removeprefix(
                    "/opt/astra/emailautomation/"
                )
                assert f'"${{REPO_ROOT}}/{relative}"' in bootstrap
            elif writable == "/var/lib/astra-backups":
                assert (
                    'install -d -o "${SERVICE_USER}" '
                    '-g "${SERVICE_GROUP}" -m 0700 "${BACKUP_DIR}"'
                ) in bootstrap
            elif writable.startswith("/run/"):
                assert Path(writable).name in runtime_directories, unit_name
            else:
                pytest.fail(
                    f"{unit_name} has unmanaged writable path: {writable}"
                )


def test_backup_and_tunnel_templates_are_fail_closed_examples() -> None:
    backup = (CLOUD / "backup.sh").read_text(encoding="utf-8")
    backup_unit = (CLOUD / "astra-backup.service").read_text(encoding="utf-8")
    timer = (CLOUD / "astra-backup.timer").read_text(encoding="utf-8")
    tunnel = (CLOUD / "cloudflared-config.example.yml").read_text(
        encoding="utf-8"
    )

    assert "process_blockers" in backup
    assert "active_job_files" in backup
    assert "RESTIC_PASSWORD_FILE" in backup
    assert 'restic backup \\' in backup
    for exclusion in (
        '--exclude ".env"',
        '--exclude ".env.*"',
        '--exclude "**/.env"',
        '--exclude "**/.env.*"',
        '--exclude "KEYS"',
        '--exclude "**/KEYS"',
        '--exclude "ACC GMAIL"',
        '--exclude "**/ACC GMAIL"',
    ):
        assert exclusion in backup
    assert "EnvironmentFile=/etc/astra-emailautomation/astra.env" in backup_unit
    assert "OnCalendar=" in timer
    assert "service: http://127.0.0.1:8000" in tunnel
    assert "service: http_status:404" in tunnel


def test_cloud_env_template_contains_placeholders_only() -> None:
    template = (CLOUD / "env.example").read_text(encoding="utf-8")

    assert "PRIVATE_JC_PASSWORD=REPLACE_" in template
    assert "DASHBOARD_AUTH_PASSWORD=REPLACE_" in template
    assert "DASHBOARD_SESSION_SECRET=REPLACE_" in template
    assert "ASTRA_EXPECTED_GIT_COMMIT=REPLACE_" in template
    assert "HANDOFF_MAC_REPO=REPLACE_" in template


def test_cloud_deployment_templates_contain_no_personal_home_paths() -> None:
    personal_home = re.compile(r"/Users/[^/\s]+/")

    for template in CLOUD.iterdir():
        if template.is_file():
            assert personal_home.search(template.read_text(encoding="utf-8")) is None


@pytest.mark.parametrize(
    "relative",
    [
        Path("KEYS"),
        Path("ACC GMAIL"),
        Path("nested/.env"),
        Path("nested/.env.cloud"),
        Path("nested/KEYS"),
        Path("nested/ACC GMAIL"),
    ],
)
def test_campaign_package_refuses_sensitive_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    relative: Path,
) -> None:
    monkeypatch.setattr(package_campaign_handoff, "ROOT", tmp_path)
    sensitive = tmp_path / relative
    sensitive.parent.mkdir(parents=True, exist_ok=True)
    sensitive.write_text("synthetic-test-value", encoding="utf-8")

    with pytest.raises(ValueError, match="Sensitive archive path is forbidden"):
        package_campaign_handoff._manifest_for(
            [sensitive],
            "synthetic-test-archive.tgz",
        )
