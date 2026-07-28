from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TOP_LEVELS = {"_important", "data", "run_logs"}
RUNTIME_ISOLATED_TEST_MODULES = {
    "test_dashboard_core.py",
    "test_important_leads_verify.py",
    "test_important_leads_workflow.py",
    "test_live_dashboard.py",
    "test_live_dashboard_auth.py",
    "test_private_bounce_hygiene.py",
    "test_retemplate_warm_queue.py",
    "test_send_shard.py",
    "test_sendgrid_hygiene.py",
    "test_web_dashboard_app.py",
}


def _isolated_runtime_path(value: Path, runtime_root: Path) -> Path | None:
    try:
        relative = value.resolve(strict=False).relative_to(REPOSITORY_ROOT)
    except (OSError, ValueError):
        return None
    if not relative.parts or relative.parts[0] not in RUNTIME_TOP_LEVELS:
        return None
    if relative.parts[:2] == ("data", "reference"):
        return None
    return runtime_root / relative


def _patch_runtime_path_defaults(monkeypatch: pytest.MonkeyPatch, runtime_root: Path) -> None:
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
                isolated = _isolated_runtime_path(value, runtime_root)
                if isolated is not None:
                    monkeypatch.setattr(module, name, isolated)
                continue
            if not inspect.isfunction(value) or id(value) in patched_functions:
                continue
            patched_functions.add(id(value))

            defaults = value.__defaults__
            if defaults:
                isolated_defaults = tuple(
                    (_isolated_runtime_path(item, runtime_root) or item)
                    if isinstance(item, Path)
                    else item
                    for item in defaults
                )
                if isolated_defaults != defaults:
                    monkeypatch.setattr(value, "__defaults__", isolated_defaults)

            kwdefaults = value.__kwdefaults__
            if kwdefaults:
                isolated_kwdefaults = {
                    key: (_isolated_runtime_path(item, runtime_root) or item)
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
    _patch_runtime_path_defaults(monkeypatch, runtime_root)

    settings_module = sys.modules.get("settings")
    if settings_module is None:
        raise RuntimeError("Dashboard runtime isolation requires the settings module.")
    monkeypatch.setattr(settings_module, "APP_ROOT", runtime_root)
    settings_module.ensure_dirs()
    return runtime_root
