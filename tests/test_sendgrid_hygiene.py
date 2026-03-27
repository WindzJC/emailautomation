from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sendgrid_hygiene import (
    clean_recipient_shards,
    classify_suppression_event,
    dedupe_webhook_events,
    is_actionable_suppression_status,
    load_active_suppressed_emails,
    load_webhook_dedupe_stats,
    normalize_webhook_events,
    parse_activity_file,
    parse_activity_multiline_text,
    write_suppression_records,
)


class SendgridHygieneTests(unittest.TestCase):
    def test_parse_multiline_activity_log(self) -> None:
        text = """Processed At
February 28, 2026 02:54:47 PM
msg-1\taSTRAProductionsByJC@gmail.com\tFinal Call:\tConsignment Consideration
Blocked
550
550 5.1.1 recipient not found
February 28, 2026 02:54:48 PM
msg-2\treader@example.com\tAnother Subject
Delivered
250
250 2.0.0 OK
"""
        events = parse_activity_multiline_text(text, "activity.txt", source_tz=timezone.utc)
        self.assertEqual(2, len(events))
        self.assertEqual("astraproductionsbyjc@gmail.com", events[0]["email"])
        self.assertEqual("Final Call:\tConsignment Consideration", events[0]["subject"])
        self.assertEqual("Blocked", events[0]["status"])
        self.assertEqual("550", events[0]["code"])
        self.assertIn("recipient not found", events[0]["response"])

    def test_parse_csv_activity_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "activity.csv"
            path.write_text(
                "Processed At,Message ID,Recipient Email,Subject Line,Status,Code,Response\n"
                "2026-03-01T12:00:00+00:00,msg-3,User@Example.com,Subject,Dropped,554,spam report\n",
                encoding="utf-8",
            )
            events = parse_activity_file(path, source_timezone="UTC")
        self.assertEqual(1, len(events))
        self.assertEqual("user@example.com", events[0]["email"])
        self.assertEqual("Dropped", events[0]["status"])
        self.assertEqual("554", events[0]["code"])

    def test_normalize_webhook_events_records_ingest_time(self) -> None:
        received_at = datetime(2026, 3, 13, 12, 5, 0, tzinfo=timezone.utc)
        events = normalize_webhook_events(
            [
                {
                    "email": "User@Example.com",
                    "event": "delivered",
                    "timestamp": 1773403200,
                    "sg_event_id": "evt-123",
                    "sg_message_id": "abc123.recvd-1",
                }
            ],
            received_at_utc=received_at,
        )

        self.assertEqual(1, len(events))
        self.assertEqual("2026-03-13T12:05:00+00:00", events[0]["received_at_utc"])
        self.assertEqual("user@example.com", events[0]["email"])
        self.assertEqual("evt-123", events[0]["event_id"])
        self.assertEqual("sg_event_id:evt-123", events[0]["dedupe_key"])

    def test_dedupe_webhook_events_filters_retries_and_records_duplicate_stats(self) -> None:
        received_at = datetime(2026, 3, 13, 12, 5, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "webhook_dedupe.sqlite3"
            normalized = normalize_webhook_events(
                [
                    {
                        "email": "User@Example.com",
                        "event": "delivered",
                        "timestamp": 1773403200,
                        "sg_event_id": "evt-123",
                        "sg_message_id": "abc123.recvd-1",
                    },
                    {
                        "email": "User@Example.com",
                        "event": "delivered",
                        "timestamp": 1773403200,
                        "sg_event_id": "evt-123",
                        "sg_message_id": "abc123.recvd-1",
                    },
                ],
                received_at_utc=received_at,
            )
            result = dedupe_webhook_events(normalized, path, reference_utc=received_at)
            stats = load_webhook_dedupe_stats(path, selected_hours=24, reference_utc=received_at)

        self.assertEqual(2, result["received"])
        self.assertEqual(1, result["stored"])
        self.assertEqual(1, result["duplicates"])
        self.assertEqual(1, len(result["unique_events"]))
        self.assertEqual("2026-03-13T12:05:00+00:00", stats["last_received_iso"])
        self.assertEqual(1, stats["duplicate_hits_5m"])
        self.assertEqual(1, stats["duplicate_hits_1h"])
        self.assertEqual(1, stats["duplicate_hits_selected_window"])
        self.assertEqual(1, stats["duplicate_hits_total"])

    def test_dedupe_webhook_events_uses_fingerprint_fallback_without_event_id(self) -> None:
        received_at = datetime(2026, 3, 13, 12, 5, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "webhook_dedupe.sqlite3"
            normalized = normalize_webhook_events(
                [
                    {
                        "email": "user@example.com",
                        "event": "open",
                        "timestamp": 1773403500,
                        "sg_message_id": "abc123.recvd-1",
                        "url": "",
                    },
                    {
                        "email": "user@example.com",
                        "event": "open",
                        "timestamp": 1773403500,
                        "sg_message_id": "abc123.recvd-1",
                        "url": "",
                    },
                ],
                received_at_utc=received_at,
            )
            result = dedupe_webhook_events(normalized, path, reference_utc=received_at)

        self.assertEqual(1, result["stored"])
        self.assertEqual(1, result["duplicates"])
        self.assertTrue(str(normalized[0]["dedupe_key"]).startswith("fp:"))

    def test_classification_rules(self) -> None:
        reference = datetime(2026, 3, 1, tzinfo=timezone.utc)
        bounced = classify_suppression_event(
            {
                "email": "a@example.com",
                "status": "Bounced",
                "code": "550",
                "response": "user unknown",
                "processed_at_utc": "2026-03-01T00:00:00+00:00",
                "source_log": "x.txt",
            },
            reference_utc=reference,
        )
        blocked = classify_suppression_event(
            {
                "email": "b@example.com",
                "status": "Blocked",
                "code": "552",
                "response": "Mailbox full. over quota",
                "processed_at_utc": "2026-03-01T01:00:00+00:00",
                "source_log": "x.txt",
            },
            reference_utc=reference,
        )
        self.assertEqual("true", bounced["is_permanent"])
        self.assertEqual("", bounced["ttl_until_utc"])
        self.assertEqual("false", blocked["is_permanent"])
        self.assertEqual(
            "2026-03-31T00:00:00+00:00",
            blocked["ttl_until_utc"],
        )

    def test_non_suppression_statuses_are_ignored(self) -> None:
        self.assertFalse(is_actionable_suppression_status("processed"))
        self.assertFalse(is_actionable_suppression_status("deferred"))
        self.assertFalse(is_actionable_suppression_status("group_resubscribe"))
        self.assertIsNone(
            classify_suppression_event(
                {
                    "email": "probe@example.com",
                    "status": "processed",
                    "response": "accepted by sendgrid",
                    "processed_at_utc": "2026-03-01T00:00:00+00:00",
                },
                reference_utc=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        )

    def test_ttl_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            suppression_csv = Path(tmpdir) / "sendgrid_suppressions.csv"
            write_suppression_records(
                suppression_csv,
                {
                    "perm@example.com": {
                        "email": "perm@example.com",
                        "status": "Bounced",
                        "code": "550",
                        "reason": "user unknown",
                        "last_seen_utc": "2026-03-01T00:00:00+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                        "source_log": "a.txt",
                    },
                    "temp@example.com": {
                        "email": "temp@example.com",
                        "status": "Blocked",
                        "code": "552",
                        "reason": "mailbox full",
                        "last_seen_utc": "2026-03-01T00:00:00+00:00",
                        "is_permanent": "false",
                        "ttl_until_utc": "2026-03-20T00:00:00+00:00",
                        "source_log": "a.txt",
                    },
                    "expired@example.com": {
                        "email": "expired@example.com",
                        "status": "Blocked",
                        "code": "552",
                        "reason": "mailbox full",
                        "last_seen_utc": "2026-02-01T00:00:00+00:00",
                        "is_permanent": "false",
                        "ttl_until_utc": "2026-02-10T00:00:00+00:00",
                        "source_log": "a.txt",
                    },
                },
            )
            blocked, summary = load_active_suppressed_emails(
                suppression_csv,
                reference_utc=datetime(2026, 3, 10, tzinfo=timezone.utc),
            )
        self.assertEqual({"perm@example.com", "temp@example.com"}, blocked)
        self.assertEqual(1, summary["total_perm"])
        self.assertEqual(1, summary["total_temp_active"])

    def test_clean_recipient_shards_preserves_header_and_removes_only_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            suppression_csv = base / "sendgrid_suppressions.csv"
            shard = base / "recipients_sendgrid_1.csv"
            backup_dir = base / "backups"
            report_path = base / "cleaning_report.json"

            write_suppression_records(
                suppression_csv,
                {
                    "remove@example.com": {
                        "email": "remove@example.com",
                        "status": "Bounced",
                        "code": "550",
                        "reason": "user unknown",
                        "last_seen_utc": "2026-03-01T00:00:00+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                        "source_log": "activity.txt",
                    },
                    "expired@example.com": {
                        "email": "expired@example.com",
                        "status": "Blocked",
                        "code": "552",
                        "reason": "mailbox full",
                        "last_seen_utc": "2026-02-01T00:00:00+00:00",
                        "is_permanent": "false",
                        "ttl_until_utc": "2026-02-10T00:00:00+00:00",
                        "source_log": "activity.txt",
                    },
                },
            )

            with shard.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email", "AuthorName"])
                writer.writeheader()
                writer.writerow({"Email": "remove@example.com", "AuthorName": "A"})
                writer.writerow({"Email": "expired@example.com", "AuthorName": "B"})
                writer.writerow({"Email": "keep@example.com", "AuthorName": "C"})

            report = clean_recipient_shards(
                suppression_csv,
                [shard],
                backup_dir,
                report_path,
                reference_utc=datetime(2026, 3, 10, tzinfo=timezone.utc),
            )

            with shard.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(1, report["total_removed"])
            self.assertEqual(2, len(rows))
            self.assertEqual(
                ["expired@example.com", "keep@example.com"],
                [row["Email"] for row in rows],
            )
            self.assertTrue(any(backup_dir.iterdir()))
            report_json = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, report_json["removed_count_per_shard"]["recipients_sendgrid_1.csv"])
            self.assertEqual({"bounced": 1}, report_json["removed_by_status"])

    def test_clean_recipient_shards_preserves_configured_always_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            suppression_csv = base / "sendgrid_suppressions.csv"
            shard = base / "recipients_sendgrid_1.csv"
            backup_dir = base / "backups"
            report_path = base / "cleaning_report.json"

            write_suppression_records(
                suppression_csv,
                {
                    "astraproductionsbyjc@gmail.com": {
                        "email": "astraproductionsbyjc@gmail.com",
                        "status": "Bounced",
                        "code": "550",
                        "reason": "legacy bad row",
                        "last_seen_utc": "2026-03-01T00:00:00+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                        "source_log": "activity.txt",
                    },
                    "remove@example.com": {
                        "email": "remove@example.com",
                        "status": "Bounced",
                        "code": "550",
                        "reason": "user unknown",
                        "last_seen_utc": "2026-03-01T00:00:00+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                        "source_log": "activity.txt",
                    },
                },
            )

            with shard.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email"])
                writer.writeheader()
                writer.writerow({"Email": "astraproductionsbyjc@gmail.com"})
                writer.writerow({"Email": "remove@example.com"})
                writer.writerow({"Email": "keep@example.com"})

            report = clean_recipient_shards(
                suppression_csv,
                [shard],
                backup_dir,
                report_path,
                preserve_emails={"astraproductionsbyjc@gmail.com"},
                reference_utc=datetime(2026, 3, 10, tzinfo=timezone.utc),
            )

            with shard.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(1, report["total_removed"])
            self.assertEqual(
                ["astraproductionsbyjc@gmail.com", "keep@example.com"],
                [row["Email"] for row in rows],
            )
            self.assertEqual(["astraproductionsbyjc@gmail.com"], report["preserved_emails"])

    def test_load_active_suppressed_emails_ignores_legacy_non_suppression_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            suppression_csv = Path(tmpdir) / "sendgrid_suppressions.csv"
            write_suppression_records(
                suppression_csv,
                {
                    "probe@example.com": {
                        "email": "probe@example.com",
                        "status": "processed",
                        "code": "",
                        "reason": "accepted by sendgrid",
                        "last_seen_utc": "2026-03-13T06:11:25+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                    },
                    "bounce@example.com": {
                        "email": "bounce@example.com",
                        "status": "Bounced",
                        "code": "550",
                        "reason": "user unknown",
                        "last_seen_utc": "2026-03-13T06:11:25+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                    },
                },
            )

            blocked, summary = load_active_suppressed_emails(suppression_csv)
            self.assertEqual({"bounce@example.com"}, blocked)
            self.assertEqual(1, summary["total_perm"])


if __name__ == "__main__":
    unittest.main()
