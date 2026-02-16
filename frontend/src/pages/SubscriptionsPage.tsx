import { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import StockListView from '../components/StockListView';
import StockSearch from '../components/StockSearch';
import DashboardNewsSection from '../components/DashboardNewsSection';
import DashboardTopTiles from '../components/DashboardTopTiles';
import { stockApi } from '../services/api';
import { subscriptionApi } from '../services/subscriptionApi';
import type { StockWidget as StockWidgetType } from '../services/types';
import { useAuth } from '../contexts/AuthContext';

const RECENT_PAGE_SIZE = 10;

export default function SubscriptionsPage() {
  const { user } = useAuth();
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [recentAnalyzedWidgets, setRecentAnalyzedWidgets] = useState<StockWidgetType[]>([]);
  const [recentTotal, setRecentTotal] = useState<number | null>(null);
  const [loadingMoreRecent, setLoadingMoreRecent] = useState(false);
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const recentScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((arr: Array<{ ticker: string; name: string }>) => {
        const map: Record<string, string> = {};
        arr.forEach(({ ticker, name }) => {
          map[ticker] = name;
        });
        setTickerToName(map);
      })
      .catch(() => {});
  }, []);

  const loadSubscriptions = async () => {
    if (!user) {
      setWidgets([]);
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      const subs = await subscriptionApi.list();
      const tickers = subs.map((s) => s.ticker);
      if (tickers.length > 0) {
        const res = await stockApi.getWidgets(tickers);
        setWidgets(res.widgets);
      } else {
        setWidgets([]);
      }
    } catch {
      setWidgets([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSubscriptions();
    const interval = setInterval(loadSubscriptions, 60000);
    return () => clearInterval(interval);
  }, [user]);

  const loadRecentPage = useCallback(
    async (offset: number, append: boolean) => {
      const today = new Date().toISOString().slice(0, 10);
      const res = await stockApi.getWidgets(undefined, today, true, RECENT_PAGE_SIZE, offset);
      if (res.total != null) setRecentTotal(res.total);
      if (append) {
        setRecentAnalyzedWidgets((prev) => [...prev, ...res.widgets]);
      } else {
        setRecentAnalyzedWidgets(res.widgets);
      }
    },
    []
  );

  useEffect(() => {
    if (!user) return;
    loadRecentPage(0, false).catch(() => {
      setRecentAnalyzedWidgets([]);
      setRecentTotal(null);
    });
    const interval = setInterval(() => loadRecentPage(0, false).catch(() => {}), 60000);
    return () => clearInterval(interval);
  }, [user, loadRecentPage]);

  const handleRecentScroll = useCallback(() => {
    const el = recentScrollRef.current;
    if (!el || loadingMoreRecent || recentTotal == null) return;
    if (recentAnalyzedWidgets.length >= recentTotal) return;
    const threshold = 120;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - threshold) {
      setLoadingMoreRecent(true);
      const today = new Date().toISOString().slice(0, 10);
      stockApi
        .getWidgets(undefined, today, true, RECENT_PAGE_SIZE, recentAnalyzedWidgets.length)
        .then((res) => {
          if (res.total != null) setRecentTotal(res.total);
          setRecentAnalyzedWidgets((prev) => [...prev, ...res.widgets]);
        })
        .finally(() => setLoadingMoreRecent(false));
    }
  }, [loadingMoreRecent, recentTotal, recentAnalyzedWidgets.length]);

  const tickers = widgets.map((w) => w.ticker);

  if (!user) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8 flex items-center justify-center">
        <div className="max-w-md text-center">
          <p className="text-gray-400 mb-6">
            Sign in to view and manage your subscribed stocks.
          </p>
          <Link
            to="/"
            className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
          >
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading && widgets.length === 0) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full">
          <StockSearch />
          <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
            <p className="text-gray-400">Loading subscribed stocks…</p>
          </div>
        </div>
      </div>
    );
  }

  if (widgets.length === 0 && recentAnalyzedWidgets.length === 0) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full">
          <StockSearch />
          <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
            <p className="text-gray-400 mb-4">You haven’t subscribed to any stocks yet.</p>
            <p className="text-gray-500 text-sm mb-6">
              Add stocks from the search above or browse on Home to build your dashboard.
            </p>
            <Link
              to="/"
              className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
            >
              Browse stocks
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8">
      <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
        <DashboardTopTiles
          subscribedWidgets={widgets}
          recentAnalyzedWidgets={recentAnalyzedWidgets}
        />
        <StockSearch />

        <div className="mt-6 flex flex-col lg:flex-row gap-6 lg:gap-8 lg:items-stretch">
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="shrink-0">
              <h2 className="text-lg font-semibold text-white mb-4">Subscribed stocks</h2>
              <StockListView widgets={widgets} tickerToName={tickerToName} />
            </div>
            <div className="flex-1 flex flex-col min-h-0 mt-8">
              <h2 className="text-lg font-semibold text-white mb-4 shrink-0">Recently Analyzed</h2>
              {recentAnalyzedWidgets.length === 0 ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center shrink-0">
                  <p className="text-gray-400 text-sm">No other analyzed stocks for this date.</p>
                </div>
              ) : (
                <StockListView
                  widgets={recentAnalyzedWidgets}
                  tickerToName={tickerToName}
                  scrollRef={recentScrollRef}
                  onScroll={handleRecentScroll}
                  footer={
                    <>
                      {loadingMoreRecent && (
                        <div className="py-3 text-center text-gray-400 text-sm">Loading more…</div>
                      )}
                      {recentTotal != null && recentAnalyzedWidgets.length >= recentTotal && recentTotal > 0 && (
                        <div className="py-2 text-center text-gray-500 text-xs">
                          All {recentTotal} analyzed today
                        </div>
                      )}
                    </>
                  }
                />
              )}
            </div>
          </div>
          <aside className="w-full lg:w-[360px] shrink-0 flex flex-col min-h-[400px]">
            <DashboardNewsSection
              tickers={tickers}
              refreshIntervalMs={120000}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}
