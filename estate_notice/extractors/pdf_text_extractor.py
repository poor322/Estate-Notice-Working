import os
import json
from pypdf import PdfReader


def extract_pdf_text(pdf_path):

    print("\n================================")
    print("PDF TEXT EXTRACTION")
    print("================================")

    # Check whether PDF exists
    if not os.path.exists(pdf_path):

        print("PDF not found:")
        print(pdf_path)

        return {
            "status": "failed",
            "reason": "file_not_found"
        }

    print("\nPDF found:")
    print(pdf_path)

    # Open PDF
    reader = PdfReader(pdf_path)

    total_pages = len(reader.pages)

    print("\nTotal pages:", total_pages)

    # Create folder for extracted text
    pdf_folder = os.path.dirname(pdf_path)

    output_folder = os.path.join(
        pdf_folder,
        "raw_text"
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    pages = []

    total_characters = 0

    # Read every page
    for index, page in enumerate(
        reader.pages,
        start=1
    ):

        print(f"\nReading page {index}...")

        try:

            text = page.extract_text() or ""

            text = text.strip()

        except Exception as e:

            print("Error:", e)

            text = ""

        character_count = len(text)

        total_characters += character_count

        # Save each page separately
        text_file = os.path.join(
            output_folder,
            f"page_{index}.txt"
        )

        with open(
            text_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(text)

        pages.append({
            "page_number": index,
            "character_count": character_count,
            "text_file": text_file
        })

        print(
            "Characters:",
            character_count
        )

    # Decide whether OCR is required
    if total_characters == 0:

        extraction_method = "ocr_required"

        print("\n================================")
        print("NO SELECTABLE TEXT")
        print("SEND PDF TO JANVI FOR OCR")
        print("================================")

    else:

        extraction_method = "direct"

        print("\n================================")
        print("DIRECT EXTRACTION SUCCESS")
        print("================================")

        print(
            "Total characters:",
            total_characters
        )

    result = {
        "status": "success",
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "total_characters": total_characters,
        "extraction_method": extraction_method,
        "pages": pages
    }

    result_file = os.path.join(
        output_folder,
        "extraction_result.json"
    )

    with open(
        result_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4
        )

    print("\nResult saved:")
    print(result_file)

    return result


if __name__ == "__main__":

    pdf_path = input(
        "Paste newspaper PDF path: "
    )

    extract_pdf_text(pdf_path)
