"""Committed ai-cache/ integrity and gateway mode behaviour."""

import hashlib
import json
from pathlib import Path

import pytest

from app.ai import cache, gateway
from app.ai.providers.local_fallback import LOCAL_GENERATED_BY
from app.config import get_settings
from app.ingestion.pdf_text import extract_pages

CACHE = Path(get_settings().ai_cache_dir)
ASSETS = Path(get_settings().demo_assets_dir)


def committed_records() -> list[tuple[Path, dict]]:
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(CACHE.glob("*/*.json"))]


def test_cache_is_not_empty():
    kinds = {r["kind"] for _, r in committed_records()}
    assert kinds == {"extraction", "rfq_structuring", "embedding"}


def test_every_record_carries_provenance():
    for path, record in committed_records():
        for key in cache.RECORD_KEYS:
            assert key in record, f"{path.name} lacks {key}"
        assert record["provider"] and record["model_id"] and record["generated_by"] and record["generated_at"]
        assert record["cache_key"] == path.stem
        assert path.parent.name == cache.KIND_DIRS[record["kind"]]


def test_local_fallback_records_are_labelled_and_never_bedrock():
    for path, record in committed_records():
        if record["provider"] == "local-fallback":
            assert record["generated_by"] == LOCAL_GENERATED_BY, path.name
            assert record["model_id"] in ("local-rules-v1", "local-lexicon-v1"), path.name
        if record["generated_by"] == "bedrock" or record["provider"] == "bedrock":
            assert record["provider"] == "bedrock" and record["generated_by"] == "bedrock", path.name
            assert not record["model_id"].startswith("local-"), path.name


def test_one_extraction_file_per_demo_pdf_keyed_by_sha256():
    pdfs = sorted(ASSETS.glob("*.pdf"))
    expected = {hashlib.sha256(p.read_bytes()).hexdigest(): p.name for p in pdfs}
    files = {p.stem: r for p, r in committed_records() if r["kind"] == "extraction"}
    assert set(files) == set(expected)
    for key, record in files.items():
        assert record["input_ref"] == expected[key]


def test_rfq_cache_keyed_by_raw_rfq_text():
    text = (ASSETS / "Ubuntu_Office_Parks_RFQ_raw.txt").read_text(encoding="utf-8")
    assert cache.read("rfq_structuring", cache.rfq_key(text)) is not None
    assert cache.rfq_key(text.replace("\n", "\r\n")) == cache.rfq_key(text)


def test_cached_hit_returns_provenance():
    data = (ASSETS / "Mmapula_Capability_Statement.pdf").read_bytes()
    outcome = gateway.run_extraction(extract_pages(data), "x.pdf", cache.extraction_key(data), "cached")
    assert outcome.cache_hit is True
    assert outcome.generated_by and outcome.model_id and outcome.generated_at


def test_cached_mode_miss_raises_cache_miss():
    with pytest.raises(gateway.CacheMiss):
        gateway.run_extraction(["unknown"], "unknown.pdf", "0" * 64, "cached")
    with pytest.raises(gateway.CacheMiss):
        gateway.run_rfq("An RFQ nobody has structured yet.", "cached")
    with pytest.raises(gateway.CacheMiss):
        gateway.run_embedding("text with no cached embedding", "cached")


def test_live_mode_without_credentials_raises_live_unavailable():
    assert gateway.live_available() is False
    with pytest.raises(gateway.LiveUnavailable):
        gateway.run_extraction(["text"], "a.pdf", "0" * 64, "live")
    with pytest.raises(gateway.LiveUnavailable):
        gateway.run_rfq("text", "live")
    with pytest.raises(gateway.LiveUnavailable):
        gateway.run_embedding("text", "live")


def test_cache_write_is_deterministic_except_generated_at(tmp_path):
    kwargs = dict(input_ref="r", provider="local-fallback", model_id="m", generated_by="g",
                  prompt_version="v", result={"b": 1, "a": [1, 2]}, root=tmp_path)
    cache.write("rfq_structuring", "k", **kwargs)
    first = json.loads(cache.cache_path("rfq_structuring", "k", tmp_path).read_text())
    cache.write("rfq_structuring", "k", **kwargs)
    second = json.loads(cache.cache_path("rfq_structuring", "k", tmp_path).read_text())
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second
