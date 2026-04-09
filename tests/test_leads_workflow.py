from __future__ import annotations

import csv
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import leads_workflow
from sendgrid_hygiene import write_suppression_records


class LeadsWorkflowTests(unittest.TestCase):
    def test_detect_column_mapping_supports_common_variants(self) -> None:
        detected = leads_workflow.detect_column_mapping(["AuthorEmail", "Name", "title"])
        self.assertEqual("AuthorEmail", detected["mapping"]["email"])
        self.assertEqual("Name", detected["mapping"]["first_name"])
        self.assertEqual("title", detected["mapping"]["book_title"])
        self.assertFalse(detected["mapping_required"])

    def test_clean_uploaded_leads_removes_invalid_duplicates_and_active_suppressions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            upload_rows = [
                {"AuthorEmail": "astraproductionsbyjc@gmail.com", "Name": "Canary One", "title": "Book A"},
                {"AuthorEmail": "astraproductionsbyjc@gmail.com", "Name": "Canary Two", "title": "Book B"},
                {"AuthorEmail": "keep@example.com", "Name": "Keep Me", "title": "Book C"},
                {"AuthorEmail": "dup@example.com", "Name": "Dupe One", "title": "Book D"},
                {"AuthorEmail": "dup@example.com", "Name": "Dupe Two", "title": "Book E"},
                {"AuthorEmail": "blocked@example.com", "Name": "Blocked", "title": "Book F"},
                {"AuthorEmail": "expired@example.com", "Name": "Expired", "title": "Book G"},
                {"AuthorEmail": "not an email", "Name": "Bad", "title": "Book H"},
            ]
            with self._patched_runtime(base, shard_count=5):
                self._write_upload_csv(base / "source.csv", upload_rows)
                write_suppression_records(
                    base / "state" / "sendgrid_suppressions.csv",
                    {
                        "blocked@example.com": {
                            "email": "blocked@example.com",
                            "status": "Blocked",
                            "code": "550",
                            "reason": "mailbox full",
                            "last_seen_utc": "2026-03-24T00:00:00+00:00",
                            "is_permanent": "false",
                            "ttl_until_utc": "2099-03-24T00:00:00+00:00",
                        },
                        "expired@example.com": {
                            "email": "expired@example.com",
                            "status": "Blocked",
                            "code": "550",
                            "reason": "old temporary block",
                            "last_seen_utc": "2026-03-01T00:00:00+00:00",
                            "is_permanent": "false",
                            "ttl_until_utc": "2026-03-02T00:00:00+00:00",
                        },
                    },
                )
                upload = leads_workflow.save_uploaded_csv("source.csv", (base / "source.csv").read_bytes())
                report = leads_workflow.clean_uploaded_leads(upload["saved_filename"])

                cleaned_path = base / "cleaned" / report["cleaned_filename"]
                with cleaned_path.open(newline="", encoding="utf-8") as handle:
                    cleaned_rows = list(csv.DictReader(handle))

        kept_emails = [row["Email"] for row in cleaned_rows]
        self.assertEqual(5, len(cleaned_rows))
        self.assertEqual(2, kept_emails.count("astraproductionsbyjc@gmail.com"))
        self.assertIn("keep@example.com", kept_emails)
        self.assertIn("dup@example.com", kept_emails)
        self.assertIn("expired@example.com", kept_emails)
        self.assertEqual(1, report["reason_counts"]["invalid_email"])
        self.assertEqual(1, report["reason_counts"]["duplicate_email"])
        self.assertEqual(1, report["reason_counts"]["suppressed"])

    def test_shard_cleaned_leads_domain_balanced_distribution_is_even(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            rows = []
            for index in range(10):
                rows.append({"Email": f"gmail{index}@gmail.com", "FirstName": f"Gmail {index}", "BookTitle": ""})
            for index in range(5):
                rows.append({"Email": f"yahoo{index}@yahoo.com", "FirstName": f"Yahoo {index}", "BookTitle": ""})

            with self._patched_runtime(base, shard_count=5):
                self._write_cleaned_csv(base / "cleaned" / "cleaned_input.csv", rows)
                report = leads_workflow.shard_cleaned_leads("cleaned_input.csv", shard_count=5, strategy="domain_balanced")

                gmail_counts = []
                shard_sizes = []
                for index in range(1, 6):
                    shard_path = base / "shards" / f"recipients_sendgrid_{index}.csv"
                    with shard_path.open(newline="", encoding="utf-8") as handle:
                        shard_rows = list(csv.DictReader(handle))
                    shard_sizes.append(len(shard_rows))
                    gmail_counts.append(sum(1 for row in shard_rows if row["Email"].endswith("@gmail.com")))

        self.assertEqual(5, len(report["per_shard"]))
        self.assertLessEqual(max(shard_sizes) - min(shard_sizes), 1)
        self.assertLessEqual(max(gmail_counts) - min(gmail_counts), 1)
        self.assertTrue(all(size == 4 for size in shard_sizes))

    def test_preview_shard_cleaned_leads_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            rows = [
                {"Email": "astraproductionsbyjc@gmail.com", "FirstName": "Canary", "BookTitle": ""},
                {"Email": "one@gmail.com", "FirstName": "One", "BookTitle": ""},
                {"Email": "two@yahoo.com", "FirstName": "Two", "BookTitle": ""},
                {"Email": "three@outlook.com", "FirstName": "Three", "BookTitle": ""},
            ]

            with self._patched_runtime(base, shard_count=2):
                self._write_cleaned_csv(base / "cleaned" / "cleaned_input.csv", rows)
                existing_rows = [{"Email": "existing@example.com", "FirstName": "Existing", "BookTitle": ""}]
                self._write_cleaned_csv(base / "shards" / "recipients_sendgrid_1.csv", existing_rows)
                self._write_cleaned_csv(base / "shards" / "recipients_sendgrid_2.csv", existing_rows)
                before_one = (base / "shards" / "recipients_sendgrid_1.csv").read_text(encoding="utf-8")
                before_two = (base / "shards" / "recipients_sendgrid_2.csv").read_text(encoding="utf-8")

                preview = leads_workflow.preview_shard_cleaned_leads("cleaned_input.csv", shard_count=2, strategy="domain_balanced")

                after_one = (base / "shards" / "recipients_sendgrid_1.csv").read_text(encoding="utf-8")
                after_two = (base / "shards" / "recipients_sendgrid_2.csv").read_text(encoding="utf-8")

        self.assertTrue(preview["preview_only"])
        self.assertEqual(before_one, after_one)
        self.assertEqual(before_two, after_two)

    def test_preview_plan_counts_match_write_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            rows = []
            for index in range(8):
                rows.append({"Email": f"gmail{index}@gmail.com", "FirstName": f"Gmail {index}", "BookTitle": ""})
            for index in range(4):
                rows.append({"Email": f"yahoo{index}@yahoo.com", "FirstName": f"Yahoo {index}", "BookTitle": ""})

            with self._patched_runtime(base, shard_count=3):
                self._write_cleaned_csv(base / "cleaned" / "cleaned_input.csv", rows)

                preview = leads_workflow.preview_shard_cleaned_leads("cleaned_input.csv", shard_count=3, strategy="domain_balanced")
                report = leads_workflow.shard_cleaned_leads("cleaned_input.csv", shard_count=3, strategy="domain_balanced")

        self.assertTrue(preview["preview_only"])
        self.assertFalse(report["preview_only"])
        self.assertEqual(preview["total_rows"], report["total_rows"])
        self.assertEqual(preview["canary_rows_injected"], report["canary_rows_injected"])
        self.assertEqual(
            [item["count"] for item in preview["per_shard"]],
            [item["count"] for item in report["per_shard"]],
        )
        self.assertEqual(
            [item["top_domains"] for item in preview["per_shard"]],
            [item["top_domains"] for item in report["per_shard"]],
        )

    def _patched_runtime(self, base: Path, shard_count: int):
        uploads = base / "uploads"
        cleaned = base / "cleaned"
        state = base / "state"
        shards = base / "shards"
        backups = state / "backups" / "leads"
        profiles = {
            f"sendgrid_{index}": {
                "provider": "sendgrid",
                "csv": f"recipients_sendgrid_{index}.csv",
                "always_send": "astraproductionsbyjc@gmail.com",
            }
            for index in range(1, shard_count + 1)
        }
        stack = ExitStack()
        stack.enter_context(
            patch.multiple(
                leads_workflow,
                ROOT=base,
                UPLOADS_DIR=uploads,
                CLEANED_DIR=cleaned,
                REPORTS_DIR=state,
                BACKUP_ROOT=backups,
                LEADS_STATE_PATH=state / "leads_dashboard_state.json",
                LATEST_SHARD_REPORT_PATH=state / "shard_report.json",
                SENDGRID_SUPPRESSIONS_PATH=state / "sendgrid_suppressions.csv",
                PROFILES=profiles,
            )
        )
        stack.enter_context(patch.object(leads_workflow.settings, "SHARDS_DIR", shards))
        stack.enter_context(
            patch.object(
                leads_workflow.settings,
                "maybe_seed_file",
                side_effect=lambda target, legacy=None: target,
            )
        )
        return stack

    def _write_upload_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["AuthorEmail", "Name", "title"])
            writer.writeheader()
            writer.writerows(rows)

    def _write_cleaned_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName", "BookTitle"])
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
