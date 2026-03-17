import { useEffect, useState, useCallback, useRef } from 'react';
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
}

const NEWS_WIDGET_HEIGHT = 960;
const PAGE_SIZE = 20;

export default function DashboardNewsSection({
  tickers,
  refreshIntervalMs = 120000,
  fillHeight = false,
}: DashboardNewsSectionProps) {
  const [articles, setArticles] = useState<NewsArticleWithTicker[]>([]);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const tickersKey = tickers.join(',');

  const fetchNews = useCallback(async () => {
    const portfolioTickers = tickersKey ? tickersKey.split(',') : [];

    if (portfolioTickers.length === 0) {
      setArticles([]);
      setSelectedTickers([]);
      setLastUpdated(new Date());
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled(
        portfolioTickers.map((ticker) => tickerApi.getNews(ticker))
      );
      const byKey = new Map<string, NewsArticleWithTicker>();
      results.forEach((result, i) => {
        if (result.status === 'fulfilled' && result.value?.articles?.length) {
          const ticker = portfolioTickers[i];
          if (!ticker) return;
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
      setArticles(merged);
      setLastUpdated(new Date());
      setDisplayCount(PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load news');
    } finally {
      setIsLoading(false);
    }
  }, [tickersKey]);

  useEffect(() => {
    fetchNews();
  }, [fetchNews]);

  useEffect(() => {
    if (refreshIntervalMs <= 0) return;
    const id = setInterval(fetchNews, refreshIntervalMs);
    return () => clearInterval(id);
  }, [fetchNews, refreshIntervalMs]);

  useEffect(() => {
    const portfolioTickers = new Set(tickersKey ? tickersKey.split(',') : []);
    setSelectedTickers((current) => current.filter((ticker) => portfolioTickers.has(ticker)));
  }, [tickersKey]);

  useEffect(() => {
    setDisplayCount(PAGE_SIZE);
  }, [selectedTickers]);

  const toggleTickerTag = useCallback((ticker: string) => {
    setSelectedTickers((current) => (
      current.includes(ticker)
        ? current.filter((item) => item !== ticker)
        : [...current, ticker]
    ));
  }, []);

  const filtered = selectedTickers.length > 0
    ? articles.filter((article) => article.tickers.some((ticker) => selectedTickers.includes(ticker)))
    : articles;
  const displayList = filtered.slice(0, displayCount);
  const hasMore = displayList.length < filtered.length;
  const tickerCounts = tickers.reduce<Record<string, number>>((acc, ticker) => {
    acc[ticker] = articles.filter((article) => article.tickers.includes(ticker)).length;
    return acc;
  }, {});

  useEffect(() => {
    if (!hasMore || !loadMoreRef.current || !scrollContainerRef.current) return;
    const sentinel = loadMoreRef.current;
    const root = scrollContainerRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setDisplayCount((c) => Math.min(c + PAGE_SIZE, filtered.length));
        }
      },
      { root, rootMargin: '100px', threshold: 0 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, filtered.length]);

  return (
    <div
      className={`bg-gray-800 rounded-lg border border-gray-700 flex flex-col ${fillHeight ? 'min-h-0 flex-1 overflow-hidden' : 'shrink-0'}`}
      style={
        fillHeight
          ? { maxHeight: 'min(calc(100vh - 12rem), 960px)' }
          : { height: NEWS_WIDGET_HEIGHT, maxHeight: NEWS_WIDGET_HEIGHT }
      }
    >
      <div className="p-4 border-b border-gray-700 shrink-0">
        {lastUpdated && (
          <div className="flex justify-end mb-3">
            <span className="text-xs text-gray-500 whitespace-nowrap">
              Last updated: {lastUpdated.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · {lastUpdated.toLocaleDateString()}
            </span>
          </div>
        )}
        {selectedTickers.length > 0 && (
          <div className="mb-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setSelectedTickers([])}
              className="text-xs font-medium text-gray-400 transition-colors hover:text-white"
            >
              Clear filters
            </button>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSelectedTickers([])}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              selectedTickers.length === 0
                ? 'border-blue-500 bg-blue-600 text-white'
                : 'border-gray-600 bg-gray-800 text-gray-300 hover:border-gray-500 hover:bg-gray-700'
            }`}
          >
            All tickers
          </button>
          {tickers.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => toggleTickerTag(t)}
              aria-pressed={selectedTickers.includes(t)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                selectedTickers.includes(t)
                  ? 'border-blue-500 bg-blue-600 text-white'
                  : 'border-gray-600 bg-gray-800 text-gray-300 hover:border-gray-500 hover:bg-gray-700'
              }`}
            >
              {t}
              <span className={`ml-1.5 ${selectedTickers.includes(t) ? 'text-blue-100' : 'text-gray-400'}`}>
                {tickerCounts[t] ?? 0}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto min-h-0 p-4"
      >
        {error && (
          <p className="text-amber-400/90 text-sm">{error}</p>
        )}
        {isLoading && articles.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-gray-700/50 rounded-lg p-4 animate-pulse">
                <div className="h-4 bg-gray-600 rounded w-3/4 mb-2" />
                <div className="h-3 bg-gray-600 rounded w-1/4" />
              </div>
            ))}
          </div>
        ) : displayList.length === 0 ? (
          <p className="text-gray-400 text-sm">
            {selectedTickers.length > 0
              ? `No news articles match ${selectedTickers.join(', ')}.`
              : 'No news articles for your stocks.'}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {displayList.map((article) => (
              <div
                key={article.uuid || article.link}
                className="bg-gray-700/50 rounded-lg p-4 hover:border-gray-600 border border-transparent transition-colors"
              >
                <div className="flex gap-4">
                  {article.thumbnail && (
                    <div className="flex-shrink-0">
                      <img
                        src={article.thumbnail}
                        alt={article.title}
                        className="w-24 h-24 object-cover rounded"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                        }}
                      />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="mb-1 flex flex-wrap gap-1">
                      {article.tickers.map((t) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => toggleTickerTag(t)}
                          aria-pressed={selectedTickers.includes(t)}
                          className={`rounded-full border px-2 py-0.5 text-xs font-medium transition-colors ${
                            selectedTickers.includes(t)
                              ? 'border-blue-500 bg-blue-600 text-white'
                              : 'border-gray-500 bg-gray-600 text-gray-200 hover:border-gray-400 hover:bg-gray-500'
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                    <a
                      href={article.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 font-semibold text-base leading-tight block hover:underline"
                    >
                      {article.title}
                    </a>
                    <div className="flex items-center gap-3 mt-1 text-sm text-gray-400">
                      <span className="font-medium">{article.publisher}</span>
                      {article.published_time && (
                        <>
                          <span>•</span>
                          <span>{article.published_time}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {hasMore && <div ref={loadMoreRef} className="h-4 col-span-full flex-shrink-0" aria-hidden />}
          </div>
        )}
      </div>
    </div>
  );
}
