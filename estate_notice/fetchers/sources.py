"""Which newspapers and dates the automatic downloader can fetch."""

FETCHABLE_NEWSPAPERS = ("Hindustan Times Delhi",)


def check_fetch_supported(newspaper, edition_date, today):
	"""Raise ValueError with a user-facing message if the edition can't be downloaded.

	InduPaper only offers the current edition and the fetcher only knows the
	Hindustan Times Delhi page, so anything else has to be uploaded as a PDF.
	"""
	if newspaper not in FETCHABLE_NEWSPAPERS:
		raise ValueError(
			f"Automatic download is only available for {', '.join(FETCHABLE_NEWSPAPERS)}. "
			f"Attach the {newspaper} PDF in Upload PDF to process it."
		)

	if edition_date != today:
		raise ValueError(
			f"Automatic download only fetches today's edition ({today}). "
			f"Attach the {edition_date} PDF in Upload PDF to process that edition."
		)
