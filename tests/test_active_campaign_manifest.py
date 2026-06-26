from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.rebuild_recipient_queues as rebuild_tool
import important_leads_workflow


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class ActiveCampaignManifestTests(unittest.TestCase):
    def test_queue_safety_uses_manifest_checked_path_instead_of_stale_important_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            app_root = tmp / "app"
            important = app_root / "_important"
            state_dir = app_root / "data" / "state"
            archive = state_dir / "backups" / "staged_batches" / "dispatch_current"
            shards = [app_root / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            rows = [
                {
                    "Email": "current@example.test",
                    "FirstName": "Current",
                    "AuthorEmail": "current@example.test",
                    "AuthorName": "Current Writer",
                    "BookTitle": "Current Book",
                }
            ]
            write_csv(
                important / "leads.csv",
                headers,
                [
                    {
                        "Email": "stale@example.test",
                        "FirstName": "Stale",
                        "AuthorEmail": "stale@example.test",
                        "AuthorName": "Stale Writer",
                        "BookTitle": "Stale Book",
                    }
                ],
            )
            write_csv(important / "leads_triaged_keep.csv", headers, rows)
            write_csv(archive / "leads.csv", headers, rows)
            write_csv(archive / "leads_triaged_reject.csv", headers, [])
            for index, path in enumerate(shards):
                write_csv(path, headers, rows if index == 0 else [])

            with (
                patch.object(rebuild_tool.settings, "APP_ROOT", app_root),
                patch.object(rebuild_tool.settings, "STATE_DIR", state_dir),
                patch.object(rebuild_tool.settings, "BACKUPS_DIR", state_dir / "backups"),
            ):
                rebuild_tool.write_active_campaign_manifest(
                    checked_path=archive / "leads.csv",
                    triaged_keep_path=important / "leads_triaged_keep.csv",
                    triaged_reject_path=archive / "leads_triaged_reject.csv",
                    intended_source_path=important / "leads_triaged_keep.csv",
                    state_dir=state_dir,
                )
                report = rebuild_tool.build_queue_safety_report(shard_paths=shards)

        self.assertTrue(report["safe"])
        self.assertEqual("active_campaign_manifest", report["source_resolution"])
        self.assertEqual(str(archive / "leads.csv"), report["checked_path"])
        self.assertEqual(str(important / "leads_triaged_keep.csv"), report["intended_source_path"])
        self.assertEqual(0, report["outside_checked_output_count"])

    def test_sendgrid_rebuild_with_explicit_paths_updates_active_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            app_root = tmp / "app"
            state_dir = app_root / "data" / "state"
            source = app_root / "_important" / "leads_triaged_keep.csv"
            checked = tmp / "archive" / "leads.csv"
            reject = tmp / "archive" / "leads_triaged_reject.csv"
            shards = [app_root / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            rows = [
                {
                    "Email": "writer@example.test",
                    "FirstName": "Writer",
                    "AuthorEmail": "writer@example.test",
                    "AuthorName": "Writer Person",
                    "BookTitle": "Writer Book",
                }
            ]
            write_csv(source, headers, rows)
            write_csv(checked, headers, rows)
            write_csv(reject, headers, [])
            for path in shards:
                write_csv(path, headers, [])

            with (
                patch.object(rebuild_tool.settings, "APP_ROOT", app_root),
                patch.object(rebuild_tool.settings, "STATE_DIR", state_dir),
                patch.object(rebuild_tool.settings, "BACKUPS_DIR", state_dir / "backups"),
                patch.object(rebuild_tool, "DEFAULT_LIVE_QUEUE_DIR", app_root),
            ):
                result = rebuild_tool.rebuild_sendgrid_recipient_queues(
                    intended_source_path=source,
                    checked_path=checked,
                    triaged_keep_path=source,
                    triaged_reject_path=reject,
                    shard_paths=shards,
                    archive_root=state_dir / "backups" / "queue_rebuild",
                    apply=True,
                )
                manifest = json.loads(rebuild_tool.active_campaign_manifest_path(state_dir).read_text(encoding="utf-8"))

        self.assertTrue(result["after"]["safe"])
        self.assertEqual(str(checked), manifest["checked_path"])
        self.assertEqual(str(source), manifest["intended_source_path"])
        self.assertEqual(1, manifest["files"]["intended_source"]["unique_email_count"])

    def test_sendgrid_rebuild_derives_author_email_and_excludes_sent_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "leads_triaged_keep.csv"
            checked = tmp / "leads.csv"
            reject = tmp / "leads_triaged_reject.csv"
            log = tmp / "sendgrid_annette_log.csv"
            shards = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            source_headers = ["Email", "FirstName", "AuthorName", "BookTitle"]
            rows = [
                {"Email": "sent@example.test", "FirstName": "Sent", "AuthorName": "Sent Writer", "BookTitle": "Sent Book"},
                {"Email": "new@example.test", "FirstName": "New", "AuthorName": "New Writer", "BookTitle": "New Book"},
            ]
            write_csv(source, source_headers, rows)
            write_csv(checked, source_headers, rows)
            write_csv(reject, source_headers, [])
            write_csv(log, ["Email", "Status"], [{"Email": "sent@example.test", "Status": "SENT"}])
            for path in shards:
                write_csv(path, list(rebuild_tool.SENDGRID_REQUIRED_HEADERS), [])

            result = rebuild_tool.rebuild_sendgrid_recipient_queues(
                intended_source_path=source,
                checked_path=checked,
                triaged_keep_path=source,
                triaged_reject_path=reject,
                shard_paths=shards,
                sendgrid_log_paths=[log],
                apply=False,
            )
            planned_root = Path(str(result["quarantine_path"])).parent
            planned_rows = []
            for path in sorted(planned_root.glob("recipients_sendgrid_*.csv")):
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    planned_rows.extend(csv.DictReader(handle))

        self.assertEqual(1, result["included_rows"])
        self.assertEqual(1, result["excluded_by_reason"]["sendgrid_already_sent"])
        self.assertEqual(["new@example.test"], [row["Email"] for row in planned_rows])
        self.assertEqual("new@example.test", planned_rows[0]["AuthorEmail"])
        self.assertTrue(result["after"]["safe"])

    def test_sendgrid_live_rebuild_aborts_without_overwriting_when_planned_after_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "leads_triaged_keep.csv"
            checked = tmp / "leads.csv"
            reject = tmp / "leads_triaged_reject.csv"
            shards = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            rows = [{"Email": "new@example.test", "FirstName": "New", "AuthorEmail": "new@example.test", "AuthorName": "New Writer", "BookTitle": "New Book"}]
            write_csv(source, headers, rows)
            write_csv(checked, headers, rows)
            write_csv(reject, headers, [])
            for path in shards:
                write_csv(path, headers, [{"Email": "existing@example.test", "FirstName": "Existing", "AuthorEmail": "existing@example.test", "AuthorName": "Existing Writer", "BookTitle": "Existing Book"}])
            before = {path: path.read_text(encoding="utf-8") for path in shards}

            with patch.object(
                rebuild_tool,
                "build_queue_safety_report",
                side_effect=[
                    {"safe": True, "unsafe_reasons": []},
                    {"safe": False, "unsafe_reasons": ["PLANNED_UNSAFE"]},
                ],
            ):
                with self.assertRaisesRegex(RuntimeError, "planned queue safety is unsafe"):
                    rebuild_tool.rebuild_sendgrid_recipient_queues(
                        intended_source_path=source,
                        checked_path=checked,
                        triaged_keep_path=source,
                        triaged_reject_path=reject,
                        shard_paths=shards,
                        archive_root=tmp / "archive",
                        apply=True,
                    )
            after = {path: path.read_text(encoding="utf-8") for path in shards}

        self.assertEqual(before, after)

    def test_confirm_dispatch_writes_active_manifest_for_archived_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master = tmp / "leads.csv"
            keep = tmp / "leads_triaged_keep.csv"
            reject = tmp / "leads_triaged_reject.csv"
            preview_dir = tmp / "previews"
            report_dir = tmp / "state"
            backup_root = tmp / "backups"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            logs = [tmp / "private_jc_log.csv", *[tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            rows = [
                {
                    "Email": "confirm@example.test",
                    "FirstName": "Confirm",
                    "AuthorEmail": "confirm@example.test",
                    "AuthorName": "Confirm Writer",
                    "BookTitle": "Confirm Book",
                }
            ]
            write_csv(master, headers, rows)
            write_csv(keep, headers, rows)
            write_csv(reject, headers, [])
            write_csv(keep.with_name("leads_triaged_quarantine.csv"), headers, [])
            write_csv(jc_queue, headers, [])
            for path in sg_queues:
                write_csv(path, headers, [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])

            preview = important_leads_workflow.preview_dispatch_master_leads(
                master_path=master,
                rejected_path=tmp / "leads_rejected.csv",
                triaged_keep_path=keep,
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
            report = important_leads_workflow.confirm_dispatch_preview(
                preview["preview_id"],
                require_stopped=False,
                backup_root=backup_root,
                report_dir=report_dir,
                persist_state=False,
                preview_dir=preview_dir,
            )
            manifest_path = Path(str(report["active_campaign_manifest_path"]))
            manifest_exists = manifest_path.exists()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            checked_exists = Path(manifest["checked_path"]).exists()
            keep_exists = Path(manifest["triaged_keep_path"]).exists()

        self.assertTrue(manifest_exists)
        self.assertEqual("confirm_dispatch", manifest["source"])
        self.assertTrue(checked_exists)
        self.assertTrue(keep_exists)
        self.assertIn("staged_batches", manifest["checked_path"])

    def test_confirm_dispatch_aborts_unsafe_planned_queues_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            master = tmp / "leads.csv"
            keep = tmp / "leads_triaged_keep.csv"
            reject = tmp / "leads_triaged_reject.csv"
            preview_dir = tmp / "previews"
            jc_queue = tmp / "recipients_private_jc.csv"
            sg_queues = [tmp / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)]
            logs = [tmp / "private_jc_log.csv", *[tmp / f"sendgrid_{index}_log.csv" for index in range(1, 6)]]
            headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
            keep_rows = [
                {
                    "Email": "unsafe@example.test",
                    "FirstName": "Unsafe",
                    "AuthorEmail": "unsafe@example.test",
                    "AuthorName": "Unsafe Writer",
                    "BookTitle": "Unsafe Book",
                }
            ]
            write_csv(master, headers, [])
            write_csv(keep, headers, keep_rows)
            write_csv(reject, headers, [])
            write_csv(jc_queue, headers, [{"Email": "existing@example.test", "FirstName": "Existing", "AuthorEmail": "existing@example.test", "AuthorName": "Existing Writer", "BookTitle": "Existing Book"}])
            for path in sg_queues:
                write_csv(path, headers, [])
            for path in logs:
                write_csv(path, ["Email", "Status"], [])
            before = {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]}

            preview = important_leads_workflow.preview_dispatch_master_leads(
                master_path=master,
                rejected_path=tmp / "leads_rejected.csv",
                triaged_keep_path=keep,
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
            with self.assertRaisesRegex(RuntimeError, "planned queue safety is unsafe"):
                important_leads_workflow.confirm_dispatch_preview(
                    preview["preview_id"],
                    require_stopped=False,
                    backup_root=tmp / "backups",
                    report_dir=tmp / "state",
                    persist_state=False,
                    preview_dir=preview_dir,
                )
            after = {path: path.read_text(encoding="utf-8") for path in [jc_queue, *sg_queues]}

        self.assertEqual(before, after)
