import { useEffect, useState, useCallback, useRef } from 'react';
import { stockApi } from '../services/api';

export interface NewsArticleWithTicker {
  uuid: string;
  title: string;
  publisher: string;
  link: string;
  published_time: string | null;
  published_timestamp: number;
  type: string;
  thumbnail: string | null;
  ticker: string;
}

interface DashboardNewsSectionProps {
  tickers: string[];
  /** Refresh interval in ms; 0 = no auto refresh */
  refreshIntervalMs?: number;
}

const NEWS_WIDGET_HEIGHT = 960;
const PAGE_SIZE = 20;

export default function DashboardNewsSection({
  tickers,
  refreshIntervalMs = 120000,
}: DashboardNewsSectionProps) {
  const [articles, setArticles] = useState<NewsArticleWithTicker[]>([]);
  const [filterTicker, setFilterTicker] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const fetchNews = useCallback(async () => {
    if (tickers.length === 0) {
      setArticles([]);
      setLastUpdated(new Date());
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled(
        tickers.map((t) => stockApi.getNews(t))
      );
      const merged: NewsArticleWithTicker[] = [];
      results.forEach((result, i) => {
        if (result.status === 'fulfilled' && result.value?.articles?.length) {
          const ticker = tickers[i];
          result.value.articles.forEach((a) => {
            merged.push({
              ...a,
              ticker,
            });
          });
        }
      });
      merged.sort((a, b) => (b.published_timestamp ?? 0) - (a.published_timestamp ?? 0));
      setArticles(merged);
      setLastUpdated(new Date());
      setDisplayCount(PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load news');
    } finally {
      setIsLoading(false);
    }
  }, [tickers.join(',')]);

  useEffect(() => {
    fetchNews();
  }, [fetchNews]);

  useEffect(() => {
    if (refreshIntervalMs <= 0) return;
    const id = setInterval(fetchNews, refreshIntervalMs);
    return () => clearInterval(id);
  }, [fetchNews, refreshIntervalMs]);

  useEffect(() => {
    setDisplayCount(PAGE_SIZE);
  }, [filterTicker]);

  const filtered = filterTicker
    ? articles.filter((a) => a.ticker === filterTicker)
    : articles;
  const displayList = filtered.slice(0, displayCount);
  const hasMore = displayList.length < filtered.length;

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
      className="bg-gray-800 rounded-lg border border-gray-700 flex flex-col shrink-0"
      style={{ height: NEWS_WIDGET_HEIGHT, maxHeight: NEWS_WIDGET_HEIGHT }}
    >
      <div className="p-4 border-b border-gray-700 shrink-0">
        <div className="flex items-center justify-between gap-2 mb-3">
          <h2 className="text-lg font-semibold text-white">News</h2>
          {lastUpdated && (
            <span className="text-xs text-gray-500 whitespace-nowrap">
              Last updated: {lastUpdated.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · {lastUpdated.toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFilterTicker(null)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              filterTicker === null
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            All
          </button>
          {tickers.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setFilterTicker(t)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                filterTicker === t
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto min-h-0 p-4 space-y-4"
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
          <p className="text-gray-400 text-sm">No news articles for your stocks.</p>
        ) : (
          <>
            {displayList.map((article) => (
              <div
                key={`${article.ticker}-${article.uuid}`}
                className="bg-gray-700/50 rounded-lg p-3 hover:border-gray-600 border border-transparent transition-colors"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <span className="shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-gray-600 text-gray-200">
                    {article.ticker}
                  </span>
                </div>
                <a
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 font-medium text-sm leading-tight block hover:underline"
                >
                  {article.title}
                </a>
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                  <span>{article.publisher}</span>
                  {article.published_time && (
                    <>
                      <span>·</span>
                      <span>{article.published_time}</span>
                    </>
                  )}
                </div>
                <a
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block"
                >
                  Read more
                </a>
              </div>
            ))}
            {hasMore && <div ref={loadMoreRef} className="h-4 flex-shrink-0" aria-hidden />}
          </>
        )}
      </div>
    </div>
  );
}
