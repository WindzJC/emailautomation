import csv
import tempfile
import unittest
from pathlib import Path

import important_leads_workflow


def _write_queue(path: Path, emails: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName"])
        writer.writeheader()
        for email in emails:
            writer.writerow({"Email": email, "FirstName": "A"})


class UntouchedQueueGuardTests(unittest.TestCase):
    def test_pending_queue_with_no_planned_rows_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            jc = Path(tmpdir) / "recipients_private_jc.csv"
            sg = Path(tmpdir) / "recipients_sendgrid_1.csv"
            _write_queue(jc, [])
            _write_queue(sg, ["pending@example.com"])

            existing = important_leads_workflow.assert_dispatch_destination_queues_empty([jc, sg], [5, 0])

            self.assertEqual([], existing[jc])
            self.assertEqual(1, len(existing[sg]))

    def test_pending_queue_with_planned_rows_still_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            jc = Path(tmpdir) / "recipients_private_jc.csv"
            sg = Path(tmpdir) / "recipients_sendgrid_1.csv"
            _write_queue(jc, ["pending@example.com"])
            _write_queue(sg, [])

            with self.assertRaisesRegex(RuntimeError, "recipient queues are not empty"):
                important_leads_workflow.assert_dispatch_destination_queues_empty([jc, sg], [5, 0])

    def test_without_planned_counts_every_queue_must_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            jc = Path(tmpdir) / "recipients_private_jc.csv"
            sg = Path(tmpdir) / "recipients_sendgrid_1.csv"
            _write_queue(jc, [])
            _write_queue(sg, ["pending@example.com"])

            with self.assertRaisesRegex(RuntimeError, "recipient queues are not empty"):
                important_leads_workflow.assert_dispatch_destination_queues_empty([jc, sg])
