import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytesseract
from PIL import Image

# ============================================================
# CONFIGURATION
# ============================================================

SITE_NAME = "ai-erpnext.local"

ALLOWED_PDF_ROOT = (
	Path.home() / "frappe-bench" / "sites" / SITE_NAME / "private" / "files" / "newspapers"
).resolve()


# ============================================================
# SAFE PDF PATH
# ============================================================


def safe_pdf_path(pdf_path):
	pdf_path = Path(pdf_path).expanduser().resolve()

	try:
		pdf_path.relative_to(ALLOWED_PDF_ROOT)
	except ValueError as exc:
		raise ValueError(f"PDF must be inside: {ALLOWED_PDF_ROOT}") from exc

	if not pdf_path.exists():
		raise FileNotFoundError(f"PDF not found: {pdf_path}")

	if pdf_path.suffix.lower() != ".pdf":
		raise ValueError("Input file must be a PDF.")

	return pdf_path


# ============================================================
# TEXT NORMALIZATION
# ============================================================


def normalize_text(text):
	text = str(text).upper()

	# Common OCR errors.
	text = text.replace("0", "O")
	text = text.replace("1", "I")
	text = text.replace("|", "I")

	text = re.sub(
		r"[^A-Z ]",
		" ",
		text,
	)

	text = re.sub(
		r"\s+",
		" ",
		text,
	)

	return text.strip()


def similarity(value, expected):
	value = normalize_text(value).replace(
		" ",
		"",
	)

	expected = normalize_text(expected).replace(
		" ",
		"",
	)

	if not value:
		return 0.0

	return SequenceMatcher(
		None,
		value,
		expected,
	).ratio()


# ============================================================
# RENDER ONE PDF PAGE
# ============================================================


def render_page(
	pdf_path,
	page_number,
):
	document = pymupdf.open(pdf_path)

	total_pages = len(document)

	if page_number < 1 or page_number > total_pages:
		document.close()

		raise ValueError(f"Page must be between 1 and {total_pages}")

	page = document[page_number - 1]

	# High-resolution image for newspaper OCR.
	matrix = pymupdf.Matrix(
		3.0,
		3.0,
	)

	pixmap = page.get_pixmap(
		matrix=matrix,
		alpha=False,
	)

	image = Image.frombytes(
		"RGB",
		(
			pixmap.width,
			pixmap.height,
		),
		pixmap.samples,
	)

	document.close()

	return image


# ============================================================
# GET OCR WORDS
# ============================================================


def get_ocr_words(image):
	data = pytesseract.image_to_data(
		image,
		output_type=pytesseract.Output.DICT,
		config="--oem 3 --psm 11",
	)

	words = []

	total = len(data["text"])

	for index in range(total):
		text = str(data["text"][index]).strip()

		if not text:
			continue

		try:
			confidence = float(data["conf"][index])
		except (
			ValueError,
			TypeError,
		):
			confidence = -1

		if confidence < 10:
			continue

		left = int(data["left"][index])

		top = int(data["top"][index])

		width = int(data["width"][index])

		height = int(data["height"][index])

		words.append(
			{
				"text": text,
				"left": left,
				"top": top,
				"right": (left + width),
				"bottom": (top + height),
				"center_x": (left + width / 2),
				"center_y": (top + height / 2),
				"confidence": confidence,
			}
		)

	return words


# ============================================================
# FIND APPROXIMATE NOTICE ROW
# ============================================================


def find_heading_anchor_y(words):
	"""
	This is only diagnostic now.

	Banner detection itself scans the full page.
	"""

	first_words = [
		"PUBLIC",
		"COURT",
		"LEGAL",
		"AUCTION",
	]

	anchors = []

	for first in words:
		first_type = None

		for expected in first_words:
			if (
				similarity(
					first["text"],
					expected,
				)
				>= 0.80
			):
				first_type = expected
				break

		if first_type is None:
			continue

		for second in words:
			if second["left"] <= first["left"]:
				continue

			horizontal_gap = second["left"] - first["right"]

			vertical_difference = abs(second["center_y"] - first["center_y"])

			if horizontal_gap > 250:
				continue

			if vertical_difference > 70:
				continue

			notice_score = max(
				similarity(
					second["text"],
					"NOTICE",
				),
				similarity(
					second["text"],
					"NOTICES",
				),
			)

			if notice_score < 0.80:
				continue

			anchors.append((first["center_y"] + second["center_y"]) / 2)

	if not anchors:
		return None

	anchors.sort()

	return anchors[len(anchors) // 2]


# ============================================================
# DETECT PURPLE NOTICE BANNERS FROM FULL PAGE
# ============================================================


def detect_banner_rectangles(
	image,
	output_folder,
):
	"""
	Detect physical coloured banners such as:

	COURT NOTICES
	PUBLIC NOTICES
	PUBLIC NOTICES
	PUBLIC NOTICES

	Important:
	We search the FULL PAGE.
	"""

	rgb = np.array(image)

	bgr = cv2.cvtColor(
		rgb,
		cv2.COLOR_RGB2BGR,
	)

	page_width = bgr.shape[1]

	# Save full page used for detection.
	cv2.imwrite(
		str(output_folder / "banner_search_page.png"),
		bgr,
	)

	# ========================================================
	# HSV CONVERSION
	# ========================================================

	hsv = cv2.cvtColor(
		bgr,
		cv2.COLOR_BGR2HSV,
	)

	# --------------------------------------------------------
	# PURPLE COLOR RANGE
	# --------------------------------------------------------
	#
	# OpenCV hue:
	# 0 - 179
	#
	# Purple/magenta usually falls roughly
	# between 120 and 175.
	# --------------------------------------------------------

	lower_purple = np.array(
		[
			115,
			45,
			35,
		],
		dtype=np.uint8,
	)

	upper_purple = np.array(
		[
			179,
			255,
			255,
		],
		dtype=np.uint8,
	)

	mask = cv2.inRange(
		hsv,
		lower_purple,
		upper_purple,
	)

	# ========================================================
	# CLEAN / JOIN MASK
	# ========================================================

	close_kernel = cv2.getStructuringElement(
		cv2.MORPH_RECT,
		(
			21,
			7,
		),
	)

	mask = cv2.morphologyEx(
		mask,
		cv2.MORPH_CLOSE,
		close_kernel,
		iterations=2,
	)

	open_kernel = cv2.getStructuringElement(
		cv2.MORPH_RECT,
		(
			5,
			3,
		),
	)

	mask = cv2.morphologyEx(
		mask,
		cv2.MORPH_OPEN,
		open_kernel,
		iterations=1,
	)

	# Save debug mask.
	cv2.imwrite(
		str(output_folder / "banner_detection_mask.png"),
		mask,
	)

	# ========================================================
	# FIND CONTOURS
	# ========================================================

	contours, _ = cv2.findContours(
		mask,
		cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE,
	)

	candidates = []

	minimum_width = max(
		100,
		int(page_width * 0.07),
	)

	maximum_width = int(page_width * 0.30)

	for contour in contours:
		x, y, width, height = cv2.boundingRect(contour)

		contour_area = cv2.contourArea(contour)

		box_area = width * height

		if box_area <= 0:
			continue

		fill_ratio = contour_area / box_area

		# ----------------------------------------------------
		# FILTER BY SIZE
		# ----------------------------------------------------

		if width < minimum_width:
			continue

		if width > maximum_width:
			continue

		if height < 20:
			continue

		if height > 180:
			continue

		aspect_ratio = width / height

		# Banner should be horizontally long.
		if aspect_ratio < 2.0:
			continue

		# Banner should contain sufficient purple pixels.
		if fill_ratio < 0.25:
			continue

		candidates.append(
			{
				"left": x,
				"top": y,
				"right": (x + width),
				"bottom": (y + height),
				"width": width,
				"height": height,
				"center_x": (x + width / 2),
				"center_y": (y + height / 2),
				"area": box_area,
				"fill_ratio": round(
					fill_ratio,
					3,
				),
			}
		)

	print()
	print(f"Purple rectangle candidates: {len(candidates)}")

	# ========================================================
	# GROUP CANDIDATES INTO ROWS
	# ========================================================

	candidates.sort(
		key=lambda item: (
			item["center_y"],
			item["center_x"],
		)
	)

	rows = []

	for candidate in candidates:
		best_row = None
		best_difference = None

		for row in rows:
			average_y = sum(item["center_y"] for item in row) / len(row)

			difference = abs(candidate["center_y"] - average_y)

			if difference <= 100:
				if best_difference is None or difference < best_difference:
					best_row = row
					best_difference = difference

		if best_row is None:
			rows.append([candidate])

		else:
			best_row.append(candidate)

	print(f"Purple rows detected: {len(rows)}")

	if not rows:
		return []

	# ========================================================
	# SELECT BEST NOTICE BANNER ROW
	# ========================================================
	#
	# We prefer:
	# 1. Row containing the most rectangles
	# 2. Total horizontal width
	#
	# This should select:
	#
	# COURT NOTICES
	# PUBLIC NOTICES
	# PUBLIC NOTICES
	# PUBLIC NOTICES
	# ========================================================

	rows.sort(
		key=lambda row: (
			len(row),
			sum(item["width"] for item in row),
		),
		reverse=True,
	)

	best_row = rows[0]

	# ========================================================
	# REMOVE DUPLICATES / OVERLAPS
	# ========================================================

	best_row.sort(key=lambda item: item["center_x"])

	cleaned = []

	for candidate in best_row:
		duplicate = False

		for existing in cleaned:
			x_difference = abs(candidate["center_x"] - existing["center_x"])

			y_difference = abs(candidate["center_y"] - existing["center_y"])

			if x_difference < 80 and y_difference < 60:
				duplicate = True

				if candidate["area"] > existing["area"]:
					existing.update(candidate)

				break

		if not duplicate:
			cleaned.append(candidate)

	cleaned.sort(key=lambda item: item["center_x"])

	print(f"Banners in selected row: {len(cleaned)}")

	return cleaned


# ============================================================
# OCR ONE PURPLE BANNER
# ============================================================


def detect_banner_type(
	image,
	banner,
):
	padding_x = 15
	padding_y = 10

	left = max(
		0,
		banner["left"] - padding_x,
	)

	top = max(
		0,
		banner["top"] - padding_y,
	)

	right = min(
		image.width,
		banner["right"] + padding_x,
	)

	bottom = min(
		image.height,
		banner["bottom"] + padding_y,
	)

	crop = image.crop(
		(
			left,
			top,
			right,
			bottom,
		)
	)

	# Upscale banner OCR slightly.
	crop = crop.resize(
		(
			crop.width * 2,
			crop.height * 2,
		)
	)

	text = pytesseract.image_to_string(
		crop,
		lang="eng",
		config="--oem 3 --psm 7",
	)

	normalized = normalize_text(text)

	if "COURT" in normalized:
		return (
			"COURT NOTICE",
			text.strip(),
		)

	if "PUBLIC" in normalized:
		return (
			"PUBLIC NOTICE",
			text.strip(),
		)

	if "LEGAL" in normalized:
		return (
			"LEGAL NOTICE",
			text.strip(),
		)

	if "AUCTION" in normalized:
		return (
			"AUCTION NOTICE",
			text.strip(),
		)

	if "SALE" in normalized:
		return (
			"SALE NOTICE",
			text.strip(),
		)

	return (
		"UNKNOWN NOTICE",
		text.strip(),
	)


# ============================================================
# BUILD COLUMNS FROM BANNER POSITIONS
# ============================================================


def build_columns_from_banners(
	banners,
	page_width,
	page_height,
):
	if not banners:
		return []

	banners = sorted(banners, key=lambda item: item["center_x"])

	centers = [banner["center_x"] for banner in banners]

	# Determine normal distance between columns.
	spacings = []

	for index in range(len(centers) - 1):
		spacing = centers[index + 1] - centers[index]

		if spacing > 50:
			spacings.append(spacing)

	if spacings:
		spacings.sort()

		typical_spacing = spacings[len(spacings) // 2]

	else:
		typical_spacing = page_width * 0.18

	columns = []

	for index, banner in enumerate(banners):
		center = banner["center_x"]

		# ====================================================
		# LEFT BOUNDARY
		# ====================================================

		if index == 0:
			left = int(center - typical_spacing / 2)

		else:
			left = int((centers[index - 1] + center) / 2)

		# ====================================================
		# RIGHT BOUNDARY
		# ====================================================

		if index == len(banners) - 1:
			right = int(center + typical_spacing / 2)

		else:
			right = int((center + centers[index + 1]) / 2)

		left = max(
			0,
			left,
		)

		right = min(
			page_width,
			right,
		)

		# Start crop slightly above banner.
		top = max(
			0,
			banner["top"] - 5,
		)

		# For first version, crop to page bottom.
		bottom = page_height

		columns.append(
			{
				"column_number": (index + 1),
				"banner": banner,
				"bbox": {
					"left": (left + 3),
					"top": top,
					"right": (right - 3),
					"bottom": bottom,
				},
			}
		)

	return columns


# ============================================================
# OCR INDIVIDUAL NOTICE COLUMN
# ============================================================


def ocr_notice_column(crop):
	image_array = np.array(crop)

	gray = cv2.cvtColor(
		image_array,
		cv2.COLOR_RGB2GRAY,
	)

	# Increase contrast slightly.
	gray = cv2.convertScaleAbs(
		gray,
		alpha=1.25,
		beta=0,
	)

	pil_gray = Image.fromarray(gray)

	# First try PSM 6 because the crop
	# should now contain one notice column.
	text = pytesseract.image_to_string(
		pil_gray,
		lang="eng",
		config="--oem 3 --psm 6",
	)

	cleaned_lines = []

	for line in text.splitlines():
		line = line.strip()

		if not line:
			continue

		cleaned_lines.append(line)

	return "\n".join(cleaned_lines)


# ============================================================
# CLASSIFY NOTICE FROM TEXT
# ============================================================


def classify_notice(
	text,
	banner_type,
):
	normalized = normalize_text(text[:1500])

	if "COURT NOTICE" in normalized or "COURT NOTICES" in normalized:
		return "COURT NOTICE"

	if "PUBLIC NOTICE" in normalized or "PUBLIC NOTICES" in normalized:
		return "PUBLIC NOTICE"

	if "LEGAL NOTICE" in normalized or "LEGAL NOTICES" in normalized:
		return "LEGAL NOTICE"

	if "AUCTION NOTICE" in normalized or "AUCTION NOTICES" in normalized:
		return "AUCTION NOTICE"

	if "SALE NOTICE" in normalized or "SALE NOTICES" in normalized:
		return "SALE NOTICE"

	return banner_type


# ============================================================
# SAVE DEBUG IMAGE
# ============================================================


def save_debug_regions(
	image,
	banners,
	columns,
	output_path,
):
	bgr = cv2.cvtColor(
		np.array(image),
		cv2.COLOR_RGB2BGR,
	)

	# GREEN = purple banner detected.
	for index, banner in enumerate(
		banners,
		start=1,
	):
		cv2.rectangle(
			bgr,
			(
				int(banner["left"]),
				int(banner["top"]),
			),
			(
				int(banner["right"]),
				int(banner["bottom"]),
			),
			(
				0,
				255,
				0,
			),
			4,
		)

		cv2.putText(
			bgr,
			f"BANNER {index}",
			(
				int(banner["left"]),
				max(
					25,
					int(banner["top"]) - 10,
				),
			),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.55,
			(
				0,
				255,
				0,
			),
			2,
		)

	# RED = final notice crop.
	for index, column in enumerate(
		columns,
		start=1,
	):
		bbox = column["bbox"]

		cv2.rectangle(
			bgr,
			(
				bbox["left"],
				bbox["top"],
			),
			(
				bbox["right"],
				bbox["bottom"],
			),
			(
				0,
				0,
				255,
			),
			4,
		)

		cv2.putText(
			bgr,
			f"NOTICE {index}",
			(
				bbox["left"] + 5,
				bbox["top"] + 25,
			),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.55,
			(
				0,
				0,
				255,
			),
			2,
		)

	cv2.imwrite(
		str(output_path),
		bgr,
	)


# ============================================================
# MAIN SPLITTER
# ============================================================


def split_notice_blocks(
	pdf_path,
	page_number,
):
	pdf_path = safe_pdf_path(pdf_path)

	image = render_page(
		pdf_path,
		page_number,
	)

	output_folder = (pdf_path.parent / "notice_blocks" / f"page_{page_number:03d}").resolve()

	try:
		output_folder.relative_to(ALLOWED_PDF_ROOT)

	except ValueError as exc:
		raise ValueError("Output folder is outside allowed newspaper directory.") from exc

	output_folder.mkdir(
		parents=True,
		exist_ok=True,
	)

	# ========================================================
	# SAVE RENDERED PAGE
	# ========================================================

	rendered_page_path = output_folder / "rendered_page.png"

	image.save(rendered_page_path)

	print(f"Rendered image size: {image.width} x {image.height}")

	# ========================================================
	# OPTIONAL OCR DIAGNOSTIC
	# ========================================================

	print()
	print("Checking notice heading position...")

	words = get_ocr_words(image)

	anchor_y = find_heading_anchor_y(words)

	if anchor_y is None:
		print("OCR heading anchor not found.")

	else:
		print(f"OCR heading anchor Y: {int(anchor_y)}")

	# ========================================================
	# PHYSICAL BANNER DETECTION
	# ========================================================

	print()
	print("=" * 60)

	print("PHYSICAL BANNER DETECTION")

	print("=" * 60)

	banners = detect_banner_rectangles(
		image,
		output_folder,
	)

	print()
	print(f"Physical banners detected: {len(banners)}")

	print()

	# ========================================================
	# OCR / CLASSIFY EACH BANNER
	# ========================================================

	for index, banner in enumerate(
		banners,
		start=1,
	):
		(
			banner_type,
			banner_text,
		) = detect_banner_type(
			image,
			banner,
		)

		banner["banner_type"] = banner_type

		banner["ocr_text"] = banner_text

		print(f"Banner {index}")

		print(f"  Type: {banner_type}")

		print(f"  OCR: {banner_text}")

		print(f"  BBox: {banner['left']}, {banner['top']}, {banner['right']}, {banner['bottom']}")

		print(f"  Fill ratio: {banner['fill_ratio']}")

		print()

	# Save detected banners.
	detected_banners_path = output_folder / "detected_banners.json"

	detected_banners_path.write_text(
		json.dumps(
			banners,
			indent=2,
			ensure_ascii=False,
		),
		encoding="utf-8",
	)

	# ========================================================
	# BUILD PHYSICAL NOTICE COLUMNS
	# ========================================================

	columns = build_columns_from_banners(
		banners,
		image.width,
		image.height,
	)

	print("=" * 60)

	print("INDIVIDUAL NOTICE COLUMNS")

	print("=" * 60)

	print()

	print(f"Notice columns created: {len(columns)}")

	print()

	# ========================================================
	# DEBUG IMAGE
	# ========================================================

	debug_path = output_folder / "detected_notice_regions.png"

	save_debug_regions(
		image,
		banners,
		columns,
		debug_path,
	)

	# ========================================================
	# OCR EACH COLUMN
	# ========================================================

	notices = []

	for index, column in enumerate(
		columns,
		start=1,
	):
		bbox = column["bbox"]

		banner = column["banner"]

		print(f"Processing Notice {index}")

		print(f"BBox: {bbox['left']}, {bbox['top']}, {bbox['right']}, {bbox['bottom']}")

		crop = image.crop(
			(
				bbox["left"],
				bbox["top"],
				bbox["right"],
				bbox["bottom"],
			)
		)

		crop_name = f"notice_{index:02d}.png"

		crop_path = output_folder / crop_name

		crop.save(crop_path)

		notice_text = ocr_notice_column(crop)

		notice_type = classify_notice(
			notice_text,
			banner.get(
				"banner_type",
				"UNKNOWN NOTICE",
			),
		)

		text_name = f"notice_{index:02d}.txt"

		text_path = output_folder / text_name

		text_path.write_text(
			notice_text,
			encoding="utf-8",
		)

		print(f"Type: {notice_type}")

		print(f"Saved: {crop_name}")

		print("-" * 50)

		notices.append(
			{
				"page_number": (page_number),
				"notice_number": (index),
				"notice_type": (notice_type),
				"banner_text": (
					banner.get(
						"ocr_text",
						"",
					)
				),
				"bbox": bbox,
				"crop_file": (crop_name),
				"text_file": (text_name),
				"raw_text": (notice_text),
			}
		)

	# ========================================================
	# FINAL JSON
	# ========================================================

	result = {
		"page_number": (page_number),
		"total_banners": (len(banners)),
		"total_notices": (len(notices)),
		"notices": (notices),
	}

	result_path = output_folder / "notice_blocks.json"

	result_path.write_text(
		json.dumps(
			result,
			indent=2,
			ensure_ascii=False,
		),
		encoding="utf-8",
	)

	return (
		result,
		output_folder,
	)


# ============================================================
# COMMAND LINE
# ============================================================


def main():
	parser = argparse.ArgumentParser(
		description=("Detect physical newspaper notice columns using coloured section banners.")
	)

	parser.add_argument(
		"--pdf",
		required=True,
		help=("Full PDF path."),
	)

	parser.add_argument(
		"--page",
		required=True,
		type=int,
		help=("1-based PDF page number."),
	)

	args = parser.parse_args()

	print()

	print("=" * 60)

	print("BANNER-BASED NOTICE BLOCK SPLITTER")

	print("=" * 60)

	try:
		result, output_folder = split_notice_blocks(
			args.pdf,
			args.page,
		)

	except Exception as exc:
		print()
		print("ERROR:")

		print(str(exc))

		raise

	print()

	print("=" * 60)

	print("SPLITTING COMPLETE")

	print("=" * 60)

	print()

	print(f"Page: {result['page_number']}")

	print(f"Banners detected: {result['total_banners']}")

	print(f"Individual notices: {result['total_notices']}")

	print()

	for notice in result["notices"]:
		print(f"Notice {notice['notice_number']} → {notice['notice_type']}")

	print()

	print("Output folder:")

	print(output_folder)

	print()

	print("Check these files:")

	print("1. banner_detection_mask.png")

	print("2. detected_notice_regions.png")

	print("3. notice_01.png, notice_02.png, ...")

	print()

	print("Green = detected coloured banner")

	print("Red = final notice column")


if __name__ == "__main__":
	main()
