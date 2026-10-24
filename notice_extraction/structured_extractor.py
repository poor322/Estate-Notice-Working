import argparse
import json
import re
from pathlib import Path


def unique(values):
	result = []

	for value in values:
		value = value.strip()

		if value and value not in result:
			result.append(value)

	return result


def compact(text):
	return re.sub(r"\s+", " ", text).strip()


def classify_property_notice(text):
	lower = text.lower()

	strong_keywords = [
		"property",
		"land",
		"title document",
		"sale deed",
		"conveyance deed",
		"sub-registrar",
		"mustatil",
		"killa",
		"survey",
		"plot",
		"mortgage",
		"encumbrance",
		"seller",
		"purchaser",
	]

	matched = [keyword for keyword in strong_keywords if keyword in lower]

	numbered_property = bool(
		re.search(
			r"\b(?:H\.?\s*No\.?|House\s+No\.?|Plot\s+No\.?|Property\s+(?:ID\s+)?No\.?)",
			text,
			re.IGNORECASE,
		)
	)

	inheritance_signal = any(
		phrase in lower
		for phrase in [
			"legal heir",
			"legal heirs",
			"inheritance",
			"transfer of ownership",
		]
	)

	property_related = (
		(numbered_property and inheritance_signal)
		or len(matched) >= 2
		or (
			"property" in lower
			and any(
				word in lower
				for word in [
					"sale",
					"transfer",
					"title",
					"mortgage",
					"encumbrance",
				]
			)
		)
		or (
			"land" in lower
			and any(
				word in lower
				for word in [
					"sale",
					"purchase",
					"seller",
					"killa",
					"mustatil",
				]
			)
		)
	)

	return (
		"PROPERTY_RELEVANT" if property_related else "NOT_RELEVANT",
		matched,
	)


def extract_notice_type(text):
	if re.search(
		r"\bPUBLIC\s+NOTICE\b",
		text,
		re.IGNORECASE,
	):
		return "PUBLIC_NOTICE"

	if re.search(
		r"\bLEGAL\s+NOTICE\b",
		text,
		re.IGNORECASE,
	):
		return "LEGAL_NOTICE"

	if re.search(
		r"\bCOURT\s+NOTICE\b",
		text,
		re.IGNORECASE,
	):
		return "COURT_NOTICE"

	return "UNKNOWN"


def extract_transaction_type(text):
	lower = text.lower()

	if (
		any(
			word in lower
			for word in [
				"lost",
				"misplaced",
				"untraceable",
			]
		)
		and "document" in lower
	):
		return "LOST_TITLE_DOCUMENTS"

	if (
		"agreed to purchase" in lower
		or "proposed purchase" in lower
		or "sale deed" in lower
		or "proposed sale" in lower
	):
		return "SALE_PURCHASE"

	if "mortgage" in lower:
		return "MORTGAGE_RELATED"

	if "transfer" in lower:
		return "PROPERTY_TRANSFER"

	return "OTHER_PROPERTY_NOTICE"


def extract_property_address(text):
	clean = compact(text)

	patterns = [
		r"(?:in\s+)?respect(?:\s+of)?\s+"
		+ r"((?:H\.?\s*No\.?|House\s+No\.?|Plot\s+No\.?).+?)"
		+ r"(?=(?:,\s*)?(?:in\s+respect|after\s+death|100%\s+share|intestate\s+death)\b|[.;])",
		r"(Plot\s+No\.?\s*\d[A-Z0-9/-]*.+?)"
		+ r"(?=,\s*has\s+been\s+(?:lost|misplaced)|\s+has\s+been\s+(?:lost|misplaced))",
		r"property\s+bearing\s+(.+?)(?=\(hereinafter|belonging\s+to|[.;])",
	]

	for pattern in patterns:
		match = re.search(pattern, clean, re.IGNORECASE)

		if match:
			return match.group(1).strip(" ,.;:-")

	return None


def extract_property_number(text):
	patterns = [
		r"\bH\.?\s*No\.?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
		r"\bHouse\s+No\.?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
		r"\bPlot\s+No\.?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
		r"\bProperty\s+(?:ID\s+)?No\.?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
		r"property\s+bearing\s+([A-Z0-9][A-Z0-9/-]*)",
	]

	for pattern in patterns:
		for match in re.finditer(pattern, text, re.IGNORECASE):
			value = match.group(1).strip()

			# Reject OCR/header words such as "Plot No. Letter".
			if not re.search(r"\d", value):
				continue

			return value

	return None


def extract_village(text):
	clean = compact(text)

	patterns = [
		r"\bVillage\s+([A-Za-z ]+?)(?=,\s*Tehsil|,|;|\()",
		r"\bVill[-.\s:]+([A-Za-z ]+?)(?=,|;|\()",
	]

	for pattern in patterns:
		match = re.search(pattern, clean, re.IGNORECASE)

		if match:
			return match.group(1).strip()

	return None


def extract_tehsil(text):
	clean = compact(text)

	match = re.search(
		r"\bTehsil\s+" + r"([A-Za-z ]+?)" + r"(?=,\s*(?:New Delhi|Delhi)|,|;)",
		clean,
		re.IGNORECASE,
	)

	if match:
		return match.group(1).strip()

	return None


def extract_owner_names(text):
	clean = compact(text)
	owners = []

	patterns = [
		r"(?:Late\s+)?Sh\.?\s+"
		+ r"([A-Za-z][A-Za-z .@'-]+?)"
		+ r"\s+(?:S/o|D/o|W/o)\b"
		+ r".+?\b(?:who\s+was|was)\s+the\s+owner",
		r"issued\s+in\s+the\s+name\s+of\s+" + r"(.+?)(?=,\s+having|\s+having)",
		r"\bmy[\s)\]}:,-]*"
		+ r"(?:mother|father|husband|wife)\s+"
		+ r"([A-Za-z][A-Za-z .'-]+?)"
		+ r"\s+(?:had\s+expired|has\s+died|died)",
	]

	for pattern in patterns:
		match = re.search(pattern, clean, re.IGNORECASE)

		if match:
			owners.append(match.group(1).strip(" ,.;"))

	return unique(owners)


def extract_legal_heirs(text):
	clean = compact(text)

	patterns = [
		r"leaving\s+behind\s+(?:the\s+following\s+)?legal\s+heirs?\s*:?\s*"
		+ r"(.+?)"
		+ r"(?=and\s+there\s+(?:is|are)\s+no\s+other\s+legal\s+heirs?"
		+ r"|If\s+any\s+person|Now,|Mother\s+Late)",
		r"leaving\s+behind\s+(.+?)" + r"\s+as\s+(?:her|his|their)\s+sole\s+legal\s+heirs?",
	]

	segment = None

	for pattern in patterns:
		match = re.search(pattern, clean, re.IGNORECASE)

		if match:
			segment = match.group(1)
			break

	if not segment:
		return []

	segment = segment.replace("\u2019", "'").replace("\u2018", "'")

	names = re.findall(
		r"(?:^|,\s*|\(\d+\)\s*)"
		r"(?:Sh\.?\s+|Smt\.?\s+|Mr\.?\s+|Ms\.?\s+)?"
		r"([A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){0,3})"
		r"\s*\)?\s*"
		r"\((?:son|daughter|wife|father|mother)\b[^)]*\)",
		segment,
		re.IGNORECASE,
	)

	return unique(names)


def extract_city(text):
	clean = compact(text)

	# Prefer the location appearing in the extracted property address.
	address = extract_property_address(text)

	cities = [
		"Faridabad",
		"Rewari",
		"New Delhi",
		"Gurugram",
		"Delhi",
	]

	if address:
		for city in cities:
			if re.search(rf"\b{re.escape(city)}\b", address, re.IGNORECASE):
				return city

	for city in cities:
		if re.search(rf"\b{re.escape(city)}\b", clean, re.IGNORECASE):
			return city

	return None


def extract_seller_names(text):
	clean = compact(text)

	names = re.findall(
		r"\[\d+\]\s*SHRI\s*"
		r"(.+?)"
		r"(?=,\s*S/o)",
		clean,
		re.IGNORECASE,
	)

	return unique(names)


def extract_mustatil_numbers(text):
	values = re.findall(
		r"Mustatil\s+No\.?\s*(\d+)",
		text,
		re.IGNORECASE,
	)

	return unique(values)


def extract_killa_numbers(text):
	values = re.findall(
		r"\b(\d+(?:/\d+)?)"
		r"\s*\(\s*\d+\s*-\s*\d+\s*\)",
		text,
	)

	return unique(values)


def extract_document_numbers(text):
	patterns = [
		r"\bDOCUMENT\s+NO\.?\s*[:#-]?\s*([A-Z0-9/-]+)",
		r"\bDEED\s+NO\.?\s*[:#-]?\s*([A-Z0-9/-]+)",
		r"\bLETTER\s+NO\.?\s*[:#-]?\s*([A-Z0-9/-]+)",
		r"\bFIR\s+APPLICATION\s+NO\.?\s*[:#-]?\s*([A-Z0-9/-]+)",
	]

	values = []

	for pattern in patterns:
		values.extend(
			re.findall(
				pattern,
				text,
				re.IGNORECASE,
			)
		)

	return unique(values)


def extract_volume_numbers(text):
	values = re.findall(
		r"VOLUME(?:\s+NO\.?)?\s*"
		r"([0-9]+)",
		text,
		re.IGNORECASE,
	)

	return unique(values)


def extract_lr_numbers(text):
	values = re.findall(
		r"L\.?\s*R\.?\s*"
		r"(?:Number|No\.?)\s*"
		r"([0-9/-]+)",
		text,
		re.IGNORECASE,
	)

	return unique(values)


def extract_phone_numbers(text):
	values = re.findall(
		r"(?<!\d)"
		r"(?:"
		r"0\d{2,4}[-\s]?\d{6,8}"
		r"|"
		r"[6-9]\d{9}"
		r")"
		r"(?!\d)",
		text,
	)

	return unique([re.sub(r"\s+", "", value) for value in values])


def extract_pincodes(text):
	values = re.findall(
		r"(?<![\d/])"
		r"([1-9]\d{5})"
		r"(?![\d/])",
		text,
	)

	return unique(values)


def extract_email_addresses(text):
	values = re.findall(
		r"\b[A-Z0-9._%+-]+"
		r"@[A-Z0-9.-]+"
		r"\.[A-Z]{2,}\b",
		text,
		re.IGNORECASE,
	)

	return unique(values)


def extract_objection_days(text):
	match = re.search(
		r"within\s+"
		r"(\d+)"
		r"(?:\s*\([^)]+\))?"
		r"\s+days",
		text,
		re.IGNORECASE,
	)

	if match:
		return int(match.group(1))

	return None


def extract_land_area(text):
	clean = compact(text)

	match = re.search(
		r"land\s+measuring\s+"
		r"(\d+\s+Bighas?"
		r"\s+(?:and\s+)?"
		r"\d+\s+Biswas?)",
		clean,
		re.IGNORECASE,
	)

	if match:
		return match.group(1)

	return None


def structure_notice(path):
	text = path.read_text(
		encoding="utf-8",
		errors="ignore",
	)

	classification, keywords = classify_property_notice(text)

	result = {
		"source_file": path.name,
		"classification": classification,
		"notice_type": extract_notice_type(text),
		"property_keywords": keywords,
	}

	if classification == "NOT_RELEVANT":
		result["raw_text"] = text.strip()
		return result

	result.update(
		{
			"transaction_type": extract_transaction_type(text),
			"property_number": extract_property_number(text),
			"property_address": extract_property_address(text),
			"village": extract_village(text),
			"tehsil": extract_tehsil(text),
			"city": extract_city(text),
			"pincodes": extract_pincodes(text),
			"owner_names": extract_owner_names(text),
			"legal_heirs": extract_legal_heirs(text),
			"seller_names": extract_seller_names(text),
			"mustatil_numbers": extract_mustatil_numbers(text),
			"killa_numbers": extract_killa_numbers(text),
			"document_numbers": extract_document_numbers(text),
			"volume_numbers": extract_volume_numbers(text),
			"lr_numbers": extract_lr_numbers(text),
			"land_area": extract_land_area(text),
			"objection_period_days": extract_objection_days(text),
			"phone_numbers": extract_phone_numbers(text),
			"email_addresses": extract_email_addresses(text),
			"raw_text": text.strip(),
		}
	)

	return result


def main():
	parser = argparse.ArgumentParser(
		description=("Convert OCR public notices into structured property JSON.")
	)

	parser.add_argument(
		"--notices-dir",
		required=True,
		help="Folder containing notice .txt files",
	)

	parser.add_argument(
		"--output",
		help="Optional output JSON path",
	)

	args = parser.parse_args()

	notices_dir = Path(args.notices_dir).expanduser().resolve()

	if not notices_dir.is_dir():
		raise SystemExit(f"Folder not found: {notices_dir}")

	txt_files = sorted(notices_dir.glob("*.txt"))

	results = [structure_notice(path) for path in txt_files]

	relevant = [item for item in results if item["classification"] == "PROPERTY_RELEVANT"]

	ignored = [item for item in results if item["classification"] == "NOT_RELEVANT"]

	if args.output:
		output_path = Path(args.output).expanduser().resolve()
	else:
		output_path = notices_dir.parent / "structured_notices.json"

	final = {
		"total_notices": len(results),
		"property_related_notices": len(relevant),
		"ignored_notices": len(ignored),
		"notices": results,
	}

	output_path.write_text(
		json.dumps(
			final,
			indent=4,
			ensure_ascii=False,
		),
		encoding="utf-8",
	)

	relevant_path = output_path.parent / "property_notices_only.json"

	relevant_path.write_text(
		json.dumps(
			relevant,
			indent=4,
			ensure_ascii=False,
		),
		encoding="utf-8",
	)

	print()
	print("=" * 60)
	print("STRUCTURED EXTRACTION COMPLETE")
	print("=" * 60)

	print(
		"Total notices:",
		len(results),
	)

	print(
		"Property related:",
		len(relevant),
	)

	print(
		"Ignored:",
		len(ignored),
	)

	print()

	for item in results:
		print(
			item["source_file"],
			"->",
			item["classification"],
		)

	print()
	print("Full output:")
	print(output_path)

	print()
	print("Property notices only:")
	print(relevant_path)


if __name__ == "__main__":
	main()
