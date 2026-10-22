import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from alerting.dedup_check import check_deduplication


def load_approved_reviews(db_path):
    """Load only approved reviews from SQLite."""

    path = Path(db_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"Review database not found: {path}"
        )

    # Open the review database in read-only mode.
    connection = sqlite3.connect(
        path.as_uri() + "?mode=ro",
        uri=True,
    )

    try:
        rows = connection.execute("""
            SELECT review_id, source_id, match_json
            FROM review_queue
            WHERE status = 'APPROVED'
        """).fetchall()
    finally:
        connection.close()

    approved_matches = []

    for review_id, source_id, match_json in rows:

        match = json.loads(match_json)

        if (
            match.get("confidence") != "MEDIUM"
            or match.get("routing_action") != "PENDING_REVIEW"
        ):
            raise ValueError(
                f"Invalid approved review: {review_id}"
            )

        approved_match = dict(match)

        approved_match["review_id"] = review_id
        approved_match["source_id"] = source_id
        approved_match["review_status"] = "APPROVED"

        # Only approved records proceed to dedup.
        approved_match["routing_action"] = (
            "READY_FOR_DEDUP_CHECK"
        )

        approved_match["whatsapp_sent"] = False

        approved_matches.append(approved_match)

    return {
        "routed_matches": approved_matches
    }


def main():

    parser = argparse.ArgumentParser(
        description="Approved Review Deduplication"
    )

    parser.add_argument("--db", required=True)
    parser.add_argument("--notices-dir", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    approved_data = load_approved_reviews(
        args.db
    )

    print("\nApproved reviews found:",
          len(approved_data["routed_matches"]))

    results = check_deduplication(
        approved_data,
        Path(args.notices_dir),
        Path(args.registry),
    )

    summary = dict(
        Counter(
            item["dedup_status"]
            for item in results
        )
    )

    output = {
        "total_approved": len(results),
        "summary": summary,
        "results": results,
    }

    output_path = Path(args.output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 55)
    print("POORNIMA - APPROVED REVIEW INTEGRATION")
    print("=" * 55)

    for match in results:

        print("\nProperty:",
              match.get("property_id"))

        print("Review ID:",
              match.get("review_id"))

        print("Review status:",
              match.get("review_status"))

        print("Dedup status:",
              match.get("dedup_status"))

        print("Alert eligible:",
              match.get("alert_eligible"))

    print("\nOutput:", output_path)
    print("DRY RUN: No WhatsApp messages sent")


if __name__ == "__main__":
    main()
