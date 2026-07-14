from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Literal

import httpx
import litellm
from pydantic import BaseModel

from fact_checker.models.claim import ClaimType
from fact_checker.models.evidence import Evidence, SourceType
from fact_checker.pipeline import credibility
from fact_checker.pipeline.fetch import PageContent, fetch_page
from fact_checker.pipeline.llm import DEFAULT_MODEL
from fact_checker.pipeline.synthesizer import label_stance
from fact_checker.search.base import SearchBackend

DepthLevel = Literal["quick", "standard", "deep"]

DEPTH_MAX_ITERATIONS: dict[DepthLevel, int] = {"quick": 6, "standard": 12, "deep": 20}
SEARCH_RESULTS_PER_QUERY = 5
FETCHED_TEXT_PREVIEW_CHARS = 6000

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": (
                "Search the web for pages relevant to a query. Returns titles, "
                "URLs, publish dates, and short snippets — not full text."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": (
                "Fetch the full text of a URL so you can read it and find a "
                "verbatim quote to cite. You must fetch a page before saving "
                "evidence from it."
            ),
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_evidence",
            "description": (
                "Record a piece of evidence to cite in the verdict. The quote "
                "must be an exact, verbatim substring of a page you previously "
                "fetched with fetch_page — it is rejected otherwise."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL the quote came from (must have been fetched first)",
                    },
                    "quote": {
                        "type": "string",
                        "description": "Exact verbatim excerpt relevant to the claim, copied word for word",
                    },
                    "source_type": {
                        "type": "string",
                        "enum": ["PRIMARY", "SECONDARY", "TERTIARY"],
                        "description": (
                            "PRIMARY: the fact originates here — an official statement "
                            "from the entity/organization the claim is about (e.g. a "
                            "company's own leadership page naming its CEO), a raw "
                            "dataset, an original study, a government record, or "
                            "first-hand testimony. SECONDARY: an independent party "
                            "reporting or compiling the fact without having created it "
                            "— this includes news articles AND general reference/"
                            "encyclopedia sites (e.g. Britannica, Wikipedia) — being "
                            "authoritative does not make a source PRIMARY if it isn't "
                            "the origin of the fact. TERTIARY: a blog, opinion piece, "
                            "or commentary discussing or analyzing the topic, often "
                            "itself citing secondary sources."
                        ),
                    },
                },
                "required": ["url", "quote", "source_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_research",
            "description": (
                "Call this when you have enough evidence to support a verdict, "
                "or when further searching is unlikely to turn up anything "
                "useful. Ends the research phase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Brief reason research is concluding"}
                },
                "required": ["reason"],
            },
        },
    },
]

_SYSTEM_PROMPT = """\
You are the research stage of a fact-checking pipeline. You are given a claim \
of type {claim_type} and must gather verifiable evidence for or against it \
using the tools available to you.

Process:
1. Use `search` once or twice to find candidate sources — a single search \
   usually returns several usable URLs, so do not re-search with slightly \
   reworded queries when you already have promising results to fetch.
2. Use `fetch_page` to read a promising result in full before citing it — \
   snippets from search are not sufficient to cite. Fetch multiple results \
   from your existing search results before searching again.
3. Use `save_evidence` to record a verbatim quote once you've found one that \
   clearly supports or contradicts the claim. Prefer PRIMARY sources (original \
   studies, official statements, datasets) over SECONDARY (news) over TERTIARY \
   (blogs/commentary) when available.
4. Call `finish_research` once you have evidence from 2-3 independent \
   credible sources, or once a couple of searches turn up nothing relevant. \
   You have a limited number of tool calls — move efficiently from search to \
   fetch to save rather than over-searching.

Rules:
- Never fabricate a quote or cite a page you have not fetched.
- If sources disagree, save evidence representing both sides rather than only \
  the one that confirms your first guess.
- If you cannot find credible coverage after a genuine effort, call \
  finish_research and say so — returning no evidence is correct when nothing \
  verifiable exists. Do not guess.
"""


class ResearchResult(BaseModel):
    evidence: list[Evidence]
    search_queries_run: list[str]
    used_cache: bool = False


async def research_claim(
    claim: str,
    claim_type: ClaimType,
    search_backend: SearchBackend,
    depth: DepthLevel = "standard",
    max_sources: int = 8,
    context: str | None = None,
) -> ResearchResult:
    max_iterations = DEPTH_MAX_ITERATIONS[depth]
    evidence: list[Evidence] = []
    queries_run: list[str] = []
    fetched_pages: dict[str, PageContent] = {}
    published_dates: dict[str, datetime | None] = {}
    used_cache = False

    user_content = f"Claim to research: {claim}"
    if context:
        user_content += f"\nAdditional context: {context}"

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(claim_type=claim_type.value)},
        {"role": "user", "content": user_content},
    ]

    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)

    for _ in range(max_iterations):
        if len(evidence) >= max_sources:
            break

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            num_retries=5,
        )
        message = response.choices[0].message
        messages.append(message.model_dump())

        tool_calls = message.tool_calls or []
        if not tool_calls:
            break

        should_stop = False
        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "search":
                result_text, from_cache = await _handle_search(
                    search_backend, args, queries_run, published_dates, claim_type
                )
                used_cache = used_cache or from_cache
            elif name == "fetch_page":
                result_text = await _handle_fetch(args, fetched_pages)
            elif name == "save_evidence":
                result_text, new_evidence = await _handle_save_evidence(
                    args, claim, claim_type, fetched_pages, published_dates, evidence
                )
                if new_evidence is not None:
                    evidence.append(new_evidence)
            elif name == "finish_research":
                should_stop = True
                result_text = "Research concluded."
            else:
                result_text = f"Error: unknown tool '{name}'."

            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result_text}
            )

        if should_stop:
            break

    return ResearchResult(evidence=evidence, search_queries_run=queries_run, used_cache=used_cache)


def _normalize_for_match(text: str) -> str:
    """Collapse whitespace, including artifacts our HTML-to-text extraction can
    introduce around punctuation (e.g. inline tags becoming stray spaces), so
    quote matching isn't brittle to those artifacts while still requiring the
    words themselves to appear verbatim and in order."""
    collapsed = " ".join(text.split())
    return re.sub(r"\s+([.,;:!?)])", r"\1", collapsed)


async def _handle_search(
    search_backend: SearchBackend,
    args: dict,
    queries_run: list[str],
    published_dates: dict[str, datetime | None],
    claim_type: ClaimType,
) -> tuple[str, bool]:
    query = args.get("query", "").strip()
    if not query:
        return "Error: query must not be empty.", False

    queries_run.append(query)
    response = await search_backend.search(
        query, max_results=SEARCH_RESULTS_PER_QUERY, claim_type=claim_type
    )
    if not response.results:
        return "No results found for this query.", response.from_cache

    lines = []
    for result in response.results:
        published_dates[result.url] = result.published_at
        lines.append(
            f'- url={result.url} domain={result.domain} '
            f'published_at={result.published_at} title="{result.title}"\n'
            f"  snippet: {result.snippet}"
        )
    text = "\n".join(lines)
    if response.from_cache:
        text += (
            f"\n\n(Note: these results were served from cache, originally "
            f"retrieved at {response.cached_at.isoformat()} — they may not "
            f"reflect the latest information, which matters most for "
            f"TEMPORAL claims.)"
        )
    return text, response.from_cache


async def _handle_fetch(args: dict, fetched_pages: dict[str, PageContent]) -> str:
    url = args.get("url", "").strip()
    if not url:
        return "Error: url must not be empty."

    try:
        page = await fetch_page(url)
    except httpx.HTTPError as exc:
        return f"Error fetching {url}: {exc}"

    fetched_pages[url] = page
    fetched_pages.setdefault(page.url, page)
    truncated = page.text[:FETCHED_TEXT_PREVIEW_CHARS]
    suffix = " [truncated]" if len(page.text) > FETCHED_TEXT_PREVIEW_CHARS else ""
    return f"Fetched {url} ({page.domain}). Content:\n{truncated}{suffix}"


async def _handle_save_evidence(
    args: dict,
    claim: str,
    claim_type: ClaimType,
    fetched_pages: dict[str, PageContent],
    published_dates: dict[str, datetime | None],
    existing_evidence: list[Evidence],
) -> tuple[str, Evidence | None]:
    url = args.get("url", "").strip()
    quote = args.get("quote", "").strip()
    source_type_raw = args.get("source_type", "")

    if not url or not quote:
        return "Error: url and quote are both required.", None

    try:
        source_type = SourceType(source_type_raw)
    except ValueError:
        return (
            f"Error: source_type must be one of PRIMARY, SECONDARY, TERTIARY "
            f"(got '{source_type_raw}').",
            None,
        )

    page = fetched_pages.get(url)
    if page is None:
        return "Error: you must fetch_page(url) before saving a quote from it.", None

    if _normalize_for_match(quote) not in _normalize_for_match(page.text):
        return (
            "Error: that quote was not found verbatim in the fetched page text. "
            "Copy the exact wording from the page rather than paraphrasing.",
            None,
        )

    if any(e.url == url and e.quote == quote for e in existing_evidence):
        return "Note: this exact quote from this URL was already saved.", None

    scored = credibility.score_source(
        domain=page.domain,
        source_type=source_type,
        claim_type=claim_type,
        published_at=published_dates.get(url),
        citation_count=page.outbound_citation_count,
    )
    if scored.excluded:
        return f"Error: {page.domain} is excluded from evidence ({scored.exclusion_reason}).", None

    stance = await label_stance(claim, quote)

    evidence = Evidence(
        id=f"src_{len(existing_evidence) + 1}",
        url=url,
        domain=page.domain,
        credibility_score=scored.credibility_score,
        credibility_breakdown=scored.credibility_breakdown,
        stance=stance,
        quote=quote,
        retrieved_at=datetime.now(timezone.utc),
    )
    return (
        f"Saved evidence {evidence.id}: stance={stance.value}, "
        f"credibility={evidence.credibility_score:.2f}.",
        evidence,
    )
