"""Weighted fit scorer (plan A11): component formulas, calibration, weights."""

import math
from datetime import date

import pytest

from app.engine import geo, scoring
from app.engine.scoring import calibrate, score, validate_weights
from app.engine.types import EvidenceRef, Fact, OpportunitySpec, SMEProfile

WEIGHTS = {"capability": 40, "experience": 25, "capacity": 20, "location": 15}
PREFERRED = [
    {
        "rule_type": "capability",
        "params": {
            "text": "Service desk, desktop/device support, Microsoft 365 administration",
            "tags": ["service_desk", "desktop_device_support", "m365_admin"],
        },
    },
    {"rule_type": "experience", "params": {"min_years": 3, "min_client_users": 200}},
    {"rule_type": "capacity", "params": {"min_technicians": 8, "hours_start": "07:00", "hours_end": "18:00"}},
    {"rule_type": "location", "params": {"anchor": "Midrand", "full_score_km": 50, "zero_score_km": 150}},
]
MODEL = "local-lexicon-v1"


def opp(weights=None):
    return OpportunitySpec(
        id=1, closing_date=date(2027, 2, 26), preferred_criteria=PREFERRED, weights=dict(weights or WEIGHTS)
    )


def fact(key, value):
    ref = EvidenceRef(
        field_key=key,
        value=value,
        source_type="ai_extracted",
        source_label="Doc.pdf",
        document_id=1,
        doc_type="capability_statement",
        quote=f"quote {key}",
        confidence=0.95,
    )
    return Fact(key, "ok", value, "ai_extracted", 0.95, ref, [ref])


def make_profile(lat=None, lon=None, **values):
    base = {
        "services_description": "service desk, desktop support and Microsoft 365 administration",
        "service_tags": ["service_desk", "desktop_device_support", "m365_admin"],
        "years_trading": 6,
        "past_clients": [{"name": "A", "user_count": 250}, {"name": "B", "user_count": 320}],
        "technician_count": 11,
        "service_desk_hours": {"start": "07:00", "end": "18:00"},
        "base_town": "Midrand",
    }
    base.update(values)
    facts = {k: fact(k, v) for k, v in base.items() if v is not None}
    return SMEProfile(sme_id=1, facts=facts, lat=lat, lon=lon)


def km_north_of_midrand(km):
    lat, lon = geo.TOWNS["Midrand"]
    return lat + math.degrees(km / geo.EARTH_RADIUS_KM), lon


def comp(result, name):
    return result.component(name)


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("km", "expected"),
    [(0, 100.0), (49.9, 100.0), (50, 100.0), (100, 50.0), (149.9, 0.1), (150, 0.0), (400, 0.0)],
)
def test_location_boundaries(km, expected):
    lat, lon = km_north_of_midrand(km)
    result = score(make_profile(lat=lat, lon=lon, base_town=None), opp(), 0.9, MODEL)
    assert comp(result, "location").score == pytest.approx(expected, abs=0.05)


def test_location_uses_town_coordinates_and_explains_distance():
    c = comp(score(make_profile(base_town="Soshanguve"), opp(), 0.9, MODEL), "location")
    assert 52 < c.details["distance_km"] < 54
    assert c.score == pytest.approx(100 * (150 - c.details["distance_km"]) / 100, abs=0.1)
    assert "Soshanguve" in c.explanation and "km from Midrand" in c.explanation


def test_location_unknown_scores_zero():
    c = comp(score(make_profile(base_town="Nowhere"), opp(), 0.9, MODEL), "location")
    assert c.score == 0.0 and "unknown" in c.explanation


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("techs", "expected"), [(6, 85.0), (8, 100.0), (11, 100.0), (0, 40.0)])
def test_capacity_technicians(techs, expected):
    assert comp(score(make_profile(technician_count=techs), opp(), 0.9, MODEL), "capacity").score == expected


def test_capacity_explains_6_vs_8():
    c = comp(score(make_profile(technician_count=6), opp(), 0.9, MODEL), "capacity")
    assert "6 technicians vs 8 preferred" in c.explanation


@pytest.mark.parametrize(
    ("hours", "coverage"),
    [
        ({"start": "07:00", "end": "18:00"}, 1.0),
        ({"start": "06:00", "end": "20:00"}, 1.0),
        ({"start": "07:30", "end": "17:00"}, 9.5 / 11),
        ({"start": "08:00", "end": "17:00"}, 9 / 11),
        ({"start": "18:00", "end": "22:00"}, 0.0),
        (None, 0.0),
    ],
)
def test_capacity_hours_overlap(hours, coverage):
    c = comp(score(make_profile(service_desk_hours=hours), opp(), 0.9, MODEL), "capacity")
    assert c.details["hours_coverage"] == pytest.approx(coverage)
    assert c.score == pytest.approx(round(100 * (0.6 + 0.4 * coverage), 1))


def test_capacity_conflict_scores_lower_value():
    refs = [
        EvidenceRef(field_key="technician_count", value=v, source_type=st, source_label=lbl)
        for v, st, lbl in ((15, "sme_confirmed", "SME profile form"), (4, "ai_extracted", "Doc.pdf"))
    ]
    prof = make_profile()
    prof.facts["technician_count"] = Fact("technician_count", "conflict", candidates=refs)
    c = comp(score(prof, opp(), 0.9, MODEL), "capacity")
    assert c.details["technicians"] == 4 and "conflicting values 4 and 15" in c.explanation


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("years", "clients", "expected"),
    [
        (3, [], 50.0),
        (3, [{"user_count": 210}, {"user_count": 80}], 80.0),
        (6, [{"user_count": 250}, {"user_count": 320}, {"user_count": 600}], 100.0),
        (1.5, [{"user_count": 200}, {"user_count": 200}], 75.0),
        (None, None, 0.0),
    ],
)
def test_experience(years, clients, expected):
    c = comp(score(make_profile(years_trading=years, past_clients=clients), opp(), 0.9, MODEL), "experience")
    assert c.score == expected


# ---------------------------------------------------------------------------
# Capability + calibration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sim", "model", "expected"),
    [
        (0.95, MODEL, 1.0),
        (0.45, MODEL, 0.5),
        (0.0, MODEL, 0.0),
        (-0.2, MODEL, 0.0),
        (float("nan"), MODEL, 0.0),
        (None, MODEL, 0.0),
        (0.2, "amazon.titan-embed-text-v2:0", 0.0),
        (0.75, "amazon.titan-embed-text-v2:0", 1.0),
        (0.475, "amazon.titan-embed-text-v2:0", 0.5),
        (0.3, "unknown-model", 0.3),
    ],
)
def test_calibration_clamp(sim, model, expected):
    assert calibrate(sim, model) == pytest.approx(expected)


def test_capability_formula_and_semantic_explanation():
    prof = make_profile(
        services_description="device lifecycle, Microsoft 365 tenant administration, "
        "remote and on-site user assistance",
        service_tags=["service_desk", "desktop_device_support"],
    )
    c = comp(score(prof, opp(), 0.45, MODEL), "capability")
    assert c.score == pytest.approx(100 * (0.6 * 0.5 + 0.4 * 2 / 3), abs=0.05)
    assert "'device lifecycle, Microsoft 365 tenant administration" in c.explanation
    assert "'Service desk, desktop/device support, Microsoft 365 administration'" in c.explanation
    assert "AI-assisted semantic match" in c.explanation
    assert "2 of 3" in c.explanation


def test_only_capability_uses_similarity():
    low = score(make_profile(), opp(), 0.1, MODEL)
    high = score(make_profile(), opp(), 0.9, MODEL)
    for name in scoring.COMPONENTS:
        same = comp(low, name).score == comp(high, name).score
        assert same == (name != "capability"), name


def test_every_component_has_explanation_and_evidence():
    result = score(make_profile(), opp(), 0.9, MODEL)
    assert [c.name for c in result.components] == list(scoring.COMPONENTS)
    for c in result.components:
        assert c.explanation and c.evidence, c.name
        assert c.weight == WEIGHTS[c.name]
        assert c.weighted == pytest.approx(c.score * c.weight / 100, abs=0.01)


def test_total_is_weighted_sum_rounded():
    result = score(make_profile(technician_count=6), opp(), 0.9, MODEL)
    expected = sum(c.score * c.weight / 100 for c in result.components)
    assert result.total == pytest.approx(round(expected, 1), abs=0.05)
    assert result.total == round(result.total, 1)


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "weights",
    [
        {"capability": 40, "experience": 25, "capacity": 20, "location": 14},
        {"capability": 40, "experience": 25, "capacity": 20, "location": 16},
        {"capability": 40.0, "experience": 25, "capacity": 20, "location": 15},
        {"capability": True, "experience": 64, "capacity": 20, "location": 15},
        {"capability": 40, "experience": 25, "capacity": 35},
        {"capability": 40, "experience": 25, "capacity": 20, "location": 15, "price": 0},
        {"capability": 120, "experience": -20, "capacity": 0, "location": 0},
        [40, 25, 20, 15],
    ],
)
def test_invalid_weights_rejected(weights):
    with pytest.raises(ValueError):
        validate_weights(weights)
    with pytest.raises(ValueError):
        score(
            make_profile(),
            opp(weights)
            if isinstance(weights, dict)
            else OpportunitySpec(id=1, closing_date=date(2027, 2, 26), weights=weights),
            0.9,
            MODEL,
        )


def test_valid_weights_accepted():
    assert validate_weights(WEIGHTS) == WEIGHTS
    assert validate_weights({"capability": 100, "experience": 0, "capacity": 0, "location": 0})


def test_editing_weights_changes_totals_and_order():
    strong_far = make_profile(
        lat=km_north_of_midrand(140)[0], lon=km_north_of_midrand(140)[1], base_town=None
    )
    weak_near = make_profile(services_description="web design", service_tags=["web_design"])
    default = (score(strong_far, opp(), 0.9, MODEL).total, score(weak_near, opp(), 0.0, MODEL).total)
    assert default[0] > default[1]
    location_heavy = {"capability": 10, "experience": 10, "capacity": 10, "location": 70}
    edited = (
        score(strong_far, opp(location_heavy), 0.9, MODEL).total,
        score(weak_near, opp(location_heavy), 0.0, MODEL).total,
    )
    assert edited != default
    assert edited[0] < edited[1]
