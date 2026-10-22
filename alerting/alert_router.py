import argparse
import json
from collections import Counter
from pathlib import Path


# Confidence routing rules
ROUTING_RULES = {
    "HIGH": "READY_FOR_DEDUP_CHECK",
    "MEDIUM": "PENDING_REVIEW",
    "LOW": "LOG_ONLY",
    "NO_MATCH": "LOG_ONLY",
}


def route_matches(data):
    """Route Ismail's property matches by confidence."""

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")

    matches = data.get("matches")

    if not isinstance(matches, list):
        raise ValueError("Missing or invalid matches list")

    results = []

    for match in matches:

        if not isinstance(match, dict):
            raise ValueError("Invalid match record")

        confidence = str(
            match.get("confidence", "")
        ).strip().upper()

        if confidence not in ROUTING_RULES:
            raise ValueError(
                f"Unknown confidence: {confidence}"
            )

        routed_match = dict(match)

        routed_match["confidence"] = confidence

        routed_match["routing_action"] = (
            ROUTING_RULES[confidence]
        )

        routed_match["review_status"] = (
            "PENDING"
            if confidence == "MEDIUM"
            else None
        )

        routed_match["whatsapp_sent"] = False

        results.append(routed_match)

    return results


def main():

    parser = argparse.ArgumentParser(
        description="Poornima Confidence Router"
    )

    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    data = json.loads(
        input_path.read_text(encoding="utf-8")
    )

    results = route_matches(data)

    counts = Counter(
        result["routing_action"]
        for result in results
    )

    summary = {
        action: counts[action]
        for action in (
            "READY_FOR_DEDUP_CHECK",
            "PENDING_REVIEW",
            "LOG_ONLY",
        )
    }

    output = {
        "total_matches": len(results),
        "summary": summary,
        "routed_matches": results,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 55)
    print("POORNIMA - CONFIDENCE ROUTING RESULTS")
    print("=" * 55)

    for match in results:
        print()
        print("Property:", match.get("property_id"))
        print("Notice:", match.get("notice_file"))
        print("Confidence:", match["confidence"])
        print("Score:", match.get("score"))
        print("Action:", match["routing_action"])

    print("\nSUMMARY")
    print("-" * 55)

    for action, count in summary.items():
        print(f"{action}: {count}")

    print("\nOutput:", output_path)
    print("DRY RUN: No WhatsApp messages sent")


if __name__ == "__main__":
    main()
