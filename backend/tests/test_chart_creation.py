import json
from types import SimpleNamespace


def _run_chart(prices: dict, tickers: list[str]):
    from ai_engine.agent.skills.chart_creation import CreateChartSkill

    payload = json.dumps({'data': prices})

    def fake_call_tool(self, executor, ctx, steps, n, tool_name, **kwargs):
        return SimpleNamespace(ok=True, to_str=lambda: payload)

    skill = CreateChartSkill()
    skill.call_tool = fake_call_tool.__get__(skill)
    result = skill.run(None, None, tickers=tickers, period='2026-01-16:2026-01-21')
    assert result.ok
    summary, chart_json = result.data.split('CHART_JSON:', 1)
    return summary, json.loads(chart_json)


def test_chart_plots_ticker_missing_from_first_row():
    # NEWCO has no close on 2026-01-16, the earliest date in the merged rows.
    summary, chart = _run_chart({
        'AAPL': 'Date,Close\n2026-01-16,100\n2026-01-20,101\n2026-01-21,102\n',
        'NEWCO': 'Date,Close\n2026-01-20,50\n2026-01-21,55\n',
    }, ['AAPL', 'NEWCO'])

    assert chart['yKeys'] == ['AAPL', 'NEWCO']
    assert len(chart['colors']) == 2
    assert chart['yAxisConfig']['min'] < 50
    assert chart['yAxisConfig']['max'] > 102
    assert 'NEWCO' in chart['title']
    assert 'No price data' not in summary


def test_chart_reports_ticker_without_data():
    summary, chart = _run_chart({
        'AAPL': 'Date,Close\n2026-01-16,100\n2026-01-20,101\n',
    }, ['AAPL', 'ZZZZ'])

    assert chart['yKeys'] == ['AAPL']
    assert len(chart['colors']) == 1
    assert 'ZZZZ' not in chart['title']
    assert 'Line chart of **AAPL**' in summary
    assert 'No price data found for ZZZZ' in summary
