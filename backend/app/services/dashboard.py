"""YES admin dashboard (plan A13): pipeline before/after, readiness gaps, skills, decisions, fairness.

Read-only aggregation over stored match runs, opportunities, info requests and the audit log.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.lexicon import CONCEPT_LABELS, tags
from app.engine.eligibility import PROVINCE_NAMES
from app.models import SME, AuditLog, InfoRequest, MatchResult, MatchRun, Opportunity

STATUSES = ("eligible", "needs_review", "not_eligible")
SMALL_SAMPLE_THRESHOLD = 30
CAPACITY_FIELDS = {"technician_count", "service_desk_hours"}

SKILL_LABELS = {
    "m365_admin": "Microsoft 365",
    "service_desk": "Service desk",
    "device_management": "Device management",
    "desktop_device_support": "Desktop/device support",
}

GAP_LABELS = {
    "operating_region": "Regional coverage",
    "certified_technicians": "Missing or expired certifications",
    "csd_registration": "CSD registration",
    "ownership_or_bbbee": "Ownership / B-BBEE evidence",
    "infosec_policy": "Security & POPIA policy",
}


def _counts(run: MatchRun) -> dict[str, Any]:
    return {k: (run.counts or {}).get(k, 0) for k in (*STATUSES, "considered", "excluded_no_consent")}


def pipeline(session: Session) -> list[dict[str, Any]]:
    """Per opportunity with runs: first run (before) vs latest run (after)."""
    out = []
    for opp in session.scalars(select(Opportunity).order_by(Opportunity.id)):
        runs = list(
            session.scalars(select(MatchRun).where(MatchRun.opportunity_id == opp.id).order_by(MatchRun.id))
        )
        if not runs:
            continue
        first, latest = runs[0], runs[-1]
        out.append(
            {
                "opportunity_id": opp.id,
                "title": opp.title,
                "run_count": len(runs),
                "before": {"run_id": first.id, "run_at": first.run_at.isoformat(), "counts": _counts(first)},
                "after": {
                    "run_id": latest.id,
                    "run_at": latest.run_at.isoformat(),
                    "counts": _counts(latest),
                },
            }
        )
    return out


def gap_label(check: dict[str, Any]) -> str:
    """Plain-language category for a non-pass check."""
    rule, issues = check["rule"], set(check.get("issues") or [])
    if rule == "data_consistency":
        fields = {c.get("field_key") for c in (check.get("details") or {}).get("conflicts") or []}
        return "Conflicting capacity data" if fields & CAPACITY_FIELDS else "Conflicting profile data"
    if "conflict" in issues:
        return "Conflicting profile data"
    if "low_confidence" in issues or "unconfirmed_failure" in issues:
        return "Unconfirmed AI-extracted data"
    if rule == "pi_insurance":
        return "Expiring insurance" if "outdated" in issues else "Insurance cover"
    if rule == "tax_compliance":
        return "Expiring tax compliance" if "outdated" in issues else "Tax compliance"
    return GAP_LABELS.get(rule, check.get("label") or rule)


def readiness_gaps(session: Session) -> list[dict[str, Any]]:
    """Distinct SMEs per gap category across all runs; `open` = still a gap in the latest run."""
    latest_ids = set()
    for opp_id in set(session.scalars(select(MatchRun.opportunity_id))):
        latest_ids.add(
            session.scalar(
                select(MatchRun.id)
                .where(MatchRun.opportunity_id == opp_id)
                .order_by(MatchRun.id.desc())
                .limit(1)
            )
        )
    seen: dict[str, set[int]] = {}
    still_open: dict[str, set[int]] = {}
    for result in session.scalars(select(MatchResult).order_by(MatchResult.id)):
        for check in result.checks or []:
            if check.get("outcome") == "pass":
                continue
            label = gap_label(check)
            seen.setdefault(label, set()).add(result.sme_id)
            if result.run_id in latest_ids:
                still_open.setdefault(label, set()).add(result.sme_id)
    rows = [
        {"label": label, "smes": len(smes), "open": len(still_open.get(label, set()))}
        for label, smes in seen.items()
    ]
    return sorted(rows, key=lambda r: (-r["smes"], r["label"]))


def skill_label(tag: str) -> str:
    label = SKILL_LABELS.get(tag) or CONCEPT_LABELS.get(tag) or tag.replace("_", " ")
    return label[:1].upper() + label[1:]


def requested_skills(session: Session) -> list[dict[str, Any]]:
    """Tag counts across every opportunity's capability criteria plus buyer info-request messages."""
    counter: Counter[str] = Counter()
    for opp in session.scalars(select(Opportunity)):
        for c in opp.preferred_criteria or []:
            if c.get("rule_type") == "capability":
                counter.update(set((c.get("params") or {}).get("tags") or []))
    for message in session.scalars(select(InfoRequest.message)):
        counter.update(tags(message))
    rows = [{"tag": t, "label": skill_label(t), "count": n} for t, n in counter.items()]
    return sorted(rows, key=lambda r: (-r["count"], r["label"]))


def decisions(session: Session) -> dict[str, Any]:
    def entries(action: str) -> list[AuditLog]:
        return list(session.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))

    overrides = entries("override")
    return {
        "shortlisted": len(entries("shortlist_decision")),
        "info_requests": len(entries("info_request")),
        "overrides": {
            "count": len(overrides),
            "items": [
                {
                    "at": o.at.isoformat(),
                    "actor_label": o.actor_label,
                    "opportunity_id": (o.details or {}).get("opportunity_id"),
                    "reason": o.reason,
                    "order": (o.details or {}).get("to"),
                    "engine_ranking": (o.details or {}).get("engine_ranking"),
                }
                for o in overrides
            ],
        },
    }


def fairness(session: Session) -> dict[str, Any]:
    """Outcomes by province and size band from the most recent run (a mechanism, not a finding)."""
    run = session.scalars(select(MatchRun).order_by(MatchRun.id.desc()).limit(1)).first()
    by_province: dict[str, dict[str, Any]] = {}
    by_size: dict[str, dict[str, Any]] = {}
    total = 0
    if run is not None:
        for result in session.scalars(select(MatchResult).where(MatchResult.run_id == run.id)):
            sme = session.get(SME, result.sme_id)
            total += 1
            for table, key, label in (
                (
                    by_province,
                    sme.province or "unknown",
                    PROVINCE_NAMES.get(sme.province or "", sme.province),
                ),
                (by_size, sme.size_band or "unknown", (sme.size_band or "unknown").capitalize()),
            ):
                row = table.setdefault(
                    key, {"group": key, "label": label or key, "total": 0, **dict.fromkeys(STATUSES, 0)}
                )
                row["total"] += 1
                row[result.status] += 1
    return {
        "run_id": run.id if run else None,
        "opportunity_id": run.opportunity_id if run else None,
        "total": total,
        "small_sample": total < SMALL_SAMPLE_THRESHOLD,
        "note": "Small sample: this shows the monitoring mechanism, not a finding.",
        "by_province": sorted(by_province.values(), key=lambda r: r["group"]),
        "by_size_band": sorted(by_size.values(), key=lambda r: r["group"]),
    }


def build(session: Session) -> dict[str, Any]:
    return {
        "pipeline": pipeline(session),
        "readiness_gaps": readiness_gaps(session),
        "requested_skills": requested_skills(session),
        "decisions": decisions(session),
        "fairness": fairness(session),
    }
