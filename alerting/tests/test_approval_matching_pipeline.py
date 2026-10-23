import tempfile
import unittest
from pathlib import Path

from alerting.review_to_matcher import build_approved_notices
from alerting.approved_notice_matching import build_matcher_results
from alerting.alert_router import route_matches


class TestApprovalMatchingPipeline(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)
        (self.root / "notice001.txt").write_text(
            "Synthetic public notice for testing",
            encoding="utf-8",
        )

        self.source = [{
            "id": "NOTICE001",
            "content_hash": "test-hash-001",
            "source_image": "original-image.png",
            "ocr_text": "Property H.No. 101",
            "survey_number": "",
            "plot_number": "",
        }]

        self.review = [{
            "notice_id": "NOTICE001",
            "content_hash": "test-hash-001",
            "review_decision": "APPROVED",
            "approved_house_number": "101",
            "approved_by": "Synthetic Reviewer",
            "approved_at": "2026-10-23T10:00:00",
            "extraction_status": "SUBJECT_CANDIDATE_REVIEW",
        }]

        self.properties = [{
            "property_id": "PROPERTY001",
            "house_number": "101",
            "village": "Village A",
        }]

    def test_pending_notice_does_not_match(self):
        review = [dict(self.review[0])]
        review[0]["review_decision"] = "PENDING"

        approved = build_approved_notices(
            self.source, review
        )

        self.assertEqual(approved, [])

        payload = build_matcher_results(
            approved,
            self.properties,
            {},
            self.root,
        )

        self.assertEqual(payload["matches"], [])

    def test_approved_notice_reaches_review_routing(self):
        approved = build_approved_notices(
            self.source, self.review
        )

        self.assertEqual(len(approved), 1)

        # Preserve the approved house identifier.
        self.assertEqual(
            approved[0]["house_number"], "101"
        )

        # A single identifier without trusted geography
        # cannot produce HIGH confidence.
        payload = build_matcher_results(
            approved,
            self.properties,
            {"NOTICE001": "notice001.txt"},
            self.root,
        )

        self.assertEqual(
            payload["matches"][0]["confidence"],
            "MEDIUM",
        )

        routed = route_matches(payload)

        self.assertEqual(
            routed[0]["routing_action"],
            "PENDING_REVIEW",
        )
        self.assertFalse(routed[0]["whatsapp_sent"])

    def test_missing_text_file_mapping_is_rejected(self):
        approved = build_approved_notices(
            self.source, self.review
        )

        with self.assertRaises(ValueError):
            build_matcher_results(
                approved,
                self.properties,
                {},
                self.root,
            )


if __name__ == "__main__":
    unittest.main()
