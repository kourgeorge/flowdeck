import { useEffect, useState, useCallback } from 'react';
import { tickerApi } from '../services/api';

export type MarketMoverRow = {
  symbol: string | null;
  shortName: string | null;
  sector?: string | null;
  industry?: string | null;
  regularMarketPrice: number | null;
  regularMarketChange: number | null;
  regularMarketChangePercent: number | null;
  regularMarketPreviousClose: number | null;
  regularMarketVolume: number | null;
};

interface DashboardMarketMoversProps {
  count?: number;
  onSelectTicker?: (ticker: string) => void;
}

function formatPrice(n: number | null): string {
  if (n == null) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPct(n: number | null): string {
  if (n == null) return '—';
  const s = n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2);
  return `${s}%`;
}

function formatVolume(n: number | null): string {
  if (n == null) return '—';
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return String(n);
}

function MoversTable({
  rows,
  title,
  changeColor,
  onSelectTicker,
}: {
  rows: MarketMoverRow[];
  title: string;
  changeColor: 'gainers' | 'losers' | 'neutral';
  onSelectTicker?: (ticker: string) => void;
}) {
  const changeClass =
    changeColor === 'gainers' ? 'text-green-400' : changeColor === 'losers' ? 'text-red-400' : 'text-gray-300';
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700 bg-gray-800/80">
        <h3 className="text-white font-semibold text-sm">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              <th className="py-2 px-3 font-medium">Symbol</th>
              <th className="py-2 px-3 font-medium min-w-0 truncate max-w-[140px]">Name</th>
              <th className="py-2 px-3 font-medium">Sector</th>
              <th className="py-2 px-3 font-medium text-right">Price</th>
              <th className="py-2 px-3 font-medium text-right">Change %</th>
              <th className="py-2 px-3 font-medium text-right">Volume</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const sym = row.symbol ?? '';
              const clickable = onSelectTicker && sym;
              return (
                <tr
                  key={sym || i}
                  onClick={() => clickable && onSelectTicker(sym)}
                  className={`border-b border-gray-700/70 ${clickable ? 'cursor-pointer hover:bg-gray-700/50 transition-colors' : ''}`}
                >
                  <td className="py-2.5 px-3 font-medium text-white">{sym || '—'}</td>
                  <td className="py-2.5 px-3 text-gray-300 truncate max-w-[140px]" title={row.shortName ?? undefined}>
                    {row.shortName || '—'}
                  </td>
                  <td className="py-2.5 px-3 text-gray-400 truncate max-w-[120px]" title={row.industry ?? undefined}>
                    {row.sector || '—'}
                  </td>
                  <td className="py-2.5 px-3 text-right text-gray-200 tabular-nums">{formatPrice(row.regularMarketPrice)}</td>
                  <td className={`py-2.5 px-3 text-right font-medium tabular-nums ${changeClass}`}>
                    {formatPct(row.regularMarketChangePercent)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-gray-400 tabular-nums">{formatVolume(row.regularMarketVolume)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DashboardMarketMovers({ count = 25, onSelectTicker }: DashboardMarketMoversProps) {
  const [gainers, setGainers] = useState<MarketMoverRow[]>([]);
  const [losers, setLosers] = useState<MarketMoverRow[]>([]);
  const [mostActive, setMostActive] = useState<MarketMoverRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMovers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await tickerApi.getMarketMovers(count);
      setGainers(data.gainers ?? []);
      setLosers(data.losers ?? []);
      setMostActive(data.most_active ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market movers');
      setGainers([]);
      setLosers([]);
      setMostActive([]);
    } finally {
      setIsLoading(false);
    }
  }, [count]);

  useEffect(() => {
    fetchMovers();
  }, [fetchMovers]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex items-center gap-2 text-gray-400">
          <svg className="w-5 h-5 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>Loading gainers, losers & most active…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-8 text-center">
        <p className="text-red-400 text-sm mb-2">{error}</p>
        <button
          type="button"
          onClick={fetchMovers}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      <MoversTable
        rows={gainers}
        title="Top gainers"
        changeColor="gainers"
        onSelectTicker={onSelectTicker}
      />
      <MoversTable
        rows={losers}
        title="Top losers"
        changeColor="losers"
        onSelectTicker={onSelectTicker}
      />
      <MoversTable
        rows={mostActive}
        title="Most active"
        changeColor="neutral"
        onSelectTicker={onSelectTicker}
      />
    </div>
  );
}
