from pathlib import Path

import live_dashboard


def _source_status(path: Path, *, verification_required: bool = False):
    return {
        "dispatch_source_mode": "cleaned",
        "dispatch_source_path": str(path),
        "dispatch_source_exists": True,
        "dispatch_source_row_count": 15342,
        "dispatch_eligible_row_count": 15342,
        "verification_required": verification_required,
        "verification_file_mtime": "2026-08-31T22:36:57.412396+00:00",
    }


def _legacy_preview(path: Path):
    return {
        "preview_id": "dispatch_preview_test",
        "status": "previewed",
        "dispatch_source_mode": "cleaned",
        "dispatch_source_kind": "cleaned",
        "source_path": str(path),
        "source_file_path": str(path),
        "source_row_count": 15342,
        "total_source_rows": 15342,
        "selected_rows": 15342,
        "verification_required": False,
        "verification_file_mtime": "",
        "updated_at_utc": "2026-09-02T00:49:51+00:00",
    }


def test_legacy_preview_schema_is_current_for_exact_cleaned_source(tmp_path):
    source = tmp_path / "leads.csv"

    preview, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            _legacy_preview(source),
            source_status=_source_status(source),
            source_generated_at=None,
        )
    )

    assert current is True
    assert preview["dispatch_source_path"] == str(source)
    assert preview["dispatch_source_row_count"] == 15342
    assert preview["dispatch_eligible_row_count"] == 15342


def test_legacy_preview_rejects_different_source_path(tmp_path):
    preview_source = tmp_path / "old" / "leads.csv"
    current_source = tmp_path / "current" / "leads.csv"

    _, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            _legacy_preview(preview_source),
            source_status=_source_status(current_source),
            source_generated_at=None,
        )
    )

    assert current is False


def test_legacy_preview_rejects_different_row_count(tmp_path):
    source = tmp_path / "leads.csv"
    preview = _legacy_preview(source)
    preview["source_row_count"] = 15341

    _, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            preview,
            source_status=_source_status(source),
            source_generated_at=None,
        )
    )

    assert current is False


def test_legacy_preview_rejects_different_eligible_count(tmp_path):
    source = tmp_path / "leads.csv"
    preview = _legacy_preview(source)
    preview["selected_rows"] = 15341

    _, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            preview,
            source_status=_source_status(source),
            source_generated_at=None,
        )
    )

    assert current is False


def test_nonverification_source_allows_empty_legacy_verification_mtime(tmp_path):
    source = tmp_path / "leads.csv"

    _, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            _legacy_preview(source),
            source_status=_source_status(
                source,
                verification_required=False,
            ),
            source_generated_at=None,
        )
    )

    assert current is True


def test_required_verification_still_requires_exact_mtime(tmp_path):
    source = tmp_path / "leads.csv"

    preview = _legacy_preview(source)
    preview["verification_required"] = True
    preview["verification_file_mtime"] = "wrong"

    _, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            preview,
            source_status=_source_status(
                source,
                verification_required=True,
            ),
            source_generated_at=None,
        )
    )

    assert current is False

    preview["verification_file_mtime"] = (
        "2026-08-31T22:36:57.412396+00:00"
    )

    _, current = (
        live_dashboard._preview_summary_for_current_staged_source(
            preview,
            source_status=_source_status(
                source,
                verification_required=True,
            ),
            source_generated_at=None,
        )
    )

    assert current is True
