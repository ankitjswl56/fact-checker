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


# Example output, captured live on 2026-07-14 (gemini-3.1-flash-lite + Tavily):
#
# {
#   "verdict": "PARTIALLY_TRUE",
#   "confidence": 0.85,
#   "summary": "The claim correctly identifies Napoleon's defeat at the
#                Battle of Waterloo, but the assertion that he was
#                'unusually short' is a historical misconception.",
#   "sub_claims": [
#     {
#       "claim": "Napoleon Bonaparte was defeated at the Battle of Waterloo.",
#       "verdict": "TRUE",
#       "confidence": 1.0,
#       "supporting_evidence": ["src_1"]
#     },
#     {
#       "claim": "Napoleon Bonaparte was unusually short for his time.",
#       "verdict": "FALSE",
#       "confidence": 0.7
#     }
#   ],
#   "sources": [
#     {
#       "id": "src_1",
#       "url": "https://www.history.com/this-day-in-history/june-18/napoleon-defeated-at-waterloo",
#       "domain": "www.history.com",
#       "credibility_score": 0.505,
#       "stance": "NEUTRAL",
#       "quote": "At Waterloo in Belgium on June 18, 1815, Napoleon Bonaparte
#                 suffers defeat at the hands of the Duke of Wellington,
#                 bringing an end to the Napoleonic era of European history."
#     }
#   ],
#   "reasoning_trace": "The evidence (src_1) confirms Napoleon's defeat at
#     the Battle of Waterloo. However, the provided evidence does not
#     address his height. Historical consensus establishes that Napoleon
#     was approximately 5 feet 7 inches, which was average for a
#     Frenchman of his time, making the claim regarding his height
#     factually incorrect despite the accuracy of the Waterloo claim.",
#   "warnings": [
#     "The evidence pool lacks documentation concerning the sub-claim about
#      Napoleon's height, which is a widely documented historical myth."
#   ]
# }
#
# Known gap worth noting honestly: the "height" sub-claim's FALSE verdict
# was reasoned from the model's own background knowledge, not a cited
# source — no evidence was fetched/saved for that half of the claim. The
# citation-verification guard only applies to evidence that *was* saved;
# it doesn't force every sub-claim to have one.
