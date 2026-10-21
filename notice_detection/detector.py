import re


# =========================================================
# 1. WORDS THAT INDICATE A LEGAL / OFFICIAL NOTICE
# =========================================================

NOTICE_TERMS = [
    "public notice",
    "public notices",
    "legal notice",
    "legal notices",
    "court notice",
    "court notices",
    "auction notice",
    "auction notices",
    "demand notice",
    "notice is hereby given",
    "notice is hereby issued",
    "notice to the public",
    "hereby notified",
    "claims and objections",
]


# =========================================================
# 2. PROPERTY / LAND TERMS
# =========================================================

PROPERTY_TERMS = [
    "immovable property",
    "immovable",
    "property",
    "land",
    "plot",
    "site",
    "premises",
    "building",
    "apartment",
    "flat",
    "house",
    "farm land",
    "farmland",
    "estate",
    "real estate",
]


# =========================================================
# 3. LEGAL / PROPERTY ACTION TERMS
# =========================================================

LEGAL_ACTION_TERMS = [
    "claim",
    "claims",
    "objection",
    "objections",
    "encumbrance",
    "title",
    "title deed",
    "sale deed",
    "deed",
    "agreement",
    "registration",
    "transfer",
    "mortgage",
    "mortgagor",
    "mortgagee",
    "lease",
    "possession",
    "acquisition",
    "recovery",
    "auction",
    "legal heirs",
    "legal heir",
    "ownership",
    "owner",
    "claimant",
]


# =========================================================
# 4. IMPORTANT PROPERTY IDENTIFIERS
# =========================================================

IDENTIFIER_PATTERNS = [
    r"\bsurvey\s*(?:no|number)\.?\s*[:\-]?",
    r"\bsy\.?\s*no\.?\s*[:\-]?",
    r"\bplot\s*(?:no|number)\.?\s*[:\-]?",
    r"\bproperty\s*(?:no|number)\.?\s*[:\-]?",
    r"\bkhata\s*(?:no|number)\.?\s*[:\-]?",
    r"\bkatha\s*(?:no|number)\.?\s*[:\-]?",
    r"\bdoor\s*(?:no|number)\.?\s*[:\-]?",
    r"\bkhasra\s*(?:no|number)\.?\s*[:\-]?",
]


# =========================================================
# 5. LEGAL PARTY TERMS
# =========================================================

PARTY_TERMS = [
    "owner",
    "claimant",
    "applicant",
    "purchaser",
    "seller",
    "vendor",
    "mortgagee",
    "mortgagor",
    "advocate",
    "legal heir",
    "legal heirs",
    "authorized signatory",
]


# =========================================================
# 6. NOTICE SECTION TERMS
# =========================================================

SECTION_TERMS = [
    "public notices",
    "public notice",
    "legal notices",
    "legal notice",
    "court notices",
    "court notice",
    "auction notices",
    "auction notice",
]


# =========================================================
# 7. ADVERTISEMENT / NEWS TERMS
# These should reduce false positives.
# =========================================================

ADVERTISEMENT_TERMS = [
    "sale or rent your property",
    "sale or rent",
    "rent your property",
    "book your property",
    "property related ads",
    "property ads",
    "classifieds",
    "to book your",
    "contact us",
    "call us",
    "for advertising",
    "advertisement",
    "advertising",
    "real estate agency",
    "real estate company",
    "property dealer",
    "property dealers",
    "property consultant",
    "property consultants",
    "property for sale",
    "property for rent",
    "flats for sale",
    "flats for rent",
    "houses for sale",
    "houses for rent",
]


# =========================================================
# 8. GENERAL REAL-ESTATE NEWS
# =========================================================

NEWS_TERMS = [
    "property prices",
    "property price",
    "property market",
    "real estate news",
    "real estate market",
    "housing market",
    "market trends",
    "property investment",
    "property prices rise",
    "property prices fall",
]


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):
    text = text.lower()

    # Keep useful punctuation such as / and -
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# FIND WORD / PHRASE MATCHES
# =========================================================

def find_terms(text, terms):

    matches = []

    for term in terms:

        if term in text:
            matches.append(term)

    return list(dict.fromkeys(matches))


# =========================================================
# FIND PROPERTY IDENTIFIERS
# =========================================================

def find_identifiers(text):

    matches = []

    for pattern in IDENTIFIER_PATTERNS:

        result = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if result:
            matches.append(result.group().strip())

    return list(dict.fromkeys(matches))


# =========================================================
# MAIN DETECTION FUNCTION
# =========================================================

def detect_notice(text):

    text = normalize_text(text)

    # -----------------------------------------------------
    # Find signals
    # -----------------------------------------------------

    notice_matches = find_terms(
        text,
        NOTICE_TERMS
    )

    property_matches = find_terms(
        text,
        PROPERTY_TERMS
    )

    legal_action_matches = find_terms(
        text,
        LEGAL_ACTION_TERMS
    )

    party_matches = find_terms(
        text,
        PARTY_TERMS
    )

    section_matches = find_terms(
        text,
        SECTION_TERMS
    )

    identifier_matches = find_identifiers(
        text
    )

    advertisement_matches = find_terms(
        text,
        ADVERTISEMENT_TERMS
    )

    news_matches = find_terms(
        text,
        NEWS_TERMS
    )

    # -----------------------------------------------------
    # Score
    # -----------------------------------------------------

    score = 0
    reasons = []

    # -----------------------------------------------------
    # NOTICE SIGNAL
    # -----------------------------------------------------

    if notice_matches:

        score += 25

        reasons.append(
            "Legal/public notice language detected"
        )

    # -----------------------------------------------------
    # PROPERTY SIGNAL
    # -----------------------------------------------------

    if property_matches:

        score += 15

        reasons.append(
            "Land/property context detected"
        )

    # -----------------------------------------------------
    # LEGAL ACTION
    # -----------------------------------------------------

    if legal_action_matches:

        score += 15

        reasons.append(
            "Legal/property action detected"
        )

    # -----------------------------------------------------
    # PROPERTY IDENTIFIER
    # -----------------------------------------------------

    if identifier_matches:

        score += 25

        reasons.append(
            "Property identifier detected"
        )

    # -----------------------------------------------------
    # LEGAL PARTY
    # -----------------------------------------------------

    if party_matches:

        score += 10

        reasons.append(
            "Legal party detected"
        )

    # -----------------------------------------------------
    # NOTICE SECTION
    # -----------------------------------------------------

    if section_matches:

        score += 10

        reasons.append(
            "Notice section detected"
        )

    # -----------------------------------------------------
    # STRONG COMBINATIONS
    # -----------------------------------------------------

    if notice_matches and property_matches:

        score += 10

        reasons.append(
            "Notice + property context"
        )

    if notice_matches and identifier_matches:

        score += 10

        reasons.append(
            "Notice + property identifier"
        )

    if property_matches and legal_action_matches:

        score += 10

        reasons.append(
            "Property + legal action"
        )

    # -----------------------------------------------------
    # NEGATIVE: ADVERTISEMENT
    # -----------------------------------------------------

    if advertisement_matches:

        score -= 60

        reasons.append(
            "Property advertisement detected"
        )

    # -----------------------------------------------------
    # NEGATIVE: GENERAL PROPERTY NEWS
    # -----------------------------------------------------

    if news_matches:

        score -= 40

        reasons.append(
            "General real-estate/news context"
        )

    # -----------------------------------------------------
    # IMPORTANT RULE
    #
    # A property advertisement should NOT become
    # an estate notice merely because it contains
    # words like property or sale.
    # -----------------------------------------------------

    if advertisement_matches and not identifier_matches:

        score = min(score, 20)

    # -----------------------------------------------------
    # IMPORTANT RULE
    #
    # A real estate news article should not become
    # an estate notice.
    # -----------------------------------------------------

    if news_matches and not identifier_matches:

        score = min(score, 20)

    # -----------------------------------------------------
    # Keep score between 0 and 100
    # -----------------------------------------------------

    score = max(
        0,
        min(score, 100)
    )

    # -----------------------------------------------------
    # FINAL CLASSIFICATION
    # -----------------------------------------------------

    if score >= 70:

        confidence = "HIGH"
        is_notice = True
        notice_type = "ESTATE_PROPERTY_NOTICE"

    elif score >= 45:

        confidence = "MEDIUM"
        is_notice = True
        notice_type = "ESTATE_PROPERTY_NOTICE"

    else:

        confidence = "LOW"
        is_notice = False
        notice_type = "NOT_RELEVANT"

    # -----------------------------------------------------
    # Extra protection:
    #
    # A notice should normally have both:
    #   1. notice language
    #   2. property/land context
    #
    # Otherwise reject it.
    # -----------------------------------------------------

    if not notice_matches:

        is_notice = False
        notice_type = "NOT_RELEVANT"

    if not property_matches:

        is_notice = False
        notice_type = "NOT_RELEVANT"

    # -----------------------------------------------------
    # Advertisement override
    # -----------------------------------------------------

    if advertisement_matches and not identifier_matches:

        is_notice = False
        notice_type = "PROPERTY_ADVERTISEMENT"

        confidence = "HIGH"

    # -----------------------------------------------------
    # News override
    # -----------------------------------------------------

    if news_matches and not identifier_matches:

        is_notice = False
        notice_type = "REAL_ESTATE_NEWS"

        confidence = "HIGH"

    # -----------------------------------------------------
    # Return result
    # -----------------------------------------------------

    return {
        "is_notice": is_notice,
        "notice_type": notice_type,
        "confidence": confidence,
        "score": score,
        "matched_notice_terms": notice_matches,
        "matched_section_terms": section_matches,
        "matched_property_terms": property_matches,
        "matched_action_terms": legal_action_matches,
        "matched_identifiers": identifier_matches,
        "matched_party_terms": party_matches,
        "advertisement_signals": advertisement_matches,
        "news_signals": news_matches,
        "reasons": reasons
    }

