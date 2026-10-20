"""Prompts, result shapes and the fixed criteria catalog shared by every AI provider.

Extraction result shape (every provider, after gateway post-checks):
    {
      "doc_type": one of DOC_TYPES,
      "issue_date": "YYYY-MM-DD" | null,
      "period_end": "YYYY-MM-DD" | null,
      "fields": [
        {"field_key": one of FIELD_KEYS, "value": <json>, "confidence": 0..1,
         "quote": "<exact sentence from the document>", "page": 1-based int | null,
         "span_start": int | null, "span_end": int | null}   # spans added by post-checks
      ]
    }

RFQ structuring result shape:
    {
      "title": str, "closing_date": "YYYY-MM-DD" | null,
      "mandatory_criteria": [{"rule_type": one of MANDATORY_RULE_TYPES, "params": {...},
                              "source_quote": str}],
      "preferred_criteria": [{"rule_type": one of PREFERRED_RULE_TYPES, "params": {...},
                              "source_quote": str}],
      "capability_text": str
    }
"""

from __future__ import annotations

EXTRACTION_PROMPT_VERSION = "extraction-v1"
RFQ_PROMPT_VERSION = "rfq-v1"
EMBEDDING_PROMPT_VERSION = "embedding-v1"

DOC_TYPES = [
    "capability_statement",
    "certification_summary",
    "infosec_popia_policy",
    "pi_schedule",
    "tax_compliance_letter",
    "other",
]

# Field key -> value description (also used to validate provider output).
FIELD_KEYS: dict[str, str] = {
    "company_name": "string",
    "base_town": "string (head office town)",
    "province": "South African province code: GP, WC, KZN, EC, FS, LP, MP, NW, NC",
    "service_regions": "list of province codes the company operates in",
    "services_description": "string: the company's own description of its services, verbatim",
    "service_tags": "list of tags from: service_desk, desktop_device_support, m365_admin, networking, "
    "cybersecurity, cloud, web_design, seo, hosting",
    "technician_count": "integer",
    "certifications": "list of {holder, cert_name, expiry_date: YYYY-MM-DD or null if unreadable}",
    "years_trading": "integer",
    "past_clients": "list of {name, user_count}",
    "service_desk_hours": "{start: HH:MM, end: HH:MM}",
    "pi_cover_amount": "integer amount in rand (professional indemnity / liability cover)",
    "pi_expiry_date": "YYYY-MM-DD",
    "tax_compliance_status": "compliant | non-compliant",
    "tax_expiry_date": "YYYY-MM-DD",
    "csd_number": "string, e.g. MAAA0000000",
    "black_ownership_pct": "integer percentage",
    "bbbee_level": "integer 1-8",
}

MONEY_FIELDS = {"pi_cover_amount"}

# Fixed catalog: the LLM may only choose from these; no free-form rule execution.
MANDATORY_RULE_TYPES: dict[str, str] = {
    "tax_compliance": "{}",
    "csd_registration": "{}",
    "ownership_or_bbbee": "{min_black_ownership_pct: int, max_bbbee_level: int}",
    "operating_region": "{region: province code, e.g. GP}",
    "pi_insurance": "{min_amount: integer rand}",
    "infosec_policy": "{}",
    "certified_technicians": "{min_count: int}",
}

PREFERRED_RULE_TYPES: dict[str, str] = {
    "capability": "{text: str, tags: list of service tags}",
    "experience": "{min_years: int, min_client_users: int}",
    "capacity": "{min_technicians: int, hours_start: HH:MM, hours_end: HH:MM}",
    "location": "{anchor: town, full_score_km: int, zero_score_km: int}",
}


def _bullets(d: dict[str, str]) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in d.items())


EXTRACTION_SYSTEM_PROMPT = f"""You extract facts from South African SME procurement documents.
Return ONLY one JSON object, no prose, no markdown fences, with this exact shape:
{{"doc_type": str, "issue_date": "YYYY-MM-DD" or null, "period_end": "YYYY-MM-DD" or null,
  "fields": [{{"field_key": str, "value": any, "confidence": number 0-1, "quote": str, "page": int}}]}}

doc_type must be one of: {", ".join(DOC_TYPES)}.
issue_date is the date the document was issued or became effective; period_end is the date its cover,
status or validity ends. Use null when absent.

Allowed field_key values and value formats:
{_bullets(FIELD_KEYS)}

Rules:
- Only report facts stated in the document. Omit fields that are not present. Never guess.
- quote must be the exact sentence from the document text that states the fact, copied verbatim.
- page is the 1-based page number containing the quote.
- confidence reflects how unambiguous the wording is. Use a low value (<= 0.5) for vague,
  abbreviated or non-standard wording (for example an amount written as "R2 mil").
- Dates as YYYY-MM-DD. Amounts as integers in rand.
"""

RFQ_SYSTEM_PROMPT = f"""You structure a buyer's request for quotation into procurement criteria.
Return ONLY one JSON object, no prose, no markdown fences, with this exact shape:
{{"title": str, "closing_date": "YYYY-MM-DD" or null,
  "mandatory_criteria": [{{"rule_type": str, "params": object, "source_quote": str}}],
  "preferred_criteria": [{{"rule_type": str, "params": object, "source_quote": str}}],
  "capability_text": str}}

mandatory_criteria rule_type MUST be one of these (params shown); never invent other rule types:
{_bullets(MANDATORY_RULE_TYPES)}

preferred_criteria rule_type MUST be one of these (params shown):
{_bullets(PREFERRED_RULE_TYPES)}

Rules:
- Use exactly the thresholds written in the RFQ (for example "R1 million" -> min_amount 1000000).
- source_quote is the exact sentence of the RFQ the criterion came from.
- capability_text is a short comma-separated summary of the preferred service capabilities.
- If a requirement does not fit the catalog, leave it out.
"""


def extraction_user_prompt(pages: list[str], filename: str) -> str:
    body = "\n\n".join(f"--- page {i + 1} ---\n{p}" for i, p in enumerate(pages))
    return f"Document filename: {filename}\n\n{body}"


def rfq_user_prompt(text: str) -> str:
    return f"RFQ text:\n\n{text}"
