"""File cache of AI results: AI_CACHE_DIR/{extraction,rfq,embeddings}/<sha256>.json (plan A8).

Keys: extraction = sha256(file bytes); rfq = sha256(RFQ text with LF line endings, stripped);
embeddings = sha256(model_id + text).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

# Cache directory name -> record kind (matches ai_results.kind).
KIND_DIRS: dict[str, str] = {
    "extraction": "extraction",
    "rfq_structuring": "rfq",
    "embedding": "embeddings",
}

RECORD_KEYS = (
    "cache_key",
    "kind",
    "input_ref",
    "provider",
    "model_id",
    "generated_by",
    "generated_at",
    "prompt_version",
    "result",
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extraction_key(file_bytes: bytes) -> str:
    return sha256_hex(file_bytes)


def normalize_rfq_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def rfq_key(text: str) -> str:
    return sha256_hex(normalize_rfq_text(text).encode("utf-8"))


def embedding_key(model_id: str, text: str) -> str:
    return sha256_hex((model_id + text).encode("utf-8"))


def cache_root() -> Path:
    return Path(get_settings().ai_cache_dir)


def cache_path(kind: str, key: str, root: Path | None = None) -> Path:
    return (root or cache_root()) / KIND_DIRS[kind] / f"{key}.json"


def read(kind: str, key: str, root: Path | None = None) -> dict[str, Any] | None:
    path = cache_path(kind, key, root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write(
    kind: str,
    key: str,
    *,
    input_ref: str,
    provider: str,
    model_id: str,
    generated_by: str,
    prompt_version: str,
    result: Any,
    generated_at: datetime | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    record = {
        "cache_key": key,
        "kind": kind,
        "input_ref": input_ref,
        "provider": provider,
        "model_id": model_id,
        "generated_by": generated_by,
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "prompt_version": prompt_version,
        "result": result,
    }
    path = cache_path(kind, key, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sorted keys, LF endings, trailing newline: byte-identical apart from generated_at.
    payload = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_bytes(payload.encode("utf-8"))
    return record
