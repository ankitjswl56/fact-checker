from __future__ import annotations

import time

from fact_checker.models.claim import ClaimType
from fact_checker.models.verdict import FactCheckMetadata, FactCheckResult, VerdictType
from fact_checker.pipeline.classifier import classify_claim
from fact_checker.pipeline.research_loop import DepthLevel, research_claim
from fact_checker.pipeline.synthesizer import synthesize_verdict
from fact_checker.search.base import SearchBackend
from fact_checker.search.tavily import TavilySearchBackend


async def fact_check(
    claim: str,
    depth: DepthLevel = "standard",
    context: str | None = None,
    max_sources: int = 8,
    search_backend: SearchBackend | None = None,
) -> FactCheckResult:
    start = time.perf_counter()
    backend = search_backend or TavilySearchBackend()

    classification = await classify_claim(claim)

    if classification.claim_type == ClaimType.OPINION:
        return FactCheckResult(
            verdict=VerdictType.OPINION,
            confidence=1.0,
            summary="This is a subjective claim and cannot be empirically fact-checked.",
            sub_claims=[],
            sources=[],
            reasoning_trace=classification.reasoning or "Classified as an opinion, not a checkable fact.",
            warnings=[],
            metadata=FactCheckMetadata(
                sub_claims_count=0,
                sources_evaluated=0,
                search_queries_run=[],
                processing_time_ms=_elapsed_ms(start),
                depth=depth,
            ),
        )

    research = await research_claim(
        claim=claim,
        claim_type=classification.claim_type,
        search_backend=backend,
        depth=depth,
        max_sources=max_sources,
        context=context,
    )

    synthesis = await synthesize_verdict(
        claim=claim,
        claim_type=classification.claim_type,
        evidence=research.evidence,
    )

    return FactCheckResult(
        verdict=synthesis.verdict,
        confidence=synthesis.confidence,
        summary=synthesis.summary,
        sub_claims=synthesis.sub_claims,
        sources=research.evidence,
        reasoning_trace=synthesis.reasoning_trace,
        warnings=synthesis.warnings,
        metadata=FactCheckMetadata(
            sub_claims_count=len(classification.sub_claims),
            sources_evaluated=len(research.evidence),
            search_queries_run=research.search_queries_run,
            processing_time_ms=_elapsed_ms(start),
            depth=depth,
        ),
    )


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)