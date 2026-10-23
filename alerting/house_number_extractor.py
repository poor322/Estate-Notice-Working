"""Conservative house-number extraction for review only."""

import re

HOUSE = (
    r"(?:house\s*(?:no\.?|number)|h\.?\s*no\.?)"
    r"\s*[:#.-]?\s*([0-9][A-Za-z0-9/-]*)"
)

HOUSE_PATTERN = re.compile(r"\b" + HOUSE, re.IGNORECASE)

SUBJECT_PATTERN = re.compile(
    r"(?:"
    r"transfer\s+of\s+ownership\s+in\s+respect(?:\s+of)?"
    r"|ownership\s+in\s+respect\s+of"
    r"|transfer\s+of"
    r"|property\s+bearing"
    r"|house\s+property\s+bearing"
    r")"
    r"\s+" + HOUSE,
    re.IGNORECASE,
)

RESIDENCE_PATTERN = re.compile(
    r"(?:\bR\s*/\s*o\b|\bresiding\s+at\b)"
    r"\s*" + HOUSE,
    re.IGNORECASE,
)


def extract_house_number(text):
    if not isinstance(text, str) or not text.strip():
        return {
            "house_number": None,
            "status": "NO_IDENTIFIER",
            "candidates": [],
        }

    candidates = list(dict.fromkeys(
        match.group(1)
        for match in HOUSE_PATTERN.finditer(text)
    ))

    residence_positions = [
        (match.start(1), match.end(1))
        for match in RESIDENCE_PATTERN.finditer(text)
    ]

    subject_numbers = set()

    for match in SUBJECT_PATTERN.finditer(text):
        position = (match.start(1), match.end(1))

        if position not in residence_positions:
            subject_numbers.add(match.group(1))

    if len(subject_numbers) == 1:
        return {
            "house_number": next(iter(subject_numbers)),
            "status": "SUBJECT_CANDIDATE_REVIEW",
            "candidates": candidates,
        }

    return {
        "house_number": None,
        "status": (
            "NEEDS_REVIEW"
            if candidates else "NO_IDENTIFIER"
        ),
        "candidates": candidates,
    }
