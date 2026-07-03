from __future__ import annotations

import csv
import imaplib
import io
import json
import smtplib
import sys
import tempfile
import unittest
from contextlib import ExitStack
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import send_shard
import settings
import dashboard_core
import live_dashboard
from tools.diagnose_private_jc_auth import run_diagnostic
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
    count_prunable_rows,
    dedupe_scope_for_runtime,
    domain_finalize_attempt,
    domain_wait_for_slot,
    filter_account_map_entries_for_runtime_dedupe,
    get_personalization_name,
    is_temporary_auth_failure,
    prioritize_always_send_rows,
    prune_sent_from_csv,
    render_message_parts,
    worker_stop_category,
)


class SendShardTests(unittest.TestCase):
    def test_private_jc_auth_diagnostic_logs_in_without_sending_or_printing_secret(self) -> None:
        calls: list[str] = []

        class FakeSMTP:
            def quit(self) -> None:
                calls.append("smtp_quit")

        class FakeIMAP:
            def login(self, _user: str, password: str) -> None:
                self.password = password
                calls.append("imap_login")

            def logout(self) -> None:
                calls.append("imap_logout")

        output = io.StringIO()
        with patch.dict(send_shard.os.environ, {"PRIVATE_JC_PASSWORD": "synthetic-secret"}, clear=False):
            with redirect_stdout(output):
                result = run_diagnostic(
                    check_smtp=True,
                    check_imap=True,
                    smtp_login_func=lambda *_args: FakeSMTP(),
                    imap_factory=lambda *_args, **_kwargs: FakeIMAP(),
                )

        self.assertEqual(0, result)
        self.assertEqual(["smtp_quit", "imap_login", "imap_logout"], calls)
        self.assertIn("key=PRIVATE_JC_PASSWORD", output.getvalue())
        self.assertNotIn("synthetic-secret", output.getvalue())

    def test_private_jc_auth_diagnostic_distinguishes_missing_dev_credential(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            env_files = [Path(tmpdir) / ".env.local", Path(tmpdir) / ".env"]
            with patch.dict(send_shard.os.environ, {"PRIVATE_JC_PASSWORD": ""}, clear=False):
                with redirect_stdout(output):
                    result = run_diagnostic(check_smtp=True, check_imap=True, env_files=env_files)

        text = output.getvalue()
        self.assertEqual(2, result)
        self.assertIn("ENV FILE STATUS: .env.local=missing .env=missing", text)
        self.assertIn("PRIVATE_JC_PASSWORD is not configured in this repo/environment", text)
        self.assertIn("If this is Mac/dev, test on the Windows/WSL live repo instead", text)
        self.assertIn("missing credential is not proof that the password is wrong", text)
        self.assertIn("category=credential_missing", text)

    def test_private_jc_auth_diagnostic_distinguishes_rejected_credentials(self) -> None:
        class RejectingIMAP:
            def login(self, _user: str, _password: str) -> None:
                raise imaplib.IMAP4.error("synthetic rejection")

            def logout(self) -> None:
                pass

        def reject_smtp(*_args: object) -> object:
            raise smtplib.SMTPAuthenticationError(535, b"synthetic rejection")

        output = io.StringIO()
        with patch.dict(send_shard.os.environ, {"PRIVATE_JC_PASSWORD": "synthetic-secret"}, clear=False):
            with redirect_stdout(output):
                result = run_diagnostic(
                    check_smtp=True,
                    check_imap=True,
                    smtp_login_func=reject_smtp,
                    imap_factory=lambda *_args, **_kwargs: RejectingIMAP(),
                    env_files=[],
                )

        text = output.getvalue()
        self.assertEqual(1, result)
        self.assertIn("category=smtp_auth_failure", text)
        self.assertIn("category=imap_auth_failure", text)
        self.assertNotIn("category=credential_missing", text)
        self.assertNotIn("synthetic-secret", text)

    def test_worker_stop_categories_distinguish_operator_failure_modes(self) -> None:
        self.assertEqual("manual_interruption", worker_stop_category("interrupted"))
        self.assertEqual("smtp_auth_failure", worker_stop_category("auth_error"))
        self.assertEqual("smtp_reconnect_failure", worker_stop_category("reconnect_failed"))
        self.assertEqual("queue_exhausted", worker_stop_category("queue_exhausted"))

    def test_personalization_name_blocks_raw_fallbacks_when_not_allowed(self) -> None:
        row = {
            "FirstName": "",
            "first_name_clean": "",
            "firstname": "A",
            "authorname": "A Murray",
            "name": "A Murray",
            "personalization_allowed": "false",
        }

        personalization_name = get_personalization_name(row)
        author = send_shard.choose_salutation_name(personalization_name, "test@example.com")
        _, body_text, _, _ = render_message_parts(
            author,
            "",
            "Subject",
            "Hi {FirstName},\n\nBody",
            "unsubscribe@example.com",
            signature_file=None,
        )

        self.assertEqual(personalization_name, "")
        self.assertTrue(body_text.startswith("Hi there,"))

    def test_personalization_name_uses_clean_first_name_when_allowed(self) -> None:
        row = {
            "first_name_clean": "José",
            "personalization_allowed": "true",
        }

        self.assertEqual(get_personalization_name(row), "José")

    def test_personalization_name_keeps_old_safe_rows_without_guard_fields(self) -> None:
        old_row = {"Email": "safe@example.com", "FirstName": "Alice"}
        blocked_new_row = {
            "Email": "unsafe@example.com",
            "FirstName": "A",
            "authorname": "A Murray",
            "personalization_allowed": "false",
        }

        self.assertEqual(get_personalization_name(old_row), "Alice")
        self.assertEqual(get_personalization_name(blocked_new_row), "")

    def test_sendgrid_profile_defaults_use_35s_pacing_and_keep_noon_stop(self) -> None:
        for profile_name in [
            "sendgrid_annette",
            "sendgrid_jordan",
            "sendgrid_jodi",
            "sendgrid_alison",
            "sendgrid_fiorela",
        ]:
            profile = send_shard.PROFILES[profile_name]
            self.assertEqual(35, profile["interval"])
            self.assertEqual(35, profile["cooldown_seconds"])
            self.assertEqual("12:00", profile["stop_at_local"])

    def test_private_jc_pacing_remains_unchanged(self) -> None:
        profile = send_shard.PROFILES["private_jc"]
        self.assertEqual(60, profile["interval"])
        self.assertEqual(60, profile["cooldown_seconds"])
        self.assertEqual("12:00", profile["stop_at_local"])

    def test_attempt_outcome_sent_counts_as_authoritative_sent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "sendgrid_domain_log.csv"
            log_path.write_text(
                "TimestampUTC,Email,Status,Info\n"
                "2026-06-25T09:20:00+00:00,author@example.test,ATTEMPT,outcome=sent sg_message_id=abc\n",
                encoding="utf-8",
            )

            self.assertIn("author@example.test", send_shard.load_already_done(log_path))
            self.assertTrue(send_shard.email_logged_sent(log_path, "author@example.test"))
            self.assertTrue(send_shard.email_logged_authoritative_sent_any([log_path], "author@example.test"))

    def test_send_idempotency_reservation_blocks_duplicate_campaign_provider_email(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "send_idempotency.sqlite3"

            self.assertTrue(
                send_shard.reserve_send_idempotency(
                    campaign_id="campaign-a",
                    provider="sendgrid",
                    email="author@example.test",
                    profile="sendgrid_annette",
                    queue_file="recipients_sendgrid_1.csv",
                    db_path=db_path,
                )[0]
            )
            self.assertFalse(
                send_shard.reserve_send_idempotency(
                    campaign_id="campaign-a",
                    provider="sendgrid",
                    email="AUTHOR@example.test",
                    profile="sendgrid_annette",
                    queue_file="recipients_sendgrid_1.csv",
                    db_path=db_path,
                )[0]
            )
            self.assertTrue(
                send_shard.reserve_send_idempotency(
                    campaign_id="campaign-a",
                    provider="private",
                    email="author@example.test",
                    profile="private_jc",
                    queue_file="recipients_private_jc.csv",
                    db_path=db_path,
                )[0]
            )

    def test_claim_queue_row_atomically_removes_single_recipient(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            queue_path.write_text(
                "Email,FirstName\n"
                "author@example.test,Ada\n",
                encoding="utf-8",
            )

            self.assertTrue(send_shard.claim_queue_row(queue_path, "author@example.test"))
            self.assertFalse(send_shard.claim_queue_row(queue_path, "author@example.test"))
            self.assertNotIn("author@example.test", queue_path.read_text(encoding="utf-8"))

    def test_profile_runtime_lock_prevents_duplicate_profile_acquire(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(send_shard, "STATE_DIR", Path(tmpdir)):
                lock = send_shard.acquire_profile_runtime_lock("sendgrid_annette")
                with lock:
                    status = send_shard.profile_runtime_lock_status("sendgrid_annette")
                    self.assertTrue(status["locked"])
                    with self.assertRaises(RuntimeError):
                        with send_shard.acquire_profile_runtime_lock("sendgrid_annette"):
                            pass

                self.assertFalse(send_shard.profile_runtime_lock_status("sendgrid_annette")["locked"])

    def test_managed_dashboard_profile_refuses_stale_root_queue_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            shards = base / "data" / "shards"
            shards.mkdir(parents=True)
            root_queue = base / "recipients_sendgrid_1.csv"
            shard_queue = shards / "recipients_sendgrid_1.csv"
            profile = {**send_shard.PROFILES["sendgrid_annette"], "csv": "recipients_sendgrid_1.csv"}

            with patch.object(send_shard, "SHARDS_DIR", shards), patch.dict(
                send_shard.PROFILES,
                {"sendgrid_annette": profile},
                clear=False,
            ):
                self.assertFalse(send_shard.managed_dashboard_queue_path_allowed("sendgrid_annette", root_queue))
                self.assertTrue(send_shard.managed_dashboard_queue_path_allowed("sendgrid_annette", shard_queue))

    def _build_sendgrid_runtime_fixture(self, tmpdir: str) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path, dict[str, object]]:
        base = Path(tmpdir)
        shards = base / "data" / "shards"
        logs = base / "data" / "logs"
        state = base / "data" / "state"
        shards.mkdir(parents=True)
        logs.mkdir(parents=True)
        state.mkdir(parents=True)

        csv_path = shards / "recipients_sendgrid_1.csv"
        log_path = logs / "sendgrid_annette_log.csv"
        account_map = base / "account_map_private_sendgrid.csv"
        unsub = state / "unsubscribed.csv"
        suppress = state / "suppressed.csv"
        sg_suppress = state / "sendgrid_suppressions.csv"
        counters = state / "sendgrid_daily_counters.json"

        csv_path.write_text(
            "Email,FirstName,BookTitle\n"
            "already-sent@example.com,Sent,Book A\n"
            "astraproductionsbyjc@gmail.com,Probe,Book B\n"
            "fresh@example.com,Fresh,Book C\n",
            encoding="utf-8",
        )
        log_path.write_text(
            "TimestampUTC,Email,Status,Info\n"
            "2026-04-10T00:00:00+00:00,already-sent@example.com,SENT,\n"
            "2026-04-10T00:00:01+00:00,astraproductionsbyjc@gmail.com,SENT,\n",
            encoding="utf-8",
        )
        account_map.write_text(
            "RecipientsCSV,LogCSV\n"
            "data/shards/recipients_sendgrid_1.csv,data/logs/sendgrid_annette_log.csv\n",
            encoding="utf-8",
        )
        unsub.write_text("Email\n", encoding="utf-8")
        suppress.write_text("Email\n", encoding="utf-8")
        sg_suppress.write_text("Email,Status,Reason,Source,CreatedAtUtc,ExpiresAtUtc\n", encoding="utf-8")
        counters.write_text("{}", encoding="utf-8")

        profile = {
            **send_shard.PROFILES["sendgrid_annette"],
            "csv": csv_path.name,
            "log": log_path.name,
            "account_map": account_map.name,
            "unsub_csv": unsub.name,
            "suppress_csv": suppress.name,
            "sendgrid_suppression_csv": sg_suppress.name,
            "interval": 0,
            "repeat": False,
        }
        return base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile

    def test_preflight_reports_prune_without_mutating_shard_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile = self._build_sendgrid_runtime_fixture(tmpdir)
            profile["interval"] = 35
            profile["cooldown_seconds"] = 35
            profile["repeat"] = True
            original_csv = csv_path.read_text(encoding="utf-8")

            stdout = io.StringIO()
            with patch.object(settings, "APP_ROOT", base), patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(settings, "STATE_DIR", state), patch.object(
                send_shard, "SHARDS_DIR", shards
            ), patch.object(
                send_shard, "LOGS_DIR", logs
            ), patch.object(
                send_shard, "STATE_DIR", state
            ), patch.object(
                send_shard, "ROOT", base
            ), patch.object(
                send_shard, "DEFAULT_UNSUB_CSV", unsub
            ), patch.object(
                send_shard, "DEFAULT_SUPPRESS_CSV", suppress
            ), patch.object(
                send_shard, "DEFAULT_SENDGRID_SUPPRESSION_CSV", sg_suppress
            ), patch.object(
                send_shard, "SENDGRID_COUNTERS_PATH", counters
            ), patch.dict(
                send_shard.PROFILES, {"sendgrid_annette": profile}, clear=False
            ), patch.dict(
                send_shard.os.environ, {"SENDGRID_API_KEY": "SG.test-key"}, clear=False
            ), patch.object(
                sys, "argv", ["send_shard.py", "--profile", "sendgrid_annette", "--preflight"]
            ), redirect_stdout(stdout):
                send_shard.main()

            self.assertEqual(original_csv, csv_path.read_text(encoding="utf-8"))
            self.assertIn("PRUNE: would remove 1 from recipients_sendgrid_1.csv (preflight only)", stdout.getvalue())
            self.assertIn("PACE RESOLVED: profile=sendgrid_annette", stdout.getvalue())
            self.assertIn("effective_spacing=35s", stdout.getvalue())
            self.assertIn("PREFLIGHT: ok (no sending).", stdout.getvalue())

    def test_startup_guard_skips_initial_prune_without_mutating_shard_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile = self._build_sendgrid_runtime_fixture(tmpdir)
            original_csv = csv_path.read_text(encoding="utf-8")

            stdout = io.StringIO()
            with patch.object(settings, "APP_ROOT", base), patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(settings, "STATE_DIR", state), patch.object(
                send_shard, "SHARDS_DIR", shards
            ), patch.object(
                send_shard, "LOGS_DIR", logs
            ), patch.object(
                send_shard, "STATE_DIR", state
            ), patch.object(
                send_shard, "ROOT", base
            ), patch.object(
                send_shard, "DEFAULT_UNSUB_CSV", unsub
            ), patch.object(
                send_shard, "DEFAULT_SUPPRESS_CSV", suppress
            ), patch.object(
                send_shard, "DEFAULT_SENDGRID_SUPPRESSION_CSV", sg_suppress
            ), patch.object(
                send_shard, "SENDGRID_COUNTERS_PATH", counters
            ), patch.object(
                send_shard, "SENDGRID_SKIP_PRUNE_ON_STARTUP", True
            ), patch.dict(
                send_shard.PROFILES, {"sendgrid_annette": profile}, clear=False
            ), patch.object(
                sys, "argv", ["send_shard.py", "--profile", "sendgrid_annette", "--dry_run", "--max_total", "1"]
            ), redirect_stdout(stdout):
                send_shard.main()

            self.assertEqual(original_csv, csv_path.read_text(encoding="utf-8"))
            self.assertIn("PRUNE: startup would remove 1 from recipients_sendgrid_1.csv (guard active)", stdout.getvalue())
            self.assertIn("DRY RUN: no emails will be sent.", stdout.getvalue())

    def test_startup_without_guard_prunes_shard_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile = self._build_sendgrid_runtime_fixture(tmpdir)

            stdout = io.StringIO()
            with patch.object(settings, "APP_ROOT", base), patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(settings, "STATE_DIR", state), patch.object(
                send_shard, "SHARDS_DIR", shards
            ), patch.object(
                send_shard, "LOGS_DIR", logs
            ), patch.object(
                send_shard, "STATE_DIR", state
            ), patch.object(
                send_shard, "ROOT", base
            ), patch.object(
                send_shard, "DEFAULT_UNSUB_CSV", unsub
            ), patch.object(
                send_shard, "DEFAULT_SUPPRESS_CSV", suppress
            ), patch.object(
                send_shard, "DEFAULT_SENDGRID_SUPPRESSION_CSV", sg_suppress
            ), patch.object(
                send_shard, "SENDGRID_COUNTERS_PATH", counters
            ), patch.object(
                send_shard, "SENDGRID_SKIP_PRUNE_ON_STARTUP", False
            ), patch.dict(
                send_shard.PROFILES, {"sendgrid_annette": profile}, clear=False
            ), patch.object(
                sys, "argv", ["send_shard.py", "--profile", "sendgrid_annette", "--dry_run", "--max_total", "1"]
            ), redirect_stdout(stdout):
                send_shard.main()

            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                ["astraproductionsbyjc@gmail.com", "fresh@example.com"],
                [row["Email"] for row in rows],
            )
            self.assertIn("PRUNE: removed 1 from recipients_sendgrid_1.csv", stdout.getvalue())
            self.assertIn("DRY RUN: no emails will be sent.", stdout.getvalue())

    def test_repeat_worker_refreshes_after_suppression_only_initial_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile = self._build_sendgrid_runtime_fixture(tmpdir)
            profile.update(
                {
                    "repeat": True,
                    "batch_size": 1,
                    "interval": 0,
                    "cooldown_seconds": 0,
                    "max_messages_1h": 0,
                    "stop_at_local": "",
                }
            )
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "hold@example.com,Hold,Book A\n",
                encoding="utf-8",
            )
            log_path = logs / profile["log"]
            log_path.write_text("TimestampUTC,Email,Status,Info\n", encoding="utf-8")
            worker_log = send_shard.worker_log_path(log_path)

            refreshed_rows = [
                {"Email": "hold@example.com", "FirstName": "Hold", "BookTitle": "Book A"},
                {"Email": "fresh@example.com", "FirstName": "Fresh", "BookTitle": "Book B"},
            ]
            original_read_rows = send_shard.read_rows
            csv_reads = {"count": 0}

            def fake_read_rows(path: Path):
                if Path(path).resolve() == csv_path.resolve():
                    csv_reads["count"] += 1
                    if csv_reads["count"] == 1:
                        return original_read_rows(path)
                    with csv_path.open("w", newline="", encoding="utf-8") as handle:
                        writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName", "BookTitle"])
                        writer.writeheader()
                        writer.writerows(refreshed_rows)
                    return refreshed_rows
                return original_read_rows(path)

            stdout = io.StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.object(settings, "APP_ROOT", base))
                stack.enter_context(patch.object(settings, "SHARDS_DIR", shards))
                stack.enter_context(patch.object(settings, "LOGS_DIR", logs))
                stack.enter_context(patch.object(settings, "STATE_DIR", state))
                stack.enter_context(patch.object(send_shard, "SHARDS_DIR", shards))
                stack.enter_context(patch.object(send_shard, "LOGS_DIR", logs))
                stack.enter_context(patch.object(send_shard, "STATE_DIR", state))
                stack.enter_context(patch.object(send_shard, "ROOT", base))
                stack.enter_context(patch.object(send_shard, "DEFAULT_UNSUB_CSV", unsub))
                stack.enter_context(patch.object(send_shard, "DEFAULT_SUPPRESS_CSV", suppress))
                stack.enter_context(patch.object(send_shard, "DEFAULT_SENDGRID_SUPPRESSION_CSV", sg_suppress))
                stack.enter_context(patch.object(send_shard, "SENDGRID_COUNTERS_PATH", counters))
                stack.enter_context(patch.object(send_shard, "SENDGRID_SKIP_PRUNE_ON_STARTUP", True))
                stack.enter_context(patch.object(send_shard, "read_rows", side_effect=fake_read_rows))
                stack.enter_context(
                    patch.object(
                        send_shard,
                        "load_active_suppressed_emails",
                        return_value=(
                            {"hold@example.com"},
                            {"total_perm": 1, "total_temp_active": 0},
                        ),
                    )
                )
                stack.enter_context(patch.object(send_shard, "send_via_sendgrid", return_value={"message_id": "msg-1"}))
                stack.enter_context(patch.object(send_shard, "domain_wait_for_slot", return_value=""))
                stack.enter_context(patch.object(send_shard, "domain_finalize_attempt"))
                stack.enter_context(patch.object(send_shard, "remove_email_from_csv", return_value=True))
                stack.enter_context(patch.object(send_shard.time, "sleep", return_value=None))
                stack.enter_context(patch.object(send_shard, "sleep_with_jitter", return_value=None))
                stack.enter_context(patch.dict(send_shard.PROFILES, {"sendgrid_annette": profile}, clear=False))
                stack.enter_context(patch.dict(send_shard.os.environ, {"SENDGRID_API_KEY": "SG.test-key"}, clear=False))
                stack.enter_context(
                    patch.object(
                        sys,
                        "argv",
                        ["send_shard.py", "--profile", "sendgrid_annette", "--max_total", "1"],
                    )
                )
                stack.enter_context(redirect_stdout(stdout))
                send_shard.main()

            with log_path.open(newline="", encoding="utf-8-sig") as handle:
                log_rows = list(csv.DictReader(handle))
            self.assertEqual(
                ["SKIP", "SENT"],
                [row["Status"] for row in log_rows[-2:]],
            )
            self.assertEqual(
                ["hold@example.com", "fresh@example.com"],
                [row["Email"] for row in log_rows[-2:]],
            )
            events = [json.loads(line) for line in worker_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual("REFRESH", events[0]["event_type"])
            self.assertEqual("START", events[1]["event_type"])
            self.assertEqual("STOP", events[-1]["event_type"])
            self.assertEqual("queue_refreshed_after_empty_start", events[0]["reason"])
            self.assertEqual("worker_start", events[1]["reason"])
            self.assertEqual("max_total", events[-1]["reason"])
            self.assertIn("SENT fresh@example.com", stdout.getvalue())

    def test_worker_logs_top_level_exception_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile = self._build_sendgrid_runtime_fixture(tmpdir)
            profile.update(
                {
                    "repeat": True,
                    "batch_size": 1,
                    "interval": 0,
                    "cooldown_seconds": 0,
                    "max_messages_1h": 0,
                    "stop_at_local": "",
                }
            )
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "fresh@example.com,Fresh,Book C\n",
                encoding="utf-8",
            )
            log_path = logs / profile["log"]
            worker_log = send_shard.worker_log_path(log_path)

            with ExitStack() as stack:
                stack.enter_context(patch.object(settings, "APP_ROOT", base))
                stack.enter_context(patch.object(settings, "SHARDS_DIR", shards))
                stack.enter_context(patch.object(settings, "LOGS_DIR", logs))
                stack.enter_context(patch.object(settings, "STATE_DIR", state))
                stack.enter_context(patch.object(send_shard, "SHARDS_DIR", shards))
                stack.enter_context(patch.object(send_shard, "LOGS_DIR", logs))
                stack.enter_context(patch.object(send_shard, "STATE_DIR", state))
                stack.enter_context(patch.object(send_shard, "ROOT", base))
                stack.enter_context(patch.object(send_shard, "DEFAULT_UNSUB_CSV", unsub))
                stack.enter_context(patch.object(send_shard, "DEFAULT_SUPPRESS_CSV", suppress))
                stack.enter_context(patch.object(send_shard, "DEFAULT_SENDGRID_SUPPRESSION_CSV", sg_suppress))
                stack.enter_context(patch.object(send_shard, "SENDGRID_COUNTERS_PATH", counters))
                stack.enter_context(patch.object(send_shard, "SENDGRID_SKIP_PRUNE_ON_STARTUP", True))
                stack.enter_context(
                    patch.object(
                        send_shard,
                        "load_active_suppressed_emails",
                        return_value=(set(), {"total_perm": 0, "total_temp_active": 0}),
                    )
                )
                stack.enter_context(patch.object(send_shard, "build_message", side_effect=RuntimeError("boom from build_message")))
                stack.enter_context(patch.dict(send_shard.PROFILES, {"sendgrid_annette": profile}, clear=False))
                stack.enter_context(patch.dict(send_shard.os.environ, {"SENDGRID_API_KEY": "SG.test-key"}, clear=False))
                stack.enter_context(patch.object(sys, "argv", ["send_shard.py", "--profile", "sendgrid_annette"]))
                with self.assertRaises(RuntimeError):
                    send_shard.main()

            events = [json.loads(line) for line in worker_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual("START", events[0]["event_type"])
            self.assertEqual("ERROR", events[-1]["event_type"])
            self.assertEqual("RuntimeError", events[-1]["reason"])
            self.assertIn("boom from build_message", events[-1]["traceback"])

    def test_prune_sent_from_csv_mutates_during_normal_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "already-sent@example.com,Sent,Book A\n"
                "fresh@example.com,Fresh,Book B\n",
                encoding="utf-8",
            )

            would_remove = count_prunable_rows(csv_path, {"already-sent@example.com"})
            removed = prune_sent_from_csv(csv_path, {"already-sent@example.com"})

            self.assertEqual(1, would_remove)
            self.assertEqual(1, removed)
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(["fresh@example.com"], [row["Email"] for row in rows])

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
                self.assertEqual(
                    "Email,FirstName,AuthorEmail,AuthorName,BookTitle,source_file,source_sheet,source_row\n",
                    resolved.read_text(encoding="utf-8"),
                )

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

    def test_missing_book_title_uses_subject_fallback_and_generic_body_opening(self) -> None:
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email="reader@example.com",
            author="Anna Example",
            book_title="",
            subject="Consignment review for {BookTitle}",
            body_template=send_shard.PITCH_1_5_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
            subject_fallback="Independent author consignment review",
        )

        self.assertEqual("Independent author consignment review", subject_text)
        self.assertIn("Our team came across your author profile", body_text)
        self.assertNotIn("My team came across", body_text)
        self.assertNotIn("I came across", body_text)
        self.assertNotIn("{BookTitle}", body_text)

        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email="reader@example.com",
            author="Anna Example",
            book_title="",
            subject="Consignment review for {BookTitle}",
            body_template=send_shard.PITCH_1_5_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
            merge_fields={"FirstName": "Anna", "BookTitle": ""},
            subject_fallback="Independent author consignment review",
        )

        self.assertEqual("Independent author consignment review", subject_text)
        self.assertIn("Our team came across your author profile", body_text)
        self.assertNotIn("I came across", body_text)
        self.assertNotIn("{BookTitle}", body_text)

    def test_present_book_title_renders_personalized_subject_and_body(self) -> None:
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email="reader@example.com",
            author="Anna Example",
            book_title="The Quiet Harbor",
            subject="Consignment review for {BookTitle}",
            body_template=send_shard.PITCH_1_5_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
            subject_fallback="Independent author consignment review",
        )

        self.assertEqual("Consignment review for The Quiet Harbor", subject_text)
        self.assertIn("Our team came across The Quiet Harbor", body_text)
        self.assertNotIn("I came across The Quiet Harbor", body_text)
        self.assertNotIn("My team came across The Quiet Harbor", body_text)
        self.assertNotIn("I came across your author profile", body_text)
        self.assertNotIn("{BookTitle}", body_text)

    def test_raw_title_alias_resolves_to_canonical_book_title_before_render(self) -> None:
        row = {
            "Email": "reader@example.test",
            "FirstName": "Tina",
            "AuthorName": "Tina Writer",
            "Title": "The Alias Harbor",
        }
        merge_fields = send_shard.row_merge_fields(row, row["Email"], "Tina", "")
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email=row["Email"],
            author="Tina",
            book_title="",
            subject="Consignment review for {BookTitle}",
            body_template=send_shard.PITCH_1_5_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
            merge_fields=merge_fields,
            subject_fallback="Independent author consignment review",
        )

        self.assertEqual("The Alias Harbor", merge_fields["BookTitle"])
        self.assertEqual("Consignment review for The Alias Harbor", subject_text)
        self.assertIn("Our team came across The Alias Harbor", body_text)
        self.assertNotIn("{Title}", body_text)

    def test_unsafe_title_alias_is_blanked_and_uses_author_profile_fallback(self) -> None:
        row = {
            "Email": "reader@example.test",
            "FirstName": "Tina",
            "last_name": "Writer",
            "AuthorName": "Tina Writer",
            "Title": "Completed",
            "Publication Title": "Tina Writer",
            "Product Title": "https://example.test/book",
        }
        merge_fields = send_shard.row_merge_fields(row, row["Email"], "Tina", "")
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email=row["Email"],
            author="Tina",
            book_title="",
            subject="Consignment review for {BookTitle}",
            body_template=send_shard.PITCH_1_5_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
            merge_fields=merge_fields,
            subject_fallback="Independent author consignment review",
        )

        self.assertEqual("", merge_fields["BookTitle"])
        self.assertEqual("Independent author consignment review", subject_text)
        self.assertIn("Our team came across your author profile", body_text)
        self.assertNotIn("Completed", body_text)
        self.assertNotIn("Tina Writer", subject_text)

    def test_title_matching_first_and_last_name_is_unsafe_without_author_name(self) -> None:
        row = {
            "Email": "reader@example.test",
            "first_name": "Tina",
            "last_name": "Writer",
            "Title": "Tina Writer",
        }
        merge_fields = send_shard.row_merge_fields(row, row["Email"], "Tina", "")
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="annette@barnesnoblemarketing.com",
            to_email=row["Email"],
            author="Tina",
            book_title="",
            subject="Consignment review for {BookTitle}",
            body_template=send_shard.PITCH_1_5_BODY,
            unsub_email="annette@barnesnoblemarketing.com",
            merge_fields=merge_fields,
            subject_fallback="Independent author consignment review",
        )

        self.assertEqual("", merge_fields["BookTitle"])
        self.assertEqual("Independent author consignment review", subject_text)
        self.assertIn("Our team came across your author profile", body_text)
        self.assertNotIn("I came across Tina Writer", body_text)

    def test_title_template_placeholder_is_blocked(self) -> None:
        with self.assertRaises(ValueError):
            render_message_parts(
                "Tina",
                "The Alias Harbor",
                "Consignment review for {Title}",
                "Hi {FirstName},\n\nI came across {Title}.",
                "unsubscribe@example.test",
                signature_file=None,
                merge_fields={"FirstName": "Tina", "BookTitle": "The Alias Harbor"},
            )

    def test_title_only_queue_passes_fallback_capable_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            csv_path.write_text(
                "Email,FirstName,AuthorName,Title\n"
                "reader@example.test,Tina,Tina Writer,The Alias Harbor\n",
                encoding="utf-8",
            )
            rows = send_shard.read_rows(csv_path)

            self.assertTrue(
                send_shard.validate_book_title_queue_contract(
                    csv_path=csv_path,
                    rows=rows,
                    subject="Consignment review for {BookTitle}",
                    body_template=send_shard.PITCH_1_5_BODY,
                    profile_name="sendgrid_annette",
                    subject_fallback="Independent author consignment review",
                )
            )

    def test_placeholder_like_book_title_values_are_normalized_before_render(self) -> None:
        cases = [
            ("Život p{r}outníka", "Život proutníka", "{r}"),
            ("[(Horse Medicine)]", "((Horse Medicine))", "[(Horse Medicine)]"),
            (
                "Evolutions in Bread: Artisan Pan Breads and Dutch-Oven Loaves at Home [A baking book by the author of Flour Water Salt Yeast] Kindle Edition",
                "Evolutions in Bread: Artisan Pan Breads and Dutch-Oven Loaves at Home (A baking book by the author of Flour Water Salt Yeast) Kindle Edition",
                "[A baking book by the author of Flour Water Salt Yeast]",
            ),
        ]
        for raw_title, expected_title, forbidden_token in cases:
            with self.subTest(raw_title=raw_title):
                _msg, subject_text, body_text, _html_body, _cid = build_message(
                    from_email="annette@barnesnoblemarketing.com",
                    to_email="reader@example.com",
                    author="Anna Example",
                    book_title=raw_title,
                    subject="Consignment review for {BookTitle}",
                    body_template=send_shard.PITCH_1_5_BODY,
                    unsub_email="annette@barnesnoblemarketing.com",
                    subject_fallback="Independent author consignment review",
                )

                self.assertIn(expected_title, subject_text)
                self.assertIn(expected_title, body_text)
                self.assertNotIn(forbidden_token, subject_text)
                self.assertNotIn(forbidden_token, body_text)
                self.assertNotIn("{BookTitle}", body_text)

        _subject_text, body_text, _html_body, _cid = render_message_parts(
            "Anna",
            "Safe Book",
            "Subject",
            "Hi {FirstName},\n\n{PersonalizedOpeningLine}",
            "unsubscribe@example.com",
            signature_file=None,
            merge_fields={
                "FirstName": "Anna",
                "BookTitle": "Safe Book",
                "PersonalizedOpeningLine": "Opening for [(Horse Medicine)]",
            },
        )
        self.assertIn("Opening for ((Horse Medicine))", body_text)
        self.assertNotIn("[(Horse Medicine)]", body_text)

    def test_preflight_reports_dictreader_data_row_and_bad_field_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "first@example.test,First,Safe Book\n"
                "second@example.test,Second,Život p{r}outníka\n",
                encoding="utf-8",
            )
            rows = send_shard.read_rows(csv_path)
            stdout = io.StringIO()

            with patch.object(send_shard, "normalize_render_field_value", side_effect=lambda value: (str(value or "").strip(), [])), redirect_stdout(stdout):
                ok = send_shard.validate_book_title_queue_contract(
                    csv_path=csv_path,
                    rows=rows,
                    subject="Consignment review for {BookTitle}",
                    body_template=send_shard.PITCH_1_5_BODY,
                    profile_name="sendgrid_annette",
                    subject_fallback="Independent author consignment review",
                )

        self.assertFalse(ok)
        output = stdout.getvalue()
        self.assertIn("row=2", output)
        self.assertIn("field=BookTitle", output)
        self.assertIn("token={r}", output)
        self.assertNotIn("row=3", output)

    def test_fallback_capable_book_title_pitch_allows_mixed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "titled@example.com,Tina,The Quiet Harbor\n"
                "untitled@example.com,Uma,\n",
                encoding="utf-8",
            )
            rows = send_shard.read_rows(csv_path)

            self.assertTrue(
                send_shard.validate_book_title_queue_contract(
                    csv_path=csv_path,
                    rows=rows,
                    subject="Consignment review for {BookTitle}",
                    body_template=send_shard.PITCH_1_5_BODY,
                    profile_name="sendgrid_annette",
                    subject_fallback="Independent author consignment review",
                )
            )

            titled = rows[0]
            titled_subject, titled_body, _html_body, _cid = render_message_parts(
                "Tina",
                titled["BookTitle"],
                "Consignment review for {BookTitle}",
                send_shard.PITCH_1_5_BODY,
                "annette@barnesnoblemarketing.com",
                signature_file=None,
                merge_fields=send_shard.row_merge_fields(titled, titled["Email"], "Tina", titled["BookTitle"]),
                subject_fallback="Independent author consignment review",
            )
            self.assertEqual("Consignment review for The Quiet Harbor", titled_subject)
            self.assertIn("Our team came across The Quiet Harbor", titled_body)
            self.assertNotIn("I came across The Quiet Harbor", titled_body)
            self.assertNotIn("My team came across The Quiet Harbor", titled_body)
            self.assertNotIn("{BookTitle}", titled_body)

            untitled = rows[1]
            fallback_subject, fallback_body, _html_body, _cid = render_message_parts(
                "Uma",
                untitled["BookTitle"],
                "Consignment review for {BookTitle}",
                send_shard.PITCH_1_5_BODY,
                "annette@barnesnoblemarketing.com",
                signature_file=None,
                merge_fields=send_shard.row_merge_fields(untitled, untitled["Email"], "Uma", untitled["BookTitle"]),
                subject_fallback="Independent author consignment review",
            )
            self.assertEqual("Independent author consignment review", fallback_subject)
            self.assertIn("Our team came across your author profile", fallback_body)
            self.assertNotIn("My team came across", fallback_body)
            self.assertNotIn("I came across", fallback_body)
            self.assertNotIn("{BookTitle}", fallback_body)

    def test_fallback_capable_book_title_pitch_passes_preflight_with_mixed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base, shards, logs, state, csv_path, unsub, suppress, sg_suppress, counters, profile = self._build_sendgrid_runtime_fixture(tmpdir)
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "titled@example.com,Tina,The Quiet Harbor\n"
                "untitled@example.com,Uma,\n",
                encoding="utf-8",
            )
            profile["interval"] = 35
            profile["cooldown_seconds"] = 35
            profile["repeat"] = True
            original_csv = csv_path.read_text(encoding="utf-8")

            stdout = io.StringIO()
            with patch.object(settings, "APP_ROOT", base), patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(settings, "STATE_DIR", state), patch.object(
                send_shard, "SHARDS_DIR", shards
            ), patch.object(
                send_shard, "LOGS_DIR", logs
            ), patch.object(
                send_shard, "STATE_DIR", state
            ), patch.object(
                send_shard, "ROOT", base
            ), patch.object(
                send_shard, "DEFAULT_UNSUB_CSV", unsub
            ), patch.object(
                send_shard, "DEFAULT_SUPPRESS_CSV", suppress
            ), patch.object(
                send_shard, "DEFAULT_SENDGRID_SUPPRESSION_CSV", sg_suppress
            ), patch.object(
                send_shard, "SENDGRID_COUNTERS_PATH", counters
            ), patch.dict(
                send_shard.PROFILES, {"sendgrid_annette": profile}, clear=False
            ), patch.dict(
                send_shard.os.environ, {"SENDGRID_API_KEY": "SG.test-key"}, clear=False
            ), patch.object(
                sys, "argv", ["send_shard.py", "--profile", "sendgrid_annette", "--preflight"]
            ), redirect_stdout(stdout):
                send_shard.main()

            self.assertEqual(original_csv, csv_path.read_text(encoding="utf-8"))
            self.assertIn("PREFLIGHT: ok (no sending).", stdout.getvalue())

    def test_pitch_jc_missing_book_title_uses_fallback_subject_and_body(self) -> None:
        pitch = send_shard.PITCHES["pitch_jc"]
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="jc@astraproductions.co",
            to_email="reader@example.com",
            author="Jamie Example",
            book_title="",
            subject=pitch["subject"],
            body_template=pitch["body"],
            unsub_email="jc@astraproductions.co",
            subject_fallback=pitch["subject_fallback"],
            body_fallback=pitch["body_fallback"],
        )

        self.assertEqual("Website direction for your author brand", subject_text)
        self.assertIn("I came across your author profile", body_text)
        self.assertNotIn("My team came across", body_text)
        self.assertNotIn("Our team came across", body_text)
        self.assertNotIn("{BookTitle}", body_text)

    def test_pitch_jc_present_book_title_renders_personalized_subject_and_body(self) -> None:
        pitch = send_shard.PITCHES["pitch_jc"]
        _msg, subject_text, body_text, _html_body, _cid = build_message(
            from_email="jc@astraproductions.co",
            to_email="reader@example.com",
            author="Jamie Example",
            book_title="The Quiet Harbor",
            subject=pitch["subject"],
            body_template=pitch["body"],
            unsub_email="jc@astraproductions.co",
            subject_fallback=pitch["subject_fallback"],
        )

        self.assertEqual("Website direction for The Quiet Harbor", subject_text)
        self.assertIn("I came across The Quiet Harbor", body_text)
        self.assertNotIn("My team came across The Quiet Harbor", body_text)
        self.assertNotIn("Our team came across The Quiet Harbor", body_text)
        self.assertNotIn("I came across your author profile", body_text)
        self.assertNotIn("{BookTitle}", body_text)

    def test_pitch_jc_fallback_capable_queue_contract_allows_missing_book_title_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_private_jc.csv"
            csv_path.write_text("Email,FirstName\nreader@example.com,Jamie\n", encoding="utf-8")
            rows = send_shard.read_rows(csv_path)
            pitch = send_shard.PITCHES["pitch_jc"]

            self.assertTrue(
                send_shard.validate_book_title_queue_contract(
                    csv_path=csv_path,
                    rows=rows,
                    subject=pitch["subject"],
                    body_template=pitch["body"],
                    profile_name="private_jc",
                    subject_fallback=pitch["subject_fallback"],
                    body_fallback=pitch["body_fallback"],
                )
            )

    def test_strict_book_title_template_queue_contract_blocks_missing_book_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            csv_path.write_text(
                "Email,FirstName,BookTitle\n"
                "titled@example.com,Tina,The Quiet Harbor\n"
                "untitled@example.com,Uma,\n",
                encoding="utf-8",
            )
            rows = send_shard.read_rows(csv_path)

            self.assertFalse(
                send_shard.validate_book_title_queue_contract(
                    csv_path=csv_path,
                    rows=rows,
                    subject="Consignment review for {BookTitle}",
                    body_template=send_shard.PITCH_1_5_BODY,
                    profile_name="sendgrid_annette",
                    subject_fallback="Independent author consignment review",
                    strict_book_title_required=True,
                )
            )

    def test_strict_book_title_template_queue_contract_blocks_missing_book_title_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recipients_sendgrid_1.csv"
            csv_path.write_text("Email,FirstName\nreader@example.com,Anna\n", encoding="utf-8")
            rows = send_shard.read_rows(csv_path)

            self.assertFalse(
                send_shard.validate_book_title_queue_contract(
                    csv_path=csv_path,
                    rows=rows,
                    subject="Consignment review for {BookTitle}",
                    body_template=send_shard.PITCH_1_5_BODY,
                    profile_name="sendgrid_annette",
                    strict_book_title_required=True,
                )
            )

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

    def test_warm_private_jc_profile_uses_separate_queue_lock_and_pitch(self) -> None:
        cold = send_shard.PROFILES["private_jc"]
        warm = send_shard.PROFILES["private_jc_warm"]

        self.assertEqual("recipients_private_jc_warm.csv", warm["csv"])
        self.assertNotEqual(cold["csv"], warm["csv"])
        self.assertEqual("private_jc_warm_log.csv", warm["log"])
        self.assertNotEqual(cold["log"], warm["log"])
        self.assertEqual("private_jc_warm", warm["tmux_session"])
        self.assertNotEqual(cold["tmux_session"], warm["tmux_session"])
        self.assertNotEqual(cold["pitch"], warm["pitch"])
        self.assertEqual("pitch_jc", cold["pitch"])
        self.assertEqual("pitch_warm", warm["pitch"])
        self.assertTrue(all(cfg.get("pitch") != "pitch_warm" for name, cfg in send_shard.PROFILES.items() if name.startswith("sendgrid_")))
        self.assertNotEqual(
            send_shard.profile_runtime_lock_path("private_jc"),
            send_shard.profile_runtime_lock_path("private_jc_warm"),
        )
        self.assertTrue(warm["pre_rendered_message"])
        self.assertTrue(warm["allow_confirmed_warm_role_recipients"])
        self.assertNotIn("allow_confirmed_warm_role_recipients", cold)
        self.assertFalse(any(name.startswith("sendgrid_warm") for name in send_shard.PROFILES))

    def test_warm_sender_preflight_refuses_confirmation_payload_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            shards = root / "shards"
            logs = root / "logs"
            state = root / "state"
            shards.mkdir()
            logs.mkdir()
            state.mkdir()
            queue_path = shards / "recipients_private_jc_warm.csv"
            queue_path.write_text("Email,EmailSubject,EmailBody\nsynthetic@example.com,Changed,Changed\n", encoding="utf-8")
            stdout = io.StringIO()
            integrity = {
                "valid": False,
                "reason": "warm_queue_payload_mismatch",
                "message": "Warm queue payload no longer matches confirmed field EmailSubject.",
                "field": "EmailSubject",
            }

            with patch.object(send_shard, "SHARDS_DIR", shards), patch.object(
                send_shard, "LOGS_DIR", logs
            ), patch.object(send_shard, "STATE_DIR", state), patch.object(
                send_shard, "validate_warm_queue_contract", return_value=True
            ), patch.object(send_shard, "load_warm_confirmation_manifest", return_value={"confirmed": True}), patch.object(
                send_shard, "validate_warm_confirmed_queue", return_value=integrity
            ), patch.object(send_shard, "smtp_login") as smtp_login, patch.object(
                sys, "argv", ["send_shard.py", "--profile", "private_jc_warm", "--preflight"]
            ), redirect_stdout(stdout):
                send_shard.main()

        smtp_login.assert_not_called()
        self.assertIn("warm_queue_payload_mismatch", stdout.getvalue())

    def test_confirmed_warm_queue_allows_public_role_contact_paths_only_for_warm_profile(self) -> None:
        warm_queue = Path("recipients_private_jc_warm.csv")
        role_set = {"contact", "hello", "support"}

        for email in ["contact@example.com", "hello@example.com", "support@example.com"]:
            self.assertFalse(
                send_shard.should_block_role_recipient_for_runtime(
                    email,
                    role_set,
                    profile_name="private_jc_warm",
                    queue_path=warm_queue,
                    block_role_recipients=True,
                    allow_confirmed_warm_role_recipients=True,
                )
            )
            self.assertTrue(
                send_shard.should_block_role_recipient_for_runtime(
                    email,
                    role_set,
                    profile_name="private_jc",
                    queue_path=Path("recipients_private_jc.csv"),
                    block_role_recipients=True,
                    allow_confirmed_warm_role_recipients=False,
                )
            )
            self.assertTrue(
                send_shard.should_block_role_recipient_for_runtime(
                    email,
                    role_set,
                    profile_name="sendgrid_annette",
                    queue_path=Path("recipients_sendgrid_1.csv"),
                    block_role_recipients=True,
                    allow_confirmed_warm_role_recipients=False,
                )
            )

        self.assertTrue(
            send_shard.should_block_role_recipient_for_runtime(
                "contact@example.com",
                role_set,
                profile_name="private_jc_warm",
                queue_path=Path("some_other_queue.csv"),
                block_role_recipients=True,
                allow_confirmed_warm_role_recipients=True,
            )
        )

    def test_warm_role_bypass_does_not_override_sent_log_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            warm_log = Path(tmpdir) / "private_jc_warm_log.csv"
            warm_log.write_text(
                "TimestampUTC,Email,Status,Info\n"
                "2026-06-28T12:00:00+00:00,support@example.com,SENT,warm\n",
                encoding="utf-8",
            )

            already_done = send_shard.load_already_done(warm_log)
            role_blocked = send_shard.should_block_role_recipient_for_runtime(
                "support@example.com",
                {"support"},
                profile_name="private_jc_warm",
                queue_path=Path("recipients_private_jc_warm.csv"),
                block_role_recipients=True,
                allow_confirmed_warm_role_recipients=True,
            )

        self.assertFalse(role_blocked)
        self.assertIn("support@example.com", already_done)

    def test_start_all_still_excludes_warm_private_jc(self) -> None:
        self.assertNotIn("private_jc_warm", dashboard_core.START_ALL_PROFILES)

    def test_live_warm_status_uses_real_queue_log_and_worker_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            shards = root / "shards"
            logs = root / "logs"
            shards.mkdir()
            logs.mkdir()
            queue_path = shards / "recipients_private_jc_warm.csv"
            log_path = logs / "private_jc_warm_log.csv"
            worker_path = logs / "private_jc_warm_log_worker.jsonl"
            queue_path.write_text("Email,EmailSubject,EmailBody\n", encoding="utf-8")
            log_path.write_text(
                "TimestampUTC,Email,Status,Info\n"
                "2026-06-28T10:00:00+00:00,one@example.com,SENT,warm\n"
                "2026-06-28T10:01:00+00:00,two@example.com,SENT,warm\n",
                encoding="utf-8",
            )
            worker_path.write_text(
                json.dumps({"timestamp": "2026-06-28T10:01:01+00:00", "event_type": "DONE", "reason": "queue_complete"}) + "\n",
                encoding="utf-8",
            )
            lane = {"confirmed": True, "confirmed_rows": 2, "ready": False, "remaining": 99}

            with patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(
                live_dashboard, "warm_private_jc_lane_status", return_value=lane
            ), patch.object(
                live_dashboard, "_active_dashboard_profiles", return_value=set()
            ):
                status = live_dashboard.build_warm_private_jc_live_status()

            self.assertEqual(2, status["sent_count"])
            self.assertEqual(0, status["queued_remaining_count"])
            self.assertEqual("Complete", status["state"])
            self.assertEqual("two@example.com", status["last_sent_email"])
            self.assertEqual("2026-06-28T10:01:00+00:00", status["last_sent_timestamp"])
            self.assertEqual("", status["next_queued_email"])
            self.assertEqual("DONE", status["last_worker_event"])
            self.assertEqual("queue_complete", status["last_worker_reason"])
            self.assertTrue(any(event["type"] == "SENT" for event in status["timeline"]))

    def test_live_warm_status_detects_partial_running_and_blocked_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            shards = root / "shards"
            logs = root / "logs"
            shards.mkdir()
            logs.mkdir()
            queue_path = shards / "recipients_private_jc_warm.csv"
            log_path = logs / "private_jc_warm_log.csv"
            worker_path = logs / "private_jc_warm_log_worker.jsonl"
            queue_path.write_text(
                "Email,EmailSubject,EmailBody\n"
                "contact@example.com,Subject,Body\n"
                "hello@example.com,Subject,Body\n",
                encoding="utf-8",
            )
            log_path.write_text(
                "Timestamp,Email,Status,Info\n"
                "2026-06-28T10:00:00+00:00,sent@example.com,SENT,warm\n",
                encoding="utf-8",
            )
            lane = {"confirmed": True, "confirmed_rows": 3, "ready": True, "remaining": 77}

            with patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(
                live_dashboard, "warm_private_jc_lane_status", return_value=lane
            ), patch.object(
                live_dashboard, "_active_dashboard_profiles", return_value=set()
            ):
                partial = live_dashboard.build_warm_private_jc_live_status()

            self.assertEqual("Partial", partial["state"])
            self.assertEqual(2, partial["queued_remaining_count"])
            self.assertEqual(1, partial["sent_count"])
            self.assertEqual("contact@example.com", partial["next_queued_email"])

            with patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(
                live_dashboard, "warm_private_jc_lane_status", return_value=lane
            ), patch.object(
                live_dashboard, "_active_dashboard_profiles", return_value={"private_jc_warm"}
            ):
                running = live_dashboard.build_warm_private_jc_live_status()

            self.assertEqual("Running", running["state"])
            self.assertTrue(running["running"])

            worker_path.write_text(
                json.dumps({
                    "timestamp": "2026-06-28T10:02:00+00:00",
                    "event_type": "DONE",
                    "reason": "queue_exhausted_no_eligible_rows",
                }) + "\n",
                encoding="utf-8",
            )
            with patch.object(settings, "SHARDS_DIR", shards), patch.object(
                settings, "LOGS_DIR", logs
            ), patch.object(
                live_dashboard, "warm_private_jc_lane_status", return_value=lane
            ), patch.object(
                live_dashboard, "_active_dashboard_profiles", return_value=set()
            ):
                blocked = live_dashboard.build_warm_private_jc_live_status()

            self.assertEqual("Blocked", blocked["state"])
            self.assertTrue(blocked["blocked"])
            self.assertEqual("queue_exhausted_no_eligible_rows", blocked["last_worker_reason"])

    def test_live_snapshot_overrides_stale_warm_profile_counts_only(self) -> None:
        warm_status = {
            "queued_remaining_count": 0,
            "sent_count": 8,
            "last_sent_email": "last@example.com",
            "last_sent_timestamp": "2026-06-28T10:08:00+00:00",
            "running": False,
        }
        base_snapshot = {
            "profiles": [
                {
                    "name": "private_jc_warm",
                    "pending_count": 5,
                    "run_sent_display": 3,
                    "runtime_state": "running",
                },
                {
                    "name": "private_jc",
                    "pending_count": 12,
                    "run_sent_display": 4,
                    "runtime_state": "stopped",
                },
            ]
        }

        with patch.object(live_dashboard, "build_dashboard_snapshot", return_value=base_snapshot), patch.object(
            live_dashboard, "_build_automation_status", return_value={}
        ), patch.object(
            live_dashboard, "build_warm_private_jc_live_status", return_value=warm_status
        ):
            snapshot = live_dashboard._build_live_snapshot()

        warm_profile, cold_profile = snapshot["profiles"]
        self.assertIs(snapshot["warm_private_jc_status"], warm_status)
        self.assertEqual(0, warm_profile["pending_count"])
        self.assertEqual(8, warm_profile["run_sent_display"])
        self.assertEqual("stopped", warm_profile["runtime_state"])
        self.assertEqual(12, cold_profile["pending_count"])
        self.assertEqual(4, cold_profile["run_sent_display"])

    def test_warm_message_uses_previewed_subject_and_body_verbatim(self) -> None:
        row = {
            "EmailSubject": "Previewed warm subject",
            "EmailBody": "Hi Jamie,\n\nPreviewed warm body.\n\nP.S. reply unsub.",
        }

        message, subject, body, _html, _cid = send_shard.build_pre_rendered_message(
            "jc@astraproductions.co",
            "synthetic@example.com",
            row,
            "jc@astraproductions.co",
        )

        self.assertEqual(row["EmailSubject"], subject)
        self.assertEqual(row["EmailBody"], body)
        self.assertEqual(row["EmailSubject"], message["Subject"])
        self.assertNotIn(send_shard.PITCH_JC_BODY, body)

    def test_warm_reservation_blocks_cross_lane_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "idempotency.sqlite3"
            cold_reserved, _ = send_shard.reserve_send_idempotency(
                campaign_id="cold-campaign",
                provider="private",
                email="synthetic@example.com",
                profile="private_jc",
                queue_file="recipients_private_jc.csv",
                db_path=db_path,
            )
            warm_reserved, reason = send_shard.reserve_send_idempotency(
                campaign_id="warm-campaign",
                provider="private",
                email="synthetic@example.com",
                profile="private_jc_warm",
                queue_file="recipients_private_jc_warm.csv",
                db_path=db_path,
            )

        self.assertTrue(cold_reserved)
        self.assertFalse(warm_reserved)
        self.assertEqual("cross_lane_reservation", reason)


if __name__ == "__main__":
    unittest.main()
