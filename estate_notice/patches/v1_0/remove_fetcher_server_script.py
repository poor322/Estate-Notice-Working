import frappe


def execute():
	"""The Estate Notice Job controller now enqueues runs, so the Server Script would queue every job twice."""
	frappe.delete_doc_if_exists("Server Script", "Run Estate Notice Fetcher", force=True)
