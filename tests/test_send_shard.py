from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import settings
from send_shard import (
    DOMAIN_SLOT_TTL_SECONDS,
    PROVIDER_LIMIT_DEFAULTS,
    PITCH_JC_BODY,
    _parse_ts_safe,
    _resolve_shard_path,
    append_sendgrid_unsubscribe_footer,
    build_sendgrid_astra_custom_args,
    build_sendgrid_list_unsubscribe_header,
    build_message,
    dedupe_scope_for_runtime,
    domain_finalize_attempt,
    domain_wait_for_slot,
    filter_account_map_entries_for_runtime_dedupe,
    is_temporary_auth_failure,
    prioritize_always_send_rows,
)


class SendShardTests(unittest.TestCase):
    def test_resolve_shard_path_creates_managed_private_jc_queue_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            with patch.object(settings, "APP_ROOT", base), patch.object(settings, "SHARDS_DIR", shards), patch(
                "send_shard.SHARDS_DIR", shards
            ):
                resolved = _resolve_shard_path("recipients_private_jc.csv")
                self.assertEqual(shards / "recipients_private_jc.csv", resolved)
                self.assertTrue(resolved.exists())
                self.assertEqual("Email,FirstName,BookTitle\n", resolved.read_text(encoding="utf-8"))

    def test_prioritize_always_send_rows_moves_probe_to_front(self) -> None:
        rows = [
            {"Email": "lead1@example.com", "FirstName": "Lead One"},
            {"Email": "astraproductionsbyjc@gmail.com", "FirstName": "Probe"},
            {"Email": "lead2@example.com", "FirstName": "Lead Two"},
        ]

        ordered = prioritize_always_send_rows(rows, {"astraproductionsbyjc@gmail.com"})

        self.assertEqual(
            [
                "astraproductionsbyjc@gmail.com",
                "lead1@example.com",
                "lead2@example.com",
            ],
            [row["Email"] for row in ordered],
        )

    def test_prioritize_always_send_rows_injects_missing_probe(self) -> None:
        rows = [{"Email": "lead1@example.com"}]

        ordered = prioritize_always_send_rows(rows, {"astraproductionsbyjc@gmail.com"})

        self.assertEqual("astraproductionsbyjc@gmail.com", ordered[0]["Email"])
        self.assertEqual("lead1@example.com", ordered[1]["Email"])

    def test_sendgrid_hourly_cap_matches_parallel_pacing(self) -> None:
        self.assertEqual(180, PROVIDER_LIMIT_DEFAULTS["sendgrid"]["max_messages_1h"])

    def test_slot_reservations_expire_faster_than_sent_rows(self) -> None:
        now = datetime(2026, 3, 13, 13, 0, tzinfo=timezone.utc)
        cutoff = now - timedelta(hours=1)
        slot_cutoff = now - timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS)
        rows = [
            {"TimestampUTC": (now - timedelta(minutes=20)).isoformat(), "Status": "SENT"},
            {"TimestampUTC": (now - timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS + 30)).isoformat(), "Status": "SLOT"},
            {"TimestampUTC": (now - timedelta(seconds=30)).isoformat(), "Status": "SLOT"},
        ]

        expiry_times = []
        for row in rows:
            status = row["Status"]
            ts = _parse_ts_safe(row["TimestampUTC"])
            if status == "SENT" and ts and ts >= cutoff:
                expiry_times.append(ts + timedelta(hours=1))
            elif status == "SLOT" and ts and ts >= slot_cutoff:
                expiry_times.append(ts + timedelta(seconds=DOMAIN_SLOT_TTL_SECONDS))

        self.assertEqual(2, len(expiry_times))
        self.assertTrue(all(expiry >= now for expiry in expiry_times))

    def test_sendgrid_runtime_dedupe_scopes_to_sendgrid_entries_only(self) -> None:
        current_csv = Path("data/shards/recipients_sendgrid_1.csv")
        entries = [
            (Path("data/shards/recipients_private_jc.csv"), Path("data/logs/private_jc_log.csv")),
            (Path("data/shards/recipients_sendgrid_1.csv"), Path("data/logs/sendgrid_annette_log.csv")),
            (Path("data/shards/recipients_sendgrid_2.csv"), Path("data/logs/sendgrid_jordan_log.csv")),
            (Path("data/shards/recipients_1.csv"), Path("data/logs/private_annette_log.csv")),
        ]

        self.assertEqual("sendgrid", dedupe_scope_for_runtime("sendgrid", current_csv))

        filtered = filter_account_map_entries_for_runtime_dedupe(entries, "sendgrid", current_csv)

        self.assertEqual(
            [
                ("recipients_sendgrid_1.csv", "sendgrid_annette_log.csv"),
                ("recipients_sendgrid_2.csv", "sendgrid_jordan_log.csv"),
            ],
            [(recipient.name, log.name) for recipient, log in filtered],
        )

    def test_domain_attempt_slot_finalizes_to_attempt_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            domain_log = Path(tmpdir) / "private_domain_log.csv"

            reservation_token = domain_wait_for_slot(domain_log, 5, jitter_sec=0)
            domain_finalize_attempt(domain_log, reservation_token, "reader@example.com", "temporary_auth_failure", "454 4.7.0")

            with domain_log.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(1, len(rows))
            self.assertEqual("ATTEMPT", rows[0]["Status"])
            self.assertEqual("reader@example.com", rows[0]["Email"])
            self.assertIn("outcome=temporary_auth_failure", rows[0]["Info"])

    def test_temporary_auth_failure_classifier_matches_454(self) -> None:
        self.assertTrue(
            is_temporary_auth_failure(
                454,
                "4.7.0 Temporary authentication failure: Connection lost to authentication server",
            )
        )
        self.assertFalse(is_temporary_auth_failure(535, "5.7.8 Username and Password not accepted"))

    def test_sendgrid_custom_args_use_non_pii_astra_mapping_fields(self) -> None:
        custom_args = build_sendgrid_astra_custom_args(
            profile_name="sendgrid_annette",
            run_id="sendgrid_annette-20260406T000000Z-abc123",
            recipient_email="Reader@Example.com",
            queue_name="recipients_sendgrid_1.csv",
            message_ordinal=42,
        )

        self.assertEqual("sendgrid_annette", custom_args["astra_profile"])
        self.assertEqual("sendgrid_annette-20260406T000000Z-abc123", custom_args["astra_run_id"])
        self.assertIn("astra_recipient_id", custom_args)
        self.assertIn("astra_message_key", custom_args)
        self.assertNotIn("@", custom_args["astra_recipient_id"])
        self.assertNotIn("@", custom_args["astra_message_key"])
        self.assertEqual("sendgrid", custom_args["provider"])

    def test_sender_uses_first_name_in_salutation(self) -> None:
        msg, subject_text, body_text, html_body, cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email="reader@example.com",
            author="Anna Example",
            book_title="Sample Book",
            subject="Quick thought on your book",
            body_template=PITCH_JC_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
        )

        self.assertIn("Hi Anna,", body_text)
        self.assertNotIn("Hi ,", body_text)
        self.assertEqual("Quick thought on your book", subject_text)
        self.assertIsNotNone(msg)
        self.assertIsNotNone(html_body)

    def test_sender_uses_neutral_fallback_when_first_name_missing(self) -> None:
        _msg, _subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email="reader@example.com",
            author="",
            book_title="Sample Book",
            subject="Quick thought on your book",
            body_template=PITCH_JC_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
        )

        self.assertIn("Hi there,", body_text)
        self.assertNotIn("Hi ,", body_text)

    def test_sendgrid_unsubscribe_footer_uses_mailto_list_link(self) -> None:
        text_content, html_content = append_sendgrid_unsubscribe_footer(
            "Hello there",
            "<html><body>Hello there</body></html>",
            "unsubscribe@barnesnoblemarketing.com",
        )

        self.assertIn("Unsubscribe from this list", text_content)
        self.assertIn("<%asm_group_unsubscribe_raw_url%>", text_content)
        self.assertIn("Unsubscribe from this list", html_content)
        self.assertIn("<%asm_group_unsubscribe_raw_url%>", html_content)
        self.assertNotIn("asm_group_unsubscribe_url", html_content)

    def test_sendgrid_list_unsubscribe_header_includes_mailto_and_https(self) -> None:
        header = build_sendgrid_list_unsubscribe_header("unsubscribe@barnesnoblemarketing.com")

        self.assertIn("<mailto:unsubscribe@barnesnoblemarketing.com?subject=unsubscribe&body=unsubscribe>", header)
        self.assertIn("<%asm_group_unsubscribe_raw_url%>", header)


if __name__ == "__main__":
    unittest.main()
