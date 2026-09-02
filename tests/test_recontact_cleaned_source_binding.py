from pathlib import Path

import live_dashboard as dashboard


def test_recontact_cleaned_preview_uses_latest_staged_checked_output(
    tmp_path,
    monkeypatch,
):
    global_input = tmp_path / "global_input.csv"
    global_cleaned = tmp_path / "global_leads.csv"
    global_rejected = tmp_path / "global_rejected.csv"
    global_verified = tmp_path / "global_verified.csv"
    global_keep = tmp_path / "global_keep.csv"

    staged_dir = (
        tmp_path
        / "runs"
        / "check_20260831_222138_b8d2806e"
    )
    staged_dir.mkdir(parents=True)

    staged_cleaned = staged_dir / "leads.csv"
    staged_rejected = staged_dir / "leads_rejected.csv"
    staged_keep = staged_dir / "leads_triaged_keep.csv"

    for path in (
        global_input,
        global_cleaned,
        global_rejected,
        global_verified,
        global_keep,
        staged_cleaned,
        staged_rejected,
        staged_keep,
    ):
        path.write_text(
            "Email,AuthorName\n"
            "test@example.com,Test Author\n",
            encoding="utf-8",
        )

    # Deliberately make the global cleaned artifact different.
    global_cleaned.write_text(
        "Email,AuthorName\n"
        "wrong@example.com,Wrong Global Source\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        dashboard,
        "_build_live_snapshot",
        lambda: {},
    )

    monkeypatch.setattr(
        dashboard,
        "_dispatch_preflight_block_response",
        lambda snapshot: None,
    )

    monkeypatch.setattr(
        dashboard,
        "important_leads_path_state",
        lambda: {
            "input_path": str(global_input),
            "output_path": str(global_cleaned),
            "rejected_path": str(global_rejected),
        },
    )

    monkeypatch.setattr(
        dashboard,
        "important_leads_verify_path_state",
        lambda: {
            "verified_path": str(global_verified),
        },
    )

    monkeypatch.setattr(
        dashboard,
        "important_leads_triage_path_state",
        lambda: {
            "keep_path": str(global_keep),
        },
    )

    monkeypatch.setattr(
        dashboard,
        "_resolve_dashboard_csv_path",
        lambda value, default: Path(str(value)),
    )

    monkeypatch.setattr(
        dashboard,
        "_important_path_labels_for_state",
        lambda *args: {},
    )

    monkeypatch.setattr(
        dashboard,
        "_important_dispatch_source_labels_for_state",
        lambda *args: {},
    )

    monkeypatch.setattr(
        dashboard,
        "save_state",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        dashboard,
        "_latest_fast_triage_keep_source",
        lambda: {
            "source_resolution": "latest_completed_staged_run",
            "path": str(staged_keep),
            "paths": {
                "input": str(staged_cleaned),
                "keep": str(staged_keep),
                "rejected": str(staged_rejected),
            },
            "run_id": "check_20260831_222138_b8d2806e",
        },
    )

    seen = {}

    def find_progress_job(path):
        seen["progress_source"] = Path(path)
        # Force the synchronous Preview branch so the test can inspect
        # the exact paths supplied to preview_dispatch_master_leads.
        return None

    monkeypatch.setattr(
        dashboard,
        "_find_check_job_for_progress_source",
        find_progress_job,
    )

    def readiness_block(
        dispatch_source_mode,
        source_path,
        *,
        source_resolution="",
    ):
        seen["readiness_mode"] = dispatch_source_mode
        seen["readiness_source"] = Path(source_path)
        return None

    monkeypatch.setattr(
        dashboard,
        "_dispatch_source_readiness_block",
        readiness_block,
    )

    monkeypatch.setattr(
        dashboard,
        "_try_acquire_dispatch_preview_claim",
        lambda key: {
            "claim_token": "test-claim",
            "job_id": key,
        },
    )

    monkeypatch.setattr(
        dashboard,
        "_release_dispatch_preview_claim",
        lambda claim: None,
    )

    def fake_preview_dispatch_master_leads(**kwargs):
        seen["master_path"] = Path(kwargs["master_path"])
        seen["rejected_path"] = Path(kwargs["rejected_path"])
        seen["triaged_keep_path"] = Path(
            kwargs["triaged_keep_path"]
        )
        seen["dispatch_source_mode"] = kwargs[
            "dispatch_source_mode"
        ]
        seen["campaign_type"] = kwargs["campaign_type"]

        return {
            "preview_id": "dispatch_preview_test_recontact",
            "status": "previewed",
            "dispatch_source_name": "Checked Output",
            "dispatch_source_mode": "cleaned",
            "campaign_type": "recontact_cold",
        }

    monkeypatch.setattr(
        dashboard,
        "preview_dispatch_master_leads",
        fake_preview_dispatch_master_leads,
    )

    monkeypatch.setattr(
        dashboard,
        "_display_leads_status",
        lambda: {},
    )

    payload = dashboard.ImportantLeadDispatchPayload(
        campaign_type="recontact_cold",
        dispatch_source_mode="cleaned",
        dispatch_cap="all",
    )

    response = dashboard.preview_dispatch_important_leads(
        payload
    )

    assert response.status_code == 200

    # Critical regression contract:
    # Checked Recontact must use staged checked output.
    assert seen["master_path"] == staged_cleaned
    assert seen["progress_source"] == staged_cleaned
    assert seen["readiness_source"] == staged_cleaned
    assert seen["rejected_path"] == staged_rejected

    assert seen["master_path"] != global_cleaned

    assert seen["dispatch_source_mode"] == "cleaned"
    assert seen["campaign_type"] == "recontact_cold"


def test_fresh_cold_keep_still_uses_same_staged_run(
    tmp_path,
    monkeypatch,
):
    global_input = tmp_path / "global_input.csv"
    global_cleaned = tmp_path / "global_leads.csv"
    global_rejected = tmp_path / "global_rejected.csv"
    global_verified = tmp_path / "global_verified.csv"
    global_keep = tmp_path / "global_keep.csv"

    staged_dir = tmp_path / "runs" / "check_test"
    staged_dir.mkdir(parents=True)

    staged_cleaned = staged_dir / "leads.csv"
    staged_rejected = staged_dir / "leads_rejected.csv"
    staged_keep = staged_dir / "leads_triaged_keep.csv"

    for path in (
        global_input,
        global_cleaned,
        global_rejected,
        global_verified,
        global_keep,
        staged_cleaned,
        staged_rejected,
        staged_keep,
    ):
        path.write_text(
            "Email,AuthorName\n"
            "test@example.com,Test Author\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        dashboard,
        "_build_live_snapshot",
        lambda: {},
    )

    monkeypatch.setattr(
        dashboard,
        "_dispatch_preflight_block_response",
        lambda snapshot: None,
    )

    monkeypatch.setattr(
        dashboard,
        "important_leads_path_state",
        lambda: {
            "input_path": str(global_input),
            "output_path": str(global_cleaned),
            "rejected_path": str(global_rejected),
        },
    )

    monkeypatch.setattr(
        dashboard,
        "important_leads_verify_path_state",
        lambda: {
            "verified_path": str(global_verified),
        },
    )

    monkeypatch.setattr(
        dashboard,
        "important_leads_triage_path_state",
        lambda: {
            "keep_path": str(global_keep),
        },
    )

    monkeypatch.setattr(
        dashboard,
        "_resolve_dashboard_csv_path",
        lambda value, default: Path(str(value)),
    )

    monkeypatch.setattr(
        dashboard,
        "_important_path_labels_for_state",
        lambda *args: {},
    )

    monkeypatch.setattr(
        dashboard,
        "_important_dispatch_source_labels_for_state",
        lambda *args: {},
    )

    monkeypatch.setattr(
        dashboard,
        "save_state",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        dashboard,
        "_latest_fast_triage_keep_source",
        lambda: {
            "source_resolution": "latest_completed_staged_run",
            "path": str(staged_keep),
            "paths": {
                "input": str(staged_cleaned),
                "keep": str(staged_keep),
                "rejected": str(staged_rejected),
            },
        },
    )

    monkeypatch.setattr(
        dashboard,
        "_dispatch_source_readiness_block",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        dashboard,
        "_preview_recovery_request_block",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        dashboard,
        "_find_check_job_for_progress_source",
        lambda path: None,
    )

    monkeypatch.setattr(
        dashboard,
        "_try_acquire_dispatch_preview_claim",
        lambda key: {
            "claim_token": "test-claim",
            "job_id": key,
        },
    )

    monkeypatch.setattr(
        dashboard,
        "_release_dispatch_preview_claim",
        lambda claim: None,
    )

    seen = {}

    def fake_preview(**kwargs):
        seen.update(kwargs)
        return {
            "preview_id": "dispatch_preview_test_keep",
            "status": "previewed",
            "dispatch_source_name": "Fresh Cold Keep",
        }

    monkeypatch.setattr(
        dashboard,
        "preview_dispatch_master_leads",
        fake_preview,
    )

    monkeypatch.setattr(
        dashboard,
        "_display_leads_status",
        lambda: {},
    )

    payload = dashboard.ImportantLeadDispatchPayload(
        campaign_type="cold",
        dispatch_source_mode="triaged_keep",
        dispatch_cap="all",
    )

    response = dashboard.preview_dispatch_important_leads(
        payload
    )

    assert response.status_code == 200
    assert Path(seen["master_path"]) == staged_cleaned
    assert Path(seen["rejected_path"]) == staged_rejected
    assert Path(seen["triaged_keep_path"]) == staged_keep
