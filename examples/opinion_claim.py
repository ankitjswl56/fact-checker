"""Example: a subjective claim that short-circuits before any research runs.

Run with: python examples/opinion_claim.py
"""

from __future__ import annotations

import asyncio

from rich.console import Console

from fact_checker.cli import print_result
from fact_checker.pipeline import fact_check

CLAIM = "Pizza is the best food in the world."


async def main() -> None:
    console = Console()
    with console.status("[bold cyan]Fact-checking...[/bold cyan]"):
        result = await fact_check(CLAIM, depth="quick")
    print_result(console, CLAIM, result)


if __name__ == "__main__":
    asyncio.run(main())


# Example output, captured live on 2026-07-14 (gemini-3.1-flash-lite):
#
# {
#   "verdict": "OPINION",
#   "confidence": 1.0,
#   "summary": "This is a subjective claim and cannot be empirically
#                fact-checked.",
#   "sources": [],
#   "reasoning_trace": "The claim expresses a subjective preference that
#     cannot be empirically measured or proven as a universal fact.",
#   "warnings": [],
#   "metadata": {
#     "sources_evaluated": 0,
#     "search_queries_run": [],
#     "processing_time_ms": 3429
#   }
# }
#
# Note: OPINION claims never reach the research loop at all — the
# classifier stage alone is enough to short-circuit, which is why this
# is the cheapest and fastest of the five example verdicts.
