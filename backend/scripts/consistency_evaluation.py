#!/usr/bin/env python3
"""
Consistency evaluation for trading agents.

Runs the trading agents graph repeatedly for a set of top companies (default: top 3),
collects decisions and scores per run, then computes consistency metrics and recommendations.

Usage:
  From repo root (with .env and backend on PYTHONPATH as needed):
    python backend/scripts/consistency_evaluation.py [--runs 3] [--date 2024-05-10]
  Or with explicit tickers:
    python backend/scripts/consistency_evaluation.py --tickers AAPL,MSFT,GOOGL --runs 5
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

# Repo root and backend on path (script may be run as python backend/scripts/consistency_evaluation.py)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

from ai_engine.llm_provider import get_config_from_env
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
from ai_engine.tradingagents.default_config import DEFAULT_CONFIG

logger = logging.getLogger(__name__)

# Top 3 companies by market cap / prominence (excluding SPY). Override with --tickers.
DEFAULT_TOP_3_TICKERS = ["IBM"]

# Score keys we collect from final state (numeric 1-10 or similar)
SCORE_KEYS = [
    "market_score",
    "sentiment_score",
    "news_score",
    "fundamentals_score",
    "recommendation_score",
    "risk_score",
]

# Decision normalization: map common variants to BUY / HOLD / SELL
DECISION_ALIASES = {
    "buy": "BUY",
    "hold": "HOLD",
    "sell": "SELL",
    "strong buy": "BUY",
    "strong sell": "SELL",
    "accumulate": "BUY",
    "reduce": "SELL",
    "neutral": "HOLD",
}


@dataclass
class RunResult:
    """Outcome of a single agent run."""
    ticker: str
    run_index: int
    decision: str  # BUY, HOLD, or SELL
    scores: dict = field(default_factory=dict)
    raw_recommendation: str = ""
    raw_final_decision: str = ""

    def to_dict(self):
        d = asdict(self)
        return d


def normalize_decision(raw: str) -> str:
    """Normalize decision text to BUY, HOLD, or SELL."""
    if not raw or not isinstance(raw, str):
        return "HOLD"
    s = raw.strip().upper()
    # Direct match
    if s in ("BUY", "HOLD", "SELL"):
        return s
    # Single word
    for alias, canonical in DECISION_ALIASES.items():
        if alias.upper() == s or s == alias.upper():
            return canonical
    # Try to find first occurrence of BUY/HOLD/SELL in text
    for token in ("SELL", "BUY", "HOLD"):
        if token in s or re.search(rf"\b{token}\b", raw, re.IGNORECASE):
            return token
    return "HOLD"


def extract_decision_from_state(final_state: dict) -> tuple[str, str]:
    """Extract normalized decision and raw recommendation from graph final state."""
    rec = final_state.get("recommendation") or ""
    raw_decision = final_state.get("final_trade_decision") or ""
    if rec:
        return normalize_decision(rec), rec
    return normalize_decision(raw_decision), raw_decision


def extract_scores(final_state: dict) -> dict:
    """Extract numeric scores from final state."""
    out = {}
    for key in SCORE_KEYS:
        val = final_state.get(key)
        if val is not None and isinstance(val, (int, float)):
            out[key] = float(val)
    return out


def run_single(ticker: str, analysis_date: str, run_index: int, config: dict, analysts: list[str]) -> RunResult:
    """Run the trading graph once for a ticker and return RunResult."""
    graph = TradingAgentsGraph(selected_analysts=analysts, config=config, debug=False)
    init_state = graph.propagator.create_initial_state(ticker, analysis_date)
    graph_args = graph.propagator.get_graph_args()
    final_state = graph.graph.invoke(init_state, **graph_args)
    decision, raw_rec = extract_decision_from_state(final_state)
    scores = extract_scores(final_state)
    raw_final = (final_state.get("final_trade_decision") or "")[:200]
    return RunResult(
        ticker=ticker,
        run_index=run_index,
        decision=decision,
        scores=scores,
        raw_recommendation=raw_rec[:200] if raw_rec else "",
        raw_final_decision=raw_final,
    )


def compute_consistency_metrics(results: list[RunResult]) -> dict:
    """Compute consistency metrics over a list of RunResult (same ticker)."""
    if not results:
        return {}
    decisions = [r.decision for r in results]
    counter = Counter(decisions)
    mode_decision = counter.most_common(1)[0][0]
    mode_count = counter[mode_decision]
    n = len(results)
    decision_agreement_pct = (mode_count / n * 100) if n else 0.0

    # Score stability: per-score mean, stdev, min, max (only over present values)
    score_stats = {}
    for key in SCORE_KEYS:
        values = [r.scores[key] for r in results if key in r.scores and r.scores[key] is not None]
        if not values:
            score_stats[key] = {"mean": None, "stdev": None, "min": None, "max": None, "cv_pct": None}
            continue
        mu = mean(values)
        sigma = stdev(values) if len(values) > 1 else 0.0
        cv_pct = (sigma / mu * 100) if mu and mu != 0 else (100.0 if sigma else 0.0)
        score_stats[key] = {
            "mean": round(mu, 2),
            "stdev": round(sigma, 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "cv_pct": round(cv_pct, 1),
        }

    # Overall score stability: average of cv_pct across scores that exist (lower = more consistent)
    cvs = [s["cv_pct"] for s in score_stats.values() if s["cv_pct"] is not None]
    avg_cv = mean(cvs) if cvs else 0.0

    # Composite consistency score 0–100: higher = more consistent
    # 50% from decision agreement, 50% from low score variance (100 - min(avg_cv, 100))
    score_consistency_component = max(0, 100 - min(avg_cv, 100))
    consistency_score = round(
        0.5 * decision_agreement_pct + 0.5 * score_consistency_component,
        1,
    )

    return {
        "ticker": results[0].ticker if results else None,
        "n_runs": n,
        "decision_mode": mode_decision,
        "decision_agreement_pct": round(decision_agreement_pct, 1),
        "decision_counts": dict(counter),
        "score_stats": score_stats,
        "avg_score_cv_pct": round(avg_cv, 1),
        "consistency_score": consistency_score,
        "run_decisions": decisions,
    }


def get_recommendations(metrics_by_ticker: dict) -> list[str]:
    """Generate human-readable recommendations from consistency metrics."""
    recs = []
    for ticker, m in metrics_by_ticker.items():
        cs = m.get("consistency_score") or 0
        agree = m.get("decision_agreement_pct") or 0
        n = m.get("n_runs") or 0
        mode = m.get("decision_mode") or "—"
        if cs >= 70 and agree >= 66:
            recs.append(
                f"{ticker}: High consistency (score={cs}, decision agreement={agree}%). "
                "Agent is reliable for this ticker; consider using for production."
            )
        elif cs >= 50:
            recs.append(
                f"{ticker}: Moderate consistency (score={cs}, decision agreement={agree}%). "
                "Use with caution; consider increasing research_depth or running more evaluations."
            )
        else:
            recs.append(
                f"{ticker}: Low consistency (score={cs}, decision agreement={agree}%). "
                "Recommend increasing research_depth, checking data/LLM stability, or re-running with more runs."
            )
    if metrics_by_ticker:
        overall_avg = mean((m.get("consistency_score") or 0) for m in metrics_by_ticker.values())
        recs.append(
            f"Overall: Average consistency score across tickers = {overall_avg:.1f}. "
            "Run with --runs 5 or higher for more stable metrics."
        )
    return recs


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(
        description="Run consistency evaluation for trading agents on top companies",
    )
    parser.add_argument(
        "--tickers",
        default=",".join(DEFAULT_TOP_3_TICKERS),
        help="Comma-separated tickers (default: AAPL,MSFT,GOOGL)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per ticker (default: 3)",
    )
    parser.add_argument(
        "--date",
        default="2024-05-10",
        help="Analysis date YYYY-MM-DD (default: 2024-05-10)",
    )
    parser.add_argument(
        "--analysts",
        default="market,news,fundamentals",
        help="Comma-separated analysts (default: market,news,fundamentals)",
    )
    parser.add_argument(
        "--research-depth",
        type=int,
        default=2,
        help="Max debate rounds (default: 2 for faster eval)",
    )
    parser.add_argument(
        "--llm-provider",
        default="azure",
        help="LLM provider (default: azure)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Write JSON results to this file (default: stdout only)",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Write output to this dir (consistency_report.json + consistency_report.txt)",
    )
    parser.add_argument(
        "--run-timeout",
        type=int,
        default=600,
        help="Max seconds per run before aborting (default: 600). Prevents indefinite hang on stuck API calls.",
    )
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        tickers = DEFAULT_TOP_3_TICKERS.copy()
    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    if not analysts:
        analysts = ["market", "news", "fundamentals"]

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = args.research_depth
    config["max_risk_discuss_rounds"] = args.research_depth
    config.update(get_config_from_env(overrides={"llm_provider": args.llm_provider.lower()}))

    analysis_date = args.date.strip()
    n_runs = max(1, args.runs)
    run_timeout_seconds = max(60, args.run_timeout)

    all_results: list[RunResult] = []
    executor = ThreadPoolExecutor(max_workers=1)
    for ticker in tickers:
        logger.info("Running %d consistency runs for %s (date=%s)", n_runs, ticker, analysis_date)
        for i in range(n_runs):
            try:
                future = executor.submit(
                    run_single, ticker, analysis_date, i, config, analysts
                )
                res = future.result(timeout=run_timeout_seconds)
                all_results.append(res)
                logger.info("  Run %d/%d %s -> %s", i + 1, n_runs, ticker, res.decision)
            except FuturesTimeoutError:
                logger.error(
                    "Run %d/%d %s timed out after %d seconds. "
                    "API may be slow or stuck; try --run-timeout with a higher value or check network.",
                    i + 1, n_runs, ticker, run_timeout_seconds,
                )
                raise RuntimeError(
                    f"Run {i + 1}/{n_runs} for {ticker} timed out after {run_timeout_seconds}s. "
                    "Increase --run-timeout or check Azure/API connectivity."
                ) from None
            except Exception as e:
                logger.exception("Run %d/%d %s failed: %s", i + 1, n_runs, ticker, e)
                raise
    executor.shutdown(wait=True)

    # Per-ticker consistency metrics
    by_ticker: dict[str, list[RunResult]] = {}
    for r in all_results:
        by_ticker.setdefault(r.ticker, []).append(r)
    metrics_by_ticker = {
        ticker: compute_consistency_metrics(runs)
        for ticker, runs in by_ticker.items()
    }

    # Summary
    summary = {
        "evaluation_metadata": {
            "analysis_date": analysis_date,
            "tickers": tickers,
            "runs_per_ticker": n_runs,
            "analysts": analysts,
            "research_depth": args.research_depth,
            "llm_provider": config["llm_provider"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "per_ticker_metrics": metrics_by_ticker,
        "raw_run_decisions": {
            ticker: [r.decision for r in runs]
            for ticker, runs in by_ticker.items()
        },
        "recommendations": get_recommendations(metrics_by_ticker),
    }

    # Text report
    lines = [
        "=== Trading Agents Consistency Evaluation ===",
        f"Date: {analysis_date}  Tickers: {', '.join(tickers)}  Runs per ticker: {n_runs}",
        "",
    ]
    for ticker in tickers:
        m = metrics_by_ticker.get(ticker, {})
        lines.append(f"--- {ticker} ---")
        lines.append(f"  Consistency score: {m.get('consistency_score', 'N/A')}")
        lines.append(f"  Decision agreement: {m.get('decision_agreement_pct', 'N/A')}% (mode: {m.get('decision_mode', 'N/A')})")
        lines.append(f"  Decision counts: {m.get('decision_counts', {})}")
        lines.append(f"  Score stability (avg CV %): {m.get('avg_score_cv_pct', 'N/A')}")
        lines.append("")
    lines.append("--- Recommendations ---")
    for rec in summary["recommendations"]:
        lines.append(f"  • {rec}")
    text_report = "\n".join(lines)

    print(text_report, file=sys.stderr)
    json_str = json.dumps(summary, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        logger.info("Wrote JSON to %s", args.output)
    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "consistency_report.json").write_text(json_str, encoding="utf-8")
        (out_dir / "consistency_report.txt").write_text(text_report, encoding="utf-8")
        logger.info("Wrote reports to %s", out_dir)
    print(json_str)


if __name__ == "__main__":
    main()
