import json
import os
import re

from detector import detect_notice
from extractor import extract_notice_details


# =========================================================
# INPUT AND OUTPUT FILES
# =========================================================

INPUT_FILE = (
    "/home/frappe-Poor/frappe-bench/sites/site1.local/"
    "private/files/newspapers/manual_test/"
    "ocr_extraction/full_newspaper.txt"
)

OUTPUT_FILE = "notice_detection/newspaper_notice_results.json"


# =========================================================
# READ NEWSPAPER TEXT
# =========================================================

def read_newspaper():

    if not os.path.exists(INPUT_FILE):

        print("ERROR: Newspaper text file not found.")
        print(INPUT_FILE)

        return None

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# =========================================================
# SPLIT NEWSPAPER INTO PAGES
# =========================================================

def split_pages(text):

    pages = []

    current_page_number = None
    current_page_lines = []

    for line in text.splitlines():

        line = line.strip()

        page_match = re.match(
            r"^PAGE\s+(\d+)\s*$",
            line,
            re.IGNORECASE
        )

        if page_match:

            # Save previous page
            if current_page_number is not None:

                pages.append({
                    "page_number": current_page_number,
                    "text": "\n".join(
                        current_page_lines
                    ).strip()
                })

            current_page_number = int(
                page_match.group(1)
            )

            current_page_lines = []

            continue

        # Ignore separator lines
        if line == "====================================":

            continue

        # Add text to current page
        if current_page_number is not None and line:

            current_page_lines.append(line)

    # Save final page
    if current_page_number is not None:

        pages.append({
            "page_number": current_page_number,
            "text": "\n".join(
                current_page_lines
            ).strip()
        })

    return pages


# =========================================================
# FIND POSSIBLE NOTICE SECTIONS
# =========================================================

def find_notice_sections(text):

    lines = text.splitlines()

    keywords = [

        "public notice",
        "public notices",

        "legal notice",
        "legal notices",

        "court notice",
        "court notices",

        "auction notice",
        "auction notices",

        "claims and objections",
        "claim and objection"

    ]

    sections = []

    for index, line in enumerate(lines):

        lower_line = line.lower()

        found = False

        for keyword in keywords:

            if keyword in lower_line:

                found = True
                break

        if not found:

            continue

        # Keep some lines before and after
        # the notice heading.
        start = max(
            0,
            index - 5
        )

        end = min(
            len(lines),
            index + 40
        )

        section_text = "\n".join(
            lines[start:end]
        ).strip()

        sections.append({

            "start_line":
                start + 1,

            "end_line":
                end,

            "text":
                section_text

        })

    return sections


# =========================================================
# REMOVE DUPLICATE SECTIONS
# =========================================================

def remove_duplicate_sections(sections):

    unique = []

    seen = set()

    for section in sections:

        section_text = section["text"]

        if section_text not in seen:

            seen.add(section_text)

            unique.append(section)

    return unique


# =========================================================
# SPLIT A NOTICE SECTION INTO SMALLER BLOCKS
# =========================================================

def split_notice_into_blocks(section_text):

    lines = section_text.splitlines()

    blocks = []

    current_block = []

    boundary_terms = [

        "public notice",
        "public notices",

        "legal notice",
        "legal notices",

        "court notice",
        "court notices",

        "auction notice",
        "auction notices",

        "notice is hereby",
        "notice hereby",

        "claims and objections",

        # Advertisement boundaries
        "sale or rent",
        "classifieds",
        "property related ads",
        "to book your"

    ]

    for line in lines:

        clean_line = line.strip()

        if not clean_line:

            continue

        lower_line = clean_line.lower()

        is_boundary = False

        for term in boundary_terms:

            if term in lower_line:

                is_boundary = True
                break

        # If another strong heading appears,
        # finish the previous block.
        if is_boundary and current_block:

            blocks.append(
                "\n".join(
                    current_block
                ).strip()
            )

            current_block = []

        current_block.append(
            clean_line
        )

    # Add final block
    if current_block:

        blocks.append(
            "\n".join(
                current_block
            ).strip()
        )

    # Remove extremely small blocks
    cleaned_blocks = []

    for block in blocks:

        if len(block.strip()) >= 30:

            cleaned_blocks.append(
                block
            )

    return cleaned_blocks


# =========================================================
# DETERMINE EXTRACTION QUALITY
# =========================================================

def evaluate_extraction(extraction):

    important_fields = [

        "survey_number",
        "plot_number",
        "property_number",
        "location",
        "phone",
        "email"

    ]

    available_fields = []

    missing_fields = []

    for field in important_fields:

        value = extraction.get(
            field
        )

        if value:

            available_fields.append(
                field
            )

        else:

            missing_fields.append(
                field
            )

    # -----------------------------------------------------
    # COMPLETE
    # -----------------------------------------------------

    if len(available_fields) >= 3:

        extraction_status = "COMPLETE"

        needs_review = False

    # -----------------------------------------------------
    # PARTIAL
    # -----------------------------------------------------

    elif len(available_fields) >= 1:

        extraction_status = "PARTIAL"

        needs_review = True

    # -----------------------------------------------------
    # NOTHING EXTRACTED
    # -----------------------------------------------------

    else:

        extraction_status = (
            "NO_DETAILS_EXTRACTED"
        )

        needs_review = True

    return (
        extraction_status,
        needs_review,
        available_fields,
        missing_fields
    )


# =========================================================
# PROCESS ONE PAGE
# =========================================================

def process_page(page_number, text):

    sections = find_notice_sections(
        text
    )

    sections = remove_duplicate_sections(
        sections
    )

    detected_sections = []

    for section in sections:

        blocks = split_notice_into_blocks(
            section["text"]
        )

        for block_number, block in enumerate(
            blocks,
            start=1
        ):

            # -------------------------------------------------
            # DETECT NOTICE
            # -------------------------------------------------

            detection = detect_notice(
                block
            )

            # -------------------------------------------------
            # Ignore non-relevant content
            # -------------------------------------------------

            if not detection["is_notice"]:

                continue

            # -------------------------------------------------
            # EXTRACT DETAILS
            # -------------------------------------------------

            extraction = extract_notice_details(
                block
            )

            # -------------------------------------------------
            # CHECK EXTRACTION QUALITY
            # -------------------------------------------------

            (
                extraction_status,
                needs_review,
                available_fields,
                missing_fields
            ) = evaluate_extraction(
                extraction
            )

            # -------------------------------------------------
            # SAVE DETECTED NOTICE
            # -------------------------------------------------

            detected_sections.append({

                "section_start_line":
                    section["start_line"],

                "section_end_line":
                    section["end_line"],

                "block_number":
                    block_number,

                "detection":
                    detection,

                "extraction":
                    extraction,

                "extraction_status":
                    extraction_status,

                "needs_review":
                    needs_review,

                "available_fields":
                    available_fields,

                "missing_fields":
                    missing_fields,

                "text":
                    block

            })

    return {

        "page_number":
            page_number,

        "is_notice":
            len(detected_sections) > 0,

        "notice_count":
            len(detected_sections),

        "notice_sections":
            detected_sections

    }


# =========================================================
# PROCESS ENTIRE NEWSPAPER
# =========================================================

def process_newspaper():

    print()

    print("=" * 60)

    print(
        "ESTATE NOTICE NEWSPAPER PROCESSOR"
    )

    print("=" * 60)

    # -----------------------------------------------------
    # Read newspaper
    # -----------------------------------------------------

    newspaper_text = read_newspaper()

    if newspaper_text is None:

        return

    print()

    print(
        "Newspaper text loaded successfully."
    )

    # -----------------------------------------------------
    # Split pages
    # -----------------------------------------------------

    pages = split_pages(
        newspaper_text
    )

    print()

    print(
        "Total pages found:",
        len(pages)
    )

    # -----------------------------------------------------
    # Process pages
    # -----------------------------------------------------

    results = []

    detected_pages = 0

    total_detected_notices = 0

    for page in pages:

        page_number = page[
            "page_number"
        ]

        page_text = page[
            "text"
        ]

        result = process_page(
            page_number,
            page_text
        )

        results.append(
            result
        )

        # -------------------------------------------------
        # Print detected notices
        # -------------------------------------------------

        if result["is_notice"]:

            detected_pages += 1

            total_detected_notices += (
                result["notice_count"]
            )

            print()

            print("=" * 60)

            print(
                "NOTICE FOUND ON PAGE:",
                page_number
            )

            print("=" * 60)

            for notice in result[
                "notice_sections"
            ]:

                print()

                print(
                    "Section lines:",
                    notice[
                        "section_start_line"
                    ],
                    "-",
                    notice[
                        "section_end_line"
                    ]
                )

                print(
                    "Notice block:",
                    notice[
                        "block_number"
                    ]
                )

                print(
                    "Notice type:",
                    notice[
                        "detection"
                    ][
                        "notice_type"
                    ]
                )

                print(
                    "Confidence:",
                    notice[
                        "detection"
                    ][
                        "confidence"
                    ]
                )

                print(
                    "Score:",
                    notice[
                        "detection"
                    ][
                        "score"
                    ]
                )

                print(
                    "Reasons:",
                    notice[
                        "detection"
                    ][
                        "reasons"
                    ]
                )

                print(
                    "Extraction status:",
                    notice[
                        "extraction_status"
                    ]
                )

                print(
                    "Needs review:",
                    notice[
                        "needs_review"
                    ]
                )

                print(
                    "Available fields:",
                    notice[
                        "available_fields"
                    ]
                )

                print(
                    "Missing fields:",
                    notice[
                        "missing_fields"
                    ]
                )

                print(
                    "Extracted:",
                    notice[
                        "extraction"
                    ]
                )

                print()

                print(
                    "Notice text:"
                )

                print(
                    notice["text"]
                )

                print(
                    "-" * 60
                )

    # =====================================================
    # CREATE FINAL JSON
    # =====================================================

    output = {

        "newspaper_file":
            INPUT_FILE,

        "total_pages":
            len(pages),

        "detected_notice_pages":
            detected_pages,

        "total_detected_notices":
            total_detected_notices,

        "results":
            results

    }

    # -----------------------------------------------------
    # Save JSON
    # -----------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    # -----------------------------------------------------
    # Final summary
    # -----------------------------------------------------

    print()

    print("=" * 60)

    print(
        "PROCESSING COMPLETE"
    )

    print("=" * 60)

    print(
        "Total pages:",
        len(pages)
    )

    print(
        "Notice pages detected:",
        detected_pages
    )

    print(
        "Individual notices detected:",
        total_detected_notices
    )

    print()

    print(
        "Results saved to:",
        OUTPUT_FILE
    )


# =========================================================
# PROGRAM START
# =========================================================

if __name__ == "__main__":

    process_newspaper()
