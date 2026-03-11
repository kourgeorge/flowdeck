import { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';

const formatB = (v: number | null | undefined) => {
  if (v == null || Number.isNaN(v)) return '';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(v);
};

const formatPct = (v: number | null | undefined) => (v != null && !Number.isNaN(v) ? `${v}%` : '');

export interface FinancialChartsData {
  ticker: string;
  frequency: string;
  error?: string;
  historical_financials: {
    periods: string[];
    revenue: (number | null)[];
    operating_income: (number | null)[];
    eps: (number | null)[];
  } | null;
  shares_outstanding: { periods: string[]; values: (number | null)[] } | null;
  long_term_debt_vs_fcf: {
    periods: string[];
    long_term_debt: (number | null)[];
    free_cash_flow: (number | null)[];
  } | null;
  retained_earnings: { periods: string[]; values: (number | null)[] } | null;
  total_cash_vs_long_term_debt: {
    periods: string[];
    total_cash: (number | null)[];
    long_term_debt: (number | null)[];
  } | null;
  accounts_receivable_vs_revenue: {
    periods: string[];
    accounts_receivable: (number | null)[];
    revenue: (number | null)[];
  } | null;
  dividend_sustainability: {
    periods: string[];
    dividends_paid: (number | null)[];
    free_cash_flow: (number | null)[];
  } | null;
  performance_metrics: {
    periods: string[];
    gross_margin_pct: (number | null)[];
    pretax_margin_pct: (number | null)[];
    roic_pct: (number | null)[];
  } | null;
}

function buildChartData<T extends Record<string, (number | null)[]>>(
  periods: string[],
  series: T
): Array<{ period: string } & Record<keyof T, number | null>> {
  // Reverse so x-axis is chronological: oldest (left) → newest (right)
  const rows = periods.map((period, i) => {
    const row: Record<string, string | number | null> = { period: period.length > 7 ? period.slice(0, 7) : period };
    (Object.keys(series) as (keyof T)[]).forEach((k) => {
      const arr = series[k];
      (row as Record<string, string | number | null>)[k as string] = arr && arr[i] != null ? arr[i]! : null;
    });
    return row as { period: string } & Record<keyof T, number | null>;
  });
  return rows.reverse();
}

const chartTheme = {
  grid: '#374151',
  text: '#9ca3af',
  tooltipBg: '#1f2937',
};

interface FundamentalChartsProps {
  ticker: string;
  apiBase?: string;
}

export default function FundamentalCharts({ ticker, apiBase = '' }: FundamentalChartsProps) {
  const [data, setData] = useState<FinancialChartsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [freq, setFreq] = useState<'annual' | 'quarterly'>('annual');

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    fetch(`${apiBase}/api/data/financial-charts/${ticker}?freq=${freq}`)
      .then((r) => r.json())
      .then((d: FinancialChartsData) => {
        setData(d);
        if (d.error) setError(d.error);
      })
      .catch((e) => {
        setError(e.message || 'Failed to load chart data');
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [ticker, freq, apiBase]);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="animate-pulse h-64 bg-gray-700 rounded" />
      </div>
    );
  }
  if (error || (data && data.error)) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <p className="text-amber-400">{(data && data.error) || error || 'Failed to load chart data'}</p>
      </div>
    );
  }
  if (!data) return null;

  const hasAny =
    data.historical_financials ||
    data.shares_outstanding ||
    data.long_term_debt_vs_fcf ||
    data.retained_earnings ||
    data.total_cash_vs_long_term_debt ||
    data.accounts_receivable_vs_revenue ||
    data.dividend_sustainability ||
    data.performance_metrics;
  if (!hasAny) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <p className="text-gray-400">No chart data available for this ticker from Yahoo Finance.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Financial Charts (Yahoo Finance)</h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setFreq('annual')}
            className={`px-3 py-1.5 text-sm rounded ${freq === 'annual' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
          >
            Annual
          </button>
          <button
            type="button"
            onClick={() => setFreq('quarterly')}
            className={`px-3 py-1.5 text-sm rounded ${freq === 'quarterly' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
          >
            Quarterly
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {data.historical_financials && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Historical Financials</h4>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart
              data={buildChartData(data.historical_financials.periods, {
                revenue: data.historical_financials.revenue,
                operating_income: data.historical_financials.operating_income,
                eps: data.historical_financials.eps,
              })}
              margin={{ top: 10, right: 50, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis yAxisId="left" tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: chartTheme.text }} />
              <Tooltip
                contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }}
                labelStyle={{ color: '#fff' }}
                formatter={(value: number | undefined) => [typeof value === 'number' && value > 1e6 ? formatB(value) : value, '']}
              />
              <Legend />
              <Bar yAxisId="left" dataKey="revenue" name="Revenue" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              <Bar yAxisId="left" dataKey="operating_income" name="Operating Income" fill="#22c55e" radius={[2, 2, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="eps" name="EPS" stroke="#f97316" dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.performance_metrics && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Historical Performance Metrics (%)</h4>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={buildChartData(data.performance_metrics.periods, {
                gross_margin_pct: data.performance_metrics.gross_margin_pct,
                pretax_margin_pct: data.performance_metrics.pretax_margin_pct,
                roic_pct: data.performance_metrics.roic_pct,
              })}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis tick={{ fill: chartTheme.text }} tickFormatter={formatPct} domain={[0, 'auto']} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatPct(v), '']} />
              <Legend />
              <Line type="monotone" dataKey="gross_margin_pct" name="Gross Margin %" stroke="#a855f7" dot={{ r: 3 }} />
              <Line type="monotone" dataKey="pretax_margin_pct" name="Pretax Margin %" stroke="#06b6d4" dot={{ r: 3 }} />
              <Line type="monotone" dataKey="roic_pct" name="ROIC %" stroke="#f97316" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.shares_outstanding && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Shares Outstanding (Diluted)</h4>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart
              data={buildChartData(data.shares_outstanding.periods, { values: data.shares_outstanding.values })}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatB(v), 'Shares']} />
              <Line type="monotone" dataKey="values" name="Shares" stroke="#8b5cf6" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.long_term_debt_vs_fcf && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Long Term Debt vs Free Cash Flow</h4>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={buildChartData(data.long_term_debt_vs_fcf.periods, {
                long_term_debt: data.long_term_debt_vs_fcf.long_term_debt,
                free_cash_flow: data.long_term_debt_vs_fcf.free_cash_flow,
              })}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatB(v), '']} />
              <Legend />
              <Bar dataKey="long_term_debt" name="Long Term Debt" fill="#ef4444" radius={[2, 2, 0, 0]} />
              <Bar dataKey="free_cash_flow" name="Free Cash Flow" fill="#22c55e" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.retained_earnings && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Retained Earnings</h4>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart
              data={buildChartData(data.retained_earnings.periods, { values: data.retained_earnings.values })}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatB(v), '']} />
              <Area type="monotone" dataKey="values" name="Retained Earnings" stroke="#a855f7" fill="#a855f7" fillOpacity={0.4} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.total_cash_vs_long_term_debt && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Total Cash vs Long Term Debt</h4>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={buildChartData(data.total_cash_vs_long_term_debt.periods, {
                total_cash: data.total_cash_vs_long_term_debt.total_cash,
                long_term_debt: data.total_cash_vs_long_term_debt.long_term_debt,
              })}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatB(v), '']} />
              <Legend />
              <Bar dataKey="total_cash" name="Total Cash" fill="#22c55e" radius={[2, 2, 0, 0]} />
              <Bar dataKey="long_term_debt" name="Long Term Debt" fill="#ef4444" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.accounts_receivable_vs_revenue && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Accounts Receivable vs Revenue</h4>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart
              data={buildChartData(data.accounts_receivable_vs_revenue.periods, {
                accounts_receivable: data.accounts_receivable_vs_revenue.accounts_receivable,
                revenue: data.accounts_receivable_vs_revenue.revenue,
              })}
              margin={{ top: 10, right: 50, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis yAxisId="left" tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatB(v), '']} />
              <Legend />
              <Bar yAxisId="left" dataKey="accounts_receivable" name="A/R" fill="#f97316" radius={[2, 2, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="revenue" name="Revenue" stroke="#a855f7" dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.dividend_sustainability && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <h4 className="text-white font-medium mb-4">Dividend Sustainability (Dividends Paid vs FCF)</h4>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={buildChartData(data.dividend_sustainability.periods, {
                dividends_paid: data.dividend_sustainability.dividends_paid,
                free_cash_flow: data.dividend_sustainability.free_cash_flow,
              })}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="period" tick={{ fill: chartTheme.text }} />
              <YAxis tick={{ fill: chartTheme.text }} tickFormatter={formatB} />
              <Tooltip contentStyle={{ backgroundColor: chartTheme.tooltipBg, border: '1px solid #374151' }} formatter={(v: number | undefined) => [formatB(v), '']} />
              <Legend />
              <Bar dataKey="dividends_paid" name="Dividends Paid" fill="#eab308" radius={[2, 2, 0, 0]} />
              <Bar dataKey="free_cash_flow" name="Free Cash Flow" fill="#22c55e" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      </div>
    </div>
  );
}
