from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.prepare_sendgrid_leads import load_source_rows


class PrepareSendgridLeadsTests(unittest.TestCase):
    def test_load_source_rows_handles_tab_delimited_email_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.tsv"
            path.write_text(
                "\nFirstName\tAuthorEmail\n"
                "Michael Herrick\therrick@eastlink.ca\n"
                "Saundra Sandrock\tprofchild@gmail.com\n",
                encoding="utf-8",
            )

            rows = load_source_rows(path)

            self.assertEqual(
                [
                    {"Email": "herrick@eastlink.ca", "FirstName": "Michael Herrick"},
                    {"Email": "profchild@gmail.com", "FirstName": "Saundra Sandrock"},
                ],
                rows,
            )

    def test_load_source_rows_handles_comma_delimited_email_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            path.write_text(
                "Email,FirstName\n"
                "alice@example.com,Alice Smith\n"
                "bob@example.com,Bob Jones\n",
                encoding="utf-8",
            )

            rows = load_source_rows(path)

            self.assertEqual(
                [
                    {"Email": "alice@example.com", "FirstName": "Alice Smith"},
                    {"Email": "bob@example.com", "FirstName": "Bob Jones"},
                ],
                rows,
            )


if __name__ == "__main__":
    unittest.main()
