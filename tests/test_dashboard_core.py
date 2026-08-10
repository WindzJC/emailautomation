from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dashboard_core
import provider_pacing
import settings
import sendgrid_hygiene
from tools import rebuild_recipient_queues
from sendgrid_launch_auth import SendGridKeyResolution


class DashboardCoreTests(unittest.TestCase):
    def test_cloud_service_flag_disables_repository_dotenv_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "ASTRA_SYNTHETIC_DOTENV_VALUE=must-not-load\n",
                encoding="utf-8",
            )
            with (
                patch.object(settings, "ENV_FILES", [env_file]),
                patch.dict(
                    os.environ,
                    {"ASTRA_DISABLE_DOTENV": "1"},
                    clear=True,
                ),
            ):
                settings._load_env_files()
                self.assertNotIn(
                    "ASTRA_SYNTHETIC_DOTENV_VALUE",
                    os.environ,
                )

    def test_campaign_run_history_appends_and_loads_recent_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "campaign_run_history.jsonl"
            first = {"event_type": "start_all_requested", "timestamp": "2026-01-01T00:00:00+00:00"}
            second = {"event_type": "start_all_started", "timestamp": "2026-01-01T00:01:00+00:00"}

            dashboard_core.append_campaign_run_history(first, path=history_path)
            dashboard_core.append_campaign_run_history(second, path=history_path)
            records = dashboard_core.load_campaign_run_history(limit=1, path=history_path)

        self.assertEqual([second], records)

    def test_campaign_history_record_includes_readiness_and_queue_safety_fields(self) -> None:
        snapshot = {
            "queue_safety": {"safe": False, "unsafe_reasons": ["mixed_queue"]},
            "profiles": [
                {
                    "name": "sendgrid_annette",
                    "message_readiness": {
                        "status": "PASS",
                        "recipient_file": "recipients_sendgrid_1.csv",
                        "recipient_row_count": 2,
                        "book_title_column_present": True,
                        "rows_with_book_title": 1,
                        "fallback_row_count": 1,
                        "preview_csv_name": "sendgrid_annette_message_preview.csv",
                        "preview_row_count": 2,
                        "preview_validation_status": "PASS",
                    },
                    "run_sent": 3,
                    "run_errors": 1,
                }
            ],
        }

        record = dashboard_core.campaign_history_record(
            "preview_validate_completed",
            profile="sendgrid_annette",
            snapshot=snapshot,
        )

        self.assertEqual("preview_validate_completed", record["event_type"])
        self.assertEqual("sendgrid_annette", record["profile"])
        self.assertEqual("consignment", record["pitch_mode"])
        self.assertEqual("recipients_sendgrid_1.csv", record["recipient_file"])
        self.assertEqual(2, record["recipient_row_count"])
        self.assertEqual(True, record["BookTitle_column_present"])
        self.assertEqual(1, record["BookTitle_populated_count"])
        self.assertEqual(1, record["fallback_blank_BookTitle_count"])
        self.assertEqual("unsafe", record["queue_safety_status"])
        self.assertEqual(["mixed_queue"], record["blocked_reasons"])

    def test_profile_message_readiness_passes_for_valid_current_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "shards"
            previews = base / "previews"
            shards.mkdir()
            previews.mkdir()
            queue = shards / "recipients_sendgrid_1.csv"
            with queue.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName", "BookTitle"])
                writer.writeheader()
                writer.writerow({"Email": "reader1@example.com", "FirstName": "Ava", "BookTitle": "Launch One"})
                writer.writerow({"Email": "reader2@example.com", "FirstName": "Ben", "BookTitle": ""})
            preview = previews / "sendgrid_annette_message_preview.csv"
            preview.write_text(
                "Email,FirstName,BookTitle,Subject,Body\n"
                "reader1@example.com,Ava,Launch One,Subject,Body\n"
                "reader2@example.com,Ben,,Subject,Body\n",
                encoding="utf-8",
            )
            (previews / "sendgrid_annette_message_preview_validated.csv").write_text(
                "Email\nreader1@example.com\nreader2@example.com\n",
                encoding="utf-8",
            )
            (previews / "sendgrid_annette_message_preview_failed.csv").write_text("Email\n", encoding="utf-8")
            (previews / "sendgrid_annette_message_preview_summary.txt").write_text("failed rows: 0\n", encoding="utf-8")

            profiles = {
                "sendgrid_annette": {
                    "provider": "sendgrid",
                    "csv": str(queue),
                    "log": str(base / "sendgrid_annette_log.csv"),
                    "pitch": "pitch1",
                }
            }
            with patch.multiple(dashboard_core, SHARDS_DIR=shards, MESSAGE_PREVIEW_DIR=previews, PROFILES=profiles):
                readiness = dashboard_core.build_profile_message_readiness("sendgrid_annette")

        self.assertEqual("PASS", readiness["status"])
        self.assertEqual(2, readiness["recipient_row_count"])
        self.assertEqual(True, readiness["book_title_column_present"])
        self.assertEqual(1, readiness["rows_with_book_title"])
        self.assertEqual(1, readiness["fallback_row_count"])
        self.assertEqual("consignment", readiness["pitch_mode_expected"])
        self.assertEqual("consignment", readiness["actual_profile_mode"])

    def test_controlled_sendgrid_readiness_requires_matching_recipient_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "shards"
            previews = base / "previews"
            shards.mkdir()
            previews.mkdir()
            queue = shards / "recipients_sendgrid_controlled_test.csv"
            queue.write_text(
                "Email,FirstName,BookTitle\n"
                "astraproductionsbyjc@gmail.com,Astra,Controlled Test\n",
                encoding="utf-8",
            )
            preview = previews / "sendgrid_controlled_test_message_preview.csv"
            preview.write_text(
                "Email,FirstName,BookTitle,Subject,Body\n"
                "other@example.test,Astra,Controlled Test,Subject,Body\n",
                encoding="utf-8",
            )
            (previews / "sendgrid_controlled_test_message_preview_validated.csv").write_text(
                "Email\nother@example.test\n",
                encoding="utf-8",
            )
            (previews / "sendgrid_controlled_test_message_preview_failed.csv").write_text(
                "Email\n",
                encoding="utf-8",
            )
            (previews / "sendgrid_controlled_test_message_preview_summary.txt").write_text(
                "failed rows: 0\n",
                encoding="utf-8",
            )
            profiles = {
                "sendgrid_controlled_test": {
                    "provider": "sendgrid",
                    "csv": str(queue),
                    "log": str(base / "sendgrid_controlled_test_log.csv"),
                    "pitch": "pitch1",
                    "controlled_test": True,
                    "recipient_allowlist": "astraproductionsbyjc@gmail.com",
                    "require_preview_recipient_fingerprint": True,
                }
            }
            with patch.multiple(
                dashboard_core,
                SHARDS_DIR=shards,
                MESSAGE_PREVIEW_DIR=previews,
                PROFILES=profiles,
            ):
                stale = dashboard_core.build_profile_message_readiness(
                    "sendgrid_controlled_test"
                )
                safety = dashboard_core.build_controlled_sendgrid_queue_safety_report()

                preview.write_text(
                    "Email,FirstName,BookTitle,Subject,Body\n"
                    "astraproductionsbyjc@gmail.com,Astra,Controlled Test,Subject,Body\n",
                    encoding="utf-8",
                )
                (previews / "sendgrid_controlled_test_message_preview_validated.csv").write_text(
                    "Email\nastraproductionsbyjc@gmail.com\n",
                    encoding="utf-8",
                )
                (previews / "sendgrid_controlled_test_message_preview_summary.txt").write_text(
                    "failed rows: 0\n",
                    encoding="utf-8",
                )
                current = dashboard_core.build_profile_message_readiness(
                    "sendgrid_controlled_test"
                )

        self.assertTrue(safety["safe"])
        self.assertEqual("STALE", stale["status"])
        self.assertFalse(stale["preview_recipient_fingerprint_matches"])
        self.assertIn("fingerprint", " ".join(stale["reasons"]))
        self.assertEqual("PASS", current["status"])
        self.assertTrue(current["preview_recipient_fingerprint_matches"])

    def test_profile_message_readiness_marks_partial_preview_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "shards"
            previews = base / "previews"
            shards.mkdir()
            previews.mkdir()
            queue = shards / "recipients_private_jc.csv"
            with queue.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName", "BookTitle"])
                writer.writeheader()
                writer.writerow({"Email": "reader1@example.com", "FirstName": "Ava", "BookTitle": "Launch One"})
                writer.writerow({"Email": "reader2@example.com", "FirstName": "Ben", "BookTitle": "Launch Two"})
            preview = previews / "private_jc_message_preview.csv"
            preview.write_text(
                "Email,FirstName,BookTitle,Subject,Body\nreader1@example.com,Ava,Launch One,Subject,Body\n",
                encoding="utf-8",
            )
            (previews / "private_jc_message_preview_validated.csv").write_text(
                "Email\nreader1@example.com\n",
                encoding="utf-8",
            )
            (previews / "private_jc_message_preview_failed.csv").write_text("Email\n", encoding="utf-8")
            (previews / "private_jc_message_preview_summary.txt").write_text("failed rows: 0\n", encoding="utf-8")
            profiles = {
                "private_jc": {
                    "provider": "private",
                    "dashboard_enabled": True,
                    "csv": str(queue),
                    "log": str(base / "private_jc_log.csv"),
                    "pitch": "pitch_jc",
                }
            }

            with patch.multiple(dashboard_core, SHARDS_DIR=shards, MESSAGE_PREVIEW_DIR=previews, PROFILES=profiles):
                readiness = dashboard_core.build_profile_message_readiness("private_jc")

        self.assertEqual("STALE", readiness["status"])
        self.assertEqual(2, readiness["recipient_row_count"])
        self.assertEqual(1, readiness["preview_row_count"])
        self.assertIn("does not match recipient queue row count", " ".join(readiness["reasons"]))

    def test_profile_message_readiness_flags_missing_booktitle_not_run_and_stale_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "shards"
            previews = base / "previews"
            shards.mkdir()
            previews.mkdir()
            queue = shards / "recipients_private_jc.csv"
            with queue.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName"])
                writer.writeheader()
                writer.writerow({"Email": "reader@example.com", "FirstName": "Ava"})

            profiles = {
                "private_jc": {
                    "provider": "private",
                    "dashboard_enabled": True,
                    "csv": str(queue),
                    "log": str(base / "private_jc_log.csv"),
                    "pitch": "pitch_jc",
                }
            }
            with patch.multiple(dashboard_core, SHARDS_DIR=shards, MESSAGE_PREVIEW_DIR=previews, PROFILES=profiles):
                missing = dashboard_core.build_profile_message_readiness("private_jc")

            self.assertEqual("FAIL", missing["status"])
            self.assertEqual(False, missing["book_title_column_present"])
            self.assertEqual("NOT RUN", missing["preview_validation_status"])

            with queue.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName", "BookTitle"])
                writer.writeheader()
                writer.writerow({"Email": "reader@example.com", "FirstName": "Ava", "BookTitle": "Launch One"})
            preview = previews / "private_jc_message_preview.csv"
            preview.write_text("Email,FirstName,BookTitle,Subject,Body\nreader@example.com,Ava,Launch One,Subject,Body\n", encoding="utf-8")
            validated = previews / "private_jc_message_preview_validated.csv"
            failed = previews / "private_jc_message_preview_failed.csv"
            summary = previews / "private_jc_message_preview_summary.txt"
            validated.write_text("Email\nreader@example.com\n", encoding="utf-8")
            failed.write_text("Email\n", encoding="utf-8")
            summary.write_text("failed rows: 0\n", encoding="utf-8")
            old = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
            new = datetime(2026, 1, 2, tzinfo=timezone.utc).timestamp()
            os.utime(preview, (old, old))
            os.utime(validated, (old, old))
            os.utime(failed, (old, old))
            os.utime(summary, (old, old))
            os.utime(queue, (new, new))

            with patch.multiple(dashboard_core, SHARDS_DIR=shards, MESSAGE_PREVIEW_DIR=previews, PROFILES=profiles):
                stale = dashboard_core.build_profile_message_readiness("private_jc")

        self.assertEqual("STALE", stale["status"])
        self.assertEqual("PASS", stale["preview_validation_status"])
        self.assertIn("older than the recipient queue", " ".join(stale["reasons"]))

    def test_queue_safety_alert_blocks_mixed_recipient_queue(self) -> None:
        alert = dashboard_core.queue_safety_alert(
            {
                "safe": False,
                "overlap_with_triaged_reject": 5,
                "outside_checked_output_count": 3,
                "outside_intended_source_count": 7,
            }
        )

        self.assertIsNotNone(alert)
        self.assertEqual("critical", alert["severity"])
        self.assertEqual("Recipient queue unsafe", alert["title"])
        self.assertIn("Freeze sending", alert["message"])
        self.assertIn("5 email(s) overlap triaged_reject", alert["message"])
        self.assertTrue(alert["blocks_sending"])
        self.assertEqual("dashboard_core.queue_safety_alert", alert["source_function"])

    def test_queue_safety_alert_ignores_zero_count_overlap_reasons(self) -> None:
        alert = dashboard_core.queue_safety_alert(
            {
                "safe": False,
                "affected_provider": "sendgrid",
                "unsafe_reasons": ["TRIAGED_REJECT_OVERLAP", "OUTSIDE_INTENDED_SOURCE"],
                "overlap_with_triaged_reject": 0,
                "outside_checked_output_count": 0,
                "outside_intended_source_count": 0,
                "intended_source_reject_overlap_count": 0,
            }
        )

        self.assertIsNone(alert)

    def test_queue_safety_alert_keeps_real_safety_errors(self) -> None:
        alert = dashboard_core.queue_safety_alert(
            {
                "safe": False,
                "affected_provider": "sendgrid",
                "unsafe_reasons": ["QUEUE_SAFETY_CHECK_FAILED"],
                "message": "Queue safety check failed: fixture error",
                "overlap_with_triaged_reject": 0,
                "outside_checked_output_count": 0,
                "outside_intended_source_count": 0,
            }
        )

        self.assertIsNotNone(alert)
        self.assertEqual("Sendgrid queue unsafe", alert["title"])
        self.assertIn("fixture error", alert["message"])

    def test_provider_queue_safety_uses_only_provider_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            shards = Path(tmpdir)
            for name in [
                "recipients_private_jc.csv",
                "recipients_sendgrid_1.csv",
                "recipients_sendgrid_2.csv",
                "recipients_sendgrid_3.csv",
                "recipients_sendgrid_4.csv",
                "recipients_sendgrid_5.csv",
            ]:
                (shards / name).write_text("Email,FirstName,AuthorEmail,AuthorName,BookTitle\n", encoding="utf-8")

            captured: dict[str, list[str]] = {}

            def fake_report(*, shard_paths=None, **kwargs):
                names = [path.name for path in (shard_paths or [])]
                captured["last"] = names
                return {"safe": True, "unsafe_reasons": [], "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])]}

            with patch.multiple(dashboard_core, SHARDS_DIR=shards), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                sendgrid = dashboard_core.build_dashboard_queue_safety_report("sendgrid")
                private = dashboard_core.build_dashboard_queue_safety_report("private_jc")

        self.assertEqual("sendgrid", sendgrid["affected_provider"])
        self.assertEqual(
            [f"recipients_sendgrid_{index}.csv" for index in range(1, 6)],
            [Path(path).name for path in sendgrid["validated_shard_paths"]],
        )
        self.assertNotIn("recipients_private_jc.csv", [Path(path).name for path in sendgrid["validated_shard_paths"]])
        self.assertEqual("private_jc", private["affected_provider"])
        self.assertEqual(["recipients_private_jc.csv"], [Path(path).name for path in private["validated_shard_paths"]])

    def test_sendgrid_queue_safety_matches_sendgrid_preview_rows_without_private_jc(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            state = base / "data" / "state"
            preview_dir = base / "_important" / "dispatch_jobs" / "previews"
            shards.mkdir(parents=True)
            state.mkdir(parents=True)
            preview_dir.mkdir(parents=True)
            preview_id = "dispatch_preview_20260625_000210_synthetic"

            private_rows = [
                {"Email": f"private-{index}@example.test", "FirstName": "Private", "AuthorEmail": f"private-{index}@example.test", "AuthorName": "Private Writer", "BookTitle": "Private Book"}
                for index in range(621)
            ]
            sendgrid_rows = [
                {"Email": f"sendgrid-{index}@example.test", "FirstName": "Send", "AuthorEmail": f"sendgrid-{index}@example.test", "AuthorName": "Send Writer", "BookTitle": "Send Book"}
                for index in range(621)
            ]
            rows_by_queue = {"private_jc": private_rows}
            cursor = 0
            for shard_index, count in enumerate([125, 124, 124, 124, 124], start=1):
                rows = sendgrid_rows[cursor : cursor + count]
                cursor += count
                rows_by_queue[f"sendgrid_{shard_index}"] = rows
                self._write_recipient_rows(shards / f"recipients_sendgrid_{shard_index}.csv", rows)
            self._write_recipient_rows(shards / "recipients_private_jc.csv", private_rows)
            (state / "active_campaign_snapshot.json").write_text(json.dumps({"preview_id": preview_id}), encoding="utf-8")
            (preview_dir / f"{preview_id}.json").write_text(
                json.dumps({"preview_id": preview_id, "plan_rows_by_queue": rows_by_queue}),
                encoding="utf-8",
            )

            def fake_report(*, shard_paths=None, **kwargs):
                return {
                    "safe": True,
                    "unsafe_reasons": [],
                    "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])],
                    "shard_row_count_total": sum(1 for _ in (shard_paths or [])),
                }

            with patch.multiple(dashboard_core, ROOT=base, SHARDS_DIR=shards, STATE_DIR=state), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                sendgrid = dashboard_core.build_dashboard_queue_safety_report("sendgrid")
                private = dashboard_core.build_dashboard_queue_safety_report("private_jc")
                combined = dashboard_core.build_dashboard_queue_safety_report("all")

        self.assertTrue(sendgrid["safe"])
        self.assertEqual(621, sendgrid["expected_preview_unique_emails"])
        self.assertEqual(621, sendgrid["live_preview_unique_emails"])
        self.assertEqual(0, sendgrid["missing_from_preview_expected_count"])
        self.assertEqual(0, sendgrid["extra_vs_preview_expected_count"])
        self.assertNotIn("private-0@example.test", sendgrid["missing_from_preview_expected_fingerprint"])
        self.assertIsNone(dashboard_core.queue_safety_alert(sendgrid))
        self.assertTrue(private["safe"])
        self.assertEqual(621, private["expected_preview_unique_emails"])
        self.assertTrue(combined["safe"])
        self.assertEqual(1242, combined["expected_preview_unique_emails"])
        self.assertEqual(1242, combined["live_preview_unique_emails"])

    def test_sendgrid_queue_safety_blocks_preview_missing_or_extra_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            state = base / "data" / "state"
            preview_dir = base / "_important" / "dispatch_jobs" / "previews"
            shards.mkdir(parents=True)
            state.mkdir(parents=True)
            preview_dir.mkdir(parents=True)
            preview_id = "dispatch_preview_20260625_000210_mismatch"
            planned_rows = [
                {"Email": "planned-a@example.test", "FirstName": "A"},
                {"Email": "planned-b@example.test", "FirstName": "B"},
            ]
            live_rows = [
                {"Email": "planned-a@example.test", "FirstName": "A"},
                {"Email": "extra@example.test", "FirstName": "Extra"},
            ]
            self._write_recipient_rows(shards / "recipients_sendgrid_1.csv", live_rows)
            for index in range(2, 6):
                self._write_recipient_rows(shards / f"recipients_sendgrid_{index}.csv", [])
            self._write_recipient_rows(shards / "recipients_private_jc.csv", [])
            (state / "active_campaign_snapshot.json").write_text(json.dumps({"preview_id": preview_id}), encoding="utf-8")
            (preview_dir / f"{preview_id}.json").write_text(
                json.dumps({"preview_id": preview_id, "plan_rows_by_queue": {"private_jc": [], "sendgrid_1": planned_rows}}),
                encoding="utf-8",
            )

            def fake_report(*, shard_paths=None, **kwargs):
                return {
                    "safe": True,
                    "unsafe_reasons": [],
                    "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])],
                }

            with patch.multiple(dashboard_core, ROOT=base, SHARDS_DIR=shards, STATE_DIR=state), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                report = dashboard_core.build_dashboard_queue_safety_report("sendgrid")

        self.assertFalse(report["safe"])
        self.assertEqual(1, report["missing_from_preview_expected_count"])
        self.assertEqual(1, report["extra_vs_preview_expected_count"])
        self.assertIn("MISSING_PREVIEW_PLANNED_ROWS", report["unsafe_reasons"])
        self.assertIn("EXTRA_ROWS_NOT_IN_PREVIEW", report["unsafe_reasons"])
        alert = dashboard_core.queue_safety_alert(report)
        self.assertIsNotNone(alert)
        self.assertEqual("Sendgrid queue unsafe", alert["title"])

    def test_private_queue_safety_allows_accounted_partial_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            state = base / "data" / "state"
            logs = base / "data" / "logs"
            preview_dir = base / "_important" / "dispatch_jobs" / "previews"
            shards.mkdir(parents=True)
            state.mkdir(parents=True)
            logs.mkdir(parents=True)
            preview_dir.mkdir(parents=True)
            preview_id = "dispatch_preview_partial_private"
            planned_rows = [
                {"Email": "remaining@example.test", "FirstName": "R"},
                {"Email": "sent@example.test", "FirstName": "S"},
                {"Email": "skipped@example.test", "FirstName": "K"},
            ]
            self._write_recipient_rows(shards / "recipients_private_jc.csv", [planned_rows[0]])
            (logs / "private_jc_log.csv").write_text(
                "TimestampUTC,Email,Status,Info\n"
                "2026-06-25T00:00:00+00:00,sent@example.test,SENT,\n"
                "2026-06-25T00:00:01+00:00,skipped@example.test,SKIP,event_type=SKIPPED_ALREADY_SENT\n",
                encoding="utf-8",
            )
            (state / "active_campaign_snapshot.json").write_text(json.dumps({"preview_id": preview_id}), encoding="utf-8")
            (preview_dir / f"{preview_id}.json").write_text(
                json.dumps({"preview_id": preview_id, "plan_rows_by_queue": {"private_jc": planned_rows}}),
                encoding="utf-8",
            )

            def fake_report(*, shard_paths=None, **kwargs):
                return {
                    "safe": True,
                    "unsafe_reasons": [],
                    "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])],
                }

            profiles = {
                "private_jc": {
                    "provider": "private",
                    "csv": "recipients_private_jc.csv",
                    "log": "private_jc_log.csv",
                    "dashboard_enabled": True,
                }
            }
            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SHARDS_DIR=shards,
                STATE_DIR=state,
                PROFILES=profiles,
                DASHBOARD_PROFILES=["private_jc"],
                SENDGRID_PROFILES=[],
            ), patch.object(settings, "LOGS_DIR", logs), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                report = dashboard_core.build_dashboard_queue_safety_report("private_jc")

        self.assertTrue(report["safe"])
        self.assertTrue(report["partial_consumption_verified"])
        self.assertEqual(3, report["expected_preview_unique_emails"])
        self.assertEqual(1, report["live_preview_unique_emails"])
        self.assertEqual(2, report["missing_from_preview_expected_count"])
        self.assertEqual(2, report["accounted_missing_from_preview_expected_count"])
        self.assertEqual(0, report["unaccounted_missing_from_preview_expected_count"])
        self.assertEqual(0, report["extra_vs_preview_expected_count"])
        self.assertEqual(0, report["live_already_sent_overlap_count"])
        self.assertEqual("Queue partially consumed — remaining recipients verified safe.", report["message"])
        self.assertIsNone(dashboard_core.queue_safety_alert(report))

    def test_private_provider_history_uses_cold_and_warm_logs_not_shared_domain_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logs = Path(tmpdir)
            profiles = {
                "private_jc": {
                    "provider": "private",
                    "log": "private_jc_log.csv",
                    "domain_log": "private_domain_log.csv",
                },
                "private_jc_warm": {
                    "provider": "private",
                    "log": "private_jc_warm_log.csv",
                    "domain_log": "private_domain_log.csv",
                },
                "sendgrid_annette": {
                    "provider": "sendgrid",
                    "log": "sendgrid_annette_log.csv",
                    "domain_log": "sendgrid_domain_log.csv",
                },
            }
            for name in (
                "private_jc_log.csv",
                "private_jc_warm_log.csv",
                "private_domain_log.csv",
                "sendgrid_annette_log.csv",
                "sendgrid_domain_log.csv",
            ):
                (logs / name).write_text("TimestampUTC,Email,Status,Info\n", encoding="utf-8")

            with patch.multiple(
                dashboard_core,
                PROFILES=profiles,
                DASHBOARD_PROFILES=list(profiles),
                SENDGRID_PROFILES=["sendgrid_annette"],
            ), patch.object(settings, "LOGS_DIR", logs):
                private_paths = dashboard_core._provider_log_paths("private_jc")
                sendgrid_paths = dashboard_core._provider_log_paths("sendgrid")

        private_resolved = {path.resolve() for path in private_paths}
        sendgrid_resolved = {path.resolve() for path in sendgrid_paths}
        self.assertEqual(
            {(logs / "private_jc_log.csv").resolve(), (logs / "private_jc_warm_log.csv").resolve()},
            private_resolved,
        )
        self.assertNotIn((logs / "private_domain_log.csv").resolve(), private_resolved)
        self.assertIn((logs / "sendgrid_annette_log.csv").resolve(), sendgrid_resolved)
        self.assertIn((logs / "sendgrid_domain_log.csv").resolve(), sendgrid_resolved)

    def test_sendgrid_queue_safety_allows_empty_completed_queue_when_accounted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            state = base / "data" / "state"
            logs = base / "data" / "logs"
            preview_dir = base / "_important" / "dispatch_jobs" / "previews"
            shards.mkdir(parents=True)
            state.mkdir(parents=True)
            logs.mkdir(parents=True)
            preview_dir.mkdir(parents=True)
            preview_id = "dispatch_preview_completed_sendgrid"
            planned_rows = [
                {"Email": "one@example.test", "FirstName": "One"},
                {"Email": "two@example.test", "FirstName": "Two"},
            ]
            for index in range(1, 6):
                self._write_recipient_rows(shards / f"recipients_sendgrid_{index}.csv", [])
            (logs / "sendgrid_annette_log.csv").write_text(
                "TimestampUTC,Email,Status,Info\n"
                "2026-06-25T00:00:00+00:00,one@example.test,SENT,\n"
                "2026-06-25T00:00:01+00:00,two@example.test,ATTEMPT,outcome=sent\n",
                encoding="utf-8",
            )
            (state / "active_campaign_snapshot.json").write_text(json.dumps({"preview_id": preview_id}), encoding="utf-8")
            (preview_dir / f"{preview_id}.json").write_text(
                json.dumps({"preview_id": preview_id, "plan_rows_by_queue": {"sendgrid_1": planned_rows}}),
                encoding="utf-8",
            )

            def fake_report(*, shard_paths=None, **kwargs):
                return {
                    "safe": True,
                    "unsafe_reasons": [],
                    "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])],
                }

            profiles = {
                "sendgrid_annette": {
                    "provider": "sendgrid",
                    "csv": "recipients_sendgrid_1.csv",
                    "log": "sendgrid_annette_log.csv",
                }
            }
            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SHARDS_DIR=shards,
                STATE_DIR=state,
                PROFILES=profiles,
                DASHBOARD_PROFILES=["sendgrid_annette"],
                SENDGRID_PROFILES=["sendgrid_annette"],
            ), patch.object(settings, "LOGS_DIR", logs), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                report = dashboard_core.build_dashboard_queue_safety_report("sendgrid")

        self.assertTrue(report["safe"])
        self.assertTrue(report["partial_consumption_verified"])
        self.assertEqual(2, report["accounted_missing_from_preview_expected_count"])
        self.assertEqual(0, report["live_preview_unique_emails"])
        self.assertIsNone(dashboard_core.queue_safety_alert(report))

    def test_queue_safety_blocks_live_row_already_sent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            state = base / "data" / "state"
            logs = base / "data" / "logs"
            preview_dir = base / "_important" / "dispatch_jobs" / "previews"
            shards.mkdir(parents=True)
            state.mkdir(parents=True)
            logs.mkdir(parents=True)
            preview_dir.mkdir(parents=True)
            preview_id = "dispatch_preview_live_sent_overlap"
            planned_rows = [{"Email": "sent-still-live@example.test", "FirstName": "Sent"}]
            self._write_recipient_rows(shards / "recipients_private_jc.csv", planned_rows)
            (logs / "private_jc_log.csv").write_text(
                "TimestampUTC,Email,Status,Info\n"
                "2026-06-25T00:00:00+00:00,sent-still-live@example.test,SENT,\n",
                encoding="utf-8",
            )
            (state / "active_campaign_snapshot.json").write_text(json.dumps({"preview_id": preview_id}), encoding="utf-8")
            (preview_dir / f"{preview_id}.json").write_text(
                json.dumps({"preview_id": preview_id, "plan_rows_by_queue": {"private_jc": planned_rows}}),
                encoding="utf-8",
            )

            def fake_report(*, shard_paths=None, **kwargs):
                return {
                    "safe": True,
                    "unsafe_reasons": [],
                    "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])],
                }

            profiles = {
                "private_jc": {
                    "provider": "private",
                    "csv": "recipients_private_jc.csv",
                    "log": "private_jc_log.csv",
                    "dashboard_enabled": True,
                }
            }
            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SHARDS_DIR=shards,
                STATE_DIR=state,
                PROFILES=profiles,
                DASHBOARD_PROFILES=["private_jc"],
                SENDGRID_PROFILES=[],
            ), patch.object(settings, "LOGS_DIR", logs), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                report = dashboard_core.build_dashboard_queue_safety_report("private_jc")

        self.assertFalse(report["safe"])
        self.assertEqual(1, report["live_already_sent_overlap_count"])
        self.assertIn("LIVE_ALREADY_SENT_OVERLAP", report["unsafe_reasons"])

    def test_queue_safety_alert_uses_unaccounted_missing_count(self) -> None:
        alert = dashboard_core.queue_safety_alert(
            {
                "safe": False,
                "affected_provider": "private_jc",
                "unsafe_reasons": ["LIVE_ALREADY_SENT_OVERLAP"],
                "missing_from_preview_expected_count": 448,
                "accounted_missing_from_preview_expected_count": 448,
                "unaccounted_missing_from_preview_expected_count": 0,
                "extra_vs_preview_expected_count": 0,
                "live_already_sent_overlap_count": 1,
                "overlap_with_triaged_reject": 0,
                "outside_checked_output_count": 0,
                "outside_intended_source_count": 0,
            }
        )

        self.assertIsNotNone(alert)
        self.assertIn("0 expected preview row(s) are missing without accounting", alert["message"])
        self.assertIn("1 live row(s) already appear in authoritative sent logs", alert["message"])

    def test_queue_safety_blocks_unaccounted_missing_preview_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            state = base / "data" / "state"
            logs = base / "data" / "logs"
            preview_dir = base / "_important" / "dispatch_jobs" / "previews"
            shards.mkdir(parents=True)
            state.mkdir(parents=True)
            logs.mkdir(parents=True)
            preview_dir.mkdir(parents=True)
            preview_id = "dispatch_preview_unaccounted_missing"
            planned_rows = [
                {"Email": "remaining@example.test", "FirstName": "R"},
                {"Email": "missing@example.test", "FirstName": "M"},
            ]
            self._write_recipient_rows(shards / "recipients_private_jc.csv", [planned_rows[0]])
            (logs / "private_jc_log.csv").write_text("TimestampUTC,Email,Status,Info\n", encoding="utf-8")
            (state / "active_campaign_snapshot.json").write_text(json.dumps({"preview_id": preview_id}), encoding="utf-8")
            (preview_dir / f"{preview_id}.json").write_text(
                json.dumps({"preview_id": preview_id, "plan_rows_by_queue": {"private_jc": planned_rows}}),
                encoding="utf-8",
            )

            def fake_report(*, shard_paths=None, **kwargs):
                return {
                    "safe": True,
                    "unsafe_reasons": [],
                    "shards": [{"path": str(path), "name": path.name} for path in (shard_paths or [])],
                }

            profiles = {
                "private_jc": {
                    "provider": "private",
                    "csv": "recipients_private_jc.csv",
                    "log": "private_jc_log.csv",
                    "dashboard_enabled": True,
                }
            }
            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SHARDS_DIR=shards,
                STATE_DIR=state,
                PROFILES=profiles,
                DASHBOARD_PROFILES=["private_jc"],
                SENDGRID_PROFILES=[],
            ), patch.object(settings, "LOGS_DIR", logs), patch.object(
                dashboard_core,
                "build_queue_safety_report",
                side_effect=fake_report,
            ):
                report = dashboard_core.build_dashboard_queue_safety_report("private_jc")

        self.assertFalse(report["safe"])
        self.assertEqual(1, report["unaccounted_missing_from_preview_expected_count"])
        self.assertIn("MISSING_PREVIEW_PLANNED_ROWS", report["unsafe_reasons"])

    def test_sendgrid_queue_safety_alert_still_blocks_sent_log_overlap(self) -> None:
        alert = dashboard_core.queue_safety_alert(
            {
                "safe": False,
                "affected_provider": "sendgrid",
                "unsafe_reasons": ["SENDGRID_ALREADY_SENT_OVERLAP"],
                "sendgrid_already_sent_overlap_count": 1,
                "overlap_with_triaged_reject": 0,
                "outside_checked_output_count": 0,
                "outside_intended_source_count": 0,
            }
        )

        self.assertIsNotNone(alert)
        self.assertEqual("Sendgrid queue unsafe", alert["title"])
        self.assertTrue(alert["blocks_sending"])

    def test_sendgrid_sent_history_counts_attempt_outcome_sent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sendgrid_domain_log.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
                writer.writeheader()
                writer.writerow(
                    {
                        "TimestampUTC": "2026-06-25T00:00:00+00:00",
                        "Email": "sent@example.test",
                        "Status": "ATTEMPT",
                        "Info": "profile=sendgrid; outcome=sent",
                    }
                )
                writer.writerow(
                    {
                        "TimestampUTC": "2026-06-25T00:00:01+00:00",
                        "Email": "failed@example.test",
                        "Status": "ATTEMPT",
                        "Info": "profile=sendgrid; outcome=failed",
                    }
                )

            sent = rebuild_recipient_queues.sent_email_set(path)

        self.assertEqual({"sent@example.test"}, sent)

    def test_sendgrid_queue_safety_blocks_missing_required_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            keep = tmp / "leads_triaged_keep.csv"
            checked = tmp / "leads.csv"
            reject = tmp / "leads_triaged_reject.csv"
            shard = tmp / "recipients_sendgrid_2.csv"
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            rows = [
                {
                    "Email": "reader@example.test",
                    "FirstName": "Ava",
                    "AuthorEmail": "author@example.test",
                    "AuthorName": "Ava Writer",
                    "BookTitle": "Launch",
                }
            ]
            for path, path_rows in ((keep, rows), (checked, rows), (reject, [])):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(path_rows)
            with shard.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName"])
                writer.writeheader()
                writer.writerow({"Email": "reader@example.test", "FirstName": "Ava"})

            report = rebuild_recipient_queues.build_queue_safety_report(
                shard_paths=[shard],
                intended_source_path=keep,
                checked_path=checked,
                triaged_keep_path=keep,
                triaged_reject_path=reject,
            )

        self.assertFalse(report["safe"])
        self.assertIn("MISSING_REQUIRED_HEADERS", report["unsafe_reasons"])
        self.assertEqual(1, report["missing_required_header_shard_count"])
        self.assertEqual(
            ["AuthorEmail", "AuthorName", "BookTitle"],
            report["missing_required_header_shards"][0]["missing_required_headers"],
        )
        alert = dashboard_core.queue_safety_alert(report)
        self.assertIsNotNone(alert)
        self.assertIn("recipients_sendgrid_2.csv", alert["message"])
        self.assertIn("BookTitle", alert["message"])
        self.assertTrue(alert["blocks_sending"])

    def test_sendgrid_safe_rebuild_excludes_unsafe_rows_and_quarantines_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            keep = tmp / "leads_triaged_keep.csv"
            checked = tmp / "leads.csv"
            reject = tmp / "leads_triaged_reject.csv"
            shard_paths = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            keep_rows = [
                {"Email": "keep@example.test", "FirstName": "Keep", "AuthorEmail": "author-keep@example.test", "AuthorName": "Keep Writer", "BookTitle": "Keep Book"},
                {"Email": "outside-checked@example.test", "FirstName": "Out", "AuthorEmail": "author-out@example.test", "AuthorName": "Out Writer", "BookTitle": "Out Book"},
                {"Email": "missing-title@example.test", "FirstName": "Missing", "AuthorEmail": "author-missing@example.test", "AuthorName": "Missing Writer", "BookTitle": ""},
            ]
            reject_row = {"Email": "reject@example.test", "FirstName": "Reject", "AuthorEmail": "author-reject@example.test", "AuthorName": "Reject Writer", "BookTitle": "Reject Book"}
            for path, path_rows in ((keep, keep_rows), (checked, [keep_rows[0], keep_rows[2], reject_row]), (reject, [reject_row])):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(path_rows)
            for index, path in enumerate(shard_paths):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    if index == 1:
                        writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName"])
                        writer.writeheader()
                        writer.writerow({"Email": "outside-intended@example.test", "FirstName": "Old"})
                    else:
                        writer = csv.DictWriter(handle, fieldnames=headers)
                        writer.writeheader()
                        writer.writerow(reject_row if index == 2 else keep_rows[0])

            result = rebuild_recipient_queues.rebuild_sendgrid_recipient_queues(
                intended_source_path=keep,
                checked_path=checked,
                triaged_keep_path=keep,
                triaged_reject_path=reject,
                shard_paths=shard_paths,
                apply=False,
            )

        self.assertEqual("dry-run", result["mode"])
        self.assertFalse(result["before"]["safe"])
        self.assertTrue(result["after"]["safe"])
        self.assertEqual(1, result["included_rows"])
        self.assertGreaterEqual(result["excluded_by_reason"].get("outside_intended_source", 0), 1)
        self.assertGreaterEqual(result["excluded_by_reason"].get("outside_checked_output", 0), 1)
        self.assertGreaterEqual(result["excluded_by_reason"].get("triaged_reject_overlap", 0), 1)
        self.assertGreaterEqual(result["excluded_by_reason"].get("missing_required_field:BookTitle", 0), 1)

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

    def test_infer_runtime_state_distinguishes_smtp_auth_and_reconnect_failures(self) -> None:
        auth = dashboard_core.infer_runtime_state("bash", False, "STOP: auth_error\n")
        reconnect = dashboard_core.infer_runtime_state("bash", False, "STOP: reconnect_failed\n")
        self.assertEqual(("error", "Error", "SMTP authentication failed."), auth)
        self.assertEqual(("error", "Error", "SMTP reconnect failed."), reconnect)

    def test_private_recovered_dns_error_maps_to_recovered_ready(self) -> None:
        health = dashboard_core.build_profile_health_status(
            {
                "name": "private_jc",
                "runtime_state": "running",
                "run_errors": 1,
                "last_status": "SENT",
                "runtime_note": "Sender is actively processing recipients.",
                "last_info": "[Errno 8] nodename nor servname provided, or not known",
                "tmux_tail": "[9/100] SENT reader@example.com",
            },
            webhook_health={},
            private_bounce_guard={},
        )

        self.assertEqual("Recovered", health["label"])
        self.assertEqual("RECOVERED_DNS_ERROR", health["reason_code"])
        self.assertEqual("Ready", health["readiness_label"])
        self.assertEqual("recovered", health["run_issue_state"])

    def test_sendgrid_auth_failure_maps_to_blocked_with_auth_401_reason(self) -> None:
        health = dashboard_core.build_profile_health_status(
            {
                "name": "sendgrid_alpha",
                "runtime_state": "error",
                "run_errors": 1,
                "last_status": "ERROR",
                "runtime_note": "STOP: sendgrid account-level error (auth/credits/region).",
                "last_info": "HTTP Error 401 Unauthorized",
                "tmux_tail": "HTTP Error 401 Unauthorized",
            },
            webhook_health={},
            private_bounce_guard={},
        )

        self.assertEqual("Blocked", health["label"])
        self.assertEqual("AUTH_401", health["reason_code"])
        self.assertEqual("Blocked", health["readiness_label"])
        self.assertEqual("active", health["run_issue_state"])

    def test_webhook_stale_maps_to_watch_and_telemetry_degraded(self) -> None:
        fake_now = dashboard_core.datetime(2026, 4, 11, 12, 0, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime):
            health = dashboard_core.build_profile_health_status(
                {
                    "name": "sendgrid_alpha",
                    "runtime_state": "running",
                    "run_errors": 0,
                    "last_status": "SENT",
                    "runtime_note": "Sender is actively processing recipients.",
                },
                webhook_health={
                    "last_received_iso": "2026-04-11T11:00:00+00:00",
                    "last_received_age": "60m ago",
                },
                private_bounce_guard={},
            )

        self.assertEqual("Watch", health["label"])
        self.assertEqual("WEBHOOK_STALE", health["reason_code"])
        self.assertEqual("Telemetry Degraded", health["readiness_label"])

    def test_provider_cooldown_maps_to_paused_and_cooling_down(self) -> None:
        health = dashboard_core.build_profile_health_status(
            {
                "name": "private_jc",
                "runtime_state": "paused",
                "run_errors": 0,
                "provider_cooldown_remaining_seconds": 900,
                "restart_blocked": True,
                "restart_block_reason": "Provider cooldown active for about 15 minute(s).",
            },
            webhook_health={},
            private_bounce_guard={},
        )

        self.assertEqual("Paused", health["label"])
        self.assertIn(health["reason_code"], {"PROVIDER_COOLDOWN", "THROTTLE_COOLDOWN"})
        self.assertEqual("Cooling Down", health["readiness_label"])

    def test_active_sender_with_no_issue_maps_to_healthy_ready(self) -> None:
        fake_now = dashboard_core.datetime(2026, 4, 11, 12, 0, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime):
            health = dashboard_core.build_profile_health_status(
                {
                    "name": "sendgrid_alpha",
                    "runtime_state": "running",
                    "run_errors": 0,
                    "last_status": "SENT",
                    "runtime_note": "Sender is actively processing recipients.",
                },
                webhook_health={
                    "last_received_iso": "2026-04-11T11:58:00+00:00",
                    "last_received_age": "2m ago",
                },
                private_bounce_guard={},
            )

        self.assertEqual("Healthy", health["label"])
        self.assertEqual("Ready", health["readiness_label"])
        self.assertEqual("READY", health["reason_code"])

    def test_process_runtime_fallback_uses_last_successful_send_timestamp(self) -> None:
        fake_now = dashboard_core.datetime(2026, 4, 11, 12, 5, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        snapshot = dashboard_core.ProfileSnapshot(
            name="sendgrid_alpha",
            pane_index=0,
            csv_path="recipients_alpha.csv",
            log_path="sendgrid_alpha_log.csv",
            max_total=100,
            cooldown_seconds=35,
            cooldown_remaining_seconds=0,
            pending_count=12,
            run_started_at="",
            run_sent=1,
            run_errors=1,
            run_skipped=0,
            sent_today=1,
            errors_today=1,
            skipped_today=0,
            last_status="ERROR",
            last_email="reader@example.com",
            last_info="temporary failure",
            last_timestamp="2026-04-11 05:04:55 PDT",
            last_timestamp_utc="2026-04-11T12:04:55+00:00",
            last_age="5s ago",
            tmux_running=False,
            tmux_dead=False,
            tmux_command="bash",
            tmux_tail="repo$",
            runtime_state="stopped",
            runtime_label="Stopped",
            runtime_note="Pane is idle.",
            effective_cooldown_seconds=35,
            effective_spacing_seconds=35,
            last_sent_timestamp_utc="2026-04-11T12:04:45+00:00",
        )

        with patch.object(dashboard_core, "datetime", FrozenDateTime):
            dashboard_core._apply_process_runtime_fallback(snapshot)

        self.assertTrue(snapshot.tmux_running)
        self.assertEqual("cooldown", snapshot.runtime_state)
        self.assertEqual(20, snapshot.cooldown_remaining_seconds)
        self.assertEqual("Cooling down between sends: 20s remaining.", snapshot.runtime_note)

    def test_historical_current_run_error_does_not_dominate_after_recovery(self) -> None:
        fake_now = dashboard_core.datetime(2026, 4, 11, 12, 0, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime):
            health = dashboard_core.build_profile_health_status(
                {
                    "name": "sendgrid_alpha",
                    "runtime_state": "running",
                    "run_errors": 2,
                    "last_status": "SENT",
                    "runtime_note": "Sender is actively processing recipients.",
                    "last_info": "Recovered after one transient request error.",
                },
                webhook_health={
                    "last_received_iso": "2026-04-11T11:58:00+00:00",
                    "last_received_age": "2m ago",
                },
                private_bounce_guard={},
            )

        self.assertEqual("Recovered", health["label"])
        self.assertEqual("Ready", health["readiness_label"])
        self.assertEqual("recovered", health["run_issue_state"])

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
                    "interval": 35,
                    "cooldown_seconds": 35,
                    "repeat": True,
                    "stop_at_local": "12:00",
                    "max_total": 100,
                }
            }
            (base / "dashboard_run_settings.json").write_text(
                json.dumps({"send_cap_per_profile": 5000, "updated_at_utc": "2026-03-25T01:00:00+00:00"}),
                encoding="utf-8",
            )
            self._write_recipients(base / "recipients_alpha.csv", "reader@example.com")
            self._write_log(base / "sendgrid_alpha_log.csv", [])

            with self._patched_dashboard_context(base, profiles):
                snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        self.assertEqual(5000, snapshot["controls"]["send_target_total"])
        self.assertEqual(5000, snapshot["controls"]["estimated_total_if_start_all"])
        self.assertEqual(5000, snapshot["profiles"][0]["max_total"])
        self.assertEqual(100, snapshot["profiles"][0]["configured_max_total"])
        self.assertEqual(35, snapshot["profiles"][0]["interval_seconds"])
        self.assertEqual(35, snapshot["profiles"][0]["effective_spacing_seconds"])
        self.assertEqual(103, snapshot["profiles"][0]["effective_pace_per_hour"])

    def test_build_snapshot_applies_outside_tmux_sendgrid_cooldown_from_last_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "interval": 35,
                    "cooldown_seconds": 35,
                    "repeat": True,
                    "max_total": 100,
                }
            }
            self._write_recipients(base / "recipients_alpha.csv", "reader@example.com")
            self._write_log(
                base / "sendgrid_alpha_log.csv",
                [
                    ("2026-03-13T12:00:00+00:00", "probe@example.com", "SENT", ""),
                    ("2026-03-13T12:04:45+00:00", "reader@example.com", "SENT", "sg_message_id=abc123"),
                    ("2026-03-13T12:04:55+00:00", "reader@example.com", "ERROR", "temporary failure"),
                ],
            )
            fake_now = dashboard_core.datetime(2026, 3, 13, 12, 5, 0, tzinfo=dashboard_core.timezone.utc)

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

                with patch.object(dashboard_core, "datetime", FrozenDateTime), patch.multiple(
                    dashboard_core,
                    tmux_pane_map=lambda session="sendgrid": {"0": {"cmd": "bash", "dead": "0"}},
                    tmux_capture_tail=lambda pane_index, session="sendgrid", lines=16: "repo$",
                    _detect_running_send_shard_profiles=lambda: {"sendgrid_alpha"},
                    fetch_sendgrid_receiver_summary=lambda hours: None,
                ):
                    snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        profile = snapshot["profiles"][0]
        self.assertEqual("ERROR", profile["last_status"])
        self.assertEqual("cooldown", profile["runtime_state"])
        self.assertEqual(20, profile["cooldown_remaining_seconds"])
        self.assertTrue(profile["tmux_running"])
        self.assertEqual("2026-03-13T12:04:45+00:00", profile["last_sent_timestamp_utc"])

    def test_build_snapshot_reads_private_jc_tail_from_private_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            profiles = {
                "private_jc": {
                    "provider": "private",
                    "csv": "recipients_private_jc.csv",
                    "log": "private_jc_log.csv",
                    "from_email": "jc@astraproductions.co",
                    "always_send": "astraproductionsbyjc@gmail.com",
                    "interval": 120,
                    "cooldown_seconds": 120,
                    "repeat": True,
                    "max_total": 0,
                    "dashboard_enabled": True,
                    "dashboard_manual_only": True,
                    "tmux_session": "private_jc",
                },
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                    "interval": 35,
                    "cooldown_seconds": 35,
                    "repeat": True,
                    "max_total": 100,
                },
            }
            self._write_recipients(base / "recipients_private_jc.csv", "reader@example.com")
            self._write_recipients(base / "recipients_alpha.csv", "reader@example.com")
            self._write_log(
                base / "private_jc_log.csv",
                [
                    ("2026-03-13T12:03:00+00:00", "astraproductionsbyjc@gmail.com", "SENT", ""),
                    ("2026-03-13T12:04:00+00:00", "reader@example.com", "SENT", ""),
                ],
            )
            self._write_log(
                base / "sendgrid_alpha_log.csv",
                [
                    ("2026-03-13T12:04:40+00:00", "probe@example.com", "SENT", ""),
                    ("2026-03-13T12:04:50+00:00", "reader@example.com", "SENT", ""),
                ],
            )
            fake_now = dashboard_core.datetime(2026, 3, 13, 12, 5, 0, tzinfo=dashboard_core.timezone.utc)

            def fake_tmux_capture_tail(pane_index: int, session: str = "sendgrid", lines: int = 16) -> str:
                if session == "private_jc":
                    return "[1/100] SENT reader@example.com\nBATCH: sent=1 total=2 remaining_estimate=98 next_sleep_seconds=120"
                return "[1/100] SENT reader@example.com\nBATCH: sent=1 total=2 remaining_estimate=98 next_sleep_seconds=35"

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

                with patch.object(dashboard_core, "datetime", FrozenDateTime), patch.multiple(
                    dashboard_core,
                    tmux_pane_map=lambda session="sendgrid": {"0": {"cmd": "python", "dead": "0"}},
                    tmux_capture_tail=fake_tmux_capture_tail,
                    fetch_sendgrid_receiver_summary=lambda hours: None,
                ):
                    snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        jc = next(profile for profile in snapshot["profiles"] if profile["name"] == "private_jc")
        self.assertEqual("cooldown", jc["runtime_state"])
        self.assertEqual(120, jc["cooldown_remaining_seconds"])
        self.assertEqual("Cooling down between sends: 120s remaining.", jc["runtime_note"])

    def test_build_snapshot_prefers_receiver_summary_for_sendgrid_telemetry(self) -> None:
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
                [("2026-03-13T12:00:00+00:00", "reader@example.com", "SENT", "sg_message_id=msg-1")],
            )
            receiver_summary = {
                "selected_window_hours": 24,
                "last_received_iso": "2026-03-13T12:04:30+00:00",
                "events_5m": 2,
                "events_1h": 4,
                "unmapped_events_24h": 1,
                "profiles": {
                    "sendgrid_alpha": {
                        "last_webhook_received_at": "2026-03-13T12:04:30+00:00",
                        "mapped_events_24h": 3,
                        "unmapped_events_24h": 1,
                        "processed": 1,
                        "delivered": 1,
                        "deferred": 1,
                        "bounced": 0,
                        "blocked": 0,
                        "dropped": 0,
                        "latest_event": {
                            "time": "2026-03-13T12:04:00+00:00",
                            "status": "delivered",
                            "email": "reader@example.com",
                            "reason": "250 OK",
                        },
                        "recent": [],
                    }
                },
            }

            with self._patched_dashboard_context(base, profiles), patch.object(
                dashboard_core,
                "fetch_sendgrid_receiver_summary",
                return_value=receiver_summary,
            ):
                snapshot = dashboard_core.build_dashboard_snapshot(activity_hours=24, tail_lines=8)

        profile = snapshot["profiles"][0]
        self.assertEqual(3, profile["webhook"]["mapped_events_24h"])
        self.assertEqual(1, profile["webhook"]["unmapped_events_24h"])
        self.assertEqual(1, profile["webhook"]["summary"]["processed"])
        self.assertEqual(1, profile["webhook"]["summary"]["delivered"])
        self.assertEqual(1, snapshot["summary"]["recent_unmapped"])
        self.assertEqual("2026-03-13T12:04:30+00:00", snapshot["webhook_health"]["last_received_iso"])

    def test_start_sendgrid_profile_uses_dashboard_send_cap_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")
            settings_path = base / "dashboard_run_settings.json"
            settings_path.write_text(json.dumps({"send_cap_per_profile": 5000}), encoding="utf-8")

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
                resolve_sendgrid_api_key=lambda **kwargs: SimpleNamespace(
                    ok=True,
                    key="SG.test-key",
                    error="",
                ),
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, _ = dashboard_core.start_sendgrid_profile("sendgrid_alpha", 0)

        self.assertTrue(ok)
        self.assertIn(
            [
                str(python_bin),
                "send_shard.py",
                "--profile",
                "sendgrid_alpha",
                "--preflight",
                "--max_total",
                "5000",
                "--max_messages_1h",
                "278",
            ],
            calls,
        )
        send_keys_commands = [cmd for cmd in calls if cmd[:3] == ["tmux", "send-keys", "-t"]]
        self.assertTrue(any("--max_total 5000 --max_messages_1h 278" in " ".join(cmd) for cmd in send_keys_commands))

    def test_run_sendgrid_launcher_preflights_start_all_sendgrid_profiles_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")
            calls: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                calls.append(list(cmd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SENDGRID_PROFILES=["sendgrid_annette", "sendgrid_jordan"],
                DASHBOARD_PROFILES=["sendgrid_annette", "sendgrid_jordan", "private_jc"],
                START_ALL_PROFILES=["sendgrid_annette", "sendgrid_jordan"],
                PYTHON_BIN=python_bin,
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="SG.synthetic",
                    source_label="synthetic",
                    masked_key="SG.s...",
                    warning="",
                    error="",
                ),
            ), patch.object(
                dashboard_core,
                "_wait_for_started_profiles",
                return_value={"sendgrid_annette", "sendgrid_jordan"},
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, message = dashboard_core.run_sendgrid_launcher()

        self.assertTrue(ok, message)
        preflight_profiles = [
            cmd[cmd.index("--profile") + 1]
            for cmd in calls
            if "send_shard.py" in cmd and "--preflight" in cmd
        ]
        self.assertEqual(["sendgrid_annette", "sendgrid_jordan"], preflight_profiles)
        self.assertNotIn("private_jc", preflight_profiles)
        self.assertTrue(any(cmd[:2] == ["bash", "./run_sendgrid_tmux.sh"] for cmd in calls))

    def test_active_or_locked_sender_profiles_includes_runtime_locks(self) -> None:
        with patch.object(dashboard_core, "DASHBOARD_PROFILES", ["sendgrid_annette"]), patch.object(
            dashboard_core,
            "detect_running_sender_profiles",
            return_value=set(),
        ), patch.object(
            dashboard_core,
            "profile_runtime_lock_status",
            return_value={"locked": True, "pid": 1234},
        ):
            self.assertEqual({"sendgrid_annette"}, dashboard_core.active_or_locked_sender_profiles(["sendgrid_annette"]))

    def test_run_sendgrid_launcher_refuses_already_running_or_locked_profile(self) -> None:
        with patch.multiple(
            dashboard_core,
            SENDGRID_PROFILES=["sendgrid_annette"],
            DASHBOARD_PROFILES=["sendgrid_annette"],
            START_ALL_PROFILES=["sendgrid_annette"],
        ), patch.object(
            dashboard_core,
            "active_or_locked_sender_profiles",
            return_value={"sendgrid_annette"},
        ), patch.object(dashboard_core.subprocess, "run") as run_mock:
            ok, message = dashboard_core.run_sendgrid_launcher()

        self.assertFalse(ok)
        self.assertIn("already running or locked", message)
        run_mock.assert_not_called()

    def test_run_sendgrid_launcher_reports_success_only_when_all_five_profiles_active(self) -> None:
        profiles = [
            "sendgrid_annette",
            "sendgrid_jordan",
            "sendgrid_jodi",
            "sendgrid_alison",
            "sendgrid_fiorela",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                return SimpleNamespace(returncode=0, stdout=f"ok {' '.join(cmd)}", stderr="")

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SENDGRID_PROFILES=profiles,
                DASHBOARD_PROFILES=profiles + ["private_jc"],
                START_ALL_PROFILES=profiles,
                PYTHON_BIN=python_bin,
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="SG.synthetic",
                    source_label="synthetic",
                    masked_key="SG.s...",
                    warning="",
                    error="",
                ),
            ), patch.object(
                dashboard_core,
                "_wait_for_started_profiles",
                return_value=set(profiles),
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, message = dashboard_core.run_sendgrid_launcher()

        self.assertTrue(ok, message)
        self.assertNotIn("PARTIALLY_STARTED", message)

    def test_run_sendgrid_launcher_reports_partial_when_one_profile_missing(self) -> None:
        profiles = [
            "sendgrid_annette",
            "sendgrid_jordan",
            "sendgrid_jodi",
            "sendgrid_alison",
            "sendgrid_fiorela",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                if "--preflight" in cmd:
                    profile = cmd[cmd.index("--profile") + 1]
                    return SimpleNamespace(returncode=0, stdout=f"{profile}: status=OK", stderr="")
                return SimpleNamespace(returncode=0, stdout="Started tmux session: sendgrid", stderr="")

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SENDGRID_PROFILES=profiles,
                DASHBOARD_PROFILES=profiles + ["private_jc"],
                START_ALL_PROFILES=profiles,
                PYTHON_BIN=python_bin,
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="SG.synthetic",
                    source_label="synthetic",
                    masked_key="SG.s...",
                    warning="",
                    error="",
                ),
            ), patch.object(
                dashboard_core,
                "_wait_for_started_profiles",
                return_value=set(profiles) - {"sendgrid_fiorela"},
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, message = dashboard_core.run_sendgrid_launcher()

        self.assertFalse(ok)
        self.assertIn("PARTIALLY_STARTED", message)
        self.assertIn("sendgrid_fiorela", message)
        self.assertIn("sendgrid_fiorela: status=OK", message)

    def test_run_sendgrid_launcher_reports_shell_partial_launch_failure(self) -> None:
        profiles = [
            "sendgrid_annette",
            "sendgrid_jordan",
            "sendgrid_jodi",
            "sendgrid_alison",
            "sendgrid_fiorela",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                if "--preflight" in cmd:
                    return SimpleNamespace(returncode=0, stdout="status=OK", stderr="")
                return SimpleNamespace(
                    returncode=2,
                    stdout="Started tmux session setup\nPARTIALLY_STARTED: missing profiles: sendgrid_fiorela",
                    stderr="",
                )

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SENDGRID_PROFILES=profiles,
                DASHBOARD_PROFILES=profiles + ["private_jc"],
                START_ALL_PROFILES=profiles,
                PYTHON_BIN=python_bin,
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="SG.synthetic",
                    source_label="synthetic",
                    masked_key="SG.s...",
                    warning="",
                    error="",
                ),
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, message = dashboard_core.run_sendgrid_launcher()

        self.assertFalse(ok)
        self.assertTrue(message.startswith("PARTIALLY_STARTED"))
        self.assertIn("sendgrid_fiorela", message)

    def test_run_sendgrid_tmux_script_uses_explicit_pane_ids_and_includes_fiorela(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "run_sendgrid_tmux.sh").read_text(encoding="utf-8")
        self.assertIn("sendgrid_fiorela", script)
        self.assertIn("mapfile -t PANE_IDS", script)
        self.assertIn("Launching $profile in pane $pane", script)
        self.assertIn("send_shard.py --profile $profile", script)
        self.assertIn("PARTIALLY_STARTED: missing profiles", script)
        self.assertIn("TMUX_SENDGRID_DRY_RUN", script)

    def test_run_sendgrid_tmux_script_does_not_normalize_or_rewrite_shards(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "run_sendgrid_tmux.sh").read_text(encoding="utf-8")
        self.assertNotIn("Normalizing SendGrid shards", script)
        self.assertNotIn("normalize_sendgrid_shards.py", script)
        self.assertNotIn("SENDGRID_NORMALIZE_REPORT", script)
        self.assertNotIn("SENDGRID_BACKUP_DIR", script)
        self.assertNotIn("sendgrid_shard_normalize_report", script)

    def test_run_sendgrid_launcher_does_not_modify_recipient_csvs_before_launch(self) -> None:
        profiles = [
            "sendgrid_annette",
            "sendgrid_jordan",
            "sendgrid_jodi",
            "sendgrid_alison",
            "sendgrid_fiorela",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")
            shard_paths = []
            profile_map = {}
            for index, profile in enumerate(profiles, start=1):
                shard = base / f"recipients_sendgrid_{index}.csv"
                shard.write_text("Email,FirstName,BookTitle\nreader@example.test,Ava,Book\n", encoding="utf-8")
                shard_paths.append(shard)
                profile_map[profile] = {"provider": "sendgrid", "csv": shard.name, "log": f"{profile}_log.csv"}
            before = {path: path.stat().st_mtime_ns for path in shard_paths}

            def fake_run(cmd, **kwargs):
                self.assertEqual(before, {path: path.stat().st_mtime_ns for path in shard_paths})
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SHARDS_DIR=base,
                PROFILES=profile_map,
                SENDGRID_PROFILES=profiles,
                DASHBOARD_PROFILES=profiles,
                START_ALL_PROFILES=profiles,
                PYTHON_BIN=python_bin,
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="SG.synthetic",
                    source_label="synthetic",
                    masked_key="SG.s...",
                    warning="",
                    error="",
                ),
            ), patch.object(
                dashboard_core,
                "_wait_for_started_profiles",
                return_value=set(profiles),
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run):
                ok, message = dashboard_core.run_sendgrid_launcher()

            after = {path: path.stat().st_mtime_ns for path in shard_paths}

        self.assertTrue(ok, message)
        self.assertEqual(before, after)

    def test_run_sendgrid_launcher_reports_failing_preflight_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                if "sendgrid_jordan" in cmd:
                    return SimpleNamespace(returncode=1, stdout="", stderr="synthetic preflight failure")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.multiple(
                dashboard_core,
                ROOT=base,
                SENDGRID_PROFILES=["sendgrid_annette", "sendgrid_jordan"],
                START_ALL_PROFILES=["sendgrid_annette", "sendgrid_jordan"],
                PYTHON_BIN=python_bin,
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="SG.synthetic",
                    source_label="synthetic",
                    masked_key="SG.s...",
                    warning="",
                    error="",
                ),
            ), patch.object(dashboard_core.subprocess, "run", side_effect=fake_run) as run_mock:
                ok, message = dashboard_core.run_sendgrid_launcher()

        self.assertFalse(ok)
        self.assertIn("synthetic preflight failure", message)
        preflight_calls = [
            call.args[0]
            for call in run_mock.call_args_list
            if "send_shard.py" in call.args[0] and "--preflight" in call.args[0]
        ]
        self.assertEqual(2, len(preflight_calls))

    def test_sendgrid_hourly_cap_status_uses_dashboard_window_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            settings_path = base / "dashboard_run_settings.json"
            settings_path.write_text(json.dumps({"send_cap_per_profile": 10000}), encoding="utf-8")
            profiles = {
                name: {
                    "provider": "sendgrid",
                    "csv": f"{name}.csv",
                    "log": f"{name}.csv",
                    "from_email": f"{name}@example.com",
                    "interval": 35,
                    "cooldown_seconds": 35,
                }
                for name in ["sendgrid_a", "sendgrid_b", "sendgrid_c", "sendgrid_d", "sendgrid_e"]
            }
            with patch.multiple(
                dashboard_core,
                PROFILES=profiles,
                SENDGRID_PROFILES=list(profiles.keys()),
                DASHBOARD_PROFILES=list(profiles.keys()),
                START_ALL_PROFILES=list(profiles.keys()),
                DASHBOARD_RUN_SETTINGS_PATH=settings_path,
                LOGS_DIR=base,
            ):
                status = dashboard_core.build_sendgrid_hourly_cap_status()

        self.assertEqual(556, status["cap"])

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
            active_or_locked_sender_profiles=lambda profile_names=None: set(),
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

    def test_start_private_profile_refuses_runtime_locked_profile(self) -> None:
        with patch.object(dashboard_core, "DASHBOARD_PROFILES", ["private_jc"]), patch.object(
            dashboard_core,
            "active_or_locked_sender_profiles",
            return_value={"private_jc"},
        ), patch.object(dashboard_core.subprocess, "run") as run_mock:
            ok, message = dashboard_core.start_private_profile("private_jc", session="private_jc")

        self.assertFalse(ok)
        self.assertIn("already running or locked", message)
        run_mock.assert_not_called()

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
                    active_or_locked_sender_profiles=lambda profile_names=None: set(),
                    _load_env_value=lambda name: "secret",
                ):
                    ok, message = dashboard_core.start_private_profile("private_jc", session="private_jc")

        self.assertFalse(ok)
        self.assertIn("provider cooldown", message.lower())

    def test_start_sendgrid_profile_rejects_placeholder_key_resolution(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            python_bin = base / "python"
            python_bin.write_text("", encoding="utf-8")
            python_bin.chmod(0o755)

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
                resolve_sendgrid_api_key=lambda **kwargs: SendGridKeyResolution(
                    key="",
                    source_label="inherited environment",
                    masked_key="(invalid)",
                    warning="",
                    error="SENDGRID_API_KEY from the inherited environment is a placeholder or blank value.",
                ),
            ):
                ok, message = dashboard_core.start_sendgrid_profile("sendgrid_alpha", 0)

        self.assertFalse(ok)
        self.assertIn("placeholder or blank value", message)

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
            "last_timestamp_utc": "",
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
        self.assertTrue(alerts)
        for alert in alerts:
            self.assertFalse(alert["blocks_sending"])
            self.assertEqual("Non-blocking", alert["blocking_label"])
            self.assertEqual("dashboard_core.build_threshold_alerts", alert["source_function"])

        stale_alert = next(alert for alert in alerts if alert["title"] == "Webhook intake stale")
        self.assertIn("Last webhook seen: 50m ago (2026-03-13T11:40:00+00:00)", stale_alert["message"])
        self.assertIn("Active SendGrid profiles: 1 (yes)", stale_alert["message"])
        self.assertIn("Awaiting outcomes: 11 (backlog alert threshold 10)", stale_alert["message"])
        self.assertIn("accepted recipients may not receive final delivery or bounce outcomes", stale_alert["message"])
        self.assertIn("SendGrid Event Webhook URL", stale_alert["message"])
        self.assertIn("public tunnel/receiver", stale_alert["message"])
        self.assertIn("endpoint reachability", stale_alert["message"])
        self.assertIn("webhook signing/secrets", stale_alert["message"])

    def test_build_threshold_alerts_does_not_report_sendgrid_stale_for_private_only_activity(self) -> None:
        alerts = dashboard_core.build_threshold_alerts(
            session_label="running",
            active_profiles=1,
            recent_failures=0,
            recent_unmapped=0,
            total_awaiting_outcome=0,
            webhook_health={"last_received_age": "never"},
            profile_dicts=[
                {"name": "private_jc", "runtime_state": "running", "awaiting_outcome": 0},
                {"name": "sendgrid_alpha", "runtime_state": "stopped", "awaiting_outcome": 0},
            ],
        )

        self.assertNotIn("Webhook intake stale", {alert["title"] for alert in alerts})

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

    def test_build_threshold_alerts_ignores_recovered_run_issue_for_sender_api_alert(self) -> None:
        alerts = dashboard_core.build_threshold_alerts(
            session_label="running",
            active_profiles=1,
            recent_failures=0,
            recent_unmapped=0,
            total_awaiting_outcome=0,
            webhook_health={},
            profile_dicts=[
                {"name": "sendgrid_annette", "run_errors": 1, "runtime_state": "cooldown", "run_issue_state": "recovered"},
                {"name": "sendgrid_jodi", "run_errors": 1, "runtime_state": "stopped", "run_issue_state": "recovered"},
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
            last_timestamp_utc="2026-03-13T12:10:00+00:00",
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
            PROFILE_GUARD_BOUNCE_THRESHOLD=3,
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
            last_timestamp_utc="2026-03-13T12:10:00+00:00",
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
                PROFILE_GUARD_BOUNCE_THRESHOLD=3,
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
        self.assertIn("sendgrid_outcome_health", snapshot)
        self.assertTrue(snapshot["sendgrid_outcome_health"]["webhook_route_exists"])

    def test_sendgrid_outcome_health_warns_when_events_stale_with_awaiting_outcomes(self) -> None:
        fake_now = dashboard_core.datetime(2026, 7, 15, 12, 0, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime), patch.object(
            dashboard_core,
            "SENDGRID_WEBHOOK_RECEIVER_URL",
            "",
        ), patch.object(dashboard_core, "WEBHOOK_SIGNATURE_ENABLED", True):
            health = dashboard_core.build_sendgrid_outcome_health(
                {
                    "last_received_iso": "2026-07-13T11:00:00+00:00",
                    "last_received_age": "2d ago",
                },
                total_awaiting_outcome=814,
            )

        self.assertEqual("stale", health["state"])
        self.assertTrue(health["warning"])
        self.assertTrue(health["webhook_route_exists"])
        self.assertTrue(health["sendgrid_event_public_key_configured"])
        self.assertFalse(health["sendgrid_webhook_receiver_url_configured"])
        self.assertEqual("2026-07-13T11:00:00+00:00", health["latest_sendgrid_event_timestamp"])
        self.assertEqual(dashboard_core.SENDGRID_OUTCOME_STALE_WARNING_TEXT, health["warning_text"])

    def test_sendgrid_outcome_health_healthy_when_events_recent(self) -> None:
        fake_now = dashboard_core.datetime(2026, 7, 15, 12, 0, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime), patch.object(
            dashboard_core,
            "SENDGRID_WEBHOOK_RECEIVER_URL",
            "https://receiver.example.com",
        ), patch.object(dashboard_core, "WEBHOOK_SIGNATURE_ENABLED", True):
            health = dashboard_core.build_sendgrid_outcome_health(
                {
                    "last_received_iso": "2026-07-15T11:55:00+00:00",
                    "last_received_age": "5m ago",
                },
                total_awaiting_outcome=3,
            )

        self.assertEqual("healthy", health["state"])
        self.assertFalse(health["warning"])
        self.assertTrue(health["sendgrid_webhook_receiver_url_configured"])
        self.assertTrue(health["sendgrid_event_public_key_configured"])
        self.assertEqual("", health["warning_text"])

    def test_sendgrid_outcome_health_reports_missing_receiver_url_without_stale_warning(self) -> None:
        fake_now = dashboard_core.datetime(2026, 7, 15, 12, 0, 0, tzinfo=dashboard_core.timezone.utc)

        class FrozenDateTime(dashboard_core.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fake_now.replace(tzinfo=None)
                return fake_now.astimezone(tz)

        with patch.object(dashboard_core, "datetime", FrozenDateTime), patch.object(
            dashboard_core,
            "SENDGRID_WEBHOOK_RECEIVER_URL",
            "",
        ), patch.object(dashboard_core, "WEBHOOK_SIGNATURE_ENABLED", False):
            health = dashboard_core.build_sendgrid_outcome_health(
                {
                    "last_received_iso": "2026-07-15T11:55:00+00:00",
                    "last_received_age": "5m ago",
                },
                total_awaiting_outcome=0,
            )

        self.assertEqual("missing_receiver_url", health["state"])
        self.assertFalse(health["warning"])
        self.assertFalse(health["sendgrid_webhook_receiver_url_configured"])
        self.assertFalse(health["sendgrid_event_public_key_configured"])

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

    def _write_recipient_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

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
