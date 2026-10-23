"""Conservative identifier-based property matching. No alerts sent."""

import re


FIELDS = ("survey_number", "plot_number", "house_number")


def normalize_identifier(value):
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).strip().upper())


def match_registered_property(notice, registered):
    if not isinstance(notice, dict) or not isinstance(registered, dict):
        raise ValueError("Notice and registration must be objects")

    property_id = registered.get("property_id")
    if not isinstance(property_id, str) or not property_id.strip():
        raise ValueError("Registered property requires property_id")

    matched = []
    conflicts = []

    for field in FIELDS:
        notice_value = normalize_identifier(notice.get(field))
        registered_value = normalize_identifier(registered.get(field))

        if notice_value and registered_value:
            if notice_value == registered_value:
                matched.append(field)
            else:
                conflicts.append(field)

    # Geographic evidence helps prevent false property matches.
    geographic_fields = ("village", "tehsil", "city", "pincode")
    geographic_matches = []
    geographic_conflicts = []

    for field in geographic_fields:
        a = normalize_identifier(notice.get(field))
        b = normalize_identifier(registered.get(field))

        if a and b:
            if a == b:
                geographic_matches.append(field)
            else:
                geographic_conflicts.append(field)

    # Owner name provides supporting evidence only.
    notice_owner = str(notice.get("owner_name") or "").strip().casefold()
    registered_owner = str(
        registered.get("owner_name") or ""
    ).strip().casefold()

    owner_match = bool(
        notice_owner
        and registered_owner
        and notice_owner == registered_owner
    )

    if conflicts or geographic_conflicts:
        confidence = "MEDIUM" if matched else "NO_MATCH"
    elif len(matched) >= 2 and geographic_matches:
        confidence = "HIGH"
    elif len(matched) >= 2:
        confidence = "MEDIUM"
    elif len(matched) == 1 and owner_match:
        confidence = "MEDIUM"
    elif len(matched) == 1:
        confidence = "MEDIUM"
    else:
        confidence = "NO_MATCH"

    return {
        "property_id": property_id,
        "confidence": confidence,
        "matched_fields": matched,
        "conflicting_fields": conflicts,
        "geographic_matches": geographic_matches,
        "geographic_conflicts": geographic_conflicts,
        "owner_name_matched": owner_match,
        "requires_review": confidence == "MEDIUM",
    }
