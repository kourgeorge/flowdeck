import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import TickerSearch from '../components/TickerSearch';
import DashboardTopTiles from '../components/DashboardTopTiles';
import PageHeader from '../components/PageHeader';
import DashboardTickerSidebar from '../components/DashboardTickerSidebar';
import StockDetailPanel from '../components/TickerDetailPanel';
import TickerListView from '../components/StockListView';
import DashboardNewsSection from '../components/DashboardNewsSection';
import DashboardPriceTrendsChart from '../components/DashboardPriceTrendsChart';
import DailyDigestRunPanel from '../components/DailyDigestRunPanel';
import OverviewStatsPanel, { ByMarketSection, SubscribedChangeColumnsChart } from '../components/OverviewStatsPanel';
import { useDashboardData } from '../hooks/useDashboardData';
import { useAuth } from '../contexts/AuthContext';
import { digestApi, type DigestResponse, type DigestBriefItem } from '../services/api';

type DashboardTab = 'overview' | 'portfolio' | 'stock-view' | 'news' | 'digest';
type StockListTab = 'subscribed' | 'recent';

export default function DashboardPage() {
  const { user } = useAuth();
  const [dashboardTab, setDashboardTab] = useState<DashboardTab>('overview');
  const [stockListTab, setStockListTab] = useState<StockListTab>('subscribed');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const shouldLoadRecentAnalyzed =
    dashboardTab === 'stock-view' || (dashboardTab === 'overview' && stockListTab === 'recent');

  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [digestError, setDigestError] = useState<string | null>(null);
  const [digestDates, setDigestDates] = useState<string[]>([]);
  const [digestCountByDate, setDigestCountByDate] = useState<Record<string, number>>({});
  const [selectedDigestDate, setSelectedDigestDate] = useState<string | null>(null);
  const [digestBriefsForDay, setDigestBriefsForDay] = useState<DigestBriefItem[]>([]);
  const [selectedBrief, setSelectedBrief] = useState<DigestBriefItem | null>(null);
  const [calendarMonth, setCalendarMonth] = useState<Date>(new Date());
  const [digestUserNote, setDigestUserNote] = useState<string>('');
  const [digestNarrativeStyle, setDigestNarrativeStyle] = useState<'default' | 'concise' | 'professional' | 'technical'>('default');
  const [selectedFocusTickers, setSelectedFocusTickers] = useState<string[]>([]);
  const [showReferences, setShowReferences] = useState<boolean>(false);
  const [showDigestHistory, setShowDigestHistory] = useState<boolean>(true);
  const [showRawDigest, setShowRawDigest] = useState<boolean>(false);
  const [digestInputExpanded, setDigestInputExpanded] = useState<boolean>(false);

  const {
    widgets,
    recentAnalyzedWidgets,
    recentTotal,
    loadingMoreRecent,
    backgroundLoadingAll,
    prefetchProgress,
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
  } = useDashboardData({
    enablePrefetch: dashboardTab === 'stock-view',
    enableRecentAnalyzed: shouldLoadRecentAnalyzed,
  });

  const handleRunDigest = async () => {
    setDigestError(null);
    setDigest(null);
    setDigestLoading(true);
    try {
      const trimmedNote = digestUserNote.trim();
      const styleParam = digestNarrativeStyle === 'default' ? undefined : digestNarrativeStyle;
      const params: { user_note?: string; narrative_style?: string; user_focus_tickers?: string[] } = {};
      if (trimmedNote) params.user_note = trimmedNote;
      if (styleParam) params.narrative_style = styleParam;
      if (selectedFocusTickers.length > 0) params.user_focus_tickers = selectedFocusTickers;
      const data = await digestApi.getDigest(
        Object.keys(params).length ? params : undefined,
      );
      setDigest(data);
      setSelectedDigestDate(data.digest_date);
      setDigestDates((prev) =>
        prev.includes(data.digest_date) ? prev : [...prev, data.digest_date].sort()
      );
      setDigestCountByDate((prev) => ({
        ...prev,
        [data.digest_date]: (prev[data.digest_date] ?? 0) + 1,
      }));
      if (trimmedNote) {
        setDigestUserNote('');
      }
      // Refresh list for today so the new brief appears
      const listRes = await digestApi.getDigestsForDate(data.digest_date);
      setDigestBriefsForDay(listRes.briefs);
      setSelectedBrief(listRes.briefs[0] ?? null);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
    } finally {
      setDigestLoading(false);
    }
  };

  // Load digest history dates and show last digest when opening the digest tab (once per session)
  useEffect(() => {
    if (dashboardTab !== 'digest') return;
    if (digestDates.length > 0) return;
    (async () => {
      try {
        const res = await digestApi.getDigestDates(90);
        const dates = res.dates ?? [];
        setDigestDates(dates);
        setDigestCountByDate(res.count_by_date ?? {});
        if (dates.length > 0) {
          const latestDate = dates[dates.length - 1];
          setSelectedDigestDate(latestDate);
          setDigest(null);
          setDigestLoading(true);
          try {
            const listRes = await digestApi.getDigestsForDate(latestDate);
            setDigestBriefsForDay(listRes.briefs);
            setSelectedBrief(listRes.briefs[0] ?? null);
          } catch {
            setDigestBriefsForDay([]);
            setSelectedBrief(null);
          } finally {
            setDigestLoading(false);
          }
        }
      } catch {
        // history is best-effort; ignore errors
      }
    })();
  }, [dashboardTab, digestDates.length]);

  const handleSelectDigestDate = async (date: string) => {
    setDigestError(null);
    setDigestLoading(true);
    setSelectedDigestDate(date);
    try {
      const res = await digestApi.getDigestsForDate(date);
      setDigestBriefsForDay(res.briefs);
      setSelectedBrief(res.briefs[0] ?? null);
      setDigest(null); // use selectedBrief for display
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
      setDigestBriefsForDay([]);
      setSelectedBrief(null);
    } finally {
      setDigestLoading(false);
    }
  };

  const goToPrevMonth = () => {
    setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };

  const goToNextMonth = () => {
    setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const calendarYear = calendarMonth.getFullYear();
  const calendarMonthIndex = calendarMonth.getMonth(); // 0-11
  const firstOfMonth = new Date(calendarYear, calendarMonthIndex, 1);
  const startWeekday = firstOfMonth.getDay(); // 0 (Sun) - 6 (Sat)
  const daysInMonth = new Date(calendarYear, calendarMonthIndex + 1, 0).getDate();

  const formatDate = (y: number, mZeroBased: number, d: number) => {
    const m = mZeroBased + 1;
    const mm = m < 10 ? `0${m}` : String(m);
    const dd = d < 10 ? `0${d}` : String(d);
    return `${y}-${mm}-${dd}`;
  };

  const digestDateSet = new Set(digestDates);

  const formatBriefTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  const formatBriefForClipboard = (brief: DigestResponse | DigestBriefItem) => {
    const lines: string[] = [];
    if (brief.digest_date) {
      lines.push(`User Daily Brief – ${brief.digest_date}`);
    } else {
      lines.push('User Daily Brief');
    }
    if (brief.priority_tickers && brief.priority_tickers.length > 0) {
      lines.push(`Focus: ${brief.priority_tickers.join(', ')}`);
    }
    lines.push('');
    lines.push(brief.narrative.trim());
    if (brief.what_to_watch) {
      lines.push('');
      lines.push('What to watch');
      lines.push(brief.what_to_watch.trim());
    }
    const anyBrief = brief as any;
    const refs = anyBrief?.references as
      | { label: string; url?: string | null; source?: string | null; tickers?: string[] | null }[]
      | null
      | undefined;
    if (refs && refs.length > 0) {
      lines.push('');
      lines.push('References');
      refs.forEach((ref, idx) => {
        const parts: string[] = [];
        parts.push(`${idx + 1}. ${ref.label}`);
        const meta: string[] = [];
        if (ref.source) meta.push(ref.source);
        if (ref.url) meta.push(ref.url);
        if (ref.tickers && ref.tickers.length > 0) {
          meta.push(`Tickers: ${ref.tickers.join(', ')}`);
        }
        if (meta.length > 0) {
          parts.push(`(${meta.join(' • ')})`);
        }
        lines.push(parts.join(' '));
      });
    }
    return lines.join('\n');
  };

  const formatBriefRaw = (brief: DigestResponse | DigestBriefItem) => {
    const anyBrief = brief as any;
    const payload = {
      narrative: brief.narrative,
      what_to_watch: brief.what_to_watch,
      digest_date: brief.digest_date,
      priority_tickers: brief.priority_tickers,
      user_note: anyBrief?.user_note ?? null,
      narrative_style: anyBrief?.narrative_style ?? null,
      user_focus_tickers: anyBrief?.user_focus_tickers ?? null,
      references: anyBrief?.references ?? null,
      // Full metadata blob as stored/returned by backend
      metadata: anyBrief?.raw_metadata ?? null,
    };
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return String(payload);
    }
  };

  const handleCopyBrief = (brief: DigestResponse | DigestBriefItem) => {
    const text = formatBriefForClipboard(brief);
    if (navigator && 'clipboard' in navigator && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => {
        // best-effort; ignore copy failures
      });
    }
  };

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

  const subscribedTickers = widgets.map((w) => w.ticker);
  const hasNoStocks = !isLoading && widgets.length === 0 && recentAnalyzedWidgets.length === 0;
  const subscribedTickerSet = new Set(subscribedTickers);
  const recentAnalyzedNonSubscribed = recentAnalyzedWidgets.filter(
    (w) => !subscribedTickerSet.has(w.ticker)
  );
  const prefetchPercent = prefetchProgress.total > 0
    ? Math.round((prefetchProgress.completed / prefetchProgress.total) * 100)
    : 0;
  const showStockViewLoadingStatus = dashboardTab === 'stock-view' && (
    isLoading ||
    backgroundLoadingAll ||
    loadingMoreRecent ||
    prefetchProgress.inFlight > 0
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
                { id: 'portfolio', label: 'Portfolio' },
                { id: 'stock-view', label: 'Stock View' },
                { id: 'news', label: 'News' },
                { id: 'digest', label: 'User Daily Brief' },
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
        <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
          {showStockViewLoadingStatus && (
            <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 px-3 py-2 text-xs text-gray-300">
              <div className="flex items-center gap-2">
                <svg className="w-3.5 h-3.5 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Preparing Stock View…</span>
              </div>
              <div className="mt-1.5 space-y-1">
                <div>
                  Recently analyzed:
                  {' '}
                  {recentTotal != null
                    ? `${recentAnalyzedWidgets.length} / ${recentTotal}`
                    : (isLoading ? 'loading…' : `${recentAnalyzedWidgets.length}`)}
                </div>
                <div>
                  Stock prefetch:
                  {' '}
                  {prefetchProgress.completed} / {prefetchProgress.total}
                  {prefetchProgress.inFlight > 0 ? ` (${prefetchProgress.inFlight} in progress)` : ''}
                </div>
                {prefetchProgress.total > 0 && (
                  <div className="h-1.5 w-full rounded bg-gray-700 overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all duration-300"
                      style={{ width: `${prefetchPercent}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          )}

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
                  <DashboardTickerSidebar
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
                    <DashboardTickerSidebar
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
        </div>
      )}

      {/* ── Overview Tab ── */}
      {dashboardTab === 'overview' && (
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
                    <span>Loading dashboard data…</span>
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
              /* Combined stock list widget — full width */
              <div>
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
                  <TickerListView widgets={widgets} tickerToName={tickerToName} />
                )}

                {/* Recently analyzed tab content */}
                {stockListTab === 'recent' && (
                  isLoading && recentAnalyzedWidgets.length === 0 ? (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 border-t-0 p-8 text-center">
                      <div className="inline-flex items-center gap-2 text-gray-300 text-sm">
                        <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        <span>Loading recently analyzed stocks…</span>
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
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Portfolio Tab ── */}
      {dashboardTab === 'portfolio' && (
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
                    <span>Loading dashboard data…</span>
                  </div>
                </div>
              )}

              {/* Subscribed stocks stats by market/exchange */}
              {widgets.length > 0 && (
                <div className="mb-6">
                  <OverviewStatsPanel widgets={widgets} tickerToName={tickerToName} hideByMarket />
                </div>
              )}

              {/* Price trends chart */}
              {subscribedTickers.length > 0 && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  <div className="min-h-[340px]">
                    <DashboardPriceTrendsChart tickers={subscribedTickers} period="6mo" height={340} />
                  </div>
                  <div className="min-h-[340px]">
                    <SubscribedChangeColumnsChart widgets={widgets} height={340} />
                  </div>
                </div>
              )}

              {/* By Market */}
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

      {/* ── Digest Tab ── */}
      {dashboardTab === 'digest' && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-6 sm:p-6 lg:p-8">
            <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden space-y-4">
              {/* Run panel: brief options + Run digest button (above Brief history) */}
              <DailyDigestRunPanel
                digestUserNote={digestUserNote}
                onDigestUserNoteChange={setDigestUserNote}
                digestNarrativeStyle={digestNarrativeStyle}
                onDigestNarrativeStyleChange={setDigestNarrativeStyle}
                digestInputExpanded={digestInputExpanded}
                onDigestInputExpandedChange={setDigestInputExpanded}
                selectedFocusTickers={selectedFocusTickers}
                onSelectedFocusTickersChange={setSelectedFocusTickers}
                subscribedTickers={subscribedTickers}
                onRunDigest={handleRunDigest}
                digestLoading={digestLoading}
              />

              {/* Brief history calendar */}
              <div className="border border-gray-700/80 rounded-md bg-gray-900/60 overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowDigestHistory((v) => !v)}
                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-[11px] font-medium text-gray-300 hover:text-white hover:bg-gray-800/60 transition-colors"
                >
                  <span>Brief history</span>
                  <svg
                    className={`w-3.5 h-3.5 transition-transform ${showDigestHistory ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showDigestHistory && (
                  <div className="px-3 pb-3 pt-0">
                    <div className="flex items-center justify-between mb-2">
                      <button
                        type="button"
                        onClick={goToPrevMonth}
                        className="p-1 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
                        aria-label="Previous month"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <div className="text-xs font-medium text-gray-200">
                        {calendarMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' })}
                      </div>
                      <button
                        type="button"
                        onClick={goToNextMonth}
                        className="p-1 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
                        aria-label="Next month"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                    <div className="grid grid-cols-7 gap-1 text-[10px] text-center text-gray-500 mb-1">
                      {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d) => (
                        <div key={d}>{d}</div>
                      ))}
                    </div>
                    <div className="grid grid-cols-7 gap-1 text-xs">
                      {Array.from({ length: startWeekday }).map((_, idx) => (
                        <div key={`blank-${idx}`} />
                      ))}
                      {Array.from({ length: daysInMonth }).map((_, idx) => {
                        const day = idx + 1;
                        const dateStr = formatDate(calendarYear, calendarMonthIndex, day);
                        const hasDigest = digestDateSet.has(dateStr);
                        const count = digestCountByDate[dateStr] ?? 0;
                        const isSelected = selectedDigestDate === dateStr;
                        const baseClasses =
                          'h-7 flex items-center justify-center rounded cursor-pointer border text-xs';
                        const variant = hasDigest
                          ? isSelected
                            ? 'bg-emerald-600 border-emerald-500 text-white'
                            : 'bg-emerald-900/40 border-emerald-600/60 text-emerald-100 hover:bg-emerald-700/70'
                          : 'bg-gray-900 border-gray-800 text-gray-500';
                        return (
                          <button
                            key={dateStr}
                            type="button"
                            className={`${baseClasses} ${variant}`}
                            disabled={!hasDigest}
                            onClick={() => hasDigest && handleSelectDigestDate(dateStr)}
                            title={
                              hasDigest
                                ? `${count} brief${count !== 1 ? 's' : ''} on ${dateStr}`
                                : 'No brief for this day'
                            }
                          >
                            {day}
                            {hasDigest && count > 1 && (
                              <span className="ml-0.5 text-[10px] opacity-90">x{count}</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                    <p className="mt-2 text-[10px] text-gray-500">
                      Green days have saved briefs; number is how many that day. Click a day to view.
                    </p>
                    {selectedDigestDate && digestBriefsForDay.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-700">
                        <p className="text-[10px] font-medium text-gray-500 mb-1.5">Briefs on this day</p>
                        <div className="flex flex-wrap gap-1.5">
                          {digestBriefsForDay.map((brief, i) => (
                            <button
                              key={brief.execution_id}
                              type="button"
                              onClick={() => setSelectedBrief(brief)}
                              className={`px-2 py-1 text-xs rounded border transition-colors ${
                                selectedBrief?.execution_id === brief.execution_id
                                  ? 'bg-emerald-600 border-emerald-500 text-white'
                                  : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                              }`}
                              title={brief.created_at}
                            >
                              {formatBriefTime(brief.created_at) || `Brief ${i + 1}`}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Digest content */}
              <div className="space-y-3">
                  {digestLoading && (
                    <div className="flex items-center gap-2 text-xs text-gray-300">
                      <span className="inline-block w-4 h-4 border-2 border-gray-500 border-t-blue-400 rounded-full animate-spin" />
                      <span>Loading briefs…</span>
                    </div>
                  )}

                  {digestError && <p className="text-xs text-red-400">{digestError}</p>}

                  {/* Selected day brief content (hours list is in Brief history panel) */}
                  {!digestLoading && selectedDigestDate && digestBriefsForDay.length > 0 && selectedBrief && (
                    <>
                        <div className="space-y-3 pt-2 border-top border-gray-700">
                          <div className="flex items-start justify-between gap-3">
                            <div className="space-y-1">
                              <p className="text-xs text-gray-500">
                                {selectedBrief.digest_date}
                                {selectedBrief.created_at && (
                                  <span className="ml-2">· {formatBriefTime(selectedBrief.created_at)}</span>
                                )}
                              </p>
                              {selectedBrief.priority_tickers?.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="text-[10px] uppercase tracking-wide text-gray-500">Focus</span>
                                  {selectedBrief.priority_tickers.map((t) => (
                                    <span
                                      key={t}
                                      className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-900/40 border border-emerald-600/60 text-[11px] text-emerald-100"
                                    >
                                      {t}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {(selectedBrief.user_note ||
                                selectedBrief.narrative_style ||
                                selectedBrief.user_focus_tickers?.length) && (
                                  <div className="mt-2 space-y-1 text-[11px] text-gray-300 bg-gray-900/60 border border-gray-700 rounded px-2 py-1.5">
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                                      Run inputs
                                    </p>
                                    {selectedBrief.narrative_style && (
                                      <p>
                                        <span className="uppercase tracking-wide text-gray-500 mr-1">Style:</span>
                                        {selectedBrief.narrative_style}
                                      </p>
                                    )}
                                    {selectedBrief.user_focus_tickers?.length ? (
                                      <p>
                                        <span className="uppercase tracking-wide text-gray-500 mr-1">User focus:</span>
                                        {selectedBrief.user_focus_tickers.join(', ')}
                                      </p>
                                    ) : null}
                                    {selectedBrief.user_note && (
                                      <p className="text-[11px] text-gray-300">
                                        <span className="uppercase tracking-wide text-gray-500 mr-1">User note:</span>
                                        <span className="whitespace-pre-wrap align-top">{selectedBrief.user_note}</span>
                                      </p>
                                    )}
                                  </div>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handleCopyBrief(selectedBrief)}
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-emerald-500 text-emerald-300 hover:bg-emerald-600/10"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                                  />
                                </svg>
                                Copy brief
                              </button>
                              <button
                                type="button"
                                onClick={() => setShowRawDigest((v) => !v)}
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-gray-500 text-gray-300 hover:bg-gray-800/80"
                              >
                                {showRawDigest ? 'Hide raw' : 'Show raw'}
                              </button>
                            </div>
                          </div>
                          <div className="prose prose-invert prose-sm max-w-none">
                            <p className="text-gray-200 whitespace-pre-wrap leading-relaxed">{selectedBrief.narrative}</p>
                          </div>
                          {showRawDigest && (
                            <div className="mt-2 rounded border border-gray-700 bg-black/50 p-2">
                              <pre className="text-[11px] whitespace-pre-wrap text-gray-200">
                                {formatBriefRaw(selectedBrief)}
                              </pre>
                            </div>
                          )}
                          {selectedBrief.what_to_watch && (
                            <div className="pt-3 border-t border-gray-700 space-y-2">
                              <div>
                                <h3 className="text-sm font-semibold text-emerald-300 mb-1">What to watch</h3>
                                <p className="text-gray-200 text-sm whitespace-pre-wrap leading-relaxed">
                                  {selectedBrief.what_to_watch}
                                </p>
                              </div>
                            </div>
                          )}
                          {selectedBrief.references && selectedBrief.references.length > 0 && (
                            <div className="pt-3 border-t border-gray-700">
                              <button
                                type="button"
                                onClick={() => setShowReferences((v) => !v)}
                                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-300 hover:text-white"
                              >
                                <svg
                                  className={`w-3 h-3 transition-transform ${
                                    showReferences ? 'rotate-90 text-emerald-300' : 'text-gray-400'
                                  }`}
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                <span>References</span>
                                <span className="text-[10px] text-gray-500">({selectedBrief.references.length})</span>
                              </button>
                              {showReferences && (
                                <ul className="mt-1.5 space-y-1.5 text-[11px] text-gray-300">
                                  {selectedBrief.references.map((ref, idx) => (
                                    <li key={idx} className="flex flex-col">
                                      <span className="font-medium">{ref.label}</span>
                                      <div className="flex flex-wrap gap-2 text-[10px] text-gray-500">
                                        {ref.source && <span>{ref.source}</span>}
                                        {ref.url && (
                                          <a
                                            href={ref.url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="underline underline-offset-2 text-emerald-300 hover:text-emerald-200"
                                          >
                                            Link
                                          </a>
                                        )}
                                        {ref.tickers && ref.tickers.length > 0 && (
                                          <span>Tickers: {ref.tickers.join(', ')}</span>
                                        )}
                                      </div>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                        </div>
                    </>
                  )}

                  {/* Freshly run digest (no history selected) */}
                  {!digestLoading && digest && !selectedDigestDate && (
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-xs text-gray-500">{digest.digest_date}</p>
                          {digest.priority_tickers?.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-[10px] uppercase tracking-wide text-gray-500">Focus</span>
                              {digest.priority_tickers.map((t) => (
                                <span
                                  key={t}
                                  className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-900/40 border border-emerald-600/60 text-[11px] text-emerald-100"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}
                          {(digest.user_note || digest.narrative_style || digest.user_focus_tickers?.length) && (
                            <div className="mt-2 space-y-1 text-[11px] text-gray-300 bg-gray-900/60 border border-gray-700 rounded px-2 py-1.5">
                              <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                                Run inputs
                              </p>
                              {digest.narrative_style && (
                                <p>
                                  <span className="uppercase tracking-wide text-gray-500 mr-1">Style:</span>
                                  {digest.narrative_style}
                                </p>
                              )}
                              {digest.user_focus_tickers?.length ? (
                                <p>
                                  <span className="uppercase tracking-wide text-gray-500 mr-1">User focus:</span>
                                  {digest.user_focus_tickers.join(', ')}
                                </p>
                              ) : null}
                              {digest.user_note && (
                                <p className="text-[11px] text-gray-300">
                                  <span className="uppercase tracking-wide text-gray-500 mr-1">User note:</span>
                                  <span className="whitespace-pre-wrap align-top">{digest.user_note}</span>
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleCopyBrief(digest)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-emerald-500 text-emerald-300 hover:bg-emerald-600/10"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                              />
                            </svg>
                            Copy brief
                          </button>
                          <button
                            type="button"
                            onClick={() => setShowRawDigest((v) => !v)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-gray-500 text-gray-300 hover:bg-gray-800/80"
                          >
                            {showRawDigest ? 'Hide raw' : 'Show raw'}
                          </button>
                        </div>
                      </div>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <p className="text-gray-200 whitespace-pre-wrap leading-relaxed">{digest.narrative}</p>
                      </div>
                      {showRawDigest && (
                        <div className="mt-2 rounded border border-gray-700 bg-black/50 p-2">
                          <pre className="text-[11px] whitespace-pre-wrap text-gray-200">
                            {formatBriefRaw(digest)}
                          </pre>
                        </div>
                      )}
                      {digest.what_to_watch && (
                        <div className="pt-3 border-t border-gray-700 space-y-2">
                          <div>
                            <h3 className="text-sm font-semibold text-emerald-300 mb-1">What to watch</h3>
                            <p className="text-gray-200 text-sm whitespace-pre-wrap leading-relaxed">
                              {digest.what_to_watch}
                            </p>
                          </div>
                          {digest.references && digest.references.length > 0 && (
                            <div className="pt-2 border-t border-gray-800">
                              <button
                                type="button"
                                onClick={() => setShowReferences((v) => !v)}
                                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-300 hover:text-white"
                              >
                                <svg
                                  className={`w-3 h-3 transition-transform ${
                                    showReferences ? 'rotate-90 text-emerald-300' : 'text-gray-400'
                                  }`}
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                <span>References</span>
                                <span className="text-[10px] text-gray-500">({digest.references.length})</span>
                              </button>
                              {showReferences && (
                                <ul className="mt-1.5 space-y-1.5 text-[11px] text-gray-300">
                                  {digest.references.map((ref, idx) => (
                                    <li key={idx} className="flex flex-col">
                                      <span className="font-medium">{ref.label}</span>
                                      <div className="flex flex-wrap gap-2 text-[10px] text-gray-500">
                                        {ref.source && <span>{ref.source}</span>}
                                        {ref.url && (
                                          <a
                                            href={ref.url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="underline underline-offset-2 text-emerald-300 hover:text-emerald-200"
                                          >
                                            Link
                                          </a>
                                        )}
                                        {ref.tickers && ref.tickers.length > 0 && (
                                          <span>Tickers: {ref.tickers.join(', ')}</span>
                                        )}
                                      </div>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Empty state */}
                  {!digestLoading &&
                    !digestError &&
                    !digest &&
                    (!selectedDigestDate || digestBriefsForDay.length === 0) && (
                      <p className="text-xs text-gray-400">
                        Click &ldquo;Run digest&rdquo; to generate today&apos;s summary, or select a highlighted day in
                        the calendar to view that day&apos;s briefs.
                      </p>
                    )}
                </div>
              </div>
            </div>
          </div>
      )}

    </div>
  );
}

// Made with Bob
