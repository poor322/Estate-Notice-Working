import argparse
import sqlite3
from pathlib import Path


def build_whatsapp_message(property_id, notice_text):
    """Prepare a property notice alert message."""

    if not property_id:
        raise ValueError("Property ID is required")

    if not notice_text.strip():
        raise ValueError("Notice text cannot be empty")

    preview = " ".join(
        notice_text.split()
    )[:250]

    message = (
        "ESTATE NOTICE ALERT\n\n"
        "A possible public notice match has been "
        "identified for your registered property.\n\n"
        f"Property ID: {property_id}\n\n"
        "Newspaper Notice:\n"
        f"{preview}\n\n"
        "Please verify the notice and property details "
        "before taking any action.\n\n"
        "Estate Notice Alert System"
    )

    return message


def preview_messages(db_path, notices_dir):
    """Preview pending WhatsApp alerts without sending."""

    db_path = Path(db_path)

    if not db_path.is_file():
        raise FileNotFoundError(
            f"Database not found: {db_path}"
        )

    notices_dir = Path(notices_dir).resolve(
        strict=True
    )

    connection = sqlite3.connect(
        db_path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )

    try:
        records = connection.execute("""
            SELECT
                recipient_id,
                property_id,
                notice_file,
                status
            FROM recipient_alerts
            WHERE status = 'PENDING'
            ORDER BY id
        """).fetchall()

    finally:
        connection.close()

    print("\n" + "=" * 60)
    print("POORNIMA - WHATSAPP MESSAGE PREVIEW")
    print("=" * 60)

    for recipient_id, property_id, notice_file, status in records:

        if Path(notice_file).name != notice_file:
            raise ValueError("Unsafe notice filename")

        notice_path = (
            notices_dir / notice_file
        ).resolve()

        if (
            not notice_path.is_relative_to(notices_dir)
            or not notice_path.is_file()
        ):
            raise ValueError(
                f"Notice file missing or unsafe: {notice_file}"
            )

        notice_text = notice_path.read_text(
            encoding="utf-8"
        )

        message = build_whatsapp_message(
            property_id,
            notice_text,
        )

        print("\n" + "-" * 60)

        print("Recipient ID:", recipient_id)
        print("Property ID:", property_id)
        print("Alert Status:", status)

        print("\nMESSAGE PREVIEW:\n")
        print(message)

    print("\n" + "=" * 60)
    print("Total message previews:", len(records))
    print("DRY RUN: NO WHATSAPP MESSAGES SENT")


def main():

    parser = argparse.ArgumentParser(
        description="WhatsApp Message Preview"
    )

    parser.add_argument(
        "--db",
        required=True
    )

    parser.add_argument(
        "--notices-dir",
        required=True
    )

    args = parser.parse_args()

    preview_messages(
        args.db,
        args.notices_dir,
    )


if __name__ == "__main__":
    main()
