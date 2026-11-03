import argparse
import json
import os
import re
import unicodedata
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytesseract
from pytesseract import Output

from estate_notice.utils.deduplication import NoticeDeduplicator

# ============================================================
# 1. CONFIGURATION
# ============================================================

parser = argparse.ArgumentParser(description="Automatic Gujarati and English Public Notice Extraction")

parser.add_argument("--pdf", required=True, help="Full path of the newspaper PDF")

args = parser.parse_args()

PDF = Path(args.pdf).expanduser().resolve()

if not PDF.is_file():
	parser.error(f"PDF not found: {PDF}")

if PDF.suffix.lower() != ".pdf":
	parser.error("Input must be a PDF file")

OCR_LANG = "guj+eng"
SCAN_SCALE = 1.5
CROP_SCALE = 5

OCR_BASE = PDF.parent / "ocr_extraction"
OUTPUT = OCR_BASE / f"{PDF.stem}_automatic_test"
OUTPUT.mkdir(parents=True, exist_ok=True)

OUTPUT_JSON = OUTPUT / "all_public_notices.json"
SCAN_FILE = OUTPUT / "public_notice_pages.json"

COLUMN_DIR = OUTPUT / "columns"
NOTICE_DIR = OUTPUT / "notices"
REVIEW_DIR = OUTPUT / "needs_review"

for folder in [COLUMN_DIR, NOTICE_DIR, REVIEW_DIR]:
	folder.mkdir(parents=True, exist_ok=True)

REGISTRY_FILE = Path(
	os.environ.get("ESTATE_NOTICE_REGISTRY", str(Path.home() / ".estate_notice" / "processed_notices.json"))
)

deduplicator = NoticeDeduplicator(REGISTRY_FILE)


# ============================================================
# 2. HEADING DETECTION
# ============================================================

HEADING_KEYWORDS = [
	"જાહેરનોટિસ",
	"જાહેરનોટીસ",
	"જાહેરસૂચના",
	"જાહેરાહેરાત",
	"publicnotice",
]


def normalize_text(text):
	"""Normalize OCR text while retaining Gujarati and English letters."""
	text = unicodedata.normalize("NFC", text.lower())
	return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


NORMALIZED_KEYWORDS = [normalize_text(keyword) for keyword in HEADING_KEYWORDS]


def is_public_notice_heading(text):
	"""Check whether OCR text contains a supported notice heading."""
	clean = normalize_text(text)

	return any(keyword in clean for keyword in NORMALIZED_KEYWORDS)


def detect_headings(image):
	"""
	Detect Gujarati and English notice headings using OCR word
	coordinates rather than relying on heading colour.
	"""

	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

	gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

	data = pytesseract.image_to_data(gray, lang=OCR_LANG, config="--oem 3 --psm 11", output_type=Output.DICT)

	lines = {}

	for i, word in enumerate(data["text"]):
		word = word.strip()

		if not word:
			continue

		key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])

		x = data["left"][i]
		y = data["top"][i]
		w = data["width"][i]
		h = data["height"][i]

		if key not in lines:
			lines[key] = {"words": [], "x1": x, "y1": y, "x2": x + w, "y2": y + h}

		lines[key]["words"].append(word)

		lines[key]["x1"] = min(lines[key]["x1"], x)
		lines[key]["y1"] = min(lines[key]["y1"], y)
		lines[key]["x2"] = max(lines[key]["x2"], x + w)
		lines[key]["y2"] = max(lines[key]["y2"], y + h)

	headings = []

	for line in lines.values():
		text = " ".join(line["words"])

		if is_public_notice_heading(text):
			headings.append(
				{
					"x": int(line["x1"]),
					"y": int(line["y1"]),
					"width": int(line["x2"] - line["x1"]),
					"height": int(line["y2"] - line["y1"]),
					"text": text,
				}
			)

	return headings


# ============================================================
# 3. OPEN NEWSPAPER
# ============================================================

doc = pymupdf.open(PDF)

print("\n===== AUTOMATIC NEWSPAPER SCAN =====")
print("PDF:", PDF)
print("Total pages:", len(doc))
print("OCR languages:", OCR_LANG)

matching_pages = []

for page_index in range(len(doc)):
	page_number = page_index + 1
	page = doc[page_index]

	pix = page.get_pixmap(matrix=pymupdf.Matrix(SCAN_SCALE, SCAN_SCALE), alpha=False)

	image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()

	image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

	headings = detect_headings(image)

	print(f"Page {page_number}: {len(headings)} headings found")

	if headings:
		matching_pages.append({"page_number": page_number, "headings": headings})


# ============================================================
# 4. SAVE HEADING SCAN RESULTS
# ============================================================

scan = {
	"newspaper": PDF.stem,
	"total_pdf_pages": len(doc),
	"ocr_languages": OCR_LANG,
	"scan_scale": SCAN_SCALE,
	"matching_pages": matching_pages,
}

SCAN_FILE.write_text(json.dumps(scan, indent=4, ensure_ascii=False), encoding="utf-8")

print("\n===== PAGE SCAN COMPLETED =====")

print("Pages containing detected headings:", len(matching_pages))

for item in matching_pages:
	print("Page:", item["page_number"], "| Headings:", len(item["headings"]))

print("Scan saved:", SCAN_FILE)


# ============================================================
# 5. LOAD PREVIOUS RESULTS
# ============================================================

previous_data = {}

if OUTPUT_JSON.exists():
	try:
		previous_data = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
	except (json.JSONDecodeError, OSError):
		raise SystemExit(f"Cannot read existing output safely: {OUTPUT_JSON}")

previous_notices = previous_data.get("notices", [])

results = []
seen_fingerprints = set()

total_notices = 0
total_review = 0


# ============================================================
# 6. PROCESS DETECTED NOTICE HEADINGS
# ============================================================

print("\n===== INTEGRATED NOTICE PIPELINE =====")
print("Newspaper pages:", len(doc))
print("Pages selected by heading scan:", len(matching_pages))

for page_info in matching_pages:
	page_number = page_info["page_number"]

	print(f"\n===== PROCESSING PAGE {page_number} =====")

	page = doc[page_number - 1]

	pix = page.get_pixmap(matrix=pymupdf.Matrix(CROP_SCALE, CROP_SCALE), alpha=False)

	image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()

	image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

	H, W = image.shape[:2]

	# Convert heading coordinates from scan resolution to crop resolution.
	scale = CROP_SCALE / SCAN_SCALE

	headings = sorted(page_info["headings"], key=lambda b: (b["y"], b["x"]))

	for column_number, heading in enumerate(headings, 1):
		x = int(heading["x"] * scale)
		y = int(heading["y"] * scale)
		w = int(heading["width"] * scale)

		x1 = max(0, x - 8)
		x2 = min(W, x + w + 8)
		y1 = max(0, y)

		column = image[y1:H, x1:x2]

		if column.size == 0:
			continue

		column_name = f"page_{page_number}_column_{column_number}.png"

		cv2.imwrite(str(COLUMN_DIR / column_name), column)

		print(f"\nColumn {column_number}")
		print("Detected heading:", heading["text"])

		gray = cv2.cvtColor(column, cv2.COLOR_BGR2GRAY)

		_, binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)

		CW = column.shape[1]
		CH = column.shape[0]

		horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, int(CW * 0.55)), 1))

		vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, int(CW * 0.15))))

		horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

		vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

		borders = cv2.bitwise_or(horizontal, vertical)

		borders = cv2.morphologyEx(borders, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

		contours, _ = cv2.findContours(borders, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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

		# If no boxed candidate exists, retain the entire detected
		# heading column for manual inspection.
		if not boxes:
			filename = f"page_{page_number}_column_{column_number}_unboxed"

			cv2.imwrite(str(REVIEW_DIR / f"{filename}.png"), column)

			review_text = pytesseract.image_to_string(column, lang=OCR_LANG, config="--oem 3 --psm 6").strip()

			(REVIEW_DIR / f"{filename}.txt").write_text(review_text, encoding="utf-8")

			total_review += 1

			print("  UNBOXED CANDIDATE SAVED FOR REVIEW:", filename)

			continue

		# ====================================================
		# 7. OCR AND CLASSIFY CANDIDATE BOXES
		# ====================================================

		for candidate_number, (bx, by, bw, bh) in enumerate(boxes, 1):
			left = max(0, bx - 3)
			right = min(CW, bx + bw + 3)
			top = max(0, by - 12)
			bottom = min(CH, by + bh + 3)

			crop = column[top:bottom, left:right]

			if crop.size == 0:
				continue

			crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

			heading_part = crop_gray[: min(150, crop_gray.shape[0]), :]

			enlarged_heading = cv2.resize(heading_part, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

			heading_text = pytesseract.image_to_string(
				enlarged_heading, lang=OCR_LANG, config="--oem 3 --psm 6"
			).strip()

			filename = f"page_{page_number}_column_{column_number}_candidate_{candidate_number}"

			is_notice = is_public_notice_heading(heading_text)

			if is_notice:
				enlarged = cv2.resize(crop_gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

				text = pytesseract.image_to_string(enlarged, lang=OCR_LANG, config="--oem 3 --psm 6").strip()

				if not text:
					print("  EMPTY OCR TEXT SKIPPED:", filename)
					continue

				fingerprint = deduplicator.fingerprint(text)

				if deduplicator.is_duplicate(text) or fingerprint in seen_fingerprints:
					print("  DUPLICATE SKIPPED:", filename)
					continue

				seen_fingerprints.add(fingerprint)

				cv2.imwrite(str(NOTICE_DIR / f"{filename}.png"), crop)

				(NOTICE_DIR / f"{filename}.txt").write_text(text, encoding="utf-8")

				results.append(
					{
						"newspaper": PDF.stem,
						"page_number": page_number,
						"column_number": column_number,
						"candidate_number": candidate_number,
						"heading": heading_text,
						"image": filename + ".png",
						"characters": len(text),
						"status": "needs_review",
						"text": text,
					}
				)

				total_notices += 1

				print("  PUBLIC NOTICE:", filename)

			else:
				cv2.imwrite(str(REVIEW_DIR / f"{filename}.png"), crop)

				(REVIEW_DIR / f"{filename}.txt").write_text(heading_text, encoding="utf-8")

				total_review += 1

				print("  NEEDS REVIEW:", filename)


# ============================================================
# 8. SAVE FINAL RESULTS
# ============================================================

all_notices = previous_notices + results

output_data = {
	"newspaper": PDF.stem,
	"total_pdf_pages": len(doc),
	"pages_selected_by_heading_scan": [p["page_number"] for p in matching_pages],
	"total_notice_candidates_recognized": len(all_notices),
	"new_notices_this_run": total_notices,
	"other_candidates_needing_review": total_review,
	"notices": all_notices,
}

OUTPUT_JSON.write_text(json.dumps(output_data, indent=4, ensure_ascii=False), encoding="utf-8")

# Register only after successfully saving the output.
for notice in results:
	deduplicator.register(notice["text"])

doc.close()


# ============================================================
# 9. FINAL SUMMARY
# ============================================================

print("\n================================")
print("INTEGRATED NOTICE PIPELINE COMPLETED")
print("================================")

print("Newspaper:", PDF.stem)
print("Total pages:", len(doc) if not doc.is_closed else "Completed")
print("Pages with headings:", len(matching_pages))
print("New notices recognized:", total_notices)
print("Candidates needing review:", total_review)
print("Output:", OUTPUT_JSON)
print("Cropped columns:", COLUMN_DIR)
print("Notice images:", NOTICE_DIR)
print("Review images:", REVIEW_DIR)
