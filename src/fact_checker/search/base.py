from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from diskcache import Cache
from pydantic import BaseModel

from fact_checker.models.claim import ClaimType

CACHE_DIR = Path(os.environ.get("FACT_CHECKER_CACHE_DIR", ".cache")) / "search"
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24

# How long a search result stays cached before we re-hit the backend, per
# claim type. Fast-moving TEMPORAL facts ("is X still CEO") go stale within
# minutes; stable FACTUAL claims can safely reuse a day-old search.
CACHE_TTL_BY_CLAIM_TYPE: dict[ClaimType, int] = {
    ClaimType.TEMPORAL: 5 * 60,
    ClaimType.STATISTICAL: 60 * 60,
    ClaimType.IDENTITY: 6 * 60 * 60,
    ClaimType.FACTUAL: DEFAULT_CACHE_TTL_SECONDS,
    ClaimType.OPINION: DEFAULT_CACHE_TTL_SECONDS,
}

_cache = Cache(str(CACHE_DIR))


class SearchResult(BaseModel):
    """A raw hit from a search backend, before stance/credibility/quote are known."""

    title: str
    url: str
    domain: str
    snippet: str
    published_at: datetime | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    from_cache: bool
    cached_at: datetime


def _cache_key(backend: str, query: str, max_results: int) -> str:
    raw = json.dumps(
        {"backend": backend, "query": query, "max_results": max_results}, sort_keys=True
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class SearchBackend(ABC):
    name: str

    @abstractmethod
    async def _search(self, query: str, max_results: int) -> list[SearchResult]:
        """Call the underlying API and return raw results. No caching here."""

    async def search(
        self,
        query: str,
        max_results: int = 8,
        claim_type: ClaimType | None = None,
    ) -> SearchResponse:
        key = _cache_key(self.name, query, max_results)
        cached = _cache.get(key)
        if cached is not None:
            return SearchResponse(
                results=[SearchResult.model_validate(item) for item in cached["results"]],
                from_cache=True,
                cached_at=datetime.fromisoformat(cached["cached_at"]),
            )

        results = await self._search(query, max_results)
        cached_at = datetime.now(timezone.utc)
        ttl = (
            DEFAULT_CACHE_TTL_SECONDS
            if claim_type is None
            else CACHE_TTL_BY_CLAIM_TYPE.get(claim_type, DEFAULT_CACHE_TTL_SECONDS)
        )
        _cache.set(
            key,
            {
                "cached_at": cached_at.isoformat(),
                "results": [result.model_dump(mode="json") for result in results],
            },
            expire=ttl,
        )
        return SearchResponse(results=results, from_cache=False, cached_at=cached_at)
