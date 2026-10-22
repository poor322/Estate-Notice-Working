import shutil
from pathlib import Path

import frappe

def create_server_script():
    script_name = "Run Estate Notice Fetcher"
    
    if frappe.db.exists("Server Script", script_name):
        print("Server Script already exists.")
        return

    script_code = """
if doc.status == "Pending" and not doc.job_log:
    doc.status = "Running"
    doc.job_log = "Job queued..."
    frappe.enqueue(
        "estate_notice.setup_frontend.run_fetcher_job",
        queue="long",
        timeout=3600,
        job_name=doc.name,
        doc_name=doc.name,
        enqueue_after_commit=True
    )
"""

    doc = frappe.get_doc({
        "doctype": "Server Script",
        "name": script_name,
        "script_type": "DocType Event",
        "reference_doctype": "Estate Notice Job",
        "doctype_event": "Before Save",
        "script": script_code,
        "disabled": 0
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created Server Script.")

@frappe.whitelist()
def run_fetcher_job(doc_name=None):
    try:
        from estate_notice.extractors.pdf_text_extractor import extract_pdf_text

        job = frappe.get_doc("Estate Notice Job", doc_name)

        if job.uploaded_pdf:
            pdf_path = stage_uploaded_pdf(job)
            source_message = f"Using uploaded PDF: {pdf_path}\n"
        else:
            from estate_notice.fetchers.indupaper_fetcher import run as fetcher_run

            source_message = "Running newspaper fetcher...\n"
            frappe.db.set_value("Estate Notice Job", doc_name, "job_log", source_message)
            frappe.db.commit()
            pdf_path = fetcher_run()

        frappe.db.set_value(
            "Estate Notice Job",
            doc_name,
            "job_log",
            source_message + "Running extractor...\n",
        )
        frappe.db.commit()

        extraction_results = extract_pdf_text(str(pdf_path))

        output_folder = extraction_results.get("output_folder")
        final_log = f"Extraction Finished.\nStatus: {extraction_results.get('status')}\n"
        if extraction_results.get("status") == "success":
            final_log += f"Total Pages: {extraction_results.get('total_pages')}\n"
            final_log += f"Notice Candidates Found: {extraction_results.get('notice_candidate_pages')}\n"
            final_log += f"OCR Required Pages: {extraction_results.get('ocr_required_pages')}\n"
            final_log += f"Outputs saved to: {output_folder}\n"

            if extraction_results.get("ocr_required_pages", 0) > 0:
                frappe.db.set_value(
                    "Estate Notice Job",
                    doc_name,
                    "job_log",
                    final_log + "\nRunning OCR (this may take a while)...\n",
                )
                frappe.db.commit()

                try:
                    from estate_notice.extractors.ocr_extractor import (
                        ocr_required_pages as run_ocr,
                    )

                    direct_json_path = f"{output_folder}/direct_text.json"
                    ocr_list_path = f"{output_folder}/ocr_required_pages.json"

                    run_ocr(str(pdf_path), direct_json_path, ocr_list_path)

                    final_log += "\nOCR Extraction Finished Successfully!"
                except Exception as e:
                    final_log += f"\nOCR failed: {str(e)}"
        else:
            final_log += f"Reason: {extraction_results.get('reason')}"

        frappe.db.set_value("Estate Notice Job", doc_name, "job_log", final_log)
        final_status = "Completed" if extraction_results.get("status") == "success" else "Failed"
        frappe.db.set_value("Estate Notice Job", doc_name, "status", final_status)
        frappe.db.commit()
    except Exception as e:
        frappe.db.set_value("Estate Notice Job", doc_name, "status", "Failed")
        frappe.db.set_value("Estate Notice Job", doc_name, "job_log", f"Failed: {str(e)}")
        frappe.db.commit()


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
    if (
        file_doc.attached_to_doctype != "Estate Notice Job"
        or file_doc.attached_to_name != job.name
    ):
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
    if not source_path.is_file() or not any(
        source_path.is_relative_to(root) for root in allowed_roots
    ):
        raise ValueError("The uploaded PDF could not be found in this site's files.")

    target_dir = Path(
        frappe.get_site_path("private", "files", "newspapers", "manual_uploads")
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / f"{job.name}.pdf").resolve()
    if not target_path.is_relative_to(target_dir.resolve()):
        raise ValueError("Invalid uploaded PDF filename.")

    shutil.copy2(source_path, target_path)
    return target_path

def main():
    create_server_script()

