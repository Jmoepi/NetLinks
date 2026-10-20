"""Matching on the real seed (cached AI mode): the demo-script outcomes come out of the engine."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.audit import SystemActor
from app.config import get_settings
from app.ingestion import lineage
from app.ingestion.pipeline import ingest_document
from app.models import SME, AuditLog, InfoRequest, MatchResult, Opportunity, ReadinessAction
from app.services import matching
from app.services import seed as seed_service

THUTO_FILES = [
    "Thuto_Capability_Statement.pdf",
    "Thuto_Technician_Certifications.pdf",
    "Thuto_InfoSec_POPIA_Policy.pdf",
]
BUYER = SystemActor(role="buyer", label="Buyer: Naledi (Ubuntu Office Parks)")
MANDATORY_RULES = [
    "tax_compliance",
    "csd_registration",
    "ownership_or_bbbee",
    "operating_region",
    "pi_insurance",
    "infosec_policy",
    "certified_technicians",
]


def asset(name: str) -> bytes:
    return (Path(get_settings().demo_assets_dir) / name).read_bytes()


def sme(db, slug: str) -> SME:
    return db.scalars(select(SME).where(SME.slug == slug)).one()


def sme_actor(s: SME) -> SystemActor:
    return SystemActor(role="sme", label=f"SME: {s.name}")


@pytest.fixture
def seeded(db):
    seed_service.seed(db)
    db.commit()
    return db


@pytest.fixture
def opp_id(seeded):
    return seeded.scalars(select(Opportunity.id).where(Opportunity.status == "published")).one()


def onboard_thuto(db, confirm_pi: bool = True) -> SME:
    """The live SME flow from the script: upload 3 PDFs, correct 9 -> 11 technicians, confirm PI, consent."""
    thuto = sme(db, "thuto")
    actor = sme_actor(thuto)
    for name in THUTO_FILES:
        ingest_document(db, thuto, name, asset(name), actor)
    assert lineage.resolve_field(db, thuto.id, "technician_count")["value"] == 9
    lineage.correct_field(db, thuto.id, "technician_count", 11, actor, note="Two new hires")
    if confirm_pi:
        lineage.confirm_field(db, thuto.id, "pi_cover_amount", actor)
    thuto.consent_status = "granted"
    db.commit()
    return thuto


def results_by_slug(db, run) -> dict[str, MatchResult]:
    return {db.get(SME, r.sme_id).slug: r for r in matching.run_results(db, run.id)}


def check(result: MatchResult, rule: str) -> dict:
    return next(c for c in result.checks if c["rule"] == rule)


def component(result: MatchResult, name: str) -> dict:
    return next(c for c in result.components if c["name"] == name)


def test_thuto_needs_review_on_pi_before_confirmation(seeded, opp_id):
    onboard_thuto(seeded, confirm_pi=False)
    thuto = results_by_slug(seeded, matching.run_match(seeded, opp_id, BUYER))["thuto"]
    assert thuto.status == "needs_review" and thuto.rank is None
    pi = check(thuto, "pi_insurance")
    assert pi["outcome"] == "needs_review" and "low_confidence" in pi["issues"]
    assert "R2 mil professional liability" in pi["reason"]
    assert [c["rule"] for c in thuto.checks if c["outcome"] != "pass"] == ["pi_insurance"]


def test_seed_outcomes_and_ranking(seeded, opp_id):
    onboard_thuto(seeded)
    run = matching.run_match(seeded, opp_id, BUYER)
    seeded.commit()
    r = results_by_slug(seeded, run)

    assert {slug: res.status for slug, res in r.items()} == {
        "thuto": "eligible",
        "mmapula": "eligible",
        "zola": "needs_review",
        "brightpath": "needs_review",
        "lerato": "not_eligible",
    }
    assert r["thuto"].rank == 1 and r["mmapula"].rank == 2
    assert all(r[s].rank is None for s in ("zola", "brightpath", "lerato"))
    assert r["thuto"].score_total > r["mmapula"].score_total
    assert all(res.score_total is not None for res in r.values())  # provisional scores shown
    assert run.counts == {
        "eligible": 2,
        "needs_review": 2,
        "not_eligible": 1,
        "considered": 5,
        "excluded_no_consent": 0,
    }
    assert run.ai_mode == "cached" and run.run_by_role == "buyer"

    # Thuto: all 7 mandatory checks green, each with document evidence; 3 current certifications.
    thuto = r["thuto"]
    mandatory = [c for c in thuto.checks if c["group"] == "mandatory"]
    assert [c["rule"] for c in mandatory] == MANDATORY_RULES
    for c in mandatory:
        assert c["outcome"] == "pass", c
        assert any(e["document_id"] for e in c["evidence"]), c["rule"]
    certs = check(thuto, "certified_technicians")
    assert len(certs["details"]["current"]) == 3
    assert certs["reason"].startswith("3 technicians with current certifications")
    assert certs["evidence"][0]["source_label"] == "Thuto_Technician_Certifications.pdf"
    assert check(thuto, "data_consistency")["outcome"] == "pass"

    # Mmapula: semantic match explained; capacity lower than Thuto's, 6 vs 8.
    mm_cap = component(r["mmapula"], "capacity")
    assert mm_cap["score"] < component(thuto, "capacity")["score"]
    assert "6 technicians vs 8 preferred" in mm_cap["explanation"]
    capability = component(r["mmapula"], "capability")
    assert "AI-assisted semantic match" in capability["explanation"]
    assert "device lifecycle, Microsoft 365 tenant administration" in capability["explanation"]
    assert capability["details"]["embedding_model_id"] == "local-lexicon-v1"
    assert 0 < capability["details"]["similarity"] < component(thuto, "capability")["details"]["similarity"]

    # Zola: outdated PI, not rejected.
    zola_pi = check(r["zola"], "pi_insurance")
    assert zola_pi["outcome"] == "needs_review" and "outdated" in zola_pi["issues"]
    assert zola_pi["reason"] == "Professional indemnity cover expires 10 days before the closing date."
    assert (
        zola_pi["details"]["expiry_date"] == "2027-02-16"
        and zola_pi["details"]["closing_date"] == "2027-02-26"
    )

    # Bright Path: conflict with both sources.
    bp = check(r["brightpath"], "data_consistency")
    assert bp["outcome"] == "needs_review"
    assert bp["reason"] == "Technician count conflict: SME profile form 15, capability statement 4."
    assert {e["source_label"] for e in bp["evidence"]} == {
        "SME profile form",
        "BrightPath_Capability_Statement.pdf",
    }
    assert all(c["outcome"] == "pass" for c in r["brightpath"].checks if c["group"] == "mandatory")

    # Lerato: confirmed Western Cape only.
    region = check(r["lerato"], "operating_region")
    assert region["outcome"] == "fail"
    assert region["reason"] == "No Gauteng service region (confirmed: Western Cape only)."

    audit = seeded.scalars(select(AuditLog).where(AuditLog.action == "match_run")).one()
    assert audit.actor_role == "buyer" and audit.details["counts"] == run.counts
    assert [x["rank"] for x in audit.details["ranking"]] == [1, 2]


def test_readiness_never_changes_ranks(seeded, opp_id):
    onboard_thuto(seeded)
    run = matching.run_match(seeded, opp_id, BUYER)
    seeded.commit()

    def snapshot():
        seeded.expire_all()
        return [
            (r.sme_id, r.status, r.rank, r.score_total, r.components, r.checks)
            for r in matching.run_results(seeded, run.id)
        ]

    before = snapshot()
    actions = matching.generate_readiness(seeded, run)
    seeded.commit()
    assert snapshot() == before

    by_sme = {}
    for a in seeded.scalars(select(ReadinessAction).where(ReadinessAction.run_id == run.id)):
        by_sme.setdefault(seeded.get(SME, a.sme_id).slug, []).append(a.text)
    assert len(actions) == sum(len(v) for v in by_sme.values())
    assert "Upload a renewed PI insurance schedule covering the contract start date." in by_sme["zola"]
    assert "This opportunity requires Gauteng operations." in by_sme["lerato"]
    assert any("SME profile form 15, capability statement 4" in t for t in by_sme["brightpath"])
    assert "thuto" not in by_sme

    # Regenerating replaces, never duplicates.
    matching.generate_readiness(seeded, run)
    seeded.commit()
    assert len(seeded.scalars(select(ReadinessAction).where(ReadinessAction.run_id == run.id)).all()) == len(
        actions
    )


def test_unconsented_smes_are_excluded(seeded, opp_id):
    onboard_thuto(seeded)
    mmapula = sme(seeded, "mmapula")
    mmapula.consent_status = "declined"
    seeded.commit()
    run = matching.run_match(seeded, opp_id, BUYER)
    r = results_by_slug(seeded, run)
    assert "mmapula" not in r
    assert run.counts["excluded_no_consent"] == 1 and run.counts["considered"] == 4
    assert r["thuto"].rank == 1


def test_pending_consent_excluded_by_default(seeded, opp_id):
    run = matching.run_match(seeded, opp_id, BUYER)
    r = results_by_slug(seeded, run)
    assert "thuto" not in r and run.counts["excluded_no_consent"] == 1
    assert r["mmapula"].rank == 1


def test_zola_eligible_after_renewed_pi(seeded, opp_id):
    onboard_thuto(seeded)
    first = results_by_slug(seeded, matching.run_match(seeded, opp_id, BUYER))
    assert first["zola"].status == "needs_review"

    zola = sme(seeded, "zola")
    name = "Zola_PI_Insurance_Schedule_Renewed.pdf"
    ingest_document(seeded, zola, name, asset(name), sme_actor(zola))
    seeded.commit()

    second = results_by_slug(seeded, matching.run_match(seeded, opp_id, BUYER))
    assert second["zola"].status == "eligible"
    assert check(second["zola"], "pi_insurance")["outcome"] == "pass"
    assert second["thuto"].rank == 1 and second["mmapula"].rank == 2 and second["zola"].rank == 3
    assert second["zola"].score_total == first["zola"].score_total  # PI renewal does not change fit


def test_awaiting_sme_flag_and_responded_on_upload(seeded, opp_id):
    zola = sme(seeded, "zola")
    seeded.add(
        InfoRequest(
            opportunity_id=opp_id,
            sme_id=zola.id,
            kind="information",
            message="Please upload your renewed professional indemnity schedule.",
        )
    )
    seeded.commit()
    run = matching.run_match(seeded, opp_id, BUYER)
    r = results_by_slug(seeded, run)
    assert r["zola"].awaiting_sme is True
    assert not any(res.awaiting_sme for slug, res in r.items() if slug != "zola")

    responded = matching.mark_requests_responded(seeded, zola.id, sme_actor(zola))
    seeded.commit()
    assert [q.status for q in responded] == ["responded"] and responded[0].responded_at is not None
    seeded.expire_all()
    assert results_by_slug(seeded, run)["zola"].awaiting_sme is False
    assert seeded.scalars(select(AuditLog).where(AuditLog.action == "info_request_responded")).one()
