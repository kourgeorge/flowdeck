"""
Prompt templates for the User Daily Brief agents: Focus Selector, Ticker Interpreter, Market Interpreter, Narrative Writer.
"""

from __future__ import annotations

import re
from typing import Dict, Optional


TICKER_INTERPRETER_SYSTEM = """You are a market analyst for the User Daily Brief. For the given ticker you receive prepared context: deterministic event detections from price/fundamental data, quote, returns, news, fundamentals, analyst recommendations, insider activity, technical indicators (if any), and the latest FlowDeck platform report (thesis and key takeaways). You may also receive the user's saved investor profile and AI memory. Use that profile to choose the most relevant angle, risk framing, and decision-useful interpretation for this user. You may call the provided tools to fetch additional or fresher data if something is missing or you need to verify.

Your tasks:
1. Explain what happened for this ticker in the period, starting from the deterministic event detections when they are present.
2. Classify the main driver of the move as exactly one of: company (company-specific news/events), sector (sector-wide or industry trend), macro (broad market or macro driver), unclear (cannot determine or mixed).
3. Compare developments in the period to the latest FlowDeck thesis from the platform reports: does the thesis still hold, or has something changed?

Respond in the structured format required (explanation, driver, thesis_comparison). Be concise and evidence-based."""


def build_ticker_interpreter_prompt(
    ticker: str,
    context_text: str,
    tool_names: list[str],
    user_context_snapshot: Optional[str] = None,
    period_label: str = "today",
) -> str:
    user_profile_block = ""
    if user_context_snapshot:
        user_profile_block = (
            "\n\n### User profile and saved memory\n"
            "Personalize the interpretation to this profile when deciding what matters most.\n"
            f"{user_context_snapshot[:2000]}"
        )

    return f"""## Ticker: {ticker}

### Period
This brief is for **{period_label}**.

### Prepared context
{context_text}{user_profile_block}

You have access to these tools to fetch more data if needed: {', '.join(tool_names)}.

Provide your interpretation: explanation, driver (company/sector/macro/unclear), and thesis_comparison."""


MARKET_INTERPRETER_SYSTEM = """You are a market strategist for the User Daily Brief. You receive market movers (top gainers/losers), global/macro news, and an optional web snippet. You also know the user's portfolio tickers and which ones were prioritized for analysis (with optional one-line summaries per ticker). You may receive the user's saved investor profile and AI memory; use that to decide which macro themes, risks, and opportunities are most relevant.

Your tasks:
1. Summarize the overall market backdrop in a few sentences (what drove the market in the period, key themes, risk-on/risk-off).
2. Call out the most notable movers and the most important recent market news if they materially shaped the session.
   When citing movers, mention both the company name and ticker if available.
3. Explain why this context matters for the user's portfolio. If the portfolio is empty, explain why it matters for a general equities investor instead.

Respond in the structured format required (summary, relevance_to_portfolio). Be concise."""


def build_market_interpreter_prompt(
    market_movers_text: str,
    global_news_text: str,
    web_snippet: Optional[str],
    portfolio_tickers: list[str],
    priority_tickers: list[str],
    ticker_one_liners: Optional[dict[str, str]],
    tool_names: list[str],
    user_context_snapshot: Optional[str] = None,
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
        f"All tickers: {', '.join(portfolio_tickers) or '(none)'}",
        f"Priority tickers (analyzed in depth): {', '.join(priority_tickers) or '(none)'}",
    ])
    if ticker_one_liners:
        lines.append("")
        lines.append("One-line summary per priority ticker:")
        for t, s in ticker_one_liners.items():
            lines.append(f"- {t}: {s}")
    if user_context_snapshot:
        lines.extend(
            [
                "",
                "## User profile and saved memory",
                "Use this to judge which market developments matter most for this user.",
                user_context_snapshot[:2000],
            ]
        )
    lines.extend([
        "",
        f"You have access to these tools if you need more context: {', '.join(tool_names)}.",
        "",
        "Even if the portfolio is empty or there are no priority tickers, provide a useful market-level briefing.",
        "Provide: summary (market backdrop, notable movers, important recent news) and relevance_to_portfolio.",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Narrative writer: base prompt + style overlay composition
# ---------------------------------------------------------------------------

# Phrase used in every style block so the model maps content to the right output fields.
_OUTPUT_FIELDS_BASIC = "Output the digest narrative and the what_to_watch section as the corresponding fields: narrative, what_to_watch."
_OUTPUT_FIELDS_STRUCTURED = "Output each section as the corresponding fields: market_highlights, key_signals, what_to_watch, risks_opportunities."

# Shared closing for basic-style blocks (narrative + what_to_watch).
def _basic_tail(what_to_watch_sentences: str = "2–4 sentences") -> str:
    return f'End with a brief "What to watch" section ({what_to_watch_sentences}). {_OUTPUT_FIELDS_BASIC}'


# Styles that use four-section structured output; agent uses the structured schema for these.
STRUCTURED_OUTPUT_STYLES: set[str] = {"concise", "technical"}

# Style key normalization: UI sends "default" for Balanced; accept common typos.
_STYLE_ALIASES: Dict[str, str] = {"default": "balanced", "profesional": "professional"}


def _normalize_style_key(narrative_style: Optional[str]) -> Optional[str]:
    """Return lowercase style key for lookup, or None if empty."""
    if not narrative_style or not narrative_style.strip():
        return None
    key = narrative_style.strip().lower()
    return _STYLE_ALIASES.get(key, key)


def get_normalized_narrative_style(narrative_style: Optional[str]) -> Optional[str]:
    """Public helper for normalized narrative style lookup."""
    return _normalize_style_key(narrative_style)


# Shared narrative-writing instructions. Style prompts are appended to this block.
BASIC_NARRATIVE_WRITING_PROMPT = """Write the brief as valid Markdown. Write a short, narrative brief that starts with the overall market backdrop, notable movers, and important recent news, then connects that context to the user's holdings when relevant. When making a company-specific or stock-specific claim, explicitly name the relevant ticker symbol the claim refers to. If there are no ticker interpretations, write a market-only brief."""


# Default style overlay when no style or unknown style is provided.
DEFAULT_NARRATIVE_STYLE_PROMPT = f"""Use a conversational but informative tone. Keep the output as valid Markdown. End with a brief "What to watch" section (2–4 sentences) highlighting what the user should monitor next.

{_OUTPUT_FIELDS_BASIC}"""


# Style name (lowercase) -> style overlay appended to the base narrative-writing prompt.
NARRATIVE_STYLE_PROMPTS: Dict[str, str] = {
    "balanced": f"""**Style overlay: Balanced.** Mix context with actionable takeaways. Cover what happened and what it means without leaning too narrative or too terse. Suitable for readers who want both story and next steps in one flow. Keep to a few paragraphs plus a short forward-looking close. Return valid Markdown.

{_basic_tail()}""",
    "concise": f"""**Style overlay: Concise.** Short and scannable. Lead with the market backdrop, the most important movers, and the main implications; cut filler and repetition. Suitable for busy readers who want the gist in under a minute.

Write the brief in exactly four sections, and make each section a valid Markdown bullet list of key insights with 2–3 bullets. Every bullet must begin with `- `. Do not write prose paragraphs. Each bullet must be a single short sentence. Prefer about 8-16 words. Avoid long clauses, stacked qualifiers, and multi-part sentences.

1. **Market Highlights** — What happened in the market and the most notable movers.
2. **Key Signals** — What it means for the user's portfolio and the main drivers/themes.
3. **What to Watch** — The next catalysts, levels, events, or developments to monitor.
4. **Risks & Opportunities** — The clearest downside risks and upside setups from here.

{_OUTPUT_FIELDS_STRUCTURED}""",
    "professional": f"""**Style overlay: Professional.** Formal, measured tone. Open with a high-level market summary, then move to portfolio implications. Emphasize clarity and objectivity; avoid colloquialisms and hype. Suitable for institutional or advisory contexts. Structure as a brief report: context, interpretation, and forward-looking view. Return valid Markdown.

{_basic_tail()}""",
    "technical": f"""**Style overlay: Technical.** Use precise language; focus on data, levels, and catalysts. Suitable for active traders who want a clear, scannable structure. Return valid Markdown.

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
- The user's saved investor profile and AI memory, when available.
- An optional user note with explicit preferences for this brief.
- A summary of the main points already covered in the user's last few briefs, when available.

A base narrative-writing prompt and a style overlay will be injected below: follow both exactly for tone, structure, and output fields.

Hard requirements:
- Return valid Markdown only.
- Treat the user note as a high-priority instruction for this specific brief.
- Treat the saved investor profile and AI memory as durable preferences unless the user note overrides them for this run.
- If the user note requests a language, write the entire brief in that language.
- If the user note requests emphasis, focus, or constraints, reflect that clearly in the brief unless it conflicts with the required format or the available evidence.
- Always anchor the brief in the market interpretation first. The reader should immediately understand what is happening in the market overall.
- Include notable movers and important recent news when they are available.
- When the brief references specific movers, include the company name and ticker if available.
- If ticker interpretations exist, use them to personalize the brief after the market-level summary.
- If ticker interpretations do not exist, still produce a complete market briefing rather than a placeholder.
- If a recent-briefs summary is provided, use it for continuity and avoid repeating those already-covered points unless today's evidence materially changes them or they remain central with a genuinely new angle."""


RECENT_BRIEFS_SUMMARIZER_SYSTEM = """You summarize recent User Daily Briefs so the next brief avoids repetition.

You receive the user's last few stored briefs, newest first. Extract the main points that have already been covered across those briefs.

Requirements:
- Focus on the recurring market regime, repeated portfolio implications, and already-covered watch items.
- Compress overlapping ideas into a short summary.
- Do not invent new facts.
- Do not recommend trades.
- Keep the summary concise and concrete so another writer can avoid repeating it."""


def get_style_prompt_for_narrative(narrative_style: Optional[str]) -> str:
    """Return the style overlay appended to the base narrative-writing prompt."""
    key = get_normalized_narrative_style(narrative_style)
    if key is not None and key in NARRATIVE_STYLE_PROMPTS:
        return NARRATIVE_STYLE_PROMPTS[key]
    return DEFAULT_NARRATIVE_STYLE_PROMPT


def build_narrative_prompt_instructions(narrative_style: Optional[str]) -> str:
    """Compose the final narrative-writing instructions from the base prompt and style overlay."""
    style_prompt = get_style_prompt_for_narrative(narrative_style)
    return (
        "### Base narrative prompt\n"
        f"{BASIC_NARRATIVE_WRITING_PROMPT}\n\n"
        "### Style prompt\n"
        f"{style_prompt}"
    )


def style_uses_structured_output(narrative_style: Optional[str]) -> bool:
    """True if this style uses the four-section structured output (market_highlights, key_signals, what_to_watch, risks_opportunities)."""
    key = get_normalized_narrative_style(narrative_style)
    return key is not None and key in STRUCTURED_OUTPUT_STYLES


def build_narrative_writer_prompt(
    ticker_interpretations_text: str,
    market_interpretation_text: str,
    tool_names: list[str],
    user_context_snapshot: Optional[str] = None,
    user_note: Optional[str] = None,
    narrative_style: Optional[str] = None,
    recent_briefs_summary: Optional[str] = None,
    resources_text: Optional[str] = None,
    period_label: str = "today",
) -> str:
    user_profile_block = ""
    if user_context_snapshot:
        user_profile_block = (
            "\n\n## Saved investor profile and AI memory\n"
            "Treat this as durable personalization context for tone, emphasis, risk framing, and relevance.\n"
            f"{user_context_snapshot[:2200]}"
        )

    user_note_block = ""
    if user_note:
        user_note_block = (
            "\n\n## User note for this brief\n"
            "This note is a high-priority instruction for this run. Follow it closely for language, emphasis, and framing unless it conflicts with the required output structure or the evidence.\n"
            f"{user_note[:1500]}"
        )

    recent_briefs_block = ""
    if recent_briefs_summary:
        recent_briefs_block = (
            "\n\n## Summary of recent briefs\n"
            "These are the main points that were already covered recently. Avoid repeating them unless today's evidence materially changes them or you have a genuinely new angle.\n"
            f"{recent_briefs_summary[:2500]}"
        )

    narrative_prompt_instructions = build_narrative_prompt_instructions(narrative_style)

    period_block = f"\n\n## Period\nThis brief covers **{period_label}**."

    resources_block = ""
    if resources_text:
        resources_block = f"\n\n## Source resources\n{resources_text}"

    return f"""## Ticker interpretations
{ticker_interpretations_text}

## Market interpretation
{market_interpretation_text}{period_block}{user_profile_block}{user_note_block}{recent_briefs_block}{resources_block}

## Narrative prompt composition
{narrative_prompt_instructions}

You may use these tools to insert exact prices or report dates if needed: {', '.join(tool_names)}."""


def build_recent_briefs_summary_prompt(briefs_text: str) -> str:
    return f"""## Recent stored briefs
{briefs_text}

Summarize the main points that were already covered across these briefs so the next brief can avoid repetition."""


FOCUS_SELECTOR_SYSTEM = """You are a portfolio assistant helping choose which tickers to focus on in a User Daily Brief.

You receive:
- The user's full portfolio tickers.
- A deterministic attention score per ticker (based on moves and news in the period).
- The current default top-N tickers ranked by this attention score.
- The user's saved investor profile and AI memory, when available.
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
    user_context_snapshot: Optional[str] = None,
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
    if user_context_snapshot:
        lines.extend(
            [
                "",
                "## Saved investor profile and AI memory",
                "Use this to decide which positions deserve attention for this specific user.",
                user_context_snapshot[:1800],
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


def extract_preferred_style_from_user_context(user_context_snapshot: Optional[str]) -> Optional[str]:
    """Best-effort parse of preferred brief style from the saved user context snapshot."""
    if not user_context_snapshot:
        return None
    match = re.search(r"^Preferred AI Style:\s*(.+?)\s*$", user_context_snapshot, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip().lower()
    if not value or value == "not set":
        return None
    normalized = get_normalized_narrative_style(value)
    if normalized is None:
        return None
    if normalized == "balanced" or normalized in NARRATIVE_STYLE_PROMPTS or normalized in STRUCTURED_OUTPUT_STYLES:
        return normalized
    return None
