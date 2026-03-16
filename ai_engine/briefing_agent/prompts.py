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


# ---------------------------------------------------------------------------
# Narrative writer: output field tokens and style blocks
# ---------------------------------------------------------------------------

# Phrase used in every style block so the model maps content to the right output fields.
_OUTPUT_FIELDS_BASIC = "Output the digest narrative and the what_to_watch section as the corresponding fields: narrative, what_to_watch."
_OUTPUT_FIELDS_STRUCTURED = "Output each section as the corresponding fields: market_highlights, key_signals, what_to_watch, risks_opportunities."

# Shared closing for basic-style blocks (narrative + what_to_watch).
def _basic_tail(what_to_watch_sentences: str = "2–4 sentences") -> str:
    return f'End with a brief "What to watch" section ({what_to_watch_sentences}). {_OUTPUT_FIELDS_BASIC}'


# Styles that use four-section structured output; agent uses the structured schema for these.
STRUCTURED_OUTPUT_STYLES: set[str] = {"technical"}

# Style key normalization: UI sends "default" for Balanced; accept common typos.
_STYLE_ALIASES: Dict[str, str] = {"default": "balanced", "profesional": "professional"}


def _normalize_style_key(narrative_style: Optional[str]) -> Optional[str]:
    """Return lowercase style key for lookup, or None if empty."""
    if not narrative_style or not narrative_style.strip():
        return None
    key = narrative_style.strip().lower()
    return _STYLE_ALIASES.get(key, key)


# Default block when no style or unknown style: short narrative + what_to_watch.
BASIC_NARRATIVE_BLOCK = f"""Write a short, narrative, portfolio-centered brief (a few paragraphs). Use a conversational but informative tone. Avoid long bullet lists. End with a brief "What to watch" section (2–4 sentences) highlighting what the user should monitor next.

{_OUTPUT_FIELDS_BASIC}"""


# Style name (lowercase) -> full block injected into the narrative writer prompt.
NARRATIVE_STYLE_BLOCKS: Dict[str, str] = {
    "balanced": f"""**Style: Balanced.** Mix context with actionable takeaways. Cover what happened and what it means without leaning too narrative or too terse. Suitable for readers who want both story and next steps in one flow. Keep to a few paragraphs plus a short forward-looking close.

{_basic_tail()}""",
    "concise": f"""**Style: Concise.** Short and scannable. Lead with the most important moves and implications; cut filler and repetition. Use short sentences and clear subordination. Suitable for busy readers who want the gist in under a minute.

{_basic_tail("2–3 sentences")}""",
    "professional": f"""**Style: Professional.** Formal, measured tone. Emphasize clarity and objectivity; avoid colloquialisms and hype. Suitable for institutional or advisory contexts. Structure as a brief report: context, interpretation, and forward-looking view.

{_basic_tail()}""",
    "technical": f"""**Style: Technical.** Use precise language; focus on data, levels, and catalysts. Suitable for active traders who want a clear, scannable structure.

Write the brief in exactly four sections, each as a short block of text (a few sentences). Avoid long bullet lists. Each section will be stored with the special tokens market_highlights, key_signals, what_to_watch, risks_opportunities so that formatting can be applied by section.

1. **Market Highlights** — What happened (key price moves, headlines, and market action in the period).
2. **Key Signals** — What it means (interpretation: drivers, themes, and implications for the user's portfolio).
3. **What to Watch** — Coming catalysts (earnings, data releases, events, or levels to monitor next).
4. **Risks & Opportunities** — Trading implications (concrete risks and opportunities; how to think about positioning).

{_OUTPUT_FIELDS_STRUCTURED}""",
}

NARRATIVE_WRITER_SYSTEM = """You are the writer for a short User Daily Brief. You receive:
- Per-ticker interpretations (explanation, driver, thesis comparison) for the user's priority holdings.
- A market interpretation (overall backdrop and relevance to the portfolio).

A style/structure block will be injected below: follow it exactly for tone, structure, and output fields."""


def get_style_block_for_narrative(narrative_style: Optional[str]) -> str:
    """Return the block to inject into the narrative writer prompt. Uses BASIC_NARRATIVE_BLOCK when no/unknown style."""
    key = _normalize_style_key(narrative_style)
    if key is not None and key in NARRATIVE_STYLE_BLOCKS:
        return NARRATIVE_STYLE_BLOCKS[key]
    return BASIC_NARRATIVE_BLOCK


def style_uses_structured_output(narrative_style: Optional[str]) -> bool:
    """True if this style uses the four-section structured output (market_highlights, key_signals, what_to_watch, risks_opportunities)."""
    key = _normalize_style_key(narrative_style)
    return key is not None and key in STRUCTURED_OUTPUT_STYLES


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

    style_block = get_style_block_for_narrative(narrative_style)

    period_block = f"\n\n## Period\nThis brief covers **{period_label}**."

    resources_block = ""
    if resources_text:
        resources_block = f"\n\n## Source resources\n{resources_text}"

    return f"""## Ticker interpretations
{ticker_interpretations_text}

## Market interpretation
{market_interpretation_text}{period_block}{user_note_block}{resources_block}

## Style and structure
{style_block}

You may use these tools to insert exact prices or report dates if needed: {', '.join(tool_names)}."""


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
