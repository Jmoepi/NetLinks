"""Plain data types shared by the engine modules (no DB, no LLM).

The matching service converts DB rows into these; the engine returns them; the service stores their
to_dict() forms in match_results (JSONB).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

CONFIRMED_SOURCES = ("sme_confirmed", "verified")
SOURCE_PRIORITY = {"verified": 3, "sme_confirmed": 2, "ai_extracted": 1}

PASS = "pass"
NEEDS_REVIEW = "needs_review"
FAIL = "fail"

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"

DOC_TYPE_LABELS = {
    "capability_statement": "capability statement",
    "certification_summary": "certification summary",
    "infosec_popia_policy": "information security & POPIA policy",
    "pi_schedule": "PI insurance schedule",
    "tax_compliance_letter": "tax compliance letter",
}


@dataclass
class EvidenceRef:
    """Where a value came from: a document span or a non-document source (e.g. 'SME profile form')."""

    field_key: str | None = None
    value: Any = None
    source_type: str | None = None
    source_label: str | None = None
    document_id: int | None = None
    doc_type: str | None = None
    page: int | None = None
    span_start: int | None = None
    span_end: int | None = None
    quote: str | None = None
    confidence: float | None = None
    candidate_id: int | None = None

    @property
    def source_name(self) -> str:
        """Short plain-language source name, e.g. 'capability statement' or 'SME profile form'."""
        if self.doc_type in DOC_TYPE_LABELS:
            return DOC_TYPE_LABELS[self.doc_type]
        return self.source_label or "SME entry"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Fact:
    """Effective value of one profile field (from lineage.resolve) plus its lineage."""

    field_key: str
    status: str = "ok"  # ok | missing | conflict | low_confidence
    value: Any = None
    source_type: str | None = None
    confidence: float | None = None
    selected: EvidenceRef | None = None
    candidates: list[EvidenceRef] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return self.source_type in CONFIRMED_SOURCES

    @property
    def evidence(self) -> list[EvidenceRef]:
        """The selected source, or every candidate when the sources disagree."""
        if self.status == "conflict":
            return sorted(
                self.candidates,
                key=lambda c: (-SOURCE_PRIORITY.get(c.source_type or "", 0), c.candidate_id or 0),
            )
        return [self.selected] if self.selected else []

    @classmethod
    def missing(cls, field_key: str) -> Fact:
        return cls(field_key=field_key, status="missing")

    @classmethod
    def from_resolution(
        cls, field_key: str, resolution: dict[str, Any], doc_types: dict[int, str] | None = None
    ) -> Fact:
        """Build from app.ingestion.lineage.resolve() output; doc_types maps document_id -> doc_type."""
        doc_types = doc_types or {}
        refs = [
            EvidenceRef(
                field_key=field_key,
                value=c.get("value"),
                source_type=c.get("source_type"),
                source_label=c.get("source_label"),
                document_id=c.get("document_id"),
                doc_type=doc_types.get(c.get("document_id")) if c.get("document_id") else None,
                page=c.get("page"),
                span_start=c.get("span_start"),
                span_end=c.get("span_end"),
                quote=c.get("quote"),
                confidence=c.get("confidence"),
                candidate_id=c.get("id"),
            )
            for c in resolution.get("candidates", [])
        ]
        selected = next((r for r in refs if r.candidate_id == resolution.get("selected_id")), None)
        return cls(
            field_key=field_key,
            status=resolution.get("status", "missing"),
            value=resolution.get("value"),
            source_type=resolution.get("source_type"),
            confidence=resolution.get("confidence"),
            selected=selected,
            candidates=refs,
        )


@dataclass
class DocumentRef:
    id: int
    filename: str
    doc_type: str | None = None
    issue_date: date | None = None
    period_end: date | None = None

    def evidence(self) -> EvidenceRef:
        return EvidenceRef(
            document_id=self.id, doc_type=self.doc_type, source_label=self.filename, value=self.filename
        )


@dataclass
class SMEProfile:
    """Everything the engine needs about one SME: resolved facts and its active documents."""

    sme_id: int
    facts: dict[str, Fact] = field(default_factory=dict)
    documents: list[DocumentRef] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None

    def fact(self, key: str) -> Fact:
        return self.facts.get(key) or Fact.missing(key)


@dataclass
class OpportunitySpec:
    id: int
    closing_date: date
    mandatory_criteria: list[dict[str, Any]] = field(default_factory=list)
    preferred_criteria: list[dict[str, Any]] = field(default_factory=list)
    weights: dict[str, Any] = field(default_factory=dict)
    capability_text: str | None = None
    contract_start: date | None = None

    def preferred(self, rule_type: str) -> dict[str, Any] | None:
        crit = next((c for c in self.preferred_criteria if c.get("rule_type") == rule_type), None)
        return dict(crit.get("params") or {}) if crit else None


@dataclass
class CheckResult:
    rule: str
    label: str
    outcome: str  # pass | needs_review | fail
    reason: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    group: str = "mandatory"  # mandatory | consistency
    issues: list[str] = field(default_factory=list)  # missing, conflict, low_confidence, outdated, ...
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "label": self.label,
            "outcome": self.outcome,
            "reason": self.reason,
            "evidence": [e.to_dict() for e in self.evidence],
            "group": self.group,
            "issues": list(self.issues),
            "details": dict(self.details),
        }


@dataclass
class EligibilityResult:
    status: str  # eligible | needs_review | not_eligible
    checks: list[CheckResult]

    def check(self, rule: str) -> CheckResult:
        return next(c for c in self.checks if c.rule == rule)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "checks": [c.to_dict() for c in self.checks]}


@dataclass
class ComponentScore:
    name: str
    label: str
    score: float  # 0-100
    weight: int
    weighted: float  # score * weight / 100
    explanation: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "score": self.score,
            "weight": self.weight,
            "weighted": self.weighted,
            "explanation": self.explanation,
            "evidence": [e.to_dict() for e in self.evidence],
            "details": dict(self.details),
        }


@dataclass
class ScoreResult:
    total: float
    components: list[ComponentScore]

    def component(self, name: str) -> ComponentScore:
        return next(c for c in self.components if c.name == name)

    def to_dict(self) -> dict[str, Any]:
        return {"total": self.total, "components": [c.to_dict() for c in self.components]}
