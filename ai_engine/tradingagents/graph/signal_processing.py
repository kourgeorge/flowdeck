# TradingAgents/graph/signal_processing.py

from typing import Any, Mapping, Optional

_VALID_SIGNALS = frozenset({"BUY", "SELL", "HOLD"})


def resolve_trade_signal_from_state(state: Mapping[str, Any]) -> Optional[str]:
    """Return BUY/SELL/HOLD from structured graph fields (Risk Manager, then Trader).

    Avoids a second LLM pass over the final narrative; matches streaming/analysis_service logic.
    Returns None when neither field holds a valid signal (e.g. the Research Manager fell back
    to plain text after structured output failed) rather than guessing HOLD.
    """
    for key in ("recommendation", "trader_recommendation"):
        raw = state.get(key)
        if raw is None:
            continue
        normalized = str(raw).strip().upper()
        if normalized in _VALID_SIGNALS:
            return normalized
    return None
