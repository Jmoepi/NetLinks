"""AI mode setting: any role reads it (for the Cached/Live badge); only the admin changes it."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai import gateway
from app.audit import write_audit
from app.config import get_settings
from app.rbac import AdminActor, CurrentActor, DbSession

router = APIRouter(prefix="/api/settings", tags=["settings"])

LIVE_REQUIRES_AWS = "Live mode requires AWS credentials for Bedrock"


class AIModeUpdate(BaseModel):
    mode: Literal["cached", "live"]


def ai_mode_payload(session: Session) -> dict[str, Any]:
    settings = get_settings()
    available = gateway.live_available()
    return {
        "mode": gateway.get_mode(session),
        "live_available": available,
        "live_unavailable_reason": None if available else LIVE_REQUIRES_AWS,
        "extraction_model_id": settings.bedrock_extraction_model_id or None,
        "embedding_model_id": settings.bedrock_embedding_model_id or None,
    }


@router.get("/ai-mode")
def get_ai_mode(db: DbSession, actor: CurrentActor) -> dict[str, Any]:
    return ai_mode_payload(db)


@router.put("/ai-mode")
def put_ai_mode(body: AIModeUpdate, db: DbSession, actor: AdminActor) -> dict[str, Any]:
    if body.mode == "live" and not gateway.live_available():
        raise HTTPException(status.HTTP_409_CONFLICT, LIVE_REQUIRES_AWS)
    previous = gateway.get_mode(db)
    gateway.set_mode(db, body.mode)
    write_audit(db, actor, "ai_mode_change", "setting", "ai_mode", {"from": previous, "to": body.mode})
    db.commit()
    return ai_mode_payload(db)
