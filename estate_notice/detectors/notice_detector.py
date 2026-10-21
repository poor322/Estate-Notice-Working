import argparse
import json
import re


STRONG_PATTERNS = {
    "public_notice": (
        r"\bpublic\s+notice\b",
        25,
    ),
    "legal_notice": (
        r"\blegal\s+notice\b",
        20,
    ),
    "sale_notice": (
        r"\bsale\s+notice\b",
        20,
    ),
    "auction_notice": (
        r"\bauction\s+notice\b",
        20,
    ),
    "property": (
        r"\bproperty\b",
        10,
    ),
    "land": (
        r"\bland\b",
        10,
    ),
    "plot": (
        r"\bplot\b",
        15,
    ),
    "survey_number": (
        r"\b(?:survey|sy\.?)\s*(?:no\.?|number)?\s*[:.\-]?\s*[\w\/\-]+",
        25,
    ),
    "plot_number": (
        r"\bplot\s*(?:no\.?|number)?\s*[:.\-]?\s*[\w\/\-]+",
        20,
    ),
    "khata": (
        r"\bkhata\s*(?:no\.?|number)?\s*[:.\-]?\s*[\w\/\-]+",
        20,
    ),
    "tp_number": (
        r"\btp\s*(?:no\.?|number)?\s*[:.\-]?\s*[\w\/\-]+",
        20,
    ),
    "cts_number": (
        r"\bcts\s*(?:no\.?|number)?\s*[:.\-]?\s*[\w\/\-]+",
        20,
    ),
    "title_deed": (
        r"\btitle\s+deed\b",
        15,
    ),
    "sale_deed": (
        r"\bsale\s+deed\b",
        15,
    ),
    "mortgage": (
        r"\bmortgage\b",
        15,
    ),
    "encumbrance": (
        r"\bencumbrance\b",
        15,
    ),
    "possession": (
        r"\bpossession\b",
        10,
    ),
    "owner": (
        r"\bowner\b",
        5,
    ),
    "claimant": (
        r"\bclaimant\b",
        5,
    ),
    "auction": (
        r"\bauction\b",
        10,
    ),
    "sale": (
        r"\bsale\b",
        10,
    ),
    "village": (
        r"\bvillage\b",
        5,
    ),
    "taluk": (
        r"\btaluk\b",
        5,
    ),
    "district": (
        r"\bdistrict\b",
        5,
    ),
    "extent": (
        r"\bextent\b",
        10,
    ),
    "acres": (
        r"\bacres?\b",
        10,
    ),
    "guntas": (
        r"\bguntas?\b",
        10,
    ),
}


PROPERTY_IDENTIFIER_KEYS = {
    "survey_number",
    "plot_number",
    "khata",
    "tp_number",
    "cts_number",
    "title_deed",
    "sale_deed",
    "mortgage",
    "encumbrance",
}


def normalize_text(text):
    """
    Normalize OCR/direct extracted text before detection.
    """

    if not text:
        return ""

    text = text.lower()
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def calculate_score(text):
    """
    Calculate estate/property notice relevance score.
    """

    normalized = normalize_text(text)

    score = 0
    matches = []
    identifier_matches = []

    for name, (pattern, points) in STRONG_PATTERNS.items():
        if re.search(pattern, normalized, re.IGNORECASE):
            score += points
            matches.append(name)

            if name in PROPERTY_IDENTIFIER_KEYS:
                identifier_matches.append(name)

    score = min(score, 100)

    return score, matches, identifier_matches


def classify(score, matches, identifier_matches):
    """
    Convert the calculated score into a confidence level.

    Multiple signals are required before considering
    a page as a likely estate/property notice.
    """

    if identifier_matches and len(matches) >= 3 and score >= 70:
        return "HIGH"

    if score >= 70 and len(matches) >= 4:
        return "HIGH"

    if score >= 50 and len(matches) >= 3:
        return "MEDIUM"

    if score >= 30 and len(matches) >= 2:
        return "LOW"

    return "NOT_RELEVANT"


def detect_notice(text, page_number=None):
    """
    Detect whether a page contains an estate/property notice.
    """

    score, matches, identifier_matches = calculate_score(text)

    confidence = classify(
        score,
        matches,
        identifier_matches,
    )

    return {
        "page_number": page_number,
        "is_notice": confidence in {
            "HIGH",
            "MEDIUM",
        },
        "confidence": confidence,
        "score": score,
        "matched_signals": matches,
        "property_identifiers": identifier_matches,
    }


def detect_from_json(input_path, output_path):
    """
    Run notice detection over page-wise extracted text.
    """

    with open(
        input_path,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    results = []

    pages = data.get("pages", [])

    for page in pages:
        page_number = page.get("page_number")
        text = page.get("text", "")

        result = detect_notice(
            text,
            page_number,
        )

        result["text_preview"] = text[:500]

        results.append(result)

    output = {
        "total_pages": len(results),
        "notice_pages": [
            result
            for result in results
            if result["is_notice"]
        ],
        "all_results": results,
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Detect estate notices from extracted newspaper text."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to combined_text.json",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to save notice_detection.json",
    )

    args = parser.parse_args()

    result = detect_from_json(
        args.input,
        args.output,
    )

    print()
    print("======================================")
    print("ESTATE NOTICE DETECTION")
    print("======================================")
    print()

    print(
        f"Pages analysed: {result['total_pages']}"
    )

    print(
        f"Possible notice pages: "
        f"{len(result['notice_pages'])}"
    )

    print()

    for notice in result["notice_pages"]:
        print(
            f"Page {notice['page_number']} | "
            f"{notice['confidence']} | "
            f"score={notice['score']} | "
            f"{', '.join(notice['matched_signals'])}"
        )


if __name__ == "__main__":
    main()
