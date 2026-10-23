"""Run alert routing, deduplication and preview without sending messages."""

import argparse
import json
import tempfile
from pathlib import Path

from alerting.alert_router import route_matches
from alerting.recipient_mapping import attach_recipients
from alerting.dedup_check import check_deduplication
from alerting.recipient_alert_tracker import (
    collect_candidates,
    register_candidates,
    connect_db,
)
from alerting.review_queue import connect_db as connect_review_db
from alerting.review_queue import import_matches
from alerting.whatsapp_sender import preview_messages


def run_workflow(matches_file, mappings_file, notices_dir,
                 registry_file, alerts_db, reviews_db, output_file,
                 source_id, reviewer):

    matches = json.loads(Path(matches_file).read_text(encoding="utf-8"))
    mappings = json.loads(Path(mappings_file).read_text(encoding="utf-8"))
    notices_dir = Path(notices_dir)

    routed = {"routed_matches": route_matches(matches)}
    mapped = attach_recipients(routed, mappings)

    # MEDIUM matches remain pending manual approval.
    with tempfile.TemporaryDirectory(prefix="estate-routing-") as folder:
        routed_path = Path(folder) / "mapped_for_review.json"
        routed_path.write_text(
            json.dumps(mapped, indent=2), encoding="utf-8"
        )

        review_db = connect_review_db(reviews_db)
        try:
            import_matches(
                review_db,
                routed_path,
                source_id,
                reviewer,
            )
        finally:
            review_db.close()

    dedup_results = check_deduplication(
        mapped, notices_dir, Path(registry_file)
    )

    candidates = collect_candidates(
        {"results": dedup_results}, notices_dir
    )

    alert_db = connect_db(alerts_db)
    try:
        created, existing = register_candidates(
            alert_db, candidates
        )
    finally:
        alert_db.close()

    summary = {
        "total_matches": len(mapped["routed_matches"]),
        "new_recipient_alerts": created,
        "existing_recipient_alerts": existing,
        "results": dedup_results,
    }

    Path(output_file).write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    preview_messages(alerts_db, notices_dir)

    print("\nWORKFLOW COMPLETED — DRY RUN")
    print("New recipient alerts:", created)
    print("Existing recipient alerts:", existing)
    print("No WhatsApp messages sent")

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches", required=True)
    parser.add_argument("--mappings", required=True)
    parser.add_argument("--notices-dir", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--alerts-db", required=True)
    parser.add_argument("--reviews-db", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--reviewer", required=True)
    args = parser.parse_args()

    run_workflow(
        args.matches, args.mappings, args.notices_dir,
        args.registry, args.alerts_db, args.reviews_db,
        args.output, args.source_id, args.reviewer,
    )


if __name__ == "__main__":
    main()
