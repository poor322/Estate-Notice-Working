import argparse
import cv2
import json
import re
import pymupdf
import numpy as np
import pytesseract

from pathlib import Path

parser = argparse.ArgumentParser(
    description="Automatic Public Notice Extraction"
)

parser.add_argument(
    "--pdf",
    required=True,
    help="Full path of the newspaper PDF"
)

args = parser.parse_args()

PDF = Path(args.pdf).expanduser().resolve()

if not PDF.is_file():
    parser.error(f"PDF not found: {PDF}")

if PDF.suffix.lower() != ".pdf":
    parser.error("Input must be a PDF file")

OCR_BASE = PDF.parent / "ocr_extraction"

OUTPUT = OCR_BASE / f"{PDF.stem}_automatic_test"

SCAN_FILE = OUTPUT / "public_notice_pages.json"

COLUMN_DIR = OUTPUT / "columns"
NOTICE_DIR = OUTPUT / "notices"
REVIEW_DIR = OUTPUT / "needs_review"

for folder in [COLUMN_DIR, NOTICE_DIR, REVIEW_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

if not PDF.exists():
    raise SystemExit("ERROR: Newspaper PDF missing")

doc = pymupdf.open(PDF)

print("\n===== AUTOMATIC NEWSPAPER SCAN =====")
print("PDF:", PDF)
print("Total pages:", len(doc))

matching_pages = []

for page_index in range(len(doc)):

    page_number = page_index + 1

    page = doc[page_index]

    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(2, 2),
        alpha=False
    )

    image = np.frombuffer(
        pix.samples,
        dtype=np.uint8
    ).reshape(
        pix.height,
        pix.width,
        3
    ).copy()

    image = cv2.cvtColor(
        image,
        cv2.COLOR_RGB2BGR
    )

    H, W = image.shape[:2]

    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2HSV
    )

    lower = np.array([120, 55, 40])
    upper = np.array([165, 255, 255])

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (5, 3)
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    headings = []

    for contour in contours:

        x, y, w, h = cv2.boundingRect(contour)

        if w < W * 0.035 or h < H * 0.004:
            continue

        if h > H * 0.06 or w / h < 2.5:
            continue

        crop = image[y:y+h, x:x+w]

        gray = cv2.cvtColor(
            crop,
            cv2.COLOR_BGR2GRAY
        )

        enlarged = cv2.resize(
            gray,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC
        )

        _, binary = cv2.threshold(
            enlarged,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        text = pytesseract.image_to_string(
            binary,
            config="--psm 7"
        ).strip()

        clean = re.sub(
            r"[^A-Z]",
            "",
            text.upper()
        )

        if "PUBLICNOTICE" in clean:

            headings.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "text": text
            })

    print(
        f"Page {page_number}: "
        f"{len(headings)} headings found"
    )

    if headings:

        matching_pages.append({
            "page_number": page_number,
            "headings": headings
        })

scan = {
    "total_pdf_pages": len(doc),
    "matching_pages": matching_pages
}

SCAN_FILE.write_text(
    json.dumps(scan, indent=4),
    encoding="utf-8"
)

print("\n===== PAGE SCAN COMPLETED =====")

print(
    "Pages containing detected headings:",
    len(matching_pages)
)

for item in matching_pages:

    print(
        "Page:",
        item["page_number"],
        "| Headings:",
        len(item["headings"])
    )

print("Scan saved:", SCAN_FILE)

results = []
total_notices = 0
total_review = 0

print("\n===== INTEGRATED NOTICE PIPELINE =====")
print("Newspaper pages:", len(doc))
print("Pages selected by heading scan:",
      len(scan["matching_pages"]))

for page_info in scan["matching_pages"]:

    page_number = page_info["page_number"]

    print(f"\n===== PROCESSING PAGE {page_number} =====")

    page = doc[page_number - 1]

    # Render at 5x resolution
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(5, 5),
        alpha=False
    )

    image = np.frombuffer(
        pix.samples,
        dtype=np.uint8
    ).reshape(
        pix.height,
        pix.width,
        3
    ).copy()

    image = cv2.cvtColor(
        image,
        cv2.COLOR_RGB2BGR
    )

    H, W = image.shape[:2]

    # Previous heading scan used 2x resolution
    scale = 5 / 2

    headings = sorted(
        page_info["headings"],
        key=lambda b: (b["y"], b["x"])
    )

    for column_number, heading in enumerate(headings, 1):

        x = int(heading["x"] * scale)
        y = int(heading["y"] * scale)
        w = int(heading["width"] * scale)

        x1 = max(0, x - 8)
        x2 = min(W, x + w + 8)
        y1 = max(0, y)

        column = image[y1:H, x1:x2]

        column_name = (
            f"page_{page_number}_column_{column_number}.png"
        )

        cv2.imwrite(
            str(COLUMN_DIR / column_name),
            column
        )

        print(f"\nColumn {column_number}")

        gray = cv2.cvtColor(
            column,
            cv2.COLOR_BGR2GRAY
        )

        _, binary = cv2.threshold(
            gray,
            160,
            255,
            cv2.THRESH_BINARY_INV
        )

        CW = column.shape[1]
        CH = column.shape[0]

        horizontal_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (max(40, int(CW * 0.55)), 1)
        )

        vertical_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (1, max(25, int(CW * 0.15)))
        )

        horizontal = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            horizontal_kernel
        )

        vertical = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            vertical_kernel
        )

        borders = cv2.bitwise_or(
            horizontal,
            vertical
        )

        borders = cv2.morphologyEx(
            borders,
            cv2.MORPH_CLOSE,
            np.ones((3, 3), np.uint8)
        )

        contours, _ = cv2.findContours(
            borders,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        boxes = []

        for contour in contours:

            bx, by, bw, bh = cv2.boundingRect(contour)

            if bw < CW * 0.70:
                continue

            if bh < CH * 0.04:
                continue

            if bh > CH * 0.92:
                continue

            boxes.append((bx, by, bw, bh))

        boxes.sort(key=lambda b: (b[1], b[0]))

        print("Candidate boxes:", len(boxes))

        for candidate_number, (bx, by, bw, bh) in enumerate(
            boxes, 1
        ):

            left = max(0, bx - 3)
            right = min(CW, bx + bw + 3)
            top = max(0, by - 12)
            bottom = min(CH, by + bh + 3)

            crop = column[top:bottom, left:right]

            if crop.size == 0:
                continue

            crop_gray = cv2.cvtColor(
                crop,
                cv2.COLOR_BGR2GRAY
            )

            heading_part = crop_gray[
                :min(150, crop_gray.shape[0]), :
            ]

            enlarged_heading = cv2.resize(
                heading_part,
                None,
                fx=3,
                fy=3,
                interpolation=cv2.INTER_CUBIC
            )

            heading_text = pytesseract.image_to_string(
                enlarged_heading,
                config="--psm 6"
            )

            clean_heading = re.sub(
                r"[^A-Z]",
                "",
                heading_text.upper()
            )

            filename = (
                f"page_{page_number}_"
                f"column_{column_number}_"
                f"candidate_{candidate_number}"
            )

            # A heading banner alone is not a complete notice.
            # Require meaningful body text below the heading.
            body_part = crop_gray[
                min(150, crop_gray.shape[0]):,
                :
            ]

            body_text = ""

            if body_part.size > 0 and body_part.shape[0] >= 150:

                enlarged_body = cv2.resize(
                    body_part,
                    None,
                    fx=2,
                    fy=2,
                    interpolation=cv2.INTER_CUBIC
                )

                body_text = pytesseract.image_to_string(
                    enlarged_body,
                    config="--oem 3 --psm 6"
                ).strip()

            body_characters = len(
                re.sub(
                    r"[^A-Za-z0-9]",
                    "",
                    body_text
                )
            )

            is_complete_notice = (
                "PUBLICNOTICE" in clean_heading[:100]
                and crop_gray.shape[0] >= 300
                and body_characters >= 80
            )

            if is_complete_notice:

                # Save detected notice image
                cv2.imwrite(
                    str(NOTICE_DIR / f"{filename}.png"),
                    crop
                )

                enlarged = cv2.resize(
                    crop_gray,
                    None,
                    fx=3,
                    fy=3,
                    interpolation=cv2.INTER_CUBIC
                )

                text = pytesseract.image_to_string(
                    enlarged,
                    config="--oem 3 --psm 6"
                ).strip()

                text_file = NOTICE_DIR / f"{filename}.txt"

                text_file.write_text(
                    text,
                    encoding="utf-8"
                )

                results.append({
                    "page_number": page_number,
                    "column_number": column_number,
                    "image": filename + ".png",
                    "characters": len(text),
                    "status": "needs_review",
                    "text": text
                })

                total_notices += 1

                print(
                    f"  PUBLIC NOTICE: {filename}"
                )

            else:

                # Preserve uncertain candidates
                cv2.imwrite(
                    str(REVIEW_DIR / f"{filename}.png"),
                    crop
                )

                total_review += 1

                print(
                    f"  NEEDS REVIEW: {filename}"
                )

output_json = OUTPUT / "all_public_notices.json"

output_json.write_text(
    json.dumps(
        {
            "newspaper": "Hindustan Times",
            "total_pdf_pages": len(doc),
            "pages_selected_by_heading_scan": [
                p["page_number"]
                for p in scan["matching_pages"]
            ],
            "total_notice_candidates_recognized": total_notices,
            "other_candidates_needing_review": total_review,
            "notices": results
        },
        indent=4,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

doc.close()

print("\n================================")
print("INTEGRATED PIPELINE COMPLETED")
print("================================")
print("Notices recognized:", total_notices)
print("Other candidates needing review:", total_review)
print("Output:", output_json)
