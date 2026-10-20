"""Local-fallback provider on the committed demo documents (after gateway post-checks)."""

from pathlib import Path

import pytest

from app.ai import gateway, lexicon
from app.ai.providers.local_fallback import LocalFallbackProvider, parse_money
from app.config import LOW_CONFIDENCE, get_settings
from app.ingestion.pdf_text import extract_pages

ASSETS = Path(get_settings().demo_assets_dir)
OPPORTUNITY_CAPABILITY = "Service desk, desktop/device support, Microsoft 365 administration"


@pytest.fixture(scope="module")
def provider() -> LocalFallbackProvider:
    return LocalFallbackProvider()


def extract(provider: LocalFallbackProvider, filename: str) -> dict:
    pages = extract_pages((ASSETS / filename).read_bytes())
    return gateway.postcheck_extraction(provider.extract_document(pages, filename), pages)


def fields(result: dict) -> dict[str, dict]:
    return {f["field_key"]: f for f in result["fields"]}


def test_thuto_capability_statement(provider):
    result = extract(provider, "Thuto_Capability_Statement.pdf")
    f = fields(result)
    assert result["doc_type"] == "capability_statement"
    assert f["technician_count"]["value"] == 9
    assert f["pi_cover_amount"]["value"] == 2_000_000
    assert f["pi_cover_amount"]["confidence"] < LOW_CONFIDENCE  # "R2 mil" is informal wording
    assert f["pi_expiry_date"]["value"] == "2027-08-31"
    assert f["tax_compliance_status"]["value"] == "compliant"
    assert f["tax_expiry_date"]["value"] == "2027-06-30"
    assert f["csd_number"]["value"] == "MAAA0412345"
    assert f["black_ownership_pct"]["value"] == 100
    assert f["bbbee_level"]["value"] == 1
    assert f["service_regions"]["value"] == ["GP"]
    # Spans point at the exact sentence in the raw page text.
    pages = extract_pages((ASSETS / "Thuto_Capability_Statement.pdf").read_bytes())
    tc = f["technician_count"]
    highlighted = pages[tc["page"] - 1][tc["span_start"] : tc["span_end"]]
    assert highlighted == "Our team currently has 9 field technicians."


def test_thuto_certifications(provider):
    result = extract(provider, "Thuto_Technician_Certifications.pdf")
    certs = fields(result)["certifications"]["value"]
    assert result["doc_type"] == "certification_summary"
    assert len(certs) == 4
    network_plus = next(c for c in certs if c["cert_name"] == "CompTIA Network+")
    assert network_plus["expiry_date"] == "2026-05-31"
    assert network_plus["holder"] == "Ayanda Khumalo"


def test_mmapula_semantic_tags(provider):
    f = fields(extract(provider, "Mmapula_Capability_Statement.pdf"))
    assert {"service_desk", "desktop_device_support", "m365_admin"} <= set(f["service_tags"]["value"])
    assert "user assistance" in f["services_description"]["value"]


def test_brightpath_technician_count(provider):
    assert fields(extract(provider, "BrightPath_Capability_Statement.pdf"))["technician_count"]["value"] == 4


def test_zola_renewed_pi(provider):
    result = extract(provider, "Zola_PI_Insurance_Schedule_Renewed.pdf")
    assert result["doc_type"] == "pi_schedule"
    assert result["period_end"] == "2028-02-16"
    assert result["issue_date"] == "2026-10-01"
    f = fields(result)
    assert f["pi_cover_amount"]["value"] == 2_500_000
    assert f["pi_cover_amount"]["confidence"] >= LOW_CONFIDENCE


def test_doc_types(provider):
    expected = {
        "Mmapula_InfoSec_POPIA_Policy.pdf": "infosec_popia_policy",
        "Mmapula_Tax_Compliance_Letter.pdf": "tax_compliance_letter",
        "Zola_PI_Insurance_Schedule.pdf": "pi_schedule",
    }
    for filename, doc_type in expected.items():
        assert extract(provider, filename)["doc_type"] == doc_type


def test_rfq_proposal_uses_raw_text_threshold(provider):
    text = (ASSETS / "Ubuntu_Office_Parks_RFQ_raw.txt").read_text(encoding="utf-8")
    result = gateway.postcheck_rfq(provider.structure_rfq(text))
    rules = {c["rule_type"]: c["params"] for c in result["mandatory_criteria"]}
    assert rules["pi_insurance"] == {"min_amount": 1_000_000}
    assert set(rules) == {
        "tax_compliance", "csd_registration", "ownership_or_bbbee", "operating_region",
        "pi_insurance", "infosec_policy", "certified_technicians",
    }
    assert rules["certified_technicians"] == {"min_count": 2}
    assert result["closing_date"] == "2027-02-26"
    assert result["capability_text"] == OPPORTUNITY_CAPABILITY


def test_lexicon_semantic_ordering():
    opp = lexicon.embed(OPPORTUNITY_CAPABILITY)
    mmapula = lexicon.embed(
        "workplace technology care for corporate teams: device lifecycle, Microsoft 365 tenant "
        "administration, remote and on-site user assistance"
    )
    lerato = lexicon.embed("web design, SEO and WordPress hosting")
    assert lexicon.cosine(mmapula, opp) > lexicon.cosine(lerato, opp)
    assert lexicon.cosine(mmapula, opp) > 0.7


@pytest.mark.parametrize(
    "text,amount",
    [("R2,000,000", 2_000_000), ("R2 000 000", 2_000_000), ("R2 million", 2_000_000), ("R2m", 2_000_000),
     ("R2 mil", 2_000_000), ("R2,500,000", 2_500_000)],
)
def test_parse_money(text, amount):
    assert parse_money(text) == amount


def test_money_postcheck_caps_informal_amount():
    pages = ["Cover: R2 mil professional liability. Limit of indemnity: R2,000,000."]
    result = gateway.postcheck_extraction(
        {"doc_type": "pi_schedule", "fields": [
            {"field_key": "pi_cover_amount", "value": 2_000_000, "confidence": 0.9,
             "quote": "Cover: R2 mil professional liability."},
            {"field_key": "pi_cover_amount", "value": 2_000_000, "confidence": 0.9,
             "quote": "Limit of indemnity: R2,000,000."},
            {"field_key": "csd_number", "value": "MAAA0000000", "confidence": 0.9,
             "quote": "A sentence that is not in the document."},
            {"field_key": "not_a_field", "value": 1, "confidence": 1, "quote": "x"},
        ]},
        pages,
    )
    informal, canonical, unlocated = result["fields"]
    assert informal["confidence"] == 0.5
    assert canonical["confidence"] == 0.9
    assert unlocated["confidence"] == 0.5 and unlocated["span_start"] is None
    assert len(result["fields"]) == 3  # unknown field keys are dropped
