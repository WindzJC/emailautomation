from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from important_leads_workflow import WARM_PRIVATE_JC_QUEUE_HEADERS
from send_shard import normalized_warm_confirmation_payload, warm_confirmation_payload_hash
from tools.retemplate_warm_queue import repair_warm_queue


def _write_queue(path: Path, count: int = 22) -> list[dict[str, str]]:
    rows = []
    for index in range(count):
        email = f"author{index}@example.test"
        rows.append(
            {
                "Email": email,
                "FirstName": f"Author{index}",
                "AuthorName": f"Author {index}",
                "AuthorEmail": email,
                "BookTitleOrProject": f"Book {index}",
                "EmailSubject": f"Quick idea for Book {index}",
                "EmailBody": (
                    f"Hi Author{index},\n\nNeed signal {index}\nAngle {index}\n"
                    "Creative Director, Astra Productions\nExamples: astraproductions.co"
                ),
                "NeedSignal": f"Need signal {index}",
                "RecommendedService": f"a launch page {index}",
                "OutreachAngle": f"Angle {index}",
                "SourceURL": f"https://example.test/source/{index}",
                "ContactPath": email,
                "ResearchStatus": "New",
                "campaign_type": "warm_private_jc",
                "campaign_id": "warm_private_jc_test",
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(WARM_PRIVATE_JC_QUEUE_HEADERS))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_confirmation(path: Path, rows: list[dict[str, str]]) -> None:
    approved_rows = {
        row["Email"]: {
            "payload": normalized_warm_confirmation_payload(row),
            "payload_sha256": warm_confirmation_payload_hash(row),
        }
        for row in rows
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "confirmation_id": "warm_private_jc_test",
                "confirmed": True,
                "profile": "private_jc_warm",
                "source_path": "historical/warm_email_preview.csv",
                "source_sha256": "historical",
                "queue_path": str(path.parent / "recipients_private_jc_warm.csv"),
                "queue_sha256": "historical",
                "row_count": len(rows),
                "protected_fields": list(WARM_PRIVATE_JC_QUEUE_HEADERS),
                "approved_rows": approved_rows,
            }
        ),
        encoding="utf-8",
    )


def test_dry_run_preserves_live_files_and_reports_22_rows(tmp_path: Path) -> None:
    queue = tmp_path / "recipients_private_jc_warm.csv"
    confirmation = tmp_path / "warm_private_jc_confirmation.json"
    rows = _write_queue(queue)
    _write_confirmation(confirmation, rows)
    queue_before = queue.read_bytes()
    confirmation_before = confirmation.read_bytes()

    result = repair_warm_queue(
        queue_path=queue,
        confirmation_path=confirmation,
        backup_root=tmp_path / "backups",
        apply=False,
        worker_pids=lambda: [],
    )

    assert result["repair_status"] == "DRY_RUN"
    assert result["repaired_pending_records"] == 22
    assert queue.read_bytes() == queue_before
    assert confirmation.read_bytes() == confirmation_before
    assert not (tmp_path / "backups").exists()


def test_apply_backs_up_and_rehashes_exact_pending_queue(tmp_path: Path) -> None:
    queue = tmp_path / "recipients_private_jc_warm.csv"
    confirmation = tmp_path / "warm_private_jc_confirmation.json"
    rows = _write_queue(queue)
    _write_confirmation(confirmation, rows)

    result = repair_warm_queue(
        queue_path=queue,
        confirmation_path=confirmation,
        backup_root=tmp_path / "backups",
        apply=True,
        worker_pids=lambda: [],
    )

    backup = Path(str(result["backup_path"]))
    assert (backup / queue.name).exists()
    assert (backup / confirmation.name).exists()
    with queue.open(newline="", encoding="utf-8") as handle:
        repaired = list(csv.DictReader(handle))
    manifest = json.loads(confirmation.read_text(encoding="utf-8"))
    assert len(repaired) == 22
    assert len(manifest["approved_rows"]) == 22
    assert [row["Email"] for row in repaired] == [row["Email"] for row in rows]
    assert all(row["EmailSubject"].startswith("A focused direction for") for row in repaired)
    assert all("Founder & CEO, Astra Productions" in row["EmailBody"] for row in repaired)
    assert all("Quick idea for" not in row["EmailBody"] for row in repaired)
    assert all("Creative Director, Astra Productions" not in row["EmailBody"] for row in repaired)
    assert all(row["NeedSignal"] not in row["EmailBody"] for row in repaired)
    assert all(row["OutreachAngle"] not in row["EmailBody"] for row in repaired)
    assert result["queue_confirmation_hashes_match"] is True


def test_running_worker_refuses_repair_without_writes(tmp_path: Path) -> None:
    queue = tmp_path / "recipients_private_jc_warm.csv"
    confirmation = tmp_path / "warm_private_jc_confirmation.json"
    rows = _write_queue(queue)
    _write_confirmation(confirmation, rows)
    queue_before = queue.read_bytes()
    confirmation_before = confirmation.read_bytes()

    with pytest.raises(RuntimeError, match="private_jc_warm is running"):
        repair_warm_queue(
            queue_path=queue,
            confirmation_path=confirmation,
            backup_root=tmp_path / "backups",
            apply=True,
            worker_pids=lambda: [1234],
        )

    assert queue.read_bytes() == queue_before
    assert confirmation.read_bytes() == confirmation_before
