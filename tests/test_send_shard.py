from __future__ import annotations

import csv
import io
import json
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
)


class SendShardTests(unittest.TestCase):
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
        self.assertEqual(120, profile["interval"])
        self.assertEqual(120, profile["cooldown_seconds"])
        self.assertEqual("12:00", profile["stop_at_local"])

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
                    return original_read_rows(path) if csv_reads["count"] == 1 else refreshed_rows
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
                stack.enter_context(patch.object(sys, "argv", ["send_shard.py", "--profile", "sendgrid_annette"]))
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
            self.assertEqual("DONE", events[-1]["event_type"])
            self.assertEqual("queue_refreshed_after_empty_start", events[0]["reason"])
            self.assertEqual("worker_start", events[1]["reason"])
            self.assertEqual("queue_exhausted", events[-1]["reason"])
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
        self.assertIn(
            "Our team works with independent authors to improve how their work is presented online, especially through clearer websites, stronger book visuals, and more polished launch materials.",
            body_text,
        )
        self.assertNotIn("Our team came across", body_text)
        self.assertNotIn("your book", body_text)
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
        self.assertIn("Our team works with independent authors", body_text)
        self.assertNotIn("your book", body_text)
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
        self.assertNotIn("Our team works with independent authors", body_text)
        self.assertNotIn("your book", body_text)
        self.assertNotIn("{BookTitle}", body_text)

    def test_book_title_template_queue_contract_blocks_missing_book_title_column(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
