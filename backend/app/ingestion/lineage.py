"""Per-field lineage (plan A9): candidates, supersession, SME correction/confirmation, resolution.

Every profile fact is a row in profile_field_values. Nothing is overwritten: a newer value marks the
older one `superseded` (kept for lineage). resolve() turns the active candidates of one field into the
effective value the engine uses.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import ActorLike, write_audit
from app.config import LOW_CONFIDENCE
from app.models import Document, ProfileFieldValue

SOURCE_PRIORITY = {"verified": 3, "sme_confirmed": 2, "ai_extracted": 1}
SME_CONFIRMED_CONFIDENCE = 1.0


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def add_candidate(
    session: Session,
    sme_id: int,
    field_key: str,
    value: Any,
    source_type: str,
    *,
    document_id: int | None = None,
    source_label: str | None = None,
    page: int | None = None,
    span_start: int | None = None,
    span_end: int | None = None,
    quote: str | None = None,
    confidence: float | None = None,
    created_by_role: str | None = None,
    note: str | None = None,
) -> ProfileFieldValue:
    if source_type not in SOURCE_PRIORITY:
        raise ValueError(f"Unknown source_type: {source_type!r}")
    row = ProfileFieldValue(
        sme_id=sme_id,
        field_key=field_key,
        value=value,
        source_type=source_type,
        document_id=document_id,
        source_label=source_label,
        page=page,
        span_start=span_start,
        span_end=span_end,
        quote=quote,
        confidence=confidence,
        status="active",
        created_by_role=created_by_role,
        note=note,
    )
    session.add(row)
    session.flush()
    return row


def insert_extracted_fields(
    session: Session, document: Document, fields: list[dict[str, Any]], created_by_role: str | None
) -> list[ProfileFieldValue]:
    """One ai_extracted candidate per extracted field, labelled with the source document."""
    return [
        add_candidate(
            session,
            document.sme_id,
            f["field_key"],
            f.get("value"),
            "ai_extracted",
            document_id=document.id,
            source_label=document.filename,
            page=f.get("page"),
            span_start=f.get("span_start"),
            span_end=f.get("span_end"),
            quote=f.get("quote"),
            confidence=f.get("confidence"),
            created_by_role=created_by_role,
        )
        for f in fields
    ]


def active_candidates(session: Session, sme_id: int, field_key: str | None = None) -> list[ProfileFieldValue]:
    stmt = select(ProfileFieldValue).where(
        ProfileFieldValue.sme_id == sme_id, ProfileFieldValue.status == "active"
    )
    if field_key is not None:
        stmt = stmt.where(ProfileFieldValue.field_key == field_key)
    return list(session.scalars(stmt.order_by(ProfileFieldValue.id)))


def _supersede(rows: list[ProfileFieldValue], by: ProfileFieldValue | None) -> None:
    for row in rows:
        if by is not None and row.id == by.id:
            continue
        row.status = "superseded"
        row.superseded_by_id = by.id if by is not None else None


# ---------------------------------------------------------------------------
# Document supersession
# ---------------------------------------------------------------------------


def _doc_order(doc: Document) -> tuple[date, date]:
    return (doc.period_end or date.min, doc.issue_date or date.min)


def apply_document_supersession(session: Session, new_doc: Document) -> list[Document]:
    """Supersede older active documents of the same doc_type for the same SME.

    A document with a later (period_end, issue_date) supersedes the other; on a tie (including
    undated documents such as capability statements) the newer upload wins. The superseded
    document's active field values become `superseded`, pointing at the replacing value when the
    new document has one for the same field. Returns the documents that were superseded.
    """
    if not new_doc.doc_type or new_doc.doc_type == "other":
        return []
    others = list(session.scalars(
        select(Document).where(
            Document.sme_id == new_doc.sme_id,
            Document.doc_type == new_doc.doc_type,
            Document.id != new_doc.id,
            Document.superseded_by_document_id.is_(None),
        )
    ))
    superseded: list[Document] = []
    for old in others:
        if _doc_order(new_doc) >= _doc_order(old):
            loser, winner = old, new_doc
        else:
            loser, winner = new_doc, old
        loser.superseded_by_document_id = winner.id
        superseded.append(loser)
        winner_values = {
            v.field_key: v
            for v in session.scalars(
                select(ProfileFieldValue).where(
                    ProfileFieldValue.document_id == winner.id, ProfileFieldValue.status == "active"
                )
            )
        }
        for value in session.scalars(
            select(ProfileFieldValue).where(
                ProfileFieldValue.document_id == loser.id, ProfileFieldValue.status == "active"
            )
        ):
            value.status = "superseded"
            replacement = winner_values.get(value.field_key)
            value.superseded_by_id = replacement.id if replacement else None
        if loser is new_doc:
            break
    session.flush()
    return superseded


# ---------------------------------------------------------------------------
# SME correction / confirmation
# ---------------------------------------------------------------------------


def correct_field(
    session: Session,
    sme_id: int,
    field_key: str,
    value: Any,
    actor: ActorLike,
    note: str | None = None,
) -> ProfileFieldValue:
    """SME replaces a value: new sme_confirmed row, every active candidate superseded, audit logged."""
    old = active_candidates(session, sme_id, field_key)
    new = add_candidate(
        session,
        sme_id,
        field_key,
        value,
        "sme_confirmed",
        source_label="SME correction",
        confidence=SME_CONFIRMED_CONFIDENCE,
        created_by_role=actor.role,
        note=note,
    )
    _supersede(old, new)
    session.flush()
    write_audit(
        session, actor.role, actor.label, "sme_correction", "profile_field", new.id,
        {
            "sme_id": sme_id,
            "field_key": field_key,
            "old": [{"id": o.id, "value": o.value, "source_type": o.source_type} for o in old],
            "new": value,
            "note": note,
        },
    )
    return new


def confirm_field(
    session: Session,
    sme_id: int,
    field_key: str,
    actor: ActorLike,
    candidate_id: int | None = None,
) -> ProfileFieldValue:
    """SME confirms a value as correct: sme_confirmed copy (same value + source span), others superseded.

    With conflicting candidates the caller must say which one (candidate_id).
    """
    candidates = active_candidates(session, sme_id, field_key)
    if not candidates:
        raise LookupError(f"No value to confirm for {field_key}")
    if candidate_id is not None:
        chosen = next((c for c in candidates if c.id == candidate_id), None)
        if chosen is None:
            raise LookupError(f"Candidate {candidate_id} is not an active value of {field_key}")
    else:
        resolution = resolve(candidates)
        if resolution["status"] == "conflict":
            raise ValueError(f"{field_key} has conflicting values; choose which one to confirm")
        chosen = next(c for c in candidates if c.id == resolution["selected_id"])
    new = add_candidate(
        session,
        sme_id,
        field_key,
        chosen.value,
        "sme_confirmed",
        document_id=chosen.document_id,
        source_label=chosen.source_label,
        page=chosen.page,
        span_start=chosen.span_start,
        span_end=chosen.span_end,
        quote=chosen.quote,
        confidence=SME_CONFIRMED_CONFIDENCE,
        created_by_role=actor.role,
    )
    _supersede(candidates, new)
    session.flush()
    write_audit(
        session, actor.role, actor.label, "sme_confirmation", "profile_field", new.id,
        {
            "sme_id": sme_id,
            "field_key": field_key,
            "value": chosen.value,
            "confirmed_candidate_id": chosen.id,
            "previous_source_type": chosen.source_type,
        },
    )
    return new


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def normalize_value(value: Any) -> str:
    """Comparable form: case/whitespace-insensitive strings, order-insensitive lists of strings."""
    def norm(v: Any) -> Any:
        if isinstance(v, str):
            return " ".join(v.split()).lower()
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, list):
            items = [norm(i) for i in v]
            if all(isinstance(i, str) for i in items):
                return sorted(items)
            return items
        if isinstance(v, dict):
            return {k: norm(val) for k, val in v.items()}
        return v

    return json.dumps(norm(value), sort_keys=True)


def candidate_dict(c: ProfileFieldValue) -> dict[str, Any]:
    return {
        "id": c.id,
        "field_key": c.field_key,
        "value": c.value,
        "source_type": c.source_type,
        "document_id": c.document_id,
        "source_label": c.source_label,
        "page": c.page,
        "span_start": c.span_start,
        "span_end": c.span_end,
        "quote": c.quote,
        "confidence": c.confidence,
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "created_by_role": c.created_by_role,
        "note": c.note,
    }


def has_conflict(candidates: list[ProfileFieldValue]) -> bool:
    return len({normalize_value(c.value) for c in candidates}) > 1


def resolve(candidates: list[ProfileFieldValue]) -> dict[str, Any]:
    """Effective value of one field from its active candidates.

    status: missing (no candidates) | conflict (values differ; no value chosen) |
            low_confidence (best source is ai_extracted with confidence < LOW_CONFIDENCE) | ok.
    When values agree, the strongest source wins: verified > sme_confirmed > ai_extracted
    (ties: newest).
    """
    active = [c for c in candidates if c.status == "active"]
    listed = [candidate_dict(c) for c in active]
    if not active:
        return {"status": "missing", "value": None, "source_type": None, "confidence": None,
                "selected_id": None, "candidates": []}
    if has_conflict(active):
        return {"status": "conflict", "value": None, "source_type": None, "confidence": None,
                "selected_id": None, "candidates": listed}
    best = max(active, key=lambda c: (SOURCE_PRIORITY[c.source_type], c.id or 0))
    status = "ok"
    if best.source_type == "ai_extracted" and (best.confidence is None or best.confidence < LOW_CONFIDENCE):
        status = "low_confidence"
    return {"status": status, "value": best.value, "source_type": best.source_type,
            "confidence": best.confidence, "selected_id": best.id, "candidates": listed}


def resolve_field(session: Session, sme_id: int, field_key: str) -> dict[str, Any]:
    return resolve(active_candidates(session, sme_id, field_key))


def resolve_profile(session: Session, sme_id: int) -> dict[str, dict[str, Any]]:
    """Resolution of every field that has at least one active candidate."""
    by_field: dict[str, list[ProfileFieldValue]] = {}
    for c in active_candidates(session, sme_id):
        by_field.setdefault(c.field_key, []).append(c)
    return {key: resolve(rows) for key, rows in sorted(by_field.items())}
