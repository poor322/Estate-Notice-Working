# Copyright (c) 2026, GenEra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today
from frappe.utils.background_jobs import create_job_id

from estate_notice.fetchers.sources import check_fetch_supported
from estate_notice.job_status import on_job_failure

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
