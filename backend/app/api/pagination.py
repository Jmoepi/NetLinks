"""Shared page/page_size query params and list slicing for paginated list endpoints.

Endpoints stay backward compatible: they only paginate when a client sends page or page_size.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, TypeVar

from fastapi import Query

T = TypeVar("T")

PageQuery = Annotated[int | None, Query(ge=1)]
PageSizeQuery = Annotated[int | None, Query(ge=1, le=100)]


def paginate(items: list[T], page: int, page_size: int) -> tuple[list[T], dict[str, Any]]:
    """Slice one page (1-based). A page beyond the end is an empty list, not an error."""
    total = len(items)
    start = (page - 1) * page_size
    meta = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }
    return items[start : start + page_size], meta
