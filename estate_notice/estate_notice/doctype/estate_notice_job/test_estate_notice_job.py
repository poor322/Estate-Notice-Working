# Copyright (c) 2026, GenEra and contributors
# For license information, please see license.txt

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime, today
from rq.exceptions import NoSuchJobError

from estate_notice.fetchers.sources import check_fetch_supported
from estate_notice.job_status import check_stuck_jobs, mark_job_failed, on_job_failure

JOB = "Estate Notice Job"


class TestEstateNoticeJob(IntegrationTestCase):
	def setUp(self):
		# The status helpers commit; keep everything inside the test transaction.
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)
		self.addCleanup(frappe.db.rollback)

	def make_job(self, **values):
		with patch("frappe.enqueue") as enqueue:
			job = frappe.get_doc(
				{"doctype": JOB, "newspaper": "Hindustan Times Delhi", "job_date": today(), **values}
			).insert()
		return job, enqueue

	def set_state(self, name, status, rq_job_id=None, minutes_ago=30):
		frappe.db.set_value(
			JOB,
			name,
			{
				"status": status,
				"rq_job_id": rq_job_id,
				"modified": add_to_date(now_datetime(), minutes=-minutes_ago),
			},
			update_modified=False,
		)

	def test_fetch_support_rules(self):
		day = date(2026, 10, 22)
		check_fetch_supported("Hindustan Times Delhi", day, day)
		with self.assertRaisesRegex(ValueError, "only available for Hindustan Times Delhi"):
			check_fetch_supported("Times of India", day, day)
		with self.assertRaisesRegex(ValueError, "only fetches today's edition"):
			check_fetch_supported("Hindustan Times Delhi", date(2026, 10, 14), day)

	def test_unsupported_download_is_rejected_on_save(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_job(job_date=add_to_date(today(), days=-3))
		with self.assertRaises(frappe.ValidationError):
			self.make_job(newspaper="Times of India")

	def test_new_job_is_queued_with_failure_callback(self):
		job, enqueue = self.make_job()

		self.assertEqual(job.status, "Queued")
		self.assertTrue(job.rq_job_id.startswith(f"{frappe.local.site}||estate_notice_job|{job.name}|"))
		kwargs = enqueue.call_args.kwargs
		self.assertIs(kwargs["on_failure"], on_job_failure)
		self.assertEqual(f"{frappe.local.site}||{kwargs['job_id']}", job.rq_job_id)
		self.assertEqual(kwargs["doc_name"], job.name)
		self.assertTrue(kwargs["enqueue_after_commit"])

	def test_resaving_a_finished_job_does_not_requeue(self):
		job, _ = self.make_job()
		self.set_state(job.name, "Completed")
		job.reload()
		with patch("frappe.enqueue") as enqueue:
			job.save()
		enqueue.assert_not_called()

	def test_mark_job_failed_only_touches_active_jobs(self):
		running, _ = self.make_job()
		self.set_state(running.name, "Running")
		done, _ = self.make_job()
		self.set_state(done.name, "Completed")

		self.assertTrue(mark_job_failed(running.name, "worker died"))
		self.assertFalse(mark_job_failed(done.name, "worker died"))

		status, log = frappe.db.get_value(JOB, running.name, ["status", "job_log"])
		self.assertEqual(status, "Failed")
		self.assertIn("worker died", log)
		self.assertEqual(frappe.db.get_value(JOB, done.name, "status"), "Completed")

	def test_failure_callback_marks_abandoned_job_failed(self):
		job, _ = self.make_job()
		self.set_state(job.name, "Running", rq_job_id="x")
		rq_job = SimpleNamespace(kwargs={"site": frappe.local.site, "kwargs": {"doc_name": job.name}})
		abandoned = type("AbandonedJobError", (Exception,), {})

		with patch("frappe.utils.background_jobs.truncate_failed_registry"):
			on_job_failure(rq_job, None, abandoned, abandoned(), None)

		status, log = frappe.db.get_value(JOB, job.name, ["status", "job_log"])
		self.assertEqual(status, "Failed")
		self.assertIn("worker stopped", log)

	def test_checker_fails_jobs_rq_has_lost(self):
		no_id, _ = self.make_job()
		self.set_state(no_id.name, "Running")
		missing, _ = self.make_job()
		self.set_state(missing.name, "Running", rq_job_id="missing")
		stale, _ = self.make_job()
		self.set_state(stale.name, "Running", rq_job_id="stale")
		alive, _ = self.make_job()
		self.set_state(alive.name, "Running", rq_job_id="alive")
		waiting, _ = self.make_job()
		self.set_state(waiting.name, "Queued", rq_job_id="waiting")
		fresh, _ = self.make_job()
		self.set_state(fresh.name, "Queued", minutes_ago=0)

		now = datetime.now(UTC)
		rq_jobs = {
			"stale": SimpleNamespace(status="started", last_heartbeat=now - timedelta(minutes=30)),
			"alive": SimpleNamespace(status="started", last_heartbeat=now - timedelta(seconds=20)),
			"waiting": SimpleNamespace(status="queued", last_heartbeat=None),
		}

		def fetch(job_id, connection=None):
			if job_id not in rq_jobs:
				raise NoSuchJobError(job_id)
			rq_job = rq_jobs[job_id]
			rq_job.get_status = lambda refresh=False: rq_job.status
			return rq_job

		with patch("rq.job.Job.fetch", side_effect=fetch):
			failed = check_stuck_jobs()

		test_jobs = {job.name for job in (no_id, missing, stale, alive, waiting, fresh)}
		self.assertEqual(set(failed) & test_jobs, {no_id.name, missing.name, stale.name})
		for name in (alive.name, waiting.name):
			self.assertEqual(
				frappe.db.get_value(JOB, name, "status"), "Running" if name == alive.name else "Queued"
			)
		self.assertEqual(frappe.db.get_value(JOB, fresh.name, "status"), "Queued")
