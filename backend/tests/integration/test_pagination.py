"""Server-side pagination for the audit log and opportunities list (backward compatible)."""

import pytest
from api_helpers import ADMIN, BUYER, as_sme

# seed() writes 26 rows (20 extraction, 4 consent, 1 sme_profile_entry, 1 sme_confirmation);
# POST /api/admin/reset adds a 27th (demo_reset), which the client fixture does not run.
SEED_AUDIT_ROWS = 26
SEED_EXTRACTIONS = 20


def audit(client, headers=ADMIN, **params):
    r = client.get("/api/audit", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def ids(body):
    return [e["id"] for e in body["entries"]]


def test_legacy_audit_shape_is_oldest_first(client):
    body = audit(client)
    assert body["order"] == "oldest_first"
    assert body["total"] == len(body["entries"]) == SEED_AUDIT_ROWS
    assert body["page"] == 1
    assert body["page_size"] == body["total"]
    assert ids(body) == sorted(ids(body))


def test_paginated_default_is_twenty_newest_first(client):
    legacy = audit(client)
    body = audit(client, page=1)
    assert body["order"] == "newest_first"
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["entries"]) == 20
    assert body["total"] == legacy["total"] == SEED_AUDIT_ROWS
    page_ids = ids(body)
    assert all(a > b for a, b in zip(page_ids, page_ids[1:], strict=False))
    assert page_ids == list(reversed(ids(legacy)))[:20]


def test_page_size_alone_switches_to_paginated_mode(client):
    body = audit(client, page_size=5)
    assert body["order"] == "newest_first"
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["entries"]) == 5


def test_page_two_continues_the_sequence(client):
    reversed_legacy = list(reversed(ids(audit(client))))
    first = ids(audit(client, page=1))
    second = ids(audit(client, page=2))
    assert not set(first) & set(second)
    assert first[-1] > second[0]
    assert first + second == reversed_legacy[:40]


def test_last_partial_page(client):
    size = 20
    total = audit(client)["total"]
    pages = -(-total // size)
    body = audit(client, page=pages, page_size=size)
    assert len(body["entries"]) == total - (pages - 1) * size


def test_out_of_range_page_is_empty(client):
    body = audit(client, page=999)
    assert body["entries"] == []
    assert body["total"] == SEED_AUDIT_ROWS
    assert body["page"] == 999


def test_page_size_five(client):
    body = audit(client, page=1, page_size=5)
    assert len(body["entries"]) == 5
    assert body["page_size"] == 5


def test_action_filter(client):
    body = audit(client, page=1, action="extraction")
    assert body["total"] == SEED_EXTRACTIONS
    assert body["entries"]
    assert all(e["action"] == "extraction" for e in body["entries"])
    legacy = audit(client, action="extraction")
    assert legacy["total"] == SEED_EXTRACTIONS
    assert all(e["action"] == "extraction" for e in legacy["entries"])


def test_actor_role_filter(client):
    body = audit(client, page=1, page_size=100, actor_role="system")
    assert body["entries"]
    assert all(e["actor_role"] == "system" for e in body["entries"])


def test_buyer_opportunity_filter_with_pagination(client, opp_id):
    body = audit(client, headers=BUYER, opportunity_id=opp_id, page=1)
    assert body["order"] == "newest_first"
    assert len(body["entries"]) <= 20
    actions = {e["action"] for e in body["entries"]}
    assert not actions & {"ai_mode_change", "demo_reset"}
    legacy = audit(client, headers=BUYER, opportunity_id=opp_id)
    assert body["total"] == legacy["total"]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page": "abc"},
        {"page_size": 0},
        {"page_size": 101},
        {"action": "bogus"},
        {"actor_role": "bogus"},
    ],
)
def test_invalid_audit_params_are_422(client, params):
    r = client.get("/api/audit", headers=ADMIN, params=params)
    assert r.status_code == 422, r.text


def test_sme_still_forbidden_from_audit(client):
    r = client.get("/api/audit", headers=as_sme("thuto"), params={"page": 1})
    assert r.status_code == 403


def test_opportunities_without_params_is_bare_list(client):
    r = client.get("/api/opportunities", headers=BUYER)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_opportunities_paginated_envelope(client):
    r = client.get("/api/opportunities", headers=BUYER, params={"page": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["items"][0]["status"] == "published"


def test_opportunities_out_of_range_page_is_empty(client):
    body = client.get("/api/opportunities", headers=BUYER, params={"page": 2}).json()
    assert body["items"] == []
    assert body["total"] == 1


def test_opportunities_invalid_page_size_is_422(client):
    r = client.get("/api/opportunities", headers=BUYER, params={"page_size": 0})
    assert r.status_code == 422
