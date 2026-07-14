"""Example: a claim with no possible public evidence trail.

Run with: python examples/unverifiable.py
"""

from __future__ import annotations

import asyncio

from rich.console import Console

from fact_checker.cli import print_result
from fact_checker.pipeline import fact_check

CLAIM = "My neighbor's cat sneezed exactly 47 times last Tuesday."


async def main() -> None:
    console = Console()
    with console.status("[bold cyan]Fact-checking...[/bold cyan]"):
        result = await fact_check(CLAIM, depth="quick")
    print_result(console, CLAIM, result)


if __name__ == "__main__":
    asyncio.run(main())


# Real captured output, live on 2026-07-14 (gemini-3.1-flash-lite + Tavily) —
# from a *different* claim ("Tim Cook is the CEO of Apple") than the one
# above. That run is kept here deliberately: it's a genuine, unplanned
# capture of the UNVERIFIABLE fail-safe firing on a claim that is normally
# easy to verify, because that particular research attempt didn't land on a
# citable source within its iteration budget. It's included as honest
# evidence that the system reports UNVERIFIABLE rather than guessing when
# research comes up empty — not as a demonstration of the claim above, which
# has not yet been run live.
#
# {
#   "verdict": "UNVERIFIABLE",
#   "confidence": 0.0,
#   "summary": "No credible sources were found for this claim.",
#   "sources": [],
#   "reasoning_trace": "The research phase returned no usable evidence, so
#     no verdict can be given without guessing.",
#   "warnings": ["No sources found"],
#   "metadata": {
#     "sources_evaluated": 0,
#     "search_queries_run": ["who is the current CEO of Apple?"],
#     "processing_time_ms": 9562
#   }
# }
