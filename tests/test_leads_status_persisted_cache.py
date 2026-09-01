from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import live_dashboard
import refresh_dashboard_snapshot_cache


def _write_cache(
    path: Path,
    *,
    mode: str = "cleaned",
    eligible: int = 15342,
    keep: int = 11221,
) -> None:
    payload = {
        "generated_at_utc": "2026-09-01T23:00:00+00:00",
        "hours": 24,
        "tail_lines": 12,
        "snapshot": {"profiles": []},
        "leads_status": {
            "status_cache_ready": True,
            "status_cache_source": "persisted_dashboard_refresh",
            "dispatch_source_mode": mode,
            "dispatch_eligible_row_count": eligible,
            "dispatch_source_options": {
                "cleaned": {
                    "dispatch_source_row_count": eligible,
                    "dispatch_eligible_row_count": eligible,
                },
                "triaged_keep": {
                    "dispatch_source_row_count": keep,
                    "dispatch_eligible_row_count": keep,
                },
            },
            "lead_check_status": {
                "state": "success",
                "status": "success",
            },
            "latest_auto_dispatch_preview_current": False,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_display_leads_status_uses_persisted_cache_without_full_rebuild(
    tmp_path,
):
    cache_path = tmp_path / "snapshot.json"
    _write_cache(cache_path)

    with patch.object(
        live_dashboard,
        "DASHBOARD_SNAPSHOT_CACHE_PATH",
        cache_path,
    ), patch.object(
        live_dashboard,
        "_combined_leads_status",
        side_effect=AssertionError(
            "full Lead Ops rebuild must not run for cached display status"
        ),
    ):
        live_dashboard._reset_snapshot_caches_for_tests()

        status = live_dashboard._display_leads_status()

    assert status["dispatch_source_mode"] == "cleaned"
    assert status["dispatch_eligible_row_count"] == 15342
    assert (
        status["dispatch_source_options"]["cleaned"][
            "dispatch_source_row_count"
        ]
        == 15342
    )
    assert (
        status["dispatch_source_options"]["triaged_keep"][
            "dispatch_source_row_count"
        ]
        == 11221
    )
    assert status["lead_check_status"]["state"] == "success"


def test_systemd_cache_miss_does_not_run_expensive_rebuild(tmp_path):
    missing_path = tmp_path / "missing.json"

    with patch.object(
        live_dashboard,
        "DASHBOARD_SNAPSHOT_CACHE_PATH",
        missing_path,
    ), patch.object(
        live_dashboard.runtime_control,
        "backend_name",
        return_value="systemd",
    ), patch.object(
        live_dashboard,
        "_combined_leads_status",
        side_effect=AssertionError(
            "production cache miss must not rebuild inside HTTP request"
        ),
    ):
        live_dashboard._reset_snapshot_caches_for_tests()

        status = live_dashboard._display_leads_status()

    assert status["status_cache_ready"] is False
    assert status["status_cache_source"] == "persisted_dashboard_refresh"
    assert "dispatch_eligible_row_count" not in status


def test_non_systemd_cache_miss_keeps_local_development_fallback(
    tmp_path,
):
    missing_path = tmp_path / "missing.json"
    expected = {
        "dispatch_source_mode": "cleaned",
        "dispatch_eligible_row_count": 15342,
    }

    with patch.object(
        live_dashboard,
        "DASHBOARD_SNAPSHOT_CACHE_PATH",
        missing_path,
    ), patch.object(
        live_dashboard.runtime_control,
        "backend_name",
        return_value="tmux",
    ), patch.object(
        live_dashboard,
        "_combined_leads_status",
        return_value=expected,
    ) as rebuild:
        live_dashboard._reset_snapshot_caches_for_tests()

        status = live_dashboard._display_leads_status()

    assert status == expected
    rebuild.assert_called_once_with()


def test_cached_leads_status_invalidates_when_atomic_file_changes(
    tmp_path,
):
    cache_path = tmp_path / "snapshot.json"
    _write_cache(cache_path, eligible=15342)

    with patch.object(
        live_dashboard,
        "DASHBOARD_SNAPSHOT_CACHE_PATH",
        cache_path,
    ):
        live_dashboard._reset_snapshot_caches_for_tests()

        first = live_dashboard._load_cached_leads_status()
        assert first is not None
        assert first["dispatch_eligible_row_count"] == 15342

        # Change both content and file size so the signature must change.
        _write_cache(
            cache_path,
            eligible=999,
            keep=888,
        )

        second = live_dashboard._load_cached_leads_status()

    assert second is not None
    assert second["dispatch_eligible_row_count"] == 999
    assert (
        second["dispatch_source_options"]["triaged_keep"][
            "dispatch_source_row_count"
        ]
        == 888
    )


def test_refresh_producer_persists_lead_ops_status_atomically(
    tmp_path,
):
    cache_path = tmp_path / "snapshot.json"

    leads = {
        "dispatch_source_mode": "cleaned",
        "dispatch_eligible_row_count": 15342,
        "dispatch_source_options": {
            "cleaned": {
                "dispatch_source_row_count": 15342,
            },
            "triaged_keep": {
                "dispatch_source_row_count": 11221,
            },
        },
    }

    with patch.object(
        refresh_dashboard_snapshot_cache,
        "CACHE_PATH",
        cache_path,
    ), patch.object(
        refresh_dashboard_snapshot_cache.dashboard,
        "_build_live_snapshot",
        return_value={"profiles": []},
    ), patch.object(
        refresh_dashboard_snapshot_cache.dashboard,
        "_combined_leads_status",
        return_value=leads,
    ):
        refresh_dashboard_snapshot_cache.main()

    payload = json.loads(cache_path.read_text(encoding="utf-8"))

    assert payload["snapshot"] == {"profiles": []}
    assert payload["leads_status"]["dispatch_source_mode"] == "cleaned"
    assert (
        payload["leads_status"]["dispatch_eligible_row_count"]
        == 15342
    )
    assert payload["leads_status"]["status_cache_ready"] is True
    assert (
        payload["leads_status"]["status_cache_source"]
        == "persisted_dashboard_refresh"
    )

    temporary_files = list(
        tmp_path.glob(".snapshot.json.*.tmp")
    )
    assert temporary_files == []



def test_snapshot_refresh_cannot_mask_new_leads_status(tmp_path):
    cache_path = tmp_path / "snapshot.json"
    _write_cache(cache_path, eligible=15342)

    with patch.object(
        live_dashboard,
        "DASHBOARD_SNAPSHOT_CACHE_PATH",
        cache_path,
    ):
        live_dashboard._reset_snapshot_caches_for_tests()

        first = live_dashboard._load_cached_leads_status()
        assert first is not None
        assert first["dispatch_eligible_row_count"] == 15342

        payload = json.loads(
            cache_path.read_text(encoding="utf-8")
        )
        payload["snapshot"] = {
            "profiles": [],
            "revision": "second",
        }
        payload["leads_status"][
            "dispatch_eligible_row_count"
        ] = 999

        # Deliberately alter valid JSON content and file size so
        # the file signature must change.
        payload["test_padding"] = "SECOND-CACHE-VERSION"
        cache_path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

        # Refresh the unrelated dashboard snapshot first.
        snapshot = live_dashboard._load_cached_live_snapshot()
        assert snapshot is not None
        assert snapshot["revision"] == "second"

        # Lead status must still notice that ITS cached signature
        # belongs to the previous atomic file version.
        second = live_dashboard._load_cached_leads_status()

    assert second is not None
    assert second["dispatch_eligible_row_count"] == 999


def test_leads_refresh_cannot_mask_new_dashboard_snapshot(tmp_path):
    cache_path = tmp_path / "snapshot.json"
    _write_cache(cache_path, eligible=15342)

    with patch.object(
        live_dashboard,
        "DASHBOARD_SNAPSHOT_CACHE_PATH",
        cache_path,
    ):
        live_dashboard._reset_snapshot_caches_for_tests()

        first_snapshot = (
            live_dashboard._load_cached_live_snapshot()
        )
        assert first_snapshot is not None

        payload = json.loads(
            cache_path.read_text(encoding="utf-8")
        )
        payload["snapshot"] = {
            "profiles": [],
            "revision": "third",
        }
        payload["leads_status"][
            "dispatch_eligible_row_count"
        ] = 777

        payload["test_padding"] = "THIRD-CACHE-VERSION-LONGER"
        cache_path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

        # Refresh Lead Ops first.
        leads = live_dashboard._load_cached_leads_status()
        assert leads is not None
        assert leads["dispatch_eligible_row_count"] == 777

        # Dashboard snapshot must independently notice that its
        # own cached signature is stale.
        second_snapshot = (
            live_dashboard._load_cached_live_snapshot()
        )

    assert second_snapshot is not None
    assert second_snapshot["revision"] == "third"
