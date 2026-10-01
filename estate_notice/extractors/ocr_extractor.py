import argparse
import json
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image


def ocr_required_pages(pdf_path, direct_json_path, ocr_list_path):
    pdf_path = Path(pdf_path).expanduser().resolve()
    direct_json_path = Path(direct_json_path).expanduser().resolve()
    ocr_list_path = Path(ocr_list_path).expanduser().resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not direct_json_path.exists():
        raise FileNotFoundError(
            f"direct_text.json not found: {direct_json_path}"
        )
    if not ocr_list_path.exists():
        raise FileNotFoundError(
            f"ocr_required_pages.json not found: {ocr_list_path}"
        )

    print("\n======================================")
    print("ESTATE NOTICE - OCR EXTRACTION")
    print("======================================")
    print("\nPDF:")
    print(pdf_path)

    with direct_json_path.open("r", encoding="utf-8") as file:
        direct_data = json.load(file)

    with ocr_list_path.open("r", encoding="utf-8") as file:
        ocr_data = json.load(file)

    pages_to_ocr = [
        page["page_number"]
        for page in ocr_data["pages"]
    ]

    print("\nPages needing OCR:")
    if pages_to_ocr:
        print(", ".join(str(page) for page in pages_to_ocr))
    else:
        print("No pages need OCR.")

    output_folder = pdf_path.parent / "ocr_extraction"
    output_folder.mkdir(parents=True, exist_ok=True)

    page_text_folder = output_folder / "pages"
    page_text_folder.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open(str(pdf_path))
    ocr_results = {}

    try:
        for page_number in pages_to_ocr:
            print("\n--------------------------------------")
            print(f"OCR processing page {page_number}")

            page_index = page_number - 1

            if page_index < 0 or page_index >= document.page_count:
                print("Invalid page number.")
                continue

            page = document.load_page(page_index)

            matrix = pymupdf.Matrix(2, 2)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)

            image = Image.frombytes(
                "RGB",
                [pixmap.width, pixmap.height],
                pixmap.samples,
            )

            try:
                text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                    config="--oem 3 --psm 3",
                ).strip()
                status = "success"
                reason = None
            except Exception as error:
                text = ""
                status = "failed"
                reason = str(error)

            text_path = page_text_folder / f"page_{page_number:03d}.txt"
            text_path.write_text(text, encoding="utf-8")

            ocr_results[page_number] = {
                "page_number": page_number,
                "method": "ocr",
                "status": status,
                "text": text,
                "character_count": len(text),
                "text_file": str(text_path),
                "reason": reason,
            }

            print("Characters extracted:", len(text))

    finally:
        document.close()

    ocr_result_file = output_folder / "ocr_text.json"
    ocr_output = {
        "pdf_path": str(pdf_path),
        "ocr_page_count": len(ocr_results),
        "pages": list(ocr_results.values()),
    }
    ocr_result_file.write_text(
        json.dumps(ocr_output, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    combined_pages = []

    for direct_page in direct_data["pages"]:
        page_number = direct_page["page_number"]

        if page_number in ocr_results:
            ocr_page = ocr_results[page_number]
            combined_pages.append({
                "page_number": page_number,
                "method": "ocr",
                "status": ocr_page["status"],
                "text": ocr_page["text"],
                "character_count": ocr_page["character_count"],
                "reason": ocr_page["reason"],
            })
        else:
            combined_pages.append({
                "page_number": page_number,
                "method": "direct",
                "status": direct_page["status"],
                "text": direct_page["text"],
                "character_count": direct_page["character_count"],
                "reason": direct_page["reason"],
            })

    combined_pages.sort(key=lambda page: page["page_number"])

    combined_result = {
        "pdf_path": str(pdf_path),
        "total_pages": len(combined_pages),
        "pages": combined_pages,
    }

    combined_file = output_folder / "combined_text.json"
    combined_file.write_text(
        json.dumps(combined_result, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    full_text_file = output_folder / "full_newspaper.txt"
    with full_text_file.open("w", encoding="utf-8") as file:
        for page in combined_pages:
            file.write(
                "\n\n"
                "====================================\n"
            )
            file.write(f"PAGE {page['page_number']}\n")
            file.write(
                "====================================\n\n"
            )
            file.write(page["text"])

    print("\n======================================")
    print("OCR FINISHED")
    print("======================================")
    print("\nOCR pages processed:", len(ocr_results))
    print("\nOCR result:")
    print(ocr_result_file)
    print("\nCombined result:")
    print(combined_file)
    print("\nFull newspaper text:")
    print(full_text_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--direct-json", required=True)
    parser.add_argument("--ocr-list", required=True)
    arguments = parser.parse_args()

    ocr_required_pages(
        arguments.pdf,
        arguments.direct_json,
        arguments.ocr_list,
    )
