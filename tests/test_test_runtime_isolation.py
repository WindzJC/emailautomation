from __future__ import annotations

import os
from pathlib import Path

import important_leads_workflow
import runtime_audit
import settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_writers_and_subprocess_environment_are_isolated() -> None:
    runtime_root = settings.APP_ROOT
    assert runtime_root != REPOSITORY_ROOT
    assert settings.DATA_DIR == runtime_root / "data"
    assert runtime_audit.HEARTBEAT_PATH == runtime_root / "data/state/runtime_heartbeat.json"
    assert runtime_audit.LIFECYCLE_PATH == runtime_root / "data/state/runtime_lifecycle.jsonl"
    assert (
        important_leads_workflow._archive_assigned_dispatch_preview.__defaults__[0]
        == runtime_root / "data/state/dispatch_previews"
    )

    assert os.environ["ASTRA_DISABLE_DOTENV"] == "1"
    assert Path(os.environ["DATA_DIR"]) == runtime_root / "data"
    assert Path(os.environ["SHARDS_DIR"]) == runtime_root / "data/shards"
    assert Path(os.environ["LOGS_DIR"]) == runtime_root / "data/logs"
    assert Path(os.environ["STATE_DIR"]) == runtime_root / "data/state"
