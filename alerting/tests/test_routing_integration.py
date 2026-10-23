import tempfile
import unittest
from pathlib import Path

from alerting.alert_router import route_matches
from alerting.recipient_mapping import attach_recipients
from alerting.dedup_check import check_deduplication


class TestRoutingIntegration(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.notices_dir = self.root / "notices"
        self.notices_dir.mkdir()

        (self.notices_dir / "notice1.txt").write_text(
            "Public notice for property 101",
            encoding="utf-8"
        )

        self.registry = self.root / "registry.json"

        self.matches = {
            "matches": [
                {
                    "property_id": "TEST001",
                    "notice_file": "notice1.txt",
                    "confidence": "HIGH",
                    "score": 95
                },
                {
                    "property_id": "TEST002",
                    "notice_file": "notice2.txt",
                    "confidence": "MEDIUM",
                    "score": 45
                },
                {
                    "property_id": "TEST003",
                    "notice_file": "notice3.txt",
                    "confidence": "NO_MATCH",
                    "score": 0
                }
            ]
        }

        self.mappings = [
            {
                "property_id": "TEST001",
                "recipient_id": "RECIPIENT001",
                "verified": True
            },
            {
                "property_id": "TEST002",
                "recipient_id": "RECIPIENT002",
                "verified": True
            }
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_high_confidence(self):
        routed = route_matches(self.matches)

        high = next(
            m for m in routed if m["confidence"] == "HIGH"
        )

        self.assertEqual(
            high["routing_action"],
            "READY_FOR_DEDUP_CHECK"
        )

    def test_medium_confidence(self):
        routed = route_matches(self.matches)

        medium = next(
            m for m in routed if m["confidence"] == "MEDIUM"
        )

        self.assertEqual(
            medium["routing_action"],
            "PENDING_REVIEW"
        )

    def test_no_match(self):
        routed = route_matches(self.matches)

        no_match = next(
            m for m in routed if m["confidence"] == "NO_MATCH"
        )

        self.assertEqual(
            no_match["routing_action"],
            "LOG_ONLY"
        )

    def test_recipient_mapping(self):
        routed = {
            "routed_matches": route_matches(self.matches)
        }

        mapped = attach_recipients(routed, self.mappings)

        high = next(
            m for m in mapped["routed_matches"]
            if m["confidence"] == "HIGH"
        )

        self.assertEqual(
            high["recipient_id"],
            "RECIPIENT001"
        )

    def test_deduplication(self):
        routed = {
            "routed_matches": route_matches(self.matches)
        }

        mapped = attach_recipients(routed, self.mappings)

        results = check_deduplication(
            mapped,
            self.notices_dir,
            self.registry
        )

        high = next(
            m for m in results if m["confidence"] == "HIGH"
        )

        self.assertEqual(
            high["dedup_status"],
            "NEW_NOTICE"
        )

        self.assertTrue(high["alert_eligible"])


if __name__ == "__main__":
    unittest.main()
