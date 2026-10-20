"""Audit log read endpoint (the log itself is append-only; there is no write or delete route)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.audit import audit_dict, list_audit
from app.rbac import BuyerOrAdmin, DbSession

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def get_audit(db: DbSession, actor: BuyerOrAdmin, opportunity_id: int | None = None) -> dict[str, Any]:
    """Admin: every entry. Buyer: own opportunities and consented SMEs only. Oldest first."""
    rows = list_audit(db, actor, opportunity_id=opportunity_id, buyer_org=actor.buyer_org)
    return {"entries": [audit_dict(r) for r in rows]}
