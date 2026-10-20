"""Append-only audit log writes (FEAT-004 extends this module)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models import AuditLog


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
    actor_role: str,
    actor_label: str,
    action: str,
    entity_type: str | None,
    entity_id: Any,
    details: dict[str, Any] | None,
    reason: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_role=actor_role,
        actor_label=actor_label,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        details=details or {},
        reason=reason,
    )
    session.add(row)
    session.flush()
    return row
