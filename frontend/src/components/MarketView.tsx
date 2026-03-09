import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { tickerApi } from '../services/api';
import TickerSearch from './TickerSearch';

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function ChevronUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 15l-6-6-6 6" />
    </svg>
  );
}

export type HeadlineArticle = {
  uuid: string;
  title: string;
  summary?: string | null;
  publisher?: string;
  link: string;
  published_time: string | null;
  published_timestamp: number;
  type?: string;
  thumbnail?: string | null;
  /** Related tickers (deduplicated; multiple when same story appears for several tickers) */
  tickers: string[];
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
      className={`min-h-[3.5rem] min-w-0 rounded border border-gray-600 bg-gray-800 px-2.5 py-2 flex flex-col justify-center overflow-hidden transition-colors ${
        clickable ? 'cursor-pointer hover:border-gray-500 hover:bg-gray-700/80' : ''
      }`}
    >
      <div className="flex items-baseline justify-between gap-1 min-w-0">
        <span className="text-gray-300 text-xs font-medium truncate min-w-0" title={item.name}>
          {item.name}
        </span>
        {item.ticker && (
          <span className="text-gray-500 text-xs shrink-0 tabular-nums">{item.ticker}</span>
        )}
      </div>
      <div className="mt-0.5 flex items-baseline justify-between gap-1 min-w-0">
        <span className="text-white text-xs font-semibold tabular-nums min-w-0 truncate" title={formatPrice(item.price)}>
          {formatPrice(item.price)}
        </span>
        <span className={`text-xs font-medium tabular-nums shrink-0 ${changeClass}`}>
          {formatPct(item.changePercent)}
        </span>
      </div>
    </div>
  );
}

const TILES_PER_PAGE = 6;
const MOVERS_PAGE_SIZE = 8;
const MOVERS_LOAD_COUNT = 24;

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
    <div className="rounded-lg border border-gray-700 bg-gray-800/60 overflow-hidden">
      <div className="px-2.5 py-1.5 border-b border-gray-700 bg-gray-800/80 flex items-center justify-between gap-1">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{title}</h3>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={onPrev}
            disabled={!canPrev || paginationLoading}
            className="p-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:bg-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent disabled:hover:border-gray-600 transition-colors"
            aria-label="Previous page"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-xs text-gray-500 tabular-nums min-w-[3rem] text-center">
            {totalPages > 0 ? `${currentPage + 1}/${totalPages}` : '—'}
          </span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNext || paginationLoading}
            className="p-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:bg-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent disabled:hover:border-gray-600 transition-colors"
            aria-label="Next page"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
      <div className="p-2">
        <div className="grid grid-cols-2 gap-1.5">
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
  changeColor,
  onSelectTicker,
  currentPage = 0,
  totalPages = 1,
  onPrev,
  onNext,
  pageSize = MOVERS_PAGE_SIZE,
}: {
  rows: MarketMoverRow[];
  title: string;
  changeColor: 'gainers' | 'losers' | 'neutral';
  onSelectTicker?: (ticker: string) => void;
  currentPage?: number;
  totalPages?: number;
  onPrev?: () => void;
  onNext?: () => void;
  pageSize?: number;
}) {
  const changeClass =
    changeColor === 'gainers' ? 'text-green-400' : changeColor === 'losers' ? 'text-red-400' : 'text-gray-300';
  const canPrev = totalPages > 1 && currentPage > 0;
  const canNext = totalPages > 1 && currentPage < totalPages - 1;
  const pageRows = totalPages > 1
    ? rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
    : rows;
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden flex flex-col min-h-0">
      <div className="px-2.5 py-1.5 border-b border-gray-700 bg-gray-800/80 flex items-center justify-between gap-1 shrink-0">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{title}</h3>
        {totalPages > 1 && onPrev != null && onNext != null && (
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={onPrev}
              disabled={!canPrev}
              className="p-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:bg-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent disabled:hover:border-gray-600 transition-colors"
              aria-label="Previous page"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <span className="text-xs text-gray-500 tabular-nums min-w-[3rem] text-center">
              {currentPage + 1} / {totalPages}
            </span>
            <button
              type="button"
              onClick={onNext}
              disabled={!canNext}
              className="p-1 rounded border border-gray-600 text-gray-400 hover:text-white hover:bg-gray-700 hover:border-gray-500 disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent disabled:hover:border-gray-600 transition-colors"
              aria-label="Next page"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto flex-1 min-h-0">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              <th className="py-1.5 px-3 font-medium text-xs">Symbol</th>
              <th className="py-1.5 px-3 font-medium text-xs min-w-0 truncate max-w-[140px]">Name</th>
              <th className="py-1.5 px-3 font-medium text-xs text-right">Price</th>
              <th className="py-1.5 px-3 font-medium text-xs text-right">Change</th>
              <th className="py-1.5 px-3 font-medium text-xs text-right">Volume</th>
              <th className="py-1.5 px-3 font-medium text-xs w-0 max-w-[90px]">Sector</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => {
              const sym = row.symbol ?? '';
              const clickable = onSelectTicker && sym;
              const pct = row.regularMarketChangePercent ?? null;
              const rowChangeClass =
                changeColor === 'neutral'
                  ? pct != null && pct > 0
                    ? 'text-green-400'
                    : pct != null && pct < 0
                      ? 'text-red-400'
                      : 'text-gray-400'
                  : changeClass;
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
                  <td className="py-2 px-3 text-right text-gray-200 tabular-nums">{formatPrice(row.regularMarketPrice)}</td>
                  <td className={`py-2 px-3 text-right font-medium tabular-nums ${rowChangeClass}`}>
                    {formatPct(row.regularMarketChangePercent)}
                  </td>
                  <td className="py-2 px-3 text-right text-gray-400 tabular-nums">{formatVolume(row.regularMarketVolume)}</td>
                  <td className="py-2 px-3 text-gray-400 truncate max-w-[90px]" title={row.industry ?? undefined}>
                    {row.sector || '—'}
                  </td>
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
const HEADLINES_REFRESH_MS = 300000; // 5 minutes (was 2 min)

function RunningHeadlinesStrip({
  articles,
  isLoading,
  tickerChangeMap = {},
}: {
  articles: HeadlineArticle[];
  isLoading: boolean;
  tickerChangeMap?: Record<string, number | null>;
}) {
  // Track which specific widget instance is expanded (same article appears twice in the strip for scroll)
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const expandedWidgetRef = useRef<HTMLDivElement | null>(null);
  const [overlayState, setOverlayState] = useState<{
    top: number;
    left: number;
    width: number;
    title: string;
    summary: string;
  } | null>(null);

  // Position overlay in a portal when a tile is expanded (so it's not clipped by strip overflow)
  useEffect(() => {
    if (!expandedKey) {
      setOverlayState(null);
      return;
    }
    const id = requestAnimationFrame(() => {
      const el = expandedWidgetRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const uuid = expandedKey.replace(/-\d+$/, '');
      const article = articles.find((a) => a.uuid === uuid);
      if (!article || !(article.summary ?? '').trim()) return;
      setOverlayState({
        top: rect.bottom + 4,
        left: rect.left,
        width: Math.min(Math.max(rect.width, 280), 360),
        title: article.title,
        summary: (article.summary ?? '').trim(),
      });
    });
    return () => cancelAnimationFrame(id);
  }, [expandedKey, articles]);

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

  const renderTile = (a: HeadlineArticle, copyIndex: number) => {
    const widgetKey = `${a.uuid}-${copyIndex}`;
    const firstTicker = a.tickers?.[0];
    const changePercent = firstTicker != null ? tickerChangeMap[firstTicker] ?? tickerChangeMap[firstTicker.toUpperCase()] : null;
    const tickerColorClass =
      changePercent != null && changePercent > 0
        ? 'text-green-400'
        : changePercent != null && changePercent < 0
          ? 'text-red-400'
          : 'text-gray-500';
    const isExpanded = expandedKey === widgetKey;
    const hasSummary = a.summary != null && a.summary.trim() !== '';
    const tickersLabel = a.tickers?.length ? ` [${a.tickers.join(', ')}]` : '';
    return (
      <div
        key={widgetKey}
        ref={isExpanded ? (el) => { expandedWidgetRef.current = el; } : undefined}
        className="shrink-0 relative rounded-lg border border-gray-600 bg-gray-800/90 px-3 py-2 min-w-[260px] max-w-[320px] sm:max-w-[380px] h-[48px] flex items-center gap-2"
      >
        <div className="flex-1 min-w-0">
          {a.link ? (
            <a
              href={a.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-200 hover:text-white hover:underline text-xs leading-tight line-clamp-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 rounded"
            >
              {a.title}
              {tickersLabel && <span className={`font-medium tabular-nums ${tickerColorClass}`}>{tickersLabel}</span>}
            </a>
          ) : (
            <span className="text-gray-200 text-xs leading-tight line-clamp-2">
              {a.title}
              {tickersLabel && <span className={`font-medium tabular-nums ${tickerColorClass}`}>{tickersLabel}</span>}
            </span>
          )}
        </div>
        {hasSummary && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              setExpandedKey((prev) => (prev === widgetKey ? null : widgetKey));
            }}
            className="shrink-0 p-1 rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-800"
            aria-expanded={isExpanded}
            aria-label={isExpanded ? 'Hide summary' : 'Show summary'}
          >
            {isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
          </button>
        )}
      </div>
    );
  };

  const itemNodes = (
    <>
      {articles.map((a) => renderTile(a, 0))}
      {articles.map((a) => renderTile(a, 1))}
    </>
  );

  const overlayPortal =
    overlayState &&
    createPortal(
      <div
        className="fixed z-[200] rounded-lg border border-gray-600 bg-gray-800 shadow-xl py-3 px-3"
        role="dialog"
        aria-label="Summary"
        style={{
          top: overlayState.top,
          left: overlayState.left,
          width: overlayState.width,
        }}
      >
        <p className="text-gray-300 text-xs leading-relaxed whitespace-pre-wrap">{overlayState.summary}</p>
      </div>,
      document.body
    );

  return (
    <>
      <div className="rounded-lg border border-gray-700 bg-gray-800/80 overflow-hidden group/headlines" aria-live="polite">
        <div
          className="flex items-center overflow-hidden min-h-[56px]"
          style={{ minHeight: HEADLINES_STRIP_HEIGHT }}
        >
          <div
            className="flex items-center gap-3 py-2 pl-2 pr-4 animate-tiles-scroll group-hover/headlines:[animation-play-state:paused]"
            style={{
              animationDuration: `${Math.max(30, articles.length * 4)}s`,
              animationPlayState: overlayState ? 'paused' : undefined,
            }}
          >
            {itemNodes}
          </div>
        </div>
      </div>
      {overlayPortal}
    </>
  );
}

export default function MarketView({ onSelectTicker }: MarketViewProps) {
  const [overview, setOverview] = useState<{
    indices: OverviewItem[];
    sectors: OverviewItem[];
    international: OverviewItem[];
    commodities: OverviewItem[];
  } | null>(null);
  const [totals, setTotals] = useState({ totalIndices: 0, totalSectors: 0, totalRegions: 0, totalCommodities: 0 });
  const [pages, setPages] = useState({ indices: 0, sectors: 0, regions: 0, commodities: 0 });
  const [gainers, setGainers] = useState<MarketMoverRow[]>([]);
  const [losers, setLosers] = useState<MarketMoverRow[]>([]);
  const [mostActive, setMostActive] = useState<MarketMoverRow[]>([]);
  const [moversPageGainers, setMoversPageGainers] = useState(0);
  const [moversPageLosers, setMoversPageLosers] = useState(0);
  const [moversPageMostActive, setMoversPageMostActive] = useState(0);
  const [headlines, setHeadlines] = useState<HeadlineArticle[]>([]);
  const [headlinesLoading, setHeadlinesLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paginationSection, setPaginationSection] = useState<'indices' | 'sectors' | 'regions' | 'commodities' | null>(null);
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
      overview.commodities.forEach((i) => {
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
      const byKey = new Map<string, HeadlineArticle>();
      results.forEach((result, i) => {
        if (result.status === 'fulfilled' && result.value?.articles?.length) {
          const ticker = initialHeadlinesTickers[i];
          result.value.articles.forEach((a) => {
            const key = a.uuid || a.link;
            const existing = byKey.get(key);
            if (existing) {
              if (!existing.tickers.includes(ticker)) {
                existing.tickers.push(ticker);
              }
            } else {
              byKey.set(key, { ...a, tickers: [ticker] });
            }
          });
        }
      });
      const merged = Array.from(byKey.values());
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
      pageCommodities: number,
      updateOnlySection?: 'indices' | 'sectors' | 'regions' | 'commodities'
    ) => {
      const data = await tickerApi.getMarketOverview({
        limit_indices: TILES_PER_PAGE,
        offset_indices: pageIndices * TILES_PER_PAGE,
        limit_sectors: TILES_PER_PAGE,
        offset_sectors: pageSectors * TILES_PER_PAGE,
        limit_regions: TILES_PER_PAGE,
        offset_regions: pageRegions * TILES_PER_PAGE,
        limit_commodities: TILES_PER_PAGE,
        offset_commodities: pageCommodities * TILES_PER_PAGE,
      });
      if (updateOnlySection) {
        setOverview((prev) => {
          if (!prev) {
            return {
              indices: data.indices ?? [],
              sectors: data.sectors ?? [],
              international: data.international ?? [],
              commodities: data.commodities ?? [],
            };
          }
          return {
            indices: updateOnlySection === 'indices' ? (data.indices ?? []) : prev.indices,
            sectors: updateOnlySection === 'sectors' ? (data.sectors ?? []) : prev.sectors,
            international: updateOnlySection === 'regions' ? (data.international ?? []) : prev.international,
            commodities: updateOnlySection === 'commodities' ? (data.commodities ?? []) : prev.commodities,
          };
        });
        setTotals((prev) => ({
          totalIndices: updateOnlySection === 'indices' ? (data.totalIndices ?? 0) : prev.totalIndices,
          totalSectors: updateOnlySection === 'sectors' ? (data.totalSectors ?? 0) : prev.totalSectors,
          totalRegions: updateOnlySection === 'regions' ? (data.totalRegions ?? 0) : prev.totalRegions,
          totalCommodities: updateOnlySection === 'commodities' ? (data.totalCommodities ?? 0) : prev.totalCommodities,
        }));
      } else {
        setOverview({
          indices: data.indices ?? [],
          sectors: data.sectors ?? [],
          international: data.international ?? [],
          commodities: data.commodities ?? [],
        });
        setTotals({
          totalIndices: data.totalIndices ?? 0,
          totalSectors: data.totalSectors ?? 0,
          totalRegions: data.totalRegions ?? 0,
          totalCommodities: data.totalCommodities ?? 0,
        });
      }
      setPages({ indices: pageIndices, sectors: pageSectors, regions: pageRegions, commodities: pageCommodities });
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
          limit_commodities: TILES_PER_PAGE,
          offset_commodities: 0,
        }),
        tickerApi.getMarketMovers(MOVERS_LOAD_COUNT),
      ]);
      const gainersList = moversData.gainers ?? [];
      const losersList = moversData.losers ?? [];
      const mostActiveList = moversData.most_active ?? [];
      const indices = overviewData.indices ?? [];
      const sectors = overviewData.sectors ?? [];
      const international = overviewData.international ?? [];
      const commodities = overviewData.commodities ?? [];
      const raw: string[] = [];
      gainersList.forEach((r) => {
        const s = r.symbol?.trim();
        if (s) raw.push(s);
      });
      losersList.forEach((r) => {
        const s = r.symbol?.trim();
        if (s) raw.push(s);
      });
      mostActiveList.forEach((r) => {
        const s = r.symbol?.trim();
        if (s) raw.push(s);
      });
      [...indices, ...sectors, ...international, ...commodities].forEach((i) => {
        if (i.ticker?.trim()) raw.push(i.ticker.trim());
      });
      setInitialHeadlinesTickers([...new Set(raw)].slice(0, 50));
      setOverview({
        indices,
        sectors,
        international,
        commodities,
      });
      setTotals({
        totalIndices: overviewData.totalIndices ?? 0,
        totalSectors: overviewData.totalSectors ?? 0,
        totalRegions: overviewData.totalRegions ?? 0,
        totalCommodities: overviewData.totalCommodities ?? 0,
      });
      setPages({ indices: 0, sectors: 0, regions: 0, commodities: 0 });
      setGainers(gainersList);
      setLosers(losersList);
      setMostActive(mostActiveList);
      setMoversPageGainers(0);
      setMoversPageLosers(0);
      setMoversPageMostActive(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
      setOverview(null);
      setGainers([]);
      setLosers([]);
      setMostActive([]);
      setInitialHeadlinesTickers([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const totalPagesIndices = Math.max(1, Math.ceil(totals.totalIndices / TILES_PER_PAGE));
  const totalPagesSectors = Math.max(1, Math.ceil(totals.totalSectors / TILES_PER_PAGE));
  const totalPagesRegions = Math.max(1, Math.ceil(totals.totalRegions / TILES_PER_PAGE));
  const totalPagesCommodities = Math.max(1, Math.ceil(totals.totalCommodities / TILES_PER_PAGE));

  const handlePrevIndices = useCallback(async () => {
    if (paginationSection || pages.indices <= 0) return;
    const nextPage = pages.indices - 1;
    setPaginationSection('indices');
    try {
      await fetchOverview(nextPage, pages.sectors, pages.regions, pages.commodities, 'indices');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextIndices = useCallback(async () => {
    if (paginationSection || pages.indices >= totalPagesIndices - 1) return;
    const nextPage = pages.indices + 1;
    setPaginationSection('indices');
    try {
      await fetchOverview(nextPage, pages.sectors, pages.regions, pages.commodities, 'indices');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesIndices, fetchOverview]);

  const handlePrevSectors = useCallback(async () => {
    if (paginationSection || pages.sectors <= 0) return;
    const nextPage = pages.sectors - 1;
    setPaginationSection('sectors');
    try {
      await fetchOverview(pages.indices, nextPage, pages.regions, pages.commodities, 'sectors');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextSectors = useCallback(async () => {
    if (paginationSection || pages.sectors >= totalPagesSectors - 1) return;
    const nextPage = pages.sectors + 1;
    setPaginationSection('sectors');
    try {
      await fetchOverview(pages.indices, nextPage, pages.regions, pages.commodities, 'sectors');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesSectors, fetchOverview]);

  const handlePrevRegions = useCallback(async () => {
    if (paginationSection || pages.regions <= 0) return;
    const nextPage = pages.regions - 1;
    setPaginationSection('regions');
    try {
      await fetchOverview(pages.indices, pages.sectors, nextPage, pages.commodities, 'regions');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextRegions = useCallback(async () => {
    if (paginationSection || pages.regions >= totalPagesRegions - 1) return;
    const nextPage = pages.regions + 1;
    setPaginationSection('regions');
    try {
      await fetchOverview(pages.indices, pages.sectors, nextPage, pages.commodities, 'regions');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesRegions, fetchOverview]);

  const handlePrevCommodities = useCallback(async () => {
    if (paginationSection || pages.commodities <= 0) return;
    const nextPage = pages.commodities - 1;
    setPaginationSection('commodities');
    try {
      await fetchOverview(pages.indices, pages.sectors, pages.regions, nextPage, 'commodities');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, fetchOverview]);

  const handleNextCommodities = useCallback(async () => {
    if (paginationSection || pages.commodities >= totalPagesCommodities - 1) return;
    const nextPage = pages.commodities + 1;
    setPaginationSection('commodities');
    try {
      await fetchOverview(pages.indices, pages.sectors, pages.regions, nextPage, 'commodities');
    } finally {
      setPaginationSection(null);
    }
  }, [paginationSection, pages, totalPagesCommodities, fetchOverview]);

  const totalPagesGainers = Math.max(1, Math.ceil(gainers.length / MOVERS_PAGE_SIZE));
  const totalPagesLosers = Math.max(1, Math.ceil(losers.length / MOVERS_PAGE_SIZE));
  const totalPagesMostActive = Math.max(1, Math.ceil(mostActive.length / MOVERS_PAGE_SIZE));
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
  const handlePrevMostActive = useCallback(() => {
    setMoversPageMostActive((p) => Math.max(0, p - 1));
  }, []);
  const handleNextMostActive = useCallback(() => {
    setMoversPageMostActive((p) => Math.min(totalPagesMostActive - 1, p + 1));
  }, [totalPagesMostActive]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex items-center gap-2 text-gray-400 text-xs">
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
        <p className="text-red-400 text-xs mb-2">{error}</p>
        <button
          type="button"
          onClick={fetchAll}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded-lg transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <TickerSearch compact />
        </div>
        <div className="border-b border-gray-700" />
        <div>
          <RunningHeadlinesStrip articles={headlines} isLoading={headlinesLoading} tickerChangeMap={tickerChangeMap} />
        </div>
      </div>

      <section className="space-y-4">
        {overview && (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
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
            <OverviewSection
              title="Commodities"
              items={overview.commodities}
              currentPage={pages.commodities}
              totalPages={totalPagesCommodities}
              onPrev={handlePrevCommodities}
              onNext={handleNextCommodities}
              paginationLoading={paginationSection === 'commodities'}
              onSelectTicker={onSelectTicker}
            />
          </div>
        )}
      </section>

      <section className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          <MoversTable
            rows={gainers}
            title="Top gainers"
            changeColor="gainers"
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
            changeColor="losers"
            onSelectTicker={onSelectTicker}
            currentPage={moversPageLosers}
            totalPages={totalPagesLosers}
            onPrev={handlePrevLosers}
            onNext={handleNextLosers}
            pageSize={MOVERS_PAGE_SIZE}
          />
          <MoversTable
            rows={mostActive}
            title="Most active"
            changeColor="neutral"
            onSelectTicker={onSelectTicker}
            currentPage={moversPageMostActive}
            totalPages={totalPagesMostActive}
            onPrev={handlePrevMostActive}
            onNext={handleNextMostActive}
            pageSize={MOVERS_PAGE_SIZE}
          />
        </div>
      </section>
    </div>
  );
}
