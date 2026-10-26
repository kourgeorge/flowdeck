"""
Regression tests for Polymarket parsing and formatting.

The Gamma API returns outcomePrices as a JSON-encoded string, which the vendor
indexed character by character ("could not convert string to float: '['"), and
the analyst tool then crashed formatting the deliberately-None overall_sentiment
("unsupported format string passed to NoneType.__format__").
"""

from data_layer.vendors.polymarket_vendor import extract_probability
from ai_engine.tradingagents.agents.utils.news_data_tools import _format_polymarket_sentiment


def test_outcome_prices_json_string_is_parsed():
    market = {"id": "6171957", "question": "Q", "outcomePrices": '["0.53", "0.47"]'}

    assert extract_probability(market, 0) == 0.53
    assert extract_probability(market, 1) == 0.47


def test_outcome_prices_list_still_works():
    market = {"id": "1", "question": "Q", "outcomePrices": ["0.2", "0.8"]}

    assert extract_probability(market, 0) == 0.2


def test_format_handles_uninferred_sentiment():
    data = {
        "overall_sentiment": None,
        "confidence": None,
        "trend": "unknown",
        "market_count": 1,
        "top_markets": [{"question": "Will NVDA beat earnings?", "probability": 0.53}],
    }

    text = _format_polymarket_sentiment("nvda", data)

    assert "not inferred" in text
    assert "Will NVDA beat earnings? (prob=53%)" in text
