from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dashboard_core
import provider_pacing
import sendgrid_hygiene


class DashboardCoreTests(unittest.TestCase):
    def test_infer_runtime_state_detects_cooldown(self) -> None:
        state, label, note = dashboard_core.infer_runtime_state(
            "email",
            False,
            "[1/1663] SENT debbie@example.com\nBATCH: sent=1 total=1 remaining_estimate=99 next_sleep_seconds=180",
        )
        self.assertEqual("cooldown", state)
        self.assertEqual("Cooldown", label)
        self.assertIn("180s", note)

    def test_infer_runtime_state_detects_scheduled_stop(self) -> None:
        state, label, note = dashboard_core.infer_runtime_state(
            "bash",
            False,
            "STOP: schedule_end reached (--stop_at_local).\njc@host:/repo$",
        )
        self.assertEqual("scheduled_stop", state)
        self.assertEqual("Scheduled Stop", label)
        self.assertIn("schedule", note.lower())

    def test_build_snapshot_uses_timestamp_fallback_for_nonunique_email(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            fake_now = dashboard_core.datetime(2026, 3, 13, 16, 0, 0, tzinfo=dashboard_core.timezone.utc)
            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                },
                "sendgrid_beta": {
                    "provider": "sendgrid",
                    "csv": "recipients_beta.csv",
                    "log": "sendgrid_beta_log.csv",
                    "from_email": "beta@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                },
            }
            self._write_recipients(base / "recipients_alpha.csv", "shared@example.com")
            self._write_recipients(base / "recipients_beta.csv", "shared@example.com")
            self._write_log(
                base / "sendgrid_alpha_log.csv",
                [
                    ("2026-03-13T12:00:00+00:00", "shared@example.com", "SENT", ""),
                ],
            )
            self._write_log(
                base / "sendgrid_beta_log.csv",
                [
                    ("2026-03-13T15:00:00+00:00", "shared@example.com", "SENT", ""),
                ],
            )
            self._write_events(
                base / dashboard_core.WEBHOOK_EVENTS_JSONL,
                [
                    {
                        "processed_at_raw": "1773403230",
                        "processed_at_utc": "2026-03-13T12:00:30+00:00",
                        "message_id": "",
                        "email": "shared@example.com",
                        "domain": "example.com",
                        "subject": "",
                        "status": "delivered",
                        "code": "250",
                        "response": "250 OK",
                        "source_log": dashboard_core.WEBHOOK_EVENTS_JSONL,
                    }
                ],
            )

            with self._patched_dashboard_context(base, profiles), patch.object(
                dashboard_core,
                "dashboard_now",
                return_value=fake_now.astimezone(dashboard_core.DASHBOARD_TIMEZONE),
            ):
                class FrozenDateTime(dashboard_core.datetime):
                    @classmethod
                    def now(cls, tz=None):
                        if tz is None:
                            return fake_now.replace(tzinfo=None)
                        return fake_now.astimezone(tz)

                with patch.object(dashboard_core, "datetime", FrozenDateTime):
                    snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        self.assertEqual({"sendgrid_alpha": 1}, snapshot["activity_summary"]["by_profile"])
        self.assertEqual({"email_time": 1}, snapshot["activity_summary"]["by_attribution_source"])
        alpha = next(profile for profile in snapshot["profiles"] if profile["name"] == "sendgrid_alpha")
        beta = next(profile for profile in snapshot["profiles"] if profile["name"] == "sendgrid_beta")
        self.assertEqual(1, alpha["webhook"]["summary"]["delivered"])
        self.assertEqual(0, beta["webhook"]["summary"]["delivered"])

    def test_build_snapshot_leaves_ambiguous_shared_email_unmapped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            fake_now = dashboard_core.datetime(2026, 3, 13, 16, 0, 0, tzinfo=dashboard_core.timezone.utc)
            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                },
                "sendgrid_beta": {
                    "provider": "sendgrid",
                    "csv": "recipients_beta.csv",
                    "log": "sendgrid_beta_log.csv",
                    "from_email": "beta@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                },
            }
            self._write_recipients(base / "recipients_alpha.csv", "shared@example.com")
            self._write_recipients(base / "recipients_beta.csv", "shared@example.com")
            self._write_log(
                base / "sendgrid_alpha_log.csv",
                [
                    ("2026-03-13T12:00:00+00:00", "shared@example.com", "SENT", ""),
                ],
            )
            self._write_log(
                base / "sendgrid_beta_log.csv",
                [
                    ("2026-03-13T12:00:00+00:00", "shared@example.com", "SENT", ""),
                ],
            )
            self._write_events(
                base / dashboard_core.WEBHOOK_EVENTS_JSONL,
                [
                    {
                        "processed_at_raw": "1773403200",
                        "processed_at_utc": "2026-03-13T12:00:00+00:00",
                        "message_id": "",
                        "email": "shared@example.com",
                        "domain": "example.com",
                        "subject": "",
                        "status": "processed",
                        "code": "",
                        "response": "<shared@example.com>",
                        "source_log": dashboard_core.WEBHOOK_EVENTS_JSONL,
                    }
                ],
            )

            with self._patched_dashboard_context(base, profiles), patch.object(
                dashboard_core,
                "dashboard_now",
                return_value=fake_now.astimezone(dashboard_core.DASHBOARD_TIMEZONE),
            ):
                class FrozenDateTime(dashboard_core.datetime):
                    @classmethod
                    def now(cls, tz=None):
                        if tz is None:
                            return fake_now.replace(tzinfo=None)
                        return fake_now.astimezone(tz)

                with patch.object(dashboard_core, "datetime", FrozenDateTime):
                    snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        self.assertEqual({"unmapped": 1}, snapshot["activity_summary"]["by_profile"])
        self.assertEqual({"unmapped": 1}, snapshot["activity_summary"]["by_attribution_source"])
        self.assertEqual(1, snapshot["summary"]["recent_unmapped"])

    def test_build_snapshot_exposes_dashboard_send_cap_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                }
            }
            (base / "dashboard_run_settings.json").write_text(
                json.dumps({"send_cap_per_profile": 25, "updated_at_utc": "2026-03-25T01:00:00+00:00"}),
                encoding="utf-8",
            )
            self._write_recipients(base / "recipients_alpha.csv", "reader@example.com")
            self._write_log(base / "sendgrid_alpha_log.csv", [])

            with self._patched_dashboard_context(base, profiles):
                snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        self.assertEqual(25, snapshot["controls"]["send_cap_per_profile"])
        self.assertEqual(25, snapshot["controls"]["estimated_total_if_start_all"])
        self.assertEqual(25, snapshot["profiles"][0]["max_total"])
        self.assertEqual(100, snapshot["profiles"][0]["configured_max_total"])

    def test_start_sendgrid_profile_uses_dashboard_send_cap_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")
            settings_path = base / "dashboard_run_settings.json"
            settings_path.write_text(json.dumps({"send_cap_per_profile": 25}), encoding="utf-8")

            calls: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                calls.append(list(cmd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                }
            }

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SHARDS_DIR=base,
                LOGS_DIR=base,
                STATE_DIR=base,
                ACTIVITY_LOG_PATH=base / "sendgridlogs",
                SUPPRESSION_CSV=base / "sendgrid_suppressions.csv",
                NORMALIZE_REPORT_PATH=base / "sendgrid_shard_normalize_report.json",
                WEBHOOK_EVENTS_PATH=base / dashboard_core.WEBHOOK_EVENTS_JSONL,
                WEBHOOK_DEDUPE_PATH=base / dashboard_core.WEBHOOK_DEDUPE_DB,
                LOG_RESET_BACKUP_ROOT=base / "backups",
                PROFILES=profiles,
                SENDGRID_PROFILES=["sendgrid_alpha"],
                DASHBOARD_PROFILES=["sendgrid_alpha"],
                START_ALL_PROFILES=["sendgrid_alpha"],
                PYTHON_BIN=python_bin,
                DASHBOARD_RUN_SETTINGS_PATH=settings_path,
                ensure_sendgrid_session_layout=lambda session="sendgrid": (True, "ok"),
                tmux_pane_map=lambda session="sendgrid": {"0": {"cmd": "bash", "dead": "0"}},
                _load_env_value=lambda name: "SG.test-key",
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, _ = dashboard_core.start_sendgrid_profile("sendgrid_alpha", 0)

        self.assertTrue(ok)
        self.assertIn(
            [str(python_bin), "send_shard.py", "--profile", "sendgrid_alpha", "--preflight", "--max_total", "25"],
            calls,
        )
        send_keys_commands = [cmd for cmd in calls if cmd[:3] == ["tmux", "send-keys", "-t"]]
        self.assertTrue(any("--max_total 25" in " ".join(cmd) for cmd in send_keys_commands))

    def test_start_private_profile_requires_password_env_value(self) -> None:
        profiles = {
            "private_jc": {
                "provider": "private",
                "csv": "recipients_private_jc.csv",
                "log": "private_jc_log.csv",
                "from_email": "jc@astraproductions.co",
                "max_total": 5,
                "password_env": "PRIVATE_JC_PASSWORD",
                "dashboard_enabled": True,
                "dashboard_manual_only": True,
                "tmux_session": "private_jc",
            }
        }

        with patch.multiple(
            dashboard_core,
            PROFILES=profiles,
            SENDGRID_PROFILES=[],
            DASHBOARD_PROFILES=["private_jc"],
            START_ALL_PROFILES=[],
            _load_env_value=lambda name: "",
            load_dashboard_recovery_timer=lambda: {
                "private_jc_recovery_start_at_utc": "",
                "private_jc_recovery_note": "",
                "updated_at_utc": "",
            },
        ):
            ok, message = dashboard_core.start_private_profile("private_jc", session="private_jc")

        self.assertFalse(ok)
        self.assertEqual("PRIVATE_JC_PASSWORD is not available in the dashboard environment.", message)

    def test_start_private_profile_blocks_while_provider_cooldown_active(self) -> None:
        profiles = {
            "private_jc": {
                "provider": "private",
                "csv": "recipients_private_jc.csv",
                "log": "private_jc_log.csv",
                "from_email": "jc@astraproductions.co",
                "cooldown_seconds": 90,
                "max_total": 0,
                "password_env": "PRIVATE_JC_PASSWORD",
                "dashboard_enabled": True,
                "dashboard_manual_only": True,
                "tmux_session": "private_jc",
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "provider_pacing_state.json"
            now = dashboard_core.datetime(2026, 4, 3, 0, 0, 0, tzinfo=dashboard_core.timezone.utc)
            current_time = now + dashboard_core.timedelta(minutes=15)
            with patch.object(provider_pacing, "PROVIDER_PACING_STATE_PATH", state_path), patch.object(
                provider_pacing,
                "_now_utc",
                return_value=current_time,
            ):
                provider_pacing.record_provider_throttle(
                    "private_jc",
                    "private",
                    75 * 60,
                    90,
                    "450 4.7.1 sending limit reached",
                    now=now,
                )
                with patch.multiple(
                    dashboard_core,
                    PROFILES=profiles,
                    SENDGRID_PROFILES=[],
                    DASHBOARD_PROFILES=["private_jc"],
                    START_ALL_PROFILES=[],
                    _load_env_value=lambda name: "secret",
                ):
                    ok, message = dashboard_core.start_private_profile("private_jc", session="private_jc")

        self.assertFalse(ok)
        self.assertIn("provider cooldown", message.lower())

    def test_build_run_status_items_ignores_idle_profiles_during_partial_run(self) -> None:
        base_fields = {
            "csv_path": "recipients.csv",
            "log_path": "sender.log",
            "max_total": 100,
            "cooldown_seconds": 120,
            "cooldown_remaining_seconds": 0,
            "pending_count": 0,
            "run_started_at": "",
            "run_sent": 0,
            "run_errors": 0,
            "run_skipped": 0,
            "sent_today": 0,
            "errors_today": 0,
            "skipped_today": 0,
            "last_status": "",
            "last_email": "",
            "last_info": "",
            "last_timestamp": "",
            "last_age": "-",
            "tmux_dead": False,
            "tmux_command": "bash",
            "tmux_tail": "",
        }
        snapshots = [
            dashboard_core.ProfileSnapshot(
                name="sendgrid_alpha",
                pane_index=0,
                tmux_running=True,
                runtime_state="running",
                runtime_label="Running",
                runtime_note="Sender is actively processing recipients.",
                **base_fields,
            ),
            dashboard_core.ProfileSnapshot(
                name="sendgrid_beta",
                pane_index=1,
                tmux_running=False,
                runtime_state="stopped",
                runtime_label="Stopped",
                runtime_note="Pane is idle.",
                **base_fields,
            ),
        ]

        items = dashboard_core.build_run_status_items(
            "running",
            snapshots,
            recent_failures=0,
            historical_errors_today=0,
        )

        self.assertEqual(["No operational issues detected."], items)

    def test_build_trend_panels_aggregates_accepts_delivery_failures_and_opens(self) -> None:
        fake_now_utc = dashboard_core.datetime(2026, 3, 13, 12, 5, 0, tzinfo=dashboard_core.timezone.utc)
        attempts = [
            dashboard_core.SendAttempt(
                profile="sendgrid_alpha",
                email="reader@example.com",
                timestamp=dashboard_core.datetime(2026, 3, 13, 11, 0, 0, tzinfo=dashboard_core.timezone.utc),
                message_id="msg-1",
            ),
            dashboard_core.SendAttempt(
                profile="sendgrid_alpha",
                email="probe@example.com",
                timestamp=dashboard_core.datetime(2026, 3, 13, 11, 30, 0, tzinfo=dashboard_core.timezone.utc),
                message_id="msg-probe",
            ),
            dashboard_core.SendAttempt(
                profile="sendgrid_beta",
                email="second@example.com",
                timestamp=dashboard_core.datetime(2026, 3, 12, 15, 0, 0, tzinfo=dashboard_core.timezone.utc),
                message_id="msg-2",
            ),
        ]
        events = [
            {
                "processed_at_utc": "2026-03-13T11:10:00+00:00",
                "status": "delivered",
                "email": "reader@example.com",
            },
            {
                "processed_at_utc": "2026-03-13T11:30:00+00:00",
                "status": "open",
                "email": "reader@example.com",
            },
            {
                "processed_at_utc": "2026-03-12T15:20:00+00:00",
                "status": "bounce",
                "email": "second@example.com",
            },
            {
                "processed_at_utc": "2026-03-10T12:00:00+00:00",
                "status": "delivered",
                "email": "older@example.com",
            },
        ]
        profiles = {
            "sendgrid_alpha": {
                "provider": "sendgrid",
                "csv": "recipients_alpha.csv",
                "log": "sendgrid_alpha_log.csv",
                "from_email": "alpha@example.com",
                "always_send": "probe@example.com",
                "max_total": 100,
            },
            "sendgrid_beta": {
                "provider": "sendgrid",
                "csv": "recipients_beta.csv",
                "log": "sendgrid_beta_log.csv",
                "from_email": "beta@example.com",
                "always_send": "probe@example.com",
                "max_total": 100,
            },
        }

        with patch.object(dashboard_core, "dashboard_now", return_value=fake_now_utc.astimezone(dashboard_core.DASHBOARD_TIMEZONE)):
            with patch.multiple(
                dashboard_core,
                PROFILES=profiles,
                SENDGRID_PROFILES=list(profiles.keys()),
                DASHBOARD_PROFILES=list(profiles.keys()),
                START_ALL_PROFILES=list(profiles.keys()),
            ):
                trends = dashboard_core.build_trend_panels(attempts, events)

        self.assertEqual(2, trends["24h"]["metrics"]["accepted"]["total"])
        self.assertEqual(1, trends["24h"]["metrics"]["delivered"]["total"])
        self.assertEqual(1, trends["24h"]["metrics"]["failures"]["total"])
        self.assertEqual(1, trends["24h"]["metrics"]["opened"]["total"])
        self.assertEqual(2, trends["7d"]["metrics"]["delivered"]["total"])

    def test_build_profile_webhook_panels_tracks_unique_opens_and_clicks(self) -> None:
        activity = {
            "recent": [
                {
                    "profile": "sendgrid_alpha",
                    "status": "open",
                    "message_id": "abc123.recvd-1",
                    "email": "reader@example.com",
                    "processed_at_utc": "2026-03-13T12:00:00+00:00",
                    "response": "",
                },
                {
                    "profile": "sendgrid_alpha",
                    "status": "open",
                    "message_id": "abc123.recvd-1",
                    "email": "reader@example.com",
                    "processed_at_utc": "2026-03-13T12:05:00+00:00",
                    "response": "",
                },
                {
                    "profile": "sendgrid_alpha",
                    "status": "click",
                    "message_id": "abc123.recvd-1",
                    "email": "reader@example.com",
                    "processed_at_utc": "2026-03-13T12:06:00+00:00",
                    "response": "",
                },
                {
                    "profile": "sendgrid_alpha",
                    "status": "click",
                    "message_id": "def456.recvd-1",
                    "email": "second@example.com",
                    "processed_at_utc": "2026-03-13T12:07:00+00:00",
                    "response": "",
                },
            ]
        }

        panels = dashboard_core.build_profile_webhook_panels(activity, ["sendgrid_alpha"])
        summary = panels["sendgrid_alpha"]["summary"]

        self.assertEqual(2, summary["open"])
        self.assertEqual(1, summary["open_unique"])
        self.assertEqual(2, summary["click"])
        self.assertEqual(2, summary["click_unique"])

    def test_domain_breakdown_and_awaiting_age_buckets(self) -> None:
        fake_now = dashboard_core.datetime(2026, 3, 13, 12, 30, 0, tzinfo=dashboard_core.timezone.utc)
        attempts = [
            dashboard_core.SendAttempt(
                profile="sendgrid_alpha",
                email="reader@gmail.com",
                timestamp=dashboard_core.datetime(2026, 3, 13, 12, 25, 0, tzinfo=dashboard_core.timezone.utc),
                message_id="msg-1",
            ),
            dashboard_core.SendAttempt(
                profile="sendgrid_alpha",
                email="older@yahoo.com",
                timestamp=dashboard_core.datetime(2026, 3, 13, 11, 0, 0, tzinfo=dashboard_core.timezone.utc),
                message_id="msg-2",
            ),
            dashboard_core.SendAttempt(
                profile="sendgrid_alpha",
                email="awaiting@example.net",
                timestamp=dashboard_core.datetime(2026, 3, 13, 11, 30, 0, tzinfo=dashboard_core.timezone.utc),
                message_id="msg-3",
            ),
        ]
        events = [
            {
                "processed_at_utc": "2026-03-13T12:26:00+00:00",
                "status": "delivered",
                "message_id": "msg-1.recvd-1",
                "email": "reader@gmail.com",
                "domain": "gmail.com",
            },
            {
                "processed_at_utc": "2026-03-13T12:27:00+00:00",
                "status": "open",
                "message_id": "msg-1.recvd-1",
                "email": "reader@gmail.com",
                "domain": "gmail.com",
            },
            {
                "processed_at_utc": "2026-03-13T12:28:00+00:00",
                "status": "open",
                "message_id": "msg-1.recvd-1",
                "email": "reader@gmail.com",
                "domain": "gmail.com",
            },
            {
                "processed_at_utc": "2026-03-13T11:10:00+00:00",
                "status": "bounce",
                "message_id": "msg-2.recvd-1",
                "email": "older@yahoo.com",
                "domain": "yahoo.com",
            },
        ]
        profiles = {
            "sendgrid_alpha": {
                "provider": "sendgrid",
                "csv": "recipients_alpha.csv",
                "log": "sendgrid_alpha_log.csv",
                "from_email": "alpha@example.com",
                "always_send": "probe@example.com",
                "max_total": 100,
            }
        }

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime):
            with patch.object(dashboard_core, "dashboard_now", return_value=fake_now.astimezone(dashboard_core.DASHBOARD_TIMEZONE)):
                with patch.multiple(
                    dashboard_core,
                    PROFILES=profiles,
                    SENDGRID_PROFILES=list(profiles.keys()),
                    DASHBOARD_PROFILES=list(profiles.keys()),
                    START_ALL_PROFILES=list(profiles.keys()),
                ):
                    domains = dashboard_core.build_domain_breakdown(attempts, events, hours=24)
                    buckets = dashboard_core.build_awaiting_age_buckets(attempts, events, list(profiles.keys()))

        gmail = next(row for row in domains if row["domain"] == "gmail.com")
        yahoo = next(row for row in domains if row["domain"] == "yahoo.com")
        self.assertEqual(1, gmail["accepted"])
        self.assertEqual(1, gmail["delivered"])
        self.assertEqual(2, gmail["open_total"])
        self.assertEqual(1, gmail["open_unique"])
        self.assertEqual(1, yahoo["bounce"])
        self.assertEqual(1, yahoo["failures"])
        self.assertEqual(1, buckets["sendgrid_alpha"]["h1_to_24"])

    def test_build_threshold_alerts_flags_backlog_unmapped_stale_and_errors(self) -> None:
        profile_dicts = [
            {"name": "sendgrid_alpha", "awaiting_outcome": 6, "run_errors": 1, "runtime_state": "running"},
            {"name": "sendgrid_beta", "awaiting_outcome": 5, "run_errors": 0, "runtime_state": "finished"},
        ]
        fake_now = dashboard_core.datetime(2026, 3, 13, 12, 30, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime):
            alerts = dashboard_core.build_threshold_alerts(
                session_label="running",
                active_profiles=1,
                recent_failures=2,
                recent_unmapped=14,
                total_awaiting_outcome=11,
                webhook_health={
                    "last_received_iso": "2026-03-13T11:40:00+00:00",
                    "last_received_age": "50m ago",
                },
                profile_dicts=profile_dicts,
            )

        titles = {alert["title"] for alert in alerts}
        self.assertEqual(
            {
                "Recent delivery failures",
                "Awaiting outcome backlog",
                "Profile backlog concentration",
                "Webhook attribution gap",
                "Webhook intake stale",
                "Sender API errors",
            },
            titles,
        )

    def test_build_threshold_alerts_ignores_finished_run_errors_for_sender_api_alert(self) -> None:
        alerts = dashboard_core.build_threshold_alerts(
            session_label="stopped",
            active_profiles=0,
            recent_failures=0,
            recent_unmapped=0,
            total_awaiting_outcome=0,
            webhook_health={},
            profile_dicts=[
                {"name": "private_jc", "run_errors": 2, "runtime_state": "finished"},
                {"name": "sendgrid_alpha", "run_errors": 1, "runtime_state": "stopped"},
            ],
        )

        titles = {alert["title"] for alert in alerts}
        self.assertNotIn("Sender API errors", titles)

    def test_evaluate_profile_delivery_guards_flags_hard_bounce_cluster(self) -> None:
        profiles = {
            "sendgrid_alpha": {
                "provider": "sendgrid",
                "csv": "recipients_alpha.csv",
                "log": "sendgrid_alpha_log.csv",
                "from_email": "alpha@example.com",
                "always_send": "probe@example.com",
                "max_total": 100,
            }
        }
        snapshot = dashboard_core.ProfileSnapshot(
            name="sendgrid_alpha",
            pane_index=0,
            csv_path="recipients_alpha.csv",
            log_path="sendgrid_alpha_log.csv",
            max_total=100,
            cooldown_seconds=120,
            cooldown_remaining_seconds=120,
            pending_count=90,
            run_started_at="2026-03-13 05:00:00 PDT",
            run_sent=5,
            run_errors=0,
            run_skipped=0,
            sent_today=5,
            errors_today=0,
            skipped_today=0,
            last_status="SENT",
            last_email="reader5@example.com",
            last_info="sg_message_id=msg-5",
            last_timestamp="2026-03-13 05:10:00 PDT",
            last_age="1m ago",
            tmux_running=True,
            tmux_dead=False,
            tmux_command="python",
            tmux_tail="BATCH: sent=1 total=5 remaining_estimate=95 next_sleep_seconds=120",
            runtime_state="cooldown",
            runtime_label="Cooldown",
            runtime_note="Cooling down between sends: 120s remaining.",
        )
        attempts = [
            dashboard_core.SendAttempt("sendgrid_alpha", "probe@example.com", dashboard_core.datetime(2026, 3, 13, 12, 0, 0, tzinfo=dashboard_core.timezone.utc), "probe-1"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader1@example.com", dashboard_core.datetime(2026, 3, 13, 12, 1, 0, tzinfo=dashboard_core.timezone.utc), "msg-1"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader2@example.com", dashboard_core.datetime(2026, 3, 13, 12, 2, 0, tzinfo=dashboard_core.timezone.utc), "msg-2"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader3@example.com", dashboard_core.datetime(2026, 3, 13, 12, 3, 0, tzinfo=dashboard_core.timezone.utc), "msg-3"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader4@example.com", dashboard_core.datetime(2026, 3, 13, 12, 4, 0, tzinfo=dashboard_core.timezone.utc), "msg-4"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader5@example.com", dashboard_core.datetime(2026, 3, 13, 12, 5, 0, tzinfo=dashboard_core.timezone.utc), "msg-5"),
        ]
        events = [
            {"processed_at_utc": "2026-03-13T12:01:30+00:00", "status": "bounce", "profile": "sendgrid_alpha", "email": "reader1@example.com", "message_id": "msg-1"},
            {"processed_at_utc": "2026-03-13T12:02:30+00:00", "status": "delivered", "profile": "sendgrid_alpha", "email": "reader2@example.com", "message_id": "msg-2"},
            {"processed_at_utc": "2026-03-13T12:03:30+00:00", "status": "bounce", "profile": "sendgrid_alpha", "email": "reader3@example.com", "message_id": "msg-3"},
            {"processed_at_utc": "2026-03-13T12:04:30+00:00", "status": "bounce", "profile": "sendgrid_alpha", "email": "reader4@example.com", "message_id": "msg-4"},
        ]

        with patch.multiple(
            dashboard_core,
            PROFILES=profiles,
            SENDGRID_PROFILES=list(profiles.keys()),
            DASHBOARD_PROFILES=list(profiles.keys()),
            START_ALL_PROFILES=list(profiles.keys()),
        ):
            decisions = dashboard_core.evaluate_profile_delivery_guards([snapshot], attempts, events)

        self.assertEqual(1, len(decisions))
        self.assertEqual("sendgrid_alpha", decisions[0]["profile"])
        self.assertEqual("Hard bounce guard", decisions[0]["title"])

    def test_apply_profile_delivery_guards_stops_once_per_fingerprint(self) -> None:
        profiles = {
            "sendgrid_alpha": {
                "provider": "sendgrid",
                "csv": "recipients_alpha.csv",
                "log": "sendgrid_alpha_log.csv",
                "from_email": "alpha@example.com",
                "always_send": "probe@example.com",
                "max_total": 100,
            }
        }
        snapshot = dashboard_core.ProfileSnapshot(
            name="sendgrid_alpha",
            pane_index=0,
            csv_path="recipients_alpha.csv",
            log_path="sendgrid_alpha_log.csv",
            max_total=100,
            cooldown_seconds=120,
            cooldown_remaining_seconds=120,
            pending_count=90,
            run_started_at="2026-03-13 05:00:00 PDT",
            run_sent=5,
            run_errors=0,
            run_skipped=0,
            sent_today=5,
            errors_today=0,
            skipped_today=0,
            last_status="SENT",
            last_email="reader5@example.com",
            last_info="sg_message_id=msg-5",
            last_timestamp="2026-03-13 05:10:00 PDT",
            last_age="1m ago",
            tmux_running=True,
            tmux_dead=False,
            tmux_command="python",
            tmux_tail="BATCH: sent=1 total=5 remaining_estimate=95 next_sleep_seconds=120",
            runtime_state="cooldown",
            runtime_label="Cooldown",
            runtime_note="Cooling down between sends: 120s remaining.",
        )
        attempts = [
            dashboard_core.SendAttempt("sendgrid_alpha", "probe@example.com", dashboard_core.datetime(2026, 3, 13, 12, 0, 0, tzinfo=dashboard_core.timezone.utc), "probe-1"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader1@example.com", dashboard_core.datetime(2026, 3, 13, 12, 1, 0, tzinfo=dashboard_core.timezone.utc), "msg-1"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader2@example.com", dashboard_core.datetime(2026, 3, 13, 12, 2, 0, tzinfo=dashboard_core.timezone.utc), "msg-2"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader3@example.com", dashboard_core.datetime(2026, 3, 13, 12, 3, 0, tzinfo=dashboard_core.timezone.utc), "msg-3"),
            dashboard_core.SendAttempt("sendgrid_alpha", "reader4@example.com", dashboard_core.datetime(2026, 3, 13, 12, 4, 0, tzinfo=dashboard_core.timezone.utc), "msg-4"),
        ]
        events = [
            {"processed_at_utc": "2026-03-13T12:01:30+00:00", "status": "bounce", "profile": "sendgrid_alpha", "email": "reader1@example.com", "message_id": "msg-1"},
            {"processed_at_utc": "2026-03-13T12:02:30+00:00", "status": "bounce", "profile": "sendgrid_alpha", "email": "reader2@example.com", "message_id": "msg-2"},
            {"processed_at_utc": "2026-03-13T12:03:30+00:00", "status": "bounce", "profile": "sendgrid_alpha", "email": "reader3@example.com", "message_id": "msg-3"},
        ]

        with dashboard_core.AUTO_STOP_EVENT_LOCK:
            dashboard_core.AUTO_STOP_EVENTS.clear()

        try:
            with patch.multiple(
                dashboard_core,
                PROFILES=profiles,
                SENDGRID_PROFILES=list(profiles.keys()),
                DASHBOARD_PROFILES=list(profiles.keys()),
                START_ALL_PROFILES=list(profiles.keys()),
            ), patch.object(
                dashboard_core,
                "stop_sendgrid_profile",
                return_value=(True, "Stop signal sent to sendgrid_alpha (pane 0)."),
            ) as stop_profile:
                first = dashboard_core.apply_profile_delivery_guards([snapshot], attempts, events)
                second = dashboard_core.apply_profile_delivery_guards([snapshot], attempts, events)

            self.assertEqual(1, stop_profile.call_count)
            self.assertEqual(1, len(first))
            self.assertEqual(1, len(second))
            self.assertTrue(first[0]["ok"])
            self.assertEqual(first[0]["fingerprint"], second[0]["fingerprint"])
        finally:
            with dashboard_core.AUTO_STOP_EVENT_LOCK:
                dashboard_core.AUTO_STOP_EVENTS.clear()

    def test_build_snapshot_webhook_health_and_awaiting_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "max_total": 100,
                }
            }
            self._write_recipients(base / "recipients_alpha.csv", "reader@example.com")
            self._write_log(
                base / "sendgrid_alpha_log.csv",
                [
                    ("2026-03-13T12:00:00+00:00", "probe@example.com", "SENT", ""),
                    ("2026-03-13T12:02:00+00:00", "reader@example.com", "SENT", "sg_message_id=abc123"),
                    ("2026-03-13T12:03:00+00:00", "second@example.com", "SENT", "sg_message_id=def456"),
                ],
            )
            self._write_events(
                base / dashboard_core.WEBHOOK_EVENTS_JSONL,
                [
                    {
                        "processed_at_raw": "1773403200",
                        "processed_at_utc": "2026-03-13T02:02:30+00:00",
                        "received_at_utc": "2026-03-13T12:04:30+00:00",
                        "message_id": "abc123.recvd-1",
                        "email": "reader@example.com",
                        "domain": "example.com",
                        "subject": "",
                        "status": "delivered",
                        "code": "250",
                        "response": "250 OK",
                        "source_log": dashboard_core.WEBHOOK_EVENTS_JSONL,
                        "profile": "sendgrid_alpha",
                    },
                    {
                        "processed_at_raw": "1773403380",
                        "processed_at_utc": "2026-03-13T09:03:00+00:00",
                        "received_at_utc": "2026-03-13T11:00:00+00:00",
                        "message_id": "",
                        "email": "mystery@example.com",
                        "domain": "example.com",
                        "subject": "",
                        "status": "processed",
                        "code": "",
                        "response": "<mystery@example.com>",
                        "source_log": dashboard_core.WEBHOOK_EVENTS_JSONL,
                    },
                    {
                        "processed_at_raw": "1773403440",
                        "processed_at_utc": "2026-03-13T12:03:30+00:00",
                        "received_at_utc": "2026-03-13T12:03:45+00:00",
                        "message_id": "ghi789.recvd-1",
                        "email": "bounce1@example.com",
                        "domain": "example.com",
                        "subject": "",
                        "status": "bounce",
                        "code": "550",
                        "response": "550 5.1.1 user unknown",
                        "source_log": dashboard_core.WEBHOOK_EVENTS_JSONL,
                        "bounce_classification": "Invalid Address",
                    },
                    {
                        "processed_at_raw": "1773403470",
                        "processed_at_utc": "2026-03-13T12:04:10+00:00",
                        "received_at_utc": "2026-03-13T12:04:20+00:00",
                        "message_id": "jkl012.recvd-1",
                        "email": "bounce2@example.com",
                        "domain": "example.com",
                        "subject": "",
                        "status": "bounce",
                        "code": "550",
                        "response": "550 5.1.1 user unknown",
                        "source_log": dashboard_core.WEBHOOK_EVENTS_JSONL,
                        "bounce_classification": "",
                    },
                ],
            )
            received_at = dashboard_core.datetime(2026, 3, 13, 12, 4, 30, tzinfo=dashboard_core.timezone.utc)
            duplicate_batch = sendgrid_hygiene.normalize_webhook_events(
                [
                    {
                        "email": "reader@example.com",
                        "event": "delivered",
                        "timestamp": 1773403200,
                        "sg_event_id": "evt-dup-1",
                        "sg_message_id": "abc123.recvd-1",
                    },
                    {
                        "email": "reader@example.com",
                        "event": "delivered",
                        "timestamp": 1773403200,
                        "sg_event_id": "evt-dup-1",
                        "sg_message_id": "abc123.recvd-1",
                    },
                ],
                received_at_utc=received_at,
            )
            sendgrid_hygiene.dedupe_webhook_events(
                duplicate_batch,
                base / sendgrid_hygiene.WEBHOOK_DEDUPE_DB,
                reference_utc=received_at,
            )

            fake_now = dashboard_core.datetime(2026, 3, 13, 12, 5, 0, tzinfo=dashboard_core.timezone.utc)
            with self._patched_dashboard_context(base, profiles), patch.object(dashboard_core, "dashboard_now", return_value=fake_now.astimezone(dashboard_core.DASHBOARD_TIMEZONE)):
                class FrozenDateTime(dashboard_core.datetime):
                    @classmethod
                    def now(cls, tz=None):
                        if tz is None:
                            return fake_now.replace(tzinfo=None)
                        return fake_now.astimezone(tz)

                with patch.object(dashboard_core, "datetime", FrozenDateTime):
                    snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        self.assertEqual(1, snapshot["summary"]["total_awaiting_outcome"])
        self.assertEqual(1, snapshot["profiles"][0]["awaiting_outcome"])
        self.assertEqual(2, snapshot["profiles"][0]["accepted_recent"])
        self.assertEqual(1, snapshot["profiles"][0]["final_outcome"])
        self.assertEqual("30s ago", snapshot["webhook_health"]["last_received_age"])
        self.assertEqual(3, snapshot["webhook_health"]["events_5m"])
        self.assertEqual(3, snapshot["webhook_health"]["events_1h"])
        self.assertEqual(1, snapshot["webhook_health"]["duplicate_hits_selected_window"])
        self.assertEqual(3, snapshot["webhook_health"]["unmapped_selected_window"])
        self.assertEqual(1, snapshot["webhook_health"]["bounces_with_bounce_classification"])
        self.assertEqual(1, snapshot["webhook_health"]["bounces_missing_bounce_classification"])

    def _patched_dashboard_context(self, base: Path, profiles: dict[str, dict[str, object]]):
        return patch.multiple(
            dashboard_core,
            ROOT=base,
            SHARDS_DIR=base,
            LOGS_DIR=base,
            STATE_DIR=base,
            ACTIVITY_LOG_PATH=base / "sendgridlogs",
            SUPPRESSION_CSV=base / "sendgrid_suppressions.csv",
            NORMALIZE_REPORT_PATH=base / "sendgrid_shard_normalize_report.json",
            WEBHOOK_EVENTS_PATH=base / dashboard_core.WEBHOOK_EVENTS_JSONL,
            WEBHOOK_DEDUPE_PATH=base / dashboard_core.WEBHOOK_DEDUPE_DB,
            LOG_RESET_BACKUP_ROOT=base / "backups",
            DASHBOARD_RUN_SETTINGS_PATH=base / "dashboard_run_settings.json",
            PROFILES=profiles,
            SENDGRID_PROFILES=list(profiles.keys()),
            DASHBOARD_PROFILES=list(profiles.keys()),
            START_ALL_PROFILES=list(profiles.keys()),
            tmux_pane_map=lambda session="sendgrid": {},
            tmux_capture_tail=lambda pane_index, session="sendgrid", lines=16: "",
        )

    def _write_recipients(self, path: Path, email: str) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Email"])
            writer.writeheader()
            writer.writerow({"Email": email})

    def _write_log(self, path: Path, rows: list[tuple[str, str, str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
            writer.writeheader()
            for timestamp, email, status, info in rows:
                writer.writerow(
                    {
                        "TimestampUTC": timestamp,
                        "Email": email,
                        "Status": status,
                        "Info": info,
                    }
                )

    def _write_events(self, path: Path, events: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    unittest.main()
