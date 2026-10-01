import json
import os

from pypdf import PdfReader

# ============================================================
# SETTINGS
# ============================================================

MIN_CHARACTERS = 80
MIN_WORDS = 10


# Strong notice words
PRIMARY_NOTICE_KEYWORDS = [
	"public notice",
	"legal notice",
	"estate notice",
]


# Property-related words
PROPERTY_KEYWORDS = [
	"survey no",
	"survey number",
	"survey",
	"tp no",
	"tp number",
	"town planning",
	"property",
	"final plot",
	"plot no",
	"plot number",
	"village",
	"owner",
	"land",
	"title",
	"sale deed",
]


ALL_KEYWORDS = PRIMARY_NOTICE_KEYWORDS + PROPERTY_KEYWORDS


# ============================================================
# CHECK WHETHER DIRECTLY EXTRACTED TEXT IS USABLE
# ============================================================


def check_text_quality(text):
	cleaned_text = " ".join(text.split())

	# No selectable text
	if not cleaned_text:
		return ("needs_ocr", "No selectable text found")

	# Sometimes PDF contains only page number
	if cleaned_text.isdigit():
		return ("needs_ocr", "Only page number or numeric text was extracted")

	character_count = len(cleaned_text)

	word_count = len(cleaned_text.split())

	# Very small amount of selectable text
	if character_count < MIN_CHARACTERS:
		return ("needs_ocr", "Too little selectable text was extracted")

	if word_count < MIN_WORDS:
		return ("needs_ocr", "Extracted text is too short to be useful")

	return ("usable", None)


# ============================================================
# FIND KEYWORDS
# ============================================================


def find_keywords(text):
	text_lower = text.lower()

	primary_found = []
	property_found = []

	for keyword in PRIMARY_NOTICE_KEYWORDS:
		if keyword.lower() in text_lower:
			primary_found.append(keyword)

	for keyword in PROPERTY_KEYWORDS:
		if keyword.lower() in text_lower:
			property_found.append(keyword)

	return (primary_found, property_found)


# ============================================================
# DECIDE WHETHER PAGE IS A NOTICE CANDIDATE
# ============================================================


def is_notice_candidate(primary_keywords, property_keywords):
	# PUBLIC NOTICE / LEGAL NOTICE is strong evidence
	if primary_keywords:
		return True

	# Otherwise require at least two
	# property-related indicators
	if len(property_keywords) >= 2:
		return True

	return False


# ============================================================
# EXTRACT ONLY RELEVANT NOTICE AREA
# ============================================================


def extract_notice_context(text):
	lines = text.splitlines()

	selected_lines = []

	selected_indexes = set()

	for index, line in enumerate(lines):
		line_lower = line.lower()

		keyword_found = any(keyword.lower() in line_lower for keyword in ALL_KEYWORDS)

		if not keyword_found:
			continue

		# Keep 2 lines before keyword,
		# keyword line,
		# and 2 lines after.
		start = max(0, index - 2)

		end = min(len(lines), index + 3)

		for selected_index in range(start, end):
			selected_indexes.add(selected_index)

	# Keep original order
	for index in sorted(selected_indexes):
		line = lines[index].strip()

		if line:
			selected_lines.append(line)

	return "\n".join(selected_lines)


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================


def extract_pdf_text(pdf_path):
	print("\n======================================")

	print("ESTATE NOTICE - PDF TEXT EXTRACTION")

	print("======================================")

	# --------------------------------------------------------
	# CLEAN INPUT PATH
	# --------------------------------------------------------

	pdf_path = os.path.abspath(os.path.expanduser(pdf_path))

	# --------------------------------------------------------
	# CHECK FILE EXISTS
	# --------------------------------------------------------

	if not os.path.exists(pdf_path):
		print("\nERROR: PDF not found")

		print(pdf_path)

		return {"status": "failed", "reason": "file_not_found"}

	# --------------------------------------------------------
	# CHECK PDF EXTENSION
	# --------------------------------------------------------

	if not pdf_path.lower().endswith(".pdf"):
		print("\nERROR: Selected file is not PDF")

		return {"status": "failed", "reason": "not_a_pdf"}

	print("\nPDF found:")

	print(pdf_path)

	# --------------------------------------------------------
	# OPEN PDF
	# --------------------------------------------------------

	try:
		reader = PdfReader(pdf_path)

	except Exception as error:
		print("\nERROR: Could not open PDF")

		print(error)

		return {"status": "failed", "reason": "pdf_open_failed", "error": str(error)}

	total_pages = len(reader.pages)

	print("\nTotal PDF pages:", total_pages)

	if total_pages == 0:
		return {"status": "failed", "reason": "pdf_has_no_pages"}

	# ========================================================
	# CREATE OUTPUT FOLDERS
	# ========================================================

	pdf_folder = os.path.dirname(pdf_path)

	output_folder = os.path.join(pdf_folder, "direct_extraction")

	page_text_folder = os.path.join(output_folder, "pages")

	notice_folder = os.path.join(output_folder, "notice_candidates")

	os.makedirs(page_text_folder, exist_ok=True)

	os.makedirs(notice_folder, exist_ok=True)

	print("\nOutput folder:")

	print(output_folder)

	# ========================================================
	# RESULT STORAGE
	# ========================================================

	all_pages = []

	ocr_required_pages = []

	notice_candidate_pages = []

	usable_pages = 0

	total_characters = 0

	# ========================================================
	# PROCESS EVERY PAGE
	# ========================================================

	for page_number, page in enumerate(reader.pages, start=1):
		print("\n--------------------------------------")

		print(f"Processing page {page_number}/{total_pages}")

		extraction_error = None

		# ----------------------------------------------------
		# DIRECT TEXT EXTRACTION
		# ----------------------------------------------------

		try:
			text = page.extract_text() or ""

			text = text.strip()

		except Exception as error:
			text = ""

			extraction_error = str(error)

		character_count = len(text)

		total_characters += character_count

		# ----------------------------------------------------
		# CHECK TEXT QUALITY
		# ----------------------------------------------------

		if extraction_error:
			status = "needs_ocr"

			reason = "Direct extraction failed: " + extraction_error

		else:
			status, reason = check_text_quality(text)

		# ====================================================
		# SAVE COMPLETE PAGE TEXT
		# ====================================================

		page_text_path = os.path.join(page_text_folder, f"page_{page_number:03d}.txt")

		with open(page_text_path, "w", encoding="utf-8") as file:
			file.write(text)

		# ====================================================
		# KEYWORD / NOTICE CHECK
		# ====================================================

		primary_keywords = []

		property_keywords = []

		notice_candidate = False

		notice_text = ""

		notice_text_path = None

		# Only search keywords if
		# direct text is actually usable
		if status == "usable":
			(primary_keywords, property_keywords) = find_keywords(text)

			notice_candidate = is_notice_candidate(primary_keywords, property_keywords)

			# ------------------------------------------------
			# EXTRACT ONLY NOTICE-RELATED TEXT
			# ------------------------------------------------

			if notice_candidate:
				notice_text = extract_notice_context(text)

				notice_text_path = os.path.join(notice_folder, f"page_{page_number:03d}.txt")

				with open(notice_text_path, "w", encoding="utf-8") as file:
					file.write(notice_text)

				notice_candidate_pages.append(
					{
						"page_number": page_number,
						"primary_keywords": primary_keywords,
						"property_keywords": property_keywords,
						"text": notice_text,
						"text_file": notice_text_path,
					}
				)

		# ====================================================
		# SAVE PAGE RESULT
		# ====================================================

		page_result = {
			"page_number": page_number,
			"method": "direct",
			"status": status,
			"character_count": character_count,
			"text": text,
			"text_file": page_text_path,
			"reason": reason,
			"notice_candidate": notice_candidate,
			"primary_keywords": primary_keywords,
			"property_keywords": property_keywords,
			"notice_text": notice_text,
			"notice_text_file": notice_text_path,
		}

		all_pages.append(page_result)

		# ====================================================
		# PRINT RESULT
		# ====================================================

		if status == "needs_ocr":
			ocr_required_pages.append(
				{"page_number": page_number, "reason": reason, "character_count": character_count}
			)

			print("Result: OCR REQUIRED")

			print("Reason:", reason)

		else:
			usable_pages += 1

			print("Result: DIRECT TEXT USABLE")

			print("Characters extracted:", character_count)

			if notice_candidate:
				print("NOTICE CANDIDATE FOUND")

				all_found = primary_keywords + property_keywords

				print("Keywords:", ", ".join(all_found))

			else:
				print("No notice candidate found")

	# ========================================================
	# SAVE direct_text.json
	# ========================================================

	direct_result = {
		"status": "success",
		"pdf_path": pdf_path,
		"total_pages": total_pages,
		"usable_direct_pages": usable_pages,
		"ocr_required_pages": len(ocr_required_pages),
		"notice_candidate_pages": len(notice_candidate_pages),
		"total_characters": total_characters,
		"pages": all_pages,
	}

	direct_json_path = os.path.join(output_folder, "direct_text.json")

	with open(direct_json_path, "w", encoding="utf-8") as file:
		json.dump(direct_result, file, indent=4, ensure_ascii=False)

	# ========================================================
	# SAVE ocr_required_pages.json
	# ========================================================

	ocr_result = {
		"pdf_path": pdf_path,
		"total_pages": total_pages,
		"ocr_required_count": len(ocr_required_pages),
		"pages": ocr_required_pages,
	}

	ocr_json_path = os.path.join(output_folder, "ocr_required_pages.json")

	with open(ocr_json_path, "w", encoding="utf-8") as file:
		json.dump(ocr_result, file, indent=4, ensure_ascii=False)

	# ========================================================
	# SAVE notice_candidates.json
	# ========================================================

	notice_result = {
		"pdf_path": pdf_path,
		"candidate_count": len(notice_candidate_pages),
		"pages": notice_candidate_pages,
	}

	notice_json_path = os.path.join(output_folder, "notice_candidates.json")

	with open(notice_json_path, "w", encoding="utf-8") as file:
		json.dump(notice_result, file, indent=4, ensure_ascii=False)

	# ========================================================
	# FINAL SUMMARY
	# ========================================================

	print("\n======================================")

	print("EXTRACTION FINISHED")

	print("======================================")

	print("\nTotal pages:", total_pages)

	print("Usable direct-text pages:", usable_pages)

	print("OCR required pages:", len(ocr_required_pages))

	print("Notice candidate pages:", len(notice_candidate_pages))

	# --------------------------------------------------------
	# OCR PAGE NUMBERS
	# --------------------------------------------------------

	if ocr_required_pages:
		print("\nPages to send to Janvi:")

		print(", ".join(str(page["page_number"]) for page in ocr_required_pages))

	# --------------------------------------------------------
	# NOTICE PAGE NUMBERS
	# --------------------------------------------------------

	if notice_candidate_pages:
		print("\nPossible estate/public notice pages:")

		print(", ".join(str(page["page_number"]) for page in notice_candidate_pages))

	print("\nDirect text JSON:")

	print(direct_json_path)

	print("\nOCR required JSON:")

	print(ocr_json_path)

	print("\nNotice candidates JSON:")

	print(notice_json_path)

	return {
		"status": "success",
		"total_pages": total_pages,
		"usable_direct_pages": usable_pages,
		"ocr_required_pages": len(ocr_required_pages),
		"notice_candidate_pages": len(notice_candidate_pages),
	}


# ============================================================
# RUN FROM TERMINAL
# ============================================================

if __name__ == "__main__":
	print("\nPaste the full newspaper PDF path.")

	pdf_path = input("PDF path: ").strip()

	extract_pdf_text(pdf_path)
