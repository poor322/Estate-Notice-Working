"""Turn a job's OCR and detection output into Estate Notice records.

Every "PUBLIC NOTICE" that public_notice_pipeline crops (a heading plus at
least 80 characters of body) becomes a record. It is High if the detector
rates its own text HIGH and Medium otherwise: the detector is tuned for
survey/plot wording and under-rates ownership-transfer notices, so the crop
itself is treated as Medium evidence. A page the detector flagged High or
Medium that has no cropped notice gets one page-level record with the page
text. Records are replaced on every run, so re-running a job never
leaves duplicates.
"""

import hashlib
import json
import re
from pathlib import Path

import frappe

from estate_notice.detectors.notice_detector import detect_notice
from estate_notice.job_status import JOB_DOCTYPE

NOTICE_DOCTYPE = "Estate Notice"

# structured_extractor keys copied onto the record: as they are, as labels, or joined lists.
LABEL_FIELDS = ("classification", "notice_type", "transaction_type")
TEXT_FIELDS = (
	"property_number",
	"property_address",
	"village",
	"tehsil",
	"city",
	"land_area",
	"objection_period_days",
)
LIST_FIELDS = (
	"pincodes",
	"owner_names",
	"legal_heirs",
	"seller_names",
	"mustatil_numbers",
	"killa_numbers",
	"document_numbers",
	"phone_numbers",
	"email_addresses",
)


def build_notice_records(job_name, pdf_path, text_json, page_detection, output_folder):
	"""Replace the job's Estate Notices with this run's, save and attach the results JSON.

	Returns the results dict; its "summary" holds the counts for the job.
	"""
	from public_notice_pipeline import detect_public_notices

	output_folder = Path(output_folder)
	cropping = detect_public_notices(pdf_path, output_folder / "public_notices")

	delete_job_notices(job_name)
	entries, skipped = [], []
	seen_hashes = set()
	numbers = {}

	def add(entry):
		if entry["content_hash"] in seen_hashes:
			entry["skipped"] = "Same text as an earlier record in this run"
			skipped.append(entry)
			return
		seen_hashes.add(entry["content_hash"])
		entry["record"] = create_notice(job_name, entry, output_folder)
		entries.append(entry)

	for crop in cropping["notices"]:
		detection = detect_notice(crop["text"], crop["page_number"])
		numbers[crop["page_number"]] = numbers.get(crop["page_number"], 0) + 1
		add(
			{
				"record_level": "Notice",
				"page_number": crop["page_number"],
				"notice_number": numbers[crop["page_number"]],
				"column_number": crop["column_number"],
				"candidate_number": crop["candidate_number"],
				"image_path": crop["image_path"],
				"text": crop["text"],
				"content_hash": content_hash(crop["text"]),
				"confidence": "High" if detection["confidence"] == "HIGH" else "Medium",
				"detection": detection,
			}
		)

	# Do not turn a page-level detector hit into an Estate Notice when
	# cropping found no real notice. Newspaper articles and advertisements
	# can contain generic property words such as land, sale, plot or acres.
	# Those false positives previously appeared as "Whole page (not split)"
	# records with no notice image.
	pages_with_notices = {entry["page_number"] for entry in entries}

	for page in page_detection["notice_pages"]:
		if page["page_number"] in pages_with_notices:
			continue

		skipped.append(
			{
				"record_level": "Page",
				"page_number": page["page_number"],
				"confidence": page["confidence"].title(),
				"detection": {key: value for key, value in page.items() if key != "text_preview"},
				"skipped": "No cropped notice found; page-level fallback suppressed",
			}
		)

	high = sum(1 for entry in entries if entry["confidence"] == "High")
	results = {
		"job": job_name,
		"summary": {
			"total_notices": len(entries),
			"high_count": high,
			"medium_count": len(entries) - high,
			"cropped_notices": sum(1 for entry in entries if entry["record_level"] == "Notice"),
			"page_records": sum(1 for entry in entries if entry["record_level"] == "Page"),
			"detector_pages": [page["page_number"] for page in page_detection["notice_pages"]],
			"public_notice_pages": cropping["pages_selected_by_heading_scan"],
		},
		"records": entries,
		"skipped": skipped,
		"uncertain_crops": cropping["review_candidates"],
	}
	results_path = output_folder / "notice_results.json"
	results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
	results["file_url"] = attach_results_file(job_name, results_path)
	return results


def create_notice(job_name, entry, output_folder):
	"""Insert one Estate Notice for an entry and attach its crop; returns the record name."""
	from notice_extraction.structured_extractor import structure_notice

	text_folder = output_folder / "notice_texts"
	text_folder.mkdir(parents=True, exist_ok=True)
	suffix = "page" if entry["record_level"] == "Page" else f"notice_{entry['notice_number']:02d}"
	text_path = text_folder / f"page_{entry['page_number']:03d}_{suffix}.txt"
	text_path.write_text(entry["text"], encoding="utf-8")
	fields = structure_notice(text_path)
	entry["extracted"] = {key: value for key, value in fields.items() if key != "raw_text"}

	detection = entry["detection"]
	values = {
		"doctype": NOTICE_DOCTYPE,
		"job": job_name,
		"page_number": entry["page_number"],
		"record_level": entry["record_level"],
		"notice_number": entry["notice_number"],
		"confidence": entry["confidence"],
		"score": detection.get("score"),
		"matched_signals": ", ".join(detection.get("matched_signals") or []),
		"category": humanize(fields.get("notice_type")),
		"ocr_text": entry["text"],
		"content_hash": entry["content_hash"],
		"raw_json": json.dumps(
			{key: value for key, value in entry.items() if key != "text"}, indent=2, ensure_ascii=False
		),
	}
	for key in LABEL_FIELDS:
		values[key] = humanize(fields.get(key))
	for key in TEXT_FIELDS:
		values[key] = fields.get(key)
	for key in LIST_FIELDS:
		values[key] = ", ".join(str(value) for value in fields.get(key) or [])

	notice = frappe.get_doc(values).insert(ignore_permissions=True)
	if entry.get("image_path"):
		image_path = Path(entry["image_path"])
		image = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{notice.name}.png",
				"content": image_path.read_bytes(),
				"is_private": 1,
				"attached_to_doctype": NOTICE_DOCTYPE,
				"attached_to_name": notice.name,
				"attached_to_field": "notice_image",
			}
		).insert(ignore_permissions=True)
		notice.db_set("notice_image", image.file_url)
	return notice.name


def delete_job_notices(job_name):
	"""Delete the job's Estate Notices; their attached images go with them."""
	for name in frappe.get_all(NOTICE_DOCTYPE, filters={"job": job_name}, pluck="name"):
		frappe.delete_doc(NOTICE_DOCTYPE, name, ignore_permissions=True, force=True)


def attach_results_file(job_name, results_path):
	"""Attach the results JSON to the job as a private file, replacing the previous run's."""
	for name in frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": JOB_DOCTYPE,
			"attached_to_name": job_name,
			"attached_to_field": "results_json",
		},
		pluck="name",
	):
		frappe.delete_doc("File", name, ignore_permissions=True, force=True)

	results_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{job_name}-notice-results.json",
			"content": Path(results_path).read_bytes(),
			"is_private": 1,
			"attached_to_doctype": JOB_DOCTYPE,
			"attached_to_name": job_name,
			"attached_to_field": "results_json",
		}
	).insert(ignore_permissions=True)
	return results_file.file_url


def content_hash(text):
	normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
	return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def humanize(value):
	"""PUBLIC_NOTICE -> Public Notice."""
	if not value:
		return None
	return str(value).replace("_", " ").title()
