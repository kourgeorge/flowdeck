import { useEffect, useState, useCallback, useRef, type CSSProperties } from 'react';
import { tickerApi } from '../services/api';

export interface NewsArticleWithTicker {
  uuid: string;
  title: string;
  summary?: string | null;
  publisher: string;
  link: string;
  published_time: string | null;
  published_timestamp: number;
  type: string;
  thumbnail: string | null;
  /** Related tickers (deduplicated) */
  tickers: string[];
}

interface DashboardNewsSectionProps {
  tickers: string[];
  /** Refresh interval in ms; 0 = no auto refresh */
  refreshIntervalMs?: number;
  /** When true, grow to fill container height (e.g. to span alongside left column) */
  fillHeight?: boolean;
  /** Free-text filter for headlines, summaries, publishers, and ticker tags. */
  searchQuery?: string;
  /** Optional change handler for the external search UI. */
  onSearchQueryChange?: (value: string) => void;
  /** Optional clear handler for the external search UI. */
  onClearSearch?: () => void;
}

const PAGE_SIZE = 20;

const titleClampStyles: CSSProperties = {
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  WebkitLineClamp: 2,
  overflow: 'hidden',
};

const summaryClampStyles: CSSProperties = {
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  WebkitLineClamp: 3,
  overflow: 'hidden',
};

function formatRelativeTime(timestamp?: number | null): string {
  if (!timestamp) return 'Recently published';

  const diffMs = Date.now() - timestamp * 1000;
  if (!Number.isFinite(diffMs)) return 'Recently published';

  const diffMinutes = Math.round(diffMs / 60000);
  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(new Date(timestamp * 1000));
}

function formatAbsoluteTime(timestamp?: number | null, publishedTime?: string | null): string {
  if (timestamp) {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(timestamp * 1000));
  }

  return publishedTime || 'Publication time unavailable';
}

function formatTypeLabel(type?: string | null): string {
  if (!type) return 'News';

  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getSummary(article: NewsArticleWithTicker): string {
  const summary = article.summary?.trim();
  if (summary) return summary;

  if (article.tickers.length > 0) {
    return `Coverage tied to ${article.tickers.join(', ')}. Open the full article for the complete reporting and market context.`;
  }

  return 'Open the full article for the complete reporting and market context.';
}

function ExternalLinkIcon() {
  return (
    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M14 5h5m0 0v5m0-5L10 14" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 14v3a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3" />
    </svg>
  );
}

function StoryImage({
  article,
  className,
}: {
  article: NewsArticleWithTicker;
  className: string;
}) {
  if (!article.thumbnail) {
    return (
      <div className={`${className} relative overflow-hidden bg-slate-900`}>
        <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between gap-3 text-xs text-slate-200/90">
          <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
            {formatTypeLabel(article.type)}
          </span>
          <span className="truncate">{article.publisher}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className} overflow-hidden bg-slate-900`}>
      <img
        src={article.thumbnail}
        alt={article.title}
        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
        onError={(event) => {
          (event.target as HTMLImageElement).style.display = 'none';
        }}
      />
    </div>
  );
}

function NewsroomSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="fd-card-strong p-6">
        <div className="h-3 w-28 rounded-full bg-slate-700" />
        <div className="mt-4 h-10 w-72 rounded-full bg-slate-700" />
        <div className="mt-3 h-4 w-[32rem] max-w-full rounded-full bg-slate-800" />
        <div className="mt-5 flex flex-wrap gap-2">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-9 w-24 rounded-full bg-slate-800" />
          ))}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_22rem]">
        <div className="fd-card overflow-hidden">
          <div className="aspect-[16/8.5] bg-slate-800" />
          <div className="space-y-3 p-6">
            <div className="h-4 w-48 rounded-full bg-slate-700" />
            <div className="h-8 w-4/5 rounded-full bg-slate-700" />
            <div className="h-4 w-full rounded-full bg-slate-800" />
            <div className="h-4 w-3/4 rounded-full bg-slate-800" />
          </div>
        </div>
        <div className="fd-card p-5">
          <div className="h-5 w-32 rounded-full bg-slate-700" />
          <div className="mt-4 space-y-3">
            {[1, 2, 3, 4].map((item) => (
              <div key={item} className="fd-card-soft p-4">
                <div className="h-4 w-3/4 rounded-full bg-slate-700" />
                <div className="mt-2 h-4 w-1/2 rounded-full bg-slate-800" />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {[1, 2, 3, 4].map((item) => (
          <div key={item} className="fd-card-soft p-4">
            <div className="mb-4 aspect-[16/9] rounded-lg bg-slate-800" />
            <div className="h-4 w-28 rounded-full bg-slate-700" />
            <div className="mt-3 h-6 w-4/5 rounded-full bg-slate-700" />
            <div className="mt-2 h-4 w-full rounded-full bg-slate-800" />
            <div className="mt-2 h-4 w-3/4 rounded-full bg-slate-800" />
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState({
  selectedTickers,
  onClearFilters,
  searchQuery,
  onClearSearch,
}: {
  selectedTickers: string[];
  onClearFilters: () => void;
  searchQuery: string;
  onClearSearch?: () => void;
}) {
  const hasFilters = selectedTickers.length > 0;
  const hasSearch = searchQuery.trim().length > 0;
  const hasAnyRefinement = hasFilters || hasSearch;

  return (
    <div className="fd-card px-6 py-12 text-center">
      <div className="fd-card-soft mx-auto flex h-14 w-14 items-center justify-center text-cyan-300">
        <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7H5m14 5H8m11 5H5" />
        </svg>
      </div>
      <h3 className="mt-4 text-xl font-semibold text-white">
        {hasSearch
          ? `No stories match "${searchQuery.trim()}"`
          : hasFilters
            ? `No stories match ${selectedTickers.join(', ')}`
            : 'No newsroom stories yet'}
      </h3>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-400">
        {hasAnyRefinement
          ? 'Try broadening your search or clearing some filters to bring more of your newsroom back into view.'
          : 'Subscribe to more active names or check back shortly while the newsroom refreshes.'}
      </p>
      {hasAnyRefinement && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          {hasSearch && onClearSearch && (
            <button
              type="button"
              onClick={onClearSearch}
              className="rounded-full border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:border-slate-500 hover:bg-slate-700"
            >
              Clear search
            </button>
          )}
          {hasFilters && (
            <button
              type="button"
              onClick={onClearFilters}
              className="rounded-full border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:border-slate-500 hover:bg-slate-700"
            >
              Clear filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function TickerPills({
  article,
  selectedTickers,
  onToggleTicker,
}: {
  article: NewsArticleWithTicker;
  selectedTickers: string[];
  onToggleTicker: (ticker: string) => void;
}) {
  if (article.tickers.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {article.tickers.map((ticker) => {
        const active = selectedTickers.includes(ticker);

        return (
          <button
            key={ticker}
            type="button"
            onClick={() => onToggleTicker(ticker)}
            aria-pressed={active}
            className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
              active
                ? 'border-sky-400/60 bg-sky-500/15 text-sky-100'
                : 'border-slate-600 bg-slate-800/80 text-slate-300 hover:border-slate-500 hover:bg-slate-700'
            }`}
          >
            {ticker}
          </button>
        );
      })}
    </div>
  );
}

function PulseCard({
  article,
  selectedTickers,
  onToggleTicker,
}: {
  article: NewsArticleWithTicker;
  selectedTickers: string[];
  onToggleTicker: (ticker: string) => void;
}) {
  return (
    <a
      href={article.link}
      target="_blank"
      rel="noopener noreferrer"
      className="fd-card-soft group block p-4 transition-colors hover:border-slate-500 hover:bg-slate-950"
    >
      <div className="flex items-center justify-between gap-3 text-xs text-slate-400">
        <span className="truncate font-medium text-slate-200">{article.publisher}</span>
        <span className="shrink-0">{formatRelativeTime(article.published_timestamp)}</span>
      </div>
      <h4 className="mt-3 text-sm font-semibold leading-6 text-white transition-colors group-hover:text-cyan-200" style={titleClampStyles}>
        {article.title}
      </h4>
      <div className="mt-3">
        <TickerPills article={article} selectedTickers={selectedTickers} onToggleTicker={onToggleTicker} />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs uppercase tracking-[0.16em] text-slate-400">
        <span>{formatTypeLabel(article.type)}</span>
        <span className="inline-flex items-center gap-1 text-cyan-300">
          Open
          <ExternalLinkIcon />
        </span>
      </div>
    </a>
  );
}

function FeedCard({
  article,
  selectedTickers,
  onToggleTicker,
}: {
  article: NewsArticleWithTicker;
  selectedTickers: string[];
  onToggleTicker: (ticker: string) => void;
}) {
  return (
    <a
      href={article.link}
      target="_blank"
      rel="noopener noreferrer"
      className="fd-card group flex h-full flex-col overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-500 hover:bg-slate-900"
    >
      <StoryImage article={article} className="aspect-[16/9] w-full" />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-slate-400">
          <span className="fd-pill fd-pill-sm">
            {formatTypeLabel(article.type)}
          </span>
          <span>{formatRelativeTime(article.published_timestamp)}</span>
        </div>
        <h4 className="mt-3 text-lg font-semibold leading-7 text-white transition-colors group-hover:text-cyan-200" style={titleClampStyles}>
          {article.title}
        </h4>
        <p className="mt-3 text-sm leading-6 text-slate-300" style={summaryClampStyles}>
          {getSummary(article)}
        </p>
        <div className="mt-4">
          <TickerPills article={article} selectedTickers={selectedTickers} onToggleTicker={onToggleTicker} />
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 text-sm">
          <span className="truncate font-medium text-slate-200">{article.publisher}</span>
          <span className="inline-flex items-center gap-1 text-cyan-300 transition-colors group-hover:text-cyan-200">
            Open article
            <ExternalLinkIcon />
          </span>
        </div>
      </div>
    </a>
  );
}

export default function DashboardNewsSection({
  tickers,
  refreshIntervalMs = 120000,
  fillHeight = false,
  searchQuery = '',
  onSearchQueryChange,
  onClearSearch,
}: DashboardNewsSectionProps) {
  const [articles, setArticles] = useState<NewsArticleWithTicker[]>([]);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const requestIdRef = useRef(0);
  const tickersKey = tickers.join(',');
  const normalizedSearchQuery = searchQuery.trim().toLowerCase();

  const fetchNews = useCallback(async () => {
    const portfolioTickers = tickersKey ? tickersKey.split(',') : [];
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    if (portfolioTickers.length === 0) {
      setArticles([]);
      setSelectedTickers([]);
      setLastUpdated(new Date());
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await tickerApi.getNewsBatch(portfolioTickers);
      if (requestId !== requestIdRef.current) return;

      setArticles(
        (response.articles ?? []).map((article) => ({
          ...article,
          publisher: article.publisher ?? '',
          type: article.type ?? '',
          thumbnail: article.thumbnail ?? null,
        }))
      );
      setLastUpdated(new Date());
      setDisplayCount(PAGE_SIZE);
    } catch (fetchError) {
      if (requestId !== requestIdRef.current) return;
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load news');
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [tickersKey]);

  useEffect(() => {
    fetchNews();
  }, [fetchNews]);

  useEffect(() => {
    if (refreshIntervalMs <= 0) return;

    const intervalId = setInterval(fetchNews, refreshIntervalMs);
    return () => clearInterval(intervalId);
  }, [fetchNews, refreshIntervalMs]);

  useEffect(() => {
    const portfolioTickers = new Set(tickersKey ? tickersKey.split(',') : []);
    setSelectedTickers((current) => current.filter((ticker) => portfolioTickers.has(ticker)));
  }, [tickersKey]);

  useEffect(() => {
    setDisplayCount(PAGE_SIZE);
  }, [selectedTickers, normalizedSearchQuery]);

  const toggleTickerTag = useCallback((ticker: string) => {
    setSelectedTickers((current) => (
      current.includes(ticker)
        ? current.filter((item) => item !== ticker)
        : [...current, ticker]
    ));
  }, []);

  const clearTickerFilters = useCallback(() => {
    setSelectedTickers([]);
  }, []);

  const selectedTickerSet = new Set(selectedTickers);
  const tickerCounts = tickers.reduce<Record<string, number>>((accumulator, ticker) => {
    accumulator[ticker] = 0;
    return accumulator;
  }, {});
  const filteredArticles: NewsArticleWithTicker[] = [];

  for (const article of articles) {
    for (const ticker of article.tickers) {
      if (ticker in tickerCounts) {
        tickerCounts[ticker] += 1;
      }
    }

    const matchesTickers = selectedTickerSet.size === 0
      || article.tickers.some((ticker) => selectedTickerSet.has(ticker));

    if (!matchesTickers) continue;
    if (!normalizedSearchQuery) {
      filteredArticles.push(article);
      continue;
    }

    const searchableText = [
      article.title,
      article.summary ?? '',
      article.publisher,
      article.type,
      article.tickers.join(' '),
    ].join(' ').toLowerCase();

    if (searchableText.includes(normalizedSearchQuery)) {
      filteredArticles.push(article);
    }
  }

  const displayList = filteredArticles.slice(0, displayCount);
  const hasMore = displayList.length < filteredArticles.length;

  useEffect(() => {
    if (!hasMore || !loadMoreRef.current || (fillHeight && !scrollContainerRef.current)) return;

    const sentinel = loadMoreRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setDisplayCount((count) => Math.min(count + PAGE_SIZE, filteredArticles.length));
        }
      },
      {
        root: fillHeight ? scrollContainerRef.current : null,
        rootMargin: '160px',
        threshold: 0,
      }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [fillHeight, filteredArticles.length, hasMore]);

  const leadArticle = displayList[0] ?? null;
  const pulseArticles = displayList.slice(1, 5);
  const feedArticles = displayList.slice(5);
  const visiblePublisherCount = new Set(filteredArticles.map((article) => article.publisher).filter(Boolean)).size;
  const visibleTopPublishers = Array.from(
    new Set(filteredArticles.map((article) => article.publisher).filter(Boolean))
  ).slice(0, 5);

  return (
    <section
      className={fillHeight ? 'flex min-h-0 flex-1 flex-col' : undefined}
      style={fillHeight ? { maxHeight: 'min(calc(100vh - 12rem), 1200px)' } : undefined}
    >
      <div className="fd-page-block">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-4xl flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.3em] text-cyan-300/80">Watchlist Newsroom</div>
            <div className="mt-5 max-w-3xl">
              <label className="relative block">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m21 21-4.35-4.35M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z" />
                  </svg>
                </span>
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(event) => {
                    if (onSearchQueryChange) {
                      onSearchQueryChange(event.target.value);
                    }
                  }}
                  placeholder="Search headlines, summaries, publishers, tickers..."
                  className="fd-input focus:border-cyan-400/60"
                  aria-label="Search newsroom content"
                />
                {searchQuery.trim() && onClearSearch && (
                  <button
                    type="button"
                    onClick={onClearSearch}
                    className="absolute inset-y-0 right-2 flex items-center rounded-full px-2 text-slate-400 transition-colors hover:text-white"
                    aria-label="Clear newsroom search"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 6l12 12M18 6 6 18" />
                    </svg>
                  </button>
                )}
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-3 xl:items-end">
            <div className="flex flex-wrap gap-2 xl:justify-end">
              <div className="fd-pill fd-pill-md">
                <span className="font-semibold text-white">{filteredArticles.length}</span> live stories
              </div>
              {normalizedSearchQuery && (
                <div className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100">
                  Searching "{searchQuery.trim()}"
                </div>
              )}
              <div className="fd-pill fd-pill-md">
                <span className="font-semibold text-white">{visiblePublisherCount}</span> sources
              </div>
              {lastUpdated && (
                <div className="fd-pill fd-pill-md">
                  Updated {lastUpdated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                </div>
              )}
              <button
                type="button"
                onClick={fetchNews}
                disabled={isLoading}
                className="rounded-full border border-slate-600 bg-slate-900/70 px-4 py-2 text-sm font-medium text-white transition-colors hover:border-slate-500 hover:bg-slate-800 disabled:cursor-default disabled:opacity-60"
              >
                {isLoading ? 'Refreshing...' : 'Refresh newsroom'}
              </button>
            </div>

            {visibleTopPublishers.length > 0 && (
              <div className="flex flex-wrap gap-2 xl:justify-end">
                {visibleTopPublishers.map((publisher) => (
                  <span
                    key={publisher}
                    className="fd-pill fd-pill-sm"
                  >
                    {publisher}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={clearTickerFilters}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              selectedTickers.length === 0
                ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-100'
                : 'border-slate-600 bg-slate-900/65 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
            }`}
          >
            All watchlist
          </button>
          {tickers.map((ticker) => {
            const active = selectedTickers.includes(ticker);

            return (
              <button
                key={ticker}
                type="button"
                onClick={() => toggleTickerTag(ticker)}
                aria-pressed={active}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-100'
                    : 'border-slate-600 bg-slate-900/65 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                }`}
              >
                {ticker}
                <span className={`ml-1.5 ${active ? 'text-cyan-100/90' : 'text-slate-400'}`}>
                  {tickerCounts[ticker] ?? 0}
                </span>
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Showing the last successful newsroom pull. Refresh failed: {error}
          </div>
        )}
      </div>

      <div
        ref={fillHeight ? scrollContainerRef : undefined}
        className={fillHeight ? 'min-h-0 flex-1 overflow-y-auto' : undefined}
      >
        <div className="fd-page-content">
          {isLoading && articles.length === 0 ? (
            <NewsroomSkeleton />
          ) : !leadArticle ? (
            <EmptyState
              selectedTickers={selectedTickers}
              onClearFilters={clearTickerFilters}
              searchQuery={searchQuery}
              onClearSearch={onClearSearch}
            />
          ) : (
            <div className="space-y-6">
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_22rem]">
                <a
                  href={leadArticle.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="fd-card group overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-500"
                >
                  <div className="relative">
                    <StoryImage article={leadArticle} className="aspect-[16/8.5] w-full" />
                    <div className="pointer-events-none absolute inset-0 bg-slate-950/20" />
                    <div className="absolute right-4 top-4">
                      <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs font-medium text-white backdrop-blur">
                        Lead story
                        <ExternalLinkIcon />
                      </span>
                    </div>
                  </div>

                  <div className="p-5 sm:p-6">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      <span className="fd-pill fd-pill-sm">
                        {formatTypeLabel(leadArticle.type)}
                      </span>
                      <span className="font-medium text-slate-200">{leadArticle.publisher}</span>
                      <span>{formatRelativeTime(leadArticle.published_timestamp)}</span>
                    </div>
                    <h3 className="mt-4 text-2xl font-semibold leading-tight text-white transition-colors group-hover:text-cyan-200 sm:text-[2rem]">
                      {leadArticle.title}
                    </h3>
                    <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300 sm:text-[15px]">
                      {getSummary(leadArticle)}
                    </p>
                    <div className="mt-4">
                      <TickerPills article={leadArticle} selectedTickers={selectedTickers} onToggleTicker={toggleTickerTag} />
                    </div>
                    <div className="mt-5 flex flex-wrap items-center gap-3 text-sm text-slate-400">
                      <span>{formatAbsoluteTime(leadArticle.published_timestamp, leadArticle.published_time)}</span>
                      <span className="hidden h-1 w-1 rounded-full bg-slate-600 sm:block" />
                      <span>Source: {leadArticle.publisher}</span>
                    </div>
                  </div>
                </a>

                <div className="p-1 sm:p-0">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">Watchlist Pulse</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">Fast scan</div>
                    </div>
                    <div className="fd-pill fd-pill-sm">
                      {pulseArticles.length} stories
                    </div>
                  </div>
                  <div className="mt-4 space-y-3">
                    {pulseArticles.length > 0 ? (
                      pulseArticles.map((article) => (
                        <PulseCard
                          key={article.uuid || article.link}
                          article={article}
                          selectedTickers={selectedTickers}
                          onToggleTicker={toggleTickerTag}
                        />
                      ))
                    ) : (
                      <div className="fd-card-soft px-4 py-6 text-sm text-slate-400">
                        No additional headlines in the current filter set.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {feedArticles.length > 0 && (
                <div>
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-white">Latest Wire</h3>
                      <p className="mt-1 text-sm text-slate-400">
                        A broader stream of stories from across your watchlist.
                      </p>
                    </div>
                    <div className="text-sm text-slate-400">
                      Showing {displayList.length} of {filteredArticles.length}
                    </div>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {feedArticles.map((article) => (
                      <FeedCard
                        key={article.uuid || article.link}
                        article={article}
                        selectedTickers={selectedTickers}
                        onToggleTicker={toggleTickerTag}
                      />
                    ))}
                  </div>
                </div>
              )}

              {hasMore && <div ref={loadMoreRef} className="h-6" aria-hidden="true" />}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
