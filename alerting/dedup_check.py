import argparse
import json
from collections import Counter
from pathlib import Path

from estate_notice.utils.deduplication import NoticeDeduplicator


def build_delivery_key(match, notices_dir):
    """Build a notice + property/recipient deduplication key."""

    property_id = match.get("property_id")
    notice_file = match.get("notice_file")

    if not property_id or not notice_file:
        raise ValueError(
            "HIGH match requires property_id and notice_file"
        )

    # Prevent reading files outside the selected notice folder.
    if Path(notice_file).name != notice_file:
        raise ValueError(
            f"Invalid notice filename: {notice_file}"
        )

    notice_path = notices_dir / notice_file

    notice_text = notice_path.read_text(
        encoding="utf-8"
    ).strip()

    if not notice_text:
        raise ValueError(
            f"Empty notice text: {notice_file}"
        )

    # Property ID is a test fallback.
    # Actual sending requires a recipient ID.
    recipient_id = match.get("recipient_id")

    if recipient_id:
        scope = "RECIPIENT"
        identity = str(recipient_id)
    else:
        scope = "PROPERTY_TEST"
        identity = str(property_id)

    key = (
        f"Scope: {scope}\n"
        f"Identity: {identity}\n"
        f"Property: {property_id}\n"
        f"Notice:\n{notice_text}"
    )

    return key, scope


def check_deduplication(routed_data, notices_dir, registry_path):

    matches = routed_data.get("routed_matches")

    if not isinstance(matches, list):
        raise ValueError("Missing routed_matches list")

    dedup = NoticeDeduplicator(registry_path)

    results = []

    for original in matches:

        match = dict(original)

        action = match.get("routing_action")

        if action != "READY_FOR_DEDUP_CHECK":
            match["dedup_status"] = "NOT_APPLICABLE"
            results.append(match)
            continue

        key, scope = build_delivery_key(
            match,
            notices_dir,
        )

        match["dedup_scope"] = scope

        # If this property/recipient was already alerted,
        # suppress another alert for the same notice.
        if dedup.was_alerted(key):

            match["dedup_status"] = "ALREADY_ALERTED_SKIP"
            match["alert_eligible"] = False

        else:

            is_new = dedup.register(key)

            if is_new:
                match["dedup_status"] = "NEW_NOTICE"
            else:
                match["dedup_status"] = "REGISTERED_NOT_ALERTED"

            match["alert_eligible"] = True

        # No delivery takes place in this module.
        match["whatsapp_sent"] = False

        results.append(match)

    return results


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True)
    parser.add_argument("--notices-dir", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    input_path = Path(args.input)
    notices_dir = Path(args.notices_dir)
    registry_path = Path(args.registry)
    output_path = Path(args.output)

    data = json.loads(
        input_path.read_text(encoding="utf-8")
    )

    results = check_deduplication(
        data,
        notices_dir,
        registry_path,
    )

    summary = dict(
        Counter(
            item["dedup_status"]
            for item in results
        )
    )

    output = {
        "total_matches": len(results),
        "summary": summary,
        "results": results,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(output, indent=4),
        encoding="utf-8",
    )

    print("\n" + "=" * 55)
    print("POORNIMA + JANVI DEDUPLICATION RESULTS")
    print("=" * 55)

    for match in results:

        print()
        print("Property:", match.get("property_id"))
        print("Confidence:", match.get("confidence"))
        print("Dedup:", match["dedup_status"])

        if "alert_eligible" in match:
            print("Alert eligible:", match["alert_eligible"])

    print("\nSUMMARY")

    for status, count in summary.items():
        print(f"{status}: {count}")

    print("\nOutput:", output_path)
    print("DRY RUN: No WhatsApp messages sent")


if __name__ == "__main__":
    main()
