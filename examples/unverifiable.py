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


# Example output, captured live on 2026-07-14 (gemini-3.1-flash-lite + Tavily),
# for this exact claim:
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
#     "search_queries_run": ["\"neighbor's cat\" \"47 times\" \"last Tuesday\""],
#     "processing_time_ms": 5273
#   }
# }
