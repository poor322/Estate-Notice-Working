import unittest

from alerting.review_to_matcher import build_approved_notices


class TestReviewToMatcher(unittest.TestCase):

    def setUp(self):
        self.source = [{
            "id": "TEST-NOTICE-001",
            "content_hash": "testhash001",
            "source_image": "test_notice.png",
            "ocr_text": "Transfer of ownership of H.No. 101.",
            "survey_number": "",
            "plot_number": "",
        }]

        self.review = [{
            "notice_id": "TEST-NOTICE-001",
            "content_hash": "testhash001",
            "review_decision": "PENDING",
            "extraction_status": "SUBJECT_CANDIDATE_REVIEW",
            "approved_house_number": "",
            "approved_by": "",
            "approved_at": "",
        }]

    def test_pending_is_excluded(self):
        result = build_approved_notices(
            self.source, self.review
        )
        self.assertEqual(result, [])

    def test_rejected_is_excluded(self):
        self.review[0]["review_decision"] = "REJECTED"

        result = build_approved_notices(
            self.source, self.review
        )
        self.assertEqual(result, [])

    def test_approved_is_accepted(self):
        self.review[0].update({
            "review_decision": "APPROVED",
            "approved_house_number": "101",
            "approved_by": "test-reviewer",
            "approved_at": "2026-10-23T12:00:00",
        })

        result = build_approved_notices(
            self.source, self.review
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["house_number"], "101")

    def test_wrong_hash_is_rejected(self):
        self.review[0].update({
            "review_decision": "APPROVED",
            "content_hash": "wronghash",
            "approved_house_number": "101",
            "approved_by": "test-reviewer",
            "approved_at": "2026-10-23T12:00:00",
        })

        with self.assertRaises(ValueError):
            build_approved_notices(self.source, self.review)

    def test_missing_reviewer_is_rejected(self):
        self.review[0].update({
            "review_decision": "APPROVED",
            "approved_house_number": "101",
            "approved_by": "",
            "approved_at": "2026-10-23T12:00:00",
        })

        with self.assertRaises(ValueError):
            build_approved_notices(self.source, self.review)

    def test_missing_identifier_is_rejected(self):
        self.review[0].update({
            "review_decision": "APPROVED",
            "extraction_status": "NO_IDENTIFIER",
            "approved_house_number": "101",
            "approved_by": "test-reviewer",
            "approved_at": "2026-10-23T12:00:00",
        })

        with self.assertRaises(ValueError):
            build_approved_notices(self.source, self.review)

    def test_duplicate_approved_notice_is_rejected(self):
        self.review[0].update({
            "review_decision": "APPROVED",
            "approved_house_number": "101",
            "approved_by": "test-reviewer",
            "approved_at": "2026-10-23T12:00:00",
        })

        with self.assertRaises(ValueError):
            build_approved_notices(
                self.source,
                [self.review[0], self.review[0].copy()],
            )


if __name__ == "__main__":
    unittest.main()
