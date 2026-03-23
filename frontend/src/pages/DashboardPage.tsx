import { useEffect, useState, useCallback } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import TickerSearch from '../components/TickerSearch';
import DashboardEventsView from '../components/DashboardEventsView';
import PageHeader from '../components/PageHeader';
import TickerListView from '../components/StockListView';
import { useDashboardData } from '../hooks/useDashboardData';
import { useAuth } from '../contexts/AuthContext';
import { digestApi } from '../services/api';

type StockListTab = 'subscribed' | 'recent' | 'events';

const STOCK_LIST_TAB_IDS: StockListTab[] = ['subscribed', 'recent', 'events'];

export default function DashboardPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [stockListTab, setStockListTab] = useState<StockListTab>('subscribed');
  const [hasBriefForToday, setHasBriefForToday] = useState<boolean | null>(null);
  const [briefPromptDismissed, setBriefPromptDismissed] = useState<boolean>(() => {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem('flowdeck_brief_prompt_dismissed') === 'true';
    }
    return false;
  });
  const shouldLoadRecentAnalyzed = stockListTab === 'recent';
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;

  useEffect(() => {
    const listParam = searchParams.get('list');
    if (listParam && STOCK_LIST_TAB_IDS.includes(listParam as StockListTab)) {
      setStockListTab(listParam as StockListTab);
    }
  }, [searchParams]);

  const {
    widgets,
    recentAnalyzedWidgets,
    recentTotal,
    loadingMoreRecent,
    tickerToName,
    isLoading,
    recentScrollRef,
    handleRecentScroll,
  } = useDashboardData({
    enableRecentAnalyzed: shouldLoadRecentAnalyzed,
  });

  const handleStockListTabChange = useCallback((list: StockListTab) => {
    setStockListTab(list);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('list', list);
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await digestApi.getDigestDates(7, browserTimezone);
        const dates = res.dates ?? [];
        const today = new Date();
        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
        if (!cancelled) {
          setHasBriefForToday(dates.includes(todayStr));
        }
      } catch {
        if (!cancelled) setHasBriefForToday(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [browserTimezone, user]);

  if (searchParams.get('tab') === 'digest') {
    return <Navigate to="/brief" replace />;
  }

  if (searchParams.get('tab') === 'pulse') {
    return <Navigate to="/portfolio-pulse" replace />;
  }

  if (searchParams.get('tab') === 'news') {
    return <Navigate to="/newsroom" replace />;
  }

  if (!user) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8 flex items-center justify-center">
        <div className="max-w-md text-center">
          <p className="text-gray-400 mb-6">Sign in to view and manage your subscribed stocks.</p>
          <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  const hasNoStocks = !isLoading && widgets.length === 0 && recentAnalyzedWidgets.length === 0;
  const subscribedTickerSet = new Set(widgets.map((widget) => widget.ticker));
  const recentAnalyzedNonSubscribed = recentAnalyzedWidgets.filter(
    (widget) => !subscribedTickerSet.has(widget.ticker)
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader
        title="Dashboard"
        icon={
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        }
      />

      <div className="px-4 pt-2 border-b border-gray-700 bg-gray-900 shrink-0">
        <div className="pb-2">
          <TickerSearch compact />
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 py-6 sm:p-6 lg:p-8">
          <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
            {isLoading && widgets.length === 0 && recentAnalyzedWidgets.length === 0 && (
              <div className="mb-6 bg-gray-800 rounded-lg border border-gray-700 p-6">
                <div className="flex items-center gap-2 text-gray-300 text-sm">
                  <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Loading dashboard data...</span>
                </div>
              </div>
            )}

            {user && !briefPromptDismissed && hasBriefForToday === false && (
              <div className="mb-6 bg-gray-800 rounded-lg border border-gray-700 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-white mb-0.5">No brief for today yet.</p>
                  <p className="text-xs text-gray-400">
                    Get a short narrative summary of today's market and your portfolio.
                  </p>
                </div>
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <Link
                    to="/brief"
                    className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-gray-900"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Generate today's brief
                  </Link>
                  <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer sm:whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={briefPromptDismissed}
                      onChange={(event) => {
                        const checked = event.target.checked;
                        setBriefPromptDismissed(checked);
                        try {
                          if (checked) localStorage.setItem('flowdeck_brief_prompt_dismissed', 'true');
                          else localStorage.removeItem('flowdeck_brief_prompt_dismissed');
                        } catch {}
                      }}
                      className="rounded border-gray-600 bg-gray-900 text-emerald-600 focus:ring-emerald-500"
                    />
                    Don't show this again
                  </label>
                </div>
              </div>
            )}

            {hasNoStocks ? (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
                <p className="text-gray-400 mb-4">You haven't subscribed to any stocks yet.</p>
                <p className="text-gray-500 text-sm mb-6">Add stocks from the search above or browse on Home to build your dashboard. Use the <Link to="/market" className="text-gray-400 hover:text-white font-medium">Market</Link> page for indices, sectors, and top gainers/losers.</p>
                <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
                  Browse stocks
                </Link>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-0 mb-0 border-b border-gray-700">
                  <button
                    type="button"
                    onClick={() => handleStockListTabChange('subscribed')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors -mb-px ${
                      stockListTab === 'subscribed'
                        ? 'text-white border-blue-500 bg-gray-800'
                        : 'text-gray-400 border-transparent hover:text-white hover:bg-gray-800/60'
                    }`}
                  >
                    Subscribed stocks
                    {widgets.length > 0 && (
                      <span className="ml-1.5 text-xs text-gray-500">({widgets.length})</span>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStockListTabChange('recent')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors -mb-px ${
                      stockListTab === 'recent'
                        ? 'text-white border-blue-500 bg-gray-800'
                        : 'text-gray-400 border-transparent hover:text-white hover:bg-gray-800/60'
                    }`}
                  >
                    Recently Analyzed
                    {recentAnalyzedNonSubscribed.length > 0 && (
                      <span className="ml-1.5 text-xs text-gray-500">({recentAnalyzedNonSubscribed.length})</span>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStockListTabChange('events')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors -mb-px ${
                      stockListTab === 'events'
                        ? 'text-white border-blue-500 bg-gray-800'
                        : 'text-gray-400 border-transparent hover:text-white hover:bg-gray-800/60'
                    }`}
                  >
                    Events
                    {widgets.length > 0 && (
                      <span className="ml-1.5 text-xs text-gray-500">({widgets.length})</span>
                    )}
                  </button>
                </div>

                {stockListTab === 'subscribed' && (
                  <TickerListView widgets={widgets} tickerToName={tickerToName} />
                )}

                {stockListTab === 'recent' && (
                  isLoading && recentAnalyzedWidgets.length === 0 ? (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 border-t-0 p-8 text-center">
                      <div className="inline-flex items-center gap-2 text-gray-300 text-sm">
                        <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        <span>Loading recently analyzed stocks...</span>
                      </div>
                    </div>
                  ) : recentAnalyzedNonSubscribed.length === 0 ? (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 border-t-0 p-8 text-center">
                      <p className="text-gray-400 text-sm">No analyzed stocks in the last 3 days.</p>
                    </div>
                  ) : (
                    <TickerListView
                      widgets={recentAnalyzedNonSubscribed}
                      tickerToName={tickerToName}
                      scrollRef={recentScrollRef}
                      onScroll={handleRecentScroll}
                      preserveOrder={true}
                      footer={
                        <>
                          {loadingMoreRecent && (
                            <div className="py-3 text-center text-gray-400 text-sm">Loading more...</div>
                          )}
                          {recentTotal != null && recentAnalyzedWidgets.length >= recentTotal && recentTotal > 0 && (
                            <div className="py-2 text-center text-gray-500 text-xs">
                              All {recentAnalyzedNonSubscribed.length} analyzed in the last 3 days
                            </div>
                          )}
                        </>
                      }
                    />
                  )
                )}

                {stockListTab === 'events' && (
                  <div className="rounded-b-2xl border border-gray-700 border-t-0 bg-gray-900/45 p-4 sm:p-5">
                    <DashboardEventsView widgets={widgets} tickerToName={tickerToName} dashboardLoading={isLoading} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
