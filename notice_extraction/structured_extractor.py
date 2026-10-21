import argparse
import json
import re
from pathlib import Path


def unique(values):
    result = []

    for value in values:
        value = value.strip()

        if value and value not in result:
            result.append(value)

    return result


def compact(text):
    return re.sub(r"\s+", " ", text).strip()


def classify_property_notice(text):
    lower = text.lower()

    strong_keywords = [
        "property",
        "land",
        "title document",
        "sale deed",
        "conveyance deed",
        "sub-registrar",
        "mustatil",
        "killa",
        "survey",
        "plot",
        "mortgage",
        "encumbrance",
        "seller",
        "purchaser",
    ]

    matched = [
        keyword
        for keyword in strong_keywords
        if keyword in lower
    ]

    property_related = (
        len(matched) >= 2
        or (
            "property" in lower
            and any(
                word in lower
                for word in [
                    "sale",
                    "transfer",
                    "title",
                    "mortgage",
                    "encumbrance",
                ]
            )
        )
        or (
            "land" in lower
            and any(
                word in lower
                for word in [
                    "sale",
                    "purchase",
                    "seller",
                    "killa",
                    "mustatil",
                ]
            )
        )
    )

    return (
        "PROPERTY_RELEVANT"
        if property_related
        else "NOT_RELEVANT",
        matched,
    )


def extract_notice_type(text):
    if re.search(
        r"\bPUBLIC\s+NOTICE\b",
        text,
        re.IGNORECASE,
    ):
        return "PUBLIC_NOTICE"

    if re.search(
        r"\bLEGAL\s+NOTICE\b",
        text,
        re.IGNORECASE,
    ):
        return "LEGAL_NOTICE"

    if re.search(
        r"\bCOURT\s+NOTICE\b",
        text,
        re.IGNORECASE,
    ):
        return "COURT_NOTICE"

    return "UNKNOWN"


def extract_transaction_type(text):
    lower = text.lower()

    if (
        any(
            word in lower
            for word in [
                "lost",
                "misplaced",
                "untraceable",
            ]
        )
        and "document" in lower
    ):
        return "LOST_TITLE_DOCUMENTS"

    if (
        "agreed to purchase" in lower
        or "proposed purchase" in lower
        or "sale deed" in lower
        or "proposed sale" in lower
    ):
        return "SALE_PURCHASE"

    if "mortgage" in lower:
        return "MORTGAGE_RELATED"

    if "transfer" in lower:
        return "PROPERTY_TRANSFER"

    return "OTHER_PROPERTY_NOTICE"


def extract_property_address(text):
    clean = compact(text)

    match = re.search(
        r"property\s+bearing\s+"
        r"(.+?)"
        r"(?=\(hereinafter|belonging\s+to)",
        clean,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip(
            " ,.;"
        )

    return None


def extract_property_number(text):
    match = re.search(
        r"property\s+bearing\s+"
        r"([A-Z0-9/-]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    return None


def extract_village(text):
    clean = compact(text)

    match = re.search(
        r"\bVillage\s+"
        r"([A-Za-z ]+?)"
        r"(?=,\s*Tehsil|,|;)",
        clean,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def extract_tehsil(text):
    clean = compact(text)

    match = re.search(
        r"\bTehsil\s+"
        r"([A-Za-z ]+?)"
        r"(?=,\s*(?:New Delhi|Delhi)|,|;)",
        clean,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def extract_owner_names(text):
    clean = compact(text)

    owners = []

    match = re.search(
        r"belonging\s+to\s+"
        r"(.+?)"
        r"(?=,\s*have\s+been|,\s*has\s+been)",
        clean,
        re.IGNORECASE,
    )

    if match:
        owners.append(
            match.group(1).strip()
        )

    return unique(owners)


def extract_seller_names(text):
    clean = compact(text)

    names = re.findall(
        r"\[\d+\]\s*SHRI\s*"
        r"(.+?)"
        r"(?=,\s*S/o)",
        clean,
        re.IGNORECASE,
    )

    return unique(names)


def extract_mustatil_numbers(text):
    values = re.findall(
        r"Mustatil\s+No\.?\s*(\d+)",
        text,
        re.IGNORECASE,
    )

    return unique(values)


def extract_killa_numbers(text):
    values = re.findall(
        r"\b(\d+(?:/\d+)?)"
        r"\s*\(\s*\d+\s*-\s*\d+\s*\)",
        text,
    )

    return unique(values)


def extract_document_numbers(text):
    values = re.findall(
        r"DOCUMENT\s+NO\.?\s*"
        r"([A-Z0-9/-]+)",
        text,
        re.IGNORECASE,
    )

    return unique(values)


def extract_volume_numbers(text):
    values = re.findall(
        r"VOLUME(?:\s+NO\.?)?\s*"
        r"([0-9]+)",
        text,
        re.IGNORECASE,
    )

    return unique(values)


def extract_lr_numbers(text):
    values = re.findall(
        r"L\.?\s*R\.?\s*"
        r"(?:Number|No\.?)\s*"
        r"([0-9/-]+)",
        text,
        re.IGNORECASE,
    )

    return unique(values)


def extract_phone_numbers(text):
    values = re.findall(
        r"(?<!\d)"
        r"(?:"
        r"0\d{2,4}[-\s]?\d{6,8}"
        r"|"
        r"[6-9]\d{9}"
        r")"
        r"(?!\d)",
        text,
    )

    return unique(
        [
            re.sub(r"\s+", "", value)
            for value in values
        ]
    )


def extract_pincodes(text):
    values = re.findall(
        r"(?<![\d/])"
        r"([1-9]\d{5})"
        r"(?![\d/])",
        text,
    )

    return unique(values)


def extract_email_addresses(text):
    values = re.findall(
        r"\b[A-Z0-9._%+-]+"
        r"@[A-Z0-9.-]+"
        r"\.[A-Z]{2,}\b",
        text,
        re.IGNORECASE,
    )

    return unique(values)


def extract_objection_days(text):
    match = re.search(
        r"within\s+"
        r"(\d+)"
        r"(?:\s*\([^)]+\))?"
        r"\s+days",
        text,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def extract_land_area(text):
    clean = compact(text)

    match = re.search(
        r"land\s+measuring\s+"
        r"(\d+\s+Bighas?"
        r"\s+(?:and\s+)?"
        r"\d+\s+Biswas?)",
        clean,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    return None


def structure_notice(path):
    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    classification, keywords = (
        classify_property_notice(text)
    )

    result = {
        "source_file": path.name,
        "classification": classification,
        "notice_type": extract_notice_type(text),
        "property_keywords": keywords,
    }

    if classification == "NOT_RELEVANT":
        result["raw_text"] = text.strip()
        return result

    result.update(
        {
            "transaction_type":
                extract_transaction_type(text),

            "property_number":
                extract_property_number(text),

            "property_address":
                extract_property_address(text),

            "village":
                extract_village(text),

            "tehsil":
                extract_tehsil(text),

            "city":
                (
                    "New Delhi"
                    if re.search(
                        r"\bNew Delhi\b",
                        text,
                        re.IGNORECASE,
                    )
                    else None
                ),

            "pincodes":
                extract_pincodes(text),

            "owner_names":
                extract_owner_names(text),

            "seller_names":
                extract_seller_names(text),

            "mustatil_numbers":
                extract_mustatil_numbers(text),

            "killa_numbers":
                extract_killa_numbers(text),

            "document_numbers":
                extract_document_numbers(text),

            "volume_numbers":
                extract_volume_numbers(text),

            "lr_numbers":
                extract_lr_numbers(text),

            "land_area":
                extract_land_area(text),

            "objection_period_days":
                extract_objection_days(text),

            "phone_numbers":
                extract_phone_numbers(text),

            "email_addresses":
                extract_email_addresses(text),

            "raw_text":
                text.strip(),
        }
    )

    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Convert OCR public notices "
            "into structured property JSON."
        )
    )

    parser.add_argument(
        "--notices-dir",
        required=True,
        help="Folder containing notice .txt files",
    )

    parser.add_argument(
        "--output",
        help="Optional output JSON path",
    )

    args = parser.parse_args()

    notices_dir = Path(
        args.notices_dir
    ).expanduser().resolve()

    if not notices_dir.is_dir():
        raise SystemExit(
            f"Folder not found: {notices_dir}"
        )

    txt_files = sorted(
        notices_dir.glob("*.txt")
    )

    results = [
        structure_notice(path)
        for path in txt_files
    ]

    relevant = [
        item
        for item in results
        if item["classification"]
        == "PROPERTY_RELEVANT"
    ]

    ignored = [
        item
        for item in results
        if item["classification"]
        == "NOT_RELEVANT"
    ]

    if args.output:
        output_path = Path(
            args.output
        ).expanduser().resolve()
    else:
        output_path = (
            notices_dir.parent
            / "structured_notices.json"
        )

    final = {
        "total_notices": len(results),
        "property_related_notices": len(relevant),
        "ignored_notices": len(ignored),
        "notices": results,
    }

    output_path.write_text(
        json.dumps(
            final,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    relevant_path = (
        output_path.parent
        / "property_notices_only.json"
    )

    relevant_path.write_text(
        json.dumps(
            relevant,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("STRUCTURED EXTRACTION COMPLETE")
    print("=" * 60)

    print(
        "Total notices:",
        len(results),
    )

    print(
        "Property related:",
        len(relevant),
    )

    print(
        "Ignored:",
        len(ignored),
    )

    print()

    for item in results:
        print(
            item["source_file"],
            "->",
            item["classification"],
        )

    print()
    print("Full output:")
    print(output_path)

    print()
    print("Property notices only:")
    print(relevant_path)


if __name__ == "__main__":
    main()
