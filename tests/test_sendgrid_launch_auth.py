from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sendgrid_launch_auth import (
    looks_like_sendgrid_api_key,
    mask_sendgrid_api_key,
    resolve_sendgrid_api_key,
)


class SendGridLaunchAuthTests(unittest.TestCase):
    def test_resolve_prefers_env_file_over_placeholder_inherited_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            env_path = base / ".env"
            env_path.write_text(
                "SENDGRID_API_KEY=SG.realprefix.realsuffixvalue\n",
                encoding="utf-8",
            )

            result = resolve_sendgrid_api_key(
                env={"SENDGRID_API_KEY": "PASTE_WORKING_SENDGRID_KEY_HERE"},
                env_files=[env_path],
            )

        self.assertTrue(result.ok)
        self.assertEqual(".env", result.source_label)
        self.assertEqual("SG.realprefix.realsuffixvalue", result.key)

    def test_resolve_fails_for_missing_key(self) -> None:
        result = resolve_sendgrid_api_key(env={}, env_files=[])

        self.assertFalse(result.ok)
        self.assertIn("was not found", result.error)

    def test_resolve_fails_for_placeholder_inherited_key(self) -> None:
        result = resolve_sendgrid_api_key(
            env={"SENDGRID_API_KEY": "PASTE_WORKING_SENDGRID_KEY_HERE"},
            env_files=[],
        )

        self.assertFalse(result.ok)
        self.assertIn("placeholder or blank value", result.error)

    def test_resolve_warns_for_unusual_key_format(self) -> None:
        result = resolve_sendgrid_api_key(
            env={"SENDGRID_API_KEY": "not-an-sg-key"},
            env_files=[],
        )

        self.assertTrue(result.ok)
        self.assertIn("does not match the usual SendGrid SG.* format", result.warning)

    def test_helpers_mask_and_format(self) -> None:
        self.assertTrue(looks_like_sendgrid_api_key("SG.alpha.beta"))
        self.assertFalse(looks_like_sendgrid_api_key("not-an-sg-key"))
        self.assertEqual("SG.tes...-key", mask_sendgrid_api_key("SG.test-real-key"))
