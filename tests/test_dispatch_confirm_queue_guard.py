import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import important_leads_workflow
import live_dashboard


QUEUE_KEYS = (
    "private_jc",
    "sendgrid_1",
    "sendgrid_2",
    "sendgrid_3",
    "sendgrid_4",
    "sendgrid_5",
)


def write_queue(path: Path, rows: list[tuple[str, str]]) -> None:
    text = "Email,FirstName\n"
    for email, first_name in rows:
        text += f"{email},{first_name}\n"
    path.write_text(text, encoding="utf-8")


class DispatchConfirmQueueGuardTests(unittest.TestCase):
    def test_locked_queue_guard_rejects_nonempty_queue_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            queues = [
                root / "recipients_private_jc.csv",
                *[
                    root / f"recipients_sendgrid_{index}.csv"
                    for index in range(1, 6)
                ],
            ]

            for path in queues:
                write_queue(path, [])

            write_queue(
                queues[2],
                [("unfinished@example.com", "Unfinished")],
            )

            before = {path: path.read_bytes() for path in queues}

            with self.assertRaisesRegex(
                RuntimeError,
                "recipient queues are not empty",
            ):
                important_leads_workflow.assert_dispatch_destination_queues_empty(
                    queues
                )

            after = {path: path.read_bytes() for path in queues}
            self.assertEqual(before, after)

    def test_queue_guard_allows_header_only_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            queues = [
                root / "recipients_private_jc.csv",
                *[
                    root / f"recipients_sendgrid_{index}.csv"
                    for index in range(1, 6)
                ],
            ]

            for path in queues:
                write_queue(path, [])

            result = (
                important_leads_workflow
                .assert_dispatch_destination_queues_empty(queues)
            )

            self.assertEqual(set(queues), set(result))
            self.assertTrue(all(rows == [] for rows in result.values()))

    def test_direct_confirm_api_returns_409_and_does_not_start_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            queue_paths = {
                "private_jc": root / "recipients_private_jc.csv",
                **{
                    f"sendgrid_{index}":
                        root / f"recipients_sendgrid_{index}.csv"
                    for index in range(1, 6)
                },
            }

            for path in queue_paths.values():
                write_queue(path, [])

            write_queue(
                queue_paths["sendgrid_3"],
                [("unfinished@example.com", "Unfinished")],
            )

            before = {
                key: path.read_bytes()
                for key, path in queue_paths.items()
            }

            payload = live_dashboard.ImportantLeadDispatchPayload(
                preview_id="dispatch_preview_nonempty_guard",
                campaign_type="cold",
                dispatch_source_mode="triaged_keep",
                dispatch_cap="all",
            )

            preview = {
                "preview_id": payload.preview_id,
                "campaign_type": "cold",
                "dispatch_source_mode": "triaged_keep",
                "dispatch_source_path": "",
                "dispatch_cap": "all",
                "queue_paths": {
                    key: str(path)
                    for key, path in queue_paths.items()
                },
                "recontact_recency": {},
            }

            with (
                patch.object(
                    live_dashboard,
                    "_build_live_snapshot",
                    return_value={},
                ),
                patch.object(
                    live_dashboard,
                    "_dispatch_preflight_block_response",
                    return_value=None,
                ),
                patch.object(
                    live_dashboard,
                    "validate_dispatch_preview",
                    return_value=preview,
                ),
                patch.object(
                    live_dashboard,
                    "_combined_leads_status",
                    return_value={"dispatch_source_path": ""},
                ),
                patch.object(
                    live_dashboard,
                    "_start_important_dispatch_job",
                ) as start_job,
            ):
                response = live_dashboard._dispatch_confirm_response(payload)

            body = json.loads(response.body)

            self.assertEqual(409, response.status_code)
            self.assertFalse(body["ok"])
            self.assertTrue(body["blocked"])
            self.assertEqual(
                "recipient_queues_not_empty",
                body["error"],
            )
            self.assertEqual(
                "recipient_queues_not_empty",
                body["reason"],
            )
            self.assertIn(
                "recipient queues are not empty",
                body["message"],
            )
            start_job.assert_not_called()

            after = {
                key: path.read_bytes()
                for key, path in queue_paths.items()
            }
            self.assertEqual(before, after)


    def test_core_confirm_refuses_queue_populated_after_preview_without_consuming_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            master_path = root / "leads.csv"
            rejected_path = root / "leads_rejected.csv"
            triaged_keep_path = root / "leads_triaged_keep.csv"
            preview_dir = root / "previews"
            report_dir = root / "reports"
            backup_root = root / "backups"

            queues = [
                root / "recipients_private_jc.csv",
                *[
                    root / f"recipients_sendgrid_{index}.csv"
                    for index in range(1, 6)
                ],
            ]

            logs = [
                root / "private_jc_log.csv",
                *[
                    root / f"sendgrid_{index}_log.csv"
                    for index in range(1, 6)
                ],
            ]

            sendgrid_suppressions = root / "sendgrid_suppressions.csv"
            suppressed = root / "suppressed.csv"
            unsubscribed = root / "unsubscribed.csv"

            master_path.write_text(
                "FullName,FirstName,Email\n"
                "Alpha Person,Alpha,alpha@example.com\n",
                encoding="utf-8",
            )
            rejected_path.write_text(
                "FullName,FirstName,Email,reject_code\n",
                encoding="utf-8",
            )
            triaged_keep_path.write_text(
                "FullName,FirstName,Email,Status\n"
                "Alpha Person,Alpha,alpha@example.com,KEEP\n",
                encoding="utf-8",
            )

            for queue in queues:
                write_queue(queue, [])

            for log in logs:
                log.write_text(
                    "Email,Status\n",
                    encoding="utf-8",
                )

            sendgrid_suppressions.write_text(
                "email,state,type\n",
                encoding="utf-8",
            )
            suppressed.write_text(
                "Email\n",
                encoding="utf-8",
            )
            unsubscribed.write_text(
                "Email\n",
                encoding="utf-8",
            )

            preview = important_leads_workflow.preview_dispatch_master_leads(
                master_path=master_path,
                triaged_keep_path=triaged_keep_path,
                rejected_path=rejected_path,
                dispatch_source_mode="triaged_keep",
                jc_queue_path=queues[0],
                sendgrid_queue_paths=queues[1:],
                jc_log_path=logs[0],
                sendgrid_log_paths=logs[1:],
                sendgrid_suppressions_path=sendgrid_suppressions,
                suppressed_path=suppressed,
                unsubscribed_path=unsubscribed,
                lead_ledger_db_path=root / "lead_ledger.sqlite3",
                preview_dir=preview_dir,
            )

            self.assertEqual(
                "previewed",
                important_leads_workflow.load_dispatch_preview(
                    preview["preview_id"],
                    preview_dir=preview_dir,
                )["status"],
            )

            # Simulate unfinished work appearing after Preview but before
            # Confirm. The authoritative under-lock guard must refuse to
            # replace any destination queue.
            write_queue(
                queues[3],
                [("unfinished@example.com", "Unfinished")],
            )

            before = {
                queue: queue.read_bytes()
                for queue in queues
            }

            # Normally the changed queue is caught even earlier by the
            # preview dependency fingerprint. Mock only that earlier validator
            # so this regression specifically exercises the authoritative
            # under-lock destination-queue guard inside confirmation.
            with (
                patch.object(
                    important_leads_workflow,
                    "validate_dispatch_preview",
                    return_value=preview,
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "recipient queues are not empty",
                ),
            ):
                important_leads_workflow.confirm_dispatch_preview(
                    preview["preview_id"],
                    require_stopped=False,
                    backup_root=backup_root,
                    report_dir=report_dir,
                    persist_state=False,
                    preview_dir=preview_dir,
                )

            after = {
                queue: queue.read_bytes()
                for queue in queues
            }

            # All six queues remain byte-for-byte unchanged.
            self.assertEqual(before, after)

            # Refusal must not consume or invalidate the preview.
            current_preview = (
                important_leads_workflow.load_dispatch_preview(
                    preview["preview_id"],
                    preview_dir=preview_dir,
                )
            )
            self.assertEqual(
                "previewed",
                current_preview["status"],
            )
            self.assertFalse(
                current_preview.get("confirmed_run_id")
            )

            # A refused confirmation must not create a confirmation summary.
            confirmed_dir = report_dir / "dispatch_confirmed"
            self.assertFalse(
                confirmed_dir.exists()
                and any(confirmed_dir.glob("*.json"))
            )

if __name__ == "__main__":
    unittest.main()
