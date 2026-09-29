import os
from pypdf import PdfReader


def extract_pdf_text(pdf_path):

    print("\n================================")
    print("DIRECT PDF TEXT EXTRACTION")
    print("================================")

    # Step 1: Check PDF exists
    if not os.path.exists(pdf_path):
        print("PDF not found:")
        print(pdf_path)
        return

    print("\nPDF found:")
    print(pdf_path)

    # Step 2: Open PDF
    reader = PdfReader(pdf_path)

    total_pages = len(reader.pages)

    print("\nTotal pages:", total_pages)

    # Step 3: Create output folder
    pdf_folder = os.path.dirname(pdf_path)

    output_folder = os.path.join(
        pdf_folder,
        "raw_text"
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    total_characters = 0

    # Step 4: Read every page
    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        print(
            f"\nReading page {page_number}..."
        )

        try:

            text = page.extract_text() or ""

        except Exception as e:

            print("Error:", e)
            text = ""

        text = text.strip()

        character_count = len(text)

        total_characters += character_count

        print(
            "Characters extracted:",
            character_count
        )

        # Save page text
        text_file = os.path.join(
            output_folder,
            f"page_{page_number}.txt"
        )

        with open(
            text_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(text)

    # Step 5: Decide whether OCR is needed
    print("\n================================")

    if total_characters == 0:

        print("NO SELECTABLE TEXT FOUND")
        print("OCR IS REQUIRED")
        print("Give PDF to Janvi")

    else:

        print("DIRECT EXTRACTION SUCCESSFUL")

        print(
            "Total characters:",
            total_characters
        )

    print("================================")

    print("\nRaw text saved inside:")
    print(output_folder)


if __name__ == "__main__":

    pdf_path = input(
        "Paste newspaper PDF path: "
    )

    extract_pdf_text(pdf_path)
