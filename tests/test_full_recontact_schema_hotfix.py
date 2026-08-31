from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import important_leads_workflow as workflow


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=headers,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


class FullRecontactSchemaHotfixTests(unittest.TestCase):
    def _make_preview(
        self,
        tmp: Path,
        rows: list[dict[str, str]],
        *,
        campaign_type: str,
        source_mode: str,
        safer: bool = False,
    ):
        headers = [
            "FullName",
            "FirstName",
            "Email",
            "AuthorName",
            "BookTitle",
            "Status",
        ]

        master_path = tmp / "leads.csv"

        triaged_path = (
            tmp / "leads_safer_recontact_not_seen_active_history.csv"
            if safer
            else tmp / "leads_triaged_keep.csv"
        )

        rejected_path = tmp / "leads_rejected.csv"

        write_csv(master_path, headers, rows)
        write_csv(triaged_path, headers, rows)
        write_csv(rejected_path, headers, [])

        jc_queue = tmp / "recipients_private_jc.csv"

        sg_queues = [
            tmp / f"recipients_sendgrid_{index}.csv"
            for index in range(1, 6)
        ]

        logs = [
            tmp / "private_jc_log.csv",
            *[
                tmp / f"sendgrid_{index}_log.csv"
                for index in range(1, 6)
            ],
        ]

        for path in [jc_queue, *sg_queues]:
            write_csv(
                path,
                ["Email", "FirstName"],
                [],
            )

        for path in logs:
            write_csv(
                path,
                ["Email", "Status"],
                [],
            )

        suppressed = tmp / "suppressed.csv"
        unsubscribed = tmp / "unsubscribed.csv"
        sendgrid_suppressions = tmp / "sendgrid_suppressions.csv"
        sendgrid_events = tmp / "sendgrid_events.jsonl"

        write_csv(suppressed, ["Email"], [])
        write_csv(unsubscribed, ["Email"], [])

        write_csv(
            sendgrid_suppressions,
            [
                "email",
                "status",
                "code",
                "reason",
                "last_seen_utc",
                "is_permanent",
                "ttl_until_utc",
            ],
            [],
        )

        sendgrid_events.write_text(
            "",
            encoding="utf-8",
        )

        preview_dir = tmp / "previews"

        preview = workflow.preview_dispatch_master_leads(
            master_path=master_path,
            triaged_keep_path=triaged_path,
            rejected_path=rejected_path,
            dispatch_source_mode=source_mode,
            jc_queue_path=jc_queue,
            sendgrid_queue_paths=sg_queues,
            jc_log_path=logs[0],
            sendgrid_log_paths=logs[1:],
            suppressed_path=suppressed,
            unsubscribed_path=unsubscribed,
            sendgrid_suppressions_path=sendgrid_suppressions,
            sendgrid_events_path=sendgrid_events,
            lead_ledger_db_path=tmp / "lead_ledger.sqlite3",
            campaign_type=campaign_type,
            preview_dir=preview_dir,
        )

        return {
            "preview": preview,
            "preview_dir": preview_dir,
            "jc_queue": jc_queue,
            "sg_queues": sg_queues,
        }

    def test_required_fields_are_campaign_specific(self) -> None:
        row = {
            "Email": "jane@example.com",
            "FirstName": "",
            "AuthorEmail": "",
            "AuthorName": "Jane Writer",
            "BookTitle": "",
        }

        self.assertEqual(
            [],
            workflow._missing_required_dispatch_fields(
                row,
                full_recontact=True,
            ),
        )

        self.assertEqual(
            ["FirstName", "AuthorEmail", "BookTitle"],
            workflow._missing_required_dispatch_fields(row),
        )

        missing_author = dict(row)
        missing_author["AuthorName"] = ""

        self.assertEqual(
            ["AuthorName"],
            workflow._missing_required_dispatch_fields(
                missing_author,
                full_recontact=True,
            ),
        )

    def test_full_recontact_accepts_live_shaped_rows_without_fake_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            rows = [
                {
                    "FullName": "Jane Writer",
                    "FirstName": "",
                    "Email": "jane@example.com",
                    "AuthorName": "Jane Writer",
                    "BookTitle": "",
                    "Status": "KEEP",
                },
                {
                    "FullName": "Reader Writer",
                    "FirstName": "Reader",
                    "Email": "reader@example.com",
                    "AuthorName": "Reader Writer",
                    "BookTitle": "",
                    "Status": "KEEP",
                },
                {
                    "FullName": "Titled Writer",
                    "FirstName": "Titled",
                    "Email": "titled@example.com",
                    "AuthorName": "Titled Writer",
                    "BookTitle": "Real Book",
                    "Status": "KEEP",
                },
            ]

            fixture = self._make_preview(
                tmp,
                rows,
                campaign_type="recontact_cold",
                source_mode="cleaned",
            )

            preview = fixture["preview"]

            self.assertTrue(
                preview["full_recontact_sendgrid_only"]
            )

            self.assertEqual(
                0,
                preview["rows_to_add_private_jc"],
            )

            self.assertEqual(
                3,
                preview["rows_to_add_sendgrid"],
            )

            self.assertEqual(
                3,
                preview["total_planned_unique_count"],
            )

            self.assertEqual(
                0,
                preview["duplicate_planned_email_count"],
            )

            self.assertEqual(
                0,
                int(
                    preview["exclusion_reason_counts"].get(
                        "missing_required_dispatch_field",
                        0,
                    )
                ),
            )

            planned = [
                row
                for key, queue_rows
                in preview["plan_rows_by_queue"].items()
                if key.startswith("sendgrid_")
                for row in queue_rows
            ]

            self.assertEqual(
                {
                    "jane@example.com",
                    "reader@example.com",
                    "titled@example.com",
                },
                {row["Email"] for row in planned},
            )

            by_email = {
                row["Email"]: row
                for row in planned
            }

            # No title is invented.
            self.assertEqual(
                "",
                by_email["jane@example.com"].get(
                    "BookTitle",
                    "",
                ),
            )

            self.assertEqual(
                "",
                by_email["reader@example.com"].get(
                    "BookTitle",
                    "",
                ),
            )

            # A real title is preserved.
            self.assertEqual(
                "Real Book",
                by_email["titled@example.com"].get(
                    "BookTitle",
                    "",
                ),
            )

            # AuthorEmail is not fabricated merely to satisfy
            # an obsolete dispatch gate. Email remains canonical.
            self.assertEqual(
                "jane@example.com",
                by_email["jane@example.com"]["Email"],
            )

    def test_full_recontact_preview_passes_confirm_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            rows = [
                {
                    "FullName": "Jane Writer",
                    "FirstName": "",
                    "Email": "jane@example.com",
                    "AuthorName": "Jane Writer",
                    "BookTitle": "",
                    "Status": "KEEP",
                },
                {
                    "FullName": "Reader Writer",
                    "FirstName": "Reader",
                    "Email": "reader@example.com",
                    "AuthorName": "Reader Writer",
                    "BookTitle": "",
                    "Status": "KEEP",
                },
            ]

            fixture = self._make_preview(
                tmp,
                rows,
                campaign_type="recontact_cold",
                source_mode="cleaned",
            )

            preview = fixture["preview"]

            confirmed = workflow.confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=tmp / "backups",
                report_dir=tmp / "reports",
                persist_state=False,
                preview_dir=fixture["preview_dir"],
            )

            self.assertEqual(
                preview["campaign_id"],
                confirmed["campaign_id"],
            )

            self.assertEqual(
                [],
                read_csv(fixture["jc_queue"]),
            )

            final_sendgrid_rows = [
                row
                for path in fixture["sg_queues"]
                for row in read_csv(path)
            ]

            self.assertEqual(
                2,
                len(final_sendgrid_rows),
            )

            self.assertEqual(
                {
                    "jane@example.com",
                    "reader@example.com",
                },
                {
                    row["Email"]
                    for row in final_sendgrid_rows
                },
            )

            self.assertEqual(
                {preview["campaign_id"]},
                {
                    row["campaign_id"]
                    for row in final_sendgrid_rows
                },
            )

    def test_fresh_cold_remains_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            rows = [
                {
                    "FullName": "Fresh Writer",
                    "FirstName": "Fresh",
                    "Email": "fresh@example.com",
                    "AuthorName": "Fresh Writer",
                    "BookTitle": "",
                    "Status": "KEEP",
                },
            ]

            fixture = self._make_preview(
                tmp,
                rows,
                campaign_type="cold",
                source_mode="triaged_keep",
            )

            preview = fixture["preview"]

            self.assertEqual(
                0,
                preview["total_planned_unique_count"],
            )

            self.assertEqual(
                1,
                preview["exclusion_reason_counts"][
                    "missing_required_dispatch_field"
                ],
            )

    def test_safer_recontact_remains_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            rows = [
                {
                    "FullName": "Safer Writer",
                    "FirstName": "Safer",
                    "Email": "safer@example.com",
                    "AuthorName": "Safer Writer",
                    "BookTitle": "",
                    "Status": "KEEP",
                },
            ]

            fixture = self._make_preview(
                tmp,
                rows,
                campaign_type="recontact_cold",
                source_mode="triaged_keep",
                safer=True,
            )

            preview = fixture["preview"]

            self.assertFalse(
                preview["full_recontact_sendgrid_only"]
            )

            self.assertEqual(
                "safer_recontact",
                preview["dispatch_source_kind"],
            )

            self.assertEqual(
                0,
                preview["total_planned_unique_count"],
            )

            self.assertEqual(
                1,
                preview["exclusion_reason_counts"][
                    "missing_required_dispatch_field"
                ],
            )

    def test_frontend_uses_same_full_recontact_contract(
        self,
    ) -> None:
        app_js = (
            Path(workflow.__file__).resolve().parent
            / "web_dashboard"
            / "app.js"
        ).read_text(
            encoding="utf-8",
        )

        self.assertIn(
            'const FULL_RECONTACT_REQUIRED_DISPATCH_FIELDS = '
            '["Email", "AuthorName"];',
            app_js,
        )

        self.assertIn(
            "preview?.full_recontact_sendgrid_only",
            app_js,
        )

        self.assertIn(
            "? FULL_RECONTACT_REQUIRED_DISPATCH_FIELDS",
            app_js,
        )

        # The original strict Fresh Cold / Safer contract remains.
        self.assertIn(
            'const REQUIRED_DISPATCH_FIELDS = '
            '["Email", "FirstName", "AuthorEmail", '
            '"AuthorName", "BookTitle"];',
            app_js,
        )


if __name__ == "__main__":
    unittest.main()
