"""Weighted fit scorer (plan A11). Pure: the semantic similarity is computed in Postgres by the
matching service and passed in; only the capability component uses it.

Components (default weights 40/25/20/15, stored per opportunity and editable):
- capability = 0.6 * calibrated semantic similarity + 0.4 * tag coverage
- experience = 0.5 * min(years / min_years, 1) + 0.5 * clients (0 comparable -> 0, 1 -> 0.6, >= 2 -> 1)
- capacity   = 0.6 * min(technicians / min_technicians, 1) + 0.4 * hours coverage of the preferred window
- location   = 100 within full_score_km of the anchor, linear to 0 at zero_score_km
total = sum(score * weight / 100), rounded to 1 decimal.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from app.ai.lexicon import CONCEPT_LABELS
from app.config import EMBEDDING_CALIBRATION
from app.engine.eligibility import as_number, format_value
from app.engine.geo import haversine_km, town_coordinates
from app.engine.types import ComponentScore, Fact, OpportunitySpec, ScoreResult, SMEProfile

COMPONENTS = ("capability", "experience", "capacity", "location")
COMPONENT_LABELS = {
    "capability": "Capability match",
    "experience": "Experience",
    "capacity": "Capacity",
    "location": "Location",
}
DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "capability": {"text": "", "tags": []},
    "experience": {"min_years": 3, "min_client_users": 200},
    "capacity": {"min_technicians": 8, "hours_start": "07:00", "hours_end": "18:00"},
    "location": {"anchor": "Midrand", "full_score_km": 50, "zero_score_km": 150},
}
DEFAULT_CALIBRATION = {"floor": 0.0, "ceil": 1.0}


def validate_weights(weights: Any) -> dict[str, int]:
    """Weights must be integers (0-100) for exactly the four components and sum to 100."""
    if not isinstance(weights, Mapping):
        raise ValueError("Weights must be an object of component -> integer.")
    if set(weights) != set(COMPONENTS):
        raise ValueError(f"Weights must have exactly these components: {', '.join(COMPONENTS)}.")
    out: dict[str, int] = {}
    for name in COMPONENTS:
        value = weights[name]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"Weight for {name} must be an integer between 0 and 100.")
        out[name] = value
    total = sum(out.values())
    if total != 100:
        raise ValueError(f"Weights must sum to 100 (got {total}).")
    return out


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def calibrate(similarity: float | None, model_id: str | None) -> float:
    """clamp((cos - floor) / (ceil - floor)) with per-model calibration from config."""
    if similarity is None or math.isnan(similarity):
        return 0.0
    cal = EMBEDDING_CALIBRATION.get(model_id or "", DEFAULT_CALIBRATION)
    span = cal["ceil"] - cal["floor"]
    if span <= 0:
        return 0.0
    return _clamp((similarity - cal["floor"]) / span)


def _number(fact: Fact) -> tuple[float | None, str | None]:
    """Numeric value for scoring. Conflicts score on the lower value (conservative) with a note."""
    if fact.status in ("ok", "low_confidence"):
        return as_number(fact.value), None
    if fact.status == "conflict":
        values = sorted(v for v in (as_number(e.value) for e in fact.evidence) if v is not None)
        if values:
            listed = " and ".join(format_value(v) for v in values)
            return values[0], f"conflicting values {listed}; scored on the lower value"
    return None, None


def _minutes(hhmm: Any) -> int | None:
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Components: each returns (score 0-100, explanation, evidence, details)
# ---------------------------------------------------------------------------


def score_capability(
    profile: SMEProfile,
    params: dict[str, Any],
    similarity: float | None,
    model_id: str | None,
    buyer_text: str,
) -> tuple[float, str, list, dict[str, Any]]:
    description = profile.fact("services_description")
    tags_fact = profile.fact("service_tags")
    wanted = [t for t in params.get("tags") or []]
    sme_tags = (
        tags_fact.value
        if tags_fact.status in ("ok", "low_confidence") and isinstance(tags_fact.value, list)
        else []
    )
    covered = [t for t in wanted if t in sme_tags]
    coverage = len(covered) / len(wanted) if wanted else None
    semantic = calibrate(similarity, model_id)
    raw = 0.6 * semantic + 0.4 * coverage if coverage is not None else semantic

    if description.status not in ("ok", "low_confidence") or not description.value:
        lead = "Services description not provided, so no semantic match."
    elif similarity is None or math.isnan(similarity):
        lead = "No comparable embedding for the services description, so no semantic match."
    else:
        verb = "matched" if semantic >= 0.5 else "partly matched" if semantic > 0 else "did not match"
        lead = f"'{description.value}' {verb} '{buyer_text}' (AI-assisted semantic match)."
    if coverage is None:
        cover = ""
    else:
        names = ", ".join(CONCEPT_LABELS.get(t, t) for t in covered)
        cover = f" Covers {len(covered)} of {len(wanted)} requested service areas" + (
            f": {names}." if names else "."
        )
    details = {
        "similarity": similarity,
        "embedding_model_id": model_id,
        "semantic": round(semantic, 4),
        "tag_coverage": coverage,
        "covered_tags": covered,
        "requested_tags": wanted,
        "buyer_text": buyer_text,
    }
    return raw * 100, lead + cover, description.evidence + tags_fact.evidence, details


def score_experience(profile: SMEProfile, params: dict[str, Any]) -> tuple[float, str, list, dict[str, Any]]:
    min_years = float(params.get("min_years") or 1)
    min_users = float(params.get("min_client_users") or 0)
    years_fact, clients_fact = profile.fact("years_trading"), profile.fact("past_clients")
    years, years_note = _number(years_fact)
    years_part = _clamp(years / min_years) if years is not None else 0.0

    clients = (
        clients_fact.value
        if clients_fact.status in ("ok", "low_confidence") and isinstance(clients_fact.value, list)
        else []
    )
    comparable = [
        c for c in clients if isinstance(c, dict) and (as_number(c.get("user_count")) or 0) >= min_users
    ]
    clients_part = 0.0 if not comparable else 0.6 if len(comparable) == 1 else 1.0
    raw = 0.5 * years_part + 0.5 * clients_part

    years_text = (
        f"{format_value(years)} years trading ({format_value(min_years)}+ preferred)"
        if years is not None
        else "Years trading not provided"
    )
    if years_note:
        years_text += f" ({years_note})"
    users = ", ".join(format_value(as_number(c.get("user_count"))) for c in comparable)
    n = len(comparable)
    client_text = f"{n} comparable client{'s' if n != 1 else ''} of {format_value(min_users)}+ users" + (
        f" ({users} users)" if users else ""
    )
    details = {
        "years": years,
        "comparable_clients": comparable,
        "min_years": min_years,
        "min_client_users": min_users,
    }
    return raw * 100, f"{years_text}; {client_text}.", years_fact.evidence + clients_fact.evidence, details


def score_capacity(profile: SMEProfile, params: dict[str, Any]) -> tuple[float, str, list, dict[str, Any]]:
    min_tech = float(params.get("min_technicians") or 1)
    ws, we = _minutes(params.get("hours_start")), _minutes(params.get("hours_end"))
    tech_fact, hours_fact = profile.fact("technician_count"), profile.fact("service_desk_hours")
    techs, tech_note = _number(tech_fact)
    tech_part = _clamp(techs / min_tech) if techs is not None else 0.0

    hours = (
        hours_fact.value
        if hours_fact.status in ("ok", "low_confidence") and isinstance(hours_fact.value, dict)
        else None
    )
    s, e = (_minutes(hours.get("start")), _minutes(hours.get("end"))) if hours else (None, None)
    window = f"{params.get('hours_start')}-{params.get('hours_end')}"
    if s is None or e is None or ws is None or we is None or we <= ws:
        coverage = 0.0
        hours_text = "service desk hours not provided"
    else:
        coverage = _clamp((min(e, we) - max(s, ws)) / (we - ws))
        hours_text = (
            f"service desk hours {hours['start']}-{hours['end']} cover {round(coverage * 100)}% of {window}"
        )
    raw = 0.6 * tech_part + 0.4 * coverage

    if techs is None:
        tech_text = f"Technician count not provided ({format_value(min_tech)} preferred)"
    else:
        tech_text = f"{format_value(techs)} technicians vs {format_value(min_tech)} preferred"
        if tech_note:
            tech_text += f" ({tech_note})"
    details = {"technicians": techs, "min_technicians": min_tech, "hours": hours, "hours_coverage": coverage}
    return raw * 100, f"{tech_text}; {hours_text}.", tech_fact.evidence + hours_fact.evidence, details


def score_location(profile: SMEProfile, params: dict[str, Any]) -> tuple[float, str, list, dict[str, Any]]:
    anchor = str(params.get("anchor") or "")
    full_km = float(params.get("full_score_km") or 0)
    zero_km = float(params.get("zero_score_km") or full_km)
    town_fact = profile.fact("base_town")
    town = town_fact.value if town_fact.status in ("ok", "low_confidence") else None
    base = town_coordinates(town)
    if base is None and profile.lat is not None and profile.lon is not None:
        base = (profile.lat, profile.lon)
    anchor_coords = town_coordinates(anchor)
    if base is None or anchor_coords is None:
        return (
            0.0,
            f"Base location unknown, so distance to {anchor} cannot be scored.",
            town_fact.evidence,
            {},
        )
    km = haversine_km(base, anchor_coords)
    if km <= full_km:
        raw = 1.0
    elif km >= zero_km or zero_km <= full_km:
        raw = 0.0
    else:
        raw = (zero_km - km) / (zero_km - full_km)
    where = f"Based in {town}" if town else "Base"
    explanation = (
        f"{where}, {km:.0f} km from {anchor} (full score within {format_value(full_km)} km, "
        f"none beyond {format_value(zero_km)} km)."
    )
    return raw * 100, explanation, town_fact.evidence, {"distance_km": round(km, 1), "anchor": anchor}


# ---------------------------------------------------------------------------


def score(
    profile: SMEProfile,
    opportunity: OpportunitySpec,
    similarity: float | None = None,
    embedding_model_id: str | None = None,
) -> ScoreResult:
    """Score one SME against the opportunity's preferred criteria using the opportunity's weights."""
    weights = validate_weights(opportunity.weights)

    def params(name: str) -> dict[str, Any]:
        return {**DEFAULT_PARAMS[name], **(opportunity.preferred(name) or {})}

    cap = params("capability")
    buyer_text = cap.get("text") or opportunity.capability_text or ""
    raw_scores = {
        "capability": score_capability(profile, cap, similarity, embedding_model_id, buyer_text),
        "experience": score_experience(profile, params("experience")),
        "capacity": score_capacity(profile, params("capacity")),
        "location": score_location(profile, params("location")),
    }
    components: list[ComponentScore] = []
    total = 0.0
    for name in COMPONENTS:
        raw, explanation, evidence, details = raw_scores[name]
        raw = _clamp(raw, 0.0, 100.0)
        weighted = raw * weights[name] / 100
        total += weighted
        components.append(
            ComponentScore(
                name=name,
                label=COMPONENT_LABELS[name],
                score=round(raw, 1),
                weight=weights[name],
                weighted=round(weighted, 2),
                explanation=explanation,
                evidence=list(evidence),
                details=details,
            )
        )
    return ScoreResult(total=round(total, 1), components=components)
