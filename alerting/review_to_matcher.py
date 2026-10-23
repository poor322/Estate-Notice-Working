"""Convert manually approved notice identifiers into matcher inputs.

No database writes, recipient lookup, or message sending.
"""

import csv
import json
from pathlib import Path


def read_csv(path):
    with Path(path).open(
        encoding="utf-8-sig", newline=""
    ) as file:
        return list(csv.DictReader(file))


def build_approved_notices(source_rows, review_rows):
    source_by_id = {}

    for row in source_rows:
        notice_id = (row.get("id") or "").strip()
        content_hash = (row.get("content_hash") or "").strip()

        if not notice_id or not content_hash:
            raise ValueError("Source notice missing ID or content hash")

        if notice_id in source_by_id:
            raise ValueError("Duplicate source notice ID")

        source_by_id[notice_id] = row

    approved = []
    seen = set()

    for review in review_rows:
        if (review.get("review_decision") or "").strip().upper() != "APPROVED":
            continue

        notice_id = (review.get("notice_id") or "").strip()

        if notice_id in seen:
            raise ValueError("Duplicate approved review")
        seen.add(notice_id)

        source = source_by_id.get(notice_id)
        if source is None:
            raise ValueError("Approved review has unknown notice ID")

        if (review.get("content_hash") or "").strip() != (
            source.get("content_hash") or ""
        ).strip():
            raise ValueError("Approved review content hash mismatch")

        approved_house = (
            review.get("approved_house_number") or ""
        ).strip()

        reviewer = (review.get("approved_by") or "").strip()
        reviewed_at = (review.get("approved_at") or "").strip()

        if not approved_house or not reviewer or not reviewed_at:
            raise ValueError("Incomplete approval information")

        if (review.get("extraction_status") or "") == "NO_IDENTIFIER":
            raise ValueError("Cannot approve a missing identifier")

        approved.append({
            "notice_id": notice_id,
            "content_hash": source["content_hash"],
            "source_file": source.get("source_image", ""),
            "house_number": approved_house,
            "village": (
                review.get("approved_village") or ""
            ).strip(),
            "tehsil": (
                review.get("approved_tehsil") or ""
            ).strip(),
            "survey_number": (
                source.get("survey_number") or ""
            ).strip(),
            "plot_number": (
                source.get("plot_number") or ""
            ).strip(),
            "ocr_text": source.get("ocr_text", ""),
            "approved_by": reviewer,
            "approved_at": reviewed_at,
        })

    return approved


def convert_files(source_csv, review_csv, output_json):
    notices = build_approved_notices(
        read_csv(source_csv),
        read_csv(review_csv),
    )

    output = Path(output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(notices, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return len(notices)
