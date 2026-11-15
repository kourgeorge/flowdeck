import datetime
import json


# Dec 31 close is the last one before the Jan 1 start, so the period return is
# 100 -> 110 = +10%. Measuring from the first in-range close (105) would give
# about +4.76% and leave out the Jan 2 move.
_PRICES = json.dumps({'data': {
    'TEST': 'Date,Close\n2025-12-30,80\n2025-12-31,100\n2026-01-02,105\n2026-01-05,110\n',
    'OTHER': 'Date,Close\n2025-12-31,50\n2026-01-02,45\n2026-01-05,40\n',
}})


def test_portfolio_returns_match_compare_stocks_previous_close():
    from ai_engine.agent.skills.compare_stocks import _compute_returns
    from ai_engine.agent.skills.portfolio_performance import _build_returns_report

    compare = {r['ticker']: r['return_pct'] for r in _compute_returns(_PRICES, ['TEST', 'OTHER'], '2026-01-01', '2026-01-05')}
    assert compare == {'TEST': 10, 'OTHER': -20}

    _, chart_json = _build_returns_report(_PRICES, 'Test', '2026-01-01', '2026-01-05')
    portfolio = {row['ticker']: row['return_pct'] for row in json.loads(chart_json)['data']}
    assert portfolio == compare


def test_portfolio_fetch_reaches_back_for_previous_close():
    from types import SimpleNamespace
    from ai_engine.agent.skills.portfolio_performance import PortfolioPerformanceSkill

    calls = {}

    def fake_call_tool(self, executor, ctx, steps, n, tool_name, **kwargs):
        calls[tool_name] = kwargs
        if tool_name == 'get_user_subscriptions':
            return SimpleNamespace(ok=True, to_str=lambda: '**TEST**')
        return SimpleNamespace(ok=True, to_str=lambda: _PRICES)

    skill = PortfolioPerformanceSkill()
    skill.call_tool = fake_call_tool.__get__(skill)
    result = skill.run(None, None, period='2026-01-01:2026-01-05')
    assert calls['get_multi_historical_prices']['start_date'] == '2025-12-18'
    assert '+   10.00%' in result.data


def test_chart_creation_resolves_1w_to_one_week():
    from ai_engine.agent.skills.chart_creation import _resolve_period

    start, end, label = _resolve_period('1w')
    start_d, end_d = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    assert label == 'Last Week'
    assert start_d.weekday() == 0 and (end_d - start_d).days == 4
    assert (datetime.date.today() - start_d).days <= 13

    assert _resolve_period('this week')[2] == 'This Week'
    assert _resolve_period(None)[2] == 'Past 1 Year'
