"""Reconcile recorded SENT alerts with the deduplication registry.

This module never sends messages.
A SENT record must come from a trusted delivery confirmation.
"""

import argparse
import sqlite3
from pathlib import Path

from alerting.dedup_check import build_delivery_key
from estate_notice.utils.deduplication import NoticeDeduplicator


def sync_deliveries(db_path, notices_dir, registry_path):
    db_path = Path(db_path).resolve(strict=True)
    notices_dir = Path(notices_dir).resolve(strict=True)

    connection = sqlite3.connect(
        db_path.as_uri() + "?mode=ro",
        uri=True,
    )

    try:
        rows = connection.execute("""
            SELECT
                a.id,
                a.recipient_id,
                a.property_id,
                a.notice_file,
                a.notice_fingerprint
            FROM recipient_alerts a
            WHERE a.status = 'SENT'
              AND EXISTS (
                  SELECT 1
                  FROM delivery_attempts d
                  WHERE d.alert_id = a.id
                    AND d.result = 'SENT'
                    AND d.provider_message_id IS NOT NULL
                    AND TRIM(d.provider_message_id) != ''
              )
            ORDER BY a.id
        """).fetchall()
    finally:
        connection.close()

    registry = NoticeDeduplicator(registry_path)

    synchronized = 0
    already_synced = 0
    errors = []

    for alert_id, recipient_id, property_id, notice_file, fingerprint in rows:
        try:
            if not all([
                recipient_id,
                property_id,
                notice_file,
                fingerprint,
            ]):
                raise ValueError("Missing required alert information")

            if Path(notice_file).name != notice_file:
                raise ValueError("Unsafe notice filename")

            notice_path = (notices_dir / notice_file).resolve()

            if (
                not notice_path.is_relative_to(notices_dir)
                or not notice_path.is_file()
            ):
                raise ValueError("Missing or unsafe notice file")

            notice_text = notice_path.read_text(encoding="utf-8")

            if NoticeDeduplicator.fingerprint(notice_text) != fingerprint:
                raise ValueError("Notice fingerprint mismatch")

            match = {
                "recipient_id": recipient_id,
                "property_id": property_id,
                "notice_file": notice_file,
            }

            key, scope = build_delivery_key(match, notices_dir)

            if scope != "RECIPIENT":
                raise ValueError("Recipient-specific scope required")

            if registry.was_alerted(key):
                already_synced += 1
                continue

            if not registry.is_duplicate(key):
                raise ValueError("Notice not found in dedup registry")

            registry.mark_alerted(key)
            synchronized += 1

        except (ValueError, OSError, KeyError) as error:
            errors.append((alert_id, str(error)))

    return synchronized, already_synced, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--notices-dir", required=True)
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()

    synchronized, already_synced, errors = sync_deliveries(
        args.db,
        args.notices_dir,
        args.registry,
    )

    print("Newly synchronized:", synchronized)
    print("Already synchronized:", already_synced)
    print("Errors:", len(errors))

    for alert_id, error in errors:
        print(f"Alert {alert_id}: {error}")

    print("DRY RUN: No WhatsApp messages sent")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
