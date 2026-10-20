"""Deterministic eligibility engine (plan A10): every rule, the shared rules and aggregation."""

from datetime import date
from itertools import count
from pathlib import Path

import pytest

from app.engine import eligibility
from app.engine.eligibility import UNCONFIRMED_FAILURE, aggregate, evaluate
from app.engine.types import DocumentRef, EvidenceRef, Fact, OpportunitySpec, SMEProfile

CLOSING = date(2027, 2, 26)
_ids = count(1)

MANDATORY = [
    {"rule_type": "tax_compliance", "params": {}},
    {"rule_type": "csd_registration", "params": {}},
    {"rule_type": "ownership_or_bbbee", "params": {"min_black_ownership_pct": 51, "max_bbbee_level": 2}},
    {"rule_type": "operating_region", "params": {"region": "GP"}},
    {"rule_type": "pi_insurance", "params": {"min_amount": 2000000}},
    {"rule_type": "infosec_policy", "params": {}},
    {"rule_type": "certified_technicians", "params": {"min_count": 2}},
]
PREFERRED = [
    {"rule_type": "capability", "params": {"text": "Service desk", "tags": ["service_desk"]}},
    {"rule_type": "experience", "params": {"min_years": 3, "min_client_users": 200}},
    {"rule_type": "capacity", "params": {"min_technicians": 8, "hours_start": "07:00", "hours_end": "18:00"}},
    {"rule_type": "location", "params": {"anchor": "Midrand", "full_score_km": 50, "zero_score_km": 150}},
]
OPP = OpportunitySpec(
    id=1,
    closing_date=CLOSING,
    mandatory_criteria=MANDATORY,
    preferred_criteria=PREFERRED,
    weights={"capability": 40, "experience": 25, "capacity": 20, "location": 15},
)

CURRENT_CERTS = [
    {"holder": "A (fictional)", "cert_name": "CompTIA A+", "expiry_date": "2028-03-31"},
    {"holder": "B (fictional)", "cert_name": "ITIL 4 Foundation", "expiry_date": "2029-01-31"},
]


def fact(
    key,
    value,
    source_type="ai_extracted",
    confidence=0.95,
    source_label="Doc.pdf",
    doc_type="capability_statement",
):
    confirmed = source_type in ("sme_confirmed", "verified")
    ref = EvidenceRef(
        field_key=key,
        value=value,
        source_type=source_type,
        source_label=source_label,
        document_id=None if doc_type is None else 1,
        doc_type=doc_type,
        page=1,
        span_start=0,
        span_end=5,
        quote=f"quote {value}",
        confidence=confidence,
        candidate_id=next(_ids),
    )
    status = "low_confidence" if not confirmed and confidence < 0.6 else "ok"
    return Fact(key, status, value, source_type, confidence, ref, [ref])


def conflict(key, *values):
    """values: (value, source_type, source_label, doc_type)."""
    refs = [
        EvidenceRef(
            field_key=key,
            value=v,
            source_type=st,
            source_label=label,
            doc_type=dt,
            document_id=1 if dt else None,
            candidate_id=next(_ids),
        )
        for v, st, label, dt in values
    ]
    return Fact(key, "conflict", None, None, None, None, refs)


def good_facts():
    return {
        "tax_compliance_status": fact("tax_compliance_status", "compliant"),
        "tax_expiry_date": fact("tax_expiry_date", "2027-06-30"),
        "csd_number": fact("csd_number", "MAAA0412345"),
        "black_ownership_pct": fact("black_ownership_pct", 100),
        "bbbee_level": fact("bbbee_level", 1),
        "service_regions": fact("service_regions", ["GP"]),
        "pi_cover_amount": fact("pi_cover_amount", 2000000),
        "pi_expiry_date": fact("pi_expiry_date", "2027-08-31"),
        "certifications": fact("certifications", CURRENT_CERTS, doc_type="certification_summary"),
        "technician_count": fact("technician_count", 11),
        "service_desk_hours": fact("service_desk_hours", {"start": "07:00", "end": "18:00"}),
        "base_town": fact("base_town", "Midrand"),
    }


POLICY = DocumentRef(id=9, filename="X_InfoSec_POPIA_Policy.pdf", doc_type="infosec_popia_policy")


def profile(documents=None, **overrides):
    facts = good_facts()
    for key, value in overrides.items():
        if value is None:
            facts.pop(key, None)
        else:
            facts[key] = value
    return SMEProfile(sme_id=1, facts=facts, documents=[POLICY] if documents is None else documents)


def check(prof, rule, opp=OPP):
    return evaluate(prof, opp).check(rule)


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def test_all_pass_is_eligible_with_evidence():
    result = evaluate(profile(), OPP)
    assert result.status == "eligible"
    assert [c.rule for c in result.checks] == [c["rule_type"] for c in MANDATORY] + ["data_consistency"]
    for c in result.checks:
        assert c.outcome == "pass", c
        if c.group == "mandatory":
            assert c.evidence, c.rule
    assert result.check("data_consistency").group == "consistency"


def test_unknown_rule_type_rejected():
    opp = OpportunitySpec(
        id=1, closing_date=CLOSING, mandatory_criteria=[{"rule_type": "free_text", "params": {}}]
    )
    with pytest.raises(ValueError):
        evaluate(profile(), opp)


# ---------------------------------------------------------------------------
# Shared rules on every fact-based rule
# ---------------------------------------------------------------------------

# rule, field, failing value
FIELD_RULES = [
    ("tax_compliance", "tax_compliance_status", "non-compliant"),
    ("csd_registration", "csd_number", "MAAA12345"),
    ("operating_region", "service_regions", ["WC"]),
    ("pi_insurance", "pi_cover_amount", 1000000),
    ("certified_technicians", "certifications", CURRENT_CERTS[:1]),
]


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_missing_value_needs_review(rule, key, bad):
    c = check(profile(**{key: None}), rule)
    assert c.outcome == "needs_review" and "missing" in c.issues
    assert "not provided" in c.reason


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_low_confidence_needs_review(rule, key, bad):
    good = good_facts()[key]
    c = check(profile(**{key: fact(key, good.value, confidence=0.5)}), rule)
    assert c.outcome == "needs_review" and "low_confidence" in c.issues
    assert "low confidence" in c.reason and "SME to confirm" in c.reason


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_low_confidence_value_passes_once_confirmed(rule, key, bad):
    good = good_facts()[key]
    c = check(profile(**{key: fact(key, good.value, source_type="sme_confirmed", confidence=1.0)}), rule)
    assert c.outcome == "pass"


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_conflict_needs_review_naming_both(rule, key, bad):
    good = good_facts()[key]
    f = conflict(
        key,
        (good.value, "sme_confirmed", "SME profile form", None),
        (bad, "ai_extracted", "Doc.pdf", "capability_statement"),
    )
    c = check(profile(**{key: f}), rule)
    assert c.outcome == "needs_review" and "conflict" in c.issues
    assert "SME profile form" in c.reason and "capability statement" in c.reason
    assert len([e for e in c.evidence if e.field_key == key]) == 2


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_ai_extracted_failing_value_needs_review(rule, key, bad):
    c = check(profile(**{key: fact(key, bad)}), rule)
    assert c.outcome == "needs_review" and "unconfirmed_failure" in c.issues
    assert UNCONFIRMED_FAILURE in c.reason


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_confirmed_failing_value_is_not_eligible(rule, key, bad):
    prof = profile(**{key: fact(key, bad, source_type="sme_confirmed", confidence=1.0)})
    result = evaluate(prof, OPP)
    assert result.check(rule).outcome == "fail"
    assert result.status == "not_eligible"


@pytest.mark.parametrize(("rule", "key", "bad"), FIELD_RULES)
def test_verified_failing_value_is_fail(rule, key, bad):
    c = check(profile(**{key: fact(key, bad, source_type="verified", confidence=1.0)}), rule)
    assert c.outcome == "fail"


# ---------------------------------------------------------------------------
# Expiry rules
# ---------------------------------------------------------------------------

EXPIRY_RULES = [
    ("tax_compliance", "tax_expiry_date", "Tax compliance status"),
    ("pi_insurance", "pi_expiry_date", "Professional indemnity cover"),
]


@pytest.mark.parametrize(("rule", "key", "subject"), EXPIRY_RULES)
def test_expires_before_closing_is_outdated_review(rule, key, subject):
    c = check(profile(**{key: fact(key, "2027-02-16")}), rule)
    assert c.outcome == "needs_review" and "outdated" in c.issues
    assert c.reason == f"{subject} expires 10 days before the closing date."


@pytest.mark.parametrize(("rule", "key", "subject"), EXPIRY_RULES)
def test_expires_exactly_on_closing_is_outdated_review(rule, key, subject):
    c = check(profile(**{key: fact(key, "2027-02-26")}), rule)
    assert c.outcome == "needs_review" and "outdated" in c.issues
    assert c.reason == f"{subject} expires on the closing date."


@pytest.mark.parametrize(("rule", "key", "subject"), EXPIRY_RULES)
def test_expires_day_after_closing_passes(rule, key, subject):
    assert check(profile(**{key: fact(key, "2027-02-27")}), rule).outcome == "pass"


@pytest.mark.parametrize(("rule", "key", "subject"), EXPIRY_RULES)
def test_confirmed_outdated_is_never_fail(rule, key, subject):
    c = check(profile(**{key: fact(key, "2026-01-01", source_type="sme_confirmed", confidence=1.0)}), rule)
    assert c.outcome == "needs_review" and "outdated" in c.issues


@pytest.mark.parametrize(("rule", "key", "subject"), EXPIRY_RULES)
def test_unparsable_date_needs_review(rule, key, subject):
    c = check(profile(**{key: fact(key, "end of Feb")}), rule)
    assert c.outcome == "needs_review" and "unreadable" in c.issues


@pytest.mark.parametrize(("rule", "key", "subject"), EXPIRY_RULES)
def test_missing_expiry_needs_review(rule, key, subject):
    assert check(profile(**{key: None}), rule).outcome == "needs_review"


def test_pi_confirmed_short_amount_beats_outdated_expiry():
    prof = profile(
        pi_cover_amount=fact("pi_cover_amount", 1000000, source_type="sme_confirmed", confidence=1.0),
        pi_expiry_date=fact("pi_expiry_date", "2027-02-16"),
    )
    c = check(prof, "pi_insurance")
    assert c.outcome == "fail" and "below the R2,000,000 minimum" in c.reason


def test_pi_low_confidence_amount_quotes_source():
    c = check(profile(pi_cover_amount=fact("pi_cover_amount", 2000000, confidence=0.5)), "pi_insurance")
    assert c.outcome == "needs_review" and "quote 2000000" in c.reason


# ---------------------------------------------------------------------------
# Rule specifics
# ---------------------------------------------------------------------------


def test_csd_malformed_formats():
    for bad in ("MAAA041234", "MAAA04123456", "maaa0412345", "MBBB0412345", ""):
        c = check(
            profile(csd_number=fact("csd_number", bad, source_type="sme_confirmed", confidence=1.0)),
            "csd_registration",
        )
        assert c.outcome == "fail", bad
    assert (
        check(profile(csd_number=fact("csd_number", " MAAA0412345 ")), "csd_registration").outcome == "pass"
    )


@pytest.mark.parametrize(
    ("own", "level", "expected"),
    [
        ((100, "ai_extracted"), (1, "ai_extracted"), "pass"),
        ((40, "sme_confirmed"), (2, "ai_extracted"), "pass"),  # B-BBEE route qualifies
        ((60, "ai_extracted"), (4, "sme_confirmed"), "pass"),  # ownership route qualifies
        ((51, "ai_extracted"), None, "pass"),  # one route is enough
        (None, (2, "ai_extracted"), "pass"),
        (None, None, "needs_review"),
        ((40, "ai_extracted"), (4, "ai_extracted"), "needs_review"),  # unconfirmed failures
        ((40, "sme_confirmed"), (4, "ai_extracted"), "needs_review"),
        ((40, "sme_confirmed"), None, "needs_review"),
        ((40, "sme_confirmed"), (4, "verified"), "fail"),  # both confirmed and failing
    ],
)
def test_ownership_or_bbbee_combinations(own, level, expected):
    def make(key, spec):
        if spec is None:
            return None
        return fact(key, spec[0], source_type=spec[1], confidence=1.0 if spec[1] != "ai_extracted" else 0.95)

    prof = profile(
        black_ownership_pct=make("black_ownership_pct", own), bbbee_level=make("bbbee_level", level)
    )
    assert check(prof, "ownership_or_bbbee").outcome == expected


def test_ownership_low_confidence_alone_is_review():
    prof = profile(black_ownership_pct=fact("black_ownership_pct", 100, confidence=0.4), bbbee_level=None)
    assert check(prof, "ownership_or_bbbee").outcome == "needs_review"


def test_operating_region_confirmed_wording():
    prof = profile(
        service_regions=fact("service_regions", ["WC"], source_type="sme_confirmed", confidence=1.0)
    )
    c = check(prof, "operating_region")
    assert c.outcome == "fail"
    assert c.reason == "No Gauteng service region (confirmed: Western Cape only)."


def test_operating_region_multiple_regions():
    assert (
        check(profile(service_regions=fact("service_regions", ["WC", "GP"])), "operating_region").outcome
        == "pass"
    )


def test_infosec_policy_document_present_or_absent():
    assert check(profile(), "infosec_policy").outcome == "pass"
    other = DocumentRef(id=2, filename="Capability.pdf", doc_type="capability_statement")
    c = check(profile(documents=[other]), "infosec_policy")
    assert c.outcome == "needs_review" and "missing" in c.issues


def test_infosec_policy_is_not_judged_by_fields():
    prof = profile(documents=[])
    prof.facts["infosec_policy"] = fact("infosec_policy", True)
    assert check(prof, "infosec_policy").outcome == "needs_review"


def cert(holder, expiry):
    return {"holder": holder, "cert_name": "CompTIA A+", "expiry_date": expiry}


@pytest.mark.parametrize(
    ("certs", "min_count", "source_type", "expected", "issue"),
    [
        (
            [cert("A", "2028-01-01"), cert("B", "2028-01-01"), cert("C", "2026-05-31")],
            2,
            "ai_extracted",
            "pass",
            None,
        ),
        ([cert("A", "2028-01-01"), cert("B", "2027-02-16")], 2, "sme_confirmed", "needs_review", "outdated"),
        ([cert("A", "2028-01-01"), cert("B", "2027-02-26")], 2, "sme_confirmed", "needs_review", "outdated"),
        ([cert("A", "2028-01-01"), cert("B", None)], 2, "sme_confirmed", "needs_review", "unreadable"),
        ([cert("A", "2028-01-01"), cert("B", "soon")], 2, "sme_confirmed", "needs_review", "unreadable"),
        # gap of 2 but only one expired cert could close it
        ([cert("A", "2028-01-01"), cert("B", "2026-05-31")], 3, "sme_confirmed", "fail", "confirmed_failure"),
        (
            [cert("A", "2028-01-01"), cert("B", "2026-05-31")],
            3,
            "ai_extracted",
            "needs_review",
            "unconfirmed_failure",
        ),
        (
            [cert("A", "2028-01-01"), cert("B", "2026-05-31"), cert("C", None)],
            3,
            "sme_confirmed",
            "needs_review",
            "outdated",
        ),
        # one holder with two current certs is one technician
        ([cert("A", "2028-01-01"), cert("A", "2029-01-01")], 2, "sme_confirmed", "fail", "confirmed_failure"),
    ],
)
def test_certified_technicians(certs, min_count, source_type, expected, issue):
    opp = OpportunitySpec(
        id=1,
        closing_date=CLOSING,
        mandatory_criteria=[{"rule_type": "certified_technicians", "params": {"min_count": min_count}}],
    )
    conf = 0.95 if source_type == "ai_extracted" else 1.0
    prof = profile(certifications=fact("certifications", certs, source_type=source_type, confidence=conf))
    c = check(prof, "certified_technicians", opp)
    assert c.outcome == expected, c.reason
    if issue:
        assert issue in c.issues


def test_certified_technicians_pass_lists_current_certs():
    certs = [
        cert("A", "2028-03-31"),
        cert("B", "2027-09-30"),
        cert("C", "2029-01-31"),
        cert("D", "2026-05-31"),
    ]
    c = check(profile(certifications=fact("certifications", certs)), "certified_technicians")
    assert c.outcome == "pass"
    assert c.reason.startswith("3 technicians with current certifications (minimum 2)")
    assert len(c.details["current"]) == 3 and len(c.details["expired_before_closing"]) == 1


# ---------------------------------------------------------------------------
# Data consistency + aggregation
# ---------------------------------------------------------------------------


def test_data_consistency_conflict_on_used_field():
    f = conflict(
        "technician_count",
        (4, "ai_extracted", "B_Capability_Statement.pdf", "capability_statement"),
        (15, "sme_confirmed", "SME profile form", None),
    )
    result = evaluate(profile(technician_count=f), OPP)
    c = result.check("data_consistency")
    assert c.outcome == "needs_review" and c.group == "consistency"
    assert c.reason == "Technician count conflict: SME profile form 15, capability statement 4."
    assert {e.source_label for e in c.evidence} == {"SME profile form", "B_Capability_Statement.pdf"}
    assert result.status == "needs_review"
    assert all(ch.outcome == "pass" for ch in result.checks if ch.group == "mandatory")


def test_data_consistency_ignores_fields_the_opportunity_does_not_use():
    f = conflict(
        "company_name",
        ("A", "ai_extracted", "a.pdf", "capability_statement"),
        ("B", "sme_confirmed", "SME profile form", None),
    )
    assert check(profile(company_name=f), "data_consistency").outcome == "pass"
    no_capacity = OpportunitySpec(id=1, closing_date=CLOSING, mandatory_criteria=MANDATORY)
    tech = conflict(
        "technician_count",
        (4, "ai_extracted", "a.pdf", "capability_statement"),
        (15, "sme_confirmed", "SME profile form", None),
    )
    assert check(profile(technician_count=tech), "data_consistency", no_capacity).outcome == "pass"


def test_aggregation_fail_beats_needs_review():
    prof = profile(
        service_regions=fact("service_regions", ["WC"], source_type="sme_confirmed", confidence=1.0),
        pi_expiry_date=fact("pi_expiry_date", "2027-02-16"),
    )
    assert evaluate(prof, OPP).status == "not_eligible"
    assert aggregate(["pass", "needs_review", "fail"]) == "not_eligible"
    assert aggregate(["pass", "needs_review"]) == "needs_review"
    assert aggregate(["pass", "pass"]) == "eligible"


def test_deterministic_same_input_same_output():
    prof = profile(pi_expiry_date=fact("pi_expiry_date", "2027-02-16"))
    assert evaluate(prof, OPP).to_dict() == evaluate(prof, OPP).to_dict()


# ---------------------------------------------------------------------------
# Guard rails on the source
# ---------------------------------------------------------------------------

APP = Path(eligibility.__file__).resolve().parents[1]
SME_NAMES = ("thuto", "mmapula", "zola", "bright path", "brightpath", "lerato")


def test_engine_and_matching_have_no_sme_specific_logic():
    files = [*sorted((APP / "engine").glob("*.py")), APP / "services" / "matching.py"]
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for name in SME_NAMES:
            assert name not in text, f"{name!r} found in {path.name}"


def test_eligibility_does_not_import_ai():
    text = (APP / "engine" / "eligibility.py").read_text(encoding="utf-8")
    assert "app.ai" not in text and "gateway" not in text and "bedrock" not in text.lower()
