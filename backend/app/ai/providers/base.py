"""AI provider interface (plan A8). Result shapes are documented in app.ai.prompts."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    name: str
    extraction_model_id: str
    embedding_model_id: str
    generated_by: str

    def available(self) -> bool:
        """True when the provider can be called right now (credentials etc.)."""
        ...

    def extract_document(self, pages: list[str], filename: str) -> dict[str, Any]:
        """Extract the document-level facts. Gateway post-checks run on the result."""
        ...

    def structure_rfq(self, text: str) -> dict[str, Any]:
        """Turn raw RFQ prose into catalog criteria."""
        ...

    def embed(self, text: str) -> list[float]:
        """Embedding vector for text."""
        ...
