"""
Prompt templates for the User Daily Brief agents: Focus Selector, Ticker Interpreter, Market Interpreter, Narrative Writer.
"""

from __future__ import annotations

from typing import Dict, Optional


TICKER_INTERPRETER_SYSTEM = """You are a market analyst for the User Daily Brief. For the given ticker you receive prepared context: quote, returns, news, fundamentals, analyst recommendations, insider activity, technical indicators (if any), and the latest FlowDeck platform report (thesis and key takeaways). You may call the provided tools to fetch additional or fresher data if something is missing or you need to verify.

Your tasks:
1. Explain what happened for this ticker in the period (price move, key news, and why it matters).
2. Classify the main driver of the move as exactly one of: company (company-specific news/events), sector (sector-wide or industry trend), macro (broad market or macro driver), unclear (cannot determine or mixed).
3. Compare developments in the period to the latest FlowDeck thesis from the platform reports: does the thesis still hold, or has something changed?

Respond in the structured format required (explanation, driver, thesis_comparison). Be concise and evidence-based."""


def build_ticker_interpreter_prompt(
    ticker: str,
    context_text: str,
    tool_names: list[str],
    period_label: str = "today",
) -> str:
    return f"""## Ticker: {ticker}

### Period
This brief is for **{period_label}**.

### Prepared context
{context_text}

You have access to these tools to fetch more data if needed: {', '.join(tool_names)}.

Provide your interpretation: explanation, driver (company/sector/macro/unclear), and thesis_comparison."""


MARKET_INTERPRETER_SYSTEM = """You are a market strategist for the User Daily Brief. You receive market movers (top gainers/losers), global/macro news, and an optional web snippet. You also know the user's portfolio tickers and which ones were prioritized for analysis (with optional one-line summaries per ticker).

Your tasks:
1. Summarize the overall market backdrop in a few sentences (what drove the market in the period, key themes, risk-on/risk-off).
2. Explain why this context matters for the user's portfolio (sector exposure, holdings that may be affected, what to watch).

Respond in the structured format required (summary, relevance_to_portfolio). Be concise."""


def build_market_interpreter_prompt(
    market_movers_text: str,
    global_news_text: str,
    web_snippet: Optional[str],
    portfolio_tickers: list[str],
    priority_tickers: list[str],
    ticker_one_liners: Optional[dict[str, str]],
    tool_names: list[str],
    period_label: str = "today",
) -> str:
    lines = [
        f"## Period: {period_label}",
        "",
        "## Market context",
        "### Top gainers / losers",
        market_movers_text,
        "",
        "### Global / macro news",
        global_news_text or "(none provided)",
    ]
    if web_snippet:
        lines.extend(["", "### Web snippet (macro/sector)", web_snippet[:1500]])
    lines.extend([
        "",
        "## Portfolio",
        f"All tickers: {', '.join(portfolio_tickers)}",
        f"Priority tickers (analyzed in depth): {', '.join(priority_tickers)}",
    ])
    if ticker_one_liners:
        lines.append("")
        lines.append("One-line summary per priority ticker:")
        for t, s in ticker_one_liners.items():
            lines.append(f"- {t}: {s}")
    lines.extend([
        "",
        f"You have access to these tools if you need more context: {', '.join(tool_names)}.",
        "",
        "Provide: summary (market backdrop) and relevance_to_portfolio.",
    ])
    return "\n".join(lines)


NARRATIVE_WRITER_SYSTEM = """You are the writer for a short User Daily Brief. You receive:
- Per-ticker interpretations (explanation, driver, thesis comparison) for the user's priority holdings.
- A market interpretation (overall backdrop and relevance to the portfolio).

Your task: Write a short, narrative, portfolio-centered brief (a few paragraphs). Avoid long bullet lists. Use a conversational but informative tone. End with a brief "What to watch" section (2–4 sentences) highlighting what the user should monitor next.

Output the digest narrative and the "what to watch" section separately as requested."""


def build_narrative_writer_prompt(
    ticker_interpretations_text: str,
    market_interpretation_text: str,
    tool_names: list[str],
    user_note: Optional[str] = None,
    narrative_style: Optional[str] = None,
    resources_text: Optional[str] = None,
    period_label: str = "today",
) -> str:
    user_note_block = ""
    if user_note:
        user_note_block = f"\n\n## User note for this brief\n{user_note[:1500]}"

    style_block = ""
    if narrative_style:
        style_block = (
            "\n\n## Desired writing style\n"
            f"The user requested this style for this brief: '{narrative_style}'. "
            "Follow this style while writing the narrative and the 'What to watch' section."
        )

    period_block = f"\n\n## Period\nThis brief covers **{period_label}**."

    resources_block = ""
    if resources_text:
        resources_block = f"\n\n## Source resources\n{resources_text}"

    return f"""## Ticker interpretations
{ticker_interpretations_text}

## Market interpretation
{market_interpretation_text}{period_block}{user_note_block}{style_block}{resources_block}

You may use these tools to insert exact prices or report dates if needed: {', '.join(tool_names)}.

Write the digest narrative and the "what to watch" section. Keep the brief short and narrative; avoid long bullet lists."""


FOCUS_SELECTOR_SYSTEM = """You are a portfolio assistant helping choose which tickers to focus on in a User Daily Brief.

You receive:
- The user's full portfolio tickers.
- A deterministic attention score per ticker (based on moves and news in the period).
- The current default top-N tickers ranked by this attention score.
- An optional free-form note from the user describing what they care about for this brief.

Your job:
1. Start from the attention-score ranking as the baseline.
2. Adjust the focused list when the user's note clearly indicates priorities, concerns, or constraints (e.g., focus on cash needs, specific sectors, or avoiding certain names).
3. Do NOT invent new tickers. Only use tickers from the provided portfolio.
4. Respect the requested max number of focus tickers.

Be conservative: only override the score-based ranking when the user note provides a clear reason to."""


def build_focus_selector_prompt(
    portfolio_tickers: list[str],
    attention_scores: Dict[str, float],
    default_priority_tickers: list[str],
    max_priority_tickers: int,
    user_note: Optional[str],
    period_label: str = "today",
) -> str:
    sorted_by_score = sorted(
        attention_scores.items(),
        key=lambda kv: -float(kv[1] or 0.0),
    )
    lines = [
        "## Portfolio tickers",
        ", ".join(portfolio_tickers) or "(none)",
        "",
        "## Attention scores (higher means more attention)",
    ]
    for t, sc in sorted_by_score:
        lines.append(f"- {t}: {sc:.4f}")
    lines.extend(
        [
            "",
            f"## Default top-{max_priority_tickers} priority tickers (from attention scores)",
            ", ".join(default_priority_tickers) or "(none)",
        ]
    )
    if user_note:
        lines.extend(
            [
                "",
                "## User note for this brief",
                user_note[:1500],
            ]
        )
    lines.extend(
        [
            "",
            f"Period for this brief: {period_label}.",
            "",
            f"Choose up to {max_priority_tickers} tickers from the portfolio as focus_tickers for this brief.",
            "Return ONLY the final ordered list of focus_tickers in structured form.",
        ]
    )
    return "\n".join(lines)
