"""Demo seed and reset (plan A14).

Seed facts come from the demo documents through the real ingestion pipeline in cached mode;
seed_data.json only holds non-document facts (accounts, form entries, consent, opportunities).
Neither seed() nor reset() commits: the caller owns the transaction.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai import gateway
from app.audit import ActorLike, SystemActor, write_audit
from app.config import get_settings
from app.db import Base
from app.ingestion import lineage
from app.ingestion.pipeline import ingest_document
from app.models import SME, Opportunity

SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "seed_data.json"


@lru_cache
def load_seed_data() -> dict[str, Any]:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def _seed_actor(sme_name: str | None = None) -> SystemActor:
    return SystemActor(label=f"Demo seed (on behalf of SME: {sme_name})" if sme_name else "Demo seed")


def seed(session: Session) -> dict[str, int]:
    data = load_seed_data()
    settings = get_settings()
    assets = Path(settings.demo_assets_dir)
    excluded = set(data["exclude_documents"])
    smes: dict[str, SME] = {}
    doc_count = 0

    for spec in data["smes"]:
        sme = SME(
            slug=spec["slug"], name=spec["name"], base_town=spec["base_town"], province=spec["province"],
            lat=spec["lat"], lon=spec["lon"], size_band=spec["size_band"], employees=spec["employees"],
            consent_status="pending",
        )
        session.add(sme)
        session.flush()
        smes[spec["slug"]] = sme
        if spec["preseed_documents"]:
            actor = _seed_actor(sme.name)
            for pdf in sorted(assets.glob(f"{spec['doc_prefix']}_*.pdf")):
                if pdf.name in excluded:
                    continue
                ingest_document(session, sme, pdf.name, pdf.read_bytes(), actor, mode="cached")
                doc_count += 1

    for conf in data["confirmations"]:
        sme = smes[conf["sme"]]
        actor = _seed_actor(sme.name)
        if conf["mode"] == "form":
            row = lineage.add_candidate(
                session, sme.id, conf["field_key"], conf["value"], "sme_confirmed",
                source_label=conf["source_label"], confidence=lineage.SME_CONFIRMED_CONFIDENCE,
                created_by_role="sme", note=conf.get("note"),
            )
            write_audit(session, actor.role, actor.label, "sme_profile_entry", "profile_field", row.id,
                        {"sme_id": sme.id, "field_key": conf["field_key"], "value": conf["value"],
                         "source_label": conf["source_label"], "seeded": True})
        else:
            row = lineage.confirm_field(session, sme.id, conf["field_key"], actor)
            if lineage.normalize_value(row.value) != lineage.normalize_value(conf["value"]):
                raise RuntimeError(
                    f"Seed confirmation mismatch for {conf['sme']}.{conf['field_key']}: "
                    f"document says {row.value!r}, seed expects {conf['value']!r}"
                )

    now = datetime.now(UTC)
    for spec in data["smes"]:
        if spec["consent"] == "granted":
            sme = smes[spec["slug"]]
            sme.consent_status = "granted"
            sme.consent_at = now
            actor = _seed_actor(sme.name)
            write_audit(session, actor.role, actor.label, "consent", "sme", sme.id,
                        {"granted": True, "seeded": True})

    embedding_count = 0
    for sme in smes.values():
        description = lineage.resolve_field(session, sme.id, "services_description")
        if description["value"]:
            gateway.embed_and_store(session, "sme", sme.id, description["value"], mode="cached")
            embedding_count += 1

    opp_count = 0
    for spec in data["opportunities"]:
        raw = (assets / spec["raw_rfq_file"]).read_text(encoding="utf-8") if spec["raw_rfq_file"] else None
        opp = Opportunity(
            buyer_org=spec["buyer_org"], buyer_contact=spec["buyer_contact"], title=spec["title"],
            description=spec["description"], raw_rfq_text=raw,
            closing_date=date.fromisoformat(spec["closing_date"]),
            contract_start=date.fromisoformat(spec["contract_start"]),
            status=spec["status"], weights=dict(spec["weights"]),
            mandatory_criteria=spec["mandatory_criteria"], preferred_criteria=spec["preferred_criteria"],
            capability_text=spec["capability_text"],
        )
        session.add(opp)
        session.flush()
        opp_count += 1
        if opp.status == "published" and opp.capability_text:
            gateway.embed_and_store(session, "opportunity", opp.id, opp.capability_text, mode="cached")
            embedding_count += 1

    session.flush()
    return {"smes": len(smes), "documents": doc_count, "embeddings": embedding_count,
            "opportunities": opp_count}


def clear_uploads() -> None:
    """Delete everything under UPLOAD_DIR (local storage only; the directory itself is a volume)."""
    settings = get_settings()
    if settings.storage_backend != "local":
        return
    root = Path(settings.upload_dir)
    if not root.is_dir():
        return
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def reset(session: Session, actor: ActorLike | None = None) -> dict[str, int]:
    """Truncate everything, clear uploads, reseed, force cached AI mode, audit demo_reset."""
    actor = actor or SystemActor(label="Demo reset")
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    clear_uploads()
    gateway.set_mode(session, "cached")
    counts = seed(session)
    write_audit(session, actor.role, actor.label, "demo_reset", "demo", None, {"seeded": counts})
    session.flush()
    return counts


def is_seeded(session: Session) -> bool:
    return session.scalar(select(SME.id).limit(1)) is not None
