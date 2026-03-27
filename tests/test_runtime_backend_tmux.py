from __future__ import annotations

import unittest
from unittest.mock import patch

import runtime_backend_tmux


class RuntimeBackendTmuxTests(unittest.TestCase):
    def test_start_sender_resolves_profile_to_pane_index(self) -> None:
        with patch.object(runtime_backend_tmux.dashboard_core, "SENDGRID_PROFILES", ["sendgrid_alpha", "sendgrid_beta"]), patch.object(
            runtime_backend_tmux.dashboard_core,
            "start_sendgrid_profile",
            return_value=(True, "started"),
        ) as start_sendgrid_profile:
            ok, message = runtime_backend_tmux.start_sender("sendgrid_beta")

        self.assertTrue(ok)
        self.assertEqual("started", message)
        start_sendgrid_profile.assert_called_once_with(
            "sendgrid_beta",
            1,
            session=runtime_backend_tmux.dashboard_core.TMUX_SESSION_NAME,
        )

    def test_stop_sender_rejects_unknown_profile(self) -> None:
        with patch.object(runtime_backend_tmux.dashboard_core, "SENDGRID_PROFILES", ["sendgrid_alpha"]):
            ok, message = runtime_backend_tmux.stop_sender("sendgrid_beta")

        self.assertFalse(ok)
        self.assertEqual("Unknown profile: sendgrid_beta", message)


if __name__ == "__main__":
    unittest.main()
