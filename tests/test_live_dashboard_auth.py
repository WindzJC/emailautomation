from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import dashboard_security
import live_dashboard


class LiveDashboardAuthTests(unittest.TestCase):
    def test_dashboard_auth_blocks_protected_routes_until_login_and_enforces_upload_limit(self) -> None:
        async def noop_background_loop() -> None:
            return None

        with patch.dict(
            live_dashboard.os.environ,
            {"DASHBOARD_AUTH_DISABLED": "0", "LOCAL_DASHBOARD_NO_AUTH": "0", "DASHBOARD_ALLOW_AUTO_START": "1"},
            clear=False,
        ), patch.object(live_dashboard.settings, "DASHBOARD_AUTH_USERNAME", "admin"), patch.object(
            live_dashboard.settings,
            "DASHBOARD_AUTH_PASSWORD",
            "valid-dashboard-password",
        ), patch.object(
            live_dashboard.settings,
            "DASHBOARD_SESSION_SECRET",
            "independent-session-signing-secret",
        ), patch.object(
            live_dashboard.settings,
            "APP_HOST",
            "127.0.0.1",
        ), patch.object(
            live_dashboard.settings,
            "DASHBOARD_MAX_UPLOAD_BYTES",
            8,
        ), patch.object(
            live_dashboard,
            "_background_automation_loop",
            new=noop_background_loop,
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"ok": True},
        ):
            with TestClient(live_dashboard.app) as client:
                auth_status = client.get("/api/auth/status").json()
                self.assertTrue(auth_status["auth_enabled"])
                self.assertFalse(auth_status["auth_disabled"])
                self.assertTrue(auth_status["auth_configuration_valid"])
                self.assertFalse(auth_status["authenticated"])
                self.assertEqual("live", auth_status["dashboard_mode"])
                self.assertTrue(auth_status["auto_start_allowed"])
                self.assertEqual(401, client.get("/api/snapshot").status_code)
                self.assertEqual(401, client.post("/api/leads/verify-important", json={}).status_code)
                self.assertEqual(401, client.post("/api/leads/dispatch-important", json={}).status_code)
                self.assertEqual(
                    401,
                    client.post(
                        "/api/leads/check-important/upload",
                        files={"file": ("test.csv", b"Email,FirstName\nanna@example.com,Anna\n", "text/csv")},
                    ).status_code,
                )

                login = client.post(
                    "/api/auth/login",
                    json={"username": "admin", "password": "valid-dashboard-password"},
                )
                self.assertEqual(200, login.status_code)
                self.assertTrue(login.json()["authenticated"])

                snapshot = client.get("/api/snapshot")
                self.assertEqual(200, snapshot.status_code)
                self.assertEqual({"ok": True}, snapshot.json())

                upload = client.post(
                    "/api/leads/upload",
                    files={"file": ("large.csv", b"123456789ABCDEF", "text/csv")},
                )
                self.assertEqual(413, upload.status_code)
                self.assertEqual("UPLOAD_TOO_LARGE", upload.json()["error"])

                logout = client.post("/api/auth/logout")
                self.assertEqual(200, logout.status_code)
                self.assertEqual(401, client.get("/api/snapshot").status_code)

    def test_dashboard_auth_disabled_flag_bypasses_login_for_local_development(self) -> None:
        async def noop_background_loop() -> None:
            return None

        with patch.dict(
            live_dashboard.os.environ,
            {
                "DASHBOARD_AUTH_DISABLED": "1",
                "LOCAL_DASHBOARD_NO_AUTH": "0",
                "DASHBOARD_ALLOW_AUTO_START": "0",
                "DASHBOARD_ENABLE_LIVE_ACTIONS": "0",
            },
            clear=False,
        ), patch.object(live_dashboard.settings, "DASHBOARD_AUTH_USERNAME", "admin"), patch.object(
            live_dashboard.settings,
            "DASHBOARD_AUTH_PASSWORD",
            "",
        ), patch.object(
            live_dashboard.settings,
            "DASHBOARD_SESSION_SECRET",
            "",
        ), patch.object(
            live_dashboard.settings,
            "APP_HOST",
            "127.0.0.1",
        ), patch.object(
            live_dashboard,
            "_background_automation_loop",
            new=noop_background_loop,
        ), patch.object(
            live_dashboard,
            "_build_live_snapshot",
            return_value={"ok": True},
        ):
            with TestClient(live_dashboard.app) as client:
                status = client.get("/api/auth/status")
                self.assertEqual(200, status.status_code)
                self.assertEqual(
                    {
                        "ok": True,
                        "auth_enabled": False,
                        "auth_disabled": True,
                        "auth_configuration_valid": False,
                        "authenticated": True,
                        "username": "admin",
                        "local_mode": True,
                        "dashboard_mode": "local_dev",
                        "auto_start_allowed": False,
                        "auto_start_env_var": "DASHBOARD_ALLOW_AUTO_START",
                        "live_actions_enabled": False,
                        "live_actions_env_var": "DASHBOARD_ENABLE_LIVE_ACTIONS",
                    },
                    status.json(),
                )
                self.assertEqual(200, client.get("/api/snapshot").status_code)

                with patch.object(live_dashboard.runtime_control, "start_all_senders") as start_all_senders:
                    blocked_start = client.post("/api/start")
                self.assertEqual(403, blocked_start.status_code)
                self.assertEqual("live_actions_disabled", blocked_start.json()["error"])
                self.assertIn("DASHBOARD_ENABLE_LIVE_ACTIONS=1", blocked_start.json()["message"])
                start_all_senders.assert_not_called()

                with patch.object(live_dashboard.runtime_control, "is_known_profile", return_value=True), patch.object(
                    live_dashboard.runtime_control,
                    "start_sender",
                ) as start_sender:
                    blocked_profile_start = client.post("/api/start/sendgrid_annette")
                self.assertEqual(403, blocked_profile_start.status_code)
                self.assertEqual("live_actions_disabled", blocked_profile_start.json()["error"])
                self.assertEqual("sendgrid_annette", blocked_profile_start.json()["profile"])
                start_sender.assert_not_called()

                self.assertEqual(200, client.get("/api/snapshot").status_code)

                login = client.post(
                    "/api/auth/login",
                    json={"username": "ignored", "password": "ignored"},
                )
                self.assertEqual(200, login.status_code)
                self.assertTrue(login.json()["authenticated"])
                self.assertTrue(login.json()["auth_disabled"])

                logout = client.post("/api/auth/logout")
                self.assertEqual(200, logout.status_code)
                self.assertTrue(logout.json()["authenticated"])

                markup = client.get("/").text
                self.assertIn('id="start-btn"', markup)
                self.assertIn('id="ops-tab-btn"', markup)
                self.assertIn('id="leads-tab-btn"', markup)

    def test_local_dashboard_no_auth_alias_is_supported(self) -> None:
        with patch.dict(
            live_dashboard.os.environ,
            {"DASHBOARD_AUTH_DISABLED": "0", "LOCAL_DASHBOARD_NO_AUTH": "1"},
            clear=False,
        ), patch.object(
            live_dashboard.settings,
            "APP_HOST",
            "127.0.0.1",
        ):
            self.assertTrue(live_dashboard._dashboard_auth_disabled())
            self.assertFalse(live_dashboard._dashboard_auth_enabled())

    def test_missing_auth_configuration_fails_closed(self) -> None:
        with patch.dict(
            live_dashboard.os.environ,
            {
                "DASHBOARD_AUTH_DISABLED": "0",
                "LOCAL_DASHBOARD_NO_AUTH": "0",
                "DASHBOARD_ALLOW_AUTO_START": "0",
                "DASHBOARD_ENABLE_LIVE_ACTIONS": "0",
            },
            clear=False,
        ), patch.object(live_dashboard.settings, "DASHBOARD_AUTH_PASSWORD", ""), patch.object(
            live_dashboard.settings,
            "DASHBOARD_SESSION_SECRET",
            "",
        ), patch.object(
            live_dashboard.settings,
            "APP_HOST",
            "127.0.0.1",
        ):
            status = live_dashboard._dashboard_auth_response()

        self.assertFalse(status["auth_enabled"])
        self.assertFalse(status["auth_disabled"])
        self.assertFalse(status["auth_configuration_valid"])
        self.assertFalse(status["authenticated"])
        self.assertEqual("configuration_error", status["dashboard_mode"])
        self.assertFalse(status["auto_start_allowed"])
        self.assertFalse(status["live_actions_enabled"])

    def test_missing_password_fails_closed(self) -> None:
        status = dashboard_security.validate_dashboard_security(
            password="",
            session_secret="independent-session-signing-secret",
            host="127.0.0.1",
            env={},
        )
        self.assertFalse(status.startup_allowed)
        self.assertIn("missing_password", status.errors)

    def test_blank_password_fails_closed(self) -> None:
        status = dashboard_security.validate_dashboard_security(
            password="   ",
            session_secret="independent-session-signing-secret",
            host="127.0.0.1",
            env={},
        )
        self.assertFalse(status.startup_allowed)
        self.assertIn("missing_password", status.errors)

    def test_placeholder_password_fails_closed(self) -> None:
        status = dashboard_security.validate_dashboard_security(
            password="change-me",
            session_secret="independent-session-signing-secret",
            host="127.0.0.1",
            env={},
        )
        self.assertFalse(status.startup_allowed)
        self.assertIn("placeholder_password", status.errors)

    def test_missing_or_blank_session_secret_fails_closed(self) -> None:
        for session_secret in ("", "   "):
            with self.subTest(session_secret=repr(session_secret)):
                status = dashboard_security.validate_dashboard_security(
                    password="valid-dashboard-password",
                    session_secret=session_secret,
                    host="127.0.0.1",
                    env={},
                )
                self.assertFalse(status.startup_allowed)
                self.assertIn("missing_session_secret", status.errors)

    def test_identical_password_and_session_secret_fail_closed(self) -> None:
        status = dashboard_security.validate_dashboard_security(
            password="same-credential-value",
            session_secret="same-credential-value",
            host="127.0.0.1",
            env={},
        )
        self.assertFalse(status.startup_allowed)
        self.assertIn("credentials_not_independent", status.errors)

    def test_no_auth_without_explicit_development_permission_fails_closed(self) -> None:
        status = dashboard_security.validate_dashboard_security(
            password="",
            session_secret="",
            host="127.0.0.1",
            env={"DASHBOARD_AUTH_DISABLED": "0", "LOCAL_DASHBOARD_NO_AUTH": "0"},
        )
        self.assertFalse(status.no_auth_requested)
        self.assertFalse(status.no_auth_allowed)
        self.assertFalse(status.startup_allowed)

    def test_development_no_auth_is_loopback_only(self) -> None:
        loopback = dashboard_security.validate_dashboard_security(
            password="",
            session_secret="",
            host="127.0.0.1",
            env={"DASHBOARD_AUTH_DISABLED": "1"},
        )
        public = dashboard_security.validate_dashboard_security(
            password="valid-dashboard-password",
            session_secret="independent-session-signing-secret",
            host="0.0.0.0",
            env={"DASHBOARD_AUTH_DISABLED": "1"},
        )
        self.assertTrue(loopback.no_auth_allowed)
        self.assertTrue(loopback.startup_allowed)
        self.assertFalse(public.no_auth_allowed)
        self.assertFalse(public.startup_allowed)
        self.assertIn("no_auth_requires_loopback", public.errors)

    def test_tunnel_startup_requires_valid_credentials(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "startup refused"):
            dashboard_security.require_dashboard_startup_security(
                password="",
                session_secret="",
                host="127.0.0.1",
                tunnel_mode=True,
                env={"DASHBOARD_AUTH_DISABLED": "1"},
            )

        status = dashboard_security.require_dashboard_startup_security(
            password="valid-dashboard-password",
            session_secret="independent-session-signing-secret",
            host="0.0.0.0",
            tunnel_mode=True,
            env={},
        )
        self.assertTrue(status.startup_allowed)
        self.assertTrue(status.credentials_valid)

    def test_public_startup_with_invalid_credentials_fails_before_runtime_writes(self) -> None:
        with patch.dict(
            live_dashboard.os.environ,
            {"DASHBOARD_AUTH_DISABLED": "0", "LOCAL_DASHBOARD_NO_AUTH": "0"},
            clear=False,
        ), patch.object(live_dashboard.settings, "DASHBOARD_AUTH_PASSWORD", ""), patch.object(
            live_dashboard.settings,
            "DASHBOARD_SESSION_SECRET",
            "",
        ), patch.object(
            live_dashboard.settings,
            "APP_HOST",
            "0.0.0.0",
        ), patch.object(
            live_dashboard.runtime_audit,
            "write_app_start",
        ) as write_app_start, patch.object(
            live_dashboard,
            "_resume_pending_important_check_jobs",
        ) as resume_jobs:
            with self.assertRaisesRegex(RuntimeError, "startup refused"):
                asyncio.run(live_dashboard._startup_background_automation())

        write_app_start.assert_not_called()
        resume_jobs.assert_not_called()

    def test_invalid_credentials_cannot_expose_state_changing_endpoints(self) -> None:
        async def noop_background_loop() -> None:
            return None

        with patch.dict(
            live_dashboard.os.environ,
            {"DASHBOARD_AUTH_DISABLED": "0", "LOCAL_DASHBOARD_NO_AUTH": "0"},
            clear=False,
        ), patch.object(live_dashboard.settings, "DASHBOARD_AUTH_PASSWORD", ""), patch.object(
            live_dashboard.settings,
            "DASHBOARD_SESSION_SECRET",
            "",
        ), patch.object(
            live_dashboard.settings,
            "APP_HOST",
            "127.0.0.1",
        ), patch.object(
            live_dashboard,
            "require_dashboard_startup_security",
        ), patch.object(
            live_dashboard.runtime_audit,
            "write_app_start",
        ), patch.object(
            live_dashboard,
            "_resume_pending_important_check_jobs",
        ), patch.object(
            live_dashboard,
            "_background_automation_loop",
            new=noop_background_loop,
        ), patch.object(
            live_dashboard,
            "dispatch_important_leads",
        ) as dispatch:
            with TestClient(live_dashboard.app) as client:
                response = client.post("/api/leads/dispatch-important", json={})

        self.assertEqual(503, response.status_code)
        self.assertEqual(
            "dashboard_auth_configuration_invalid",
            response.json()["error"],
        )
        dispatch.assert_not_called()

    def test_launch_scripts_run_security_preflight_before_process_mutation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        live_script = (root / "run_live_dashboard.sh").read_text(encoding="utf-8")
        self.assertLess(
            live_script.index("dashboard_security.py"),
            live_script.index("-m uvicorn"),
        )
        for script_name in (
            "run_dashboard_tmux.sh",
            "run_mailops_tmux.sh",
            "run_tunnel_tmux.sh",
        ):
            with self.subTest(script=script_name):
                text = (root / script_name).read_text(encoding="utf-8")
                preflight_index = text.index("dashboard_security.py")
                first_process_mutation = min(
                    index
                    for marker in ("tmux kill-session", "pkill -f")
                    if (index := text.find(marker)) >= 0
                )
                self.assertLess(preflight_index, first_process_mutation)


if __name__ == "__main__":
    unittest.main()
