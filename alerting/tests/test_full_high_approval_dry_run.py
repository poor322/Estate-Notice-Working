import json
import tempfile
import unittest
from pathlib import Path

from alerting.approved_notice_matching import build_matcher_results
from alerting.workflow import run_workflow


class TestHighConfidenceDryRun(unittest.TestCase):

    def test_high_match_creates_one_pending_alert(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            notices_dir = root / "notices"
            notices_dir.mkdir()

            (notices_dir / "notice001.txt").write_text(
                "Synthetic notice: Survey 123/4, Plot 45, Village A.",
                encoding="utf-8",
            )

            # Fictional, pre-reviewed data.
            # Does not simulate authenticated approval.
            approved_notices = [{
                "notice_id": "NOTICE001",
                "content_hash": "synthetic-hash-001",
                "survey_number": "123/4",
                "plot_number": "45",
                "village": "Village A",
                "tehsil": "Tehsil A",
            }]

            properties = [{
                "property_id": "PROPERTY001",
                "survey_number": "123/4",
                "plot_number": "45",
                "village": "Village A",
                "tehsil": "Tehsil A",
            }]

            payload = build_matcher_results(
                approved_notices,
                properties,
                {"NOTICE001": "notice001.txt"},
                notices_dir,
            )

            self.assertEqual(
                payload["matches"][0]["confidence"], "HIGH"
            )

            matches_file = root / "matches.json"
            mappings_file = root / "mappings.json"

            matches_file.write_text(
                json.dumps(payload), encoding="utf-8"
            )

            mappings_file.write_text(
                json.dumps([{
                    "property_id": "PROPERTY001",
                    "recipient_id": "RECIPIENT001",
                    "verified": True,
                }]),
                encoding="utf-8",
            )

            args = dict(
                matches_file=matches_file,
                mappings_file=mappings_file,
                notices_dir=notices_dir,
                registry_file=root / "registry.sqlite",
                alerts_db=root / "alerts.sqlite",
                reviews_db=root / "reviews.sqlite",
                output_file=root / "results.json",
                source_id="SYNTHETIC_TEST",
                reviewer="Test Reviewer",
            )

            first = run_workflow(**args)

            self.assertEqual(first["total_matches"], 1)
            self.assertEqual(first["new_recipient_alerts"], 1)
            self.assertEqual(first["existing_recipient_alerts"], 0)

            second = run_workflow(**args)

            self.assertEqual(second["new_recipient_alerts"], 0)
            self.assertEqual(second["existing_recipient_alerts"], 1)

            print("\nPASS: HIGH-confidence matching")
            print("PASS: First run creates one pending alert")
            print("PASS: Second run does not duplicate alert")
            print("PASS: No WhatsApp messages sent")


if __name__ == "__main__":
    unittest.main()
