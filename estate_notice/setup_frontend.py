import shutil
from pathlib import Path

import frappe
from frappe.utils import getdate, today

from estate_notice.job_status import JOB_DOCTYPE, mark_job_failed, reconnect_db, set_job_values


class JobLog:
	"""Accumulates the job log and saves it after every step."""

	def __init__(self, doc_name):
		self.doc_name = doc_name
		self.lines = []

	def add(self, text, **values):
		self.lines.append(text)
		set_job_values(self.doc_name, job_log="\n".join(self.lines) + "\n", **values)


def run_fetcher_job(doc_name=None):
	"""Background job: get the PDF, extract text, OCR, detect notices, then create Estate Notices."""
	log = JobLog(doc_name)
	try:
		from estate_notice.detectors.notice_detector import detect_from_json
		from estate_notice.extractors.ocr_extractor import ocr_required_pages as run_ocr
		from estate_notice.extractors.pdf_text_extractor import extract_pdf_text
		from estate_notice.notice_results import build_notice_records

		job = frappe.get_doc(JOB_DOCTYPE, doc_name)
		output_folder = get_job_output_folder(job.name)
		log.add("Job started.", status="Running", output_folder=str(output_folder))

		if job.uploaded_pdf:
			pdf_path = stage_uploaded_pdf(job)
			log.add(f"Using uploaded PDF: {pdf_path}")
		else:
			from estate_notice.fetchers.indupaper_fetcher import run as fetcher_run

			log.add(f"Downloading {job.newspaper} for {job.job_date}...")
			pdf_path = fetcher_run(
				newspaper=job.newspaper,
				edition_date=getdate(job.job_date),
				today=getdate(today()),
			)
			log.add(f"Downloaded PDF: {pdf_path}", downloaded_pdf=attach_downloaded_pdf(job.name, pdf_path))

		log.add("Running extractor...")
		extraction = extract_pdf_text(str(pdf_path), output_folder=output_folder / "direct_extraction")
		if extraction.get("status") != "success":
			raise RuntimeError(f"Text extraction failed: {extraction.get('reason')}")

		direct_folder = Path(extraction["output_folder"])
		text_json = direct_folder / "direct_text.json"
		ocr_page_count = extraction.get("ocr_required_pages", 0)
		log.add(
			f"Total Pages: {extraction.get('total_pages')}\n"
			f"Text-layer candidates: {extraction.get('notice_candidate_pages')}\n"
			f"OCR Required Pages: {ocr_page_count}",
			total_pages=extraction.get("total_pages"),
			ocr_pages=ocr_page_count,
		)

		if ocr_page_count:
			log.add("Running OCR (this may take a while)...")
			ocr = run_ocr(
				str(pdf_path),
				str(text_json),
				str(direct_folder / "ocr_required_pages.json"),
				output_folder=output_folder / "ocr_extraction",
			)
			failed_pages = ocr["failed_pages"]
			if failed_pages and len(failed_pages) == ocr["ocr_page_count"]:
				raise RuntimeError(f"OCR failed on all {len(failed_pages)} pages.")
			text_json = Path(ocr["combined_file"])
			failed_note = (
				f" Pages that failed OCR: {', '.join(str(page) for page in failed_pages)}"
				if failed_pages
				else ""
			)
			log.add("OCR finished." + failed_note)

		detection = detect_from_json(str(text_json), str(output_folder / "notice_detection.json"))
		notice_pages = detection["notice_pages"]
		high = sum(1 for page in notice_pages if page["confidence"] == "HIGH")
		page_list = ", ".join(str(page["page_number"]) for page in notice_pages) or "none"
		log.add(
			f"Notice pages (detector on {'OCR' if ocr_page_count else 'text-layer'} text): "
			f"{len(notice_pages)} (HIGH {high}, MEDIUM {len(notice_pages) - high}; pages: {page_list})"
		)

		log.add("Cropping public notices and extracting fields...")
		results = build_notice_records(job.name, str(pdf_path), text_json, detection, output_folder)
		summary = results["summary"]
		log.add(
			f"Estate Notices created: {summary['total_notices']} "
			f"(High {summary['high_count']}, Medium {summary['medium_count']}): "
			f"{summary['cropped_notices']} cropped notices, "
			f"{summary['page_records']} whole-page records for flagged pages with no cropped notice\n"
			f"Outputs saved to: {output_folder}",
			status="Completed",
			total_notices=summary["total_notices"],
			high_count=summary["high_count"],
			medium_count=summary["medium_count"],
			results_json=results["file_url"],
		)
	except Exception as error:
		# The connection may be gone (bench migrate kills idle ones during OCR),
		# so open a fresh one before recording the failure.
		reconnect_db()
		mark_job_failed(doc_name, f"{type(error).__name__}: {error}")
		raise


def get_job_output_folder(job_name):
	"""Return private/files/estate_notice/jobs/<job name>/, creating it."""
	jobs_root = Path(frappe.get_site_path("private", "files", "estate_notice", "jobs")).resolve()
	folder = (jobs_root / job_name).resolve()
	if folder.parent != jobs_root:
		raise ValueError(f"Invalid job name for an output folder: {job_name}")
	folder.mkdir(parents=True, exist_ok=True)
	return folder


def attach_downloaded_pdf(job_name, pdf_path):
	"""Save the downloaded PDF as a private File on the job and return its URL.

	Frappe only serves files kept directly in private/files, so this stores a
	copy there (Frappe reuses an existing copy with the same content).
	"""
	pdf_path = Path(pdf_path)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{pdf_path.stem}_{pdf_path.parent.name}.pdf",
			"content": pdf_path.read_bytes(),
			"is_private": 1,
			"attached_to_doctype": JOB_DOCTYPE,
			"attached_to_name": job_name,
			"attached_to_field": "downloaded_pdf",
		}
	).insert(ignore_permissions=True)
	return file_doc.file_url


def stage_uploaded_pdf(job):
	"""Copy the job's attached PDF into the extractor's allowed input folder."""
	if not job.uploaded_pdf:
		raise ValueError("No PDF was uploaded for this job.")

	file_doc = frappe.get_doc(
		"File",
		{
			"file_url": job.uploaded_pdf,
			"attached_to_doctype": "Estate Notice Job",
			"attached_to_name": job.name,
		},
	)
	if file_doc.attached_to_doctype != "Estate Notice Job" or file_doc.attached_to_name != job.name:
		raise ValueError("The uploaded file is not attached to this Estate Notice Job.")

	file_name = file_doc.file_name or job.uploaded_pdf
	if Path(file_name).suffix.lower() != ".pdf":
		raise ValueError("Upload a PDF file.")

	source_path = Path(file_doc.get_full_path()).resolve()
	site_path = Path(frappe.get_site_path()).resolve()
	allowed_roots = (
		(site_path / "private" / "files").resolve(),
		(site_path / "public" / "files").resolve(),
	)
	if not source_path.is_file() or not any(source_path.is_relative_to(root) for root in allowed_roots):
		raise ValueError("The uploaded PDF could not be found in this site's files.")

	target_dir = Path(frappe.get_site_path("private", "files", "newspapers", "manual_uploads"))
	target_dir.mkdir(parents=True, exist_ok=True)
	target_path = (target_dir / f"{job.name}.pdf").resolve()
	if not target_path.is_relative_to(target_dir.resolve()):
		raise ValueError("Invalid uploaded PDF filename.")

	shutil.copy2(source_path, target_path)
	return target_path
