"""Server-side role-based access control for the demo (plan A13).

DEMO SIMPLIFICATION: the caller states its role in request headers (`X-Demo-Role: sme|buyer|admin`,
plus `X-Demo-Sme-Id: <slug>` for SMEs) chosen with the frontend's role switcher. Production replaces
this with Amazon Cognito sign-in, mapping the authenticated user to the same Actor. Either way every
non-public endpoint enforces its roles here, through FastAPI dependencies, never in the frontend.
Because these headers are not authentication, the stack binds to 127.0.0.1 only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SME
from app.services.seed import load_seed_data

ROLES = ("sme", "buyer", "admin")
ADMIN_LABEL = "YES Admin"


def buyer_identity() -> dict[str, str]:
    """The single demo buyer: {contact, org, label}."""
    return load_seed_data()["buyer"]


@dataclass(frozen=True)
class Actor:
    role: str
    label: str
    sme: SME | None = None

    @property
    def buyer_org(self) -> str | None:
        return buyer_identity()["org"] if self.role == "buyer" else None


DbSession = Annotated[Session, Depends(get_db)]


def get_actor(
    db: DbSession,
    x_demo_role: Annotated[str | None, Header()] = None,
    x_demo_sme_id: Annotated[str | None, Header()] = None,
) -> Actor:
    """401 when the role header is missing/invalid or an SME slug is missing/unknown."""
    role = (x_demo_role or "").strip().lower()
    if role not in ROLES:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-Demo-Role header (sme, buyer or admin)."
        )
    if role == "sme":
        slug = (x_demo_sme_id or "").strip().lower()
        sme = db.scalars(select(SME).where(SME.slug == slug)).first() if slug else None
        if sme is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Missing or unknown X-Demo-Sme-Id header for the SME role."
            )
        return Actor(role="sme", label=f"SME: {sme.name}", sme=sme)
    if role == "buyer":
        return Actor(role="buyer", label=buyer_identity()["label"])
    return Actor(role="admin", label=ADMIN_LABEL)


CurrentActor = Annotated[Actor, Depends(get_actor)]


def require_role(*roles: str):
    """Dependency factory: the current actor, or 403 when their role is not allowed."""

    def dependency(actor: CurrentActor) -> Actor:
        if actor.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"This action is not available to the {actor.role} role."
            )
        return actor

    return dependency


SmeActor = Annotated[Actor, Depends(require_role("sme"))]
BuyerActor = Annotated[Actor, Depends(require_role("buyer"))]
AdminActor = Annotated[Actor, Depends(require_role("admin"))]
BuyerOrAdmin = Annotated[Actor, Depends(require_role("buyer", "admin"))]
