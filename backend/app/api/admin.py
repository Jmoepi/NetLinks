"""Admin endpoints (Reset demo, YES dashboard) and the public demo-identities list for the role switcher."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.models import SME
from app.rbac import ADMIN_LABEL, AdminActor, DbSession, buyer_identity
from app.services import dashboard
from app.services import seed as seed_service

router = APIRouter(prefix="/api/admin", tags=["admin"])
public_router = APIRouter(prefix="/api/demo", tags=["demo"])


@public_router.get("/identities")
def identities(db: DbSession) -> dict[str, Any]:
    """Role switcher options (public: lists fictional demo identities only)."""
    buyer = buyer_identity()
    smes = db.scalars(select(SME).order_by(SME.id)).all()
    return {
        "identities": [
            *({"role": "sme", "sme_slug": s.slug, "label": f"SME: {s.name}", "name": s.name} for s in smes),
            {"role": "buyer", "sme_slug": None, "label": buyer["label"], "name": buyer["contact"]},
            {"role": "admin", "sme_slug": None, "label": ADMIN_LABEL, "name": ADMIN_LABEL},
        ]
    }


@router.post("/reset")
def reset_demo(db: DbSession, actor: AdminActor) -> dict[str, Any]:
    """Truncate everything, delete uploads, reseed, force cached AI mode, audit demo_reset."""
    counts = seed_service.reset(db, actor)
    db.commit()
    return {"status": "ok", "seeded": counts}


@router.get("/dashboard")
def get_dashboard(db: DbSession, actor: AdminActor) -> dict[str, Any]:
    return dashboard.build(db)
