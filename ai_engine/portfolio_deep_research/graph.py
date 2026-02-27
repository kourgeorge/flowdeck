"""
Portfolio Deep Research LangGraph: interpret → plan → load reports → research → extract evidence → synthesize → QA → deliver.
Uses ai_engine.llm_provider for all LLM access (fast vs deep).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from .config import PortfolioDeepResearchConfig
from .prompts import (
    INTERPRET_QUERY_SYSTEM,
    INTERPRET_QUERY_USER,
    PLAN_SYSTEM,
    PLAN_USER,
    QA_DEEP_SYSTEM,
    QA_FAST_SYSTEM,
    RESEARCH_AGENT_SYSTEM,
    RESEARCH_AGENT_USER,
    SYNTHESIZE_SYSTEM,
    SYNTHESIZE_USER,
    RISK_PROFILE_SUMMARY_SYSTEM,
    RISK_PROFILE_SUMMARY_USER,
    PORTFOLIO_QUESTIONS_INTRO_SYSTEM,
    PORTFOLIO_QUESTIONS_INTRO_USER,
)
from .source_quality import apply_reliability_to_evidence
from .state import Claim, ResearchState
from .tools import get_all_tools, get_latest_reports
from .portfolio_risk_profiler import analyze_portfolio_risk
from .portfolio_interrogator import generate_portfolio_questions


def _get_config(config: Optional[Dict[str, Any]] = None) -> PortfolioDeepResearchConfig:
    return PortfolioDeepResearchConfig.from_runnable_config(config or {})


def _get_llm(role: str, config: Optional[Dict[str, Any]] = None):
    from ai_engine.llm_provider import get_llm
    cfg = _get_config(config)
    return get_llm(
        role,
        cfg.llm_config(),
        request_timeout=cfg.request_timeout,
    )


def _messages_to_text(messages: list) -> str:
    from langchain_core.messages import get_buffer_string
    return get_buffer_string(messages) if messages else ""


def _parse_synthesize_sections(content: str) -> Dict[str, str]:
    """Split synthesize output into executive summary, main report, and figure explanations."""
    sections = {
        "summary": "",
        "narrative": "",
        "figure_explanations": "",
    }
    if not content or not content.strip():
        return sections
    markers = [
        ("---EXECUTIVE SUMMARY---", "---MAIN REPORT---", "summary"),
        ("---MAIN REPORT---", "---FIGURE EXPLANATIONS---", "narrative"),
        ("---FIGURE EXPLANATIONS---", None, "figure_explanations"),
    ]
    text = content.strip()
    for i, (start_marker, end_marker, key) in enumerate(markers):
        start_pos = text.find(start_marker)
        if start_pos == -1:
            continue
        begin = start_pos + len(start_marker)
        if end_marker:
            end_pos = text.find(end_marker, begin)
            if end_pos == -1:
                end_pos = len(text)
            sections[key] = text[begin:end_pos].strip()
        else:
            sections[key] = text[begin:].strip()
    # If no delimiters found, treat full content as narrative and use first 500 chars as summary
    if not sections["narrative"] and not sections["summary"]:
        sections["narrative"] = text
        sections["summary"] = text[:500].strip() if len(text) > 500 else text
    return sections


# --- Nodes ---


async def interpret_query(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Use tickers and user_query when both provided (e.g. CLI); else parse message with LLM."""
    input_tickers = state.get("tickers") or []
    input_query = (state.get("user_query") or "").strip()

    if input_tickers and input_query:
        # Caller gave both (e.g. --tickers and --query): use them as-is, no LLM.
        tickers = list(dict.fromkeys(t.upper().strip() for t in input_tickers))[:20]
        logger.info("Step: interpret_query — using provided inputs | query=%s | tickers=%s", input_query[:80], tickers)
        return {
            "user_query": input_query[:500],
            "tickers": tickers,
        }

    # Single message blob (e.g. chat): interpret with LLM to extract query and tickers.
    logger.info("Step: interpret_query — parsing user message with LLM")
    messages = state.get("messages") or []
    user_text = _messages_to_text(messages)
    if not user_text.strip():
        return {"user_query": "No query", "tickers": []}

    llm = _get_llm("quick", config)
    prompt = INTERPRET_QUERY_USER.format(user_text=user_text)
    response = await llm.ainvoke([
        SystemMessage(content=INTERPRET_QUERY_SYSTEM),
        HumanMessage(content=prompt),
    ])
    content = response.content if hasattr(response, "content") else str(response)
    tickers = list(dict.fromkeys(t.upper().strip() for t in input_tickers)) if input_tickers else []
    query = content.split("\n")[0][:500] if content else user_text[:500]
    logger.info("Step: interpret_query — done | query=%s | tickers=%s", query[:80], tickers[:10])
    return {
        "user_query": query,
        "tickers": tickers[:20],
    }


async def plan(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Produce research plan: sub-questions, sources (fast model)."""
    logger.info("Step: plan — building research plan")
    user_query = state.get("user_query") or ""
    tickers = state.get("tickers") or []

    llm = _get_llm("quick", config)
    prompt = PLAN_USER.format(
        user_query=user_query,
        tickers=", ".join(tickers) if tickers else "none specified",
    )
    response = await llm.ainvoke([
        SystemMessage(content=PLAN_SYSTEM),
        HumanMessage(content=prompt),
    ])
    content = response.content if hasattr(response, "content") else str(response)
    plan_list = [line.strip() for line in content.split("\n") if line.strip() and line.strip()[0].isdigit()]
    if not plan_list:
        plan_list = [content[:500]]
    logger.info("Step: plan — done | %d sub-questions", len(plan_list[:15]))
    return {"plan": plan_list[:15]}


async def load_existing_reports(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Fetch latest reports for each ticker from backend; store in existing_reports."""
    tickers = state.get("tickers") or []
    logger.info("Step: load_existing_reports — tickers=%s", tickers[:10])
    if not tickers:
        return {"existing_reports": {}}

    cfg = _get_config(config)
    base = (cfg.info_service_url or os.environ.get("INFO_SERVICE_URL") or "http://localhost:8002").strip().rstrip("/")
    existing = {}
    if base:
        try:
            data = json.dumps({"tickers": [t.upper() for t in tickers[:50]]}).encode("utf-8")
            req = urllib.request.Request(f"{base}/api/data/reports/batch", data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                out = json.loads(resp.read().decode())
            for t, info in (out.get("tickers") or {}).items():
                existing[t.upper()] = {"report_date": info.get("report_date"), "reports": info.get("reports") or {}, "summary": ""}
        except Exception as e:
            existing = {t.upper(): {"summary": f"Failed to fetch: {e}", "reports": {}} for t in tickers}
    if not existing:
        tickers_str = ",".join(tickers[:50])
        result = get_latest_reports.invoke({"tickers": tickers_str})
        text = result if isinstance(result, str) else str(result)
        for t in tickers:
            existing[t.upper()] = {"summary": text, "report_date": None, "reports": {}}
    logger.info("Step: load_existing_reports — done | %d tickers", len(existing))
    return {"existing_reports": existing, "audit_log": [{"step": "load_existing_reports", "tickers": list(existing.keys())}]}


def _source_id_for_tool(name: str, args: Dict[str, Any]) -> str:
    """Build a stable source_id for a tool call so the agent can cite it."""
    if not name:
        return "unknown"
    # Key arg for citation: query for search, tickers for reports, first string arg for data tools
    key_arg = ""
    if name in ("web_search", "serpapi_search"):
        key_arg = (args.get("query") or "").strip()
    elif name == "get_latest_reports":
        key_arg = (args.get("tickers") or "").strip()
    else:
        for k, v in args.items():
            if isinstance(v, str) and v:
                key_arg = v[:100]
                break
            if v is not None:
                key_arg = str(v)[:100]
                break
    if key_arg:
        return f'{name}("{key_arg}")'
    return name


def _sources_from_agent_messages(messages: list) -> tuple[list, list]:
    """
    Extract all tool results from create_agent messages as sources with stable source_id.
    Returns (sources, search_queries_run) for ResearchState. Every ToolMessage becomes
    a source so downstream steps and the agent's citations can reference them.
    """
    call_id_to_info: Dict[str, tuple[str, Dict[str, Any]]] = {}
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            cid = tc.get("id") or ""
            if cid:
                call_id_to_info[cid] = (tc.get("name") or "", tc.get("args") or {})

    sources = []
    search_queries_run = []
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        tid = getattr(m, "tool_call_id", None) or ""
        name, args = call_id_to_info.get(tid, ("", {}))
        content = getattr(m, "content", "") or str(m)
        source_id = _source_id_for_tool(name, args)

        # One source entry per tool call with stable source_id for citations
        entry: Dict[str, Any] = {
            "source_id": source_id,
            "kind": "serpapi" if name in ("web_search", "serpapi_search") else "tool",
            "content": content,
        }
        if name in ("web_search", "serpapi_search"):
            q = (args.get("query") or "").strip()
            if q:
                entry["query"] = q
                search_queries_run.append({"query": q, "timestamp": datetime.utcnow().isoformat()})
        sources.append(entry)
    return sources, search_queries_run


async def research(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Run LangChain create_agent research agent with tools to answer plan questions."""
    plan_list = state.get("plan") or []
    user_query = state.get("user_query") or ""
    tickers = state.get("tickers") or []
    cfg = _get_config(config)
    sources = list(state.get("sources") or [])
    search_queries_run = list(state.get("search_queries_run") or [])

    plan_bullets = "\n".join(f"- {p[:300]}" for p in (plan_list[:10] or ["General market and portfolio context"]))
    tools = get_all_tools(cfg)
    model = _get_llm("quick", config)
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    user_content = RESEARCH_AGENT_USER.format(
        current_date=current_date,
        user_query=user_query,
        tickers=", ".join(tickers) if tickers else "none",
        plan_bullets=plan_bullets,
    )
    research_agent = create_agent(
        model,
        tools=tools,
        system_prompt=RESEARCH_AGENT_SYSTEM,
    )
    input_messages = [HumanMessage(content=user_content)]
    if hasattr(research_agent, "ainvoke"):
        result = await research_agent.ainvoke(
            {"messages": input_messages},
            config=config,
        )
    else:
        result = await asyncio.to_thread(
            research_agent.invoke,
            {"messages": input_messages},
            config,
        )
    agent_sources, agent_queries = _sources_from_agent_messages(result.get("messages") or [])
    sources.extend(agent_sources)
    search_queries_run.extend(agent_queries)
    logger.info("Step: research — done | %d sources", len(sources))
    return {"sources": sources, "search_queries_run": search_queries_run}


async def extract_evidence(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Build evidence + a concise claim verdict in one pass."""
    logger.info("Step: extract_evidence — normalizing sources + reports + claims")
    sources = state.get("sources") or []
    existing_reports = state.get("existing_reports") or {}
    user_query = state.get("user_query") or ""
    evidence_items = []

    for i, source in enumerate(sources):
        content = str(source.get("content") or "").strip()
        if not content:
            continue
        source_id = source.get("source_id") or f"source_{i}"
        kind = source.get("kind") or "tool"
        notes = f"kind={kind}"
        if source.get("query"):
            notes += f"; query={source.get('query')}"
        evidence_items.append({
            "source_id": source_id,
            "snippet": content[:1000],
            "paraphrase": content[:300],
            "reliability_score": None,
            "notes": notes[:300],
        })

    for ticker, data in existing_reports.items():
        report_date = data.get("report_date") or "unknown_date"
        reports = data.get("reports") or {}
        summary = (data.get("summary") or "").strip()
        if summary:
            evidence_items.append({
                "source_id": f"existing_report_summary({ticker})",
                "snippet": summary[:1000],
                "paraphrase": summary[:300],
                "reliability_score": None,
                "notes": f"existing reports summary; report_date={report_date}",
            })
        for report_type, report_data in reports.items():
            key_takeaways = report_data.get("key_takeaways") or []
            if not key_takeaways:
                recommendation = report_data.get("recommendation")
                if recommendation:
                    key_takeaways = [f"Recommendation: {recommendation}"]
            if not key_takeaways:
                continue
            joined = "; ".join(str(x) for x in key_takeaways if x)
            if not joined.strip():
                continue
            evidence_items.append({
                "source_id": f"existing_report({ticker},{report_type})",
                "snippet": joined[:1000],
                "paraphrase": joined[:300],
                "reliability_score": None,
                "notes": f"existing report type={report_type}; report_date={report_date}",
            })

    if not evidence_items:
        evidence_items = [{
            "source_id": "no_evidence",
            "snippet": "No evidence was collected from sources or existing reports.",
            "paraphrase": "No usable evidence found.",
            "reliability_score": 0.0,
            "notes": "fallback",
        }]

    evidence_items = evidence_items[:120]
    apply_reliability_to_evidence(evidence_items)

    unique_sources = []
    seen = set()
    for e in evidence_items:
        sid = (e.get("source_id") or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            unique_sources.append(sid)

    source_count = len(unique_sources)
    if source_count >= 6:
        status = "supported"
        confidence = f"high ({source_count} unique sources)"
    elif source_count >= 2:
        status = "partially_supported"
        confidence = f"medium ({source_count} unique sources)"
    else:
        status = "unknown"
        confidence = f"low ({source_count} unique sources)"

    claim_text = (user_query or "Portfolio research question").strip()[:1000]
    claims = [Claim(
        claim_text=claim_text,
        status=status,
        evidence_for=unique_sources[:12],
        confidence=confidence,
    )]
    logger.info("Step: extract_evidence — done | %d evidence items | %d claims", len(evidence_items), len(claims))
    return {
        "evidence_items": evidence_items,
        "claims": [c.model_dump() if hasattr(c, "model_dump") else c for c in claims],
    }


async def synthesize(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Write narrative report with citations and figure explanations (deep model)."""
    logger.info("Step: synthesize — writing narrative report")
    user_query = state.get("user_query") or ""
    tickers = state.get("tickers") or []
    claims = state.get("claims") or []
    evidence_items = state.get("evidence_items") or []

    claims_and_evidence = "\n".join(
        (c.get("claim_text") if isinstance(c, dict) else getattr(c, "claim_text", str(c)) for c in claims[:15])
    ) + "\n\nEvidence:\n" + "\n".join(
        (e.get("snippet") or e.get("paraphrase") or str(e))for e in evidence_items
    )

    llm = _get_llm("deep", config)
    prompt = SYNTHESIZE_USER.format(
        user_query=user_query,
        tickers=", ".join(tickers),
        claims_and_evidence=claims_and_evidence,
    )
    response = await llm.ainvoke([
        SystemMessage(content=SYNTHESIZE_SYSTEM),
        HumanMessage(content=prompt),
    ])
    content = response.content if hasattr(response, "content") else str(response)
    sections = _parse_synthesize_sections(content)
    # Use parsed sections so Summary / Discussion / Interpretation of figures are not repetitive
    narrative = sections["narrative"] or content
    summary = sections["summary"].strip() if sections["summary"] else content[:800].strip()
    figure_explanations = sections["figure_explanations"].strip() if sections["figure_explanations"] else "See narrative for figure context."
    logger.info("Step: synthesize — done | report length=%d chars", len(content))
    return {
        "final_answer": content,
        "narrative_output": {
            "title": f"Portfolio Research: {user_query[:80]}",
            "summary": summary,
            "narrative": narrative,
            "figure_explanations": figure_explanations,
        },
    }


async def qa(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Fast then deep QA pass."""
    logger.info("Step: qa — fast then deep QA pass")
    draft = state.get("final_answer") or ""
    llm_quick = _get_llm("quick", config)
    llm_deep = _get_llm("deep", config)
    fast_response = await llm_quick.ainvoke([
        SystemMessage(content=QA_FAST_SYSTEM),
        HumanMessage(content=f"Draft report:\n{draft[:6000]}\n\nList any issues (citations, structure, length)."),
    ])
    fast_issues = fast_response.content if hasattr(fast_response, "content") else str(fast_response)
    deep_response = await llm_deep.ainvoke([
        SystemMessage(content=QA_DEEP_SYSTEM),
        HumanMessage(content=f"Draft:\n{draft[:6000]}\n\nStrongest counter-argument? Do conclusions follow from evidence?"),
    ])
    deep_issues = deep_response.content if hasattr(deep_response, "content") else str(deep_response)
    improved = draft
    if fast_issues or deep_issues:
        improved = draft + "\n\n--- QA notes ---\nFast: " + fast_issues[:500] + "\nDeep: " + deep_issues[:500]
    logger.info("Step: qa — done")
    return {"final_answer": improved}


async def analyze_portfolio_risk_node(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze portfolio risk: sector exposure, concentration, beta, correlations."""
    logger.info("Step: analyze_portfolio_risk — calculating risk metrics")
    tickers = state.get("tickers") or []
    existing_reports = state.get("existing_reports") or {}
    
    if not tickers:
        logger.warning("No tickers provided, skipping risk analysis")
        return {"risk_profile": None, "portfolio_questions": None}
    
    # Perform risk analysis
    risk_profile = analyze_portfolio_risk(tickers, existing_reports)
    risk_profile_dict = risk_profile.to_dict()
    
    # Generate critical questions
    questions = generate_portfolio_questions(tickers, risk_profile_dict)
    questions_dict = [q.to_dict() for q in questions]
    
    logger.info(
        "Step: analyze_portfolio_risk — done | risk_score=%.1f | questions=%d",
        risk_profile_dict.get("risk_score", 0),
        len(questions_dict),
    )
    
    return {
        "risk_profile": risk_profile_dict,
        "portfolio_questions": questions_dict,
    }


async def deliver(state: ResearchState, config: RunnableConfig) -> Dict[str, Any]:
    """Set final output; optionally build HTML with figures (see figures.py)."""
    logger.info("Step: deliver — building HTML and final output")
    final = state.get("final_answer") or ""
    narrative_output = state.get("narrative_output") or {}
    tickers = state.get("tickers") or []
    existing_reports = state.get("existing_reports") or {}
    risk_profile = state.get("risk_profile") or {}
    portfolio_questions = state.get("portfolio_questions") or []
    
    # Build minimal payload and figure_data for HTML when available
    payload = {"entries": []}
    figure_data = {}
    for t in tickers:
        payload["entries"].append({
            "ticker": t,
            "recommendation": "—",
            "quote": {},
            "expected_return_pct": None,
            "bear_case_return_pct": None,
            "bull_case_return_pct": None,
        })
        figure_data[t] = {}
    try:
        from .figures import build_figure_data_and_payload
        figure_data, payload = build_figure_data_and_payload(tickers, existing_reports, config)
    except Exception:  # noqa: BLE001
        pass
    
    # Add risk profile and questions to agent output (convert markdown to HTML)
    import markdown
    
    risk_section = ""
    risk_section_html = ""
    if risk_profile:
        risk_warnings = risk_profile.get("risk_warnings", [])
        risk_score = risk_profile.get("risk_score", 0)
        sector_exposure = risk_profile.get("sector_exposure", {})
        
        risk_section = f"\n\n## Portfolio Risk Profile\n\n"
        risk_section += f"**Risk Score:** {risk_score:.0f}/100\n\n"
        
        if sector_exposure:
            risk_section += "**Sector Exposure:**\n"
            for sector, pct in list(sector_exposure.items())[:5]:
                risk_section += f"- {sector}: {pct:.1f}%\n"
            risk_section += "\n"
        
        if risk_warnings:
            risk_section += "**Risk Warnings:**\n"
            for warning in risk_warnings[:5]:
                risk_section += f"- {warning}\n"
            risk_section += "\n"
        
        # Convert to HTML
        risk_section_html = markdown.markdown(risk_section)
    
    questions_section = ""
    questions_section_html = ""
    if portfolio_questions:
        questions_section = "\n\n## Critical Questions About Your Portfolio\n\n"
        for i, q in enumerate(portfolio_questions[:8], 1):
            urgency = q.get("urgency", "medium")
            urgency_emoji = "🔴" if urgency == "high" else "🟡" if urgency == "medium" else "🟢"
            questions_section += f"{urgency_emoji} **{q.get('question', '')}**\n\n"
            questions_section += f"{q.get('context', '')}\n\n"
            if q.get("suggested_action"):
                questions_section += f"*Suggested Action:* {q.get('suggested_action')}\n\n"
        
        # Convert to HTML
        questions_section_html = markdown.markdown(questions_section)
    
    try:
        from ai_engine.watchlist_consulting.vega_specs import build_all_specs
        from ai_engine.watchlist_consulting.html_report import build_html
        specs = build_all_specs(payload, figure_data)
        
        # Enhance narrative with risk profile and questions (use HTML versions)
        enhanced_narrative = narrative_output.get("narrative") or final
        enhanced_narrative += risk_section_html + questions_section_html
        
        agent_output = {
            "title": narrative_output.get("title") or "Portfolio Deep Research Report",
            "portfolio_summary": narrative_output.get("summary") or final[:2000],
            "narrative": enhanced_narrative,
            "figure_explanations": narrative_output.get("figure_explanations") or "See narrative for figure context.",
            "per_ticker_highlights": [],
            "actions_section": "",
            "references": [],
            "research_qa": [],
        }
        report_date = datetime.utcnow().strftime("%Y-%m-%d")
        html = build_html(agent_output, payload, specs, report_date=report_date)
        return {"final_report_html": html, "figure_specs": specs, "figure_data": figure_data, "payload": payload}
    except Exception:
        # Fallback: use markdown versions for plain text output
        return {"final_report_html": None, "final_answer": final + risk_section + questions_section}
    finally:
        logger.info("Step: deliver — done")


# --- Graph build ---

builder = StateGraph[ResearchState, None, ResearchState, ResearchState](ResearchState)
builder.add_node("interpret_query", interpret_query)
builder.add_node("plan", plan)
builder.add_node("load_existing_reports", load_existing_reports)
builder.add_node("analyze_portfolio_risk", analyze_portfolio_risk_node)
builder.add_node("research", research)
builder.add_node("extract_evidence", extract_evidence)
builder.add_node("synthesize", synthesize)
builder.add_node("qa", qa)
builder.add_node("deliver", deliver)

builder.add_edge(START, "interpret_query")
builder.add_edge("interpret_query", "plan")
builder.add_edge("plan", "load_existing_reports")
builder.add_edge("load_existing_reports", "analyze_portfolio_risk")
builder.add_edge("analyze_portfolio_risk", "research")
builder.add_edge("research", "extract_evidence")
builder.add_edge("extract_evidence", "synthesize")
builder.add_edge("synthesize", "qa")
builder.add_edge("qa", "deliver")
builder.add_edge("deliver", END)

portfolio_research_graph = builder.compile()
