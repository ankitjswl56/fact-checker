"""Example: a compound claim where one part holds and another doesn't.

Run with: python examples/partially_true.py
"""

from __future__ import annotations

import asyncio

from rich.console import Console

from fact_checker.cli import print_result
from fact_checker.pipeline import fact_check

CLAIM = (
    "Napoleon Bonaparte was unusually short for his time and was defeated "
    "at the Battle of Waterloo."
)


async def main() -> None:
    console = Console()
    with console.status("[bold cyan]Fact-checking...[/bold cyan]"):
        result = await fact_check(CLAIM, depth="standard")
    print_result(console, CLAIM, result)


if __name__ == "__main__":
    asyncio.run(main())


# This claim is deliberately compound: the classifier should decompose it
# into two sub-claims — "Napoleon was unusually short" (a persistent myth;
# he was roughly average height for his era) and "defeated at Waterloo"
# (true) — which should combine into a PARTIALLY_TRUE overall verdict.
#
# No real output has been captured for this one yet — PARTIALLY_TRUE hasn't
# been exercised in a live run, deferred to the next session with fresh
# Gemini quota (see project memory). Run this script yourself to fill in
# this comment with real output once quota allows.
