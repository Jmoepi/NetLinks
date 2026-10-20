"""Per-page PDF text extraction with pypdf (text PDFs only; OCR is out of scope)."""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError


class UnreadablePDF(ValueError):
    """The upload is not a readable PDF."""


def extract_pages(data: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        return [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, ValueError, KeyError, TypeError) as exc:
        raise UnreadablePDF(f"Could not read PDF text: {exc}") from exc
