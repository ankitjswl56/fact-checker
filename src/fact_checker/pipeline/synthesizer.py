from __future__ import annotations

from pydantic import BaseModel

from fact_checker.models.claim import ClaimType
from fact_checker.models.evidence import Evidence, Stance
from fact_checker.models.verdict import SynthesisResult, VerdictType
from fact_checker.pipeline.llm import complete_structured

_STANCE_SYSTEM_PROMPT = """\
You are the stance-labeling stage of a fact-checking pipeline. You are given \
a claim and a single verbatim quote from a source. Decide whether the quote:
- SUPPORTS the claim (it corroborates the claim's assertion),
- CONTRADICTS the claim (it directly disputes or disproves the assertion), or
- NEUTRAL (it does not address the claim, is inconclusive, or only provides \
  tangential context).

Judge only what the quote itself says — do not use outside knowledge. \
Respond with JSON matching the required schema only.
"""

_SYNTHESIS_SYSTEM_PROMPT = """\
You are the verdict synthesis stage of a fact-checking pipeline. You are \
given a claim, its claim type, and a pool of evidence — each item has an id, \
domain, a 0-1 credibility score, a stance (already determined) relative to \
the claim, and a verbatim quote.

Decide the overall verdict:
- TRUE: credible evidence (favor higher credibility scores) supports the \
  claim and nothing credible contradicts it.
- FALSE: credible evidence contradicts the claim and nothing credible \
  supports it.
- PARTIALLY_TRUE: some sub-claims hold and others don't, or credible sources \
  genuinely conflict with each other.
- UNVERIFIABLE: the evidence is too weak, off-topic, or low-credibility to \
  support any verdict. Never guess.

Rules:
- Weigh sources by their credibility_score — a high-credibility CONTRADICTS \
  should usually beat a low-credibility SUPPORTS, and vice versa.
- For TEMPORAL claim types, be alert to sources whose quotes describe an \
  announced-but-not-yet-effective change (e.g. a successor named but not yet \
  in office) — that is grounds for PARTIALLY_TRUE with a warning, not a flat \
  TRUE or FALSE.
- Only cite evidence ids that were given to you. Never invent an id.
- reasoning_trace must explain, in terms of the specific evidence ids and \
  their credibility scores, why the verdict was reached — including why any \
  source was trusted over a conflicting one.
- warnings should flag things like source conflicts, absence of primary \
  sources, or thin evidence — not restate the summary.

Respond with JSON matching the required schema only.
"""


class _StanceResponse(BaseModel):
    stance: Stance


async def label_stance(claim: str, quote: str) -> Stance:
    response = await complete_structured(
        system=_STANCE_SYSTEM_PROMPT,
        user=f"Claim: {claim}\nQuote: {quote}",
        response_model=_StanceResponse,
        fast=True,
    )
    return response.stance


def _format_evidence(evidence: list[Evidence]) -> str:
    lines = [
        f'- id={item.id} domain={item.domain} credibility={item.credibility_score:.2f} '
        f'stance={item.stance.value} quote="{item.quote}"'
        for item in evidence
    ]
    return "\n".join(lines)


def _drop_hallucinated_citations(result: SynthesisResult, valid_ids: set[str]) -> SynthesisResult:
    warnings = list(result.warnings)
    cleaned_sub_claims = []
    for sub in result.sub_claims:
        supporting = [i for i in sub.supporting_evidence if i in valid_ids]
        contradicting = [i for i in sub.contradicting_evidence if i in valid_ids]
        if len(supporting) != len(sub.supporting_evidence) or len(
            contradicting
        ) != len(sub.contradicting_evidence):
            warnings.append(
                f"Removed a hallucinated evidence citation on sub-claim: {sub.claim}"
            )
        cleaned_sub_claims.append(
            sub.model_copy(
                update={"supporting_evidence": supporting, "contradicting_evidence": contradicting}
            )
        )
    return result.model_copy(update={"sub_claims": cleaned_sub_claims, "warnings": warnings})


async def synthesize_verdict(
    claim: str,
    claim_type: ClaimType,
    evidence: list[Evidence],
) -> SynthesisResult:
    if not evidence:
        return SynthesisResult(
            verdict=VerdictType.UNVERIFIABLE,
            confidence=0.0,
            summary="No credible sources were found for this claim.",
            sub_claims=[],
            reasoning_trace=(
                "The research phase returned no usable evidence, so no verdict "
                "can be given without guessing."
            ),
            warnings=["No sources found"],
        )

    valid_ids = {item.id for item in evidence}
    user_prompt = (
        f"Claim: {claim}\n"
        f"Claim type: {claim_type.value}\n\n"
        f"Evidence pool:\n{_format_evidence(evidence)}\n\n"
        f"Valid evidence ids you may cite: {', '.join(sorted(valid_ids))}"
    )

    result = await complete_structured(
        system=_SYNTHESIS_SYSTEM_PROMPT,
        user=user_prompt,
        response_model=SynthesisResult,
        fast=False,
    )
    return _drop_hallucinated_citations(result, valid_ids)