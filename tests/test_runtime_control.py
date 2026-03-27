from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import runtime_control


class RuntimeControlTests(unittest.TestCase):
    def test_start_sender_delegates_to_backend(self) -> None:
        backend = SimpleNamespace(
            start_sender=lambda profile_name, session="tmux-default": (True, f"{profile_name}:{session}"),
        )
        with patch.object(runtime_control, "_BACKEND", backend):
            ok, message = runtime_control.start_sender("sendgrid_beta")

        self.assertTrue(ok)
        self.assertEqual("sendgrid_beta:tmux-default", message)

    def test_snapshot_runtime_status_delegates_to_backend(self) -> None:
        backend = SimpleNamespace(
            snapshot_runtime_status=lambda tail_lines=12, session="tmux-default": {
                "backend": "stub",
                "tail_lines": tail_lines,
                "session": session,
            }
        )
        with patch.object(runtime_control, "_BACKEND", backend):
            status = runtime_control.snapshot_runtime_status(tail_lines=7)

        self.assertEqual("stub", status["backend"])
        self.assertEqual(7, status["tail_lines"])
        self.assertEqual("tmux-default", status["session"])


if __name__ == "__main__":
    unittest.main()
