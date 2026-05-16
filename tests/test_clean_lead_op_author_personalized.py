from __future__ import annotations

import csv
import io
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

from openpyxl import Workbook

from tools.clean_lead_op_author_personalized import OUTPUT_COLUMNS, clean_workbooks, print_summary


class LeadOpAuthorPersonalizedCleanerTests(unittest.TestCase):
    def test_clean_workbooks_creates_upload_ready_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            workbook_path = base / "authors.xlsx"
            self._write_workbook(
                workbook_path,
                [
                    {"AuthorName": "Lisa Stone", "AuthorEmail": "LISA@example.com ", "BookTitle": "The Quiet Harbor", "ConfidenceScore": "3"},
                    {"AuthorName": "Mary Author", "Email": "mary@example.com", "BookTitle": "Real Book", "ConfidenceScore": "2", "Website": "https://example.test/mary"},
                    {"AuthorName": "Robert Hanson", "AuthorEmail": "robert@example.com", "BookTitle": "Complete", "ConfidenceScore": "3"},
                    {"AuthorName": "Phone Writer", "AuthorEmail": "phone@example.com", "BookTitle": "555-123-4567", "ConfidenceScore": "2"},
                    {"AuthorName": "Percent Writer", "AuthorEmail": "percent@example.com", "BookTitle": "50%", "ConfidenceScore": "2"},
                    {"AuthorName": "Bracket Writer", "AuthorEmail": "bracket@example.com", "BookTitle": "Title [subtitle]", "ConfidenceScore": "3"},
                    {"AuthorName": "Dup Weak", "AuthorEmail": "dupe@example.com", "ConfidenceScore": "2"},
                    {"AuthorName": "Dup Strong", "AuthorEmail": "dupe@example.com", "BookTitle": "Winner Book", "ConfidenceScore": "3"},
                    {"AuthorName": "Low Confidence", "AuthorEmail": "low@example.com", "BookTitle": "Low Book", "ConfidenceScore": "1"},
                    {"AuthorName": "Bad Name", "AuthorEmail": "badname@example.com", "BookTitle": "Bad Name", "ConfidenceScore": "3"},
                    {"AuthorName": "AuthorHouseUK", "AuthorEmail": "publisher@example.com", "BookTitle": "Publisher Book", "ConfidenceScore": "3"},
                    {"AuthorName": "Bad Email", "AuthorEmail": "not an email", "BookTitle": "Email Book", "ConfidenceScore": "3"},
                ],
            )

            result = clean_workbooks([workbook_path], base)
            upload_rows = self._read_csv(base / "lead_op_author_personalized_upload.csv")
            review_rows = self._read_csv(base / "lead_op_author_personalized_review.csv")

        self.assertEqual(base / "lead_op_author_personalized_upload.csv", result["upload_path"])
        self.assertEqual(OUTPUT_COLUMNS, list(upload_rows[0].keys()))

        emails = [row["email"] for row in upload_rows]
        self.assertEqual(len(emails), len(set(emails)))
        self.assertIn("lisa@example.com", emails)
        self.assertIn("mary@example.com", emails)
        self.assertIn("robert@example.com", emails)
        self.assertIn("phone@example.com", emails)
        self.assertIn("percent@example.com", emails)
        self.assertIn("bracket@example.com", emails)
        self.assertIn("dupe@example.com", emails)
        self.assertNotIn("low@example.com", emails)
        self.assertNotIn("publisher@example.com", emails)

        lisa = next(row for row in upload_rows if row["email"] == "lisa@example.com")
        self.assertEqual("lisa@example.com", lisa["email"])
        self.assertEqual("lisa@example.com", lisa["AuthorEmail"])
        self.assertEqual("Lisa Stone", lisa["AuthorName"])
        self.assertEqual("Lisa", lisa["first_name"])
        self.assertEqual("Stone", lisa["last_name"])
        self.assertEqual("The Quiet Harbor", lisa["BookTitle"])
        self.assertIn("The Quiet Harbor", lisa["PersonalizedOpeningLine"])
        self.assertEqual("3", lisa["ConfidenceScore"])

        mary = next(row for row in upload_rows if row["email"] == "mary@example.com")
        self.assertEqual("mary@example.com", mary["AuthorEmail"])
        self.assertEqual("Mary", mary["first_name"])
        self.assertEqual("Real Book", mary["BookTitle"])
        self.assertEqual("https://example.test/mary", mary["Website"])

        robert = next(row for row in upload_rows if row["email"] == "robert@example.com")
        self.assertEqual("", robert["BookTitle"])
        phone = next(row for row in upload_rows if row["email"] == "phone@example.com")
        self.assertEqual("", phone["BookTitle"])
        percent = next(row for row in upload_rows if row["email"] == "percent@example.com")
        self.assertEqual("", percent["BookTitle"])
        badname = next(row for row in upload_rows if row["email"] == "badname@example.com")
        self.assertEqual("", badname["BookTitle"])

        dupe = next(row for row in upload_rows if row["email"] == "dupe@example.com")
        self.assertEqual("Winner Book", dupe["BookTitle"])
        self.assertEqual("3", dupe["ConfidenceScore"])

        bracket = next(row for row in upload_rows if row["email"] == "bracket@example.com")
        self.assertEqual("Title (subtitle)", bracket["BookTitle"])
        self.assertNotIn("[subtitle]", bracket["PersonalizedOpeningLine"])

        for row in upload_rows:
            self.assertNotRegex(" ".join(row.values()), r"{[A-Za-z][A-Za-z0-9_]*}|\[[^\[\]\r\n]+\]|<<[^<>\r\n]+>>")
            self.assertIn(row["ConfidenceScore"], {"2", "3"})
            if row["BookTitle"]:
                self.assertIn(row["BookTitle"], row["PersonalizedOpeningLine"])

        self.assertEqual(12, result["counts"]["total_input_rows"])
        self.assertEqual(1, result["counts"]["duplicate_emails_removed"])
        self.assertEqual(1, result["counts"]["invalid_email_rows_removed"])
        self.assertEqual(1, result["counts"]["unsafe_author_rows_removed"])
        self.assertEqual(4, result["counts"]["book_titles_cleared"])
        self.assertEqual(1, result["counts"]["book_titles_normalized"])
        self.assertEqual(1, result["counts"]["confidence_rows_removed"])
        self.assertGreaterEqual(len(review_rows), 1)

    def test_summary_prints_counts_only(self) -> None:
        counts = Counter(
            {
                "total_input_rows": 10,
                "upload_rows": 6,
                "invalid_email_rows_removed": 1,
                "unsafe_author_rows_removed": 1,
                "book_titles_cleared": 3,
                "book_titles_normalized": 1,
                "duplicate_emails_removed": 1,
                "rows_with_book_title": 3,
                "review_rows": 4,
                "safe_book_titles_preserved": 3,
                "confidence_2_rows": 2,
                "confidence_3_rows": 4,
                "confidence_rows_removed": 1,
            }
        )
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_summary(counts)
        text = buffer.getvalue()

        self.assertIn("total input rows: 10", text)
        self.assertIn("upload rows: 6", text)
        self.assertIn("review rows: 4", text)
        self.assertIn("duplicate emails removed: 1", text)
        self.assertIn("confidence 2 rows: 2", text)
        self.assertIn("confidence 3 rows: 4", text)
        self.assertNotIn("%", text)
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)

    def _write_workbook(self, path: Path, rows: list[dict[str, str]]) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "Visible Leads"
        headers = [
            "AuthorName",
            "AuthorEmail",
            "Email",
            "BookTitle",
            "ConfidenceScore",
            "Website",
            "BookURL",
            "WhyAstraFit",
            "SourceURL",
        ]
        ws.append(headers)
        for row in rows:
            ws.append([row.get(header, "") for header in headers])
        hidden = wb.create_sheet("Hidden Leads")
        hidden.sheet_state = "hidden"
        hidden.append(headers)
        hidden.append(["Hidden Person", "hidden@example.com", "", "Hidden Book"])
        wb.save(path)

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
