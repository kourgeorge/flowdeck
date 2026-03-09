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

type OverviewItem = {
  ticker: string;
  name: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
};

interface MarketViewProps {
  moversCount?: number;
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

function OverviewCard({
  item,
  onSelectTicker,
}: {
  item: OverviewItem;
  onSelectTicker?: (ticker: string) => void;
}) {
  const hasChange = item.changePercent != null;
  const positive = (item.changePercent ?? 0) >= 0;
  const changeClass = !hasChange ? 'text-gray-400' : positive ? 'text-green-400' : 'text-red-400';
  const clickable = onSelectTicker && item.ticker && !item.ticker.startsWith('^');

  return (
    <div
      role={clickable ? 'button' : undefined}
      onClick={() => clickable && onSelectTicker(item.ticker)}
      className={`min-h-[4.5rem] rounded-lg border border-gray-600 bg-gray-800 px-4 py-3 flex flex-col justify-center transition-colors ${
        clickable ? 'cursor-pointer hover:border-gray-500 hover:bg-gray-700/80' : ''
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-gray-300 text-sm font-medium truncate" title={item.name}>
          {item.name}
        </span>
        {item.ticker && (
          <span className="text-gray-500 text-xs shrink-0 tabular-nums">{item.ticker}</span>
        )}
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-2">
        <span className="text-white font-semibold tabular-nums">{formatPrice(item.price)}</span>
        <span className={`text-sm font-medium tabular-nums ${changeClass}`}>
          {formatPct(item.changePercent)}
        </span>
      </div>
    </div>
  );
}

const TILES_PER_PAGE = 6;

function OverviewSection({
  title,
  items,
  currentPage,
  totalPages,
  onPrev,
  onNext,
  paginationLoading,
  onSelectTicker,
}: {
  title: string;
  items: OverviewItem[];
  currentPage: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
  paginationLoading?: boolean;
  onSelectTicker?: (ticker: string) => void;
}) {
  const canPrev = totalPages > 1 && currentPage > 0;
  const canNext = totalPages > 1 && currentPage < totalPages - 1;
  if (items.length === 0 && totalPages === 0) return null;
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/60 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-700 bg-gray-800/80 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">{title}</h3>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onPrev}
            disabled={!canPrev || paginationLoading}
            className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors"
            aria-label="Previous page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-xs text-gray-500 tabular-nums min-w-[4rem] text-center">
            {totalPages > 0 ? `${currentPage + 1} / ${totalPages}` : '—'}
          </span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNext || paginationLoading}
            className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors"
            aria-label="Next page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-2 gap-3">
          {items.map((item) => (
            <OverviewCard key={item.ticker} item={item} onSelectTicker={onSelectTicker} />
          ))}
        </div>
      </div>
    </div>
  );
}

function MoversTable({
  rows,
  title,
  isGainers,
  onSelectTicker,
}: {
  rows: MarketMoverRow[];
  title: string;
  isGainers: boolean;
  onSelectTicker?: (ticker: string) => void;
}) {
  const changeClass = isGainers ? 'text-green-400' : 'text-red-400';
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

export default function MarketView({ moversCount = 25, onSelectTicker }: MarketViewProps) {
  const [overview, setOverview] = useState<{
    indices: OverviewItem[];
    sectors: OverviewItem[];
    international: OverviewItem[];
  } | null>(null);
  const [totals, setTotals] = useState({ totalIndices: 0, totalSectors: 0, totalRegions: 0 });
  const [pages, setPages] = useState({ indices: 0, sectors: 0, regions: 0 });
  const [gainers, setGainers] = useState<MarketMoverRow[]>([]);
  const [losers, setLosers] = useState<MarketMoverRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paginationSection, setPaginationSection] = useState<'indices' | 'sectors' | 'regions' | null>(null);

  const fetchOverview = useCallback(async (pageIndices: number, pageSectors: number, pageRegions: number) => {
    const data = await tickerApi.getMarketOverview({
      limit_indices: TILES_PER_PAGE,
      offset_indices: pageIndices * TILES_PER_PAGE,
      limit_sectors: TILES_PER_PAGE,
      offset_sectors: pageSectors * TILES_PER_PAGE,
      limit_regions: TILES_PER_PAGE,
      offset_regions: pageRegions * TILES_PER_PAGE,
    });
    setOverview({
      indices: data.indices ?? [],
      sectors: data.sectors ?? [],
      international: data.international ?? [],
    });
    setTotals({
      totalIndices: data.totalIndices ?? 0,
      totalSectors: data.totalSectors ?? 0,
      totalRegions: data.totalRegions ?? 0,
    });
    setPages({ indices: pageIndices, sectors: pageSectors, regions: pageRegions });
    return data;
  }, []);

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [overviewData, moversData] = await Promise.all([
        tickerApi.getMarketOverview({
          limit_indices: TILES_PER_PAGE,
          offset_indices: 0,
          limit_sectors: TILES_PER_PAGE,
          offset_sectors: 0,
          limit_regions: TILES_PER_PAGE,
          offset_regions: 0,
        }),
        tickerApi.getMarketMovers(moversCount),
      ]);
      setOverview({
        indices: overviewData.indices ?? [],
        sectors: overviewData.sectors ?? [],
        international: overviewData.international ?? [],
      });
      setTotals({
        totalIndices: overviewData.totalIndices ?? 0,
        totalSectors: overviewData.totalSectors ?? 0,
        totalRegions: overviewData.totalRegions ?? 0,
      });
      setPages({ indices: 0, sectors: 0, regions: 0 });
      setGainers(moversData.gainers ?? []);
      setLosers(moversData.losers ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
      setOverview(null);
      setGainers([]);
      setLosers([]);
    } finally {
      setIsLoading(false);
    }
  }, [moversCount]);

  const totalPagesIndices = Math.max(1, Math.ceil(totals.totalIndices / TILES_PER_PAGE));
  const totalPagesSectors = Math.max(1, Math.ceil(totals.totalSectors / TILES_PER_PAGE));
  const totalPagesRegions = Math.max(1, Math.ceil(totals.totalRegions / TILES_PER_PAGE));

  const handlePrevIndices = useCallback(async () => {
    if (paginationSection || pages.indices <= 0) return;
    const nextPage = pages.indices - 1;
    setPaginationSection('indices');
    try {
      await fetchOverview(nextPage, pages.sectors, pages.regions);
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextIndices = useCallback(async () => {
    if (paginationSection || pages.indices >= totalPagesIndices - 1) return;
    const nextPage = pages.indices + 1;
    setPaginationSection('indices');
    try {
      await fetchOverview(nextPage, pages.sectors, pages.regions);
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesIndices, fetchOverview]);

  const handlePrevSectors = useCallback(async () => {
    if (paginationSection || pages.sectors <= 0) return;
    const nextPage = pages.sectors - 1;
    setPaginationSection('sectors');
    try {
      await fetchOverview(pages.indices, nextPage, pages.regions);
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextSectors = useCallback(async () => {
    if (paginationSection || pages.sectors >= totalPagesSectors - 1) return;
    const nextPage = pages.sectors + 1;
    setPaginationSection('sectors');
    try {
      await fetchOverview(pages.indices, nextPage, pages.regions);
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesSectors, fetchOverview]);

  const handlePrevRegions = useCallback(async () => {
    if (paginationSection || pages.regions <= 0) return;
    const nextPage = pages.regions - 1;
    setPaginationSection('regions');
    try {
      await fetchOverview(pages.indices, pages.sectors, nextPage);
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextRegions = useCallback(async () => {
    if (paginationSection || pages.regions >= totalPagesRegions - 1) return;
    const nextPage = pages.regions + 1;
    setPaginationSection('regions');
    try {
      await fetchOverview(pages.indices, pages.sectors, nextPage);
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesRegions, fetchOverview]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex items-center gap-2 text-gray-400">
          <svg className="w-5 h-5 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>Loading market overview…</span>
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
          onClick={fetchAll}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Market overview */}
      <section className="space-y-6">
        <h2 className="text-lg font-semibold text-white border-b border-gray-700 pb-2">Market overview</h2>
        {overview && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <OverviewSection
              title="Indices"
              items={overview.indices}
              currentPage={pages.indices}
              totalPages={totalPagesIndices}
              onPrev={handlePrevIndices}
              onNext={handleNextIndices}
              paginationLoading={paginationSection === 'indices'}
              onSelectTicker={onSelectTicker}
            />
            <OverviewSection
              title="Sectors"
              items={overview.sectors}
              currentPage={pages.sectors}
              totalPages={totalPagesSectors}
              onPrev={handlePrevSectors}
              onNext={handleNextSectors}
              paginationLoading={paginationSection === 'sectors'}
              onSelectTicker={onSelectTicker}
            />
            <OverviewSection
              title="Regions"
              items={overview.international}
              currentPage={pages.regions}
              totalPages={totalPagesRegions}
              onPrev={handlePrevRegions}
              onNext={handleNextRegions}
              paginationLoading={paginationSection === 'regions'}
              onSelectTicker={onSelectTicker}
            />
          </div>
        )}
      </section>

      {/* Top gainers & losers */}
      <section className="space-y-6">
        <h2 className="text-lg font-semibold text-white border-b border-gray-700 pb-2">Top gainers & losers</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MoversTable
            rows={gainers}
            title="Top gainers"
            isGainers={true}
            onSelectTicker={onSelectTicker}
          />
          <MoversTable
            rows={losers}
            title="Top losers"
            isGainers={false}
            onSelectTicker={onSelectTicker}
          />
        </div>
      </section>
    </div>
  );
}
