"""Document text for the source viewer (spans are offsets into pages[page - 1])."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.common import document_dict
from app.models import SME, Document
from app.rbac import CurrentActor, DbSession

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/{document_id}/text")
def document_text(document_id: int, db: DbSession, actor: CurrentActor) -> dict[str, Any]:
    """SME: own documents only. Buyer: only documents of SMEs that consented. Admin: all."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    sme = db.get(SME, doc.sme_id)
    if actor.role == "sme" and actor.sme.id != doc.sme_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "SMEs can only view their own documents.")
    if actor.role == "buyer" and sme.consent_status != "granted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This SME has not consented to share its profile.")
    return {
        **document_dict(doc),
        "sme_slug": sme.slug,
        "sme_name": sme.name,
        "pages": list(doc.pages_text or []),
    }
