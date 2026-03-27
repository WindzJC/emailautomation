from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from tools import post_run_report


class PostRunReportTests(unittest.TestCase):
    def test_classify_failure_categories(self) -> None:
        self.assertEqual(
            "mailbox_not_found",
            post_run_report.classify_failure("550 5.1.1 recipient does not exist here", "550", "bounce"),
        )
        self.assertEqual(
            "mailbox_disabled",
            post_run_report.classify_failure("554.30 mailbox is disabled", "554", "bounce"),
        )
        self.assertEqual(
            "reputation_block",
            post_run_report.classify_failure("blocked by Validity - https://senderscore.org/blocklist-lookup/", "550", "bounce"),
        )
        self.assertEqual(
            "policy_denied",
            post_run_report.classify_failure("", "550", "bounce", bounce_classification="Content"),
        )
        self.assertEqual(
            "mailbox_not_found",
            post_run_report.classify_failure("550 5.1.1 Not our Customer", "550", "bounce"),
        )
        self.assertEqual(
            "mailbox_full",
            post_run_report.classify_failure(
                "552 5.2.2 The recipient's inbox is out of storage space. Please try again later.",
                "552",
                "bounce",
            ),
        )
        self.assertEqual(
            "reputation_block",
            post_run_report.classify_failure(
                "554 resimta-c2p-558934.sys.comcast.net found on one or more DNSBLs",
                "554",
                "bounce",
            ),
        )
        self.assertEqual(
            "spam_report",
            post_run_report.classify_failure("", "", "spamreport"),
        )

    def test_build_post_run_report_outputs_domain_metrics_and_suppressions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles = {
                "sendgrid_alpha": {
                    "provider": "sendgrid",
                    "csv": "recipients_alpha.csv",
                    "log": "sendgrid_alpha_log.csv",
                    "from_email": "alpha@example.com",
                    "always_send": "probe@example.com",
                }
            }
            self._write_log(
                root / "sendgrid_alpha_log.csv",
                [
                    ("2026-03-13T12:00:00+00:00", "probe@example.com", "SENT", "sg_message_id=probe"),
                    ("2026-03-13T12:01:00+00:00", "reader@gmail.com", "SENT", "sg_message_id=msg-1"),
                    ("2026-03-13T12:02:00+00:00", "dead@yahoo.com", "SENT", "sg_message_id=msg-2"),
                ],
            )
            self._write_events(
                root / "sendgrid_events.jsonl",
                [
                    {
                        "processed_at_utc": "2026-03-13T12:01:30+00:00",
                        "received_at_utc": "2026-03-13T12:01:30+00:00",
                        "message_id": "msg-1",
                        "dedupe_key": "msg-1-processed",
                        "email": "reader@gmail.com",
                        "domain": "gmail.com",
                        "status": "processed",
                        "response": "",
                        "profile": "sendgrid_alpha",
                    },
                    {
                        "processed_at_utc": "2026-03-13T12:02:30+00:00",
                        "received_at_utc": "2026-03-13T12:02:30+00:00",
                        "message_id": "msg-1",
                        "dedupe_key": "msg-1-delivered",
                        "email": "reader@gmail.com",
                        "domain": "gmail.com",
                        "status": "delivered",
                        "response": "250 OK",
                        "profile": "sendgrid_alpha",
                    },
                    {
                        "processed_at_utc": "2026-03-13T12:03:00+00:00",
                        "received_at_utc": "2026-03-13T12:03:00+00:00",
                        "message_id": "msg-1",
                        "dedupe_key": "msg-1-open",
                        "email": "reader@gmail.com",
                        "domain": "gmail.com",
                        "status": "open",
                        "response": "",
                        "profile": "sendgrid_alpha",
                    },
                    {
                        "processed_at_utc": "2026-03-13T12:03:30+00:00",
                        "received_at_utc": "2026-03-13T12:03:30+00:00",
                        "message_id": "msg-1",
                        "dedupe_key": "msg-1-open",
                        "email": "reader@gmail.com",
                        "domain": "gmail.com",
                        "status": "open",
                        "response": "",
                        "profile": "sendgrid_alpha",
                    },
                    {
                        "processed_at_utc": "2026-03-13T12:04:00+00:00",
                        "received_at_utc": "2026-03-13T12:04:00+00:00",
                        "message_id": "msg-2",
                        "dedupe_key": "msg-2-bounce",
                        "email": "dead@yahoo.com",
                        "domain": "yahoo.com",
                        "status": "bounce",
                        "bounce_classification": "Invalid Address",
                        "response": "550 5.1.1 recipient does not exist here",
                        "profile": "sendgrid_alpha",
                    },
                ],
            )
            self._write_suppressions(root / "sendgrid_suppressions.csv", ["existing@example.com"])

            start = datetime(2026, 3, 13, 0, 0, tzinfo=timezone.utc)
            end = datetime(2026, 3, 14, 0, 0, tzinfo=timezone.utc)
            report = post_run_report.build_post_run_report(
                root=root,
                start_utc=start,
                end_utc=end,
                report_tz=ZoneInfo("UTC"),
                profile_configs=profiles,
                suppression_path=root / "sendgrid_suppressions.csv",
            )

        self.assertEqual(3, report["totals"]["accepted_total"])
        self.assertEqual(2, report["totals"]["real_leads"])
        self.assertEqual(1, report["totals"]["delivered"])
        self.assertEqual(1, report["totals"]["failures"])
        self.assertEqual(1, report["totals"]["open_unique"])
        self.assertEqual(1, report["profiles"][0]["open_unique"])
        self.assertEqual(1, report["profiles"][0]["open_total"])
        self.assertEqual("sendgrid_alpha", report["best_profile"]["profile"])
        yahoo = next(row for row in report["domain_breakdown"] if row["domain"] == "yahoo.com")
        self.assertEqual(1, yahoo["failures"])
        hotspot = next(row for row in report["profile_domain_breakdown"] if row["domain"] == "yahoo.com")
        self.assertEqual("sendgrid_alpha", hotspot["profile"])
        self.assertEqual(
            {
                "bounces_total": 1,
                "bounces_with_bounce_classification": 1,
                "bounces_missing_bounce_classification": 0,
            },
            report["bounce_classification_coverage"],
        )
        self.assertEqual("yahoo.com", report["worst_domain_per_profile"][0]["domain"])
        self.assertEqual(0.0, report["profile_failure_rate_excluding_top_domain"]["sendgrid_alpha"])
        self.assertEqual(1, report["failure_categories"]["mailbox_not_found"])
        self.assertEqual("dead@yahoo.com", report["suppress_now"][0]["email"])
        self.assertEqual([], report["unknown_samples"])

    def test_unknown_samples_capture_raw_reasons(self) -> None:
        message = post_run_report.AcceptedMessage(
            profile="sendgrid_alpha",
            email="mystery@example.com",
            domain="example.com",
            from_email="alpha@example.com",
            accepted_at_utc=datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc),
            accepted_at_local="2026-03-13 12:00:00 UTC",
            message_id="msg-9",
            is_canary=False,
            source_log="sendgrid_alpha_log.csv",
            info="sg_message_id=msg-9",
            events=[
                {
                    "status": "bounce",
                    "code": "550",
                    "response": "550 weird provider failure text",
                    "bounce_classification": "",
                }
            ],
        )

        _, _, _, _, unknown_samples = post_run_report.build_failure_sections([message])

        self.assertEqual(1, len(unknown_samples))
        self.assertEqual("550 weird provider failure text", unknown_samples[0]["reason"])
        self.assertEqual(1, unknown_samples[0]["count"])

    def test_build_failure_sections_uses_fallback_patterns_from_unknown_samples(self) -> None:
        message = post_run_report.AcceptedMessage(
            profile="sendgrid_alpha",
            email="maryguerin@comcast.net",
            domain="comcast.net",
            from_email="alpha@example.com",
            accepted_at_utc=datetime(2026, 3, 13, 12, 0, tzinfo=timezone.utc),
            accepted_at_local="2026-03-13 12:00:00 UTC",
            message_id="msg-10",
            is_canary=False,
            source_log="sendgrid_alpha_log.csv",
            info="sg_message_id=msg-10",
            events=[
                {
                    "status": "bounce",
                    "code": "5.1.1",
                    "response": "550 5.1.1 Not our Customer",
                    "bounce_classification": "",
                }
            ],
        )

        overall, _, _, _, unknown_samples = post_run_report.build_failure_sections([message])

        self.assertEqual({"mailbox_not_found": 1}, overall)
        self.assertEqual([], unknown_samples)

    def test_apply_suppressions_skips_existing_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sendgrid_suppressions.csv"
            self._write_suppressions(path, ["dead@yahoo.com"])
            rows = [
                {
                    "email": "dead@yahoo.com",
                    "profile": "sendgrid_alpha",
                    "domain": "yahoo.com",
                    "outcome": "bounce",
                    "category": "mailbox_not_found",
                    "reason": "550 5.1.1",
                    "accepted_at_utc": "2026-03-13T12:04:00+00:00",
                    "accepted_at_local": "2026-03-13 12:04:00 UTC",
                },
                {
                    "email": "new@yahoo.com",
                    "profile": "sendgrid_alpha",
                    "domain": "yahoo.com",
                    "outcome": "bounce",
                    "category": "mailbox_not_found",
                    "reason": "550 5.1.1",
                    "accepted_at_utc": "2026-03-13T12:05:00+00:00",
                    "accepted_at_local": "2026-03-13 12:05:00 UTC",
                },
            ]
            added = post_run_report.apply_suppressions(path, rows)
            self.assertEqual(1, added)
            with path.open(newline="", encoding="utf-8") as handle:
                emails = [row["email"] for row in csv.DictReader(handle)]
            self.assertEqual(["dead@yahoo.com", "new@yahoo.com"], emails)

    @staticmethod
    def _write_log(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["TimestampUTC", "Email", "Status", "Info"])
            writer.writerows(rows)

    @staticmethod
    def _write_events(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    @staticmethod
    def _write_suppressions(path: Path, emails: list[str]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["email", "status", "code", "reason", "last_seen_utc", "is_permanent", "ttl_until_utc"])
            for email in emails:
                writer.writerow([email, "bounce", "", "", "2026-03-13T00:00:00+00:00", "true", ""])


if __name__ == "__main__":
    unittest.main()
