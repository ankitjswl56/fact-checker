from __future__ import annotations

from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

USER_AGENT = "fact-checker-bot/0.1 (+https://github.com/; research tool)"
FETCH_TIMEOUT_SECONDS = 15.0


class PageContent(BaseModel):
    url: str
    domain: str
    text: str
    outbound_citation_count: int


async def fetch_page(url: str, client: httpx.AsyncClient | None = None) -> PageContent:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True)
    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = " ".join(soup.get_text(separator=" ").split())
        domain = urlparse(str(response.url)).netloc
        return PageContent(
            url=str(response.url),
            domain=domain,
            text=text,
            outbound_citation_count=_count_outbound_domains(soup, domain),
        )
    finally:
        if owns_client:
            await client.aclose()


def _count_outbound_domains(soup: BeautifulSoup, own_domain: str) -> int:
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        parsed = urlparse(anchor["href"])
        if parsed.scheme in ("http", "https") and parsed.netloc and parsed.netloc != own_domain:
            seen.add(parsed.netloc)
    return len(seen)
