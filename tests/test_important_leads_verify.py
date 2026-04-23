from __future__ import annotations

import csv
import json
import threading
import time
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import important_leads_verify
import lead_ledger


class ImportantLeadsVerifyTests(unittest.TestCase):
    def test_fast_triage_keeps_valid_full_name_and_normal_email(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [{"FullName": "Alpha Baker", "Email": "alpha@examplebooks.com"}],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path):
                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=base / "triaged_keep.csv",
                    rejected_path=base / "triaged_reject.csv",
                    quarantine_path=base / "triaged_quarantine.csv",
                    persist_state=True,
                    disposable_domains=set(),
                )

            self.assertEqual(1, report["keep_count"])
            self.assertEqual(0, report["reject_count"])
            self.assertEqual(0, report["quarantine_count"])

    def test_fast_triage_rejects_missing_email_and_invalid_email(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [
                    {"FullName": "No Email", "Email": ""},
                    {"FullName": "Bad Email", "Email": "not-an-email"},
                ],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path):
                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=base / "triaged_keep.csv",
                    rejected_path=base / "triaged_reject.csv",
                    quarantine_path=base / "triaged_quarantine.csv",
                    persist_state=True,
                    disposable_domains=set(),
                )

            self.assertEqual(0, report["keep_count"])
            self.assertEqual(2, report["reject_count"])

    def test_fast_triage_quarantines_missing_usable_name_and_role_email(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [
                    {"FullName": "Prince", "Email": "prince@examplebooks.com"},
                    {"FullName": "Support Team", "Email": "support@examplebooks.com"},
                ],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path):
                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=base / "triaged_keep.csv",
                    rejected_path=base / "triaged_reject.csv",
                    quarantine_path=base / "triaged_quarantine.csv",
                    persist_state=True,
                    disposable_domains=set(),
                )

            self.assertEqual(0, report["keep_count"])
            self.assertEqual(0, report["reject_count"])
            self.assertEqual(2, report["quarantine_count"])
            self.assertEqual(1, report["reason_counts"]["MISSING_USABLE_NAME"])
            self.assertEqual(1, report["reason_counts"]["ROLE_ACCOUNT"])

    def test_fast_triage_rejects_junk_name_and_disposable_domain(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [
                    {"FullName": "Test User", "Email": "test@examplebooks.com"},
                    {"FullName": "Real Person", "Email": "real@tempmail.co"},
                ],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path):
                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=base / "triaged_keep.csv",
                    rejected_path=base / "triaged_reject.csv",
                    quarantine_path=base / "triaged_quarantine.csv",
                    persist_state=True,
                    disposable_domains={"tempmail.co"},
                )

            self.assertEqual(0, report["keep_count"])
            self.assertEqual(2, report["reject_count"])
            self.assertEqual(1, report["reason_counts"]["JUNK_NAME"])
            self.assertEqual(1, report["reason_counts"]["DISPOSABLE_DOMAIN"])

    def test_fast_triage_resumes_from_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [
                    {"FullName": "Alpha Baker", "Email": "alpha@examplebooks.com"},
                    {"FullName": "Beta Baker", "Email": "beta@examplebooks.com"},
                ],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path), patch.object(
                important_leads_verify,
                "VERIFY_CHECKPOINT_ROWS",
                1,
            ):
                original_save = important_leads_verify._save_triage_checkpoint_state

                def crash_after_first_checkpoint(payload: dict[str, object]) -> None:
                    original_save(payload)
                    if int(payload.get("next_row_index") or 0) == 1:
                        raise RuntimeError("mid-triage stop")

                with patch.object(important_leads_verify, "_save_triage_checkpoint_state", side_effect=crash_after_first_checkpoint):
                    with self.assertRaises(RuntimeError):
                        important_leads_verify.fast_triage_master_leads(
                            input_path=input_path,
                            keep_path=base / "triaged_keep.csv",
                            rejected_path=base / "triaged_reject.csv",
                            quarantine_path=base / "triaged_quarantine.csv",
                            persist_state=True,
                            disposable_domains=set(),
                        )

                checkpoint = json.loads(triage_state_path.read_text(encoding="utf-8"))
                self.assertEqual(1, checkpoint["next_row_index"])

                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=base / "triaged_keep.csv",
                    rejected_path=base / "triaged_reject.csv",
                    quarantine_path=base / "triaged_quarantine.csv",
                    persist_state=True,
                    disposable_domains=set(),
                )

            self.assertEqual(2, report["keep_count"])
            self.assertEqual(2, report["processed_rows"])

    def test_fast_triage_stop_preserves_outputs_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [
                    {"FullName": "Alpha Baker", "Email": "alpha@examplebooks.com"},
                    {"FullName": "Beta Baker", "Email": "beta@examplebooks.com"},
                ],
            )
            cancel_calls = {"count": 0}

            def should_cancel() -> bool:
                cancel_calls["count"] += 1
                return cancel_calls["count"] > 2

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "TRIAGE_STATE_PATH", triage_state_path), patch.object(
                important_leads_verify,
                "VERIFY_CHECKPOINT_ROWS",
                2,
            ):
                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=base / "triaged_keep.csv",
                    rejected_path=base / "triaged_reject.csv",
                    quarantine_path=base / "triaged_quarantine.csv",
                    persist_state=True,
                    disposable_domains=set(),
                    should_cancel=should_cancel,
                )

            self.assertTrue(report["canceled"])
            checkpoint = json.loads(triage_state_path.read_text(encoding="utf-8"))
            self.assertFalse(checkpoint["completed"])
            self.assertEqual(0, checkpoint["next_row_index"])

    def test_fast_triage_updates_lead_ledger_and_preserves_csv_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            keep_path = base / "triaged_keep.csv"
            rejected_path = base / "triaged_reject.csv"
            quarantine_path = base / "triaged_quarantine.csv"
            triage_state_path = state_dir / "important_leads_triage_state.json"
            ledger_db_path = state_dir / "lead_ledger.sqlite3"
            self._write_csv(
                input_path,
                ["FullName", "Email"],
                [
                    {"FullName": "Alpha Baker", "Email": "alpha@examplebooks.com"},
                    {"FullName": "Prince", "Email": "prince@examplebooks.com"},
                    {"FullName": "Bad Email", "Email": "not-an-email"},
                ],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(
                important_leads_verify.settings,
                "LEAD_LEDGER_DB_PATH",
                ledger_db_path,
            ), patch.object(
                important_leads_verify,
                "TRIAGE_STATE_PATH",
                triage_state_path,
            ):
                report = important_leads_verify.fast_triage_master_leads(
                    input_path=input_path,
                    keep_path=keep_path,
                    rejected_path=rejected_path,
                    quarantine_path=quarantine_path,
                    persist_state=True,
                    disposable_domains=set(),
                )

            self.assertEqual(1, report["keep_count"])
            self.assertEqual(1, report["reject_count"])
            self.assertEqual(1, report["quarantine_count"])
            self.assertEqual("KEEP", self._read_csv_rows(keep_path)[0]["Status"])
            self.assertEqual("REJECT", self._read_csv_rows(rejected_path)[0]["Status"])
            self.assertEqual("QUARANTINE", self._read_csv_rows(quarantine_path)[0]["Status"])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                alpha = lead_ledger.load_lead_by_id(conn, lead_ledger.deterministic_lead_id("alpha@examplebooks.com"))
                prince = lead_ledger.load_lead_by_id(conn, lead_ledger.deterministic_lead_id("prince@examplebooks.com"))
                invalid = lead_ledger.load_lead_by_id(conn, lead_ledger.deterministic_lead_id("not-an-email"))
                self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM lead_ledger").fetchone()[0])
                self.assertEqual(lead_ledger.FAST_TRIAGE_STAGE, alpha["current_stage"])
                self.assertEqual("KEEP", alpha["current_status"])
                self.assertIn("FAST_TRIAGE_LOCAL_CONFIDENCE", alpha["reason_codes"])
                self.assertEqual("leads.csv", alpha["source_file"])
                self.assertEqual(lead_ledger.FAST_TRIAGE_STAGE, prince["current_stage"])
                self.assertEqual("QUARANTINE", prince["current_status"])
                self.assertIn("MISSING_USABLE_NAME", prince["reason_codes"])
                self.assertEqual("REJECT", invalid["current_status"])
                self.assertIn("INVALID_EMAIL_SYNTAX", invalid["reason_codes"])
            finally:
                conn.close()

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
                {"FullName": "Alpha Baker", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Book One"},
                {"FullName": "Beta Baker", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Book Two"},
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
                    return {"text": "Alpha Baker alpha@example.com"}
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

    def test_verify_master_leads_concurrent_workers_preserve_decisions(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            rows = [
                {"FullName": "Alpha Baker", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Book One"},
                {"FullName": "Beta Baker", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Book Two"},
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
                    return {"text": "Alpha Baker alpha@example.com"}
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
                10,
            ):
                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=base / "leads_verified.csv",
                    rejected_path=base / "leads_rejected.csv",
                    quarantine_path=base / "leads_quarantine.csv",
                    persist_state=True,
                    searcher=searcher,
                    fetcher=fetcher,
                    max_workers=3,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertEqual(1, report["keep_count"])
            self.assertEqual(1, report["quarantine_count"])
            self.assertEqual(1, report["reject_count"])
            self.assertEqual(3, report["processed_rows"])

    def test_verify_master_leads_exits_after_first_strong_email_proof(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            self._write_csv(
                input_path,
                ["FullName", "FirstName", "Email", "BookTitle"],
                [{"FullName": "Alpha Baker", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Book One"}],
            )
            queries: list[str] = []

            def searcher(query: str) -> list[dict[str, str]]:
                queries.append(query)
                return [{"url": "memory://proof"}]

            def fetcher(url: str) -> dict[str, str]:
                return {"text": "Alpha Baker alpha@example.com"}

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "VERIFY_STATE_PATH", checkpoint_path):
                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=base / "leads_verified.csv",
                    rejected_path=base / "leads_rejected.csv",
                    quarantine_path=base / "leads_quarantine.csv",
                    persist_state=True,
                    searcher=searcher,
                    fetcher=fetcher,
                    max_workers=1,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertEqual(1, report["keep_count"])
            self.assertEqual(['"alpha@example.com"'], queries)

    def test_verify_master_leads_does_not_use_book_title_queries(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            self._write_csv(
                input_path,
                ["FullName", "FirstName", "Email", "BookTitle"],
                [{"FullName": "Beta Baker", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Rare Book Title"}],
            )
            queries: list[str] = []

            def searcher(query: str) -> list[dict[str, str]]:
                queries.append(query)
                return []

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "VERIFY_STATE_PATH", checkpoint_path):
                important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=base / "leads_verified.csv",
                    rejected_path=base / "leads_rejected.csv",
                    quarantine_path=base / "leads_quarantine.csv",
                    persist_state=True,
                    searcher=searcher,
                    fetcher=lambda url: {"text": ""},
                    max_workers=1,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertTrue(queries)
            self.assertFalse(any("Rare Book Title" in query for query in queries))

    def test_verify_master_leads_conflicting_email_rejects(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            self._write_csv(
                input_path,
                ["FullName", "FirstName", "Email", "BookTitle"],
                [{"FullName": "Gamma Author", "FirstName": "Gamma", "Email": "gamma@example.com", "BookTitle": "Book Three"}],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "VERIFY_STATE_PATH", checkpoint_path):
                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=base / "leads_verified.csv",
                    rejected_path=base / "leads_rejected.csv",
                    quarantine_path=base / "leads_quarantine.csv",
                    persist_state=True,
                    searcher=lambda query: [{"url": "memory://proof"}],
                    fetcher=lambda url: {"text": "Different Person other@example.com"},
                    max_workers=1,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertEqual(1, report["reject_count"])
            self.assertEqual(0, report["keep_count"])

    def test_verify_master_leads_weak_email_only_proof_quarantines(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            self._write_csv(
                input_path,
                ["FullName", "FirstName", "Email", "BookTitle"],
                [{"FullName": "Delta Author", "FirstName": "Delta", "Email": "delta@example.com", "BookTitle": "Book Four"}],
            )

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "VERIFY_STATE_PATH", checkpoint_path):
                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=base / "leads_verified.csv",
                    rejected_path=base / "leads_rejected.csv",
                    quarantine_path=base / "leads_quarantine.csv",
                    persist_state=True,
                    searcher=lambda query: [{"url": "memory://proof"}],
                    fetcher=lambda url: {"text": "Contact delta@example.com"},
                    max_workers=1,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertEqual(1, report["quarantine_count"])
            self.assertEqual(0, report["keep_count"])

    def test_verify_master_leads_cancel_does_not_wait_for_running_network_tasks(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            rows = [
                {"FullName": "Slow One", "FirstName": "Slow", "Email": "slow1@example.com", "BookTitle": "Book One"},
                {"FullName": "Slow Two", "FirstName": "Slow", "Email": "slow2@example.com", "BookTitle": "Book Two"},
            ]
            self._write_csv(input_path, ["FullName", "FirstName", "Email", "BookTitle"], rows)
            release_fetchers = threading.Event()

            def searcher(query: str) -> list[dict[str, str]]:
                return [{"url": f"memory://proof?q={query}"}]

            def fetcher(url: str) -> dict[str, str]:
                release_fetchers.wait(3.0)
                return {"text": ""}

            started_at = time.monotonic()

            def should_cancel() -> bool:
                return time.monotonic() - started_at > 0.2

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
                2,
            ), patch.object(
                important_leads_verify,
                "VERIFY_CANCEL_POLL_SECONDS",
                0.05,
            ):
                try:
                    report = important_leads_verify.verify_master_leads(
                        input_path=input_path,
                        verified_path=base / "leads_verified.csv",
                        rejected_path=base / "leads_rejected.csv",
                        quarantine_path=base / "leads_quarantine.csv",
                        persist_state=True,
                        searcher=searcher,
                        fetcher=fetcher,
                        max_workers=2,
                        max_pages_per_lead=1,
                        retries=0,
                        allow_social_proof=True,
                        validate_deliverability=False,
                        should_cancel=should_cancel,
                    )
                finally:
                    release_fetchers.set()

            elapsed = time.monotonic() - started_at
            self.assertLess(elapsed, 1.0)
            self.assertTrue(report["canceled"])
            self.assertFalse(report["checkpoint_completed"])
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertFalse(checkpoint["completed"])
            self.assertEqual(0, checkpoint["next_row_index"])

    def test_verify_master_leads_updates_lead_ledger_and_preserves_csv_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            verified_path = base / "leads_verified.csv"
            rejected_path = base / "leads_rejected.csv"
            quarantine_path = base / "leads_quarantine.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            ledger_db_path = state_dir / "lead_ledger.sqlite3"
            rows = [
                {"FullName": "Alpha Baker", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Book One"},
                {"FullName": "Beta Baker", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Book Two"},
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
                    return {"text": "Alpha Baker alpha@example.com"}
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
                important_leads_verify.settings,
                "LEAD_LEDGER_DB_PATH",
                ledger_db_path,
            ), patch.object(
                important_leads_verify,
                "VERIFY_STATE_PATH",
                checkpoint_path,
            ):
                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    quarantine_path=quarantine_path,
                    persist_state=True,
                    searcher=searcher,
                    fetcher=fetcher,
                    max_workers=1,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                )

            self.assertEqual(1, report["keep_count"])
            self.assertEqual(1, report["reject_count"])
            self.assertEqual(1, report["quarantine_count"])
            self.assertEqual("KEEP", self._read_csv_rows(verified_path)[0]["Status"])
            self.assertEqual("REJECT", self._read_csv_rows(rejected_path)[0]["Status"])
            self.assertEqual("QUARANTINE", self._read_csv_rows(quarantine_path)[0]["Status"])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                alpha = lead_ledger.load_lead_by_id(conn, lead_ledger.deterministic_lead_id("alpha@example.com"))
                beta = lead_ledger.load_lead_by_id(conn, lead_ledger.deterministic_lead_id("beta@example.com"))
                gamma = lead_ledger.load_lead_by_id(conn, lead_ledger.deterministic_lead_id("gamma@example.com"))
                self.assertEqual(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, alpha["current_stage"])
                self.assertEqual("KEEP", alpha["current_status"])
                self.assertIn("FULL_NAME_AND_EMAIL_MATCH", alpha["reason_codes"])
                self.assertEqual("QUARANTINE", beta["current_status"])
                self.assertIn("INSUFFICIENT_PROOF", beta["reason_codes"])
                self.assertEqual("REJECT", gamma["current_status"])
                self.assertIn("PROOF_MISMATCH", gamma["reason_codes"])
            finally:
                conn.close()

    def test_verify_master_leads_selected_lead_ids_filters_input_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory(dir=important_leads_verify.settings.APP_ROOT) as tmpdir:
            base = Path(tmpdir)
            state_dir = base / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            input_path = base / "leads.csv"
            verified_path = base / "leads_verified.csv"
            rejected_path = base / "leads_rejected.csv"
            quarantine_path = base / "leads_quarantine.csv"
            checkpoint_path = state_dir / "important_leads_verify_state.json"
            self._write_csv(
                input_path,
                ["FullName", "FirstName", "Email", "BookTitle"],
                [
                    {"FullName": "Alpha Baker", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Book One"},
                    {"FullName": "Beta Baker", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Book Two"},
                ],
            )
            beta_lead_id = lead_ledger.deterministic_lead_id("beta@example.com")

            def searcher(query: str) -> list[dict[str, str]]:
                return [{"url": f"memory://proof?q={query}"}]

            def fetcher(url: str) -> dict[str, str]:
                return {"text": "Beta Baker beta@example.com"}

            with patch.object(important_leads_verify.settings, "APP_ROOT", base), patch.object(
                important_leads_verify.settings,
                "STATE_DIR",
                state_dir,
            ), patch.object(important_leads_verify, "VERIFY_STATE_PATH", checkpoint_path):
                report = important_leads_verify.verify_master_leads(
                    input_path=input_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    quarantine_path=quarantine_path,
                    persist_state=True,
                    searcher=searcher,
                    fetcher=fetcher,
                    max_workers=1,
                    max_pages_per_lead=1,
                    retries=0,
                    allow_social_proof=True,
                    validate_deliverability=False,
                    selected_lead_ids=[beta_lead_id],
                )

            self.assertEqual(1, report["input_rows"])
            self.assertEqual(1, report["processed_rows"])
            self.assertEqual(1, report["selected_lead_ids_count"])
            verified_rows = self._read_csv_rows(verified_path)
            self.assertEqual(1, len(verified_rows))
            self.assertEqual("beta@example.com", verified_rows[0]["Email"])
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(1, checkpoint["selected_lead_ids_count"])
            self.assertTrue(str(checkpoint["selected_lead_ids_fingerprint"]))

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _read_csv_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
