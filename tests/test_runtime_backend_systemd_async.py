from __future__ import annotations

import subprocess
import unittest
from dataclasses import dataclass
from unittest.mock import patch

import runtime_backend_systemd as backend


@dataclass(frozen=True)
class FakeSnapshot:
    name: str = "private_jc"
    tmux_running: bool = False
    tmux_dead: bool = False
    tmux_command: str = ""
    tmux_tail: str = ""
    runtime_state: str = "stopped"
    runtime_label: str = "Stopped"
    runtime_note: str = ""


def completed(
    command: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout,
        stderr,
    )


class AsyncSystemdStartTests(unittest.TestCase):
    def test_start_control_uses_no_block(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            return completed(command)

        with patch.object(
            backend.subprocess,
            "run",
            side_effect=fake_run,
        ):
            result = backend._control(
                "start",
                "private_jc",
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual(1, len(calls))

        command, kwargs = calls[0]

        self.assertEqual(
            [
                backend.SYSTEMCTL_BIN,
                "--no-block",
                "start",
                "astra-sender@private_jc.service",
            ],
            command,
        )
        self.assertEqual(120, kwargs["timeout"])

    def test_active_state_uses_systemctl_show(self) -> None:
        calls: list[list[str]] = []

        def fake_run(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            del kwargs
            calls.append(command)
            return completed(
                command,
                stdout="activating\n",
            )

        with patch.object(
            backend.subprocess,
            "run",
            side_effect=fake_run,
        ):
            state = backend._active_state("private_jc")

        self.assertEqual("activating", state)
        self.assertEqual(
            [[
                backend.SYSTEMCTL_BIN,
                "show",
                "astra-sender@private_jc.service",
                "--property=ActiveState",
                "--value",
            ]],
            calls,
        )

    def test_start_sender_accepts_job_that_becomes_activating(self) -> None:
        actions: list[str] = []

        def fake_control(
            action: str,
            profile_name: str,
        ) -> subprocess.CompletedProcess[str]:
            self.assertEqual("private_jc", profile_name)
            actions.append(action)
            return completed(["systemctl", action])

        with patch.object(
            backend,
            "_active_state",
            side_effect=["inactive", "inactive"]
            + ["activating"] * (backend.START_VERIFY_ATTEMPTS - 1),
        ), patch.object(
            backend,
            "_control",
            side_effect=fake_control,
        ), patch.object(
            backend.time,
            "sleep",
        ):
            ok, message = backend.start_sender(
                "private_jc",
            )

        self.assertTrue(ok)
        self.assertIn("STARTING:", message)
        self.assertIn("still activating", message)
        self.assertEqual(["start"], actions)

    def test_start_sender_accepts_verified_active_state(self) -> None:
        with patch.object(
            backend,
            "_active_state",
            side_effect=["inactive", "active"],
        ), patch.object(
            backend,
            "_control",
            return_value=completed(["systemctl", "start"]),
        ), patch.object(backend.time, "sleep"):
            ok, message = backend.start_sender("private_jc")

        self.assertTrue(ok)
        self.assertIn("STARTED:", message)
        self.assertIn("verified state=active", message)

    def test_start_sender_rejects_exec_condition_style_inactive_state(self) -> None:
        with patch.object(
            backend,
            "_active_state",
            return_value="inactive",
        ), patch.object(
            backend,
            "_control",
            return_value=completed(["systemctl", "start"]),
        ), patch.object(backend.time, "sleep") as sleep:
            ok, message = backend.start_sender("private_jc")

        self.assertFalse(ok)
        self.assertIn("REFUSED:", message)
        self.assertIn("skipped", message)
        self.assertIn("remained inactive", message)
        self.assertEqual(backend.START_VERIFY_ATTEMPTS - 1, sleep.call_count)

    def test_start_sender_rejects_dead_post_start_state(self) -> None:
        with patch.object(
            backend,
            "_active_state",
            side_effect=["inactive"] + ["dead"] * backend.START_VERIFY_ATTEMPTS,
        ), patch.object(
            backend,
            "_control",
            return_value=completed(["systemctl", "start"]),
        ), patch.object(backend.time, "sleep"):
            ok, message = backend.start_sender("private_jc")

        self.assertFalse(ok)
        self.assertIn("REFUSED:", message)
        self.assertIn("skipped", message)
        self.assertIn("remained dead", message)

    def test_start_sender_rejects_failed_post_start_state(self) -> None:
        with patch.object(
            backend,
            "_active_state",
            side_effect=["inactive", "failed"],
        ), patch.object(
            backend,
            "_control",
            return_value=completed(["systemctl", "start"]),
        ), patch.object(backend.time, "sleep"):
            ok, message = backend.start_sender("private_jc")

        self.assertFalse(ok)
        self.assertIn("FAILED:", message)
        self.assertIn("failed state", message)

    def test_start_sender_times_out_when_post_start_state_is_unknown(self) -> None:
        states = ["inactive"] + ["unknown"] * backend.START_VERIFY_ATTEMPTS
        with patch.object(
            backend,
            "_active_state",
            side_effect=states,
        ), patch.object(
            backend,
            "_control",
            return_value=completed(["systemctl", "start"]),
        ), patch.object(backend.time, "sleep"):
            ok, message = backend.start_sender("private_jc")

        self.assertFalse(ok)
        self.assertIn("VERIFICATION_TIMEOUT:", message)
        self.assertIn("timed out", message)

    def test_start_sender_rejects_duplicate_activating_job(
        self,
    ) -> None:
        with patch.object(
            backend,
            "_active_state",
            return_value="activating",
        ), patch.object(
            backend,
            "_control",
        ) as control:
            ok, message = backend.start_sender(
                "private_jc",
            )

        self.assertFalse(ok)
        self.assertIn("already starting", message)
        control.assert_not_called()

    def test_unknown_state_fails_closed(self) -> None:
        with patch.object(
            backend,
            "_active_state",
            return_value="unknown",
        ), patch.object(
            backend,
            "_control",
        ) as control:
            ok, message = backend.start_sender(
                "private_jc",
            )

        self.assertFalse(ok)
        self.assertIn(
            "Unable to determine",
            message,
        )
        control.assert_not_called()

    def test_activating_snapshot_is_starting(self) -> None:
        with patch.object(
            backend.dashboard_core,
            "load_profile_snapshot",
            return_value=FakeSnapshot(),
        ), patch.object(
            backend,
            "_active_state",
            return_value="activating",
        ):
            snapshot = backend._profile_snapshot(
                "private_jc",
                pane_index=0,
                tail_lines=12,
            )

        self.assertEqual(
            "starting",
            snapshot.runtime_state,
        )
        self.assertEqual(
            "Starting",
            snapshot.runtime_label,
        )
        self.assertTrue(snapshot.tmux_running)
        self.assertIn(
            "startup verification",
            snapshot.runtime_note,
        )

    def test_runtime_profile_overlays_reuses_systemd_mapping_without_loading_metrics(self) -> None:
        backend._reset_runtime_overlay_cache_for_tests()
        with patch.object(
            backend,
            "configured_profiles",
            return_value=["private_jc", "sendgrid_annette"],
        ), patch.object(
            backend,
            "_batch_active_states",
            return_value={
                "private_jc": "active",
                "sendgrid_annette": "inactive",
            },
        ) as batch_active_states, patch.object(
            backend.dashboard_core,
            "load_profile_snapshot",
        ) as load_profile_snapshot:
            overlays = backend.runtime_profile_overlays()

        self.assertEqual("running", overlays["private_jc"]["runtime_state"])
        self.assertTrue(overlays["private_jc"]["tmux_running"])
        self.assertEqual("stopped", overlays["sendgrid_annette"]["runtime_state"])
        self.assertFalse(overlays["sendgrid_annette"]["tmux_running"])
        batch_active_states.assert_called_once_with(
            ["private_jc", "sendgrid_annette"]
        )
        load_profile_snapshot.assert_not_called()

    def test_runtime_profile_overlays_preserves_failed_mapping(self) -> None:
        backend._reset_runtime_overlay_cache_for_tests()
        with patch.object(
            backend,
            "configured_profiles",
            return_value=["private_jc"],
        ), patch.object(
            backend,
            "_batch_active_states",
            return_value={"private_jc": "failed"},
        ):
            overlays = backend.runtime_profile_overlays()

        self.assertEqual("error", overlays["private_jc"]["runtime_state"])
        self.assertEqual("Error", overlays["private_jc"]["runtime_label"])
        self.assertTrue(overlays["private_jc"]["tmux_dead"])

    def test_batch_active_states_uses_one_systemctl_show(self) -> None:
        stdout = (
            "Id=astra-sender@private_jc.service\n"
            "ActiveState=active\n"
            "\n"
            "Id=astra-sender@sendgrid_annette.service\n"
            "ActiveState=failed\n"
        )
        with patch.object(
            backend.subprocess,
            "run",
            return_value=completed([], stdout=stdout),
        ) as run:
            states = backend._batch_active_states(
                ["private_jc", "sendgrid_annette"]
            )

        self.assertEqual(
            {
                "private_jc": "active",
                "sendgrid_annette": "failed",
            },
            states,
        )
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(
            [
                backend.SYSTEMCTL_BIN,
                "show",
                "astra-sender@private_jc.service",
                "astra-sender@sendgrid_annette.service",
                "--property=Id",
                "--property=ActiveState",
                "--no-pager",
            ],
            command,
        )
        self.assertEqual(
            backend.RUNTIME_OVERLAY_SYSTEMCTL_TIMEOUT_SECONDS,
            run.call_args.kwargs["timeout"],
        )

    def test_runtime_profile_overlays_reuses_short_lived_cache(self) -> None:
        backend._reset_runtime_overlay_cache_for_tests()
        with patch.object(
            backend,
            "configured_profiles",
            return_value=["private_jc"],
        ), patch.object(
            backend,
            "_batch_active_states",
            return_value={"private_jc": "active"},
        ) as batch_active_states:
            first = backend.runtime_profile_overlays()
            second = backend.runtime_profile_overlays()

        self.assertEqual(first, second)
        self.assertEqual("running", second["private_jc"]["runtime_state"])
        batch_active_states.assert_called_once_with(["private_jc"])

    def test_runtime_profile_overlays_returns_stale_cache_during_refresh(
        self,
    ) -> None:
        backend._reset_runtime_overlay_cache_for_tests()
        with patch.object(
            backend,
            "configured_profiles",
            return_value=["private_jc"],
        ), patch.object(
            backend,
            "_batch_active_states",
            return_value={"private_jc": "active"},
        ):
            initial = backend.runtime_profile_overlays()

        self.assertEqual(
            "running",
            initial["private_jc"]["runtime_state"],
        )

        with backend._RUNTIME_OVERLAY_CACHE_LOCK:
            backend._RUNTIME_OVERLAY_CACHE_AT = (
                backend.time.monotonic()
                - backend.RUNTIME_OVERLAY_CACHE_TTL_SECONDS
                - 0.1
            )
            backend._RUNTIME_OVERLAY_REFRESHING = True

        try:
            with patch.object(
                backend,
                "_batch_active_states",
            ) as batch_active_states:
                stale = backend.runtime_profile_overlays(
                    ["private_jc"]
                )
        finally:
            with backend._RUNTIME_OVERLAY_CACHE_LOCK:
                backend._RUNTIME_OVERLAY_REFRESHING = False

        self.assertEqual(
            "running",
            stale["private_jc"]["runtime_state"],
        )
        batch_active_states.assert_not_called()

    def test_runtime_profile_overlays_batch_failure_is_fail_closed(
        self,
    ) -> None:
        backend._reset_runtime_overlay_cache_for_tests()
        with patch.object(
            backend,
            "configured_profiles",
            return_value=["private_jc"],
        ), patch.object(
            backend,
            "_batch_active_states",
            return_value=None,
        ):
            overlays = backend.runtime_profile_overlays()

        self.assertEqual("error", overlays["private_jc"]["runtime_state"])
        self.assertEqual("Unknown", overlays["private_jc"]["runtime_label"])
        self.assertTrue(overlays["private_jc"]["tmux_dead"])

    def test_list_sender_snapshots_uses_runtime_overlay_batch(self) -> None:
        backend._reset_runtime_overlay_cache_for_tests()
        overlays = {
            "private_jc": backend._runtime_fields_from_active_state(
                "private_jc",
                "active",
            ),
            "sendgrid_annette": backend._runtime_fields_from_active_state(
                "sendgrid_annette",
                "inactive",
            ),
        }

        with patch.object(
            backend,
            "configured_profiles",
            return_value=["private_jc", "sendgrid_annette"],
        ), patch.object(
            backend,
            "runtime_profile_overlays",
            return_value=overlays,
        ) as runtime_profile_overlays, patch.object(
            backend.dashboard_core,
            "load_profile_snapshot",
            side_effect=[
                FakeSnapshot(name="private_jc"),
                FakeSnapshot(name="sendgrid_annette"),
            ],
        ):
            snapshots = backend.list_sender_snapshots()

        runtime_profile_overlays.assert_called_once_with(
            ["private_jc", "sendgrid_annette"]
        )
        self.assertEqual(2, len(snapshots))
        self.assertEqual("running", snapshots[0].runtime_state)
        self.assertEqual("stopped", snapshots[1].runtime_state)

    def test_stop_sender_can_stop_activating_unit(
        self,
    ) -> None:
        with patch.object(
            backend,
            "_active_state",
            side_effect=[
                "activating",
                "inactive",
            ],
        ), patch.object(
            backend,
            "_control",
            return_value=completed(
                ["systemctl", "stop"],
            ),
        ) as control:
            ok, message = backend.stop_sender(
                "private_jc",
            )

        self.assertTrue(ok)
        self.assertIn("Stopped", message)
        control.assert_called_once_with(
            "stop",
            "private_jc",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
