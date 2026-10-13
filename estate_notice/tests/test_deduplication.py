import tempfile
import unittest
from pathlib import Path

from estate_notice.utils.deduplication import NoticeDeduplicator


class TestNoticeDeduplicator(unittest.TestCase):
	def setUp(self):
		self.temp_dir = tempfile.TemporaryDirectory()
		self.registry = Path(self.temp_dir.name) / "registry.json"
		self.dedup = NoticeDeduplicator(self.registry)

	def tearDown(self):
		self.temp_dir.cleanup()

	def test_new_notice(self):
		self.assertTrue(self.dedup.register("Public notice survey 123"))

	def test_duplicate_notice(self):
		text = "Public notice survey 123"
		self.assertTrue(self.dedup.register(text))
		self.assertFalse(self.dedup.register(text))

	def test_normalized_text(self):
		self.dedup.register("Public Notice Survey 123")
		self.assertTrue(self.dedup.is_duplicate(" PUBLIC   NOTICE SURVEY 123 "))

	def test_persistence_after_restart(self):
		text = "Public notice survey 456"
		self.dedup.register(text)
		restarted = NoticeDeduplicator(self.registry)
		self.assertTrue(restarted.is_duplicate(text))

	def test_alert_status(self):
		text = "Public notice survey 789"
		self.dedup.register(text)
		self.dedup.mark_alerted(text)
		restarted = NoticeDeduplicator(self.registry)
		self.assertTrue(restarted.was_alerted(text))

	def test_alert_not_sent_before_marking(self):
		text = "Public notice survey 101"
		self.dedup.register(text)
		self.assertFalse(self.dedup.was_alerted(text))

	def test_duplicate_registration_preserves_alert_status(self):
		text = "Public notice survey 102"
		self.dedup.register(text)
		self.dedup.mark_alerted(text)

		self.assertFalse(self.dedup.register(text))
		self.assertTrue(self.dedup.was_alerted(text))

	def test_empty_text(self):
		with self.assertRaises(ValueError):
			self.dedup.register("   ")

	def test_unalerted_notice_can_be_retried(self):
		text = "Public notice survey 103"
		self.dedup.register(text)
		self.assertTrue(self.dedup.needs_alert(text))

		# Before a successful alert, it remains unalerted.
		self.assertFalse(self.dedup.was_alerted(text))

		# After a successful alert, it must not be alerted again.
		self.dedup.mark_alerted(text)
		self.assertFalse(self.dedup.needs_alert(text))
		self.assertTrue(self.dedup.was_alerted(text))


if __name__ == "__main__":
	unittest.main()
