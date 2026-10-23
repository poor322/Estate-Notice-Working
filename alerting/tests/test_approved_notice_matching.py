import tempfile
import unittest
from pathlib import Path

from alerting.approved_notice_matching import build_matcher_results
from alerting.alert_router import route_matches


class TestApprovedNoticeMatching(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)
        (self.root / "notice.txt").write_text(
            "Synthetic property notice",
            encoding="utf-8",
        )

        self.notice = {
            "notice_id": "NOTICE001",
            "content_hash": "hash001",
            "survey_number": "123/4",
            "plot_number": "45",
            "village": "Village A",
            "tehsil": "Tehsil A",
        }

        self.property = {
            "property_id": "PROPERTY001",
            "survey_number": "123/4",
            "plot_number": "45",
            "village": "Village A",
            "tehsil": "Tehsil A",
        }

    def build(self, notices=None, properties=None, mapping=None):
        return build_matcher_results(
            [self.notice] if notices is None else notices,
            [self.property] if properties is None else properties,
            {"NOTICE001": "notice.txt"} if mapping is None else mapping,
            self.root,
        )

    def test_valid_high_match_and_routing(self):
        payload = self.build()

        self.assertEqual(payload["total_comparisons"], 1)
        match = payload["matches"][0]
        self.assertEqual(match["confidence"], "HIGH")
        self.assertEqual(match["notice_id"], "NOTICE001")
        self.assertEqual(match["content_hash"], "hash001")
        self.assertEqual(match["notice_file"], "notice.txt")
        self.assertTrue(match["reasons"])
        self.assertIsInstance(match["score"], int)

        routed = route_matches(payload)
        self.assertFalse(routed[0]["whatsapp_sent"])

    def test_missing_file_mapping_rejected(self):
        with self.assertRaises(ValueError):
            self.build(mapping={})

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.build(mapping={"NOTICE001": "../outside.txt"})

    def test_image_not_accepted_as_text(self):
        (self.root / "notice.png").write_bytes(b"fake image")
        with self.assertRaises(ValueError):
            self.build(mapping={"NOTICE001": "notice.png"})

    def test_duplicate_properties_rejected(self):
        with self.assertRaises(ValueError):
            self.build(properties=[self.property, dict(self.property)])

    def test_duplicate_notices_rejected(self):
        with self.assertRaises(ValueError):
            self.build(notices=[self.notice, dict(self.notice)])

    def test_conflicting_geography_never_high(self):
        notice = dict(self.notice)
        notice["village"] = "Village B"

        payload = self.build(notices=[notice])
        match = payload["matches"][0]

        self.assertEqual(match["confidence"], "MEDIUM")
        self.assertLessEqual(match["score"], 49)
        self.assertTrue(
            any("Geographic conflict" in r for r in match["reasons"])
        )

    def test_no_registered_properties(self):
        payload = self.build(properties=[])
        self.assertEqual(payload["total_comparisons"], 0)
        self.assertEqual(payload["matches"], [])

    def test_missing_notice_hash_rejected(self):
        notice = dict(self.notice)
        notice["content_hash"] = ""
        with self.assertRaises(ValueError):
            self.build(notices=[notice])


if __name__ == "__main__":
    unittest.main()
