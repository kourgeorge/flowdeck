"""Service to read reports from results directory."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import RESULTS_DIR

from services.key_takeaways import extract_key_takeaways


def _date_part(run_id_or_date: Optional[str]) -> Optional[str]:
    """Extract YYYY-MM-DD from run id (YYYY-MM-DD_HH-MM-SS) or return as-is if already date-only."""
    if not run_id_or_date:
        return None
    if "_" in run_id_or_date:
        return run_id_or_date.split("_")[0]
    return run_id_or_date


def _days_ago(report_date: Optional[str], generated_at: Optional[str]) -> Optional[int]:
    ref = None
    if generated_at:
        try:
            ref = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if ref is None and report_date:
        try:
            date_part = _date_part(report_date)
            if date_part:
                ref = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if ref is None:
        return None
    return max(0, (datetime.now(timezone.utc) - ref).days)


def _report_data_from_json(data: dict, date: str) -> Dict[str, Any]:
    meta = data.get("metadata") or {}
    content = data.get("content", "")
    analysis_date = meta.get("analysis_date") or date
    out = {
        "content": content,
        "score": meta.get("score"),
        "score_label": meta.get("score_label"),
        "key_takeaways": meta.get("key_takeaways") or (extract_key_takeaways(content) if content else []),
        "analysis_date": analysis_date,
        "generated_at": meta.get("generated_at"),
        "days_ago": _days_ago(analysis_date, meta.get("generated_at")) or _days_ago(analysis_date, None),
        "recommendation": meta.get("recommendation"),
        "expected_return_pct": meta.get("expected_return_pct"),
        "bear_case_return_pct": meta.get("bear_case_return_pct"),
        "bull_case_return_pct": meta.get("bull_case_return_pct"),
        "confidence": meta.get("confidence"),
        "models_used": meta.get("models_used"),
    }
    if "bull_viewpoint" in data:
        out["bull_viewpoint"] = data["bull_viewpoint"]
    if "bear_viewpoint" in data:
        out["bear_viewpoint"] = data["bear_viewpoint"]
    if "risky_viewpoint" in data:
        out["risky_viewpoint"] = data["risky_viewpoint"]
    if "safe_viewpoint" in data:
        out["safe_viewpoint"] = data["safe_viewpoint"]
    if "neutral_viewpoint" in data:
        out["neutral_viewpoint"] = data["neutral_viewpoint"]
    return out


_EMPTY = {
    "content": None, "score": None, "score_label": None, "key_takeaways": [],
    "analysis_date": None, "generated_at": None, "days_ago": None,
    "recommendation": None, "expected_return_pct": None, "bear_case_return_pct": None,
    "bull_case_return_pct": None, "confidence": None,
}


class ReportService:
    def __init__(self, results_dir: str = None):
        self.results_dir = Path(results_dir or RESULTS_DIR)
        if not self.results_dir.is_absolute():
            self.results_dir = Path(__file__).parent.parent.parent / self.results_dir  # repo root

    def _reports_dir(self, ticker: str, run_id: str) -> Path:
        """run_id is directory name: YYYY-MM-DD or YYYY-MM-DD_HH-MM-SS."""
        return self.results_dir / ticker.upper() / run_id / "reports"

    def get_latest_report_date(self, ticker: str) -> Optional[str]:
        ticker_dir = self.results_dir / ticker.upper()
        if not ticker_dir.exists():
            return None
        dates = sorted(
            (d.name for d in ticker_dir.iterdir() if d.is_dir() and (d / "reports").exists()),
            reverse=True,
        )
        return dates[0] if dates else None

    def has_report_for_date(self, ticker: str, date: str) -> bool:
        """date can be YYYY-MM-DD (match any run that day) or full run id YYYY-MM-DD_HH-MM-SS (exact)."""
        ticker_dir = self.results_dir / ticker.upper()
        if not ticker_dir.exists():
            return False
        if "_" in date:
            rd = self._reports_dir(ticker, date)
            return rd.exists() and rd.is_dir() and any(rd.glob("*.json"))
        for d in ticker_dir.iterdir():
            if d.is_dir() and d.name.startswith(date):
                rd = d / "reports"
                if rd.exists() and rd.is_dir() and any(rd.glob("*.json")):
                    return True
        return False

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        """date can be YYYY-MM-DD (tickers with any run that day) or full run id (exact)."""
        if not self.results_dir.exists():
            return []
        return [p.name for p in self.results_dir.iterdir() if p.is_dir() and self.has_report_for_date(p.name, date)]

    def get_reports_with_scores(self, ticker: str, date: str) -> Dict[str, Dict[str, Any]]:
        rd = self._reports_dir(ticker, date)
        if not rd.exists():
            return {}
        result = {}
        for f in rd.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    result[f.stem] = _report_data_from_json(json.load(fp), date)
            except Exception:
                result[f.stem] = {**_EMPTY, "analysis_date": date, "days_ago": _days_ago(date, None)}
        return result

    def get_reports_for_date(self, ticker: str, date: str) -> Dict[str, Optional[str]]:
        return {k: (v.get("content") or "") for k, v in self.get_reports_with_scores(ticker, date).items()}

    def get_latest_reports(self, ticker: str) -> Dict[str, Optional[str]]:
        d = self.get_latest_report_date(ticker)
        return self.get_reports_for_date(ticker, d) if d else {}

    def get_historical_analyses(self, ticker: str) -> List[Dict]:
        ticker_dir = self.results_dir / ticker.upper()
        if not ticker_dir.exists():
            return []
        analyses = [
            {"date": d.name, "available_reports": sorted(f.stem for f in (d / "reports").glob("*.json"))}
            for d in ticker_dir.iterdir()
            if d.is_dir() and (d / "reports").exists()
        ]
        analyses.sort(key=lambda x: x["date"], reverse=True)
        return analyses

    def has_reports(self, ticker: str) -> bool:
        return self.get_latest_report_date(ticker) is not None
