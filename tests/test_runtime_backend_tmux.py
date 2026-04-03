from __future__ import annotations

import unittest
from unittest.mock import patch

import runtime_backend_tmux


class RuntimeBackendTmuxTests(unittest.TestCase):
    def test_start_sender_resolves_profile_to_pane_index(self) -> None:
        with patch.object(runtime_backend_tmux.dashboard_core, "DASHBOARD_PROFILES", ["sendgrid_alpha", "sendgrid_beta"]), patch.object(
            runtime_backend_tmux.dashboard_core,
            "SENDGRID_PROFILES",
            ["sendgrid_alpha", "sendgrid_beta"],
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "profile_session_name",
            return_value=runtime_backend_tmux.dashboard_core.TMUX_SESSION_NAME,
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "profile_pane_index",
            return_value=1,
        ), patch.object(
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
        with patch.object(runtime_backend_tmux.dashboard_core, "DASHBOARD_PROFILES", ["sendgrid_alpha"]):
            ok, message = runtime_backend_tmux.stop_sender("sendgrid_beta")

        self.assertFalse(ok)
        self.assertEqual("Unknown profile: sendgrid_beta", message)

    def test_start_sender_routes_private_profiles_to_private_launcher(self) -> None:
        with patch.object(runtime_backend_tmux.dashboard_core, "DASHBOARD_PROFILES", ["private_jc"]), patch.object(
            runtime_backend_tmux.dashboard_core,
            "SENDGRID_PROFILES",
            [],
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "profile_session_name",
            return_value="private_jc",
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "start_private_profile",
            return_value=(True, "started private"),
        ) as start_private_profile:
            ok, message = runtime_backend_tmux.start_sender("private_jc")

        self.assertTrue(ok)
        self.assertEqual("started private", message)
        start_private_profile.assert_called_once_with("private_jc", session="private_jc")


if __name__ == "__main__":
    unittest.main()
