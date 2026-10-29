"""Abstract interface for live news discovery adapters."""

from __future__ import annotations

from typing import List, Protocol
from src.models import Article


class NewsSourceAdapter(Protocol):
    def discover_articles(
        self,
        query_terms: List[str],
        languages: List[str],
        limit: int = 100
    ) -> List[Article]:
        """Discovers recent news metadata matching query criteria."""
        ...
