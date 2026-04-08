from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import live_dashboard
from important_leads_workflow import ImportantLeadsCheckError


class LiveDashboardTests(unittest.TestCase):
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
                "FirstName,Email\nJane,jane@example.com\nJohn,john@example.com\n",
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
                input_path=str(input_path),
                verified_path=str(verified_path),
                rejected_path=str(rejected_path),
                quarantine_path=str(quarantine_path),
            )
            fake_report = {
                "input_label": str(input_path),
                "verified_label": str(verified_path),
                "rejected_label": str(rejected_path),
                "quarantine_label": str(quarantine_path),
                "keep_count": 1,
                "reject_count": 0,
                "quarantine_count": 0,
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
                "verify_master_leads",
                return_value=fake_report,
            ) as verify_master_leads, patch.object(
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
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            self.assertIn("Verified", body["message"])
            kwargs = verify_master_leads.call_args.kwargs
            self.assertEqual(input_path.resolve(), kwargs["input_path"])
            self.assertEqual(verified_path.resolve(), kwargs["verified_path"])
            self.assertEqual(rejected_path.resolve(), kwargs["rejected_path"])
            self.assertEqual(quarantine_path.resolve(), kwargs["quarantine_path"])
            save_state.assert_called()

    def test_dispatch_important_leads_uses_selected_source_mode(self) -> None:
        with tempfile.TemporaryDirectory(dir=live_dashboard.settings.APP_ROOT) as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            verified_path = tmp / "leads_verified.csv"
            input_path.write_text("FirstName,Email\nLegacy,legacy@example.com\n", encoding="utf-8")
            verified_path.write_text("FirstName,Email,Status\nJane,jane@example.com,KEEP\n", encoding="utf-8")
            payload = live_dashboard.ImportantLeadPathsPayload(
                input_path=str(input_path),
                output_path=str(output_path),
                rejected_path=str(rejected_path),
                dispatch_source_mode="verified",
            )
            fake_report = {
                "generated_at_utc": "2026-04-09T00:00:00+00:00",
                "master_read": 1,
                "dispatch_source_mode": "verified",
                "dispatch_source_path": str(verified_path),
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_block_reason": "",
                "verification_required": True,
                "verification_file_mtime": "2026-04-09T00:00:00+00:00",
                "added_astra": 1,
                "added_sendgrid": 1,
                "skipped_both": 0,
                "suppressed_skipped": 0,
                "duplicate_master_skipped": 0,
                "assigned_sg1": 1,
                "assigned_sg2": 0,
                "assigned_sg3": 0,
                "assigned_sg4": 0,
                "assigned_sg5": 0,
                "final_queue_counts": {"jc": 1, "sg1": 1, "sg2": 0, "sg3": 0, "sg4": 0, "sg5": 0},
                "queue_headers": ["Email", "FirstName"],
                "assigned_preview_rows": [],
                "dispatch_source_preview_rows": [],
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
            ), patch.object(live_dashboard, "save_state") as save_state, patch.object(
                live_dashboard,
                "dispatch_master_leads",
                return_value=fake_report,
            ) as dispatch_master_leads, patch.object(
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
                response = live_dashboard.dispatch_important_leads(payload)

            body = json.loads(response.body)
            self.assertEqual(200, response.status_code)
            self.assertTrue(body["ok"])
            kwargs = dispatch_master_leads.call_args.kwargs
            self.assertEqual("verified", kwargs["dispatch_source_mode"])
            self.assertEqual(
                Path(live_dashboard.settings.APP_ROOT / "_important" / "leads_verified.csv").resolve(),
                kwargs["verified_path"],
            )
            save_state.assert_called()

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
                "check": 2,
                "dispatch": 3,
                "dispatch_source_mode": "verified",
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
        ):
            response = live_dashboard.leads_status()

        body = json.loads(response.body)
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "shard": 1,
                "check": 2,
                "dispatch": 3,
                "verify": 4,
                "dispatch_source_mode": "verified",
                "dispatch_source_path": "_important/leads_verified.csv",
                "dispatch_source_exists": True,
                "dispatch_source_row_count": 1,
                "dispatch_eligible_row_count": 1,
                "dispatch_block_reason": "",
                "verification_required": True,
                "verification_file_mtime": "2026-04-09T00:00:00+00:00",
            },
            body["status"],
        )

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
