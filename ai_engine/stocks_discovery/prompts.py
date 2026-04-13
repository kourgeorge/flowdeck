"""LLM prompts for the standalone stocks discovery writer."""

from __future__ import annotations

STOCKS_DISCOVERY_WRITER_SYSTEM = """You are FlowDeck's Stocks Discovery writer.

You receive:
- The user's portfolio tickers (for exclusion only — do not treat them as discovery targets).
- An interest cluster (sectors/industries inferred from their holdings).
- Non-portfolio tickers that scored highly on FlowDeck's deterministic market-event signals, with event details.

Your job is to produce a single **markdown** report for the end user that:
1. States whether the scan is Daily or Weekly and the as-of date.
2. Briefly explains the interest cluster (sectors/industries).
3. For each discovered ticker, explains **why it surfaced** using only the evidence provided (signals, scores, sector/industry). Do not invent catalysts or prices not in the evidence.
4. If no tickers passed the threshold, explain that clearly and suggest subscribing to more tickers or trying a weekly span.

Tone: concise, professional. Use `## Ticker` sections for each symbol. Do not output JSON — only markdown."""


def build_stocks_discovery_writer_prompt(
    *,
    span_label: str,
    digest_date: str,
    portfolio_tickers: list[str],
    interest_cluster: dict,
    evidence_markdown: str,
) -> str:
    cluster_lines = []
    if interest_cluster.get("sectors"):
        cluster_lines.append("Sectors: " + ", ".join(str(s) for s in interest_cluster["sectors"][:5]))
    if interest_cluster.get("industries"):
        cluster_lines.append("Industries: " + ", ".join(str(i) for i in interest_cluster["industries"][:5]))
    cluster_block = "\n".join(cluster_lines) if cluster_lines else "(empty cluster)"

    return f"""## Scan
- **Span:** {span_label}
- **As-of date:** {digest_date}

## Portfolio (exclude from discovery; context only)
{", ".join(portfolio_tickers) if portfolio_tickers else "(none)"}

## Interest cluster
{cluster_block}

## Ranked non-portfolio candidates (deterministic evidence)
{evidence_markdown}

Write the full user-facing markdown report now."""
