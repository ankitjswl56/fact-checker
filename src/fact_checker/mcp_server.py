from __future__ import annotations

from fastmcp import FastMCP

from fact_checker.models.claim import ClaimClassification
from fact_checker.models.verdict import FactCheckResult
from fact_checker.pipeline import fact_check as _fact_check
from fact_checker.pipeline.classifier import classify_claim as _classify_claim
from fact_checker.pipeline.research_loop import DepthLevel

mcp = FastMCP("fact-checker")


@mcp.tool()
async def fact_check(
    claim: str,
    depth: DepthLevel = "standard",
    context: str | None = None,
    max_sources: int = 8,
) -> FactCheckResult:
    """Fact-check a claim end-to-end: classify it, research it with an
    agentic search loop, score and cross-reference sources by credibility,
    and return a verdict (TRUE/FALSE/PARTIALLY_TRUE/UNVERIFIABLE/OPINION)
    with verbatim cited quotes and a reasoning trace. Never guesses — returns
    UNVERIFIABLE rather than an unsupported answer when no credible evidence
    is found.

    Args:
        claim: The claim to fact-check.
        depth: How much research effort to spend — "quick", "standard", or
            "deep". Deeper searches more sources but takes longer.
        context: Optional grounding context, e.g. "said by X in a 2024
            interview", to disambiguate the claim.
        max_sources: Maximum number of sources to cite in the verdict.
    """
    return await _fact_check(claim, depth=depth, context=context, max_sources=max_sources)


@mcp.tool()
async def classify_claim(claim: str) -> ClaimClassification:
    """Classify a claim's type (FACTUAL/STATISTICAL/TEMPORAL/OPINION/IDENTITY)
    and decompose it into atomic sub-claims if it bundles multiple assertions
    — without running the full research pipeline. Useful for checking
    whether a claim is even checkable before spending a fact_check call on
    it (OPINION claims are not checkable).
    """
    return await _classify_claim(claim)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
