from ai_engine.agent.skills._subscriptions import parse_subscribed_tickers
from ai_engine.agent.skills import portfolio_health, portfolio_performance


SAMPLE = (
    "Your subscriptions:\n"
    "- **AAPL** — subscribed 2026-01-02\n"
    "- **BRK-B** — subscribed 2026-01-03\n"
    "- **0700.HK** — subscribed 2026-01-04\n"
    "- **GC=F** — subscribed 2026-01-05\n"
    "- **AAPL** — subscribed 2026-02-01\n"
)


def test_parse_keeps_digits_and_equals_in_order_once_each():
    assert parse_subscribed_tickers(SAMPLE) == ["AAPL", "BRK-B", "0700.HK", "GC=F"]


def test_both_skills_use_the_shared_parser():
    assert portfolio_health.parse_subscribed_tickers is parse_subscribed_tickers
    assert portfolio_performance.parse_subscribed_tickers is parse_subscribed_tickers
    assert not hasattr(portfolio_health, "_parse_tickers")
    assert not hasattr(portfolio_performance, "_parse_tickers")


def test_empty_text_gives_no_tickers():
    assert parse_subscribed_tickers("You have no subscriptions.") == []
