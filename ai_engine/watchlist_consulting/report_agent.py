"""
Report agent: takes watchlist payload, calls LLM, returns structured report (portfolio summary, narrative, per-ticker highlights).
Uses ai_engine.llm_provider for LLM access (OpenAI, Azure, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repo root is on path so ai_engine.llm_provider can be imported
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _get_llm():
    """Return LLM via ai_engine.llm_provider (quick role). Raises if not configured."""
    from ai_engine.llm_provider import get_config_from_env, get_llm
    config = get_config_from_env()
    return get_llm(
        "quick",
        config,
        temperature=0.3,
        request_timeout=120,
    )


def _payload_to_text(payload: Dict[str, Any], max_chars: int = 40000) -> str:
    """Condense payload for prompt: full per-ticker report insights (takeaways, bull/bear, scores) for integration."""
    entries = payload.get("entries") or []
    lines = [
        f"User: {payload.get('user') or {}}",
        f"Tickers ({len(entries)}): {payload.get('tickers', [])}",
        "",
    ]
    for e in entries:
        rec = e.get("recommendation") or "—"
        conf = e.get("confidence")
        conf_str = f", confidence={conf:.2f}" if isinstance(conf, (int, float)) else ""
        qt = e.get("quote") or {}
        price = qt.get("current_price")
        ch = qt.get("daily_change_percent")
        price_str = f", price={price}, daily_change%={ch}" if price is not None else ""
        lines.append(
            f"--- {e.get('ticker')} ({e.get('name', e.get('ticker'))}) ---"
        )
        lines.append(
            f"Recommendation: {rec}{conf_str}{price_str}. "
            f"Report date: {e.get('report_date')}. "
            f"Expected return: {e.get('expected_return_pct')}% (bear: {e.get('bear_case_return_pct')}%, bull: {e.get('bull_case_return_pct')}%)."
        )
        takeaways = e.get("key_takeaways") or []
        if takeaways:
            lines.append("Key takeaways from analysis:")
            for t in takeaways[:5]:
                lines.append(f"  • {t[:400]}" + ("..." if len(t) > 400 else ""))
        bull = e.get("bull_viewpoint")
        bear = e.get("bear_viewpoint")
        if bull:
            pts = bull if isinstance(bull, list) else [str(bull)]
            s = " ".join(pts)[:350]
            lines.append("Bull case: " + s + ("..." if len(str(bull)) > 350 else ""))
        if bear:
            pts = bear if isinstance(bear, list) else [str(bear)]
            s = " ".join(pts)[:350]
            lines.append("Bear case: " + s + ("..." if len(str(bear)) > 350 else ""))
        scores = e.get("report_scores") or {}
        if scores:
            lines.append("Scores: " + ", ".join(f"{k}={v.get('score_label') or v.get('score')}" for k, v in list(scores.items())[:5]))
        lines.append("")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


def _fallback_per_ticker_highlights(entries: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Build per-ticker highlights from payload when LLM is unavailable or errors."""
    out = []
    for e in entries:
        ticker = e.get("ticker") or ""
        name = e.get("name", ticker)
        rec = e.get("recommendation") or "—"
        takeaways = e.get("key_takeaways") or []
        bull = e.get("bull_viewpoint")
        bear = e.get("bear_viewpoint")
        if takeaways:
            summary = f"{rec} — " + (takeaways[0][:200] + "..." if len(takeaways[0]) > 200 else takeaways[0])
        elif bull or bear:
            parts = []
            if bull:
                p = bull if isinstance(bull, list) else [str(bull)]
                parts.append("Bull: " + " ".join(p)[:120])
            if bear:
                p = bear if isinstance(bear, list) else [str(bear)]
                parts.append("Bear: " + " ".join(p)[:120])
            summary = f"{rec} — {name}. " + " ".join(parts)[:250]
        else:
            summary = f"{rec} — {name}"
        out.append({"ticker": ticker, "short_summary": summary})
    return out


FIGURE_CONTEXT = """
The report will include the following figures (Vega-Lite charts). Your narrative and figure_explanations should reference and explain them so the reader understands what each chart shows and how it supports the story:

1. **Recommendation distribution** — Bar chart of BUY / SELL / HOLD counts across the watchlist. Shows overall tilt of the portfolio.
2. **Daily % change by ticker** — Bar chart of each stock's same-day price change. Reflects short-term market reaction.
3. **Expected return % (Bear / Base / Bull)** — Points per ticker for bear case, base case, and bull case return. Shows risk/reward range from analysis.
4. **Price series** — Line chart(s) of closing price over time (e.g. 6 months) for each ticker. Market context and trend.
5. **Fundamentals (Revenue, EPS)** — Bar charts of revenue or EPS over time per ticker. Fundamental health and growth.
"""


def run_report_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the report agent on the watchlist payload. Returns structured report content.

    Returns dict with:
      - portfolio_summary: str (3–5 paragraphs integrating all report insights into a wider picture)
      - narrative: str (extended: what the figures show and how they connect to the story)
      - figure_explanations: str (explanation of each chart type and how to interpret)
      - per_ticker_highlights: list of { ticker, short_summary }
      - title: optional str
    
    The response style adapts to the user's experience level from their profile.
    """
    try:
        llm = _get_llm()
    except (ValueError, ImportError):
        entries = payload.get("entries") or []
        rec_counts = {}
        for e in entries:
            r = (e.get("recommendation") or "HOLD").upper()
            if r not in ("BUY", "SELL", "HOLD"):
                r = "HOLD"
            rec_counts[r] = rec_counts.get(r, 0) + 1
        return {
            "title": "Watchlist Report (no LLM)",
            "portfolio_summary": (
                f"This watchlist has {len(entries)} subscribed ticker(s). "
                f"Recommendations: {rec_counts.get('BUY', 0)} BUY, {rec_counts.get('SELL', 0)} SELL, {rec_counts.get('HOLD', 0)} HOLD. "
                "Enable OPENAI_API_KEY (or Azure) for an AI-generated portfolio summary that integrates insights from each stock's analysis and explains the figures."
            ),
            "narrative": "Summary not generated (LLM not configured).",
            "figure_explanations": (
                "Charts in this report: Recommendation distribution (BUY/SELL/HOLD counts); "
                "Daily % change by ticker; Expected return (bear/base/bull) per ticker; "
                "Price series and fundamentals (revenue/EPS) where available."
            ),
            "per_ticker_highlights": [
                {"ticker": e.get("ticker"), "short_summary": f"{e.get('recommendation') or '—'} — {e.get('name', e.get('ticker'))}"}
                for e in entries
            ],
        }

    from pydantic import BaseModel, Field

    class ReportOutput(BaseModel):
        portfolio_summary: str = Field(
            description="3-5 paragraphs. Integrate insights from ALL stock reports into one clearer picture: themes, sector/concentration, consensus vs divergence, risk/reward across the watchlist. Draw on key takeaways, bull/bear cases, and recommendations to tell a coherent story, not a ticker-by-ticker list."
        )
        narrative: str = Field(
            description="2-4 paragraphs. Explain what the figures in the report show and how to read them. Connect the charts (recommendation mix, daily moves, return ranges, price trends, fundamentals) to the integrated story. E.g. what does the recommendation distribution say about the portfolio tilt; what do price/fundamental charts add."
        )
        figure_explanations: str = Field(
            description="Several paragraphs or clear bullets. For EACH chart type (recommendation bar, daily % change, expected return bear/base/bull, price series, revenue/EPS) write 2-4 sentences: what the chart shows, how to read it, and what to look for. Be specific so the reader can interpret the figures without guessing."
        )
        per_ticker_highlights: List[Dict[str, str]] = Field(
            description="List of objects with keys ticker and short_summary. Each short_summary must be 1-3 sentences drawing from that stock's report (key takeaway, bull/bear point, or recommendation), not just 'BUY — Name'."
        )
        title: Optional[str] = Field(default=None, description="Optional report title")

    from langchain_core.messages import HumanMessage
    
    # Extract user experience level from payload
    user_info = payload.get("user") or {}
    experience_level = user_info.get("experience_level", "intermediate")
    
    # Define experience-level style guidance
    style_instructions = {
        "beginner": (
            "Use simple, everyday language. Avoid jargon or explain it immediately. "
            "Use direct statements with clear reasoning. Break down complex concepts into simple steps. "
            "Focus on the 'what' and 'why' before the 'how'. Provide context and educational explanations. "
            "Use concrete examples. Be encouraging and educational. "
            "Give clear, actionable guidance with explicit reasoning."
        ),
        "intermediate": (
            "Use standard financial terms but explain less common concepts. Balance accessibility with precision. "
            "Lead with key insights, then provide supporting details. Use moderate technical depth. "
            "Explain the reasoning and key assumptions. Cover both opportunities and risks. "
            "Reference real market scenarios. Be informative and practical. "
            "Provide clear guidance with trade-offs."
        ),
        "advanced": (
            "Use financial terminology freely. Assume familiarity with market concepts, metrics, and analysis frameworks. "
            "Lead with analysis and implications. Use dense, information-rich explanations. "
            "Focus on nuanced analysis, edge cases, and second-order effects. Discuss multiple scenarios. "
            "Reference sophisticated strategies and market dynamics. Be analytical and precise. "
            "Present options with detailed trade-offs and risk-reward profiles."
        ),
        "professional": (
            "Use professional-grade financial language. Assume institutional-level knowledge. "
            "Deliver concise, high-density analysis. Skip basic explanations entirely. "
            "Focus on actionable insights, market microstructure, and portfolio implications. "
            "Discuss positioning, timing, and risk management. Reference institutional strategies and market regimes. "
            "Be direct and efficient. Present sophisticated analysis with minimal hand-holding."
        ),
    }
    
    style_guide = style_instructions.get(experience_level, style_instructions["intermediate"])
    
    prompt_text = (
        "You are a financial report writer. Your report will be shown alongside several Vega-Lite charts.\n\n"
        f"WRITING STYLE: Adapt your response to a {experience_level} investor. {style_guide}\n\n"
        "Requirements:\n"
        "1. Portfolio summary: Integrate insights from each stock's analysis (key takeaways, bull/bear cases, recommendations, return ranges) into a single, clearer big picture — themes, concentration, risk, consensus or divergence. Write 3-5 substantial paragraphs; weave in specific insights from the tickers, not generic statements.\n"
        "2. Narrative: Explain what the figures show and how they connect to that story. Write 2-4 paragraphs.\n"
        "3. Figure explanations: For EACH of the five chart types below, write 2-4 sentences explaining what the chart shows, how to read it, and what to look for. Be explicit so the reader understands every figure. Do not use a single short line per chart.\n"
        + FIGURE_CONTEXT + "\n"
        "Watchlist data (per-ticker reports and insights):\n{data}\n\n"
        "Produce: portfolio_summary (3-5 paragraphs, integrated and specific), narrative (2-4 paragraphs), "
        "figure_explanations (detailed explanation for each chart type, multiple sentences per chart), "
        "per_ticker_highlights (list of ticker + short_summary using report insights), and optional title."
    )
    text = _payload_to_text(payload)
    try:
        # Use function_calling to avoid OpenAI strict JSON schema validation (400 on Pydantic schema)
        structured_llm = llm.with_structured_output(ReportOutput, method="function_calling")
        out = structured_llm.invoke([HumanMessage(content=prompt_text.format(data=text))])
        if hasattr(out, "model_dump"):
            return out.model_dump()
        if isinstance(out, dict):
            return out
        return {"portfolio_summary": str(out), "narrative": "", "per_ticker_highlights": [], "title": None}
    except Exception:
        entries = payload.get("entries") or []
        rec_counts = {}
        for x in entries:
            r = (x.get("recommendation") or "HOLD").upper()
            if r not in ("BUY", "SELL", "HOLD"):
                r = "HOLD"
            rec_counts[r] = rec_counts.get(r, 0) + 1
        return {
            "title": "Watchlist Report",
            "portfolio_summary": (
                f"This watchlist has {len(entries)} ticker(s). "
                f"Recommendations: {rec_counts.get('BUY', 0)} BUY, {rec_counts.get('SELL', 0)} SELL, {rec_counts.get('HOLD', 0)} HOLD. "
                "Use the charts and per-ticker highlights below to see current prices, return ranges, and fundamentals. "
                "(Report generation encountered an error; using fallback content.)"
            ),
            "narrative": (
                "The charts in this report give a snapshot of your watchlist: the mix of recommendations, "
                "today's price moves, expected return ranges from analysis, and price and fundamental trends. "
                "Use the figure explanations and per-ticker section to interpret each chart."
            ),
            "figure_explanations": (
                "**Recommendation distribution** — Shows how many stocks are rated BUY, HOLD, or SELL across your watchlist; "
                "gives the overall tilt of analyst views.\n\n"
                "**Daily % change by ticker** — Same-day price change for each symbol; reflects short-term market reaction.\n\n"
                "**Expected return % (Bear / Base / Bull)** — For each ticker, the low, base, and high return scenarios from the latest analysis; "
                "wider ranges mean more uncertainty.\n\n"
                "**Price series** — Closing price over time (e.g. 6 months) per ticker; use for trend and context.\n\n"
                "**Fundamentals (Revenue, EPS)** — Revenue or earnings per share over recent periods; shows fundamental health and growth."
            ),
            "per_ticker_highlights": _fallback_per_ticker_highlights(entries),
        }
