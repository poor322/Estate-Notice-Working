# Copyright (c) 2026, GenEra and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today
from frappe.utils.background_jobs import create_job_id

from estate_notice.fetchers.sources import check_fetch_supported
from estate_notice.job_status import ACTIVE_STATUSES, on_job_failure

JOB_TIMEOUT_SECONDS = 3600


class EstateNoticeJob(Document):
	def validate(self):
		if self.is_new_run() and not self.uploaded_pdf:
			try:
				check_fetch_supported(self.newspaper, getdate(self.job_date), getdate(today()))
			except ValueError as error:
				frappe.throw(str(error), title=_("Can't download this edition"))

	def before_save(self):
		if self.is_new_run():
			self.queue_run()

	def is_new_run(self):
		return self.status == "Pending" and not self.job_log

	def queue_run(self):
		"""Enqueue the pipeline once this save commits. The worker sets Running when it starts."""
		job_id = f"estate_notice_job|{self.name}|{frappe.generate_hash(length=8)}"
		self.status = "Queued"
		self.job_log = "Job queued...\n"
		self.rq_job_id = create_job_id(job_id)
		frappe.enqueue(
			"estate_notice.setup_frontend.run_fetcher_job",
			queue="long",
			timeout=JOB_TIMEOUT_SECONDS,
			job_id=job_id,
			on_failure=on_job_failure,
			enqueue_after_commit=True,
			doc_name=self.name,
		)


NOTICE_LIST_FIELDS = (
	"name",
	"page_number",
	"notice_number",
	"record_level",
	"confidence",
	"score",
	"category",
	"review_status",
	"notice_image",
	"property_number",
	"property_address",
	"village",
	"owner_names",
	"phone_numbers",
	"classification",
	"transaction_type",
	"objection_period_days",
)


@frappe.whitelist()
def get_job_results(job: str):
	"""Return the job's Estate Notices and its parsed results JSON for the form."""
	doc = frappe.get_doc("Estate Notice Job", job)
	doc.check_permission("read")

	notices = frappe.get_list(
		"Estate Notice",
		filters={"job": job},
		fields=list(NOTICE_LIST_FIELDS),
		order_by="page_number asc, notice_number asc",
		limit_page_length=0,
	)
	results = None
	if doc.results_json:
		file_name = frappe.db.get_value(
			"File",
			{
				"file_url": doc.results_json,
				"attached_to_doctype": "Estate Notice Job",
				"attached_to_name": job,
			},
		)
		if file_name:
			results = json.loads(frappe.get_doc("File", file_name).get_content())
	return {"notices": notices, "results": results}


@frappe.whitelist(methods=["POST"])
def rerun(job: str):
	"""Queue the job again; the new run replaces its Estate Notices when it finishes."""
	doc = frappe.get_doc("Estate Notice Job", job)
	doc.check_permission("write")
	if doc.status in ACTIVE_STATUSES:
		frappe.throw(_("This job is already queued or running."))

	doc.status = "Pending"
	doc.job_log = None
	doc.save()
