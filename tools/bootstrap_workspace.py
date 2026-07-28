#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import settings  # noqa: E402


IMPORTANT_DIR = settings.APP_ROOT / "_important"
LEADSCHECKER_PATH = IMPORTANT_DIR / "leadschecker.csv"
LEADSCHECKER_HEADER = "FirstName,Email\n"


def important_link_targets() -> dict[str, Path]:
    return {
        "recipients_private_jc.csv": settings.SHARDS_DIR / "recipients_private_jc.csv",
        "recipients_sendgrid_1.csv": settings.SHARDS_DIR / "recipients_sendgrid_1.csv",
        "recipients_sendgrid_2.csv": settings.SHARDS_DIR / "recipients_sendgrid_2.csv",
        "recipients_sendgrid_3.csv": settings.SHARDS_DIR / "recipients_sendgrid_3.csv",
        "recipients_sendgrid_4.csv": settings.SHARDS_DIR / "recipients_sendgrid_4.csv",
        "recipients_sendgrid_5.csv": settings.SHARDS_DIR / "recipients_sendgrid_5.csv",
    }


def _relative_target(target: Path, link_parent: Path) -> str:
    return os.path.relpath(str(target), start=str(link_parent))


def ensure_link(link_path: Path, target: Path, *, force: bool = False) -> str:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    if link_path.is_symlink():
        try:
            current = link_path.resolve()
        except OSError:
            current = None
        if current == target.resolve():
            return "kept"
        if not force:
            return "skipped"
        link_path.unlink()
    elif link_path.exists():
        if not force:
            return "skipped"
        if link_path.is_dir():
            raise IsADirectoryError(f"Refusing to replace directory: {link_path}")
        link_path.unlink()

    relative_target = _relative_target(target, link_path.parent)
    link_path.symlink_to(relative_target)
    return "linked"


def ensure_leadschecker(path: Path, *, force: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not force:
            return "kept"
        if path.is_dir():
            raise IsADirectoryError(f"Refusing to replace directory: {path}")
        path.unlink()
    path.write_text(LEADSCHECKER_HEADER, encoding="utf-8")
    return "seeded"


def bootstrap_workspace(*, important_dir: Path = IMPORTANT_DIR, force_links: bool = False, force_seed: bool = False) -> dict[str, object]:
    important_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {
        "important_dir": str(important_dir),
        "links": {},
    }

    for name, target in important_link_targets().items():
        status = ensure_link(important_dir / name, target, force=force_links)
        results["links"][name] = {
            "status": status,
            "target": str(target),
        }

    results["leadschecker"] = {
        "status": ensure_leadschecker(important_dir / "leadschecker.csv", force=force_seed),
        "path": str(important_dir / "leadschecker.csv"),
    }
    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recreate the local _important workspace links and starter files."
    )
    parser.add_argument(
        "--force-links",
        action="store_true",
        help="Replace existing files/symlinks for managed helper links.",
    )
    parser.add_argument(
        "--force-seed",
        action="store_true",
        help="Replace _important/leadschecker.csv with a fresh starter file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = bootstrap_workspace(force_links=args.force_links, force_seed=args.force_seed)

    print(f"Workspace: {report['important_dir']}")
    for name, info in report["links"].items():
        print(f"{name}: {info['status']} -> {info['target']}")
    leadschecker = report["leadschecker"]
    print(f"leadschecker.csv: {leadschecker['status']} -> {leadschecker['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
