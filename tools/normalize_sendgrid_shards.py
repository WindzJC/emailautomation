#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import settings
from send_shard import ROLE_LOCALPART_BLOCKLIST, is_role_recipient, norm_email, parse_email_list


def detect_email_field(fieldnames: List[str]) -> str:
    for name in fieldnames:
        if (name or "").strip().lower() == "email":
            return name
    return fieldnames[0]


def backup_files(paths: List[Path], backup_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_root / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.copy2(path, dest / path.name)
    return dest


def normalize_shards(paths: List[Path], always_send: set[str]) -> Dict[str, object]:
    seen: set[str] = set()
    totals = Counter()
    per_shard: Dict[str, Dict[str, int]] = {}

    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        if not fieldnames:
            per_shard[path.name] = {"kept": 0, "removed_duplicates": 0, "removed_role": 0, "removed_empty": 0}
            continue

        email_field = detect_email_field(fieldnames)
        kept_rows: List[Dict[str, str]] = []
        removed_duplicates = 0
        removed_role = 0
        removed_empty = 0

        for row in rows:
            email = norm_email(row.get(email_field) or "")
            if not email:
                removed_empty += 1
                continue

            row[email_field] = email
            is_always = email in always_send

            if not is_always and is_role_recipient(email, ROLE_LOCALPART_BLOCKLIST):
                removed_role += 1
                continue

            if not is_always and email in seen:
                removed_duplicates += 1
                continue

            kept_rows.append(row)
            if not is_always:
                seen.add(email)

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept_rows)

        per_shard[path.name] = {
            "kept": len(kept_rows),
            "removed_duplicates": removed_duplicates,
            "removed_role": removed_role,
            "removed_empty": removed_empty,
        }
        totals["kept"] += len(kept_rows)
        totals["removed_duplicates"] += removed_duplicates
        totals["removed_role"] += removed_role
        totals["removed_empty"] += removed_empty

    return {
        "per_shard": per_shard,
        "totals": dict(totals),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalize SendGrid recipient shards for smoother sending.")
    ap.add_argument("--shards-glob", default=str(settings.SHARDS_DIR / "recipients_sendgrid_*.csv"))
    ap.add_argument("--backup-dir", default=str(settings.BACKUPS_DIR))
    ap.add_argument("--always-send", default="astraproductionsbyjc@gmail.com")
    ap.add_argument("--report-path", default=str(settings.SENDGRID_NORMALIZE_REPORT_PATH))
    args = ap.parse_args()

    shards_glob = args.shards_glob
    if not Path(shards_glob).is_absolute():
        shards_glob = str(settings.SHARDS_DIR / Path(shards_glob).name)

    backup_dir_arg = Path(args.backup_dir)
    if not backup_dir_arg.is_absolute():
        backup_dir_arg = settings.state_path(args.backup_dir)

    report_path_arg = Path(args.report_path)
    if not report_path_arg.is_absolute():
        report_path_arg = settings.state_path(args.report_path)

    paths = [Path(p) for p in sorted(glob.glob(shards_glob))]
    if not paths:
        raise SystemExit(f"No shard files matched: {shards_glob}")

    backup_dir = backup_files(paths, backup_dir_arg)
    report = normalize_shards(paths, parse_email_list(args.always_send))
    report["backup_dir"] = str(backup_dir)
    report["shards"] = [p.name for p in paths]

    report_path = report_path_arg
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Normalized {len(paths)} shard file(s).")
    print(f"Backup: {backup_dir}")
    print(f"Report: {report_path}")
    print(json.dumps(report["totals"], indent=2))


if __name__ == "__main__":
    main()
