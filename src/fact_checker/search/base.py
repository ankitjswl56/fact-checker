from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from diskcache import Cache
from pydantic import BaseModel

CACHE_DIR = Path(os.environ.get("FACT_CHECKER_CACHE_DIR", ".cache")) / "search"
CACHE_TTL_SECONDS = 60 * 60 * 24

_cache = Cache(str(CACHE_DIR))


class SearchResult(BaseModel):
    """A raw hit from a search backend, before stance/credibility/quote are known."""

    title: str
    url: str
    domain: str
    snippet: str
    published_at: datetime | None = None


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

    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        key = _cache_key(self.name, query, max_results)
        cached = _cache.get(key)
        if cached is not None:
            return [SearchResult.model_validate(item) for item in cached]

        results = await self._search(query, max_results)
        _cache.set(
            key,
            [result.model_dump(mode="json") for result in results],
            expire=CACHE_TTL_SECONDS,
        )
        return results