"""Field lineage: supersession, SME correction/confirmation, conflicts, resolution statuses."""

from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.ingestion import lineage
from app.ingestion.pipeline import ingest_document
from app.models import SME, AuditLog, Document, ProfileFieldValue

ASSETS = Path(get_settings().demo_assets_dir)


@dataclass(frozen=True)
class Actor:
    role: str = "sme"
    label: str = "SME: Test Co"


ACTOR = Actor()


@pytest.fixture
def sme(db) -> SME:
    row = SME(slug="testco", name="Test Co")
    db.add(row)
    db.flush()
    return row


def pfv(value, source_type="ai_extracted", confidence=0.95, id_=None) -> ProfileFieldValue:
    return ProfileFieldValue(id=id_, sme_id=1, field_key="technician_count", value=value,
                             source_type=source_type, confidence=confidence, status="active")


# --- pure resolution -------------------------------------------------------


def test_resolve_missing():
    assert lineage.resolve([])["status"] == "missing"


def test_resolve_ok_and_source_preference():
    r = lineage.resolve([pfv(4, id_=1), pfv(4, "verified", None, id_=2), pfv(4, "sme_confirmed", 1.0, id_=3)])
    assert r["status"] == "ok"
    assert r["value"] == 4
    assert r["source_type"] == "verified"
    assert len(r["candidates"]) == 3


def test_resolve_low_confidence_only_for_ai_values():
    assert lineage.resolve([pfv(2_000_000, confidence=0.5, id_=1)])["status"] == "low_confidence"
    assert lineage.resolve([pfv(2_000_000, "sme_confirmed", 0.5, id_=1)])["status"] == "ok"


def test_resolve_conflict_has_no_value_and_lists_both():
    r = lineage.resolve([pfv(15, "sme_confirmed", 1.0, id_=1), pfv(4, id_=2)])
    assert r["status"] == "conflict"
    assert r["value"] is None
    assert {c["value"] for c in r["candidates"]} == {15, 4}


def test_normalized_values_agree():
    assert not lineage.has_conflict([pfv(["GP", "WC"], id_=1), pfv(["wc", "gp"], id_=2)])
    assert not lineage.has_conflict([pfv(9, id_=1), pfv(9.0, id_=2)])


# --- DB-backed lineage -----------------------------------------------------


def test_correction_supersedes_ai_value(db, sme):
    ai = lineage.add_candidate(db, sme.id, "technician_count", 9, "ai_extracted", confidence=0.95,
                               source_label="Doc.pdf")
    new = lineage.correct_field(db, sme.id, "technician_count", 11, ACTOR, note="two new hires")
    db.refresh(ai)
    assert ai.status == "superseded" and ai.superseded_by_id == new.id
    r = lineage.resolve_field(db, sme.id, "technician_count")
    assert r["status"] == "ok" and r["value"] == 11 and r["source_type"] == "sme_confirmed"
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "sme_correction")).one()
    assert audit.details["new"] == 11 and audit.details["old"][0]["value"] == 9
    assert audit.actor_role == "sme"


def test_confirm_changes_source_type_and_keeps_span(db, sme):
    ai = lineage.add_candidate(db, sme.id, "pi_cover_amount", 2_000_000, "ai_extracted", confidence=0.5,
                               page=1, span_start=10, span_end=40, quote="R2 mil")
    assert lineage.resolve_field(db, sme.id, "pi_cover_amount")["status"] == "low_confidence"
    confirmed = lineage.confirm_field(db, sme.id, "pi_cover_amount", ACTOR)
    assert (confirmed.page, confirmed.span_start, confirmed.span_end) == (1, 10, 40)
    db.refresh(ai)
    assert ai.status == "superseded"
    r = lineage.resolve_field(db, sme.id, "pi_cover_amount")
    assert r["status"] == "ok" and r["source_type"] == "sme_confirmed" and r["value"] == 2_000_000
    assert db.scalars(select(AuditLog).where(AuditLog.action == "sme_confirmation")).one()


def test_conflict_detection_and_explicit_confirmation(db, sme):
    form = lineage.add_candidate(db, sme.id, "technician_count", 15, "sme_confirmed",
                                 source_label="SME profile form", confidence=1.0)
    lineage.add_candidate(db, sme.id, "technician_count", 4, "ai_extracted", confidence=0.95,
                          source_label="Capability.pdf")
    r = lineage.resolve_field(db, sme.id, "technician_count")
    assert r["status"] == "conflict"
    assert {c["source_label"] for c in r["candidates"]} == {"SME profile form", "Capability.pdf"}
    with pytest.raises(ValueError):
        lineage.confirm_field(db, sme.id, "technician_count", ACTOR)
    lineage.confirm_field(db, sme.id, "technician_count", ACTOR, candidate_id=form.id)
    r = lineage.resolve_field(db, sme.id, "technician_count")
    assert r["status"] == "ok" and r["value"] == 15


def ingest(db, sme, filename: str) -> Document:
    return ingest_document(db, sme, filename, (ASSETS / filename).read_bytes(), ACTOR, mode="cached")


def test_document_supersession_by_later_period_end(db, sme):
    old = ingest(db, sme, "Zola_PI_Insurance_Schedule.pdf")
    assert lineage.resolve_field(db, sme.id, "pi_expiry_date")["value"] == "2027-02-16"
    new = ingest(db, sme, "Zola_PI_Insurance_Schedule_Renewed.pdf")
    db.refresh(old)
    assert old.superseded_by_document_id == new.id
    r = lineage.resolve_field(db, sme.id, "pi_expiry_date")
    assert r["status"] == "ok" and r["value"] == "2028-02-16"  # supersession, not a conflict
    old_values = db.scalars(select(ProfileFieldValue).where(ProfileFieldValue.document_id == old.id)).all()
    assert old_values and all(v.status == "superseded" and v.superseded_by_id for v in old_values)


def test_older_document_uploaded_later_does_not_win(db, sme):
    new = ingest(db, sme, "Zola_PI_Insurance_Schedule_Renewed.pdf")
    old = ingest(db, sme, "Zola_PI_Insurance_Schedule.pdf")
    assert old.superseded_by_document_id == new.id
    assert lineage.resolve_field(db, sme.id, "pi_expiry_date")["value"] == "2028-02-16"
    docs = db.scalars(select(Document).where(Document.superseded_by_document_id.is_(None))).all()
    assert [d.id for d in docs] == [new.id]
