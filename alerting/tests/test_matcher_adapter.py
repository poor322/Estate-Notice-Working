import math
import tempfile
import unittest
from pathlib import Path

from alerting.matcher_adapter import validate_matcher_results


class TestMatcherAdapter(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "notice1.txt").write_text(
            "TEST PUBLIC NOTICE", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def make_match(self, **changes):
        item = {
            "property_id": "TEST001",
            "notice_file": "notice1.txt",
            "confidence": "HIGH",
            "score": 95,
            "reasons": ["Exact property number match"],
        }
        item.update(changes)
        return item

    def validate(self, matches):
        return validate_matcher_results(
            {
                "total_comparisons": len(matches),
                "matches": matches,
            },
            self.root,
        )

    def test_valid_high_match(self):
        result = self.validate([self.make_match()])
        match = result["matches"][0]
        self.assertEqual(match["confidence"], "HIGH")
        self.assertEqual(match["score"], 95)
        self.assertEqual(
            match["reasons"], ["Exact property number match"]
        )

    def test_valid_medium_match(self):
        result = self.validate([
            self.make_match(confidence="medium", score=35)
        ])
        self.assertEqual(
            result["matches"][0]["confidence"], "MEDIUM"
        )

    def test_no_match(self):
        result = self.validate([
            self.make_match(
                confidence="NO_MATCH",
                score=0,
                notice_file=None,
                reasons=[],
            )
        ])
        self.assertEqual(len(result["matches"]), 1)

    def test_missing_property_id(self):
        with self.assertRaises(ValueError):
            self.validate([self.make_match(property_id="")])

    def test_invalid_confidence(self):
        with self.assertRaises(ValueError):
            self.validate([
                self.make_match(confidence="UNKNOWN")
            ])

    def test_invalid_score(self):
        for score in (-1, 201, True, "95", math.nan):
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    self.validate([
                        self.make_match(score=score)
                    ])

    def test_missing_notice_file(self):
        with self.assertRaises(ValueError):
            self.validate([
                self.make_match(notice_file="missing.txt")
            ])

    def test_path_traversal(self):
        with self.assertRaises(ValueError):
            self.validate([
                self.make_match(notice_file="../outside.txt")
            ])

    def test_absolute_path(self):
        with self.assertRaises(ValueError):
            self.validate([
                self.make_match(
                    notice_file=str(self.root / "notice1.txt")
                )
            ])

    def test_incorrect_total_comparisons(self):
        with self.assertRaises(ValueError):
            validate_matcher_results(
                {
                    "total_comparisons": 2,
                    "matches": [self.make_match()],
                },
                self.root,
            )


if __name__ == "__main__":
    unittest.main()
