import { useEffect, useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { tickerApi } from '../services/api';

interface HistoricalPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const PERIODS = [
  { label: '1D', value: '1d' },
  { label: '1W', value: '5d' },
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: 'YTD', value: 'ytd' },
  { label: '1Y', value: '1y' },
  { label: '5Y', value: '5y' },
  { label: '10Y', value: '10y' },
  { label: 'MAX', value: 'max' },
];

interface DashboardPriceTrendsChartProps {
  tickers: string[];
  period?: string;
  height?: number;
}

// Distinct colors for up to ~15 stocks (colorblind-friendly palette)
const LINE_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#84cc16', // lime
  '#f97316', // orange
  '#6366f1', // indigo
  '#14b8a6', // teal
  '#a855f7', // purple
  '#eab308', // yellow
  '#22c55e', // green
  '#ef4444', // red
  '#64748b', // slate
];

function formatPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function formatDate(dateStr: string, is1D?: boolean): string {
  const d = new Date(dateStr);
  if (is1D && dateStr.includes('T')) {
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' });
}

export default function DashboardPriceTrendsChart({
  tickers,
  period: initialPeriod = '6mo',
  height = 340,
}: DashboardPriceTrendsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState(initialPeriod);
  const [seriesByTicker, setSeriesByTicker] = useState<Record<string, { date: string; pct: number }[]>>({});
  const [visibleTickers, setVisibleTickers] = useState<Set<string>>(() => new Set(tickers));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reset visible tickers when tickers change; default all visible
  useEffect(() => {
    setVisibleTickers(new Set(tickers));
  }, [tickers.join(',')]);

  const toggleTicker = (ticker: string) => {
    setVisibleTickers((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else {
        next.add(ticker);
      }
      return next;
    });
  };

  useEffect(() => {
    if (tickers.length === 0) {
      setSeriesByTicker({});
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;

    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const interval = selectedPeriod === '1d' ? '5m' : '1d';
        const results = await Promise.allSettled(
          tickers.map((ticker) => tickerApi.getHistoricalPrices(ticker, selectedPeriod, interval))
        );

        const next: Record<string, { date: string; pct: number }[]> = {};
        results.forEach((result, i) => {
          const ticker = tickers[i];
          if (result.status === 'rejected' || cancelled) return;
          const data = result.status === 'fulfilled' ? result.value : null;
          const prices: HistoricalPrice[] = data?.data ?? [];
          if (prices.length === 0) return;
          const firstClose = prices[0].close;
          if (firstClose <= 0) return;
          next[ticker] = prices.map((d) => ({
            date: d.date,
            pct: ((d.close - firstClose) / firstClose) * 100,
          }));
        });

        if (!cancelled) setSeriesByTicker(next);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchAll();
    return () => {
      cancelled = true;
    };
  }, [tickers.join(','), selectedPeriod]);

  const chartData = useMemo(() => {
    const tickerList = Object.keys(seriesByTicker);
    if (tickerList.length === 0) return [];

    const dateSet = new Set<string>();
    tickerList.forEach((t) => {
      seriesByTicker[t].forEach((p) => dateSet.add(p.date));
    });
    const sortedDates = Array.from(dateSet).sort();

    const byTicker: Record<string, Map<string, number>> = {};
    tickerList.forEach((t) => {
      const map = new Map<string, number>();
      let lastPct: number | null = null;
      sortedDates.forEach((date) => {
        const point = seriesByTicker[t].find((p) => p.date === date);
        if (point != null) {
          lastPct = point.pct;
        }
        if (lastPct != null) map.set(date, lastPct);
      });
      byTicker[t] = map;
    });

    return sortedDates.map((date) => {
      const row: Record<string, string | number | null> = { date };
      tickerList.forEach((t) => {
        row[t] = byTicker[t].get(date) ?? null;
      });
      return row;
    });
  }, [seriesByTicker]);

  const chartTheme = {
    grid: '#374151',
    text: '#9ca3af',
    tooltipBg: '#1f2937',
    tooltipBorder: '#4b5563',
    zeroLine: 'rgba(148, 163, 184, 0.4)', // mild slate-400
  };

  if (tickers.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-2">Price trends (% change)</h3>
        <p className="text-gray-400 text-sm">Subscribe to stocks to see their price trends here.</p>
      </div>
    );
  }

  if (loading && chartData.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-2">Price trends (% change)</h3>
        <div className="animate-pulse h-[280px] bg-gray-700 rounded mt-4" />
      </div>
    );
  }

  if (error && chartData.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-2">Price trends (% change)</h3>
        <p className="text-gray-400 text-sm">{error}</p>
      </div>
    );
  }

  const tickerList = Object.keys(seriesByTicker);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div>
          <h3 className="text-lg font-semibold text-white">Price trends (% change)</h3>
          <p className="text-gray-500 text-xs sm:text-sm mt-0.5">
            {selectedPeriod === '1d'
              ? 'Intraday trend for the last trading day. One line per subscribed stock.'
              : 'Normalized from start of period. One line per subscribed stock.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 justify-end">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setSelectedPeriod(p.value)}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                selectedPeriod === p.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 8, left: 8, bottom: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
            <XAxis
              dataKey="date"
              tick={{ fill: chartTheme.text, fontSize: 11 }}
              tickFormatter={(v) => formatDate(v, selectedPeriod === '1d')}
            />
            <YAxis
              tick={{ fill: chartTheme.text, fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
              domain={['auto', 'auto']}
            />
            <ReferenceLine y={0} stroke={chartTheme.zeroLine} strokeWidth={1} strokeDasharray="4 4" />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || payload.length === 0) return null;
                const safeLabel = typeof label === 'string' ? label : '';
                const sorted = [...payload].sort((a, b) => {
                  const va = a.value != null && typeof a.value === 'number' ? a.value : -Infinity;
                  const vb = b.value != null && typeof b.value === 'number' ? b.value : -Infinity;
                  return vb - va;
                });
                return (
                  <div
                    style={{
                      backgroundColor: chartTheme.tooltipBg,
                      border: `1px solid ${chartTheme.tooltipBorder}`,
                      borderRadius: '8px',
                      padding: '8px 12px',
                      maxWidth: 320,
                    }}
                  >
                    <div style={{ color: '#e5e7eb', marginBottom: 6, fontWeight: 500 }}>
                      {formatDate(safeLabel, selectedPeriod === '1d')}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {sorted.map((entry) => (
                        <div key={String(entry.name)} style={{ color: entry.color ?? chartTheme.text, fontSize: 12 }}>
                          {entry.name}: {formatPct(entry.value as number)}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 12 }}
              iconType="line"
              iconSize={10}
              content={({ payload }) => (
                <div className="flex flex-wrap gap-x-4 gap-y-1 justify-center mt-2">
                  {payload?.map((entry) => {
                    const ticker = String(entry.value ?? '');
                    const visible = visibleTickers.has(ticker);
                    return (
                      <button
                        key={ticker}
                        type="button"
                        onClick={() => toggleTicker(ticker)}
                        className="inline-flex items-center gap-1.5 text-xs transition-opacity hover:opacity-100"
                        style={{
                          color: entry.color ?? chartTheme.text,
                          opacity: visible ? 1 : 0.4,
                          cursor: 'pointer',
                        }}
                      >
                        <span
                          className="w-3 h-0.5 shrink-0 rounded"
                          style={{ backgroundColor: entry.color ?? chartTheme.text }}
                        />
                        {ticker}
                      </button>
                    );
                  })}
                </div>
              )}
            />
            {tickerList.map((ticker, i) => (
              <Line
                key={ticker}
                type="monotone"
                dataKey={ticker}
                name={ticker}
                stroke={LINE_COLORS[i % LINE_COLORS.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={true}
                hide={!visibleTickers.has(ticker)}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
