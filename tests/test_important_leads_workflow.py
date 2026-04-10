from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import important_leads_verify
import important_leads_workflow
from important_leads_workflow import check_master_leads, dispatch_master_leads


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class ImportantLeadsWorkflowTests(unittest.TestCase):
    def test_saved_windows_paths_reset_to_local_important_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            important_dir = root / "_important"
            important_dir.mkdir()
            defaults = {
                "leadschecker.csv": "FullName,FirstName,Email\n",
                "leads.csv": "FullName,FirstName,Email\n",
                "leads_rejected.csv": "Email,reject_code\n",
                "leads_verified.csv": "FullName,FirstName,Email,Status\n",
                "leads_verify_rejected.csv": "FullName,FirstName,Email,Status\n",
                "leads_quarantine.csv": "FullName,FirstName,Email,Status\n",
            }
            for name, content in defaults.items():
                (important_dir / name).write_text(content, encoding="utf-8")

            poisoned_state = {
                important_leads_workflow.IMPORTANT_PATHS_STATE_KEY: {
                    "input_path": "/mnt/d/VS/email automation/_important/leadschecker.csv",
                    "output_path": "/mnt/d/VS/email automation/_important/leads.csv",
                    "rejected_path": "C:\\VS\\email automation\\_important\\leads_rejected.csv",
                },
                important_leads_verify.VERIFY_PATHS_STATE_KEY: {
                    "input_path": "/mnt/d/VS/email automation/_important/leads.csv",
                    "verified_path": "leads_verified.csv",
                    "rejected_path": "/mnt/d/VS/email automation/_important/leads_verify_rejected.csv",
                    "quarantine_path": "D:\\VS\\email automation\\_important\\leads_quarantine.csv",
                },
            }

            with patch.object(important_leads_workflow.settings, "APP_ROOT", root), patch.object(
                important_leads_workflow, "IMPORTANT_DIR", important_dir
            ), patch.object(
                important_leads_workflow, "MASTER_INPUT_PATH", important_dir / "leadschecker.csv"
            ), patch.object(
                important_leads_workflow, "MASTER_OUTPUT_PATH", important_dir / "leads.csv"
            ), patch.object(
                important_leads_workflow, "MASTER_REJECTED_PATH", important_dir / "leads_rejected.csv"
            ), patch.object(
                important_leads_workflow, "load_state", return_value=poisoned_state
            ), patch.object(
                important_leads_verify.settings, "APP_ROOT", root
            ), patch.object(
                important_leads_verify, "IMPORTANT_DIR", important_dir
            ), patch.object(
                important_leads_verify, "DEFAULT_INPUT_PATH", important_dir / "leads.csv"
            ), patch.object(
                important_leads_verify, "DEFAULT_VERIFIED_PATH", important_dir / "leads_verified.csv"
            ), patch.object(
                important_leads_verify, "DEFAULT_REJECTED_PATH", important_dir / "leads_verify_rejected.csv"
            ), patch.object(
                important_leads_verify, "DEFAULT_QUARANTINE_PATH", important_dir / "leads_quarantine.csv"
            ), patch.object(
                important_leads_verify, "load_state", return_value=poisoned_state
            ):
                self.assertEqual(
                    {
                        "input_path": "_important/leadschecker.csv",
                        "output_path": "_important/leads.csv",
                        "rejected_path": "_important/leads_rejected.csv",
                    },
                    important_leads_workflow.important_leads_path_state(),
                )
                self.assertEqual(
                    {
                        "input_path": "_important/leads.csv",
                        "verified_path": "_important/leads_verified.csv",
                        "rejected_path": "_important/leads_verify_rejected.csv",
                        "quarantine_path": "_important/leads_quarantine.csv",
                    },
                    important_leads_verify.important_leads_verify_path_state(),
                )

    def test_check_master_leads_hardens_rows_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            report_dir = tmp / "reports"
            summary_dir = tmp / "check_runs"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            disposable_domains_path = tmp / "disposable_domains.txt"

            input_path.write_text(
                "\ufefffull_name;author_email;Source\n"
                " Alice Example ; Alice@Gmial.com ;list-a\n"
                "Alice Rich;ALICE@gmail.com;list-a-dup\n"
                "Support;support@gmail.com;role\n"
                "Temp;temp@mailinator.com;temp\n"
                "Supp;suppressed@gmail.com;supp\n"
                "Bad;not-an-email;bad\n"
                "Maybe;writer@gmaill.com;typo\n"
                "Bob;bob@yahoo.com;good\n"
                "\n",
                encoding="utf-8",
            )
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@gmail.com"}])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])
            disposable_domains_path.write_text("mailinator.com\n", encoding="utf-8")

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                report_dir=report_dir,
                summary_dir=summary_dir,
                validate_deliverability=False,
                reject_role_accounts=True,
                reject_disposable=True,
                disposable_domains_path=disposable_domains_path,
                persist_state=False,
            )

            self.assertEqual(report["input_rows"], 9)
            self.assertEqual(report["total_input_rows"], 9)
            self.assertEqual(report["cleaned_rows"], 2)
            self.assertEqual(report["valid_rows"], 2)
            self.assertEqual(report["rejected_rows"], 7)
            self.assertEqual(report["duplicates_removed"], 1)
            self.assertEqual(report["suppressed_removed"], 1)
            self.assertEqual(report["role_accounts_removed"], 1)
            self.assertEqual(report["disposable_removed"], 1)
            self.assertEqual(report["invalid_syntax_removed"], 1)
            self.assertEqual(report["suspicious_flagged"], 1)
            self.assertEqual(report["corrected_rows"], 1)
            self.assertEqual(report["safe_fixes_applied"], 1)
            self.assertEqual(report["blank_rows"], 1)
            self.assertEqual(report["output_fieldnames"], ["FullName", "FirstName", "Email", "Source"])

            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["FullName"], "Alice Example")
            self.assertEqual(rows[0]["FirstName"], "Alice")
            self.assertEqual(rows[0]["Email"], "alice@gmail.com")
            self.assertEqual(rows[0]["Source"], "list-a")
            self.assertEqual(rows[1]["Email"], "bob@yahoo.com")

            with rejected_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rejected = list(reader)
            self.assertEqual(len(rejected), 7)
            rejected_codes = [row["reject_code"] for row in rejected]
            self.assertIn("BLANK_ROW", rejected_codes)
            self.assertIn("DUPLICATE_IN_BATCH", rejected_codes)
            self.assertIn("ROLE_ACCOUNT", rejected_codes)
            self.assertIn("DISPOSABLE_DOMAIN", rejected_codes)
            self.assertIn("SUPPRESSED", rejected_codes)
            self.assertIn("INVALID_EMAIL_SYNTAX", rejected_codes)
            self.assertIn("UNKNOWN_DOMAIN_TYPO", rejected_codes)
            self.assertIn("normalized_email", reader.fieldnames or [])
            self.assertIn("correction_applied", reader.fieldnames or [])
            self.assertIn("correction_reason", reader.fieldnames or [])
            self.assertIn("reject_reason", reader.fieldnames or [])

            summary_path = Path(report["summary_path"])
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["total_input_rows"], 9)
            self.assertEqual(summary["valid_rows"], 2)
            self.assertEqual(summary["rejected_rows"], 7)
            self.assertEqual(summary["duplicates_removed"], 1)
            self.assertEqual(summary["suppressed_removed"], 1)
            self.assertEqual(summary["role_accounts_removed"], 1)
            self.assertEqual(summary["disposable_removed"], 1)
            self.assertEqual(summary["invalid_syntax_removed"], 1)
            self.assertEqual(summary["blank_rows"], 1)
            self.assertFalse(summary["deliverability_enabled"])

    def test_check_master_leads_accepts_two_column_no_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "rejected.csv"
            report_dir = tmp / "reports"
            summary_dir = tmp / "check_runs"

            input_path.write_text(
                "Jane,jane@gmail.com\nJohn, JOHN@YAHOO.COM \n",
                encoding="utf-8",
            )

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                report_dir=report_dir,
                summary_dir=summary_dir,
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

            self.assertEqual(report["input_rows"], 2)
            self.assertEqual(report["cleaned_rows"], 2)
            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(rows[0]["Email"], "jane@gmail.com")
            self.assertEqual(rows[1]["Email"], "john@yahoo.com")

    def test_check_master_leads_marks_undeliverable_domains(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "rejected.csv"
            report_dir = tmp / "reports"
            summary_dir = tmp / "check_runs"

            write_csv(
                input_path,
                ["FullName", "FirstName", "Email"],
                [{"FullName": "Test Person", "FirstName": "Test", "Email": "nobody@example.com"}],
            )

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                report_dir=report_dir,
                summary_dir=summary_dir,
                validate_deliverability=True,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

            self.assertEqual(report["cleaned_rows"], 0)
            self.assertEqual(report["undeliverable_removed"], 1)
            self.assertEqual(report["reason_counts"]["UNDELIVERABLE_DOMAIN"], 1)

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
                ["FullName", "FirstName", "Email", "Source"],
                [
                    {"FullName": "Fresh Person", "FirstName": "Fresh", "Email": "fresh-both@example.com", "Source": "master"},
                    {"FullName": "Astra Sent Person", "FirstName": "Astra Sent", "Email": "astra-sent@example.com", "Source": "master"},
                    {"FullName": "SendGrid Sent Person", "FirstName": "SendGrid Sent", "Email": "sg-sent@example.com", "Source": "master"},
                    {"FullName": "Astra Queue Person", "FirstName": "Astra Queue", "Email": "queued-astra@example.com", "Source": "master"},
                    {"FullName": "SendGrid Queue Person", "FirstName": "SendGrid Queue", "Email": "queued-sg@example.com", "Source": "master"},
                    {"FullName": "Both Sent Person", "FirstName": "Both Sent", "Email": "both-sent@example.com", "Source": "master"},
                    {"FullName": "Both Queue Person", "FirstName": "Both Queue", "Email": "both-queued@example.com", "Source": "master"},
                    {"FullName": "Supp Person", "FirstName": "Supp", "Email": "suppressed@example.com", "Source": "master"},
                    {"FullName": "Fresh Duplicate Person", "FirstName": "Fresh Duplicate", "Email": "fresh-both@example.com", "Source": "dup"},
                ],
            )
            write_csv(
                jc_queue,
                ["Email", "FirstName"],
                [
                    {"Email": "queued-astra@example.com", "FirstName": "Queued Astra"},
                    {"Email": "both-queued@example.com", "FirstName": "Both Queue"},
                ],
            )
            write_csv(
                sg_queues[0],
                ["Email", "FirstName"],
                [{"Email": "queued-sg@example.com", "FirstName": "Queued SG"}],
            )
            write_csv(
                sg_queues[1],
                ["Email", "FirstName"],
                [{"Email": "both-queued@example.com", "FirstName": "Both Queue"}],
            )
            for path in sg_queues[2:]:
                write_csv(path, ["Email", "FirstName"], [])
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
                dispatch_source_mode="cleaned",
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
            self.assertEqual(report["dispatch_source_mode"], "cleaned")
            self.assertEqual(report["dispatch_source_row_count"], 9)
            self.assertEqual(report["dispatch_eligible_row_count"], 9)
            self.assertFalse(report["verification_required"])
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
            self.assertIn("FirstName", reader.fieldnames or [])
            self.assertNotIn("AuthorName", reader.fieldnames or [])
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
                    self.assertIn("FirstName", reader.fieldnames or [])
                    self.assertNotIn("AuthorName", reader.fieldnames or [])
                    all_sg_emails.extend(row["Email"] for row in sg_rows)

            self.assertEqual(len(all_sg_emails), len(set(all_sg_emails)))
            self.assertIn("fresh-both@example.com", all_sg_emails)
            self.assertIn("astra-sent@example.com", all_sg_emails)
            self.assertIn("queued-astra@example.com", all_sg_emails)
            self.assertNotIn("sg-sent@example.com", all_sg_emails)
            self.assertIn("queued-sg@example.com", all_sg_emails)

            self.assertTrue(Path(report["backup_dir"]).exists())
            self.assertTrue((Path(report["backup_dir"]) / jc_queue.name).exists())

    def test_dispatch_master_leads_verified_mode_uses_verified_keep_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(
                verified_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Verified One Person", "FirstName": "Verified", "Email": "verified1@example.com", "Status": "KEEP"},
                    {"FullName": "Verified Two Person", "FirstName": "Verified", "Email": "verified2@example.com", "Status": "KEEP"},
                    {"FullName": "Rejected Person", "FirstName": "Rejected", "Email": "rejected@example.com", "Status": "REJECT"},
                    {"FullName": "Quarantine Person", "FirstName": "Q", "Email": "quarantine@example.com", "Status": "QUARANTINE"},
                ],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            report = dispatch_master_leads(
                master_path=master_path,
                verified_path=verified_path,
                rejected_path=rejected_path,
                dispatch_source_mode="verified",
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

            self.assertEqual(report["dispatch_source_mode"], "verified")
            self.assertEqual(report["master_read"], 4)
            self.assertEqual(report["dispatch_source_row_count"], 4)
            self.assertEqual(report["dispatch_eligible_row_count"], 2)
            self.assertTrue(report["verification_required"])
            self.assertEqual(report["added_astra"], 2)
            self.assertEqual(report["added_sendgrid"], 2)
            with jc_queue.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual({row["Email"] for row in rows}, {"verified1@example.com", "verified2@example.com"})

    def test_dispatch_master_leads_verified_mode_blocks_without_keep_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(
                verified_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Rejected Person", "FirstName": "Rejected", "Email": "rejected@example.com", "Status": "REJECT"},
                    {"FullName": "Quarantine Person", "FirstName": "Quarantine", "Email": "quarantine@example.com", "Status": "QUARANTINE"},
                ],
            )
            write_csv(tmp / "recipients_private_jc.csv", ["Email", "FirstName"], [])
            for path in [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]:
                write_csv(path, ["Email", "FirstName"], [])
            for path in [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            with self.assertRaisesRegex(ValueError, "no KEEP rows"):
                dispatch_master_leads(
                    master_path=master_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="verified",
                    require_stopped=False,
                    jc_queue_path=tmp / "recipients_private_jc.csv",
                    sendgrid_queue_paths=[tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)],
                    jc_log_path=tmp / "private_jc_log.csv",
                    sendgrid_log_paths=[tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)],
                    sendgrid_suppressions_path=sendgrid_suppressions_path,
                    suppressed_path=suppressed_path,
                    unsubscribed_path=unsubscribed_path,
                    backup_root=backup_root,
                    report_dir=report_dir,
                    persist_state=False,
                )

    def test_dispatch_master_leads_verified_mode_blocks_header_only_verified_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(verified_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            with self.assertRaisesRegex(ValueError, "Verified dispatch source is empty"):
                dispatch_master_leads(
                    master_path=master_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="verified",
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

    def test_dispatch_master_leads_verified_mode_blocks_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "missing_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            with self.assertRaisesRegex(ValueError, "Verified dispatch source missing"):
                dispatch_master_leads(
                    master_path=master_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="verified",
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


if __name__ == "__main__":
    unittest.main()
