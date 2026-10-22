"""Atomic alert delivery states. Does not send messages."""

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def open_db(db_path):
    path = Path(db_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Existing alert database not found: {path}"
        )

    db = sqlite3.connect(
        path,
        timeout=10,
        isolation_level=None,
    )

    db.execute("PRAGMA foreign_keys = ON")

    exists = db.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name='recipient_alerts'"
    ).fetchone()

    if not exists:
        db.close()
        raise ValueError(
            "The database has no recipient_alerts table"
        )

    db.execute("""
        CREATE TABLE IF NOT EXISTS delivery_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL
                REFERENCES recipient_alerts(id),
            claim_token TEXT NOT NULL UNIQUE,
            result TEXT NOT NULL DEFAULT 'IN_PROGRESS'
                CHECK (
                    result IN (
                        'IN_PROGRESS',
                        'SENT',
                        'FAILED'
                    )
                ),
            provider_message_id TEXT,
            error_message TEXT,
            claimed_at TEXT NOT NULL,
            finished_at TEXT
        )
    """)

    return db


def claim_delivery(db, alert_id):
    """Atomically claim an eligible alert."""

    db.execute("BEGIN IMMEDIATE")

    try:
        cursor = db.execute(
            "UPDATE recipient_alerts "
            "SET status='SENDING' "
            "WHERE id=? "
            "AND status IN ('PENDING', 'FAILED')",
            (alert_id,),
        )

        if cursor.rowcount == 0:
            db.rollback()
            return None

        token = secrets.token_urlsafe(24)

        db.execute(
            "INSERT INTO delivery_attempts "
            "(alert_id, claim_token, claimed_at) "
            "VALUES (?, ?, ?)",
            (alert_id, token, now()),
        )

        db.commit()
        return token

    except Exception:
        db.rollback()
        raise


def finish_delivery(
    db,
    claim_token,
    result,
    provider_message_id=None,
    error_message=None,
):
    """Record a definitive delivery result."""

    if result not in ("SENT", "FAILED"):
        raise ValueError(
            "Result must be SENT or FAILED"
        )

    if result == "SENT" and not provider_message_id:
        raise ValueError(
            "SENT requires a confirmed provider message ID"
        )

    if result == "FAILED" and not error_message:
        raise ValueError(
            "FAILED requires a confirmed failure reason"
        )

    db.execute("BEGIN IMMEDIATE")

    try:
        row = db.execute(
            "SELECT attempt_id, alert_id "
            "FROM delivery_attempts "
            "WHERE claim_token=? "
            "AND result='IN_PROGRESS'",
            (claim_token,),
        ).fetchone()

        if row is None:
            db.rollback()
            return False

        attempt_id, alert_id = row

        cursor = db.execute(
            "UPDATE recipient_alerts "
            "SET status=? "
            "WHERE id=? AND status='SENDING'",
            (result, alert_id),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Alert is not in SENDING state"
            )

        db.execute(
            "UPDATE delivery_attempts "
            "SET result=?, "
            "provider_message_id=?, "
            "error_message=?, "
            "finished_at=? "
            "WHERE attempt_id=? "
            "AND result='IN_PROGRESS'",
            (
                result,
                provider_message_id,
                error_message,
                now(),
                attempt_id,
            ),
        )

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise
