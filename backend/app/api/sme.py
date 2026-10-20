"""SME endpoints (own profile only) plus the buyer/admin view of a consented SME profile."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.ai import gateway, prompts
from app.api.common import (
    CACHE_MISS_DOCUMENT,
    ai_error,
    document_dict,
    field_payload,
    iso,
    profile_payload,
    sme_dict,
    sme_documents,
)
from app.audit import write_audit
from app.ingestion import lineage
from app.ingestion.pdf_text import UnreadablePDF
from app.ingestion.pipeline import ingest_document
from app.models import SME, InfoRequest, MatchResult, Opportunity, ReadinessAction
from app.rbac import BuyerOrAdmin, DbSession, SmeActor
from app.services import matching

router = APIRouter(prefix="/api/sme/me", tags=["sme"])
smes_router = APIRouter(prefix="/api/smes", tags=["smes"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
INTEGER_FIELDS = {
    "technician_count",
    "years_trading",
    "pi_cover_amount",
    "black_ownership_pct",
    "bbbee_level",
}


class FieldCorrection(BaseModel):
    value: Any
    note: str | None = None


class FieldConfirmation(BaseModel):
    candidate_id: int | None = None


class ConsentBody(BaseModel):
    granted: bool


def _check_field_key(field_key: str) -> None:
    if field_key not in prompts.FIELD_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown profile field: {field_key}")


@router.get("")
def me(db: DbSession, actor: SmeActor) -> dict[str, Any]:
    return {
        **sme_dict(actor.sme),
        "documents": [document_dict(d) for d in sme_documents(db, actor.sme.id)],
    }


@router.get("/profile")
def my_profile(db: DbSession, actor: SmeActor) -> dict[str, Any]:
    return profile_payload(db, actor.sme)


@router.post("/documents")
def upload_documents(
    files: Annotated[list[UploadFile], File()], db: DbSession, actor: SmeActor
) -> dict[str, Any]:
    """Ingest one or more PDFs (all or nothing). Uploading also answers the SME's open info requests."""
    docs = []
    try:
        for upload in files:
            data = upload.file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{upload.filename} is larger than 10 MB."
                )
            docs.append(ingest_document(db, actor.sme, upload.filename or "document.pdf", data, actor))
        responded = matching.mark_requests_responded(db, actor.sme.id, actor)
    except (gateway.CacheMiss, gateway.LiveUnavailable) as exc:
        db.rollback()
        raise ai_error(exc, CACHE_MISS_DOCUMENT) from exc
    except UnreadablePDF as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "The file could not be read as a text PDF."
        ) from exc
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return {
        "documents": [document_dict(d) for d in docs],
        "responded_info_request_ids": [r.id for r in responded],
    }


@router.patch("/profile/fields/{field_key}")
def correct_field(field_key: str, body: FieldCorrection, db: DbSession, actor: SmeActor) -> dict[str, Any]:
    _check_field_key(field_key)
    value = body.value
    if field_key in INTEGER_FIELDS and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{field_key} must be a whole number.")
    if value is None or (isinstance(value, str) and not value.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A value is required.")
    lineage.correct_field(db, actor.sme.id, field_key, value, actor, note=body.note)
    db.commit()
    return field_payload(field_key, lineage.resolve_field(db, actor.sme.id, field_key))


@router.post("/profile/fields/{field_key}/confirm")
def confirm_field(
    field_key: str, db: DbSession, actor: SmeActor, body: FieldConfirmation | None = None
) -> dict[str, Any]:
    _check_field_key(field_key)
    try:
        lineage.confirm_field(
            db, actor.sme.id, field_key, actor, candidate_id=body.candidate_id if body else None
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    db.commit()
    return field_payload(field_key, lineage.resolve_field(db, actor.sme.id, field_key))


@router.post("/consent")
def consent(body: ConsentBody, db: DbSession, actor: SmeActor) -> dict[str, Any]:
    sme = actor.sme
    previous = sme.consent_status
    sme.consent_status = "granted" if body.granted else "declined"
    sme.consent_at = datetime.now(UTC)
    write_audit(
        db,
        actor,
        "consent",
        "sme",
        sme.id,
        {"sme_id": sme.id, "granted": body.granted, "previous": previous},
    )
    db.commit()
    return sme_dict(sme)


def _request_dict(req: InfoRequest, opp: Opportunity | None) -> dict[str, Any]:
    return {
        "id": req.id,
        "opportunity_id": req.opportunity_id,
        "opportunity_title": opp.title if opp else None,
        "buyer_org": opp.buyer_org if opp else None,
        "kind": req.kind,
        "message": req.message,
        "status": req.status,
        "created_at": iso(req.created_at),
        "responded_at": iso(req.responded_at),
    }


@router.get("/readiness")
def readiness(db: DbSession, actor: SmeActor) -> dict[str, Any]:
    """Buyer requests, readiness actions and the SME's latest status per published opportunity."""
    sme = actor.sme
    requests = db.scalars(
        select(InfoRequest).where(InfoRequest.sme_id == sme.id).order_by(InfoRequest.id.desc())
    ).all()
    opportunities = []
    for opp in db.scalars(
        select(Opportunity).where(Opportunity.status == "published").order_by(Opportunity.id)
    ):
        run = matching.latest_run(db, opp.id)
        result = (
            db.scalars(
                select(MatchResult).where(MatchResult.run_id == run.id, MatchResult.sme_id == sme.id)
            ).first()
            if run
            else None
        )
        actions = (
            db.scalars(
                select(ReadinessAction)
                .where(ReadinessAction.run_id == run.id, ReadinessAction.sme_id == sme.id)
                .order_by(ReadinessAction.id)
            ).all()
            if run
            else []
        )
        opportunities.append(
            {
                "opportunity_id": opp.id,
                "title": opp.title,
                "buyer_org": opp.buyer_org,
                "closing_date": iso(opp.closing_date),
                "run_id": run.id if run else None,
                "run_at": iso(run.run_at) if run else None,
                "status": result.status if result else None,
                "awaiting_sme": result.awaiting_sme if result else False,
                "checks": result.checks if result else [],
                "actions": [{"category": a.category, "text": a.text} for a in actions],
            }
        )
    return {
        "sme": sme_dict(sme),
        "requests": [_request_dict(r, db.get(Opportunity, r.opportunity_id)) for r in requests],
        "opportunities": opportunities,
    }


@smes_router.get("/{slug}/profile")
def sme_profile(slug: str, db: DbSession, actor: BuyerOrAdmin) -> dict[str, Any]:
    """Buyers only see SMEs that consented to share their profile."""
    sme = db.scalars(select(SME).where(SME.slug == slug)).first()
    if sme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SME not found.")
    if actor.role == "buyer" and sme.consent_status != "granted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This SME has not consented to share its profile.")
    return profile_payload(db, sme)
