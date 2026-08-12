from __future__ import annotations

import csv
import io
import signal
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import send_shard
import settings


class SendShardInterruptSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        authority = patch.object(
            send_shard,
            "assert_send_authorized",
            return_value={
                "status": "active",
                "authorized_machine": "mac",
            },
        )
        authority.start()
        self.addCleanup(authority.stop)

    def build_fixture(self, tmpdir: str):
        base = Path(tmpdir)

        shards = base / "data" / "shards"
        logs = base / "data" / "logs"
        state = base / "data" / "state"

        shards.mkdir(parents=True)
        logs.mkdir(parents=True)
        state.mkdir(parents=True)

        queue = shards / "recipients_sendgrid_1.csv"
        recipient_log = logs / "sendgrid_annette_log.csv"
        domain_log = logs / "sendgrid_domain_log.csv"

        unsub = state / "unsubscribed.csv"
        suppress = state / "suppressed.csv"
        sg_suppress = state / "sendgrid_suppressions.csv"
        counters = state / "sendgrid_daily_counters.json"
        events = state / "sendgrid_events.jsonl"
        ledger = state / "lead_ledger.sqlite3"

        account_map = base / "account_map_private_sendgrid.csv"

        queue.write_text(
            "Email,FirstName,BookTitle\n"
            "interrupt-test@example.com,Interrupt,Safe Test\n",
            encoding="utf-8",
        )

        recipient_log.write_text(
            "TimestampUTC,Email,Status,Info\n",
            encoding="utf-8",
        )

        domain_log.write_text(
            "TimestampUTC,Email,Status,Info\n",
            encoding="utf-8",
        )

        unsub.write_text(
            "Email\n",
            encoding="utf-8",
        )

        suppress.write_text(
            "Email\n",
            encoding="utf-8",
        )

        sg_suppress.write_text(
            "Email,Status,Reason,Source,CreatedAtUtc,ExpiresAtUtc\n",
            encoding="utf-8",
        )

        counters.write_text(
            "{}",
            encoding="utf-8",
        )

        events.touch()

        account_map.write_text(
            "RecipientsCSV,LogCSV\n"
            "data/shards/recipients_sendgrid_1.csv,"
            "data/logs/sendgrid_annette_log.csv\n",
            encoding="utf-8",
        )

        profile = {
            **send_shard.PROFILES["sendgrid_annette"],
            "csv": queue.name,
            "log": recipient_log.name,
            "domain_log": domain_log.name,
            "account_map": account_map.name,
            "unsub_csv": unsub.name,
            "suppress_csv": suppress.name,
            "sendgrid_suppression_csv": sg_suppress.name,
            "interval": 0,
            "cooldown_seconds": 0,
            "repeat": False,
            "stop_at_local": "",
            "always_send": "",
            "global_dedupe": False,
            "prune_sent": False,
            "max_messages_1h": 5,
        }

        return {
            "base": base,
            "shards": shards,
            "logs": logs,
            "state": state,
            "queue": queue,
            "recipient_log": recipient_log,
            "domain_log": domain_log,
            "unsub": unsub,
            "suppress": suppress,
            "sg_suppress": sg_suppress,
            "counters": counters,
            "events": events,
            "ledger": ledger,
            "profile": profile,
        }

    def run_sender(
        self,
        fixture,
        *,
        send_side_effect=None,
        domain_finalize_side_effect=None,
    ):
        stdout = io.StringIO()

        domain_calls = []

        def domain_finalize(
            path,
            token,
            email,
            outcome,
            info="",
        ):
            domain_calls.append(
                {
                    "path": Path(path),
                    "token": token,
                    "email": email,
                    "outcome": outcome,
                    "info": info,
                }
            )

            if domain_finalize_side_effect is not None:
                return domain_finalize_side_effect(
                    path,
                    token,
                    email,
                    outcome,
                    info,
                )

            return None

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    settings,
                    "APP_ROOT",
                    fixture["base"],
                )
            )

            stack.enter_context(
                patch.object(
                    settings,
                    "SHARDS_DIR",
                    fixture["shards"],
                )
            )

            stack.enter_context(
                patch.object(
                    settings,
                    "LOGS_DIR",
                    fixture["logs"],
                )
            )

            stack.enter_context(
                patch.object(
                    settings,
                    "STATE_DIR",
                    fixture["state"],
                )
            )

            stack.enter_context(
                patch.object(
                    settings,
                    "WEBHOOK_EVENTS_PATH",
                    fixture["events"],
                )
            )

            stack.enter_context(
                patch.object(
                    settings,
                    "LEAD_LEDGER_DB_PATH",
                    fixture["ledger"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "SHARDS_DIR",
                    fixture["shards"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "LOGS_DIR",
                    fixture["logs"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "STATE_DIR",
                    fixture["state"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "ROOT",
                    fixture["base"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "DEFAULT_UNSUB_CSV",
                    fixture["unsub"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "DEFAULT_SUPPRESS_CSV",
                    fixture["suppress"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "DEFAULT_SENDGRID_SUPPRESSION_CSV",
                    fixture["sg_suppress"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "SENDGRID_COUNTERS_PATH",
                    fixture["counters"],
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "SENDGRID_SKIP_PRUNE_ON_STARTUP",
                    True,
                )
            )

            send_mock = stack.enter_context(
                patch.object(
                    send_shard,
                    "send_via_sendgrid",
                    side_effect=send_side_effect,
                    return_value={
                        "message_id": "synthetic-interrupt-message",
                    },
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "domain_wait_for_slot",
                    return_value="synthetic-slot-token",
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "domain_finalize_attempt",
                    side_effect=domain_finalize,
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard.time,
                    "sleep",
                    return_value=None,
                )
            )

            stack.enter_context(
                patch.object(
                    send_shard,
                    "sleep_with_jitter",
                    return_value=None,
                )
            )

            stack.enter_context(
                patch.dict(
                    send_shard.PROFILES,
                    {
                        "sendgrid_annette":
                            fixture["profile"],
                    },
                    clear=False,
                )
            )

            stack.enter_context(
                patch.dict(
                    send_shard.os.environ,
                    {
                        "SENDGRID_API_KEY":
                            "SG.synthetic-test-key",
                    },
                    clear=False,
                )
            )

            stack.enter_context(
                patch.object(
                    sys,
                    "argv",
                    [
                        "send_shard.py",
                        "--profile",
                        "sendgrid_annette",
                    ],
                )
            )

            stack.enter_context(
                redirect_stdout(stdout)
            )

            send_shard.main()

        return {
            "stdout": stdout.getvalue(),
            "send_mock": send_mock,
            "domain_calls": domain_calls,
        }

    def read_recipient_rows(self, fixture):
        with fixture["recipient_log"].open(
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            return list(csv.DictReader(handle))

    def request_sigint(self):
        handler = signal.getsignal(signal.SIGINT)

        self.assertTrue(
            callable(handler),
            "SIGINT handler was not installed",
        )

        handler(
            signal.SIGINT,
            None,
        )

    def test_sigint_during_provider_submission_is_deferred(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = self.build_fixture(tmpdir)

            def provider_side_effect(*_args, **_kwargs):
                self.request_sigint()

                return {
                    "message_id":
                        "provider-boundary-message",
                }

            with self.assertRaises(KeyboardInterrupt):
                self.run_sender(
                    fixture,
                    send_side_effect=provider_side_effect,
                )

            rows = self.read_recipient_rows(fixture)

            sent = [
                row
                for row in rows
                if row["Status"] == "SENT"
                and row["Email"]
                == "interrupt-test@example.com"
            ]

            self.assertEqual(
                1,
                len(sent),
            )

            self.assertEqual(
                1,
                sum(
                    1
                    for row in rows
                    if row["Status"] == "SENT"
                ),
            )

    def test_sigint_during_domain_finalize_completes_before_interrupt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = self.build_fixture(tmpdir)

            finalized = []

            def finalize_side_effect(
                _path,
                token,
                email,
                outcome,
                info,
            ):
                self.request_sigint()

                finalized.append(
                    (
                        token,
                        email,
                        outcome,
                        info,
                    )
                )

            with self.assertRaises(KeyboardInterrupt):
                self.run_sender(
                    fixture,
                    domain_finalize_side_effect=
                        finalize_side_effect,
                )

            self.assertEqual(
                1,
                len(finalized),
            )

            token, email, outcome, info = finalized[0]

            self.assertEqual(
                "synthetic-slot-token",
                token,
            )

            self.assertEqual(
                "interrupt-test@example.com",
                email,
            )

            self.assertEqual(
                "sent",
                outcome,
            )

            self.assertIn(
                "sg_message_id=",
                info,
            )

            rows = self.read_recipient_rows(fixture)

            sent = [
                row
                for row in rows
                if row["Status"] == "SENT"
            ]

            self.assertEqual(
                1,
                len(sent),
            )

    def test_domain_finalize_failure_never_retries_accepted_send(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = self.build_fixture(tmpdir)

            def finalize_failure(*_args, **_kwargs):
                raise RuntimeError(
                    "synthetic domain finalize failure"
                )

            result = self.run_sender(
                fixture,
                domain_finalize_side_effect=
                    finalize_failure,
            )

            self.assertEqual(
                1,
                result["send_mock"].call_count,
            )

            rows = self.read_recipient_rows(fixture)

            sent = [
                row
                for row in rows
                if row["Status"] == "SENT"
            ]

            self.assertEqual(
                1,
                len(sent),
            )

            self.assertIn(
                "STOP: domain_finalize_failed "
                "after accepted send",
                result["stdout"],
            )

            self.assertNotIn(
                "retry_failed",
                result["stdout"],
            )


    def test_known_accepted_bookkeeping_failure_never_becomes_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = self.build_fixture(tmpdir)
            outcomes = []

            def outcome_side_effect(**kwargs):
                outcome = kwargs.get("outcome")
                outcomes.append(outcome)

                if outcome == "sent":
                    raise RuntimeError(
                        "synthetic accepted-send bookkeeping failure"
                    )

                return None

            with patch.object(
                send_shard,
                "record_send_idempotency_outcome",
                side_effect=outcome_side_effect,
            ):
                result = self.run_sender(fixture)

            self.assertEqual(
                1,
                result["send_mock"].call_count,
            )

            self.assertEqual(
                ["sent"],
                outcomes,
            )

            self.assertNotIn(
                "ambiguous",
                outcomes,
            )

            self.assertIn(
                "STOP: accepted-send bookkeeping failed "
                "after provider submission; recipient "
                "will not be retried",
                result["stdout"],
            )

            rows = self.read_recipient_rows(fixture)

            self.assertEqual(
                1,
                sum(
                    1
                    for row in rows
                    if row["Status"] == "SENT"
                ),
            )


if __name__ == "__main__":
    unittest.main()
