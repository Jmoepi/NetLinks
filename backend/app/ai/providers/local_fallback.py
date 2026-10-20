"""Local fallback provider: rule-based parsing of the known demo document wording.

Used when no AWS credentials are available (including to generate the committed cache). It produces
the same result shapes as the Bedrock provider and is always labelled as local-fallback.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.ai import lexicon

LOCAL_EXTRACTION_MODEL_ID = "local-rules-v1"
LOCAL_EMBEDDING_MODEL_ID = "local-lexicon-v1"
LOCAL_GENERATED_BY = "local-fallback (regenerate with Bedrock before demo)"

PROVINCES: dict[str, str] = {
    "gauteng": "GP",
    "western cape": "WC",
    "kwazulu-natal": "KZN",
    "eastern cape": "EC",
    "free state": "FS",
    "limpopo": "LP",
    "mpumalanga": "MP",
    "north west": "NW",
    "northern cape": "NC",
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_HIGH = 0.95
_DESCRIPTION = 0.9
_DERIVED = 0.8
_LENIENT_MONEY = 0.7  # parsed from non-standard wording; gateway post-checks cap it further

_DATE = r"\d{4}-\d{2}-\d{2}"


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_date(text: str) -> str | None:
    """ISO date from 'YYYY-MM-DD' or '31 August 2027'; None when unreadable."""
    text = text.strip().rstrip(".")
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_money(text: str) -> int | None:
    """Rand amount from 'R2,500,000', 'R2 000 000', 'R2 million', 'R2m' or the lenient 'R2 mil'."""
    t = text.strip().lower().replace("\u00a0", " ")
    m = re.match(r"r\s?(\d+(?:\.\d+)?)\s?(million|mil|m)\b", t)
    if m:
        return int(round(float(m.group(1)) * 1_000_000))
    m = re.match(r"r\s?(\d{1,3}(?:[ ,]\d{3})+|\d+)", t)
    if m:
        return int(re.sub(r"[ ,]", "", m.group(1)))
    return None


def province_codes(text: str) -> list[str]:
    low = text.lower()
    return [code for name, code in PROVINCES.items() if re.search(r"\b" + re.escape(name) + r"\b", low)]


def _number(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def classify_doc_type(text: str) -> str:
    """doc_type from the document title (the first words after the watermark/footer lines)."""
    body = normalize_ws(text)
    body = body.replace("FICTIONAL - DEMO ONLY", " ")
    body = body.replace("Fictional demo document generated for the NetLinks hackathon prototype", " ")
    head = normalize_ws(body)[:160].lower()
    rules = [
        ("capability statement", "capability_statement"),
        ("technician certification", "certification_summary"),
        ("information security and popia policy", "infosec_popia_policy"),
        ("professional indemnity insurance schedule", "pi_schedule"),
        ("tax compliance status summary", "tax_compliance_letter"),
    ]
    for keyword, doc_type in rules:
        if keyword in head:
            return doc_type
    return "other"


def _field(key: str, value: Any, quote: str, confidence: float = _HIGH) -> dict[str, Any]:
    return {"field_key": key, "value": value, "confidence": confidence, "quote": quote, "page": None}


def _one_date(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def extract_fields(text: str) -> list[dict[str, Any]]:
    """Every field the demo wording supports, from whitespace-normalised document text."""
    t = normalize_ws(text)
    fields: list[dict[str, Any]] = []

    if m := re.search(r"Company name: ([^.]+)\.", t):
        fields.append(_field("company_name", m.group(1).strip(), m.group(0)))
    if m := re.search(r"Head office: ([^,.]+), ([^.]+)\.", t):
        fields.append(_field("base_town", m.group(1).strip(), m.group(0)))
        codes = province_codes(m.group(2))
        if codes:
            fields.append(_field("province", codes[0], m.group(0)))
    if m := re.search(r"Service regions: ([^.]+)\.", t):
        fields.append(_field("service_regions", province_codes(m.group(1)), m.group(0)))
    if m := re.search(r"We have been trading for (\d+) years\.", t):
        fields.append(_field("years_trading", int(m.group(1)), m.group(0)))
    if m := re.search(r"(?:Our services: |We offer )([^.]+)\.", t):
        description = m.group(1).strip()
        fields.append(_field("services_description", description, m.group(0), _DESCRIPTION))
        fields.append(_field("service_tags", lexicon.tags(description), m.group(0), _DERIVED))
    if m := re.search(r"([A-Z][a-z]+(?: [a-z]+)*) hours: (\d{2}:\d{2}) to (\d{2}:\d{2})[^.]*\.", t):
        fields.append(_field("service_desk_hours", {"start": m.group(2), "end": m.group(3)}, m.group(0)))
    if m := re.search(r"(?:Our team currently has|We have) (\w+) (?:field )?technicians\.", t):
        count = _number(m.group(1))
        if count is not None:
            fields.append(_field("technician_count", count, m.group(0)))

    clients = list(re.finditer(r"Client: ([^,]+?) \(fictional\), (\d+) users\.", t))
    if clients:
        value = [{"name": c.group(1).strip(), "user_count": int(c.group(2))} for c in clients]
        fields.append(_field("past_clients", value, t[clients[0].start() : clients[-1].end()]))

    certs = list(re.finditer(r"Technician: ([^,]+?) \(fictional\), ([^,]+), expires ([^.]+?)\.(?!\d)", t))
    if certs:
        value = [
            {
                "holder": c.group(1).strip(),
                "cert_name": c.group(2).strip(),
                "expiry_date": parse_date(c.group(3)),
            }
            for c in certs
        ]
        fields.append(_field("certifications", value, t[certs[0].start() : certs[-1].end()]))

    if m := re.search(rf"Tax compliance status: ([a-z-]+)(?:, valid to ({_DATE}))?\.", t):
        fields.append(_field("tax_compliance_status", m.group(1), m.group(0)))
        if m.group(2):
            fields.append(_field("tax_expiry_date", m.group(2), m.group(0)))
    if m := re.search(rf"Status valid until: ({_DATE})\.", t):
        fields.append(_field("tax_expiry_date", m.group(1), m.group(0)))
    if m := re.search(r"CSD supplier number: ([A-Z0-9]+)\.", t):
        fields.append(_field("csd_number", m.group(1), m.group(0)))
    if m := re.search(r"Black ownership: (\d+)% Black-owned\.", t):
        fields.append(_field("black_ownership_pct", int(m.group(1)), m.group(0)))
    if m := re.search(r"B-BBEE status: Level (\d)\.", t):
        fields.append(_field("bbbee_level", int(m.group(1)), m.group(0)))

    # PI cover written informally inside a capability statement (Thuto).
    if m := re.search(r"Cover: (R[^,]*?) professional (?:liability|indemnity), valid to ([^.]+)\.", t):
        amount = parse_money(m.group(1))
        if amount is not None:
            canonical = bool(re.fullmatch(r"R\s?\d{1,3}(?:[ ,]\d{3})+", m.group(1).strip()))
            confidence = _HIGH if canonical else _LENIENT_MONEY
            fields.append(_field("pi_cover_amount", amount, m.group(0), confidence))
        expiry = parse_date(m.group(2))
        if expiry:
            fields.append(_field("pi_expiry_date", expiry, m.group(0)))
    # PI schedule wording.
    if m := re.search(r"Limit of indemnity: (R[\d, ]+?)\.", t):
        amount = parse_money(m.group(1))
        if amount is not None:
            fields.append(_field("pi_cover_amount", amount, m.group(0)))
    if m := re.search(rf"Cover expires: ({_DATE})\.", t):
        fields.append(_field("pi_expiry_date", m.group(1), m.group(0)))

    return fields


def _period(doc_type: str, text: str) -> tuple[str | None, str | None]:
    t = normalize_ws(text)
    if doc_type == "pi_schedule":
        return _one_date(rf"Date issued: ({_DATE})\.", t), _one_date(rf"Cover expires: ({_DATE})\.", t)
    if doc_type == "tax_compliance_letter":
        return _one_date(rf"Date issued: ({_DATE})\.", t), _one_date(rf"Status valid until: ({_DATE})\.", t)
    if doc_type == "infosec_popia_policy":
        return (
            _one_date(rf"Effective date: ({_DATE})\.", t),
            _one_date(rf"Next review date: ({_DATE})\.", t),
        )
    return None, None


def _sentences(text: str) -> list[str]:
    """Sentences per line, so headings never merge into the following sentence."""
    out: list[str] = []
    for line in (text or "").splitlines():
        out.extend(s.strip() for s in re.split(r"(?<=\.)\s+", normalize_ws(line)) if s.strip())
    return out


def _criterion(rule_type: str, params: dict[str, Any], quote: str) -> dict[str, Any]:
    return {"rule_type": rule_type, "params": params, "source_quote": quote}


def structure_rfq_text(text: str) -> dict[str, Any]:
    """Rule-based RFQ structuring: only catalog rule types, thresholds as written in the prose."""
    title = ""
    closing = None
    for line in (text or "").splitlines():
        if line.startswith("Title:"):
            title = line.removeprefix("Title:").strip()
        elif line.startswith("Closing date:"):
            closing = parse_date(line.removeprefix("Closing date:"))

    mandatory: list[dict[str, Any]] = []
    preferred: list[dict[str, Any]] = []
    capability_text = ""
    for s in _sentences(text):
        low = s.lower()
        if "must" in low:
            if "tax compliance" in low:
                mandatory.append(_criterion("tax_compliance", {}, s))
            elif "central supplier database" in low or "csd" in low:
                mandatory.append(_criterion("csd_registration", {}, s))
            elif m := re.search(r"at least (\d+)% black-owned or hold a b-bbee level \d+ or level (\d+)",
                                low):
                mandatory.append(_criterion(
                    "ownership_or_bbbee",
                    {"min_black_ownership_pct": int(m.group(1)), "max_bbbee_level": int(m.group(2))},
                    s,
                ))
            elif m := re.search(r"must operate in ([a-z -]+?)\.", low):
                codes = province_codes(m.group(1))
                if codes:
                    mandatory.append(_criterion("operating_region", {"region": codes[0]}, s))
            elif "professional indemnity" in low:
                if m := re.search(r"at least (R[\d,. ]+(?:million|mil|m)?)", s, re.IGNORECASE):
                    amount = parse_money(m.group(1))
                    if amount is not None:
                        mandatory.append(_criterion("pi_insurance", {"min_amount": amount}, s))
            elif "information security" in low and "popia" in low:
                mandatory.append(_criterion("infosec_policy", {}, s))
            elif m := re.search(r"at least (\w+) technicians with current certifications", low):
                count = _number(m.group(1))
                if count is not None:
                    mandatory.append(_criterion("certified_technicians", {"min_count": count}, s))
        elif "prefer" in low:
            if m := re.search(r"at least (\d+) years.*?clients of (\d+) or more users", low):
                preferred.append(_criterion(
                    "experience", {"min_years": int(m.group(1)), "min_client_users": int(m.group(2))}, s
                ))
            elif m := re.search(r"(\d+) or more technicians.*?(\d{2}:\d{2}) to (\d{2}:\d{2})", low):
                preferred.append(_criterion(
                    "capacity",
                    {"min_technicians": int(m.group(1)), "hours_start": m.group(2), "hours_end": m.group(3)},
                    s,
                ))
            elif m := re.search(r"within (?:about )?(\d+) km of our (\w+)", s, re.IGNORECASE):
                km = int(m.group(1))
                preferred.append(_criterion(
                    "location", {"anchor": m.group(2), "full_score_km": km, "zero_score_km": km * 3}, s
                ))
            else:
                concepts = lexicon.tags(s)
                if concepts:
                    capability_text = lexicon.capability_text_from_tags(concepts)
                    preferred.append(_criterion("capability", {"text": capability_text, "tags": concepts}, s))

    return {
        "title": title,
        "closing_date": closing,
        "mandatory_criteria": mandatory,
        "preferred_criteria": preferred,
        "capability_text": capability_text,
    }


class LocalFallbackProvider:
    name = "local-fallback"
    extraction_model_id = LOCAL_EXTRACTION_MODEL_ID
    embedding_model_id = LOCAL_EMBEDDING_MODEL_ID
    generated_by = LOCAL_GENERATED_BY

    def available(self) -> bool:
        return True

    def extract_document(self, pages: list[str], filename: str) -> dict[str, Any]:
        text = "\n".join(pages)
        doc_type = classify_doc_type(pages[0] if pages else "")
        issue_date, period_end = _period(doc_type, text)
        return {
            "doc_type": doc_type,
            "issue_date": issue_date,
            "period_end": period_end,
            "fields": extract_fields(text),
        }

    def structure_rfq(self, text: str) -> dict[str, Any]:
        return structure_rfq_text(text)

    def embed(self, text: str) -> list[float]:
        return lexicon.embed(text)
