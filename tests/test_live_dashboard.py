from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import live_dashboard


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
                input_text="FirstName,Email\r\nJane,jane@example.com\r\n",
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
            self.assertEqual("FirstName,Email\nJane,jane@example.com\n", run_input_path.read_text(encoding="utf-8"))
            self.assertEqual(run_input_path.resolve(), kwargs["input_path"])
            self.assertEqual(output_path.resolve(), kwargs["output_path"])
            self.assertEqual(rejected_path.resolve(), kwargs["rejected_path"])
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
