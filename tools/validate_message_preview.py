#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Literal, Sequence

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import settings
from send_shard import BOOK_TITLE_GENERIC_OPENING


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONEISH_RE = re.compile(r"^[+()\d\s.\-]{7,}$")
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
BAD_LITERAL_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:nan|none)(?![A-Za-z0-9])")
BAD_PLACEHOLDERS = ("{FirstName}", "{BookTitle}", "{PersonalizedOpeningLine}")
CONSIGNMENT_SUBJECT_FALLBACK = "Bookstore shelf review"
CONSIGNMENT_SUBJECT_FALLBACKS = {
    "Bookstore shelf review",
    "Independent author shelf review opportunity",
    "Independent author shelf consideration",
    "Bookstore placement review",
    "Regarding your book",
    "Independent author review",
}
ASTRA_VISUAL_SUBJECT_FALLBACK = "A trailer idea for independent authors"
BOOK_TITLE_PERSONALIZED_OPENINGS = (
    "My team came across",
)
CONSIGNMENT_SUBJECT_TEMPLATES = (
    "Shelf review: {book_title}",
    "Shelf review opportunity for {book_title}",
    "Shelf consideration for {book_title}",
    "Reviewing {book_title} for bookstore placement",
    "Regarding {book_title}",
    "Independent author review: {book_title}",
)
BAD_AUTHOR_NAMES = {
    "authorhouseuk",
    "cancelled",
    "complete",
    "iuniverse",
    "n/a",
    "na",
    "resubmission",
    "test",
    "unknown",
    "xlibris",
}
BAD_BOOK_VALUES = BAD_AUTHOR_NAMES | {
    "authorhouse",
    "authorhouse uk",
    "bookbaby",
    "completed",
    "draft2digital",
    "in progress",
    "kindle direct publishing",
    "kdp",
    "lulu",
    "pending",
    "published",
    "rejected",
    "submitted",
    "untitled",
    "your book",
}
ASTRA_SERVICE_TERMS = ("author website", "book trailer", "launch visuals", "online presentation")
ASTRA_LANGUAGE_TERMS = ("astra productions", "cinematic book trailer", "launch visuals")
CONSIGNMENT_LANGUAGE_TERMS = (
    "consignment",
    "stocking any book",
    "retail-ready",
    "sale price",
    "shipping to the store",
    "sales reporting",
    "title for review",
)
OUTPUT_FIELDS = [
    "Email",
    "AuthorEmail",
    "AuthorName",
    "FirstName",
    "BookTitle",
    "PersonalizedOpeningLine",
    "Subject",
    "Body",
    "ValidationStatus",
    "FailureReasons",
]
PreviewMode = Literal["astra_visual", "bulk_book_title", "consignment", "researched"]


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


BAD_AUTHOR_KEYS = {normalize_key(value) for value in BAD_AUTHOR_NAMES}
BAD_BOOK_KEYS = {normalize_key(value) for value in BAD_BOOK_VALUES}


def normalize_space(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def canonical_mode(mode: str) -> PreviewMode:
    raw = str(mode or "").strip().lower()
    if raw == "bulk_book_title":
        return "consignment"
    if raw in {"astra_visual", "consignment", "researched"}:
        return raw  # type: ignore[return-value]
    return "consignment"


def default_preview_path(profile: str) -> Path:
    safe_profile = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(profile or "").strip() or "sender")
    return settings.APP_ROOT / "data" / "message_previews" / f"{safe_profile}_message_preview.csv"


def output_paths(input_path: Path) -> tuple[Path, Path, Path]:
    stem = input_path.stem
    if stem.endswith("_message_preview"):
        base = stem[: -len("_message_preview")]
    else:
        base = stem
    parent = input_path.parent
    return (
        parent / f"{base}_message_preview_validated.csv",
        parent / f"{base}_message_preview_failed.csv",
        parent / f"{base}_message_preview_summary.txt",
    )


def read_rows(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(field or "").lstrip("\ufeff").strip() for field in (reader.fieldnames or [])]
        rows = [
            {field: str(row.get(field, "") or "").strip() for field in fieldnames}
            for row in reader
        ]
    return fieldnames, rows


def write_rows(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def first_nonblank_line(text: str) -> str:
    for line in str(text or "").splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


def contains_bad_render_tokens(value: str, field_name: str) -> List[str]:
    failures: List[str] = []
    for placeholder in BAD_PLACEHOLDERS:
        if placeholder in value:
            failures.append(f"{field_name}_unrendered_placeholder:{placeholder}")
    if BAD_LITERAL_RE.search(value or ""):
        failures.append(f"{field_name}_bad_literal_nan_or_none")
    return failures


def book_title_failures(book_title: str) -> List[str]:
    title = normalize_space(book_title)
    normalized = normalize_key(title)
    failures: List[str] = []
    if EMAIL_RE.match(title):
        failures.append("book_title_looks_like_email")
    if URL_RE.search(title):
        failures.append("book_title_looks_like_url")
    digits = re.sub(r"\D+", "", title)
    if PHONEISH_RE.match(title) and len(digits) >= 7:
        failures.append("book_title_looks_like_phone")
    if title.startswith("{") and title.endswith("}"):
        failures.append("book_title_placeholder_value")
    if normalized in BAD_BOOK_KEYS:
        failures.append("book_title_status_or_publisher")
    return failures


def validate_consignment_subject(subject: str, book_title: str, book_failures: Sequence[str]) -> List[str]:
    if book_title and not book_failures:
        expected_subjects = {template.format(book_title=book_title) for template in CONSIGNMENT_SUBJECT_TEMPLATES}
        if subject not in expected_subjects:
            return ["consignment_subject_mismatch"]
        return []
    if subject not in CONSIGNMENT_SUBJECT_FALLBACKS:
        return ["consignment_subject_fallback_required"]
    return []


def validate_book_title_fallback_rendering(subject: str, body: str, mode: PreviewMode) -> List[str]:
    failures: List[str] = []
    if mode == "astra_visual":
        expected_subjects = {ASTRA_VISUAL_SUBJECT_FALLBACK}
    else:
        expected_subjects = CONSIGNMENT_SUBJECT_FALLBACKS
    if subject not in expected_subjects:
        failures.append("book_title_subject_fallback_required")
    if BOOK_TITLE_GENERIC_OPENING not in body:
        failures.append("book_title_generic_opening_missing")
    body_lower = body.lower()
    if any(opening.lower() in body_lower for opening in BOOK_TITLE_PERSONALIZED_OPENINGS):
        failures.append("book_title_personalized_opening_not_removed")
    if "{BookTitle}" in body:
        failures.append("body_unrendered_placeholder:{BookTitle}")
    if re.search(r"\bcame across your book\b", body_lower):
        failures.append("body_generic_your_book")
    return failures


def validate_row(row: Dict[str, str], mode: PreviewMode) -> List[str]:
    email = normalize_space(row.get("Email", ""))
    author_name = normalize_space(row.get("AuthorName", ""))
    first_name = normalize_space(row.get("FirstName", ""))
    book_title = normalize_space(row.get("BookTitle", ""))
    opening = normalize_space(row.get("PersonalizedOpeningLine", ""))
    subject = normalize_space(row.get("Subject", ""))
    body = str(row.get("Body", "") or "")
    combined_text = f"{subject}\n{body}".lower()

    failures: List[str] = []
    if not email:
        failures.append("missing_email")
    elif not EMAIL_RE.match(email):
        failures.append("invalid_email_syntax")
    if mode == "researched" and not author_name:
        failures.append("missing_author_name")
    elif normalize_key(author_name) in BAD_AUTHOR_KEYS:
        failures.append("bad_author_name_status")
    if mode in {"astra_visual", "consignment"} and not first_name:
        failures.append("missing_first_name")
    elif normalize_key(first_name) in BAD_AUTHOR_KEYS:
        failures.append("bad_first_name_status")

    book_failures: List[str] = []
    if book_title:
        book_failures = book_title_failures(book_title)
    safe_book_title = bool(book_title) and not book_failures
    fallback_capable_mode = mode in {"astra_visual", "consignment"}

    if mode == "researched":
        if not safe_book_title:
            failures.append("missing_book_title" if not book_title else "unsafe_book_title")
            failures.extend(book_failures)
        if not opening:
            failures.append("missing_personalized_opening_line")
        elif opening not in body:
            failures.append("body_missing_personalized_opening_line")
    if mode == "consignment":
        if safe_book_title:
            failures.extend(validate_consignment_subject(subject, book_title, book_failures))
        else:
            failures.extend(validate_book_title_fallback_rendering(subject, body, mode))
        if any(term in combined_text for term in ASTRA_LANGUAGE_TERMS):
            failures.append("consignment_contains_astra_visual_language")
        if "consignment" not in combined_text:
            failures.append("consignment_language_missing")
    if mode == "astra_visual":
        if not safe_book_title:
            failures.extend(validate_book_title_fallback_rendering(subject, body, mode))
        if any(term in combined_text for term in CONSIGNMENT_LANGUAGE_TERMS):
            failures.append("astra_visual_contains_consignment_language")
        for term in ASTRA_SERVICE_TERMS:
            if term not in body.lower():
                failures.append(f"astra_visual_missing_service_term:{term}")

    if not fallback_capable_mode and not safe_book_title:
        failures.append("missing_book_title" if not book_title else "unsafe_book_title")
        failures.extend(book_failures)
    if safe_book_title and book_title not in body:
        failures.append("body_missing_book_title")
    if first_name:
        expected_greeting = f"Hi {first_name},"
        if first_nonblank_line(body) != expected_greeting:
            failures.append("greeting_first_name_mismatch")
    failures.extend(contains_bad_render_tokens(subject, "subject"))
    failures.extend(contains_bad_render_tokens(body, "body"))
    return failures


def summarize(mode: PreviewMode, total: int, passed: int, failed: int, reason_counts: Counter[str]) -> str:
    lines = [
        f"pitch mode: {mode}",
        f"total rows checked: {total}",
        f"passed rows: {passed}",
        f"failed rows: {failed}",
        "",
        "failure reasons:",
    ]
    if reason_counts:
        for reason, count in reason_counts.most_common():
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def validate_preview(input_path: Path, mode: PreviewMode = "bulk_book_title") -> Dict[str, object]:
    mode = canonical_mode(mode)
    fieldnames, rows = read_rows(input_path)
    required_columns = ["Email", "FirstName", "BookTitle", "Subject", "Body"]
    if mode == "researched":
        required_columns.extend(["AuthorName", "PersonalizedOpeningLine"])
    missing_columns = [f"missing_column:{field}" for field in required_columns if field not in fieldnames]
    passed_rows: List[Dict[str, str]] = []
    failed_rows: List[Dict[str, str]] = []
    reason_counts: Counter[str] = Counter()

    for raw_row in rows:
        row = {field: raw_row.get(field, "") for field in OUTPUT_FIELDS}
        failures = list(missing_columns)
        failures.extend(validate_row(row, mode))
        row["FailureReasons"] = ";".join(failures)
        if failures:
            row["ValidationStatus"] = "FAIL"
            failed_rows.append(row)
            reason_counts.update(failures)
        else:
            row["ValidationStatus"] = "PASS"
            passed_rows.append(row)

    validated_path, failed_path, summary_path = output_paths(input_path)
    write_rows(validated_path, passed_rows)
    write_rows(failed_path, failed_rows)
    summary = summarize(mode, len(rows), len(passed_rows), len(failed_rows), reason_counts)
    summary_path.write_text(summary, encoding="utf-8")
    return {
        "input_path": str(input_path),
        "validated_path": str(validated_path),
        "failed_path": str(failed_path),
        "summary_path": str(summary_path),
        "total": len(rows),
        "passed": len(passed_rows),
        "failed": len(failed_rows),
        "mode": mode,
        "reason_counts": dict(reason_counts),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate rendered sender message preview CSVs before sending.")
    parser.add_argument("--profile", default="", help="Profile name, e.g. sendgrid_annette.")
    parser.add_argument("--input", default="", help="Optional explicit message preview CSV path.")
    parser.add_argument(
        "--pitch-mode",
        choices=("astra_visual", "bulk_book_title", "consignment", "researched"),
        default="consignment",
        help="Validation rules to apply. bulk_book_title is a compatibility alias for consignment.",
    )
    parser.add_argument("--fail-on-errors", action="store_true", help="Exit non-zero when any preview row fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser() if args.input else default_preview_path(args.profile)
    if not input_path.is_absolute():
        input_path = settings.APP_ROOT / input_path
    if not input_path.exists():
        raise SystemExit(f"Preview file not found: {input_path}")

    result = validate_preview(input_path, args.pitch_mode)
    print(f"Checked {result['total']} row(s): {result['passed']} passed, {result['failed']} failed")
    print(f"Validated: {result['validated_path']}")
    print(f"Failed: {result['failed_path']}")
    print(f"Summary: {result['summary_path']}")
    if args.fail_on_errors and int(result["failed"] or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
