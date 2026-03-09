import { useEffect, useState, useCallback, useMemo } from 'react';
import { tickerApi } from '../services/api';

export type HeadlineArticle = {
  uuid: string;
  title: string;
  publisher?: string;
  link: string;
  published_time: string | null;
  published_timestamp: number;
  type?: string;
  thumbnail?: string | null;
  ticker?: string;
};

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
      className={`min-h-[4.5rem] min-w-0 rounded-lg border border-gray-600 bg-gray-800 px-4 py-3 flex flex-col justify-center overflow-hidden transition-colors ${
        clickable ? 'cursor-pointer hover:border-gray-500 hover:bg-gray-700/80' : ''
      }`}
    >
      <div className="flex items-baseline justify-between gap-2 min-w-0">
        <span className="text-gray-300 text-sm font-medium truncate min-w-0" title={item.name}>
          {item.name}
        </span>
        {item.ticker && (
          <span className="text-gray-500 text-xs shrink-0 tabular-nums">{item.ticker}</span>
        )}
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-2 min-w-0">
        <span className="text-white font-semibold tabular-nums min-w-0 truncate" title={formatPrice(item.price)}>
          {formatPrice(item.price)}
        </span>
        <span className={`text-sm font-medium tabular-nums shrink-0 ${changeClass}`}>
          {formatPct(item.changePercent)}
        </span>
      </div>
    </div>
  );
}

const TILES_PER_PAGE = 6;
const MOVERS_PAGE_SIZE = 10;
const MOVERS_LOAD_COUNT = 20;

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
      <div className="px-4 py-2 border-b border-gray-700 bg-gray-800/80 flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{title}</h3>
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
  currentPage = 0,
  totalPages = 1,
  onPrev,
  onNext,
  pageSize = MOVERS_PAGE_SIZE,
}: {
  rows: MarketMoverRow[];
  title: string;
  isGainers: boolean;
  onSelectTicker?: (ticker: string) => void;
  currentPage?: number;
  totalPages?: number;
  onPrev?: () => void;
  onNext?: () => void;
  pageSize?: number;
}) {
  const changeClass = isGainers ? 'text-green-400' : 'text-red-400';
  const canPrev = totalPages > 1 && currentPage > 0;
  const canNext = totalPages > 1 && currentPage < totalPages - 1;
  const pageRows = totalPages > 1
    ? rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
    : rows;
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-700 bg-gray-800/80 flex items-center justify-between gap-2">
        <h3 className="text-white font-semibold text-xs">{title}</h3>
        {totalPages > 1 && onPrev != null && onNext != null && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onPrev}
              disabled={!canPrev}
              className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors"
              aria-label="Previous page"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <span className="text-xs text-gray-500 tabular-nums min-w-[4rem] text-center">
              {currentPage + 1} / {totalPages}
            </span>
            <button
              type="button"
              onClick={onNext}
              disabled={!canNext}
              className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors"
              aria-label="Next page"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              <th className="py-1.5 px-3 font-medium text-xs">Symbol</th>
              <th className="py-1.5 px-3 font-medium text-xs min-w-0 truncate max-w-[140px]">Name</th>
              <th className="py-1.5 px-3 font-medium text-xs w-0 max-w-[90px]">Sector</th>
              <th className="py-1.5 px-3 font-medium text-xs text-right">Price</th>
              <th className="py-1.5 px-3 font-medium text-xs text-right">Change %</th>
              <th className="py-1.5 px-3 font-medium text-xs text-right">Volume</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => {
              const sym = row.symbol ?? '';
              const clickable = onSelectTicker && sym;
              return (
                <tr
                  key={sym || i}
                  onClick={() => clickable && onSelectTicker(sym)}
                  className={`border-b border-gray-700/70 ${clickable ? 'cursor-pointer hover:bg-gray-700/50 transition-colors' : ''}`}
                >
                  <td className="py-2 px-3 font-medium text-white">{sym || '—'}</td>
                  <td className="py-2 px-3 text-gray-300 truncate max-w-[140px]" title={row.shortName ?? undefined}>
                    {row.shortName || '—'}
                  </td>
                  <td className="py-2 px-3 text-gray-400 truncate max-w-[90px]" title={row.industry ?? undefined}>
                    {row.sector || '—'}
                  </td>
                  <td className="py-2 px-3 text-right text-gray-200 tabular-nums">{formatPrice(row.regularMarketPrice)}</td>
                  <td className={`py-2 px-3 text-right font-medium tabular-nums ${changeClass}`}>
                    {formatPct(row.regularMarketChangePercent)}
                  </td>
                  <td className="py-2 px-3 text-right text-gray-400 tabular-nums">{formatVolume(row.regularMarketVolume)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const HEADLINES_STRIP_HEIGHT = 56;
const HEADLINES_REFRESH_MS = 120000;

function RunningHeadlinesStrip({
  articles,
  isLoading,
  tickerChangeMap = {},
}: {
  articles: HeadlineArticle[];
  isLoading: boolean;
  tickerChangeMap?: Record<string, number | null>;
}) {
  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800/80 px-4 text-gray-400 text-xs"
        style={{ minHeight: HEADLINES_STRIP_HEIGHT }}
        aria-live="polite"
        aria-busy="true"
      >
        <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <span>Loading news…</span>
      </div>
    );
  }
  if (articles.length === 0) {
    return (
      <div
        className="flex items-center rounded-lg border border-gray-700 bg-gray-800/80 px-4 text-gray-500 text-xs"
        style={{ minHeight: HEADLINES_STRIP_HEIGHT }}
        aria-live="polite"
      >
        No headlines
      </div>
    );
  }
  const itemNodes = articles.map((a) => {
    const changePercent = a.ticker != null ? tickerChangeMap[a.ticker] ?? tickerChangeMap[a.ticker.toUpperCase()] : null;
    const tickerColorClass =
      changePercent != null && changePercent > 0
        ? 'text-green-400'
        : changePercent != null && changePercent < 0
          ? 'text-red-400'
          : 'text-gray-500';
    return (
      <div
        key={a.uuid}
        className="shrink-0 border-r border-gray-600 pr-4 pl-4 first:pl-0 min-w-[240px] max-w-[320px] sm:max-w-[380px]"
      >
        {a.link ? (
          <a
            href={a.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-200 hover:text-white hover:underline text-xs leading-tight line-clamp-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 rounded"
          >
            {a.title}
            {a.ticker && <span className={`font-medium tabular-nums ${tickerColorClass}`}> [{a.ticker}]</span>}
          </a>
        ) : (
          <span className="text-gray-200 text-xs leading-tight line-clamp-2">
            {a.title}
            {a.ticker && <span className={`font-medium tabular-nums ${tickerColorClass}`}> [{a.ticker}]</span>}
          </span>
        )}
      </div>
    );
  });
  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/80 overflow-hidden"
      style={{ height: HEADLINES_STRIP_HEIGHT }}
      aria-live="polite"
    >
      <div className="h-full flex items-center overflow-hidden">
        <div
          className="flex items-center gap-0 pr-4 animate-tiles-scroll"
          style={{ animationDuration: `${Math.max(30, articles.length * 4)}s` }}
        >
          {itemNodes}
          {itemNodes}
        </div>
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
  const [moversPageGainers, setMoversPageGainers] = useState(0);
  const [moversPageLosers, setMoversPageLosers] = useState(0);
  const [headlines, setHeadlines] = useState<HeadlineArticle[]>([]);
  const [headlinesLoading, setHeadlinesLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paginationSection, setPaginationSection] = useState<'indices' | 'sectors' | 'regions' | null>(null);
  // Ticker list for headlines: set only on initial load so news does not refresh when navigating sections
  const [initialHeadlinesTickers, setInitialHeadlinesTickers] = useState<string[]>([]);

  const tickerChangeMap = useMemo(() => {
    const map: Record<string, number | null> = {};
    gainers.forEach((r) => {
      const s = r.symbol?.trim();
      if (s) map[s] = r.regularMarketChangePercent ?? null;
    });
    losers.forEach((r) => {
      const s = r.symbol?.trim();
      if (s) map[s] = r.regularMarketChangePercent ?? null;
    });
    if (overview) {
      overview.indices.forEach((i) => {
        if (i.ticker?.trim()) map[i.ticker.trim()] = i.changePercent ?? null;
      });
      overview.sectors.forEach((i) => {
        if (i.ticker?.trim()) map[i.ticker.trim()] = i.changePercent ?? null;
      });
      overview.international.forEach((i) => {
        if (i.ticker?.trim()) map[i.ticker.trim()] = i.changePercent ?? null;
      });
    }
    return map;
  }, [gainers, losers, overview]);

  const fetchHeadlines = useCallback(async () => {
    if (initialHeadlinesTickers.length === 0) return;
    setHeadlinesLoading(true);
    try {
      const results = await Promise.allSettled(
        initialHeadlinesTickers.map((t) => tickerApi.getNews(t))
      );
      const merged: HeadlineArticle[] = [];
      results.forEach((result, i) => {
        if (result.status === 'fulfilled' && result.value?.articles?.length) {
          const ticker = initialHeadlinesTickers[i];
          result.value.articles.forEach((a) => {
            merged.push({ ...a, ticker });
          });
        }
      });
      merged.sort((a, b) => (b.published_timestamp ?? 0) - (a.published_timestamp ?? 0));
      setHeadlines(merged);
    } finally {
      setHeadlinesLoading(false);
    }
  }, [initialHeadlinesTickers]);

  useEffect(() => {
    fetchHeadlines();
  }, [fetchHeadlines]);

  useEffect(() => {
    if (initialHeadlinesTickers.length === 0) return;
    const id = setInterval(fetchHeadlines, HEADLINES_REFRESH_MS);
    return () => clearInterval(id);
  }, [fetchHeadlines, initialHeadlinesTickers.length]);

  const fetchOverview = useCallback(
    async (
      pageIndices: number,
      pageSectors: number,
      pageRegions: number,
      updateOnlySection?: 'indices' | 'sectors' | 'regions'
    ) => {
      const data = await tickerApi.getMarketOverview({
        limit_indices: TILES_PER_PAGE,
        offset_indices: pageIndices * TILES_PER_PAGE,
        limit_sectors: TILES_PER_PAGE,
        offset_sectors: pageSectors * TILES_PER_PAGE,
        limit_regions: TILES_PER_PAGE,
        offset_regions: pageRegions * TILES_PER_PAGE,
      });
      if (updateOnlySection) {
        setOverview((prev) => {
          if (!prev) return { indices: data.indices ?? [], sectors: data.sectors ?? [], international: data.international ?? [] };
          return {
            indices: updateOnlySection === 'indices' ? (data.indices ?? []) : prev.indices,
            sectors: updateOnlySection === 'sectors' ? (data.sectors ?? []) : prev.sectors,
            international: updateOnlySection === 'regions' ? (data.international ?? []) : prev.international,
          };
        });
        setTotals((prev) => ({
          totalIndices: updateOnlySection === 'indices' ? (data.totalIndices ?? 0) : prev.totalIndices,
          totalSectors: updateOnlySection === 'sectors' ? (data.totalSectors ?? 0) : prev.totalSectors,
          totalRegions: updateOnlySection === 'regions' ? (data.totalRegions ?? 0) : prev.totalRegions,
        }));
      } else {
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
      }
      setPages({ indices: pageIndices, sectors: pageSectors, regions: pageRegions });
      return data;
    },
    []
  );

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
        tickerApi.getMarketMovers(MOVERS_LOAD_COUNT),
      ]);
      const gainersList = moversData.gainers ?? [];
      const losersList = moversData.losers ?? [];
      const indices = overviewData.indices ?? [];
      const sectors = overviewData.sectors ?? [];
      const international = overviewData.international ?? [];
      const raw: string[] = [];
      gainersList.forEach((r) => {
        const s = r.symbol?.trim();
        if (s) raw.push(s);
      });
      losersList.forEach((r) => {
        const s = r.symbol?.trim();
        if (s) raw.push(s);
      });
      [...indices, ...sectors, ...international].forEach((i) => {
        if (i.ticker?.trim()) raw.push(i.ticker.trim());
      });
      setInitialHeadlinesTickers([...new Set(raw)].slice(0, 50));
      setOverview({
        indices,
        sectors,
        international,
      });
      setTotals({
        totalIndices: overviewData.totalIndices ?? 0,
        totalSectors: overviewData.totalSectors ?? 0,
        totalRegions: overviewData.totalRegions ?? 0,
      });
      setPages({ indices: 0, sectors: 0, regions: 0 });
      setGainers(gainersList);
      setLosers(losersList);
      setMoversPageGainers(0);
      setMoversPageLosers(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
      setOverview(null);
      setGainers([]);
      setLosers([]);
      setInitialHeadlinesTickers([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const totalPagesIndices = Math.max(1, Math.ceil(totals.totalIndices / TILES_PER_PAGE));
  const totalPagesSectors = Math.max(1, Math.ceil(totals.totalSectors / TILES_PER_PAGE));
  const totalPagesRegions = Math.max(1, Math.ceil(totals.totalRegions / TILES_PER_PAGE));

  const handlePrevIndices = useCallback(async () => {
    if (paginationSection || pages.indices <= 0) return;
    const nextPage = pages.indices - 1;
    setPaginationSection('indices');
    try {
      await fetchOverview(nextPage, pages.sectors, pages.regions, 'indices');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextIndices = useCallback(async () => {
    if (paginationSection || pages.indices >= totalPagesIndices - 1) return;
    const nextPage = pages.indices + 1;
    setPaginationSection('indices');
    try {
      await fetchOverview(nextPage, pages.sectors, pages.regions, 'indices');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesIndices, fetchOverview]);

  const handlePrevSectors = useCallback(async () => {
    if (paginationSection || pages.sectors <= 0) return;
    const nextPage = pages.sectors - 1;
    setPaginationSection('sectors');
    try {
      await fetchOverview(pages.indices, nextPage, pages.regions, 'sectors');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextSectors = useCallback(async () => {
    if (paginationSection || pages.sectors >= totalPagesSectors - 1) return;
    const nextPage = pages.sectors + 1;
    setPaginationSection('sectors');
    try {
      await fetchOverview(pages.indices, nextPage, pages.regions, 'sectors');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesSectors, fetchOverview]);

  const handlePrevRegions = useCallback(async () => {
    if (paginationSection || pages.regions <= 0) return;
    const nextPage = pages.regions - 1;
    setPaginationSection('regions');
    try {
      await fetchOverview(pages.indices, pages.sectors, nextPage, 'regions');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextRegions = useCallback(async () => {
    if (paginationSection || pages.regions >= totalPagesRegions - 1) return;
    const nextPage = pages.regions + 1;
    setPaginationSection('regions');
    try {
      await fetchOverview(pages.indices, pages.sectors, nextPage, 'regions');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesRegions, fetchOverview]);

  const totalPagesGainers = Math.max(1, Math.ceil(gainers.length / MOVERS_PAGE_SIZE));
  const totalPagesLosers = Math.max(1, Math.ceil(losers.length / MOVERS_PAGE_SIZE));
  const handlePrevGainers = useCallback(() => {
    setMoversPageGainers((p) => Math.max(0, p - 1));
  }, []);
  const handleNextGainers = useCallback(() => {
    setMoversPageGainers((p) => Math.min(totalPagesGainers - 1, p + 1));
  }, [totalPagesGainers]);
  const handlePrevLosers = useCallback(() => {
    setMoversPageLosers((p) => Math.max(0, p - 1));
  }, []);
  const handleNextLosers = useCallback(() => {
    setMoversPageLosers((p) => Math.min(totalPagesLosers - 1, p + 1));
  }, [totalPagesLosers]);

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
      {/* Running headlines */}
      <RunningHeadlinesStrip articles={headlines} isLoading={headlinesLoading} tickerChangeMap={tickerChangeMap} />

      <section className="space-y-6">
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

      <section className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MoversTable
            rows={gainers}
            title="Top gainers"
            isGainers={true}
            onSelectTicker={onSelectTicker}
            currentPage={moversPageGainers}
            totalPages={totalPagesGainers}
            onPrev={handlePrevGainers}
            onNext={handleNextGainers}
            pageSize={MOVERS_PAGE_SIZE}
          />
          <MoversTable
            rows={losers}
            title="Top losers"
            isGainers={false}
            onSelectTicker={onSelectTicker}
            currentPage={moversPageLosers}
            totalPages={totalPagesLosers}
            onPrev={handlePrevLosers}
            onNext={handleNextLosers}
            pageSize={MOVERS_PAGE_SIZE}
          />
        </div>
      </section>
    </div>
  );
}
