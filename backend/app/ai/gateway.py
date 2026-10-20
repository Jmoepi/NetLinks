"""AI gateway (plan A8): cached vs live mode, deterministic post-checks, ai_results recording.

Cached mode: read the committed ai-cache/ files; a miss raises CacheMiss.
Live mode: call Bedrock if available, else raise LiveUnavailable. Live results are recorded in
ai_results but never written to the committed cache.
The same post-checks run on every provider's output so Cached and Live behave the same.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai import cache, prompts
from app.ai.providers.base import AIProvider
from app.ai.providers.local_fallback import LOCAL_EMBEDDING_MODEL_ID
from app.models import AIResult, AppSetting, Embedding

MODES = ("cached", "live")
LOW_CONFIDENCE_CAP = 0.5


class CacheMiss(Exception):
    """Cached mode and no cache file exists for this input."""


class LiveUnavailable(Exception):
    """Live mode requested but Bedrock is not available (no credentials or model IDs)."""


@dataclass
class AIOutcome:
    kind: str
    input_sha256: str
    provider: str
    model_id: str
    generated_by: str
    generated_at: datetime
    cache_hit: bool
    prompt_version: str
    result: dict[str, Any]


# ---------------------------------------------------------------------------
# Mode + providers
# ---------------------------------------------------------------------------


def get_mode(session: Session) -> str:
    setting = session.get(AppSetting, "ai_mode")
    return setting.value if setting and setting.value in MODES else "cached"


def set_mode(session: Session, mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"Unknown AI mode: {mode!r}")
    setting = session.get(AppSetting, "ai_mode")
    if setting is None:
        session.add(AppSetting(key="ai_mode", value=mode))
    else:
        setting.value = mode
    session.flush()


def bedrock_provider() -> AIProvider:
    from app.ai.providers.bedrock import BedrockProvider

    return BedrockProvider()


def live_available() -> bool:
    return bedrock_provider().available()


def _live_provider() -> AIProvider:
    provider = bedrock_provider()
    if not provider.available():
        raise LiveUnavailable(
            "Live AI mode needs Amazon Bedrock credentials and model IDs; none are configured."
        )
    return provider


# ---------------------------------------------------------------------------
# Deterministic post-checks
# ---------------------------------------------------------------------------

# Canonical rand amounts: R2,000,000 / R2 000 000 / R2000000 / R2 million / R2m.
_CANONICAL_AMOUNT = re.compile(
    r"R\s?(?:\d{1,3}(?:[ ,]\d{3})+|\d{4,})(?![\d,])|R\s?\d+(?:\.\d+)?\s?(?:million|m)\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalized_with_map(text: str) -> tuple[str, list[int]]:
    """Lower-cased text with whitespace runs collapsed to one space, plus a map to raw offsets."""
    out: list[str] = []
    index: list[int] = []
    prev_space = True  # drop leading whitespace
    for i, ch in enumerate(text):
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                index.append(i)
            prev_space = True
            continue
        low = ch.lower()
        out.append(low if len(low) == 1 else ch)
        index.append(i)
        prev_space = False
    return "".join(out), index


def locate_quote(pages: list[str], quote: str, page_hint: int | None = None) -> tuple[int, int, int] | None:
    """Find quote in page text (whitespace-normalised, case-insensitive).

    Returns (page 1-based, span_start, span_end) as offsets into the raw page text, or None.
    """
    needle, _ = _normalized_with_map(quote or "")
    needle = needle.strip()
    if not needle:
        return None
    order = list(range(len(pages)))
    if page_hint and 1 <= page_hint <= len(pages):
        order.remove(page_hint - 1)
        order.insert(0, page_hint - 1)
    for p in order:
        hay, index = _normalized_with_map(pages[p])
        pos = hay.find(needle)
        if pos >= 0:
            return p + 1, index[pos], index[pos + len(needle) - 1] + 1
    return None


def _clamp_confidence(value: Any) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, conf))


def postcheck_extraction(result: dict[str, Any], pages: list[str]) -> dict[str, Any]:
    """Validate shape, compute spans, cap confidence for unlocated quotes and informal amounts."""
    out = copy.deepcopy(result) if isinstance(result, dict) else {}
    if out.get("doc_type") not in prompts.DOC_TYPES:
        out["doc_type"] = "other"
    for key in ("issue_date", "period_end"):
        value = out.get(key)
        out[key] = value if isinstance(value, str) and _ISO_DATE.match(value) else None

    fields: list[dict[str, Any]] = []
    for raw in out.get("fields") or []:
        if not isinstance(raw, dict) or raw.get("field_key") not in prompts.FIELD_KEYS:
            continue
        field = dict(raw)
        quote = field.get("quote") if isinstance(field.get("quote"), str) else ""
        field["quote"] = quote
        confidence = _clamp_confidence(field.get("confidence"))
        hint = field.get("page") if isinstance(field.get("page"), int) else None
        found = locate_quote(pages, quote, hint)
        if found:
            field["page"], field["span_start"], field["span_end"] = found
        else:
            field["page"], field["span_start"], field["span_end"] = None, None, None
            confidence = min(confidence, LOW_CONFIDENCE_CAP)
        if field["field_key"] in prompts.MONEY_FIELDS and not _CANONICAL_AMOUNT.search(quote):
            confidence = min(confidence, LOW_CONFIDENCE_CAP)
        field["confidence"] = round(confidence, 4)
        fields.append(field)
    out["fields"] = fields
    return out


def postcheck_rfq(result: dict[str, Any]) -> dict[str, Any]:
    """Keep only catalog rule types (no free-form rules ever reach the engine)."""
    out = copy.deepcopy(result) if isinstance(result, dict) else {}
    for key, catalog in (
        ("mandatory_criteria", prompts.MANDATORY_RULE_TYPES),
        ("preferred_criteria", prompts.PREFERRED_RULE_TYPES),
    ):
        kept = []
        for c in out.get(key) or []:
            if isinstance(c, dict) and c.get("rule_type") in catalog:
                params = c.get("params")
                kept.append({
                    "rule_type": c["rule_type"],
                    "params": params if isinstance(params, dict) else {},
                    "source_quote": c.get("source_quote") or "",
                })
        out[key] = kept
    out["title"] = out.get("title") or ""
    closing = out.get("closing_date")
    out["closing_date"] = closing if isinstance(closing, str) and _ISO_DATE.match(closing) else None
    out["capability_text"] = out.get("capability_text") or ""
    return out


# ---------------------------------------------------------------------------
# Pure gateway calls (no DB): used by the DB-recording wrappers and unit tests
# ---------------------------------------------------------------------------


def _from_cache(kind: str, key: str) -> AIOutcome:
    record = cache.read(kind, key)
    if record is None:
        raise CacheMiss(f"No cached AI result for this {kind.replace('_', ' ')} input ({key[:12]}...).")
    return AIOutcome(
        kind=kind,
        input_sha256=key,
        provider=record["provider"],
        model_id=record["model_id"],
        generated_by=record["generated_by"],
        generated_at=datetime.fromisoformat(record["generated_at"]),
        cache_hit=True,
        prompt_version=record.get("prompt_version", ""),
        result=record["result"],
    )


def _live(kind: str, key: str, provider: AIProvider, model_id: str, version: str, result: Any) -> AIOutcome:
    return AIOutcome(
        kind=kind,
        input_sha256=key,
        provider=provider.name,
        model_id=model_id,
        generated_by=provider.generated_by,
        generated_at=datetime.now(UTC),
        cache_hit=False,
        prompt_version=version,
        result=result,
    )


def run_extraction(pages: list[str], filename: str, file_sha256: str, mode: str) -> AIOutcome:
    if mode == "live":
        provider = _live_provider()
        raw = provider.extract_document(pages, filename)
        outcome = _live("extraction", file_sha256, provider, provider.extraction_model_id,
                        prompts.EXTRACTION_PROMPT_VERSION, raw)
    else:
        outcome = _from_cache("extraction", file_sha256)
    outcome.result = postcheck_extraction(outcome.result, pages)
    return outcome


def run_rfq(text: str, mode: str) -> AIOutcome:
    key = cache.rfq_key(text)
    if mode == "live":
        provider = _live_provider()
        raw = provider.structure_rfq(cache.normalize_rfq_text(text))
        outcome = _live("rfq_structuring", key, provider, provider.extraction_model_id,
                        prompts.RFQ_PROMPT_VERSION, raw)
    else:
        outcome = _from_cache("rfq_structuring", key)
    outcome.result = postcheck_rfq(outcome.result)
    return outcome


def cached_embedding_model_ids() -> list[str]:
    """Embedding models looked up in cached mode, Bedrock first (a Bedrock-regenerated cache wins)."""
    return [bedrock_provider().embedding_model_id, LOCAL_EMBEDDING_MODEL_ID]


def run_embedding(text: str, mode: str) -> AIOutcome:
    if mode == "live":
        provider = _live_provider()
        key = cache.embedding_key(provider.embedding_model_id, text)
        vector = provider.embed(text)
        return _live("embedding", key, provider, provider.embedding_model_id,
                     prompts.EMBEDDING_PROMPT_VERSION, {"text": text, "vector": vector})
    for model_id in cached_embedding_model_ids():
        key = cache.embedding_key(model_id, text)
        if cache.read("embedding", key) is not None:
            return _from_cache("embedding", key)
    raise CacheMiss("No cached embedding for this text.")


# ---------------------------------------------------------------------------
# DB-recording wrappers: every AI result actually used is written to ai_results
# ---------------------------------------------------------------------------


def _record(session: Session, outcome: AIOutcome, document_id: int | None = None) -> AIResult:
    row = AIResult(
        kind=outcome.kind,
        input_sha256=outcome.input_sha256,
        document_id=document_id,
        provider=outcome.provider,
        model_id=outcome.model_id,
        generated_by=outcome.generated_by,
        generated_at=outcome.generated_at,
        cache_hit=outcome.cache_hit,
        result=outcome.result,
    )
    session.add(row)
    session.flush()
    return row


def extract_document(
    session: Session,
    pages: list[str],
    filename: str,
    file_sha256: str,
    document_id: int | None = None,
    mode: str | None = None,
) -> tuple[AIOutcome, AIResult]:
    outcome = run_extraction(pages, filename, file_sha256, mode or get_mode(session))
    return outcome, _record(session, outcome, document_id)


def structure_rfq(session: Session, text: str, mode: str | None = None) -> tuple[AIOutcome, AIResult]:
    outcome = run_rfq(text, mode or get_mode(session))
    return outcome, _record(session, outcome)


def embed(session: Session, text: str, mode: str | None = None) -> tuple[AIOutcome, AIResult]:
    outcome = run_embedding(text, mode or get_mode(session))
    return outcome, _record(session, outcome)


def embed_and_store(
    session: Session, owner_type: str, owner_id: int, text: str, mode: str | None = None
) -> Embedding:
    """Embed text and store it in the embeddings table, replacing older rows for the same owner+model."""
    outcome, _ = embed(session, text, mode)
    text_sha = cache.sha256_hex(text.encode("utf-8"))
    session.query(Embedding).filter_by(
        owner_type=owner_type, owner_id=owner_id, model_id=outcome.model_id
    ).delete()
    row = Embedding(
        owner_type=owner_type,
        owner_id=owner_id,
        text_sha256=text_sha,
        provider=outcome.provider,
        model_id=outcome.model_id,
        generated_by=outcome.generated_by,
        vector=outcome.result["vector"],
    )
    session.add(row)
    session.flush()
    return row
