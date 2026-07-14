# Fact-Checker

An AI-powered fact-checking pipeline, exposed as an [MCP](https://modelcontextprotocol.io) server so other AI agents can call it as a tool — and usable directly as a Python function or a CLI.

Given a claim, it classifies and decomposes it, runs an agentic search loop that decides what to search and when to stop, scores every source it finds with a deterministic (non-LLM) credibility formula, cross-references sources for agreement/disagreement, and returns a verdict anchored to verbatim cited quotes — never an unsupported guess.

## What It Does

1. **Classifies** the claim (`FACTUAL` / `STATISTICAL` / `TEMPORAL` / `OPINION` / `IDENTITY`) and splits it into atomic sub-claims if it bundles more than one assertion.
2. **Researches** it with an agentic loop: an LLM decides what to search, which pages to fetch, and which verbatim quotes to save as evidence — or gives up and reports `UNVERIFIABLE` rather than guessing.
3. **Scores** every source's credibility with a deterministic formula (domain reputation, source type, recency, citation density) — no LLM involved in the score itself.
4. **Cross-references** sources, weighing higher-credibility evidence over lower, and flags disagreement.
5. **Returns** a verdict (`TRUE` / `FALSE` / `PARTIALLY_TRUE` / `UNVERIFIABLE` / `OPINION`) with a full reasoning trace explaining why one source was trusted over another, plus every cited quote.

**The one rule the whole system is built around**: a piece of evidence with no verbatim quote is not evidence. `quote` is a required, non-blank Pydantic field on every source — there is no code path that produces a citation without one. The research loop even verifies each quote is an exact substring of the page it claims to be from before accepting it, rejecting anything paraphrased or hallucinated.

## Architecture

```
User Claim
    │
    ▼
[Claim Classifier]        deterministic types, LLM classifies + decomposes
    │
    ▼
[Agentic Research Loop]   LLM + tool use loop — searches until it decides it's done
    │  Tools: search(query), fetch_page(url), save_evidence(url, quote, source_type)
    │  save_evidence rejects any quote that isn't a verbatim substring of the fetched page
    ▼
[Credibility Scorer]      deterministic — scores every retrieved source, 0.0-1.0
    │
    ▼
[Verdict Synthesizer]     LLM reads scored evidence, writes verdict + reasoning trace
    │  Empty evidence pool short-circuits to UNVERIFIABLE in code, no LLM call
    ▼
Structured JSON output (FactCheckResult)
```

Two doors into this pipeline: call `fact_check()` directly from Python (what the CLI does), or call it over MCP (what `mcp_server.py` exposes). Both hit the exact same function — MCP is a thin adapter, not where the logic lives.

## Quick Start

```bash
git clone <this repo>
cd fact-checker
python -m venv .venv
.venv/bin/pip install -e ".[dev]"

cp .env.example .env
# edit .env: add GEMINI_API_KEY (free at https://aistudio.google.com/apikey)
#        and TAVILY_API_KEY (free at https://app.tavily.com)
```

**CLI:**

```bash
fact-checker "The Eiffel Tower is located in Paris, France."
fact-checker "Tim Cook is the CEO of Apple" --depth deep --context "as of 2024"
```

**MCP server** (e.g. with Claude Desktop — add to `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "fact-checker": {
      "command": "/absolute/path/to/fact-checker/.venv/bin/fact-checker-mcp"
    }
  }
}
```

Exposes two tools: `fact_check(claim, depth, context, max_sources)` and `classify_claim(claim)`.

**As a library:**

```python
from fact_checker.pipeline import fact_check

result = await fact_check("The Great Wall of China is visible from space.")
print(result.verdict, result.confidence)
```

## Example Outputs

See [`examples/`](examples/) for five runnable scripts, one per verdict type, each with real captured output in a trailing comment:

- [`true_claim.py`](examples/true_claim.py) — TRUE, two independent sources
- [`false_claim.py`](examples/false_claim.py) — FALSE, debunked with primary astronaut testimony
- [`opinion_claim.py`](examples/opinion_claim.py) — OPINION, short-circuits before any research runs
- [`unverifiable.py`](examples/unverifiable.py) — UNVERIFIABLE, the no-guessing fail-safe
- [`partially_true.py`](examples/partially_true.py) — PARTIALLY_TRUE, a compound claim with one true and one false sub-claim

A nice real-world validation caught during benchmarking: fact-checking "Tim Cook is the CEO of Apple" live turned up a real, dated announcement of Cook transitioning to executive chairman with John Ternus succeeding him — and the system correctly returned `PARTIALLY_TRUE` with a warning about the pending transition, rather than a stale flat `TRUE`. That's exactly the announced-but-not-yet-effective edge case the claim-type-aware recency decay and synthesizer prompt were designed to catch.

## Source Credibility Scoring

Every source gets a score from 0.0-1.0, computed with zero LLM calls:

```
credibility = domain_tier * 0.40 + source_type * 0.30 + recency * 0.15 + citation_density * 0.15
```

- **Domain tier (40%)**: a curated list of ~160 domains across three tiers (`.gov`/`.edu`/journals; wire services and major outlets; general web) — unknown domains default to the lowest tier. Known satire domains score `0.0` and are excluded outright.
- **Source type (30%)**: the research loop's LLM labels each source PRIMARY / SECONDARY / TERTIARY as it saves the quote.
- **Recency (15%)**: exponential decay, with a half-life tuned per claim type — a `TEMPORAL` claim ("is X still CEO") decays in 14 days, a stable `FACTUAL` claim in 365.
- **Citation density (15%)**: how many distinct outbound domains a fetched page links to, as a rough signal of whether it cites its own sources.

All four signals are returned individually in `credibility_breakdown` on every source, not just the final number.

## Known Limitations

- **Free-tier LLM quota is tight.** The default model is Gemini's free tier, and on this project's account `gemini-2.5-flash`/`gemini-3.5-flash` are capped at 20 requests/day, while `gemini-2.0-flash` isn't enabled on the free tier at all. Both `LLM_MODEL` and `LLM_MODEL_FAST` currently default to `gemini-3.1-flash-lite` as the only model with reliable headroom — weaker reasoning than the stronger Flash models, swappable via env var with no code changes once quota/budget allows.
- **A sub-claim's verdict can be reasoned from the model's background knowledge rather than a cited source.** The citation-verification guard only applies to evidence that *is* saved via `save_evidence` — it doesn't force every sub-claim in a compound claim to have a citation (observed on a `PARTIALLY_TRUE` benchmark: one sub-claim was correctly judged FALSE with no source ever fetched for it).
- **Duplicate-domain evidence isn't down-weighted.** Two saved quotes from the same URL still count as two sources in the pool (observed on an IDENTITY benchmark) — credibility scoring doesn't currently check independence across sources.
- **Only Tavily is implemented** as a search backend; Brave (the second backend in the original design) requires a paid API key and hasn't been built.
- **MCP server is schema-verified but not yet tested against a live MCP client** end-to-end.
- **The search cache can serve results up to its TTL old** even while fully online — TTL is claim-type-aware (5 minutes for `TEMPORAL`, up to a day for stable `FACTUAL` claims) specifically to bound this, and a cache hit surfaces a warning in the result, but it's not eliminated.
- **`litellm`'s tool-calling path requires the `[proxy]` extra** even though this project never runs litellm's proxy server — it unconditionally imports proxy-server code once the `mcp` package is importable (which `fastmcp` requires), pulling in `fastapi`/`orjson`/etc. as a side effect. Already handled in `pyproject.toml`; noted here in case it resurfaces with a litellm upgrade.
- Per the design's existing safeguards: no Wikipedia (user-editable, not a primary source), no verdict without a verbatim quote, `UNVERIFIABLE` rather than a guess when evidence is thin.

## Development

```bash
.venv/bin/pytest        # offline — uses a recorded VCR cassette, no network/API keys needed
.venv/bin/mypy
```

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM calls | `litellm` (provider-agnostic; swap model via `LLM_MODEL` env var) |
| Search | Tavily (Brave planned, not yet built) |
| HTTP / HTML | `httpx` + `beautifulsoup4` |
| Data models | `pydantic v2` — strict validation throughout |
| Caching | `diskcache`, claim-type-aware TTL |
| MCP server | `fastmcp` |
| CLI | `rich` |
| Tests | `pytest` + `pytest-recording` (VCR cassettes) |
| Type checking | `mypy --strict` |
