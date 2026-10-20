"""Seed service on the real demo assets and committed AI cache (cached mode)."""

import pytest
from sqlalchemy import func, select

from app.audit import SystemActor
from app.ingestion import lineage
from app.models import SME, AIResult, AuditLog, Document, Embedding, Opportunity
from app.services import seed as seed_service


@pytest.fixture
def seeded(db):
    counts = seed_service.seed(db)
    db.commit()
    return counts


def sme(db, slug: str) -> SME:
    return db.scalars(select(SME).where(SME.slug == slug)).one()


def test_seed_counts(db, seeded):
    assert seeded["smes"] == 5
    assert seeded["documents"] == 20
    assert db.scalar(select(func.count()).select_from(SME)) == 5


def test_thuto_is_account_only(db, seeded):
    thuto = sme(db, "thuto")
    assert thuto.consent_status == "pending"
    assert db.scalar(select(func.count()).select_from(Document).where(Document.sme_id == thuto.id)) == 0


def test_four_smes_consented(db, seeded):
    granted = db.scalars(select(SME.slug).where(SME.consent_status == "granted")).all()
    assert sorted(granted) == ["brightpath", "lerato", "mmapula", "zola"]


def test_brightpath_technician_conflict_shows_both_sources(db, seeded):
    r = lineage.resolve_field(db, sme(db, "brightpath").id, "technician_count")
    assert r["status"] == "conflict"
    by_source = {c["source_type"]: c for c in r["candidates"]}
    assert by_source["sme_confirmed"]["value"] == 15
    assert by_source["sme_confirmed"]["source_label"] == "SME profile form"
    assert by_source["ai_extracted"]["value"] == 4
    assert by_source["ai_extracted"]["source_label"] == "BrightPath_Capability_Statement.pdf"
    assert by_source["ai_extracted"]["span_start"] is not None


def test_lerato_regions_confirmed(db, seeded):
    r = lineage.resolve_field(db, sme(db, "lerato").id, "service_regions")
    assert r["status"] == "ok" and r["value"] == ["WC"] and r["source_type"] == "sme_confirmed"


def test_zola_has_only_expiring_pi(db, seeded):
    zola = sme(db, "zola")
    names = db.scalars(select(Document.filename).where(Document.sme_id == zola.id)).all()
    assert "Zola_PI_Insurance_Schedule_Renewed.pdf" not in names
    assert lineage.resolve_field(db, zola.id, "pi_expiry_date")["value"] == "2027-02-16"


def test_opportunity_final_criteria_vs_raw_rfq(db, seeded):
    opp = db.scalars(select(Opportunity).where(Opportunity.status == "published")).one()
    pi = next(c for c in opp.mandatory_criteria if c["rule_type"] == "pi_insurance")
    assert pi["params"]["min_amount"] == 2_000_000
    assert "R1 million" in opp.raw_rfq_text
    assert opp.weights == {"capability": 40, "experience": 25, "capacity": 20, "location": 15}
    assert str(opp.closing_date) == "2027-02-26" and str(opp.contract_start) == "2027-04-01"
    assert opp.buyer_contact == "Naledi"
    closed = db.scalars(select(Opportunity).where(Opportunity.status == "closed")).all()
    assert len(closed) == 2


def test_extraction_audit_and_ai_results(db, seeded):
    audits = db.scalars(select(AuditLog).where(AuditLog.action == "extraction")).all()
    assert len(audits) == 20
    for a in audits:
        assert a.details["cache_hit"] is True
        assert a.details["provider"] and a.details["model_id"] and a.details["generated_by"]
    results = db.scalars(select(AIResult).where(AIResult.kind == "extraction")).all()
    assert len(results) == 20 and all(r.document_id for r in results)
    for r in db.scalars(select(AIResult)).all():
        assert (r.provider == "bedrock") == (r.generated_by == "bedrock")


def test_embeddings_stored_for_consented_smes_and_opportunity(db, seeded):
    rows = db.scalars(select(Embedding)).all()
    assert {r.owner_type for r in rows} == {"sme", "opportunity"}
    assert sum(r.owner_type == "sme" for r in rows) == 4


def test_reset_restores_seed_state(db, seeded):
    lineage.correct_field(db, sme(db, "zola").id, "technician_count", 99,
                          SystemActor(role="sme", label="SME: Zola Systems"))
    db.commit()
    counts = seed_service.reset(db)
    db.commit()
    assert counts["smes"] == 5
    assert lineage.resolve_field(db, sme(db, "zola").id, "technician_count")["value"] == 9
    actions = db.scalars(select(AuditLog.action)).all()
    assert "sme_correction" not in actions and actions.count("demo_reset") == 1
    assert db.scalar(select(func.min(SME.id))) == 1  # identities restarted
