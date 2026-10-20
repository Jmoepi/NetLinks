"""Command line tools.

    python -m app.cli regenerate-cache --provider {bedrock,local-fallback}

Runs the real extraction (pypdf text + provider + gateway post-checks) on every demo-assets PDF,
structures the raw RFQ and embeds every SME services description plus the opportunity capability
text, then rewrites ai-cache/. Files not produced by this run are removed so the cache always
reflects exactly one provider. Output is deterministic apart from generated_at.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.ai import cache, gateway, prompts
from app.ai.providers import PROVIDER_NAMES, get_provider
from app.config import get_settings
from app.ingestion.pdf_text import extract_pages
from app.services.seed import load_seed_data

RFQ_FILENAME = "Ubuntu_Office_Parks_RFQ_raw.txt"


def regenerate_cache(provider_name: str, assets_dir: Path, cache_dir: Path) -> dict[str, int]:
    provider = get_provider(provider_name)
    if not provider.available():
        raise SystemExit(
            f"Provider {provider_name!r} is not available (Bedrock needs AWS credentials, "
            "BEDROCK_EXTRACTION_MODEL_ID and BEDROCK_EMBEDDING_MODEL_ID)."
        )
    written: dict[str, set[str]] = {kind: set() for kind in cache.KIND_DIRS}

    def write(kind: str, key: str, input_ref: str, model_id: str, version: str, result: object) -> None:
        cache.write(
            kind, key, input_ref=input_ref, provider=provider.name, model_id=model_id,
            generated_by=provider.generated_by, prompt_version=version, result=result, root=cache_dir,
        )
        written[kind].add(key)

    embed_texts: dict[str, str] = {}  # text -> input_ref

    for pdf in sorted(assets_dir.glob("*.pdf")):
        data = pdf.read_bytes()
        pages = extract_pages(data)
        result = gateway.postcheck_extraction(provider.extract_document(pages, pdf.name), pages)
        write("extraction", cache.extraction_key(data), pdf.name, provider.extraction_model_id,
              prompts.EXTRACTION_PROMPT_VERSION, result)
        if result["doc_type"] == "capability_statement":
            for field in result["fields"]:
                if field["field_key"] == "services_description" and field.get("value"):
                    embed_texts.setdefault(field["value"], f"{pdf.name}#services_description")

    rfq_text = (assets_dir / RFQ_FILENAME).read_text(encoding="utf-8")
    rfq_result = gateway.postcheck_rfq(provider.structure_rfq(cache.normalize_rfq_text(rfq_text)))
    write("rfq_structuring", cache.rfq_key(rfq_text), RFQ_FILENAME, provider.extraction_model_id,
          prompts.RFQ_PROMPT_VERSION, rfq_result)
    if rfq_result.get("capability_text"):
        embed_texts.setdefault(rfq_result["capability_text"], f"{RFQ_FILENAME}#capability_text")

    for opp in load_seed_data()["opportunities"]:
        if opp["status"] == "published" and opp.get("capability_text"):
            embed_texts.setdefault(opp["capability_text"], f"opportunity:{opp['key']}#capability_text")

    for text, ref in sorted(embed_texts.items()):
        write("embedding", cache.embedding_key(provider.embedding_model_id, text), ref,
              provider.embedding_model_id, prompts.EMBEDDING_PROMPT_VERSION,
              {"text": text, "vector": provider.embed(text)})

    for kind, dirname in cache.KIND_DIRS.items():
        for stale in (cache_dir / dirname).glob("*.json"):
            if stale.stem not in written[kind]:
                stale.unlink()

    return {kind: len(keys) for kind, keys in written.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    regen = sub.add_parser("regenerate-cache", help="Rebuild ai-cache/ from demo-assets/")
    regen.add_argument("--provider", choices=PROVIDER_NAMES, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.command == "regenerate-cache":
        counts = regenerate_cache(args.provider, Path(settings.demo_assets_dir), Path(settings.ai_cache_dir))
        provider = get_provider(args.provider)
        print(f"Provider: {provider.name} ({provider.generated_by})")
        for kind, n in counts.items():
            print(f"  {cache.KIND_DIRS[kind]}: {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
