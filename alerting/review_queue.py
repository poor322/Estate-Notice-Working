import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def connect_db(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS review_queue (
            review_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            property_id TEXT NOT NULL,
            notice_file TEXT NOT NULL,
            confidence TEXT NOT NULL,
            score INTEGER,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN (
                    'PENDING', 'APPROVED', 'REJECTED'
                )),
            assigned_to TEXT NOT NULL,
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            match_json TEXT NOT NULL
        )
    """)

    connection.commit()
    return connection


def import_matches(connection, input_file, source_id, reviewer):
    data = json.loads(
        Path(input_file).read_text(encoding="utf-8")
    )

    matches = data.get("routed_matches")

    if not isinstance(matches, list):
        raise ValueError("Missing routed_matches list")

    created = 0
    existing = 0

    for match in matches:
        if not isinstance(match, dict):
            raise ValueError("Invalid match record")

        if match.get("routing_action") != "PENDING_REVIEW":
            continue

        if match.get("confidence") != "MEDIUM":
            continue

        property_id = match.get("property_id")
        notice_file = match.get("notice_file")

        if not property_id or not notice_file:
            raise ValueError(
                "Review match missing property_id or notice_file"
            )

        identity = json.dumps(
            [source_id, property_id, notice_file],
            ensure_ascii=False,
        )

        review_id = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]

        cursor = connection.execute("""
            INSERT OR IGNORE INTO review_queue (
                review_id,
                source_id,
                property_id,
                notice_file,
                confidence,
                score,
                assigned_to,
                created_at,
                match_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id,
            source_id,
            property_id,
            notice_file,
            "MEDIUM",
            match.get("score"),
            reviewer,
            timestamp(),
            json.dumps(match, ensure_ascii=False),
        ))

        if cursor.rowcount == 1:
            created += 1
        else:
            existing += 1

    connection.commit()

    print("\nPOORNIMA - MANUAL REVIEW QUEUE")
    print("=" * 50)
    print("New review records:", created)
    print("Already existing:", existing)
    print("No WhatsApp messages sent")


def list_reviews(connection):
    rows = connection.execute("""
        SELECT
            review_id,
            property_id,
            notice_file,
            score,
            status,
            assigned_to
        FROM review_queue
        ORDER BY created_at
    """).fetchall()

    print("\nREVIEW QUEUE")
    print("=" * 50)

    for row in rows:
        review_id, prop, notice, score, status, assigned = row

        print("\nReview ID:", review_id)
        print("Property:", prop)
        print("Notice:", notice)
        print("Score:", score)
        print("Status:", status)
        print("Assigned to:", assigned)

    print("\nTotal review records:", len(rows))



def decide_review(connection, review_id, reviewer, decision):
    """Approve or reject a pending review."""

    reviewer = reviewer.strip()

    if not reviewer:
        raise ValueError("Reviewer cannot be empty")

    row = connection.execute(
        """
        SELECT status, assigned_to
        FROM review_queue
        WHERE review_id = ?
        """,
        (review_id,),
    ).fetchone()

    if row is None:
        raise ValueError("Review record not found")

    current_status, assigned_to = row

    if reviewer != assigned_to:
        raise PermissionError(
            "Only the assigned reviewer can decide this review"
        )

    if current_status != "PENDING":
        raise ValueError(
            f"Review already decided: {current_status}"
        )

    cursor = connection.execute(
        """
        UPDATE review_queue
        SET status = ?,
            reviewed_by = ?,
            reviewed_at = ?
        WHERE review_id = ?
          AND status = 'PENDING'
          AND assigned_to = ?
        """,
        (
            decision,
            reviewer,
            timestamp(),
            review_id,
            reviewer,
        ),
    )

    if cursor.rowcount != 1:
        connection.rollback()
        raise RuntimeError(
            "Review changed during processing"
        )

    connection.commit()

    print("\nREVIEW DECISION SAVED")
    print("=" * 50)
    print("Review ID:", review_id)
    print("Decision:", decision)
    print("Reviewed by:", reviewer)
    print("No WhatsApp messages sent")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--db",
        required=True
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    importer = subparsers.add_parser("import")

    importer.add_argument("--input", required=True)
    importer.add_argument("--source-id", required=True)
    importer.add_argument("--reviewer", required=True)

    subparsers.add_parser("list")

    for command in ("approve", "reject"):
        decision_parser = subparsers.add_parser(command)

        decision_parser.add_argument(
            "--review-id",
            required=True,
        )

        decision_parser.add_argument(
            "--reviewer",
            required=True,
        )

    args = parser.parse_args()

    if args.command == "import":
        if not args.source_id.strip():
            parser.error("--source-id cannot be empty")
        if not args.reviewer.strip():
            parser.error("--reviewer cannot be empty")

    connection = connect_db(args.db)

    try:
        if args.command == "import":
            import_matches(
                connection,
                args.input,
                args.source_id,
                args.reviewer,
            )

        elif args.command == "list":
            list_reviews(connection)

        elif args.command in ("approve", "reject"):
            decision = (
                "APPROVED"
                if args.command == "approve"
                else "REJECTED"
            )

            decide_review(
                connection,
                args.review_id,
                args.reviewer,
                decision,
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
