from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import important_leads_verify


class ImportantLeadsVerifyTests(unittest.TestCase):
    def test_verify_master_leads_resumes_from_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            verified_path = base / "leads_verified.csv"
            rejected_path = base / "leads_rejected.csv"
            quarantine_path = base / "leads_quarantine.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"

            rows = [
                {"FullName": "Alpha Author", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Book One"},
                {"FullName": "Beta Author", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Book Two"},
                {"FullName": "Gamma Author", "FirstName": "Gamma", "Email": "gamma@example.com", "BookTitle": "Book Three"},
            ]
            self._write_csv(input_path, ["FullName", "FirstName", "Email", "BookTitle"], rows)

            def searcher(query: str) -> list[dict[str, str]]:
                if "alpha@example.com" in query:
                    return [{"url": "memory://proof?row=0"}]
                if "beta@example.com" in query:
                    return [{"url": "memory://proof?row=1"}]
                if "gamma@example.com" in query:
                    return [{"url": "memory://proof?row=2"}]
                return []

            def fetcher(url: str) -> dict[str, str]:
                row = parse_qs(urlparse(url).query).get("row", [""])[0]
                if row == "0":
                    return {"text": "Alpha Author alpha@example.com"}
                if row == "1":
                    return {"text": "Contact beta@example.com"}
                if row == "2":
                    return {"text": "Different Person other@example.com"}
                return {"text": ""}

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(
                important_leads_verify,
                "VERIFY_STATE_PATH",
                checkpoint_path,
            ), patch.object(
                important_leads_verify,
                "VERIFY_CHECKPOINT_ROWS",
                1,
            ):
                original_save_checkpoint_state = important_leads_verify._save_checkpoint_state

                def crash_after_first_checkpoint(payload: dict[str, object]) -> None:
                    original_save_checkpoint_state(payload)
                    if int(payload.get("next_row_index") or 0) == 1:
                        raise RuntimeError("mid-job stop")

                with patch.object(
                    important_leads_verify,
                    "_save_checkpoint_state",
                    side_effect=crash_after_first_checkpoint,
                ):
                    with self.assertRaises(RuntimeError):
                        important_leads_verify.verify_master_leads(
                            input_path=input_path,
                            verified_path=verified_path,
                            rejected_path=rejected_path,
                            quarantine_path=quarantine_path,
                            persist_state=True,
                            searcher=searcher,
                            fetcher=fetcher,
                            max_pages_per_lead=1,
                            retries=0,
                            allow_social_proof=True,
                            validate_deliverability=False,
                        )

                checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                self.assertEqual(1, checkpoint["next_row_index"])

                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    quarantine_path=quarantine_path,
                    persist_state=True,
                    searcher=searcher,
                    fetcher=fetcher,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertTrue(report["resume_supported"])
            self.assertEqual(1, report["keep_count"])
            self.assertEqual(1, report["quarantine_count"])
            self.assertEqual(1, report["reject_count"])

            with verified_path.open(newline="", encoding="utf-8") as handle:
                verified_rows = list(csv.DictReader(handle))
            with rejected_path.open(newline="", encoding="utf-8") as handle:
                rejected_rows = list(csv.DictReader(handle))
            with quarantine_path.open(newline="", encoding="utf-8") as handle:
                quarantine_rows = list(csv.DictReader(handle))

            self.assertEqual(1, len(verified_rows))
            self.assertEqual("KEEP", verified_rows[0]["Status"])
            self.assertEqual(1, len(rejected_rows))
            self.assertEqual("REJECT", rejected_rows[0]["Status"])
            self.assertEqual(1, len(quarantine_rows))
            self.assertEqual("QUARANTINE", quarantine_rows[0]["Status"])

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
