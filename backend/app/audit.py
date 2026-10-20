"""Append-only audit log: writes attributed to an actor (role + label) and role-scoped reads.

Rows are never updated or deleted (a Postgres trigger enforces it; see app.db.init_db).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SME, AuditLog, Opportunity

# Every action written by the app (seed adds sme_profile_entry for the seeded form value).
ACTIONS = (
    "extraction",
    "sme_correction",
    "sme_confirmation",
    "sme_profile_entry",
    "consent",
    "requirement_edit",
    "rfq_structured",
    "match_run",
    "info_request",
    "info_request_responded",
    "shortlist_decision",
    "override",
    "ai_mode_change",
    "demo_reset",
)


class ActorLike(Protocol):
    role: str
    label: str


@dataclass(frozen=True)
class SystemActor:
    """Actor for non-user actions (startup seed, CLI)."""

    role: str = "system"
    label: str = "Demo seed"


def write_audit(
    session: Session,
    actor: ActorLike,
    action: str,
    entity_type: str | None,
    entity_id: Any,
    details: dict[str, Any] | None,
    reason: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_role=actor.role,
        actor_label=actor.label,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        details=details or {},
        reason=reason,
    )
    session.add(row)
    session.flush()
    return row


def audit_dict(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "at": row.at.isoformat() if row.at else None,
        "actor_role": row.actor_role,
        "actor_label": row.actor_label,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "details": row.details,
        "reason": row.reason,
    }


def _entry_sme_id(row: AuditLog) -> int | None:
    sme_id = (row.details or {}).get("sme_id")
    if sme_id is None and row.entity_type == "sme" and row.entity_id and row.entity_id.isdigit():
        sme_id = int(row.entity_id)
    return sme_id if isinstance(sme_id, int) else None


def _entry_opportunity_id(row: AuditLog) -> int | None:
    opp_id = (row.details or {}).get("opportunity_id")
    if opp_id is None and row.entity_type == "opportunity" and row.entity_id and row.entity_id.isdigit():
        opp_id = int(row.entity_id)
    return opp_id if isinstance(opp_id, int) else None


def list_audit(
    session: Session,
    actor: ActorLike,
    opportunity_id: int | None = None,
    buyer_org: str | None = None,
) -> list[AuditLog]:
    """Audit entries visible to the actor, oldest first.

    admin: everything. buyer: entries about their own opportunities (buyer_org) and entries about
    SMEs that have consented to share their profile; platform entries (AI mode, reset) are hidden.
    opportunity_id narrows to that opportunity's entries plus SME entries (entries tied to another
    opportunity are dropped).
    """
    rows = list(session.scalars(select(AuditLog).order_by(AuditLog.id)))
    own_opps: set[int] | None = None
    consented: set[int] | None = None
    if actor.role != "admin":
        own_opps = set(session.scalars(select(Opportunity.id).where(Opportunity.buyer_org == buyer_org)))
        consented = set(session.scalars(select(SME.id).where(SME.consent_status == "granted")))

    visible: list[AuditLog] = []
    for row in rows:
        opp_id = _entry_opportunity_id(row)
        sme_id = _entry_sme_id(row)
        if opportunity_id is not None and opp_id is not None and opp_id != opportunity_id:
            continue
        if own_opps is not None and consented is not None:
            if opp_id is not None:
                if opp_id not in own_opps:
                    continue
            elif sme_id is None or sme_id not in consented:
                continue
        visible.append(row)
    return visible
