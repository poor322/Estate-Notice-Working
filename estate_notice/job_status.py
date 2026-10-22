"""Keep Estate Notice Job statuses in step with what RQ actually did.

A job can die without its own code getting a chance to record it: the worker
is restarted, the VM reboots, or `bench migrate` kills the job's idle database
connection. Three things cover that:

- `set_job_values` reconnects to the database once if a write fails;
- `on_job_failure` is the RQ failure callback, which RQ also calls for jobs a
  restarted worker finds abandoned;
- `check_stuck_jobs` runs on the scheduler and fails active jobs RQ has lost.
"""

from datetime import UTC, datetime, timedelta

import frappe
from frappe.utils import add_to_date, now, now_datetime

JOB_DOCTYPE = "Estate Notice Job"
ACTIVE_STATUSES = ("Queued", "Running")

# Leave a fresh job alone while its enqueue-after-commit is still in flight.
QUEUE_GRACE_MINUTES = 2
# The worker refreshes a running job's heartbeat every few seconds.
STALE_HEARTBEAT_MINUTES = 10


def reconnect_db():
	"""Drop the current database connection and open a new one as the same user."""
	user = frappe.session.user if getattr(frappe.local, "session", None) else "Administrator"
	for close in (frappe.db.rollback, frappe.db.close):
		try:
			close()
		except Exception:
			pass
	frappe.connect()
	frappe.set_user(user)


def set_job_values(doc_name, **values):
	"""Write fields on the job and commit, reconnecting once if the connection was lost."""
	try:
		frappe.db.set_value(JOB_DOCTYPE, doc_name, values)
		frappe.db.commit()
	except Exception:
		reconnect_db()
		frappe.db.set_value(JOB_DOCTYPE, doc_name, values)
		frappe.db.commit()


def mark_job_failed(doc_name, reason):
	"""Set an active job to Failed and append the reason to its log.

	Jobs that already finished are left untouched, so callers don't need to
	know whether the job recorded its own outcome first.
	"""
	status, job_log = frappe.db.get_value(JOB_DOCTYPE, doc_name, ["status", "job_log"]) or (None, None)
	if status not in ACTIVE_STATUSES:
		return False

	job_log = (job_log or "").rstrip()
	set_job_values(
		doc_name,
		status="Failed",
		job_log=f"{job_log}\n\nFailed ({now()[:19]}): {reason}".lstrip(),
	)
	return True


def on_job_failure(job, connection, exc_type, exc_value, traceback):
	"""RQ failure callback for run_fetcher_job.

	RQ calls this in the work-horse when the job raises or times out, and in a
	worker's registry cleanup when it finds a job whose worker died. Neither
	context has a Frappe site set up, so this opens and closes its own.
	"""
	from frappe.utils.background_jobs import truncate_failed_registry

	site = job.kwargs.get("site")
	doc_name = (job.kwargs.get("kwargs") or {}).get("doc_name")
	reason = describe_failure(exc_type, exc_value)

	owns_context = getattr(frappe.local, "site", None) != site
	if owns_context:
		frappe.init(site, force=True)
		frappe.connect()
	try:
		# Frappe's default failure callback, which ours replaces.
		truncate_failed_registry(job, connection, exc_type, exc_value, traceback)
		if doc_name:
			mark_job_failed(doc_name, reason)
	finally:
		if owns_context:
			frappe.destroy()


def describe_failure(exc_type, exc_value):
	name = getattr(exc_type, "__name__", str(exc_type))
	if name == "AbandonedJobError":
		return "The worker stopped while this job was running (restart or reboot)."
	if name == "JobTimeoutException":
		return f"The job ran past its time limit. {exc_value}".strip()
	return f"{name}: {exc_value}"


def check_stuck_jobs():
	"""Scheduled: fail Queued/Running jobs that RQ is no longer working on."""
	cutoff = add_to_date(now_datetime(), minutes=-QUEUE_GRACE_MINUTES)
	jobs = frappe.get_all(
		JOB_DOCTYPE,
		filters={"status": ["in", ACTIVE_STATUSES], "modified": ["<", cutoff]},
		fields=["name", "rq_job_id"],
	)
	failed = []
	for job in jobs:
		reason = get_lost_job_reason(job.rq_job_id)
		if reason and mark_job_failed(job.name, reason):
			failed.append(job.name)
	return failed


def get_lost_job_reason(rq_job_id):
	"""Return why RQ is no longer running this job, or None if it still is."""
	from frappe.utils.background_jobs import get_redis_conn
	from rq.exceptions import NoSuchJobError
	from rq.job import Job

	if not rq_job_id:
		return "No RQ job ID was recorded, so the job can't be tracked. It was most likely lost in a restart."

	try:
		job = Job.fetch(rq_job_id, connection=get_redis_conn())
	except NoSuchJobError:
		return "RQ has no record of this job any more; the worker probably stopped before it could finish."

	status = job.get_status(refresh=False)
	status = getattr(status, "value", status)
	if status in ("queued", "deferred", "scheduled"):
		return None
	if status == "started":
		heartbeat = job.last_heartbeat
		if heartbeat and heartbeat.tzinfo is None:
			heartbeat = heartbeat.replace(tzinfo=UTC)
		stale_before = datetime.now(UTC) - timedelta(minutes=STALE_HEARTBEAT_MINUTES)
		if heartbeat and heartbeat < stale_before:
			return f"The worker stopped sending heartbeats at {heartbeat:%Y-%m-%d %H:%M} UTC."
		return None
	if status == "finished":
		return "RQ finished the job but it never recorded its result."
	return f"RQ marked the job as {status}."
