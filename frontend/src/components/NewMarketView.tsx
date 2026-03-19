import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { tickerApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import TickerSearch from './TickerSearch';
import WorldMapRegionalStocks from './WorldMapRegionalStocks';

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

function getPublishedDate(article: HeadlineArticle): Date | null {
  const rawTimestamp = article.published_timestamp;
  const timestampMs = rawTimestamp > 1e12 ? rawTimestamp : rawTimestamp > 0 ? rawTimestamp * 1000 : NaN;
  const date = Number.isFinite(timestampMs) ? new Date(timestampMs) : article.published_time ? new Date(article.published_time) : null;
  return date && !Number.isNaN(date.getTime()) ? date : null;
}

function formatPublishedLabel(article: HeadlineArticle): string {
  const date = getPublishedDate(article);
  if (!date) return 'Latest';

  const diffMinutes = Math.round((date.getTime() - Date.now()) / 60000);
  const absoluteMinutes = Math.abs(diffMinutes);
  if (absoluteMinutes < 1) return 'Just now';
  if (absoluteMinutes < 60) return `${absoluteMinutes}m ago`;
  if (absoluteMinutes < 1440) return `${Math.round(absoluteMinutes / 60)}h ago`;
  if (absoluteMinutes < 10080) return `${Math.round(absoluteMinutes / 1440)}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatPublishedDateTime(article: HeadlineArticle): string {
  const date = getPublishedDate(article);
  if (!date) return 'Latest';
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function getRangeLabel(range: '1d' | '1w' | '1mo' | '6mo' | 'ytd'): string {
  switch (range) {
    case '1d':
      return 'Today';
    case '1w':
      return 'This week';
    case '1mo':
      return 'This month';
    case '6mo':
      return 'Last 6 months';
    case 'ytd':
      return 'Year to date';
    default:
      return 'Current range';
  }
}

function getChangeSurface(changePercent: number | null) {
  if (changePercent == null) {
    return {
      border: 'border-gray-700',
      glow: 'bg-gray-700/20',
      badge: 'border-gray-700 bg-gray-700/50 text-slate-300',
      text: 'text-slate-300',
    };
  }
  if (changePercent >= 0) {
    return {
      border: 'border-emerald-900/40',
      glow: 'bg-emerald-950/20',
      badge: 'border-emerald-900/40 bg-emerald-950/40 text-emerald-300',
      text: 'text-emerald-300',
    };
  }
  return {
    border: 'border-red-900/40',
    glow: 'bg-red-950/20',
    badge: 'border-red-900/40 bg-red-950/40 text-red-300',
    text: 'text-red-300',
  };
}

function getMoverTheme(changeColor: 'gainers' | 'losers' | 'neutral') {
  if (changeColor === 'gainers') {
    return {
      dot: 'bg-emerald-600',
      glow: 'bg-emerald-950/20',
      text: 'text-emerald-300',
    };
  }
  if (changeColor === 'losers') {
    return {
      dot: 'bg-red-700',
      glow: 'bg-red-950/20',
      text: 'text-red-300',
    };
  }
  return {
    dot: 'bg-sky-400',
    glow: 'bg-sky-400/[0.04]',
    text: 'text-sky-200',
  };
}

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="space-y-1.5">
      {eyebrow ? <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-gray-400">{eyebrow}</div> : null}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <h2 className="text-lg font-semibold text-white sm:text-xl">{title}</h2>
        {description ? <p className="max-w-2xl text-xs leading-relaxed text-gray-400 sm:text-sm">{description}</p> : null}
      </div>
    </div>
  );
}

function PulseCard({
  eyebrow,
  value,
  detail,
  tone = 'sky',
}: {
  eyebrow: string;
  value: string;
  detail: string;
  tone?: 'sky' | 'emerald' | 'rose';
}) {
  const toneClasses =
    tone === 'emerald'
      ? {
          dot: 'bg-emerald-600',
          value: 'text-emerald-300',
          eyebrow: 'text-emerald-300/80',
        }
      : tone === 'rose'
        ? {
            dot: 'bg-red-700',
            value: 'text-red-300',
            eyebrow: 'text-red-300/80',
          }
        : {
            dot: 'bg-sky-400',
            value: 'text-sky-200',
            eyebrow: 'text-sky-200/80',
          };

  return (
    <div className="flex min-w-0 items-center gap-2.5 rounded-lg border border-gray-700 bg-gray-800/80 px-3 py-2">
      <span className={`h-2 w-2 shrink-0 rounded-full ${toneClasses.dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-baseline justify-between gap-2">
          <div className={`truncate text-[11px] font-semibold uppercase tracking-[0.14em] ${toneClasses.eyebrow}`}>{eyebrow}</div>
          <div className={`shrink-0 text-sm font-semibold tracking-tight ${toneClasses.value}`}>{value}</div>
        </div>
        <div className="mt-0.5 truncate text-[11px] leading-snug text-gray-400">{detail}</div>
      </div>
    </div>
  );
}

function NewsBriefingPanel({
  articles,
  isLoading,
  tickerChangeMap,
  compact = false,
}: {
  articles: HeadlineArticle[];
  isLoading: boolean;
  tickerChangeMap: Record<string, number | null>;
  compact?: boolean;
}) {
  const initialVisibleCount = compact ? 12 : 20;
  const loadStep = compact ? 8 : 12;
  const [visibleCount, setVisibleCount] = useState(initialVisibleCount);

  useEffect(() => {
    setVisibleCount((current) => {
      if (articles.length === 0) return initialVisibleCount;
      if (current < initialVisibleCount) return Math.min(initialVisibleCount, articles.length);
      return Math.min(current, articles.length);
    });
  }, [articles.length, initialVisibleCount]);

  const handleLoadMore = useCallback(() => {
    setVisibleCount((current) => Math.min(current + loadStep, articles.length));
  }, [articles.length, loadStep]);

  return (
    <div className={`rounded-xl border border-gray-700 bg-gray-800/80 shadow-[0_14px_28px_-24px_rgba(15,23,42,0.85)] ${compact ? 'p-3' : 'p-3.5 xl:flex xl:h-[44rem] xl:min-h-0 xl:flex-col'}`}>
      <div className="mb-3 flex flex-col gap-1.5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-500">News briefing</div>
        </div>
        <div className="inline-flex w-fit rounded-full border border-gray-700 bg-gray-700/50 px-2.5 py-1 text-[11px] font-medium text-gray-300">
          {isLoading ? 'Refreshing headlines' : `${articles.length} headlines`}
        </div>
      </div>
      <RunningHeadlinesStrip
        articles={articles}
        isLoading={isLoading}
        compact={compact}
        tickerChangeMap={tickerChangeMap}
        visibleCount={visibleCount}
        hasMore={visibleCount < articles.length}
        onLoadMore={handleLoadMore}
      />
    </div>
  );
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
  const changeClass = !hasChange ? 'text-slate-500' : positive ? 'text-emerald-300' : 'text-red-300';
  const clickable = onSelectTicker && item.ticker && !item.ticker.startsWith('^');

  return (
    <div
      role={clickable ? 'button' : undefined}
      onClick={() => clickable && onSelectTicker(item.ticker)}
      className={`min-h-[4.1rem] min-w-0 rounded-lg border border-gray-700 bg-gray-800/70 px-2.5 py-2 flex flex-col justify-center overflow-hidden transition-colors ${
        clickable ? 'cursor-pointer hover:border-gray-600 hover:bg-gray-700/70' : ''
      }`}
    >
      <div className="flex min-w-0 items-baseline justify-between gap-1.5">
        <span className="min-w-0 truncate text-[12px] font-medium text-slate-300" title={item.name}>
          {item.name}
        </span>
        {item.ticker && (
          <span className="shrink-0 text-[11px] tabular-nums text-slate-500">{item.ticker}</span>
        )}
      </div>
      <div className="mt-1 flex min-w-0 items-baseline justify-between gap-1.5">
        <span className="min-w-0 truncate text-[13px] font-semibold tabular-nums text-white" title={formatPrice(item.price)}>
          {formatPrice(item.price)}
        </span>
        <span className={`shrink-0 text-[12px] font-medium tabular-nums ${changeClass}`}>
          {formatPct(item.changePercent)}
        </span>
      </div>
    </div>
  );
}

const TILES_PER_PAGE = 6;
const MOVERS_PAGE_SIZE = 8;
const MOVERS_TOTAL_PAGES = 3;

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
    <div className="relative overflow-hidden rounded-xl border border-gray-700 bg-gray-800/80 shadow-[0_12px_28px_-24px_rgba(15,23,42,0.85)]">
      <div className="relative flex items-center justify-between gap-2 border-b border-gray-700 bg-gray-800 px-3 py-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">{title}</h3>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onPrev}
            disabled={!canPrev || paginationLoading}
            className="rounded-md border border-gray-700 bg-gray-700/60 p-1.5 text-slate-300 transition hover:border-gray-600 hover:bg-gray-700 hover:text-white disabled:cursor-default disabled:opacity-40 disabled:hover:border-gray-700 disabled:hover:bg-gray-700/60"
            aria-label="Previous page"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="min-w-[3rem] text-center text-[11px] tabular-nums text-slate-500">
            {totalPages > 0 ? `${currentPage + 1}/${totalPages}` : '—'}
          </span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNext || paginationLoading}
            className="rounded-md border border-gray-700 bg-gray-700/60 p-1.5 text-slate-300 transition hover:border-gray-600 hover:bg-gray-700 hover:text-white disabled:cursor-default disabled:opacity-40 disabled:hover:border-gray-700 disabled:hover:bg-gray-700/60"
            aria-label="Next page"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
      <div className="relative min-h-[8.5rem] p-2.5">
        {paginationLoading && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-gray-900/70"
            aria-live="polite"
            aria-busy="true"
          >
            <svg className="h-6 w-6 animate-spin shrink-0 text-sky-400" fill="none" viewBox="0 0 24 24" aria-hidden>
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          </div>
        )}
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
  paginationLoading,
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
  paginationLoading?: boolean;
}) {
  const theme = getMoverTheme(changeColor);
  const canPrev = totalPages > 1 && currentPage > 0 && !paginationLoading;
  const canNext = !paginationLoading && currentPage < totalPages - 1;
  const pageRows = totalPages > 1
    ? rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
    : rows;
  return (
    <div className="relative flex min-h-0 flex-col overflow-hidden rounded-xl border border-gray-700 bg-gray-800/80 shadow-[0_12px_28px_-24px_rgba(15,23,42,0.85)]">
      <div className={`absolute inset-0 ${theme.glow}`} />
      <div className="relative flex items-center justify-between gap-2 border-b border-gray-700 bg-gray-800 px-3 py-2 shrink-0">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
            <span className={`h-2 w-2 rounded-full ${theme.dot}`} />
            {title}
          </h3>
        </div>
        {totalPages > 1 && onPrev != null && onNext != null && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onPrev}
              disabled={!canPrev}
              className="rounded-md border border-gray-700 bg-gray-700/60 p-1.5 text-slate-300 transition hover:border-gray-600 hover:bg-gray-700 hover:text-white disabled:cursor-default disabled:opacity-40 disabled:hover:border-gray-700 disabled:hover:bg-gray-700/60"
              aria-label="Previous page"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <span className="min-w-[3rem] text-center text-[11px] tabular-nums text-slate-500">
              {currentPage + 1}/{totalPages}
            </span>
            <button
              type="button"
              onClick={onNext}
              disabled={!canNext}
              className="rounded-md border border-gray-700 bg-gray-700/60 p-1.5 text-slate-300 transition hover:border-gray-600 hover:bg-gray-700 hover:text-white disabled:cursor-default disabled:opacity-40 disabled:hover:border-gray-700 disabled:hover:bg-gray-700/60"
              aria-label="Next page"
              aria-busy={paginationLoading}
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="relative min-h-0 flex-1 overflow-x-auto">
        {paginationLoading && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center rounded-b-xl bg-gray-900/80"
            aria-live="polite"
            aria-busy="true"
          >
            <span className="flex items-center gap-1.5 text-xs text-slate-300">
              <svg className="h-4 w-4 animate-spin shrink-0 text-sky-400" fill="none" viewBox="0 0 24 24" aria-hidden>
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Updating…
            </span>
          </div>
        )}
        <table className="w-full bg-gray-800 text-left text-xs">
          <thead className="sticky top-0 z-[1] bg-gray-800">
            <tr className="border-b border-gray-700 text-slate-400">
              <th className="px-3 py-2 font-medium text-[10px] uppercase tracking-[0.14em]">Ticker</th>
              <th className="px-3 py-2 font-medium text-[10px] uppercase tracking-[0.14em] text-right">Change</th>
              <th className="px-3 py-2 font-medium text-[10px] uppercase tracking-[0.14em]">Company</th>
              <th className="px-3 py-2 font-medium text-[10px] uppercase tracking-[0.14em] text-right">Price</th>
              <th className="px-3 py-2 font-medium text-[10px] uppercase tracking-[0.14em] text-right">Volume</th>
              <th className="px-3 py-2 font-medium text-[10px] uppercase tracking-[0.14em]">Sector</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => {
              const sym = row.symbol ?? '';
              const clickable = onSelectTicker && sym;
              const pct = row.regularMarketChangePercent ?? null;
              const rowTone = changeColor === 'neutral' ? getChangeSurface(pct) : null;
              const changeTextClass = rowTone ? rowTone.text : theme.text;
              return (
                <tr
                  key={sym || i}
                  onClick={() => clickable && onSelectTicker(sym)}
                  className={`border-b border-gray-700/70 bg-gray-800 last:border-b-0 ${clickable ? 'cursor-pointer transition-colors hover:bg-gray-700/40' : ''}`}
                >
                  <td className="px-3 py-2.5 font-medium text-white tabular-nums">
                    {sym || '—'}
                  </td>
                  <td className={`px-3 py-2.5 text-right text-[12px] font-medium tabular-nums ${changeTextClass}`}>
                    <span>
                      {formatPct(row.regularMarketChangePercent)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="truncate text-[12px] text-slate-300" title={row.shortName ?? undefined}>
                      {row.shortName || '—'}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right text-[12px] tabular-nums text-slate-200">
                    {formatPrice(row.regularMarketPrice)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-[12px] tabular-nums text-slate-400">
                    {formatVolume(row.regularMarketVolume)}
                  </td>
                  <td className="px-3 py-2.5 text-[12px] text-slate-400">
                    <div className="truncate" title={row.sector ?? undefined}>
                      {row.sector || '—'}
                    </div>
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

const HEADLINES_REFRESH_MS = 300000; // 5 minutes (was 2 min)

type HeadlineTone = {
  line: string;
  dot: string;
  dotCore: string;
  ticker: string;
};

function getHeadlineTone(article: HeadlineArticle, tickerChangeMap: Record<string, number | null>): HeadlineTone {
  const linkedChange = article.tickers.reduce<number | null>((found, ticker) => {
    if (found != null) return found;
    return tickerChangeMap[ticker] ?? tickerChangeMap[ticker.toUpperCase()] ?? null;
  }, null);

  if (linkedChange != null && linkedChange > 0) {
    return {
      line: 'bg-emerald-400/55',
      dot: 'border-emerald-400/70 bg-emerald-400/10',
      dotCore: 'bg-emerald-300',
      ticker: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-200',
    };
  }

  if (linkedChange != null && linkedChange < 0) {
    return {
      line: 'bg-rose-400/55',
      dot: 'border-rose-400/70 bg-rose-400/10',
      dotCore: 'bg-rose-300',
      ticker: 'border-rose-500/25 bg-rose-500/10 text-rose-200',
    };
  }

  return {
    line: 'bg-sky-400/55',
    dot: 'border-sky-400/70 bg-sky-400/10',
    dotCore: 'bg-sky-300',
    ticker: 'border-sky-500/25 bg-sky-500/10 text-sky-200',
  };
}

function RunningHeadlinesStrip({
  articles,
  isLoading,
  compact = false,
  tickerChangeMap = {},
  visibleCount,
  hasMore = false,
  onLoadMore,
}: {
  articles: HeadlineArticle[];
  isLoading: boolean;
  compact?: boolean;
  tickerChangeMap?: Record<string, number | null>;
  visibleCount: number;
  hasMore?: boolean;
  onLoadMore?: () => void;
}) {
  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    if (!hasMore || !onLoadMore) return;
    const target = event.currentTarget;
    if (target.scrollHeight - target.scrollTop - target.clientHeight <= 120) {
      onLoadMore();
    }
  }, [hasMore, onLoadMore]);

  if (isLoading) {
    return (
      <div
        className="overflow-hidden rounded-lg border border-gray-700 bg-[linear-gradient(180deg,rgba(31,41,55,0.92),rgba(17,24,39,0.96))]"
        aria-live="polite"
        aria-busy="true"
      >
        <div className={`${compact ? 'max-h-[420px]' : 'max-h-[760px] xl:max-h-none xl:h-full'} overflow-y-auto ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}>
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className={`grid grid-cols-[1rem_minmax(0,1fr)] gap-2.5 ${item < 4 ? 'pb-3' : ''}`}>
              <div className="relative flex justify-center">
                {item < 4 ? <div className="absolute top-3.5 bottom-[-0.8rem] w-px bg-gray-700/80" /> : null}
                <div className="relative mt-1 h-2.5 w-2.5 rounded-full border border-sky-400/60 bg-sky-400/10">
                  <div className="absolute inset-[3px] rounded-full bg-sky-300/90" />
                </div>
              </div>
              <div className="animate-pulse rounded-md border border-gray-700 bg-gray-800/55 px-3 py-2.5">
                <div className="h-4 w-5/6 rounded bg-gray-700/80" />
                <div className="mt-2 h-4 w-3/4 rounded bg-gray-700/75" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/70 px-4 py-5 text-sm text-slate-400" aria-live="polite">
        No headlines
      </div>
    );
  }

  const timelineArticles = articles.slice(0, visibleCount);

  return (
    <div
      className="overflow-hidden rounded-lg border border-gray-700 bg-[linear-gradient(180deg,rgba(31,41,55,0.88),rgba(17,24,39,0.96))] xl:flex-1 xl:min-h-0"
      aria-live="polite"
    >
      <div
        className={`${compact ? 'max-h-[420px]' : 'max-h-[760px] xl:max-h-none xl:h-full'} overflow-y-auto ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}
        onScroll={handleScroll}
      >
        {timelineArticles.map((article, index) => {
          const tone = getHeadlineTone(article, tickerChangeMap);
          const isLast = index === timelineArticles.length - 1;

          return (
            <a
              key={article.uuid}
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className={`group grid grid-cols-[1rem_minmax(0,1fr)] gap-2.5 transition focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-500 ${
                index < timelineArticles.length - 1 ? 'pb-3' : ''
              }`}
            >
              <div className="relative flex justify-center">
                {index < timelineArticles.length - 1 ? (
                  <div className={`absolute top-3.5 bottom-[-0.8rem] w-px ${tone.line}`} />
                ) : null}
                <div className={`relative mt-1 h-2.5 w-2.5 rounded-full border ${tone.dot}`}>
                  <div className={`absolute inset-[3px] rounded-full ${tone.dotCore}`} />
                </div>
              </div>

              <div className={`min-w-0 pb-2.5 ${isLast ? '' : 'border-b border-gray-800/80 group-hover:border-gray-700/90'}`}>
                <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0 text-[11px] text-slate-400">
                    {formatPublishedDateTime(article)}
                  </div>
                  <div className="shrink-0 text-[11px] text-slate-500">
                    {formatPublishedLabel(article)}
                  </div>
                </div>
                <div className="text-sm font-medium leading-snug text-slate-100">
                  {article.title}
                </div>
                {article.tickers.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {article.tickers.slice(0, compact ? 2 : 3).map((ticker) => (
                      <span
                        key={ticker}
                        className={`rounded-sm border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${tone.ticker}`}
                      >
                        {ticker}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </a>
          );
        })}
        {hasMore ? (
          <div className="pt-2 text-center text-[11px] text-slate-500">
            Scroll for more
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function MarketView({ onSelectTicker }: MarketViewProps) {
  const { user } = useAuth();
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
  const [moversPaginationLoading, setMoversPaginationLoading] = useState<'gainers' | 'losers' | 'most_active' | null>(null);
  const [headlines, setHeadlines] = useState<HeadlineArticle[]>([]);
  const [headlinesLoading, setHeadlinesLoading] = useState(false);
  const [mapRegions, setMapRegions] = useState<OverviewItem[]>([]);
  const [mapUsIndices, setMapUsIndices] = useState<OverviewItem[]>([]);
  const [mapDataLoading, setMapDataLoading] = useState(false);
  const [overviewDataLoading, setOverviewDataLoading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<'overview' | 'regional'>('overview');
  const [range, setRange] = useState<'1d' | '1w' | '1mo' | '6mo' | 'ytd'>('1d');

  // Sync URL -> tab state (reload / back restores tab)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam === 'overview' || tabParam === 'regional') {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  const handleMarketTabChange = useCallback((tab: 'overview' | 'regional') => {
    setActiveTab(tab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', tab);
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  const [paginationSection, setPaginationSection] = useState<'indices' | 'sectors' | 'regions' | 'commodities' | null>(null);
  const [error, setError] = useState<string | null>(null);
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
      const { articles } = await tickerApi.getNewsBatch(initialHeadlinesTickers);
      const merged: HeadlineArticle[] = (articles ?? []).map((a) => ({
        uuid: a.uuid,
        title: a.title,
        summary: a.summary ?? null,
        publisher: a.publisher,
        link: a.link,
        published_time: a.published_time ?? null,
        published_timestamp: a.published_timestamp ?? 0,
        type: a.type,
        thumbnail: a.thumbnail ?? null,
        tickers: a.tickers ?? [],
      }));
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
      updateOnlySection?: 'indices' | 'sectors' | 'regions' | 'commodities',
      overviewRange?: '1d' | '1w' | '1mo' | '3mo' | 'ytd'
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
        range: overviewRange ?? range,
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
    [range]
  );

  const applyOverviewAndMoversData = useCallback(
    (overviewData: Awaited<ReturnType<typeof tickerApi.getMarketOverview>>, moversData: { gainers?: MarketMoverRow[]; losers?: MarketMoverRow[]; most_active?: MarketMoverRow[] }) => {
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
      setMapRegions([]);
      setMapUsIndices([]);
      setOverview({ indices, sectors, international, commodities });
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
    },
    []
  );

  const fetchAll = useCallback(async () => {
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
          range,
        }),
        tickerApi.getMarketMovers(MOVERS_PAGE_SIZE),
      ]);
      applyOverviewAndMoversData(overviewData, moversData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load market data');
      setOverview(null);
      setMapRegions([]);
      setMapUsIndices([]);
      setGainers([]);
      setLosers([]);
      setMostActive([]);
      setInitialHeadlinesTickers([]);
    }
  }, [range, applyOverviewAndMoversData]);

  const fetchMapOverview = useCallback(async () => {
    if (!user) return;
    setMapDataLoading(true);
    try {
      // Fetch only regions and indices (no sectors/commodities) so the backend does not call yfinance for unused groups.
      const [regionsRes, indicesRes] = await Promise.all([
        tickerApi.getMarketOverviewSection('regions', { limit: 100, offset: 0, range }),
        tickerApi.getMarketOverviewSection('indices', { limit: 15, offset: 0, range }),
      ]);
      setMapRegions(regionsRes.items ?? []);
      setMapUsIndices(indicesRes.items ?? []);
    } finally {
      setMapDataLoading(false);
    }
  }, [user, range]);

  useEffect(() => {
    if (activeTab === 'regional' && user) {
      fetchMapOverview();
    }
  }, [activeTab, user, fetchMapOverview]);

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

  const totalPagesGainers = MOVERS_TOTAL_PAGES;
  const totalPagesLosers = MOVERS_TOTAL_PAGES;
  const totalPagesMostActive = MOVERS_TOTAL_PAGES;

  const fetchMoreMovers = useCallback(async (requiredCount: number, table: 'gainers' | 'losers' | 'most_active') => {
    const capped = Math.min(requiredCount, MOVERS_TOTAL_PAGES * MOVERS_PAGE_SIZE);
    if (capped <= gainers.length) return;
    setMoversPaginationLoading(table);
    try {
      const data = await tickerApi.getMarketMovers(capped);
      setGainers(data.gainers ?? []);
      setLosers(data.losers ?? []);
      setMostActive(data.most_active ?? []);
    } finally {
      setMoversPaginationLoading(null);
    }
  }, [gainers.length]);

  const handlePrevGainers = useCallback(() => {
    setMoversPageGainers((p) => Math.max(0, p - 1));
  }, []);
  const handleNextGainers = useCallback(async () => {
    const nextPage = moversPageGainers + 1;
    const requiredCount = (nextPage + 1) * MOVERS_PAGE_SIZE;
    if (gainers.length < requiredCount) {
      await fetchMoreMovers(requiredCount, 'gainers');
    }
    setMoversPageGainers(nextPage);
  }, [moversPageGainers, gainers.length, fetchMoreMovers]);
  const handlePrevLosers = useCallback(() => {
    setMoversPageLosers((p) => Math.max(0, p - 1));
  }, []);
  const handleNextLosers = useCallback(async () => {
    const nextPage = moversPageLosers + 1;
    const requiredCount = (nextPage + 1) * MOVERS_PAGE_SIZE;
    if (losers.length < requiredCount) {
      await fetchMoreMovers(requiredCount, 'losers');
    }
    setMoversPageLosers(nextPage);
  }, [moversPageLosers, losers.length, fetchMoreMovers]);
  const handlePrevMostActive = useCallback(() => {
    setMoversPageMostActive((p) => Math.max(0, p - 1));
  }, []);
  const handleNextMostActive = useCallback(async () => {
    const nextPage = moversPageMostActive + 1;
    const requiredCount = (nextPage + 1) * MOVERS_PAGE_SIZE;
    if (mostActive.length < requiredCount) {
      await fetchMoreMovers(requiredCount, 'most_active');
    }
    setMoversPageMostActive(nextPage);
  }, [moversPageMostActive, mostActive.length, fetchMoreMovers]);

  const hasInitialFetched = useRef(false);
  const prevRangeRef = useRef(range);

  useEffect(() => {
    if (hasInitialFetched.current) return;
    hasInitialFetched.current = true;
    setError(null);
    const r = range;
    const overviewPromise = tickerApi.getMarketOverview({
      limit_indices: TILES_PER_PAGE,
      offset_indices: 0,
      limit_sectors: TILES_PER_PAGE,
      offset_sectors: 0,
      limit_regions: TILES_PER_PAGE,
      offset_regions: 0,
      limit_commodities: TILES_PER_PAGE,
      offset_commodities: 0,
      range: r,
    });
    const moversPromise = tickerApi.getMarketMovers(MOVERS_PAGE_SIZE);

    // Show market movers as soon as they load
    moversPromise
      .then((moversData) => {
        setGainers(moversData.gainers ?? []);
        setLosers(moversData.losers ?? []);
        setMostActive(moversData.most_active ?? []);
        setMoversPageGainers(0);
        setMoversPageLosers(0);
        setMoversPageMostActive(0);
      })
      .catch(() => {});

    // Show overview tiles as soon as they load
    overviewPromise
      .then((overviewData) => {
        setOverview({
          indices: overviewData.indices ?? [],
          sectors: overviewData.sectors ?? [],
          international: overviewData.international ?? [],
          commodities: overviewData.commodities ?? [],
        });
        setTotals({
          totalIndices: overviewData.totalIndices ?? 0,
          totalSectors: overviewData.totalSectors ?? 0,
          totalRegions: overviewData.totalRegions ?? 0,
          totalCommodities: overviewData.totalCommodities ?? 0,
        });
        setPages({ indices: 0, sectors: 0, regions: 0, commodities: 0 });
      })
      .catch(() => {});

    // When both are ready, set merged headlines and ensure full state
    Promise.all([overviewPromise, moversPromise])
      .then(([overviewData, moversData]) => {
        applyOverviewAndMoversData(overviewData, moversData);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed to load market data');
        setOverview(null);
        setMapRegions([]);
        setMapUsIndices([]);
        setGainers([]);
        setLosers([]);
        setMostActive([]);
        setInitialHeadlinesTickers([]);
      });
  }, [applyOverviewAndMoversData]);

  useEffect(() => {
    if (prevRangeRef.current === range) return;
    prevRangeRef.current = range;
    if (activeTab === 'overview') {
      setOverviewDataLoading(true);
      fetchOverview(0, 0, 0, 0).finally(() => setOverviewDataLoading(false));
    } else if (activeTab === 'regional' && user) {
      fetchMapOverview();
    }
  }, [range, activeTab, user, fetchOverview, fetchMapOverview]);

  const overviewItems = useMemo(
    () => (overview ? [...overview.indices, ...overview.sectors, ...overview.international, ...overview.commodities] : []),
    [overview]
  );

  const positiveOverviewCount = useMemo(
    () => overviewItems.filter((item) => (item.changePercent ?? 0) >= 0).length,
    [overviewItems]
  );

  const breadthPercent = overviewItems.length > 0 ? Math.round((positiveOverviewCount / overviewItems.length) * 100) : null;

  const topPerformer = useMemo(() => {
    const candidates = [
      ...overviewItems.map((item) => ({
        ticker: item.ticker,
        name: item.name,
        changePercent: item.changePercent,
      })),
      ...gainers.map((row) => ({
        ticker: row.symbol ?? '',
        name: row.shortName ?? row.symbol ?? 'Top mover',
        changePercent: row.regularMarketChangePercent,
      })),
    ]
      .filter((item) => item.changePercent != null)
      .sort((a, b) => (b.changePercent ?? Number.NEGATIVE_INFINITY) - (a.changePercent ?? Number.NEGATIVE_INFINITY));

    return candidates[0] ?? null;
  }, [overviewItems, gainers]);

  const volumeLeader = mostActive[0] ?? null;
  const marketTone: 'emerald' | 'sky' | 'rose' =
    breadthPercent == null ? 'sky' : breadthPercent >= 60 ? 'emerald' : breadthPercent >= 45 ? 'sky' : 'rose';
  const heroDescription =
    activeTab === 'overview'
      ? `${getRangeLabel(range)} across indices, sectors, global benchmarks, and commodities.`
      : `${getRangeLabel(range)} performance mapped across regional exchanges and major U.S. anchors.`;

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
    <div className="space-y-6 pb-4">
      <section className="rounded-xl border border-gray-700 bg-gray-800/80 shadow-[0_14px_30px_-26px_rgba(15,23,42,0.8)]">
        <div className="space-y-4 p-4 sm:p-5">
          <div className="space-y-3">
            <div className="space-y-4 xl:grid xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.95fr)] xl:items-start xl:gap-4 xl:space-y-0">
              <div className="space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-gray-700 bg-gray-700/50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                <span className="h-2 w-2 rounded-full bg-sky-400" />
                Market view
              </div>
              <div className="space-y-2">
                <h1 className="max-w-3xl text-xl font-semibold tracking-tight text-white sm:text-2xl">
                  Market overview, movers, and regional context in one screen.
                </h1>
                <p className="max-w-2xl text-xs leading-relaxed text-gray-400 sm:text-sm">
                  {heroDescription} Scan the market quickly, then drill into the names or regions that matter.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full border border-gray-700 bg-gray-700/50 px-3 py-1 text-[11px] font-medium text-slate-300">
                  {activeTab === 'overview' ? 'Cross-asset overview' : 'Regional heat map'}
                </span>
                <span className="rounded-full border border-gray-700 bg-gray-700/50 px-3 py-1 text-[11px] font-medium text-slate-300">
                  Range: {getRangeLabel(range)}
                </span>
              </div>
              <div className="max-w-2xl">
                <TickerSearch compact />
              </div>
              </div>
              <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
                <PulseCard
                  eyebrow="Breadth"
                  value={breadthPercent != null ? `${breadthPercent}% green` : 'Loading'}
                  detail={
                    overviewItems.length > 0
                      ? `${positiveOverviewCount} of ${overviewItems.length} tracked benchmarks are positive.`
                      : 'Collecting cross-asset performance.'
                  }
                  tone={marketTone}
                />
                <PulseCard
                  eyebrow="Leader"
                  value={topPerformer?.ticker || '—'}
                  detail={
                    topPerformer
                      ? `${topPerformer.name} · ${formatPct(topPerformer.changePercent)}`
                      : 'Scanning for the strongest move.'
                  }
                  tone={topPerformer ? ((topPerformer.changePercent ?? 0) >= 0 ? 'emerald' : 'rose') : 'sky'}
                />
                <PulseCard
                  eyebrow="Volume"
                  value={volumeLeader?.symbol || '—'}
                  detail={
                    volumeLeader
                      ? `${volumeLeader.shortName || 'Most active'} · Vol ${formatVolume(volumeLeader.regularMarketVolume)}`
                      : 'Waiting for active tape data.'
                  }
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-gray-700 bg-gray-800/80 p-3 shadow-[0_12px_26px_-22px_rgba(15,23,42,0.8)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleMarketTabChange('overview')}
              className={`rounded-full border px-4 py-1.5 text-xs font-medium transition sm:text-sm ${
                activeTab === 'overview'
                  ? 'border-sky-400/25 bg-sky-400/10 text-white'
                  : 'border-gray-700 bg-gray-700/50 text-slate-300 hover:border-gray-600 hover:bg-gray-700 hover:text-white'
              }`}
            >
              Overview
            </button>
            <button
              type="button"
              onClick={() => handleMarketTabChange('regional')}
              className={`rounded-full border px-4 py-1.5 text-xs font-medium transition sm:text-sm ${
                activeTab === 'regional'
                  ? 'border-sky-400/25 bg-sky-400/10 text-white'
                  : 'border-gray-700 bg-gray-700/50 text-slate-300 hover:border-gray-600 hover:bg-gray-700 hover:text-white'
              }`}
            >
              Regional Map
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Timeframe">
            {activeTab === 'overview' && overviewDataLoading && (
              <span className="mr-1 flex items-center gap-1.5 text-xs text-slate-400" aria-live="polite">
                <svg className="h-3.5 w-3.5 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" aria-hidden>
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Updating…
              </span>
            )}
            {activeTab === 'regional' && mapDataLoading && (
              <span className="mr-1 flex items-center gap-1.5 text-xs text-slate-400" aria-live="polite">
                <svg className="h-3.5 w-3.5 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" aria-hidden>
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Updating…
              </span>
            )}
            {(['1d', '1w', '1mo', '6mo', 'ytd'] as const).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] transition sm:text-xs ${
                  range === r
                    ? 'border-gray-500 bg-gray-700 text-white'
                    : 'border-gray-700 bg-gray-700/50 text-slate-300 hover:border-gray-600 hover:bg-gray-700 hover:text-white'
                }`}
              >
                {r === '1d'
                  ? '1D'
                  : r === '1w'
                    ? '1W'
                    : r === '1mo'
                      ? '1M'
                      : r === '6mo'
                        ? '6M'
                        : 'YTD'}
              </button>
            ))}
          </div>
        </div>
      </section>

      {activeTab === 'overview' && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px] xl:items-stretch">
          <div className="space-y-6">
            <section className="space-y-4">
              <SectionHeading
                title="Cross-asset overview"
              />

              {overview ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-4">
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
              ) : (
                <div className="grid grid-cols-1 gap-4 animate-pulse sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800/70">
                      <div className="h-14 border-b border-gray-700 bg-gray-700/60" />
                      <div className="grid grid-cols-2 gap-2.5 p-3">
                        {[1, 2, 3, 4, 5, 6].map((j) => (
                          <div key={j} className="h-32 rounded-lg bg-gray-700/70" />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="space-y-4">
              <SectionHeading
                title="Today&apos;s market movers"
              />

              {gainers.length > 0 || losers.length > 0 || mostActive.length > 0 ? (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 2xl:grid-cols-3">
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
                    paginationLoading={moversPaginationLoading === 'gainers'}
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
                    paginationLoading={moversPaginationLoading === 'losers'}
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
                    paginationLoading={moversPaginationLoading === 'most_active'}
                  />
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-6 animate-pulse lg:grid-cols-2 2xl:grid-cols-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800/70">
                      <div className="h-16 border-b border-gray-700 bg-gray-700/60" />
                      <div className="space-y-2 p-3">
                        {[1, 2, 3, 4, 5, 6, 7, 8].map((j) => (
                          <div key={j} className="h-12 rounded-lg bg-gray-700/70" />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="space-y-4 xl:hidden">
              <NewsBriefingPanel
                articles={headlines}
                isLoading={headlinesLoading}
                tickerChangeMap={tickerChangeMap}
              />
            </section>
          </div>

          <aside className="hidden xl:block xl:min-h-0">
            <NewsBriefingPanel
              articles={headlines}
              isLoading={headlinesLoading}
              tickerChangeMap={tickerChangeMap}
            />
          </aside>
        </div>
      )}

      {activeTab === 'regional' && (
        <section className="space-y-4">
          <div className="relative rounded-xl border border-gray-700 bg-gray-800/80 p-3 shadow-[0_12px_26px_-22px_rgba(15,23,42,0.8)] sm:p-4">
            {!user ? (
              <>
                <WorldMapRegionalStocks regionalItems={[]} usIndices={[]} />
                <div
                  className="absolute inset-3 flex flex-col items-center justify-center rounded-xl bg-gray-900/88"
                  role="status"
                  aria-live="polite"
                >
                  <p className="text-sm font-medium text-slate-200">Sign in to unlock the regional map</p>
                  <p className="mt-1 max-w-md text-center text-xs leading-relaxed text-slate-500">
                    Regional market data for the map is only requested for logged-in users.
                  </p>
                </div>
              </>
            ) : mapDataLoading && mapRegions.length === 0 && mapUsIndices.length === 0 ? (
              <>
                <div className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800/80">
                  <div className="h-12 border-b border-gray-700 bg-gray-700/60" />
                  <div className="w-full animate-pulse bg-gray-700/60" style={{ aspectRatio: '2 / 1' }} />
                </div>
                <div className="absolute left-6 right-6 top-6 z-10 rounded-xl border border-gray-700 bg-gray-800/90 px-4 py-3 shadow-[0_14px_32px_-24px_rgba(0,0,0,0.85)]">
                  <div className="flex items-center gap-3">
                    <svg className="h-5 w-5 animate-spin shrink-0 text-sky-400" fill="none" viewBox="0 0 24 24" aria-hidden>
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-200">Preparing Regional Map…</div>
                      <div className="mt-0.5 text-xs text-slate-400">Loading regional indices and U.S. anchors.</div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <WorldMapRegionalStocks
                regionalItems={mapRegions}
                usIndices={mapUsIndices}
                onSelectTicker={onSelectTicker}
              />
            )}
          </div>
        </section>
      )}
    </div>
  );
}
