from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TOP_LEVELS = {"_important", "data", "run_logs"}
CONFIGURED_RUNTIME_DIRS = {
    "DATA_DIR": ("data",),
    "UPLOADS_DIR": ("data", "uploads"),
    "CLEANED_DIR": ("data", "cleaned"),
    "SHARDS_DIR": ("data", "shards"),
    "LOGS_DIR": ("data", "logs"),
    "STATE_DIR": ("data", "state"),
    "TMP_DIR": ("data", "tmp"),
}
RUNTIME_ISOLATED_TEST_MODULES = {
    "test_active_campaign_manifest.py",
    "test_dashboard_core.py",
    "test_important_leads_verify.py",
    "test_important_leads_workflow.py",
    "test_live_dashboard.py",
    "test_live_dashboard_auth.py",
    "test_private_bounce_hygiene.py",
    "test_retemplate_warm_queue.py",
    "test_send_shard.py",
    "test_send_shard_interrupt_safety.py",
    "test_sendgrid_hygiene.py",
    "test_test_runtime_isolation.py",
    "test_web_dashboard_app.py",
}


def _isolated_runtime_path(
    value: Path,
    runtime_root: Path,
    configured_roots: tuple[tuple[Path, tuple[str, ...]], ...] = (),
) -> Path | None:
    try:
        relative = value.resolve(strict=False).relative_to(REPOSITORY_ROOT)
    except (OSError, ValueError):
        relative = None
    if relative is not None:
        if not relative.parts or relative.parts[0] not in RUNTIME_TOP_LEVELS:
            return None
        if relative.parts[:2] == ("data", "reference"):
            return None
        return runtime_root / relative

    for configured, target_parts in configured_roots:
        try:
            relative = value.resolve(strict=False).relative_to(
                configured.resolve(strict=False)
            )
        except (OSError, ValueError):
            continue
        return runtime_root.joinpath(*target_parts, relative)
    return None


def _patch_runtime_path_defaults(monkeypatch: pytest.MonkeyPatch, runtime_root: Path) -> None:
    settings_module = sys.modules.get("settings")
    configured_roots = []
    if settings_module is not None:
        for attribute, target_parts in CONFIGURED_RUNTIME_DIRS.items():
            configured = getattr(settings_module, attribute, None)
            if isinstance(configured, Path):
                configured_roots.append((configured, target_parts))
    configured_roots.sort(key=lambda item: len(item[0].parts), reverse=True)
    frozen_roots = tuple(configured_roots)

    patched_functions: set[int] = set()
    for module in tuple(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            Path(module_file).resolve().relative_to(REPOSITORY_ROOT)
        except (OSError, ValueError):
            continue

        for name, value in tuple(vars(module).items()):
            if isinstance(value, Path):
                isolated = _isolated_runtime_path(value, runtime_root, frozen_roots)
                if isolated is not None:
                    monkeypatch.setattr(module, name, isolated)
                continue
            if not inspect.isfunction(value) or id(value) in patched_functions:
                continue
            patched_functions.add(id(value))

            defaults = value.__defaults__
            if defaults:
                isolated_defaults = tuple(
                    (_isolated_runtime_path(item, runtime_root, frozen_roots) or item)
                    if isinstance(item, Path)
                    else item
                    for item in defaults
                )
                if isolated_defaults != defaults:
                    monkeypatch.setattr(value, "__defaults__", isolated_defaults)

            kwdefaults = value.__kwdefaults__
            if kwdefaults:
                isolated_kwdefaults = {
                    key: (_isolated_runtime_path(item, runtime_root, frozen_roots) or item)
                    if isinstance(item, Path)
                    else item
                    for key, item in kwdefaults.items()
                }
                if isolated_kwdefaults != kwdefaults:
                    monkeypatch.setattr(value, "__kwdefaults__", isolated_kwdefaults)


@pytest.fixture(autouse=True)
def isolate_dashboard_runtime(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path | None:
    if request.path.name not in RUNTIME_ISOLATED_TEST_MODULES:
        return None

    runtime_root = tmp_path / "dashboard_runtime"
    runtime_root.mkdir()
    data_root = runtime_root / "data"
    monkeypatch.setenv("ASTRA_DISABLE_DOTENV", "1")
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setenv("UPLOADS_DIR", str(data_root / "uploads"))
    monkeypatch.setenv("CLEANED_DIR", str(data_root / "cleaned"))
    monkeypatch.setenv("SHARDS_DIR", str(data_root / "shards"))
    monkeypatch.setenv("LOGS_DIR", str(data_root / "logs"))
    monkeypatch.setenv("STATE_DIR", str(data_root / "state"))
    monkeypatch.setenv("TMP_DIR", str(data_root / "tmp"))
    _patch_runtime_path_defaults(monkeypatch, runtime_root)

    settings_module = sys.modules.get("settings")
    if settings_module is None:
        raise RuntimeError("Dashboard runtime isolation requires the settings module.")
    monkeypatch.setattr(settings_module, "APP_ROOT", runtime_root)
    settings_module.ensure_dirs()
    return runtime_root
