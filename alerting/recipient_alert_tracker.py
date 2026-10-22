import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from estate_notice.utils.deduplication import NoticeDeduplicator


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def connect_db(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS recipient_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_id TEXT NOT NULL,
            property_id TEXT NOT NULL,
            notice_fingerprint TEXT NOT NULL,
            notice_file TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN (
                    'PENDING',
                    'SENDING',
                    'SENT',
                    'FAILED'
                )),
            created_at TEXT NOT NULL,
            UNIQUE (
                recipient_id,
                property_id,
                notice_fingerprint
            )
        )
    """)

    connection.commit()
    return connection


def collect_candidates(data, notices_dir):
    matches = data.get("results")

    if not isinstance(matches, list):
        raise ValueError("Expected a results list")

    root = Path(notices_dir).resolve(strict=True)
    candidates = []

    for match in matches:
        if not isinstance(match, dict):
            raise ValueError("Invalid match record")

        if match.get("routing_action") != "READY_FOR_DEDUP_CHECK":
            continue

        if match.get("alert_eligible") is not True:
            continue

        confidence = match.get("confidence")

        if confidence not in ("HIGH", "MEDIUM"):
            raise ValueError("Invalid alert confidence")

        if confidence == "MEDIUM":
            if match.get("review_status") != "APPROVED":
                raise ValueError(
                    "MEDIUM alert requires approved review"
                )

        recipient_id = match.get("recipient_id")
        property_id = match.get("property_id")
        notice_file = match.get("notice_file")

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                recipient_id,
                property_id,
                notice_file,
            )
        ):
            raise ValueError(
                "Recipient, property and notice IDs are required"
            )

        if Path(notice_file).name != notice_file:
            raise ValueError("Invalid notice filename")

        notice_path = (root / notice_file).resolve()

        if (
            not notice_path.is_relative_to(root)
            or not notice_path.is_file()
        ):
            raise ValueError("Notice file is missing or unsafe")

        notice_text = notice_path.read_text(
            encoding="utf-8"
        )

        fingerprint = NoticeDeduplicator.fingerprint(
            notice_text
        )

        candidates.append((
            recipient_id,
            property_id,
            fingerprint,
            notice_file,
            timestamp(),
        ))

    return candidates


def register_candidates(connection, candidates):
    created = 0
    existing = 0

    with connection:
        for candidate in candidates:
            cursor = connection.execute("""
                INSERT OR IGNORE INTO recipient_alerts (
                    recipient_id,
                    property_id,
                    notice_fingerprint,
                    notice_file,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, candidate)

            if cursor.rowcount == 1:
                created += 1
            else:
                existing += 1

    return created, existing


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True)
    parser.add_argument("--notices-dir", required=True)
    parser.add_argument("--db", required=True)

    args = parser.parse_args()

    data = json.loads(
        Path(args.input).read_text(encoding="utf-8")
    )

    candidates = collect_candidates(
        data,
        args.notices_dir,
    )

    connection = connect_db(args.db)

    try:
        created, existing = register_candidates(
            connection,
            candidates,
        )

        rows = connection.execute("""
            SELECT recipient_id, property_id, status
            FROM recipient_alerts
            ORDER BY id
        """).fetchall()
    finally:
        connection.close()

    print("\n" + "=" * 55)
    print("POORNIMA - RECIPIENT ALERT TRACKING")
    print("=" * 55)

    print("New alert records:", created)
    print("Existing alert records:", existing)

    for recipient, prop, status in rows:
        print()
        print("Recipient:", recipient)
        print("Property:", prop)
        print("Status:", status)

    print("\nTotal stored:", len(rows))
    print("DRY RUN: No WhatsApp messages sent")


if __name__ == "__main__":
    main()
