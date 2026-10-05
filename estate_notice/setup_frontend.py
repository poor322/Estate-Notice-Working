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
    
    # We enqueue a background job to run the scripts
    frappe.enqueue(
        "estate_notice.setup_frontend.run_fetcher_job",
        queue="default",
        job_name=doc.name
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
    # This is the background job function
    import sys
    from pathlib import Path
    
    # We need to run indupaper_fetcher.py logic here
    # The simplest way is to import the fetcher and run it
    try:
        from estate_notice.fetchers.indupaper_fetcher import run as fetcher_run
        from estate_notice.extractors.pdf_text_extractor import extract_pdf_text
        
        frappe.db.set_value("Estate Notice Job", doc_name, "job_log", "Running fetcher...\n")
        frappe.db.commit()
        
        # 1. Run fetcher
        pdf_path = fetcher_run()
        
        frappe.db.set_value("Estate Notice Job", doc_name, "job_log", f"Fetcher completed. PDF saved to: {pdf_path}\nRunning extractor...\n")
        frappe.db.commit()
        
        # 2. Run extractor
        extraction_results = extract_pdf_text(str(pdf_path))
        
        output_folder = extraction_results.get('output_folder')
        
        # 3. Log results
        final_log = f"Extraction Finished.\nStatus: {extraction_results.get('status')}\n"
        if extraction_results.get('status') == 'success':
            final_log += f"Total Pages: {extraction_results.get('total_pages')}\n"
            final_log += f"Notice Candidates Found: {extraction_results.get('notice_candidate_pages')}\n"
            final_log += f"OCR Required Pages: {extraction_results.get('ocr_required_pages')}\n"
            final_log += f"Outputs saved to: {output_folder}\n"
            
            # 4. Run OCR if needed
            if extraction_results.get('ocr_required_pages', 0) > 0:
                frappe.db.set_value("Estate Notice Job", doc_name, "job_log", final_log + "\nRunning OCR (this may take a while)...\n")
                frappe.db.commit()
                
                try:
                    from estate_notice.extractors.ocr_extractor import ocr_required_pages as run_ocr
                    
                    direct_json_path = f"{output_folder}/direct_text.json"
                    ocr_list_path = f"{output_folder}/ocr_required_pages.json"
                    
                    run_ocr(str(pdf_path), direct_json_path, ocr_list_path)
                    
                    final_log += "\nOCR Extraction Finished Successfully!"
                except Exception as e:
                    final_log += f"\nOCR failed: {str(e)}"
        else:
            final_log += f"Reason: {extraction_results.get('reason')}"
            
        frappe.db.set_value("Estate Notice Job", doc_name, "job_log", final_log)
        frappe.db.set_value("Estate Notice Job", doc_name, "status", "Completed")
        frappe.db.commit()
    except Exception as e:
        frappe.db.set_value("Estate Notice Job", doc_name, "status", "Failed")
        frappe.db.set_value("Estate Notice Job", doc_name, "job_log", f"Failed: {str(e)}")
        frappe.db.commit()

def main():
    create_server_script()

