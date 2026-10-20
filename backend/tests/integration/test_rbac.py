"""Server-side RBAC and validation over HTTP: roles are enforced by the API, not the frontend."""

import io

import pytest
from api_helpers import ADMIN, BUYER, THUTO_FILES, as_sme, pdf_files
from reportlab.pdfgen import canvas

from app.ai import gateway

THUTO = as_sme("thuto")
MMAPULA = as_sme("mmapula")
ZOLA = as_sme("zola")


def unknown_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "FICTIONAL - DEMO ONLY. A capability statement that was never cached.")
    c.save()
    return buf.getvalue()


def upload_thuto_capability(client) -> int:
    r = client.post("/api/sme/me/documents", headers=THUTO, files=pdf_files(THUTO_FILES[0]))
    assert r.status_code == 200, r.text
    return r.json()["documents"][0]["id"]


def test_public_endpoints_need_no_role(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    identities = client.get("/api/demo/identities").json()["identities"]
    assert [i["role"] for i in identities] == ["sme"] * 5 + ["buyer", "admin"]
    assert identities[5]["label"] == "Buyer: Naledi (Ubuntu Office Parks)"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Demo-Role": "superuser"},
        {"X-Demo-Role": "sme"},
        {"X-Demo-Role": "sme", "X-Demo-Sme-Id": "unknown-sme"},
    ],
)
def test_401_without_valid_role(client, headers):
    assert client.get("/api/opportunities", headers=headers).status_code == 401
    assert client.get("/api/sme/me", headers=headers).status_code == 401
    assert client.get("/api/settings/ai-mode", headers=headers).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/opportunities/{opp}/match-runs", None),
        ("post", "/api/admin/reset", None),
        ("get", "/api/admin/dashboard", None),
        ("put", "/api/settings/ai-mode", {"mode": "cached"}),
        ("get", "/api/audit", None),
        ("get", "/api/opportunities", None),
        ("post", "/api/opportunities/{opp}/shortlist", {"sme_slug": "mmapula"}),
        ("get", "/api/smes/zola/profile", None),
    ],
)
def test_sme_forbidden(client, opp_id, method, path, body):
    r = client.request(method, path.format(opp=opp_id), headers=MMAPULA, json=body)
    assert r.status_code == 403, r.text


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/admin/reset", None),
        ("put", "/api/settings/ai-mode", {"mode": "cached"}),
        ("get", "/api/admin/dashboard", None),
        ("get", "/api/sme/me/profile", None),
    ],
)
def test_buyer_forbidden(client, method, path, body):
    r = client.request(method, path, headers=BUYER, json=body)
    assert r.status_code == 403, r.text


def test_admin_cannot_act_as_buyer(client, opp_id):
    assert client.post(f"/api/opportunities/{opp_id}/match-runs", headers=ADMIN).status_code == 403
    assert client.get(f"/api/opportunities/{opp_id}/match-runs/latest", headers=ADMIN).status_code == 200


def test_buyer_only_sees_own_opportunities(client):
    buyer = client.get("/api/opportunities", headers=BUYER).json()
    admin = client.get("/api/opportunities", headers=ADMIN).json()
    assert [o["buyer_org"] for o in buyer] == ["Ubuntu Office Parks (fictional)"]
    assert len(admin) == 3
    other = next(o["id"] for o in admin if o["buyer_org"] != "Ubuntu Office Parks (fictional)")
    assert client.get(f"/api/opportunities/{other}", headers=BUYER).status_code == 403


def test_buyer_blocked_from_unconsented_sme(client, opp_id):
    doc_id = upload_thuto_capability(client)
    assert client.get("/api/smes/thuto/profile", headers=BUYER).status_code == 403
    assert client.get(f"/api/documents/{doc_id}/text", headers=BUYER).status_code == 403
    r = client.post(
        f"/api/opportunities/{opp_id}/info-requests",
        headers=BUYER,
        json={"sme_slug": "thuto", "kind": "information", "message": "Hello"},
    )
    assert r.status_code == 403
    audit = client.get("/api/audit", headers=BUYER).json()["entries"]
    assert not any(e["details"].get("sme_id") == 1 for e in audit)  # Thuto's history stays private
    # The owner and the admin can read it; the buyer can after consent.
    assert client.get(f"/api/documents/{doc_id}/text", headers=THUTO).status_code == 200
    assert client.get(f"/api/documents/{doc_id}/text", headers=ADMIN).status_code == 200
    assert client.get("/api/smes/thuto/profile", headers=ADMIN).status_code == 200
    assert client.post("/api/sme/me/consent", headers=THUTO, json={"granted": True}).status_code == 200
    assert client.get("/api/smes/thuto/profile", headers=BUYER).status_code == 200
    assert client.get(f"/api/documents/{doc_id}/text", headers=BUYER).status_code == 200
    audit = client.get("/api/audit", headers=BUYER).json()["entries"]
    assert any(e["action"] == "extraction" and e["details"].get("sme_id") == 1 for e in audit)


def test_sme_cannot_read_another_smes_document(client):
    doc_id = upload_thuto_capability(client)
    assert client.get(f"/api/documents/{doc_id}/text", headers=ZOLA).status_code == 403


def test_override_requires_reason(client, opp_id):
    assert client.post(f"/api/opportunities/{opp_id}/match-runs", headers=BUYER).status_code == 200
    for slug in ("mmapula", "zola"):
        r = client.post(f"/api/opportunities/{opp_id}/shortlist", headers=BUYER, json={"sme_slug": slug})
        assert r.status_code == 200, r.text
    url = f"/api/opportunities/{opp_id}/shortlist/order"
    for body in ({"sme_slugs": ["zola", "mmapula"]}, {"sme_slugs": ["zola", "mmapula"], "reason": "   "}):
        r = client.put(url, headers=BUYER, json=body)
        assert r.status_code == 422
        assert r.json()["detail"] == "A written reason is required to change the shortlist order."
    r = client.put(url, headers=BUYER, json={"sme_slugs": ["zola"], "reason": "Prefer Zola"})
    assert r.status_code == 422
    audit = client.get("/api/audit", headers=BUYER).json()["entries"]
    assert "override" not in [e["action"] for e in audit]
    shortlist = client.get(f"/api/opportunities/{opp_id}/match-runs/latest", headers=BUYER).json()[
        "shortlist"
    ]
    assert [e["sme_slug"] for e in shortlist] == ["mmapula", "zola"]


def test_weights_must_sum_to_100(client, opp_id):
    opp = client.get(f"/api/opportunities/{opp_id}", headers=BUYER).json()
    body = {
        "mandatory_criteria": opp["mandatory_criteria"],
        "preferred_criteria": opp["preferred_criteria"],
        "weights": {"capability": 50, "experience": 25, "capacity": 20, "location": 15},
    }
    r = client.put(f"/api/opportunities/{opp_id}", headers=BUYER, json=body)
    assert r.status_code == 422 and "sum to 100" in r.json()["detail"]
    body["weights"] = {"capability": 40, "experience": 25, "capacity": 20, "location": 15}
    body["mandatory_criteria"] = [*opp["mandatory_criteria"], {"rule_type": "run_python", "params": {}}]
    assert client.put(f"/api/opportunities/{opp_id}", headers=BUYER, json=body).status_code == 422
    stored = client.get(f"/api/opportunities/{opp_id}", headers=BUYER).json()
    assert stored["weights"] == {"capability": 40, "experience": 25, "capacity": 20, "location": 15}


def test_cached_mode_upload_of_unknown_pdf_is_409(client):
    r = client.post(
        "/api/sme/me/documents",
        headers=THUTO,
        files=[("files", ("Unknown.pdf", unknown_pdf(), "application/pdf"))],
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "No cached AI result for this document. An admin can switch AI mode to Live."
    assert client.get("/api/sme/me", headers=THUTO).json()["documents"] == []


def test_live_mode_needs_aws_credentials(client, monkeypatch):
    monkeypatch.setattr(gateway, "live_available", lambda: False)
    r = client.put("/api/settings/ai-mode", headers=ADMIN, json={"mode": "live"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Live mode requires AWS credentials for Bedrock"
    mode = client.get("/api/settings/ai-mode", headers=BUYER).json()
    assert mode["mode"] == "cached" and mode["live_available"] is False
    assert mode["live_unavailable_reason"] == "Live mode requires AWS credentials for Bedrock"
    audit = client.get("/api/audit", headers=ADMIN).json()["entries"]
    assert "ai_mode_change" not in [e["action"] for e in audit]

    r = client.put("/api/settings/ai-mode", headers=ADMIN, json={"mode": "cached"})
    assert r.status_code == 200
    change = client.get("/api/audit", headers=ADMIN).json()["entries"][-1]
    assert change["action"] == "ai_mode_change" and change["actor_label"] == "YES Admin"
