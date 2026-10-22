# Copyright (c) 2026, GenEra and contributors
# For license information, please see license.txt

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today
from PIL import Image

from estate_notice.notice_results import build_notice_records

HIGH_NOTICE = (
	"PUBLIC NOTICE\nGeneral public is hereby informed that the original allotment letter of "
	"Plot No. 12 in respect of the property has been lost. Encumbrance free."
)
LOW_NOTICE = (
	"PUBLIC NOTICE\nSubject: Transfer of ownership in respect of H.No. 841, Sector-7C, "
	"Faridabad after the death of the owner."
)


class TestEstateNotice(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.db.rollback)
		with patch("frappe.enqueue"):
			self.job = frappe.get_doc(
				{"doctype": "Estate Notice Job", "newspaper": "Hindustan Times Delhi", "job_date": today()}
			).insert()

		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)
		image = self.folder / "crop.png"
		Image.new("RGB", (20, 30), "white").save(image)

		self.text_json = self.folder / "combined_text.json"
		self.text_json.write_text(
			json.dumps(
				{
					"pages": [
						{"page_number": 10, "text": "Sale of land, survey no 4, plot no 9, village owner"},
						{"page_number": 22, "text": "classifieds page"},
					]
				}
			)
		)
		self.cropping = {
			"pages_selected_by_heading_scan": [22],
			"review_candidates": [{"page_number": 22, "image_path": str(image)}],
			"notices": [
				self.crop(1, HIGH_NOTICE, image),
				self.crop(2, LOW_NOTICE, image),
				self.crop(3, LOW_NOTICE, image),  # same text as the previous crop
			],
		}
		self.detection = {
			"notice_pages": [
				{"page_number": 10, "confidence": "HIGH", "score": 80, "matched_signals": ["survey_number"]},
				{
					"page_number": 22,
					"confidence": "MEDIUM",
					"score": 55,
					"matched_signals": ["public_notice"],
				},
			]
		}

	def crop(self, candidate, text, image):
		return {
			"page_number": 22,
			"column_number": 1,
			"candidate_number": candidate,
			"image_path": str(image),
			"text": text,
		}

	def build(self):
		with patch("public_notice_pipeline.detect_public_notices", return_value=self.cropping):
			return build_notice_records(
				self.job.name, "unused.pdf", self.text_json, self.detection, self.folder
			)

	def notices(self):
		return frappe.get_all(
			"Estate Notice",
			filters={"job": self.job.name},
			fields=["name", "page_number", "record_level", "confidence", "notice_image", "category"],
			order_by="page_number, notice_number",
		)

	def test_crops_and_unsplit_pages_become_records(self):
		results = self.build()
		notices = self.notices()

		self.assertEqual(
			[(n.page_number, n.record_level, n.confidence) for n in notices],
			[(10, "Page", "High"), (22, "Notice", "High"), (22, "Notice", "Medium")],
		)
		self.assertEqual(results["summary"]["high_count"], 2)
		self.assertEqual(results["summary"]["medium_count"], 1)
		self.assertEqual(len(results["skipped"]), 1, "the repeated crop is skipped")
		self.assertEqual(notices[1].category, "Public Notice")

		crop_image = notices[1].notice_image
		self.assertTrue(crop_image.startswith("/private/files/"))
		self.assertIsNone(notices[0].notice_image)
		self.assertTrue(
			frappe.db.exists("File", {"file_url": results["file_url"], "attached_to_name": self.job.name})
		)
		saved = json.loads((self.folder / "notice_results.json").read_text())
		self.assertEqual(saved["summary"]["total_notices"], 3)

	def test_rerun_replaces_records(self):
		self.build()
		frappe.db.set_value("Estate Notice", {"job": self.job.name}, "review_status", "Rejected")
		self.build()
		notices = self.notices()

		# Frappe may reuse the deleted names, so check the records are fresh rather than renamed.
		self.assertEqual(len(notices), 3)
		self.assertEqual(
			frappe.get_all("Estate Notice", filters={"job": self.job.name}, pluck="review_status"),
			["Needs Review"] * 3,
		)
		self.assertEqual(
			frappe.db.count(
				"File",
				{
					"attached_to_doctype": "Estate Notice Job",
					"attached_to_name": self.job.name,
					"attached_to_field": "results_json",
				},
			),
			1,
		)
