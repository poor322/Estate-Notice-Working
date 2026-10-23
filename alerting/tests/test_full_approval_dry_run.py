import json
import tempfile
import unittest
from pathlib import Path

from alerting.review_to_matcher import build_approved_notices
from alerting.approved_notice_matching import build_matcher_results
from alerting.workflow import run_workflow


class TestFullApprovalDryRun(unittest.TestCase):

    def test_approved_notice_to_review_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            notices_dir = root / "notices"
            notices_dir.mkdir()

            (notices_dir / "notice001.txt").write_text(
                "Public notice concerning House No. 101.",
                encoding="utf-8",
            )

            source = [{
                "id": "NOTICE001",
                "content_hash": "synthetic-hash-001",
                "source_image": "newspaper_crop.png",
                "ocr_text": "Public notice concerning House No. 101.",
                "house_number": "101",
                "survey_number": "",
                "plot_number": "",
            }]

            reviews = [{
                "notice_id": "NOTICE001",
                "content_hash": "synthetic-hash-001",
                "review_decision": "APPROVED",
                "approved_house_number": "101",
                "approved_by": "Test Reviewer",
                "approved_at": "2026-10-23T10:00:00",
                "extraction_status": "SUBJECT_CANDIDATE_REVIEW",
            }]

            properties = [{
                "property_id": "PROPERTY001",
                "house_number": "101",
                "village": "Village A",
            }]

            approved = build_approved_notices(source, reviews)
            self.assertEqual(len(approved), 1)

            payload = build_matcher_results(
                approved,
                properties,
                {"NOTICE001": "notice001.txt"},
                notices_dir,
            )

            # One identifier, without trusted geography:
            # this must NOT create a HIGH-confidence alert.
            self.assertEqual(
                payload["matches"][0]["confidence"],
                "MEDIUM",
            )

            matches_file = root / "matches.json"
            mappings_file = root / "mappings.json"

            matches_file.write_text(
                json.dumps(payload),
                encoding="utf-8",
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
                output_file=root / "result.json",
                source_id="SYNTHETIC_TEST",
                reviewer="Test Reviewer",
            )

            first = run_workflow(**args)

            self.assertEqual(first["total_matches"], 1)
            self.assertEqual(first["new_recipient_alerts"], 0)

            second = run_workflow(**args)

            self.assertEqual(second["new_recipient_alerts"], 0)

            self.assertTrue((root / "result.json").is_file())


if __name__ == "__main__":
    unittest.main()
