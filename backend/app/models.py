"""SQLAlchemy 2 models for every table in plan A4."""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

DEFAULT_WEIGHTS = {"capability": 40, "experience": 25, "capacity": 20, "location": 15}


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SME(Base):
    __tablename__ = "smes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_town: Mapped[str | None] = mapped_column(String(128))
    province: Mapped[str | None] = mapped_column(String(8))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    size_band: Mapped[str | None] = mapped_column(String(16))  # micro | small
    employees: Mapped[int | None] = mapped_column(Integer)
    consent_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sme_id: Mapped[int] = mapped_column(ForeignKey("smes.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # capability_statement | certification_summary | infosec_popia_policy | pi_schedule
    # | tax_compliance_letter | other
    doc_type: Mapped[str | None] = mapped_column(String(64))
    issue_date: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    storage_key: Mapped[str | None] = mapped_column(String(512))
    pages_text: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    uploaded_at: Mapped[datetime] = _now_column()
    uploaded_by_role: Mapped[str | None] = mapped_column(String(16))
    superseded_by_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))


class AIResult(Base):
    __tablename__ = "ai_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # extraction | rfq_structuring | embedding
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProfileFieldValue(Base):
    __tablename__ = "profile_field_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sme_id: Mapped[int] = mapped_column(ForeignKey("smes.id"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[Any] = mapped_column(JSONB)
    # ai_extracted | sme_confirmed | verified
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    source_label: Mapped[str | None] = mapped_column(String(255))
    page: Mapped[int | None] = mapped_column(Integer)
    span_start: Mapped[int | None] = mapped_column(Integer)
    span_end: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active | superseded
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("profile_field_values.id"))
    created_at: Mapped[datetime] = _now_column()
    created_by_role: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_org: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_contact: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    raw_rfq_text: Mapped[str | None] = mapped_column(Text)
    closing_date: Mapped[date | None] = mapped_column(Date)
    contract_start: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    weights: Mapped[dict[str, int]] = mapped_column(
        JSONB, default=lambda: dict(DEFAULT_WEIGHTS), nullable=False
    )
    mandatory_criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    preferred_criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    capability_text: Mapped[str | None] = mapped_column(Text)


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False)  # sme | opportunity
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    # No fixed dimension so different providers (lexicon vs Titan) can coexist.
    vector: Mapped[list[float]] = mapped_column(Vector(), nullable=False)


class MatchRun(Base):
    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), nullable=False, index=True)
    run_at: Mapped[datetime] = _now_column()
    run_by_role: Mapped[str | None] = mapped_column(String(16))
    ai_mode: Mapped[str | None] = mapped_column(String(16))
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"), nullable=False, index=True)
    sme_id: Mapped[int] = mapped_column(ForeignKey("smes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # eligible | needs_review | not_eligible
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    score_total: Mapped[float | None] = mapped_column(Float)
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)  # eligible only
    awaiting_sme: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class InfoRequest(Base):
    __tablename__ = "info_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    sme_id: Mapped[int] = mapped_column(ForeignKey("smes.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # information | clarification
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)  # open | responded
    created_at: Mapped[datetime] = _now_column()
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShortlistEntry(Base):
    __tablename__ = "shortlist_entries"

    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    sme_id: Mapped[int] = mapped_column(ForeignKey("smes.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = _now_column()


class ReadinessAction(Base):
    __tablename__ = "readiness_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sme_id: Mapped[int] = mapped_column(ForeignKey("smes.id"), nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now_column()


class AuditLog(Base):
    """Append-only: a Postgres trigger (app.db.init_db) raises on UPDATE/DELETE."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = _now_column()
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
