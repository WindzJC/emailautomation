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


if __name__ == "__main__":
    unittest.main()
