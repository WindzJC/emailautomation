from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
import time
from unittest.mock import patch

import dashboard_core


def _bounds() -> tuple[datetime, datetime]:
    start = datetime(2026, 8, 11, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _write_log(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    body = ["TimestampUTC,Email,Status,Info\n"]
    for timestamp, email, status, info in rows:
        body.append(f"{timestamp},{email},{status},{info}\n")
    path.write_text("".join(body), encoding="utf-8")


def test_profile_log_metrics_cache_reuses_unchanged_log(tmp_path: Path) -> None:
    path = tmp_path / "sender.csv"
    _write_log(
        path,
        [
            ("2026-08-11T01:00:00+00:00", "a@example.test", "SENT", "ok"),
            ("2026-08-11T02:00:00+00:00", "b@example.test", "SKIP", "skip"),
        ],
    )
    start, end = _bounds()
    dashboard_core._reset_profile_log_metrics_cache_for_tests()

    original = dashboard_core.read_csv_rows
    with patch.object(
        dashboard_core,
        "read_csv_rows",
        wraps=original,
    ) as read_rows:
        first = dashboard_core._profile_log_metrics(
            path,
            start=start,
            end=end,
            always_send_email="",
        )
        second = dashboard_core._profile_log_metrics(
            path,
            start=start,
            end=end,
            always_send_email="",
        )

    assert first == second
    assert first["sent_today"] == 1
    assert first["skipped_today"] == 1
    assert read_rows.call_count == 1


def test_profile_log_metrics_cache_invalidates_when_log_changes(tmp_path: Path) -> None:
    path = tmp_path / "sender.csv"
    _write_log(
        path,
        [("2026-08-11T01:00:00+00:00", "a@example.test", "SENT", "ok")],
    )
    start, end = _bounds()
    dashboard_core._reset_profile_log_metrics_cache_for_tests()

    first = dashboard_core._profile_log_metrics(
        path,
        start=start,
        end=end,
        always_send_email="",
    )
    assert first["sent_today"] == 1

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "2026-08-11T02:00:00+00:00,b@example.test,SENT,ok\n"
        )

    second = dashboard_core._profile_log_metrics(
        path,
        start=start,
        end=end,
        always_send_email="",
    )
    assert second["sent_today"] == 2
    assert second["last_email"] == "b@example.test"


def test_profile_log_metrics_preserves_latest_run_boundary(tmp_path: Path) -> None:
    path = tmp_path / "sender.csv"
    _write_log(
        path,
        [
            ("2026-08-11T01:00:00+00:00", "marker@example.test", "SENT", "start1"),
            ("2026-08-11T02:00:00+00:00", "a@example.test", "SENT", "ok"),
            ("2026-08-11T03:00:00+00:00", "b@example.test", "SKIP", "skip"),
            ("2026-08-11T04:00:00+00:00", "marker@example.test", "SENT", "start2"),
            ("2026-08-11T05:00:00+00:00", "c@example.test", "SENT", "ok"),
            ("2026-08-11T06:00:00+00:00", "d@example.test", "ERROR", "bad"),
        ],
    )
    start, end = _bounds()
    dashboard_core._reset_profile_log_metrics_cache_for_tests()

    metrics = dashboard_core._profile_log_metrics(
        path,
        start=start,
        end=end,
        always_send_email="marker@example.test",
    )

    assert metrics["sent_today"] == 4
    assert metrics["skipped_today"] == 1
    assert metrics["errors_today"] == 1
    assert metrics["run_sent"] == 2
    assert metrics["run_skipped"] == 0
    assert metrics["run_errors"] == 1
    assert metrics["run_started_at"] == datetime(
        2026, 8, 11, 4, 0, tzinfo=timezone.utc
    )
    assert metrics["last_email"] == "d@example.test"
    assert metrics["last_status"] == "ERROR"


def test_profile_log_metrics_singleflights_concurrent_miss(tmp_path: Path) -> None:
    path = tmp_path / "sender.csv"
    _write_log(
        path,
        [("2026-08-11T01:00:00+00:00", "a@example.test", "SENT", "ok")],
    )
    start, end = _bounds()
    dashboard_core._reset_profile_log_metrics_cache_for_tests()

    entered = threading.Event()
    release = threading.Event()
    calls = 0
    calls_lock = threading.Lock()
    real_compute = dashboard_core._compute_profile_log_metrics

    def slow_compute(*args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return real_compute(*args, **kwargs)

    def load():
        return dashboard_core._profile_log_metrics(
            path,
            start=start,
            end=end,
            always_send_email="",
        )

    with patch.object(
        dashboard_core,
        "_compute_profile_log_metrics",
        side_effect=slow_compute,
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(load)
            assert entered.wait(timeout=5)
            second = pool.submit(load)
            time.sleep(0.05)
            release.set()
            first_result = first.result(timeout=5)
            second_result = second.result(timeout=5)

    assert first_result == second_result
    assert calls == 1
