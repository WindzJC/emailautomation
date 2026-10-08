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


    def test_stop_all_senders_uses_verified_profile_stop_without_killing_tmux_sessions(self) -> None:
        with patch.object(
            runtime_backend_tmux.dashboard_core,
            "DASHBOARD_PROFILES",
            ["private_jc"],
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "active_or_locked_sender_profiles",
            side_effect=[{"private_jc"}, set()],
        ), patch.object(
            runtime_backend_tmux,
            "stop_sender",
            return_value=(True, "Stopped and verified private_jc."),
        ) as stop_sender, patch.object(
            runtime_backend_tmux.dashboard_core,
            "stop_sendgrid_session",
        ) as kill_session:
            ok, message = runtime_backend_tmux.stop_all_senders()

        self.assertTrue(ok)
        self.assertIn("Stopped and verified private_jc", message)
        stop_sender.assert_called_once_with(
            "private_jc", session=runtime_backend_tmux.dashboard_core.TMUX_SESSION_NAME
        )
        kill_session.assert_not_called()

    def test_batch_stop_requests_all_profiles_before_shared_verification(self) -> None:
        calls: list[str] = []

        def fake_wait(profile_names, *, timeout_seconds):
            calls.append(f"wait:{','.join(sorted(profile_names))}:{timeout_seconds}")
            return [], set()

        with patch.object(
            runtime_backend_tmux.dashboard_core,
            "DASHBOARD_PROFILES",
            ["private_jc", "sendgrid_annette"],
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "active_or_locked_sender_profiles",
            return_value={"private_jc", "sendgrid_annette"},
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "profile_session_name",
            side_effect=lambda profile: profile,
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "profile_pane_index",
            side_effect=lambda profile: 1 if profile == "private_jc" else 2,
        ), patch.object(
            runtime_backend_tmux.dashboard_core.subprocess,
            "run",
            side_effect=lambda args, **kwargs: calls.append(f"tmux:{args[3]}") or type("Proc", (), {"stdout": "", "stderr": ""})(),
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "_wait_for_sender_stop",
            side_effect=fake_wait,
        ), patch.object(
            runtime_backend_tmux.dashboard_core,
            "stop_sender_processes",
        ) as stop_sender_processes:
            result = runtime_backend_tmux.stop_profiles_cooperatively(["private_jc", "sendgrid_annette"])

        self.assertTrue(result["ok"])
        self.assertEqual(
            ["tmux:private_jc:run.1", "tmux:sendgrid_annette:run.2", "wait:private_jc,sendgrid_annette:3.0"],
            calls,
        )
        stop_sender_processes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
