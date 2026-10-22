"""Attach verified recipients to property matches. No messages sent."""

import argparse
import json
from pathlib import Path


def attach_recipients(data, mappings):
    records = data.get("routed_matches")

    if not isinstance(records, list):
        raise ValueError("Missing routed_matches list")

    if not isinstance(mappings, list):
        raise ValueError("Mappings must be a list")

    lookup = {}

    for entry in mappings:
        if not isinstance(entry, dict):
            raise ValueError("Invalid recipient mapping")

        property_id = entry.get("property_id")
        recipient_id = entry.get("recipient_id")

        if not (
            isinstance(property_id, str) and property_id.strip()
            and isinstance(recipient_id, str) and recipient_id.strip()
        ):
            raise ValueError("Invalid property or recipient ID")

        if entry.get("verified") is not True:
            continue

        lookup.setdefault(property_id, set()).add(recipient_id)

    results = []

    for match in records:
        if not isinstance(match, dict):
            raise ValueError("Invalid match")

        property_id = match.get("property_id")
        recipients = sorted(lookup.get(property_id, set()))

        if match.get("routing_action") == "LOG_ONLY":
            results.append(dict(match))
            continue

        if not recipients:
            raise ValueError(
                f"No verified recipient for property: {property_id}"
            )

        for recipient_id in recipients:
            item = dict(match)
            item["recipient_id"] = recipient_id
            results.append(item)

    return {"routed_matches": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--mappings", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = json.loads(
        Path(args.input).read_text(encoding="utf-8")
    )

    mappings = json.loads(
        Path(args.mappings).read_text(encoding="utf-8")
    )

    result = attach_recipients(data, mappings)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Recipient mappings completed:", len(result["routed_matches"]))
    print("Output:", output)
    print("DRY RUN: No WhatsApp messages sent")


if __name__ == "__main__":
    main()
