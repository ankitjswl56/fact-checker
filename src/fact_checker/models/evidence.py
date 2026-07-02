from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SourceType(StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    TERTIARY = "TERTIARY"


class Stance(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


class CredibilityBreakdown(BaseModel):
    domain_tier: float = Field(ge=0.0, le=1.0, description="Domain tier signal, 0-1")
    source_type: SourceType
    recency_days: int | None = Field(
        default=None, ge=0, description="Age of the source in days, if known"
    )
    citation_density: float = Field(ge=0.0, le=1.0, description="Outbound citation signal, 0-1")


class Evidence(BaseModel):
    id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    credibility_score: float = Field(ge=0.0, le=1.0)
    credibility_breakdown: CredibilityBreakdown
    stance: Stance
    quote: str = Field(
        min_length=1,
        description="Verbatim excerpt from the source — required, no exceptions",
    )
    retrieved_at: datetime

    @field_validator("quote")
    @classmethod
    def quote_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("quote must be a non-empty verbatim excerpt")
        return value