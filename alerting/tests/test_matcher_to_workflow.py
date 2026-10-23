import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alerting.workflow import run_workflow


class TestMatcherToWorkflow(unittest.TestCase):

    def test_real_matcher_to_dry_run_alert(self):
        matcher_dir = (
            Path.home()
            / "Estate-Notice-Ismail-Matching"
            / "property_matching"
        )
        if not (matcher_dir / "property_matcher.py").is_file():
            self.skipTest(
                "Ismail matcher worktree is unavailable; "
                "cross-repository integration not tested"
            )

        sys.path.insert(0, str(matcher_dir))
        try:
            from property_matcher import match_property
        finally:
            sys.path.remove(str(matcher_dir))

        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            notices_dir = base / "notices"
            notices_dir.mkdir()

            (notices_dir / "notice1.txt").write_text(
                "TEST PUBLIC NOTICE: Property 101, Delhi.",
                encoding="utf-8",
            )

            property_record = {
                "property_id": "TEST001",
                "property_number": "101",
                "village": "Delhi",
                "tehsil": "Delhi",
                "mustatil_number": "",
                "killa_number": "",
                "address": "Property 101 Delhi",
                "owner_name": "Test Owner",
            }

            notice = {
                "source_file": "notice1.txt",
                "property_number": "101",
                "village": "Delhi",
                "tehsil": "Delhi",
                "mustatil_numbers": [],
                "killa_numbers": [],
                "property_address": "Property 101 Delhi",
                "owner_names": ["Test Owner"],
                "seller_names": [],
            }

            match = match_property(property_record, notice)
            self.assertEqual(match["confidence"], "HIGH")

            matches_file = base / "matches.json"
            matches_file.write_text(
                json.dumps({
                    "total_comparisons": 1,
                    "matches": [match],
                }),
                encoding="utf-8",
            )

            mappings_file = base / "mappings.json"
            mappings_file.write_text(
                json.dumps([{
                    "property_id": "TEST001",
                    "recipient_id": "TEST_RECIPIENT_001",
                    "verified": True,
                }]),
                encoding="utf-8",
            )

            args = (
                matches_file,
                mappings_file,
                notices_dir,
                base / "registry.json",
                base / "alerts.db",
                base / "reviews.db",
                base / "results.json",
                "TEST-SOURCE-001",
                "test-reviewer",
            )

            with patch("alerting.workflow.preview_messages") as preview:
                first = run_workflow(*args)
                second = run_workflow(*args)

            self.assertEqual(first["new_recipient_alerts"], 1)
            self.assertEqual(second["new_recipient_alerts"], 0)
            self.assertEqual(second["existing_recipient_alerts"], 1)
            self.assertEqual(preview.call_count, 2)

            with sqlite3.connect(base / "alerts.db") as db:
                count = db.execute(
                    "SELECT COUNT(*) FROM recipient_alerts"
                ).fetchone()[0]

            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
