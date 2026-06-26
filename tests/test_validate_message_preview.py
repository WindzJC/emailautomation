from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools import validate_message_preview


class ValidateMessagePreviewTests(unittest.TestCase):
    def _write_preview(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Email", "FirstName", "BookTitle", "Subject", "Body"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_consignment_blank_booktitle_passes_when_generic_fallback_rendered(self) -> None:
        generic_opening = validate_message_preview.BOOK_TITLE_GENERIC_OPENING
        with tempfile.TemporaryDirectory() as tmpdir:
            preview_path = Path(tmpdir) / "sendgrid_annette_message_preview.csv"
            self._write_preview(
                preview_path,
                [
                    {
                        "Email": "reader@example.test",
                        "FirstName": "JC",
                        "BookTitle": "",
                        "Subject": "Independent author shelf review opportunity",
                        "Body": f"Hi JC,\n\n{generic_opening}\n\nWe are opening consignment spots for independent authors.",
                    }
                ],
            )

            result = validate_message_preview.validate_preview(preview_path, "consignment")

        self.assertEqual(1, result["passed"])
        self.assertEqual(0, result["failed"])
        self.assertEqual({}, result["reason_counts"])

    def test_consignment_present_booktitle_passes_with_personalized_rendering(self) -> None:
        title = "The Test Author Launch"
        with tempfile.TemporaryDirectory() as tmpdir:
            preview_path = Path(tmpdir) / "sendgrid_annette_message_preview.csv"
            self._write_preview(
                preview_path,
                [
                    {
                        "Email": "reader@example.test",
                        "FirstName": "JC",
                        "BookTitle": title,
                        "Subject": f"Shelf review opportunity for {title}",
                        "Body": (
                            "Hi JC,\n\n"
                            f"Our team came across {title} and thought it may be a strong fit for readers "
                            "discovering new independent books this summer.\n\n"
                            "We are opening consignment spots for independent authors."
                        ),
                    }
                ],
            )

            result = validate_message_preview.validate_preview(preview_path, "consignment")

        self.assertEqual(1, result["passed"])
        self.assertEqual(0, result["failed"])

    def test_blank_booktitle_fails_when_generic_fallback_is_not_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            preview_path = Path(tmpdir) / "sendgrid_annette_message_preview.csv"
            self._write_preview(
                preview_path,
                [
                    {
                        "Email": "reader@example.test",
                        "FirstName": "JC",
                        "BookTitle": "",
                        "Subject": "Independent author shelf review opportunity",
                        "Body": "Hi JC,\n\nWe came across your book.\n\nWe are opening consignment spots.",
                    }
                ],
            )

            result = validate_message_preview.validate_preview(preview_path, "consignment")

        self.assertEqual(0, result["passed"])
        self.assertEqual(1, result["failed"])
        reasons = result["reason_counts"]
        self.assertIn("book_title_generic_opening_missing", reasons)
        self.assertIn("body_generic_your_book", reasons)


if __name__ == "__main__":
    unittest.main()
