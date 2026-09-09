from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import important_leads_workflow as wf


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _preview(tmp_path: Path, route: str, count: int = 4) -> dict[str, object]:
    headers = ["Email", "FirstName", "AuthorEmail", "AuthorName", "BookTitle"]
    rows = [
        {
            "Email": f"fresh{index}@example.test",
            "FirstName": f"Fresh{index}",
            "AuthorEmail": f"fresh{index}@example.test",
            "AuthorName": f"Fresh Author {index}",
            "BookTitle": f"Fresh Book {index}",
        }
        for index in range(count)
    ]
    master = tmp_path / "leads.csv"
    triaged = tmp_path / "leads_triaged_keep.csv"
    rejected = tmp_path / "leads_rejected.csv"
    verified = tmp_path / "leads_verified.csv"
    _write_csv(master, headers, rows)
    _write_csv(triaged, headers + ["Status"], [{**row, "Status": "KEEP"} for row in rows])
    _write_csv(rejected, headers, [])
    _write_csv(verified, headers, [])

    queues = [tmp_path / "recipients_private_jc.csv"] + [
        tmp_path / f"recipients_sendgrid_{index}.csv" for index in range(1, 6)
    ]
    logs = [tmp_path / "private_jc_log.csv"] + [
        tmp_path / f"sendgrid_{index}_log.csv" for index in range(1, 6)
    ]
    for path in queues:
        _write_csv(path, headers, [])
    for path in logs:
        _write_csv(path, ["TimestampUTC", "Email", "Status", "Info"], [])

    suppressions = tmp_path / "sendgrid_suppressions.csv"
    suppressed = tmp_path / "suppressed.csv"
    unsubscribed = tmp_path / "unsubscribed.csv"
    _write_csv(suppressions, ["Email"], [])
    _write_csv(suppressed, ["Email"], [])
    _write_csv(unsubscribed, ["Email"], [])

    with patch.object(wf, "_unresolved_idempotency_emails", return_value=set()):
        return wf.preview_dispatch_master_leads(
            master_path=master,
            rejected_path=rejected,
            verified_path=verified,
            triaged_keep_path=triaged,
            dispatch_source_mode=wf.DISPATCH_SOURCE_TRIAGED_KEEP,
            campaign_type=wf.CAMPAIGN_TYPE_COLD,
            fresh_cold_route=route,
            jc_queue_path=queues[0],
            sendgrid_queue_paths=queues[1:],
            jc_log_path=logs[0],
            sendgrid_log_paths=logs[1:],
            sendgrid_suppressions_path=suppressions,
            suppressed_path=suppressed,
            unsubscribed_path=unsubscribed,
            lead_ledger_db_path=tmp_path / "lead_ledger.sqlite3",
            preview_dir=tmp_path / "dispatch_previews",
        )


@pytest.mark.parametrize(
    ("route", "expected_private", "expected_sendgrid"),
    [
        ("sendgrid", 0, 4),
        ("private_jc", 4, 0),
        ("both", 2, 2),
    ],
)
def test_fresh_cold_route_controls_destination_family(
    tmp_path: Path,
    route: str,
    expected_private: int,
    expected_sendgrid: int,
) -> None:
    preview = _preview(tmp_path, route)
    assert preview["fresh_cold_route"] == route
    assert preview["private_jc_planned_count"] == expected_private
    assert preview["sendgrid_planned_count"] == expected_sendgrid
    assert preview["total_planned_unique_count"] == 4
    assert preview["duplicate_planned_email_count"] == 0
    assert preview["fresh_cold_route_binding"] == wf._fresh_cold_route_binding(preview)


def test_fresh_cold_route_mismatch_fails_closed(tmp_path: Path) -> None:
    preview = _preview(tmp_path, "sendgrid")
    with pytest.raises(RuntimeError, match="Fresh Cold route is missing or mismatched"):
        wf._validate_fresh_cold_route_request(preview, "private_jc")


def test_fresh_cold_archived_route_authority_detects_tampering(tmp_path: Path) -> None:
    preview = _preview(tmp_path, "sendgrid")
    preview_path = Path(str(preview["preview_path"]))
    payload = json.loads(preview_path.read_text(encoding="utf-8"))
    payload["fresh_cold_route"] = "private_jc"
    preview_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        wf.validate_dispatch_preview(str(preview["preview_id"]), preview_dir=preview_path.parent)


def test_dashboard_and_frontend_contract_is_explicit() -> None:
    dash = Path("live_dashboard.py").read_text(encoding="utf-8")
    app = Path("web_dashboard/app.js").read_text(encoding="utf-8")
    assert 'fresh_cold_route: str = ""' in dash
    assert '"fresh_cold_route": str(fresh_cold_route or "").strip()' in dash
    assert 'fresh_cold_route=requested_fresh_cold_route' in dash
    assert 'data-fresh-cold-route' in app
    assert 'value="sendgrid"' in app
    assert 'value="private_jc"' in app
    assert 'value="both"' in app
    assert '{ fresh_cold_route: selectedFreshColdRoute }' in app


def test_legacy_implicit_both_preview_can_confirm_route_request_omission(tmp_path: Path) -> None:
    preview = _preview(tmp_path, "both")
    preview["fresh_cold_route_explicit"] = False
    preview["fresh_cold_route_binding"] = wf._fresh_cold_route_binding(preview)
    wf._validate_fresh_cold_route_request(preview, None)


def test_explicit_both_preview_still_requires_confirm_route(tmp_path: Path) -> None:
    preview = _preview(tmp_path, "both")
    assert preview["fresh_cold_route_explicit"] is True
    with pytest.raises(RuntimeError, match="Fresh Cold route is missing or mismatched"):
        wf._validate_fresh_cold_route_request(preview, None)
