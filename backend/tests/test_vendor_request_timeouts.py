"""Alpha Vantage and Google News must time out instead of hanging, and a
timeout must let interface._route fall through to the next vendor."""

import pytest
import requests

from data_layer.vendors import alpha_vantage_common, googlenews_utils, interface


class _FakeResponse:
    status_code = 200
    text = "symbol,value\nAAPL,1\n"
    content = b"<html></html>"

    def raise_for_status(self):
        pass


def _no_sleep(monkeypatch):
    monkeypatch.setattr(googlenews_utils.time, "sleep", lambda _s: None)


def test_alpha_vantage_request_passes_timeout(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(alpha_vantage_common.requests, "get", fake_get)
    alpha_vantage_common._make_api_request("INSIDER_TRANSACTIONS", {"symbol": "AAPL"})
    assert seen.get("timeout")


def test_google_news_request_passes_timeout(monkeypatch):
    _no_sleep(monkeypatch)
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(googlenews_utils.requests, "get", fake_get)
    assert googlenews_utils.getNewsData("AAPL", "2026-01-01", "2026-01-07") == []
    assert seen.get("timeout")


def _raise_timeout(*_args, **_kwargs):
    raise requests.Timeout("read timed out")


def test_alpha_vantage_timeout_raises(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr(alpha_vantage_common.requests, "get", _raise_timeout)
    with pytest.raises(requests.Timeout):
        alpha_vantage_common._make_api_request("NEWS_SENTIMENT", {})


def test_google_news_timeout_raises_when_nothing_collected(monkeypatch):
    # An empty list would look like "no news"; the real cause must surface.
    _no_sleep(monkeypatch)
    monkeypatch.setattr(googlenews_utils.requests, "get", _raise_timeout)
    with pytest.raises(requests.Timeout):
        googlenews_utils.getNewsData("AAPL", "2026-01-01", "2026-01-07")


def test_google_news_page_loop_is_capped(monkeypatch):
    # A results page that always has a "Next" link must not loop forever.
    _no_sleep(monkeypatch)
    page = (
        '<div class="SoaBEf"><a href="http://x">x</a><div class="MBeuO">t</div>'
        '<div class="GI74Re">s</div><div class="LfVVr">d</div>'
        '<div class="NUnG9d"><span>src</span></div></div>'
        '<a id="pnnext" href="#">Next</a>'
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        resp = _FakeResponse()
        resp.content = page.encode()
        return resp

    monkeypatch.setattr(googlenews_utils.requests, "get", fake_get)
    results = googlenews_utils.getNewsData("AAPL", "2026-01-01", "2026-01-07")
    assert len(calls) == googlenews_utils.MAX_PAGES
    assert len(results) == googlenews_utils.MAX_PAGES


def _route_with(monkeypatch, method, primary, vendors):
    monkeypatch.setattr(interface, "get_vendor", lambda *_a, **_k: primary)
    monkeypatch.setitem(interface.VENDOR_METHODS, method, vendors)


def test_route_falls_through_after_alpha_vantage_timeout(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr(alpha_vantage_common.requests, "get", _raise_timeout)
    _route_with(
        monkeypatch,
        "get_insider_transactions",
        "alpha_vantage",
        {
            "alpha_vantage": interface.get_alpha_vantage_insider_transactions,
            "yfinance": lambda *_a, **_k: "yfinance insider data",
        },
    )
    assert interface._route("get_insider_transactions", "AAPL") == "yfinance insider data"


def test_route_falls_through_after_google_news_timeout(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(googlenews_utils.requests, "get", _raise_timeout)
    _route_with(
        monkeypatch,
        "get_news",
        "google",
        {
            "google": interface.get_google_news,
            "yfinance": lambda *_a, **_k: "yfinance news",
        },
    )
    assert interface._route("get_news", "AAPL", "2026-01-01", "2026-01-07") == "yfinance news"
