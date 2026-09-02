from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools import rebuild_recipient_queues as rq
from send_shard import row_merge_fields
from tools.validate_message_preview import contains_bad_render_tokens, validate_row


def _write_csv(path: Path, headers, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_legitimate_none_inside_validated_book_title_is_allowed() -> None:
    title = "Death Has None"

    assert contains_bad_render_tokens(
        "Shelf review: Death Has None",
        "subject",
        allowed_render_values=(title,),
    ) == []

    assert contains_bad_render_tokens(
        "While reviewing Death Has None for our bookstore shelves.",
        "body",
        allowed_render_values=(title,),
    ) == []


def test_unrelated_none_still_fails_after_book_title_masking() -> None:
    failures = contains_bad_render_tokens(
        "Death Has None — author value: None",
        "body",
        allowed_render_values=("Death Has None",),
    )
    assert "body_bad_literal_nan_or_none" in failures


def test_plain_none_and_nan_still_fail() -> None:
    assert "subject_bad_literal_nan_or_none" in contains_bad_render_tokens(
        "Shelf review: None",
        "subject",
    )
    assert "body_bad_literal_nan_or_none" in contains_bad_render_tokens(
        "Hello nan,",
        "body",
    )


def test_active_manifest_identity_is_preserved_for_full_recontact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        state = base / "data/state"
        important = base / "_important"
        shards = base / "data/shards"

        state.mkdir(parents=True)
        important.mkdir(parents=True)
        shards.mkdir(parents=True)

        checked = important / "checked.csv"
        keep = important / "keep.csv"
        reject = important / "reject.csv"
        queue = shards / "recipients_private_jc.csv"

        _write_csv(
            checked,
            ["Email", "FirstName", "BookTitle"],
            [
                {
                    "Email": "keep@example.test",
                    "FirstName": "Keep",
                    "BookTitle": "Keep Book",
                },
                {
                    "Email": "reject@example.test",
                    "FirstName": "Reject",
                    "BookTitle": "Rejected By Triage Only",
                },
            ],
        )

        _write_csv(
            keep,
            ["Email", "FirstName", "BookTitle"],
            [
                {
                    "Email": "keep@example.test",
                    "FirstName": "Keep",
                    "BookTitle": "Keep Book",
                },
            ],
        )

        _write_csv(
            reject,
            ["Email", "VerificationReason"],
            [
                {
                    "Email": "reject@example.test",
                    "VerificationReason": "SYNTHETIC_TRIAGE_REJECT",
                },
            ],
        )

        _write_csv(
            queue,
            ["Email", "FirstName", "BookTitle"],
            [
                {
                    "Email": "reject@example.test",
                    "FirstName": "Reject",
                    "BookTitle": "Rejected By Triage Only",
                },
            ],
        )

        campaign_id = "dispatch_preview_20260902_120000_deadbeef"

        manifest = {
            "source": "confirm_dispatch",
            "campaign_type": "recontact_cold",
            "campaign_id": campaign_id,
            "preview_id": campaign_id,
            "dispatch_source_mode": "cleaned",
            "dispatch_source_kind": "full_recontact",
            "checked_path": str(checked),
            "intended_source_path": str(checked),
            "triaged_keep_path": str(keep),
            "triaged_reject_path": str(reject),
        }

        (state / "active_campaign_snapshot.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

        resolved = rq._active_campaign_manifest_source_paths(state)

        assert resolved is not None
        assert isinstance(resolved.get("manifest"), dict)
        assert resolved["manifest"]["source"] == "confirm_dispatch"
        assert resolved["manifest"]["campaign_type"] == "recontact_cold"
        assert resolved["manifest"]["dispatch_source_kind"] == "full_recontact"

        with patch.object(rq.settings, "APP_ROOT", base), patch.object(
            rq.settings,
            "STATE_DIR",
            state,
        ):
            report = rq.build_queue_safety_report(
                shard_paths=[queue],
                sendgrid_log_paths=[],
                recontact_blocked_overlap_export_path=base / "blocked.csv",
            )

        assert report["safe"] is True
        assert report["full_recontact_reject_overlap_allowed"] is True
        assert report["overlap_with_triaged_reject"] == 1
        assert report["allowed_triaged_reject_overlap_count"] == 1
        assert report["blocked_triaged_reject_overlap_count"] == 0



def test_sender_merge_fields_canonicalize_author_email() -> None:
    row = {
        "Email": "haines@gmail.com",
        "AuthorEmail": "AuthorA. Haines@gmail.com",
        "AuthorName": "Andrew Haines",
        "BookTitle": "Surviving the Ashlands",
    }

    fields = row_merge_fields(
        row,
        "haines@gmail.com",
        "Andrew",
        "Surviving the Ashlands",
    )

    assert fields["AuthorEmail"] == "haines@gmail.com"


def test_message_validator_rejects_malformed_author_email_metadata() -> None:
    failures = validate_row(
        {
            "Email": "haines@gmail.com",
            "AuthorEmail": "AuthorA. Haines@gmail.com",
            "AuthorName": "Andrew Haines",
            "FirstName": "Andrew",
            "BookTitle": "Surviving the Ashlands",
            "PersonalizedOpeningLine": "",
            "Subject": "Shelf review: Surviving the Ashlands",
            "Body": "Consignment bookstore shelf review.",
        },
        "consignment",
    )

    assert "invalid_author_email_syntax" in failures


def test_message_validator_accepts_matching_canonical_author_email() -> None:
    failures = validate_row(
        {
            "Email": "haines@gmail.com",
            "AuthorEmail": "haines@gmail.com",
            "AuthorName": "Andrew Haines",
            "FirstName": "Andrew",
            "BookTitle": "Surviving the Ashlands",
            "PersonalizedOpeningLine": "",
            "Subject": "Shelf review: Surviving the Ashlands",
            "Body": "Consignment bookstore shelf review.",
        },
        "consignment",
    )

    assert "invalid_author_email_syntax" not in failures
    assert "author_email_mismatch" not in failures
