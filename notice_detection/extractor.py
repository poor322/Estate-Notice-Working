import re


def extract_notice_details(text):
	text = text.strip()

	# ---------------------------------------------------------
	# SURVEY NUMBER
	# Only extract when "survey no", "survey number",
	# "sy no" or "sy. no." is explicitly present.
	# ---------------------------------------------------------

	survey_match = re.search(
		r"\b(?:survey\s*(?:no|number)|sy\.?\s*no\.?)"
		r"\s*[:\-]?\s*([A-Za-z0-9]+(?:[\/\-][A-Za-z0-9]+)*)",
		text,
		re.IGNORECASE,
	)

	if survey_match:
		survey_number = survey_match.group(1)
	else:
		survey_number = None

	# ---------------------------------------------------------
	# PLOT NUMBER
	# ---------------------------------------------------------

	plot_match = re.search(
		r"\bplot\s*(?:no|number)"
		r"\s*[:\-]?\s*([A-Za-z0-9]+(?:[\/\-][A-Za-z0-9]+)*)",
		text,
		re.IGNORECASE,
	)

	if plot_match:
		plot_number = plot_match.group(1)
	else:
		plot_number = None

	# ---------------------------------------------------------
	# PROPERTY NUMBER
	# ---------------------------------------------------------

	property_match = re.search(
		r"\bproperty\s*(?:no|number)"
		r"\s*[:\-]?\s*([A-Za-z0-9]+(?:[\/\-][A-Za-z0-9]+)*)",
		text,
		re.IGNORECASE,
	)

	if property_match:
		property_number = property_match.group(1)
	else:
		property_number = None

	# ---------------------------------------------------------
	# LOCATION
	# ---------------------------------------------------------

	location_match = re.search(
		r"\b(?:situated at|located at|situated in|located in)"
		r"\s+([A-Za-z][A-Za-z0-9 ,\-]*?)"
		r"(?=\s+(?:is|and|which|where|proposed|for|shall|will)\b|[.;,\n]|$)",
		text,
		re.IGNORECASE,
	)

	if location_match:
		location = location_match.group(1).strip()
	else:
		location = None

	# ---------------------------------------------------------
	# PHONE NUMBER
	# ---------------------------------------------------------

	phone_match = re.search(r"\b[6-9]\d{9}\b", text)

	if phone_match:
		phone = phone_match.group()
	else:
		phone = None

	# ---------------------------------------------------------
	# EMAIL
	# ---------------------------------------------------------

	email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)

	if email_match:
		email = email_match.group()
	else:
		email = None

	return {
		"survey_number": survey_number,
		"plot_number": plot_number,
		"property_number": property_number,
		"location": location,
		"phone": phone,
		"email": email,
	}
