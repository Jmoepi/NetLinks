"""Buyer opportunity endpoints: requirements editor, RFQ structuring, matching, requests and shortlist.

Buyers only see and act on their own organisation's opportunities; the admin can read all of them.
Engine ranks are never altered by shortlist decisions: a reorder is an override with a written reason.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import gateway, prompts
from app.api.common import CACHE_MISS_EMBEDDING, CACHE_MISS_RFQ, ai_error, iso
from app.audit import write_audit
from app.engine import scoring
from app.engine.eligibility import rand
from app.models import SME, AIResult, InfoRequest, MatchResult, MatchRun, Opportunity, ShortlistEntry
from app.rbac import Actor, BuyerActor, BuyerOrAdmin, DbSession
from app.services import matching

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

GROUPS = ("eligible", "needs_review", "not_eligible")
NUMERIC_PARAMS = {
    "min_amount",
    "min_black_ownership_pct",
    "max_bbbee_level",
    "min_count",
    "min_years",
    "min_client_users",
    "min_technicians",
    "full_score_km",
    "zero_score_km",
}
REASON_REQUIRED = "A written reason is required to change the shortlist order."


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------


class Criterion(BaseModel):
    rule_type: str
    params: dict[str, Any] = Field(default_factory=dict)
    source_quote: str | None = None


class OpportunityUpdate(BaseModel):
    mandatory_criteria: list[Criterion]
    preferred_criteria: list[Criterion]
    weights: dict[str, Any]
    # ai_results.id returned by structure-rfq when the editor was loaded from an AI proposal; the
    # requirement_edit audit then records the buyer's changes against that proposal (e.g. R1m -> R2m).
    proposal_ai_result_id: int | None = None


class StructureRfqBody(BaseModel):
    raw_text: str | None = None


class InfoRequestBody(BaseModel):
    sme_slug: str
    kind: Literal["information", "clarification"]
    message: Annotated[str, Field(min_length=1, max_length=2000)]


class ShortlistAddBody(BaseModel):
    sme_slug: str


class ShortlistOrderBody(BaseModel):
    sme_slugs: list[str]
    reason: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_opportunity(db: Session, opportunity_id: int, actor: Actor) -> Opportunity:
    opp = db.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found.")
    if actor.role == "buyer" and opp.buyer_org != actor.buyer_org:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This opportunity belongs to another buyer.")
    return opp


def _sme_by_slug(db: Session, slug: str) -> SME:
    sme = db.scalars(select(SME).where(SME.slug == slug)).first()
    if sme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"SME not found: {slug}")
    return sme


def _run_dict(run: MatchRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "opportunity_id": run.opportunity_id,
        "run_at": iso(run.run_at),
        "run_by_role": run.run_by_role,
        "ai_mode": run.ai_mode,
        "counts": run.counts,
    }


def _summary(db: Session, opp: Opportunity) -> dict[str, Any]:
    run = matching.latest_run(db, opp.id)
    return {
        "id": opp.id,
        "title": opp.title,
        "buyer_org": opp.buyer_org,
        "buyer_contact": opp.buyer_contact,
        "status": opp.status,
        "closing_date": iso(opp.closing_date),
        "contract_start": iso(opp.contract_start),
        "latest_run": _run_dict(run) if run else None,
    }


def _detail(db: Session, opp: Opportunity) -> dict[str, Any]:
    return {
        **_summary(db, opp),
        "description": opp.description,
        "raw_rfq_text": opp.raw_rfq_text,
        "weights": opp.weights,
        "mandatory_criteria": opp.mandatory_criteria,
        "preferred_criteria": opp.preferred_criteria,
        "capability_text": opp.capability_text,
    }


def _clean_criteria(items: list[Criterion], catalog: dict[str, str], group: str) -> list[dict[str, Any]]:
    """Only catalog rule types (no free-form rules reach the engine), each once, numeric params >= 0."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in items:
        if c.rule_type not in catalog:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown {group} rule type: {c.rule_type}"
            )
        if c.rule_type in seen:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Duplicate {group} rule type: {c.rule_type}"
            )
        seen.add(c.rule_type)
        for key in NUMERIC_PARAMS & c.params.keys():
            value = c.params[key]
            if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"{c.rule_type}.{key} must be a number of 0 or more.",
                )
        item: dict[str, Any] = {"rule_type": c.rule_type, "params": dict(c.params)}
        if c.source_quote:
            item["source_quote"] = c.source_quote
        out.append(item)
    return out


def _fmt(param: str | None, value: Any) -> str:
    if value is None:
        return "none"
    if param == "min_amount" and isinstance(value, int | float):
        return rand(value)
    return str(value)


def criteria_changes(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> list[dict[str, Any]]:
    """Param-level differences between two criteria sets (source quotes ignored)."""
    changes: list[dict[str, Any]] = []
    for group in ("mandatory", "preferred"):
        b = {c["rule_type"]: c.get("params") or {} for c in before.get(group) or []}
        a = {c["rule_type"]: c.get("params") or {} for c in after.get(group) or []}
        for rule in dict.fromkeys([*b, *a]):
            if rule not in a or rule not in b:
                change = "removed" if rule not in a else "added"
                changes.append(
                    {
                        "group": group,
                        "rule_type": rule,
                        "change": change,
                        "param": None,
                        "from": b.get(rule),
                        "to": a.get(rule),
                        "summary": f"{rule}: {change}",
                    }
                )
                continue
            for param in dict.fromkeys([*b[rule], *a[rule]]):
                old, new = b[rule].get(param), a[rule].get(param)
                if old != new:
                    changes.append(
                        {
                            "group": group,
                            "rule_type": rule,
                            "change": "changed",
                            "param": param,
                            "from": old,
                            "to": new,
                            "summary": f"{rule}.{param}: {_fmt(param, old)} -> {_fmt(param, new)}",
                        }
                    )
    return changes


def _criteria(mandatory: Any, preferred: Any) -> dict[str, list[dict]]:
    return {"mandatory": list(mandatory or []), "preferred": list(preferred or [])}


def _request_dict(req: InfoRequest) -> dict[str, Any]:
    return {
        "id": req.id,
        "opportunity_id": req.opportunity_id,
        "sme_id": req.sme_id,
        "kind": req.kind,
        "message": req.message,
        "status": req.status,
        "created_at": iso(req.created_at),
        "responded_at": iso(req.responded_at),
    }


def _shortlist(db: Session, opp_id: int, run: MatchRun | None) -> list[dict[str, Any]]:
    results = {r.sme_id: r for r in matching.run_results(db, run.id)} if run else {}
    entries = db.scalars(
        select(ShortlistEntry)
        .where(ShortlistEntry.opportunity_id == opp_id)
        .order_by(ShortlistEntry.position)
    ).all()
    out = []
    for e in entries:
        sme = db.get(SME, e.sme_id)
        result = results.get(e.sme_id)
        out.append(
            {
                "sme_slug": sme.slug,
                "sme_name": sme.name,
                "position": e.position,
                "engine_rank": result.rank if result else None,
                "status": result.status if result else None,
                "added_at": iso(e.added_at),
            }
        )
    return out


def run_payload(db: Session, opp: Opportunity) -> dict[str, Any]:
    """Latest run with results grouped by status (eligible by rank; others by provisional score)."""
    run = matching.latest_run(db, opp.id)
    groups: dict[str, list[dict[str, Any]]] = {g: [] for g in GROUPS}
    if run is not None:
        requests: dict[int, list[dict[str, Any]]] = {}
        for req in db.scalars(
            select(InfoRequest).where(InfoRequest.opportunity_id == opp.id).order_by(InfoRequest.id)
        ):
            requests.setdefault(req.sme_id, []).append(_request_dict(req))
        for r in matching.run_results(db, run.id):
            sme = db.get(SME, r.sme_id)
            groups[r.status].append(
                {
                    "sme": {
                        "id": sme.id,
                        "slug": sme.slug,
                        "name": sme.name,
                        "base_town": sme.base_town,
                        "province": sme.province,
                        "size_band": sme.size_band,
                    },
                    "status": r.status,
                    "rank": r.rank,
                    "score_total": r.score_total,
                    "provisional": r.status != "eligible",
                    "awaiting_sme": r.awaiting_sme,
                    "checks": r.checks,
                    "components": r.components,
                    "info_requests": requests.get(sme.id, []),
                }
            )
        groups["eligible"].sort(key=lambda x: x["rank"])
        for g in ("needs_review", "not_eligible"):
            groups[g].sort(key=lambda x: (-(x["score_total"] or 0), x["sme"]["name"]))
    return {
        "opportunity_id": opp.id,
        "run": _run_dict(run) if run else None,
        "groups": groups,
        "shortlist": _shortlist(db, opp.id, run),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
def list_opportunities(db: DbSession, actor: BuyerOrAdmin) -> list[dict[str, Any]]:
    stmt = select(Opportunity).order_by(Opportunity.id)
    if actor.role == "buyer":
        stmt = stmt.where(Opportunity.buyer_org == actor.buyer_org)
    return [_summary(db, o) for o in db.scalars(stmt)]


@router.get("/{opportunity_id}")
def get_opportunity(opportunity_id: int, db: DbSession, actor: BuyerOrAdmin) -> dict[str, Any]:
    return _detail(db, _get_opportunity(db, opportunity_id, actor))


@router.put("/{opportunity_id}")
def update_opportunity(
    opportunity_id: int, body: OpportunityUpdate, db: DbSession, actor: BuyerActor
) -> dict[str, Any]:
    opp = _get_opportunity(db, opportunity_id, actor)
    try:
        weights = scoring.validate_weights(body.weights)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    new = {
        "mandatory": _clean_criteria(body.mandatory_criteria, prompts.MANDATORY_RULE_TYPES, "mandatory"),
        "preferred": _clean_criteria(body.preferred_criteria, prompts.PREFERRED_RULE_TYPES, "preferred"),
    }
    proposal_changes = None
    if body.proposal_ai_result_id is not None:
        proposal = db.get(AIResult, body.proposal_ai_result_id)
        if proposal is None or proposal.kind != "rfq_structuring":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown RFQ structuring proposal.")
        proposal_criteria = _criteria(
            proposal.result.get("mandatory_criteria"), proposal.result.get("preferred_criteria")
        )
        proposal_changes = criteria_changes(proposal_criteria, new)

    previous = _criteria(opp.mandatory_criteria, opp.preferred_criteria)
    previous_weights = dict(opp.weights or {})
    details = {
        "opportunity_id": opp.id,
        "changes_vs_previous": criteria_changes(previous, new),
        "proposal_ai_result_id": body.proposal_ai_result_id,
        "changes_vs_proposal": proposal_changes,
        "weights": {"from": previous_weights, "to": weights} if previous_weights != weights else None,
    }
    opp.mandatory_criteria = new["mandatory"]
    opp.preferred_criteria = new["preferred"]
    opp.weights = weights
    capability = next((c for c in new["preferred"] if c["rule_type"] == "capability"), None)
    if capability and capability["params"].get("text"):
        opp.capability_text = capability["params"]["text"]
    write_audit(db, actor, "requirement_edit", "opportunity", opp.id, details)
    db.commit()
    return _detail(db, opp)


@router.post("/{opportunity_id}/structure-rfq")
def structure_rfq(
    opportunity_id: int, db: DbSession, actor: BuyerActor, body: StructureRfqBody | None = None
) -> dict[str, Any]:
    """AI proposal for the editor (unsaved): mandatory vs preferred criteria from the raw RFQ text."""
    opp = _get_opportunity(db, opportunity_id, actor)
    text = (body.raw_text if body and body.raw_text and body.raw_text.strip() else None) or opp.raw_rfq_text
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Paste the RFQ text first.")
    try:
        outcome, row = gateway.structure_rfq(db, text)
    except (gateway.CacheMiss, gateway.LiveUnavailable) as exc:
        db.rollback()
        raise ai_error(exc, CACHE_MISS_RFQ) from exc
    write_audit(
        db,
        actor,
        "rfq_structured",
        "opportunity",
        opp.id,
        {
            "opportunity_id": opp.id,
            "ai_result_id": row.id,
            "provider": outcome.provider,
            "model_id": outcome.model_id,
            "generated_by": outcome.generated_by,
            "cache_hit": outcome.cache_hit,
        },
    )
    db.commit()
    return {
        "ai_result_id": row.id,
        "provider": outcome.provider,
        "model_id": outcome.model_id,
        "generated_by": outcome.generated_by,
        "generated_at": iso(outcome.generated_at),
        "cache_hit": outcome.cache_hit,
        "proposal": outcome.result,
    }


@router.post("/{opportunity_id}/match-runs")
def create_match_run(opportunity_id: int, db: DbSession, actor: BuyerActor) -> dict[str, Any]:
    opp = _get_opportunity(db, opportunity_id, actor)
    try:
        run = matching.run_match(db, opp.id, actor)
    except (gateway.CacheMiss, gateway.LiveUnavailable) as exc:
        db.rollback()
        raise ai_error(exc, CACHE_MISS_EMBEDDING) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    matching.generate_readiness(db, run)
    db.commit()
    return run_payload(db, opp)


@router.get("/{opportunity_id}/match-runs/latest")
def latest_match_run(opportunity_id: int, db: DbSession, actor: BuyerOrAdmin) -> dict[str, Any]:
    return run_payload(db, _get_opportunity(db, opportunity_id, actor))


@router.post("/{opportunity_id}/info-requests")
def create_info_request(
    opportunity_id: int, body: InfoRequestBody, db: DbSession, actor: BuyerActor
) -> dict[str, Any]:
    opp = _get_opportunity(db, opportunity_id, actor)
    sme = _sme_by_slug(db, body.sme_slug)
    if sme.consent_status != "granted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This SME has not consented to share its profile.")
    message = body.message.strip()
    if not message:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A message is required.")
    req = InfoRequest(opportunity_id=opp.id, sme_id=sme.id, kind=body.kind, message=message)
    db.add(req)
    db.flush()
    matching.refresh_awaiting(db, opp.id, sme.id)
    write_audit(
        db,
        actor,
        "info_request",
        "info_request",
        req.id,
        {
            "opportunity_id": opp.id,
            "sme_id": sme.id,
            "sme_slug": sme.slug,
            "kind": req.kind,
            "message": message,
        },
    )
    db.commit()
    run = matching.latest_run(db, opp.id)
    result = (
        db.scalars(
            select(MatchResult).where(MatchResult.run_id == run.id, MatchResult.sme_id == sme.id)
        ).first()
        if run
        else None
    )
    return {**_request_dict(req), "sme_slug": sme.slug, "awaiting_sme": bool(result and result.awaiting_sme)}


@router.post("/{opportunity_id}/shortlist")
def add_to_shortlist(
    opportunity_id: int, body: ShortlistAddBody, db: DbSession, actor: BuyerActor
) -> dict[str, Any]:
    opp = _get_opportunity(db, opportunity_id, actor)
    sme = _sme_by_slug(db, body.sme_slug)
    run = matching.latest_run(db, opp.id)
    result = (
        db.scalars(
            select(MatchResult).where(MatchResult.run_id == run.id, MatchResult.sme_id == sme.id)
        ).first()
        if run
        else None
    )
    if result is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Run matching first: this SME is not in the latest results."
        )
    if db.get(ShortlistEntry, (opp.id, sme.id)) is None:
        position = (
            db.scalar(
                select(func.max(ShortlistEntry.position)).where(ShortlistEntry.opportunity_id == opp.id)
            )
            or 0
        ) + 1
        db.add(ShortlistEntry(opportunity_id=opp.id, sme_id=sme.id, position=position))
        db.flush()
        write_audit(
            db,
            actor,
            "shortlist_decision",
            "shortlist",
            f"{opp.id}:{sme.id}",
            {
                "opportunity_id": opp.id,
                "sme_id": sme.id,
                "sme_slug": sme.slug,
                "decision": "added",
                "position": position,
                "engine_rank": result.rank,
                "status": result.status,
            },
        )
        db.commit()
    return {"opportunity_id": opp.id, "shortlist": _shortlist(db, opp.id, run)}


@router.put("/{opportunity_id}/shortlist/order")
def reorder_shortlist(
    opportunity_id: int, body: ShortlistOrderBody, db: DbSession, actor: BuyerActor
) -> dict[str, Any]:
    """A human override of the engine order: requires a written reason, audited with it."""
    opp = _get_opportunity(db, opportunity_id, actor)
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, REASON_REQUIRED)
    entries = {
        db.get(SME, e.sme_id).slug: e
        for e in db.scalars(
            select(ShortlistEntry)
            .where(ShortlistEntry.opportunity_id == opp.id)
            .order_by(ShortlistEntry.position)
        )
    }
    if sorted(body.sme_slugs) != sorted(entries) or len(set(body.sme_slugs)) != len(body.sme_slugs):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "sme_slugs must list every shortlisted SME exactly once."
        )
    before = list(entries)
    for position, slug in enumerate(body.sme_slugs, start=1):
        entries[slug].position = position
    run = matching.latest_run(db, opp.id)
    engine_ranking = []
    if run is not None:
        ranked = sorted((r for r in matching.run_results(db, run.id) if r.rank), key=lambda r: r.rank)
        engine_ranking = [db.get(SME, r.sme_id).slug for r in ranked]
    db.flush()
    write_audit(
        db,
        actor,
        "override",
        "shortlist",
        opp.id,
        {
            "opportunity_id": opp.id,
            "from": before,
            "to": list(body.sme_slugs),
            "engine_ranking": engine_ranking,
            "run_id": run.id if run else None,
        },
        reason=reason,
    )
    db.commit()
    return {"opportunity_id": opp.id, "shortlist": _shortlist(db, opp.id, run)}
