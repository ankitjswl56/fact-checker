from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import urlparse

import httpx

from fact_checker.search.base import SearchBackend, SearchResult

TAVILY_API_URL = "https://api.tavily.com/search"


class TavilySearchBackend(SearchBackend):
    name = "tavily"

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.environ["TAVILY_API_KEY"]
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def _search(self, query: str, max_results: int) -> list[SearchResult]:
        response = await self._client.post(
            TAVILY_API_URL,
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return [_to_search_result(item) for item in payload.get("results", [])]

    async def aclose(self) -> None:
        await self._client.aclose()


def _to_search_result(item: dict) -> SearchResult:
    url = item["url"]
    return SearchResult(
        title=item.get("title", ""),
        url=url,
        domain=urlparse(url).netloc,
        snippet=item.get("content", ""),
        published_at=_parse_date(item.get("published_date")),
    )


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None