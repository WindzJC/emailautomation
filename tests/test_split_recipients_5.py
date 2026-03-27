from __future__ import annotations

import csv
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from split_recipients_5 import main


class SplitRecipientsFiveTests(unittest.TestCase):
    def write_rows(self, path: Path, emails: list[str]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Email", "AuthorName"])
            writer.writeheader()
            for email in emails:
                writer.writerow({"Email": email, "AuthorName": email.split("@", 1)[0]})

    def read_emails(self, path: Path) -> list[str]:
        with path.open(newline="", encoding="utf-8") as handle:
            return [row["Email"] for row in csv.DictReader(handle)]

    def test_count_targets_actual_appended_rows_and_reports_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            src = base / "leads_prechecked.csv"
            dst_paths = [base / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]

            self.write_rows(
                src,
                [
                    "already@example.com",
                    "b@example.com",
                    "b@example.com",
                    "c@example.com",
                    "d@example.com",
                    "e@example.com",
                ],
            )
            self.write_rows(dst_paths[0], ["already@example.com"])
            for path in dst_paths[1:]:
                self.write_rows(path, [])

            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "--src",
                        str(src),
                        "--dst",
                        *[str(path) for path in dst_paths],
                        "--count",
                        "3",
                        "--append",
                        "--remove",
                    ]
                )

            self.assertEqual(0, result)
            text = output.getvalue()
            self.assertIn("requested=3", text)
            self.assertIn("inspected=5", text)
            self.assertIn("appended=3", text)
            self.assertIn("skipped_existing=1", text)
            self.assertIn("skipped_source_dupe=1", text)
            self.assertIn("removed=5", text)
            self.assertIn("remaining=1", text)

            self.assertEqual(["e@example.com"], self.read_emails(src))
            self.assertEqual(["already@example.com", "b@example.com"], self.read_emails(dst_paths[0]))
            self.assertEqual(["c@example.com"], self.read_emails(dst_paths[1]))
            self.assertEqual(["d@example.com"], self.read_emails(dst_paths[2]))
            self.assertEqual([], self.read_emails(dst_paths[3]))
            self.assertEqual([], self.read_emails(dst_paths[4]))

    def test_count_zero_drains_source_but_reports_non_appended_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            src = base / "leads_prechecked.csv"
            dst_paths = [base / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]

            self.write_rows(src, ["already@example.com", "fresh1@example.com", "fresh2@example.com"])
            self.write_rows(dst_paths[0], ["already@example.com"])
            for path in dst_paths[1:]:
                self.write_rows(path, [])

            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "--src",
                        str(src),
                        "--dst",
                        *[str(path) for path in dst_paths],
                        "--count",
                        "0",
                        "--append",
                        "--remove",
                    ]
                )

            self.assertEqual(0, result)
            text = output.getvalue()
            self.assertIn("requested=all", text)
            self.assertIn("appended=2", text)
            self.assertIn("skipped_existing=1", text)
            self.assertIn("removed=3", text)
            self.assertIn("remaining=0", text)
            self.assertEqual([], self.read_emails(src))


if __name__ == "__main__":
    unittest.main()
