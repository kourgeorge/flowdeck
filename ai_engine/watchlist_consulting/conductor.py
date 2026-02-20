"""
Orchestrator for the personalized report pipeline DAG.
Loads/builds watchlist_payload; optional user_profile; runs stages 1→2→3→5→6→7→8→9 (optional 9→8 loop).
Optional file cache keyed by (user_id, report_date). Produces report_json, figure_specs, figure_data, provenance.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline_schemas import (
    ActionsOutput,
    NarrativeOutput,
    ReportJson,
    WebResearchOutput,
)
from report_payload import build_payload
from stage1_user_intent import run_user_intent
from stage2_evidence_extractor import run_evidence_extractor
from stage3_theme_miner import run_theme_miner
from stage4_web_research import run_web_research
from stage5_figure_planner import run_figure_planner
from stage6_data_builder import run_data_builder
from stage7_action_engine import run_action_engine
from stage8_narrative_composer import run_narrative_composer
from stage9_auditor import run_auditor
from vega_specs import build_all_specs


def _cache_dir(base_path: Optional[Path] = None) -> Path:
    if base_path is None:
        base_path = Path(__file__).resolve().parent / "out" / "cache"
    return base_path


def _cache_key(user_id: Optional[int], report_date: str) -> str:
    return f"user_{user_id or 0}_{report_date}"


def _stage_output_dir(base: Path, user_slug: str, report_date: str) -> Path:
    """Directory for this run's stage outputs: out/pipeline_stages/<user_slug>_<report_date>/"""
    d = base / "pipeline_stages" / f"{user_slug}_{report_date}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_stage(stage_dir: Optional[Path], name: str, data: Any) -> None:
    """Write one stage output to a JSON file. Uses default=str for dates/non-JSON types."""
    if not stage_dir:
        return
    path = stage_dir / f"{name}.json"
    try:
        if hasattr(data, "model_dump"):
            obj = data.model_dump()
        elif isinstance(data, (list, tuple)) and data and hasattr(data[0], "model_dump"):
            obj = [x.model_dump() if hasattr(x, "model_dump") else x for x in data]
        elif isinstance(data, dict):
            obj = data
        else:
            obj = data
        path.write_text(json.dumps(obj, default=str, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_cache(key: str, cache_dir: Path) -> Optional[Dict[str, Any]]:
    p = cache_dir / f"{key}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(key: str, cache_dir: Path, data: Dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{key}.json"
    # Only cache serializable structs (no raw figure_data by_ticker with complex objects)
    out = {
        "evidence_packets": [x.model_dump() if hasattr(x, "model_dump") else x for x in data.get("evidence_packets", [])],
        "theme_output": data.get("theme_output"),
        "figure_plan": data.get("figure_plan"),
        "data_jobs": [x.model_dump() if hasattr(x, "model_dump") else x for x in data.get("data_jobs", [])],
        "actions_output": data.get("actions_output"),
        "narrative_output": data.get("narrative_output"),
    }
    if data.get("user_intent"):
        out["user_intent"] = data["user_intent"].model_dump() if hasattr(data["user_intent"], "model_dump") else data["user_intent"]
    try:
        p.write_text(json.dumps(out, default=str), encoding="utf-8")
    except Exception:
        pass


def run_pipeline(
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    *,
    use_cache: bool = True,
    skip_audit: bool = False,
    use_llm_evidence: bool = True,
    use_llm_theme: bool = True,
    use_llm_narrative: bool = True,
    web_breadth: int = 3,
    web_depth: int = 2,
    cache_dir: Optional[Path] = None,
    write_stage_outputs: bool = True,
    stage_output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run the full pipeline: payload → 1 → 2 → 3 → 4 (web) → 5 → 6 → 7 → 8 → 9.
    Returns dict with: report_json, figure_specs, figure_data, provenance, audit_output, payload.
    """
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = build_payload(user_id=user_id, email=email)
    if payload.get("error"):
        return {"error": payload["error"], "report_json": None, "figure_specs": [], "figure_data": {}, "provenance": []}
    user = payload.get("user")
    if not user:
        return {"error": "User not found", "report_json": None, "figure_specs": [], "figure_data": {}, "provenance": []}

    user_slug = (user.get("email") or str(user.get("id", "unknown"))).replace("@", "_").replace(".", "_")
    stage_dir: Optional[Path] = None
    if write_stage_outputs:
        base = Path(__file__).resolve().parent / "out"
        stage_dir = stage_output_dir or _stage_output_dir(base, user_slug, report_date)
        print(f"Writing stage outputs to {stage_dir}", flush=True)

    entries = payload.get("entries") or []
    tickers = payload.get("tickers") or []
    cache_key = _cache_key(user.get("id"), report_date)
    cdir = _cache_dir(cache_dir)
    cached = _load_cache(cache_key, cdir) if use_cache else None

    _write_stage(stage_dir, "00_payload", payload)

    # Stage 1
    user_intent = run_user_intent(user_profile=user_profile, watchlist_payload=payload)
    _write_stage(stage_dir, "01_user_intent", user_intent)

    # Stage 2
    if cached and cached.get("evidence_packets"):
        from pipeline_schemas import EvidencePacket
        evidence_packets = [EvidencePacket(**x) for x in cached["evidence_packets"]]
    else:
        evidence_packets = run_evidence_extractor(entries, use_llm=use_llm_evidence)
    _write_stage(stage_dir, "02_evidence_packets", evidence_packets)

    # Stage 3
    if cached and cached.get("theme_output"):
        from pipeline_schemas import ThemeOutput
        theme_output = ThemeOutput(**cached["theme_output"])
    else:
        theme_output = run_theme_miner(evidence_packets, watchlist_payload=payload, use_llm=use_llm_theme)
    _write_stage(stage_dir, "03_theme_output", theme_output)

    # Stage 4: Web research (optional; skipped when web_breadth=0 or SERPAPI_KEY unset)
    web_research_output: WebResearchOutput = run_web_research(
        user_intent, theme_output, payload, breadth=web_breadth, depth=web_depth
    )
    _write_stage(stage_dir, "04_web_research_output", web_research_output)

    # Stage 5
    if cached and cached.get("figure_plan") and cached.get("data_jobs"):
        from pipeline_schemas import DataJob, FigurePlanItem
        figure_plan = [FigurePlanItem(**x) for x in cached["figure_plan"]]
        data_jobs = [DataJob(**x) for x in cached["data_jobs"]]
    else:
        figure_plan, data_jobs = run_figure_planner(evidence_packets, theme_output, user_intent, payload)
    _write_stage(stage_dir, "05_figure_plan", {
        "figure_plan": [x.model_dump() if hasattr(x, "model_dump") else x for x in figure_plan],
        "data_jobs": [x.model_dump() if hasattr(x, "model_dump") else x for x in data_jobs],
    })

    # Stage 6
    figure_data, data_quality_notes = run_data_builder(figure_plan, data_jobs, payload)
    _write_stage(stage_dir, "06_data_builder", {"figure_data_keys": list(figure_data.keys()), "data_quality_notes": data_quality_notes, "figure_data": figure_data})

    # Stage 7
    actions_output: ActionsOutput = run_action_engine(
        user_intent, evidence_packets, theme_output, web_research_output=web_research_output
    )
    _write_stage(stage_dir, "07_actions_output", actions_output)

    # Stage 8
    narrative_output: NarrativeOutput = run_narrative_composer(
        user_intent, evidence_packets, theme_output, figure_plan, figure_data,
        actions_output, payload, use_llm=use_llm_narrative,
        web_research_output=web_research_output,
    )
    _write_stage(stage_dir, "08_narrative_output", narrative_output)

    # Optional cache write
    if use_cache and not cached:
        _save_cache(cache_key, cdir, {
            "evidence_packets": evidence_packets,
            "theme_output": theme_output.model_dump() if hasattr(theme_output, "model_dump") else theme_output,
            "figure_plan": [x.model_dump() if hasattr(x, "model_dump") else x for x in figure_plan],
            "data_jobs": [x.model_dump() if hasattr(x, "model_dump") else x for x in data_jobs],
            "actions_output": actions_output.model_dump() if hasattr(actions_output, "model_dump") else actions_output,
            "narrative_output": narrative_output.model_dump() if hasattr(narrative_output, "model_dump") else narrative_output,
            "user_intent": user_intent,
        })

    # References and research Q&A from web research (for report and HTML)
    references: List[str] = []
    research_qa: List[Dict[str, Any]] = []
    if web_research_output and web_research_output.sources:
        references = list(web_research_output.sources)
    if web_research_output and web_research_output.learnings:
        # Group learnings by query; preserve order of queries_used
        seen_queries: set = set()
        for q in web_research_output.queries_used or []:
            if not q or q in seen_queries:
                continue
            seen_queries.add(q)
            answers = [wl.text for wl in web_research_output.learnings if wl.query_used == q and wl.text.strip()]
            if answers:
                research_qa.append({"question": q, "answers": answers})

    # Stage 9
    report_dict = {
        "title": narrative_output.title,
        "watchlist_summary": narrative_output.watchlist_summary,
        "narrative": getattr(narrative_output, "narrative", "") or "",
        "figure_explanations": narrative_output.figure_explanations,
        "ticker_cards": [c.model_dump() if hasattr(c, "model_dump") else c for c in narrative_output.ticker_cards],
        "actions_section": narrative_output.actions_section,
        "data_freshness": report_date,
        "provenance": narrative_output.provenance,
        "references": references,
        "research_qa": research_qa,
    }
    by_ticker = figure_data.get("by_ticker") or figure_data
    figure_specs = build_all_specs(payload, by_ticker)

    audit_output = None
    if not skip_audit:
        audit_output = run_auditor(
            report_dict, figure_specs, figure_data, evidence_packets, user_intent, narrative_output.provenance, use_llm=False,
        )
        _write_stage(stage_dir, "09_audit_output", audit_output)
        if audit_output.issues_found:
            report_dict["audit_notes"] = "; ".join(
                f"[{i.severity}] {i.message}" for i in audit_output.issues_found
            )

    report_json = ReportJson(
        title=report_dict["title"],
        watchlist_summary=report_dict["watchlist_summary"],
        narrative=report_dict.get("narrative", ""),
        figure_explanations=report_dict["figure_explanations"],
        ticker_cards=report_dict["ticker_cards"],
        actions_section=report_dict["actions_section"],
        data_freshness=report_dict.get("data_freshness"),
        audit_notes=report_dict.get("audit_notes"),
        provenance=report_dict.get("provenance", []),
        references=report_dict.get("references", []),
        research_qa=report_dict.get("research_qa", []),
    )

    return {
        "report_json": report_json,
        "figure_specs": figure_specs,
        "figure_data": figure_data,
        "provenance": narrative_output.provenance,
        "audit_output": audit_output,
        "payload": payload,
        "data_quality_notes": data_quality_notes,
    }
