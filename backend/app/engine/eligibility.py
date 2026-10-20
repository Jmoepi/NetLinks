"""Deterministic eligibility engine (plan A10). Pure Python: no DB, no AI calls.

Every mandatory rule is plain code over resolved profile facts, so the same input always gives the same
answer. General rules applied by every check:
- missing value -> needs_review
- conflicting values -> needs_review (both values and sources named)
- low confidence / unreadable and not SME-confirmed or verified -> needs_review
- expiry on or before the closing date -> needs_review ("outdated"); outdated is never a fail
- a value that fails the rule -> fail only when SME-confirmed or verified; AI-extracted only -> needs_review
Overall: any fail -> not_eligible; else any needs_review -> needs_review; else eligible.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.config import LOW_CONFIDENCE
from app.engine.types import (
    ELIGIBLE,
    FAIL,
    NEEDS_REVIEW,
    NOT_ELIGIBLE,
    PASS,
    CheckResult,
    EligibilityResult,
    EvidenceRef,
    Fact,
    OpportunitySpec,
    SMEProfile,
)

CSD_PATTERN = re.compile(r"^MAAA\d{7}$")
UNCONFIRMED_FAILURE = "Unconfirmed AI-extracted value fails the rule; SME to confirm."

PROVINCE_NAMES = {
    "GP": "Gauteng",
    "WC": "Western Cape",
    "KZN": "KwaZulu-Natal",
    "EC": "Eastern Cape",
    "FS": "Free State",
    "LP": "Limpopo",
    "MP": "Mpumalanga",
    "NW": "North West",
    "NC": "Northern Cape",
}

FIELD_LABELS = {
    "tax_compliance_status": "Tax compliance status",
    "tax_expiry_date": "Tax compliance expiry date",
    "csd_number": "CSD supplier number",
    "black_ownership_pct": "Black ownership",
    "bbbee_level": "B-BBEE level",
    "service_regions": "Service regions",
    "pi_cover_amount": "Professional indemnity cover amount",
    "pi_expiry_date": "Professional indemnity expiry date",
    "certifications": "Technician certifications",
    "technician_count": "Technician count",
    "service_desk_hours": "Service desk hours",
    "years_trading": "Years trading",
    "past_clients": "Past clients",
    "services_description": "Services description",
    "service_tags": "Service tags",
    "base_town": "Base town",
}

# Profile fields each criterion reads; data_consistency looks for conflicts on these.
CRITERIA_FIELDS: dict[str, tuple[str, ...]] = {
    "tax_compliance": ("tax_compliance_status", "tax_expiry_date"),
    "csd_registration": ("csd_number",),
    "ownership_or_bbbee": ("black_ownership_pct", "bbbee_level"),
    "operating_region": ("service_regions",),
    "pi_insurance": ("pi_cover_amount", "pi_expiry_date"),
    "infosec_policy": (),
    "certified_technicians": ("certifications",),
    "capability": ("services_description", "service_tags"),
    "experience": ("years_trading", "past_clients"),
    "capacity": ("technician_count", "service_desk_hours"),
    "location": ("base_town",),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _Verdict:
    outcome: str
    reason: str = ""
    issues: list[str] = field(default_factory=list)
    evidence: list[EvidenceRef] = field(default_factory=list)


def parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace(" ", "").lstrip("Rr"))
        except ValueError:
            return None
    return None


def rand(amount: float) -> str:
    return f"R{amount:,.0f}"


def region_names(codes: Iterable[str]) -> str:
    names = [PROVINCE_NAMES.get(str(c).upper(), str(c)) for c in codes]
    if not names:
        return "none"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(format_value(v) for v in value)
    if isinstance(value, dict):
        if {"start", "end"} <= value.keys():
            return f"{value['start']}-{value['end']}"
        return ", ".join(f"{k} {format_value(v)}" for k, v in value.items())
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def field_label(field_key: str) -> str:
    return FIELD_LABELS.get(field_key, field_key.replace("_", " ").capitalize())


def conflict_reason(fact: Fact) -> str:
    """e.g. 'Technician count conflict: SME profile form 15, capability statement 4.'"""
    parts = ", ".join(f"{e.source_name} {format_value(e.value)}" for e in fact.evidence)
    return f"{field_label(fact.field_key)} conflict: {parts}."


def is_low_confidence(fact: Fact) -> bool:
    if fact.confirmed:
        return False
    return fact.status == "low_confidence" or fact.confidence is None or fact.confidence < LOW_CONFIDENCE


def _precheck(fact: Fact) -> _Verdict | None:
    """Shared rules that stop evaluation: missing, conflict, low confidence."""
    label = field_label(fact.field_key)
    if fact.status == "missing":
        return _Verdict(NEEDS_REVIEW, f"{label} not provided.", ["missing"])
    if fact.status == "conflict":
        return _Verdict(NEEDS_REVIEW, conflict_reason(fact), ["conflict"], fact.evidence)
    if is_low_confidence(fact):
        quote = fact.selected.quote if fact.selected and fact.selected.quote else None
        conf = f", confidence {fact.confidence:.2f}" if fact.confidence is not None else ""
        said = f' ("{quote}")' if quote else ""
        return _Verdict(
            NEEDS_REVIEW,
            f"{label} is low confidence{said} (AI-extracted{conf}); SME to confirm.",
            ["low_confidence"],
            fact.evidence,
        )
    return None


# A test returns (verdict, reason) with verdict pass | fail | outdated | unreadable.
FactTest = Callable[[Fact], tuple[str, str]]


def _judge(fact: Fact, test: FactTest) -> _Verdict:
    pre = _precheck(fact)
    if pre:
        return pre
    verdict, reason = test(fact)
    if verdict == PASS:
        return _Verdict(PASS, reason, [], fact.evidence)
    if verdict in ("outdated", "unreadable"):
        return _Verdict(NEEDS_REVIEW, reason, [verdict], fact.evidence)
    if fact.confirmed:
        return _Verdict(FAIL, reason, ["confirmed_failure"], fact.evidence)
    return _Verdict(NEEDS_REVIEW, f"{reason} {UNCONFIRMED_FAILURE}", ["unconfirmed_failure"], fact.evidence)


def _expiry_test(subject: str, closing: date) -> FactTest:
    def test(fact: Fact) -> tuple[str, str]:
        expiry = parse_date(fact.value)
        if expiry is None:
            return "unreadable", f"{subject} expiry date is unreadable ({format_value(fact.value)})."
        days = (closing - expiry).days
        if days > 0:
            return (
                "outdated",
                f"{subject} expires {days} day{'s' if days != 1 else ''} before the closing date.",
            )
        if days == 0:
            return "outdated", f"{subject} expires on the closing date."
        return PASS, ""

    return test


def _all(
    rule: str, label: str, verdicts: list[_Verdict], pass_reason: str, details: dict[str, Any] | None = None
) -> CheckResult:
    """AND-combine: any fail -> fail; else any needs_review -> needs_review; else pass."""
    evidence = [e for v in verdicts for e in v.evidence]
    for outcome in (FAIL, NEEDS_REVIEW):
        hits = [v for v in verdicts if v.outcome == outcome]
        if hits:
            return CheckResult(
                rule,
                label,
                outcome,
                " ".join(v.reason for v in hits),
                evidence,
                issues=[i for v in hits for i in v.issues],
                details=details or {},
            )
    return CheckResult(rule, label, PASS, pass_reason, evidence, details=details or {})


def aggregate(outcomes: Iterable[str]) -> str:
    outcomes = list(outcomes)
    if FAIL in outcomes:
        return NOT_ELIGIBLE
    if NEEDS_REVIEW in outcomes:
        return NEEDS_REVIEW
    return ELIGIBLE


# ---------------------------------------------------------------------------
# Mandatory rules (fixed catalog, plan A7)
# ---------------------------------------------------------------------------


def check_tax_compliance(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    status = profile.fact("tax_compliance_status")
    expiry = profile.fact("tax_expiry_date")

    def status_test(f: Fact) -> tuple[str, str]:
        if " ".join(str(f.value).split()).lower() == "compliant":
            return PASS, ""
        qual = " (confirmed)" if f.confirmed else ""
        return FAIL, f"Tax compliance status is '{format_value(f.value)}'{qual}."

    verdicts = [_judge(status, status_test), _judge(expiry, _expiry_test("Tax compliance status", closing))]
    return _all(
        "tax_compliance",
        "Valid SARS tax compliance status",
        verdicts,
        f"Tax compliant, valid to {format_value(expiry.value)} (after the {closing.isoformat()} "
        "closing date).",
        {"expiry_date": expiry.value, "closing_date": closing.isoformat()},
    )


def check_csd_registration(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    csd = profile.fact("csd_number")

    def test(f: Fact) -> tuple[str, str]:
        number = str(f.value).strip()
        if CSD_PATTERN.match(number):
            return PASS, ""
        qual = " (confirmed)" if f.confirmed else ""
        return FAIL, f"CSD supplier number '{number}' is not in the MAAA + 7 digits format{qual}."

    return _all(
        "csd_registration",
        "CSD registration",
        [_judge(csd, test)],
        f"CSD supplier number {format_value(csd.value)} is present and well-formed.",
    )


def check_ownership_or_bbbee(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    min_pct = params.get("min_black_ownership_pct", 51)
    max_level = params.get("max_bbbee_level", 2)
    label = f"≥{min_pct}% Black-owned or B-BBEE Level 1–{max_level}"

    def own_test(f: Fact) -> tuple[str, str]:
        pct = as_number(f.value)
        if pct is None:
            return "unreadable", f"Black ownership is unreadable ({format_value(f.value)})."
        if pct >= min_pct:
            return PASS, f"{format_value(pct)}% Black-owned (minimum {min_pct}%)"
        return FAIL, f"Black ownership is {format_value(pct)}% (minimum {min_pct}%)."

    def level_test(f: Fact) -> tuple[str, str]:
        level = as_number(f.value)
        if level is None or not level.is_integer():
            return "unreadable", f"B-BBEE level is unreadable ({format_value(f.value)})."
        if 1 <= level <= max_level:
            return PASS, f"B-BBEE Level {int(level)} (Level 1–{max_level} accepted)"
        return FAIL, f"B-BBEE level is {int(level)} (Level 1–{max_level} required)."

    verdicts = [
        _judge(profile.fact("black_ownership_pct"), own_test),
        _judge(profile.fact("bbbee_level"), level_test),
    ]
    evidence = [e for v in verdicts for e in v.evidence]
    passes = [v for v in verdicts if v.outcome == PASS]
    if passes:  # OR logic: either route qualifies
        return CheckResult(
            "ownership_or_bbbee", label, PASS, "; ".join(v.reason for v in passes) + ".", evidence
        )
    if all(v.outcome == FAIL for v in verdicts):  # both confirmed and failing
        return CheckResult(
            "ownership_or_bbbee",
            label,
            FAIL,
            " ".join(v.reason for v in verdicts),
            evidence,
            issues=["confirmed_failure"],
        )
    return CheckResult(
        "ownership_or_bbbee",
        label,
        NEEDS_REVIEW,
        " ".join(v.reason for v in verdicts),
        evidence,
        issues=[i for v in verdicts for i in v.issues],
    )


def check_operating_region(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    region = str(params.get("region", "GP")).upper()
    region_name = PROVINCE_NAMES.get(region, region)
    regions = profile.fact("service_regions")

    def test(f: Fact) -> tuple[str, str]:
        codes = f.value if isinstance(f.value, list) else [f.value]
        codes = [str(c).strip().upper() for c in codes if c is not None]
        if region in codes:
            return PASS, ""
        qual = "confirmed" if f.confirmed else "AI-extracted"
        return FAIL, f"No {region_name} service region ({qual}: {region_names(codes)} only)."

    value = regions.value if isinstance(regions.value, list) else []
    listed = f" ({region_names(value)})" if len(value) > 1 else ""
    return _all(
        "operating_region",
        f"Operates in {region_name}",
        [_judge(regions, test)],
        f"Service regions include {region_name}{listed}.",
        {"region": region},
    )


def check_pi_insurance(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    min_amount = float(params.get("min_amount", 0))
    amount = profile.fact("pi_cover_amount")
    expiry = profile.fact("pi_expiry_date")

    def amount_test(f: Fact) -> tuple[str, str]:
        value = as_number(f.value)
        if value is None:
            return (
                "unreadable",
                f"Professional indemnity cover amount is unreadable ({format_value(f.value)}).",
            )
        if value >= min_amount:
            return PASS, ""
        qual = " (confirmed)" if f.confirmed else ""
        return (
            FAIL,
            f"Professional indemnity cover is {rand(value)}, below the {rand(min_amount)} minimum{qual}.",
        )

    verdicts = [
        _judge(amount, amount_test),
        _judge(expiry, _expiry_test("Professional indemnity cover", closing)),
    ]
    amount_value = as_number(amount.value)
    pass_reason = (
        f"Professional indemnity cover {rand(amount_value or 0)} (minimum {rand(min_amount)}), "
        f"valid to {format_value(expiry.value)}."
    )
    return _all(
        "pi_insurance",
        f"Professional indemnity insurance ≥ {rand(min_amount)}, current",
        verdicts,
        pass_reason,
        {
            "amount": amount.value,
            "min_amount": min_amount,
            "expiry_date": expiry.value,
            "closing_date": closing.isoformat(),
        },
    )


def check_infosec_policy(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    label = "Information security & POPIA policy provided"
    docs = [d for d in profile.documents if d.doc_type == "infosec_popia_policy"]
    if docs:
        names = ", ".join(d.filename for d in docs)
        return CheckResult(
            "infosec_policy",
            label,
            PASS,
            f"Information security & POPIA policy provided ({names}).",
            [d.evidence() for d in docs],
        )
    return CheckResult(
        "infosec_policy",
        label,
        NEEDS_REVIEW,
        "No information security & POPIA policy document provided.",
        issues=["missing"],
    )


def check_certified_technicians(profile: SMEProfile, params: dict[str, Any], closing: date) -> CheckResult:
    min_count = int(params.get("min_count", 1))
    rule, label = "certified_technicians", f"≥ {min_count} technicians with current certifications"
    fact = profile.fact("certifications")
    pre = _precheck(fact)
    if pre:
        return CheckResult(rule, label, pre.outcome, pre.reason, pre.evidence, issues=pre.issues)
    certs = fact.value if isinstance(fact.value, list) else []
    if not isinstance(fact.value, list):
        return CheckResult(
            rule,
            label,
            NEEDS_REVIEW,
            "Technician certifications are unreadable.",
            fact.evidence,
            issues=["unreadable"],
        )

    current, expired, unreadable = [], [], []
    for cert in certs:
        cert = cert if isinstance(cert, dict) else {"cert_name": str(cert)}
        expiry = parse_date(cert.get("expiry_date"))
        if expiry is None:
            unreadable.append(cert)
        elif expiry > closing:
            current.append(cert)
        else:
            expired.append(cert)

    def holder_key(c: dict[str, Any], i: int) -> str:
        holder = " ".join(str(c.get("holder") or "").split()).lower()
        return holder or f"#{i}"

    current_holders = {holder_key(c, i) for i, c in enumerate(current)}
    n = len(current_holders)
    details = {
        "current": current,
        "expired_before_closing": expired,
        "unreadable": unreadable,
        "min_count": min_count,
        "closing_date": closing.isoformat(),
    }

    def describe(c: dict[str, Any]) -> str:
        name = c.get("cert_name") or "certification"
        return f"{c.get('holder') or 'Unnamed'} ({name}, to {c.get('expiry_date')})"

    if n >= min_count:
        listed = "; ".join(describe(c) for c in current)
        return CheckResult(
            rule,
            label,
            PASS,
            f"{n} technicians with current certifications (minimum {min_count}): {listed}.",
            fact.evidence,
            details=details,
        )

    gap = min_count - n
    short = f"Only {n} technician{'s' if n != 1 else ''} with current certifications (minimum {min_count})."
    could_close = {holder_key(c, 1000 + i) for i, c in enumerate(expired + unreadable)} - current_holders
    if len(could_close) >= gap:
        bits = []
        if expired:
            bits.append(
                f"{len(expired)} expire{'s' if len(expired) == 1 else ''} on or before the closing date"
            )
        if unreadable:
            bits.append(
                f"{len(unreadable)} {'has' if len(unreadable) == 1 else 'have'} an unreadable expiry date"
            )
        issues = (["outdated"] if expired else []) + (["unreadable"] if unreadable else [])
        return CheckResult(
            rule,
            label,
            NEEDS_REVIEW,
            f"{short} {' and '.join(bits).capitalize()}, which could close the gap.",
            fact.evidence,
            issues=issues,
            details=details,
        )
    if fact.confirmed:
        return CheckResult(
            rule,
            label,
            FAIL,
            f"{short[:-1]} (confirmed).",
            fact.evidence,
            issues=["confirmed_failure"],
            details=details,
        )
    return CheckResult(
        rule,
        label,
        NEEDS_REVIEW,
        f"{short} {UNCONFIRMED_FAILURE}",
        fact.evidence,
        issues=["unconfirmed_failure"],
        details=details,
    )


RULES: dict[str, Callable[[SMEProfile, dict[str, Any], date], CheckResult]] = {
    "tax_compliance": check_tax_compliance,
    "csd_registration": check_csd_registration,
    "ownership_or_bbbee": check_ownership_or_bbbee,
    "operating_region": check_operating_region,
    "pi_insurance": check_pi_insurance,
    "infosec_policy": check_infosec_policy,
    "certified_technicians": check_certified_technicians,
}


# ---------------------------------------------------------------------------
# Data consistency + evaluation
# ---------------------------------------------------------------------------


def criteria_fields(opportunity: OpportunitySpec) -> list[str]:
    keys: set[str] = set()
    for crit in [*opportunity.mandatory_criteria, *opportunity.preferred_criteria]:
        keys.update(CRITERIA_FIELDS.get(crit.get("rule_type", ""), ()))
    return sorted(keys)


def check_data_consistency(profile: SMEProfile, opportunity: OpportunitySpec) -> CheckResult:
    label = "Data consistency across sources"
    fields = criteria_fields(opportunity)
    conflicts = [profile.fact(k) for k in fields if profile.fact(k).status == "conflict"]
    if not conflicts:
        return CheckResult(
            "data_consistency",
            label,
            PASS,
            f"No conflicting values across sources for the {len(fields)} fields this opportunity uses.",
            group="consistency",
            details={"fields": fields},
        )
    details = {
        "fields": fields,
        "conflicts": [
            {
                "field_key": f.field_key,
                "label": field_label(f.field_key),
                "values": [
                    {
                        "value": e.value,
                        "source": e.source_name,
                        "source_type": e.source_type,
                        "document_id": e.document_id,
                    }
                    for e in f.evidence
                ],
            }
            for f in conflicts
        ],
    }
    return CheckResult(
        "data_consistency",
        label,
        NEEDS_REVIEW,
        " ".join(conflict_reason(f) for f in conflicts),
        [e for f in conflicts for e in f.evidence],
        group="consistency",
        issues=["conflict"],
        details=details,
    )


def evaluate(profile: SMEProfile, opportunity: OpportunitySpec) -> EligibilityResult:
    """Run every mandatory criterion of the opportunity plus the data_consistency check."""
    checks: list[CheckResult] = []
    for crit in opportunity.mandatory_criteria:
        rule = crit.get("rule_type")
        if rule not in RULES:
            raise ValueError(f"Unknown mandatory rule type: {rule!r}")
        checks.append(RULES[rule](profile, dict(crit.get("params") or {}), opportunity.closing_date))
    checks.append(check_data_consistency(profile, opportunity))
    return EligibilityResult(aggregate(c.outcome for c in checks), checks)
