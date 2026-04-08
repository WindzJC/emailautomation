from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import tempfile
import time
import tracemalloc
import sys
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from important_leads_verify import verify_master_leads
from important_leads_workflow import check_master_leads, dispatch_master_leads


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_email(index: int) -> str:
    return f"lead{index:05d}@example.com"


def _build_check_rows(total: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(total):
        email = _make_email(index)
        first_name = f"Author{index:05d}"
        full_name = f"Author {index:05d}"
        if index % 17 == 0:
            email = f"{email.upper()}"
        if index % 23 == 0:
            email = email.replace("example.com", "gmail.com")
        if index % 29 == 0:
            full_name = ""
        if index % 31 == 0:
            first_name = ""
        rows.append(
            {
                "FullName": full_name,
                "FirstName": first_name,
                "Email": email,
                "Source": f"batch-{index % 5}",
            }
        )
    for dup_index in range(0, total, max(1, total // 20)):
        rows.append(
            {
                "FullName": f"Duplicate {dup_index}",
                "FirstName": f"Dup{dup_index}",
                "Email": _make_email(dup_index),
                "Source": "dup",
            }
        )
    random.shuffle(rows)
    return rows


def _extract_benchmark_identity(query: str) -> tuple[str, str]:
    quoted = [part.strip() for part in query.split('"') if part.strip()]
    name = quoted[0] if quoted else ""
    email = ""
    for token in query.split():
        token = token.strip(",;:!?()[]{}<>\"'")
        if "@" in token and "." in token:
            email = token.lower()
            break
    return name, email


def _make_verification_searcher():
    def searcher(query: str) -> list[dict[str, str]]:
        digest = hashlib.sha1(query.encode("utf-8")).hexdigest()
        bucket = int(digest[:2], 16) % 5
        if bucket == 0:
            status = "keep"
            source_type = "publisher"
        elif bucket == 1:
            status = "reject"
            source_type = "official"
        elif bucket == 2:
            status = "quarantine_name"
            source_type = "official"
        elif bucket == 3:
            status = "quarantine_email"
            source_type = "publisher"
        else:
            status = "quarantine_none"
            source_type = "official"
        name, email = _extract_benchmark_identity(query)
        payload = quote(
            json.dumps(
                {
                    "query": query,
                    "name": name,
                    "email": email,
                    "status": status,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            safe="",
        )
        return [
            {
                "url": f"https://benchmark.example.test/{status}/{payload}",
                "source_type": source_type,
                "note": status,
            }
        ]

    return searcher


def _make_verification_fetcher():
    def fetcher(url: str) -> dict[str, object]:
        parts = url.rstrip("/").split("/")
        status = parts[-2] if len(parts) >= 2 else "quarantine_none"
        payload = {}
        try:
            payload = json.loads(unquote(parts[-1]))
        except Exception:
            payload = {}
        query = str(payload.get("query") or "")
        name = str(payload.get("name") or "")
        email = str(payload.get("email") or "")
        if status == "keep":
            return {
                "url": url,
                "final_url": url,
                "status_code": 200,
                "robots_allowed": True,
                "fetched_at": "2026-04-09T00:00:00+00:00",
                "html_text": (
                    "<html><head>"
                    f"<title>{name or 'Author Match'}</title>"
                    f"<meta name='author' content='{name or 'Author Match'}'>"
                    "</head><body>"
                    f"<h1>{name or 'Author Match'}</h1>"
                    f"<p>Contact: <a href='mailto:{email or 'author@example.com'}'>{email or 'author@example.com'}</a></p>"
                    "</body></html>"
                ),
            }
        if status == "reject":
            return {
                "url": url,
                "final_url": url,
                "status_code": 200,
                "robots_allowed": True,
                "fetched_at": "2026-04-09T00:00:00+00:00",
                "html_text": (
                    "<html><head><title>Different Person</title></head><body>"
                    "<h1>Different Person</h1>"
                    "<p>Contact: other@example.com</p>"
                    "</body></html>"
                ),
            }
        if status == "quarantine_name":
            return {
                "url": url,
                "final_url": url,
                "status_code": 200,
                "robots_allowed": True,
                "fetched_at": "2026-04-09T00:00:00+00:00",
                "html_text": (
                    "<html><head><title>Author Bio</title></head><body>"
                    f"<h1>{name or 'Author Bio'}</h1>"
                    "<p>Bio text without a public email.</p>"
                    "</body></html>"
                ),
            }
        if status == "quarantine_email":
            return {
                "url": url,
                "final_url": url,
                "status_code": 200,
                "robots_allowed": True,
                "fetched_at": "2026-04-09T00:00:00+00:00",
                "html_text": (
                    "<html><head><title>Contact Page</title></head><body>"
                    f"<p>Contact: <a href='mailto:{email or 'someone@example.com'}'>{email or 'someone@example.com'}</a></p>"
                    "</body></html>"
                ),
            }
        return {
            "url": url,
            "final_url": url,
            "status_code": 200,
            "robots_allowed": True,
            "fetched_at": "2026-04-09T00:00:00+00:00",
            "html_text": (
                "<html><head><title>Proof Page</title></head><body>"
                f"<p>{query}</p>"
                "<p>No clear identity or email proof here.</p>"
                "</body></html>"
            ),
        }

    return fetcher


def _measure(fn):
    tracemalloc.start()
    start = time.perf_counter()
    result = fn()
    seconds = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, seconds, peak / (1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the important leads pipeline.")
    parser.add_argument("--check-rows", type=int, default=50000)
    parser.add_argument("--verify-rows", type=int, default=5000)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw_path = tmp / "important_check_input.csv"
        checked_path = tmp / "important_checked.csv"
        rejected_path = tmp / "important_rejected.csv"
        verified_path = tmp / "important_verified.csv"
        verify_rejected = tmp / "important_verify_rejected.csv"
        quarantine_path = tmp / "important_quarantine.csv"
        dispatch_verified = tmp / "important_dispatch_verified.csv"
        jc_queue = tmp / "recipients_private_jc.csv"
        sg_queue_paths = [tmp / f"recipients_sendgrid_{idx}.csv" for idx in range(1, 6)]
        jc_log = tmp / "private_jc_log.csv"
        sg_logs = [tmp / f"sendgrid_{idx}.csv" for idx in range(1, 6)]

        check_rows = _build_check_rows(args.check_rows)
        _write_csv(raw_path, ["FullName", "FirstName", "Email", "Source"], check_rows)

        def run_check():
            return check_master_leads(
                input_path=raw_path,
                output_path=checked_path,
                rejected_path=rejected_path,
                validate_deliverability=False,
                reject_role_accounts=False,
                reject_disposable=False,
                persist_state=False,
            )

        check_report, check_seconds, check_peak = _measure(run_check)

        with checked_path.open("r", encoding="utf-8") as handle:
            checked_rows = list(csv.DictReader(handle))
        verified_rows = []
        for row in checked_rows[: args.verify_rows]:
            row = dict(row)
            row["Status"] = "KEEP"
            verified_rows.append(row)
        if not verified_rows:
            verified_rows = [{"FullName": "Author One", "FirstName": "Author", "Email": "author@example.com", "Status": "KEEP"}]
        _write_csv(verified_path, list(verified_rows[0].keys()), verified_rows)

        def run_verify():
            return verify_master_leads(
                input_path=checked_path,
                verified_path=verified_path,
                rejected_path=verify_rejected,
                quarantine_path=quarantine_path,
                persist_state=False,
                searcher=_make_verification_searcher(),
                fetcher=_make_verification_fetcher(),
                max_workers=8,
                timeout_seconds=5,
                max_pages_per_lead=1,
                retries=1,
                respect_robots=False,
                allow_social_proof=True,
                validate_deliverability=False,
            )

        verify_report, verify_seconds, verify_peak = _measure(run_verify)

        for path in [jc_queue, *sg_queue_paths, jc_log, *sg_logs]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

        def run_dispatch():
            return dispatch_master_leads(
                master_path=checked_path,
                verified_path=verified_path,
                dispatch_source_mode="verified",
                require_stopped=False,
                jc_queue_path=jc_queue,
                sendgrid_queue_paths=sg_queue_paths,
                jc_log_path=jc_log,
                sendgrid_log_paths=sg_logs,
                persist_state=False,
            )

        dispatch_report, dispatch_seconds, dispatch_peak = _measure(run_dispatch)

        result = {
            "check": {
                "seconds": round(check_seconds, 3),
                "peak_mb": round(check_peak, 2),
                "input_rows": check_report.get("input_rows"),
                "cleaned_rows": check_report.get("cleaned_rows"),
                "rejected_rows": check_report.get("rejected_rows"),
            },
            "verify": {
                "seconds": round(verify_seconds, 3),
                "peak_mb": round(verify_peak, 2),
                "keep_count": verify_report.get("keep_count"),
                "reject_count": verify_report.get("reject_count"),
                "quarantine_count": verify_report.get("quarantine_count"),
            },
            "dispatch": {
                "seconds": round(dispatch_seconds, 3),
                "peak_mb": round(dispatch_peak, 2),
                "dispatch_source_row_count": dispatch_report.get("dispatch_source_row_count"),
                "dispatch_eligible_row_count": dispatch_report.get("dispatch_eligible_row_count"),
                "added_astra": dispatch_report.get("added_astra"),
                "added_sendgrid": dispatch_report.get("added_sendgrid"),
            },
            "bottleneck": max(
                (
                    ("check", check_seconds),
                    ("verify", verify_seconds),
                    ("dispatch", dispatch_seconds),
                ),
                key=lambda item: item[1],
            )[0],
            "rows_per_second": {
                "check": round((check_report.get("input_rows") or 0) / check_seconds, 2) if check_seconds else 0.0,
                "verify": round((verify_report.get("processed_rows") or 0) / verify_seconds, 2) if verify_seconds else 0.0,
                "dispatch": round((dispatch_report.get("dispatch_source_row_count") or 0) / dispatch_seconds, 2) if dispatch_seconds else 0.0,
            },
        }
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
