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


# OLD has a close before the 2025-11-16 start; NEWIPO only starts trading on
# 2026-07-01, so it has no previous close and must be named, not measured.
_IPO_PRICES = json.dumps({'data': {
    'OLD': 'Date,Close\n2025-11-10,100\n2026-03-02,110\n2026-11-13,120\n',
    'NEWIPO': 'Date,Close\n2026-07-01,20\n2026-11-13,30\n',
}})


def _fake_skill(skill_cls, prices, subs='**OLD**\n**NEWIPO**'):
    from types import SimpleNamespace

    def fake_call_tool(self, executor, ctx, steps, n, tool_name, **kwargs):
        if tool_name == 'get_user_subscriptions':
            return SimpleNamespace(ok=True, to_str=lambda: subs)
        return SimpleNamespace(ok=True, to_str=lambda: prices)

    skill = skill_cls()
    skill.call_tool = fake_call_tool.__get__(skill)
    return skill


def test_period_returns_report_skipped_tickers():
    from ai_engine.agent.skills._periods import compute_period_returns_with_skipped

    results, skipped = compute_period_returns_with_skipped(_IPO_PRICES, ['OLD', 'NEWIPO'], '2025-11-16', '2026-11-16')
    assert [r['ticker'] for r in results] == ['OLD']
    assert results[0]['return_pct'] == 20
    assert skipped == ['NEWIPO']


def test_portfolio_names_ticker_without_history_and_counts_measured_only():
    from ai_engine.agent.skills.portfolio_performance import PortfolioPerformanceSkill

    result = _fake_skill(PortfolioPerformanceSkill, _IPO_PRICES).run(None, None, period='2025-11-16:2026-11-16')
    table_rows = [l for l in result.data.splitlines() if l.startswith('| ') and 'Ticker' not in l]
    assert len(table_rows) == 1 and 'OLD' in table_rows[0] and '+   20.00%' in table_rows[0]
    assert 'No full price history for this period: NEWIPO' in result.data
    assert '**Tickers analysed:** 1' in result.data
    assert 'Top gainer' not in result.data and 'Top loser' not in result.data
    chart = json.loads(result.data.split('CHART_JSON:', 1)[1])
    assert [row['ticker'] for row in chart['data']] == ['OLD']


def test_portfolio_keeps_gainer_and_loser_with_two_measured():
    from ai_engine.agent.skills.portfolio_performance import PortfolioPerformanceSkill

    result = _fake_skill(PortfolioPerformanceSkill, _PRICES, subs='**TEST**\n**OTHER**').run(
        None, None, period='2026-01-01:2026-01-05')
    assert '**Tickers analysed:** 2' in result.data
    assert '**🏆 Top gainer:** TEST' in result.data
    assert '**📉 Top loser:** OTHER' in result.data
    assert 'No full price history' not in result.data


def test_compare_stocks_names_ticker_without_history():
    from ai_engine.agent.skills.compare_stocks import CompareStocksSkill

    result = _fake_skill(CompareStocksSkill, _IPO_PRICES).run(
        None, None, tickers=['OLD', 'NEWIPO'], period='2025-11-16:2026-11-16')
    assert result.ok
    assert 'No full price history for this period: NEWIPO' in result.data
    assert 'Best performer' not in result.data and 'Worst performer' not in result.data
    table_rows = [l for l in result.data.splitlines() if l.startswith('| ') and 'Ticker' not in l]
    assert len(table_rows) == 1 and 'OLD' in table_rows[0]


def test_compare_stocks_title_and_count_use_measured_tickers_only():
    from ai_engine.agent.skills.compare_stocks import CompareStocksSkill

    # NEWCO's first trade falls inside the period; GHOST has no rows at all.
    prices = json.dumps({'data': {
        'AAPL': 'Date,Close\n2025-12-31,100\n2026-01-05,110\n',
        'NEWCO': 'Date,Close\n2026-01-02,10\n2026-01-05,12\n',
    }})
    result = _fake_skill(CompareStocksSkill, prices).run(
        None, None, tickers=['AAPL', 'NEWCO', 'GHOST'], period='2026-01-01:2026-01-05')
    assert result.ok
    assert '# ⚖️ Market Comparison: AAPL\n' in result.data
    assert 'NEWCO' not in result.data.split('\n', 1)[0]
    assert 'Best performer' not in result.data and 'Worst performer' not in result.data
    assert ('No full price history for this period: '
            'NEWCO (no price before the start), GHOST (no data at all)') in result.data
    assert result.metrics['tickers_compared'] == 1
    chart = json.loads(result.data.split('CHART_JSON:', 1)[1])
    assert chart['title'].startswith('% Return: AAPL —')
    assert [row['ticker'] for row in chart['data']] == ['AAPL']


def test_portfolio_names_reason_for_skipped_ticker():
    from ai_engine.agent.skills.portfolio_performance import PortfolioPerformanceSkill

    result = _fake_skill(PortfolioPerformanceSkill, _IPO_PRICES).run(None, None, period='2025-11-16:2026-11-16')
    assert 'No full price history for this period: NEWIPO (no price before the start)' in result.data
