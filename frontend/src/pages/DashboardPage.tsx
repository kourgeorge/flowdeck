import { useEffect, useState, useCallback, type ComponentProps } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import TickerSearch from '../components/TickerSearch';
import DashboardTopTiles from '../components/DashboardTopTiles';
import PageHeader from '../components/PageHeader';
import TickerListView from '../components/StockListView';
import DashboardNewsSection from '../components/DashboardNewsSection';
import DashboardPriceTrendsChart from '../components/DashboardPriceTrendsChart';
import DailyDigestRunPanel from '../components/DailyDigestRunPanel';
import OverviewStatsPanel, { ByMarketSection, SubscribedChangeColumnsChart } from '../components/OverviewStatsPanel';
import { useDashboardData } from '../hooks/useDashboardData';
import { useAuth } from '../contexts/AuthContext';
import ReactMarkdown from 'react-markdown';
import { digestApi, type DigestResponse, type DigestBriefItem } from '../services/api';

/** Special tokens used in technical-style briefs for formatting by section. */
const BRIEF_SECTION_TOKENS = ['market_highlights', 'key_signals', 'what_to_watch', 'risks_opportunities'];

/** True if the brief narrative already uses the 4-section format (Market Highlights, Key Signals, What to Watch, Risks & Opportunities). */
function briefHasStructuredSections(narrative: string): boolean {
    return /##\s*(Market Highlights|What to Watch|Risks\s*&\s*Opportunities)/i.test(narrative);
}

/** Remove standalone special-token lines from narrative for display (tokens stay in stored narrative for parsing). */
function narrativeForDisplay(narrative: string): string {
    if (!briefHasStructuredSections(narrative)) return narrative;
    const tokenSet = new Set(BRIEF_SECTION_TOKENS);
    return narrative
        .split('\n')
        .filter((line) => !tokenSet.has(line.trim()))
        .join('\n');
}

/** ReactMarkdown components so brief section titles (##) use the same green as "What to watch". */
const briefMarkdownComponents = {
    h2: ({ children, ...props }: ComponentProps<'h2'>) => (
        <h2 className="text-sm font-semibold text-emerald-300 mb-1 mt-4 first:mt-0" {...props}>{children}</h2>
    ),
};

type DashboardTab = 'overview' | 'portfolio' | 'news' | 'digest';
type StockListTab = 'subscribed' | 'recent';

const DASHBOARD_TAB_IDS: DashboardTab[] = ['overview', 'portfolio', 'news', 'digest'];
const STOCK_LIST_TAB_IDS: StockListTab[] = ['subscribed', 'recent'];

export default function DashboardPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [dashboardTab, setDashboardTab] = useState<DashboardTab>('overview');
  const [stockListTab, setStockListTab] = useState<StockListTab>('subscribed');
  const shouldLoadRecentAnalyzed = dashboardTab === 'overview' && stockListTab === 'recent';

  // Sync URL -> tab state (reload / back restores tab)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    const listParam = searchParams.get('list');
    if (tabParam && DASHBOARD_TAB_IDS.includes(tabParam as DashboardTab)) {
      setDashboardTab(tabParam as DashboardTab);
    }
    if (listParam && STOCK_LIST_TAB_IDS.includes(listParam as StockListTab)) {
      setStockListTab(listParam as StockListTab);
    }
  }, [searchParams]);

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
  const [digestSpan, setDigestSpan] = useState<'daily' | 'weekly'>('daily');
  const [selectedFocusTickers, setSelectedFocusTickers] = useState<string[]>([]);
  const [showReferences, setShowReferences] = useState<boolean>(false);
  const [showRawDigest, setShowRawDigest] = useState<boolean>(false);
  const [digestInputExpanded, setDigestInputExpanded] = useState<boolean>(false);
  const [shareLinkCopied, setShareLinkCopied] = useState<boolean>(false);
  const [copyBriefCopied, setCopyBriefCopied] = useState<boolean>(false);
  const [newBriefModalOpen, setNewBriefModalOpen] = useState<boolean>(false);
  const [hasBriefForToday, setHasBriefForToday] = useState<boolean | null>(null);
  const [briefPromptDismissed, setBriefPromptDismissed] = useState<boolean>(() => {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem('flowdeck_brief_prompt_dismissed') === 'true';
    }
    return false;
  });

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

  const handleDashboardTabChange = useCallback((tab: DashboardTab) => {
    setDashboardTab(tab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', tab);
      if (tab !== 'overview') next.delete('list');
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  const handleStockListTabChange = useCallback((list: StockListTab) => {
    setStockListTab(list);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', 'overview');
      next.set('list', list);
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  const handleRunDigest = async () => {
    setDigestError(null);
    setDigest(null);
    setDigestLoading(true);
    try {
      const trimmedNote = digestUserNote.trim();
      const styleParam = digestNarrativeStyle === 'default' ? undefined : digestNarrativeStyle;
      const params: { span?: 'daily' | 'weekly'; user_note?: string; narrative_style?: string; user_focus_tickers?: string[] } = {};
      if (digestSpan !== 'daily') params.span = digestSpan;
      if (trimmedNote) params.user_note = trimmedNote;
      if (styleParam) params.narrative_style = styleParam;
      if (selectedFocusTickers.length > 0) params.user_focus_tickers = selectedFocusTickers;
      const data = await digestApi.getDigest(
        Object.keys(params).length ? params : undefined,
      );
      setDigest(data);
      const slot = (data.span_type === 'weekly' ? `w:${data.digest_date}` : data.digest_date);
      setSelectedDigestDate(slot);
      setDigestDates((prev) =>
        prev.includes(slot) ? prev : [...prev, slot].sort()
      );
      setDigestCountByDate((prev) => ({
        ...prev,
        [slot]: (prev[slot] ?? 0) + 1,
      }));
      const today = new Date();
      const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      if (data.digest_date === todayStr) setHasBriefForToday(true);
      if (trimmedNote) {
        setDigestUserNote('');
      }
      const listRes = await digestApi.getDigestsForDate(slot);
      setDigestBriefsForDay(listRes.briefs);
      setSelectedBrief(listRes.briefs[0] ?? null);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
    } finally {
      setDigestLoading(false);
    }
  };

  // On Overview: check if user has a brief for today (for "no brief today" card)
  useEffect(() => {
    if (dashboardTab !== 'overview' || !user) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await digestApi.getDigestDates(7);
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
    return () => { cancelled = true; };
  }, [dashboardTab, user]);

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
          const latestSlot = dates[dates.length - 1];
          setSelectedDigestDate(latestSlot);
          setDigest(null);
          setDigestLoading(true);
          try {
            const listRes = await digestApi.getDigestsForDate(latestSlot);
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

  const formatDate = (y: number, mZeroBased: number, d: number) => {
    const m = mZeroBased + 1;
    const mm = m < 10 ? `0${m}` : String(m);
    const dd = d < 10 ? `0${d}` : String(d);
    return `${y}-${mm}-${dd}`;
  };

  const dailyDigestDates = digestDates.filter((d) => !d.startsWith('w:'));
  const weeklyDigestSlots = digestDates.filter((d) => d.startsWith('w:'));
  const digestDateSet = new Set(dailyDigestDates);

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
    if (brief.what_to_watch && !briefHasStructuredSections(brief.narrative)) {
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

  const handleDeleteBrief = async () => {
    if (!selectedBrief || !selectedDigestDate) return;
    if (!window.confirm('Delete this brief? This cannot be undone.')) return;
    setDigestError(null);
    try {
      await digestApi.deleteBrief(selectedBrief.execution_id);
      const listRes = await digestApi.getDigestsForDate(selectedDigestDate);
      setDigestBriefsForDay(listRes.briefs);
      setSelectedBrief(listRes.briefs[0] ?? null);
      const datesRes = await digestApi.getDigestDates(90);
      setDigestDates(datesRes.dates);
      setDigestCountByDate(datesRes.count_by_date);
      if (listRes.briefs.length === 0) {
        setSelectedDigestDate(null);
      }
      const today = new Date();
      const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      if (selectedBrief.digest_date === todayStr && listRes.briefs.length === 0) {
        setHasBriefForToday(false);
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
    }
  };

  const handleCopyBrief = (brief: DigestResponse | DigestBriefItem) => {
    const text = formatBriefForClipboard(brief);
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopyBriefCopied(true);
        setTimeout(() => setCopyBriefCopied(false), 2000);
      }).catch(() => {});
    }
  };

  const handleCopyShareLink = (shareUrl: string) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(shareUrl);
      setShareLinkCopied(true);
      setTimeout(() => setShareLinkCopied(false), 2000);
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
                { id: 'news', label: 'News' },
                { id: 'digest', label: 'User Daily Brief' },
              ] as { id: DashboardTab; label: string }[]).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleDashboardTabChange(tab.id)}
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

              {/* No brief for today — prompt card (only when not dismissed) */}
              {user && dashboardTab === 'overview' && !briefPromptDismissed && hasBriefForToday === false && (
                <div className="mb-6 bg-gray-800 rounded-lg border border-gray-700 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-white mb-0.5">No brief for today yet.</p>
                    <p className="text-xs text-gray-400">
                      Get a short narrative summary of today&apos;s market and your portfolio.
                    </p>
                  </div>
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                    <button
                      type="button"
                      onClick={() => handleDashboardTabChange('digest')}
                      className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-gray-900"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Generate today&apos;s brief
                    </button>
                    <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer sm:whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={briefPromptDismissed}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setBriefPromptDismissed(checked);
                          try {
                            if (checked) localStorage.setItem('flowdeck_brief_prompt_dismissed', 'true');
                            else localStorage.removeItem('flowdeck_brief_prompt_dismissed');
                          } catch {}
                        }}
                        className="rounded border-gray-600 bg-gray-900 text-emerald-600 focus:ring-emerald-500"
                      />
                      Don&apos;t show this again
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
              /* Combined stock list widget — full width */
              <div>
                {/* Tab header */}
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

      {/* ── Digest Tab: calendar view — left: current month + generation panel; right: brief ── */}
      {dashboardTab === 'digest' && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="px-4 py-6 sm:p-6 lg:p-8">
            <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
              <div className="flex flex-col lg:flex-row gap-6">
                {/* Left: calendar panel (with New brief integrated) */}
                <div className="lg:w-72 xl:w-80 shrink-0">
                  <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                    {/* Top bar: New brief action integrated into panel */}
                    <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-gray-700/80">
                      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Briefs</span>
                      <button
                        type="button"
                        onClick={() => setNewBriefModalOpen(true)}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-emerald-300 hover:text-white hover:bg-emerald-600/20 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                        title="Create new brief"
                        aria-label="Create new brief"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        <span>New</span>
                      </button>
                    </div>

                    {/* Month + grid */}
                    <div className="p-4 pt-3">
                    <div className="flex items-center justify-between mb-3">
                      <button
                        type="button"
                        onClick={goToPrevMonth}
                        className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
                        aria-label="Previous month"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <span className="text-sm font-semibold text-white">
                        {calendarMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' })}
                      </span>
                      <button
                        type="button"
                        onClick={goToNextMonth}
                        className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
                        aria-label="Next month"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                    <div className="grid grid-cols-7 gap-0.5 text-xs text-center text-gray-500 mb-1">
                      {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d) => (
                        <div key={d}>{d}</div>
                      ))}
                    </div>
                    <div className="grid grid-cols-7 gap-0.5 text-xs">
                      {(() => {
                        const year = calendarMonth.getFullYear();
                        const monthIndex = calendarMonth.getMonth();
                        const firstOfMonth = new Date(year, monthIndex, 1);
                        const startWeekday = firstOfMonth.getDay();
                        const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
                        return (
                          <>
                            {Array.from({ length: startWeekday }).map((_, idx) => (
                              <div key={`b-${idx}`} />
                            ))}
                            {Array.from({ length: daysInMonth }).map((_, idx) => {
                              const day = idx + 1;
                              const dateStr = formatDate(year, monthIndex, day);
                              const hasDigest = digestDateSet.has(dateStr);
                              const count = digestCountByDate[dateStr] ?? 0;
                              const isSelected = selectedDigestDate === dateStr;
                              const baseClasses =
                                'h-8 relative flex items-center justify-center rounded cursor-pointer border text-xs';
                              const variant = hasDigest
                                ? isSelected
                                  ? 'bg-emerald-600 border-emerald-500 text-white'
                                  : 'bg-emerald-900/40 border-emerald-600/60 text-emerald-100 hover:bg-emerald-700/70'
                                : 'bg-gray-900 border-gray-800 text-gray-500';
                              return (
                                <button
                                  key={dateStr}
                                  type="button"
                                  className={`${baseClasses} ${variant} min-w-0`}
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
                                    <span className="absolute bottom-0 right-0.5 text-[9px] leading-none opacity-80">×{count}</span>
                                  )}
                                </button>
                              );
                            })}
                          </>
                        );
                      })()}
                    </div>
                    <p className="mt-2 text-xs text-gray-500">
                      Green = briefs. Click a day to view.
                    </p>
                    {weeklyDigestSlots.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-700">
                        <p className="text-xs font-medium text-gray-500 mb-1.5">Weekly briefs</p>
                        <div className="flex flex-wrap gap-1">
                          {weeklyDigestSlots.map((slot) => {
                            const endDate = slot.startsWith('w:') ? slot.slice(2) : slot;
                            const isSelected = selectedDigestDate === slot;
                            return (
                              <button
                                key={slot}
                                type="button"
                                onClick={() => handleSelectDigestDate(slot)}
className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                                isSelected
                                    ? 'bg-emerald-600 border-emerald-500 text-white'
                                    : 'bg-gray-900 border-gray-600 text-gray-300 hover:bg-gray-700'
                                }`}
                                title={endDate}
                              >
                                Week {endDate}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {selectedDigestDate && digestBriefsForDay.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-700">
                        <p className="text-xs font-medium text-gray-500 mb-1.5">
                          {selectedDigestDate.startsWith('w:') ? 'This week' : 'This day'}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {digestBriefsForDay.map((brief, i) => (
                            <button
                              key={brief.execution_id}
                              type="button"
                              onClick={() => setSelectedBrief(brief)}
                              className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                                selectedBrief?.execution_id === brief.execution_id
                                  ? 'bg-emerald-600 border-emerald-500 text-white'
                                  : 'bg-gray-900 border-gray-600 text-gray-300 hover:bg-gray-700'
                              }`}
                              title={brief.created_at}
                            >
                              {formatBriefTime(brief.created_at) || `#${i + 1}`}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    </div>
                  </div>
                </div>

                {/* New brief modal (create new email style) */}
                {newBriefModalOpen && (
                  <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
                    onClick={() => setNewBriefModalOpen(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="new-brief-modal-title"
                  >
                    <div
                      className="bg-gray-800 border border-gray-700 rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="sticky top-0 flex justify-between items-center px-4 py-3 border-b border-gray-700 bg-gray-800 z-10">
                        <h2 id="new-brief-modal-title" className="text-base font-semibold text-white">
                          Create new brief
                        </h2>
                        <button
                          type="button"
                          onClick={() => setNewBriefModalOpen(false)}
                          className="p-1.5 text-gray-400 hover:text-white rounded-lg transition-colors"
                          aria-label="Close"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                      <div className="p-4">
                        <DailyDigestRunPanel
                          digestUserNote={digestUserNote}
                          onDigestUserNoteChange={setDigestUserNote}
                          digestNarrativeStyle={digestNarrativeStyle}
                          onDigestNarrativeStyleChange={setDigestNarrativeStyle}
                          digestSpan={digestSpan}
                          onDigestSpanChange={setDigestSpan}
                          digestInputExpanded={digestInputExpanded}
                          onDigestInputExpandedChange={setDigestInputExpanded}
                          selectedFocusTickers={selectedFocusTickers}
                          onSelectedFocusTickersChange={setSelectedFocusTickers}
                          subscribedTickers={subscribedTickers}
                          onRunDigest={() => {
                            handleRunDigest();
                            setNewBriefModalOpen(false);
                          }}
                          digestLoading={digestLoading}
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Right: brief content */}
                <div className="flex-1 min-w-0 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                  <div className="bg-gray-900/40 min-h-[200px] px-4 sm:px-6 pt-2 sm:pt-3 pb-4 sm:pb-6 space-y-3">
                  {digestLoading && (
                    <div className="flex flex-col items-center justify-center min-h-[280px] py-12 px-4">
                      <div className="relative">
                        <div className="w-16 h-16 rounded-2xl border-2 border-emerald-500/30 bg-emerald-950/30 flex items-center justify-center">
                          <svg className="w-8 h-8 text-emerald-400/80 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <span className="absolute -inset-1 rounded-2xl border border-emerald-400/20 animate-ping opacity-30" aria-hidden />
                      </div>
                      <p className="mt-5 text-base font-semibold text-white">Generating your brief</p>
                      <p className="mt-1 text-sm text-gray-400">Analyzing market and portfolio…</p>
                      <div className="mt-6 w-48 h-1 rounded-full bg-gray-700 overflow-hidden">
                        <div className="h-full w-1/2 rounded-full bg-emerald-500 [animation:briefShimmer_1.8s_ease-in-out_infinite]" />
                      </div>
                      <style>{`@keyframes briefShimmer { 0%, 100% { transform: translateX(-100%); } 50% { transform: translateX(200%); } }`}</style>
                    </div>
                  )}

                  {digestError && <p className="text-sm text-red-400">{digestError}</p>}

                  {/* Selected day brief content (hours list is in Brief history panel) */}
                  {!digestLoading && selectedDigestDate && digestBriefsForDay.length > 0 && selectedBrief && (
                    <>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between gap-2 flex-nowrap">
                            <span className="text-sm text-gray-500 whitespace-nowrap shrink-0">
                              {selectedBrief.span_label && selectedBrief.span_label !== 'Daily' && (
                                <span className="mr-1.5">{selectedBrief.span_label}</span>
                              )}
                              {selectedBrief.digest_date}
                              {selectedBrief.created_at && (
                                <span className="ml-1.5">· {formatBriefTime(selectedBrief.created_at)}</span>
                              )}
                            </span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                type="button"
                                onClick={() => handleCopyBrief(selectedBrief)}
                                className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${copyBriefCopied ? 'border-green-500/70 text-green-400' : 'border-gray-500 text-gray-300'}`}
                                title={copyBriefCopied ? 'Copied!' : 'Copy brief'}
                                aria-label="Copy brief"
                              >
                                {copyBriefCopied ? (
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                  </svg>
                                ) : (
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                  </svg>
                                )}
                              </button>
                              {selectedBrief.share_url && (
                                <button
                                  type="button"
                                  onClick={() => handleCopyShareLink(selectedBrief.share_url!)}
                                  className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${shareLinkCopied ? 'border-green-500/70 text-green-400' : 'border-gray-500 text-gray-300'}`}
                                  title={shareLinkCopied ? 'Link copied!' : 'Copy share link'}
                                  aria-label="Copy share link"
                                >
                                  {shareLinkCopied ? (
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                    </svg>
                                  ) : (
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                                    </svg>
                                  )}
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => setShowRawDigest((v) => !v)}
                                className="inline-flex items-center justify-center p-1.5 rounded border border-gray-500 text-gray-300 hover:bg-gray-800/80"
                                title={showRawDigest ? 'Hide raw' : 'Show raw'}
                                aria-label={showRawDigest ? 'Hide raw' : 'Show raw'}
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                                </svg>
                              </button>
                              <button
                                type="button"
                                onClick={handleDeleteBrief}
                                className="inline-flex items-center justify-center p-1.5 rounded border border-red-500/70 text-red-300 hover:bg-red-600/20"
                                title="Delete this brief"
                                aria-label="Delete this brief"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                          </div>
                          {(selectedBrief.user_note ||
                            selectedBrief.narrative_style ||
                            selectedBrief.user_focus_tickers?.length) && (
                              <div className="space-y-1 text-sm text-gray-300 bg-gray-900/60 border border-gray-700 rounded px-3 py-2">
                                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Run inputs</p>
                                {selectedBrief.narrative_style && (
                                  <p><span className="text-gray-500 mr-1">Style:</span>{selectedBrief.narrative_style}</p>
                                )}
                                {selectedBrief.user_focus_tickers?.length ? (
                                  <p><span className="text-gray-500 mr-1">User focus:</span>{selectedBrief.user_focus_tickers.join(', ')}</p>
                                ) : null}
                                {selectedBrief.user_note && (
                                  <p><span className="text-gray-500 mr-1">User note:</span><span className="whitespace-pre-wrap align-top">{selectedBrief.user_note}</span></p>
                                )}
                              </div>
                            )}
                          {selectedBrief.priority_tickers?.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-xs uppercase tracking-wide text-gray-500">Focus</span>
                              {selectedBrief.priority_tickers.map((t) => (
                                <span
                                  key={t}
                                  className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-900/40 border border-emerald-600/60 text-sm text-emerald-100"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="prose prose-invert prose-sm max-w-none text-gray-200">
                            {briefHasStructuredSections(selectedBrief.narrative) ? (
                              <ReactMarkdown components={briefMarkdownComponents}>{narrativeForDisplay(selectedBrief.narrative)}</ReactMarkdown>
                            ) : (
                              <p className="whitespace-pre-wrap leading-relaxed">{selectedBrief.narrative}</p>
                            )}
                          </div>
                          {showRawDigest && (
                            <div className="mt-2 rounded border border-gray-700 bg-black/50 p-2">
                              <pre className="text-xs whitespace-pre-wrap text-gray-200">
                                {formatBriefRaw(selectedBrief)}
                              </pre>
                            </div>
                          )}
                          {selectedBrief.what_to_watch && !briefHasStructuredSections(selectedBrief.narrative) && (
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
                                className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-300 hover:text-white"
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
                                <span className="text-xs text-gray-500">({selectedBrief.references.length})</span>
                              </button>
                              {showReferences && (
                                <ul className="mt-1.5 space-y-1.5 text-sm text-gray-300">
                                  {selectedBrief.references.map((ref, idx) => (
                                    <li key={idx} className="flex flex-col">
                                      <span className="font-medium">{ref.label}</span>
                                      <div className="flex flex-wrap gap-2 text-xs text-gray-500">
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

                  {/* Freshly run digest (shown when no list/selection yet, e.g. right after run or list fetch failed) */}
                  {!digestLoading && digest && (!selectedDigestDate || digestBriefsForDay.length === 0) && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-2 flex-nowrap">
                        <span className="text-sm text-gray-500 whitespace-nowrap shrink-0">
                          {digest.span_label && digest.span_label !== 'Daily' && (
                            <span className="mr-1.5">{digest.span_label}</span>
                          )}
                          {digest.digest_date}
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleCopyBrief(digest)}
                            className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${copyBriefCopied ? 'border-green-500/70 text-green-400' : 'border-gray-500 text-gray-300'}`}
                            title={copyBriefCopied ? 'Copied!' : 'Copy brief'}
                            aria-label="Copy brief"
                          >
                            {copyBriefCopied ? (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                              </svg>
                            ) : (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                            )}
                          </button>
                          {digest.share_url && (
                            <button
                              type="button"
                              onClick={() => handleCopyShareLink(digest.share_url!)}
                              className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${shareLinkCopied ? 'border-green-500/70 text-green-400' : 'border-gray-500 text-gray-300'}`}
                              title={shareLinkCopied ? 'Link copied!' : 'Copy share link'}
                              aria-label="Copy share link"
                            >
                              {shareLinkCopied ? (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                                </svg>
                              )}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setShowRawDigest((v) => !v)}
                            className="inline-flex items-center justify-center p-1.5 rounded border border-gray-500 text-gray-300 hover:bg-gray-800/80"
                            title={showRawDigest ? 'Hide raw' : 'Show raw'}
                            aria-label={showRawDigest ? 'Hide raw' : 'Show raw'}
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                            </svg>
                          </button>
                        </div>
                      </div>
                      {(digest.user_note || digest.narrative_style || digest.user_focus_tickers?.length) && (
                        <div className="space-y-1 text-sm text-gray-300 bg-gray-900/60 border border-gray-700 rounded px-3 py-2">
                          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Run inputs</p>
                          {digest.narrative_style && (
                            <p><span className="text-gray-500 mr-1">Style:</span>{digest.narrative_style}</p>
                          )}
                          {digest.user_focus_tickers?.length ? (
                            <p><span className="text-gray-500 mr-1">User focus:</span>{digest.user_focus_tickers.join(', ')}</p>
                          ) : null}
                          {digest.user_note && (
                            <p><span className="text-gray-500 mr-1">User note:</span><span className="whitespace-pre-wrap align-top">{digest.user_note}</span></p>
                          )}
                        </div>
                      )}
                      {digest.priority_tickers?.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs uppercase tracking-wide text-gray-500">Focus</span>
                          {digest.priority_tickers.map((t) => (
                            <span
                              key={t}
                              className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-900/40 border border-emerald-600/60 text-sm text-emerald-100"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="prose prose-invert prose-sm max-w-none text-gray-200">
                        {briefHasStructuredSections(digest.narrative) ? (
                          <ReactMarkdown components={briefMarkdownComponents}>{narrativeForDisplay(digest.narrative)}</ReactMarkdown>
                        ) : (
                          <p className="whitespace-pre-wrap leading-relaxed">{digest.narrative}</p>
                        )}
                      </div>
                      {showRawDigest && (
                        <div className="mt-2 rounded border border-gray-700 bg-black/50 p-2">
                          <pre className="text-xs whitespace-pre-wrap text-gray-200">
                            {formatBriefRaw(digest)}
                          </pre>
                        </div>
                      )}
                      {digest.what_to_watch && !briefHasStructuredSections(digest.narrative) && (
                        <div className="pt-3 border-t border-gray-700 space-y-2">
                          <div>
                            <h3 className="text-sm font-semibold text-emerald-300 mb-1">What to watch</h3>
                            <p className="text-gray-200 text-sm whitespace-pre-wrap leading-relaxed">
                              {digest.what_to_watch}
                            </p>
                          </div>
                        </div>
                      )}
                      {digest.references && digest.references.length > 0 && (
                        <div className="pt-3 border-t border-gray-700">
                          <button
                            type="button"
                            onClick={() => setShowReferences((v) => !v)}
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-300 hover:text-white"
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
                            <span className="text-xs text-gray-500">({digest.references.length})</span>
                          </button>
                          {showReferences && (
                            <ul className="mt-1.5 space-y-1.5 text-sm text-gray-300">
                              {digest.references.map((ref, idx) => (
                                <li key={idx} className="flex flex-col">
                                  <span className="font-medium">{ref.label}</span>
                                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
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

                  {/* Empty state */}
                  {!digestLoading &&
                    !digestError &&
                    !digest &&
                    (!selectedDigestDate || digestBriefsForDay.length === 0) && (
                      <p className="text-sm text-gray-400">
                        Click &ldquo;Run digest&rdquo; to generate today&apos;s summary, or select a highlighted day in
                        the calendar to view that day&apos;s briefs.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

// Made with Bob
