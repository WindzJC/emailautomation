from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import bootstrap_workspace


class BootstrapWorkspaceTests(unittest.TestCase):
    def test_ensure_link_creates_relative_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "data" / "shards" / "recipients_sendgrid_1.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Email,FirstName\n", encoding="utf-8")

            link_path = root / "_important" / "recipients_sendgrid_1.csv"
            status = bootstrap_workspace.ensure_link(link_path, target)

            self.assertEqual("linked", status)
            self.assertTrue(link_path.is_symlink())
            self.assertEqual(target.resolve(), link_path.resolve())

    def test_ensure_leadschecker_seeds_header_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "_important" / "leadschecker.csv"
            status = bootstrap_workspace.ensure_leadschecker(path)

            self.assertEqual("seeded", status)
            self.assertEqual("FirstName,Email\n", path.read_text(encoding="utf-8"))

    def test_bootstrap_workspace_preserves_existing_seed_file_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            important_dir = root / "_important"
            important_dir.mkdir(parents=True, exist_ok=True)

            leadschecker = important_dir / "leadschecker.csv"
            leadschecker.write_text("FirstName,Email\nAlice,alice@example.com\n", encoding="utf-8")

            targets: dict[str, Path] = {
                "sendshard.py": root / "send_shard.py",
                "recipients_private_jc.csv": root / "data" / "shards" / "recipients_private_jc.csv",
            }
            for path in targets.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")

            original_targets = bootstrap_workspace.important_link_targets
            try:
                bootstrap_workspace.important_link_targets = lambda: targets
                report = bootstrap_workspace.bootstrap_workspace(important_dir=important_dir)
            finally:
                bootstrap_workspace.important_link_targets = original_targets

            self.assertEqual("kept", report["leadschecker"]["status"])
            self.assertIn("Alice,alice@example.com", leadschecker.read_text(encoding="utf-8"))
            self.assertTrue((important_dir / "sendshard.py").is_symlink())
            self.assertTrue((important_dir / "recipients_private_jc.csv").is_symlink())


if __name__ == "__main__":
    unittest.main()
