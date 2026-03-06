import { useState } from 'react';
import { Link } from 'react-router-dom';
import TickerSearch from '../components/StockSearch';
import DashboardTopTiles from '../components/DashboardTopTiles';
import DashboardStockSidebar from '../components/DashboardStockSidebar';
import StockDetailPanel from '../components/StockDetailPanel';
import StockListView from '../components/StockListView';
import DashboardNewsSection from '../components/DashboardNewsSection';
import DashboardPriceTrendsChart from '../components/DashboardPriceTrendsChart';
import OverviewStatsPanel, { ByMarketSection } from '../components/OverviewStatsPanel';
import { useDashboardData } from '../hooks/useDashboardData';
import { useAuth } from '../contexts/AuthContext';

type DashboardTab = 'overview' | 'stock-view' | 'news';
type StockListTab = 'subscribed' | 'recent';

export default function DashboardPage() {
  const { user } = useAuth();
  const [dashboardTab, setDashboardTab] = useState<DashboardTab>('overview');
  const [stockListTab, setStockListTab] = useState<StockListTab>('subscribed');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const {
    widgets,
    recentAnalyzedWidgets,
    recentTotal,
    loadingMoreRecent,
    backgroundLoadingAll,
    tickerToName,
    isLoading,
    selectedTicker,
    setSelectedTicker,
    prefetchCache,
    sidebarScrollRef,
    recentScrollRef,
    handleSidebarScroll,
    handleRecentScroll,
    handleSubscriptionChange,
  } = useDashboardData();

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

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <svg className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-gray-400 text-sm">Loading dashboard…</p>
        </div>
      </div>
    );
  }

  if (widgets.length === 0 && recentAnalyzedWidgets.length === 0) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full">
          <TickerSearch />
          <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
            <p className="text-gray-400 mb-4">You haven't subscribed to any stocks yet.</p>
            <p className="text-gray-500 text-sm mb-6">Add stocks from the search above or browse on Home to build your dashboard.</p>
            <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
              Browse stocks
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const subscribedTickers = widgets.map((w) => w.ticker);
  const subscribedTickerSet = new Set(subscribedTickers);
  const recentAnalyzedNonSubscribed = recentAnalyzedWidgets.filter(
    (w) => !subscribedTickerSet.has(w.ticker)
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Scrolling ticker bar */}
      <DashboardTopTiles
        subscribedWidgets={widgets}
        recentAnalyzedWidgets={recentAnalyzedWidgets}
        onSelectTicker={(ticker) => { setSelectedTicker(ticker); setDashboardTab('stock-view'); }}
      />

      {/* Dashboard-level tab bar + search */}
      <div className="px-4 pt-2 border-b border-gray-700 bg-gray-900 shrink-0">
        {/* Search row — full width */}
        <div className="pb-2">
          <TickerSearch compact />
        </div>
        {/* Tabs row */}
        <div className="flex items-end gap-0.5">
          <nav className="flex gap-0.5" aria-label="Dashboard views">
            {([
                { id: 'overview', label: 'Overview' },
                { id: 'stock-view', label: 'Stock View' },
                { id: 'news', label: 'News' },
              ] as { id: DashboardTab; label: string }[]).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setDashboardTab(tab.id)}
                className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors -mb-px ${
                  dashboardTab === tab.id
                    ? 'text-white border-blue-500 bg-gray-800'
                    : 'text-gray-400 border-transparent hover:text-white hover:bg-gray-800/60'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ── Stock View Tab ── */}
      {dashboardTab === 'stock-view' && (
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* Left sidebar — desktop */}
          <aside className={`shrink-0 border-r border-gray-700 bg-gray-800/50 flex-row min-h-0 hidden md:flex transition-all duration-200 ${sidebarCollapsed ? 'w-6' : 'w-64'}`}>
            {/* Stock list — hidden when collapsed */}
            {!sidebarCollapsed && (
              <div
                ref={sidebarScrollRef}
                onScroll={handleSidebarScroll}
                className="flex-1 min-w-0 min-h-0 overflow-y-auto"
              >
                <DashboardStockSidebar
                  subscribedWidgets={widgets}
                  recentWidgets={recentAnalyzedWidgets}
                  tickerToName={tickerToName}
                  selectedTicker={selectedTicker}
                  onSelect={setSelectedTicker}
                />
                {(loadingMoreRecent || backgroundLoadingAll) && (
                  <div className="py-3 text-center text-gray-400 text-xs flex items-center justify-center gap-1.5">
                    <svg className="w-3 h-3 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    {backgroundLoadingAll
                      ? `Loading ${recentAnalyzedWidgets.length}${recentTotal != null ? ` / ${recentTotal}` : ''}…`
                      : 'Loading more…'}
                  </div>
                )}
                {recentTotal != null && recentAnalyzedWidgets.length >= recentTotal && recentTotal > 0 && (
                  <div className="py-2 text-center text-gray-500 text-xs">
                    All {recentTotal} analyzed in the last 3 days
                  </div>
                )}
              </div>
            )}
            {/* Collapse toggle — vertical strip on the right edge */}
            <button
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="shrink-0 flex items-center justify-center w-6 self-stretch border-l border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700/50 transition-colors"
            >
              <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${sidebarCollapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          </aside>

          {/* Mobile: collapsible stock list above detail panel */}
          <div className="md:hidden flex flex-col flex-1 min-h-0 overflow-y-auto">
            {/* Toggle header */}
            <div className="shrink-0 border-b border-gray-700 bg-gray-800/80">
              <button
                type="button"
                onClick={() => setSidebarCollapsed((c) => !c)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors"
              >
                <span className="font-medium">Stocks</span>
                <svg className={`w-4 h-4 transition-transform duration-200 ${sidebarCollapsed ? '' : 'rotate-180'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {!sidebarCollapsed && (
                <div style={{ maxHeight: '35vh', overflowY: 'auto' }}>
                  <DashboardStockSidebar
                    subscribedWidgets={widgets}
                    recentWidgets={recentAnalyzedWidgets}
                    tickerToName={tickerToName}
                    selectedTicker={selectedTicker}
                    onSelect={(ticker) => { setSelectedTicker(ticker); setSidebarCollapsed(true); }}
                  />
                </div>
              )}
            </div>
            {/* Detail panel below */}
            <div className="flex-1 min-h-0 bg-gray-900">
              {selectedTicker ? (
                <StockDetailPanel
                  key={selectedTicker}
                  ticker={selectedTicker}
                  prefetchedData={prefetchCache[selectedTicker] ?? null}
                  onSubscriptionChange={handleSubscriptionChange}
                />
              ) : (
                <div className="flex-1 flex items-center justify-center text-gray-500 text-sm p-8">
                  Select a stock from the list above to view details.
                </div>
              )}
            </div>
          </div>

          {/* Right main panel — desktop */}
          <main className="flex-1 min-w-0 flex-col min-h-0 bg-gray-900 hidden md:flex">
            {selectedTicker ? (
              <StockDetailPanel
                key={selectedTicker}
                ticker={selectedTicker}
                prefetchedData={prefetchCache[selectedTicker] ?? null}
                onSubscriptionChange={handleSubscriptionChange}
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                Select a stock from the list to view details.
              </div>
            )}
          </main>
        </div>
      )}

      {/* ── Overview Tab ── */}
      {dashboardTab === 'overview' && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-6 sm:p-6 lg:p-8">
            <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">

              {/* Subscribed stocks stats by market/exchange */}
              {widgets.length > 0 && (
                <div className="mb-6">
                  <OverviewStatsPanel widgets={widgets} tickerToName={tickerToName} hideByMarket />
                </div>
              )}

              {/* Price trends chart */}
              {subscribedTickers.length > 0 && (
                <div className="min-h-[340px]">
                  <DashboardPriceTrendsChart tickers={subscribedTickers} period="6mo" height={340} />
                </div>
              )}

              {/* Combined stock list widget — full width */}
              <div className="mt-6">
                {/* Tab header */}
                <div className="flex items-center gap-0 mb-0 border-b border-gray-700">
                  <button
                    type="button"
                    onClick={() => setStockListTab('subscribed')}
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
                    onClick={() => setStockListTab('recent')}
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
                </div>

                {/* Subscribed tab content */}
                {stockListTab === 'subscribed' && (
                  <StockListView widgets={widgets} tickerToName={tickerToName} />
                )}

                {/* Recently analyzed tab content */}
                {stockListTab === 'recent' && (
                  recentAnalyzedNonSubscribed.length === 0 ? (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 border-t-0 p-8 text-center">
                      <p className="text-gray-400 text-sm">No analyzed stocks in the last 3 days.</p>
                    </div>
                  ) : (
                    <StockListView
                      widgets={recentAnalyzedNonSubscribed}
                      tickerToName={tickerToName}
                      scrollRef={recentScrollRef}
                      onScroll={handleRecentScroll}
                      preserveOrder={true}
                      footer={
                        <>
                          {loadingMoreRecent && (
                            <div className="py-3 text-center text-gray-400 text-sm">Loading more…</div>
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
              </div>

              {/* By Market — below the subscribed stocks table */}
              {widgets.length > 0 && (
                <div className="mt-6">
                  <ByMarketSection widgets={widgets} tickerToName={tickerToName} />
                </div>
              )}

            </div>
          </div>
        </div>
      )}

      {/* ── News Tab ── */}
      {dashboardTab === 'news' && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-6 sm:p-6 lg:p-8">
            <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
              {subscribedTickers.length > 0 ? (
                <DashboardNewsSection
                  tickers={subscribedTickers}
                  refreshIntervalMs={120000}
                />
              ) : (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
                  <p className="text-gray-400 text-sm">Subscribe to stocks to see news here.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

// Made with Bob
