from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from importlib import resources

from pydantic import BaseModel

from fact_checker.models.claim import ClaimType
from fact_checker.models.evidence import CredibilityBreakdown, SourceType

DOMAIN_TIER_SCORES: dict[int, float] = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}
SOURCE_TYPE_SCORES: dict[SourceType, float] = {
    SourceType.PRIMARY: 1.0,
    SourceType.SECONDARY: 0.6,
    SourceType.TERTIARY: 0.3,
}

# Half-life (days) for the recency decay. Stable facts decay slowly,
# fast-moving news decays quickly.
RECENCY_HALF_LIFE_DAYS: dict[ClaimType, int] = {
    ClaimType.TEMPORAL: 14,
    ClaimType.STATISTICAL: 60,
    ClaimType.IDENTITY: 180,
    ClaimType.FACTUAL: 365,
    ClaimType.OPINION: 365,
}

CITATION_DENSITY_CAP = 10

DOMAIN_WEIGHT = 0.40
SOURCE_TYPE_WEIGHT = 0.30
RECENCY_WEIGHT = 0.15
CITATION_WEIGHT = 0.15


class ScoredSource(BaseModel):
    domain: str
    credibility_score: float
    credibility_breakdown: CredibilityBreakdown
    excluded: bool = False
    exclusion_reason: str | None = None


def _normalize_domain(domain: str) -> str:
    normalized = domain.strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized


def _domain_and_parents(domain: str) -> list[str]:
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)]


@lru_cache(maxsize=1)
def _load_domain_tiers() -> dict[int, frozenset[str]]:
    raw = resources.files("fact_checker.data").joinpath("domain_tiers.json").read_text()
    data = json.loads(raw)
    return {
        1: frozenset(data.get("tier_1", [])),
        2: frozenset(data.get("tier_2", [])),
        3: frozenset(data.get("tier_3", [])),
    }


@lru_cache(maxsize=1)
def _load_satire_domains() -> frozenset[str]:
    raw = resources.files("fact_checker.data").joinpath("satire_domains.txt").read_text()
    domains = {
        line.strip().lower()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return frozenset(domains)


def is_satire_domain(domain: str) -> bool:
    satire_domains = _load_satire_domains()
    normalized = _normalize_domain(domain)
    return any(candidate in satire_domains for candidate in _domain_and_parents(normalized))


def get_domain_tier(domain: str) -> int:
    tiers = _load_domain_tiers()
    normalized = _normalize_domain(domain)
    for candidate in _domain_and_parents(normalized):
        for tier, domains in tiers.items():
            if candidate in domains:
                return tier
    return 4


def recency_score(
    published_at: datetime | None,
    claim_type: ClaimType,
    now: datetime | None = None,
) -> float:
    if published_at is None:
        return 0.5
    now = now or datetime.now(timezone.utc)
    age_days = max((now - published_at).days, 0)
    half_life = RECENCY_HALF_LIFE_DAYS.get(claim_type, 180)
    score = 0.5 ** (age_days / half_life)
    return max(0.0, min(1.0, score))


def citation_density_score(citation_count: int | None, cap: int = CITATION_DENSITY_CAP) -> float:
    if not citation_count:
        return 0.0
    return max(0.0, min(1.0, citation_count / cap))


def score_source(
    domain: str,
    source_type: SourceType,
    claim_type: ClaimType,
    published_at: datetime | None = None,
    citation_count: int | None = None,
    now: datetime | None = None,
) -> ScoredSource:
    normalized = _normalize_domain(domain)
    now = now or datetime.now(timezone.utc)
    age_days = max((now - published_at).days, 0) if published_at else None

    if is_satire_domain(normalized):
        return ScoredSource(
            domain=normalized,
            credibility_score=0.0,
            credibility_breakdown=CredibilityBreakdown(
                domain_tier=0.0,
                source_type=source_type,
                recency_days=age_days,
                citation_density=0.0,
            ),
            excluded=True,
            exclusion_reason="satire domain",
        )

    domain_tier_score = DOMAIN_TIER_SCORES[get_domain_tier(normalized)]
    source_type_score = SOURCE_TYPE_SCORES[source_type]
    rec_score = recency_score(published_at, claim_type, now)
    cit_score = citation_density_score(citation_count)

    total = (
        domain_tier_score * DOMAIN_WEIGHT
        + source_type_score * SOURCE_TYPE_WEIGHT
        + rec_score * RECENCY_WEIGHT
        + cit_score * CITATION_WEIGHT
    )

    return ScoredSource(
        domain=normalized,
        credibility_score=round(total, 4),
        credibility_breakdown=CredibilityBreakdown(
            domain_tier=domain_tier_score,
            source_type=source_type,
            recency_days=age_days,
            citation_density=cit_score,
        ),
        excluded=False,
        exclusion_reason=None,
    )