from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.rebuild_recipient_queues import (
    QUEUE_FILENAMES,
    build_queue_safety_report,
    default_queue_paths,
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
