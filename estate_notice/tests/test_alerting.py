
import tempfile
import unittest
from pathlib import Path

from estate_notice.utils.alerting import send_notice_alert
from estate_notice.utils.deduplication import NoticeDeduplicator


class TestAlerting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        registry = Path(self.temp_dir.name) / "registry.json"
        self.dedup = NoticeDeduplicator(registry)
        self.text = "Public Notice Survey 123"
        self.dedup.register(self.text)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_alert_is_recorded(self):
        result = send_notice_alert(self.text, self.dedup, lambda text: True)
        self.assertEqual(result, "sent")
        self.assertTrue(self.dedup.was_alerted(self.text))

    def test_failed_alert_can_be_retried(self):
        result = send_notice_alert(self.text, self.dedup, lambda text: False)
        self.assertEqual(result, "failed")
        self.assertTrue(self.dedup.needs_alert(self.text))

    def test_successful_alert_is_not_repeated(self):
        send_notice_alert(self.text, self.dedup, lambda text: True)
        result = send_notice_alert(self.text, self.dedup, lambda text: True)
        self.assertEqual(result, "not_pending")

    def test_sender_exception_leaves_notice_pending(self):
        def failing_sender(text):
            raise RuntimeError("Delivery failed")

        with self.assertRaises(RuntimeError):
            send_notice_alert(self.text, self.dedup, failing_sender)

        self.assertTrue(self.dedup.needs_alert(self.text))


if __name__ == "__main__":
    unittest.main()
