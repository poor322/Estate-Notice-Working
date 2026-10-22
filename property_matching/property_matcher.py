import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


def normalize(value):
	if value is None:
		return ""

	value = str(value).lower()
	value = re.sub(r"[^a-z0-9/]+", " ", value)
	return " ".join(value.split())


def similarity(a, b):
	a = normalize(a)
	b = normalize(b)

	if not a or not b:
		return 0.0

	return SequenceMatcher(None, a, b).ratio()


def list_contains(values, target):
	target = normalize(target)

	if not target:
		return False

	return any(normalize(value) == target for value in values or [])


def match_property(property_record, notice):
	reasons = []
	score = 0

	# -------------------------------------------------
	# PROPERTY NUMBER
	# -------------------------------------------------

	registered_property_no = normalize(property_record.get("property_number"))

	notice_property_no = normalize(notice.get("property_number"))

	if registered_property_no and notice_property_no and registered_property_no == notice_property_no:
		score += 40
		reasons.append("Exact property number match")

	# -------------------------------------------------
	# VILLAGE
	# -------------------------------------------------

	registered_village = normalize(property_record.get("village"))

	notice_village = normalize(notice.get("village"))

	if registered_village and notice_village and registered_village == notice_village:
		score += 25
		reasons.append("Exact village match")

	# -------------------------------------------------
	# TEHSIL
	# -------------------------------------------------

	registered_tehsil = normalize(property_record.get("tehsil"))

	notice_tehsil = normalize(notice.get("tehsil"))

	if registered_tehsil and notice_tehsil and registered_tehsil == notice_tehsil:
		score += 10
		reasons.append("Exact tehsil match")

	# -------------------------------------------------
	# MUSTATIL
	# -------------------------------------------------

	mustatil = property_record.get("mustatil_number")

	if list_contains(
		notice.get("mustatil_numbers", []),
		mustatil,
	):
		score += 30
		reasons.append(f"Mustatil number match: {mustatil}")

	# -------------------------------------------------
	# KILLA
	# -------------------------------------------------

	killa = property_record.get("killa_number")

	if list_contains(
		notice.get("killa_numbers", []),
		killa,
	):
		score += 30
		reasons.append(f"Killa number match: {killa}")

	# -------------------------------------------------
	# ADDRESS
	# -------------------------------------------------

	registered_address = normalize(property_record.get("address"))

	notice_address = normalize(notice.get("property_address"))

	if registered_address and notice_address:
		address_similarity = similarity(
			registered_address,
			notice_address,
		)

		if address_similarity >= 0.80:
			score += 30
			reasons.append("Strong property address match")

		elif address_similarity >= 0.60:
			score += 15
			reasons.append("Partial property address match")

	# -------------------------------------------------
	# OWNER / SELLER NAME
	# -------------------------------------------------

	owner = property_record.get("owner_name")

	owner_best_score = 0.0
	owner_best_name = None

	candidate_names = notice.get("owner_names", []) + notice.get("seller_names", [])

	for candidate in candidate_names:
		current = similarity(
			owner,
			candidate,
		)

		if current > owner_best_score:
			owner_best_score = current
			owner_best_name = candidate

	if owner_best_score >= 0.90:
		# Owner name helps confirm a match,
		# but owner name alone must never create HIGH.
		score += 20
		reasons.append(f"Strong owner/seller name match: {owner_best_name}")

	elif owner_best_score >= 0.75:
		score += 10
		reasons.append(f"Possible owner/seller name match: {owner_best_name}")

	# -------------------------------------------------
	# CONFIDENCE
	# -------------------------------------------------

	strong_identifier_match = (
		registered_property_no and notice_property_no and registered_property_no == notice_property_no
	) or (
		list_contains(
			notice.get(
				"mustatil_numbers",
				[],
			),
			mustatil,
		)
		and list_contains(
			notice.get(
				"killa_numbers",
				[],
			),
			killa,
		)
	)

	if score >= 60 and strong_identifier_match:
		confidence = "HIGH"

	elif score >= 30:
		confidence = "MEDIUM"

	else:
		confidence = "NO_MATCH"

	return {
		"property_id": property_record.get("property_id"),
		"notice_file": notice.get("source_file"),
		"confidence": confidence,
		"score": score,
		"reasons": reasons,
	}


def main():
	parser = argparse.ArgumentParser()

	parser.add_argument(
		"--properties",
		required=True,
	)

	parser.add_argument(
		"--notices",
		required=True,
	)

	parser.add_argument(
		"--output",
		required=True,
	)

	args = parser.parse_args()

	properties = json.loads(Path(args.properties).read_text(encoding="utf-8"))

	notices = json.loads(Path(args.notices).read_text(encoding="utf-8"))

	results = []

	for property_record in properties:
		for notice in notices:
			result = match_property(
				property_record,
				notice,
			)

			results.append(result)

	output = {
		"total_comparisons": len(results),
		"matches": results,
	}

	Path(args.output).write_text(
		json.dumps(
			output,
			indent=4,
			ensure_ascii=False,
		),
		encoding="utf-8",
	)

	print()
	print("=" * 65)
	print("PROPERTY MATCHING RESULTS")
	print("=" * 65)

	for result in results:
		print()
		print(
			result["property_id"],
			"<->",
			result["notice_file"],
		)
		print(
			"Confidence:",
			result["confidence"],
		)
		print(
			"Score:",
			result["score"],
		)

		for reason in result["reasons"]:
			print(" -", reason)

	print()
	print("Output:", args.output)


if __name__ == "__main__":
	main()
