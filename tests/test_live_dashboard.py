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
                patch.object(live_dashboard.runtime_control, "list_active_sender_snapshots", return_value=[]),
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
                patch.object(live_dashboard.runtime_control, "list_active_sender_snapshots", return_value=[]),
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

    def test_start_profile_blocks_when_message_readiness_is_not_pass(self) -> None:
        safe_report = {"safe": True, "unsafe_reasons": []}
        for status in ("NOT RUN", "STALE", "FAIL"):
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
            ) as start_sender:
                response = live_dashboard.start_profile("sendgrid_annette")

            self.assertEqual(409, response.status_code)
            body = json.loads(response.body)
            self.assertEqual("start_preconditions_failed", body["error"])
            self.assertEqual(status, body["message_readiness_status"])
            self.assertIn(status, " ".join(body["blocked_reasons"]))
            start_sender.assert_not_called()

    def test_start_profile_blocks_stale_or_temp_lead_state(self) -> None:
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
        ) as start_sender:
            response = live_dashboard.start_profile("sendgrid_annette")

        self.assertEqual(409, response.status_code)
        body = json.loads(response.body)
        self.assertIn("temp artifact", " ".join(body["blocked_reasons"]))
        start_sender.assert_not_called()

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
            self.assertEqual(output_path.resolve(), kwargs["output_path"])
            self.assertEqual(rejected_path.resolve(), kwargs["rejected_path"])
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

            with patch.object(live_dashboard, "IMPORTANT_LEADS_CHECK_JOBS", jobs_dir), patch.object(
                live_dashboard,
                "_execute_important_check",
                return_value=report,
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
            self.assertEqual(2, live_dashboard._count_csv_rows(keep_path))
            self.assertEqual(1, live_dashboard._count_csv_rows(triage_reject_path))
            self.assertTrue(quarantine_path.exists())
            keep_rows = self._read_csv_rows(keep_path)
            self.assertEqual("Signals at Dawn", keep_rows[0]["BookTitle"])
            self.assertEqual("Alpha Baker", keep_rows[0]["AuthorName"])
            self.assertEqual("Synthetic opening.", keep_rows[0]["PersonalizedOpeningLine"])
            self.assertEqual("Synthetic fit.", keep_rows[0]["WhyAstraFit"])
            self.assertEqual(shard_before, shard_path.read_text(encoding="utf-8"))
            preview_dispatch.assert_called_once()
            self.assertEqual(keep_path, preview_dispatch.call_args.kwargs["triaged_keep_path"])
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


if __name__ == "__main__":
    unittest.main()
