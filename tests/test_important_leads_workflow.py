from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from important_leads_workflow import check_master_leads, dispatch_master_leads


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class ImportantLeadsWorkflowTests(unittest.TestCase):
    def test_check_master_leads_preserves_extra_columns_and_counts_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            report_dir = tmp / "reports"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            write_csv(
                input_path,
                ["First Name", "Email Address", "Source"],
                [
                    {"First Name": " Alice ", "Email Address": " Alice@Gmial.com ", "Source": "list-a"},
                    {"First Name": "Alice Dup", "Email Address": "alice@gmail.com", "Source": "dup"},
                    {"First Name": "Supp", "Email Address": "suppressed@example.com", "Source": "list-a"},
                    {"First Name": "Bad", "Email Address": "not-an-email", "Source": "list-a"},
                    {"First Name": "Two", "Email Address": "one@example.com;two@example.com", "Source": "list-a"},
                    {"First Name": "Bob", "Email Address": "bob@example.com", "Source": "list-b"},
                ],
            )
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@example.com"}])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                report_dir=report_dir,
                persist_state=False,
            )

            self.assertEqual(report["input_rows"], 6)
            self.assertEqual(report["cleaned_rows"], 2)
            self.assertEqual(report["duplicates_removed"], 1)
            self.assertEqual(report["invalid_removed"], 1)
            self.assertEqual(report["suppressed_removed"], 1)
            self.assertEqual(report["suspicious_flagged"], 1)
            self.assertEqual(report["safe_fixes_applied"], 1)
            self.assertEqual(report["output_fieldnames"], ["FirstName", "Email", "Source"])

            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["FirstName"], "Alice")
            self.assertEqual(rows[0]["Email"], "alice@gmail.com")
            self.assertEqual(rows[0]["Source"], "list-a")
            self.assertEqual(rows[1]["Email"], "bob@example.com")

            with rejected_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rejected = list(reader)
            self.assertEqual(len(rejected), 4)
            self.assertIn("Reason", reader.fieldnames or [])

    def test_dispatch_master_leads_uses_channel_specific_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(
                master_path,
                ["FirstName", "Email", "Source"],
                [
                    {"FirstName": "Fresh", "Email": "fresh-both@example.com", "Source": "master"},
                    {"FirstName": "Astra Sent", "Email": "astra-sent@example.com", "Source": "master"},
                    {"FirstName": "SendGrid Sent", "Email": "sg-sent@example.com", "Source": "master"},
                    {"FirstName": "Astra Queue", "Email": "queued-astra@example.com", "Source": "master"},
                    {"FirstName": "SendGrid Queue", "Email": "queued-sg@example.com", "Source": "master"},
                    {"FirstName": "Both Sent", "Email": "both-sent@example.com", "Source": "master"},
                    {"FirstName": "Both Queue", "Email": "both-queued@example.com", "Source": "master"},
                    {"FirstName": "Supp", "Email": "suppressed@example.com", "Source": "master"},
                    {"FirstName": "Fresh Duplicate", "Email": "fresh-both@example.com", "Source": "dup"},
                ],
            )
            write_csv(
                jc_queue,
                ["Email", "AuthorName"],
                [
                    {"Email": "queued-astra@example.com", "AuthorName": "Queued Astra"},
                    {"Email": "both-queued@example.com", "AuthorName": "Both Queue"},
                ],
            )
            write_csv(
                sg_queues[0],
                ["Email", "AuthorName"],
                [{"Email": "queued-sg@example.com", "AuthorName": "Queued SG"}],
            )
            write_csv(
                sg_queues[1],
                ["Email", "AuthorName"],
                [{"Email": "both-queued@example.com", "AuthorName": "Both Queue"}],
            )
            for path in sg_queues[2:]:
                write_csv(path, ["Email", "AuthorName"], [])
            write_csv(
                logs[0],
                ["Email", "Status"],
                [
                    {"Email": "astra-sent@example.com", "Status": "SENT"},
                    {"Email": "both-sent@example.com", "Status": "SENT"},
                ],
            )
            write_csv(logs[1], ["Email", "Status"], [{"Email": "sg-sent@example.com", "Status": "SENT"}])
            write_csv(logs[2], ["Email", "Status"], [{"Email": "both-sent@example.com", "Status": "SENT"}])
            for path in logs[3:]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@example.com"}])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            report = dispatch_master_leads(
                master_path=master_path,
                rejected_path=rejected_path,
                require_stopped=False,
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=False,
            )

            self.assertEqual(report["master_read"], 9)
            self.assertEqual(report["added_astra"], 3)
            self.assertEqual(report["skipped_astra_already_sent"], 2)
            self.assertEqual(report["skipped_astra_already_queued"], 2)
            self.assertEqual(report["added_sendgrid"], 3)
            self.assertEqual(report["skipped_sendgrid_already_sent"], 2)
            self.assertEqual(report["skipped_sendgrid_already_queued"], 2)
            self.assertEqual(report["suppressed_skipped"], 1)
            self.assertEqual(report["duplicate_master_skipped"], 1)
            self.assertEqual(report["assigned_sg1"], 1)
            self.assertEqual(report["assigned_sg2"], 1)
            self.assertEqual(report["assigned_sg3"], 1)
            self.assertEqual(report["assigned_sg4"], 0)
            self.assertEqual(report["assigned_sg5"], 0)
            self.assertEqual(report["skipped_both"], 2)

            with jc_queue.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                jc_rows = list(reader)
            self.assertEqual(len(jc_rows), 5)
            self.assertIn("Source", reader.fieldnames or [])
            jc_emails = {row["Email"] for row in jc_rows}
            self.assertIn("fresh-both@example.com", jc_emails)
            self.assertIn("sg-sent@example.com", jc_emails)
            self.assertIn("queued-sg@example.com", jc_emails)
            self.assertNotIn("astra-sent@example.com", jc_emails)
            self.assertIn("queued-astra@example.com", jc_emails)

            all_sg_emails: list[str] = []
            for path in sg_queues:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.DictReader(handle)
                    sg_rows = list(reader)
                    self.assertIn("Source", reader.fieldnames or [])
                    all_sg_emails.extend(row["Email"] for row in sg_rows)

            self.assertEqual(len(all_sg_emails), len(set(all_sg_emails)))
            self.assertIn("fresh-both@example.com", all_sg_emails)
            self.assertIn("astra-sent@example.com", all_sg_emails)
            self.assertIn("queued-astra@example.com", all_sg_emails)
            self.assertNotIn("sg-sent@example.com", all_sg_emails)
            self.assertIn("queued-sg@example.com", all_sg_emails)

            self.assertTrue(Path(report["backup_dir"]).exists())
            self.assertTrue((Path(report["backup_dir"]) / jc_queue.name).exists())


if __name__ == "__main__":
    unittest.main()
