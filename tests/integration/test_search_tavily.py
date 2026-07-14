from __future__ import annotations

import os

import pytest

from fact_checker.search.base import _cache
from fact_checker.search.tavily import TavilySearchBackend

# Cassette replay never inspects the request body's api_key (see conftest's
# match_on), so a placeholder is fine when no real key is available (e.g. CI).
_TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _clear_search_cache():
    _cache.clear()
    yield
    _cache.clear()


@pytest.mark.vcr()
async def test_tavily_search_returns_results() -> None:
    backend = TavilySearchBackend(api_key=_TAVILY_API_KEY)
    try:
        response = await backend.search("who is the CEO of Apple", max_results=3)
    finally:
        await backend.aclose()

    assert response.from_cache is False
    assert response.results
    for result in response.results:
        assert result.url
        assert result.domain
        assert result.title