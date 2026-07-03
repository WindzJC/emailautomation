from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

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
            "secret",
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
                    json={"username": "admin", "password": "secret"},
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
            "secret",
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
        ):
            self.assertTrue(live_dashboard._dashboard_auth_disabled())
            self.assertFalse(live_dashboard._dashboard_auth_enabled())

    def test_missing_auth_configuration_is_reported_as_local_dev(self) -> None:
        with patch.dict(
            live_dashboard.os.environ,
            {
                "DASHBOARD_AUTH_DISABLED": "0",
                "LOCAL_DASHBOARD_NO_AUTH": "0",
                "DASHBOARD_ALLOW_AUTO_START": "0",
                "DASHBOARD_ENABLE_LIVE_ACTIONS": "0",
            },
            clear=False,
        ), patch.object(live_dashboard.settings, "DASHBOARD_AUTH_PASSWORD", ""):
            status = live_dashboard._dashboard_auth_response()

        self.assertFalse(status["auth_enabled"])
        self.assertFalse(status["auth_disabled"])
        self.assertEqual("local_dev", status["dashboard_mode"])
        self.assertFalse(status["auto_start_allowed"])
        self.assertFalse(status["live_actions_enabled"])


if __name__ == "__main__":
    unittest.main()
