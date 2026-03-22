from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, computed_field

EventDomain = Literal["price_technical", "news_information", "fundamental"]
EventStrength = Literal["low", "medium", "high"]

_EVENT_DESCRIPTIONS: Dict[str, str] = {
    "price_spike_up": "The stock rose sharply in a single session relative to its recent normal movement.",
    "price_spike_down": "The stock fell sharply in a single session relative to its recent normal movement.",
    "price_gap_up": "The stock opened materially above the prior close, indicating a strong upward gap at the open.",
    "price_gap_down": "The stock opened materially below the prior close, indicating a strong downward gap at the open.",
    "volatility_expansion": "Price swings have become meaningfully larger than the recent baseline.",
    "volatility_compression": "Price swings have tightened relative to the recent baseline.",
    "moving_average_cross": "A short-term moving average crossed a longer-term moving average.",
    "new_52w_high": "The stock reached or exceeded its highest price level of the past 52 weeks.",
    "new_52w_low": "The stock reached or fell below its lowest price level of the past 52 weeks.",
    "volume_spike": "Trading volume rose materially above the recent average.",
    "earnings_upcoming": "The company has an upcoming earnings report within the monitored forward window.",
    "insider_buying": "Recent insider transactions indicate meaningful net buying activity by company insiders.",
    "insider_selling": "Recent insider transactions indicate meaningful net selling activity by company insiders.",
    "rsi_bullish_divergence": "Price weakness and RSI momentum are diverging in a way that can suggest selling pressure is easing.",
    "rsi_bearish_divergence": "Price strength and RSI momentum are diverging in a way that can suggest upside momentum is weakening.",
}


class DetectedEvent(BaseModel):
    """Deterministic event record shared across workflows, APIs, and UI consumers."""

    event_type: str = Field(description="Stable event key, e.g. price_gap_up.")
    domain: EventDomain = Field(description="High-level event domain.")
    detected_on: Optional[str] = Field(default=None, description="Primary event date (YYYY-MM-DD).")
    window_start: Optional[str] = Field(default=None, description="Start of detection window (YYYY-MM-DD).")
    window_end: Optional[str] = Field(default=None, description="End of detection window (YYYY-MM-DD).")
    strength: EventStrength = Field(description="Relative event severity from deterministic rules.")
    metric_value: Optional[float] = Field(default=None, description="Primary numeric metric for the event.")
    threshold_value: Optional[float] = Field(default=None, description="Threshold that triggered the event.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Event-specific deterministic metadata.")

    @computed_field(return_type=str)
    @property
    def description(self) -> str:
        return _EVENT_DESCRIPTIONS.get(
            self.event_type,
            "A deterministic event was detected from the available market data.",
        )


class TickerEventSummary(BaseModel):
    """Grouped deterministic events for one ticker."""

    ticker: str = Field(description="Ticker symbol.")
    events: List[DetectedEvent] = Field(default_factory=list, description="Detected events for this ticker.")
    event_score: float = Field(default=0.0, description="Deterministic scalar summarizing event importance.")
    dominant_events: List[str] = Field(default_factory=list, description="Dominant event types ordered by contribution.")
    event_count: int = Field(default=0, description="Number of detected events.")


_EVENT_WEIGHT: Dict[str, float] = {
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
_PRICE_TECHNICAL_LOOKBACK_DAYS = 10
_UPCOMING_EARNINGS_LOOKAHEAD_DAYS = 30
_INSIDER_LOOKBACK_DAYS = 30
_INSIDER_VALUE_THRESHOLD = 100_000.0
_INSIDER_SHARES_THRESHOLD = 1_000.0


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _safe_pct_change(new_val: Optional[float], old_val: Optional[float]) -> Optional[float]:
    if new_val is None or old_val in (None, 0):
        return None
    return (new_val - old_val) / old_val * 100.0


def _strength_from_ratio(ratio: Optional[float]) -> EventStrength:
    if ratio is None:
        return "low"
    if ratio >= 2.0:
        return "high"
    if ratio >= 1.35:
        return "medium"
    return "low"


def _score_events(events: List[DetectedEvent]) -> tuple[float, List[str]]:
    weighted: Dict[str, float] = {}
    total = 0.0
    for event in events:
        contribution = _EVENT_WEIGHT.get(event.event_type, 1.0) * _STRENGTH_MULTIPLIER.get(event.strength, 1.0)
        total += contribution
        weighted[event.event_type] = weighted.get(event.event_type, 0.0) + contribution
    dominant = [
        name
        for name, _score in sorted(
            weighted.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    return round(total, 4), dominant


def _valid_values(values: List[Optional[float]]) -> List[float]:
    return [value for value in values if value is not None]


def _build_prefix_stats(values: List[Optional[float]]) -> tuple[List[int], List[float], List[float]]:
    counts = [0]
    sums = [0.0]
    sum_squares = [0.0]
    for value in values:
        if value is None:
            counts.append(counts[-1])
            sums.append(sums[-1])
            sum_squares.append(sum_squares[-1])
            continue
        counts.append(counts[-1] + 1)
        sums.append(sums[-1] + value)
        sum_squares.append(sum_squares[-1] + (value * value))
    return counts, sums, sum_squares


def _window_count(prefix_counts: List[int], start: int, end: int) -> int:
    return prefix_counts[end] - prefix_counts[start]


def _window_mean(
    prefix_counts: List[int],
    prefix_sums: List[float],
    start: int,
    end: int,
) -> Optional[float]:
    count = _window_count(prefix_counts, start, end)
    if count <= 0:
        return None
    return (prefix_sums[end] - prefix_sums[start]) / count


def _window_pstdev(
    prefix_counts: List[int],
    prefix_sums: List[float],
    prefix_sum_squares: List[float],
    start: int,
    end: int,
) -> Optional[float]:
    count = _window_count(prefix_counts, start, end)
    if count <= 0:
        return None
    total = prefix_sums[end] - prefix_sums[start]
    total_squares = prefix_sum_squares[end] - prefix_sum_squares[start]
    mean_value = total / count
    variance = max(0.0, (total_squares / count) - (mean_value * mean_value))
    return variance ** 0.5


def _normalize_bars(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in bars:
        if not isinstance(raw, dict):
            continue
        dt = _parse_date(raw.get("date"))
        if dt is None:
            continue
        normalized.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "open": _as_float(raw.get("open")),
                "high": _as_float(raw.get("high")),
                "low": _as_float(raw.get("low")),
                "close": _as_float(raw.get("close")),
                "volume": _as_float(raw.get("volume")),
            }
        )
    normalized.sort(key=lambda row: row["date"])
    return normalized


def _classify_insider_transaction(raw: Any) -> Optional[str]:
    if isinstance(raw, dict):
        text = str(raw.get("transaction") or raw.get("text") or "").strip().lower()
    else:
        text = str(raw or "").strip().lower()
    if not text:
        return None
    normalized = text.replace("-", " ").replace("_", " ")
    code = normalized.split()[0]
    buy_codes = {"p", "a", "buy", "purchase", "acquire", "acquisition"}
    sell_codes = {"s", "d", "sale", "sell", "dispose", "disposition"}
    if code in buy_codes:
        return "buy"
    if code in sell_codes:
        return "sell"
    if "purchase" in normalized or "buy" in normalized or "acquir" in normalized:
        return "buy"
    if "sale" in normalized or "sell" in normalized or "dispos" in normalized:
        return "sell"
    return None


def parse_rsi_indicator_data(raw_data: Any) -> Dict[str, float]:
    """Parse the backend indicator payload into a date -> RSI float map."""
    if raw_data is None:
        return {}
    text = raw_data if isinstance(raw_data, str) else str(raw_data)
    parsed: Dict[str, float] = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line or line.startswith("##"):
            continue
        date_part, value_part = line.split(":", 1)
        date_str = date_part.strip()
        value_str = value_part.strip()
        if "N/A" in value_str or "not" in value_str.lower():
            continue
        try:
            value = float(value_str)
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 100:
            parsed[date_str] = value
    return parsed


def extract_insider_events(
    ticker: str,
    *,
    as_of_date: str,
    insider_transactions: Any = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> TickerEventSummary:
    """Extract deterministic insider buy/sell events from normalized transaction payloads."""

    end_dt = _parse_date(end_date or as_of_date) or datetime.utcnow()
    start_dt = _parse_date(start_date or as_of_date) or end_dt
    window_start_dt = start_dt - timedelta(days=_INSIDER_LOOKBACK_DAYS)
    transactions = []
    if isinstance(insider_transactions, dict):
        transactions = insider_transactions.get("transactions") or []

    grouped: Dict[str, Dict[str, Any]] = {
        "buy": {"count": 0, "total_value": 0.0, "total_shares": 0.0, "latest_date": None, "insiders": []},
        "sell": {"count": 0, "total_value": 0.0, "total_shares": 0.0, "latest_date": None, "insiders": []},
    }

    for raw in transactions:
        if not isinstance(raw, dict):
            continue
        direction = _classify_insider_transaction(raw)
        if direction is None:
            continue
        transaction_dt = _parse_date(raw.get("start_date"))
        if transaction_dt is None:
            continue
        if transaction_dt < window_start_dt or transaction_dt > end_dt:
            continue

        bucket = grouped[direction]
        bucket["count"] += 1
        bucket["total_value"] += abs(_as_float(raw.get("value")) or 0.0)
        bucket["total_shares"] += abs(_as_float(raw.get("shares")) or 0.0)
        latest = bucket["latest_date"]
        if latest is None or transaction_dt > latest:
            bucket["latest_date"] = transaction_dt
        insider_name = str(raw.get("insider") or "").strip()
        if insider_name and insider_name not in bucket["insiders"]:
            bucket["insiders"].append(insider_name)

    events: List[DetectedEvent] = []
    for direction, event_type in (("buy", "insider_buying"), ("sell", "insider_selling")):
        bucket = grouped[direction]
        total_value = float(bucket["total_value"] or 0.0)
        total_shares = float(bucket["total_shares"] or 0.0)
        count = int(bucket["count"] or 0)
        latest_dt = bucket["latest_date"]
        value_ratio = total_value / _INSIDER_VALUE_THRESHOLD if _INSIDER_VALUE_THRESHOLD > 0 else 0.0
        shares_ratio = total_shares / _INSIDER_SHARES_THRESHOLD if _INSIDER_SHARES_THRESHOLD > 0 else 0.0
        trigger_ratio = max(value_ratio, shares_ratio)
        if latest_dt is None or count == 0 or trigger_ratio < 1.0:
            continue

        metric_value = total_value if total_value > 0 else total_shares
        threshold_value = _INSIDER_VALUE_THRESHOLD if total_value > 0 else _INSIDER_SHARES_THRESHOLD
        events.append(
            DetectedEvent(
                event_type=event_type,
                domain="fundamental",
                detected_on=latest_dt.strftime("%Y-%m-%d"),
                window_start=window_start_dt.strftime("%Y-%m-%d"),
                window_end=end_dt.strftime("%Y-%m-%d"),
                strength=_strength_from_ratio(trigger_ratio),
                metric_value=round(metric_value, 4),
                threshold_value=round(threshold_value, 4),
                metadata={
                    "transaction_count": count,
                    "total_value": round(total_value, 4),
                    "total_shares": round(total_shares, 4),
                    "latest_transaction_date": latest_dt.strftime("%Y-%m-%d"),
                    "insiders": bucket["insiders"][:5],
                },
            )
        )

    event_score, dominant_events = _score_events(events)
    return TickerEventSummary(
        ticker=ticker.upper(),
        events=events,
        event_score=event_score,
        dominant_events=dominant_events,
        event_count=len(events),
    )


def _detect_rsi_divergence(
    ticker: str,
    *,
    bars: List[Dict[str, Any]],
    rsi_data: Dict[str, float],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> TickerEventSummary:
    """Detect RSI divergences between price and RSI indicator."""
    normalized = _normalize_bars(bars)
    if len(normalized) < 10:
        return TickerEventSummary(ticker=ticker.upper())

    highs = [row["high"] for row in normalized]
    lows = [row["low"] for row in normalized]
    dates = [row["date"] for row in normalized]

    end_dt = _parse_date(end_date or dates[-1]) or datetime.utcnow()
    start_dt = _parse_date(start_date or dates[0]) or _parse_date(dates[0]) or end_dt

    price_peaks = []
    price_troughs = []
    events: List[DetectedEvent] = []

    window = min(5, len(normalized) // 10)

    for i in range(window, len(normalized) - window):
        if highs[i] == max(highs[i - window : i + window + 1]):
            date_str = dates[i]
            if date_str in rsi_data:
                price_peaks.append((i, date_str, highs[i], rsi_data[date_str]))

        if lows[i] == min(lows[i - window : i + window + 1]):
            date_str = dates[i]
            if date_str in rsi_data:
                price_troughs.append((i, date_str, lows[i], rsi_data[date_str]))

    if len(price_peaks) >= 2:
        recent_peaks = sorted(price_peaks, key=lambda x: x[0])[-2:]
        if (
            len(recent_peaks) >= 2
            and recent_peaks[1][2] > recent_peaks[0][2]
            and recent_peaks[1][3] < recent_peaks[0][3]
        ):
            events.append(
                DetectedEvent(
                    event_type="rsi_bearish_divergence",
                    domain="price_technical",
                    detected_on=recent_peaks[1][1],
                    window_start=start_dt.strftime("%Y-%m-%d"),
                    window_end=end_dt.strftime("%Y-%m-%d"),
                    strength="high",
                    metric_value=round(recent_peaks[1][2], 4),
                    threshold_value=round(recent_peaks[0][2], 4),
                    metadata={
                        "price_trend": "higher highs",
                        "rsi_trend": "lower highs",
                        "latest_rsi": round(recent_peaks[1][3], 2),
                        "prior_rsi": round(recent_peaks[0][3], 2),
                    },
                )
            )

    if len(price_troughs) >= 2:
        recent_troughs = sorted(price_troughs, key=lambda x: x[0])[-2:]
        if (
            len(recent_troughs) >= 2
            and recent_troughs[1][2] < recent_troughs[0][2]
            and recent_troughs[1][3] > recent_troughs[0][3]
        ):
            events.append(
                DetectedEvent(
                    event_type="rsi_bullish_divergence",
                    domain="price_technical",
                    detected_on=recent_troughs[1][1],
                    window_start=start_dt.strftime("%Y-%m-%d"),
                    window_end=end_dt.strftime("%Y-%m-%d"),
                    strength="high",
                    metric_value=round(recent_troughs[1][2], 4),
                    threshold_value=round(recent_troughs[0][2], 4),
                    metadata={
                        "price_trend": "lower lows",
                        "rsi_trend": "higher lows",
                        "latest_rsi": round(recent_troughs[1][3], 2),
                        "prior_rsi": round(recent_troughs[0][3], 2),
                    },
                )
            )

    event_score, dominant_events = _score_events(events)
    return TickerEventSummary(
        ticker=ticker.upper(),
        events=events,
        event_score=event_score,
        dominant_events=dominant_events,
        event_count=len(events),
    )


def extract_price_technical_events(
    ticker: str,
    *,
    bars: List[Dict[str, Any]],
    lookback_days: int = _PRICE_TECHNICAL_LOOKBACK_DAYS,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> TickerEventSummary:
    """Extract high-confidence price/technical events from daily OHLCV bars."""

    normalized = _normalize_bars(bars)
    if len(normalized) < 2:
        return TickerEventSummary(ticker=ticker.upper())

    closes = [row["close"] for row in normalized]
    opens = [row["open"] for row in normalized]
    highs = [row["high"] for row in normalized]
    lows = [row["low"] for row in normalized]
    volumes = [row["volume"] for row in normalized]
    dates = [row["date"] for row in normalized]
    date_points = [_parse_date(value) or datetime.utcnow() for value in dates]

    earliest_dt = date_points[0]
    end_dt = _parse_date(end_date or dates[-1]) or date_points[-1] or datetime.utcnow()
    if start_date:
        start_dt = _parse_date(start_date) or earliest_dt
    else:
        normalized_lookback_days = max(1, int(lookback_days))
        start_dt = max(earliest_dt, end_dt - timedelta(days=normalized_lookback_days - 1))

    daily_returns: List[Optional[float]] = [
        _safe_pct_change(closes[idx], closes[idx - 1]) for idx in range(1, len(closes))
    ]
    abs_gaps: List[Optional[float]] = [None] + [
        abs(_safe_pct_change(opens[idx], closes[idx - 1]))
        if _safe_pct_change(opens[idx], closes[idx - 1]) is not None
        else None
        for idx in range(1, len(opens))
    ]
    positive_volumes: List[Optional[float]] = [
        value if value is not None and value > 0 else None for value in volumes
    ]
    daily_return_counts, daily_return_sums, daily_return_sum_squares = _build_prefix_stats(daily_returns)
    gap_counts, gap_sums, _gap_sum_squares = _build_prefix_stats(abs_gaps)
    volume_counts, volume_sums, _volume_sum_squares = _build_prefix_stats(positive_volumes)
    close_counts, close_sums, _close_sum_squares = _build_prefix_stats(closes)

    valid_daily_returns = [value for value in daily_returns if value is not None]
    valid_return_prefix_counts = [0]
    for value in daily_returns:
        valid_return_prefix_counts.append(valid_return_prefix_counts[-1] + (1 if value is not None else 0))
    valid_return_counts, valid_return_sums, valid_return_sum_squares = _build_prefix_stats(valid_daily_returns)

    events: List[DetectedEvent] = []
    window_indices = [
        idx for idx, point in enumerate(date_points)
        if start_dt <= point <= end_dt
    ]

    for idx in window_indices:
        event_date = dates[idx]

        if idx >= 1:
            latest_return = daily_returns[idx - 1]
            prior_start = max(0, idx - 21)
            prior_end = idx - 1
            prior_return_count = _window_count(daily_return_counts, prior_start, prior_end)
            if latest_return is not None and prior_return_count > 0:
                vol20 = _window_pstdev(
                    daily_return_counts,
                    daily_return_sums,
                    daily_return_sum_squares,
                    prior_start,
                    prior_end,
                )
                vol20 = vol20 if vol20 is not None and prior_return_count >= 2 else 0.0
                threshold = max(4.0, 2.0 * vol20)
                if abs(latest_return) >= threshold:
                    ratio = abs(latest_return) / threshold if threshold > 0 else None
                    event_type = "price_spike_up" if latest_return > 0 else "price_spike_down"
                    events.append(
                        DetectedEvent(
                            event_type=event_type,
                            domain="price_technical",
                            detected_on=event_date,
                            window_start=dates[max(0, idx - 20)],
                            window_end=event_date,
                            strength=_strength_from_ratio(ratio),
                            metric_value=round(latest_return, 4),
                            threshold_value=round(threshold, 4),
                            metadata={
                                "return_1d_pct": round(latest_return, 4),
                                "rolling_vol_20d_pct": round(vol20, 4),
                            },
                        )
                    )

            latest_open = opens[idx]
            prev_close = closes[idx - 1]
            gap_pct = _safe_pct_change(latest_open, prev_close)
            prior_gap_start = max(1, idx - 20)
            prior_gap_end = idx
            avg_gap = _window_mean(gap_counts, gap_sums, prior_gap_start, prior_gap_end)
            if gap_pct is not None and avg_gap is not None:
                threshold = max(2.0, 1.5 * avg_gap)
                if abs(gap_pct) >= threshold:
                    ratio = abs(gap_pct) / threshold if threshold > 0 else None
                    event_type = "price_gap_up" if gap_pct > 0 else "price_gap_down"
                    events.append(
                        DetectedEvent(
                            event_type=event_type,
                            domain="price_technical",
                            detected_on=event_date,
                            window_start=dates[max(0, idx - 20)],
                            window_end=event_date,
                            strength=_strength_from_ratio(ratio),
                            metric_value=round(gap_pct, 4),
                            threshold_value=round(threshold, 4),
                            metadata={
                                "gap_pct": round(gap_pct, 4),
                                "prev_close": prev_close,
                                "open": latest_open,
                                "avg_abs_gap_20d_pct": round(avg_gap, 4),
                            },
                        )
                    )

            current_volume = volumes[idx]
            prior_volume_start = max(0, idx - 20)
            prior_volume_end = idx
            avg_volume = _window_mean(volume_counts, volume_sums, prior_volume_start, prior_volume_end)
            if current_volume is not None and avg_volume is not None:
                if avg_volume > 0:
                    ratio = current_volume / avg_volume
                    if ratio >= 2.0:
                        events.append(
                            DetectedEvent(
                                event_type="volume_spike",
                                domain="price_technical",
                                detected_on=event_date,
                                window_start=dates[max(0, idx - 20)],
                                window_end=event_date,
                                strength=_strength_from_ratio(ratio / 2.0),
                                metric_value=round(ratio, 4),
                                threshold_value=2.0,
                                metadata={
                                    "current_volume": int(current_volume),
                                    "avg_volume_20d": round(avg_volume, 2),
                                },
                            )
                        )

        valid_return_end = valid_return_prefix_counts[idx]
        if valid_return_end >= 60:
            short_vol = _window_pstdev(
                valid_return_counts,
                valid_return_sums,
                valid_return_sum_squares,
                valid_return_end - 10,
                valid_return_end,
            )
            short_vol = short_vol if short_vol is not None else 0.0
            long_vol = _window_pstdev(
                valid_return_counts,
                valid_return_sums,
                valid_return_sum_squares,
                valid_return_end - 60,
                valid_return_end,
            )
            long_vol = long_vol if long_vol is not None else 0.0
            if long_vol > 0:
                ratio = short_vol / long_vol
                if ratio >= 1.5:
                    events.append(
                        DetectedEvent(
                            event_type="volatility_expansion",
                            domain="price_technical",
                            detected_on=event_date,
                            window_start=dates[max(0, idx - 59)],
                            window_end=event_date,
                            strength=_strength_from_ratio(ratio / 1.5),
                            metric_value=round(ratio, 4),
                            threshold_value=1.5,
                            metadata={
                                "short_vol_10d_pct": round(short_vol, 4),
                                "long_vol_60d_pct": round(long_vol, 4),
                            },
                        )
                    )
                elif ratio <= 0.67:
                    compression_ratio = 0.67 / ratio if ratio > 0 else 2.0
                    events.append(
                        DetectedEvent(
                            event_type="volatility_compression",
                            domain="price_technical",
                            detected_on=event_date,
                            window_start=dates[max(0, idx - 59)],
                            window_end=event_date,
                            strength=_strength_from_ratio(compression_ratio),
                            metric_value=round(ratio, 4),
                            threshold_value=0.67,
                            metadata={
                                "short_vol_10d_pct": round(short_vol, 4),
                                "long_vol_60d_pct": round(long_vol, 4),
                            },
                        )
                    )

        if idx >= 1:
            ma_short_prev = _window_mean(close_counts, close_sums, max(0, idx - 20), idx)
            ma_short_now = _window_mean(close_counts, close_sums, max(0, idx - 19), idx + 1)
            ma_long_prev = _window_mean(close_counts, close_sums, max(0, idx - 50), idx)
            ma_long_now = _window_mean(close_counts, close_sums, max(0, idx - 49), idx + 1)
            if None not in (ma_short_prev, ma_long_prev, ma_short_now, ma_long_now) and ma_short_prev <= ma_long_prev and ma_short_now > ma_long_now:
                ratio = abs(ma_short_now - ma_long_now) / max(abs(ma_long_now), 1e-9)
                events.append(
                    DetectedEvent(
                        event_type="moving_average_cross",
                        domain="price_technical",
                        detected_on=event_date,
                        window_start=dates[max(0, idx - 49)],
                        window_end=event_date,
                        strength=_strength_from_ratio(ratio * 100.0),
                        metric_value=round(ma_short_now - ma_long_now, 4),
                        threshold_value=0.0,
                        metadata={
                            "short_window": 20,
                            "long_window": 50,
                            "cross": "bullish",
                            "ma_short": round(ma_short_now, 4),
                            "ma_long": round(ma_long_now, 4),
                        },
                    )
                )
            elif None not in (ma_short_prev, ma_long_prev, ma_short_now, ma_long_now) and ma_short_prev >= ma_long_prev and ma_short_now < ma_long_now:
                ratio = abs(ma_short_now - ma_long_now) / max(abs(ma_long_now), 1e-9)
                events.append(
                    DetectedEvent(
                        event_type="moving_average_cross",
                        domain="price_technical",
                        detected_on=event_date,
                        window_start=dates[max(0, idx - 49)],
                        window_end=event_date,
                        strength=_strength_from_ratio(ratio * 100.0),
                        metric_value=round(ma_short_now - ma_long_now, 4),
                        threshold_value=0.0,
                        metadata={
                            "short_window": 20,
                            "long_window": 50,
                            "cross": "bearish",
                            "ma_short": round(ma_short_now, 4),
                            "ma_long": round(ma_long_now, 4),
                        },
                    )
                )

        if idx >= 1 and idx + 1 >= 252 and highs[idx] is not None:
            prior_high_values = _valid_values(highs[max(0, idx - 251): idx])
            prior_high = max(prior_high_values) if prior_high_values else None
            if prior_high is not None and highs[idx] >= prior_high:
                ratio = highs[idx] / prior_high if prior_high > 0 else None
                events.append(
                    DetectedEvent(
                        event_type="new_52w_high",
                        domain="price_technical",
                        detected_on=event_date,
                        window_start=dates[max(0, idx - 251)],
                        window_end=event_date,
                        strength=_strength_from_ratio(ratio),
                        metric_value=round(highs[idx], 4),
                        threshold_value=round(prior_high, 4),
                        metadata={
                            "current_high": round(highs[idx], 4),
                            "prior_52w_high": round(prior_high, 4),
                        },
                    )
                )
        if idx >= 1 and idx + 1 >= 252 and lows[idx] is not None:
            prior_low_values = _valid_values(lows[max(0, idx - 251): idx])
            prior_low = min(prior_low_values) if prior_low_values else None
            if prior_low is not None and lows[idx] <= prior_low:
                ratio = prior_low / lows[idx] if lows[idx] and lows[idx] > 0 else None
                events.append(
                    DetectedEvent(
                        event_type="new_52w_low",
                        domain="price_technical",
                        detected_on=event_date,
                        window_start=dates[max(0, idx - 251)],
                        window_end=event_date,
                        strength=_strength_from_ratio(ratio),
                        metric_value=round(lows[idx], 4),
                        threshold_value=round(prior_low, 4),
                        metadata={
                            "current_low": round(lows[idx], 4),
                            "prior_52w_low": round(prior_low, 4),
                        },
                    )
                )

    event_score, dominant_events = _score_events(events)
    return TickerEventSummary(
        ticker=ticker.upper(),
        events=events,
        event_score=event_score,
        dominant_events=dominant_events,
        event_count=len(events),
    )


def extract_fundamental_events(
    ticker: str,
    *,
    as_of_date: str,
    future_events: Any = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> TickerEventSummary:
    """Extract high-confidence fundamental events from structured platform data."""

    end_dt = _parse_date(end_date or as_of_date) or datetime.utcnow()
    start_dt = _parse_date(start_date or as_of_date) or end_dt
    events: List[DetectedEvent] = []

    future_list = future_events.get("events") if isinstance(future_events, dict) else []
    future_list = future_list or []
    upcoming: List[tuple[int, datetime, Dict[str, Any]]] = []
    for raw in future_list:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("type") or "").lower() != "earnings":
            continue
        event_dt = _parse_date(raw.get("date"))
        if event_dt is None:
            continue
        days_until = (event_dt.date() - end_dt.date()).days
        if days_until < 0 or days_until > _UPCOMING_EARNINGS_LOOKAHEAD_DAYS:
            continue
        upcoming.append((days_until, event_dt, raw))

    upcoming.sort(key=lambda item: item[0])
    if upcoming:
        days_until, event_dt, raw = upcoming[0]
        if days_until <= 7:
            strength: EventStrength = "high"
        elif days_until <= 21:
            strength = "medium"
        else:
            strength = "low"
        eps_estimate = _as_float(raw.get("eps_estimate"))
        events.append(
            DetectedEvent(
                event_type="earnings_upcoming",
                domain="fundamental",
                detected_on=event_dt.strftime("%Y-%m-%d"),
                window_start=start_dt.strftime("%Y-%m-%d"),
                window_end=(end_dt + timedelta(days=_UPCOMING_EARNINGS_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d"),
                strength=strength,
                metric_value=float(days_until),
                threshold_value=float(_UPCOMING_EARNINGS_LOOKAHEAD_DAYS),
                metadata={
                    "days_until": days_until,
                    "event_date": event_dt.strftime("%Y-%m-%d"),
                    "eps_estimate": eps_estimate,
                    "label": raw.get("label"),
                },
            )
        )

    event_score, dominant_events = _score_events(events)
    return TickerEventSummary(
        ticker=ticker.upper(),
        events=events,
        event_score=event_score,
        dominant_events=dominant_events,
        event_count=len(events),
    )


def extract_ticker_events(
    ticker: str,
    *,
    bars: List[Dict[str, Any]],
    as_of_date: str,
    future_events: Any = None,
    insider_transactions: Any = None,
    rsi_data: Optional[Dict[str, float]] = None,
    price_technical_lookback_days: int = _PRICE_TECHNICAL_LOOKBACK_DAYS,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> TickerEventSummary:
    """Merge deterministic technical and fundamental events into one ticker summary."""

    technical = extract_price_technical_events(
        ticker,
        bars=bars,
        lookback_days=price_technical_lookback_days,
        start_date=start_date,
        end_date=end_date,
    )
    fundamental = extract_fundamental_events(
        ticker,
        as_of_date=as_of_date,
        future_events=future_events,
        start_date=start_date,
        end_date=end_date,
    )
    insider = extract_insider_events(
        ticker,
        as_of_date=as_of_date,
        insider_transactions=insider_transactions,
        start_date=start_date,
        end_date=end_date,
    )
    events = [*technical.events, *fundamental.events, *insider.events]
    event_score, dominant_events = _score_events(events)

    indicator_events = TickerEventSummary(ticker=ticker.upper())
    if rsi_data:
        indicator_events = _detect_rsi_divergence(
            ticker,
            bars=bars,
            rsi_data=rsi_data,
            start_date=start_date,
            end_date=end_date,
        )

    events.extend(indicator_events.events)
    event_score, dominant_events = _score_events(events)
    return TickerEventSummary(
        ticker=ticker.upper(),
        events=events,
        event_score=event_score,
        dominant_events=dominant_events,
        event_count=len(events),
    )
