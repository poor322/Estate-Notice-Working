"""Validate property matcher output before alert routing.

This module does not send messages or write database records.
"""

import json
from pathlib import Path

VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "NO_MATCH"}


def validate_matcher_results(data, notices_dir):
    if not isinstance(data, dict):
        raise ValueError("Matcher output must be a JSON object")

    matches = data.get("matches")
    if not isinstance(matches, list):
        raise ValueError("Matcher output must contain a matches list")

    if "total_comparisons" in data:
        total = data["total_comparisons"]
        if type(total) is not int or total != len(matches):
            raise ValueError("Invalid total_comparisons")

    root = Path(notices_dir).resolve()
    if not root.is_dir():
        raise ValueError("Notices directory does not exist")

    validated = []

    for index, record in enumerate(matches, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Match {index}: expected an object")

        item = dict(record)

        property_id = item.get("property_id")
        if not isinstance(property_id, str) or not property_id.strip():
            raise ValueError(f"Match {index}: invalid property_id")

        confidence = item.get("confidence")
        if not isinstance(confidence, str):
            raise ValueError(f"Match {index}: invalid confidence")

        confidence = confidence.strip().upper()
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Match {index}: unknown confidence")

        score = item.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not (0 <= score <= 200)
        ):
            raise ValueError(f"Match {index}: invalid score")

        reasons = item.get("reasons")
        if not isinstance(reasons, list) or not all(
            isinstance(reason, str) for reason in reasons
        ):
            raise ValueError(f"Match {index}: invalid reasons")

        # Actionable matches require their source notice.
        if confidence in {"HIGH", "MEDIUM"}:
            notice_file = item.get("notice_file")

            if not isinstance(notice_file, str) or not notice_file.strip():
                raise ValueError(
                    f"Match {index}: missing notice_file"
                )

            relative = Path(notice_file)
            if relative.is_absolute():
                raise ValueError(
                    f"Match {index}: absolute notice paths not allowed"
                )

            notice_path = (root / relative).resolve()

            if not notice_path.is_relative_to(root):
                raise ValueError(
                    f"Match {index}: notice path escapes directory"
                )

            if not notice_path.is_file():
                raise ValueError(
                    f"Match {index}: notice file not found"
                )

        item["confidence"] = confidence
        validated.append(item)

    return {"matches": validated}


def validate_matcher_file(input_file, notices_dir):
    data = json.loads(
        Path(input_file).read_text(encoding="utf-8")
    )
    return validate_matcher_results(data, notices_dir)
