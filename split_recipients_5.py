#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
import tempfile
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from recipient_file_lock import lock_files


DEFAULT_HEADERS = ["Email", "FirstName"]


def norm_email(s: str) -> str:
    return (s or "").strip().lower()


@dataclass(frozen=True)
class Row:
    email: str
    first_name: str

    def as_dict(self) -> Dict[str, str]:
        return {"Email": self.email, "FirstName": self.first_name}


@dataclass
class SelectionSummary:
    inspected: int = 0
    appended: int = 0
    skipped_existing: int = 0
    skipped_source_dupe: int = 0
    skipped_keep_top: int = 0


def clean_name_token(value: str) -> str:
    return re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", (value or "").strip())


def first_name_only(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    first_token = clean_name_token(raw.split()[0])
    return first_token or ""


def detect_fieldnames(fieldnames: Optional[Sequence[str]]) -> Tuple[str, str]:
    if not fieldnames:
        return ("Email", "FirstName")

    # Handle BOM in first header (common on Windows exports)
    fn = [f.lstrip("\ufeff") for f in fieldnames]
    lower = {f.lower(): f for f in fn}

    def pick(candidates: Sequence[str]) -> Optional[str]:
        for c in candidates:
            if c in lower:
                return lower[c]
        return None

    email_key = pick(["email", "e-mail", "e_mail", "mail", "address"]) or fn[0]
    name_key = pick(["firstname", "first_name", "authorname", "author_name", "name"]) or (fn[1] if len(fn) > 1 else fn[0])
    return (email_key, name_key)


def read_rows_csv(path: Path) -> Tuple[List[str], List[Row]]:
    if not path.exists():
        return (DEFAULT_HEADERS[:], [])

    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
        # Allow completely empty files
        sample = f.read(4096)
        if not sample.strip():
            return (DEFAULT_HEADERS[:], [])
        f.seek(0)

        reader = csv.DictReader(f)
        email_key, name_key = detect_fieldnames(reader.fieldnames)
        headers = DEFAULT_HEADERS[:]

        out: List[Row] = []
        for r in reader:
            email = (r.get(email_key) or "").strip()
            if not email:
                continue
            out.append(
                Row(
                    email=email,
                    first_name=first_name_only(r.get(name_key) or ""),
                )
            )
        return (headers, out)


def write_rows_csv(path: Path, rows: Iterable[Row]) -> None:
    row_list = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=DEFAULT_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([r.as_dict() for r in row_list])
    temp_path.replace(path)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Pull N rows from a source leads CSV and distribute evenly into 5 recipient CSVs."
    )
    ap.add_argument("--src", required=True, help="Source CSV (e.g., leads_prechecked.csv)")
    ap.add_argument(
        "--dst",
        nargs=5,
        required=True,
        metavar=("DST1", "DST2", "DST3", "DST4", "DST5"),
        help="Exactly 5 destination CSVs",
    )
    ap.add_argument(
        "--count",
        type=int,
        default=100,
        help="How many unique rows to actually distribute from --src (0 = all).",
    )
    ap.add_argument(
        "--remove",
        action="store_true",
        help="Remove the pulled (and actually written) rows from --src",
    )
    ap.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Do not dedupe by email against destination files or within the pulled set",
    )
    ap.add_argument(
        "--append",
        action="store_true",
        help="Append to destination files (default behavior is to rewrite/normalize the file with header)",
    )
    ap.add_argument("--keep-top-email", default="", help="Email to force as first row in every destination")
    ap.add_argument("--keep-top-name", default="", help="Name for --keep-top-email (optional)")
    ap.add_argument("--dry-run", action="store_true", help="Compute and print counts but don't write files")
    return ap.parse_args(list(argv))


def load_existing_emails(dst_paths: Sequence[Path]) -> Tuple[List[List[Row]], set]:
    existing_lists: List[List[Row]] = []
    all_emails: set = set()
    for p in dst_paths:
        _, rows = read_rows_csv(p)
        existing_lists.append(rows)
        for r in rows:
            all_emails.add(norm_email(r.email))
    return existing_lists, all_emails


def select_rows_for_distribution(
    src_rows: Sequence[Row],
    existing_emails: set,
    want_count: int,
    dedupe: bool,
    keep_top_email: str,
) -> Tuple[List[Row], int, SelectionSummary]:
    target = None if want_count == 0 else want_count
    seen: set = set()
    selected: List[Row] = []
    summary = SelectionSummary()

    for row in src_rows:
        if target is not None and len(selected) >= target:
            break
        summary.inspected += 1
        email = norm_email(row.email)
        if not email:
            continue
        if dedupe and email in seen:
            summary.skipped_source_dupe += 1
            continue
        if dedupe and email in existing_emails:
            summary.skipped_existing += 1
            continue
        if dedupe and keep_top_email and email == keep_top_email:
            summary.skipped_keep_top += 1
            continue
        if dedupe:
            seen.add(email)
        selected.append(row)

    summary.appended = len(selected)
    return selected, summary.inspected, summary


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    src_path = Path(args.src)
    dst_paths = [Path(p) for p in args.dst]

    keep_top_email = norm_email(args.keep_top_email)
    top_row: Optional[Row] = None
    if keep_top_email:
        top_row = Row(
            email=args.keep_top_email.strip(),
            first_name=first_name_only(args.keep_top_name or ""),
        )

    want_count = args.count
    if want_count < 0:
        print("ERROR: --count must be >= 0", file=sys.stderr)
        return 2

    dedupe = not args.no_dedupe
    with lock_files([src_path, *dst_paths]):
        _, src_rows = read_rows_csv(src_path)
        existing_rows_by_file, existing_emails = load_existing_emails(dst_paths)

        pulled, inspected_count, summary = select_rows_for_distribution(
            src_rows,
            existing_emails,
            want_count,
            dedupe,
            keep_top_email,
        )

        buckets: List[List[Row]] = [[] for _ in range(5)]
        for bucket_idx, row in zip(cycle(range(5)), pulled):
            buckets[bucket_idx].append(row)

        remaining = src_rows[inspected_count:] if args.remove else list(src_rows)
        removed_count = inspected_count if args.remove else 0

        before_counts = [len(rows) for rows in existing_rows_by_file]
        after_counts: List[int] = []
        top_deltas: List[int] = []

        for i, dst in enumerate(dst_paths):
            existing = existing_rows_by_file[i]
            existing_without_top = (
                [r for r in existing if norm_email(r.email) != keep_top_email]
                if keep_top_email
                else list(existing)
            )
            out_rows = (
                ([top_row] if top_row else []) + existing_without_top + buckets[i]
                if keep_top_email
                else existing_without_top + buckets[i]
            )
            top_deltas.append(len(out_rows) - before_counts[i] - len(buckets[i]))
            if not args.dry_run:
                write_rows_csv(dst, out_rows)
                after_counts.append(len(read_rows_csv(dst)[1]))
            else:
                after_counts.append(len(out_rows))

        if not args.dry_run and args.remove:
            write_rows_csv(src_path, remaining)
            remaining_count = len(read_rows_csv(src_path)[1])
        else:
            remaining_count = len(remaining)

    requested_display = "all" if want_count == 0 else str(want_count)
    print(
        f"Source={src_path.name} requested={requested_display} inspected={summary.inspected} "
        f"appended={summary.appended} skipped_existing={summary.skipped_existing} "
        f"skipped_source_dupe={summary.skipped_source_dupe} skipped_keep_top={summary.skipped_keep_top} "
        f"removed={removed_count} remaining={remaining_count}"
    )
    for i, bucket in enumerate(buckets, start=1):
        message = (
            f"{dst_paths[i-1].name}: before={before_counts[i-1]} +{len(bucket)} => after={after_counts[i-1]}"
        )
        if top_deltas[i - 1]:
            message += f" top_delta={top_deltas[i - 1]:+d}"
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
