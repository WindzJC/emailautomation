#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Sequence

import settings


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DST = [
    str(settings.SHARDS_DIR / "recipients_sendgrid_1.csv"),
    str(settings.SHARDS_DIR / "recipients_sendgrid_2.csv"),
    str(settings.SHARDS_DIR / "recipients_sendgrid_3.csv"),
    str(settings.SHARDS_DIR / "recipients_sendgrid_4.csv"),
    str(settings.SHARDS_DIR / "recipients_sendgrid_5.csv"),
]
EMAIL_HEADER_CANDIDATES = (
    "email",
    "authoremail",
    "e_mail",
    "e-mail",
    "mail",
    "address",
)
FIRST_NAME_HEADER_CANDIDATES = (
    "authorname",
    "author_name",
    "author",
    "name",
    "firstname",
    "first_name",
)


def normalize_header(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum())


def pick_header(fieldnames: Sequence[str], candidates: Iterable[str]) -> str | None:
    normalized = {normalize_header(name): name for name in fieldnames if name}
    for candidate in candidates:
        match = normalized.get(normalize_header(candidate))
        if match:
            return match
    return None


def nonblank_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [line for line in raw.splitlines() if line.strip()]
    return "\n".join(lines)


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:25])
    if not sample:
        return ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        if "\t" in first_line:
            return "\t"
        return ","


def load_source_rows(path: Path) -> List[dict[str, str]]:
    text = nonblank_text(path)
    if not text.strip():
        return []

    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    fieldnames = [name.lstrip("\ufeff") for name in (reader.fieldnames or [])]
    if not fieldnames:
        return []

    email_key = pick_header(fieldnames, EMAIL_HEADER_CANDIDATES)
    if not email_key:
        raise SystemExit(
            f"Could not find an email column in {path.name}. "
            f"Headers seen: {', '.join(fieldnames)}"
        )
    first_name_key = pick_header(fieldnames, FIRST_NAME_HEADER_CANDIDATES)

    rows: List[dict[str, str]] = []
    for row in reader:
        email = (row.get(email_key) or "").strip()
        first_name = (row.get(first_name_key) or "").strip() if first_name_key else ""
        if not email and not first_name:
            continue
        rows.append({"Email": email, "FirstName": first_name})
    return rows


def write_normalized_input(path: Path, rows: Sequence[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Email", "FirstName"])
        writer.writeheader()
        writer.writerows(rows)


def run_command(args: Sequence[str]) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def resolve_cli_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Normalize raw leads, run precheck, then distribute valid leads into the 5 SendGrid shards."
    )
    ap.add_argument("--in", dest="inp", default="leads.csv", help="Raw lead file to validate.")
    ap.add_argument(
        "--prechecked-out",
        default=str(settings.state_path("leads_prechecked.csv")),
        help="Validated lead staging file written by precheck.",
    )
    ap.add_argument(
        "--suppressed",
        default=str(settings.SUPPRESSED_PATH),
        help="Reject report / suppression file maintained by precheck.",
    )
    ap.add_argument(
        "--dst",
        nargs=5,
        default=DEFAULT_DST,
        metavar=("DST1", "DST2", "DST3", "DST4", "DST5"),
        help="Exactly 5 SendGrid shard CSVs.",
    )
    ap.add_argument(
        "--count",
        type=int,
        default=0,
        help="How many validated rows to distribute from the staged prechecked file (0 = all).",
    )
    ap.add_argument("--no_mx", action="store_true", help="Skip MX checks during precheck.")
    ap.add_argument("--allow_role", action="store_true", help="Allow role-based emails during precheck.")
    ap.add_argument("--mx_timeout", type=float, default=2.0, help="DNS timeout per try (seconds).")
    ap.add_argument("--mx_lifetime", type=float, default=6.0, help="DNS total lifetime (seconds).")
    ap.add_argument(
        "--keep-top-email",
        default="astraproductionsbyjc@gmail.com",
        help="Email to preserve at the top of every shard.",
    )
    ap.add_argument(
        "--keep-top-name",
        default="",
        help="Optional name to use for --keep-top-email.",
    )
    ap.add_argument(
        "--remove-prechecked",
        dest="remove_prechecked",
        action="store_true",
        default=True,
        help="Remove distributed rows from the staged prechecked file.",
    )
    ap.add_argument(
        "--keep-prechecked",
        dest="remove_prechecked",
        action="store_false",
        help="Keep distributed rows in the staged prechecked file.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Run precheck and compute distribution counts without writing shard files.",
    )
    return ap.parse_args(list(argv))


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    input_path = resolve_cli_path(args.inp)
    prechecked_path = resolve_cli_path(args.prechecked_out)
    suppressed_path = resolve_cli_path(args.suppressed)
    dst_paths = [resolve_cli_path(path) for path in args.dst]

    rows = load_source_rows(input_path)
    if not rows:
        print(f"No lead rows found in {input_path.name}.")
        return 0

    temp_paths: list[Path] = []

    def make_temp_path(prefix: str) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            suffix=".csv",
            prefix=prefix,
            dir=ROOT,
            delete=False,
        ) as handle:
            path = Path(handle.name)
        temp_paths.append(path)
        return path

    staged_prechecked_path = prechecked_path
    staged_suppressed_path = suppressed_path
    if args.dry_run:
        staged_prechecked_path = make_temp_path("prepare_sendgrid_prechecked_")
        staged_suppressed_path = make_temp_path("prepare_sendgrid_suppressed_")

    temp_path = make_temp_path("prepare_sendgrid_")
    try:
        write_normalized_input(temp_path, rows)
        print(f"Normalized {len(rows)} raw lead rows from {input_path.name}.")

        precheck_cmd = [
            sys.executable,
            str(ROOT / "precheck_leads.py"),
            "--in",
            str(temp_path),
            "--out",
            str(staged_prechecked_path),
            "--suppressed",
            str(staged_suppressed_path),
            "--email_col",
            "Email",
            "--author_col",
            "FirstName",
            "--require_author",
            "--mx_timeout",
            str(args.mx_timeout),
            "--mx_lifetime",
            str(args.mx_lifetime),
            "--no_drain_in",
        ]
        if args.no_mx:
            precheck_cmd.append("--no_mx")
        if args.allow_role:
            precheck_cmd.append("--allow_role")

        print("Running precheck...")
        run_command(precheck_cmd)

        split_cmd = [
            sys.executable,
            str(ROOT / "split_recipients_5.py"),
            "--src",
            str(staged_prechecked_path),
            "--dst",
            *[str(path) for path in dst_paths],
            "--count",
            str(args.count),
            "--append",
        ]
        if args.remove_prechecked:
            split_cmd.append("--remove")
        if args.keep_top_email:
            split_cmd.extend(["--keep-top-email", args.keep_top_email])
        if args.keep_top_name:
            split_cmd.extend(["--keep-top-name", args.keep_top_name])
        if args.dry_run:
            split_cmd.append("--dry-run")

        print("Distributing validated leads into SendGrid shards...")
        run_command(split_cmd)
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)

    print("Done.")
    if args.dry_run:
        print("Dry run only: staging and shard files were not modified.")
    else:
        print(f"Validated staging file: {prechecked_path}")
        print(f"Shard files updated: {', '.join(path.name for path in dst_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
