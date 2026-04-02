from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from private_bounce_hygiene import (
    append_unique_suppressed_emails,
    extract_bounced_recipients_from_message,
    is_probable_bounce_message,
    run_private_bounce_monitor_cycle,
    sync_private_bounces,
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

    def test_sync_private_bounces_defaults_to_inbox_and_spam(self) -> None:
        class FakeIMAP:
            def __init__(self, host: str, port: int, timeout: int = 0) -> None:
                self.current_folder = "INBOX"
                self._messages = {
                    "INBOX": {},
                    "Spam": {
                        1: self._build_bounce(
                            "Thu, 02 Apr 2026 20:30:01 +0000",
                            "one@example.com",
                        ),
                    },
                    "Trash": {
                        14: self._build_bounce(
                            "Thu, 02 Apr 2026 20:34:48 +0000",
                            "two@example.com",
                        ),
                    },
                }

            @staticmethod
            def _build_bounce(date_header: str, recipient: str) -> bytes:
                msg = EmailMessage()
                msg["From"] = "Mail Delivery System <MAILER-DAEMON@example.com>"
                msg["Subject"] = "Undelivered Mail Returned to Sender"
                msg["Date"] = date_header
                msg.set_content(
                    "This is the mail system at host pe-b.jellyfish.systems.\n"
                    f"Final-Recipient: rfc822; {recipient}\n"
                    "Diagnostic-Code: smtp; 550 5.1.1 User unknown\n"
                )
                return msg.as_bytes()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, email_addr: str, password: str):
                return ("OK", [b"logged in"])

            def select(self, folder: str, readonly: bool = True):
                self.current_folder = folder
                count = len(self._messages.get(folder, {}))
                return ("OK", [str(count).encode()])

            def uid(self, command: str, *args):
                command = command.lower()
                folder_messages = self._messages.get(self.current_folder, {})
                if command == "search":
                    if args and len(args) >= 2 and str(args[1]).endswith(":*"):
                        start_uid = int(str(args[1]).split(":", 1)[0])
                        uids = [uid for uid in sorted(folder_messages) if uid >= start_uid]
                    else:
                        uids = sorted(folder_messages)
                    return ("OK", [b" ".join(str(uid).encode() for uid in uids)])
                if command == "fetch":
                    uid = int(str(args[0]))
                    payload = folder_messages[uid]
                    return ("OK", [(b"RFC822", payload)])
                raise AssertionError(f"Unsupported command: {command}")

            def logout(self):
                return ("BYE", [b"logout"])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_path = tmp / "state.json"
            suppressed_path = tmp / "suppressed.csv"
            with patch.dict(os.environ, {"PRIVATE_JC_PASSWORD": "secret"}, clear=False):
                with patch("private_bounce_hygiene.imaplib.IMAP4_SSL", FakeIMAP):
                    report = sync_private_bounces(
                        profile_name="private_jc",
                        state_path=state_path,
                        suppressed_path=suppressed_path,
                        report_dir=tmp,
                    )

            self.assertEqual(["INBOX", "Spam"], report["folders"])
            self.assertEqual(1, report["scanned_messages"])
            self.assertEqual(1, report["matched_messages"])
            self.assertEqual({"one@example.com"}, set(report["extracted_recipient_list"]))
            self.assertEqual(1, report["added_suppressed"])

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                {"INBOX": 0, "Spam": 1},
                state["private_jc"]["last_uid_by_folder"],
            )

    def test_sync_private_bounces_can_include_trash_for_backfill(self) -> None:
        class FakeIMAP:
            def __init__(self, host: str, port: int, timeout: int = 0) -> None:
                self.current_folder = "INBOX"
                self._messages = {
                    "INBOX": {},
                    "Spam": {},
                    "Trash": {
                        14: self._build_bounce(
                            "Thu, 02 Apr 2026 20:34:48 +0000",
                            "two@example.com",
                        ),
                    },
                }

            @staticmethod
            def _build_bounce(date_header: str, recipient: str) -> bytes:
                msg = EmailMessage()
                msg["From"] = "Mail Delivery System <MAILER-DAEMON@example.com>"
                msg["Subject"] = "Undelivered Mail Returned to Sender"
                msg["Date"] = date_header
                msg.set_content(
                    "This is the mail system at host pe-b.jellyfish.systems.\n"
                    f"Final-Recipient: rfc822; {recipient}\n"
                    "Diagnostic-Code: smtp; 550 5.1.1 User unknown\n"
                )
                return msg.as_bytes()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, email_addr: str, password: str):
                return ("OK", [b"logged in"])

            def select(self, folder: str, readonly: bool = True):
                self.current_folder = folder
                count = len(self._messages.get(folder, {}))
                return ("OK", [str(count).encode()])

            def uid(self, command: str, *args):
                command = command.lower()
                folder_messages = self._messages.get(self.current_folder, {})
                if command == "search":
                    if args and len(args) >= 2 and str(args[1]).endswith(":*"):
                        start_uid = int(str(args[1]).split(":", 1)[0])
                        uids = [uid for uid in sorted(folder_messages) if uid >= start_uid]
                    else:
                        uids = sorted(folder_messages)
                    return ("OK", [b" ".join(str(uid).encode() for uid in uids)])
                if command == "fetch":
                    uid = int(str(args[0]))
                    payload = folder_messages[uid]
                    return ("OK", [(b"RFC822", payload)])
                raise AssertionError(f"Unsupported command: {command}")

            def logout(self):
                return ("BYE", [b"logout"])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_path = tmp / "state.json"
            suppressed_path = tmp / "suppressed.csv"
            with patch.dict(os.environ, {"PRIVATE_JC_PASSWORD": "secret"}, clear=False):
                with patch("private_bounce_hygiene.imaplib.IMAP4_SSL", FakeIMAP):
                    report = sync_private_bounces(
                        profile_name="private_jc",
                        folders=["INBOX", "Spam", "Trash"],
                        state_path=state_path,
                        suppressed_path=suppressed_path,
                        report_dir=tmp,
                    )

            self.assertEqual(["INBOX", "Spam", "Trash"], report["folders"])
            self.assertEqual(1, report["scanned_messages"])
            self.assertEqual(1, report["matched_messages"])
            self.assertEqual({"two@example.com"}, set(report["extracted_recipient_list"]))
            self.assertEqual(1, report["added_suppressed"])

    def test_monitor_cycle_uses_message_dates_for_recent_bounce_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

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
                    "extracted_recipient_events": [
                        {"email": "one@example.com", "detected_at_utc": "2026-04-03T01:00:00+00:00"},
                        {"email": "two@example.com", "detected_at_utc": "2026-04-03T01:00:00+00:00"},
                        {"email": "three@example.com", "detected_at_utc": "2026-04-03T01:00:00+00:00"},
                    ],
                    "added_suppressed": 3,
                    "added_suppressed_addresses": [
                        "one@example.com",
                        "two@example.com",
                        "three@example.com",
                    ],
                }

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
                stop_profile=lambda profile_name: (True, f"Stopped {profile_name}"),
            )

            self.assertFalse(result["cooldown_active"])
            self.assertEqual("Watching", result["status_label"])
            self.assertEqual(0, result["recent_bounces_window"])
            self.assertEqual(3, result["last_added_suppressed"])

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
