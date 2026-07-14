"""Example: a straightforwardly TRUE claim, backed by independent sources.

Run with: python examples/true_claim.py
"""

from __future__ import annotations

import asyncio

from rich.console import Console

from fact_checker.cli import print_result
from fact_checker.pipeline import fact_check

CLAIM = "The Eiffel Tower is located in Paris, France."


async def main() -> None:
    console = Console()
    with console.status("[bold cyan]Fact-checking...[/bold cyan]"):
        result = await fact_check(CLAIM, depth="quick")
    print_result(console, CLAIM, result)


if __name__ == "__main__":
    asyncio.run(main())


# Example output, captured live on 2026-07-14 (gemini-3.1-flash-lite + Tavily):
#
# {
#   "verdict": "TRUE",
#   "confidence": 1.0,
#   "summary": "The Eiffel Tower is located in Paris, France, as confirmed by
#                both official and encyclopedic sources.",
#   "sources": [
#     {
#       "id": "src_1",
#       "url": "https://www.toureiffel.paris/en/access-map",
#       "domain": "www.toureiffel.paris",
#       "credibility_score": 0.625,
#       "stance": "SUPPORTS",
#       "quote": "The Eiffel Tower is located in the heart of Paris, in the
#                 7th arrondissement, on the Champ de Mars, and is very easy
#                 to access. Its official address is: 5 avenue Anatole
#                 France, 75007 Paris, France."
#     },
#     {
#       "id": "src_2",
#       "url": "https://www.britannica.com/topic/Eiffel-Tower-Paris-France",
#       "domain": "www.britannica.com",
#       "credibility_score": 0.625,
#       "stance": "SUPPORTS",
#       "quote": "The Eiffel Tower can be found on the Champs de Mars at 5
#                 Avenue Anatole France within the 7th arrondissement of
#                 Paris."
#     }
#   ],
#   "reasoning_trace": "Both evidence sources (src_1 and src_2) possess high
#     credibility (0.62) and provide explicit confirmation that the Eiffel
#     Tower is located in the 7th arrondissement of Paris, France. There is
#     no contradicting evidence.",
#   "warnings": []
# }
