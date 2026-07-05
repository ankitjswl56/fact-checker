from __future__ import annotations

from fact_checker.models.claim import ClaimClassification
from fact_checker.pipeline.llm import complete_structured

_SYSTEM_PROMPT = """\
You are the claim classification stage of a fact-checking pipeline. Given a \
single claim, classify it and, if it bundles multiple independently-checkable \
assertions, decompose it into atomic sub-claims.

Claim types (choose exactly one for the overall claim, and one per sub-claim):
- FACTUAL: a verifiable true/false assertion about the world (e.g. "the Great \
  Wall of China is visible from space").
- STATISTICAL: a claim built on a number, rate, or measurement that requires \
  an original data source to verify (e.g. "unemployment rose 2% last year").
- TEMPORAL: a claim about a status or state that is time-sensitive and can \
  change ("X is currently the CEO of Y", "Z is the reigning champion").
- OPINION: a subjective judgment, prediction, or value statement that cannot \
  be empirically verified (e.g. "this is the best policy").
- IDENTITY: a claim about who a specific person or entity is, or a fact tied \
  to their identity, where privacy is a relevant concern.

Rules:
- Only decompose a claim into sub_claims if it bundles two or more distinct, \
  independently-checkable assertions (e.g. joined by "and", or listing \
  several facts). A single assertion should have an empty sub_claims list.
- is_checkable is false ONLY when the overall claim_type is OPINION. Every \
  other claim type is checkable, even if evidence later turns out to be hard \
  to find (that is a research problem, not a classification problem).
- Do not soften or hedge the claim_type choice — pick the single best fit.
- reasoning should be one or two sentences explaining the classification, \
  not a restatement of the claim.

Respond with JSON matching the required schema only.
"""


async def classify_claim(claim: str) -> ClaimClassification:
    return await complete_structured(
        system=_SYSTEM_PROMPT,
        user=claim,
        response_model=ClaimClassification,
        fast=True,
    )