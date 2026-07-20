from __future__ import annotations

import asyncio
import csv
import json
import os
import subprocess
from io import BytesIO, StringIO
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import Workbook

import lead_ledger
import dashboard_core
import important_leads_verify
import important_leads_workflow
import live_dashboard
from important_leads_workflow import ImportantLeadsCheckError


class LiveDashboardTests(unittest.TestCase):
    def _write_csv(self, path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def _read_csv_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))

    def test_preview_validate_profile_runs_preview_then_validation_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            preview_path = tmp / "sendgrid_annette_message_preview.csv"
            validated_path = tmp / "sendgrid_annette_message_preview_validated.csv"
            failed_path = tmp / "sendgrid_annette_message_preview_failed.csv"
            summary_path = tmp / "sendgrid_annette_message_preview_summary.txt"
            calls: list[list[str]] = []

            def fake_run(command, **kwargs):
                calls.append([str(part) for part in command])
                if "send_shard.py" in command:
                    preview_path.write_text(
                        "Email,FirstName,BookTitle,Subject,Body\nreader@example.com,Ava,Launch,Subject,Body\n",
                        encoding="utf-8",
                    )
                else:
                    validated_path.write_text("Email\nreader@example.com\n", encoding="utf-8")
                    failed_path.write_text("Email\n", encoding="utf-8")
                    summary_path.write_text("failed rows: 0\n", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with (
                patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True),
                patch.object(live_dashboard, "_active_sender_names", return_value=set()),
                patch.object(live_dashboard, "_find_active_dashboard_job", return_value=None),
                patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": []}),
                patch.object(live_dashboard, "message_preview_path_for_profile", return_value=preview_path),
                patch.object(live_dashboard, "message_preview_output_paths", return_value=(validated_path, failed_path, summary_path)),
                patch.object(live_dashboard, "append_campaign_run_history") as history_mock,
                patch.object(live_dashboard, "subprocess") as subprocess_mock,
            ):
                subprocess_mock.run.side_effect = fake_run
                subprocess_mock.TimeoutExpired = subprocess.TimeoutExpired
                response = live_dashboard.preview_validate_profile("sendgrid_annette")

        payload = json.loads(response.body)
        self.assertTrue(payload["ok"])
        self.assertEqual("PASS", payload["result"]["validation_status"])
        self.assertEqual(1, payload["result"]["preview_row_count"])
        self.assertEqual("consignment", payload["result"]["pitch_mode"])
        self.assertEqual("send_shard.py", calls[0][1])
        self.assertEqual("tools/validate_message_preview.py", calls[1][1])
        self.assertIn("--preview_messages", calls[0])
        self.assertIn("--fail-on-errors", calls[1])
        self.assertEqual(
            ["preview_validate_started", "preview_validate_completed"],
            [call.args[0]["event_type"] for call in history_mock.call_args_list],
        )

    def test_background_automation_does_not_auto_start_senders_by_default(self) -> None:
        def exercise_monitor_start(**kwargs):
            ok, message = kwargs["start_profile"]("private_jc")
            self.assertFalse(ok)
            self.assertIn("Automatic sender startup disabled", message)

        with patch.dict(os.environ, {}, clear=False), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
        ) as start_sender, patch.object(
            live_dashboard.runtime_control,
            "apply_delivery_guards",
        ), patch.object(
            live_dashboard,
            "PRIVATE_BOUNCE_MONITOR_ENABLED",
            True,
        ), patch.object(
            live_dashboard,
            "_profile_runtime_active",
            return_value=False,
        ), patch.object(
            live_dashboard,
            "run_private_bounce_monitor_cycle",
            side_effect=exercise_monitor_start,
        ):
            os.environ.pop(live_dashboard.DASHBOARD_AUTO_START_ENV_VAR, None)
            live_dashboard._run_background_automation_once()

        start_sender.assert_not_called()

    def test_daily_auto_start_runs_when_explicitly_enabled(self) -> None:
        run_settings = {
            "auto_start_sendgrid_enabled": True,
            "auto_start_sendgrid_local_time": "00:00",
            "auto_start_private_jc_enabled": False,
            "auto_start_private_jc_local_time": "00:00",
        }
        with patch.dict(os.environ, {live_dashboard.DASHBOARD_AUTO_START_ENV_VAR: "1"}), patch.object(
            live_dashboard,
            "load_dashboard_run_settings",
            return_value=run_settings,
        ), patch.object(
            live_dashboard,
            "_load_dashboard_auto_start_state",
            return_value={
                "sendgrid_last_started_local_date": "",
                "sendgrid_last_attempt_utc": "",
                "private_jc_last_started_local_date": "",
                "private_jc_last_attempt_utc": "",
                "private_jc_recovery_last_attempt_utc": "",
            },
        ), patch.object(
            live_dashboard,
            "_active_dashboard_profiles",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_retry_due",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "_save_dashboard_auto_start_state",
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "Started."),
        ) as start_sender:
            live_dashboard._run_dashboard_daily_auto_start_once()

        self.assertEqual(
            list(live_dashboard.SENDGRID_PROFILES),
            [call.args[0] for call in start_sender.call_args_list],
        )

    def test_private_recovery_auto_start_runs_when_explicitly_enabled(self) -> None:
        with patch.dict(os.environ, {live_dashboard.DASHBOARD_AUTO_START_ENV_VAR: "1"}), patch.object(
            live_dashboard,
            "_load_dashboard_auto_start_state",
            return_value={"private_jc_recovery_last_attempt_utc": ""},
        ), patch.object(
            live_dashboard,
            "provider_pacing_status",
            return_value={"recovery_pending": True, "cooldown_active": False},
        ), patch.object(
            live_dashboard,
            "_profile_runtime_active",
            return_value=False,
        ), patch.object(
            live_dashboard,
            "_retry_due",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "_save_dashboard_auto_start_state",
        ), patch.object(
            live_dashboard,
            "mark_recovery_started",
        ) as mark_recovery_started, patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "Started."),
        ) as start_sender:
            live_dashboard._run_private_jc_recovery_auto_start_once()

        start_sender.assert_called_once_with(live_dashboard.PRIVATE_BOUNCE_PROFILE)
        mark_recovery_started.assert_called_once()

    def test_automation_status_reports_disabled_gate(self) -> None:
        with patch.dict(os.environ, {live_dashboard.DASHBOARD_AUTO_START_ENV_VAR: "0"}), patch.object(
            live_dashboard,
            "load_dashboard_run_settings",
            return_value={
                "auto_start_sendgrid_enabled": True,
                "auto_start_sendgrid_local_time": "18:00",
                "auto_start_private_jc_enabled": True,
                "auto_start_private_jc_local_time": "18:00",
            },
        ), patch.object(
            live_dashboard,
            "_load_dashboard_auto_start_state",
            return_value={},
        ), patch.object(
            live_dashboard,
            "_load_dashboard_timer_state",
            return_value={},
        ), patch.object(
            live_dashboard,
            "provider_pacing_status",
            return_value={},
        ), patch.object(
            live_dashboard,
            "_profile_runtime_active",
            return_value=False,
        ):
            status = live_dashboard._build_automation_status()

        self.assertFalse(status["auto_start_allowed"])
        self.assertIn("DASHBOARD_ALLOW_AUTO_START=1", status["auto_start_note"])

    def test_manual_start_is_allowed_in_local_dev_when_live_actions_explicitly_enabled(self) -> None:
        preconditions = {"ok": True, "blocked": False, "warning_reasons": []}
        with patch.dict(
            os.environ,
            {
                "DASHBOARD_AUTH_DISABLED": "1",
                "LOCAL_DASHBOARD_NO_AUTH": "0",
                "DASHBOARD_ENABLE_LIVE_ACTIONS": "1",
            },
            clear=False,
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": []},
        ), patch.object(
            live_dashboard,
            "_build_start_preconditions_report",
            return_value=preconditions,
        ), patch.object(
            live_dashboard,
            "_start_preconditions_block_response",
            return_value=None,
        ), patch.object(
            live_dashboard,
            "append_campaign_run_history",
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
            return_value=(True, "Started."),
        ) as start_all_senders, patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start()

        self.assertEqual(200, response.status_code)
        self.assertTrue(json.loads(response.body)["ok"])
        start_all_senders.assert_called_once()

    def test_preview_validate_profile_blocks_active_sender(self) -> None:
        with (
            patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True),
            patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[SimpleNamespace(name="sendgrid_annette", runtime_state="running")],
            ),
            patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": []}),
            patch.object(live_dashboard, "append_campaign_run_history"),
        ):
            response = live_dashboard.preview_validate_profile("sendgrid_annette")

        payload = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(payload["ok"])
        self.assertEqual("profile_active", payload["error"])

    def test_preview_validate_profile_returns_validation_failure_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            preview_path = tmp / "private_jc_message_preview.csv"
            validated_path = tmp / "private_jc_message_preview_validated.csv"
            failed_path = tmp / "private_jc_message_preview_failed.csv"
            summary_path = tmp / "private_jc_message_preview_summary.txt"

            def fake_run(command, **kwargs):
                if "send_shard.py" in command:
                    preview_path.write_text(
                        "Email,FirstName,BookTitle,Subject,Body\nreader@example.com,Ava,,Subject,Body\n",
                        encoding="utf-8",
                    )
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                validated_path.write_text("Email\n", encoding="utf-8")
                failed_path.write_text("Email\nreader@example.com\n", encoding="utf-8")
                summary_path.write_text("failed rows: 1\nfailure reasons:\n- missing_book_title: 1\n", encoding="utf-8")
                return SimpleNamespace(returncode=1, stdout="", stderr="")

            with (
                patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True),
                patch.object(live_dashboard, "_active_sender_names", return_value=set()),
                patch.object(live_dashboard, "_find_active_dashboard_job", return_value=None),
                patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": []}),
                patch.object(live_dashboard, "message_preview_path_for_profile", return_value=preview_path),
                patch.object(live_dashboard, "message_preview_output_paths", return_value=(validated_path, failed_path, summary_path)),
                patch.object(live_dashboard, "append_campaign_run_history") as history_mock,
                patch.object(live_dashboard.subprocess, "run", side_effect=fake_run),
            ):
                response = live_dashboard.preview_validate_profile("private_jc")

        payload = json.loads(response.body)
        self.assertTrue(payload["ok"])
        self.assertEqual("FAIL", payload["result"]["validation_status"])
        self.assertEqual(["missing_book_title: 1"], payload["result"]["validation_reasons"])
        self.assertEqual("preview_validate_completed", history_mock.call_args_list[-1].args[0]["event_type"])

    def test_start_all_writes_requested_and_started_history(self) -> None:
        preconditions = {
            "ok": True,
            "blocked": False,
            "profile": "",
            "profiles": ["sendgrid_annette"],
            "queue_safety": {"safe": True},
            "queue_safety_status": "safe",
            "snapshot": {"profiles": [], "queue_safety": {"safe": True}},
        }
        with (
            patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": [], "queue_safety": {"safe": True}}),
            patch.object(live_dashboard, "_build_start_preconditions_report", return_value=preconditions),
            patch.object(live_dashboard.runtime_control, "start_all_senders", return_value=(True, "started")),
            patch.object(live_dashboard, "append_campaign_run_history") as history_mock,
            patch.object(live_dashboard.time, "sleep", return_value=None),
        ):
            response = live_dashboard.start()

        payload = json.loads(response.body)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            ["start_all_requested", "start_all_started"],
            [call.args[0]["event_type"] for call in history_mock.call_args_list],
        )

    def test_start_all_writes_partially_started_history(self) -> None:
        preconditions = {
            "ok": True,
            "blocked": False,
            "profile": "",
            "profiles": ["sendgrid_annette", "sendgrid_fiorela"],
            "queue_safety": {"safe": True},
            "queue_safety_status": "safe",
            "snapshot": {"profiles": [], "queue_safety": {"safe": True}},
        }
        message = "PARTIALLY_STARTED: missing profiles: sendgrid_fiorela. Last preflight output: sendgrid_fiorela: status=OK"
        with (
            patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": [], "queue_safety": {"safe": True}}),
            patch.object(live_dashboard, "_build_start_preconditions_report", return_value=preconditions),
            patch.object(live_dashboard.runtime_control, "start_all_senders", return_value=(False, message)),
            patch.object(live_dashboard, "append_campaign_run_history") as history_mock,
            patch.object(live_dashboard.time, "sleep", return_value=None),
        ):
            response = live_dashboard.start()

        payload = json.loads(response.body)
        self.assertFalse(payload["ok"])
        self.assertEqual("PARTIALLY_STARTED", payload["status"])
        self.assertIn("sendgrid_fiorela", payload["message"])
        self.assertEqual(
            ["start_all_requested", "start_all_partially_started"],
            [call.args[0]["event_type"] for call in history_mock.call_args_list],
        )
        self.assertIn("sendgrid_fiorela", " ".join(history_mock.call_args_list[-1].args[0]["blocked_reasons"]))

    def test_start_profile_blocked_by_queue_safety_writes_history(self) -> None:
        with (
            patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True),
            patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": [], "queue_safety": {"safe": False}}),
            patch.object(live_dashboard, "build_dashboard_queue_safety_report", return_value={"safe": False, "unsafe_reasons": ["mixed_queue"]}),
            patch.object(live_dashboard, "_active_sender_names", return_value=set()),
            patch.object(live_dashboard, "_profile_readiness_from_snapshot", return_value={"status": "PASS", "reasons": []}),
            patch.object(live_dashboard, "_lead_state_start_block_reasons", return_value=[]),
            patch.object(live_dashboard, "append_campaign_run_history") as history_mock,
        ):
            response = live_dashboard.start_profile("sendgrid_annette")

        payload = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(payload["ok"])
        self.assertEqual(
            ["start_profile_requested", "start_profile_blocked"],
            [call.args[0]["event_type"] for call in history_mock.call_args_list],
        )

    def test_resolve_dashboard_csv_path_accepts_absolute_workspace_mnt_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            path = Path(tmpdir) / "checked.csv"

            resolved = live_dashboard._resolve_dashboard_csv_path(str(path), live_dashboard.IMPORTANT_LEADS_OUTPUT)

        self.assertEqual(path.resolve(strict=False), resolved)

    def test_resolve_dashboard_csv_path_blocks_windows_traversal_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir, tempfile.TemporaryDirectory() as outside_dir:
            tmp = Path(tmpdir)
            outside = Path(outside_dir)
            outside_file = outside / "escaped.csv"
            outside_file.write_text("Email\n", encoding="utf-8")

            for raw_path in (
                "C:\\VS\\email automation\\_important\\leads.csv",
                "D:\\VS\\email automation\\_important\\leads.csv",
                str(live_dashboard.settings.APP_ROOT.parent / "outside.csv"),
                str(tmp / ".." / ".." / "outside.csv"),
            ):
                with self.assertRaises(ValueError):
                    live_dashboard._resolve_dashboard_csv_path(raw_path, live_dashboard.IMPORTANT_LEADS_OUTPUT)

            link = tmp / "outside_link.csv"
            os.symlink(outside_file, link)
            with self.assertRaises(ValueError):
                live_dashboard._resolve_dashboard_csv_path(str(link), live_dashboard.IMPORTANT_LEADS_OUTPUT)

            linked_dir = tmp / "outside_dir"
            os.symlink(outside, linked_dir)
            with self.assertRaises(ValueError):
                live_dashboard._resolve_dashboard_csv_path(str(linked_dir / "nested.csv"), live_dashboard.IMPORTANT_LEADS_OUTPUT)

    def test_leads_pipeline_status_summarizes_next_step_and_counts(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            cleaned = tmp / "leads.csv"
            triaged = tmp / "leads_triaged_keep.csv"
            quarantine = tmp / "leads_triaged_quarantine.csv"
            cleaned.write_text("Email,FirstName\none@example.com,One\n", encoding="utf-8")
            triaged.write_text("Email,FirstName\none@example.com,One\n", encoding="utf-8")
            quarantine.write_text("Email,FirstName,Status\nhold@example.com,Hold,QUARANTINE\n", encoding="utf-8")

            status = {
                "important_output_label": str(cleaned),
                "important_triage_keep_label": str(triaged),
                "important_triage_quarantine_label": str(quarantine),
                "dispatch_source": {"dispatch_eligible_row_count": 1},
            }

            pipeline = live_dashboard._build_leads_pipeline_status(status)

        self.assertEqual(1, pipeline["checked_rows"])
        self.assertEqual(1, pipeline["triaged_keep_rows"])
        self.assertEqual(1, pipeline["quarantine_rows"])
        self.assertEqual("quarantine", pipeline["next_step"])
        review_step = next(step for step in pipeline["steps"] if step["key"] == "quarantine")
        self.assertEqual("warn", review_step["state"])

    def test_lead_funnel_summary_calculates_current_live_counts(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            raw = tmp / "leadschecker.csv"
            checked = tmp / "leads.csv"
            rejected = tmp / "leads_rejected.csv"
            keep = tmp / "leads_triaged_keep.csv"
            triage_reject = tmp / "leads_triaged_reject.csv"
            quarantine = tmp / "leads_triaged_quarantine.csv"
            self._write_csv(raw, ["Email"], [{"Email": f"raw{i}@example.test"} for i in range(10)])
            self._write_csv(checked, ["Email"], [{"Email": f"clean{i}@example.test"} for i in range(8)])
            self._write_csv(rejected, ["Email"], [{"Email": f"reject{i}@example.test"} for i in range(2)])
            self._write_csv(keep, ["Email"], [{"Email": f"keep{i}@example.test"} for i in range(5)])
            self._write_csv(triage_reject, ["Email"], [{"Email": f"triage-reject{i}@example.test"} for i in range(2)])
            self._write_csv(quarantine, ["Email"], [{"Email": "hold@example.test"}])

            with patch.object(live_dashboard, "IMPORTANT_LEADS_INPUT", raw), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_OUTPUT",
                checked,
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_REJECTED", rejected), patch.object(
                live_dashboard,
                "TRIAGED_KEEP_PATH",
                keep,
            ), patch.object(live_dashboard, "_latest_important_check_job", return_value=None):
                summary = live_dashboard._build_lead_funnel_summary({})

        current = summary["current_live"]
        self.assertEqual(10, current["raw_input"]["row_count"])
        self.assertEqual(8, current["cleaned_after_check"]["row_count"])
        self.assertEqual(5, current["triage_keep"]["row_count"])
        self.assertEqual(5, current["total_removed_excluded"]["row_count"])
        self.assertEqual(50.0, current["pass_through_rate"]["value"])

    def test_lead_funnel_summary_marks_missing_staged_stage_pending(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            staged = tmp / "runs" / "check_next"
            checked = staged / "leads.csv"
            rejected = staged / "leads_rejected.csv"
            self._write_csv(checked, ["Email"], [{"Email": "one@example.test"}])
            self._write_csv(rejected, ["Email"], [])
            job = {
                "job_id": "check_next",
                "staged_run_dir": str(staged),
                "total_input_rows": 2,
                "output_path": str(checked),
                "rejected_path": str(rejected),
            }

            with patch.object(live_dashboard, "_latest_important_check_job", return_value=job):
                summary = live_dashboard._build_lead_funnel_summary({})

        next_batch = summary["next_batch"]
        self.assertEqual(2, next_batch["raw_input"]["row_count"])
        self.assertEqual(1, next_batch["cleaned_after_check"]["row_count"])
        self.assertEqual("pending", next_batch["triage_keep"]["status"])
        self.assertEqual("pending", next_batch["final_eligible"]["status"])

    def test_lead_funnel_summary_keeps_staged_counts_separate_from_current_live(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            live_raw = tmp / "live" / "leadschecker.csv"
            live_checked = tmp / "live" / "leads.csv"
            live_rejected = tmp / "live" / "leads_rejected.csv"
            live_keep = tmp / "live" / "leads_triaged_keep.csv"
            staged = tmp / "runs" / "check_staged"
            staged_checked = staged / "leads.csv"
            staged_rejected = staged / "leads_rejected.csv"
            staged_keep = staged / "leads_triaged_keep.csv"
            self._write_csv(live_raw, ["Email"], [{"Email": f"live-raw{i}@example.test"} for i in range(4)])
            self._write_csv(live_checked, ["Email"], [{"Email": f"live-clean{i}@example.test"} for i in range(3)])
            self._write_csv(live_rejected, ["Email"], [{"Email": "live-reject@example.test"}])
            self._write_csv(live_keep, ["Email"], [{"Email": f"live-keep{i}@example.test"} for i in range(2)])
            self._write_csv(staged_checked, ["Email"], [{"Email": f"stage-clean{i}@example.test"} for i in range(5)])
            self._write_csv(staged_rejected, ["Email"], [{"Email": "stage-reject@example.test"}])
            self._write_csv(staged_keep, ["Email"], [{"Email": f"stage-keep{i}@example.test"} for i in range(3)])
            job = {
                "job_id": "check_staged",
                "staged_run_dir": str(staged),
                "total_input_rows": 6,
                "output_path": str(staged_checked),
                "rejected_path": str(staged_rejected),
                "auto_triage_keep_path": str(staged_keep),
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_INPUT", live_raw), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_OUTPUT",
                live_checked,
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_REJECTED", live_rejected), patch.object(
                live_dashboard,
                "TRIAGED_KEEP_PATH",
                live_keep,
            ), patch.object(live_dashboard, "_latest_important_check_job", return_value=job):
                summary = live_dashboard._build_lead_funnel_summary({})

        self.assertEqual(2, summary["current_live"]["final_eligible"]["row_count"])
        self.assertEqual(3, summary["next_batch"]["final_eligible"]["row_count"])
        self.assertEqual(50.0, summary["current_live"]["pass_through_rate"]["value"])
        self.assertEqual(50.0, summary["next_batch"]["pass_through_rate"]["value"])

    def test_check_leads_running_is_next_batch_status_not_current_send_blocker(self) -> None:
        status = {
            "active_important_check_job": {
                "job_id": "check_next_batch",
                "status": "running",
                "stage": "checking",
                "processed_rows": 10,
                "total_input_rows": 100,
            },
            "latest_master_check": {},
            "latest_lead_triage": {},
            "latest_auto_dispatch_preview": {},
            "pipeline": {},
            "sendgrid_queues": [
                {"profile": "sendgrid_1", "fieldnames": ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]},
            ],
        }
        with patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value={"safe": True, "unsafe_reasons": []},
        ):
            current = live_dashboard._build_current_send_safety_status(status)
            prep = live_dashboard._build_next_batch_prep_status(status)

        self.assertEqual("READY", current["status"])
        self.assertFalse(current["blocked"])
        self.assertEqual("WAIT", prep["status"])
        self.assertFalse(prep["blocks_current_send"])
        self.assertIn("Check Leads is running", " ".join(prep["reasons"]))

    def test_start_all_blocks_when_queue_safety_is_unsafe(self) -> None:
        unsafe_report = {
            "safe": False,
            "unsafe_reasons": ["overlap_with_triaged_reject", "outside_intended_source"],
            "message": "Synthetic unsafe queue.",
        }

        with patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=unsafe_report,
        ), patch.object(
            live_dashboard,
            "SENDGRID_PROFILES",
            ["sendgrid_annette"],
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"queue_safety": unsafe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
        ) as start_all_senders:
            response = live_dashboard.start()

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertFalse(body["ok"])
        self.assertTrue(body["blocked"])
        self.assertEqual("queue_safety_unsafe", body["error"])
        self.assertEqual("unsafe", body["safety_status"])
        self.assertEqual(unsafe_report["unsafe_reasons"], body["reasons"])
        self.assertIn("rebuild queues", body["suggested_fix"])
        start_all_senders.assert_not_called()

    def test_start_profile_blocks_when_queue_safety_is_unsafe(self) -> None:
        unsafe_report = {
            "safe": False,
            "unsafe_reasons": ["QUEUE_SAFETY_CHECK_FAILED"],
            "message": "Synthetic queue safety failure.",
        }

        with patch.object(
            live_dashboard.runtime_control,
            "is_known_profile",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=unsafe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"queue_safety": unsafe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
        ) as start_sender:
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertFalse(body["ok"])
        self.assertEqual("sendgrid_annette", body["profile"])
        self.assertEqual("queue_safety_unsafe", body["error"])
        start_sender.assert_not_called()

    def test_private_queue_unsafe_does_not_block_sendgrid_profile_start(self) -> None:
        reports = {
            "sendgrid": {"safe": True, "unsafe_reasons": [], "affected_provider": "sendgrid"},
            "private_jc": {"safe": False, "unsafe_reasons": ["OUTSIDE_INTENDED_SOURCE"], "affected_provider": "private_jc"},
            "all": {"safe": False, "unsafe_reasons": ["OUTSIDE_INTENDED_SOURCE"], "affected_provider": "all"},
        }

        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            side_effect=lambda provider="all": reports[str(provider or "all")],
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": []},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "started"),
        ) as start_sender, patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertEqual("sendgrid", body["preconditions"]["queue_safety_provider"])
        start_sender.assert_called_once_with("sendgrid_annette")

    def test_sendgrid_queue_unsafe_blocks_sendgrid_profile_start(self) -> None:
        reports = {
            "sendgrid": {"safe": False, "unsafe_reasons": ["OUTSIDE_CHECKED_OUTPUT"], "affected_provider": "sendgrid"},
            "all": {"safe": False, "unsafe_reasons": ["OUTSIDE_CHECKED_OUTPUT"], "affected_provider": "all"},
        }

        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            side_effect=lambda provider="all": reports.get(str(provider or "all"), reports["all"]),
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": []},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
        ) as start_sender:
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertEqual("sendgrid", body["queue_safety"]["affected_provider"])
        start_sender.assert_not_called()

    def test_private_queue_unsafe_blocks_private_profile_start(self) -> None:
        reports = {
            "private_jc": {"safe": False, "unsafe_reasons": ["OUTSIDE_INTENDED_SOURCE"], "affected_provider": "private_jc"},
            "all": {"safe": False, "unsafe_reasons": ["OUTSIDE_INTENDED_SOURCE"], "affected_provider": "all"},
        }

        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            side_effect=lambda provider="all": reports.get(str(provider or "all"), reports["all"]),
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": []},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
        ) as start_sender:
            response = live_dashboard.start_profile("private_jc")

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertEqual("private_jc", body["queue_safety"]["affected_provider"])
        start_sender.assert_not_called()

    def test_private_provider_blocker_blocks_private_profile_start(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": [], "affected_provider": "private_jc"}
        snapshot = {
            "profiles": [
                {
                    "name": "private_jc",
                    "readiness_label": "Blocked",
                    "readiness_tone": "bad",
                    "reason_code": "BOUNCE_SYNC_ERROR",
                    "reason_note": "Private bounce sync failed.",
                    "message_readiness": {"status": "PASS", "reasons": []},
                }
            ]
        }

        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value=snapshot,
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
        ) as start_sender:
            response = live_dashboard.start_profile("private_jc")

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertEqual("start_preconditions_failed", body["error"])
        self.assertIn("BOUNCE_SYNC_ERROR", " ".join(body["blocked_reasons"]))
        start_sender.assert_not_called()

    def test_private_provider_blocker_does_not_block_sendgrid_profile_start(self) -> None:
        reports = {
            "sendgrid": {"safe": True, "unsafe_reasons": [], "affected_provider": "sendgrid"},
            "private_jc": {"safe": True, "unsafe_reasons": [], "affected_provider": "private_jc"},
            "all": {"safe": True, "unsafe_reasons": [], "affected_provider": "all"},
        }
        snapshot = {
            "profiles": [
                {
                    "name": "private_jc",
                    "readiness_label": "Blocked",
                    "readiness_tone": "bad",
                    "reason_code": "BOUNCE_SYNC_ERROR",
                    "reason_note": "Private bounce sync failed.",
                    "message_readiness": {"status": "PASS", "reasons": []},
                },
                {
                    "name": "sendgrid_annette",
                    "readiness_label": "Ready",
                    "readiness_tone": "good",
                    "message_readiness": {"status": "PASS", "reasons": []},
                },
            ]
        }

        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            side_effect=lambda provider="all": reports[str(provider or "all")],
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value=snapshot,
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "started"),
        ) as start_sender, patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertEqual("sendgrid", body["preconditions"]["queue_safety_provider"])
        start_sender.assert_called_once_with("sendgrid_annette")

    def test_start_profile_allows_safe_queue_and_calls_runtime_start(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}

        with patch.object(
            live_dashboard.runtime_control,
            "is_known_profile",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "Started sendgrid_annette."),
        ) as start_sender, patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"queue_safety": safe_report},
        ), patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertEqual("Started sendgrid_annette.", body["message"])
        start_sender.assert_called_once_with("sendgrid_annette")

    def test_start_all_blocks_when_any_sender_is_active(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}

        with patch.object(
            live_dashboard,
            "SENDGRID_PROFILES",
            ["sendgrid_annette"],
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value={"sendgrid_jordan"},
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
        ) as start_all_senders:
            response = live_dashboard.start()

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertEqual("start_preconditions_failed", body["error"])
        self.assertIn("sendgrid_jordan", " ".join(body["blocked_reasons"]))
        start_all_senders.assert_not_called()

    def test_start_all_blocks_when_preview_process_is_active(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}

        with patch.object(
            live_dashboard,
            "SENDGRID_PROFILES",
            ["sendgrid_annette", "sendgrid_jordan"],
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value={"sendgrid_jordan"},
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
        ) as start_all_senders:
            response = live_dashboard.start()

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertIn("Preview validation", " ".join(body["blocked_reasons"]))
        self.assertIn("sendgrid_jordan", " ".join(body["blocked_reasons"]))
        start_all_senders.assert_not_called()

    def test_start_all_excludes_private_jc_and_warns_for_not_run_readiness(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}
        checked_profiles: list[str] = []

        def fake_readiness(snapshot, profile):
            checked_profiles.append(profile)
            return {"status": "NOT RUN", "reasons": ["synthetic not run"]}

        with patch.object(
            live_dashboard,
            "SENDGRID_PROFILES",
            ["sendgrid_annette", "sendgrid_jordan"],
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            side_effect=fake_readiness,
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
            return_value=(True, "started"),
        ) as start_all_senders, patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start()

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertEqual(["sendgrid_annette", "sendgrid_jordan"], checked_profiles)
        self.assertNotIn("private_jc", json.dumps(body))
        self.assertIn("NOT RUN", " ".join(body["warnings"]))
        start_all_senders.assert_called_once()

    def test_start_all_blocks_failed_message_readiness(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}

        with patch.object(
            live_dashboard,
            "SENDGRID_PROFILES",
            ["sendgrid_annette"],
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "FAIL", "reasons": ["synthetic fail"]},
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
        ) as start_all_senders:
            response = live_dashboard.start()

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertIn("FAIL", " ".join(body["blocked_reasons"]))
        start_all_senders.assert_not_called()

    def test_start_profile_treats_not_run_and_stale_readiness_as_warnings(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}
        for status in ("NOT RUN", "STALE"):
            with self.subTest(status=status), patch.object(
                live_dashboard.runtime_control,
                "is_known_profile",
                return_value=True,
            ), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value=safe_report,
            ), patch.object(
                live_dashboard,
                "_active_sender_names",
                return_value=set(),
            ), patch.object(
                live_dashboard,
                "_active_preview_names",
                return_value=set(),
            ), patch.object(
                live_dashboard,
                "_profile_readiness_from_snapshot",
                return_value={"status": status, "reasons": [f"synthetic {status.lower()}"]},
            ), patch.object(
                live_dashboard,
                "_lead_state_start_block_reasons",
                return_value=[],
            ), patch.object(
                live_dashboard,
                "_build_live_snapshot",
                return_value={"profiles": [], "queue_safety": safe_report},
            ), patch.object(
                live_dashboard.runtime_control,
                "start_sender",
                return_value=(True, "Started sendgrid_annette."),
            ) as start_sender, patch.object(live_dashboard.time, "sleep"):
                response = live_dashboard.start_profile("sendgrid_annette")

            self.assertEqual(200, response.status_code)
            body = json.loads(response.body)
            self.assertTrue(body["ok"])
            self.assertIn(status, " ".join(body["warnings"]))
            start_sender.assert_called_once_with("sendgrid_annette")

    def test_start_profile_blocks_when_message_readiness_fails(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}
        with patch.object(
            live_dashboard.runtime_control,
            "is_known_profile",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_active_preview_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "FAIL", "reasons": ["synthetic fail"]},
        ), patch.object(
            live_dashboard,
            "_lead_state_start_block_reasons",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
        ) as start_sender:
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertEqual("start_preconditions_failed", body["error"])
        self.assertEqual("FAIL", body["message_readiness_status"])
        self.assertIn("FAIL", " ".join(body["blocked_reasons"]))
        start_sender.assert_not_called()

    def test_start_profile_warns_but_does_not_block_stale_next_batch_state(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}
        temp_path = live_dashboard.settings.APP_ROOT / "tmp_synthetic_run" / "_important" / "leads.csv"
        status = {
            "active_important_check_job": None,
            "latest_master_check": {"output_label": str(temp_path), "rejected_label": ""},
            "latest_lead_triage": {},
            "latest_auto_dispatch_preview": {},
        }

        with patch.object(
            live_dashboard.runtime_control,
            "is_known_profile",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_combined_leads_status",
            return_value=status,
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "started"),
        ) as start_sender:
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertIn("temp artifact", " ".join(body["warnings"]))
        start_sender.assert_called_once_with("sendgrid_annette")

    def test_start_all_does_not_block_on_stale_lead_state_when_queue_and_readiness_pass(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}
        temp_path = live_dashboard.settings.APP_ROOT / "tmp_synthetic_run" / "_important" / "leads.csv"
        status = {
            "active_important_check_job": None,
            "latest_master_check": {"output_label": str(temp_path), "rejected_label": ""},
            "latest_lead_triage": {
                "verified_label": str(temp_path.with_name("leads_triaged_keep.csv")),
                "rejected_label": str(temp_path.with_name("leads_triaged_reject.csv")),
            },
            "latest_auto_dispatch_preview": {},
        }

        with patch.object(
            live_dashboard,
            "SENDGRID_PROFILES",
            ["sendgrid_annette"],
        ), patch.object(
            live_dashboard,
            "build_dashboard_queue_safety_report",
            return_value=safe_report,
        ), patch.object(
            live_dashboard,
            "_active_sender_names",
            return_value=set(),
        ), patch.object(
            live_dashboard,
            "_profile_readiness_from_snapshot",
            return_value={"status": "PASS", "reasons": []},
        ), patch.object(
            live_dashboard,
            "_combined_leads_status",
            return_value=status,
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": [], "queue_safety": safe_report},
        ), patch.object(
            live_dashboard.runtime_control,
            "start_all_senders",
            return_value=(True, "started"),
        ) as start_all_senders, patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start()

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        self.assertNotIn("leads.csv", " ".join(body.get("blocked_reasons", [])))
        start_all_senders.assert_called_once()

    def test_start_profile_does_not_block_missing_live_important_files_after_dispatch_cleanup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="synthetic_dispatch_cleanup_", dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            archived = tmp / "data" / "state" / "backups" / "staged_batches" / "dispatch_clean"
            archived.mkdir(parents=True)
            checked = archived / "leads.csv"
            keep = archived / "leads_triaged_keep.csv"
            reject = archived / "leads_triaged_reject.csv"
            checked.write_text("Email,FirstName\nreader@example.test,Ava\n", encoding="utf-8")
            keep.write_text("Email,FirstName\nreader@example.test,Ava\n", encoding="utf-8")
            reject.write_text("Email,FirstName\n", encoding="utf-8")
            missing = tmp / "tmp_stale_after_dispatch_cleanup" / "_important"
            status = {
                "active_important_check_job": None,
                "latest_master_check": {
                    "output_label": str(missing / "leads.csv"),
                    "rejected_label": str(missing / "leads_rejected.csv"),
                },
                "latest_lead_triage": {
                    "verified_label": str(missing / "leads_triaged_keep.csv"),
                    "rejected_label": str(missing / "leads_triaged_reject.csv"),
                },
                "latest_auto_dispatch_preview": {},
            }
            safe_report = {
                "safe": True,
                "unsafe_reasons": [],
                "source_resolution": "latest_queue_rebuild_archived_dispatch_state",
                "intended_source_path": str(keep),
                "checked_path": str(checked),
                "triaged_keep_path": str(keep),
                "triaged_reject_path": str(reject),
                "outside_checked_output_count": 0,
                "outside_intended_source_count": 0,
                "overlap_with_triaged_reject": 0,
            }

            with patch.object(
                live_dashboard.runtime_control,
                "is_known_profile",
                return_value=True,
            ), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value=safe_report,
            ), patch.object(
                live_dashboard,
                "_active_sender_names",
                return_value=set(),
            ), patch.object(
                live_dashboard,
                "_profile_readiness_from_snapshot",
                return_value={"status": "PASS", "reasons": []},
            ), patch.object(
                live_dashboard,
                "_combined_leads_status",
                return_value=status,
            ), patch.object(
                live_dashboard,
                "_build_live_snapshot",
                return_value={"profiles": [], "queue_safety": safe_report},
            ), patch.object(
                live_dashboard.runtime_control,
                "start_sender",
                return_value=(True, "Started sendgrid_annette."),
            ) as start_sender, patch.object(live_dashboard.time, "sleep"):
                response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(200, response.status_code)
        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        start_sender.assert_called_once_with("sendgrid_annette")

    def test_upload_check_large_author_csv_writes_fresh_outputs_and_counts(self) -> None:
        valid_rows = 1005
        declared_upload_size = 87 * 1024 * 1024
        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["AuthorName", "AuthorEmail", "BookTitle", "PersonalizedOpeningLine"])
        for index in range(valid_rows):
            writer.writerow([
                f"Author {index}",
                f"synthetic-author-{index}@example.com",
                f"Book {index}",
                f"Opening line {index}",
            ])
        writer.writerow(["Duplicate", "synthetic-author-10@example.com", "Duplicate Book", "Duplicate line"])
        writer.writerow(["Invalid", "not-an-email", "Invalid Book", "Invalid line"])
        writer.writerow(["Missing", "", "Missing Book", "Missing line"])
        content = buffer.getvalue().encode("utf-8")

        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            check_runs_dir = tmp / "check_runs"
            jobs_dir = tmp / "jobs"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            suppressed_path.write_text("Email\n", encoding="utf-8")
            unsubscribed_path.write_text("Email\n", encoding="utf-8")
            sendgrid_suppressions_path.write_text("email,state,type\n", encoding="utf-8")

            def check_master_leads_without_external_state(**kwargs):
                return important_leads_workflow.check_master_leads(
                    **kwargs,
                    sendgrid_suppressions_path=sendgrid_suppressions_path,
                    suppressed_path=suppressed_path,
                    unsubscribed_path=unsubscribed_path,
                    report_dir=tmp / "state",
                    summary_dir=tmp / "check_summaries",
                    validate_deliverability=False,
                    reject_role_accounts=False,
                    reject_disposable=False,
                    persist_state=False,
                )

            def start_check_job_without_thread(**kwargs):
                job_id = "check_20260512_010203_synthetic"
                job = {
                    "job_id": job_id,
                    "status": "queued",
                    "stage": "queued",
                    "created_at_utc": "2026-05-12T01:02:03+00:00",
                    "updated_at_utc": "2026-05-12T01:02:03+00:00",
                    "source_label": kwargs["source_label"],
                    "source_mode": kwargs["source_mode"],
                    "original_uploaded_filename": kwargs["original_uploaded_filename"],
                    "server_received_filename": kwargs["server_received_filename"],
                    "selected_filename": kwargs["selected_filename"],
                    "selected_size_bytes": kwargs["selected_size_bytes"],
                    "selected_extension": kwargs["selected_extension"],
                    "source_sheet": kwargs["source_sheet"],
                    "input_path": str(kwargs["input_path"]),
                    "saved_input_path": str(kwargs["effective_input_path"]),
                    "output_path": str(kwargs["output_path"]),
                    "rejected_path": str(kwargs["rejected_path"]),
                    "effective_input_path": str(kwargs["effective_input_path"]),
                    "total_input_rows": int(kwargs["total_input_rows"] or 0),
                    "processed_rows": 0,
                    "remaining_rows": int(kwargs["total_input_rows"] or 0),
                    "eta_seconds": "",
                    "progress_percent": 0,
                }
                live_dashboard._save_important_check_job(job)
                return job

            upload = live_dashboard.UploadFile(
                filename="lead_op_author_personalized_upload.csv",
                file=BytesIO(content),
            )
            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_RUNS", check_runs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_JOBS",
                jobs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260512_010203",
            ), patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                side_effect=check_master_leads_without_external_state,
            ), patch.object(
                live_dashboard,
                "_start_important_check_job",
                side_effect=start_check_job_without_thread,
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}):
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="lead_op_author_personalized_upload.csv",
                        client_selected_size_bytes=str(declared_upload_size),
                        client_selected_extension=".csv",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )
                body = json.loads(response.body)
                live_dashboard._run_important_check_job(body["job"]["job_id"])

            self.assertEqual(202, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual("lead_op_author_personalized_upload.csv", body["server_received_filename"])
            self.assertEqual(declared_upload_size, body["selected_size_bytes"])
            self.assertEqual(declared_upload_size, body["job"]["selected_size_bytes"])
            self.assertEqual(valid_rows + 3, body["job"]["total_input_rows"])

            saved_job = json.loads((jobs_dir / f"{body['job']['job_id']}.json").read_text(encoding="utf-8"))
            report = saved_job["check"]
            self.assertEqual("completed", saved_job["status"])
            self.assertEqual(valid_rows, report["cleaned_rows"])
            self.assertEqual(3, report["rejected_rows"])
            self.assertEqual(1, report["reason_counts"]["DUPLICATE_IN_BATCH"])
            self.assertEqual(1, report["reason_counts"]["INVALID_EMAIL_SYNTAX"])
            self.assertEqual(1, report["reason_counts"]["MISSING_EMAIL"])
            self.assertEqual(str(output_path), saved_job["output_path"])
            self.assertEqual(str(rejected_path), saved_job["rejected_path"])
            self.assertEqual(valid_rows, live_dashboard._count_csv_rows(output_path))
            self.assertEqual(3, live_dashboard._count_csv_rows(rejected_path))
            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                output_reader = csv.DictReader(handle)
                output_rows = list(output_reader)
            self.assertIn("BookTitle", output_reader.fieldnames or [])
            self.assertIn("AuthorName", output_reader.fieldnames or [])
            self.assertIn("PersonalizedOpeningLine", output_reader.fieldnames or [])
            self.assertEqual(valid_rows, len(output_rows))
            self.assertEqual("Book 0", output_rows[0]["BookTitle"])
            self.assertEqual("Author 0", output_rows[0]["AuthorName"])
            with rejected_path.open(newline="", encoding="utf-8-sig") as handle:
                rejected_reader = csv.DictReader(handle)
                rejected_rows = list(rejected_reader)
            self.assertIn("BookTitle", rejected_reader.fieldnames or [])
            rejected_titles = {row["BookTitle"] for row in rejected_rows}
            self.assertIn("Invalid Book", rejected_titles)
            self.assertIn("Missing Book", rejected_titles)

            pipeline = live_dashboard._build_leads_pipeline_status(
                {
                    "important_output_label": str(output_path),
                    "important_triage_keep_label": str(tmp / "missing_triaged_keep.csv"),
                    "important_triage_quarantine_label": str(tmp / "missing_quarantine.csv"),
                    "latest_master_check": {
                        "generated_at_utc": "2026-05-12T00:00:00+00:00",
                        "cleaned_rows": 1,
                    },
                    "dispatch_source": {"dispatch_eligible_row_count": valid_rows},
                }
            )
            self.assertEqual(valid_rows, pipeline["checked_rows"])
            self.assertEqual(valid_rows, pipeline["steps"][0]["count"])
            self.assertEqual(valid_rows, pipeline["dispatch_eligible_rows"])

            jc_queue = tmp / "recipients_private_jc.csv"
            sendgrid_queues = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            jc_log = tmp / "private_jc_log.csv"
            sendgrid_logs = [tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]
            jc_queue.write_text("Email,FirstName\n", encoding="utf-8")
            jc_log.write_text("Email,Status\n", encoding="utf-8")
            for path in sendgrid_queues:
                path.write_text("Email,FirstName\n", encoding="utf-8")
            for path in sendgrid_logs:
                path.write_text("Email,Status\n", encoding="utf-8")

            preview = important_leads_workflow.preview_dispatch_master_leads(
                master_path=output_path,
                rejected_path=rejected_path,
                dispatch_source_mode=important_leads_workflow.DISPATCH_SOURCE_CLEANED,
                dispatch_cap="all",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sendgrid_queues,
                jc_log_path=jc_log,
                sendgrid_log_paths=sendgrid_logs,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=tmp / "dispatch_previews",
            )
            self.assertEqual(valid_rows, preview["dispatch_source_row_count"])
            self.assertEqual(valid_rows, preview["dispatch_eligible_row_count"])

    def test_uploaded_check_job_writes_staged_outputs_without_overwriting_live_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            important_dir = tmp / "_important"
            runs_dir = important_dir / "runs"
            check_runs_dir = important_dir / "check_runs"
            jobs_dir = check_runs_dir / "jobs"
            live_output = important_dir / "leads.csv"
            live_rejected = important_dir / "leads_rejected.csv"
            input_path = check_runs_dir / "uploaded.csv"
            self._write_csv(
                input_path,
                ["Email", "FirstName", "BookTitle"],
                [{"Email": "reader@example.com", "FirstName": "Ava", "BookTitle": "Synthetic Book"}],
            )
            live_output.parent.mkdir(parents=True, exist_ok=True)
            live_output.write_text("Email,FirstName\nexisting@example.com,Existing\n", encoding="utf-8")
            live_rejected.write_text("Email,FirstName\n", encoding="utf-8")
            live_output_before = live_output.read_text(encoding="utf-8")
            live_rejected_before = live_rejected.read_text(encoding="utf-8")

            class NoopThread:
                def __init__(self, *args, **kwargs):
                    pass

                def start(self):
                    return None

            def check_master_leads_without_external_state(**kwargs):
                return important_leads_workflow.check_master_leads(
                    **kwargs,
                    sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                    suppressed_path=tmp / "suppressed.csv",
                    unsubscribed_path=tmp / "unsubscribed.csv",
                    report_dir=tmp / "state",
                    summary_dir=check_runs_dir,
                    validate_deliverability=False,
                    reject_role_accounts=False,
                    reject_disposable=False,
                    persist_state=False,
                )

            (tmp / "sendgrid_suppressions.csv").write_text("email,state,type\n", encoding="utf-8")
            (tmp / "suppressed.csv").write_text("Email\n", encoding="utf-8")
            (tmp / "unsubscribed.csv").write_text("Email\n", encoding="utf-8")

            with patch.object(live_dashboard, "IMPORTANT_LEADS_RUNS", runs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_JOBS",
                jobs_dir,
            ), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_OUTPUT",
                live_output,
            ), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_REJECTED",
                live_rejected,
            ), patch.object(
                live_dashboard.threading,
                "Thread",
                NoopThread,
            ), patch.object(
                live_dashboard,
                "check_master_leads",
                side_effect=check_master_leads_without_external_state,
            ), patch.object(
                live_dashboard,
                "_run_auto_fast_triage_after_check",
                side_effect=lambda job: job,
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[SimpleNamespace(name="sendgrid_annette", runtime_state="running")],
            ):
                job = live_dashboard._start_important_check_job(
                    input_path=input_path,
                    output_path=live_output,
                    rejected_path=live_rejected,
                    effective_input_path=input_path,
                    source_label="uploaded.csv",
                    source_mode="uploaded_file",
                    total_input_rows=1,
                )
                live_dashboard._run_important_check_job(job["job_id"])

            saved_job = json.loads((jobs_dir / f"{job['job_id']}.json").read_text(encoding="utf-8"))
            staged_output = Path(saved_job["output_path"])
            staged_rejected = Path(saved_job["rejected_path"])
            self.assertEqual(runs_dir / job["job_id"] / "leads.csv", staged_output)
            self.assertEqual(runs_dir / job["job_id"] / "leads_rejected.csv", staged_rejected)
            self.assertEqual(1, live_dashboard._count_csv_rows(staged_output))
            self.assertEqual(live_output_before, live_output.read_text(encoding="utf-8"))
            self.assertEqual(live_rejected_before, live_rejected.read_text(encoding="utf-8"))

    def test_warm_upload_job_writes_split_outputs_without_entering_cold_pipeline(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            runs_dir = tmp / "_important" / "runs"
            jobs_dir = tmp / "_important" / "check_runs" / "jobs"
            input_path = tmp / "warm.csv"
            input_path.write_text("AuthorName,BookTitleOrProject,NeedSignal,SourcePlatform,SourceURL,ContactPath,RecommendedService,OutreachAngle,Status\n", encoding="utf-8")

            class NoopThread:
                def __init__(self, *args, **kwargs):
                    pass

                def start(self):
                    return None

            def fake_warm_check(**kwargs):
                Path(kwargs["email_ready_path"]).write_text("AuthorName,AuthorEmail\n", encoding="utf-8")
                Path(kwargs["contact_form_review_path"]).write_text("AuthorName,ContactMethod\n", encoding="utf-8")
                Path(kwargs["rejected_path"]).write_text("AuthorName,reject_code\n", encoding="utf-8")
                return {
                    "upload_type": "warm_research",
                    "generated_at_utc": "2026-06-28T00:00:00+00:00",
                    "input_label": "warm.csv",
                    "input_rows": 0,
                    "total_input_rows": 0,
                    "warm_email_ready_rows": 0,
                    "warm_contact_form_rows": 0,
                    "warm_rejected_rows": 0,
                    "already_contacted_rows": 0,
                    "reason_counts": {},
                    "dispatch_enabled": False,
                }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_RUNS", runs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_JOBS",
                jobs_dir,
            ), patch.object(
                live_dashboard.threading,
                "Thread",
                NoopThread,
            ), patch.object(
                live_dashboard,
                "check_warm_research_leads",
                side_effect=fake_warm_check,
            ), patch.object(
                live_dashboard,
                "_run_auto_fast_triage_after_check",
            ) as auto_triage:
                job = live_dashboard._start_important_check_job(
                    input_path=input_path,
                    output_path=tmp / "cold_leads.csv",
                    rejected_path=tmp / "cold_rejected.csv",
                    effective_input_path=input_path,
                    source_label="warm.csv",
                    source_mode="uploaded_file",
                    upload_type="warm_research",
                )
                live_dashboard._run_important_check_job(job["job_id"])

                saved = json.loads((jobs_dir / f"{job['job_id']}.json").read_text(encoding="utf-8"))
                self.assertEqual("completed", saved["status"])
                self.assertEqual("warm_research", saved["upload_type"])
                self.assertEqual("warm_email_ready.csv", Path(saved["output_path"]).name)
                self.assertEqual("warm_contact_form_review.csv", Path(saved["contact_form_review_path"]).name)
                self.assertEqual("warm_rejected.csv", Path(saved["rejected_path"]).name)
                self.assertEqual("warm_research_upload", saved["auto_triage_skip_reason"])
                self.assertFalse(saved["check"]["dispatch_enabled"])
                self.assertIsNone(live_dashboard._latest_completed_important_check_job())
                self.assertEqual(job["job_id"], live_dashboard._latest_completed_warm_check_job()["job_id"])
                auto_triage.assert_not_called()

    def test_warm_preview_endpoint_writes_preview_csv_without_dispatch_queues(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "jobs"
            run_dir = tmp / "runs" / "check_warm"
            ready_path = run_dir / "warm_email_ready.csv"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            run_dir.mkdir(parents=True, exist_ok=True)
            self._write_csv(
                ready_path,
                list(important_leads_workflow.WARM_EMAIL_READY_HEADERS),
                [{
                    "AuthorName": "Synthetic Author",
                    "AuthorEmail": "author@example.com",
                    "BookTitleOrProject": "Synthetic Project",
                    "NeedSignal": "Synthetic need",
                    "SourcePlatform": "Synthetic platform",
                    "SourceURL": "https://example.test/source",
                    "ContactPath": "author@example.com",
                    "RecommendedService": "a launch page",
                    "OutreachAngle": "A clear project story.",
                    "ResearchStatus": "New",
                    "ContactMethod": "email",
                }],
            )
            job = {
                "job_id": "check_warm",
                "status": "completed",
                "created_at_utc": "2026-06-28T00:00:00+00:00",
                "upload_type": "warm_research",
                "output_path": str(ready_path),
                "staged_run_dir": str(run_dir),
                "check": {
                    "upload_type": "warm_research",
                    "generated_at_utc": "2026-06-28T00:00:00+00:00",
                    "warm_email_ready_rows": 1,
                },
            }
            (jobs_dir / "check_warm.json").write_text(json.dumps(job), encoding="utf-8")

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "_combined_leads_status",
                return_value={},
            ):
                response = live_dashboard.generate_warm_research_email_preview()

            body = json.loads(response.body)
            self.assertTrue(body["ok"])
            self.assertEqual(1, body["preview"]["warm_email_preview_rows"])
            self.assertTrue((run_dir / "warm_email_preview.csv").exists())
            self.assertFalse(any(run_dir.glob("recipients_*.csv")))

    def test_check_important_leads_upload_rejects_declared_size_over_check_upload_limit(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            upload = live_dashboard.UploadFile(
                filename="authors_upload.csv",
                file=BytesIO(b"Email,FirstName\nanna@example.com,Anna\n"),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "check_master_leads",
            ) as check_master_leads:
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="authors_upload.csv",
                        client_selected_size_bytes=str(live_dashboard.IMPORTANT_LEADS_CHECK_UPLOAD_MAX_BYTES + 1),
                        client_selected_extension=".csv",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            body = json.loads(response.body)
            self.assertEqual(413, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("UPLOAD_TOO_LARGE", body["error"])
            self.assertIn("CSV/XLSX", body["message"])
            self.assertEqual(live_dashboard.IMPORTANT_LEADS_CHECK_UPLOAD_MAX_BYTES, body["details"]["max_upload_bytes"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_upload_rejects_stream_over_check_upload_limit(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            upload = live_dashboard.UploadFile(
                filename="authors_upload.csv",
                file=BytesIO(b"Email,FirstName\nanna@example.com,Anna\n"),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "_read_upload_bytes_with_limit",
                side_effect=ValueError("Upload too large. Limit is 157286400 bytes."),
            ) as read_upload, patch.object(
                live_dashboard,
                "_start_important_check_job",
            ) as start_job:
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="authors_upload.csv",
                        client_selected_size_bytes="0",
                        client_selected_extension=".csv",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            body = json.loads(response.body)
            self.assertEqual(413, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("UPLOAD_TOO_LARGE", body["error"])
            self.assertIn("CSV/XLSX", body["message"])
            self.assertEqual(live_dashboard.IMPORTANT_LEADS_CHECK_UPLOAD_MAX_BYTES, body["details"]["max_upload_bytes"])
            read_upload.assert_called_once()
            start_job.assert_not_called()

    def test_dispatch_job_creates_pre_dispatch_archive_before_confirm(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs = tmp / "dispatch_jobs"
            backups = tmp / "backups"
            report_path = tmp / "dispatch_report.json"
            job = {
                "job_id": "dispatch_test",
                "preview_id": "preview_1",
                "status": "queued",
                "stage": "queued",
                "phase": "queued",
                "total_rows": 1,
            }
            jobs.mkdir()
            (jobs / "dispatch_test.json").write_text(json.dumps(job), encoding="utf-8")
            call_order: list[str] = []

            def fake_pack_archive(path: Path, include_check_history: bool = False):
                call_order.append("archive")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("archive", encoding="utf-8")
                return {
                    "file_count": 2,
                    "created_at_utc": "2026-04-26T00:00:00+00:00",
                    "queue_counts": {"data/shards/recipients_sendgrid_1.csv": 10},
                    "state_summaries": {},
                }

            def fake_confirm(*args, **kwargs):
                call_order.append("confirm")
                return {
                    "run_id": "dispatch_run_test",
                    "report_path": str(report_path),
                    "added_astra": 1,
                    "added_sendgrid": 1,
                    "skipped_both": 0,
                    "dispatch_selected_row_count": 1,
                    "suppressed_skipped": 0,
                    "duplicate_master_skipped": 0,
                    "invalid_malformed_skipped": 0,
                }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_DISPATCH_JOBS", jobs), patch.object(
                live_dashboard.settings, "BACKUPS_DIR", backups
            ), patch.object(live_dashboard, "pack_archive", side_effect=fake_pack_archive), patch.object(
                live_dashboard, "confirm_dispatch_preview", side_effect=fake_confirm
            ), patch.object(live_dashboard, "save_state") as save_state:
                live_dashboard._run_important_dispatch_job("dispatch_test")

            saved_job = json.loads((jobs / "dispatch_test.json").read_text(encoding="utf-8"))

            self.assertEqual(["archive", "confirm"], call_order)
            self.assertEqual("completed", saved_job["status"])
            self.assertIn("pre_dispatch_archive", saved_job)
            self.assertTrue(Path(saved_job["pre_dispatch_archive_path"]).exists())
            self.assertIn("pre_dispatch_archive", json.loads(report_path.read_text(encoding="utf-8")))
            save_state.assert_called()

    def test_dispatch_job_archive_failure_fails_closed_without_mutating_live_queues(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs = tmp / "dispatch_jobs"
            queue_path = tmp / "recipients_sendgrid_1.csv"
            original_queue = "Email,FirstName\nqueued@example.com,Queued\n"
            queue_path.write_text(original_queue, encoding="utf-8")
            job = {
                "job_id": "dispatch_archive_failure",
                "preview_id": "preview_1",
                "status": "queued",
                "stage": "queued",
                "phase": "queued",
                "total_rows": 1,
            }
            jobs.mkdir()
            (jobs / "dispatch_archive_failure.json").write_text(json.dumps(job), encoding="utf-8")

            def fail_if_called(*args, **kwargs):
                queue_path.write_text("Email,FirstName\nmutated@example.com,Mutated\n", encoding="utf-8")
                raise AssertionError("confirm_dispatch_preview should not run after archive failure")

            with patch.object(live_dashboard, "IMPORTANT_LEADS_DISPATCH_JOBS", jobs), patch.object(
                live_dashboard,
                "_create_pre_dispatch_archive",
                side_effect=RuntimeError("archive failed"),
            ), patch.object(
                live_dashboard,
                "confirm_dispatch_preview",
                side_effect=fail_if_called,
            ) as confirm_dispatch_preview, patch.object(
                live_dashboard,
                "save_state",
            ) as save_state:
                live_dashboard._run_important_dispatch_job("dispatch_archive_failure")

            saved_job = json.loads((jobs / "dispatch_archive_failure.json").read_text(encoding="utf-8"))

            self.assertEqual("failed", saved_job["status"])
            self.assertEqual("failed", saved_job["stage"])
            self.assertEqual("failed", saved_job["phase"])
            self.assertIn("archive failed", saved_job["error"])
            self.assertEqual(original_queue, queue_path.read_text(encoding="utf-8"))
            self.assertNotIn("pre_dispatch_archive", saved_job)
            confirm_dispatch_preview.assert_not_called()
            save_state.assert_not_called()

    def test_repair_private_jc_queue_requires_confirmed_dispatch_before_queue_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            shards = tmp / "shards"
            backups = tmp / "backups"
            queue_path = shards / "recipients_private_jc.csv"
            self._write_csv(queue_path, ["Email", "FirstName"], [{"Email": "stale@example.com", "FirstName": "Stale"}])
            original = queue_path.read_text(encoding="utf-8")

            with patch.object(live_dashboard.settings, "SHARDS_DIR", shards), patch.object(
                live_dashboard.settings, "BACKUPS_DIR", backups
            ), patch.object(live_dashboard, "_build_live_snapshot", return_value={}), patch.object(
                live_dashboard,
                "_dispatch_preflight_block_response",
                return_value=None,
            ), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value={"safe": False, "shard_row_count_total": 1},
            ), patch.object(
                live_dashboard,
                "load_state",
                return_value={},
            ):
                response = live_dashboard.repair_private_jc_queue()

            body = json.loads(response.body)
            self.assertEqual(409, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("private_jc_repair_blocked", body["error"])
            self.assertIn("Preview Dispatch and Confirm Dispatch", body["message"])
            self.assertEqual(original, queue_path.read_text(encoding="utf-8"))
            self.assertFalse(backups.exists())

    def test_repair_private_jc_queue_archives_and_rebuilds_from_confirmed_preview_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            shards = tmp / "shards"
            backups = tmp / "backups"
            previews = tmp / "previews"
            queue_path = shards / "recipients_private_jc.csv"
            self._write_csv(
                queue_path,
                ["Email", "FirstName"],
                [
                    {"Email": "outside@example.com", "FirstName": "Outside"},
                    {"Email": "reject@example.com", "FirstName": "Reject"},
                ],
            )
            latest_dispatch = {
                "status": "completed",
                "run_id": "dispatch_run_1",
                "preview_id": "preview_1",
                "generated_at_utc": "2026-05-20T00:00:00+00:00",
            }
            preview = {
                "status": "confirmed",
                "preview_id": "preview_1",
                "confirmed_run_id": "dispatch_run_1",
                "queue_headers": ["Email", "FirstName", "AuthorName", "BookTitle"],
                "queue_paths": {"private_jc": str(queue_path)},
                "plan_rows_by_queue": {
                    "private_jc": [
                        {
                            "Email": "safe1@example.com",
                            "FirstName": "Safe",
                            "AuthorName": "Safe Author",
                            "BookTitle": "Safe Book",
                        },
                        {
                            "Email": "safe2@example.com",
                            "FirstName": "Ready",
                            "AuthorName": "Ready Author",
                            "BookTitle": "Ready Book",
                        },
                    ]
                },
            }
            before = {
                "safe": False,
                "shard_row_count_total": 2,
                "overlap_with_triaged_reject": 1,
                "outside_intended_source_count": 2,
                "outside_checked_output_count": 2,
            }
            after = {"safe": True, "shard_row_count_total": 2}

            with patch.object(live_dashboard.settings, "SHARDS_DIR", shards), patch.object(
                live_dashboard.settings, "BACKUPS_DIR", backups
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_DISPATCH_PREVIEWS", previews), patch.object(
                live_dashboard, "_build_live_snapshot", return_value={}
            ), patch.object(live_dashboard, "_dispatch_preflight_block_response", return_value=None), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                side_effect=[before, after],
            ), patch.object(
                live_dashboard,
                "load_state",
                return_value={live_dashboard.MASTER_DISPATCH_STATE_KEY: latest_dispatch},
            ), patch.object(
                live_dashboard,
                "load_dispatch_preview",
                return_value=preview,
            ), patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                response = live_dashboard.repair_private_jc_queue()

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertTrue(body["repaired"])
            self.assertEqual(2, body["summary"]["unsafe_queue_rows_archived"])
            self.assertEqual(1, body["summary"]["reject_overlap_rows_removed"])
            self.assertEqual(2, body["summary"]["outside_source_rows_removed"])
            self.assertEqual(2, body["summary"]["rebuilt_queue_rows"])
            backup_path = Path(body["summary"]["backup_path"])
            self.assertTrue(backup_path.exists())
            self.assertIn("outside@example.com", backup_path.read_text(encoding="utf-8"))
            rebuilt_rows = self._read_csv_rows(queue_path)
            self.assertEqual(["safe1@example.com", "safe2@example.com"], [row["Email"] for row in rebuilt_rows])
            self.assertEqual(["Email", "FirstName", "AuthorName", "BookTitle"], list(rebuilt_rows[0].keys()))
            send_via_sendgrid.assert_not_called()

    def test_repair_private_jc_queue_zero_add_confirmed_preview_archives_and_clears(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            shards = tmp / "shards"
            backups = tmp / "backups"
            queue_path = shards / "recipients_private_jc.csv"
            source = tmp / "leads_triaged_keep.csv"
            rejected = tmp / "leads_triaged_reject.csv"
            quarantine = tmp / "leads_triaged_quarantine.csv"
            headers = ["Email", "FirstName", "AuthorName", "BookTitle"]
            self._write_csv(
                queue_path,
                headers,
                [
                    {"Email": "matching@example.com", "FirstName": "Match", "AuthorName": "Match Author", "BookTitle": "Match Book"},
                    {"Email": "outside@example.com", "FirstName": "Outside", "AuthorName": "Outside Author", "BookTitle": "Outside Book"},
                ],
            )
            self._write_csv(source, headers, [{"Email": "matching@example.com", "FirstName": "Match", "AuthorName": "Match Author", "BookTitle": "Match Book"}])
            self._write_csv(rejected, headers, [])
            self._write_csv(quarantine, headers, [])
            latest_dispatch = {
                "status": "completed",
                "run_id": "dispatch_run_zero",
                "preview_id": "preview_zero",
                "generated_at_utc": "2026-05-20T00:00:00+00:00",
                "staged_batch_cleanup": {
                    "files": [
                        {"key": "triaged_keep", "archive_path": str(source)},
                        {"key": "triaged_reject", "archive_path": str(rejected)},
                        {"key": "triaged_quarantine", "archive_path": str(quarantine)},
                    ]
                },
            }
            preview = {
                "status": "confirmed",
                "preview_id": "preview_zero",
                "confirmed_run_id": "dispatch_run_zero",
                "queue_headers": headers,
                "queue_paths": {"private_jc": str(queue_path)},
                "plan_rows_by_queue": {"private_jc": []},
            }
            before = {
                "safe": False,
                "shard_row_count_total": 2,
                "overlap_with_triaged_reject": 0,
                "outside_intended_source_count": 1,
                "outside_checked_output_count": 1,
            }
            after = {"safe": True, "shard_row_count_total": 0}

            with patch.object(live_dashboard.settings, "SHARDS_DIR", shards), patch.object(
                live_dashboard.settings, "BACKUPS_DIR", backups
            ), patch.object(live_dashboard, "_build_live_snapshot", return_value={}), patch.object(
                live_dashboard, "_dispatch_preflight_block_response", return_value=None
            ), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                side_effect=[before, after],
            ), patch.object(
                live_dashboard,
                "load_state",
                return_value={live_dashboard.MASTER_DISPATCH_STATE_KEY: latest_dispatch},
            ), patch.object(
                live_dashboard,
                "load_dispatch_preview",
                return_value=preview,
            ), patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                response = live_dashboard.repair_private_jc_queue()

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual(2, body["summary"]["unsafe_queue_rows_archived"])
            self.assertEqual(1, body["summary"]["outside_source_rows_removed"])
            self.assertEqual(1, body["summary"]["matching_current_source_reviewed"])
            self.assertEqual(0, body["summary"]["rebuilt_queue_rows"])
            backup_path = Path(body["summary"]["backup_path"])
            self.assertTrue(backup_path.exists())
            self.assertEqual([], self._read_csv_rows(queue_path))
            self.assertEqual(",".join(headers), queue_path.read_text(encoding="utf-8").splitlines()[0])
            send_via_sendgrid.assert_not_called()

    def test_dispatch_preview_archives_assigned_plan_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            master = tmp / "leads.csv"
            rejected = tmp / "leads_rejected.csv"
            triaged_keep = tmp / "leads_triaged_keep.csv"
            verified = tmp / "leads_verified.csv"
            queues = [tmp / "recipients_private_jc.csv", *[tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]]
            logs = [tmp / "private_jc_log.csv", *[tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]]
            suppressions = tmp / "sendgrid_suppressions.csv"
            suppressed = tmp / "suppressed.csv"
            unsubscribed = tmp / "unsubscribed.csv"
            preview_dir = tmp / "state" / "dispatch_previews"
            ledger_db = tmp / "lead_ledger.sqlite3"
            rows = [
                {"Email": "alpha@example.com", "FirstName": "Alpha", "AuthorEmail": "alpha@example.com", "AuthorName": "Alpha Author", "BookTitle": "Alpha Book"},
                {"Email": "beta@example.com", "FirstName": "Beta", "AuthorEmail": "beta@example.com", "AuthorName": "Beta Author", "BookTitle": "Beta Book"},
            ]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            self._write_csv(master, headers, rows)
            self._write_csv(triaged_keep, headers + ["Status"], [{**row, "Status": "KEEP"} for row in rows])
            self._write_csv(rejected, headers, [])
            self._write_csv(verified, headers, [])
            for queue in queues:
                self._write_csv(queue, headers, [])
            for log in logs:
                self._write_csv(log, ["TimestampUTC", "Email", "Status", "Info"], [])
            for path in [suppressions, suppressed, unsubscribed]:
                self._write_csv(path, ["Email"], [])

            with patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                preview = important_leads_workflow.preview_dispatch_master_leads(
                    master_path=master,
                    rejected_path=rejected,
                    verified_path=verified,
                    triaged_keep_path=triaged_keep,
                    dispatch_source_mode=important_leads_workflow.DISPATCH_SOURCE_TRIAGED_KEEP,
                    jc_queue_path=queues[0],
                    sendgrid_queue_paths=queues[1:],
                    jc_log_path=logs[0],
                    sendgrid_log_paths=logs[1:],
                    sendgrid_suppressions_path=suppressions,
                    suppressed_path=suppressed,
                    unsubscribed_path=unsubscribed,
                    lead_ledger_db_path=ledger_db,
                    preview_dir=preview_dir,
                )

            archive_path = Path(str(preview["assigned_preview_archive_path"]))
            self.assertTrue(archive_path.exists())
            archived = json.loads(archive_path.read_text(encoding="utf-8"))
            self.assertEqual(2, archived["source_row_count"])
            self.assertEqual(2, archived["eligible_row_count"])
            self.assertEqual(1, len(archived["private_jc_planned_rows"]))
            self.assertEqual(1, len(archived["sendgrid_planned_rows"]))
            self.assertEqual(1, len(archived["per_shard_planned_rows"]["sendgrid_1"]))
            self.assertEqual(0, len(archived["per_shard_planned_rows"]["sendgrid_2"]))
            send_via_sendgrid.assert_not_called()

    def test_confirm_dispatch_archives_confirmed_summary_counts(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state = tmp / "state"
            master = tmp / "leads.csv"
            rejected = tmp / "leads_rejected.csv"
            triaged_keep = tmp / "leads_triaged_keep.csv"
            verified = tmp / "leads_verified.csv"
            queues = [tmp / "recipients_private_jc.csv", *[tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]]
            logs = [tmp / "private_jc_log.csv", *[tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]]
            suppressions = tmp / "sendgrid_suppressions.csv"
            suppressed = tmp / "suppressed.csv"
            unsubscribed = tmp / "unsubscribed.csv"
            preview_dir = state / "dispatch_previews"
            ledger_db = state / "lead_ledger.sqlite3"
            rows = [
                {"Email": "alpha@example.com", "FirstName": "Alpha", "AuthorEmail": "alpha@example.com", "AuthorName": "Alpha Author", "BookTitle": "Alpha Book"},
                {"Email": "beta@example.com", "FirstName": "Beta", "AuthorEmail": "beta@example.com", "AuthorName": "Beta Author", "BookTitle": "Beta Book"},
            ]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            self._write_csv(master, headers, rows)
            self._write_csv(triaged_keep, headers + ["Status"], [{**row, "Status": "KEEP"} for row in rows])
            self._write_csv(rejected, headers, [])
            self._write_csv(verified, headers, [])
            for queue in queues:
                self._write_csv(queue, headers, [])
            for log in logs:
                self._write_csv(log, ["TimestampUTC", "Email", "Status", "Info"], [])
            for path in [suppressions, suppressed, unsubscribed]:
                self._write_csv(path, ["Email"], [])

            preview = important_leads_workflow.preview_dispatch_master_leads(
                master_path=master,
                rejected_path=rejected,
                verified_path=verified,
                triaged_keep_path=triaged_keep,
                dispatch_source_mode=important_leads_workflow.DISPATCH_SOURCE_TRIAGED_KEEP,
                jc_queue_path=queues[0],
                sendgrid_queue_paths=queues[1:],
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=suppressions,
                suppressed_path=suppressed,
                unsubscribed_path=unsubscribed,
                lead_ledger_db_path=ledger_db,
                preview_dir=preview_dir,
            )
            with patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                report = important_leads_workflow.confirm_dispatch_preview(
                    str(preview["preview_id"]),
                    require_stopped=False,
                    backup_root=state / "backups",
                    report_dir=state,
                    persist_state=False,
                    preview_dir=preview_dir,
                )

            confirmed_path = Path(str(report["confirmed_summary_path"]))
            self.assertTrue(confirmed_path.exists())
            confirmed = json.loads(confirmed_path.read_text(encoding="utf-8"))
            self.assertEqual(1, confirmed["private_jc_added"])
            self.assertEqual(1, confirmed["sendgrid_added"])
            self.assertEqual(1, confirmed["sg1_added"])
            self.assertEqual(0, confirmed["sg2_added"])
            self.assertEqual(0, confirmed["sg3_added"])
            self.assertEqual(str(preview["assigned_preview_archive_path"]), confirmed["assigned_preview_archive_path"])
            self.assertEqual(1, report["private_jc_added"])
            self.assertEqual(1, report["sendgrid_added"])
            self.assertTrue(Path(str(report["assigned_preview_archive_path"])).exists())
            send_via_sendgrid.assert_not_called()

    def test_zero_add_dispatch_archives_explicit_zero_summary(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state = tmp / "state"
            master = tmp / "leads.csv"
            rejected = tmp / "leads_rejected.csv"
            triaged_keep = tmp / "leads_triaged_keep.csv"
            verified = tmp / "leads_verified.csv"
            queues = [tmp / "recipients_private_jc.csv", *[tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]]
            logs = [tmp / "private_jc_log.csv", *[tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]]
            suppressions = tmp / "sendgrid_suppressions.csv"
            suppressed = tmp / "suppressed.csv"
            unsubscribed = tmp / "unsubscribed.csv"
            preview_dir = state / "dispatch_previews"
            ledger_db = state / "lead_ledger.sqlite3"
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            self._write_csv(master, headers, [{"Email": "dupe@example.com", "FirstName": "Dupe", "AuthorEmail": "dupe@example.com", "AuthorName": "Dupe Author", "BookTitle": "Dupe Book"}])
            self._write_csv(triaged_keep, headers + ["Status"], [{"Email": "dupe@example.com", "FirstName": "Dupe", "AuthorEmail": "dupe@example.com", "AuthorName": "Dupe Author", "BookTitle": "Dupe Book", "Status": "KEEP"}])
            self._write_csv(rejected, headers, [])
            self._write_csv(verified, headers, [])
            for queue in queues:
                self._write_csv(queue, headers, [{"Email": "dupe@example.com", "FirstName": "Dupe", "AuthorEmail": "dupe@example.com", "AuthorName": "Dupe Author", "BookTitle": "Dupe Book"}])
            for log in logs:
                self._write_csv(log, ["TimestampUTC", "Email", "Status", "Info"], [])
            for path in [suppressions, suppressed, unsubscribed]:
                self._write_csv(path, ["Email"], [])

            preview = important_leads_workflow.preview_dispatch_master_leads(
                master_path=master,
                rejected_path=rejected,
                verified_path=verified,
                triaged_keep_path=triaged_keep,
                dispatch_source_mode=important_leads_workflow.DISPATCH_SOURCE_TRIAGED_KEEP,
                jc_queue_path=queues[0],
                sendgrid_queue_paths=queues[1:],
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=suppressions,
                suppressed_path=suppressed,
                unsubscribed_path=unsubscribed,
                lead_ledger_db_path=ledger_db,
                preview_dir=preview_dir,
            )
            self.assertEqual(0, preview["total_rows_would_write"])
            with patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                report = important_leads_workflow.confirm_dispatch_preview(
                    str(preview["preview_id"]),
                    require_stopped=False,
                    backup_root=state / "backups",
                    report_dir=state,
                    persist_state=False,
                    preview_dir=preview_dir,
                )

            confirmed = json.loads(Path(str(report["confirmed_summary_path"])).read_text(encoding="utf-8"))
            self.assertEqual(0, confirmed["private_jc_added"])
            self.assertEqual(0, confirmed["sendgrid_added"])
            self.assertIn("already_queued", confirmed["report"]["exclusion_reason_counts"])
            self.assertIn("Zero-add dispatch confirmed", report["message"])
            self.assertIn("already queued", report["message"])
            self.assertEqual(report["confirmed_summary_path"], report["confirmed_summary_archive_path"])
            send_via_sendgrid.assert_not_called()

    def test_combined_leads_status_uses_latest_confirmed_dispatch_summary(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state = tmp / "state"
            confirmed_dir = state / "dispatch_confirmed"
            confirmed_dir.mkdir(parents=True)
            confirmed_path = confirmed_dir / "dispatch_confirmed_20260520_010203.json"
            confirmed_path.write_text(
                json.dumps(
                    {
                        "confirmed_at_utc": "2026-05-20T01:02:03+00:00",
                        "source_path": "_important/leads_triaged_keep.csv",
                        "source_rows": 97,
                        "eligible_rows": 97,
                        "private_jc_added": 41,
                        "sendgrid_added": 52,
                        "sg1_added": 11,
                        "sg2_added": 10,
                        "sg3_added": 10,
                        "sg4_added": 10,
                        "sg5_added": 11,
                        "skipped_both": 4,
                        "suppressed": 3,
                        "backup_path": "data/state/backups/dispatch_test",
                        "assigned_preview_archive_path": "data/state/dispatch_previews/dispatch_preview_20260520_010200.json",
                        "report": {
                            "generated_at_utc": "2026-05-20T01:02:03+00:00",
                            "dispatch_source_name": "Fast Triage Keep",
                            "dispatch_source_path": "_important/leads_triaged_keep.csv",
                            "dispatch_source_row_count": 97,
                            "dispatch_eligible_row_count": 97,
                            "dispatch_selected_row_count": 97,
                            "added_astra": 41,
                            "added_sendgrid": 52,
                            "assigned_sg1": 11,
                            "assigned_sg2": 10,
                            "assigned_sg3": 10,
                            "assigned_sg4": 10,
                            "assigned_sg5": 11,
                            "skipped_both": 4,
                            "assigned_preview_rows": [{"Email": "synthetic@example.com"}],
                            "queue_headers": ["Email"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(live_dashboard.settings, "STATE_DIR", state), patch.object(
                live_dashboard,
                "load_state",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={"latest_dispatch": {}},
            ), patch.object(live_dashboard, "important_leads_verify_status", return_value={}), patch.object(
                live_dashboard,
                "_find_active_important_check_job",
                return_value=None,
            ), patch.object(live_dashboard, "_find_active_dashboard_job", return_value=None), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value={"safe": True},
            ), patch.object(
                live_dashboard,
                "_latest_fast_triage_keep_source",
                return_value={"source_resolution": "legacy_important_triaged_keep"},
            ):
                status = live_dashboard._combined_leads_status()

            latest = status["latest_dispatch"]
            self.assertEqual(41, latest["private_jc_added"])
            self.assertEqual(52, latest["sendgrid_added"])
            self.assertEqual(11, latest["sg1_added"])
            self.assertEqual(97, latest["dispatch_source_row_count"])
            self.assertEqual(str(confirmed_path), latest["confirmed_summary_path"])

    def test_combined_leads_status_exposes_active_campaign_snapshot_for_display(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state = tmp / "state"
            state.mkdir(parents=True)
            source = tmp / "safe_recontact.csv"
            checked = tmp / "checked.csv"
            reject = tmp / "reject.csv"
            self._write_csv(source, ["Email"], [{"Email": "synthetic-one@example.test"}, {"Email": "synthetic-two@example.test"}])
            self._write_csv(checked, ["Email"], [{"Email": "synthetic-one@example.test"}, {"Email": "synthetic-two@example.test"}, {"Email": "synthetic-three@example.test"}])
            self._write_csv(reject, ["Email"], [])
            (state / "active_campaign_snapshot.json").write_text(
                json.dumps(
                    {
                        "created_at_utc": "2026-06-20T10:00:00+00:00",
                        "campaign_type": "recontact_cold",
                        "intended_source_path": str(source),
                        "checked_path": str(checked),
                        "triaged_reject_path": str(reject),
                        "files": {
                            "intended_source": {"path": str(source), "row_count": 2},
                            "checked": {"path": str(checked), "row_count": 3},
                            "triaged_reject": {"path": str(reject), "row_count": 0},
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(live_dashboard.settings, "STATE_DIR", state), patch.object(
                live_dashboard,
                "load_state",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={"jc_queue": {"count": 544}, "sendgrid_queues": []}), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={"latest_dispatch": {}},
            ), patch.object(live_dashboard, "important_leads_verify_status", return_value={}), patch.object(
                live_dashboard,
                "_find_active_important_check_job",
                return_value=None,
            ), patch.object(live_dashboard, "_find_active_dashboard_job", return_value=None), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value={"safe": True},
            ), patch.object(live_dashboard, "_load_latest_confirmed_dispatch_summary", return_value={}):
                status = live_dashboard._combined_leads_status()

            snapshot = status["active_campaign_snapshot"]
            self.assertEqual("recontact_cold", snapshot["campaign_type"])
            self.assertEqual(str(source), snapshot["intended_source_path"])
            self.assertEqual(2, snapshot["intended_source_row_count"])
            self.assertEqual(3, snapshot["checked_row_count"])

    def test_combined_leads_status_prefers_latest_staged_triaged_keep(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "jobs"
            runs_dir = tmp / "runs"
            run_dir = runs_dir / "check_20260521_160619_9eb75e28"
            jobs_dir.mkdir(parents=True)
            run_dir.mkdir(parents=True)
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            keep_path = run_dir / "leads_triaged_keep.csv"
            triage_reject_path = run_dir / "leads_triaged_reject.csv"
            quarantine_path = run_dir / "leads_triaged_quarantine.csv"
            self._write_csv(
                output_path,
                ["FirstName", "Email", "AuthorName", "AuthorEmail", "BookTitle"],
                [
                    {"FirstName": "Ava", "Email": "ava@example.test", "AuthorName": "Ava Author", "AuthorEmail": "ava@example.test", "BookTitle": "Ava Book"},
                    {"FirstName": "Bea", "Email": "bea@example.test", "AuthorName": "Bea Author", "AuthorEmail": "bea@example.test", "BookTitle": "Bea Book"},
                ],
            )
            self._write_csv(rejected_path, ["FirstName", "Email"], [])
            self._write_csv(
                keep_path,
                ["FirstName", "Email", "AuthorName", "AuthorEmail", "BookTitle", "Status"],
                [
                    {"FirstName": "Ava", "Email": "ava@example.test", "AuthorName": "Ava Author", "AuthorEmail": "ava@example.test", "BookTitle": "Ava Book", "Status": "KEEP"},
                    {"FirstName": "Bea", "Email": "bea@example.test", "AuthorName": "Bea Author", "AuthorEmail": "bea@example.test", "BookTitle": "Bea Book", "Status": "KEEP"},
                ],
            )
            self._write_csv(triage_reject_path, ["FirstName", "Email"], [])
            self._write_csv(quarantine_path, ["FirstName", "Email"], [])
            job = {
                "job_id": "check_20260521_160619_9eb75e28",
                "status": "completed",
                "created_at_utc": "2026-05-21T16:06:19+00:00",
                "completed_at_utc": "2026-05-21T16:12:19+00:00",
                "intake_mode": live_dashboard.TRIAGE_MODE_MANUAL_AUTHOR_RESEARCH,
                "total_input_rows": 2044,
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "auto_triage_status": "completed",
                "auto_triage_keep_path": str(keep_path),
                "auto_triage_rejected_path": str(triage_reject_path),
                "auto_triage_quarantine_path": str(quarantine_path),
            }
            (jobs_dir / f"{job['job_id']}.json").write_text(json.dumps(job), encoding="utf-8")

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                runs_dir,
            ), patch.object(
                live_dashboard,
                "load_state",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={
                    "dispatch_source_mode": important_leads_workflow.DISPATCH_SOURCE_TRIAGED_KEEP,
                    "dispatch_source": {"dispatch_source_path": "_important/leads_triaged_keep.csv", "dispatch_source_row_count": 0},
                    "dispatch_source_options": {},
                    "latest_master_check": {"intake_mode": "STANDARD", "input_rows": 1, "cleaned_rows": 1},
                    "latest_lead_triage": {"keep_count": 0},
                },
            ), patch.object(live_dashboard, "important_leads_verify_status", return_value={}), patch.object(
                live_dashboard,
                "_find_active_important_check_job",
                return_value=None,
            ), patch.object(live_dashboard, "_find_active_dashboard_job", return_value=None), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value={"safe": True},
            ), patch.object(live_dashboard, "_load_latest_confirmed_dispatch_summary", return_value={}):
                status = live_dashboard._combined_leads_status()

            self.assertEqual("MANUAL_AUTHOR_RESEARCH", status["latest_master_check"]["intake_mode"])
            self.assertEqual(2044, status["latest_master_check"]["input_rows"])
            self.assertEqual(2, status["latest_master_check"]["cleaned_rows"])
            self.assertEqual(2, status["latest_lead_triage"]["keep_count"])
            self.assertEqual(live_dashboard._dashboard_path_label(keep_path), status["dispatch_source_path"])
            self.assertEqual(2, status["dispatch_source_row_count"])
            self.assertEqual("latest_completed_staged_run", status["dispatch_source"]["source_resolution"])

    def test_lead_check_status_running_state_when_job_is_active(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            run_dir = Path(tmpdir) / "check_active"
            input_path = run_dir / "leadschecker.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            status = {
                "active_important_check_job": {
                    "job_id": "check_active",
                    "status": "running",
                    "stage": "checking",
                    "created_at_utc": "2026-05-21T16:00:00+00:00",
                    "updated_at_utc": live_dashboard.iso_utc(),
                },
                "important_input_label": str(input_path),
                "important_output_label": str(output_path),
                "important_rejected_label": str(rejected_path),
                "latest_master_check": {},
            }
            state = {"important_leads_paths": {"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)}}

            result = live_dashboard._build_lead_check_status(status, state)

            self.assertEqual("processing", result["state"])
            self.assertEqual("Processing / checking", result["label"])
            self.assertFalse(result["preview_ready"])
            self.assertIn("processing", result["preview_block_reason"].lower())

    def test_lead_check_status_success_ready_requires_matching_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            run_dir = Path(tmpdir) / "check_ready"
            input_path = run_dir / "leadschecker.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            self._write_csv(output_path, ["Email"], [{"Email": "reader@example.test"}])
            self._write_csv(rejected_path, ["Email"], [])
            status = {
                "active_important_check_job": None,
                "important_input_label": str(input_path),
                "important_output_label": str(output_path),
                "important_rejected_label": str(rejected_path),
                "latest_master_check": {
                    "generated_at_utc": "2026-05-21T16:12:19+00:00",
                    "output_label": str(output_path),
                    "rejected_label": str(rejected_path),
                    "cleaned_rows": 1,
                },
            }
            state = {"important_leads_paths": {"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)}}

            result = live_dashboard._build_lead_check_status(status, state)

            self.assertEqual("success", result["state"])
            self.assertEqual("Success — ready for Preview Dispatch", result["label"])
            self.assertTrue(result["preview_ready"])
            self.assertEqual(1, result["cleaned_rows"])

    def test_lead_check_status_stale_when_running_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            run_dir = Path(tmpdir) / "check_stale"
            input_path = run_dir / "leadschecker.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            status = {
                "active_important_check_job": {
                    "job_id": "check_stale",
                    "status": "running",
                    "stage": "checking",
                    "updated_at_utc": "2020-01-01T00:00:00+00:00",
                },
                "important_input_label": str(input_path),
                "important_output_label": str(output_path),
                "important_rejected_label": str(rejected_path),
                "latest_master_check": {},
            }
            state = {"important_leads_paths": {"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)}}

            result = live_dashboard._build_lead_check_status(status, state)

            self.assertEqual("stale", result["state"])
            self.assertEqual("Failed/Stale — check did not produce outputs", result["label"])
            self.assertIn("No cleaned/rejected output files were produced", result["message"])
            self.assertEqual(
                "Do not preview. Re-upload a clean lead CSV and run Upload & Check again.",
                result["guidance"],
            )
            self.assertIn("Check failed or stale", result["preview_block_reason"])

    def test_lead_check_status_running_missing_outputs_overrides_old_latest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            run_dir = tmp / "check_20260713_161206_1d857689"
            old_run = tmp / "check_20260704_synthetic"
            input_path = tmp / "leadschecker_20260713_161206.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            old_output = old_run / "leads.csv"
            old_rejected = old_run / "leads_rejected.csv"
            run_dir.mkdir(parents=True)
            self._write_csv(input_path, ["Email"], [{"Email": "bad-combined@example.test"}])
            self._write_csv(old_output, ["Email"], [{"Email": "old@example.test"}])
            self._write_csv(old_rejected, ["Email"], [])
            status = {
                "active_important_check_job": {
                    "job_id": "check_20260713_161206_1d857689",
                    "status": "running",
                    "stage": "checking",
                    "created_at_utc": "2026-07-13T16:12:06+00:00",
                    "updated_at_utc": "2020-01-01T00:00:00+00:00",
                },
                "important_input_label": str(input_path),
                "important_output_label": str(output_path),
                "important_rejected_label": str(rejected_path),
                "latest_master_check": {
                    "generated_at_utc": "2026-07-04T12:00:00+00:00",
                    "output_label": str(old_output),
                    "rejected_label": str(old_rejected),
                    "cleaned_rows": 1,
                },
            }
            state = {"important_leads_paths": {"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)}}

            result = live_dashboard._build_lead_check_status(status, state)

            self.assertEqual("stale", result["state"])
            self.assertNotEqual("not_started", result["state"])
            self.assertEqual("Failed/Stale — check did not produce outputs", result["label"])
            self.assertFalse(result["preview_ready"])
            self.assertFalse(result["confirm_ready"])
            self.assertEqual(
                "Do not preview. Re-upload a clean lead CSV and run Upload & Check again.",
                result["guidance"],
            )
            self.assertIn("No cleaned/rejected output files were produced", result["preview_block_reason"])

    def test_lead_ops_progress_reconciles_zombie_running_job_as_stale(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            run_dir = Path(tmpdir) / "check_zombie"
            input_path = run_dir / "leadschecker.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            status = {
                "active_important_check_job": {
                    "job_id": "check_zombie",
                    "status": "running",
                    "stage": "checking",
                    "created_at_utc": "2020-01-01T00:00:00+00:00",
                    "updated_at_utc": "2020-01-01T00:05:00+00:00",
                    "effective_input_path": str(input_path),
                    "output_path": str(output_path),
                    "rejected_path": str(rejected_path),
                    "total_input_rows": 1,
                },
                "active_important_verify_job": None,
                "active_important_dispatch_job": None,
            }

            progress = live_dashboard._current_lead_ops_progress(status)

            self.assertEqual("stale", progress["phase"])
            self.assertEqual("Stale — rerun check before preview", progress["current_message"])
            self.assertFalse(progress["output_exists"])
            self.assertFalse(progress["rejected_exists"])

    def test_start_important_check_job_writes_upload_received_progress_without_touching_queues(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            jobs_dir = tmp / "jobs"
            runs_dir = tmp / "runs"
            input_path = tmp / "leadschecker.csv"
            uploaded_path = tmp / "upload.csv"
            self._write_csv(uploaded_path, ["Email"], [{"Email": "reader@example.test"}])

            class FakeThread:
                def __init__(self, *args, **kwargs):
                    pass

                def start(self) -> None:
                    pass

            with patch.object(live_dashboard.settings, "STATE_DIR", state_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_JOBS",
                jobs_dir,
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_RUNS", runs_dir), patch.object(
                live_dashboard.threading,
                "Thread",
                FakeThread,
            ):
                job = live_dashboard._start_important_check_job(
                    input_path=input_path,
                    output_path=tmp / "leads.csv",
                    rejected_path=tmp / "leads_rejected.csv",
                    effective_input_path=uploaded_path,
                    source_label="upload.csv",
                    source_mode="uploaded_file",
                    total_input_rows=1,
                )
                progress_path = state_dir / f"lead_ops_progress_{job['job_id']}.json"
                progress = json.loads(progress_path.read_text(encoding="utf-8"))

            self.assertEqual("upload_received", progress["phase"])
            self.assertEqual("Upload received", progress["current_message"])
            self.assertEqual(1, progress["total_rows"])
            self.assertEqual(str(uploaded_path), progress["input_path"])

    def test_lead_ops_progress_checking_percent_uses_actual_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            input_path = tmp / "leadschecker.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            job = {
                "job_id": "check_progress_percent",
                "created_at_utc": "2026-07-14T09:29:50+00:00",
                "effective_input_path": str(input_path),
                "total_input_rows": 100,
                "eta_seconds": 30,
            }

            with patch.object(live_dashboard.settings, "STATE_DIR", state_dir):
                progress = live_dashboard._write_lead_ops_progress(
                    job,
                    phase="checking",
                    status="running",
                    processed_rows=25,
                    total_rows=100,
                    current_message="Checking leads",
                )

            self.assertEqual("checking", progress["phase"])
            self.assertEqual(25, progress["processed_rows"])
            self.assertEqual(100, progress["total_rows"])
            self.assertEqual(25.0, progress["percent"])
            self.assertEqual("Checking leads", progress["current_message"])
            self.assertEqual(30, progress["eta_seconds"])
            self.assertIn("elapsed_seconds", progress)

    def test_lead_ops_progress_triage_percent_uses_actual_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            input_path = tmp / "leads.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            job = {
                "job_id": "triage_progress_percent",
                "created_at_utc": "2026-07-14T09:30:00+00:00",
                "effective_input_path": str(input_path),
                "auto_triage_total_rows": 80,
                "auto_triage_eta_seconds": 45,
            }

            with patch.object(live_dashboard.settings, "STATE_DIR", state_dir):
                progress = live_dashboard._write_lead_ops_progress(
                    job,
                    phase="triaging",
                    status="running",
                    processed_rows=40,
                    total_rows=80,
                    current_message="Fast triage",
                )

            self.assertEqual("triaging", progress["phase"])
            self.assertEqual(40, progress["processed_rows"])
            self.assertEqual(80, progress["total_rows"])
            self.assertEqual(50.0, progress["percent"])
            self.assertEqual("Fast triage", progress["current_message"])
            self.assertEqual(45, progress["eta_seconds"])

    def test_lead_ops_progress_complete_failed_and_stale_payloads_are_clear(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            state_dir = tmp / "state"
            input_path = tmp / "leads.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            self._write_csv(output_path, ["Email"], [{"Email": "reader@example.test"}])
            self._write_csv(rejected_path, ["Email"], [])
            job = {
                "job_id": "complete_progress",
                "created_at_utc": "2026-07-14T09:31:00+00:00",
                "effective_input_path": str(input_path),
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
            }

            with patch.object(live_dashboard.settings, "STATE_DIR", state_dir):
                complete = live_dashboard._write_lead_ops_progress(
                    job,
                    phase="preview_complete",
                    status="preview_complete",
                    processed_rows=10,
                    total_rows=10,
                    percent=100,
                    current_message="Preview complete",
                )
                failed = live_dashboard._write_lead_ops_progress(
                    {**job, "job_id": "failed_progress"},
                    phase="failed",
                    status="failed",
                    processed_rows=0,
                    total_rows=10,
                    percent=0,
                    current_message="Failed",
                    error_summary="Checker crashed.",
                )

            stale = live_dashboard._reconcile_lead_ops_progress(
                {
                    **job,
                    "job_id": "stale_progress",
                    "phase": "checking",
                    "status": "running",
                    "updated_at_utc": "2020-01-01T00:00:00+00:00",
                    "output_path": str(tmp / "missing_leads.csv"),
                    "rejected_path": str(tmp / "missing_rejected.csv"),
                },
                active_job_ids={"stale_progress"},
            )

            self.assertEqual("preview_complete", complete["phase"])
            self.assertEqual(100, complete["percent"])
            self.assertEqual("Preview complete", complete["current_message"])
            self.assertEqual("failed", failed["phase"])
            self.assertEqual("Checker crashed.", failed["error_summary"])
            self.assertEqual("stale", stale["phase"])
            self.assertEqual(live_dashboard.LEAD_OPS_PROGRESS_STALE_WARNING, stale["stale_warning"])

    def test_lead_check_status_mismatch_when_latest_check_points_to_old_run(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            current_run = tmp / "check_current"
            old_run = tmp / "check_old"
            input_path = current_run / "leadschecker.csv"
            output_path = current_run / "leads.csv"
            rejected_path = current_run / "leads_rejected.csv"
            old_output = old_run / "leads.csv"
            old_rejected = old_run / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "new@example.test"}])
            self._write_csv(output_path, ["Email"], [{"Email": "new@example.test"}])
            self._write_csv(rejected_path, ["Email"], [])
            self._write_csv(old_output, ["Email"], [{"Email": "old@example.test"}])
            self._write_csv(old_rejected, ["Email"], [])
            status = {
                "active_important_check_job": None,
                "important_input_label": str(input_path),
                "important_output_label": str(output_path),
                "important_rejected_label": str(rejected_path),
                "latest_master_check": {
                    "generated_at_utc": "2026-05-20T16:12:19+00:00",
                    "output_label": str(old_output),
                    "rejected_label": str(old_rejected),
                    "cleaned_rows": 1,
                },
            }
            state = {"important_leads_paths": {"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)}}

            result = live_dashboard._build_lead_check_status(status, state)

            self.assertEqual("mismatch", result["state"])
            self.assertEqual("Check state mismatch", result["label"])
            self.assertEqual("Latest check result does not match the current upload.", result["message"])
            self.assertFalse(result["preview_ready"])

    def test_lead_check_status_failed_blocks_preview_when_outputs_missing(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            run_dir = Path(tmpdir) / "check_failed"
            input_path = run_dir / "leadschecker.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            self._write_csv(input_path, ["Email"], [{"Email": "reader@example.test"}])
            status = {
                "active_important_check_job": None,
                "important_input_label": str(input_path),
                "important_output_label": str(output_path),
                "important_rejected_label": str(rejected_path),
                "latest_master_check": {},
            }
            state = {"important_leads_paths": {"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)}}

            result = live_dashboard._build_lead_check_status(status, state)

            self.assertEqual("failed", result["state"])
            self.assertFalse(result["preview_ready"])
            self.assertEqual(
                "Do not preview. Re-upload a clean lead CSV and run Upload & Check again.",
                result["guidance"],
            )
            self.assertIn("No cleaned/rejected output files were produced", result["preview_block_reason"])

    def test_combined_leads_status_clears_stale_confirmed_dispatch_for_newer_staged_triage(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "jobs"
            runs_dir = tmp / "runs"
            run_dir = runs_dir / "check_20260529_145034_abcd1234"
            jobs_dir.mkdir(parents=True)
            run_dir.mkdir(parents=True)
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            keep_path = run_dir / "leads_triaged_keep.csv"
            triage_reject_path = run_dir / "leads_triaged_reject.csv"
            quarantine_path = run_dir / "leads_triaged_quarantine.csv"
            self._write_csv(output_path, ["FirstName", "Email"], [{"FirstName": "Ava", "Email": "ava@example.test"}])
            self._write_csv(rejected_path, ["FirstName", "Email"], [])
            self._write_csv(keep_path, ["FirstName", "Email", "Status"], [{"FirstName": "Ava", "Email": "ava@example.test", "Status": "KEEP"}])
            self._write_csv(triage_reject_path, ["FirstName", "Email"], [])
            self._write_csv(quarantine_path, ["FirstName", "Email"], [])
            job = {
                "job_id": "check_20260529_145034_abcd1234",
                "status": "completed",
                "created_at_utc": "2026-05-29T14:50:34+00:00",
                "completed_at_utc": "2026-05-29T14:55:34+00:00",
                "auto_triage_status": "completed",
                "auto_triage_completed_at_utc": "2026-05-29T14:58:00+00:00",
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "auto_triage_keep_path": str(keep_path),
                "auto_triage_rejected_path": str(triage_reject_path),
                "auto_triage_quarantine_path": str(quarantine_path),
            }
            (jobs_dir / f"{job['job_id']}.json").write_text(json.dumps(job), encoding="utf-8")
            stale_dispatch = {
                "generated_at_utc": "2026-05-28T10:00:00+00:00",
                "dispatch_source_path": "_important/leads_triaged_keep.csv",
                "dispatch_source_row_count": 97,
                "added_sendgrid": 43,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                runs_dir,
            ), patch.object(
                live_dashboard,
                "load_state",
                return_value={"latest_auto_dispatch_preview": {"preview_id": "old_preview", "generated_at_utc": "2026-05-28T09:00:00+00:00"}},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={
                    "dispatch_source_mode": important_leads_workflow.DISPATCH_SOURCE_TRIAGED_KEEP,
                    "dispatch_source": {"dispatch_source_path": "_important/leads_triaged_keep.csv", "dispatch_source_row_count": 0},
                    "dispatch_source_options": {},
                },
            ), patch.object(live_dashboard, "important_leads_verify_status", return_value={}), patch.object(
                live_dashboard,
                "_find_active_important_check_job",
                return_value=None,
            ), patch.object(live_dashboard, "_find_active_dashboard_job", return_value=None), patch.object(
                live_dashboard,
                "build_dashboard_queue_safety_report",
                return_value={"safe": True},
            ), patch.object(live_dashboard, "_load_latest_confirmed_dispatch_summary", return_value=stale_dispatch):
                status = live_dashboard._combined_leads_status()

            self.assertEqual({}, status["latest_dispatch"])
            self.assertEqual(stale_dispatch, status["stale_latest_dispatch"])
            self.assertFalse(status["latest_confirmed_dispatch_current"])
            self.assertEqual({}, status["latest_auto_dispatch_preview"])
            self.assertFalse(status["latest_auto_dispatch_preview_current"])
            self.assertEqual(live_dashboard._dashboard_path_label(keep_path), status["dispatch_source_path"])

    def test_sendgrid_event_webhook_returns_ledger_summary_without_breaking_response(self) -> None:
        class RequestStub:
            headers: dict[str, str] = {}

            async def body(self) -> bytes:
                return b'[{"email":"user@example.com","event":"delivered"}]'

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with patch.object(live_dashboard, "SENDGRID_EVENT_PUBLIC_KEY", ""), patch.object(
                live_dashboard,
                "WEBHOOK_DEDUPE_PATH",
                tmp / "webhook_dedupe.sqlite3",
            ), patch.object(
                live_dashboard,
                "WEBHOOK_EVENTS_PATH",
                tmp / "sendgrid_events.jsonl",
            ), patch.object(
                live_dashboard,
                "SUPPRESSION_CSV",
                tmp / "sendgrid_suppressions.csv",
            ), patch.object(
                live_dashboard,
                "normalize_webhook_events",
                return_value=[{"email": "user@example.com", "status": "delivered"}],
            ), patch.object(
                live_dashboard,
                "dedupe_webhook_events",
                return_value={"unique_events": [{"email": "user@example.com", "status": "delivered"}], "duplicates": 0},
            ), patch.object(
                live_dashboard,
                "append_events_jsonl",
                return_value=1,
            ), patch.object(
                live_dashboard,
                "update_suppressions_from_events",
                return_value={"updated_events": 0, "records_total": 0, "total_perm": 0, "total_temp_active": 0},
            ), patch.object(
                live_dashboard,
                "ingest_send_outcome_events",
                return_value={
                    "processed_events": 1,
                    "matched_events": 1,
                    "unmatched_events": 0,
                    "ignored_events": 0,
                    "dispatch_rows_updated": 1,
                    "lead_rows_updated": 1,
                    "suppressed_events": 0,
                    "outcome_counts": {"delivered": 1},
                },
            ), patch.object(
                live_dashboard.runtime_control,
                "apply_delivery_guards",
                return_value={},
            ):
                response = asyncio.run(live_dashboard.sendgrid_event_webhook(RequestStub()))

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertTrue(body["ok"])
        self.assertEqual({"delivered": 1}, body["ledger_summary"]["outcome_counts"])
        self.assertIn("suppression_summary", body)

    def test_check_important_leads_accepts_pasted_csv_text(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="\ufefffirst_name;email\r\nJane;jane@example.com\r\n",
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120000.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 1,
                "reason_counts": {},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                tmp / "runs",
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120000",
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual("FirstName,Email\nLegacy,legacy@example.com\n", input_path.read_text(encoding="utf-8"))
            check_master_leads.assert_called_once()
            kwargs = check_master_leads.call_args.kwargs
            run_input_path = check_runs_dir / "leadschecker_20260409_120000.csv"
            self.assertEqual("first_name;email\nJane;jane@example.com\n", run_input_path.read_text(encoding="utf-8"))
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])
            self.assertEqual(tmp / "runs", kwargs["output_path"].parent.parent)
            self.assertEqual("leads.csv", kwargs["output_path"].name)
            self.assertEqual(kwargs["output_path"].with_name("leads_rejected.csv"), kwargs["rejected_path"])
            self.assertEqual(str(output_path), body["live_output_path"])
            self.assertEqual(str(rejected_path), body["live_rejected_path"])
            save_state.assert_called()

    def test_check_important_leads_adds_header_for_simple_name_email_paste(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="Jane,jane@example.com\r\nJohn,john@example.com\r\n",
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120100.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 2,
                "reason_counts": {},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120100",
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            self.assertEqual(200, response.status_code)
            run_input_path = check_runs_dir / "leadschecker_20260409_120100.csv"
            self.assertEqual(
                "Email,FirstName\njane@example.com,Jane\njohn@example.com,John\n",
                run_input_path.read_text(encoding="utf-8"),
            )
            kwargs = check_master_leads.call_args.kwargs
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])

    def test_check_important_leads_normalizes_email_only_rows_to_canonical_queue_shape(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="  User.Tag+promo@Example.COM  \r\nsecond.person@EXAMPLE.org\r\n",
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120200.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 1,
                "reason_counts": {},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120200",
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            self.assertEqual(200, response.status_code)
            run_input_path = check_runs_dir / "leadschecker_20260409_120200.csv"
            self.assertEqual(
                "Email,FirstName\nUser.Tag+promo@example.com,\nsecond.person@example.org,\n",
                run_input_path.read_text(encoding="utf-8"),
            )
            kwargs = check_master_leads.call_args.kwargs
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])

    def test_check_important_leads_extracts_email_from_wrapper_text(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="Contact: Jane.Doe+Promo@EXAMPLE.com\r\n",
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120205.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 1,
                "reason_counts": {},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120205",
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            self.assertEqual(200, response.status_code)
            run_input_path = check_runs_dir / "leadschecker_20260409_120205.csv"
            self.assertEqual(
                "Email,FirstName\nJane.Doe+Promo@example.com,\n",
                run_input_path.read_text(encoding="utf-8"),
            )
            kwargs = check_master_leads.call_args.kwargs
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])

    def test_check_important_leads_splits_comma_separated_email_list(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="alice@example.com,bob@example.com,charlie@example.com\r\n",
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120210.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 3,
                "reason_counts": {},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120210",
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            self.assertEqual(200, response.status_code)
            run_input_path = check_runs_dir / "leadschecker_20260409_120210.csv"
            self.assertEqual(
                "Email,FirstName\nalice@example.com,\nbob@example.com,\ncharlie@example.com,\n",
                run_input_path.read_text(encoding="utf-8"),
            )
            kwargs = check_master_leads.call_args.kwargs
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])

    def test_check_important_leads_upload_uses_run_scoped_input(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "canonical.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            input_path.write_text("Email,FirstName\nLegacy,legacy@example.com\n", encoding="utf-8")
            upload = live_dashboard.UploadFile(
                filename="authors_upload.csv",
                file=BytesIO(b"Email,FirstName\nanna@example.com,Anna\n"),
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 1,
                "reason_counts": {},
            }
            fake_job = {
                "job_id": "check_20260409_120230_abcd1234",
                "status": "queued",
                "stage": "queued",
                "created_at_utc": "2026-04-09T12:02:30+00:00",
                "updated_at_utc": "2026-04-09T12:02:30+00:00",
                "source_mode": "uploaded_file",
                "source_label": "authors_upload.csv",
                "original_uploaded_filename": "authors_upload.csv",
                "server_received_filename": "authors_upload.csv",
                "selected_filename": "authors_upload.csv",
                "selected_size_bytes": 37,
                "selected_extension": ".csv",
                "input_path": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "saved_input_path": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "effective_input_path": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "total_input_rows": 1,
                "processed_rows": 0,
                "remaining_rows": 1,
                "eta_seconds": "",
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120230",
            ), patch.object(
                live_dashboard,
                "_start_important_check_job",
                return_value=fake_job,
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="authors_upload.csv",
                        client_selected_size_bytes="37",
                        client_selected_extension=".csv",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            self.assertEqual(202, response.status_code)
            body = json.loads(response.body)
            self.assertTrue(body["ok"])
            self.assertEqual(fake_job["job_id"], body["job"]["job_id"])
            run_input_path = check_runs_dir / "leadschecker_20260409_120230.csv"
            self.assertEqual(
                "Email,FirstName\nanna@example.com,Anna\n",
                run_input_path.read_text(encoding="utf-8"),
            )
            self.assertEqual("uploaded_file", body["job"]["source_mode"])
            self.assertEqual("authors_upload.csv", body["job"]["server_received_filename"])
            self.assertEqual("authors_upload.csv", body["job"]["selected_filename"])
            self.assertEqual(37, body["job"]["selected_size_bytes"])
            self.assertEqual(str(run_input_path), body["job"]["input_path"])
            self.assertEqual(str(run_input_path), body["job"]["saved_input_path"])
            self.assertEqual(str(run_input_path), body["job"]["effective_input_path"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_upload_ignores_stale_windows_output_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            check_runs_dir = tmp / "check_runs"
            default_output = tmp / "_important" / "leads.csv"
            default_rejected = tmp / "_important" / "leads_rejected.csv"
            default_output.parent.mkdir(parents=True, exist_ok=True)
            upload = live_dashboard.UploadFile(
                filename="authors_upload.csv",
                file=BytesIO(b"Email,FirstName\nanna@example.com,Anna\n"),
            )
            fake_job = {
                "job_id": "check_20260409_120230_abcd1234",
                "status": "queued",
                "stage": "queued",
                "created_at_utc": "2026-04-09T12:02:30+00:00",
                "updated_at_utc": "2026-04-09T12:02:30+00:00",
                "source_mode": "uploaded_file",
                "source_label": "authors_upload.csv",
                "original_uploaded_filename": "authors_upload.csv",
                "server_received_filename": "authors_upload.csv",
                "selected_filename": "authors_upload.csv",
                "selected_size_bytes": 37,
                "selected_extension": ".csv",
                "input_path": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "saved_input_path": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "output_path": str(default_output),
                "rejected_path": str(default_rejected),
                "effective_input_path": str(check_runs_dir / "leadschecker_20260409_120230.csv"),
                "total_input_rows": 1,
                "processed_rows": 0,
                "remaining_rows": 1,
                "eta_seconds": "",
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_OUTPUT", default_output), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_REJECTED",
                default_rejected,
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_RUNS", check_runs_dir), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120230",
            ), patch.object(
                live_dashboard,
                "_start_important_check_job",
                return_value=fake_job,
            ) as start_job, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}):
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="authors_upload.csv",
                        client_selected_size_bytes="37",
                        client_selected_extension=".csv",
                        output_path="D:\\VS\\email automation\\_important\\leads.csv",
                        rejected_path="C:\\VS\\email automation\\_important\\leads_rejected.csv",
                    )
                )

            self.assertEqual(202, response.status_code)
            start_job.assert_called_once()
            kwargs = start_job.call_args.kwargs
            self.assertEqual(default_output.resolve(strict=False), kwargs["output_path"])
            self.assertEqual(default_rejected.resolve(strict=False), kwargs["rejected_path"])

    def test_check_important_leads_upload_requires_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "check_master_leads",
            ) as check_master_leads:
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=None,
                        client_selected_filename="authors_upload.csv",
                        client_selected_size_bytes="0",
                        client_selected_extension=".csv",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            body = json.loads(response.body)
            self.assertEqual(400, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("UPLOAD_FILE_REQUIRED", body["error"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_upload_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            upload = live_dashboard.UploadFile(
                filename="authors_upload.xls",
                file=BytesIO(b"Email,FirstName\nanna@example.com,Anna\n"),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "check_master_leads",
            ) as check_master_leads:
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="authors_upload.xls",
                        client_selected_size_bytes="37",
                        client_selected_extension=".xls",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            body = json.loads(response.body)
            self.assertEqual(415, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("UPLOAD_UNSUPPORTED_FILE_TYPE", body["error"])
            self.assertIn(".csv", body["message"])
            self.assertIn(".xlsx", body["message"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_upload_accepts_xlsx_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Leads"
            sheet.append(["Email", "FirstName"])
            sheet.append(["anna@example.com", "Anna"])
            sheet.append(["bob@example.com", "Bob"])
            xlsx_buffer = BytesIO()
            workbook.save(xlsx_buffer)
            workbook.close()
            upload = live_dashboard.UploadFile(
                filename="EmailFullName_Leads.xlsx",
                file=BytesIO(xlsx_buffer.getvalue()),
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120240.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 2,
                "reason_counts": {},
            }
            fake_job = {
                "job_id": "check_20260409_120240_abcd1234",
                "status": "queued",
                "stage": "queued",
                "created_at_utc": "2026-04-09T12:02:40+00:00",
                "updated_at_utc": "2026-04-09T12:02:40+00:00",
                "source_mode": "uploaded_file",
                "source_label": "EmailFullName_Leads.xlsx",
                "original_uploaded_filename": "EmailFullName_Leads.xlsx",
                "server_received_filename": "EmailFullName_Leads.xlsx",
                "selected_filename": "EmailFullName_Leads.xlsx",
                "selected_size_bytes": len(xlsx_buffer.getvalue()),
                "selected_extension": ".xlsx",
                "input_path": str(check_runs_dir / "leadschecker_20260409_120240.csv"),
                "saved_input_path": str(check_runs_dir / "leadschecker_20260409_120240.csv"),
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "effective_input_path": str(check_runs_dir / "leadschecker_20260409_120240.csv"),
                "total_input_rows": 3,
                "processed_rows": 0,
                "remaining_rows": 3,
                "eta_seconds": "",
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120240",
            ), patch.object(
                live_dashboard,
                "_start_important_check_job",
                return_value=fake_job,
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="EmailFullName_Leads.xlsx",
                        client_selected_size_bytes=str(len(xlsx_buffer.getvalue())),
                        client_selected_extension=".xlsx",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            self.assertEqual(202, response.status_code)
            body = json.loads(response.body)
            self.assertTrue(body["ok"])
            run_input_path = check_runs_dir / "leadschecker_20260409_120240.csv"
            text = run_input_path.read_text(encoding="utf-8")
            self.assertIn("Email,FirstName", text)
            self.assertIn("anna@example.com,Anna", text)
            self.assertIn("bob@example.com,Bob", text)
            self.assertEqual("EmailFullName_Leads.xlsx", body["server_received_filename"])
            self.assertEqual("EmailFullName_Leads.xlsx", body["selected_filename"])
            self.assertEqual(".xlsx", body["selected_extension"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_upload_rejects_invalid_xlsx(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            upload = live_dashboard.UploadFile(
                filename="EmailFullName_Leads.xlsx",
                file=BytesIO(b"not a workbook"),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "check_master_leads",
            ) as check_master_leads:
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="EmailFullName_Leads.xlsx",
                        client_selected_size_bytes="14",
                        client_selected_extension=".xlsx",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            body = json.loads(response.body)
            self.assertEqual(400, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("UPLOAD_WORKBOOK_INVALID", body["error"])
            self.assertIn("Failed to read XLSX upload", body["message"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_upload_rejects_filename_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            upload = live_dashboard.UploadFile(
                filename="authors_upload.csv",
                file=BytesIO(b"Email,FirstName\nanna@example.com,Anna\n"),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "important_leads_status", return_value={}), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(live_dashboard, "shard_status", return_value={}), patch.object(
                live_dashboard,
                "check_master_leads",
            ) as check_master_leads:
                response = asyncio.run(
                    live_dashboard.check_important_leads_upload(
                        file=upload,
                        client_selected_filename="different_name.csv",
                        client_selected_size_bytes="37",
                        client_selected_extension=".csv",
                        output_path=str(output_path),
                        rejected_path=str(rejected_path),
                    )
                )

            body = json.loads(response.body)
            self.assertEqual(400, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("UPLOAD_FILENAME_MISMATCH", body["error"])
            self.assertIn("mismatch", body["message"].lower())
            check_master_leads.assert_not_called()

    def test_check_important_leads_blocks_large_paste_and_recommends_upload(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="\n".join(f"lead{i:04d}@example.com,Author{i:04d}" for i in range(live_dashboard.IMPORTANT_LEADS_PASTE_MAX_ROWS + 1)),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
            ) as check_master_leads, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(413, response.status_code)
            self.assertFalse(body["ok"])
            self.assertEqual("PASTE_TOO_LARGE", body["error"])
            self.assertEqual(live_dashboard.IMPORTANT_LEADS_PASTE_MAX_ROWS + 1, body["details"]["paste_rows"])
            check_master_leads.assert_not_called()

    def test_check_important_leads_job_runner_persists_completed_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "jobs"
            job_id = "check_20260409_120231_abcd1234"
            job_path = jobs_dir / f"{job_id}.json"
            job = {
                "job_id": job_id,
                "status": "queued",
                "stage": "queued",
                "created_at_utc": "2026-04-09T12:02:31+00:00",
                "updated_at_utc": "2026-04-09T12:02:31+00:00",
                "source_label": "authors_upload.csv",
                "input_path": str(tmp / "input.csv"),
                "output_path": str(tmp / "cleaned.csv"),
                "rejected_path": str(tmp / "rejected.csv"),
                "effective_input_path": str(tmp / "check_runs" / "leadschecker_20260409_120231.csv"),
                "total_input_rows": 1,
                "processed_rows": 0,
                "remaining_rows": 1,
                "eta_seconds": "",
            }
            report = {
                "input_label": "leadschecker_20260409_120231.csv",
                "output_label": "cleaned.csv",
                "rejected_label": "rejected.csv",
                "cleaned_rows": 1,
                "reason_counts": {},
            }

            def fake_execute_check(**_kwargs):
                self._write_csv(Path(job["output_path"]), ["Email"], [{"Email": "reader@example.test"}])
                self._write_csv(Path(job["rejected_path"]), ["Email"], [])
                return report

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "_execute_important_check",
                side_effect=fake_execute_check,
            ) as execute_check:
                live_dashboard._save_important_check_job(job)
                live_dashboard._run_important_check_job(job_id)

            saved = json.loads(job_path.read_text(encoding="utf-8"))
            self.assertEqual("completed", saved["status"])
            self.assertEqual(report, saved["check"])
            self.assertEqual(1, saved["processed_rows"])
            self.assertEqual(0, saved["remaining_rows"])
            self.assertEqual(0, saved["eta_seconds"])
            execute_check.assert_called_once()

    def test_active_check_job_endpoint_returns_running_progress_payload(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            jobs_dir = Path(tmpdir) / "jobs"
            running_job = {
                "job_id": "check_20260409_120231_active",
                "status": "running",
                "stage": "checking",
                "created_at_utc": "2026-04-09T12:02:31+00:00",
                "updated_at_utc": "2026-04-09T12:03:31+00:00",
                "source_label": "authors_upload.xlsx",
                "source_sheet": "Authors",
                "current_sheet": "Authors",
                "total_input_rows": 100,
                "processed_rows": 25,
                "remaining_rows": 75,
                "eta_seconds": 300,
            }
            completed_job = {
                "job_id": "check_20260409_120230_done",
                "status": "completed",
                "stage": "done",
                "total_input_rows": 10,
                "processed_rows": 10,
                "remaining_rows": 0,
                "eta_seconds": 0,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ):
                live_dashboard._save_important_check_job(completed_job)
                live_dashboard._save_important_check_job(running_job)
                response = live_dashboard.get_active_check_important_leads_job()

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertEqual("check_20260409_120231_active", body["job"]["job_id"])
            self.assertEqual(25.0, body["job"]["progress_percent"])
            self.assertEqual(300, body["job"]["eta_seconds"])
            self.assertEqual(25, body["job"]["processed_rows"])
            self.assertEqual(75, body["job"]["remaining_rows"])
            self.assertEqual("Authors", body["job"]["current_sheet"])

    def test_leads_status_includes_active_check_job_source_of_truth(self) -> None:
        active_job = {
            "job_id": "check_20260409_120231_active",
            "status": "queued",
            "stage": "queued",
            "total_input_rows": 40,
            "processed_rows": 0,
            "remaining_rows": 40,
            "eta_seconds": "",
        }
        with patch.object(live_dashboard, "_find_active_important_check_job", return_value=active_job), patch.object(
            live_dashboard,
            "shard_status",
            return_value={},
        ), patch.object(
            live_dashboard,
            "important_leads_status",
            return_value={},
        ), patch.object(
            live_dashboard,
            "important_leads_verify_status",
            return_value={},
        ):
            response = live_dashboard.leads_status()

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertEqual(active_job, body["status"]["active_important_check_job"])

    def test_completed_check_job_is_not_returned_as_active(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            jobs_dir = Path(tmpdir) / "jobs"
            completed_job = {
                "job_id": "check_20260409_120230_done",
                "status": "completed",
                "stage": "done",
                "total_input_rows": 10,
                "processed_rows": 10,
                "remaining_rows": 0,
                "eta_seconds": 0,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ):
                live_dashboard._save_important_check_job(completed_job)
                response = live_dashboard.get_active_check_important_leads_job()

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertIsNone(body["job"])

    def test_active_verify_job_endpoint_returns_progress_payload(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            jobs_dir = Path(tmpdir) / "verify_jobs"
            running_job = {
                "job_id": "verify_20260409_120231_active",
                "status": "running",
                "stage": "verifying",
                "phase": "verifying",
                "total_rows": 100,
                "processed_rows": 40,
                "remaining_rows": 60,
                "eta_seconds": 120,
            }
            with patch.object(live_dashboard, "IMPORTANT_LEADS_VERIFY_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ):
                live_dashboard._save_important_verify_job(running_job)
                response = live_dashboard.get_active_verify_important_leads_job()

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertEqual("verify_20260409_120231_active", body["job"]["job_id"])
            self.assertEqual(40.0, body["job"]["progress_percent"])
            self.assertEqual(40, body["job"]["processed_rows"])
            self.assertEqual(60, body["job"]["remaining_rows"])
            self.assertEqual(120, body["job"]["eta_seconds"])

    def test_cancel_verify_job_marks_cancel_requested_without_touching_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            jobs_dir = Path(tmpdir) / "verify_jobs"
            running_job = {
                "job_id": "verify_20260409_120231_active",
                "status": "running",
                "stage": "verifying",
                "phase": "verifying",
                "total_rows": 100,
                "processed_rows": 40,
                "remaining_rows": 60,
                "eta_seconds": 120,
            }
            with patch.object(live_dashboard, "IMPORTANT_LEADS_VERIFY_JOBS", jobs_dir):
                live_dashboard._save_important_verify_job(running_job)
                response = live_dashboard.cancel_verify_important_leads_job(running_job["job_id"])

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertTrue(body["job"]["cancel_requested"])
            self.assertEqual("cancel_requested", body["job"]["stage"])

    def test_active_dispatch_job_endpoint_returns_progress_payload(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            jobs_dir = Path(tmpdir) / "dispatch_jobs"
            running_job = {
                "job_id": "dispatch_20260409_120231_active",
                "status": "running",
                "stage": "dispatching",
                "phase": "dispatching",
                "dispatch_source_mode": "strict_verified",
                "total_rows": 100,
                "processed_rows": 20,
                "assigned_rows": 35,
                "skipped_rows": 4,
                "remaining_rows": 80,
                "eta_seconds": 240,
            }
            with patch.object(live_dashboard, "IMPORTANT_LEADS_DISPATCH_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ):
                live_dashboard._save_important_dispatch_job(running_job)
                response = live_dashboard.get_active_dispatch_important_leads_job()

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertEqual("dispatch_20260409_120231_active", body["job"]["job_id"])
            self.assertEqual(20.0, body["job"]["progress_percent"])
            self.assertEqual(35, body["job"]["assigned_rows"])
            self.assertEqual(4, body["job"]["skipped_rows"])
            self.assertEqual(80, body["job"]["remaining_rows"])
            self.assertEqual("strict_verified", body["job"]["dispatch_source_mode"])

    def test_check_important_leads_flags_ambiguous_text_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            check_runs_dir = tmp / "check_runs"
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="This is not an email address\r\n",
            )
            fake_report = {
                "input_label": str(check_runs_dir / "leadschecker_20260409_120220.csv"),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 0,
                "reason_counts": {"MISSING_EMAIL": 1},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_RUNS",
                check_runs_dir,
            ), patch.object(
                live_dashboard,
                "timestamp_slug",
                return_value="20260409_120220",
            ), patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            self.assertEqual(200, response.status_code)
            run_input_path = check_runs_dir / "leadschecker_20260409_120220.csv"
            self.assertEqual(
                "Email,FirstName\n,This is not an email address\n",
                run_input_path.read_text(encoding="utf-8"),
            )
            kwargs = check_master_leads.call_args.kwargs
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])

    def test_check_important_leads_returns_structured_checker_error(self) -> None:
        payload = live_dashboard.ImportantLeadPathsPayload(
            input_path="_important/leadschecker.csv",
            output_path="_important/leads.csv",
            rejected_path="_important/leads_rejected.csv",
            input_text="OnlyName\nJane\n",
        )

        with patch.object(
            live_dashboard,
            "important_leads_path_state",
            return_value={
                "input_path": "_important/leadschecker.csv",
                "output_path": "_important/leads.csv",
                "rejected_path": "_important/leads_rejected.csv",
            },
        ), patch.object(live_dashboard, "save_state"), patch.object(
            live_dashboard,
            "check_master_leads",
            side_effect=ImportantLeadsCheckError(
                "NO_EMAIL_HEADER",
                "Could not detect an email column.",
                details={"fieldnames": ["OnlyName"]},
            ),
        ), patch.object(
            live_dashboard,
            "important_leads_status",
            return_value={},
        ), patch.object(
            live_dashboard,
            "shard_status",
            return_value={},
        ):
            response = live_dashboard.check_important_leads(payload)

        body = json.loads(response.body)
        self.assertEqual(400, response.status_code)
        self.assertFalse(body["ok"])
        self.assertEqual("NO_EMAIL_HEADER", body["error"])
        self.assertEqual({"fieldnames": ["OnlyName"]}, body["details"])

    def test_verify_important_leads_uses_current_verify_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            quarantine_path = tmp / "leads_quarantine.csv"
            input_path.write_text("Email,FullName\njane@example.com,Jane Author\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadVerifyPayload(
                mode=live_dashboard.TRIAGE_MODE_STRICT,
                input_path=str(input_path),
                verified_path=str(verified_path),
                rejected_path=str(rejected_path),
                quarantine_path=str(quarantine_path),
            )
            fake_job = {
                "job_id": "verify_20260409_120230_abcd1234",
                "status": "queued",
                "stage": "queued",
                "total_rows": 1,
                "processed_rows": 0,
                "remaining_rows": 1,
                "progress_percent": 0,
                "eta_seconds": "",
            }

            with patch.object(
                live_dashboard,
                "important_leads_verify_path_state",
                return_value={
                    "input_path": "_important/leads.csv",
                    "verified_path": "_important/leads_verified.csv",
                    "rejected_path": "_important/leads_verify_rejected.csv",
                    "quarantine_path": "_important/leads_quarantine.csv",
                },
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "_start_important_verify_job",
                return_value=fake_job,
            ) as start_verify_job, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.verify_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(202, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual(fake_job["job_id"], body["job"]["job_id"])
            kwargs = start_verify_job.call_args.kwargs
            self.assertEqual(input_path.resolve(), kwargs["input_path"])
            self.assertEqual(verified_path.resolve(), kwargs["verified_path"])
            self.assertEqual(rejected_path.resolve(), kwargs["rejected_path"])
            self.assertEqual(quarantine_path.resolve(), kwargs["quarantine_path"])
            save_state.assert_called()

    def test_preview_dispatch_important_leads_uses_selected_source_mode(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            verified_path = tmp / "leads_verified.csv"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            verified_path.write_text("FirstName,Email,Status\nJane,jane@example.com,KEEP\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadDispatchPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                dispatch_source_mode="strict_verified",
            )
            fake_preview = {
                "preview_id": "dispatch_preview_20260409_120230_abcd1234",
                "dispatch_source_mode": "strict_verified",
                "dispatch_source_name": "Strict Public Proof Verified",
                "dispatch_source_path": str(verified_path),
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_selected_row_count": 1,
                "dispatch_cap": "all",
                "total_rows_would_write": 2,
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(
                live_dashboard,
                "important_leads_verify_path_state",
                return_value={
                    "input_path": "_important/leads.csv",
                    "verified_path": "_important/leads_verified.csv",
                    "rejected_path": "_important/leads_verify_rejected.csv",
                    "quarantine_path": "_important/leads_quarantine.csv",
                },
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(
                live_dashboard,
                "_dispatch_source_readiness_block",
                return_value=None,
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ) as preview_dispatch_master_leads, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={"dispatch_eligible_row_count": 1, "dispatch_block_reason": ""},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.preview_dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual(fake_preview["preview_id"], body["preview"]["preview_id"])
            kwargs = preview_dispatch_master_leads.call_args.kwargs
            self.assertEqual("strict_verified", kwargs["dispatch_source_mode"])
            self.assertEqual(
                Path(live_dashboard.settings.APP_ROOT / "_important" / "leads_verified.csv").resolve(),
                kwargs["verified_path"],
            )
            save_state.assert_called()

    def test_preview_dispatch_important_leads_uses_cleaned_source_for_recontact_cold(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            verified_path = tmp / "leads_verified.csv"
            input_path.write_text("AuthorName,AuthorEmail,BookTitle\nLegacy,legacy@example.com,\n", encoding="utf-8")
            output_path.write_text("AuthorName,AuthorEmail,BookTitle\nLegacy,legacy@example.com,\n", encoding="utf-8")
            triaged_keep_path.write_text("AuthorName,AuthorEmail,BookTitle,Status\nTriage,triage@example.com,Book,KEEP\n", encoding="utf-8")
            verified_path.write_text("AuthorName,AuthorEmail,BookTitle,Status\nStrict,strict@example.com,Book,KEEP\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadDispatchPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                dispatch_source_mode="triaged_keep",
                campaign_type="recontact_cold",
            )
            fake_preview = {
                "preview_id": "dispatch_preview_20260620_224051_recontact",
                "campaign_type": "recontact_cold",
                "dispatch_source_mode": "cleaned",
                "dispatch_source_name": "Checked Leads",
                "dispatch_source_path": str(output_path),
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_selected_row_count": 1,
                "dispatch_cap": "all",
                "total_rows_would_write": 2,
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(
                live_dashboard,
                "important_leads_verify_path_state",
                return_value={
                    "input_path": "_important/leads.csv",
                    "verified_path": str(verified_path),
                    "rejected_path": "_important/leads_verify_rejected.csv",
                    "quarantine_path": "_important/leads_quarantine.csv",
                },
            ), patch.object(
                live_dashboard,
                "important_leads_triage_path_state",
                return_value={
                    "input_path": "_important/leads.csv",
                    "keep_path": str(triaged_keep_path),
                    "rejected_path": "_important/leads_triaged_reject.csv",
                    "quarantine_path": "_important/leads_triaged_quarantine.csv",
                },
            ), patch.object(
                live_dashboard,
                "_latest_fast_triage_keep_source",
                return_value={
                    "source_resolution": "legacy_important_triaged_keep",
                    "job": None,
                    "run_id": "",
                    "path": triaged_keep_path,
                    "paths": {},
                    "exists": True,
                    "row_count": 1,
                },
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ) as preview_dispatch_master_leads, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={"dispatch_eligible_row_count": 1, "dispatch_block_reason": ""},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.preview_dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual("recontact_cold", body["preview"]["campaign_type"])
            self.assertEqual("cleaned", body["preview"]["dispatch_source_mode"])
            kwargs = preview_dispatch_master_leads.call_args.kwargs
            self.assertEqual("cleaned", kwargs["dispatch_source_mode"])
            self.assertEqual("recontact_cold", kwargs["campaign_type"])
            self.assertEqual(output_path.resolve(), kwargs["master_path"])
            save_state.assert_any_call(important_leads_dispatch_source={"dispatch_source_mode": "cleaned"})

    def test_preview_dispatch_important_leads_defaults_to_triaged_keep_source(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            output_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            triaged_keep_path.write_text("FirstName,Email,Status\nJane,jane@example.com,KEEP\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadDispatchPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
            )
            fake_preview = {
                "preview_id": "dispatch_preview_20260409_120230_triage",
                "dispatch_source_mode": "triaged_keep",
                "dispatch_source_name": "Fast Triage Keep",
                "dispatch_source_path": str(triaged_keep_path),
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_selected_row_count": 1,
                "dispatch_cap": "all",
                "total_rows_would_write": 2,
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(
                live_dashboard,
                "important_leads_verify_path_state",
                return_value={
                    "input_path": "_important/leads.csv",
                    "verified_path": "_important/leads_verified.csv",
                    "rejected_path": "_important/leads_verify_rejected.csv",
                    "quarantine_path": "_important/leads_quarantine.csv",
                },
            ), patch.object(
                live_dashboard,
                "important_leads_triage_path_state",
                return_value={
                    "input_path": "_important/leads.csv",
                    "keep_path": str(triaged_keep_path),
                    "rejected_path": "_important/leads_triaged_reject.csv",
                    "quarantine_path": "_important/leads_triaged_quarantine.csv",
                },
            ), patch.object(
                live_dashboard,
                "_latest_fast_triage_keep_source",
                return_value={
                    "source_resolution": "legacy_important_triaged_keep",
                    "job": None,
                    "run_id": "",
                    "path": triaged_keep_path,
                    "paths": {},
                    "exists": True,
                    "row_count": 1,
                },
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ) as preview_dispatch_master_leads, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={"dispatch_eligible_row_count": 1, "dispatch_block_reason": ""},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.preview_dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual(fake_preview["preview_id"], body["preview"]["preview_id"])
            kwargs = preview_dispatch_master_leads.call_args.kwargs
            self.assertEqual("triaged_keep", kwargs["dispatch_source_mode"])
            self.assertEqual(triaged_keep_path.resolve(), kwargs["triaged_keep_path"])
            save_state.assert_called()

    def test_preview_dispatch_important_leads_uses_latest_completed_staged_triaged_keep(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "jobs"
            runs_dir = tmp / "runs"
            run_dir = runs_dir / "check_20260521_160619_9eb75e28"
            jobs_dir.mkdir(parents=True)
            run_dir.mkdir(parents=True)
            input_path = run_dir / "leadschecker.csv"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            staged_keep_path = run_dir / "leads_triaged_keep.csv"
            legacy_keep_path = tmp / "_important" / "leads_triaged_keep.csv"
            self._write_csv(input_path, ["FirstName", "Email"], [{"FirstName": "Ava", "Email": "ava@example.test"}])
            self._write_csv(output_path, ["FirstName", "Email"], [{"FirstName": "Ava", "Email": "ava@example.test"}])
            self._write_csv(rejected_path, ["FirstName", "Email"], [])
            self._write_csv(staged_keep_path, ["FirstName", "Email", "Status"], [{"FirstName": "Ava", "Email": "ava@example.test", "Status": "KEEP"}])
            job = {
                "job_id": "check_20260521_160619_9eb75e28",
                "status": "completed",
                "created_at_utc": "2026-05-21T16:06:19+00:00",
                "completed_at_utc": "2026-05-21T16:12:19+00:00",
                "intake_mode": live_dashboard.TRIAGE_MODE_MANUAL_AUTHOR_RESEARCH,
                "total_input_rows": 2,
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "auto_triage_status": "completed",
                "auto_triage_keep_path": str(staged_keep_path),
                "auto_triage_rejected_path": str(run_dir / "leads_triaged_reject.csv"),
                "auto_triage_quarantine_path": str(run_dir / "leads_triaged_quarantine.csv"),
            }
            (jobs_dir / f"{job['job_id']}.json").write_text(json.dumps(job), encoding="utf-8")
            payload = live_dashboard.ImportantLeadDispatchPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
            )
            fake_preview = {
                "preview_id": "dispatch_preview_staged",
                "dispatch_source_mode": "triaged_keep",
                "dispatch_source_name": "Fast Triage Keep",
                "dispatch_source_path": str(staged_keep_path),
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_selected_row_count": 1,
                "dispatch_cap": "all",
                "total_rows_would_write": 1,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                runs_dir,
            ), patch.object(
                live_dashboard,
                "TRIAGED_KEEP_PATH",
                legacy_keep_path,
            ), patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={"input_path": str(input_path), "output_path": str(output_path), "rejected_path": str(rejected_path)},
            ), patch.object(
                live_dashboard,
                "important_leads_verify_path_state",
                return_value={
                    "input_path": str(output_path),
                    "verified_path": str(tmp / "leads_verified.csv"),
                    "rejected_path": str(tmp / "leads_verify_rejected.csv"),
                    "quarantine_path": str(tmp / "leads_quarantine.csv"),
                },
            ), patch.object(
                live_dashboard,
                "important_leads_triage_path_state",
                return_value={
                    "input_path": str(output_path),
                    "keep_path": str(legacy_keep_path),
                    "rejected_path": str(tmp / "leads_triaged_reject.csv"),
                    "quarantine_path": str(tmp / "leads_triaged_quarantine.csv"),
                },
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ) as preview_dispatch_master_leads, patch.object(
                live_dashboard,
                "_combined_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "_build_live_snapshot",
                return_value={},
            ):
                response = live_dashboard.preview_dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            kwargs = preview_dispatch_master_leads.call_args.kwargs
            self.assertEqual(staged_keep_path, kwargs["triaged_keep_path"])
            self.assertEqual(output_path, kwargs["master_path"])
            self.assertEqual(rejected_path, kwargs["rejected_path"])

    def test_preview_dispatch_important_leads_blocks_empty_current_staged_keep(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "jobs"
            runs_dir = tmp / "runs"
            run_dir = runs_dir / "check_empty"
            jobs_dir.mkdir(parents=True)
            run_dir.mkdir(parents=True)
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            staged_keep_path = run_dir / "leads_triaged_keep.csv"
            self._write_csv(output_path, ["FirstName", "Email"], [{"FirstName": "Ava", "Email": "ava@example.test"}])
            self._write_csv(rejected_path, ["FirstName", "Email"], [])
            self._write_csv(staged_keep_path, ["FirstName", "Email", "Status"], [])
            job = {
                "job_id": "check_empty",
                "status": "completed",
                "created_at_utc": "2026-05-21T16:06:19+00:00",
                "intake_mode": live_dashboard.TRIAGE_MODE_MANUAL_AUTHOR_RESEARCH,
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "auto_triage_status": "completed",
                "auto_triage_keep_path": str(staged_keep_path),
            }
            (jobs_dir / "check_empty.json").write_text(json.dumps(job), encoding="utf-8")
            payload = live_dashboard.ImportantLeadDispatchPayload(output_path=str(output_path), rejected_path=str(rejected_path))

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                runs_dir,
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
            ) as preview_dispatch_master_leads, patch.object(
                live_dashboard,
                "_build_live_snapshot",
                return_value={},
            ):
                response = live_dashboard.preview_dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(409, response.status_code)
            self.assertFalse(body["ok"])
            self.assertTrue(body["blocked"])
            self.assertEqual("triage_not_ready", body["error"])
            self.assertEqual("Current staged Fast Triage Keep is empty. Run Check Leads / Fast Triage first.", body["message"])
            preview_dispatch_master_leads.assert_not_called()

    def test_preview_dispatch_important_leads_blocks_empty_triaged_keep_source(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            output_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            rejected_path.write_text("FirstName,Email\n", encoding="utf-8")
            triaged_keep_path.write_text("FirstName,Email,Status\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadDispatchPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
            )

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "rejected_path": str(rejected_path),
                },
            ), patch.object(
                live_dashboard,
                "important_leads_verify_path_state",
                return_value={
                    "input_path": str(output_path),
                    "verified_path": "_important/leads_verified.csv",
                    "rejected_path": "_important/leads_verify_rejected.csv",
                    "quarantine_path": "_important/leads_quarantine.csv",
                },
            ), patch.object(
                live_dashboard,
                "important_leads_triage_path_state",
                return_value={
                    "input_path": str(output_path),
                    "keep_path": str(triaged_keep_path),
                    "rejected_path": "_important/leads_triaged_reject.csv",
                    "quarantine_path": "_important/leads_triaged_quarantine.csv",
                },
            ), patch.object(
                live_dashboard,
                "_latest_fast_triage_keep_source",
                return_value={
                    "source_resolution": "legacy_important_triaged_keep",
                    "job": None,
                    "run_id": "",
                    "path": triaged_keep_path,
                    "paths": {},
                    "exists": True,
                    "row_count": 0,
                },
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(live_dashboard, "save_state"), patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
            ) as preview_dispatch_master_leads, patch.object(
                live_dashboard,
                "_build_live_snapshot",
                return_value={},
            ):
                response = live_dashboard.preview_dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(409, response.status_code)
            self.assertFalse(body["ok"])
            self.assertTrue(body["blocked"])
            self.assertEqual("triage_not_ready", body["error"])
            self.assertIn("leads_triaged_keep.csv has no Keep rows", body["message"])
            preview_dispatch_master_leads.assert_not_called()

    def test_confirm_dispatch_important_leads_blocks_when_senders_active(self) -> None:
        payload = live_dashboard.ImportantLeadDispatchPayload(
            dispatch_source_mode="triaged_keep",
            dispatch_cap="500",
            preview_id="dispatch_preview_20260409_120230_blocked",
        )
        preview = {
            "preview_id": payload.preview_id,
            "dispatch_source_mode": "triaged_keep",
            "dispatch_cap": "500",
            "dispatch_source_name": "Fast Triage Keep",
            "dispatch_source_path": "_important/leads_triaged_keep.csv",
            "dispatch_source_row_count": 10,
            "dispatch_eligible_row_count": 10,
            "dispatch_selected_row_count": 10,
            "total_rows_would_write": 20,
        }
        active_profiles = [SimpleNamespace(name="sendgrid_1", runtime_state="running")]

        with patch.object(live_dashboard, "validate_dispatch_preview", return_value=preview), patch.object(
            live_dashboard.runtime_control,
            "list_active_sender_snapshots",
            return_value=active_profiles,
        ), patch.object(
            live_dashboard,
            "_start_important_dispatch_job",
        ) as start_dispatch_job:
            response = live_dashboard.confirm_dispatch_important_leads(payload)

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(body["ok"])
        self.assertTrue(body["blocked"])
        self.assertEqual("senders_active", body["reason"])
        self.assertEqual("senders_active", body["error"])
        self.assertEqual(["sendgrid_1"], body["active_profiles"])
        self.assertEqual(1, body["active_sender_count"])
        start_dispatch_job.assert_not_called()

    def test_confirm_dispatch_important_leads_requires_matching_campaign_type(self) -> None:
        payload = live_dashboard.ImportantLeadDispatchPayload(
            dispatch_source_mode="cleaned",
            dispatch_cap="all",
            campaign_type="cold",
            preview_id="dispatch_preview_20260620_224051_recontact",
        )
        preview = {
            "preview_id": payload.preview_id,
            "campaign_type": "recontact_cold",
            "dispatch_source_mode": "cleaned",
            "dispatch_cap": "all",
            "dispatch_source_name": "Checked Leads",
            "dispatch_source_path": "_important/leads.csv",
            "dispatch_source_row_count": 10,
            "dispatch_eligible_row_count": 10,
            "dispatch_selected_row_count": 10,
            "total_rows_would_write": 20,
        }

        with patch.object(live_dashboard, "validate_dispatch_preview", return_value=preview), patch.object(
            live_dashboard.runtime_control,
            "list_active_sender_snapshots",
            return_value=[],
        ), patch.object(
            live_dashboard,
            "_start_important_dispatch_job",
        ) as start_dispatch_job:
            response = live_dashboard.confirm_dispatch_important_leads(payload)

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(body["ok"])
        self.assertEqual("dispatch_blocked", body["error"])
        self.assertIn("campaign type", body["message"])
        start_dispatch_job.assert_not_called()

    def test_preview_dispatch_important_leads_blocks_when_senders_active(self) -> None:
        payload = live_dashboard.ImportantLeadDispatchPayload(
            dispatch_source_mode="triaged_keep",
            dispatch_cap="100",
        )
        active_profiles = [
            SimpleNamespace(name="private_jc", runtime_state="running"),
            SimpleNamespace(name="sendgrid_annette", runtime_state="cooldown"),
        ]

        with patch.object(
            live_dashboard.runtime_control,
            "list_active_sender_snapshots",
            return_value=active_profiles,
        ), patch.object(
            live_dashboard,
            "preview_dispatch_master_leads",
        ) as preview_dispatch_master_leads:
            response = live_dashboard.preview_dispatch_important_leads(payload)

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(body["ok"])
        self.assertTrue(body["blocked"])
        self.assertEqual("senders_active", body["reason"])
        self.assertEqual("senders_active", body["error"])
        self.assertEqual(["private_jc", "sendgrid_annette"], body["active_profiles"])
        self.assertEqual(2, body["active_sender_count"])
        preview_dispatch_master_leads.assert_not_called()

    def test_quarantine_review_list_returns_filtered_leads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lead_ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                lead_ledger.upsert_lead(
                    conn,
                    email="alpha@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=4.5,
                    reason_codes=["WEAK_PROOF"],
                )
                lead_ledger.upsert_lead(
                    conn,
                    email="beta@example.com",
                    current_stage=lead_ledger.STRICT_PUBLIC_PROOF_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=8.7,
                    reason_codes=["NO_PUBLIC_MATCH"],
                )
            finally:
                conn.close()

            with patch.object(live_dashboard.settings, "LEAD_LEDGER_DB_PATH", db_path):
                response = live_dashboard.quarantine_review_list(
                    reason_code="NO_PUBLIC_MATCH",
                    stage="",
                    status="QUARANTINE",
                    sort="score_desc",
                    limit=100,
                    offset=0,
                )

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertTrue(body["ok"])
        self.assertEqual(1, body["review"]["counts"]["filtered"])
        self.assertEqual("beta@example.com", body["review"]["leads"][0]["email"])

    def test_quarantine_review_action_updates_operator_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lead_ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                lead = lead_ledger.upsert_lead(
                    conn,
                    email="note-review@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=5.5,
                    reason_codes=["WEAK_PROOF"],
                )
            finally:
                conn.close()

            payload = live_dashboard.QuarantineReviewActionPayload(
                lead_ids=[lead["lead_id"]],
                action="update_operator_note",
                operator_note="Reviewed from dashboard.",
            )
            with patch.object(live_dashboard.settings, "LEAD_LEDGER_DB_PATH", db_path):
                response = live_dashboard.quarantine_review_action(payload)

            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
            finally:
                conn.close()

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertTrue(body["ok"])
        self.assertEqual("Reviewed from dashboard.", updated["operator_note"])
        self.assertEqual(1, body["result"]["updated"])

    def test_quarantine_review_action_select_all_filtered_applies_to_full_filtered_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lead_ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                alpha = lead_ledger.upsert_lead(
                    conn,
                    email="alpha-filtered@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=4.0,
                    reason_codes=["WEAK_PROOF"],
                )
                beta = lead_ledger.upsert_lead(
                    conn,
                    email="beta-filtered@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=6.0,
                    reason_codes=["WEAK_PROOF"],
                )
                gamma = lead_ledger.upsert_lead(
                    conn,
                    email="gamma-other@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=8.0,
                    reason_codes=["OTHER_REASON"],
                )
            finally:
                conn.close()

            payload = live_dashboard.QuarantineReviewActionPayload(
                action="promote_dispatch_ready",
                select_all_filtered=True,
                reason_code="WEAK_PROOF",
                status="QUARANTINE",
                sort="score_desc",
            )
            with patch.object(live_dashboard.settings, "LEAD_LEDGER_DB_PATH", db_path):
                response = live_dashboard.quarantine_review_action(payload)

            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                alpha_updated = lead_ledger.load_lead_by_id(conn, alpha["lead_id"])
                beta_updated = lead_ledger.load_lead_by_id(conn, beta["lead_id"])
                gamma_updated = lead_ledger.load_lead_by_id(conn, gamma["lead_id"])
            finally:
                conn.close()

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertTrue(body["ok"])
        self.assertEqual(2, body["result"]["updated"])
        self.assertEqual(lead_ledger.DISPATCH_READY_STATUS, alpha_updated["current_status"])
        self.assertEqual(lead_ledger.DISPATCH_READY_STATUS, beta_updated["current_status"])
        self.assertEqual(lead_ledger.QUARANTINE_STATUS, gamma_updated["current_status"])

    def test_quarantine_review_action_select_all_filtered_respects_excluded_lead_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lead_ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                alpha = lead_ledger.upsert_lead(
                    conn,
                    email="alpha-excluded@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=4.0,
                    reason_codes=["WEAK_PROOF"],
                )
                beta = lead_ledger.upsert_lead(
                    conn,
                    email="beta-excluded@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status=lead_ledger.QUARANTINE_STATUS,
                    score=6.0,
                    reason_codes=["WEAK_PROOF"],
                )
            finally:
                conn.close()

            payload = live_dashboard.QuarantineReviewActionPayload(
                action="reject_permanently",
                select_all_filtered=True,
                reason_code="WEAK_PROOF",
                status="QUARANTINE",
                sort="score_desc",
                excluded_lead_ids=[beta["lead_id"]],
            )
            with patch.object(live_dashboard.settings, "LEAD_LEDGER_DB_PATH", db_path):
                response = live_dashboard.quarantine_review_action(payload)

            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                alpha_updated = lead_ledger.load_lead_by_id(conn, alpha["lead_id"])
                beta_updated = lead_ledger.load_lead_by_id(conn, beta["lead_id"])
            finally:
                conn.close()

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertTrue(body["ok"])
        self.assertEqual(1, body["result"]["updated"])
        self.assertEqual(lead_ledger.REJECTED_STATUS, alpha_updated["current_status"])
        self.assertEqual(lead_ledger.QUARANTINE_STATUS, beta_updated["current_status"])

    def test_check_important_leads_uses_canonical_input_when_paste_empty(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "pasted_leads.csv"
            output_path = tmp / "cleaned.csv"
            rejected_path = tmp / "rejected.csv"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                input_text="   ",
            )
            fake_report = {
                "input_label": str(input_path),
                "output_label": str(output_path),
                "rejected_label": str(rejected_path),
                "cleaned_rows": 1,
                "reason_counts": {},
            }

            with patch.object(
                live_dashboard,
                "important_leads_path_state",
                return_value={
                    "input_path": "_important/leadschecker.csv",
                    "output_path": "_important/leads.csv",
                    "rejected_path": "_important/leads_rejected.csv",
                },
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "check_master_leads",
                return_value=fake_report,
            ) as check_master_leads, patch.object(
                live_dashboard,
                "important_leads_status",
                return_value={},
            ), patch.object(
                live_dashboard,
                "shard_status",
                return_value={},
            ):
                response = live_dashboard.check_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertEqual("FirstName,Email\nLegacy,legacy@example.com\n", input_path.read_text(encoding="utf-8"))
            kwargs = check_master_leads.call_args.kwargs
            self.assertEqual(input_path.resolve(), kwargs["input_path"])
            save_state.assert_called()

    def test_leads_status_includes_verify_state(self) -> None:
        with patch.object(live_dashboard, "shard_status", return_value={"shard": 1}), patch.object(
            live_dashboard,
            "important_leads_status",
            return_value={
                "check_paste_policy": {
                    "mode": "small_manual_only",
                    "paste_warning_rows": 250,
                    "paste_max_rows": 1000,
                    "upload_required_rows": 1000,
                    "upload_recommended_rows": 250,
                },
                "check": 2,
                "dispatch": 3,
                "dispatch_source_mode": "strict_verified",
                "dispatch_source_path": "_important/leads_verified.csv",
                "dispatch_source_exists": True,
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_block_reason": "",
                "verification_required": True,
                "verification_file_mtime": "2026-04-09T00:00:00+00:00",
            },
        ), patch.object(
            live_dashboard,
            "important_leads_verify_status",
            return_value={"verify": 4},
        ), patch.object(
            live_dashboard,
            "_find_active_important_check_job",
            return_value=None,
        ), patch.object(
            live_dashboard,
            "_find_active_dashboard_job",
            return_value=None,
        ):
            response = live_dashboard.leads_status()

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        expected = {
            "shard": 1,
            "check_paste_policy": {
                "mode": "small_manual_only",
                "paste_warning_rows": 250,
                "paste_max_rows": 1000,
                "upload_required_rows": 1000,
                "upload_recommended_rows": 250,
            },
            "check": 2,
            "dispatch": 3,
            "verify": 4,
            "dispatch_source_mode": "strict_verified",
            "dispatch_source_path": "_important/leads_verified.csv",
            "dispatch_source_exists": True,
            "dispatch_source_row_count": 1,
            "dispatch_eligible_row_count": 1,
            "dispatch_block_reason": "",
            "verification_required": True,
            "verification_file_mtime": "2026-04-09T00:00:00+00:00",
            "active_important_check_job": None,
            "active_important_verify_job": None,
            "active_important_dispatch_job": None,
        }
        for key, value in expected.items():
            self.assertEqual(value, body["status"][key])
        self.assertIn("pipeline", body["status"])

    def test_upload_check_success_auto_runs_fast_triage_without_touching_shards(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            important_dir = tmp / "_important"
            state_dir = tmp / "state"
            jobs_dir = important_dir / "check_runs" / "jobs"
            check_runs_dir = important_dir / "check_runs"
            output_path = important_dir / "leads.csv"
            rejected_path = important_dir / "leads_rejected.csv"
            keep_path = important_dir / "leads_triaged_keep.csv"
            triage_reject_path = important_dir / "leads_triaged_reject.csv"
            quarantine_path = important_dir / "leads_triaged_quarantine.csv"
            input_path = check_runs_dir / "uploaded.csv"
            ledger_path = state_dir / "lead_ledger.sqlite3"
            shard_path = tmp / "data" / "shards" / "recipients_sendgrid_1.csv"
            self._write_csv(shard_path, ["Email", "FirstName"], [{"Email": "queued@example.test", "FirstName": "Queued"}])
            shard_before = shard_path.read_text(encoding="utf-8")
            state_dir.mkdir(parents=True, exist_ok=True)
            self._write_csv(state_dir / "suppressed.csv", ["Email"], [])
            self._write_csv(state_dir / "unsubscribed.csv", ["Email"], [])
            self._write_csv(state_dir / "sendgrid_suppressions.csv", ["email", "status"], [])
            headers = [
                "FullName",
                "FirstName",
                "Email",
                "BookTitle",
                "AuthorName",
                "AuthorEmail",
                "PersonalizedOpeningLine",
                "WhyAstraFit",
                "Website",
                "BookURL",
                "ConfidenceScore",
                "source_file",
                "source_sheet",
                "source_row",
            ]
            self._write_csv(
                input_path,
                headers,
                [
                    {
                        "FullName": "Alpha Baker",
                        "FirstName": "Alpha",
                        "Email": "alpha.author@examplebooks.com",
                        "BookTitle": "Signals at Dawn",
                        "AuthorName": "Alpha Baker",
                        "AuthorEmail": "alpha.author@examplebooks.com",
                        "PersonalizedOpeningLine": "Synthetic opening.",
                        "WhyAstraFit": "Synthetic fit.",
                        "Website": "https://example.test/alpha",
                        "BookURL": "https://books.example.test/signals",
                        "ConfidenceScore": "0.99",
                        "source_file": "synthetic.csv",
                        "source_sheet": "Sheet1",
                        "source_row": "2",
                    },
                    {
                        "FullName": "Gamma Harbor",
                        "FirstName": "Gamma",
                        "Email": "gamma.author@examplebooks.com",
                        "BookTitle": "",
                        "AuthorName": "Gamma Harbor",
                        "AuthorEmail": "gamma.author@examplebooks.com",
                        "PersonalizedOpeningLine": "Synthetic generic opening.",
                        "WhyAstraFit": "Synthetic fit without title.",
                        "Website": "https://example.test/gamma",
                        "BookURL": "",
                        "ConfidenceScore": "0.88",
                        "source_file": "synthetic.csv",
                        "source_sheet": "Sheet1",
                        "source_row": "3",
                    },
                    {
                        "FullName": "Reject Writer",
                        "FirstName": "Reject",
                        "Email": "reject@example.com",
                        "BookTitle": "Rejected Book",
                        "AuthorName": "Reject Writer",
                        "AuthorEmail": "reject@example.com",
                        "PersonalizedOpeningLine": "Synthetic reject opening.",
                        "WhyAstraFit": "Synthetic reject fit.",
                        "Website": "https://example.test/reject",
                        "BookURL": "https://books.example.test/reject",
                        "ConfidenceScore": "0.12",
                        "source_file": "synthetic.csv",
                        "source_sheet": "Sheet1",
                        "source_row": "4",
                    },
                ],
            )
            job = {
                "job_id": "check_auto_triage_success",
                "status": "queued",
                "stage": "queued",
                "created_at_utc": "2026-05-13T00:00:00+00:00",
                "source_mode": "uploaded_file",
                "input_path": str(input_path),
                "saved_input_path": str(input_path),
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "effective_input_path": str(input_path),
                "total_input_rows": 3,
                "processed_rows": 0,
                "remaining_rows": 3,
            }

            def check_master_leads_without_external_state(**kwargs):
                return important_leads_workflow.check_master_leads(
                    **kwargs,
                    sendgrid_suppressions_path=state_dir / "sendgrid_suppressions.csv",
                    suppressed_path=state_dir / "suppressed.csv",
                    unsubscribed_path=state_dir / "unsubscribed.csv",
                    report_dir=state_dir,
                    summary_dir=check_runs_dir,
                    validate_deliverability=False,
                    reject_role_accounts=False,
                    reject_disposable=False,
                    persist_state=False,
                )

            fake_preview = {
                "preview_id": "dispatch_preview_auto_triage",
                "preview_path": str(tmp / "dispatch_preview_auto_triage.json"),
                "rows_written_per_queue": {
                    "private_jc": 2,
                    "sendgrid_1": 1,
                    "sendgrid_2": 1,
                    "sendgrid_3": 0,
                    "sendgrid_4": 0,
                    "sendgrid_5": 0,
                },
                "suppressed_skipped": 2,
                "suppression_summary": {"total_perm": 1, "total_temp_active": 1},
                "dispatch_source_row_count": 2,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_OUTPUT", output_path), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_REJECTED",
                rejected_path,
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_RUNS", check_runs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_JOBS",
                jobs_dir,
            ), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                important_dir / "runs",
            ), patch.object(live_dashboard.settings, "STATE_DIR", state_dir), patch.object(
                live_dashboard.settings,
                "LEAD_LEDGER_DB_PATH",
                ledger_path,
            ), patch.object(
                live_dashboard,
                "check_master_leads",
                side_effect=check_master_leads_without_external_state,
            ), patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ) as preview_dispatch, patch.object(
                live_dashboard,
                "build_queue_safety_report",
                return_value={"safe": True, "unsafe_reasons": [], "shard_row_count_total": 0},
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch.object(
                live_dashboard,
                "confirm_dispatch_preview",
            ) as confirm_dispatch, patch.object(
                live_dashboard.runtime_control,
                "start_sender",
            ) as start_sender, patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                live_dashboard._save_important_check_job(job)
                live_dashboard._run_important_check_job(job["job_id"])

            saved_job = json.loads((jobs_dir / f"{job['job_id']}.json").read_text(encoding="utf-8"))
            self.assertEqual("completed", saved_job["status"])
            self.assertEqual("completed", saved_job["auto_triage_status"])
            self.assertEqual("completed", saved_job["auto_dispatch_preview_status"])
            self.assertEqual(3, live_dashboard._count_csv_rows(output_path))
            staged_keep_path = Path(saved_job["auto_triage_keep_path"])
            staged_reject_path = Path(saved_job["auto_triage_rejected_path"])
            staged_quarantine_path = Path(saved_job["auto_triage_quarantine_path"])
            self.assertEqual(2, live_dashboard._count_csv_rows(staged_keep_path))
            self.assertEqual(1, live_dashboard._count_csv_rows(staged_reject_path))
            self.assertTrue(staged_quarantine_path.exists())
            self.assertFalse(keep_path.exists())
            self.assertFalse(triage_reject_path.exists())
            self.assertFalse(quarantine_path.exists())
            keep_rows = self._read_csv_rows(staged_keep_path)
            self.assertEqual("Signals at Dawn", keep_rows[0]["BookTitle"])
            self.assertEqual("Alpha Baker", keep_rows[0]["AuthorName"])
            self.assertEqual("Synthetic opening.", keep_rows[0]["PersonalizedOpeningLine"])
            self.assertEqual("Synthetic fit.", keep_rows[0]["WhyAstraFit"])
            self.assertEqual(shard_before, shard_path.read_text(encoding="utf-8"))
            preview_dispatch.assert_called_once()
            self.assertEqual(output_path, preview_dispatch.call_args.kwargs["master_path"])
            self.assertEqual(staged_keep_path, preview_dispatch.call_args.kwargs["triaged_keep_path"])
            self.assertEqual(important_dir / "runs" / job["job_id"] / "dispatch_previews", preview_dispatch.call_args.kwargs["preview_dir"])
            confirm_dispatch.assert_not_called()
            start_sender.assert_not_called()
            send_via_sendgrid.assert_not_called()
            summary = saved_job["auto_dispatch_preview"]
            self.assertEqual("dispatch_preview_auto_triage", summary["preview_id"])
            self.assertEqual(2, summary["total_keep_rows"])
            self.assertEqual(1, summary["rejected_rows"])
            self.assertEqual(1, summary["rows_with_booktitle"])
            self.assertEqual(1, summary["rows_without_booktitle"])
            self.assertTrue(summary["fallback_capable"])
            self.assertTrue(summary["fallback_readiness"]["profiles"]["private_jc"]["fallback_supported"])
            self.assertEqual(2, summary["suppression_unsubscribe_skip_count"])
            self.assertEqual(1, summary["per_profile_planned_counts"]["sendgrid_1"])
            self.assertTrue(summary["queue_safety"]["safe"])
            self.assertFalse(summary["any_sender_running"])
            self.assertTrue(summary["manual_rebuild_allowed"])
            self.assertTrue(summary["manual_rebuild_required"])
            self.assertTrue(summary["manual_start_required"])
            self.assertFalse(summary["auto_rebuild_performed"])
            self.assertFalse(summary["auto_dispatch_performed"])
            self.assertFalse(summary["auto_start_performed"])

            with patch.object(live_dashboard, "fast_triage_master_leads") as fast_triage:
                live_dashboard._run_auto_fast_triage_after_check(saved_job)
            fast_triage.assert_not_called()

    def test_auto_triage_waits_for_completed_nonempty_check_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            jobs_dir = tmp / "_important" / "check_runs" / "jobs"
            output_path = tmp / "_important" / "runs" / "check_wait" / "leads.csv"
            rejected_path = tmp / "_important" / "runs" / "check_wait" / "leads_rejected.csv"
            self._write_csv(output_path, ["FullName", "Email"], [{"FullName": "Ready Row", "Email": "ready@example.com"}])
            self._write_csv(rejected_path, ["FullName", "Email"], [])
            running_job = {
                "job_id": "check_wait",
                "status": "running",
                "source_mode": "uploaded_file",
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "staged_run_dir": str(output_path.parent),
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "fast_triage_master_leads",
            ) as fast_triage:
                saved_job = live_dashboard._run_auto_fast_triage_after_check(dict(running_job))

            self.assertEqual("skipped", saved_job["auto_triage_status"])
            self.assertEqual("check_still_running", saved_job["auto_triage_skip_reason"])
            self.assertIn("Check still running", saved_job["message"])
            fast_triage.assert_not_called()

            empty_output_path = tmp / "_important" / "runs" / "check_empty" / "leads.csv"
            empty_rejected_path = tmp / "_important" / "runs" / "check_empty" / "leads_rejected.csv"
            self._write_csv(empty_output_path, ["FullName", "Email"], [])
            self._write_csv(empty_rejected_path, ["FullName", "Email"], [])
            completed_empty_job = {
                "job_id": "check_empty",
                "status": "completed",
                "source_mode": "uploaded_file",
                "output_path": str(empty_output_path),
                "rejected_path": str(empty_rejected_path),
                "staged_run_dir": str(empty_output_path.parent),
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "fast_triage_master_leads",
            ) as fast_triage:
                saved_empty_job = live_dashboard._run_auto_fast_triage_after_check(dict(completed_empty_job))

            self.assertEqual("skipped", saved_empty_job["auto_triage_status"])
            self.assertEqual("fresh_check_output_empty", saved_empty_job["auto_triage_skip_reason"])
            self.assertIn("no accepted rows", saved_empty_job["message"])
            fast_triage.assert_not_called()

    def test_auto_triage_manual_author_research_rewrites_stale_zero_keep_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            important_dir = tmp / "_important"
            state_dir = tmp / "state"
            jobs_dir = important_dir / "check_runs" / "jobs"
            ledger_path = state_dir / "lead_ledger.sqlite3"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            run_dir = important_dir / "runs" / "check_manual_stale"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            keep_path = run_dir / "leads_triaged_keep.csv"
            triage_reject_path = run_dir / "leads_triaged_reject.csv"
            quarantine_path = run_dir / "leads_triaged_quarantine.csv"
            headers = [
                "FullName",
                "FirstName",
                "Email",
                "first_name_clean",
                "first_name_status",
                "AuthorName",
                "AuthorEmail",
                "BookTitle",
                "Website",
                "SourceURL",
                "BookURL",
                "ConfidenceScore",
            ]
            accepted_rows = [
                {
                    "FullName": "A",
                    "FirstName": "A",
                    "Email": "",
                    "first_name_clean": "",
                    "first_name_status": "initials_only",
                    "AuthorName": "Manual Alpha",
                    "AuthorEmail": "manual.alpha@examplebooks.com",
                    "BookTitle": "Alpha Launch",
                    "Website": "",
                    "SourceURL": "",
                    "BookURL": "",
                    "ConfidenceScore": "2",
                },
                {
                    "FullName": "B",
                    "FirstName": "B",
                    "Email": "",
                    "first_name_clean": "",
                    "first_name_status": "initials_only",
                    "AuthorName": "Manual Beta",
                    "AuthorEmail": "manual.beta@examplebooks.com",
                    "BookTitle": "Beta Launch",
                    "Website": "",
                    "SourceURL": "",
                    "BookURL": "",
                    "ConfidenceScore": "2",
                },
                {
                    "FullName": "No Title",
                    "FirstName": "No",
                    "Email": "",
                    "first_name_clean": "No",
                    "first_name_status": "ok",
                    "AuthorName": "Manual No Title",
                    "AuthorEmail": "manual.notitle@examplebooks.com",
                    "BookTitle": "",
                    "Website": "",
                    "SourceURL": "",
                    "BookURL": "",
                    "ConfidenceScore": "2",
                },
            ]
            self._write_csv(output_path, headers, accepted_rows)
            self._write_csv(rejected_path, headers, [])
            audit_headers = headers + ["Status", "VerificationReason", "VerificationEvidence", "VerifiedAtUtc"]
            self._write_csv(keep_path, audit_headers, [])
            self._write_csv(triage_reject_path, audit_headers, [])
            stale_quarantine_rows = [
                {
                    **row,
                    "Status": "QUARANTINE",
                    "VerificationReason": "MISSING_USABLE_PERSON_NAME",
                    "VerificationEvidence": "Legacy Manual Author Research policy quarantined weak names.",
                    "VerifiedAtUtc": "2026-05-21T00:00:00+00:00",
                }
                for row in accepted_rows
            ]
            self._write_csv(quarantine_path, audit_headers, stale_quarantine_rows)
            state_dir.mkdir(parents=True, exist_ok=True)
            triage_state_path.write_text(
                json.dumps(
                    {
                        "mode": important_leads_verify.TRIAGE_MODE_MANUAL_AUTHOR_RESEARCH,
                        "input_path": str(output_path),
                        "input_fingerprint": important_leads_verify._hash_input_file(output_path),
                        "keep_path": str(keep_path),
                        "rejected_path": str(triage_reject_path),
                        "quarantine_path": str(quarantine_path),
                        "base_headers": headers,
                        "next_row_index": len(accepted_rows),
                        "total_input_rows": len(accepted_rows),
                        "completed": True,
                    }
                ),
                encoding="utf-8",
            )
            job = {
                "job_id": "check_manual_stale",
                "status": "completed",
                "stage": "done",
                "phase": "done",
                "source_mode": "uploaded_file",
                "intake_mode": "MANUAL_AUTHOR_RESEARCH",
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "staged_run_dir": str(run_dir),
                "total_input_rows": len(accepted_rows),
            }
            fake_preview = {
                "preview_id": "dispatch_preview_manual_stale",
                "preview_path": str(run_dir / "dispatch_previews" / "dispatch_preview_manual_stale.json"),
                "rows_written_per_queue": {"private_jc": 2},
                "suppressed_skipped": 0,
                "suppression_summary": {},
                "dispatch_source_row_count": 2,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                important_dir / "runs",
            ), patch.object(live_dashboard.settings, "STATE_DIR", state_dir), patch.object(
                live_dashboard.settings,
                "LEAD_LEDGER_DB_PATH",
                ledger_path,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path), patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ) as preview_dispatch, patch.object(
                live_dashboard,
                "build_queue_safety_report",
                return_value={"safe": True, "unsafe_reasons": [], "shard_row_count_total": 0},
            ), patch.object(
                live_dashboard,
                "_book_title_fallback_readiness",
                return_value={"fallback_capable": False, "profiles": []},
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                live_dashboard._save_important_check_job(job)
                saved_job = live_dashboard._run_auto_fast_triage_after_check(dict(job))

            self.assertEqual("completed", saved_job["auto_triage_status"])
            self.assertEqual(2, saved_job["auto_triage_report"]["keep_count"])
            self.assertEqual(0, saved_job["auto_triage_report"]["reject_count"])
            self.assertEqual(1, saved_job["auto_triage_report"]["quarantine_count"])
            self.assertEqual(2, saved_job["auto_triage_report"]["send_ready_keep_rows"])
            self.assertEqual(2, saved_job["auto_triage_report"]["keep_with_warnings_rows"])
            self.assertIn("SOURCEURL_MISSING", saved_job["auto_triage_report"]["soft_warning_counts"])
            keep_rows = self._read_csv_rows(keep_path)
            quarantine_rows = self._read_csv_rows(quarantine_path)
            self.assertEqual(2, len(keep_rows))
            self.assertEqual(1, len(quarantine_rows))
            self.assertEqual("KEEP", keep_rows[0]["Status"])
            self.assertEqual("manual.alpha@examplebooks.com", keep_rows[0]["Email"])
            self.assertEqual("manual.alpha@examplebooks.com", keep_rows[0]["AuthorEmail"])
            self.assertEqual("Alpha Launch", keep_rows[0]["BookTitle"])
            self.assertEqual("BOOKTITLE_MISSING", quarantine_rows[0]["VerificationReason"])
            preview_dispatch.assert_called_once()
            self.assertEqual(keep_path, preview_dispatch.call_args.kwargs["triaged_keep_path"])
            send_via_sendgrid.assert_not_called()

    def test_auto_triage_manual_author_research_keeps_missing_booktitle_when_pitch_fallback_supported(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            important_dir = tmp / "_important"
            state_dir = tmp / "state"
            jobs_dir = important_dir / "check_runs" / "jobs"
            ledger_path = state_dir / "lead_ledger.sqlite3"
            run_dir = important_dir / "runs" / "check_manual_fallback"
            output_path = run_dir / "leads.csv"
            rejected_path = run_dir / "leads_rejected.csv"
            keep_path = run_dir / "leads_triaged_keep.csv"
            headers = ["AuthorName", "AuthorEmail", "BookTitle", "PersonalizedOpeningLine"]
            self._write_csv(
                output_path,
                headers,
                [{"AuthorName": "Fallback Author", "AuthorEmail": "fallback@examplebooks.com", "BookTitle": "", "PersonalizedOpeningLine": ""}],
            )
            self._write_csv(rejected_path, headers, [])
            job = {
                "job_id": "check_manual_fallback",
                "status": "completed",
                "stage": "done",
                "phase": "done",
                "source_mode": "uploaded_file",
                "intake_mode": "MANUAL_AUTHOR_RESEARCH",
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "staged_run_dir": str(run_dir),
                "total_input_rows": 1,
            }
            fake_preview = {
                "preview_id": "dispatch_preview_manual_fallback",
                "preview_path": str(run_dir / "dispatch_previews" / "dispatch_preview_manual_fallback.json"),
                "rows_written_per_queue": {"private_jc": 1},
                "suppressed_skipped": 0,
                "suppression_summary": {},
                "dispatch_source_row_count": 1,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                important_dir / "runs",
            ), patch.object(live_dashboard.settings, "STATE_DIR", state_dir), patch.object(
                live_dashboard.settings,
                "LEAD_LEDGER_DB_PATH",
                ledger_path,
            ), patch.object(
                live_dashboard,
                "_book_title_fallback_readiness",
                return_value={"fallback_capable": True, "profiles": []},
            ), patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value=fake_preview,
            ), patch.object(
                live_dashboard,
                "build_queue_safety_report",
                return_value={"safe": True, "unsafe_reasons": [], "shard_row_count_total": 0},
            ), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ), patch("send_shard.send_via_sendgrid") as send_via_sendgrid:
                live_dashboard._save_important_check_job(job)
                saved_job = live_dashboard._run_auto_fast_triage_after_check(dict(job))

            self.assertEqual("completed", saved_job["auto_triage_status"])
            self.assertTrue(saved_job["auto_triage_report"]["book_title_fallback_supported"])
            self.assertEqual(1, saved_job["auto_triage_report"]["keep_count"])
            self.assertEqual(0, saved_job["auto_triage_report"]["quarantine_count"])
            self.assertEqual(1, saved_job["auto_triage_report"]["keep_with_fallback_rows"])
            self.assertIn("BOOKTITLE_MISSING_USING_TEMPLATE_FALLBACK", saved_job["auto_triage_report"]["soft_warning_counts"])
            keep_rows = self._read_csv_rows(keep_path)
            self.assertEqual(1, len(keep_rows))
            self.assertEqual("", keep_rows[0]["BookTitle"])
            self.assertEqual("", keep_rows[0]["PersonalizedOpeningLine"])
            self.assertIn("BOOKTITLE_MISSING_USING_TEMPLATE_FALLBACK", keep_rows[0]["VerificationEvidence"])
            send_via_sendgrid.assert_not_called()

    def test_auto_triage_uses_manual_author_research_intake_mode(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            important_dir = tmp / "_important"
            state_dir = tmp / "state"
            jobs_dir = important_dir / "check_runs" / "jobs"
            output_path = important_dir / "runs" / "check_manual" / "leads.csv"
            rejected_path = important_dir / "runs" / "check_manual" / "leads_rejected.csv"
            self._write_csv(output_path, ["FullName", "Email"], [{"FullName": "Manual Author", "Email": "manual@example.com"}])
            self._write_csv(rejected_path, ["FullName", "Email"], [])
            job = {
                "job_id": "check_manual",
                "status": "completed",
                "source_mode": "uploaded_file",
                "intake_mode": "MANUAL_AUTHOR_RESEARCH",
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "staged_run_dir": str(output_path.parent),
            }
            report = {
                "mode": "MANUAL_AUTHOR_RESEARCH",
                "generated_at_utc": "2026-05-20T00:00:00+00:00",
                "input_label": str(output_path),
                "verified_label": str(output_path.parent / "leads_triaged_keep.csv"),
                "rejected_label": str(output_path.parent / "leads_triaged_reject.csv"),
                "quarantine_label": str(output_path.parent / "leads_triaged_quarantine.csv"),
                "total_input_rows": 1,
                "input_rows": 1,
                "processed_rows": 1,
                "keep_count": 0,
                "reject_count": 0,
                "quarantine_count": 1,
                "soft_warning_counts": {"PERSONAL_EMAIL_PROVIDER": 1},
                "hard_reject_counts": {},
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_RUNS",
                important_dir / "runs",
            ), patch.object(live_dashboard.settings, "STATE_DIR", state_dir), patch.object(
                live_dashboard,
                "fast_triage_master_leads",
                return_value=report,
            ) as fast_triage, patch.object(
                live_dashboard,
                "preview_dispatch_master_leads",
                return_value={"preview_id": "preview_manual", "rows_written_per_queue": {}, "suppressed_skipped": 0, "dispatch_source_row_count": 0},
            ), patch.object(live_dashboard, "build_queue_safety_report", return_value={"safe": True}), patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[],
            ):
                live_dashboard._save_important_check_job(job)
                saved_job = live_dashboard._run_auto_fast_triage_after_check(job)

            self.assertEqual("MANUAL_AUTHOR_RESEARCH", fast_triage.call_args.kwargs["mode"])
            self.assertEqual("Manual Author Research", saved_job["auto_triage_report"]["intake_mode_label"])
            self.assertEqual({"PERSONAL_EMAIL_PROVIDER": 1}, saved_job["auto_triage_report"]["soft_warning_counts"])

    def test_upload_check_failure_and_cancel_skip_auto_triage(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            important_dir = tmp / "_important"
            state_dir = tmp / "state"
            jobs_dir = important_dir / "check_runs" / "jobs"
            check_runs_dir = important_dir / "check_runs"
            output_path = important_dir / "leads.csv"
            rejected_path = important_dir / "leads_rejected.csv"
            keep_path = important_dir / "leads_triaged_keep.csv"
            input_path = check_runs_dir / "uploaded.csv"
            self._write_csv(
                input_path,
                ["FullName", "Email", "BookTitle"],
                [{"FullName": "Beta Writer", "Email": "beta@examplebooks.com", "BookTitle": "Beta Book"}],
            )
            state_dir.mkdir(parents=True, exist_ok=True)
            self._write_csv(state_dir / "suppressed.csv", ["Email"], [])
            self._write_csv(state_dir / "unsubscribed.csv", ["Email"], [])
            self._write_csv(state_dir / "sendgrid_suppressions.csv", ["email", "status"], [])
            base_job = {
                "status": "queued",
                "stage": "queued",
                "created_at_utc": "2026-05-13T00:00:00+00:00",
                "source_mode": "uploaded_file",
                "input_path": str(input_path),
                "saved_input_path": str(input_path),
                "output_path": str(output_path),
                "rejected_path": str(rejected_path),
                "effective_input_path": str(input_path),
                "total_input_rows": 1,
                "processed_rows": 0,
                "remaining_rows": 1,
            }

            with patch.object(live_dashboard, "IMPORTANT_LEADS_OUTPUT", output_path), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_REJECTED",
                rejected_path,
            ), patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_RUNS", check_runs_dir), patch.object(
                live_dashboard,
                "IMPORTANT_LEADS_CHECK_JOBS",
                jobs_dir,
            ), patch.object(live_dashboard.settings, "STATE_DIR", state_dir), patch.object(
                live_dashboard.settings,
                "LEAD_LEDGER_DB_PATH",
                state_dir / "lead_ledger.sqlite3",
            ):
                failed_job = dict(base_job, job_id="check_auto_triage_failed")
                live_dashboard._save_important_check_job(failed_job)
                with patch.object(live_dashboard, "check_master_leads", side_effect=RuntimeError("synthetic failure")):
                    live_dashboard._run_important_check_job(failed_job["job_id"])
                saved_failed = json.loads((jobs_dir / f"{failed_job['job_id']}.json").read_text(encoding="utf-8"))
                self.assertEqual("failed", saved_failed["status"])
                self.assertFalse(keep_path.exists())

                def check_master_leads_without_external_state(**kwargs):
                    return important_leads_workflow.check_master_leads(
                        **kwargs,
                        sendgrid_suppressions_path=state_dir / "sendgrid_suppressions.csv",
                        suppressed_path=state_dir / "suppressed.csv",
                        unsubscribed_path=state_dir / "unsubscribed.csv",
                        report_dir=state_dir,
                        summary_dir=check_runs_dir,
                        validate_deliverability=False,
                        reject_role_accounts=False,
                        reject_disposable=False,
                        persist_state=False,
                    )

                canceled_job = dict(base_job, job_id="check_auto_triage_canceled", cancel_requested=True)
                live_dashboard._save_important_check_job(canceled_job)
                with patch.object(live_dashboard, "check_master_leads", side_effect=check_master_leads_without_external_state):
                    live_dashboard._run_important_check_job(canceled_job["job_id"])
                saved_canceled = json.loads((jobs_dir / f"{canceled_job['job_id']}.json").read_text(encoding="utf-8"))
                self.assertEqual("canceled", saved_canceled["status"])
                self.assertEqual("skipped", saved_canceled["auto_triage_status"])
                self.assertFalse(keep_path.exists())

    def test_pipeline_reports_auto_triage_running_from_check_job(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            checked = tmp / "leads.csv"
            checked.write_text("Email,FirstName\none@example.com,One\n", encoding="utf-8")
            pipeline = live_dashboard._build_leads_pipeline_status(
                {
                    "important_output_label": str(checked),
                    "important_triage_keep_label": str(tmp / "missing_keep.csv"),
                    "important_triage_quarantine_label": str(tmp / "missing_quarantine.csv"),
                    "active_important_check_job": {
                        "status": "auto_triage_running",
                        "stage": "auto_triage",
                        "auto_triage_status": "running",
                        "auto_triage_processed_rows": 1,
                    },
                }
            )

        check_step = next(step for step in pipeline["steps"] if step["key"] == "check")
        triage_step = next(step for step in pipeline["steps"] if step["key"] == "triage")
        self.assertEqual("done", check_step["state"])
        self.assertEqual("active", triage_step["state"])
        self.assertEqual("Auto triage running.", triage_step["note"])

    def test_auto_dispatch_preview_marks_rebuild_blocked_when_sender_active(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            keep_path = tmp / "leads_triaged_keep.csv"
            rejected_path = tmp / "leads_triaged_reject.csv"
            self._write_csv(
                keep_path,
                ["Email", "FullName", "BookTitle"],
                [
                    {"Email": "one@examplebooks.com", "FullName": "One Author", "BookTitle": "One Book"},
                    {"Email": "two@examplebooks.com", "FullName": "Two Author", "BookTitle": ""},
                ],
            )
            self._write_csv(rejected_path, ["Email", "FullName", "BookTitle"], [])
            preview = {
                "preview_id": "dispatch_preview_blocked",
                "preview_path": str(tmp / "dispatch_preview_blocked.json"),
                "rows_written_per_queue": {"private_jc": 2, "sendgrid_1": 1},
                "suppressed_skipped": 0,
                "suppression_summary": {},
            }
            triage_report = {"keep_count": 2, "reject_count": 0, "quarantine_count": 0}

            with patch.object(
                live_dashboard.runtime_control,
                "list_active_sender_snapshots",
                return_value=[SimpleNamespace(name="sendgrid_annette", runtime_state="running")],
            ), patch.object(
                live_dashboard,
                "build_queue_safety_report",
                return_value={"safe": True, "unsafe_reasons": []},
            ):
                summary = live_dashboard._auto_dispatch_preview_summary(
                    preview=preview,
                    triage_report=triage_report,
                    checked_path=keep_path,
                    keep_path=keep_path,
                    rejected_path=rejected_path,
                )

        self.assertTrue(summary["any_sender_running"])
        self.assertEqual(["sendgrid_annette"], summary["active_profiles"])
        self.assertFalse(summary["manual_rebuild_allowed"])
        self.assertIn("active senders", summary["message"])

    def test_shard_block_when_senders_active(self) -> None:
        payload = live_dashboard.ShardLeadsPayload(
            cleaned_filename="cleaned_input.csv",
            shard_count=5,
            strategy="domain_balanced",
        )
        active_profiles = [
            SimpleNamespace(name="sendgrid_annette", runtime_state="running"),
            SimpleNamespace(name="sendgrid_jodi", runtime_state="cooldown"),
        ]

        with patch.object(live_dashboard.runtime_control, "list_active_sender_snapshots", return_value=active_profiles), patch.object(
            live_dashboard,
            "shard_cleaned_leads",
        ) as shard_cleaned_leads:
            response = live_dashboard.shard_leads(payload)

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(body["ok"])
        self.assertEqual("senders_active", body["error"])
        self.assertEqual(["sendgrid_annette", "sendgrid_jodi"], body["active_profiles"])
        self.assertEqual(
            {
                "sendgrid_annette": "running",
                "sendgrid_jodi": "cooldown",
            },
            body["states"],
        )
        shard_cleaned_leads.assert_not_called()

    def test_start_warm_private_jc_requires_explicit_confirmation(self) -> None:
        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "warm_private_jc_lane_status",
            return_value={"confirmed": False, "ready": False, "remaining": 0, "message": "Confirmation required."},
        ), patch.object(live_dashboard.runtime_control, "start_sender") as start_sender, patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": []},
        ), patch.object(live_dashboard, "_append_campaign_history"):
            response = live_dashboard.start_profile("private_jc_warm")

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertEqual("warm_confirmation_required", body["error"])
        start_sender.assert_not_called()

    def test_warm_confirm_endpoint_uses_latest_warm_preview_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            preview_path = Path(tmpdir) / "warm_email_preview.csv"
            preview_path.write_text("AuthorEmail\nsynthetic@example.com\n", encoding="utf-8")
            job = {"job_id": "warm-job", "warm_email_preview_path": str(preview_path), "check": {"upload_type": "warm_research"}}
            confirmation = {"confirmation_id": "warm-confirm", "row_count": 1, "message": "Confirmed."}
            with patch.object(live_dashboard, "_latest_completed_warm_check_job", return_value=job), patch.object(
                live_dashboard,
                "confirm_warm_private_jc_preview",
                return_value=confirmation,
            ) as confirm_preview, patch.object(live_dashboard, "_save_important_check_job"), patch.object(
                live_dashboard,
                "_combined_leads_status",
                return_value={"warm_private_jc_lane": {"confirmed": True}},
            ):
                response = live_dashboard.confirm_warm_research_private_jc()

        body = json.loads(response.body)
        self.assertTrue(body["ok"])
        confirm_preview.assert_called_once_with(preview_path=preview_path)

    def test_start_warm_private_jc_calls_runtime_only_when_confirmed(self) -> None:
        lane = {"confirmed": True, "ready": True, "remaining": 1, "message": "Ready."}
        with patch.dict(os.environ, {live_dashboard.DASHBOARD_AUTO_START_ENV_VAR: "0"}), patch.object(
            live_dashboard.runtime_control,
            "is_known_profile",
            return_value=True,
        ), patch.object(
            live_dashboard,
            "warm_private_jc_lane_status",
            return_value=lane,
        ), patch.object(live_dashboard, "_active_sender_names", return_value=set()), patch.object(
            live_dashboard.runtime_control,
            "start_sender",
            return_value=(True, "Started warm lane."),
        ) as start_sender, patch.object(live_dashboard, "_build_live_snapshot", return_value={"profiles": []}), patch.object(
            live_dashboard,
            "_append_campaign_history",
        ), patch.object(live_dashboard.time, "sleep"):
            response = live_dashboard.start_profile("private_jc_warm")

        self.assertEqual(200, response.status_code)
        start_sender.assert_called_once_with("private_jc_warm")

    def test_start_warm_private_jc_blocks_payload_mismatch_without_runtime_call(self) -> None:
        lane = {
            "confirmed": False,
            "ready": False,
            "remaining": 1,
            "integrity_reason": "warm_queue_payload_mismatch",
            "message": "Warm queue payload no longer matches confirmed field EmailSubject.",
        }
        with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
            live_dashboard,
            "warm_private_jc_lane_status",
            return_value=lane,
        ), patch.object(live_dashboard.runtime_control, "start_sender") as start_sender, patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"profiles": []},
        ), patch.object(live_dashboard, "_append_campaign_history"):
            response = live_dashboard.start_profile("private_jc_warm")

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertEqual("warm_queue_payload_mismatch", body["error"])
        start_sender.assert_not_called()

    def test_start_all_profile_set_does_not_include_warm_lane(self) -> None:
        self.assertNotIn("private_jc_warm", dashboard_core.START_ALL_PROFILES)


if __name__ == "__main__":
    unittest.main()
