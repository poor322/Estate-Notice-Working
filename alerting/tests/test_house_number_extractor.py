import unittest

from alerting.house_number_extractor import extract_house_number


class TestHouseNumberExtractor(unittest.TestCase):

    def test_subject_house_number(self):
        text = (
            "Transfer of ownership in respect of "
            "H.No. 1-A/174, Faridabad."
        )
        result = extract_house_number(text)

        self.assertEqual(result["house_number"], "1-A/174")
        self.assertEqual(
            result["status"], "SUBJECT_CANDIDATE_REVIEW"
        )

    def test_house_number_without_space(self):
        text = (
            "Transfer of ownership in respect "
            "H.No.841, Sector-7C."
        )
        result = extract_house_number(text)

        self.assertEqual(result["house_number"], "841")

    def test_subject_and_residential_address(self):
        text = (
            "Transfer of ownership in respect of H.No. 267. "
            "Applicant R/o H.No. 46, Faridabad."
        )
        result = extract_house_number(text)

        self.assertEqual(result["house_number"], "267")

    def test_residential_address_only(self):
        text = "Applicant R/o H.No. 406, Faridabad."
        result = extract_house_number(text)

        self.assertIsNone(result["house_number"])
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_no_identifier(self):
        result = extract_house_number(
            "Public notice regarding legal proceedings."
        )

        self.assertIsNone(result["house_number"])
        self.assertEqual(result["status"], "NO_IDENTIFIER")

    def test_property_keyword_followed_by_residence(self):
        text = (
            "This property notice is issued by the applicant "
            "R/o H.No. 46, Faridabad."
        )
        result = extract_house_number(text)

        self.assertIsNone(
            result["house_number"],
            "Residential address must not become subject property"
        )


    def test_conflicting_subject_properties(self):
        text = (
            "Transfer of ownership in respect of H.No. 100. "
            "Transfer of ownership in respect of H.No. 200."
        )
        result = extract_house_number(text)

        self.assertIsNone(result["house_number"])
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_subject_property_with_residential_address(self):
        text = (
            "Transfer of ownership in respect of H.No. 267. "
            "Applicant residing at H.No. 46."
        )
        result = extract_house_number(text)

        self.assertEqual(result["house_number"], "267")
        self.assertEqual(
            result["status"], "SUBJECT_CANDIDATE_REVIEW"
        )

    def test_unrelated_property_phrase_and_residence(self):
        text = (
            "Property ownership notice issued to applicant. "
            "Applicant residing at H.No. 46."
        )
        result = extract_house_number(text)

        self.assertIsNone(result["house_number"])
        self.assertEqual(result["status"], "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
