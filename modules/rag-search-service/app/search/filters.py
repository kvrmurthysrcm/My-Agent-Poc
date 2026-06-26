from dataclasses import dataclass, field
from typing import Any

from app.schemas.search_request import SearchFilters


@dataclass(frozen=True)
class SearchFilterSet:
    resource_id: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def to_filter_set(filters: SearchFilters | None) -> SearchFilterSet:
    if filters is None:
        return SearchFilterSet()
    return SearchFilterSet(
        resource_id=filters.resource_id,
        category=filters.category,
        tags=filters.tags,
        metadata=filters.metadata,
    )
