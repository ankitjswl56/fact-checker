# Fact-Checker AI Pipeline

Portfolio project: an AI-powered fact-checking pipeline exposed as an MCP server so other AI agents can call it as a tool.

## What It Does

Given a claim, the system:
1. Classifies and decomposes it into atomic sub-claims
2. Runs an agentic search loop (model decides what to search, when to stop)
3. Scores source credibility programmatically
4. Cross-references sources — flags agreement, disagreement, no coverage
5. Returns a verdict (TRUE / FALSE / PARTIALLY_TRUE / UNVERIFIABLE / OPINION) with verbatim cited quotes, not LLM opinion
6. Produces a full reasoning trace showing why it trusted source A over source B

## Architecture

```
User Claim
    │
    ▼
[Claim Classifier]        deterministic — classifies type, splits compound claims
    │
    ▼
[Agentic Research Loop]   Claude + tool use loop — searches until model decides done
    │  Tools: search(query), fetch_page(url)
    │  Model decides: search more? fetch a URL? enough evidence? give up?
    ▼
[Credibility Scorer]      deterministic — scores every retrieved source
    │
    ▼
[Verdict Synthesizer]     Claude reads scored evidence, writes verdict + reasoning trace
    │
    ▼
Structured JSON output
```

### Claim Types
- `FACTUAL` — verifiable true/false
- `STATISTICAL` — number-based, requires original data source
- `TEMPORAL` — time-sensitive ("X is currently...")
- `OPINION` — not verifiable, return OPINION verdict immediately
- `IDENTITY` — about a person/entity, privacy-sensitive

### Verdict Types
- `TRUE` — supported by credible sources
- `FALSE` — contradicted by credible sources
- `PARTIALLY_TRUE` — some sub-claims hold, others don't; or sources conflict
- `UNVERIFIABLE` — no reliable sources found; do NOT guess
- `OPINION` — claim is not empirically checkable

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | async-first, best AI ecosystem |
| LLM calls | `litellm` | provider-agnostic; swap model via env var |
| Default model | `claude-sonnet-4-6` | tool use + extended thinking |
| Fast/cheap steps | `claude-haiku-4-5` | claim classification, stance labeling |
| Search backend 1 | Brave Search API | clean results, reasonable free tier |
| Search backend 2 | Tavily API | built for AI agents, returns pre-extracted snippets |
| HTTP | `httpx` | async |
| Data models | `pydantic v2` | strict validation throughout; load-bearing |
| Caching | `diskcache` | cache search results by query hash |
| MCP server | `fastmcp` | exposes pipeline as MCP tool |
| CLI | `rich` | formatted output for demos |
| Tests | `pytest` + `pytest-recording` | VCR cassettes for deterministic search tests |
| Type checking | `mypy` | enforced in CI |

### Provider Switching

One env var controls the model. No code changes needed:

```
# .env
LLM_MODEL=claude-sonnet-4-6      # default
# LLM_MODEL=gpt-4o               # OpenAI
# LLM_MODEL=gemini/gemini-2.0-flash
# LLM_MODEL=ollama/llama3.2      # local, free
```

**No LangChain.** The agent loop is a plain Python while loop. LiteLLM only handles the model call translation — all orchestration logic is explicit in this codebase.

**No Wikipedia API.** User-editable, not a reliable primary source.

## Source Credibility Scoring

Every source gets a score 0.0–1.0 from four signals:

```
credibility = (domain_tier * 0.40) + (source_type * 0.30) +
              (recency * 0.15) + (citation_density * 0.15)
```

- **Domain tier** (0.40): Pre-curated `domain_tiers.json` — tier 1 (.gov, .edu, journals), tier 2 (Reuters, AP, BBC), tier 3 (general web), tier 4 (unknown). Satire domains score 0.0 and are excluded.
- **Source type** (0.30): LLM classifies PRIMARY (original study/report) vs SECONDARY (news article about it) vs TERTIARY (blog about article)
- **Recency** (0.15): Decay function — rate depends on claim type (stable facts decay slowly, current events decay fast)
- **Citation density** (0.15): Does the source cite its own sources? Count outbound reference links in fetched HTML.

All four signals are logged individually in output so users can see the breakdown.

## MCP Tool Interface

```python
@mcp.tool()
async def fact_check(
    claim: str,
    depth: Literal["quick", "standard", "deep"] = "standard",
    context: str | None = None,   # e.g. "said by X in 2024"
    max_sources: int = 8
) -> FactCheckResult: ...

@mcp.tool()
async def classify_claim(
    claim: str
) -> ClaimClassification: ...    # is this even checkable?
```

### Output Schema (FactCheckResult)

```json
{
  "verdict": "TRUE | FALSE | PARTIALLY_TRUE | UNVERIFIABLE | OPINION",
  "confidence": 0.0,
  "summary": "one paragraph explanation",
  "sub_claims": [
    {
      "claim": "atomic sub-claim",
      "verdict": "...",
      "confidence": 0.0,
      "supporting_evidence": ["src_1"],
      "contradicting_evidence": ["src_2"]
    }
  ],
  "sources": [
    {
      "id": "src_1",
      "url": "https://...",
      "domain": "reuters.com",
      "credibility_score": 0.82,
      "credibility_breakdown": {
        "domain_tier": 0.75,
        "source_type": "secondary",
        "recency_days": 14,
        "citation_density": 0.60
      },
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL",
      "quote": "verbatim excerpt — required, no exceptions",
      "retrieved_at": "ISO datetime"
    }
  ],
  "reasoning_trace": "step-by-step explanation of verdict logic",
  "warnings": ["Sources conflict on sub-claim 2", "No primary sources found"],
  "metadata": {
    "sub_claims_count": 3,
    "sources_evaluated": 14,
    "search_queries_run": ["query1", "query2"],
    "processing_time_ms": 4200,
    "depth": "standard"
  }
}
```

**Critical rule**: every verdict must anchor to a verbatim `quote` from a real URL. No quote = evidence is discarded. This is enforced as a required Pydantic field, not just a convention.

## Repo Structure

```
fact-checker/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── src/
│   └── fact_checker/
│       ├── __init__.py
│       ├── pipeline/
│       │   ├── __init__.py         # orchestrator
│       │   ├── classifier.py       # claim type detection + decomposition
│       │   ├── research_loop.py    # agentic search loop (litellm + tool use)
│       │   ├── credibility.py      # deterministic source scoring
│       │   └── synthesizer.py      # verdict aggregation + reasoning trace
│       ├── models/
│       │   ├── claim.py
│       │   ├── evidence.py
│       │   └── verdict.py
│       ├── search/
│       │   ├── base.py             # abstract SearchBackend
│       │   ├── brave.py
│       │   └── tavily.py
│       ├── data/
│       │   ├── domain_tiers.json
│       │   └── satire_domains.txt
│       ├── mcp_server.py
│       └── cli.py
│
├── tests/
│   ├── cassettes/                  # VCR recorded search responses
│   ├── unit/
│   │   ├── test_credibility.py
│   │   ├── test_classifier.py
│   │   └── test_synthesizer.py
│   └── integration/
│       ├── test_pipeline.py
│       └── test_mcp.py
│
└── examples/
    ├── true_claim.py
    ├── false_claim.py
    ├── partially_true.py
    ├── unverifiable.py
    └── opinion_claim.py
```

## Build Order

### Phase 1 — Models + Credibility Scorer (no external calls)
- Define all Pydantic models (`claim.py`, `evidence.py`, `verdict.py`)
- Build `domain_tiers.json` with ~200 known domains
- Build `credibility.py` — pure deterministic scoring
- Unit test: given URL → assert credibility score
- **Done when**: `pytest tests/unit/test_credibility.py` passes, no external calls needed

### Phase 2 — Search Backends
- Implement abstract `SearchBackend` in `search/base.py`
- Implement `brave.py`, then `tavily.py`
- Record VCR cassettes with real queries
- **Done when**: given a query string, returns list of `Evidence` objects; tests run offline

### Phase 3 — LLM Stages (isolated, prompt-tunable)
- `classifier.py` — test with 10 claims covering all types
- `synthesizer.py` — test with pre-built evidence pools
- Each stage independently testable with real LLM calls (not mocked — prompt quality matters)
- **Done when**: each stage has 5+ passing tests

### Phase 4 — Agentic Research Loop
- Build `research_loop.py` — litellm + tool use while loop
- Wire classifier → research loop → credibility scorer → synthesizer
- Run 10 benchmark claims covering all verdict types
- Main prompt-tuning phase; expect multiple iterations
- **Done when**: 10 benchmarks produce defensible verdicts with cited quotes

### Phase 5 — MCP Server
- Implement `mcp_server.py` with `fastmcp`
- Test with Claude Desktop as host
- Validate JSON schema matches spec
- **Done when**: another AI agent can call `fact_check()` and get valid structured response

### Phase 6 — Portfolio Polish
- CLI with rich-formatted tables and color-coded verdicts
- README: what it does, architecture, known limitations, how to run, example outputs
- GitHub Actions: pytest + mypy on push
- Five `examples/` scripts with real output

## Known Hard Edge Cases

| Case | Mitigation |
|---|---|
| Rapidly changing facts ("X is CEO of Y") | Surface `retrieved_at`, aggressive recency decay, warn on "current status" claims |
| Cherry-picked statistics | Detect statistical claims, require original data source, surface time range in verdict |
| Opinion disguised as fact | Classify upfront; return OPINION immediately, no verdict assigned |
| Circular sourcing (A cites B cites A) | Track citation graph; down-rank circular references |
| Satire laundering | Satire domain list; LLM checks content for satirical markers if domain unknown |
| No sources found | Return UNVERIFIABLE, show what was searched, do not guess |
| High-credibility source conflict | Surface both quotes side by side, return PARTIALLY_TRUE |
| LLM hallucinating source stances | Required `quote` field in Pydantic model — no quote = evidence discarded |

## Environment Variables

```
ANTHROPIC_API_KEY=      # required if using Anthropic models
OPENAI_API_KEY=         # required if switching to OpenAI models
BRAVE_API_KEY=          # required
TAVILY_API_KEY=         # required
LLM_MODEL=claude-sonnet-4-6    # change to swap provider
LLM_MODEL_FAST=claude-haiku-4-5  # used for cheap classification steps
```
