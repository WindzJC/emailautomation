from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import runtime_handoff

PROFILE = "sendgrid_annette"


def _report(emails: list[str], validated: bool) -> dict[str, object]:
    headers = ["Email", "AuthorEmail", "AuthorName", "FirstName", "BookTitle", "Opening", "Subject", "Body"]
    if validated:
        headers += ["ValidationStatus", "ValidationReason"]
    rows = {}
    for email in emails:
        row = {
            "Email": email,
            "AuthorEmail": email,
            "AuthorName": "Test Author",
            "FirstName": "Test",
            "BookTitle": "Book",
            "Opening": "Opening",
            "Subject": "Subject",
            "Body": "Body",
        }
        if validated:
            row["ValidationStatus"] = "PASS"
            row["ValidationReason"] = ""
        rows[email] = row
    return {
        "exists": True,
        "row_count": len(emails),
        "emails": set(emails),
        "ordered_emails": list(emails),
        "rows_by_email": rows,
        "fingerprint": runtime_handoff._email_fingerprint(emails),
        "headers": headers,
        "missing_fields": [],
        "duplicate_headers": [],
        "extra_column_rows": 0,
        "blank_email_rows": 0,
        "malformed_email_rows": 0,
        "conflicting_email_rows": 0,
        "duplicate_email_rows": 0,
        "non_pass_rows": 0,
        "parse_error": "",
    }


def _fixture(tmp_path: Path, current=None, terminal="SENT"):
    repo = tmp_path / "repo"
    queue_dir = repo / "data/shards"
    log_dir = repo / "data/logs"
    state_dir = repo / "data/state"
    dispatch_dir = repo / "_important/dispatch_jobs/previews"
    for p in (queue_dir, log_dir, state_dir, dispatch_dir):
        p.mkdir(parents=True, exist_ok=True)

    plan = ["first@example.test", "second@example.test", "third@example.test"]
    current = list(current or plan[1:])
    queue_path = queue_dir / "recipients_sendgrid_1.csv"
    with queue_path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["Email", "FirstName", "BookTitle"])
        w.writeheader()
        for email in current:
            w.writerow({"Email": email, "FirstName": "Test", "BookTitle": "Book"})

    preview_id = "dispatch_preview_normal_progress"
    manifest = {"preview_id": preview_id, "snapshot_type": "confirmed_dispatch"}
    (state_dir / "active_campaign_snapshot.json").write_text(json.dumps(manifest), encoding="utf-8")
    (dispatch_dir / f"{preview_id}.json").write_text(
        json.dumps({
            "preview_id": preview_id,
            "campaign_id": "cold",
            "plan_rows_by_queue": {
                "sendgrid_1": [
                    {"Email": email, "FirstName": "Test", "BookTitle": "Book"}
                    for email in plan
                ]
            },
        }),
        encoding="utf-8",
    )

    removed = [email for email in plan if email not in set(current)]
    with (log_dir / f"{PROFILE}_log.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["TimestampUTC", "Email", "Status", "Info"])
        w.writeheader()
        for email in removed:
            if terminal == "MISSING":
                continue
            if terminal == "GENERIC_SKIP":
                w.writerow({"TimestampUTC": "2026-08-11T00:00:00Z", "Email": email, "Status": "SKIP", "Info": "event_type=SKIPPED_SUPPRESSED"})
            else:
                w.writerow({"TimestampUTC": "2026-08-11T00:00:00Z", "Email": email, "Status": "SENT", "Info": "campaign_type=cold"})

    failed = _report([], True)
    return {
        "repo": repo,
        "queue_path": queue_path,
        "queue_state": runtime_handoff._read_queue_state(queue_path, PROFILE),
        "manifest": manifest,
        "generated": _report(plan, False),
        "validated": _report(plan, True),
        "failed": failed,
        "summary": {"exists": True, "parse_error": "", "missing_fields": [], "duplicate_fields": [], "counts": {"total": 3, "passed": 3, "failed": 0}, "mode": "astra_visual"},
    }


def _run(f):
    return runtime_handoff._normal_queue_progress_match(
        f["repo"], profile=PROFILE, manifest=f["manifest"], queue_path=f["queue_path"],
        queue_state=f["queue_state"], generated=f["generated"], validated=f["validated"],
        failed=f["failed"], summary=f["summary"], expected_mode="astra_visual"
    )


def test_normal_progress_accepts_authoritative_sent_remainder(tmp_path):
    r = _run(_fixture(tmp_path))
    assert r["safe"] is True
    assert r["verified_normal_queue_progress"] is True
    assert r["removed_rows"] == 1
    assert r["terminal_sent_rows"] == 1


def test_normal_progress_rejects_missing_terminal(tmp_path):
    r = _run(_fixture(tmp_path, terminal="MISSING"))
    assert r["safe"] is False
    assert "normal_progress_every_removed_recipient_has_terminal_result" in r["failed_predicates"]


def test_normal_progress_rejects_generic_skip(tmp_path):
    r = _run(_fixture(tmp_path, terminal="GENERIC_SKIP"))
    assert r["safe"] is False
    assert "normal_progress_no_generic_or_non_authoritative_results" in r["failed_predicates"]


def test_normal_progress_rejects_reordered_survivors(tmp_path):
    r = _run(_fixture(tmp_path, current=["third@example.test", "second@example.test"]))
    assert r["safe"] is False
    assert "normal_progress_remaining_queue_order_preserved" in r["failed_predicates"]


def test_normal_progress_rejects_changed_survivor(tmp_path):
    f = _fixture(tmp_path)
    p = f["queue_path"]
    p.write_text(p.read_text(encoding="utf-8").replace("second@example.test,Test,Book", "second@example.test,Changed,Book"), encoding="utf-8")
    f["queue_state"] = runtime_handoff._read_queue_state(p, PROFILE)
    r = _run(f)
    assert r["safe"] is False
    assert "normal_progress_surviving_queue_rows_unchanged" in r["failed_predicates"]


def test_normal_progress_rejects_inserted_recipient(tmp_path):
    r = _run(_fixture(tmp_path, current=["second@example.test", "inserted@example.test"]))
    assert r["safe"] is False
    assert "normal_progress_no_new_recipients_added" in r["failed_predicates"]
