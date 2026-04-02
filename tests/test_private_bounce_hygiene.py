from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from private_bounce_hygiene import (
    append_unique_suppressed_emails,
    extract_bounced_recipients_from_message,
    is_probable_bounce_message,
    run_private_bounce_monitor_cycle,
)


class PrivateBounceHygieneTests(unittest.TestCase):
    def test_extracts_final_recipient_from_bounce_message(self) -> None:
        msg = EmailMessage()
        msg["From"] = "Mail Delivery System <MAILER-DAEMON@example.com>"
        msg["Subject"] = "Undelivered Mail Returned to Sender"
        msg.set_content(
            "This is the mail system at host pe-b.jellyfish-systems.com.\n"
            "Final-Recipient: rfc822; DavidSDale310@gmail.com\n"
            "Diagnostic-Code: smtp; 550 5.1.1 User unknown\n"
        )

        self.assertTrue(is_probable_bounce_message(msg))
        self.assertEqual(
            {"davidsdale310@gmail.com"},
            extract_bounced_recipients_from_message(msg, mailbox_email="jc@astraproductions.co"),
        )

    def test_normal_auto_reply_is_not_treated_as_bounce(self) -> None:
        msg = EmailMessage()
        msg["From"] = "ReadyForTakeoff <readyfortakeoff310@gmail.com>"
        msg["Subject"] = "Please send emails to the author at DavidSDale310@gmail.com Re: Quick thought on your book"
        msg["Auto-Submitted"] = "auto-replied"
        msg.set_content("Please send emails to the author at DavidSDale310@gmail.com")

        self.assertFalse(is_probable_bounce_message(msg))
        self.assertEqual(set(), extract_bounced_recipients_from_message(msg, mailbox_email="jc@astraproductions.co"))

    def test_append_unique_suppressed_emails_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suppressed.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Email"])
                writer.writeheader()
                writer.writerow({"Email": "existing@example.com"})

            result = append_unique_suppressed_emails(
                path,
                ["existing@example.com", "new@example.com", "NEW@example.com"],
            )

            self.assertEqual(1, result["added"])
            self.assertEqual(["new@example.com"], result["added_addresses"])
            with path.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                ["existing@example.com", "new@example.com"],
                [row["Email"] for row in rows],
            )

    def test_monitor_cycle_starts_cooldown_on_clustered_private_bounces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stop_calls: list[str] = []

            def fake_sync(**_: object) -> dict[str, object]:
                return {
                    "generated_at_utc": "2026-04-03T03:00:00+00:00",
                    "report_path": str(tmp / "report.json"),
                    "scanned_messages": 3,
                    "probable_bounce_messages": 3,
                    "matched_messages": 3,
                    "extracted_recipients": 3,
                    "extracted_recipient_list": [
                        "one@example.com",
                        "two@example.com",
                        "three@example.com",
                    ],
                    "added_suppressed": 3,
                    "added_suppressed_addresses": [
                        "one@example.com",
                        "two@example.com",
                        "three@example.com",
                    ],
                }

            def fake_stop(profile_name: str) -> tuple[bool, str]:
                stop_calls.append(profile_name)
                return True, f"Stopped {profile_name}"

            result = run_private_bounce_monitor_cycle(
                profile_name="private_jc",
                monitor_path=tmp / "monitor.json",
                sync_state_path=tmp / "sync.json",
                suppressed_path=tmp / "suppressed.csv",
                report_dir=tmp,
                profile_active=True,
                now=datetime(2026, 4, 3, 3, 0, tzinfo=timezone.utc),
                interval_seconds=60,
                window_minutes=15,
                bounce_threshold=3,
                cooldown_minutes=15,
                sync_func=fake_sync,
                stop_profile=fake_stop,
            )

            self.assertEqual(["private_jc"], stop_calls)
            self.assertTrue(result["cooldown_active"])
            self.assertEqual("Cooldown", result["status_label"])
            self.assertEqual(3, result["recent_bounces_window"])
            self.assertEqual(3, result["last_added_suppressed"])
            self.assertEqual(
                {"sync_completed", "suppression_added", "cooldown_started"},
                {event["event_type"] for event in result["events"][:3]},
            )

    def test_monitor_cycle_auto_resumes_after_private_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            monitor_path = tmp / "monitor.json"
            monitor_path.write_text(
                "{\n"
                '  "private_jc": {\n'
                '    "profile_name": "private_jc",\n'
                '    "enabled": true,\n'
                '    "interval_seconds": 120,\n'
                '    "window_minutes": 15,\n'
                '    "bounce_threshold": 3,\n'
                '    "cooldown_minutes": 15,\n'
                '    "last_sync_utc": "2026-04-03T02:30:00+00:00",\n'
                '    "last_success_utc": "2026-04-03T02:30:00+00:00",\n'
                '    "last_error": "",\n'
                '    "last_error_utc": "",\n'
                '    "last_report_path": "",\n'
                '    "last_scanned_messages": 0,\n'
                '    "last_probable_bounce_messages": 0,\n'
                '    "last_matched_messages": 0,\n'
                '    "last_extracted_recipients": 0,\n'
                '    "last_added_suppressed": 0,\n'
                '    "recent_events": [],\n'
                '    "window_reset_utc": "",\n'
                '    "cooldown_active": true,\n'
                '    "cooldown_started_utc": "2026-04-03T02:30:00+00:00",\n'
                '    "cooldown_until_utc": "2026-04-03T02:40:00+00:00",\n'
                '    "last_cluster_count": 3,\n'
                '    "last_cluster_preview": ["one@example.com"],\n'
                '    "last_cluster_at_utc": "2026-04-03T02:30:00+00:00",\n'
                '    "last_action": "cooldown_started",\n'
                '    "last_action_message": "Stopped private_jc",\n'
                '    "last_action_utc": "2026-04-03T02:30:00+00:00"\n'
                "  }\n"
                "}\n",
                encoding="utf-8",
            )

            start_calls: list[str] = []

            def fake_start(profile_name: str) -> tuple[bool, str]:
                start_calls.append(profile_name)
                return True, f"Started {profile_name}"

            result = run_private_bounce_monitor_cycle(
                profile_name="private_jc",
                monitor_path=monitor_path,
                sync_state_path=tmp / "sync.json",
                suppressed_path=tmp / "suppressed.csv",
                report_dir=tmp,
                profile_active=False,
                now=datetime(2026, 4, 3, 2, 45, tzinfo=timezone.utc),
                interval_seconds=9999,
                window_minutes=15,
                bounce_threshold=3,
                cooldown_minutes=15,
                sync_func=lambda **_: {},
                start_profile=fake_start,
            )

            self.assertEqual(["private_jc"], start_calls)
            self.assertFalse(result["cooldown_active"])
            self.assertEqual("Watching", result["status_label"])
            self.assertEqual("auto_resumed", result["last_action"])
            self.assertEqual("cooldown_ended", result["events"][0]["event_type"])


if __name__ == "__main__":
    unittest.main()
