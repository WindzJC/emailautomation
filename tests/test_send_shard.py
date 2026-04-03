from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from send_shard import (
    DOMAIN_SLOT_TTL_SECONDS,
    PROVIDER_LIMIT_DEFAULTS,
    _parse_ts_safe,
    dedupe_scope_for_runtime,
    filter_account_map_entries_for_runtime_dedupe,
    prioritize_always_send_rows,
)


class SendShardTests(unittest.TestCase):
    def test_prioritize_always_send_rows_moves_probe_to_front(self) -> None:
        rows = [
            {"Email": "lead1@example.com", "AuthorName": "Lead One"},
            {"Email": "astraproductionsbyjc@gmail.com", "AuthorName": "Probe"},
            {"Email": "lead2@example.com", "AuthorName": "Lead Two"},
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


if __name__ == "__main__":
    unittest.main()
