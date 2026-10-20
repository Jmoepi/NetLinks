"""Demo script section 2 walked end to end over HTTP (cached AI mode, real engine on the seed)."""

from api_helpers import ADMIN, BUYER, THUTO_FILES, as_sme, asset, pdf_files

THUTO = as_sme("thuto")
ZOLA = as_sme("zola")
LERATO = as_sme("lerato")
OVERRIDE_REASON = "strongest Microsoft 365 references from comparable clients"
RENEWED_PI_ACTION = "Upload a renewed PI insurance schedule covering the contract start date."
EXTRACTED_FIELDS = [
    "services_description",
    "service_regions",
    "technician_count",
    "certifications",
    "years_trading",
    "past_clients",
    "service_desk_hours",
    "pi_cover_amount",
    "pi_expiry_date",
    "tax_expiry_date",
]


def slugs(group: list[dict]) -> list[str]:
    return [r["sme"]["slug"] for r in group]


def result_for(run: dict, slug: str) -> dict:
    return next(r for g in run["groups"].values() for r in g if r["sme"]["slug"] == slug)


def check(result: dict, rule: str) -> dict:
    return next(c for c in result["checks"] if c["rule"] == rule)


def test_demo_script_flow(client, opp_id):
    # --- 1:15-3:15 SME Thuto: upload -> extract -> confirm -------------------------------------
    r = client.post("/api/sme/me/documents", headers=THUTO, files=pdf_files(*THUTO_FILES))
    assert r.status_code == 200, r.text
    assert [d["filename"] for d in r.json()["documents"]] == THUTO_FILES

    profile = client.get("/api/sme/me/profile", headers=THUTO).json()
    fields = {f["field_key"]: f for f in profile["fields"]}
    for key in EXTRACTED_FIELDS:
        f = fields[key]
        assert f["badge"] == "AI-extracted", key
        assert f["selected"]["document_id"] and f["selected"]["span_start"] is not None, key
    assert fields["technician_count"]["value"] == 9
    pi = fields["pi_cover_amount"]
    assert pi["low_confidence"] is True and pi["value"] == 2000000
    assert profile["low_confidence"] == ["pi_cover_amount"]

    # "View source" highlights the sentence in the document text.
    sel = pi["selected"]
    doc = client.get(f"/api/documents/{sel['document_id']}/text", headers=THUTO).json()
    assert (
        "R2 mil professional liability" in doc["pages"][sel["page"] - 1][sel["span_start"] : sel["span_end"]]
    )

    r = client.post("/api/sme/me/profile/fields/pi_cover_amount/confirm", headers=THUTO)
    assert r.status_code == 200, r.text
    assert r.json()["value"] == 2000000 and r.json()["badge"] == "SME-confirmed"
    assert r.json()["low_confidence"] is False

    r = client.patch(
        "/api/sme/me/profile/fields/technician_count",
        headers=THUTO,
        json={"value": 11, "note": "Two new hires"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["value"] == 11 and r.json()["source_type"] == "sme_confirmed"
    assert r.json()["badge"] == "SME-confirmed"

    r = client.post("/api/sme/me/consent", headers=THUTO, json={"granted": True})
    assert r.status_code == 200 and r.json()["consent_status"] == "granted"

    # --- 3:15-4:30 Buyer: structure the RFQ, raise PI to R2m, weights visible -------------------
    opps = client.get("/api/opportunities", headers=BUYER).json()
    assert [o["buyer_org"] for o in opps] == ["Ubuntu Office Parks (fictional)"]
    s = client.post(
        f"/api/opportunities/{opp_id}/structure-rfq",
        headers=BUYER,
        json={"raw_text": asset("Ubuntu_Office_Parks_RFQ_raw.txt").decode("utf-8")},
    )
    assert s.status_code == 200, s.text
    proposal = s.json()["proposal"]
    assert s.json()["cache_hit"] is True and s.json()["generated_by"]
    pi_rule = next(c for c in proposal["mandatory_criteria"] if c["rule_type"] == "pi_insurance")
    assert pi_rule["params"]["min_amount"] == 1000000

    mandatory = [
        {**c, "params": {"min_amount": 2000000}} if c["rule_type"] == "pi_insurance" else c
        for c in proposal["mandatory_criteria"]
    ]
    weights = client.get(f"/api/opportunities/{opp_id}", headers=BUYER).json()["weights"]
    assert weights == {"capability": 40, "experience": 25, "capacity": 20, "location": 15}
    r = client.put(
        f"/api/opportunities/{opp_id}",
        headers=BUYER,
        json={
            "mandatory_criteria": mandatory,
            "preferred_criteria": proposal["preferred_criteria"],
            "weights": weights,
            "proposal_ai_result_id": s.json()["ai_result_id"],
        },
    )
    assert r.status_code == 200, r.text
    saved_pi = next(c for c in r.json()["mandatory_criteria"] if c["rule_type"] == "pi_insurance")
    assert saved_pi["params"]["min_amount"] == 2000000
    assert r.json()["weights"] == weights
    assert r.json()["id"] == opp_id and len(client.get("/api/opportunities", headers=BUYER).json()) == 1

    # --- 4:30-6:45 Matching & explainable shortlist ---------------------------------------------
    r = client.post(f"/api/opportunities/{opp_id}/match-runs", headers=BUYER)
    assert r.status_code == 200, r.text
    run = r.json()
    assert {k: run["run"]["counts"][k] for k in ("eligible", "needs_review", "not_eligible")} == {
        "eligible": 2,
        "needs_review": 2,
        "not_eligible": 1,
    }
    assert slugs(run["groups"]["eligible"]) == ["thuto", "mmapula"]
    assert [x["rank"] for x in run["groups"]["eligible"]] == [1, 2]
    assert set(slugs(run["groups"]["needs_review"])) == {"zola", "brightpath"}
    assert slugs(run["groups"]["not_eligible"]) == ["lerato"]
    thuto = result_for(run, "thuto")
    assert all(c["outcome"] == "pass" for c in thuto["checks"] if c["group"] == "mandatory")
    assert {c["name"] for c in thuto["components"]} == {"capability", "experience", "capacity", "location"}
    assert (
        "6 technicians vs 8 preferred"
        in next(c for c in result_for(run, "mmapula")["components"] if c["name"] == "capacity")["explanation"]
    )
    assert (
        check(result_for(run, "zola"), "pi_insurance")["reason"]
        == "Professional indemnity cover expires 10 days before the closing date."
    )
    assert (
        check(result_for(run, "brightpath"), "data_consistency")["reason"]
        == "Technician count conflict: SME profile form 15, capability statement 4."
    )
    assert (
        check(result_for(run, "lerato"), "operating_region")["reason"]
        == "No Gauteng service region (confirmed: Western Cape only)."
    )
    assert result_for(run, "zola")["provisional"] is True and result_for(run, "zola")["rank"] is None

    # --- 6:45-7:45 Buyer decision & audit trail -------------------------------------------------
    for slug in ("thuto", "mmapula"):
        r = client.post(f"/api/opportunities/{opp_id}/shortlist", headers=BUYER, json={"sme_slug": slug})
        assert r.status_code == 200, r.text
    assert [e["sme_slug"] for e in r.json()["shortlist"]] == ["thuto", "mmapula"]

    r = client.post(
        f"/api/opportunities/{opp_id}/info-requests",
        headers=BUYER,
        json={
            "sme_slug": "zola",
            "kind": "information",
            "message": "Please upload your renewed professional indemnity schedule.",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["awaiting_sme"] is True and r.json()["status"] == "open"
    r = client.post(
        f"/api/opportunities/{opp_id}/info-requests",
        headers=BUYER,
        json={
            "sme_slug": "brightpath",
            "kind": "clarification",
            "message": "Please confirm your technician count: profile form 15, capability statement 4.",
        },
    )
    assert r.status_code == 200, r.text
    latest = client.get(f"/api/opportunities/{opp_id}/match-runs/latest", headers=BUYER).json()
    assert result_for(latest, "zola")["awaiting_sme"] is True
    assert result_for(latest, "zola")["info_requests"][0]["kind"] == "information"

    r = client.put(
        f"/api/opportunities/{opp_id}/shortlist/order",
        headers=BUYER,
        json={"sme_slugs": ["mmapula", "thuto"], "reason": OVERRIDE_REASON},
    )
    assert r.status_code == 200, r.text
    shortlist = r.json()["shortlist"]
    assert [(e["sme_slug"], e["position"], e["engine_rank"]) for e in shortlist] == [
        ("mmapula", 1, 2),
        ("thuto", 2, 1),
    ]
    latest = client.get(f"/api/opportunities/{opp_id}/match-runs/latest", headers=BUYER).json()
    assert [x["rank"] for x in latest["groups"]["eligible"]] == [1, 2]  # engine ranks untouched
    assert slugs(latest["groups"]["eligible"]) == ["thuto", "mmapula"]

    # --- 7:45-8:30 SME readiness view ----------------------------------------------------------
    readiness = client.get("/api/sme/me/readiness", headers=ZOLA).json()
    assert [q["message"] for q in readiness["requests"]] == [
        "Please upload your renewed professional indemnity schedule."
    ]
    zola_opp = readiness["opportunities"][0]
    assert zola_opp["status"] == "needs_review" and zola_opp["awaiting_sme"] is True
    assert RENEWED_PI_ACTION in [a["text"] for a in zola_opp["actions"]]

    r = client.post(
        "/api/sme/me/documents", headers=ZOLA, files=pdf_files("Zola_PI_Insurance_Schedule_Renewed.pdf")
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["responded_info_request_ids"]) == 1
    rerun = client.post(f"/api/opportunities/{opp_id}/match-runs", headers=BUYER).json()
    assert result_for(rerun, "zola")["status"] == "eligible"
    assert slugs(rerun["groups"]["eligible"]) == ["thuto", "mmapula", "zola"]
    assert result_for(rerun, "zola")["awaiting_sme"] is False
    readiness = client.get("/api/sme/me/readiness", headers=ZOLA).json()
    assert readiness["requests"][0]["status"] == "responded"
    assert readiness["opportunities"][0]["status"] == "eligible"

    lerato = client.get("/api/sme/me/readiness", headers=LERATO).json()["opportunities"][0]
    assert lerato["status"] == "not_eligible"
    assert "This opportunity requires Gauteng operations." in [a["text"] for a in lerato["actions"]]

    # --- 8:30-9:15 YES dashboard ---------------------------------------------------------------
    r = client.get("/api/admin/dashboard", headers=ADMIN)
    assert r.status_code == 200, r.text
    dash = r.json()
    pipeline = next(p for p in dash["pipeline"] if p["opportunity_id"] == opp_id)
    assert pipeline["run_count"] == 2
    assert (pipeline["before"]["counts"]["eligible"], pipeline["before"]["counts"]["needs_review"]) == (2, 2)
    assert (pipeline["after"]["counts"]["eligible"], pipeline["after"]["counts"]["needs_review"]) == (3, 1)
    assert pipeline["after"]["counts"]["not_eligible"] == 1
    gaps = {g["label"]: g for g in dash["readiness_gaps"]}
    assert {"Expiring insurance", "Conflicting capacity data", "Regional coverage"} <= gaps.keys()
    assert gaps["Expiring insurance"]["open"] == 0  # fixed by Zola's renewal
    assert {s["label"] for s in dash["requested_skills"][:3]} == {
        "Microsoft 365",
        "Service desk",
        "Device management",
    }
    assert dash["decisions"]["overrides"]["count"] == 1
    assert dash["decisions"]["overrides"]["items"][0]["reason"] == OVERRIDE_REASON
    assert dash["decisions"]["shortlisted"] == 2
    fairness = dash["fairness"]
    assert fairness["small_sample"] is True and fairness["total"] == 5
    assert {row["group"] for row in fairness["by_province"]} == {"GP", "WC"}
    assert {row["group"] for row in fairness["by_size_band"]} == {"micro", "small"}

    # --- Audit log: every step timestamped and attributed to a role -----------------------------
    r = client.get("/api/audit", headers=BUYER, params={"opportunity_id": opp_id})
    assert r.status_code == 200, r.text
    entries = r.json()["entries"]
    for entry in entries:
        assert entry["actor_role"] and entry["actor_label"] and entry["at"]
    actions = [e["action"] for e in entries]
    for action in (
        "extraction",
        "sme_correction",
        "sme_confirmation",
        "consent",
        "requirement_edit",
        "match_run",
        "info_request",
        "info_request_responded",
        "shortlist_decision",
        "override",
    ):
        assert action in actions, action
    thuto_correction = next(e for e in entries if e["action"] == "sme_correction")
    assert thuto_correction["actor_role"] == "sme"
    assert thuto_correction["actor_label"] == "SME: Thuto Tech Solutions"
    assert thuto_correction["details"]["new"] == 11
    edit = next(e for e in entries if e["action"] == "requirement_edit")
    assert edit["actor_role"] == "buyer" and edit["actor_label"] == "Buyer: Naledi (Ubuntu Office Parks)"
    assert [
        (c["rule_type"], c["param"], c["from"], c["to"]) for c in edit["details"]["changes_vs_proposal"]
    ] == [("pi_insurance", "min_amount", 1000000, 2000000)]
    override = next(e for e in entries if e["action"] == "override")
    assert override["reason"] == OVERRIDE_REASON and override["actor_role"] == "buyer"
    assert override["details"]["to"] == ["mmapula", "thuto"]
    assert override["details"]["engine_ranking"] == ["thuto", "mmapula"]

    # Order follows the script: extraction -> correction -> consent -> edit -> run -> request -> override.
    def first_by_sme(action: str) -> int:
        return next(i for i, e in enumerate(entries) if e["action"] == action and e["actor_role"] == "sme")

    sequence = [
        first_by_sme("extraction"),
        first_by_sme("sme_correction"),
        first_by_sme("consent"),
        *(actions.index(a) for a in ("requirement_edit", "match_run", "info_request", "override")),
    ]
    assert sequence == sorted(sequence)

    # --- Reset demo restores the seed -----------------------------------------------------------
    r = client.post("/api/admin/reset", headers=ADMIN)
    assert r.status_code == 200, r.text
    me = client.get("/api/sme/me", headers=THUTO).json()
    assert me["documents"] == [] and me["consent_status"] == "pending"
    assert client.get(f"/api/opportunities/{opp_id}/match-runs/latest", headers=BUYER).json()["run"] is None
    assert client.get("/api/settings/ai-mode", headers=ADMIN).json()["mode"] == "cached"
    admin_audit = client.get("/api/audit", headers=ADMIN).json()["entries"]
    assert admin_audit[-1]["action"] == "demo_reset" and admin_audit[-1]["actor_label"] == "YES Admin"
    assert "override" not in [e["action"] for e in admin_audit]
