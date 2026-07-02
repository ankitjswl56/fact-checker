from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from fact_checker.models.evidence import Evidence


class VerdictType(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    UNVERIFIABLE = "UNVERIFIABLE"
    OPINION = "OPINION"


class SubClaimResult(BaseModel):
    claim: str = Field(min_length=1)
    verdict: VerdictType
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Evidence ids that support this sub-claim"
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list, description="Evidence ids that contradict this sub-claim"
    )


class FactCheckMetadata(BaseModel):
    sub_claims_count: int = Field(ge=0)
    sources_evaluated: int = Field(ge=0)
    search_queries_run: list[str] = Field(default_factory=list)
    processing_time_ms: int = Field(ge=0)
    depth: Literal["quick", "standard", "deep"]


class FactCheckResult(BaseModel):
    verdict: VerdictType
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    sub_claims: list[SubClaimResult] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)
    reasoning_trace: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    metadata: FactCheckMetadata