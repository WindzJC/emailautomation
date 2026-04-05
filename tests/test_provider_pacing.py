from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import provider_pacing


class ProviderPacingTests(unittest.TestCase):
    def test_private_throttle_records_cooldown_and_recommended_pace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "provider_pacing_state.json"
            now = datetime(2026, 4, 3, 0, 0, 0, tzinfo=timezone.utc)
            with patch.object(provider_pacing, "PROVIDER_PACING_STATE_PATH", state_path):
                status = provider_pacing.record_provider_throttle(
                    "private_jc",
                    "private",
                    75 * 60,
                    90,
                    "450 4.7.1 sending limit reached",
                    now=now,
                )

                self.assertTrue(status["cooldown_active"])
                self.assertEqual(120, status["recommended_cooldown_seconds"])
                self.assertTrue(status["recovery_pending"])

                after_cooldown = provider_pacing.provider_pacing_status(
                    "private_jc",
                    "private",
                    90,
                    now=now + timedelta(hours=8),
                )
                self.assertFalse(after_cooldown["cooldown_active"])
                self.assertEqual(105, after_cooldown["recommended_cooldown_seconds"])

                fully_recovered = provider_pacing.provider_pacing_status(
                    "private_jc",
                    "private",
                    90,
                    now=now + timedelta(hours=25),
                )
                self.assertEqual(90, fully_recovered["recommended_cooldown_seconds"])

    def test_private_third_recent_throttle_steps_down_to_150_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "provider_pacing_state.json"
            now = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)
            with patch.object(provider_pacing, "PROVIDER_PACING_STATE_PATH", state_path):
                provider_pacing.record_provider_throttle(
                    "private_jc",
                    "private",
                    75 * 60,
                    120,
                    "first throttle",
                    now=now - timedelta(hours=5),
                )
                provider_pacing.record_provider_throttle(
                    "private_jc",
                    "private",
                    90 * 60,
                    120,
                    "second throttle",
                    now=now - timedelta(hours=2),
                )

                status = provider_pacing.record_provider_throttle(
                    "private_jc",
                    "private",
                    90 * 60,
                    120,
                    "third throttle",
                    now=now,
                )

                self.assertEqual(3, status["recent_throttle_count_24h"])
                self.assertEqual(150, status["recommended_cooldown_seconds"])

    def test_temporary_auth_failure_records_recovery_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "provider_pacing_state.json"
            now = datetime(2026, 4, 3, 18, 0, 0, tzinfo=timezone.utc)
            with patch.object(provider_pacing, "PROVIDER_PACING_STATE_PATH", state_path):
                status = provider_pacing.record_provider_temporary_failure(
                    "private_jc",
                    "private",
                    provider_pacing.temporary_failure_pause_seconds("private", 1),
                    120,
                    "454 4.7.0 Temporary authentication failure",
                    now=now,
                )

                self.assertTrue(status["cooldown_active"])
                self.assertTrue(status["recovery_pending"])
                self.assertEqual("temporary_auth_failure", status["recovery_kind"])
                self.assertIn("Temporary authentication failure", status["recovery_reason"])
                self.assertEqual(1, status["recent_temporary_failure_count_24h"])

                resumed = provider_pacing.mark_recovery_started("private_jc", now=now + timedelta(minutes=16))
                self.assertFalse(bool(resumed["recovery_pending"]))
                self.assertEqual("", resumed["recovery_kind"])


if __name__ == "__main__":
    unittest.main()
