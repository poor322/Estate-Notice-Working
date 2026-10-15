
import tempfile
import unittest
from pathlib import Path

from estate_notice.utils.alerting import (
    process_pending_alerts,
    send_notice_alert,
)
from estate_notice.utils.deduplication import NoticeDeduplicator


class TestAlerting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dedup = NoticeDeduplicator(
            Path(self.temp_dir.name) / "registry.json"
        )
        self.text = "Public Notice Survey 123"
        self.dedup.register(self.text)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_alert(self):
        result = send_notice_alert(self.text, self.dedup, lambda text: True)
        self.assertEqual(result, "sent")
        self.assertTrue(self.dedup.was_alerted(self.text))

    def test_failed_alert_can_retry(self):
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

    def test_process_pending_alerts(self):
        other_text = "Public Notice Plot 456"
        sender_calls = []

        def mock_sender(text):
            sender_calls.append(text)
            return True

        results = process_pending_alerts(
            [{"text": self.text}, {"text": other_text}],
            self.dedup,
            mock_sender,
        )

        self.assertEqual(results, ["sent", "not_registered"])
        self.assertEqual(sender_calls, [self.text])
        self.assertTrue(self.dedup.was_alerted(self.text))
        self.assertFalse(self.dedup.is_duplicate(other_text))



if __name__ == "__main__":
    unittest.main()
