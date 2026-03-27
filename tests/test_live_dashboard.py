from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import live_dashboard


class LiveDashboardTests(unittest.TestCase):
    def test_shard_block_when_senders_active(self) -> None:
        payload = live_dashboard.ShardLeadsPayload(
            cleaned_filename="cleaned_input.csv",
            shard_count=5,
            strategy="domain_balanced",
        )
        active_profiles = [
            SimpleNamespace(name="sendgrid_annette", runtime_state="running"),
            SimpleNamespace(name="sendgrid_jodi", runtime_state="cooldown"),
        ]

        with patch.object(live_dashboard.runtime_control, "list_active_sender_snapshots", return_value=active_profiles), patch.object(
            live_dashboard,
            "shard_cleaned_leads",
        ) as shard_cleaned_leads:
            response = live_dashboard.shard_leads(payload)

        body = json.loads(response.body)
        self.assertEqual(409, response.status_code)
        self.assertFalse(body["ok"])
        self.assertEqual("senders_active", body["error"])
        self.assertEqual(["sendgrid_annette", "sendgrid_jodi"], body["active_profiles"])
        self.assertEqual(
            {
                "sendgrid_annette": "running",
                "sendgrid_jodi": "cooldown",
            },
            body["states"],
        )
        shard_cleaned_leads.assert_not_called()


if __name__ == "__main__":
    unittest.main()
