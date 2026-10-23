import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alerting.workflow import run_workflow


class TestAlertWorkflow(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.notices = self.base / "notices"
        self.notices.mkdir()

        (self.notices / "notice1.txt").write_text(
            "TEST PUBLIC NOTICE: Property 101.",
            encoding="utf-8",
        )

        self.matches = self.base / "matches.json"
        self.matches.write_text(json.dumps({
            "matches": [
                {
                    "property_id": "TEST001",
                    "notice_file": "notice1.txt",
                    "confidence": "HIGH",
                    "score": 95,
                },
                {
                    "property_id": "TEST002",
                    "notice_file": "notice2.txt",
                    "confidence": "MEDIUM",
                    "score": 40,
                },
                {
                    "property_id": "TEST003",
                    "notice_file": "notice3.txt",
                    "confidence": "NO_MATCH",
                    "score": 0,
                },
            ]
        }), encoding="utf-8")

        self.mappings = self.base / "mappings.json"
        self.mappings.write_text(json.dumps([
            {
                "property_id": "TEST001",
                "recipient_id": "RECIPIENT001",
                "verified": True,
            },
            {
                "property_id": "TEST002",
                "recipient_id": "RECIPIENT002",
                "verified": True,
            },
        ]), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_pipeline(self):
        return run_workflow(
            self.matches,
            self.mappings,
            self.notices,
            self.base / "registry.json",
            self.base / "alerts.db",
            self.base / "reviews.db",
            self.base / "results.json",
            "TEST-SOURCE-001",
            "test-reviewer",
        )

    def test_first_run(self):
        with patch("alerting.workflow.preview_messages") as preview:
            result = self.run_pipeline()

        self.assertEqual(result["total_matches"], 3)
        self.assertEqual(result["new_recipient_alerts"], 1)
        self.assertEqual(result["existing_recipient_alerts"], 0)
        preview.assert_called_once()

        with sqlite3.connect(self.base / "reviews.db") as db:
            rows = db.execute(
                "SELECT confidence, status FROM review_queue"
            ).fetchall()

        self.assertEqual(rows, [("MEDIUM", "PENDING")])

        with sqlite3.connect(self.base / "alerts.db") as db:
            rows = db.execute(
                "SELECT recipient_id, status FROM recipient_alerts"
            ).fetchall()

        self.assertEqual(rows, [("RECIPIENT001", "PENDING")])

    def test_repeat_run_does_not_duplicate(self):
        with patch("alerting.workflow.preview_messages"):
            first = self.run_pipeline()
            second = self.run_pipeline()

        self.assertEqual(first["new_recipient_alerts"], 1)
        self.assertEqual(second["new_recipient_alerts"], 0)
        self.assertEqual(second["existing_recipient_alerts"], 1)

        with sqlite3.connect(self.base / "reviews.db") as db:
            review_count = db.execute(
                "SELECT COUNT(*) FROM review_queue"
            ).fetchone()[0]

        with sqlite3.connect(self.base / "alerts.db") as db:
            alert_count = db.execute(
                "SELECT COUNT(*) FROM recipient_alerts"
            ).fetchone()[0]

        self.assertEqual(review_count, 1)
        self.assertEqual(alert_count, 1)

    def test_unverified_recipient_is_rejected(self):
        self.mappings.write_text(json.dumps([
            {
                "property_id": "TEST001",
                "recipient_id": "RECIPIENT001",
                "verified": False,
            },
            {
                "property_id": "TEST002",
                "recipient_id": "RECIPIENT002",
                "verified": True,
            },
        ]), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.run_pipeline()

        self.assertFalse((self.base / "alerts.db").exists())
        self.assertFalse((self.base / "reviews.db").exists())


if __name__ == "__main__":
    unittest.main()
