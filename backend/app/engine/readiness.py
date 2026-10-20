"""Readiness actions (plan A12): plain-language next steps from templates. Pure.

Input is the stored form of match results (checks/components as dicts), so the same function works on
fresh engine output and on persisted match_results. It never reads or writes ranks or scores.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.ai.lexicon import CONCEPT_LABELS
from app.engine.eligibility import PROVINCE_NAMES, format_value, rand
from app.engine.types import PASS, OpportunitySpec

LOW_COMPONENT_SCORE = 60


def _check_text(check: Mapping[str, Any], opportunity: OpportunitySpec) -> str:
    rule, issues, details = check["rule"], set(check.get("issues") or []), check.get("details") or {}
    if "conflict" in issues and rule != "data_consistency":
        return f"Resolve the conflicting values for '{check['label']}' on your profile."
    if "low_confidence" in issues or "unconfirmed_failure" in issues:
        return f"Review and confirm the AI-extracted values for '{check['label']}' on your profile."

    if rule == "pi_insurance":
        if "outdated" in issues:
            return "Upload a renewed PI insurance schedule covering the contract start date."
        if "confirmed_failure" in issues:
            return (
                f"Increase professional indemnity cover to at least {rand(details.get('min_amount') or 0)} "
                "and upload the updated schedule."
            )
        return "Upload your PI insurance schedule."
    if rule == "tax_compliance":
        if "outdated" in issues:
            return "Upload a tax compliance status letter that is valid beyond the closing date."
        return "Upload a current tax compliance status letter."
    if rule == "operating_region":
        region = PROVINCE_NAMES.get(str(details.get("region", "")).upper(), details.get("region", ""))
        return f"This opportunity requires {region} operations."
    if rule == "csd_registration":
        return "Add your CSD supplier number (MAAA followed by 7 digits) to your profile."
    if rule == "ownership_or_bbbee":
        return "Add your Black ownership percentage or B-BBEE level, with a supporting document."
    if rule == "infosec_policy":
        return "Upload your information security & POPIA policy."
    if rule == "certified_technicians":
        return (
            f"Renew expired technician certifications or upload current ones: at least "
            f"{details.get('min_count', 1)} must be valid beyond the closing date."
        )
    if rule == "data_consistency":
        parts = []
        for c in details.get("conflicts") or []:
            values = ", ".join(f"{v['source']} {format_value(v['value'])}" for v in c.get("values", []))
            parts.append(f"{c['label'].lower()} ({values})")
        listed = "; ".join(parts) or "conflicting values"
        return f"Resolve conflicting information on your profile: {listed}."
    return f"Review '{check['label']}' on your profile."


def _component_text(component: Mapping[str, Any], opportunity: OpportunitySpec) -> str:
    name, details = component["name"], component.get("details") or {}
    if name == "capability":
        missing = [
            t for t in details.get("requested_tags") or [] if t not in (details.get("covered_tags") or [])
        ]
        if missing:
            areas = ", ".join(CONCEPT_LABELS.get(t, t) for t in missing)
            return f"Build and describe capability in: {areas}."
        return "Describe your services in more detail so buyers can match them."
    if name == "experience":
        users = format_value(details.get("min_client_users") or 0)
        return (
            f"Add references from comparable clients of {users}+ users "
            f"({format_value(details.get('min_years') or 0)}+ years' experience preferred)."
        )
    if name == "capacity":
        return (
            f"Grow technician capacity towards {format_value(details.get('min_technicians') or 0)} "
            "or extend service desk hours to cover the preferred window."
        )
    if name == "location":
        anchor = details.get("anchor") or "the buyer's sites"
        return (
            f"On-site response is easier from a base near {anchor}; "
            "consider a local partner or satellite office."
        )
    return f"Improve your {component.get('label', name).lower()} score."


def generate(results: Iterable[Mapping[str, Any]], opportunity: OpportunitySpec) -> list[dict[str, Any]]:
    """One action per non-pass check and per component scoring below 60.

    results: mappings with sme_id, checks (list of check dicts) and components (list of component dicts).
    Returns [{sme_id, category, text}] in a stable order.
    """
    actions: list[dict[str, Any]] = []
    for result in results:
        sme_id = result["sme_id"]
        seen: set[str] = set()

        def add(category: str, text: str, sme_id: int = sme_id, seen: set[str] = seen) -> None:
            if text not in seen:
                seen.add(text)
                actions.append({"sme_id": sme_id, "category": category, "text": text})

        for check in result.get("checks") or []:
            if check.get("outcome") != PASS:
                add(check["rule"], _check_text(check, opportunity))
        for component in result.get("components") or []:
            if (component.get("score") or 0) < LOW_COMPONENT_SCORE:
                add(f"{component['name']}_score", _component_text(component, opportunity))
    return actions
