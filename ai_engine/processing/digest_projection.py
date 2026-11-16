from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .event import DetectedEvent, EventStrength, TickerEventSummary

_EVENT_WEIGHT = {
    "price_spike_up": 2.0,
    "price_spike_down": 2.0,
    "price_gap_up": 2.0,
    "price_gap_down": 2.0,
    "volatility_expansion": 1.25,
    "volatility_compression": 1.0,
    "moving_average_cross": 1.5,
    "new_52w_high": 2.5,
    "new_52w_low": 2.5,
    "volume_spike": 1.5,
    "earnings_upcoming": 1.25,
    "insider_buying": 1.75,
    "insider_selling": 1.75,
    "rsi_bullish_divergence": 2.0,
    "rsi_bearish_divergence": 2.0,
}
_STRENGTH_MULTIPLIER: Dict[EventStrength, float] = {"low": 1.0, "medium": 1.5, "high": 2.0}


class ImportantEvent(BaseModel):
    """Digest-facing event payload derived from ticker-level event summaries."""

    ticker: str = Field(description="Ticker symbol associated with the event.")
    importance_score: float = Field(description="Deterministic contribution score used for ranking.")
    event: DetectedEvent = Field(description="Canonical detected event payload.")


def _event_importance_score(event: DetectedEvent) -> float:
    return round(
        _EVENT_WEIGHT.get(event.event_type, 1.0) * _STRENGTH_MULTIPLIER.get(event.strength, 1.0),
        4,
    )


def build_important_events(
    event_summaries: Dict[str, TickerEventSummary],
    *,
    ticker_order: Optional[List[str]] = None,
    max_events: Optional[int] = 10,
) -> List[ImportantEvent]:
    """Flatten ticker event summaries into an ordered digest payload."""

    ordered_tickers = [str(t).upper() for t in (ticker_order or list(event_summaries.keys()))]
    ticker_rank = {ticker: idx for idx, ticker in enumerate(ordered_tickers)}
    flattened: List[tuple[float, int, int, ImportantEvent]] = []

    for ticker in ordered_tickers:
        summary = event_summaries.get(ticker)
        if summary is None:
            continue
        for event_idx, event in enumerate(summary.events):
            importance_score = _event_importance_score(event)
            flattened.append(
                (
                    importance_score,
                    ticker_rank.get(ticker, len(ticker_rank)),
                    event_idx,
                    ImportantEvent(
                        ticker=ticker,
                        importance_score=importance_score,
                        event=event.model_copy(deep=True),
                    ),
                ),
            )

    flattened.sort(key=lambda item: (-item[0], item[1], item[2]))
    important_events = [event for _, _, _, event in flattened]
    if max_events is None or max_events < 0:
        return important_events
    return important_events[:max_events]
