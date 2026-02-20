"""
Build the final HTML report from agent output, payload, and figure data.
Embeds Vega-Lite via vega-embed CDN. Layout integrates text and figures like a scientific paper:
numbered figures, captions, and sections that interleave narrative with relevant charts.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

# Use vega 5 schema in specs (vega_specs uses v5)
VEGA_EMBED_CDN = "https://cdn.jsdelivr.net/npm/vega-embed@6"
VEGA_LITE_CDN = "https://cdn.jsdelivr.net/npm/vega-lite@5"
VEGA_CDN = "https://cdn.jsdelivr.net/npm/vega@5"

# Number of leading specs treated as "summary figures" (placed right after summary with intro text)
NUM_SUMMARY_FIGURES = 3  # recommendation bar, daily change, return range


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _cite_refs(html: str, num_refs: int) -> str:
    """Replace [1], [2], ... [num_refs] in HTML with superscript links to #ref-1, #ref-2, etc."""
    if num_refs < 1:
        return html
    # Replace from highest to lowest so [10] is not turned into [1]0
    for n in range(num_refs, 0, -1):
        marker = f"[{n}]"
        link = f'<sup><a href="#ref-{n}" class="citation">[{n}]</a></sup>'
        html = html.replace(_escape_html(marker), link)
    return html


def _specs_to_js(specs: List[Dict[str, Any]]) -> str:
    """Serialize Vega-Lite specs as a JavaScript array of objects."""
    return json.dumps(specs, separators=(",", ":"))


def _figure_block(spec_index: int, figure_num: int, caption: str, chart_id: str) -> str:
    """One figure: caption + chart container (paper-style)."""
    return (
        f'<figure class="report-figure" id="fig-{figure_num}">'
        f'<div class="chart-container" id="{chart_id}"></div>'
        f'<figcaption><strong>Figure {figure_num}.</strong> {_escape_html(caption)}</figcaption>'
        "</figure>"
    )


def build_html(
    agent_output: Dict[str, Any],
    payload: Dict[str, Any],
    specs: List[Dict[str, Any]],
    *,
    report_date: str | None = None,
) -> str:
    """
    Build a single HTML document with text and figures integrated like a scientific paper:
    - Title and meta
    - Summary (abstract-like)
    - Summary figures (Fig 1, 2, 3) with short intro text, then each figure
    - Discussion / narrative
    - Interpretation of figures (figure_explanations)
    - Action plan
    - Per-ticker highlights
    - Supporting figures (Fig 4+) with captions
    """
    title = agent_output.get("title") or "Watchlist Report"
    portfolio_summary = agent_output.get("portfolio_summary") or ""
    narrative = agent_output.get("narrative") or ""
    figure_explanations = agent_output.get("figure_explanations") or ""
    per_ticker = agent_output.get("per_ticker_highlights") or []
    actions_section = agent_output.get("actions_section") or ""
    references: List[str] = agent_output.get("references") or []
    research_qa: List[Dict[str, Any]] = agent_output.get("research_qa") or []
    user = payload.get("user") or {}
    user_name = user.get("name") or user.get("email") or "User"
    date_str = report_date or ""

    def _para(s: str, add_citations: bool = True) -> str:
        """Escape HTML and turn newlines into <br>. Support **bold** as <strong>. Optionally turn [1],[2] into citation links."""
        s = _escape_html(s).replace(chr(10), "<br>")
        # Simple **text** -> <strong>text</strong> (pairwise)
        parts = s.split("**")
        out = []
        for i, p in enumerate(parts):
            if i % 2 == 1:
                out.append(f"<strong>{p}</strong>")
            else:
                out.append(p)
        html = "".join(out)
        if add_citations and references:
            html = _cite_refs(html, len(references))
        return html

    # Build list of (spec_index, figure_number, caption)
    figure_num = 0
    fig_items: List[tuple[int, int, str]] = []
    for i, spec in enumerate(specs):
        figure_num += 1
        cap = (spec.get("title") or f"Chart {i + 1}").strip()
        fig_items.append((i, figure_num, cap))

    # Summary section (abstract-like)
    summary_html = (
        f'<div class="section section-summary">'
        f'<h2>Summary</h2>'
        f'<div class="prose">{_para(portfolio_summary)}</div>'
        "</div>"
    )

    # Summary figures: interleave short intro + figure (paper-style)
    summary_figure_intros = [
        "Figure 1 shows the distribution of BUY, HOLD, and SELL recommendations across the watchlist.",
        "Figure 2 shows the same-day price change for each ticker.",
        "Figure 3 shows the expected return range (bear, base, and bull case) from the latest analysis for each ticker.",
    ]
    summary_figs_html_parts: List[str] = []
    for k, (spec_idx, fig_n, caption) in enumerate(fig_items):
        if fig_n > NUM_SUMMARY_FIGURES:
            break
        intro = summary_figure_intros[k] if k < len(summary_figure_intros) else ""
        if intro:
            summary_figs_html_parts.append(f'<p class="figure-intro">{_escape_html(intro)}</p>')
        summary_figs_html_parts.append(_figure_block(spec_idx, fig_n, caption, f"chart-{spec_idx}"))
    summary_figs_html = "\n".join(summary_figs_html_parts)

    # Discussion / narrative
    narrative_html = (
        f'<div class="section"><h2>Discussion</h2><div class="prose">{_para(narrative)}</div></div>'
        if narrative else ""
    )

    # Interpretation of figures
    figure_explanations_html = (
        f'<div class="section"><h2>Interpretation of figures</h2><div class="prose">{_para(figure_explanations)}</div></div>'
        if figure_explanations else ""
    )

    # Action plan
    actions_html = (
        f'<div class="section"><h2>Action plan</h2><div class="prose">{_para(actions_section)}</div></div>'
        if actions_section else ""
    )

    # Per-ticker highlights
    highlights_parts = ['<div class="section"><h2>Per-ticker highlights</h2><ul class="ticker-list">']
    for h in per_ticker:
        ticker = h.get("ticker") or ""
        summary = h.get("short_summary") or ""
        highlights_parts.append(f"<li><strong>{_escape_html(ticker)}</strong>: {_escape_html(summary)}</li>")
    highlights_parts.append("</ul></div>")
    highlights_html = "\n".join(highlights_parts)

    # Supporting figures (Fig 4, 5, ...)
    supporting_parts: List[str] = []
    for spec_idx, fig_n, caption in fig_items:
        if fig_n <= NUM_SUMMARY_FIGURES:
            continue
        supporting_parts.append(_figure_block(spec_idx, fig_n, caption, f"chart-{spec_idx}"))
    supporting_figs_html = ""
    if supporting_parts:
        supporting_figs_html = (
            '<div class="section">'
            '<h2>Supporting figures</h2>'
            '<p class="figure-intro">Price series and fundamental metrics (revenue or EPS) for watchlist tickers.</p>'
            + "\n".join(supporting_parts) +
            "</div>"
        )

    # Research questions explored (deep research Q&A)
    research_qa_html = ""
    if research_qa:
        qa_parts = ['<div class="section"><h2>Research questions explored</h2><p class="figure-intro">Questions investigated during deep research and key findings.</p>']
        for item in research_qa:
            q = item.get("question") or ""
            answers = item.get("answers") or []
            if not q:
                continue
            qa_parts.append(f'<div class="research-qa-item"><p class="research-question">{_escape_html(q)}</p>')
            if answers:
                qa_parts.append('<ul class="research-qa-answers">')
                for a in answers:
                    if a and str(a).strip():
                        qa_parts.append(f"<li>{_escape_html(str(a).strip())}</li>")
                qa_parts.append("</ul>")
            qa_parts.append("</div>")
        qa_parts.append("</div>")
        research_qa_html = "\n".join(qa_parts)

    # References (sources cited); each <li> has id="ref-1", "ref-2" for citation links
    references_html = ""
    if references:
        ref_parts = ['<div class="section"><h2>References</h2><ol class="ref-list">']
        for i, url in enumerate(references, start=1):
            url = (url or "").strip()
            if url:
                ref_parts.append(f'<li id="ref-{i}"><a href="{_escape_html(url)}" target="_blank" rel="noopener">{_escape_html(url)}</a></li>')
        ref_parts.append("</ol></div>")
        references_html = "\n".join(ref_parts)

    specs_js = _specs_to_js(specs)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape_html(title)}</title>
  <script src="{VEGA_CDN}"></script>
  <script src="{VEGA_LITE_CDN}"></script>
  <script src="{VEGA_EMBED_CDN}"></script>
  <style>
    body {{ font-family: Georgia, "Times New Roman", serif; max-width: 720px; margin: 0 auto; padding: 2rem; background: #fff; color: #1e293b; line-height: 1.6; }}
    h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; color: #0f172a; }}
    .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }}
    .section {{ margin-bottom: 2rem; }}
    .section h2 {{ font-size: 1.125rem; font-weight: 600; color: #0f172a; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.25rem; }}
    .prose {{ color: #334155; }}
    .section-summary .prose {{ font-style: normal; }}
    .figure-intro {{ color: #475569; font-size: 0.9375rem; margin-bottom: 0.5rem; }}
    figure.report-figure {{ margin: 1.5rem 0; text-align: center; }}
    figure.report-figure .chart-container {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem; display: inline-block; margin-bottom: 0.5rem; }}
    figcaption {{ font-size: 0.875rem; color: #64748b; text-align: center; max-width: 560px; margin: 0 auto; }}
    .ticker-list {{ padding-left: 1.5rem; }}
    .ticker-list li {{ margin-bottom: 0.5rem; }}
    .ref-list {{ padding-left: 1.5rem; }}
    .ref-list li {{ margin-bottom: 0.35rem; word-break: break-all; }}
    .ref-list a {{ color: #2563eb; }}
    .research-qa-item {{ margin-bottom: 1.25rem; }}
    .research-question {{ font-weight: 600; color: #0f172a; margin-bottom: 0.35rem; }}
    .research-qa-answers {{ padding-left: 1.5rem; margin-top: 0.25rem; }}
    sup.citation, .citation {{ font-size: 0.75em; vertical-align: super; }}
    .citation {{ text-decoration: none; color: #2563eb; }}
  </style>
</head>
<body>
  <h1>{_escape_html(title)}</h1>
  <p class="meta">Report for {_escape_html(str(user_name))}{(" — " + _escape_html(date_str)) if date_str else ""}</p>

  {summary_html}

  <div class="section">
    <h2>Key metrics</h2>
    {summary_figs_html}
  </div>

  {narrative_html}
  {figure_explanations_html}
  {actions_html}
  {highlights_html}
  {supporting_figs_html}
  {research_qa_html}
  {references_html}

  <script>
    (function() {{
      var specs = {specs_js};
      specs.forEach(function(spec, i) {{
        var el = document.getElementById("chart-" + i);
        if (el && spec) {{
          vegaEmbed("#chart-" + i, spec, {{ actions: false }}).catch(console.error);
        }}
      }});
    }})();
  </script>
</body>
</html>
"""
    return html
