import unittest

from alerting.registered_property_matcher import (
    match_registered_property,
)


class TestRegisteredPropertyMatcher(unittest.TestCase):

    def setUp(self):
        self.registered = {
            "property_id": "TEST001",
            "survey_number": "123/4",
            "plot_number": "45",
            "house_number": "101",
            "owner_name": "Test Owner",
        }

    def match(self, notice):
        return match_registered_property(
            notice, self.registered
        )

    def test_two_identifiers_high(self):
        result = self.match({
            "survey_number": "123/4",
            "plot_number": "45",
        })
        self.assertEqual(result["confidence"], "HIGH")

    def test_one_identifier_medium(self):
        result = self.match({"house_number": "101"})
        self.assertEqual(result["confidence"], "MEDIUM")

    def test_conflicting_survey_never_high(self):
        result = self.match({
            "survey_number": "999",
            "plot_number": "45",
            "house_number": "101",
        })
        self.assertNotEqual(result["confidence"], "HIGH")
        self.assertIn(
            "survey_number",
            result["conflicting_fields"],
        )

    def test_owner_only_no_match(self):
        result = self.match({
            "owner_name": "Test Owner",
        })
        self.assertEqual(result["confidence"], "NO_MATCH")

    def test_no_matching_identifier(self):
        result = self.match({"house_number": "999"})
        self.assertEqual(result["confidence"], "NO_MATCH")

    def test_identifier_types_not_interchangeable(self):
        result = self.match({
            "house_number": "45",
            "plot_number": "101",
        })
        self.assertEqual(result["confidence"], "NO_MATCH")

    def test_normalization(self):
        result = self.match({
            "survey_number": " 123 / 4 ",
            "plot_number": " 45 ",
        })
        self.assertEqual(result["confidence"], "HIGH")

    def test_missing_property_id_rejected(self):
        registered = dict(self.registered)
        registered["property_id"] = ""

        with self.assertRaises(ValueError):
            match_registered_property(
                {"house_number": "101"},
                registered,
            )

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            match_registered_property(
                "not a notice", self.registered
            )


if __name__ == "__main__":
    unittest.main()
