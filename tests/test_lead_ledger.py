from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

import lead_ledger


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class LeadLedgerTests(unittest.TestCase):
    def _seed_dispatched_lead(
        self,
        conn: sqlite3.Connection,
        *,
        email: str = "dispatch@example.com",
        run_id: str = "dispatch_run_1",
        queue_target: str = "sendgrid_1",
        dispatched_at: str = "2026-04-11T03:00:00+00:00",
    ) -> tuple[dict[str, object], dict[str, object]]:
        lead = lead_ledger.upsert_lead(
            conn,
            email=email,
            current_stage=lead_ledger.FAST_TRIAGE_STAGE,
            current_status="KEEP",
        )
        dispatch = lead_ledger.record_dispatch_event(
            conn,
            lead_id=lead["lead_id"],
            run_id=run_id,
            dispatch_source="triaged_keep",
            profile=queue_target,
            queue_target=queue_target,
            result_status="queued",
            dispatched_at=dispatched_at,
        )
        return lead, dispatch

    def _seed_quarantined_lead(
        self,
        conn: sqlite3.Connection,
        *,
        email: str,
        stage: str = lead_ledger.FAST_TRIAGE_STAGE,
        score: float = 0,
        reason_codes: list[str] | None = None,
    ) -> dict[str, object]:
        return lead_ledger.upsert_lead(
            conn,
            email=email,
            full_name=email.split("@", 1)[0].replace(".", " ").title(),
            first_name=email.split("@", 1)[0].split(".", 1)[0].title(),
            current_stage=stage,
            current_status=lead_ledger.QUARANTINE_STATUS,
            score=score,
            reason_codes=reason_codes or [],
            source_file="_important/leads_quarantine.csv",
            source_row_hash=f"row-{email}",
        )

    def test_deterministic_lead_id_uses_normalized_email(self) -> None:
        self.assertEqual(
            lead_ledger.deterministic_lead_id(" Alice@Example.COM "),
            lead_ledger.deterministic_lead_id("alice@example.com"),
        )

    def test_schema_init_creates_tables_indexes_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lead_ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                self.assertTrue(db_path.exists())
                self.assertEqual(
                    lead_ledger.LEAD_LEDGER_SCHEMA_VERSION,
                    conn.execute("PRAGMA user_version").fetchone()[0],
                )
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                self.assertIn("lead_ledger", tables)
                self.assertIn("lead_ledger_events", tables)
                self.assertIn("lead_ledger_import_rows", tables)
                self.assertIn("lead_dispatch_history", tables)
                indexes = {
                    row[1]
                    for row in conn.execute("PRAGMA index_list('lead_ledger')").fetchall()
                }
                self.assertIn("idx_lead_ledger_lead_id", indexes)
                self.assertIn("idx_lead_ledger_email", indexes)
                self.assertIn("idx_lead_ledger_stage_status", indexes)
                self.assertIn("idx_lead_ledger_source_row_hash", indexes)
                dispatch_indexes = {
                    row[1]
                    for row in conn.execute("PRAGMA index_list('lead_dispatch_history')").fetchall()
                }
                self.assertIn("idx_lead_dispatch_history_lead_id", dispatch_indexes)
                self.assertIn("idx_lead_dispatch_history_run_id", dispatch_indexes)
                self.assertIn("idx_lead_dispatch_history_provider_message_id", dispatch_indexes)
            finally:
                conn.close()

    def test_upsert_lead_merges_existing_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                created = lead_ledger.upsert_lead(
                    conn,
                    email="alice@example.com",
                    full_name="Alice Example",
                    first_name="Alice",
                    source_file="_important/leads_triaged_keep.csv",
                    source_row_hash="rowhash-1",
                    first_seen_at="2026-04-01T00:00:00+00:00",
                    last_seen_at="2026-04-01T00:00:00+00:00",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status="KEEP",
                    score=7.5,
                    reason_codes=["FAST_TRIAGE_LOCAL_CONFIDENCE"],
                )
                updated = lead_ledger.upsert_lead(
                    conn,
                    email="alice@example.com",
                    full_name="",
                    first_name="Ali",
                    source_file="_important/leads_verified.csv",
                    source_row_hash="rowhash-2",
                    first_seen_at="2026-04-03T00:00:00+00:00",
                    last_seen_at="2026-04-03T00:00:00+00:00",
                    current_stage=lead_ledger.STRICT_PUBLIC_PROOF_STAGE,
                    current_status="KEEP",
                    score=9,
                    reason_codes=["STRICT_PUBLIC_PROOF_PASS"],
                    dispatch_count=2,
                )

                self.assertEqual(created["lead_id"], updated["lead_id"])
                self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM lead_ledger").fetchone()[0])
                self.assertEqual("Alice Example", updated["full_name"])
                self.assertEqual("Ali", updated["first_name"])
                self.assertEqual("_important/leads_verified.csv", updated["source_file"])
                self.assertEqual("rowhash-2", updated["source_row_hash"])
                self.assertEqual("2026-04-01T00:00:00+00:00", updated["first_seen_at"])
                self.assertEqual("2026-04-03T00:00:00+00:00", updated["last_seen_at"])
                self.assertEqual(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, updated["current_stage"])
                self.assertEqual(["FAST_TRIAGE_LOCAL_CONFIDENCE", "STRICT_PUBLIC_PROOF_PASS"], updated["reason_codes"])
                self.assertEqual(2, updated["dispatch_count"])
            finally:
                conn.close()

    def test_record_transition_and_load_by_lead_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = lead_ledger.upsert_lead(
                    conn,
                    email="bob@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status="QUARANTINE",
                )
                loaded = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                self.assertIsNotNone(loaded)
                updated = lead_ledger.update_stage_status(
                    conn,
                    lead["lead_id"],
                    stage_after=lead_ledger.STRICT_PUBLIC_PROOF_STAGE,
                    status_after="KEEP",
                    reason_code="STRICT_PUBLIC_PROOF_PASS",
                    note="Promoted after public proof.",
                    run_id="verify_run_1",
                )

                self.assertEqual(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, updated["current_stage"])
                self.assertEqual("KEEP", updated["current_status"])
                events = lead_ledger.load_lead_events(conn, lead["lead_id"])
                self.assertEqual(1, len(events))
                self.assertEqual("stage_status_updated", events[0]["event_type"])
                self.assertEqual(lead_ledger.FAST_TRIAGE_STAGE, events[0]["stage_before"])
                self.assertEqual(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, events[0]["stage_after"])
                self.assertEqual("QUARANTINE", events[0]["status_before"])
                self.assertEqual("KEEP", events[0]["status_after"])
            finally:
                conn.close()

    def test_record_reason_codes_adds_only_new_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = lead_ledger.upsert_lead(
                    conn,
                    email="cara@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status="REJECT",
                )
                codes = lead_ledger.record_reason_codes(conn, lead["lead_id"], ["BAD_DOMAIN", "SUPPRESSED"])
                codes = lead_ledger.record_reason_codes(conn, lead["lead_id"], ["SUPPRESSED", "ROLE_ACCOUNT"])
                self.assertEqual(["BAD_DOMAIN", "SUPPRESSED", "ROLE_ACCOUNT"], codes)
                loaded = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                self.assertEqual(["BAD_DOMAIN", "SUPPRESSED", "ROLE_ACCOUNT"], loaded["reason_codes"])
                events = lead_ledger.load_lead_events(conn, lead["lead_id"])
                self.assertEqual(3, len(events))
                self.assertTrue(all(event["event_type"] == "reason_code_recorded" for event in events))
            finally:
                conn.close()

    def test_update_stage_status_is_safe_noop_when_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = lead_ledger.upsert_lead(
                    conn,
                    email="safe@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status="KEEP",
                )
                updated = lead_ledger.update_stage_status(
                    conn,
                    lead["lead_id"],
                    stage_after=lead_ledger.FAST_TRIAGE_STAGE,
                    status_after="KEEP",
                )
                self.assertEqual(lead_ledger.FAST_TRIAGE_STAGE, updated["current_stage"])
                self.assertEqual("KEEP", updated["current_status"])
                self.assertEqual([], lead_ledger.load_lead_events(conn, lead["lead_id"]))
            finally:
                conn.close()

    def test_import_leads_csv_backfills_and_reruns_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db_path = tmp / "ledger.sqlite3"
            triaged_keep = tmp / "_important" / "leads_triaged_keep.csv"
            write_csv(
                triaged_keep,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"},
                    {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"},
                    {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com", "Status": "KEEP"},
                ],
            )

            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                first = lead_ledger.import_leads_csv(
                    conn,
                    triaged_keep,
                    stage=lead_ledger.FAST_TRIAGE_STAGE,
                    status="KEEP",
                    run_id="backfill_1",
                    imported_at="2026-04-11T00:00:00+00:00",
                )
                second = lead_ledger.import_leads_csv(
                    conn,
                    triaged_keep,
                    stage=lead_ledger.FAST_TRIAGE_STAGE,
                    status="KEEP",
                    run_id="backfill_2",
                    imported_at="2026-04-11T01:00:00+00:00",
                )

                self.assertEqual(3, first["processed_rows"])
                self.assertEqual(2, first["imported_rows"])
                self.assertEqual(1, first["skipped_existing_rows"])
                self.assertEqual(0, second["imported_rows"])
                self.assertEqual(3, second["skipped_existing_rows"])
                self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM lead_ledger").fetchone()[0])
                self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM lead_ledger_import_rows").fetchone()[0])
            finally:
                conn.close()

    def test_backfill_merges_duplicate_emails_across_csv_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            conn = lead_ledger.connect_lead_ledger(tmp / "ledger.sqlite3")
            try:
                triaged_keep = tmp / "_important" / "leads_triaged_keep.csv"
                verified = tmp / "_important" / "leads_verified.csv"
                write_csv(
                    triaged_keep,
                    ["FullName", "FirstName", "Email", "Status"],
                    [{"FullName": "Delta Person", "FirstName": "Delta", "Email": "delta@example.com", "Status": "KEEP"}],
                )
                write_csv(
                    verified,
                    ["FullName", "FirstName", "Email", "Status", "VerificationReason"],
                    [{"FullName": "Delta Person", "FirstName": "Delta", "Email": "delta@example.com", "Status": "KEEP", "VerificationReason": "STRICT_PUBLIC_PROOF_PASS"}],
                )

                report = lead_ledger.backfill_lead_ledger(
                    conn,
                    csv_specs=(
                        {"path": triaged_keep, "stage": lead_ledger.FAST_TRIAGE_STAGE, "status": "KEEP"},
                        {"path": verified, "stage": lead_ledger.STRICT_PUBLIC_PROOF_STAGE, "status": "KEEP"},
                    ),
                    run_id="backfill_cross_file",
                    imported_at="2026-04-11T02:00:00+00:00",
                )

                self.assertEqual(2, report["processed_rows"])
                self.assertEqual(2, report["imported_rows"])
                self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM lead_ledger").fetchone()[0])
                lead = lead_ledger.load_lead_by_id(
                    conn,
                    lead_ledger.deterministic_lead_id("delta@example.com"),
                )
                self.assertEqual(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, lead["current_stage"])
                self.assertEqual("KEEP", lead["current_status"])
                self.assertIn("STRICT_PUBLIC_PROOF_PASS", lead["reason_codes"])
            finally:
                conn.close()

    def test_record_dispatch_event_updates_ledger_and_attempt_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = lead_ledger.upsert_lead(
                    conn,
                    email="dispatch@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status="KEEP",
                )
                first = lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=lead["lead_id"],
                    run_id="dispatch_run_1",
                    dispatch_source="triaged_keep",
                    profile="private_jc",
                    queue_target="private_jc",
                    result_status="queued",
                    dispatched_at="2026-04-11T03:00:00+00:00",
                )
                second = lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=lead["lead_id"],
                    run_id="dispatch_run_1",
                    dispatch_source="triaged_keep",
                    profile="sendgrid_1",
                    queue_target="sendgrid_1",
                    result_status="queued",
                    dispatched_at="2026-04-11T03:00:00+00:00",
                )

                self.assertEqual(1, first["attempt_number"])
                self.assertEqual(2, second["attempt_number"])
                dispatch_events = lead_ledger.load_dispatch_events(conn, lead["lead_id"])
                self.assertEqual(2, len(dispatch_events))
                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                self.assertEqual(2, updated["dispatch_count"])
                self.assertEqual("2026-04-11T03:00:00+00:00", updated["last_dispatch_at"])
                self.assertEqual("sendgrid_1", updated["last_profile"])
            finally:
                conn.close()

    def test_dispatch_history_state_and_contacted_lead_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                first = lead_ledger.upsert_lead(conn, email="alpha@example.com")
                second = lead_ledger.upsert_lead(conn, email="beta@example.com")
                lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=first["lead_id"],
                    run_id="dispatch_run_1",
                    dispatch_source="triaged_keep",
                    profile="private_jc",
                    queue_target="private_jc",
                    result_status="queued",
                    dispatched_at="2026-04-11T04:00:00+00:00",
                )
                lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=second["lead_id"],
                    run_id="dispatch_run_1",
                    dispatch_source="triaged_keep",
                    profile="sendgrid_1",
                    queue_target="sendgrid_1",
                    result_status="queued",
                    dispatched_at="2026-04-11T04:00:00+00:00",
                )

                state = lead_ledger.dispatch_history_state(conn)
                self.assertEqual(2, state["dispatch_event_count"])
                self.assertEqual(2, state["contacted_lead_count"])
                self.assertEqual(
                    {first["lead_id"], second["lead_id"]},
                    lead_ledger.load_contacted_lead_ids(conn),
                )
            finally:
                conn.close()

    def test_ingest_send_outcome_events_updates_delivered_and_deferred_history_only(self) -> None:
        for outcome in ("delivered", "deferred"):
            with self.subTest(outcome=outcome):
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "ledger.sqlite3"
                    conn = lead_ledger.connect_lead_ledger(db_path)
                    try:
                        lead, _ = self._seed_dispatched_lead(conn)
                    finally:
                        conn.close()

                    summary = lead_ledger.ingest_send_outcome_events(
                        [
                            {
                                "email": lead["email"],
                                "status": outcome,
                                "message_id": "ABC123.recvd-1",
                                "shard": "recipients_sendgrid_1.csv",
                                "astra_run_id": "dispatch_run_1",
                                "processed_at_utc": "2026-04-11T03:05:00+00:00",
                            }
                        ],
                        db_path=db_path,
                    )

                    self.assertEqual(1, summary["matched_events"])
                    self.assertEqual(0, summary["unmatched_events"])
                    self.assertEqual(0, summary["suppressed_events"])

                    conn = lead_ledger.connect_lead_ledger(db_path)
                    try:
                        updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                        events = lead_ledger.load_dispatch_events(conn, lead["lead_id"])
                        self.assertEqual(outcome, updated["last_outcome"])
                        self.assertFalse(updated["suppressed"])
                        self.assertEqual(outcome, events[0]["result_status"])
                        self.assertEqual("abc123", events[0]["provider_message_id"])
                    finally:
                        conn.close()

    def test_ingest_send_outcome_events_suppresses_bounced_unsubscribed_and_complained(self) -> None:
        cases = (
            ("bounced", "550 user unknown"),
            ("unsubscribed", "recipient unsubscribed"),
            ("spam_report", "spam complaint received"),
        )
        for raw_status, expected_reason in cases:
            with self.subTest(raw_status=raw_status):
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "ledger.sqlite3"
                    conn = lead_ledger.connect_lead_ledger(db_path)
                    try:
                        lead, _ = self._seed_dispatched_lead(conn, email=f"{raw_status}@example.com")
                    finally:
                        conn.close()

                    summary = lead_ledger.ingest_send_outcome_events(
                        [
                            {
                                "email": lead["email"],
                                "status": raw_status,
                                "code": "550" if raw_status == "bounced" else "",
                                "response": expected_reason,
                                "shard": "recipients_sendgrid_1.csv",
                                "astra_run_id": "dispatch_run_1",
                                "processed_at_utc": "2026-04-11T03:06:00+00:00",
                            }
                        ],
                        db_path=db_path,
                    )

                    self.assertEqual(1, summary["matched_events"])
                    self.assertEqual(1, summary["suppressed_events"])

                    conn = lead_ledger.connect_lead_ledger(db_path)
                    try:
                        updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                        dispatch_rows = lead_ledger.load_dispatch_events(conn, lead["lead_id"])
                        self.assertEqual(
                            "complained" if raw_status == "spam_report" else raw_status,
                            updated["last_outcome"],
                        )
                        self.assertTrue(updated["suppressed"])
                        self.assertIn(expected_reason.split()[0], updated["suppression_reason"])
                        self.assertEqual(updated["last_outcome"], dispatch_rows[0]["result_status"])
                    finally:
                        conn.close()

    def test_ingest_send_outcome_events_updates_blocked_and_dropped_without_auto_suppression(self) -> None:
        for outcome in ("blocked", "dropped"):
            with self.subTest(outcome=outcome):
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "ledger.sqlite3"
                    conn = lead_ledger.connect_lead_ledger(db_path)
                    try:
                        lead, _ = self._seed_dispatched_lead(conn, email=f"{outcome}@example.com")
                    finally:
                        conn.close()

                    summary = lead_ledger.ingest_send_outcome_events(
                        [
                            {
                                "email": lead["email"],
                                "status": outcome,
                                "response": f"{outcome} by provider",
                                "shard": "recipients_sendgrid_1.csv",
                                "astra_run_id": "dispatch_run_1",
                                "processed_at_utc": "2026-04-11T03:07:00+00:00",
                            }
                        ],
                        db_path=db_path,
                    )

                    self.assertEqual(1, summary["matched_events"])
                    self.assertEqual(0, summary["suppressed_events"])

                    conn = lead_ledger.connect_lead_ledger(db_path)
                    try:
                        updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                        dispatch_rows = lead_ledger.load_dispatch_events(conn, lead["lead_id"])
                        self.assertEqual(outcome, updated["last_outcome"])
                        self.assertFalse(updated["suppressed"])
                        self.assertEqual(outcome, dispatch_rows[0]["result_status"])
                    finally:
                        conn.close()

    def test_ingest_send_outcome_events_matches_by_provider_message_id_after_initial_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                lead, _ = self._seed_dispatched_lead(conn, email="provider@example.com")
            finally:
                conn.close()

            first = lead_ledger.ingest_send_outcome_events(
                [
                    {
                        "email": lead["email"],
                        "status": "delivered",
                        "message_id": "MSG-123.recvd-1",
                        "shard": "recipients_sendgrid_1.csv",
                        "astra_run_id": "dispatch_run_1",
                        "processed_at_utc": "2026-04-11T03:08:00+00:00",
                    }
                ],
                db_path=db_path,
            )
            second = lead_ledger.ingest_send_outcome_events(
                [
                    {
                        "email": lead["email"],
                        "status": "bounced",
                        "message_id": "MSG-123.recvd-9",
                        "response": "user unknown",
                        "processed_at_utc": "2026-04-11T03:09:00+00:00",
                    }
                ],
                db_path=db_path,
            )

            self.assertEqual(1, first["matched_events"])
            self.assertEqual(1, second["matched_events"])

            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                dispatch_rows = lead_ledger.load_dispatch_events(conn, lead["lead_id"])
                self.assertEqual("bounced", updated["last_outcome"])
                self.assertTrue(updated["suppressed"])
                self.assertEqual("msg-123", dispatch_rows[0]["provider_message_id"])
                self.assertEqual("bounced", dispatch_rows[0]["result_status"])
            finally:
                conn.close()

    def test_ingest_send_outcome_events_unmatched_events_fail_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ledger.sqlite3"
            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                lead = lead_ledger.upsert_lead(
                    conn,
                    email="safe_unmatched@example.com",
                    current_stage=lead_ledger.FAST_TRIAGE_STAGE,
                    current_status="KEEP",
                )
            finally:
                conn.close()

            summary = lead_ledger.ingest_send_outcome_events(
                [
                    {
                        "email": lead["email"],
                        "status": "bounced",
                        "response": "user unknown",
                        "processed_at_utc": "2026-04-11T03:10:00+00:00",
                    }
                ],
                db_path=db_path,
            )

            self.assertEqual(0, summary["matched_events"])
            self.assertEqual(1, summary["unmatched_events"])

            conn = lead_ledger.connect_lead_ledger(db_path)
            try:
                unchanged = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                self.assertEqual("", unchanged["last_outcome"])
                self.assertFalse(unchanged["suppressed"])
                self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM lead_dispatch_history").fetchone()[0])
            finally:
                conn.close()

    def test_list_quarantined_leads_filter_and_sort(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                low = self._seed_quarantined_lead(
                    conn,
                    email="low@example.com",
                    score=2.5,
                    reason_codes=["WEAK_PROOF"],
                )
                high = self._seed_quarantined_lead(
                    conn,
                    email="high@example.com",
                    stage=lead_ledger.STRICT_PUBLIC_PROOF_STAGE,
                    score=9.8,
                    reason_codes=["NO_PUBLIC_MATCH"],
                )
                mid = self._seed_quarantined_lead(
                    conn,
                    email="mid@example.com",
                    score=5.1,
                    reason_codes=["WEAK_PROOF"],
                )

                listed = lead_ledger.list_quarantine_review_leads(conn)
                filtered = lead_ledger.list_quarantine_review_leads(conn, reason_code="NO_PUBLIC_MATCH")
                ascending = lead_ledger.list_quarantine_review_leads(conn, sort="score_asc")
                filtered_ids = lead_ledger.list_quarantine_review_lead_ids(conn, reason_code="WEAK_PROOF")
                filtered_ids_with_exclusion = lead_ledger.list_quarantine_review_lead_ids(
                    conn,
                    reason_code="WEAK_PROOF",
                    exclude_lead_ids=[low["lead_id"]],
                )

                self.assertEqual(3, listed["counts"]["total_quarantined"])
                self.assertEqual(high["lead_id"], listed["leads"][0]["lead_id"])
                self.assertEqual([high["lead_id"]], [lead["lead_id"] for lead in filtered["leads"]])
                self.assertEqual(low["lead_id"], ascending["leads"][0]["lead_id"])
                self.assertEqual([mid["lead_id"], low["lead_id"]], filtered_ids)
                self.assertEqual([mid["lead_id"]], filtered_ids_with_exclusion)
                self.assertIn("NO_PUBLIC_MATCH", listed["reason_code_options"])
                self.assertIn(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, listed["stage_options"])
            finally:
                conn.close()

    def test_quarantine_promote_action_updates_ledger_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = self._seed_quarantined_lead(conn, email="promote@example.com", reason_codes=["WEAK_PROOF"])

                result = lead_ledger.apply_quarantine_review_action(
                    conn,
                    lead_ids=[lead["lead_id"]],
                    action="promote_dispatch_ready",
                    operator_note="Manual review approved.",
                    run_id="review_1",
                    updated_at="2026-04-11T05:00:00+00:00",
                )

                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                events = lead_ledger.load_lead_events(conn, lead["lead_id"])
                self.assertEqual(1, result["updated"])
                self.assertEqual(lead_ledger.QUARANTINE_REVIEW_STAGE, updated["current_stage"])
                self.assertEqual(lead_ledger.DISPATCH_READY_STATUS, updated["current_status"])
                self.assertEqual("Manual review approved.", updated["operator_note"])
                self.assertIn("REVIEW_PROMOTED_DISPATCH_READY", updated["reason_codes"])
                self.assertIn("quarantine_promoted_dispatch_ready", [event["event_type"] for event in events])
                self.assertIn("operator_note_updated", [event["event_type"] for event in events])
            finally:
                conn.close()

    def test_quarantine_reject_action_updates_ledger_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = self._seed_quarantined_lead(conn, email="reject@example.com", reason_codes=["CONFLICTING_PROOF"])

                lead_ledger.apply_quarantine_review_action(
                    conn,
                    lead_ids=[lead["lead_id"]],
                    action="reject_permanently",
                    run_id="review_2",
                    updated_at="2026-04-11T05:05:00+00:00",
                )

                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                events = lead_ledger.load_lead_events(conn, lead["lead_id"])
                self.assertEqual(lead_ledger.QUARANTINE_REVIEW_STAGE, updated["current_stage"])
                self.assertEqual(lead_ledger.REJECTED_STATUS, updated["current_status"])
                self.assertIn("REVIEW_REJECTED_PERMANENTLY", updated["reason_codes"])
                self.assertIn("quarantine_rejected_permanently", [event["event_type"] for event in events])
            finally:
                conn.close()

    def test_quarantine_send_to_strict_verify_marks_rows_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = self._seed_quarantined_lead(conn, email="strict@example.com", reason_codes=["NEEDS_WEB_PROOF"])

                lead_ledger.apply_quarantine_review_action(
                    conn,
                    lead_ids=[lead["lead_id"]],
                    action="send_to_strict_verify",
                    run_id="review_3",
                    updated_at="2026-04-11T05:10:00+00:00",
                )

                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                events = lead_ledger.load_lead_events(conn, lead["lead_id"])
                self.assertEqual(lead_ledger.STRICT_PUBLIC_PROOF_STAGE, updated["current_stage"])
                self.assertEqual(lead_ledger.PENDING_STRICT_PUBLIC_PROOF_STATUS, updated["current_status"])
                self.assertIn("REVIEW_SENT_TO_STRICT_PUBLIC_PROOF", updated["reason_codes"])
                self.assertIn("quarantine_sent_to_strict_public_proof", [event["event_type"] for event in events])
            finally:
                conn.close()

    def test_update_operator_note_persists_for_quarantine_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = lead_ledger.connect_lead_ledger(Path(tmpdir) / "ledger.sqlite3")
            try:
                lead = self._seed_quarantined_lead(conn, email="notes@example.com", reason_codes=["WEAK_PROOF"])

                lead_ledger.apply_quarantine_review_action(
                    conn,
                    lead_ids=[lead["lead_id"]],
                    action="update_operator_note",
                    operator_note="Need author site confirmation.",
                    run_id="review_4",
                    updated_at="2026-04-11T05:15:00+00:00",
                )

                updated = lead_ledger.load_lead_by_id(conn, lead["lead_id"])
                detail = lead_ledger.load_quarantine_review_lead(conn, lead["lead_id"])
                self.assertEqual("Need author site confirmation.", updated["operator_note"])
                self.assertIsNotNone(detail)
                self.assertEqual("Need author site confirmation.", detail["operator_note"])
                self.assertIn("operator_note_updated", [event["event_type"] for event in detail["review_events"]])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
