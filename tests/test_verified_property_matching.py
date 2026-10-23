import unittest

from alerting.registered_property_matcher import (
    match_registered_property,
)


class TestVerifiedPropertyMatching(unittest.TestCase):

    def setUp(self):
        self.property = {
            "property_id": "TEST-PROPERTY-001",
            "survey_number": "123/4",
            "plot_number": "45",
            "house_number": "101",
            "village": "Test Village",
            "city": "Test City",
        }

    def test_full_identifier_match(self):
        notice = {
            "survey_number": "123/4",
            "plot_number": "45",
            "house_number": "101",
            "village": "Test Village",
            "city": "Test City",
        }

        result = match_registered_property(
            notice, self.property
        )

        self.assertEqual(result["confidence"], "HIGH")

    def test_conflicting_identifiers(self):
        notice = {
            "survey_number": "999/9",
            "plot_number": "999",
            "house_number": "999",
            "village": "Other Village",
        }

        result = match_registered_property(
            notice, self.property
        )

        self.assertNotEqual(
            result["confidence"], "HIGH"
        )

    def test_partial_match_not_high(self):
        notice = {
            "survey_number": "123/4",
            "village": "Test Village",
        }

        result = match_registered_property(
            notice, self.property
        )

        self.assertNotEqual(
            result["confidence"], "HIGH"
        )


if __name__ == "__main__":
    unittest.main()
