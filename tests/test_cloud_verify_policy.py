from __future__ import annotations

import unittest

from tools.cloud_verify_policy import unsafe_runtime_blockers


class CloudVerifyPolicyTests(unittest.TestCase):
    def test_dashboard_and_tunnel_are_allowed(self) -> None:
        blockers = [
            "101 dashboard: python -m uvicorn live_dashboard:app",
            "102 tunnel: /usr/bin/cloudflared tunnel run astra",
        ]

        self.assertEqual(unsafe_runtime_blockers(blockers), [])

    def test_sender_and_migration_remain_blocked(self) -> None:
        blockers = [
            "101 dashboard: python -m uvicorn live_dashboard:app",
            "201 sender: python send_shard.py --profile private_jc",
            "202 migration: python tools/mac_runtime_migration.py",
            "102 tunnel: /usr/bin/cloudflared tunnel run astra",
        ]

        self.assertEqual(
            unsafe_runtime_blockers(blockers),
            [
                "201 sender: python send_shard.py --profile private_jc",
                "202 migration: python tools/mac_runtime_migration.py",
            ],
        )

    def test_unknown_category_remains_blocked(self) -> None:
        blocker = "303 unknown: unrecognized-process"

        self.assertEqual(
            unsafe_runtime_blockers([blocker]),
            [blocker],
        )

    def test_malformed_entries_fail_closed(self) -> None:
        malformed = [
            "",
            "dashboard",
            "dashboard: uvicorn",
            "123 unknown-format",
        ]

        for blocker in malformed:
            with self.subTest(blocker=blocker):
                with self.assertRaises(ValueError):
                    unsafe_runtime_blockers([blocker])

    def test_non_string_entry_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            unsafe_runtime_blockers([123])  # type: ignore[list-item]


if __name__ == "__main__":
    unittest.main(verbosity=2)
