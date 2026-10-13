import hashlib
import json
import re
from pathlib import Path


class NoticeDeduplicator:
	"""Identify previously processed notices using persistent fingerprints."""

	def __init__(self, registry_path):
		self.registry_path = Path(registry_path)
		self.registry_path.parent.mkdir(parents=True, exist_ok=True)
		self.registry = self._load_registry()

	def _load_registry(self):
		if not self.registry_path.exists():
			return {"notices": {}}

		try:
			data = json.loads(self.registry_path.read_text(encoding="utf-8"))
			if isinstance(data, dict) and isinstance(data.get("notices"), dict):
				return data
		except (json.JSONDecodeError, OSError):
			raise RuntimeError(f"Cannot safely read deduplication registry: {self.registry_path}")

		raise RuntimeError("Invalid deduplication registry format")

	@staticmethod
	def fingerprint(text):
		"""Create a stable hash from normalized notice text."""
		normalized = re.sub(r"\s+", " ", text).strip().casefold()

		if not normalized:
			raise ValueError("Notice text cannot be empty")

		return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

	def is_duplicate(self, text):
		"""Return True if this notice has already been registered."""
		return self.fingerprint(text) in self.registry["notices"]

	def register(self, text):
		"""Register a new notice. Return False if it already exists."""
		fingerprint = self.fingerprint(text)

		if fingerprint in self.registry["notices"]:
			return False

		self.registry["notices"][fingerprint] = {"status": "processed"}

		self._save_registry()
		return True

	def mark_alerted(self, text):
		"""Mark a notice alerted only after its alert succeeds."""
		fingerprint = self.fingerprint(text)

		if fingerprint not in self.registry["notices"]:
			raise KeyError("Notice must be registered before marking alerted")

		self.registry["notices"][fingerprint]["status"] = "alerted"
		self._save_registry()

	def was_alerted(self, text):
		"""Check whether an alert was previously recorded."""
		fingerprint = self.fingerprint(text)
		notice = self.registry["notices"].get(fingerprint)
		return notice is not None and notice.get("status") == "alerted"

	def needs_alert(self, text):
		"""Return True when a registered notice has not been alerted."""
		fingerprint = self.fingerprint(text)
		notice = self.registry["notices"].get(fingerprint)
		return notice is not None and notice.get("status") != "alerted"

	def _save_registry(self):
		temporary_path = self.registry_path.with_suffix(".tmp")
		temporary_path.write_text(
			json.dumps(self.registry, indent=2, ensure_ascii=False),
			encoding="utf-8",
		)
		temporary_path.replace(self.registry_path)
