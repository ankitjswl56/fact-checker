from __future__ import annotations

import argparse
import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fact_checker.models.verdict import FactCheckResult, VerdictType
from fact_checker.pipeline import fact_check

VERDICT_STYLES: dict[VerdictType, str] = {
    VerdictType.TRUE: "bold white on dark_green",
    VerdictType.FALSE: "bold white on dark_red",
    VerdictType.PARTIALLY_TRUE: "bold black on yellow",
    VerdictType.UNVERIFIABLE: "bold white on grey30",
    VerdictType.OPINION: "bold white on blue",
}

QUOTE_PREVIEW_CHARS = 100


def print_result(console: Console, claim: str, result: FactCheckResult) -> None:
    style = VERDICT_STYLES.get(result.verdict, "bold white")
    verdict_badge = f" {result.verdict.value} "
    console.print(
        Panel(
            f"[{style}]{verdict_badge}[/{style}]  confidence: {result.confidence:.0%}",
            title=claim,
            title_align="left",
        )
    )
    console.print(result.summary, style="italic")

    if result.sub_claims:
        sub_table = Table(title="Sub-claims", show_lines=True)
        sub_table.add_column("Claim")
        sub_table.add_column("Verdict")
        sub_table.add_column("Confidence")
        for sub in result.sub_claims:
            sub_style = VERDICT_STYLES.get(sub.verdict, "bold white")
            sub_table.add_row(sub.claim, f"[{sub_style}]{sub.verdict.value}[/{sub_style}]", f"{sub.confidence:.0%}")
        console.print(sub_table)

    if result.sources:
        table = Table(title="Sources", show_lines=True)
        table.add_column("Domain")
        table.add_column("Credibility")
        table.add_column("Stance")
        table.add_column("Quote")
        for src in result.sources:
            quote = src.quote
            if len(quote) > QUOTE_PREVIEW_CHARS:
                quote = quote[:QUOTE_PREVIEW_CHARS] + "..."
            table.add_row(src.domain, f"{src.credibility_score:.2f}", src.stance.value, quote)
        console.print(table)

    if result.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            console.print(f"  - {warning}")

    console.print("\n[bold]Reasoning:[/bold]")
    console.print(result.reasoning_trace)

    meta = result.metadata
    console.print(
        f"\n[dim]{meta.sources_evaluated} sources evaluated, "
        f"{len(meta.search_queries_run)} searches run, "
        f"{meta.processing_time_ms}ms, depth={meta.depth}[/dim]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fact-checker",
        description="AI-powered fact-checking pipeline with cited, credibility-scored verdicts.",
    )
    parser.add_argument("claim", help="The claim to fact-check")
    parser.add_argument(
        "--depth",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="How much research effort to spend (default: standard)",
    )
    parser.add_argument(
        "--context",
        default=None,
        help='Optional grounding context, e.g. "said by X in a 2024 interview"',
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=8,
        help="Maximum number of sources to cite (default: 8)",
    )
    args = parser.parse_args()

    console = Console()
    with console.status("[bold cyan]Fact-checking...[/bold cyan]"):
        result = asyncio.run(
            fact_check(
                args.claim,
                depth=args.depth,
                context=args.context,
                max_sources=args.max_sources,
            )
        )

    print_result(console, args.claim, result)


if __name__ == "__main__":
    main()
