import json

from detector import detect_notice
from extractor import extract_notice_details


# ============================================
# PROCESS ONE NEWSPAPER PAGE
# ============================================

def process_page(page_number, text):

    print()
    print("=" * 60)
    print("PROCESSING PAGE:", page_number)
    print("=" * 60)

    # ----------------------------------------
    # STEP 1: DETECT NOTICE
    # ----------------------------------------

    detection = detect_notice(text)

    print()
    print("NOTICE DETECTION")
    print("-" * 60)

    print(
        "Notice detected:",
        detection["is_notice"]
    )

    print(
        "Confidence:",
        detection["confidence"]
    )

    print(
        "Score:",
        detection["score"]
    )

    print(
        "Reasons:",
        detection["reasons"]
    )

    # ----------------------------------------
    # STEP 2: EXTRACT DETAILS
    # ----------------------------------------

    if detection["is_notice"]:

        details = extract_notice_details(text)

        print()
        print("EXTRACTED INFORMATION")
        print("-" * 60)

        for key, value in details.items():

            print(
                key,
                ":",
                value
            )

    else:

        details = {}

        print()
        print(
            "This page is NOT treated as a notice."
        )

    # ----------------------------------------
    # STEP 3: FINAL JSON RESULT
    # ----------------------------------------

    result = {

        "page_number": page_number,

        "detection": detection,

        "extraction": details
    }

    return result


# ============================================
# TEST THE PIPELINE
# ============================================

if __name__ == "__main__":

    sample_text = """

    PUBLIC NOTICE

    Notice is hereby given to the general public
    that the property bearing Survey No. 123/4
    situated at Bengaluru is proposed to be sold.

    Any person having any claim or objection
    may contact the undersigned advocate.

    Contact: 9876543210

    Email: advocate@example.com

    """

    # ----------------------------------------
    # PROCESS PAGE
    # ----------------------------------------

    result = process_page(
        page_number=3,
        text=sample_text
    )

    # ----------------------------------------
    # PRINT FINAL RESULT
    # ----------------------------------------

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=4
        )
    )

    # ----------------------------------------
    # SAVE JSON FILE
    # ----------------------------------------

    with open(
        "notice_results.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False
        )

    print()
    print(
        "Result saved to notice_results.json"
    )
