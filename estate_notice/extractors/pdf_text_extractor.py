import os
import json
from pypdf import PdfReader


# ============================================================
# SETTINGS
# ============================================================

# These are simple checks to decide whether extracted text
# looks useful enough or should be sent to Janvi for OCR.
MIN_CHARACTERS = 80
MIN_WORDS = 10


# ============================================================
# CHECK WHETHER TEXT IS USABLE
# ============================================================

def check_text_quality(text):
    """
    Check whether the directly extracted text looks usable.

    Returns:
        status
        reason
    """

    cleaned_text = " ".join(text.split())

    # No text at all
    if not cleaned_text:

        return (
            "needs_ocr",
            "No selectable text found"
        )

    # Sometimes only page number like "3" is extracted
    if cleaned_text.isdigit():

        return (
            "needs_ocr",
            "Only a page number or numeric text was extracted"
        )

    character_count = len(cleaned_text)

    words = cleaned_text.split()

    word_count = len(words)

    # Very little text
    if character_count < MIN_CHARACTERS:

        return (
            "needs_ocr",
            "Too little selectable text was extracted"
        )

    # Not enough real words
    if word_count < MIN_WORDS:

        return (
            "needs_ocr",
            "Extracted text is too short to be useful"
        )

    return (
        "usable",
        None
    )


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_direct_text(pdf_path):

    print("\n======================================")
    print("ESTATE NOTICE - PDF TEXT EXTRACTION")
    print("======================================")

    # --------------------------------------------------------
    # CHECK PDF PATH
    # --------------------------------------------------------

    pdf_path = os.path.abspath(
        os.path.expanduser(pdf_path)
    )

    if not os.path.exists(pdf_path):

        print("\nERROR:")
        print("PDF file not found:")
        print(pdf_path)

        return {
            "status": "failed",
            "reason": "file_not_found",
            "pdf_path": pdf_path
        }


    if not pdf_path.lower().endswith(".pdf"):

        print("\nERROR:")
        print("The supplied file is not a PDF.")

        return {
            "status": "failed",
            "reason": "not_a_pdf",
            "pdf_path": pdf_path
        }


    print("\nPDF found:")
    print(pdf_path)


    # --------------------------------------------------------
    # OPEN PDF
    # --------------------------------------------------------

    try:

        reader = PdfReader(
            pdf_path
        )

    except Exception as error:

        print("\nERROR:")
        print("Could not open PDF.")
        print(error)

        return {
            "status": "failed",
            "reason": "pdf_open_failed",
            "error": str(error),
            "pdf_path": pdf_path
        }


    total_pages = len(
        reader.pages
    )


    print("\nTotal PDF pages:")
    print(total_pages)


    if total_pages == 0:

        print("\nERROR:")
        print("PDF contains no pages.")

        return {
            "status": "failed",
            "reason": "pdf_has_no_pages",
            "pdf_path": pdf_path
        }


    # ========================================================
    # CREATE OUTPUT FOLDERS
    # ========================================================

    pdf_folder = os.path.dirname(
        pdf_path
    )


    output_folder = os.path.join(
        pdf_folder,
        "direct_extraction"
    )


    page_text_folder = os.path.join(
        output_folder,
        "pages"
    )


    os.makedirs(
        page_text_folder,
        exist_ok=True
    )


    print("\nOutput folder:")
    print(output_folder)


    # ========================================================
    # RESULT LISTS
    # ========================================================

    all_pages = []

    ocr_required_pages = []

    usable_pages = 0

    total_characters = 0


    # ========================================================
    # PROCESS EVERY PDF PAGE
    # ========================================================

    for page_index, page in enumerate(
        reader.pages,
        start=1
    ):

        print("\n--------------------------------------")

        print(
            f"Processing page "
            f"{page_index}/{total_pages}"
        )


        # ----------------------------------------------------
        # DIRECT TEXT EXTRACTION
        # ----------------------------------------------------

        extraction_error = None

        try:

            text = (
                page.extract_text()
                or ""
            )

            text = text.strip()

        except Exception as error:

            text = ""

            extraction_error = str(
                error
            )


        # ----------------------------------------------------
        # TEXT QUALITY CHECK
        # ----------------------------------------------------

        if extraction_error is not None:

            status = "needs_ocr"

            reason = (
                "Direct text extraction failed: "
                + extraction_error
            )

        else:

            status, reason = (
                check_text_quality(
                    text
                )
            )


        character_count = len(
            text
        )


        total_characters += (
            character_count
        )


        # ----------------------------------------------------
        # SAVE PAGE TEXT
        # ----------------------------------------------------

        text_filename = (
            f"page_{page_index:03d}.txt"
        )


        text_file_path = os.path.join(
            page_text_folder,
            text_filename
        )


        with open(
            text_file_path,
            "w",
            encoding="utf-8"
        ) as text_file:

            text_file.write(
                text
            )


        # ----------------------------------------------------
        # CREATE ONE RESULT FOR EVERY PAGE
        # ----------------------------------------------------

        page_result = {
            "page_number": page_index,
            "method": "direct",
            "status": status,
            "text": text,
            "character_count": character_count,
            "text_file": text_file_path,
            "reason": reason
        }


        all_pages.append(
            page_result
        )


        # ----------------------------------------------------
        # OCR REQUIRED?
        # ----------------------------------------------------

        if status == "needs_ocr":

            ocr_record = {
                "page_number": page_index,
                "reason": reason,
                "character_count": character_count
            }


            ocr_required_pages.append(
                ocr_record
            )


            print(
                "Result: OCR REQUIRED"
            )

            print(
                "Reason:",
                reason
            )


        else:

            usable_pages += 1


            print(
                "Result: DIRECT TEXT USABLE"
            )

            print(
                "Characters extracted:",
                character_count
            )


    # ========================================================
    # SAVE direct_text.json
    # ========================================================

    direct_text_result = {
        "status": "success",
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "usable_direct_pages": usable_pages,
        "ocr_required_pages": len(
            ocr_required_pages
        ),
        "total_characters": total_characters,
        "pages": all_pages
    }


    direct_text_json = os.path.join(
        output_folder,
        "direct_text.json"
    )


    with open(
        direct_text_json,
        "w",
        encoding="utf-8"
    ) as json_file:

        json.dump(
            direct_text_result,
            json_file,
            indent=4,
            ensure_ascii=False
        )


    # ========================================================
    # SAVE ocr_required_pages.json
    # ========================================================

    ocr_result = {
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "ocr_required_count": len(
            ocr_required_pages
        ),
        "pages": ocr_required_pages
    }


    ocr_json = os.path.join(
        output_folder,
        "ocr_required_pages.json"
    )


    with open(
        ocr_json,
        "w",
        encoding="utf-8"
    ) as json_file:

        json.dump(
            ocr_result,
            json_file,
            indent=4,
            ensure_ascii=False
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n======================================")
    print("EXTRACTION FINISHED")
    print("======================================")

    print(
        "\nTotal pages:",
        total_pages
    )

    print(
        "Usable direct-text pages:",
        usable_pages
    )

    print(
        "OCR required pages:",
        len(ocr_required_pages)
    )


    if ocr_required_pages:

        print(
            "\nPages to send to Janvi:"
        )

        page_numbers = [
            str(page["page_number"])
            for page
            in ocr_required_pages
        ]

        print(
            ", ".join(
                page_numbers
            )
        )

    else:

        print(
            "\nNo pages currently "
            "require OCR."
        )


    print(
        "\nDirect text result:"
    )

    print(
        direct_text_json
    )


    print(
        "\nOCR required list:"
    )

    print(
        ocr_json
    )


    print(
        "\nPage text files:"
    )

    print(
        page_text_folder
    )


    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {
        "status": "success",
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "usable_direct_pages": usable_pages,
        "ocr_required_pages": len(
            ocr_required_pages
        ),
        "direct_text_json": direct_text_json,
        "ocr_required_json": ocr_json
    }


# ============================================================
# RUN FROM TERMINAL
# ============================================================

if __name__ == "__main__":

    print(
        "\nPaste the full newspaper PDF path."
    )

    pdf_path = input(
        "PDF path: "
    ).strip()


    extract_direct_text(
        pdf_path
    )
