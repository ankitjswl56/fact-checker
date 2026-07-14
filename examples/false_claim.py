"""Example: a widely-believed but FALSE claim, debunked by primary testimony.

Run with: python examples/false_claim.py
"""

from __future__ import annotations

import asyncio

from rich.console import Console

from fact_checker.cli import print_result
from fact_checker.pipeline import fact_check

CLAIM = "The Great Wall of China is visible from space with the naked eye."


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
#   "verdict": "FALSE",
#   "confidence": 0.95,
#   "summary": "Scientific consensus and reports from astronauts confirm
#                that the Great Wall of China is not visible to the human
#                eye from space.",
#   "sources": [
#     {
#       "id": "src_1",
#       "url": "https://www.wtamu.edu/~cbaird/sq/2012/12/11/what-makes-the-great-wall-of-china-the-only-man-made-object-visible-from-space",
#       "domain": "www.wtamu.edu",
#       "credibility_score": 0.4,
#       "stance": "CONTRADICTS",
#       "quote": "The Great Wall of China is not visible to the naked eye
#                 from space, even in low-earth orbit, according to NASA."
#     },
#     {
#       "id": "src_2",
#       "url": "https://www.skyatnightmagazine.com/space-science/can-you-see-great-wall-china-from-space",
#       "domain": "www.skyatnightmagazine.com",
#       "credibility_score": 0.445,
#       "stance": "CONTRADICTS",
#       "quote": "This was confirmed by China's own first astronaut, Yang
#                 Liwei, who orbited Earth 14 times in October 2003 ...
#                 \"The Earth looked very beautiful from space, but I did
#                 not see our Great Wall,\" he said."
#     }
#   ],
#   "reasoning_trace": "Both sources consistently refute the claim. src_1
#     cites NASA to explain the wall is too thin to be seen, while src_2
#     cites the direct testimony of China's first astronaut.",
#   "warnings": []
# }
