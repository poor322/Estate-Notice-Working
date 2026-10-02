import json
import re
from pathlib import Path

from pypdf import PdfReader

SITE_NAME = "site1.local"

MIN_CHARACTERS = 80
MIN_WORDS = 10


PRIMARY_NOTICE_KEYWORDS = [
	"public notice",
	"legal notice",
	"estate notice",
]


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


def get_private_files_root():
	return (Path.home() / "frappe-bench" / "sites" / SITE_NAME / "private" / "files").resolve()


def get_allowed_newspaper_root():
	return (get_private_files_root() / "newspapers").resolve()


def get_output_root():
	return (get_private_files_root() / "estate_notice").resolve()


def ensure_within_root(
	path,
	root,
):
	resolved_path = Path(path).resolve()

	resolved_root = Path(root).resolve()

	try:
		resolved_path.relative_to(resolved_root)

	except ValueError as error:
		raise ValueError(f"Path is outside the allowed directory: {resolved_root}") from error

	return resolved_path


def validate_pdf_path(
	pdf_path,
):
	allowed_root = get_allowed_newspaper_root()

	if not allowed_root.exists():
		raise FileNotFoundError(f"Newspaper folder does not exist: {allowed_root}")

	requested_pdf = Path(pdf_path).expanduser().resolve()

	ensure_within_root(
		requested_pdf,
		allowed_root,
	)

	if requested_pdf.suffix.lower() != ".pdf":
		raise ValueError("Only PDF files are allowed")

	if not requested_pdf.is_file():
		raise FileNotFoundError(f"PDF file does not exist: {requested_pdf}")

	return requested_pdf


def safe_name(
	value,
):
	cleaned = re.sub(
		r"[^A-Za-z0-9._-]+",
		"_",
		value,
	).strip("._")

	if not cleaned:
		return "newspaper"

	return cleaned[:120]


def safe_output_path(
	base_dir,
	relative_path,
):
	base_dir = Path(base_dir).resolve()

	target_path = (base_dir / relative_path).resolve()

	ensure_within_root(
		target_path,
		base_dir,
	)

	return target_path


def safe_write_text(
	base_dir,
	relative_path,
	content,
):
	target_path = safe_output_path(
		base_dir,
		relative_path,
	)

	target_path.parent.mkdir(
		parents=True,
		exist_ok=True,
	)

	target_path.write_text(
		content,
		encoding="utf-8",
	)

	return target_path


def safe_write_json(
	base_dir,
	relative_path,
	data,
):
	json_text = json.dumps(
		data,
		indent=4,
		ensure_ascii=False,
	)

	return safe_write_text(
		base_dir,
		relative_path,
		json_text,
	)


def check_text_quality(
	text,
):
	cleaned_text = " ".join(text.split())

	if not cleaned_text:
		return (
			"needs_ocr",
			"No selectable text found",
		)

	if cleaned_text.isdigit():
		return (
			"needs_ocr",
			"Only page number or numeric text was extracted",
		)

	character_count = len(cleaned_text)

	word_count = len(cleaned_text.split())

	if character_count < MIN_CHARACTERS:
		return (
			"needs_ocr",
			"Too little selectable text was extracted",
		)

	if word_count < MIN_WORDS:
		return (
			"needs_ocr",
			"Extracted text is too short to be useful",
		)

	return (
		"usable",
		None,
	)


def find_keywords(
	text,
):
	text_lower = text.lower()

	primary_found = [keyword for keyword in PRIMARY_NOTICE_KEYWORDS if keyword.lower() in text_lower]

	property_found = [keyword for keyword in PROPERTY_KEYWORDS if keyword.lower() in text_lower]

	return (
		primary_found,
		property_found,
	)


def is_notice_candidate(
	primary_keywords,
	property_keywords,
):
	if primary_keywords:
		return True

	return len(property_keywords) >= 2


def extract_notice_context(
	text,
):
	lines = text.splitlines()

	selected_indexes = set()

	for index, line in enumerate(lines):
		line_lower = line.lower()

		keyword_found = any(keyword.lower() in line_lower for keyword in ALL_KEYWORDS)

		if not keyword_found:
			continue

		start = max(
			0,
			index - 2,
		)

		end = min(
			len(lines),
			index + 3,
		)

		selected_indexes.update(
			range(
				start,
				end,
			)
		)

	selected_lines = [lines[index].strip() for index in sorted(selected_indexes) if lines[index].strip()]

	return "\n".join(selected_lines)


def extract_pdf_text(
	pdf_path,
):
	print("\n======================================")

	print("ESTATE NOTICE - PDF TEXT EXTRACTION")

	print("======================================")

	try:
		pdf_path = validate_pdf_path(pdf_path)

	except (
		ValueError,
		FileNotFoundError,
	) as error:
		print("\nERROR:")

		print(error)

		return {
			"status": "failed",
			"reason": str(error),
		}

	print("\nPDF found:")

	print(pdf_path)

	try:
		reader = PdfReader(str(pdf_path))

	except Exception as error:
		print("\nERROR: Could not open PDF")

		print(error)

		return {
			"status": "failed",
			"reason": "pdf_open_failed",
			"error": str(error),
		}

	total_pages = len(reader.pages)

	if total_pages == 0:
		return {
			"status": "failed",
			"reason": "pdf_has_no_pages",
		}

	print(
		"\nTotal PDF pages:",
		total_pages,
	)

	output_root = get_output_root()

	newspaper_name = safe_name(pdf_path.stem)

	output_folder = (output_root / "direct_extraction" / newspaper_name).resolve()

	ensure_within_root(
		output_folder,
		output_root,
	)

	output_folder.mkdir(
		parents=True,
		exist_ok=True,
	)

	print("\nOutput folder:")

	print(output_folder)

	all_pages = []

	ocr_required_pages = []

	notice_candidate_pages = []

	usable_pages = 0

	total_characters = 0

	for (
		page_number,
		page,
	) in enumerate(
		reader.pages,
		start=1,
	):
		print("\n--------------------------------------")

		print(f"Processing page {page_number}/{total_pages}")

		extraction_error = None

		try:
			text = (page.extract_text() or "").strip()

		except Exception as error:
			text = ""

			extraction_error = str(error)

		character_count = len(text)

		total_characters += character_count

		if extraction_error:
			status = "needs_ocr"

			reason = "Direct extraction failed: " + extraction_error

		else:
			status, reason = check_text_quality(text)

		page_relative_path = Path("pages") / (f"page_{page_number:03d}.txt")

		page_text_path = safe_write_text(
			output_folder,
			page_relative_path,
			text,
		)

		primary_keywords = []

		property_keywords = []

		notice_candidate = False

		notice_text = ""

		notice_text_path = None

		if status == "usable":
			(
				primary_keywords,
				property_keywords,
			) = find_keywords(text)

			notice_candidate = is_notice_candidate(
				primary_keywords,
				property_keywords,
			)

			if notice_candidate:
				notice_text = extract_notice_context(text)

				notice_relative_path = Path("notice_candidates") / (f"page_{page_number:03d}.txt")

				notice_text_path = safe_write_text(
					output_folder,
					notice_relative_path,
					notice_text,
				)

				notice_candidate_pages.append(
					{
						"page_number": page_number,
						"primary_keywords": primary_keywords,
						"property_keywords": property_keywords,
						"text": notice_text,
						"text_file": str(notice_text_path),
					}
				)

		page_result = {
			"page_number": page_number,
			"method": "direct",
			"status": status,
			"character_count": character_count,
			"text": text,
			"text_file": str(page_text_path),
			"reason": reason,
			"notice_candidate": notice_candidate,
			"primary_keywords": primary_keywords,
			"property_keywords": property_keywords,
			"notice_text": notice_text,
			"notice_text_file": (str(notice_text_path) if notice_text_path else None),
		}

		all_pages.append(page_result)

		if status == "needs_ocr":
			ocr_required_pages.append(
				{
					"page_number": page_number,
					"reason": reason,
					"character_count": character_count,
				}
			)

			print("Result: OCR REQUIRED")

			print(
				"Reason:",
				reason,
			)

		else:
			usable_pages += 1

			print("Result: DIRECT TEXT USABLE")

			print(
				"Characters extracted:",
				character_count,
			)

			if notice_candidate:
				all_found = primary_keywords + property_keywords

				print("NOTICE CANDIDATE FOUND")

				print(
					"Keywords:",
					", ".join(all_found),
				)

			else:
				print("No notice candidate found")

	direct_result = {
		"status": "success",
		"pdf_path": str(pdf_path),
		"total_pages": total_pages,
		"usable_direct_pages": usable_pages,
		"ocr_required_pages": len(ocr_required_pages),
		"notice_candidate_pages": len(notice_candidate_pages),
		"total_characters": total_characters,
		"pages": all_pages,
	}

	direct_json_path = safe_write_json(
		output_folder,
		"direct_text.json",
		direct_result,
	)

	ocr_result = {
		"pdf_path": str(pdf_path),
		"total_pages": total_pages,
		"ocr_required_count": len(ocr_required_pages),
		"pages": ocr_required_pages,
	}

	ocr_json_path = safe_write_json(
		output_folder,
		"ocr_required_pages.json",
		ocr_result,
	)

	notice_result = {
		"pdf_path": str(pdf_path),
		"candidate_count": len(notice_candidate_pages),
		"pages": notice_candidate_pages,
	}

	notice_json_path = safe_write_json(
		output_folder,
		"notice_candidates.json",
		notice_result,
	)

	print("\n======================================")

	print("EXTRACTION FINISHED")

	print("======================================")

	print(
		"\nTotal pages:",
		total_pages,
	)

	print(
		"Usable direct-text pages:",
		usable_pages,
	)

	print(
		"OCR required pages:",
		len(ocr_required_pages),
	)

	print(
		"Notice candidate pages:",
		len(notice_candidate_pages),
	)

	if ocr_required_pages:
		print("\nPages to send to Janvi:")

		print(", ".join(str(page["page_number"]) for page in ocr_required_pages))

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
		"output_folder": str(output_folder),
	}


if __name__ == "__main__":
	print("\nPaste the full newspaper PDF path.")

	pdf_path = input("PDF path: ").strip()

	extract_pdf_text(pdf_path)
