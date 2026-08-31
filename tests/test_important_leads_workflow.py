from __future__ import annotations

import csv
import json
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import important_leads_verify
import important_leads_workflow
import lead_ledger
import leads_workflow
import send_shard
from tools.rebuild_recipient_queues import default_queue_paths
from important_leads_workflow import (
    _validate_dispatch_preview_contract,
    _sent_email_set,
    check_master_leads,
    check_warm_research_leads,
    confirm_dispatch_preview,
    confirm_warm_private_jc_preview,
    create_safer_recontact_pool_from_preview,
    dispatch_master_leads,
    generate_warm_email_preview,
    is_safer_recontact_source_path,
    load_dispatch_preview,
    preview_dispatch_master_leads,
)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    source_like_names = {
        "leads.csv",
        "leads_triaged_keep.csv",
        "leads_verified.csv",
        "safer_recontact_pool.csv",
    }
    normalized_fieldnames = list(fieldnames)
    normalized_rows = [dict(row) for row in rows]
    if path.name in source_like_names and "Email" in normalized_fieldnames:
        original_fieldnames = set(normalized_fieldnames)
        for required in ["AuthorEmail", "AuthorName", "BookTitle"]:
            if required not in normalized_fieldnames:
                normalized_fieldnames.append(required)
        for row in normalized_rows:
            if "AuthorEmail" not in original_fieldnames and not str(row.get("AuthorEmail") or "").strip():
                row["AuthorEmail"] = str(row.get("Email") or "")
            if "AuthorName" not in original_fieldnames and not str(row.get("AuthorName") or "").strip():
                row["AuthorName"] = str(row.get("FullName") or row.get("FirstName") or "")
            if "BookTitle" not in original_fieldnames and not str(row.get("BookTitle") or "").strip():
                row["BookTitle"] = f"{str(row.get('FirstName') or row.get('FullName') or 'Test').strip() or 'Test'} Book"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=normalized_fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def planned_row(email: str, first_name: str = "Fresh") -> dict[str, str]:
    return {
        "Email": email,
        "FirstName": first_name,
        "AuthorEmail": email,
        "AuthorName": f"{first_name} Author",
        "BookTitle": f"{first_name} Book",
    }


def build_dynamic_dispatch_fixture(
    tmp: Path,
    *,
    preview_name: str,
    lead_count: int = 8,
    campaign_type: str = "cold",
) -> dict[str, object]:
    master_path = tmp / "leads.csv"
    triaged_keep_path = tmp / "leads_triaged_keep.csv"
    rows = [
        {
            "FullName": f"Lead {index}",
            "FirstName": f"Lead{index}",
            "Email": f"lead-{index}@example.com",
            "Status": "KEEP",
        }
        for index in range(1, lead_count + 1)
    ]
    write_csv(
        master_path,
        ["FullName", "FirstName", "Email"],
        [
            {key: row[key] for key in ("FullName", "FirstName", "Email")}
            for row in rows
        ],
    )
    write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
    for cfg in send_shard.PROFILES.values():
        csv_name = str(cfg.get("csv") or "").strip()
        log_name = str(cfg.get("log") or "").strip()
        if csv_name:
            write_csv(tmp / Path(csv_name).name, ["Email", "FirstName"], [])
        if log_name:
            write_csv(tmp / Path(log_name).name, ["Email", "Status"], [])
    write_csv(tmp / "sendgrid_domain_log.csv", ["Email", "Status"], [])
    write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])
    write_csv(tmp / "suppressed.csv", ["Email"], [])
    write_csv(tmp / "unsubscribed.csv", ["Email"], [])

    def managed_path(value: object) -> Path:
        return tmp / Path(str(value)).name

    preview_dir = tmp / preview_name
    with (
        patch.object(important_leads_workflow.settings, "shard_path", side_effect=managed_path),
        patch.object(important_leads_workflow.settings, "log_path", side_effect=managed_path),
    ):
        preview = preview_dispatch_master_leads(
            master_path=master_path,
            triaged_keep_path=triaged_keep_path,
            rejected_path=tmp / "leads_rejected.csv",
            dispatch_source_mode="triaged_keep",
            sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
            suppressed_path=tmp / "suppressed.csv",
            unsubscribed_path=tmp / "unsubscribed.csv",
            lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
            campaign_type=campaign_type,
            preview_dir=preview_dir,
        )
    return {
        "preview": preview,
        "preview_dir": preview_dir,
        "master_path": master_path,
        "triaged_keep_path": triaged_keep_path,
    }


class ImportantLeadsWorkflowTests(unittest.TestCase):
    def test_full_recontact_uses_only_currently_enabled_sendgrid_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = build_dynamic_dispatch_fixture(
                Path(tmpdir),
                preview_name="recontact_preview",
                campaign_type="recontact_cold",
            )
            preview = fixture["preview"]
            expected_profiles = [
                name
                for name in send_shard.PRODUCTION_SENDGRID_PROFILES
                if bool(send_shard.PROFILES[name].get("send_enabled", True))
            ]
            self.assertEqual(expected_profiles, preview["sendgrid_profile_order"])
            self.assertNotIn("sendgrid_annette", preview["sendgrid_profile_order"])
            self.assertNotIn("sendgrid_fiorela", preview["sendgrid_profile_order"])
            self.assertEqual(0, preview["rows_to_add_private_jc"])
            self.assertEqual(8, preview["rows_to_add_sendgrid"])
            self.assertTrue(preview["full_recontact_sendgrid_only"])

    def test_full_recontact_fails_when_no_sendgrid_lane_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            write_csv(master_path, ["Email", "FirstName"], [{"Email": "one@example.com", "FirstName": "One"}])
            write_csv(triaged_keep_path, ["Email", "FirstName", "Status"], [{"Email": "one@example.com", "FirstName": "One", "Status": "KEEP"}])
            jc_queue = tmp / "recipients_private_jc.csv"
            jc_log = tmp / "private_jc_log.csv"
            sg_log = tmp / "sendgrid_log.csv"
            write_csv(jc_queue, ["Email", "FirstName"], [])
            write_csv(jc_log, ["Email", "Status"], [])
            write_csv(sg_log, ["Email", "Status"], [])

            with patch.object(
                important_leads_workflow,
                "_dispatch_profile_paths",
                return_value=(jc_queue, [], jc_log, [sg_log]),
            ):
                with self.assertRaisesRegex(ValueError, "at least one enabled production SendGrid profile"):
                    preview_dispatch_master_leads(
                        master_path=master_path,
                        triaged_keep_path=triaged_keep_path,
                        rejected_path=tmp / "leads_rejected.csv",
                        dispatch_source_mode="triaged_keep",
                        campaign_type="recontact_cold",
                        preview_dir=tmp / "previews",
                    )

    def test_safer_recontact_keeps_balanced_private_and_sendgrid_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            safer_path = tmp / "leads_safer_recontact_not_seen_active_history.csv"
            rows = [
                {"Email": "one@example.com", "FirstName": "One", "AuthorEmail": "one@example.com", "AuthorName": "One", "BookTitle": "One Book", "Status": "KEEP"},
                {"Email": "two@example.com", "FirstName": "Two", "AuthorEmail": "two@example.com", "AuthorName": "Two", "BookTitle": "Two Book", "Status": "KEEP"},
            ]
            write_csv(master_path, ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"], [{key: row[key] for key in ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]} for row in rows])
            write_csv(safer_path, ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle", "Status"], rows)
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            logs = [tmp / "private_jc_log.csv", *[tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]]
            for path in [jc_queue, *sg_queues]:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=safer_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                campaign_type="recontact_cold",
                preview_dir=tmp / "previews",
            )
            self.assertEqual("safer_recontact", preview["dispatch_source_kind"])
            self.assertFalse(preview["full_recontact_sendgrid_only"])
            self.assertEqual(1, preview["rows_to_add_private_jc"])
            self.assertEqual(1, preview["rows_to_add_sendgrid"])
            self.assertNotIn("campaign_id", preview)
            self.assertNotIn("campaign_id", preview["queue_headers"])
            self.assertNotIn("dispatch_source_kind", preview["queue_headers"])
            for planned_rows in preview["plan_rows_by_queue"].values():
                for row in planned_rows:
                    self.assertNotIn("dispatch_source_kind", row)
                    self.assertNotIn("campaign_id", row)

            confirmed = confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=tmp / "backups",
                report_dir=tmp / "reports",
                persist_state=False,
                preview_dir=tmp / "previews",
            )
            self.assertEqual("", confirmed["campaign_id"])
            final_rows = [row for path in [jc_queue, *sg_queues] for row in read_csv_rows(path)]
            self.assertEqual(2, len(final_rows))
            self.assertTrue(all("campaign_id" not in row for row in final_rows))
            self.assertTrue(all("dispatch_source_kind" not in row for row in final_rows))
            self.assertEqual(
                {"recontact_cold"},
                {send_shard.campaign_id_for_row(row, "recontact_cold") for row in final_rows},
            )

    def test_warm_research_check_splits_email_contact_form_and_rejected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "warm.csv"
            ready_path = tmp / "warm_email_ready.csv"
            forms_path = tmp / "warm_contact_form_review.csv"
            rejected_path = tmp / "warm_rejected.csv"
            log_path = tmp / "private_jc_log.csv"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            suppressions_path = tmp / "sendgrid_suppressions.csv"
            bad_events_path = tmp / "sendgrid_events.jsonl"
            headers = [
                *important_leads_workflow.WARM_RESEARCH_HEADERS,
                *important_leads_workflow.WARM_RESEARCH_OPTIONAL_HEADERS,
            ]

            def warm_row(name: str, contact_path: str) -> dict[str, str]:
                return {
                    "AuthorName": name,
                    "BookTitleOrProject": "Synthetic Project",
                    "NeedSignal": "Synthetic need",
                    "SourcePlatform": "Synthetic source",
                    "SourceURL": "https://example.test/source",
                    "ContactPath": contact_path,
                    "RecommendedService": "Website",
                    "OutreachAngle": "Synthetic angle",
                    "PersonalizationLine": (
                        "I noticed your recent launch gives readers a clear way into the project."
                    ),
                }

            write_csv(
                input_path,
                headers,
                [
                    warm_row("Ready", "Email: ready@example.com"),
                    warm_row("Form", "Contact form: https://example.test/contact"),
                    warm_row("Duplicate", "ready@example.com"),
                    warm_row("Contacted", "contacted@example.com"),
                    warm_row("Suppressed", "suppressed@example.com"),
                    warm_row("Unsubscribed", "unsubscribed@example.com"),
                    warm_row("Bad event", "bad-event@example.com"),
                    warm_row("Invalid", "not-an-email@"),
                ],
            )
            write_csv(log_path, ["Email", "Status", "Info"], [{"Email": "contacted@example.com", "Status": "SENT", "Info": ""}])
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@example.com"}])
            write_csv(unsubscribed_path, ["Email"], [{"Email": "unsubscribed@example.com"}])
            write_csv(suppressions_path, ["email", "state", "type"], [])
            bad_events_path.write_text('{"event":"bounce","email":"bad-event@example.com"}\n', encoding="utf-8")

            report = check_warm_research_leads(
                input_path=input_path,
                email_ready_path=ready_path,
                contact_form_review_path=forms_path,
                rejected_path=rejected_path,
                log_paths=[log_path],
                sendgrid_suppressions_path=suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                bad_events_path=bad_events_path,
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
            )

            self.assertEqual(1, report["warm_email_ready_rows"])
            self.assertEqual(1, report["warm_contact_form_rows"])
            self.assertEqual(6, report["warm_rejected_rows"])
            self.assertEqual(1, report["already_contacted_rows"])
            self.assertEqual(3, report["suppressed_removed"])
            self.assertFalse(report["dispatch_enabled"])
            ready_row = read_csv_rows(ready_path)[0]
            self.assertEqual("ready@example.com", ready_row["AuthorEmail"])
            self.assertEqual("New", ready_row["ResearchStatus"])
            self.assertIn("PersonalizationLine", ready_row)
            self.assertEqual(
                "I noticed your recent launch gives readers a clear way into the project.",
                ready_row["PersonalizationLine"],
            )
            self.assertEqual("contact_form", read_csv_rows(forms_path)[0]["ContactMethod"])
            self.assertEqual(
                {"DUPLICATE_IN_BATCH", "ALREADY_CONTACTED", "SUPPRESSED", "INVALID_EMAIL_SYNTAX"},
                {row["reject_code"] for row in read_csv_rows(rejected_path)},
            )

    def test_warm_research_status_alias_maps_to_research_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            headers = [
                *important_leads_workflow.WARM_RESEARCH_HEADERS,
                *important_leads_workflow.WARM_RESEARCH_OPTIONAL_HEADERS,
                "Status",
                "ResearchStatus",
            ]
            input_path = tmp / "warm_with_status.csv"
            row = {header: "Synthetic" for header in important_leads_workflow.WARM_RESEARCH_HEADERS}
            row.update({
                "ContactPath": "author@example.com",
                "PersonalizationLine": "I saw your recent update about improving the reader journey.",
                "Status": "Qualified",
                "ResearchStatus": "",
            })
            research_status_row = dict(row)
            research_status_row.update({"ContactPath": "reviewed@example.com", "Status": "Legacy", "ResearchStatus": "Reviewed"})
            write_csv(input_path, headers, [row, research_status_row])
            write_csv(tmp / "suppressed.csv", ["Email"], [])
            write_csv(tmp / "unsubscribed.csv", ["Email"], [])
            write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])
            (tmp / "events.jsonl").write_text("", encoding="utf-8")

            report = check_warm_research_leads(
                input_path=input_path,
                email_ready_path=tmp / "warm_email_ready.csv",
                contact_form_review_path=tmp / "warm_contact_form_review.csv",
                rejected_path=tmp / "warm_rejected.csv",
                log_paths=[],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                bad_events_path=tmp / "events.jsonl",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
            )

            self.assertEqual(2, report["warm_email_ready_rows"])
            ready = read_csv_rows(tmp / "warm_email_ready.csv")
            self.assertEqual("Qualified", ready[0]["ResearchStatus"])
            self.assertEqual("Reviewed", ready[1]["ResearchStatus"])
            self.assertEqual(
                "I saw your recent update about improving the reader journey.",
                ready[0]["PersonalizationLine"],
            )
            self.assertNotIn("Status", ready[0])

    def test_warm_email_preview_renders_title_and_fallback_without_queue_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ready_path = tmp / "warm_email_ready.csv"
            preview_path = tmp / "warm_email_preview.csv"
            base = {
                "NeedSignal": "The campaign page is still being refined.",
                "SourcePlatform": "Synthetic source",
                "SourceURL": "https://example.test/source",
                "RecommendedService": "a premium campaign page",
                "OutreachAngle": "Lead with a clearer visual story.",
                "ResearchStatus": "New",
            }
            legacy_headers = [
                header
                for header in important_leads_workflow.WARM_EMAIL_READY_HEADERS
                if header != "PersonalizationLine"
            ]
            write_csv(
                ready_path,
                legacy_headers,
                [
                    {**base, "AuthorName": "Sarah Author", "AuthorEmail": "sarah@example.com", "BookTitleOrProject": "The Silent Garden", "ContactPath": "sarah@example.com", "ContactMethod": "email"},
                    {**base, "AuthorName": "", "AuthorEmail": "fallback@example.com", "BookTitleOrProject": "", "ContactPath": "fallback@example.com", "ContactMethod": "email"},
                    {**base, "AuthorName": "Form Only", "AuthorEmail": "form@example.com", "BookTitleOrProject": "Form Project", "ContactPath": "https://example.test/contact", "ContactMethod": "contact_form"},
                ],
            )

            report = generate_warm_email_preview(email_ready_path=ready_path, preview_path=preview_path)
            rows = read_csv_rows(preview_path)

            self.assertEqual(2, report["warm_email_preview_rows"])
            self.assertFalse(report["dispatch_enabled"])
            self.assertEqual(list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS), list(rows[0].keys()))
            self.assertEqual("A focused direction for The Silent Garden", rows[0]["EmailSubject"])
            self.assertIn("Hi Sarah,", rows[0]["EmailBody"])
            self.assertEqual(
                "A focused direction for your author platform",
                rows[1]["EmailSubject"],
            )
            self.assertIn("Hi there,", rows[1]["EmailBody"])
            self.assertIn(
                "I reviewed the available information about your author platform and identified "
                "one focused opportunity to strengthen how the project is presented.",
                rows[1]["EmailBody"],
            )
            combined_body = rows[0]["EmailBody"] + rows[1]["EmailBody"]
            self.assertIn("a focused launch presentation", combined_body)
            self.assertNotRegex(combined_body, r"\{[A-Za-z][A-Za-z0-9_]*\}")
            self.assertIn('reply “unsubscribe.”', rows[0]["EmailBody"])
            self.assertIn('reply “unsubscribe.”', rows[1]["EmailBody"])

    def test_warm_email_preview_uses_safe_personalization_without_raw_research_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ready_path = tmp / "warm_email_ready.csv"
            preview_path = tmp / "warm_email_preview.csv"
            personalization = (
                "  I saw your recent post about building a clearer home for readers\n"
                "without replacing the parts of the launch that already work.  "
            )
            need_signal = "INTERNAL NEED SIGNAL MUST NOT APPEAR"
            outreach_angle = "INTERNAL OUTREACH ANGLE MUST NOT APPEAR"
            write_csv(
                ready_path,
                list(important_leads_workflow.WARM_EMAIL_READY_HEADERS),
                [{
                    "AuthorName": "Riley Example",
                    "AuthorEmail": "riley@example.test",
                    "BookTitleOrProject": "A Database Story",
                    "NeedSignal": need_signal,
                    "SourcePlatform": "Synthetic source",
                    "SourceURL": "https://example.test/source",
                    "ContactPath": "riley@example.test",
                    "RecommendedService": "Custom author website",
                    "OutreachAngle": outreach_angle,
                    "PersonalizationLine": personalization,
                    "ResearchStatus": "New",
                    "ContactMethod": "email",
                }],
            )

            generate_warm_email_preview(email_ready_path=ready_path, preview_path=preview_path)
            row = read_csv_rows(preview_path)[0]
            body = row["EmailBody"]

            self.assertIn(
                "I saw your recent post about building a clearer home for readers "
                "without replacing the parts of the launch that already work.",
                body,
            )
            self.assertIn(
                "Based on what you shared, the clearest next step is a custom author website.",
                body,
            )
            self.assertNotIn(need_signal, body)
            self.assertNotIn(outreach_angle, body)
            self.assertIn(
                "\nWindelle JC\nFounder & CEO, Astra Productions\nastraproductions.co\n",
                body,
            )
            self.assertTrue(
                body.endswith(
                    'P.S. If you would rather not hear from me again, reply “unsubscribe.”\n'
                )
            )

    def test_warm_email_copy_uses_fallback_for_missing_blank_or_internal_personalization(self) -> None:
        unsafe_values = (
            None,
            "",
            "   ",
            "Explicit Need — author needs a stronger website",
            "Verified Presentation Gap — weak landing page",
            "NeedSignal: launch copy needs work",
            "OutreachAngle: lead with the trailer",
            "Scraper notes: source was https://example.test/internal",
            "NeedSignal suggests the launch copy needs clearer reader direction",
            "OUTREACH-ANGLE recommends leading with the trailer direction",
            "Need.Signal recommends a clearer reader direction for the launch",
            "The author shared more context at example.ai/about",
            "The author shared more context at https://example.test/about",
            "Reach the author directly at author@example.test",
            "<strong>The launch is centered on the reader journey.</strong>",
            "[The launch page](https://example.test) focuses on the reader journey.",
            "The `internal note` describes the current reader journey.",
            "The {FieldName} placeholder describes the current reader journey.",
            "The launch centers on readers.\n\nThe research also notes a new edition.",
            "- The launch centers on readers\n- A new edition is coming soon",
            "The launch centers on readers.\u0007",
        )
        for value in unsafe_values:
            with self.subTest(personalization=value):
                rendered = send_shard.render_warm_email_copy(
                    first_name="Sarah",
                    book_title_or_project="The Silent Garden",
                    recommended_service="Book landing page",
                    personalization_line=value,
                )
                self.assertEqual("fallback", rendered["template"])
                self.assertIn(
                    "I reviewed the available information about The Silent Garden and identified "
                    "one focused opportunity to strengthen how the project is presented.",
                    rendered["body"],
                )
                self.assertNotIn("Explicit Need", rendered["body"])
                self.assertNotIn("NeedSignal:", rendered["body"])
                self.assertNotIn("OutreachAngle:", rendered["body"])
                self.assertNotIn("https://example.test", rendered["body"])
                self.assertNotIn("author@example.test", rendered["body"])
                self.assertNotRegex(
                    rendered["subject"] + rendered["body"],
                    r"\{[A-Za-z][A-Za-z0-9_]*\}",
                )
                self.assertIn('reply “unsubscribe.”', rendered["body"])
        self.assertEqual(
            "I saw your recent launch update!",
            send_shard.normalize_warm_personalization_line(
                "  I saw your recent\nlaunch update!!  "
            ),
        )

    def test_warm_recommended_service_values_use_allowlist_or_fallback(self) -> None:
        expected = {
            "Custom author website": "a custom author website",
            "Cinematic book trailer": "a cinematic book trailer",
            "Book launch visuals": "book launch visuals",
            "Author platform presentation": "a stronger author-platform presentation",
            "Book landing page": "a book landing page",
            "Launch visuals + landing page + trailer clips": (
                "launch visuals, a landing page, and trailer clips"
            ),
        }
        for value, phrase in expected.items():
            with self.subTest(service=value):
                self.assertEqual(
                    phrase,
                    send_shard.format_warm_recommended_service_phrase(value),
                )
        unsupported_values = (
            None,
            "",
            "   ",
            "Premium campaign page",
            "Unsupported campaign service",
            "RecommendedService",
            "Synthetic service",
            "NeedSignal: launch copy needs work",
            "https://example.test/service",
            "service@example.test",
            "{RecommendedService}",
            "x" * 161,
        )
        for value in unsupported_values:
            with self.subTest(unsupported_service=value):
                self.assertEqual(
                    "a focused launch presentation",
                    send_shard.format_warm_recommended_service_phrase(value),
                )
        rendered = send_shard.render_warm_email_copy(
            first_name="Sarah",
            book_title_or_project="The Silent Garden",
            recommended_service="Author platform presentation",
            personalization_line="I saw how your recent launch gives readers a clear path into the story.",
        )
        self.assertIn(
            "Based on what you shared, the clearest next step is "
            "a stronger author-platform presentation.",
            rendered["body"],
        )

    def test_warm_research_requires_valid_personalization_for_email_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "warm.csv"
            headers = [
                *important_leads_workflow.WARM_RESEARCH_HEADERS,
                *important_leads_workflow.WARM_RESEARCH_OPTIONAL_HEADERS,
            ]
            base = {
                "BookTitleOrProject": "Synthetic Project",
                "NeedSignal": "Synthetic need",
                "SourcePlatform": "Synthetic source",
                "SourceURL": "https://example.test/source",
                "RecommendedService": "Website",
                "OutreachAngle": "Synthetic angle",
            }
            write_csv(
                input_path,
                headers,
                [
                    {
                        **base,
                        "AuthorName": "Valid",
                        "ContactPath": "valid@example.com",
                        "PersonalizationLine": (
                            "I noticed your latest release gives readers a clear entry into the series."
                        ),
                    },
                    {
                        **base,
                        "AuthorName": "Blank",
                        "ContactPath": "blank@example.com",
                        "PersonalizationLine": "",
                    },
                    {
                        **base,
                        "AuthorName": "Unsafe",
                        "ContactPath": "unsafe@example.com",
                        "PersonalizationLine": "NeedSignal indicates a stronger launch page is required",
                    },
                ],
            )
            for name, fields in (
                ("suppressed.csv", ["Email"]),
                ("unsubscribed.csv", ["Email"]),
                ("sendgrid_suppressions.csv", ["email", "state", "type"]),
            ):
                write_csv(tmp / name, fields, [])
            (tmp / "events.jsonl").write_text("", encoding="utf-8")

            report = check_warm_research_leads(
                input_path=input_path,
                email_ready_path=tmp / "warm_email_ready.csv",
                contact_form_review_path=tmp / "warm_contact_form_review.csv",
                rejected_path=tmp / "warm_rejected.csv",
                log_paths=[],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                bad_events_path=tmp / "events.jsonl",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
            )

            self.assertEqual(1, report["warm_email_ready_rows"])
            self.assertEqual(0, report["warm_contact_form_rows"])
            self.assertEqual(2, report["warm_rejected_rows"])
            rejected = read_csv_rows(tmp / "warm_rejected.csv")
            self.assertTrue(
                all(row["reject_code"] == "PERSONALIZATION_REVIEW_REQUIRED" for row in rejected)
            )
            self.assertTrue(
                all(
                    row["reject_reason"]
                    == "Manual review required: missing or invalid PersonalizationLine."
                    for row in rejected
                )
            )

    def test_legacy_warm_research_without_personalization_is_parseable_but_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "legacy_warm.csv"
            write_csv(
                input_path,
                list(important_leads_workflow.WARM_RESEARCH_HEADERS),
                [{
                    "AuthorName": "Legacy",
                    "BookTitleOrProject": "Synthetic Project",
                    "NeedSignal": "Synthetic need",
                    "SourcePlatform": "Synthetic source",
                    "SourceURL": "https://example.test/source",
                    "ContactPath": "legacy@example.com",
                    "RecommendedService": "Website",
                    "OutreachAngle": "Synthetic angle",
                }],
            )
            for name, fields in (
                ("suppressed.csv", ["Email"]),
                ("unsubscribed.csv", ["Email"]),
                ("sendgrid_suppressions.csv", ["email", "state", "type"]),
            ):
                write_csv(tmp / name, fields, [])
            (tmp / "events.jsonl").write_text("", encoding="utf-8")

            report = check_warm_research_leads(
                input_path=input_path,
                email_ready_path=tmp / "warm_email_ready.csv",
                contact_form_review_path=tmp / "warm_contact_form_review.csv",
                rejected_path=tmp / "warm_rejected.csv",
                log_paths=[],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                bad_events_path=tmp / "events.jsonl",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
            )

            self.assertEqual(0, report["warm_email_ready_rows"])
            self.assertEqual(1, report["warm_rejected_rows"])
            rejected = read_csv_rows(tmp / "warm_rejected.csv")[0]
            self.assertEqual("Legacy", rejected["AuthorName"])
            self.assertEqual("PERSONALIZATION_REVIEW_REQUIRED", rejected["reject_code"])

    def test_warm_subject_uses_author_platform_fallback_for_unsafe_project_labels(self) -> None:
        unsafe_titles = (
            "",
            "Current catalog",
            "  cUrReNt   CaTaLoG  ",
            "Current catalog and newest two books",
            "Multiple projects",
            "Newest books",
            "Unknown",
            "N/A",
            "NA",
            "None",
            "Author platform",
            "example.ai/catalog",
            "author@example.test",
            "NeedSignal: internal title",
            "<strong>Current catalog</strong>",
            "[Current catalog](https://example.test)",
            "{BookTitleOrProject}",
        )
        for title in unsafe_titles:
            with self.subTest(title=title):
                rendered = send_shard.render_warm_email_copy(
                    first_name="Sarah",
                    book_title_or_project=title,
                    recommended_service="Book landing page",
                    personalization_line="",
                )
                self.assertEqual(
                    "A focused direction for your author platform",
                    rendered["subject"],
                )
                self.assertIn(
                    "I reviewed the available information about your author platform and identified "
                    "one focused opportunity to strengthen how the project is presented.",
                    rendered["body"],
                )
                if title:
                    self.assertNotIn(title, rendered["subject"])
                    self.assertNotIn(title, rendered["body"])

        clean = send_shard.render_warm_email_copy(
            first_name="Sarah",
            book_title_or_project="The Silent Garden",
            recommended_service="Book landing page",
            personalization_line="",
        )
        self.assertEqual(
            "A focused direction for The Silent Garden",
            clean["subject"],
        )

    def test_warm_optional_personalization_does_not_change_queue_or_hash_schema(self) -> None:
        self.assertIn(
            "PersonalizationLine",
            important_leads_workflow.WARM_EMAIL_READY_HEADERS,
        )
        self.assertNotIn(
            "PersonalizationLine",
            important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS,
        )
        self.assertNotIn(
            "PersonalizationLine",
            important_leads_workflow.WARM_PRIVATE_JC_QUEUE_HEADERS,
        )
        self.assertNotIn(
            "PersonalizationLine",
            send_shard.WARM_CONFIRMATION_PROTECTED_FIELDS,
        )

    def test_warm_template_change_does_not_replace_cold_or_sendgrid_pitches(self) -> None:
        self.assertIs(send_shard.PITCHES["pitch_jc"]["body"], send_shard.PITCH_JC_BODY)
        self.assertTrue(
            all(
                config.get("pitch") != "pitch_warm"
                for name, config in send_shard.PROFILES.items()
                if name == "private_jc" or name.startswith("sendgrid_")
            )
        )

    def test_safer_recontact_source_path_helper_classifies_safe_csv(self) -> None:
        self.assertTrue(is_safer_recontact_source_path("_important/runs/check_x/leads_safer_recontact_not_seen_active_history.csv"))
        self.assertTrue(is_safer_recontact_source_path("/tmp/leads_safer_recontact_not_seen_active_history.csv"))
        self.assertFalse(is_safer_recontact_source_path("_important/runs/check_x/leads.csv"))
        self.assertFalse(is_safer_recontact_source_path(""))

    def test_author_outreach_fields_survive_check_triage_preview_and_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "authors.csv"
            checked_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            triaged_reject_path = tmp / "leads_triaged_reject.csv"
            triaged_quarantine_path = tmp / "leads_triaged_quarantine.csv"
            strict_verified_path = tmp / "leads_verified.csv"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            ledger_path = tmp / "lead_ledger.sqlite3"
            preview_dir = tmp / "previews"
            backups_dir = tmp / "backups"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            jc_log = tmp / "private_jc_log.csv"
            sg_logs = [tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]
            author_headers = [
                "AuthorName",
                "AuthorEmail",
                "Website",
                "SourceURL",
                "Location",
                "BookTitle",
                "BookURL",
                "RecentSignal",
                "IndieOrSmallPressSignal",
                "WebsitePresentationIssue",
                "WhyAstraFit",
                "PersonalizedOpeningLine",
                "ConfidenceScore",
                "ExtraProofColumn",
            ]
            write_csv(
                input_path,
                author_headers,
                [
                    {
                        "AuthorName": "Lisa Stone",
                        "AuthorEmail": "lisa@stonebooks.com",
                        "Website": "https://stonebooks.com",
                        "SourceURL": "https://source.test/lisa",
                        "Location": "Austin, TX",
                        "BookTitle": "The Quiet Harbor",
                        "BookURL": "https://books.test/quiet-harbor",
                        "RecentSignal": "Recent author event",
                        "IndieOrSmallPressSignal": "Small press imprint",
                        "WebsitePresentationIssue": "Book page lacks trailer",
                        "WhyAstraFit": "Strong visual fiction brand",
                        "PersonalizedOpeningLine": "I noticed your recent event for The Quiet Harbor.",
                        "ConfidenceScore": "91",
                        "ExtraProofColumn": "keep this proof",
                    }
                ],
            )
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])
            write_csv(strict_verified_path, ["Email", "FirstName"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            write_csv(jc_log, ["Email", "Status"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in sg_logs:
                write_csv(path, ["Email", "Status"], [])

            check_master_leads(
                input_path=input_path,
                output_path=checked_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                report_dir=tmp,
                summary_dir=tmp / "check_runs",
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )
            with checked_path.open(newline="", encoding="utf-8-sig") as handle:
                checked_reader = csv.DictReader(handle)
                checked_rows = list(checked_reader)
            required_headers = {
                "Email",
                "AuthorEmail",
                "AuthorName",
                "FirstName",
                "first_name_clean",
                "BookTitle",
                "PersonalizedOpeningLine",
                "ConfidenceScore",
                "Website",
                "SourceURL",
                "BookURL",
                "Location",
                "RecentSignal",
                "IndieOrSmallPressSignal",
                "WebsitePresentationIssue",
                "WhyAstraFit",
                "ExtraProofColumn",
            }
            self.assertTrue(required_headers.issubset(set(checked_reader.fieldnames or [])))
            self.assertEqual("lisa@stonebooks.com", checked_rows[0]["Email"])
            self.assertEqual("lisa@stonebooks.com", checked_rows[0]["AuthorEmail"])
            self.assertEqual("Lisa Stone", checked_rows[0]["AuthorName"])
            self.assertEqual("Lisa", checked_rows[0]["FirstName"])
            self.assertEqual("Lisa", checked_rows[0]["first_name_clean"])
            self.assertEqual("I noticed your recent event for The Quiet Harbor.", checked_rows[0]["PersonalizedOpeningLine"])

            with patch.object(important_leads_verify, "_lead_ledger_db_path", return_value=ledger_path):
                important_leads_verify.fast_triage_master_leads(
                    input_path=checked_path,
                    keep_path=triaged_keep_path,
                    rejected_path=triaged_reject_path,
                    quarantine_path=triaged_quarantine_path,
                    persist_state=False,
                    disposable_domains=set(),
                )
            with triaged_keep_path.open(newline="", encoding="utf-8-sig") as handle:
                triage_reader = csv.DictReader(handle)
                triage_rows = list(triage_reader)
            self.assertEqual(1, len(triage_rows))
            self.assertTrue(required_headers.issubset(set(triage_reader.fieldnames or [])))

            preview = preview_dispatch_master_leads(
                master_path=checked_path,
                rejected_path=rejected_path,
                verified_path=strict_verified_path,
                triaged_keep_path=triaged_keep_path,
                dispatch_source_mode=important_leads_workflow.DISPATCH_SOURCE_TRIAGED_KEEP,
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=jc_log,
                sendgrid_log_paths=sg_logs,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=ledger_path,
                preview_dir=preview_dir,
            )
            self.assertIn("BookTitle", preview["queue_headers"])
            self.assertIn("PersonalizedOpeningLine", preview["queue_headers"])
            self.assertIn("AuthorName", preview["queue_headers"])
            self.assertIn("AuthorEmail", preview["queue_headers"])
            planned_rows = [row for rows in preview["plan_rows_by_queue"].values() for row in rows]
            self.assertEqual("The Quiet Harbor", planned_rows[0]["BookTitle"])
            self.assertEqual("I noticed your recent event for The Quiet Harbor.", planned_rows[0]["PersonalizedOpeningLine"])

            confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=backups_dir,
                report_dir=tmp,
                persist_state=False,
                preview_dir=preview_dir,
            )
            queued_headers = set()
            queued_rows: list[dict[str, str]] = []
            for path in [jc_queue, *sg_queues]:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.DictReader(handle)
                    queued_headers.update(reader.fieldnames or [])
                    queued_rows.extend(list(reader))
            self.assertTrue({"BookTitle", "PersonalizedOpeningLine", "AuthorName", "AuthorEmail"}.issubset(queued_headers))
            self.assertEqual("The Quiet Harbor", queued_rows[0]["BookTitle"])
            self.assertEqual("I noticed your recent event for The Quiet Harbor.", queued_rows[0]["PersonalizedOpeningLine"])

    def test_saved_windows_paths_reset_to_local_important_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            important_dir = root / "_important"
            important_dir.mkdir()
            defaults = {
                "leadschecker.csv": "FullName,FirstName,Email\n",
                "leads.csv": "FullName,FirstName,Email\n",
                "leads_rejected.csv": "Email,reject_code\n",
                "leads_verified.csv": "FullName,FirstName,Email,Status\n",
                "leads_verify_rejected.csv": "FullName,FirstName,Email,Status\n",
                "leads_quarantine.csv": "FullName,FirstName,Email,Status\n",
            }
            for name, content in defaults.items():
                (important_dir / name).write_text(content, encoding="utf-8")

            poisoned_state = {
                important_leads_workflow.IMPORTANT_PATHS_STATE_KEY: {
                    "input_path": "/mnt/d/VS/email automation/_important/leadschecker.csv",
                    "output_path": "/mnt/d/VS/email automation/_important/leads.csv",
                    "rejected_path": "C:\\VS\\email automation\\_important\\leads_rejected.csv",
                },
                important_leads_verify.VERIFY_PATHS_STATE_KEY: {
                    "input_path": "/mnt/d/VS/email automation/_important/leads.csv",
                    "verified_path": "leads_verified.csv",
                    "rejected_path": "/mnt/d/VS/email automation/_important/leads_verify_rejected.csv",
                    "quarantine_path": "D:\\VS\\email automation\\_important\\leads_quarantine.csv",
                },
            }

            with patch.object(important_leads_workflow.settings, "APP_ROOT", root), patch.object(
                important_leads_workflow, "IMPORTANT_DIR", important_dir
            ), patch.object(
                important_leads_workflow, "MASTER_INPUT_PATH", important_dir / "leadschecker.csv"
            ), patch.object(
                important_leads_workflow, "MASTER_OUTPUT_PATH", important_dir / "leads.csv"
            ), patch.object(
                important_leads_workflow, "MASTER_REJECTED_PATH", important_dir / "leads_rejected.csv"
            ), patch.object(
                important_leads_workflow, "load_state", return_value=poisoned_state
            ), patch.object(
                important_leads_verify.settings, "APP_ROOT", root
            ), patch.object(
                important_leads_verify, "IMPORTANT_DIR", important_dir
            ), patch.object(
                important_leads_verify, "DEFAULT_INPUT_PATH", important_dir / "leads.csv"
            ), patch.object(
                important_leads_verify, "DEFAULT_VERIFIED_PATH", important_dir / "leads_verified.csv"
            ), patch.object(
                important_leads_verify, "DEFAULT_REJECTED_PATH", important_dir / "leads_verify_rejected.csv"
            ), patch.object(
                important_leads_verify, "DEFAULT_QUARANTINE_PATH", important_dir / "leads_quarantine.csv"
            ), patch.object(
                important_leads_verify, "load_state", return_value=poisoned_state
            ):
                self.assertEqual(
                    {
                        "input_path": "_important/leadschecker.csv",
                        "output_path": "_important/leads.csv",
                        "rejected_path": "_important/leads_rejected.csv",
                    },
                    important_leads_workflow.important_leads_path_state(),
                )
                self.assertEqual(
                    {
                        "input_path": "_important/leads.csv",
                        "verified_path": "_important/leads_verified.csv",
                        "rejected_path": "_important/leads_verify_rejected.csv",
                        "quarantine_path": "_important/leads_quarantine.csv",
                    },
                    important_leads_verify.important_leads_verify_path_state(),
                )

    def test_check_master_leads_hardens_rows_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            report_dir = tmp / "reports"
            summary_dir = tmp / "check_runs"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            disposable_domains_path = tmp / "disposable_domains.txt"

            input_path.write_text(
                "\ufefffull_name;author_email;Source\n"
                " Alice Example ; Alice@Gmial.com ;list-a\n"
                "Alice Rich;ALICE@gmail.com;list-a-dup\n"
                "Support;support@gmail.com;role\n"
                "Temp;temp@mailinator.com;temp\n"
                "Supp;suppressed@gmail.com;supp\n"
                "Bad;not-an-email;bad\n"
                "Maybe;writer@gmaill.com;typo\n"
                "Bob;bob@yahoo.com;good\n"
                "\n",
                encoding="utf-8",
            )
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@gmail.com"}])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])
            disposable_domains_path.write_text("mailinator.com\n", encoding="utf-8")

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                report_dir=report_dir,
                summary_dir=summary_dir,
                validate_deliverability=False,
                reject_role_accounts=True,
                reject_disposable=True,
                disposable_domains_path=disposable_domains_path,
                persist_state=False,
            )

            self.assertEqual(report["input_rows"], 9)
            self.assertEqual(report["total_input_rows"], 9)
            self.assertEqual(report["cleaned_rows"], 2)
            self.assertEqual(report["valid_rows"], 2)
            self.assertEqual(report["rejected_rows"], 7)
            self.assertEqual(report["duplicates_removed"], 1)
            self.assertEqual(report["suppressed_removed"], 1)
            self.assertEqual(report["role_accounts_removed"], 1)
            self.assertEqual(report["disposable_removed"], 1)
            self.assertEqual(report["invalid_syntax_removed"], 1)
            self.assertEqual(report["suspicious_flagged"], 1)
            self.assertEqual(report["corrected_rows"], 1)
            self.assertEqual(report["safe_fixes_applied"], 1)
            self.assertEqual(report["blank_rows"], 1)
            self.assertEqual(
                report["output_fieldnames"],
                [
                    "FullName",
                    "FirstName",
                    "Email",
                    "first_name_clean",
                    "last_name_clean",
                    "first_name_status",
                    "personalization_allowed",
                    "cleanup_notes",
                    "last_name",
                    "AuthorEmail",
                    "Source",
                ],
            )

            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["FullName"], "Alice Example")
            self.assertEqual(rows[0]["FirstName"], "Alice")
            self.assertEqual(rows[0]["first_name_clean"], "Alice")
            self.assertEqual(rows[0]["first_name_status"], "valid")
            self.assertEqual(rows[0]["personalization_allowed"], "true")
            self.assertEqual(rows[0]["Email"], "alice@gmail.com")
            self.assertEqual(rows[0]["AuthorEmail"], "Alice@Gmial.com")
            self.assertEqual(rows[0]["Source"], "list-a")
            self.assertEqual(rows[1]["Email"], "bob@yahoo.com")

            with rejected_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rejected = list(reader)
            self.assertEqual(len(rejected), 7)
            rejected_codes = [row["reject_code"] for row in rejected]
            self.assertIn("BLANK_ROW", rejected_codes)
            self.assertIn("DUPLICATE_IN_BATCH", rejected_codes)
            self.assertIn("ROLE_ACCOUNT", rejected_codes)
            self.assertIn("DISPOSABLE_DOMAIN", rejected_codes)
            self.assertIn("SUPPRESSED", rejected_codes)
            self.assertIn("INVALID_EMAIL_SYNTAX", rejected_codes)
            self.assertIn("UNKNOWN_DOMAIN_TYPO", rejected_codes)
            self.assertIn("normalized_email", reader.fieldnames or [])
            self.assertIn("correction_applied", reader.fieldnames or [])
            self.assertIn("correction_reason", reader.fieldnames or [])
            self.assertIn("reject_reason", reader.fieldnames or [])

            summary_path = Path(report["summary_path"])
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["total_input_rows"], 9)
            self.assertEqual(summary["valid_rows"], 2)
            self.assertEqual(summary["rejected_rows"], 7)
            self.assertEqual(summary["duplicates_removed"], 1)
            self.assertEqual(summary["suppressed_removed"], 1)
            self.assertEqual(summary["role_accounts_removed"], 1)
            self.assertEqual(summary["disposable_removed"], 1)
            self.assertEqual(summary["invalid_syntax_removed"], 1)
            self.assertEqual(summary["blank_rows"], 1)
            self.assertFalse(summary["deliverability_enabled"])

    def test_lead_op_fields_preserved_in_cleaned_and_rejected_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "lead_op_upload.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            headers = [
                "AuthorName",
                "AuthorEmail",
                "BookTitle",
                "PersonalizedOpeningLine",
                "WhyAstraFit",
                "Website",
                "BookURL",
                "ConfidenceScore",
                "source_file",
                "source_sheet",
                "source_row",
            ]
            write_csv(
                input_path,
                headers,
                [
                    {
                        "AuthorName": "Casey Vale",
                        "AuthorEmail": "casey.vale@example.org",
                        "BookTitle": "Harbor Signals",
                        "PersonalizedOpeningLine": "I noticed the launch page for Harbor Signals.",
                        "WhyAstraFit": "The book page would benefit from clearer retail links.",
                        "Website": "https://casey.example.org",
                        "BookURL": "https://books.example.org/harbor-signals",
                        "ConfidenceScore": "94",
                        "source_file": "synthetic_upload.csv",
                        "source_sheet": "Authors",
                        "source_row": "2",
                    },
                    {
                        "AuthorName": "Morgan Reed",
                        "AuthorEmail": "not-an-email",
                        "BookTitle": "Broken Compass",
                        "PersonalizedOpeningLine": "I noticed the listing for Broken Compass.",
                        "WhyAstraFit": "Synthetic rejected-row proof.",
                        "Website": "https://morgan.example.org",
                        "BookURL": "https://books.example.org/broken-compass",
                        "ConfidenceScore": "71",
                        "source_file": "synthetic_upload.csv",
                        "source_sheet": "Authors",
                        "source_row": "3",
                    },
                ],
            )
            write_csv(tmp / "suppressed.csv", ["Email"], [])
            write_csv(tmp / "unsubscribed.csv", ["Email"], [])
            write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                report_dir=tmp / "reports",
                summary_dir=tmp / "check_runs",
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

            self.assertEqual(2, report["total_input_rows"])
            self.assertEqual(1, report["cleaned_rows"])
            self.assertEqual(1, report["rejected_rows"])
            self.assertEqual(1, report["reason_counts"]["INVALID_EMAIL_SYNTAX"])
            expected_headers = {
                "FullName",
                "FirstName",
                "Email",
                "first_name_clean",
                "last_name_clean",
                "first_name_status",
                "personalization_allowed",
                "cleanup_notes",
                "last_name",
                "BookTitle",
                "AuthorName",
                "AuthorEmail",
                "PersonalizedOpeningLine",
                "WhyAstraFit",
                "Website",
                "BookURL",
                "ConfidenceScore",
                "source_file",
                "source_sheet",
                "source_row",
            }
            self.assertTrue(expected_headers.issubset(set(report["output_fieldnames"])))

            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                cleaned_reader = csv.DictReader(handle)
                cleaned_rows = list(cleaned_reader)
            self.assertTrue(expected_headers.issubset(set(cleaned_reader.fieldnames or [])))
            self.assertEqual("Harbor Signals", cleaned_rows[0]["BookTitle"])
            self.assertEqual("Casey Vale", cleaned_rows[0]["AuthorName"])
            self.assertEqual("casey.vale@example.org", cleaned_rows[0]["AuthorEmail"])
            self.assertEqual("I noticed the launch page for Harbor Signals.", cleaned_rows[0]["PersonalizedOpeningLine"])
            self.assertEqual("The book page would benefit from clearer retail links.", cleaned_rows[0]["WhyAstraFit"])
            self.assertEqual("https://casey.example.org", cleaned_rows[0]["Website"])
            self.assertEqual("https://books.example.org/harbor-signals", cleaned_rows[0]["BookURL"])
            self.assertEqual("94", cleaned_rows[0]["ConfidenceScore"])
            self.assertEqual("synthetic_upload.csv", cleaned_rows[0]["source_file"])
            self.assertEqual("Authors", cleaned_rows[0]["source_sheet"])
            self.assertEqual("2", cleaned_rows[0]["source_row"])

            with rejected_path.open(newline="", encoding="utf-8-sig") as handle:
                rejected_reader = csv.DictReader(handle)
                rejected_rows = list(rejected_reader)
            self.assertTrue(expected_headers.issubset(set(rejected_reader.fieldnames or [])))
            self.assertEqual("Broken Compass", rejected_rows[0]["BookTitle"])
            self.assertEqual("Morgan Reed", rejected_rows[0]["AuthorName"])
            self.assertEqual("not-an-email", rejected_rows[0]["AuthorEmail"])
            self.assertEqual("Synthetic rejected-row proof.", rejected_rows[0]["WhyAstraFit"])
            self.assertEqual("INVALID_EMAIL_SYNTAX", rejected_rows[0]["reject_code"])

    def test_check_master_leads_hardens_first_names_without_rejecting_valid_emails(self) -> None:
        invalid_cases = {
            "A": "one_character",
            "AA": "initials_only",
            "J.": "dotted_initials",
            "A.J.": "dotted_initials",
            "Dr.": "honorific_only",
            "PhD": "credential_only",
            "MD": "credential_only",
            "Jr.": "suffix_only",
            "CEO": "role_title_only",
            "Founder": "role_title_only",
            "Author": "role_title_only",
            "Info": "generic_business",
            "Admin": "generic_business",
            ":Lisa": "surrounding_punctuation",
            "'Ana": "surrounding_punctuation",
            "555-121-9090": "phone_like",
            "bad@example.com": "email_like",
            "!!!": "mostly_punctuation",
            "JosÃ©": "mojibake",
            "": "blank",
        }
        valid_cases = ["John", "Mary", "Anne-Marie", "O’Connor", "José", "Chloë", "Jean Luc", "ทองแดง", "(Seth)"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            rows = []
            index = 0
            for name in invalid_cases:
                index += 1
                rows.append({"first_name": name, "last_name": "Example", "email": f"bad-name-{index}@example.org"})
            for name in valid_cases:
                index += 1
                rows.append({"first_name": name, "last_name": "Example", "email": f"good-name-{index}@example.org"})
            write_csv(input_path, ["first_name", "last_name", "email"], rows)

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                report_dir=tmp / "reports",
                summary_dir=tmp / "check_runs",
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

            self.assertEqual(report["cleaned_rows"], len(rows))
            self.assertEqual(report["rejected_rows"], 0)
            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                cleaned = list(csv.DictReader(handle))
            by_email = {row["Email"]: row for row in cleaned}

            for idx, (name, status) in enumerate(invalid_cases.items(), start=1):
                row = by_email[f"bad-name-{idx}@example.org"]
                self.assertEqual(row["FirstName"], "", name)
                self.assertEqual(row["first_name_clean"], "", name)
                self.assertEqual(row["first_name_status"], status, name)
                self.assertEqual(row["personalization_allowed"], "false", name)
                self.assertIn(status, row["cleanup_notes"], name)

            valid_start = len(invalid_cases) + 1
            for offset, name in enumerate(valid_cases):
                row = by_email[f"good-name-{valid_start + offset}@example.org"]
                expected = "Seth" if name == "(Seth)" else name
                self.assertEqual(row["FirstName"], expected)
                self.assertEqual(row["first_name_clean"], expected)
                self.assertEqual(row["first_name_status"], "valid")
                self.assertEqual(row["personalization_allowed"], "true")
                self.assertEqual(row["last_name_clean"], "Example")

    def test_queue_row_does_not_repopulate_first_name_when_personalization_blocked(self) -> None:
        row = {
            "Email": "test@example.com",
            "first_name": "A",
            "first_name_clean": "",
            "personalization_allowed": "false",
            "FullName": "A Murray",
            "AuthorName": "A Murray",
            "author": "A Murray",
            "name": "A Murray",
        }

        queue_row = important_leads_workflow._master_row_to_queue_row(row, ["Email", "FirstName", "FullName"])

        self.assertEqual(queue_row["Email"], "test@example.com")
        self.assertEqual(queue_row["FirstName"], "")

    def test_queue_row_uses_clean_first_name_when_personalization_allowed(self) -> None:
        row = {
            "Email": "lisa@example.com",
            "first_name": ":Lisa",
            "first_name_clean": "Lisa",
            "personalization_allowed": "true",
        }

        queue_row = important_leads_workflow._master_row_to_queue_row(row, ["Email", "FirstName"])

        self.assertEqual(queue_row["Email"], "lisa@example.com")
        self.assertEqual(queue_row["FirstName"], "Lisa")

    def test_check_master_leads_reports_progress_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            progress: list[tuple[int, int]] = []

            input_path.write_text(
                "FullName,Email\nAlice,alice@example.com\nBob,bob@example.com\n",
                encoding="utf-8",
            )
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                report_dir=tmp / "reports",
                summary_dir=tmp / "check_runs",
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
                progress_callback=lambda processed, total: progress.append((processed, total)),
            )

            self.assertIn((1, 2), progress)
            self.assertEqual((2, 2), progress[-1])

    def test_check_master_leads_accepts_two_column_no_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "rejected.csv"
            report_dir = tmp / "reports"
            summary_dir = tmp / "check_runs"

            input_path.write_text(
                "Jane,jane@gmail.com\nJohn, JOHN@YAHOO.COM \n",
                encoding="utf-8",
            )

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                report_dir=report_dir,
                summary_dir=summary_dir,
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

            self.assertEqual(report["input_rows"], 2)
            self.assertEqual(report["cleaned_rows"], 2)
            with output_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(rows[0]["Email"], "jane@gmail.com")
            self.assertEqual(rows[1]["Email"], "john@yahoo.com")

    def test_check_master_leads_marks_undeliverable_domains(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            input_path = tmp / "leadschecker.csv"
            output_path = tmp / "leads.csv"
            rejected_path = tmp / "rejected.csv"
            report_dir = tmp / "reports"
            summary_dir = tmp / "check_runs"

            write_csv(
                input_path,
                ["FullName", "FirstName", "Email"],
                [{"FullName": "Test Person", "FirstName": "Test", "Email": "nobody@example.com"}],
            )

            report = check_master_leads(
                input_path=input_path,
                output_path=output_path,
                rejected_path=rejected_path,
                report_dir=report_dir,
                summary_dir=summary_dir,
                validate_deliverability=True,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

            self.assertEqual(report["cleaned_rows"], 0)
            self.assertEqual(report["undeliverable_removed"], 1)
            self.assertEqual(report["reason_counts"]["UNDELIVERABLE_DOMAIN"], 1)

    def test_fresh_cold_globally_blocks_prior_success_and_active_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email", "Source"],
                [
                    {"FullName": "Fresh Person", "FirstName": "Fresh", "Email": "fresh-both@example.com", "Source": "master"},
                    {"FullName": "Astra Sent Person", "FirstName": "Astra Sent", "Email": "astra-sent@example.com", "Source": "master"},
                    {"FullName": "SendGrid Sent Person", "FirstName": "SendGrid Sent", "Email": "sg-sent@example.com", "Source": "master"},
                    {"FullName": "Astra Queue Person", "FirstName": "Astra Queue", "Email": "queued-astra@example.com", "Source": "master"},
                    {"FullName": "SendGrid Queue Person", "FirstName": "SendGrid Queue", "Email": "queued-sg@example.com", "Source": "master"},
                    {"FullName": "Both Sent Person", "FirstName": "Both Sent", "Email": "both-sent@example.com", "Source": "master"},
                    {"FullName": "Both Queue Person", "FirstName": "Both Queue", "Email": "both-queued@example.com", "Source": "master"},
                    {"FullName": "Supp Person", "FirstName": "Supp", "Email": "suppressed@example.com", "Source": "master"},
                    {"FullName": "Fresh Duplicate Person", "FirstName": "Fresh Duplicate", "Email": "fresh-both@example.com", "Source": "dup"},
                ],
            )
            write_csv(
                jc_queue,
                ["Email", "FirstName"],
                [
                    {"Email": "queued-astra@example.com", "FirstName": "Queued Astra"},
                    {"Email": "both-queued@example.com", "FirstName": "Both Queue"},
                ],
            )
            write_csv(
                sg_queues[0],
                ["Email", "FirstName"],
                [{"Email": "queued-sg@example.com", "FirstName": "Queued SG"}],
            )
            write_csv(
                sg_queues[1],
                ["Email", "FirstName"],
                [{"Email": "both-queued@example.com", "FirstName": "Both Queue"}],
            )
            for path in sg_queues[2:]:
                write_csv(path, ["Email", "FirstName"], [])
            write_csv(
                logs[0],
                ["Email", "Status"],
                [
                    {"Email": "astra-sent@example.com", "Status": "SENT"},
                    {"Email": "both-sent@example.com", "Status": "SENT"},
                ],
            )
            write_csv(
                logs[1],
                ["Email", "Status", "SenderFrom"],
                [
                    {
                        "Email": "sg-sent@example.com",
                        "Status": "SENT",
                        "SenderFrom": "alisonaguiar@bnmarketing.us",
                    }
                ],
            )
            write_csv(
                logs[2],
                ["Email", "Status", "SenderFrom"],
                [
                    {
                        "Email": "both-sent@example.com",
                        "Status": "SENT",
                        "SenderFrom": "jordankendrick@bnmarketing.us",
                    }
                ],
            )
            for path in logs[3:]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@example.com"}])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])
            queue_bytes_before = {
                path: path.read_bytes()
                for path in (jc_queue, *sg_queues)
            }

            report = preview_dispatch_master_leads(
                master_path=master_path,
                rejected_path=rejected_path,
                dispatch_source_mode="cleaned",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=tmp / "previews",
            )

            planned = report["plan_rows_by_queue"]

            jc_emails = {
                row["Email"]
                for row in planned["private_jc"]
            }

            all_sg_emails = [
                row["Email"]
                for index in range(1, 6)
                for row in planned[f"sendgrid_{index}"]
            ]

            self.assertEqual({"fresh-both@example.com"}, jc_emails)

            self.assertEqual(
                len(all_sg_emails),
                len(set(all_sg_emails)),
            )
            self.assertEqual(set(), set(all_sg_emails))

            self.assertTrue(
                jc_emails.isdisjoint(all_sg_emails)
            )
            self.assertNotIn(
                "both-queued@example.com",
                jc_emails | set(all_sg_emails),
            )
            self.assertNotIn(
                "suppressed@example.com",
                jc_emails | set(all_sg_emails),
            )
            self.assertEqual(3, report["exclusion_reason_counts"]["already_sent"])
            self.assertEqual(3, report["exclusion_reason_counts"]["already_queued"])
            self.assertEqual(
                queue_bytes_before,
                {path: path.read_bytes() for path in (jc_queue, *sg_queues)},
            )

    def test_dispatch_master_leads_default_uses_triaged_keep_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            rejected_path = tmp / "leads_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [
                    {"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"},
                    {"FullName": "Triaged One Person", "FirstName": "Triaged", "Email": "triaged1@example.com"},
                    {"FullName": "Triaged Two Person", "FirstName": "Triaged", "Email": "triaged2@example.com"},
                ],
            )
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Triaged One Person", "FirstName": "Triaged", "Email": "triaged1@example.com", "Status": "KEEP"},
                    {"FullName": "Triaged Two Person", "FirstName": "Triaged", "Email": "triaged2@example.com", "Status": "KEEP"},
                ],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            report = dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                require_stopped=False,
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=False,
            )

            self.assertEqual("triaged_keep", report["dispatch_source_mode"])
            self.assertEqual("Fast Triage Keep", report["dispatch_source_name"])
            self.assertEqual(report["dispatch_source_row_count"], 2)
            self.assertEqual(report["dispatch_eligible_row_count"], 2)
            self.assertFalse(report["verification_required"])
            with jc_queue.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            all_rows = list(rows)
            for path in sg_queues:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    all_rows.extend(list(csv.DictReader(handle)))
            self.assertEqual({row["Email"] for row in all_rows}, {"triaged1@example.com", "triaged2@example.com"})
            self.assertEqual(len(all_rows), len({row["Email"].lower() for row in all_rows}))

    def test_dispatch_master_leads_triaged_keep_blocks_missing_selected_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "missing_triaged_keep.csv"
            rejected_path = tmp / "leads_rejected.csv"
            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [
                    {"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"},
                    {"FullName": "Verified One Person", "FirstName": "Verified", "Email": "verified1@example.com"},
                    {"FullName": "Verified Two Person", "FirstName": "Verified", "Email": "verified2@example.com"},
                    {"FullName": "Rejected Person", "FirstName": "Rejected", "Email": "rejected@example.com"},
                    {"FullName": "Quarantine Person", "FirstName": "Q", "Email": "quarantine@example.com"},
                ],
            )

            with self.assertRaisesRegex(ValueError, "Fast Triage Keep dispatch source missing"):
                dispatch_master_leads(
                    master_path=master_path,
                    triaged_keep_path=triaged_keep_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="triaged_keep",
                    require_stopped=False,
                    jc_queue_path=tmp / "recipients_private_jc.csv",
                    sendgrid_queue_paths=[tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)],
                    jc_log_path=tmp / "private_jc_log.csv",
                    sendgrid_log_paths=[tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)],
                    sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                    suppressed_path=tmp / "suppressed.csv",
                    unsubscribed_path=tmp / "unsubscribed.csv",
                    lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                    backup_root=tmp / "backups",
                    report_dir=tmp / "reports",
                    persist_state=False,
                )

    def test_dispatch_master_leads_verified_mode_uses_verified_keep_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [
                    {"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"},
                    {"FullName": "Verified One Person", "FirstName": "Verified", "Email": "verified1@example.com"},
                    {"FullName": "Verified Two Person", "FirstName": "Verified", "Email": "verified2@example.com"},
                    {"FullName": "Rejected Person", "FirstName": "Rejected", "Email": "rejected@example.com"},
                    {"FullName": "Quarantine Person", "FirstName": "Q", "Email": "quarantine@example.com"},
                ],
            )
            write_csv(
                verified_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Verified One Person", "FirstName": "Verified", "Email": "verified1@example.com", "Status": "KEEP"},
                    {"FullName": "Verified Two Person", "FirstName": "Verified", "Email": "verified2@example.com", "Status": "KEEP"},
                    {"FullName": "Rejected Person", "FirstName": "Rejected", "Email": "rejected@example.com", "Status": "REJECT"},
                    {"FullName": "Quarantine Person", "FirstName": "Q", "Email": "quarantine@example.com", "Status": "QUARANTINE"},
                ],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            report = dispatch_master_leads(
                master_path=master_path,
                verified_path=verified_path,
                rejected_path=rejected_path,
                dispatch_source_mode="strict_verified",
                require_stopped=False,
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=False,
            )

            self.assertEqual(report["dispatch_source_mode"], "strict_verified")
            self.assertEqual(report["master_read"], 4)
            self.assertEqual(report["dispatch_source_row_count"], 4)
            self.assertEqual(report["dispatch_eligible_row_count"], 2)
            self.assertTrue(report["verification_required"])
            self.assertEqual(report["added_astra"], 1)
            self.assertEqual(report["added_sendgrid"], 1)
            with jc_queue.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            all_rows = list(rows)
            for path in sg_queues:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    all_rows.extend(list(csv.DictReader(handle)))
            self.assertEqual({row["Email"] for row in all_rows}, {"verified1@example.com", "verified2@example.com"})
            self.assertEqual(len(all_rows), len({row["Email"].lower() for row in all_rows}))

    def test_dispatch_master_leads_verified_mode_blocks_without_keep_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(
                verified_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Rejected Person", "FirstName": "Rejected", "Email": "rejected@example.com", "Status": "REJECT"},
                    {"FullName": "Quarantine Person", "FirstName": "Quarantine", "Email": "quarantine@example.com", "Status": "QUARANTINE"},
                ],
            )
            write_csv(tmp / "recipients_private_jc.csv", ["Email", "FirstName"], [])
            for path in [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]:
                write_csv(path, ["Email", "FirstName"], [])
            for path in [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            with self.assertRaisesRegex(ValueError, "no KEEP rows"):
                dispatch_master_leads(
                    master_path=master_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="strict_verified",
                    require_stopped=False,
                    jc_queue_path=tmp / "recipients_private_jc.csv",
                    sendgrid_queue_paths=[tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)],
                    jc_log_path=tmp / "private_jc_log.csv",
                    sendgrid_log_paths=[tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)],
                    sendgrid_suppressions_path=sendgrid_suppressions_path,
                    suppressed_path=suppressed_path,
                    unsubscribed_path=unsubscribed_path,
                    lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                    backup_root=backup_root,
                    report_dir=report_dir,
                    persist_state=False,
                )

    def test_dispatch_master_leads_verified_mode_blocks_header_only_verified_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "leads_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(verified_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            with self.assertRaisesRegex(ValueError, "Strict Public Proof Verified dispatch source is empty"):
                dispatch_master_leads(
                    master_path=master_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="strict_verified",
                    require_stopped=False,
                    jc_queue_path=jc_queue,
                    sendgrid_queue_paths=sg_queues,
                    jc_log_path=logs[0],
                    sendgrid_log_paths=logs[1:],
                    sendgrid_suppressions_path=sendgrid_suppressions_path,
                    suppressed_path=suppressed_path,
                    unsubscribed_path=unsubscribed_path,
                    lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                    backup_root=backup_root,
                    report_dir=report_dir,
                    persist_state=False,
                )

    def test_dispatch_master_leads_verified_mode_blocks_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            verified_path = tmp / "missing_verified.csv"
            rejected_path = tmp / "leads_verify_rejected.csv"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [{"FullName": "Ignored Person", "FirstName": "Ignored", "Email": "ignored@example.com"}])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            with self.assertRaisesRegex(ValueError, "Strict Public Proof Verified dispatch source missing"):
                dispatch_master_leads(
                    master_path=master_path,
                    verified_path=verified_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="strict_verified",
                    require_stopped=False,
                    jc_queue_path=jc_queue,
                    sendgrid_queue_paths=sg_queues,
                    jc_log_path=logs[0],
                    sendgrid_log_paths=logs[1:],
                    sendgrid_suppressions_path=sendgrid_suppressions_path,
                    suppressed_path=suppressed_path,
                    unsubscribed_path=unsubscribed_path,
                    lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                    backup_root=backup_root,
                    report_dir=report_dir,
                    persist_state=False,
                )

    def test_preview_dispatch_master_leads_computes_counts_without_writing_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [
                    {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com"},
                    {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com"},
                    {"FullName": "Gamma Person", "FirstName": "Gamma", "Email": "gamma@example.com"},
                ],
            )
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Fresh Person", "FirstName": "Fresh", "Email": "fresh@example.com", "Status": "KEEP"},
                    {"FullName": "Sent Person", "FirstName": "Sent", "Email": "sent@example.com", "Status": "KEEP"},
                    {"FullName": "Queued Person", "FirstName": "Queued", "Email": "queued@example.com", "Status": "KEEP"},
                    {"FullName": "Supp Person", "FirstName": "Supp", "Email": "supp@example.com", "Status": "KEEP"},
                    {"FullName": "Bad Person", "FirstName": "Bad", "Email": "bad-email", "Status": "KEEP"},
                ],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [{"Email": "queued@example.com", "FirstName": "Queued"}])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            write_csv(logs[0], ["Email", "Status"], [{"Email": "sent@example.com", "Status": "SENT"}])
            for path in logs[1:]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [{"Email": "supp@example.com"}])
            write_csv(unsubscribed_path, ["Email"], [])
            write_csv(sendgrid_suppressions_path, ["email", "state", "type"], [])

            jc_before = jc_queue.read_text(encoding="utf-8")
            sg_before = [path.read_text(encoding="utf-8") for path in sg_queues]

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            self.assertEqual("triaged_keep", preview["active_source_key"])
            self.assertEqual("Fast Triage Keep", preview["source_label"])
            self.assertEqual(str(triaged_keep_path), preview["source_path"])
            self.assertEqual(str(triaged_keep_path), preview["source_file_path"])
            self.assertEqual(5, preview["source_row_count"])
            self.assertEqual(5, preview["total_source_rows"])
            self.assertEqual(5, preview["eligible_rows"])
            self.assertEqual(1, preview["skipped_already_sent"])
            self.assertEqual(1, preview["skipped_already_queued"])
            self.assertEqual(1, preview["skipped_suppressed"])
            self.assertEqual(1, preview["skipped_invalid_malformed"])
            self.assertEqual(1, preview["rows_to_add_private_jc"])
            self.assertEqual(
                {"sendgrid_1": 0, "sendgrid_2": 0, "sendgrid_3": 0, "sendgrid_4": 0, "sendgrid_5": 0},
                preview["rows_to_add_sendgrid_shards"],
            )
            self.assertEqual("cold", preview["campaign_type"])
            self.assertEqual("triaged_keep", preview["dispatch_source_mode"])
            self.assertIs(True, preview["dispatch_source_exists"])
            self.assertEqual(1, preview["private_jc_planned_count"])
            self.assertEqual(0, preview["sendgrid_planned_count"])
            self.assertEqual(1, preview["total_planned_unique_count"])
            self.assertEqual(0, preview["duplicate_planned_email_count"])
            self.assertEqual(1, preview["total_rows_that_would_be_written"])
            self.assertEqual(preview["skipped_rows"], sum(preview["exclusion_reason_counts"].values()))
            preview_path = preview_dir / f"{preview['preview_id']}.json"
            self.assertTrue(preview_path.exists())
            persisted_preview = json.loads(preview_path.read_text(encoding="utf-8"))
            self.assertIs(True, persisted_preview["dispatch_source_exists"])
            self.assertEqual(jc_before, jc_queue.read_text(encoding="utf-8"))
            self.assertEqual(sg_before, [path.read_text(encoding="utf-8") for path in sg_queues])

    def test_preview_dispatch_master_leads_skips_rows_missing_required_dispatch_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            required_headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle", "Status"]
            write_csv(master_path, required_headers, [])
            write_csv(
                triaged_keep_path,
                required_headers,
                [
                    {
                        "Email": "ready@example.com",
                        "FirstName": "Ready",
                        "AuthorEmail": "ready@example.com",
                        "AuthorName": "Ready Author",
                        "BookTitle": "Ready Book",
                        "Status": "KEEP",
                    },
                    {
                        "Email": "missing-first@example.com",
                        "FirstName": "",
                        "AuthorEmail": "missing-first@example.com",
                        "AuthorName": "Missing Author",
                        "BookTitle": "Missing Book",
                        "Status": "KEEP",
                    },
                ],
            )
            write_csv(jc_queue, ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=tmp / "previews",
            )

            planned_emails = {
                row["Email"]
                for rows in preview["plan_rows_by_queue"].values()
                for row in rows
            }
            self.assertEqual({"ready@example.com"}, planned_emails)
            self.assertEqual(1, preview["exclusion_reason_counts"]["missing_required_dispatch_field"])
            self.assertEqual(1, preview["total_planned_unique_count"])

    def test_fresh_cold_preview_allocates_to_sendgrid_without_writing_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            rows = [
                {"FullName": f"Fresh Person {idx}", "FirstName": f"Fresh{idx}", "Email": f"fresh{idx}@example.com", "Status": "KEEP"}
                for idx in range(1, 7)
            ]
            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [{key: row[key] for key in ["FullName", "FirstName", "Email"]} for row in rows],
            )
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            queue_before = {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]}

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                campaign_type="cold",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            self.assertGreater(preview["rows_to_add_private_jc"], 0)
            self.assertGreater(preview["rows_to_add_sendgrid"], 0)
            self.assertEqual(preview["rows_to_add_sendgrid"], sum(preview["rows_to_add_sendgrid_shards"].values()))
            self.assertEqual(0, preview["duplicate_planned_email_count"])
            self.assertEqual("", preview["sendgrid_zero_reason"])
            archived_preview = json.loads(Path(preview["assigned_preview_archive_path"]).read_text(encoding="utf-8"))
            self.assertEqual(preview["sendgrid_shard_planned_counts"], archived_preview["sendgrid_shard_planned_counts"])
            self.assertEqual("", archived_preview["sendgrid_zero_reason"])
            self.assertEqual(preview["rows_to_add_sendgrid"], archived_preview["rows_to_add_sendgrid"])

            planned_email_routes: dict[str, str] = {}
            for route, planned_rows in preview["plan_rows_by_queue"].items():
                for row in planned_rows:
                    email = row["Email"].lower()
                    self.assertNotIn(email, planned_email_routes)
                    planned_email_routes[email] = route
            self.assertEqual(preview["total_planned_unique_count"], len(planned_email_routes))
            self.assertEqual(queue_before, {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]})
            self.assertEqual([], read_csv_rows(jc_queue))
            for path in sg_queues:
                self.assertEqual([], read_csv_rows(path))

    def test_active_sendgrid_queue_membership_blocks_all_fresh_cold_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            rows = [
                {"FullName": f"Fresh Person {idx}", "FirstName": f"Fresh{idx}", "Email": f"fresh{idx}@example.com", "Status": "KEEP"}
                for idx in range(1, 5)
            ]
            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [{key: row[key] for key in ["FullName", "FirstName", "Email"]} for row in rows],
            )
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [{"Email": row["Email"], "FirstName": row["FirstName"]} for row in rows])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                campaign_type="cold",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            self.assertEqual(0, preview["rows_to_add_sendgrid"])
            self.assertEqual(0, preview["rows_to_add_private_jc"])
            self.assertEqual(0, preview["duplicate_planned_email_count"])
            self.assertEqual(len(rows), preview["exclusion_reason_counts"]["already_queued"])

    def test_confirm_dispatch_preview_writes_exact_previewed_rows_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            rejected_path = tmp / "leads_rejected.csv"
            triaged_reject_path = tmp / "leads_triaged_reject.csv"
            triaged_quarantine_path = tmp / "leads_triaged_quarantine.csv"

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [
                    {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com"},
                    {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com"},
                    {"FullName": "Gamma Person", "FirstName": "Gamma", "Email": "gamma@example.com"},
                ],
            )
            write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"},
                    {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com", "Status": "KEEP"},
                    {"FullName": "Gamma Person", "FirstName": "Gamma", "Email": "gamma@example.com", "Status": "KEEP"},
                ],
            )
            write_csv(triaged_reject_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(triaged_quarantine_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                preview_dir=preview_dir,
            )

            report = confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=False,
                preview_dir=preview_dir,
            )

            confirmed_preview = load_dispatch_preview(preview["preview_id"], preview_dir=preview_dir)
            self.assertEqual("confirmed", confirmed_preview["status"])
            self.assertEqual(report["run_id"], confirmed_preview["confirmed_run_id"])
            self.assertEqual("completed", report["status"])
            self.assertEqual(preview["total_rows_that_would_be_written"], report["total_rows_that_would_be_written"])
            self.assertEqual(preview["rows_to_add_sendgrid_shards"], report["rows_written_sendgrid_shards"])
            self.assertEqual(preview["rows_to_add_private_jc"], report["rows_written_private_jc"])
            self.assertEqual(
                "Dispatch confirmed. Staged batch archived and cleared. Run Check Leads and Fast Triage before previewing another batch.",
                report["message"],
            )
            cleanup = report["staged_batch_cleanup"]
            self.assertTrue(cleanup["archived"])
            self.assertTrue(cleanup["cleared"])
            archive_path = Path(cleanup["archive_path"])
            self.assertTrue(archive_path.exists())
            self.assertTrue((archive_path / "metadata.json").exists())
            self.assertTrue((archive_path / master_path.name).exists())
            self.assertTrue((archive_path / rejected_path.name).exists())
            self.assertTrue((archive_path / triaged_keep_path.name).exists())
            self.assertTrue((archive_path / triaged_reject_path.name).exists())
            self.assertTrue((archive_path / triaged_quarantine_path.name).exists())
            self.assertFalse(master_path.exists())
            self.assertFalse(rejected_path.exists())
            self.assertFalse(triaged_keep_path.exists())
            self.assertFalse(triaged_reject_path.exists())
            self.assertFalse(triaged_quarantine_path.exists())

            with jc_queue.open(newline="", encoding="utf-8-sig") as handle:
                jc_rows = list(csv.DictReader(handle))
            self.assertEqual(preview["plan_rows_by_queue"]["private_jc"], jc_rows)
            for index, path in enumerate(sg_queues, start=1):
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    rows = list(csv.DictReader(handle))
                expected_rows = preview["plan_rows_by_queue"][f"sendgrid_{index}"]
                self.assertEqual(expected_rows, rows)

            history_path = report_dir / important_leads_workflow.DISPATCH_RUN_HISTORY_PATH.name
            history = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual(report["run_id"], history[0]["run_id"])
            self.assertEqual("triaged_keep", history[0]["source_key"])
            self.assertEqual("Fast Triage Keep", history[0]["source_label"])
            self.assertEqual("completed", history[0]["status"])
            self.assertTrue(Path(report["report_path"]).exists())
            self.assertEqual(3, report["dispatch_history_rows_created"])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                alpha_id = lead_ledger.deterministic_lead_id("alpha@example.com")
                beta_id = lead_ledger.deterministic_lead_id("beta@example.com")
                gamma_id = lead_ledger.deterministic_lead_id("gamma@example.com")
                self.assertEqual(1, len(lead_ledger.load_dispatch_events(conn, alpha_id)))
                self.assertEqual(1, len(lead_ledger.load_dispatch_events(conn, beta_id)))
                self.assertEqual(1, len(lead_ledger.load_dispatch_events(conn, gamma_id)))
                alpha = lead_ledger.load_lead_by_id(conn, alpha_id)
                self.assertEqual(1, alpha["dispatch_count"])
                self.assertTrue(alpha["last_dispatch_at"])
                expected_alpha_profile = next(
                    key
                    for key, rows in preview["plan_rows_by_queue"].items()
                    if any(
                        row["Email"] == "alpha@example.com"
                        for row in rows
                    )
                )
                self.assertEqual(
                    expected_alpha_profile,
                    alpha["last_profile"],
                )
            finally:
                conn.close()

    def test_fresh_cold_campaign_blocks_successful_sendgrid_history_globally(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            rejected_path = tmp / "leads_rejected.csv"
            triaged_reject_path = tmp / "leads_triaged_reject.csv"
            triaged_quarantine_path = tmp / "leads_triaged_quarantine.csv"
            rows = [
                {
                    "FullName": "Alpha Person",
                    "FirstName": "Alpha",
                    "Email": "alpha@example.com",
                    "AuthorEmail": "alpha@example.com",
                    "AuthorName": "Alpha Person",
                    "BookTitle": "Alpha Book",
                    "Status": "KEEP",
                },
                {
                    "FullName": "Beta Person",
                    "FirstName": "Beta",
                    "Email": "beta@example.com",
                    "AuthorEmail": "beta@example.com",
                    "AuthorName": "Beta Person",
                    "BookTitle": "Beta Book",
                    "Status": "KEEP",
                },
            ]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle"],
                [
                    {key: row[key] for key in ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle"]}
                    for row in rows
                ],
            )
            write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle", "Status"],
                rows,
            )
            write_csv(triaged_reject_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(triaged_quarantine_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(
                logs[1],
                ["Email", "Status"],
                [
                    {"Email": "alpha@example.com", "Status": "SENT"},
                    {"Email": "beta@example.com", "Status": "SENT"},
                ],
            )

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                preview_dir=preview_dir,
            )
            self.assertEqual(0, preview["rows_to_add_sendgrid"])
            self.assertEqual(0, preview["rows_to_add_private_jc"])
            self.assertEqual(2, preview["skipped_already_sent"])
            self.assertEqual(2, preview["skipped_rows"])
            self.assertEqual({"already_sent": 2}, preview["exclusion_reason_counts"])
            self.assertEqual(preview["skipped_rows"], sum(preview["exclusion_reason_counts"].values()))
            sendgrid_emails = [
                row["Email"]
                for queue_name in ("sendgrid_1", "sendgrid_2", "sendgrid_3", "sendgrid_4", "sendgrid_5")
                for row in preview["plan_rows_by_queue"][queue_name]
            ]
            self.assertEqual([], sendgrid_emails)
            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                alpha_id = lead_ledger.deterministic_lead_id("alpha@example.com")
                beta_id = lead_ledger.deterministic_lead_id("beta@example.com")
                self.assertEqual([], lead_ledger.load_dispatch_events(conn, alpha_id))
                self.assertEqual([], lead_ledger.load_dispatch_events(conn, beta_id))
            finally:
                conn.close()

    def test_recontact_cold_preview_allows_good_history_and_blocks_bad_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            sendgrid_events_path = tmp / "sendgrid_events.jsonl"
            suppressed_path = tmp / "suppressed.csv"
            unsubscribed_path = tmp / "unsubscribed.csv"
            sendgrid_suppressions_path = tmp / "sendgrid_suppressions.csv"
            headers = ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle", "Status"]
            rows = [
                {"FullName": "Sent Person", "FirstName": "Sent", "Email": "sent@example.com", "AuthorEmail": "sent@example.com", "AuthorName": "Sent Person", "BookTitle": "Sent Book", "Status": "KEEP"},
                {"FullName": "Contacted Person", "FirstName": "Contacted", "Email": "contacted@example.com", "AuthorEmail": "contacted@example.com", "AuthorName": "Contacted Person", "BookTitle": "Contacted Book", "Status": "KEEP"},
                {"FullName": "", "FirstName": "", "Email": "fresh@example.com", "AuthorEmail": "fresh@example.com", "AuthorName": "", "BookTitle": "", "Status": "KEEP"},
                {"FullName": "Sent Again", "FirstName": "Sent", "Email": "sent@example.com", "AuthorEmail": "sent@example.com", "AuthorName": "Sent Person", "BookTitle": "Sent Book", "Status": "KEEP"},
                {"FullName": "Bad Email", "FirstName": "Bad", "Email": "bad-email", "AuthorEmail": "bad-email", "AuthorName": "Bad Email", "BookTitle": "Bad Book", "Status": "KEEP"},
                {"FullName": "Bounce Person", "FirstName": "Bounce", "Email": "bounce@example.com", "AuthorEmail": "bounce@example.com", "AuthorName": "Bounce Person", "BookTitle": "Bounce Book", "Status": "KEEP"},
                {"FullName": "Spam Person", "FirstName": "Spam", "Email": "spam@example.com", "AuthorEmail": "spam@example.com", "AuthorName": "Spam Person", "BookTitle": "Spam Book", "Status": "KEEP"},
                {"FullName": "Group Person", "FirstName": "Group", "Email": "group@example.com", "AuthorEmail": "group@example.com", "AuthorName": "Group Person", "BookTitle": "Group Book", "Status": "KEEP"},
                {"FullName": "Unsub Event", "FirstName": "Unsub", "Email": "unsub-event@example.com", "AuthorEmail": "unsub-event@example.com", "AuthorName": "Unsub Event", "BookTitle": "Unsub Book", "Status": "KEEP"},
                {"FullName": "Dropped Person", "FirstName": "Dropped", "Email": "dropped@example.com", "AuthorEmail": "dropped@example.com", "AuthorName": "Dropped Person", "BookTitle": "Dropped Book", "Status": "KEEP"},
                {"FullName": "Invalid Event", "FirstName": "Invalid", "Email": "invalid-event@example.com", "AuthorEmail": "invalid-event@example.com", "AuthorName": "Invalid Event", "BookTitle": "Invalid Book", "Status": "KEEP"},
                {"FullName": "Suppressed Person", "FirstName": "Supp", "Email": "suppressed@example.com", "AuthorEmail": "suppressed@example.com", "AuthorName": "Suppressed Person", "BookTitle": "Supp Book", "Status": "KEEP"},
                {"FullName": "Sg Suppressed", "FirstName": "Sg", "Email": "sgsuppressed@example.com", "AuthorEmail": "sgsuppressed@example.com", "AuthorName": "Sg Suppressed", "BookTitle": "Sg Supp Book", "Status": "KEEP"},
                {"FullName": "Unsubscribed Person", "FirstName": "Unsubscribed", "Email": "unsubscribed@example.com", "AuthorEmail": "unsubscribed@example.com", "AuthorName": "Unsubscribed Person", "BookTitle": "Unsubscribed Book", "Status": "KEEP"},
            ]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle"],
                [
                    {key: row[key] for key in ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle"]}
                    for row in rows
                ],
            )
            write_csv(triaged_keep_path, headers, rows)
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            write_csv(logs[0], ["Email", "Status"], [])
            write_csv(
                logs[1],
                ["Email", "Status", "SenderFrom"],
                [
                    {
                        "Email": "sent@example.com",
                        "Status": "SENT",
                        "SenderFrom": "jodihorowitz@bnmarketing.us",
                    },
                    {
                        "Email": "invalid-event@example.com",
                        "Status": "INVALID",
                        "SenderFrom": "jodihorowitz@bnmarketing.us",
                    },
                ],
            )
            for path in logs[2:]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(suppressed_path, ["Email"], [{"Email": "suppressed@example.com"}])
            write_csv(unsubscribed_path, ["Email"], [{"Email": "unsubscribed@example.com"}])
            write_csv(
                sendgrid_suppressions_path,
                ["email", "status", "code", "reason", "last_seen_utc", "is_permanent", "ttl_until_utc"],
                [
                    {
                        "email": "sgsuppressed@example.com",
                        "status": "bounce",
                        "code": "550",
                        "reason": "suppressed",
                        "last_seen_utc": "2026-04-12T00:00:00+00:00",
                        "is_permanent": "true",
                        "ttl_until_utc": "",
                    }
                ],
            )
            sendgrid_events_path.write_text(
                "\n".join(
                    json.dumps({"email": email, "event": event})
                    for email, event in [
                        ("bounce@example.com", "bounce"),
                        ("spam@example.com", "spamreport"),
                        ("group@example.com", "group_unsubscribe"),
                        ("unsub-event@example.com", "unsubscribe"),
                        ("dropped@example.com", "dropped"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                contacted = lead_ledger.upsert_lead(conn, email="contacted@example.com")
                lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=contacted["lead_id"],
                    run_id="dispatch_run_prior",
                    dispatch_source="triaged_keep",
                    profile="sendgrid_1",
                    queue_target="sendgrid_1",
                    result_status="delivered",
                    dispatched_at="2026-04-11T05:00:00+00:00",
                )
            finally:
                conn.close()

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions_path,
                suppressed_path=suppressed_path,
                unsubscribed_path=unsubscribed_path,
                lead_ledger_db_path=ledger_db_path,
                sendgrid_events_path=sendgrid_events_path,
                campaign_type="recontact_cold",
                preview_dir=tmp / "previews",
            )

            self.assertEqual("recontact_cold", preview["campaign_type"])
            self.assertTrue(preview["allow_previously_sent"])
            self.assertEqual(14, preview["input_rows"])
            self.assertEqual(13, preview["rows_with_booktitle"])
            self.assertEqual(1, preview["rows_missing_booktitle"])
            self.assertEqual(13, preview["rows_with_author_name"])
            self.assertEqual(1, preview["rows_missing_author_name"])
            self.assertEqual(1, preview["previously_sent_allowed_count"])
            self.assertEqual(1, preview["already_contacted_allowed_count"])
            self.assertEqual(0, preview["skipped_already_sent"])
            self.assertEqual(0, preview["skipped_already_contacted"])
            self.assertEqual(6, preview["skipped_bad_sendgrid_event"])
            self.assertEqual(3, preview["skipped_suppressed"])
            self.assertEqual(1, preview["duplicate_master_skipped"])
            self.assertEqual(2, preview["invalid_malformed_skipped"])
            self.assertEqual(1, preview["exclusion_reason_counts"]["missing_required_dispatch_field"])
            self.assertEqual(9, preview["bad_suppressed_removed_count"])
            self.assertEqual(0, preview["rows_to_add_private_jc"])
            self.assertEqual(2, preview["rows_to_add_sendgrid"])
            self.assertEqual(2, preview["total_rows_would_write"])
            self.assertIn("campaign_type", preview["queue_headers"])
            self.assertIn("campaign_id", preview["queue_headers"])
            self.assertEqual(preview["preview_id"], preview["campaign_id"])
            self.assertEqual([], preview["plan_rows_by_queue"]["private_jc"])
            planned_emails = [
                row["Email"]
                for rows_by_queue in preview["plan_rows_by_queue"].values()
                for row in rows_by_queue
            ]
            self.assertEqual(1, planned_emails.count("sent@example.com"))
            self.assertEqual(1, planned_emails.count("contacted@example.com"))
            self.assertNotIn("fresh@example.com", planned_emails)
            self.assertNotIn("bounce@example.com", planned_emails)
            for rows_by_queue in preview["plan_rows_by_queue"].values():
                for row in rows_by_queue:
                    self.assertEqual("recontact_cold", row["campaign_type"])
                    self.assertEqual(preview["campaign_id"], row["campaign_id"])

    def test_recontact_preview_counts_history_without_confirmation_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            rejected_path = tmp / "leads_rejected.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            rows = [
                {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"},
                {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com", "Status": "KEEP"},
                {"FullName": "Gamma Person", "FirstName": "Gamma", "Email": "gamma@example.com", "Status": "KEEP"},
            ]
            write_csv(master_path, ["FullName", "FirstName", "Email"], [{key: row[key] for key in ["FullName", "FirstName", "Email"]} for row in rows])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
            write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])
            write_csv(tmp / "suppressed.csv", ["Email"], [])
            write_csv(tmp / "unsubscribed.csv", ["Email"], [])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                month_seen = datetime.now(timezone.utc).replace(day=2, hour=12, minute=0, second=0, microsecond=0).isoformat()
                for email, timestamp in [
                    ("alpha@example.com", month_seen),
                    ("beta@example.com", "2020-01-10T12:00:00+00:00"),
                ]:
                    lead = lead_ledger.upsert_lead(conn, email=email)
                    lead_ledger.record_dispatch_event(
                        conn,
                        lead_id=lead["lead_id"],
                        run_id="prior_dispatch",
                        dispatch_source="triaged_keep",
                        profile="private_jc",
                        queue_target="private_jc",
                        result_status="delivered",
                        dispatched_at=timestamp,
                    )
            finally:
                conn.close()

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                campaign_type="recontact_cold",
                preview_dir=preview_dir,
            )

            self.assertEqual(3, preview["recontact_planned_unique"])
            self.assertEqual(2, preview["recontact_found_in_active_history"])
            self.assertEqual(1, preview["recontact_seen_this_month"])
            self.assertEqual(1, preview["recontact_not_found_in_active_history"])
            self.assertTrue(preview["recontact_recency_high_risk"])
            self.assertEqual("red", preview["recontact_recency_risk_level"])
            self.assertEqual("red", preview["recontact_recency"]["risk_level"])
            self.assertEqual("Not recommended: most leads were contacted recently.", preview["recontact_recency_warning"])

            confirmed = confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=tmp / "backups",
                report_dir=tmp / "reports",
                persist_state=False,
                preview_dir=preview_dir,
            )
            self.assertEqual("recontact_cold", confirmed["campaign_type"])
            self.assertEqual(preview["campaign_id"], confirmed["campaign_id"])
            self.assertEqual(3, confirmed["total_rows_would_write"])
            self.assertEqual(0, confirmed["rows_written_private_jc"])
            final_rows = [row for path in sg_queues for row in read_csv_rows(path)]
            self.assertEqual(3, len(final_rows))
            self.assertEqual({preview["campaign_id"]}, {row["campaign_id"] for row in final_rows})

    def test_safer_recontact_pool_writes_separate_csv_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "runs" / "check_test" / "leads.csv"
            triaged_keep_path = tmp / "runs" / "check_test" / "leads_triaged_keep.csv"
            rejected_path = tmp / "runs" / "check_test" / "leads_rejected.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            preview_dir = tmp / "previews"
            state_dir = tmp / "state"
            logs_dir = tmp / "logs"
            summary_path = state_dir / "safer_recontact_source_summary.json"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            rows = [
                {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "BookTitle": "Alpha Book", "Status": "KEEP"},
                {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com", "BookTitle": "Beta Book", "Status": "KEEP"},
                {"FullName": "Gamma Person", "FirstName": "Gamma", "Email": "gamma@example.com", "BookTitle": "Gamma Book", "Status": "KEEP"},
            ]
            write_csv(master_path, ["FullName", "FirstName", "Email", "BookTitle"], [{key: row[key] for key in ["FullName", "FirstName", "Email", "BookTitle"]} for row in rows])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "BookTitle", "Status"], rows)
            write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
            write_csv(jc_queue, ["Email", "FirstName", "BookTitle"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName", "BookTitle"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])
            write_csv(tmp / "suppressed.csv", ["Email"], [])
            write_csv(tmp / "unsubscribed.csv", ["Email"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="cleaned",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                campaign_type="recontact_cold",
                preview_dir=preview_dir,
            )

            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            state_dir.mkdir(parents=True)
            logs_dir.mkdir(parents=True)
            write_csv(
                logs_dir / "sendgrid_local_log.csv",
                ["Email", "Status", "created_at_utc"],
                [
                    {"Email": "alpha@example.com", "Status": "SENT", "created_at_utc": f"{current_month}-02T12:00:00+00:00"},
                    {"Email": "beta@example.com", "Status": "SENT", "created_at_utc": "2020-01-02T12:00:00+00:00"},
                ],
            )
            (state_dir / "dispatch_run_history.json").write_text(
                json.dumps(
                    [
                        {"email": "alpha@example.com", "dispatched_at": f"{current_month}-02T12:00:00+00:00"},
                        {"email": "beta@example.com", "dispatched_at": "2020-01-02T12:00:00+00:00"},
                    ]
                ),
                encoding="utf-8",
            )

            summary = create_safer_recontact_pool_from_preview(
                preview["preview_id"],
                preview_dir=preview_dir,
                summary_path=summary_path,
                logs_dir=logs_dir,
                state_dir=state_dir,
            )

            output_path = Path(str(summary["output_path"]))
            self.assertTrue(output_path.exists())
            headers, safer_rows = important_leads_workflow._read_csv_rows(output_path)
            self.assertIn("Email", headers)
            self.assertEqual(1, len(safer_rows))
            self.assertEqual("gamma@example.com", safer_rows[0]["Email"])
            self.assertEqual(3, summary["planned_unique"])
            self.assertEqual(2, summary["found_in_active_history"])
            self.assertEqual(1, summary["seen_this_month"])
            self.assertEqual(1, summary["not_found_in_active_history"])
            self.assertEqual(1, summary["safer_rows_written"])
            self.assertEqual(0, summary["safer_found_in_active_history"])
            self.assertTrue(summary_path.exists())
            self.assertEqual(master_path, tmp / "runs" / "check_test" / "leads.csv")
            self.assertNotEqual(output_path, master_path)

    def test_confirm_dispatch_preview_allows_sendgrid_already_sent_for_recontact_cold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            report_dir = tmp / "reports"
            backup_root = tmp / "backups"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            rejected_path = tmp / "leads_rejected.csv"
            triaged_reject_path = tmp / "leads_triaged_reject.csv"
            triaged_quarantine_path = tmp / "leads_triaged_quarantine.csv"
            rows = [
                {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "AuthorEmail": "alpha@example.com", "AuthorName": "Alpha Person", "BookTitle": "Alpha Book", "Status": "KEEP"},
                {"FullName": "Beta Person", "FirstName": "Beta", "Email": "beta@example.com", "AuthorEmail": "beta@example.com", "AuthorName": "Beta Person", "BookTitle": "Beta Book", "Status": "KEEP"},
            ]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle"],
                [
                    {key: row[key] for key in ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle"]}
                    for row in rows
                ],
            )
            write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "AuthorEmail", "AuthorName", "BookTitle", "Status"], rows)
            write_csv(triaged_reject_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(triaged_quarantine_path, ["FullName", "FirstName", "Email", "Status"], [])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            write_csv(
                logs[1],
                ["Email", "Status"],
                [
                    {"Email": "alpha@example.com", "Status": "SENT"},
                    {"Email": "beta@example.com", "Status": "SENT"},
                ],
            )

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                campaign_type="recontact_cold",
                preview_dir=preview_dir,
            )
            self.assertEqual(2, preview["rows_to_add_sendgrid"])
            self.assertEqual(0, preview["rows_to_add_private_jc"])

            report = confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=False,
                preview_dir=preview_dir,
            )

            self.assertEqual("completed", report["status"])
            self.assertEqual("recontact_cold", report["campaign_type"])
            self.assertEqual(0, report["confirm_filtered_sendgrid_already_sent"])
            self.assertEqual(2, sum(report["rows_written_sendgrid_shards"].values()))
            self.assertEqual(0, report["rows_written_private_jc"])
            self.assertEqual(2, report["total_rows_would_write"])
            with jc_queue.open(newline="", encoding="utf-8-sig") as handle:
                self.assertEqual([], [row["Email"] for row in csv.DictReader(handle)])
            sendgrid_emails: list[str] = []
            sendgrid_campaign_ids: set[str] = set()
            for path in sg_queues:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    rows_from_queue = list(csv.DictReader(handle))
                    sendgrid_emails.extend(row["Email"] for row in rows_from_queue)
                    sendgrid_campaign_ids.update(row["campaign_id"] for row in rows_from_queue)
            self.assertEqual(["alpha@example.com", "beta@example.com"], sendgrid_emails)
            self.assertEqual({preview["campaign_id"]}, sendgrid_campaign_ids)

    def test_confirm_dispatch_preview_failure_preserves_staged_files_and_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            rejected_path = tmp / "leads_rejected.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            backup_root = tmp / "backups"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(
                master_path,
                ["FullName", "FirstName", "Email"],
                [{"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com"}],
            )
            write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [{"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"}],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            staged_before = {path: path.read_text(encoding="utf-8") for path in [master_path, rejected_path, triaged_keep_path]}
            queue_before = {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]}

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            with patch.object(important_leads_workflow, "_record_dispatch_history_from_preview", side_effect=RuntimeError("ledger failed")):
                with self.assertRaisesRegex(RuntimeError, "ledger failed"):
                    confirm_dispatch_preview(
                        preview["preview_id"],
                        require_stopped=False,
                        backup_root=backup_root,
                        report_dir=tmp / "reports",
                        persist_state=False,
                        preview_dir=preview_dir,
                    )

            self.assertFalse((backup_root / "staged_batches").exists())
            for path, content in staged_before.items():
                self.assertTrue(path.exists())
                self.assertEqual(content, path.read_text(encoding="utf-8"))
            for path, content in queue_before.items():
                self.assertEqual(content, path.read_text(encoding="utf-8"))

    def test_confirm_dispatch_preview_is_transactional_across_queues_and_records(self) -> None:
        fault_phases = [
            "before_first_replacement",
            *[f"queue_replacement_{position}" for position in range(1, 7)],
            "after_sixth_replacement",
            "ledger_recording",
            "campaign_history_recording",
            "final_confirmation_state",
        ]

        for fault_phase in fault_phases:
            with self.subTest(fault_phase=fault_phase), tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                master_path = tmp / "leads.csv"
                rejected_path = tmp / "leads_rejected.csv"
                triaged_keep_path = tmp / "leads_triaged_keep.csv"
                triaged_reject_path = tmp / "leads_triaged_reject.csv"
                triaged_quarantine_path = tmp / "leads_triaged_quarantine.csv"
                preview_dir = tmp / "previews"
                report_dir = tmp / "reports"
                backup_root = tmp / "backups"
                ledger_path = tmp / "lead_ledger.sqlite3"
                state_path = tmp / "leads_state.json"
                jc_queue = tmp / "recipients_private_jc.csv"
                sg_queues = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
                queue_paths = [jc_queue, *sg_queues]
                logs = [tmp / "private_jc_log.csv"] + [
                    tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)
                ]
                source_rows = [
                    {
                        "FullName": f"Person {index}",
                        "FirstName": f"Person{index}",
                        "Email": f"person{index}@example.com",
                        "BookTitle": "A title with\nan intact second line" if index == 1 else f"Book {index}",
                        "Status": "KEEP",
                    }
                    for index in range(1, 13)
                ]
                write_csv(
                    master_path,
                    ["FullName", "FirstName", "Email", "BookTitle"],
                    [{key: row[key] for key in ["FullName", "FirstName", "Email", "BookTitle"]} for row in source_rows],
                )
                write_csv(rejected_path, ["FullName", "FirstName", "Email", "reject_code"], [])
                write_csv(
                    triaged_keep_path,
                    ["FullName", "FirstName", "Email", "BookTitle", "Status"],
                    source_rows,
                )
                write_csv(triaged_reject_path, ["FullName", "FirstName", "Email", "Status"], [])
                write_csv(triaged_quarantine_path, ["FullName", "FirstName", "Email", "Status"], [])
                for path in queue_paths[:-1]:
                    write_csv(
                        path,
                        ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"],
                        [],
                    )
                self.assertFalse(queue_paths[-1].exists())
                for path in logs:
                    write_csv(path, ["Email", "Status"], [])
                report_dir.mkdir(parents=True, exist_ok=True)
                history_path = report_dir / important_leads_workflow.DISPATCH_RUN_HISTORY_PATH.name
                history_path.write_bytes(b'[{"run_id":"original-history"}]\n')
                manifest_path = report_dir / "active_campaign_snapshot.json"
                manifest_path.write_bytes(b'{"state":"original-manifest"}\n')
                state_path.write_bytes(b'{"latest_dispatch":{"status":"original"}}\n')

                preview = preview_dispatch_master_leads(
                    master_path=master_path,
                    triaged_keep_path=triaged_keep_path,
                    rejected_path=rejected_path,
                    dispatch_source_mode="triaged_keep",
                    jc_queue_path=jc_queue,
                    sendgrid_queue_paths=sg_queues,
                    jc_log_path=logs[0],
                    sendgrid_log_paths=logs[1:],
                    sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                    suppressed_path=tmp / "suppressed.csv",
                    unsubscribed_path=tmp / "unsubscribed.csv",
                    lead_ledger_db_path=ledger_path,
                    preview_dir=preview_dir,
                )
                tracked_files = [
                    *queue_paths,
                    ledger_path,
                    state_path,
                    history_path,
                    manifest_path,
                    preview_dir / f"{preview['preview_id']}.json",
                    master_path,
                    rejected_path,
                    triaged_keep_path,
                    triaged_reject_path,
                    triaged_quarantine_path,
                ]
                before = {
                    path: path.read_bytes() if path.exists() else None
                    for path in tracked_files
                }

                def inject(phase: str) -> None:
                    if phase == fault_phase:
                        raise RuntimeError(f"injected failure: {phase}")

                with (
                    patch.object(important_leads_workflow.settings, "LEADS_STATE_PATH", state_path),
                    patch.object(leads_workflow, "LEADS_STATE_PATH", state_path),
                    self.assertRaisesRegex(RuntimeError, f"injected failure: {fault_phase}"),
                ):
                    confirm_dispatch_preview(
                        preview["preview_id"],
                        require_stopped=False,
                        backup_root=backup_root,
                        report_dir=report_dir,
                        persist_state=True,
                        preview_dir=preview_dir,
                        _fault_injector=inject,
                    )

                for path, original in before.items():
                    if original is None:
                        self.assertFalse(path.exists(), f"{path} should remain missing after {fault_phase}")
                    else:
                        self.assertEqual(original, path.read_bytes(), f"{path} changed after {fault_phase}")
                self.assertFalse(list(tmp.rglob("*.dispatch.*.tmp")))
                self.assertFalse((backup_root / "staged_batches").exists())
                self.assertEqual([], list((report_dir / "dispatch_confirmed").glob("*.json")))
                self.assertEqual("previewed", load_dispatch_preview(preview["preview_id"], preview_dir=preview_dir)["status"])

                with (
                    patch.object(important_leads_workflow.settings, "LEADS_STATE_PATH", state_path),
                    patch.object(leads_workflow, "LEADS_STATE_PATH", state_path),
                ):
                    report = confirm_dispatch_preview(
                        preview["preview_id"],
                        require_stopped=False,
                        backup_root=backup_root,
                        report_dir=report_dir,
                        persist_state=True,
                        preview_dir=preview_dir,
                    )
                self.assertEqual("completed", report["status"])
                history = json.loads(history_path.read_text(encoding="utf-8"))
                self.assertEqual(1, sum(item.get("run_id") == report["run_id"] for item in history))
                all_rows = [row for path in queue_paths for row in read_csv_rows(path)]
                all_emails = [row["Email"] for row in all_rows]
                self.assertEqual(len(all_emails), len(set(all_emails)))
                self.assertIn("A title with\nan intact second line", {row["BookTitle"] for row in all_rows})
                self.assertEqual(
                    preview["queue_headers"],
                    list(all_rows[0]),
                )

    def test_preview_dispatch_master_leads_blocks_empty_triaged_keep_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], [])

            with self.assertRaisesRegex(ValueError, "Fast Triage Keep dispatch source is empty"):
                preview_dispatch_master_leads(
                    master_path=master_path,
                    triaged_keep_path=triaged_keep_path,
                    rejected_path=tmp / "leads_rejected.csv",
                    dispatch_source_mode="triaged_keep",
                    jc_queue_path=tmp / "recipients_private_jc.csv",
                    sendgrid_queue_paths=[tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)],
                    jc_log_path=tmp / "private_jc_log.csv",
                    sendgrid_log_paths=[tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)],
                    sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                    suppressed_path=tmp / "suppressed.csv",
                    unsubscribed_path=tmp / "unsubscribed.csv",
                    lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                    preview_dir=tmp / "previews",
                )

    def test_confirm_dispatch_preview_blocks_when_staged_batch_missing_or_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [{"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"}],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            triaged_keep_path.unlink()
            with self.assertRaisesRegex(RuntimeError, "No active staged Fast Triage batch found"):
                confirm_dispatch_preview(preview["preview_id"], require_stopped=False, preview_dir=preview_dir)

            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], [])
            with self.assertRaisesRegex(RuntimeError, "Active staged Fast Triage batch is empty"):
                confirm_dispatch_preview(preview["preview_id"], require_stopped=False, preview_dir=preview_dir)

    def test_confirm_dispatch_preview_rejects_missing_campaign_or_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            preview_dir = tmp / "previews"
            preview_dir.mkdir()
            preview_id = "dispatch_preview_missing_metadata"
            payload = {
                "preview_id": preview_id,
                "status": "previewed",
                "dispatch_source_path": str(tmp / "leads_triaged_keep.csv"),
                "plan_rows_by_queue": {
                    "private_jc": [],
                    "sendgrid_1": [],
                    "sendgrid_2": [],
                    "sendgrid_3": [],
                    "sendgrid_4": [],
                    "sendgrid_5": [],
                },
                "private_jc_planned_count": 0,
                "sendgrid_planned_count": 0,
                "total_planned_unique_count": 0,
                "total_rows_would_write": 0,
            }
            (preview_dir / f"{preview_id}.json").write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "missing campaign type"):
                confirm_dispatch_preview(preview_id, require_stopped=False, preview_dir=preview_dir)

            payload["campaign_type"] = "cold"
            (preview_dir / f"{preview_id}.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "missing dispatch source mode"):
                confirm_dispatch_preview(preview_id, require_stopped=False, preview_dir=preview_dir)

    def test_confirm_dispatch_preview_rejects_duplicate_email_across_planned_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            row = {"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"}
            write_csv(master_path, ["FullName", "FirstName", "Email"], [{k: row[k] for k in ["FullName", "FirstName", "Email"]}])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], [row])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )
            preview_path = preview_dir / f"{preview['preview_id']}.json"
            stored_preview = json.loads(preview_path.read_text(encoding="utf-8"))
            stored_preview["plan_rows_by_queue"]["sendgrid_1"] = [dict(stored_preview["plan_rows_by_queue"]["private_jc"][0])]
            preview_path.write_text(json.dumps(stored_preview, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "duplicate planned recipients"):
                confirm_dispatch_preview(preview["preview_id"], require_stopped=False, preview_dir=preview_dir)

    def test_confirm_dispatch_preview_blocks_when_senders_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [{"FullName": "Alpha Person", "FirstName": "Alpha", "Email": "alpha@example.com", "Status": "KEEP"}],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            with patch.object(important_leads_workflow, "_active_sender_states", return_value={"sendgrid_1": "running"}):
                with self.assertRaisesRegex(RuntimeError, "Stop all senders before dispatching leads"):
                    confirm_dispatch_preview(preview["preview_id"], preview_dir=preview_dir)

    def _preview_dispatch_cap_fixture(
        self,
        tmp: Path,
        *,
        row_count: int,
        dispatch_cap: str,
        contacted_count: int = 0,
        preview_name: str = "previews",
    ) -> dict[str, object]:
        master_path = tmp / "leads.csv"
        triaged_keep_path = tmp / "leads_triaged_keep.csv"
        jc_queue = tmp / "recipients_private_jc.csv"
        sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
        logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
        ledger_path = tmp / "lead_ledger.sqlite3"

        write_csv(master_path, ["FullName", "FirstName", "Email"], [])
        rows = [
            {
                "FullName": f"Person {index}",
                "FirstName": f"Person{index}",
                "Email": f"person{index}@example.com",
                "Status": "KEEP",
            }
            for index in range(row_count)
        ]
        write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
        write_csv(jc_queue, ["Email", "FirstName"], [])
        for path in sg_queues:
            write_csv(path, ["Email", "FirstName"], [])
        for path in logs:
            write_csv(path, ["Email", "Status"], [])

        if contacted_count:
            conn = lead_ledger.connect_lead_ledger(ledger_path)
            try:
                for row in rows[:contacted_count]:
                    lead = lead_ledger.upsert_lead(conn, email=row["Email"])
                    lead_ledger.record_dispatch_event(
                        conn,
                        lead_id=lead["lead_id"],
                        run_id="dispatch_run_prior",
                        dispatch_source="triaged_keep",
                        profile="sendgrid_1",
                        queue_target="sendgrid_1",
                        result_status="delivered",
                        dispatched_at="2026-04-11T05:00:00+00:00",
                    )
            finally:
                conn.close()

        return preview_dispatch_master_leads(
            master_path=master_path,
            triaged_keep_path=triaged_keep_path,
            rejected_path=tmp / "leads_rejected.csv",
            dispatch_source_mode="triaged_keep",
            dispatch_cap=dispatch_cap,
            jc_queue_path=jc_queue,
            sendgrid_queue_paths=sg_queues,
            jc_log_path=logs[0],
            sendgrid_log_paths=logs[1:],
            sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
            suppressed_path=tmp / "suppressed.csv",
            unsubscribed_path=tmp / "unsubscribed.csv",
            lead_ledger_db_path=ledger_path,
            preview_dir=tmp / preview_name,
        )

    def test_preview_dispatch_master_leads_applies_dispatch_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            capped = self._preview_dispatch_cap_fixture(
                tmp,
                row_count=150,
                dispatch_cap="100",
                preview_name="previews_100",
            )
            all_rows = self._preview_dispatch_cap_fixture(
                tmp,
                row_count=150,
                dispatch_cap="all",
                preview_name="previews_all",
            )

            self.assertEqual("100", capped["dispatch_cap"])
            self.assertEqual(100, capped["selected_rows"])
            self.assertEqual(100, capped["total_rows_that_would_be_written"])
            self.assertEqual("all", all_rows["dispatch_cap"])
            self.assertEqual(150, all_rows["selected_rows"])
            self.assertEqual(150, all_rows["total_rows_that_would_be_written"])

    def test_fresh_cold_cap_excludes_history_before_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            capped = self._preview_dispatch_cap_fixture(
                tmp,
                row_count=150,
                contacted_count=90,
                dispatch_cap="100",
            )

            self.assertEqual("100", capped["dispatch_cap"])
            self.assertEqual(150, capped["selected_rows"])
            self.assertEqual(90, capped["skipped_already_contacted"])
            self.assertEqual(30, capped["rows_to_add_private_jc"])
            self.assertEqual(30, capped["rows_to_add_sendgrid"])
            self.assertEqual(6, capped["assigned_sg1"])
            self.assertEqual(6, capped["assigned_sg2"])
            self.assertEqual(6, capped["assigned_sg3"])
            self.assertEqual(6, capped["assigned_sg4"])
            self.assertEqual(6, capped["assigned_sg5"])

    def test_fresh_cold_cap_scans_past_blocked_history_to_fill_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            capped = self._preview_dispatch_cap_fixture(
                tmp,
                row_count=220,
                contacted_count=90,
                dispatch_cap="100",
            )

            self.assertEqual("100", capped["dispatch_cap"])
            self.assertEqual(190, capped["selected_rows"])
            self.assertEqual(90, capped["skipped_already_contacted"])
            self.assertEqual(50, capped["rows_to_add_sendgrid"])
            self.assertEqual(50, capped["rows_to_add_private_jc"])
            self.assertEqual(10, capped["assigned_sg1"])
            self.assertEqual(10, capped["assigned_sg2"])
            self.assertEqual(10, capped["assigned_sg3"])
            self.assertEqual(10, capped["assigned_sg4"])
            self.assertEqual(10, capped["assigned_sg5"])

    def test_preview_dispatch_master_leads_missing_source_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            write_csv(tmp / "leads.csv", ["FullName", "FirstName", "Email"], [])
            with self.assertRaisesRegex(ValueError, "Fast Triage Keep dispatch source missing"):
                preview_dispatch_master_leads(
                    master_path=tmp / "leads.csv",
                    triaged_keep_path=tmp / "missing_triaged_keep.csv",
                    rejected_path=tmp / "leads_rejected.csv",
                    dispatch_source_mode="triaged_keep",
                    jc_queue_path=tmp / "recipients_private_jc.csv",
                    sendgrid_queue_paths=[tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)],
                    jc_log_path=tmp / "private_jc_log.csv",
                    sendgrid_log_paths=[tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)],
                    sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                    suppressed_path=tmp / "suppressed.csv",
                    unsubscribed_path=tmp / "unsubscribed.csv",
                    lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                    preview_dir=tmp / "previews",
                )

    def test_preview_dispatch_master_leads_source_switching_updates_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            verified_path = tmp / "leads_verified.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Fast One", "FirstName": "Fast", "Email": "fast1@example.com", "Status": "KEEP"},
                    {"FullName": "Fast Two", "FirstName": "Fast", "Email": "fast2@example.com", "Status": "KEEP"},
                ],
            )
            write_csv(
                verified_path,
                ["FullName", "FirstName", "Email", "Status"],
                [{"FullName": "Strict One", "FirstName": "Strict", "Email": "strict1@example.com", "Status": "KEEP"}],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            triaged_preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                verified_path=verified_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=tmp / "previews_triaged",
            )
            strict_preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                verified_path=verified_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="strict_verified",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=tmp / "previews_strict",
            )

            self.assertEqual("triaged_keep", triaged_preview["active_source_key"])
            self.assertEqual(2, triaged_preview["eligible_rows"])
            self.assertEqual(str(triaged_keep_path), triaged_preview["source_file_path"])
            self.assertEqual("strict_verified", strict_preview["active_source_key"])
            self.assertEqual(1, strict_preview["eligible_rows"])
            self.assertEqual(str(verified_path), strict_preview["source_file_path"])
            self.assertNotEqual(triaged_preview["preview_id"], strict_preview["preview_id"])

    def test_fresh_cold_blocks_astra_contact_instead_of_cross_lane_reroute(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]

            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(
                triaged_keep_path,
                ["FullName", "FirstName", "Email", "Status"],
                [
                    {"FullName": "Fresh Person", "FirstName": "Fresh", "Email": "fresh@example.com", "Status": "KEEP"},
                    {"FullName": "Contacted Person", "FirstName": "Contacted", "Email": "contacted@example.com", "Status": "KEEP"},
                ],
            )
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                contacted = lead_ledger.upsert_lead(conn, email="contacted@example.com")
                lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=contacted["lead_id"],
                    run_id="dispatch_run_prior",
                    dispatch_source="triaged_keep",
                    profile="private_jc",
                    queue_target="private_jc",
                    result_status="delivered",
                    dispatched_at="2026-04-11T05:00:00+00:00",
                )
            finally:
                conn.close()

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                preview_dir=tmp / "previews",
            )

            self.assertEqual(1, preview["skipped_already_contacted"])
            self.assertEqual(1, preview["rows_to_add_private_jc"])
            self.assertEqual(0, preview["rows_to_add_sendgrid"])
            self.assertEqual(1, preview["exclusion_reason_counts"]["already_contacted"])

    def test_preview_dispatch_scopes_ledger_contact_history_by_lane(self) -> None:
        scenarios = [
            ("private_jc", "private_jc", "delivered", 0, 0, 1, {"already_contacted": 1}),
            ("private_jc_warm", "private_jc_warm", "delivered", 0, 0, 1, {"already_contacted": 1}),
            ("sendgrid_jordan", "sendgrid_2", "delivered", 0, 0, 1, {"already_contacted": 1}),
            ("private_jc", "private_jc", "complaint", 0, 0, 0, {"bad_contact_history": 1}),
        ]
        for profile, queue_target, status, expected_jc, expected_sg, expected_contacted, expected_reasons in scenarios:
            with self.subTest(profile=profile, status=status), tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                master_path = tmp / "leads.csv"
                triaged_keep_path = tmp / "leads_triaged_keep.csv"
                ledger_db_path = tmp / "lead_ledger.sqlite3"
                jc_queue = tmp / "recipients_private_jc.csv"
                sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
                logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
                row = {"FullName": "Lane Person", "FirstName": "Lane", "Email": "lane@example.com", "Status": "KEEP"}
                write_csv(master_path, ["FullName", "FirstName", "Email"], [])
                write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], [row])
                write_csv(jc_queue, ["Email", "FirstName"], [])
                for path in [*sg_queues, *logs]:
                    write_csv(path, ["Email", "Status"], [])

                conn = lead_ledger.connect_lead_ledger(ledger_db_path)
                try:
                    lead = lead_ledger.upsert_lead(conn, email="lane@example.com")
                    lead_ledger.record_dispatch_event(
                        conn,
                        lead_id=lead["lead_id"],
                        run_id="dispatch_run_prior",
                        dispatch_source="triaged_keep",
                        profile=profile,
                        queue_target=queue_target,
                        result_status=status,
                        dispatched_at="2026-04-11T05:00:00+00:00",
                    )
                finally:
                    conn.close()

                preview = preview_dispatch_master_leads(
                    master_path=master_path,
                    triaged_keep_path=triaged_keep_path,
                    rejected_path=tmp / "leads_rejected.csv",
                    dispatch_source_mode="triaged_keep",
                    jc_queue_path=jc_queue,
                    sendgrid_queue_paths=sg_queues,
                    jc_log_path=logs[0],
                    sendgrid_log_paths=logs[1:],
                    sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                    suppressed_path=tmp / "suppressed.csv",
                    unsubscribed_path=tmp / "unsubscribed.csv",
                    lead_ledger_db_path=ledger_db_path,
                    preview_dir=tmp / "previews",
                )

                self.assertEqual(expected_jc, preview["rows_to_add_private_jc"])
                self.assertEqual(expected_sg, preview["rows_to_add_sendgrid"])
                self.assertEqual(expected_contacted, preview["skipped_already_contacted"])
                self.assertEqual(expected_reasons, preview["exclusion_reason_counts"])

    def test_recontact_allows_prior_success_from_both_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            row = {"FullName": "Both Person", "FirstName": "Both", "Email": "both@example.com", "Status": "KEEP"}
            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], [row])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in [*sg_queues, *logs]:
                write_csv(path, ["Email", "Status"], [])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                lead = lead_ledger.upsert_lead(conn, email="both@example.com")
                for profile, queue_target in (("private_jc", "private_jc"), ("sendgrid_jordan", "sendgrid_2")):
                    lead_ledger.record_dispatch_event(
                        conn,
                        lead_id=lead["lead_id"],
                        run_id=f"dispatch_run_{profile}",
                        dispatch_source="triaged_keep",
                        profile=profile,
                        queue_target=queue_target,
                        result_status="delivered",
                        dispatched_at="2026-04-11T05:00:00+00:00",
                    )
            finally:
                conn.close()

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                campaign_type="recontact_cold",
                preview_dir=tmp / "previews",
            )

            self.assertEqual(1, preview["total_planned_unique_count"])
            self.assertEqual(0, preview["skipped_already_contacted"])
            self.assertEqual({}, preview["exclusion_reason_counts"])

    def test_warm_private_queue_blocks_all_fresh_cold_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            jc_queue = tmp / "recipients_private_jc.csv"
            warm_queue = tmp / "recipients_private_jc_warm.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            logs = [tmp / "private_jc_log.csv"] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            row = {"FullName": "Warm Queue", "FirstName": "Warm", "Email": "warm-queued@example.com", "Status": "KEEP"}
            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], [row])
            write_csv(jc_queue, ["Email", "FirstName"], [])
            write_csv(warm_queue, ["Email", "FirstName"], [{"Email": "warm-queued@example.com", "FirstName": "Warm"}])
            for path in [*sg_queues, *logs]:
                write_csv(path, ["Email", "Status"], [])

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                preview_dir=tmp / "previews",
            )

            self.assertEqual(0, preview["rows_to_add_private_jc"])
            self.assertEqual(0, preview["rows_to_add_sendgrid"])
            self.assertEqual(1, preview["skipped_already_queued"])

    def test_preview_dispatch_ignores_queued_staged_history_for_fresh_cold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            jc_log = tmp / "private_jc_log.csv"
            staged_log_like_path = tmp / "data" / "state" / "backups" / "staged_batches" / "dispatch_test" / "leads_triaged_keep.csv"
            sg_logs = [staged_log_like_path] + [tmp / f"sendgrid_{idx}_log.csv" for idx in range(2, 6)]

            rows = [
                {"FullName": "Queued Person", "FirstName": "Queued", "Email": "queued@example.com", "Status": "KEEP"},
                {"FullName": "Fresh Person", "FirstName": "Fresh", "Email": "fresh@example.com", "Status": "KEEP"},
            ]
            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            write_csv(jc_log, ["Email", "Status"], [])
            write_csv(staged_log_like_path, ["Email", "Status"], [{"Email": "queued@example.com", "Status": "SENT"}])
            for path in sg_logs[1:]:
                write_csv(path, ["Email", "Status"], [])

            conn = lead_ledger.connect_lead_ledger(ledger_db_path)
            try:
                queued = lead_ledger.upsert_lead(conn, email="queued@example.com")
                lead_ledger.record_dispatch_event(
                    conn,
                    lead_id=queued["lead_id"],
                    run_id="dispatch_run_staged_only",
                    dispatch_source="triaged_keep",
                    profile="private_jc",
                    queue_target="private_jc",
                    result_status="queued",
                    dispatched_at="2026-06-23T21:47:27+00:00",
                )
            finally:
                conn.close()

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=jc_log,
                sendgrid_log_paths=sg_logs,
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                preview_dir=tmp / "previews",
            )

            planned_emails = [
                row["Email"]
                for rows_by_queue in preview["plan_rows_by_queue"].values()
                for row in rows_by_queue
            ]
            self.assertEqual(0, preview["skipped_already_contacted"])
            self.assertEqual(0, preview["skipped_already_sent"])
            self.assertCountEqual(["queued@example.com", "fresh@example.com"], planned_emails)
            self.assertEqual(
                1,
                preview["history_source_category_counts"]["skipped_from_non_authoritative_history_ignored"],
            )
            self.assertEqual(0, preview["history_source_category_counts"]["already_contacted_from_contact_history"])
            self.assertEqual(0, preview["history_source_category_counts"]["already_sent_from_actual_send_log"])

    def test_fresh_cold_preview_blocks_authoritative_sendgrid_sent_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            ledger_db_path = tmp / "lead_ledger.sqlite3"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
            jc_log = tmp / "private_jc_log.csv"
            sg_logs = [tmp / f"sendgrid_{idx}_log.csv" for idx in range(1, 6)]
            domain_log = tmp / "sendgrid_domain_log.csv"

            source_rows = [
                {"FullName": "Profile Sent", "FirstName": "Profile", "Email": "profile-sent@example.com", "Status": "KEEP"},
                {"FullName": "Domain Attempt Sent", "FirstName": "Domain", "Email": "domain-sent@example.com", "Status": "KEEP"},
                {"FullName": "Fresh One", "FirstName": "Fresh", "Email": "fresh-one@example.com", "Status": "KEEP"},
                {"FullName": "Fresh Two", "FirstName": "Fresh", "Email": "fresh-two@example.com", "Status": "KEEP"},
            ]
            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], source_rows)
            write_csv(jc_queue, ["Email", "FirstName"], [])
            for path in sg_queues:
                write_csv(path, ["Email", "FirstName"], [])
            write_csv(jc_log, ["Email", "Status"], [])
            write_csv(sg_logs[0], ["Email", "Status"], [{"Email": "profile-sent@example.com", "Status": "SENT"}])
            for path in sg_logs[1:]:
                write_csv(path, ["Email", "Status"], [])
            write_csv(
                domain_log,
                ["TimestampUTC", "Email", "Status", "Info"],
                [
                    {
                        "TimestampUTC": "2026-06-24T00:00:00Z",
                        "Email": "domain-sent@example.com",
                        "Status": "ATTEMPT",
                        "Info": "provider=sendgrid outcome=sent message_id=test",
                    }
                ],
            )
            write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])
            write_csv(tmp / "suppressed.csv", ["Email"], [])
            write_csv(tmp / "unsubscribed.csv", ["Email"], [])

            queue_before = {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]}

            preview = preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=tmp / "leads_rejected.csv",
                dispatch_source_mode="triaged_keep",
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queues,
                jc_log_path=jc_log,
                sendgrid_log_paths=[*sg_logs, domain_log],
                sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                suppressed_path=tmp / "suppressed.csv",
                unsubscribed_path=tmp / "unsubscribed.csv",
                lead_ledger_db_path=ledger_db_path,
                preview_dir=tmp / "previews",
            )

            planned_emails = {
                row["Email"].lower()
                for rows_by_queue in preview["plan_rows_by_queue"].values()
                for row in rows_by_queue
            }
            authoritative_sent = _sent_email_set([jc_log, *sg_logs, domain_log])
            sendgrid_planned_emails = {
                row["Email"].lower()
                for queue_name, rows_by_queue in preview["plan_rows_by_queue"].items()
                if queue_name.startswith("sendgrid_")
                for row in rows_by_queue
            }

            self.assertEqual(
                {
                    "fresh-one@example.com",
                    "fresh-two@example.com",
                },
                planned_emails,
            )
            self.assertEqual(set(), sendgrid_planned_emails & authoritative_sent)
            self.assertEqual(2, preview["skipped_already_sent"])
            self.assertEqual(2, preview["skipped_rows"])
            self.assertEqual({"already_sent": 2}, preview["exclusion_reason_counts"])
            self.assertEqual(preview["skipped_rows"], sum(preview["exclusion_reason_counts"].values()))
            self.assertEqual(
                2,
                preview["history_audit_counts"]["already_sent_from_actual_send_log"],
            )
            self.assertIn(str(domain_log), preview["sendgrid_log_paths"])
            self.assertIn(str(domain_log), preview["authoritative_send_log_paths"])
            self.assertEqual(queue_before, {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]})

    def test_fresh_cold_preview_contract_allows_large_already_sent_exclusion_when_overlap_zero(self) -> None:
        preview = {
            "campaign_type": "cold",
            "history_policy_version": 2,
            "prior_success_policy": "block_global",
            "dispatch_source_mode": "triaged_keep",
            "dispatch_source_path": "/tmp/leads_triaged_keep.csv",
            "preview_id": "preview_safe",
            "private_jc_planned_count": 621,
            "sendgrid_planned_count": 621,
            "total_planned_unique_count": 1242,
            "total_rows_would_write": 1242,
            "duplicate_planned_email_count": 0,
            "skipped_rows": 2470,
            "exclusion_reason_counts": {"already_sent": 2470},
            "planned_authoritative_sent_overlap_count": 0,
            "plan_rows_by_queue": {
                "private_jc": [planned_row(f"fresh-private-{index}@example.com", f"Private{index}") for index in range(621)],
                "sendgrid_1": [planned_row(f"fresh-sg-{index}@example.com", f"SendGrid{index}") for index in range(621)],
                "sendgrid_2": [],
                "sendgrid_3": [],
                "sendgrid_4": [],
                "sendgrid_5": [],
            },
        }

        _validate_dispatch_preview_contract(preview)

    def test_default_sendgrid_routing_uses_only_enabled_profiles_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master_path = tmp / "leads.csv"
            triaged_keep_path = tmp / "leads_triaged_keep.csv"
            rows = [
                {
                    "FullName": f"Lead {index}",
                    "FirstName": f"Lead{index}",
                    "Email": f"lead-{index}@example.com",
                    "Status": "KEEP",
                }
                for index in range(1, 7)
            ]
            write_csv(master_path, ["FullName", "FirstName", "Email"], [])
            write_csv(triaged_keep_path, ["FullName", "FirstName", "Email", "Status"], rows)
            for cfg in send_shard.PROFILES.values():
                csv_name = str(cfg.get("csv") or "").strip()
                log_name = str(cfg.get("log") or "").strip()
                if csv_name:
                    write_csv(tmp / Path(csv_name).name, ["Email", "FirstName"], [])
                if log_name:
                    write_csv(tmp / Path(log_name).name, ["Email", "Status"], [])
            write_csv(tmp / "sendgrid_domain_log.csv", ["Email", "Status"], [])
            write_csv(tmp / "sendgrid_suppressions.csv", ["email", "state", "type"], [])
            write_csv(tmp / "suppressed.csv", ["Email"], [])
            write_csv(tmp / "unsubscribed.csv", ["Email"], [])

            def managed_path(value: object) -> Path:
                return tmp / Path(str(value)).name

            def build(preview_name: str) -> dict[str, object]:
                with (
                    patch.object(important_leads_workflow.settings, "shard_path", side_effect=managed_path),
                    patch.object(important_leads_workflow.settings, "log_path", side_effect=managed_path),
                ):
                    return preview_dispatch_master_leads(
                        master_path=master_path,
                        triaged_keep_path=triaged_keep_path,
                        rejected_path=tmp / "leads_rejected.csv",
                        dispatch_source_mode="triaged_keep",
                        sendgrid_suppressions_path=tmp / "sendgrid_suppressions.csv",
                        suppressed_path=tmp / "suppressed.csv",
                        unsubscribed_path=tmp / "unsubscribed.csv",
                        lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
                        preview_dir=tmp / preview_name,
                    )

            first = build("previews-one")
            second = build("previews-two")
            expected_profiles = ["sendgrid_alison", "sendgrid_jodi", "sendgrid_jordan"]
            self.assertEqual(expected_profiles, first["sendgrid_profile_order"])
            self.assertEqual(["private_jc", *expected_profiles], first["queue_key_order"])
            self.assertNotIn("sendgrid_annette", first["plan_rows_by_queue"])
            self.assertNotIn("sendgrid_fiorela", first["plan_rows_by_queue"])
            self.assertNotIn("sendgrid_controlled_test", first["plan_rows_by_queue"])
            self.assertEqual(
                {profile: 1 for profile in expected_profiles},
                first["sendgrid_profile_planned_counts"],
            )
            first_routes = {
                key: [row["Email"] for row in planned_rows]
                for key, planned_rows in first["plan_rows_by_queue"].items()
            }
            second_routes = {
                key: [row["Email"] for row in planned_rows]
                for key, planned_rows in second["plan_rows_by_queue"].items()
            }
            self.assertEqual(first_routes, second_routes)
            safety_names = {Path(path).name for path in first["queue_safety_paths"]}
            self.assertIn("recipients_sendgrid_1.csv", safety_names)
            self.assertIn("recipients_sendgrid_5.csv", safety_names)
            self.assertIn("recipients_sendgrid_controlled_test.csv", safety_names)

            write_csv(
                tmp / "recipients_sendgrid_1.csv",
                ["Email", "FirstName"],
                [{"Email": "legacy-active@example.com", "FirstName": "Legacy"}],
            )
            with self.assertRaisesRegex(RuntimeError, "Changed inputs"):
                important_leads_workflow.validate_dispatch_preview(
                    first["preview_id"],
                    preview_dir=tmp / "previews-one",
                )

    def test_current_policy_confirmation_locks_complete_safety_set_and_writes_only_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fixture = build_dynamic_dispatch_fixture(tmp, preview_name="previews")
            preview = fixture["preview"]
            preview_dir = fixture["preview_dir"]
            queue_paths_map = preview["queue_paths"]
            destination_paths = [Path(queue_paths_map[key]) for key in preview["queue_key_order"]]
            safety_paths = [Path(path) for path in preview["queue_safety_paths"]]
            expected_lock_paths = list(dict.fromkeys([*destination_paths, *safety_paths]))
            safety_only_paths = [path for path in safety_paths if path not in destination_paths]
            safety_only_before = {path: path.read_bytes() for path in safety_only_paths}
            captured_lock_sets: list[list[Path]] = []
            real_lock_files = important_leads_workflow.lock_files

            @contextmanager
            def capture_lock_files(paths: object):
                captured = list(paths)
                captured_lock_sets.append(captured)
                with real_lock_files(captured):
                    yield

            with patch.object(important_leads_workflow, "lock_files", side_effect=capture_lock_files):
                report = confirm_dispatch_preview(
                    preview["preview_id"],
                    require_stopped=False,
                    backup_root=tmp / "backups",
                    report_dir=tmp / "reports",
                    persist_state=False,
                    preview_dir=preview_dir,
                )

            self.assertEqual([expected_lock_paths], captured_lock_sets)
            self.assertEqual(len(expected_lock_paths), len({path.resolve() for path in expected_lock_paths}))
            self.assertEqual(
                {
                    "recipients_private_jc.csv",
                    "recipients_private_jc_warm.csv",
                    "recipients_sendgrid_1.csv",
                    "recipients_sendgrid_2.csv",
                    "recipients_sendgrid_3.csv",
                    "recipients_sendgrid_4.csv",
                    "recipients_sendgrid_5.csv",
                    "recipients_sendgrid_controlled_test.csv",
                },
                {path.name for path in expected_lock_paths},
            )
            self.assertEqual(
                {"private_jc", "sendgrid_alison", "sendgrid_jodi", "sendgrid_jordan"},
                set(report["rows_written_per_queue"]),
            )
            for key, path in zip(preview["queue_key_order"], destination_paths):
                self.assertEqual(preview["plan_rows_by_queue"][key], read_csv_rows(path))
            for path, original in safety_only_before.items():
                self.assertEqual(original, path.read_bytes(), f"safety-only queue was modified: {path.name}")
            self.assertNotIn("sendgrid_annette", report["rows_written_per_queue"])
            self.assertNotIn("sendgrid_fiorela", report["rows_written_per_queue"])
            self.assertNotIn("sendgrid_controlled_test", report["rows_written_per_queue"])
            self.assertNotIn("private_jc_warm", report["rows_written_per_queue"])
            self.assertEqual(
                report["added_sendgrid"],
                sum(report["rows_written_sendgrid_shards"].values()),
            )

    def test_current_policy_confirmation_waits_for_disabled_queue_and_fails_closed_on_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fixture = build_dynamic_dispatch_fixture(tmp, preview_name="previews")
            preview = fixture["preview"]
            preview_dir = fixture["preview_dir"]
            queue_paths_map = preview["queue_paths"]
            destination_paths = [Path(queue_paths_map[key]) for key in preview["queue_key_order"]]
            destination_before = {path: path.read_bytes() for path in destination_paths}
            disabled_queue = tmp / Path(str(send_shard.PROFILES["sendgrid_annette"]["csv"])).name
            self.assertIn(str(disabled_queue), preview["queue_safety_paths"])
            self.assertNotIn(disabled_queue, destination_paths)

            writer_has_lock = threading.Event()
            allow_writer_change = threading.Event()
            confirmation_lock_attempted = threading.Event()
            writer_errors: list[BaseException] = []
            confirmation_errors: list[BaseException] = []
            real_lock_files = important_leads_workflow.lock_files

            def mutate_disabled_queue() -> None:
                try:
                    with real_lock_files([disabled_queue]):
                        writer_has_lock.set()
                        if not allow_writer_change.wait(timeout=5):
                            raise RuntimeError("timed out waiting to mutate disabled queue")
                        write_csv(
                            disabled_queue,
                            ["Email", "FirstName"],
                            [{"Email": "lead-1@example.com", "FirstName": "Lead1"}],
                        )
                except BaseException as exc:  # pragma: no cover - surfaced by assertion below
                    writer_errors.append(exc)

            @contextmanager
            def observe_confirmation_lock(paths: object):
                captured = list(paths)
                confirmation_lock_attempted.set()
                with real_lock_files(captured):
                    yield

            def run_confirmation() -> None:
                try:
                    confirm_dispatch_preview(
                        preview["preview_id"],
                        require_stopped=False,
                        backup_root=tmp / "backups",
                        report_dir=tmp / "reports",
                        persist_state=False,
                        preview_dir=preview_dir,
                    )
                except BaseException as exc:
                    confirmation_errors.append(exc)

            writer = threading.Thread(target=mutate_disabled_queue)
            writer.start()
            self.assertTrue(writer_has_lock.wait(timeout=5))
            with patch.object(important_leads_workflow, "lock_files", side_effect=observe_confirmation_lock):
                confirmation = threading.Thread(target=run_confirmation)
                confirmation.start()
                self.assertTrue(confirmation_lock_attempted.wait(timeout=5))
                time.sleep(0.05)
                self.assertTrue(confirmation.is_alive(), "confirmation did not wait for the disabled queue lock")
                allow_writer_change.set()
                writer.join(timeout=5)
                confirmation.join(timeout=5)

            self.assertFalse(writer.is_alive())
            self.assertFalse(confirmation.is_alive())
            self.assertEqual([], writer_errors)
            self.assertEqual(1, len(confirmation_errors))
            self.assertIsInstance(confirmation_errors[0], RuntimeError)
            self.assertIn("Changed inputs", str(confirmation_errors[0]))
            self.assertEqual(
                [{"Email": "lead-1@example.com", "FirstName": "Lead1"}],
                read_csv_rows(disabled_queue),
            )
            for path, original in destination_before.items():
                self.assertEqual(original, path.read_bytes(), f"destination changed after stale preview: {path.name}")
            self.assertEqual(
                "previewed",
                load_dispatch_preview(preview["preview_id"], preview_dir=preview_dir)["status"],
            )
            self.assertFalse(list((tmp / "reports" / "dispatch_confirmed").glob("*.json")))

    def test_ambiguous_legacy_fresh_cold_preview_fails_closed(self) -> None:
        preview = {
            "campaign_type": "cold",
            "dispatch_source_mode": "triaged_keep",
            "dispatch_source_path": "/tmp/leads_triaged_keep.csv",
            "preview_id": "legacy_ambiguous",
            "private_jc_planned_count": 1,
            "sendgrid_planned_count": 0,
            "total_planned_unique_count": 1,
            "total_rows_would_write": 1,
            "duplicate_planned_email_count": 0,
            "skipped_rows": 0,
            "exclusion_reason_counts": {},
            "planned_authoritative_sent_overlap_count": 0,
            "plan_rows_by_queue": {"private_jc": [planned_row("fresh@example.com")]},
        }
        with self.assertRaisesRegex(RuntimeError, "current global prior-success policy"):
            _validate_dispatch_preview_contract(preview)

    def test_recontact_preview_contract_allows_sent_log_overlap(self) -> None:
        campaign_id = "dispatch_preview_20260831_120000_deadbeef"
        preview = {
            "campaign_type": "recontact_cold",
            "dispatch_source_mode": "triaged_keep",
            "dispatch_source_kind": "triaged_keep",
            "full_recontact_sendgrid_only": True,
            "dispatch_source_path": "/tmp/leads_triaged_keep.csv",
            "preview_id": campaign_id,
            "campaign_id": campaign_id,
            "queue_headers": ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle", "campaign_type", "dispatch_source_kind", "campaign_id"],
            "private_jc_planned_count": 0,
            "sendgrid_planned_count": 2,
            "total_planned_unique_count": 2,
            "total_rows_would_write": 2,
            "duplicate_planned_email_count": 0,
            "skipped_rows": 0,
            "exclusion_reason_counts": {},
            "planned_authoritative_sent_overlap_count": 1,
            "plan_rows_by_queue": {
                "private_jc": [],
                "sendgrid_1": [
                    {**planned_row("overlap-private@example.com", "OverlapPrivate"), "campaign_type": "recontact_cold", "dispatch_source_kind": "full_recontact", "campaign_id": campaign_id},
                    {**planned_row("overlap-sg@example.com", "OverlapSg"), "campaign_type": "recontact_cold", "dispatch_source_kind": "full_recontact", "campaign_id": campaign_id},
                ],
                "sendgrid_2": [],
                "sendgrid_3": [],
                "sendgrid_4": [],
                "sendgrid_5": [],
            },
        }

        _validate_dispatch_preview_contract(preview)

    def test_recontact_preview_contract_rejects_missing_or_mixed_campaign_ids(self) -> None:
        campaign_id = "dispatch_preview_20260831_120000_deadbeef"
        base_preview = {
            "campaign_type": "recontact_cold",
            "dispatch_source_mode": "triaged_keep",
            "dispatch_source_kind": "triaged_keep",
            "full_recontact_sendgrid_only": True,
            "dispatch_source_path": "/tmp/leads_triaged_keep.csv",
            "preview_id": campaign_id,
            "campaign_id": campaign_id,
            "queue_headers": ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle", "campaign_type", "dispatch_source_kind", "campaign_id"],
            "private_jc_planned_count": 0,
            "sendgrid_planned_count": 1,
            "total_planned_unique_count": 1,
            "total_rows_would_write": 1,
            "duplicate_planned_email_count": 0,
            "skipped_rows": 0,
            "exclusion_reason_counts": {},
            "plan_rows_by_queue": {
                "private_jc": [],
                "sendgrid_1": [{**planned_row("one@example.com"), "campaign_type": "recontact_cold", "dispatch_source_kind": "full_recontact", "campaign_id": campaign_id}],
            },
        }

        missing = json.loads(json.dumps(base_preview))
        missing["plan_rows_by_queue"]["sendgrid_1"][0].pop("campaign_id")
        with self.assertRaisesRegex(RuntimeError, "missing campaign ID"):
            _validate_dispatch_preview_contract(missing)

        malformed = json.loads(json.dumps(base_preview))
        malformed["preview_id"] = "recontact_cold"
        malformed["campaign_id"] = "recontact_cold"
        malformed["plan_rows_by_queue"]["sendgrid_1"][0]["campaign_id"] = "recontact_cold"
        with self.assertRaisesRegex(RuntimeError, "malformed campaign ID"):
            _validate_dispatch_preview_contract(malformed)

        mixed = json.loads(json.dumps(base_preview))
        mixed["plan_rows_by_queue"]["sendgrid_1"][0]["campaign_id"] = "dispatch_preview_20260831_120001_feedface"
        with self.assertRaisesRegex(RuntimeError, "mixed or mismatched campaign ID"):
            _validate_dispatch_preview_contract(mixed)

        corrupted_kind = json.loads(json.dumps(base_preview))
        corrupted_kind["dispatch_source_kind"] = "safer_recontact"
        with self.assertRaisesRegex(RuntimeError, "source classification does not match"):
            _validate_dispatch_preview_contract(corrupted_kind)

    def test_fresh_cold_preview_contract_blocks_skipped_math_mismatch(self) -> None:
        preview = {
            "campaign_type": "cold",
            "history_policy_version": 2,
            "prior_success_policy": "block_global",
            "dispatch_source_mode": "triaged_keep",
            "dispatch_source_path": "/tmp/leads_triaged_keep.csv",
            "preview_id": "preview_bad_math",
            "private_jc_planned_count": 1,
            "sendgrid_planned_count": 1,
            "total_planned_unique_count": 2,
            "total_rows_would_write": 2,
            "duplicate_planned_email_count": 0,
            "skipped_rows": 2,
            "exclusion_reason_counts": {"already_sent": 1},
            "planned_authoritative_sent_overlap_count": 0,
            "plan_rows_by_queue": {
                "private_jc": [planned_row("fresh-private@example.com", "FreshPrivate")],
                "sendgrid_1": [planned_row("fresh-sg@example.com", "FreshSg")],
                "sendgrid_2": [],
                "sendgrid_3": [],
                "sendgrid_4": [],
                "sendgrid_5": [],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "skipped row count does not match skipped reasons"):
            _validate_dispatch_preview_contract(preview)

    def test_warm_confirmation_writes_only_separate_queue_from_previewed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            manifest_path = root / "warm_private_jc_confirmation.json"
            cold_queue = root / "recipients_private_jc.csv"
            write_csv(cold_queue, ["Email"], [])
            subject = "Previewed warm subject"
            body = "Hi Taylor,\n\nPreviewed warm body.\n\nP.S. If you’d rather not hear from me again, just reply unsub."
            write_csv(
                preview_path,
                list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS),
                [{
                    "AuthorName": "Taylor Example",
                    "AuthorEmail": "taylor@example.com",
                    "BookTitleOrProject": "Synthetic Project",
                    "EmailSubject": subject,
                    "EmailBody": body,
                    "NeedSignal": "Synthetic need",
                    "RecommendedService": "Synthetic service",
                    "OutreachAngle": "synthetic angle",
                    "SourceURL": "https://example.com/source",
                    "ContactPath": "mailto:taylor@example.com",
                    "ResearchStatus": "New",
                }],
            )

            result = confirm_warm_private_jc_preview(
                preview_path=preview_path,
                queue_path=queue_path,
                confirmation_path=manifest_path,
                log_paths=[],
                cold_queue_paths=[cold_queue],
                sendgrid_suppressions_path=root / "sendgrid_suppressions.csv",
                suppressed_path=root / "suppressed.csv",
                unsubscribed_path=root / "unsubscribed.csv",
                bad_events_path=root / "events.jsonl",
                lead_ledger_db_path=root / "ledger.sqlite3",
            )
            queued = read_csv_rows(queue_path)

        self.assertTrue(result["warm_private_jc_confirmed"])
        self.assertEqual(1, len(queued))
        self.assertEqual(subject, queued[0]["EmailSubject"])
        self.assertEqual(body, queued[0]["EmailBody"])
        self.assertEqual("warm_private_jc", queued[0]["campaign_type"])

    def test_warm_confirmation_rejects_contact_form_and_does_not_write_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            write_csv(
                preview_path,
                list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS),
                [{
                    "AuthorName": "Taylor Example",
                    "AuthorEmail": "taylor@example.com",
                    "BookTitleOrProject": "Synthetic Project",
                    "EmailSubject": "Subject",
                    "EmailBody": "Body",
                    "NeedSignal": "Need",
                    "RecommendedService": "Service",
                    "OutreachAngle": "Angle",
                    "SourceURL": "https://example.com/source",
                    "ContactPath": "https://example.com/contact",
                    "ResearchStatus": "New",
                }],
            )

            with self.assertRaisesRegex(RuntimeError, "not_direct_email"):
                confirm_warm_private_jc_preview(
                    preview_path=preview_path,
                    queue_path=queue_path,
                    confirmation_path=root / "manifest.json",
                    log_paths=[],
                    cold_queue_paths=[],
                    sendgrid_suppressions_path=root / "sendgrid_suppressions.csv",
                    suppressed_path=root / "suppressed.csv",
                    unsubscribed_path=root / "unsubscribed.csv",
                    bad_events_path=root / "events.jsonl",
                    lead_ledger_db_path=root / "ledger.sqlite3",
                )

            self.assertFalse(queue_path.exists())

    def test_warm_confirmation_rejects_recipient_already_in_cold_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            cold_queue = root / "recipients_private_jc.csv"
            row = {
                "AuthorName": "Taylor Example",
                "AuthorEmail": "taylor@example.com",
                "BookTitleOrProject": "Synthetic Project",
                "EmailSubject": "Subject",
                "EmailBody": "Body",
                "NeedSignal": "Need",
                "RecommendedService": "Service",
                "OutreachAngle": "Angle",
                "SourceURL": "https://example.com/source",
                "ContactPath": "mailto:taylor@example.com",
                "ResearchStatus": "New",
            }
            write_csv(preview_path, list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS), [row])
            write_csv(cold_queue, ["Email"], [{"Email": "taylor@example.com"}])

            with self.assertRaisesRegex(RuntimeError, "already_queued_cold"):
                confirm_warm_private_jc_preview(
                    preview_path=preview_path,
                    queue_path=queue_path,
                    confirmation_path=root / "manifest.json",
                    log_paths=[],
                    cold_queue_paths=[cold_queue],
                    sendgrid_suppressions_path=root / "sendgrid_suppressions.csv",
                    suppressed_path=root / "suppressed.csv",
                    unsubscribed_path=root / "unsubscribed.csv",
                    bad_events_path=root / "events.jsonl",
                    lead_ledger_db_path=root / "ledger.sqlite3",
                )

            self.assertFalse(queue_path.exists())

    def test_warm_confirmation_status_allows_safely_consumed_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            manifest_path = root / "warm_private_jc_confirmation.json"
            rows = []
            for index in range(2):
                email = f"synthetic-{index}@example.com"
                rows.append({
                    "AuthorName": f"Person {index}",
                    "AuthorEmail": email,
                    "BookTitleOrProject": "Synthetic Project",
                    "EmailSubject": f"Subject {index}",
                    "EmailBody": f"Body {index}",
                    "NeedSignal": "Need",
                    "RecommendedService": "Service",
                    "OutreachAngle": "Angle",
                    "SourceURL": "https://example.com/source",
                    "ContactPath": f"mailto:{email}",
                    "ResearchStatus": "New",
                })
            write_csv(preview_path, list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS), rows)
            confirm_warm_private_jc_preview(
                preview_path=preview_path,
                queue_path=queue_path,
                confirmation_path=manifest_path,
                log_paths=[],
                cold_queue_paths=[],
                sendgrid_suppressions_path=root / "sendgrid_suppressions.csv",
                suppressed_path=root / "suppressed.csv",
                unsubscribed_path=root / "unsubscribed.csv",
                bad_events_path=root / "events.jsonl",
                lead_ledger_db_path=root / "ledger.sqlite3",
            )
            queued = read_csv_rows(queue_path)
            write_csv(queue_path, list(important_leads_workflow.WARM_PRIVATE_JC_QUEUE_HEADERS), queued[1:])

            lane = important_leads_workflow.warm_private_jc_lane_status(
                queue_path=queue_path,
                confirmation_path=manifest_path,
            )

        self.assertTrue(lane["confirmed"])
        self.assertTrue(lane["ready"])
        self.assertEqual(1, lane["remaining"])

    def test_warm_confirmation_manifest_stores_protected_payload_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            manifest_path = root / "warm_private_jc_confirmation.json"
            row = {
                "AuthorName": "Taylor Example",
                "AuthorEmail": "taylor@example.com",
                "BookTitleOrProject": "Synthetic Project",
                "EmailSubject": "Previewed subject",
                "EmailBody": "Previewed body",
                "NeedSignal": "Need",
                "RecommendedService": "Service",
                "OutreachAngle": "Angle",
                "SourceURL": "https://example.com/source",
                "ContactPath": "mailto:taylor@example.com",
                "ResearchStatus": "New",
            }
            write_csv(preview_path, list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS), [row])
            confirm_warm_private_jc_preview(
                preview_path=preview_path,
                queue_path=queue_path,
                confirmation_path=manifest_path,
                log_paths=[],
                cold_queue_paths=[],
                sendgrid_suppressions_path=root / "sendgrid_suppressions.csv",
                suppressed_path=root / "suppressed.csv",
                unsubscribed_path=root / "unsubscribed.csv",
                bad_events_path=root / "events.jsonl",
                lead_ledger_db_path=root / "ledger.sqlite3",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        approved = manifest["approved_rows"]["taylor@example.com"]
        self.assertEqual(2, manifest["schema_version"])
        self.assertEqual("Previewed subject", approved["payload"]["EmailSubject"])
        self.assertEqual("Previewed body", approved["payload"]["EmailBody"])
        self.assertEqual(64, len(approved["payload_sha256"]))

    def test_warm_confirmation_rejects_modified_or_unconfirmed_remaining_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            manifest_path = root / "warm_private_jc_confirmation.json"
            preview_rows = []
            for index in range(2):
                email = f"person-{index}@example.com"
                preview_rows.append({
                    "AuthorName": f"Person {index}",
                    "AuthorEmail": email,
                    "BookTitleOrProject": "Synthetic Project",
                    "EmailSubject": f"Subject {index}",
                    "EmailBody": f"Body {index}",
                    "NeedSignal": "Need",
                    "RecommendedService": "Service",
                    "OutreachAngle": "Angle",
                    "SourceURL": "https://example.com/source",
                    "ContactPath": f"mailto:{email}",
                    "ResearchStatus": "New",
                })
            write_csv(preview_path, list(important_leads_workflow.WARM_EMAIL_PREVIEW_HEADERS), preview_rows)
            confirm_warm_private_jc_preview(
                preview_path=preview_path,
                queue_path=queue_path,
                confirmation_path=manifest_path,
                log_paths=[], cold_queue_paths=[],
                sendgrid_suppressions_path=root / "sendgrid_suppressions.csv",
                suppressed_path=root / "suppressed.csv",
                unsubscribed_path=root / "unsubscribed.csv",
                bad_events_path=root / "events.jsonl",
                lead_ledger_db_path=root / "ledger.sqlite3",
            )
            confirmed_rows = read_csv_rows(queue_path)
            remaining = confirmed_rows[1]

            cases = []
            for field in ("EmailSubject", "EmailBody"):
                changed = dict(remaining)
                changed[field] = changed[field] + " changed"
                cases.append((field, [changed], "warm_queue_payload_mismatch"))
            unconfirmed = dict(remaining)
            unconfirmed["Email"] = unconfirmed["AuthorEmail"] = "new@example.com"
            unconfirmed["ContactPath"] = "mailto:new@example.com"
            cases.append(("unconfirmed", [unconfirmed], "warm_queue_unconfirmed_email"))
            cases.append(("duplicate", [remaining, dict(remaining)], "warm_queue_duplicate_email"))
            missing = dict(remaining)
            missing.pop("EmailBody")
            cases.append(("missing", [missing], "warm_queue_missing_required_field"))

            for label, rows, expected_reason in cases:
                with self.subTest(label=label):
                    fieldnames = [field for field in important_leads_workflow.WARM_PRIVATE_JC_QUEUE_HEADERS if any(field in row for row in rows)]
                    write_csv(queue_path, fieldnames, rows)
                    lane = important_leads_workflow.warm_private_jc_lane_status(
                        queue_path=queue_path,
                        confirmation_path=manifest_path,
                    )
                    self.assertFalse(lane["confirmed"])
                    self.assertFalse(lane["ready"])
                    self.assertEqual(expected_reason, lane["integrity_reason"])

    def test_old_warm_confirmation_without_row_hashes_requires_reconfirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "warm_email_preview.csv"
            queue_path = root / "recipients_private_jc_warm.csv"
            manifest_path = root / "warm_private_jc_confirmation.json"
            preview_path.write_text("AuthorEmail\nsynthetic@example.com\n", encoding="utf-8")
            queue_path.write_text("Email\nsynthetic@example.com\n", encoding="utf-8")
            manifest_path.write_text(json.dumps({
                "schema_version": 1,
                "confirmed": True,
                "source_path": str(preview_path),
                "source_sha256": important_leads_workflow._file_sha256(preview_path),
                "row_count": 1,
            }), encoding="utf-8")

            lane = important_leads_workflow.warm_private_jc_lane_status(
                queue_path=queue_path,
                confirmation_path=manifest_path,
            )

        self.assertFalse(lane["confirmed"])
        self.assertFalse(lane["ready"])
        self.assertEqual("warm_confirmation_manifest_upgrade_required", lane["integrity_reason"])

    def test_cold_queue_rebuild_set_excludes_warm_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            names = {path.name for path in default_queue_paths(Path(tmpdir))}

        self.assertNotIn("recipients_private_jc_warm.csv", names)
        self.assertEqual(
            {
                "recipients_private_jc.csv",
                "recipients_sendgrid_1.csv",
                "recipients_sendgrid_2.csv",
                "recipients_sendgrid_3.csv",
                "recipients_sendgrid_4.csv",
                "recipients_sendgrid_5.csv",
            },
            names,
        )


if __name__ == "__main__":
    unittest.main()
