"""Shared response shapes and error mapping for the API routers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import gateway, prompts
from app.engine.eligibility import field_label
from app.ingestion import lineage
from app.models import SME, Document

CACHE_MISS_DOCUMENT = "No cached AI result for this document. An admin can switch AI mode to Live."
CACHE_MISS_RFQ = "No cached AI result for this RFQ text. An admin can switch AI mode to Live."
CACHE_MISS_EMBEDDING = (
    "No cached AI result for the opportunity's capability text. An admin can switch AI mode to Live."
)
LIVE_UNAVAILABLE = "Live AI mode is unavailable: Amazon Bedrock credentials or model IDs are not configured."

BADGES = {"ai_extracted": "AI-extracted", "sme_confirmed": "SME-confirmed", "verified": "Verified"}


def ai_error(exc: Exception, cache_miss_message: str) -> HTTPException:
    """CacheMiss -> 409, LiveUnavailable -> 503 (plan A8)."""
    if isinstance(exc, gateway.CacheMiss):
        return HTTPException(status.HTTP_409_CONFLICT, cache_miss_message)
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, LIVE_UNAVAILABLE)


def iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def sme_dict(sme: SME) -> dict[str, Any]:
    return {
        "id": sme.id,
        "slug": sme.slug,
        "name": sme.name,
        "base_town": sme.base_town,
        "province": sme.province,
        "size_band": sme.size_band,
        "employees": sme.employees,
        "consent_status": sme.consent_status,
        "consent_at": iso(sme.consent_at),
    }


def document_dict(doc: Document) -> dict[str, Any]:
    return {
        "id": doc.id,
        "sme_id": doc.sme_id,
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "issue_date": iso(doc.issue_date),
        "period_end": iso(doc.period_end),
        "uploaded_at": iso(doc.uploaded_at),
        "uploaded_by_role": doc.uploaded_by_role,
        "superseded_by_document_id": doc.superseded_by_document_id,
        "page_count": len(doc.pages_text or []),
    }


def sme_documents(session: Session, sme_id: int) -> list[Document]:
    return list(session.scalars(select(Document).where(Document.sme_id == sme_id).order_by(Document.id)))


def _candidate(c: dict[str, Any]) -> dict[str, Any]:
    return {**c, "badge": BADGES.get(c["source_type"])}


def field_payload(field_key: str, resolution: dict[str, Any]) -> dict[str, Any]:
    candidates = [_candidate(c) for c in resolution["candidates"]]
    selected = next((c for c in candidates if c["id"] == resolution["selected_id"]), None)
    return {
        "field_key": field_key,
        "label": field_label(field_key),
        "status": resolution["status"],  # ok | missing | conflict | low_confidence
        "value": resolution["value"],
        "source_type": resolution["source_type"],
        "badge": BADGES.get(resolution["source_type"]),
        "confidence": resolution["confidence"],
        "low_confidence": resolution["status"] == "low_confidence",
        "conflict": resolution["status"] == "conflict",
        "selected": selected,
        "candidates": candidates,
    }


def profile_payload(session: Session, sme: SME) -> dict[str, Any]:
    """Every field key in a fixed order (missing ones included) with lineage, badges and flags."""
    resolved = lineage.resolve_profile(session, sme.id)
    fields = [field_payload(key, resolved.get(key) or lineage.resolve([])) for key in prompts.FIELD_KEYS]
    return {
        "sme": sme_dict(sme),
        "fields": fields,
        "conflicts": [f["field_key"] for f in fields if f["conflict"]],
        "low_confidence": [f["field_key"] for f in fields if f["low_confidence"]],
        "documents": [document_dict(d) for d in sme_documents(session, sme.id)],
    }
