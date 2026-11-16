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
    assert "Will NVDA beat earnings? (prob=53%, 24h Δ=n/a)" in text


# The Gamma API sends the 24h move as oneDayPriceChange; reading only
# change_24h always returned a 0.0 placeholder, and a price-less market was
# shown as 50% odds. Missing data must stay None / "n/a".

from data_layer.vendors.polymarket_vendor import calculate_24h_change


def test_one_day_price_change_is_read():
    assert calculate_24h_change({"id": "1", "oneDayPriceChange": -0.12}) == -0.12


def test_change_24h_key_still_used_as_fallback():
    assert calculate_24h_change({"id": "1", "change_24h": 0.03}) == 0.03


def test_missing_change_is_none():
    assert calculate_24h_change({"id": "1", "outcomePrices": '["0.5", "0.5"]'}) is None


def test_missing_price_gives_no_probability():
    assert extract_probability({"id": "1", "question": "Q"}) is None


def test_outcome_dict_without_price_gives_no_probability():
    assert extract_probability({"id": "1", "question": "Q", "outcomes": [{"name": "Yes"}]}) is None


def test_format_never_invents_odds_or_flat_change():
    data = {
        "overall_sentiment": None,
        "confidence": None,
        "trend": "unknown",
        "market_count": 2,
        "top_markets": [
            {"question": "No price market?", "probability": None, "change_24h": None},
            {"question": "Moving market?", "probability": 0.4, "change_24h": -0.12},
        ],
    }

    text = _format_polymarket_sentiment("nvda", data)

    assert "50%" not in text
    assert "+0.0pp" not in text
    assert "No price market? (prob=n/a, 24h Δ=n/a)" in text
    assert "24h Δ=-12.0pp" in text


def test_response_model_accepts_null_probability_and_change():
    from routers.polymarket import MarketResponse

    m = MarketResponse(
        id="1", question="Q", description="", probability=None, change_24h=None,
        volume=0, liquidity=0, end_date="", category="", url="u",
    )
    assert m.probability is None and m.change_24h is None
