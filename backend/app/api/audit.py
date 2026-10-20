"""Audit log read endpoint (the log itself is append-only; there is no write or delete route)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status

from app.api.pagination import PageQuery, PageSizeQuery, paginate
from app.audit import ACTIONS, audit_dict, list_audit
from app.rbac import BuyerOrAdmin, DbSession

router = APIRouter(prefix="/api/audit", tags=["audit"])

DEFAULT_PAGE_SIZE = 20


@router.get("")
def get_audit(
    db: DbSession,
    actor: BuyerOrAdmin,
    opportunity_id: int | None = None,
    page: PageQuery = None,
    page_size: PageSizeQuery = None,
    action: str | None = None,
    actor_role: Literal["sme", "buyer", "admin", "system"] | None = None,
) -> dict[str, Any]:
    """Admin: every entry. Buyer: own opportunities and consented SMEs only.

    Without page/page_size (legacy mode) every visible entry is returned oldest first. Sending
    either switches to paginated mode: newest first, page default 1, page_size default 20 (max 100).
    action and actor_role filter in both modes; total is the filtered count.
    """
    if action is not None and action not in ACTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown audit action: {action}")
    rows = list_audit(
        db,
        actor,
        opportunity_id=opportunity_id,
        buyer_org=actor.buyer_org,
        action=action,
        actor_role=actor_role,
    )
    if page is None and page_size is None:
        return {
            "entries": [audit_dict(r) for r in rows],
            "total": len(rows),
            "page": 1,
            "page_size": len(rows),
            "order": "oldest_first",
        }
    items, meta = paginate(list(reversed(rows)), page or 1, page_size or DEFAULT_PAGE_SIZE)
    return {
        "entries": [audit_dict(r) for r in items],
        "total": meta["total"],
        "page": meta["page"],
        "page_size": meta["page_size"],
        "order": "newest_first",
    }
