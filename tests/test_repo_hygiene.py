from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_RUNTIME_FILES = {
    ".env",
    "leads.csv",
    "leads_prechecked.csv",
    "recipients.csv",
    "sendgrid_daily_counters.lock",
    "suppressed.csv",
    "unsubscribed.csv",
}


def test_generated_runtime_files_are_not_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    tracked = [path for path in result.stdout.decode("utf-8").split("\0") if path]
    violations = [
        path
        for path in tracked
        if path in ROOT_RUNTIME_FILES
        or path.startswith(("data/", "logs/", "_important/audits/"))
        or re.fullmatch(r"tmp[^/]*/.*", path)
        or re.fullmatch(r"recipients[^/]*\.csv", path)
        or re.fullmatch(r"[^/]*_log(?:_worker)?\.(?:csv|jsonl)", path)
        or re.fullmatch(r"warm_email_preview[^/]*\.csv", path)
    ]
    assert violations == [], f"Generated runtime files must not be tracked: {violations}"
