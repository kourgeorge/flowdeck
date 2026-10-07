"""Shared completion criteria for workers and administrative reruns."""
REPORT_KEYS = {"market": "market_report", "social": "sentiment_report",
    "fundamentals": "fundamentals_report", "technical": "technical_report",
    "sec": "sec_report", "valuation": "valuation_report"}


def missing_reports(reports, analysts=(), *, legacy=False):
    present = {r.report_type for r in reports if r.content and r.content.strip()}
    required = {REPORT_KEYS[a] for a in analysts if a in REPORT_KEYS}
    if not (legacy and "final_trade_decision" in present):
        required.add("trader_investment_plan")
    return required - present
