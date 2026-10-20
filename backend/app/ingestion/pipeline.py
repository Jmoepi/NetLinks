"""Document ingestion (plan A9): text -> AI extraction -> storage -> document + field lineage -> audit."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.ai import cache, gateway
from app.audit import ActorLike, write_audit
from app.ingestion import lineage
from app.ingestion.pdf_text import extract_pages
from app.models import SME, Document
from app.storage import document_key, get_store, safe_filename


def _iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def ingest_document(
    session: Session,
    sme: SME,
    filename: str,
    data: bytes,
    actor: ActorLike,
    mode: str | None = None,
) -> Document:
    """Ingest one uploaded PDF for an SME. Flushes but does not commit (the caller owns the transaction).

    The AI call happens before anything is stored, so a CacheMiss/LiveUnavailable leaves no
    orphan file or document row. mode overrides app_settings.ai_mode (the seed forces "cached").
    """
    filename = safe_filename(filename)
    sha = cache.extraction_key(data)
    pages = extract_pages(data)
    outcome, ai_row = gateway.extract_document(session, pages, filename, sha, mode=mode)
    result = outcome.result

    key = get_store().put(document_key(sme.slug, sha, filename), data)
    doc = Document(
        sme_id=sme.id,
        filename=filename,
        sha256=sha,
        doc_type=result.get("doc_type"),
        issue_date=_iso_date(result.get("issue_date")),
        period_end=_iso_date(result.get("period_end")),
        storage_key=key,
        pages_text=pages,
        uploaded_by_role=actor.role,
    )
    session.add(doc)
    session.flush()
    ai_row.document_id = doc.id

    values = lineage.insert_extracted_fields(session, doc, result.get("fields", []), actor.role)
    superseded = lineage.apply_document_supersession(session, doc)

    write_audit(
        session, actor.role, actor.label, "extraction", "document", doc.id,
        {
            "sme_id": sme.id,
            "filename": filename,
            "sha256": sha,
            "doc_type": doc.doc_type,
            "provider": outcome.provider,
            "model_id": outcome.model_id,
            "generated_by": outcome.generated_by,
            "cache_hit": outcome.cache_hit,
            "ai_result_id": ai_row.id,
            "field_count": len(values),
            "superseded_document_ids": [d.id for d in superseded],
        },
    )
    session.flush()
    return doc
