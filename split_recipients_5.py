#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_HEADERS = ["Email", "AuthorName", "BookTitle"]


def norm_email(s: str) -> str:
    return (s or "").strip().lower()


@dataclass(frozen=True)
class Row:
    email: str
    author_name: str
    book_title: str

    def as_dict(self) -> Dict[str, str]:
        return {"Email": self.email, "AuthorName": self.author_name, "BookTitle": self.book_title}


def detect_fieldnames(fieldnames: Optional[Sequence[str]]) -> Tuple[str, str, str]:
    if not fieldnames:
        return ("Email", "AuthorName", "BookTitle")

    # Handle BOM in first header (common on Windows exports)
    fn = [f.lstrip("\ufeff") for f in fieldnames]
    lower = {f.lower(): f for f in fn}

    def pick(candidates: Sequence[str]) -> Optional[str]:
        for c in candidates:
            if c in lower:
                return lower[c]
        return None

    email_key = pick(["email", "e-mail", "e_mail", "mail", "address"]) or fn[0]
    name_key = pick(["authorname", "author_name", "name", "firstname", "first_name"]) or (fn[1] if len(fn) > 1 else fn[0])
    title_key = pick(["booktitle", "book_title", "title", "book"]) or (fn[2] if len(fn) > 2 else fn[-1])

    return (email_key, name_key, title_key)


def read_rows_csv(path: Path) -> Tuple[List[str], List[Row]]:
    if not path.exists():
        return (DEFAULT_HEADERS[:], [])

    with path.open("r", newline="", encoding="utf-8", errors="replace") as f:
        # Allow completely empty files
        sample = f.read(4096)
        if not sample.strip():
            return (DEFAULT_HEADERS[:], [])
        f.seek(0)

        reader = csv.DictReader(f)
        email_key, name_key, title_key = detect_fieldnames(reader.fieldnames)
        headers = DEFAULT_HEADERS[:]

        out: List[Row] = []
        for r in reader:
            email = (r.get(email_key) or "").strip()
            if not email:
                continue
            out.append(
                Row(
                    email=email,
                    author_name=(r.get(name_key) or "").strip(),
                    book_title=(r.get(title_key) or "").strip(),
                )
            )
        return (headers, out)


def write_rows_csv(path: Path, rows: Iterable[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DEFAULT_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([r.as_dict() for r in rows])


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
    ap.add_argument("--count", type=int, default=100, help="How many rows to pull from --src (0 = all)")
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
    ap.add_argument("--keep-top-title", default="", help="Title for --keep-top-email (optional)")
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


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    src_path = Path(args.src)
    dst_paths = [Path(p) for p in args.dst]

    _, src_rows = read_rows_csv(src_path)
    existing_rows_by_file, existing_emails = load_existing_emails(dst_paths)

    keep_top_email = norm_email(args.keep_top_email)
    top_row: Optional[Row] = None
    if keep_top_email:
        top_row = Row(
            email=args.keep_top_email.strip(),
            author_name=(args.keep_top_name or "").strip(),
            book_title=(args.keep_top_title or "").strip(),
        )

    want_count = args.count
    if want_count < 0:
        print("ERROR: --count must be >= 0", file=sys.stderr)
        return 2

    max_to_take = len(src_rows) if want_count == 0 else min(want_count, len(src_rows))
    pulled_candidate_rows = src_rows[:max_to_take]

    dedupe = not args.no_dedupe
    seen: set = set()
    pulled: List[Row] = []
    pulled_set: set = set()

    for r in pulled_candidate_rows:
        ne = norm_email(r.email)
        if not ne:
            continue
        if dedupe:
            if ne in seen:
                continue
            if ne in existing_emails:
                continue
            if keep_top_email and ne == keep_top_email:
                continue
        seen.add(ne)
        pulled.append(r)
        pulled_set.add(ne)

    # Distribute pulled rows round-robin across 5 buckets
    buckets: List[List[Row]] = [[] for _ in range(5)]
    for bucket_idx, row in zip(cycle(range(5)), pulled):
        buckets[bucket_idx].append(row)

    # Write destinations
    if not args.dry_run:
        for i, dst in enumerate(dst_paths):
            if args.append:
                existing = existing_rows_by_file[i]
            else:
                # Rewrite/normalize file, but keep existing rows too (safer than wiping)
                existing = existing_rows_by_file[i]

            # Remove any existing keep-top row to avoid duplicates, then prepend it
            if keep_top_email:
                existing = [r for r in existing if norm_email(r.email) != keep_top_email]
                out_rows = ([top_row] if top_row else []) + existing + buckets[i]
            else:
                out_rows = existing + buckets[i]

            write_rows_csv(dst, out_rows)

        if args.remove:
            # Remove the first N rows from the source (the "pulled" slice),
            # regardless of whether individual rows were skipped by dedupe.
            remaining = src_rows[max_to_take:]
            removed_count = max_to_take
            write_rows_csv(src_path, remaining)
        else:
            remaining = src_rows
            removed_count = 0
    else:
        remaining = src_rows[max_to_take:] if args.remove else src_rows
        removed_count = max_to_take if args.remove else 0

    print(
        f"Pulled={len(pulled)} requested={want_count} "
        f"from={src_path.name} removed={removed_count if args.remove else 0} remaining={len(remaining)}"
    )
    for i, b in enumerate(buckets, start=1):
        print(f"{dst_paths[i-1].name}: +{len(b)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
