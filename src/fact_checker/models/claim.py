from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ClaimType(StrEnum):
    FACTUAL = "FACTUAL"
    STATISTICAL = "STATISTICAL"
    TEMPORAL = "TEMPORAL"
    OPINION = "OPINION"
    IDENTITY = "IDENTITY"


class SubClaim(BaseModel):
    text: str = Field(min_length=1, description="Atomic, independently verifiable claim")
    claim_type: ClaimType


class ClaimClassification(BaseModel):
    original_claim: str = Field(min_length=1)
    claim_type: ClaimType
    is_checkable: bool = Field(
        description="False for OPINION claims — no verdict should be attempted"
    )
    sub_claims: list[SubClaim] = Field(default_factory=list)
    reasoning: str | None = Field(
        default=None, description="Why the claim was classified/decomposed this way"
    )
