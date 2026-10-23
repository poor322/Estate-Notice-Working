"""Bridge approved notices to the existing matcher format.

Prototype only. Does not authenticate approvals, send alerts,
or determine real recipient ownership.
"""

from pathlib import Path

from alerting.registered_property_matcher import (
    match_registered_property,
)
from alerting.matcher_adapter import validate_matcher_results


def build_matcher_results(
    approved_notices,
    registered_properties,
    notice_files,
    notices_dir,
):
    if not isinstance(approved_notices, list):
        raise ValueError("Approved notices must be a list")
    if not isinstance(registered_properties, list):
        raise ValueError("Registered properties must be a list")
    if not isinstance(notice_files, dict):
        raise ValueError("Notice file mapping must be an object")

    root = Path(notices_dir).resolve()
    if not root.is_dir():
        raise ValueError("Notices directory does not exist")

    results = []
    seen_notices = set()
    seen_properties = set()

    for property_record in registered_properties:
        property_id = property_record.get("property_id", "")
        if not isinstance(property_id, str) or not property_id.strip():
            raise ValueError("Invalid registered property ID")
        if property_id in seen_properties:
            raise ValueError("Duplicate registered property ID")
        seen_properties.add(property_id)

    for notice in approved_notices:
        notice_id = notice.get("notice_id", "")
        content_hash = notice.get("content_hash", "")

        if not isinstance(notice_id, str) or not notice_id.strip():
            raise ValueError("Missing approved notice ID")
        if not isinstance(content_hash, str) or not content_hash.strip():
            raise ValueError("Missing approved notice content hash")
        if notice_id in seen_notices:
            raise ValueError("Duplicate approved notice")
        seen_notices.add(notice_id)

        # Never trust source_image as a notice text file.
        relative_name = notice_files.get(notice_id)

        if not isinstance(relative_name, str) or not relative_name.strip():
            raise ValueError("Missing explicit notice text-file mapping")

        relative = Path(relative_name)
        if relative.is_absolute() or relative.suffix.lower() != ".txt":
            raise ValueError("Notice reference must be a relative .txt file")

        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError("Invalid notice text-file location")

        for registered in registered_properties:
            result = match_registered_property(notice, registered)

            reasons = [
                "Identifier matched: " + field
                for field in result["matched_fields"]
            ]
            reasons += [
                "Identifier conflict: " + field
                for field in result["conflicting_fields"]
            ]
            reasons += [
                "Geographic match: " + field
                for field in result["geographic_matches"]
            ]
            reasons += [
                "Geographic conflict: " + field
                for field in result["geographic_conflicts"]
            ]

            # Explainable provisional score; not a calibrated probability.
            score = min(
                200,
                40 * len(result["matched_fields"])
                + 10 * len(result["geographic_matches"]),
            )

            if result["conflicting_fields"] or result["geographic_conflicts"]:
                score = min(score, 49)

            results.append({
                "property_id": result["property_id"],
                "notice_id": notice_id,
                "content_hash": content_hash,
                "notice_file": relative.as_posix(),
                "confidence": result["confidence"],
                "score": score,
                "reasons": reasons,
            })

    payload = {
        "total_comparisons": len(results),
        "matches": results,
    }

    validated = validate_matcher_results(payload, root)

    return {
        "total_comparisons": len(validated["matches"]),
        "matches": validated["matches"],
    }
