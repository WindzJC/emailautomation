from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.rebuild_recipient_queues as rebuild_tool
from tools.rebuild_recipient_queues import (
    QUEUE_FILENAMES,
    build_queue_safety_report,
    default_queue_paths,
    quarantine_malformed_stale_shard,
    rebuild_recipient_queues,
)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


class RebuildRecipientQueuesTests(unittest.TestCase):
    def test_quarantine_malformed_stale_sendgrid_shard_clears_safety_without_readding_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            checked = tmp / "leads.csv"
            keep = tmp / "leads_triaged_keep.csv"
            reject = tmp / "leads_triaged_reject.csv"
            shard = tmp / "recipients_sendgrid_5.csv"
            archive_root = tmp / "queue_quarantine"
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            safe_rows = [
                {
                    "Email": "keep@example.test",
                    "FirstName": "Keep",
                    "AuthorEmail": "author@example.test",
                    "AuthorName": "Keep Writer",
                    "BookTitle": "Keep Book",
                }
            ]
            write_csv(checked, headers, safe_rows)
            write_csv(keep, headers, safe_rows)
            write_csv(reject, headers, [])
            write_csv(
                shard,
                ["Email", "FirstName"],
                [
                    {"Email": "stale1@example.test", "FirstName": "Old"},
                    {"Email": "stale2@example.test", "FirstName": "Older"},
                ],
            )

            before = build_queue_safety_report(
                shard_paths=[shard],
                intended_source_path=keep,
                checked_path=checked,
                triaged_keep_path=keep,
                triaged_reject_path=reject,
            )
            result = quarantine_malformed_stale_shard(
                shard_path=shard,
                intended_source_path=keep,
                checked_path=checked,
                triaged_reject_path=reject,
                archive_root=archive_root,
            )
            after_headers, after_rows = rebuild_tool.read_csv(shard)
            archived_rows = read_rows(Path(str(result["archived_file"])))
            report_json_exists = Path(str(result["report_json"])).exists()
            report_csv_exists = Path(str(result["report_csv"])).exists()

        self.assertFalse(before["safe"])
        self.assertIn("MISSING_REQUIRED_HEADERS", before["unsafe_reasons"])
        self.assertEqual(2, before["outside_checked_output_count"])
        self.assertEqual(2, before["outside_intended_source_count"])
        self.assertEqual("outside_current_source_and_missing_required_headers", result["reason"])
        self.assertEqual(2, result["row_count"])
        self.assertEqual(["AuthorEmail", "AuthorName", "BookTitle"], result["missing_required_headers"])
        self.assertEqual(list(rebuild_tool.SENDGRID_REQUIRED_HEADERS), after_headers)
        self.assertEqual([], after_rows)
        self.assertEqual(2, len(archived_rows))
        self.assertTrue(report_json_exists)
        self.assertTrue(report_csv_exists)
        self.assertTrue(result["after"]["safe"])
        self.assertEqual(0, result["after"]["outside_checked_output_count"])
        self.assertEqual(0, result["after"]["outside_intended_source_count"])
        self.assertEqual(0, result["after"]["overlap_with_triaged_reject"])

    def test_quarantine_malformed_stale_shard_refuses_current_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            checked = tmp / "leads.csv"
            keep = tmp / "leads_triaged_keep.csv"
            reject = tmp / "leads_triaged_reject.csv"
            shard = tmp / "recipients_sendgrid_5.csv"
            write_csv(checked, ["Email", "FirstName"], [{"Email": "keep@example.test", "FirstName": "Keep"}])
            write_csv(keep, ["Email", "FirstName"], [{"Email": "keep@example.test", "FirstName": "Keep"}])
            write_csv(reject, ["Email", "FirstName"], [])
            write_csv(shard, ["Email", "FirstName"], [{"Email": "keep@example.test", "FirstName": "Keep"}])

            with self.assertRaises(ValueError):
                quarantine_malformed_stale_shard(
                    shard_path=shard,
                    intended_source_path=keep,
                    checked_path=checked,
                    triaged_reject_path=reject,
                    archive_root=tmp / "queue_quarantine",
                )

    def test_dry_run_detects_mixed_stale_queue_without_exposing_emails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            checked = tmp / "_important" / "leads.csv"
            keep = tmp / "_important" / "leads_triaged_keep.csv"
            reject = tmp / "_important" / "leads_triaged_reject.csv"
            shards = [tmp / "shards" / name for name in QUEUE_FILENAMES]

            write_csv(
                checked,
                ["Email", "FirstName"],
                [
                    {"Email": "keep1@example.test", "FirstName": "Keep"},
                    {"Email": "keep2@example.test", "FirstName": "Keep"},
                    {"Email": "reject1@example.test", "FirstName": "Reject"},
                ],
            )
            write_csv(
                keep,
                ["Email", "FirstName"],
                [
                    {"Email": "keep1@example.test", "FirstName": "Keep"},
                    {"Email": "keep2@example.test", "FirstName": "Keep"},
                ],
            )
            write_csv(reject, ["Email", "FirstName"], [{"Email": "reject1@example.test", "FirstName": "Reject"}])
            write_csv(
                shards[0],
                ["Email", "FirstName"],
                [
                    {"Email": "keep1@example.test", "FirstName": "Keep"},
                    {"Email": "reject1@example.test", "FirstName": "Reject"},
                    {"Email": "outside@example.test", "FirstName": "Outside"},
                ],
            )
            for path in shards[1:]:
                write_csv(path, ["Email", "FirstName"], [])

            report = build_queue_safety_report(
                shard_paths=shards,
                intended_source_path=keep,
                checked_path=checked,
                triaged_keep_path=keep,
                triaged_reject_path=reject,
            )

            self.assertFalse(report["safe"])
            self.assertEqual(3, report["unique_shard_emails"])
            self.assertEqual(2, report["overlap_with_checked_output"])
            self.assertEqual(1, report["overlap_with_triaged_keep"])
            self.assertEqual(1, report["overlap_with_triaged_reject"])
            self.assertEqual(1, report["outside_checked_output_count"])
            self.assertEqual(2, report["outside_intended_source_count"])
            self.assertIn("TRIAGED_REJECT_OVERLAP", report["unsafe_reasons"])
            self.assertIn("OUTSIDE_CHECKED_OUTPUT", report["unsafe_reasons"])
            self.assertIn("OUTSIDE_INTENDED_SOURCE", report["unsafe_reasons"])
            self.assertNotIn("outside@example.test", json.dumps(report))

    def test_rebuild_archives_first_and_preserves_logs_ledger_and_suppression_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            important = tmp / "_important"
            checked = important / "leads.csv"
            keep = important / "leads_triaged_keep.csv"
            reject = important / "leads_triaged_reject.csv"
            shards_dir = tmp / "data" / "shards"
            logs_dir = tmp / "data" / "logs"
            state_dir = tmp / "data" / "state"
            archive_root = state_dir / "backups" / "queue_rebuild"
            shards = default_queue_paths(shards_dir)

            source_rows = [
                {"Email": f"keep{index}@example.test", "FirstName": f"Keep{index}", "BookTitle": f"Book {index}"}
                for index in range(1, 14)
            ]
            write_csv(checked, ["Email", "FirstName", "BookTitle"], source_rows)
            write_csv(keep, ["Email", "FirstName", "BookTitle"], source_rows)
            write_csv(reject, ["Email", "FirstName", "BookTitle"], [])
            for path in shards:
                write_csv(path, ["Email", "FirstName"], [{"Email": "stale@example.test", "FirstName": "Stale"}])
            write_csv(logs_dir / "sendgrid_annette_log.csv", ["Email", "Status"], [{"Email": "sent@example.test", "Status": "SENT"}])
            protected = {
                state_dir / "leads_dashboard_state.json": b'{"latest_dispatch": {"id": "keep"}}\n',
                state_dir / "lead_ledger.sqlite3": b"ledger-bytes",
                state_dir / "sendgrid_suppressions.csv": b"email,state\nsuppressed@example.test,blocked\n",
                state_dir / "suppressed.csv": b"Email\nsuppressed@example.test\n",
                state_dir / "unsubscribed.csv": b"Email\nunsub@example.test\n",
                logs_dir / "sendgrid_events.jsonl": b'{"event":"bounce"}\n',
                state_dir / "sendgrid_webhook_dedupe.sqlite3": b"dedupe-bytes",
                state_dir / "sendgrid_webhook_receiver.sqlite3": b"receiver-bytes",
            }
            for path, content in protected.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            result = rebuild_recipient_queues(
                intended_source_path=keep,
                shard_paths=shards,
                archive_root=archive_root,
                checked_path=checked,
                triaged_keep_path=keep,
                triaged_reject_path=reject,
                log_dir=logs_dir,
                state_dir=state_dir,
                protected_paths=list(protected),
            )

            archive_dir = Path(str(result["archive_dir"]))
            self.assertTrue((archive_dir / "manifest.json").exists())
            self.assertTrue((archive_dir / QUEUE_FILENAMES[0]).exists())
            self.assertTrue((archive_dir / "sendgrid_annette_log.csv").exists())
            self.assertTrue((archive_dir / "lead_ledger.sqlite3").exists())

            for path, content in protected.items():
                self.assertEqual(content, path.read_bytes())
            self.assertEqual(
                [{"Email": "sent@example.test", "Status": "SENT"}],
                read_rows(logs_dir / "sendgrid_annette_log.csv"),
            )

            rebuilt_rows = [row for path in shards for row in read_rows(path)]
            self.assertEqual(13, len(rebuilt_rows))
            self.assertEqual({row["Email"] for row in source_rows}, {row["Email"] for row in rebuilt_rows})
            self.assertEqual(0, result["after"]["overlap_with_triaged_reject"])
            self.assertEqual(0, result["after"]["outside_intended_source_count"])
            self.assertEqual(0, result["after"]["outside_checked_output_count"])

    def test_queue_safety_uses_latest_dispatch_archive_when_current_sources_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            app_root = tmp / "app"
            state_dir = app_root / "data" / "state"
            staged = state_dir / "backups" / "staged_batches" / "dispatch_20260514_070407"
            shards = default_queue_paths(app_root / "data" / "shards")
            keep_rows = [
                {"Email": "keep1@example.test", "FirstName": "One", "AuthorEmail": "author1@example.test", "AuthorName": "One Writer", "BookTitle": "Book One"},
                {"Email": "keep2@example.test", "FirstName": "Two", "AuthorEmail": "author2@example.test", "AuthorName": "Two Writer", "BookTitle": "Book Two"},
                {"Email": "keep3@example.test", "FirstName": "Three", "AuthorEmail": "author3@example.test", "AuthorName": "Three Writer", "BookTitle": ""},
            ]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle", "PersonalizedOpeningLine"]
            write_csv(staged / "leads.csv", headers, keep_rows)
            write_csv(staged / "leads_triaged_keep.csv", headers, keep_rows)
            write_csv(staged / "leads_triaged_reject.csv", headers, [])
            for index, path in enumerate(shards):
                rows = [keep_rows[index]] if index < len(keep_rows) else []
                write_csv(path, headers, rows)
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "leads_dashboard_state.json").write_text(
                json.dumps({"latest_dispatch": {"staged_batch_archive_path": str(staged)}}),
                encoding="utf-8",
            )

            with (
                patch.object(rebuild_tool.settings, "APP_ROOT", app_root),
                patch.object(rebuild_tool.settings, "STATE_DIR", state_dir),
                patch.object(rebuild_tool.settings, "BACKUPS_DIR", state_dir / "backups"),
            ):
                report = build_queue_safety_report(shard_paths=shards)

        self.assertTrue(report["safe"])
        self.assertEqual("latest_dispatch_staged_batch_archive", report["source_resolution"])
        self.assertEqual(str(staged / "leads_triaged_keep.csv"), report["intended_source_path"])
        self.assertEqual(0, report["outside_checked_output_count"])
        self.assertEqual(0, report["outside_intended_source_count"])
        self.assertEqual(0, report["overlap_with_triaged_reject"])

    def test_sendgrid_safe_rebuild_normalizes_placeholder_like_book_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "leads_triaged_keep.csv"
            checked = tmp / "leads.csv"
            reject = tmp / "leads_triaged_reject.csv"
            shards = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle", "PersonalizedOpeningLine"]
            rows = [
                {
                    "Email": "brace@example.test",
                    "FirstName": "Brace",
                    "AuthorEmail": "author-brace@example.test",
                    "AuthorName": "Brace Writer",
                    "BookTitle": "Život p{r}outníka",
                    "PersonalizedOpeningLine": "Opening for Život p{r}outníka",
                },
                {
                    "Email": "square@example.test",
                    "FirstName": "Square",
                    "AuthorEmail": "author-square@example.test",
                    "AuthorName": "Square Writer",
                    "BookTitle": "[(Horse Medicine)]",
                    "PersonalizedOpeningLine": "Opening for [(Horse Medicine)]",
                },
                {
                    "Email": "subtitle@example.test",
                    "FirstName": "Subtitle",
                    "AuthorEmail": "author-subtitle@example.test",
                    "AuthorName": "Subtitle Writer",
                    "BookTitle": "Evolutions in Bread: Artisan Pan Breads and Dutch-Oven Loaves at Home [A baking book by the author of Flour Water Salt Yeast] Kindle Edition",
                    "PersonalizedOpeningLine": "Opening for title [A baking book by the author of Flour Water Salt Yeast]",
                },
            ]
            write_csv(source, headers, rows)
            write_csv(checked, headers, rows)
            write_csv(reject, headers, [])
            for path in shards:
                write_csv(path, headers, [])

            result = rebuild_tool.rebuild_sendgrid_recipient_queues(
                intended_source_path=source,
                checked_path=checked,
                triaged_keep_path=source,
                triaged_reject_path=reject,
                shard_paths=shards,
                apply=False,
            )
            planned_root = Path(str(result["quarantine_path"])).parent
            planned_rows = [
                row
                for path in sorted(planned_root.glob("recipients_sendgrid_*.csv"))
                for row in read_rows(path)
            ]
            quarantine_rows = read_rows(Path(str(result["quarantine_path"])))

        self.assertEqual(3, result["included_rows"])
        self.assertEqual([], quarantine_rows)
        self.assertTrue(result["after"]["safe"])
        titles = {row["Email"]: row["BookTitle"] for row in planned_rows}
        self.assertEqual("Život proutníka", titles["brace@example.test"])
        self.assertEqual("((Horse Medicine))", titles["square@example.test"])
        self.assertIn("(A baking book by the author of Flour Water Salt Yeast)", titles["subtitle@example.test"])
        for row in planned_rows:
            self.assertNotRegex(row["BookTitle"], r"{[A-Za-z][A-Za-z0-9_]*}|\[[^\[\]\r\n]+\]|<<[^<>\r\n]+>>")
            self.assertNotRegex(row["PersonalizedOpeningLine"], r"{[A-Za-z][A-Za-z0-9_]*}|\[[^\[\]\r\n]+\]|<<[^<>\r\n]+>>")
            self.assertIn("BookTitle:", row["normalization_note"])
            self.assertIn("PersonalizedOpeningLine:", row["normalization_note"])
