import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import PageHeader from '../components/PageHeader';
import {
  adminApi,
  type AdminStats,
  type AdminUserItem,
  type AdminReportItem,
  type AdminReportDetail,
  type AdminAnalysisItem,
  type AdminSubscriptionItem,
  type AnalysisDailyCount,
  type ViewsDailyCount,
  type AdminReportViewRunItem,
  type AdminReportViewItem,
  type MissionControlTickerItem,
  type RunningAnalysisItem,
} from '../services/adminApi';
import {
  formatDate,
  compareNullableNumber,
  compareNullableString,
  quoteTypeSortRank,
  summarizeMissionRunResult,
} from '../components/admin/adminUtils';
import JsonViewer from '../components/admin/JsonViewer';
import OverviewTab from '../components/admin/OverviewTab';
import MissionControlTab from '../components/admin/MissionControlTab';
import UsersTab from '../components/admin/UsersTab';

type AdminTab = 'overview' | 'mission-control' | 'users';
const ADMIN_TAB_IDS: AdminTab[] = ['overview', 'mission-control', 'users'];
type MissionSortKey = 'ticker' | 'company' | 'type' | 'market_cap' | 'sector' | 'industry' | 'last_completed' | 'reports' | 'status' | 'priority' | 'subscriptions';
type MissionSortDirection = 'asc' | 'desc';
type ViewRunsSortKey = 'ticker' | 'analysis_run_id' | 'unique_views' | 'viewed';
type ViewRunsSortDirection = 'asc' | 'desc';

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [reports, setReports] = useState<AdminReportItem[]>([]);
  const [reportsTotal, setReportsTotal] = useState(0);
  const [selectedReport, setSelectedReport] = useState<AdminReportItem | null>(null);
  const [selectedReportDetail, setSelectedReportDetail] = useState<AdminReportDetail | null>(null);
  const [loadingReportDetail, setLoadingReportDetail] = useState(false);
  const [reportDetailError, setReportDetailError] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<AdminAnalysisItem[]>([]);
  const [analysesTotal, setAnalysesTotal] = useState(0);
  const [analysisTickerFilter, setAnalysisTickerFilter] = useState('');
  const [analysisCreatorFilter, setAnalysisCreatorFilter] = useState('');
  const [loadingMoreAnalyses, setLoadingMoreAnalyses] = useState(false);
  const analysesContainerRef = useRef<HTMLDivElement>(null);
  const [subscriptions, setSubscriptions] = useState<AdminSubscriptionItem[]>([]);
  const [subscriptionsTotal, setSubscriptionsTotal] = useState(0);
  const [viewRuns, setViewRuns] = useState<AdminReportViewRunItem[]>([]);
  const [viewRunsTotal, setViewRunsTotal] = useState(0);
  const [viewsByRun, setViewsByRun] = useState<Record<string, AdminReportViewItem[]>>({});
  const [expandedViewRunKeys, setExpandedViewRunKeys] = useState<Set<string>>(new Set());
  const [loadingRunViewKeys, setLoadingRunViewKeys] = useState<Set<string>>(new Set());
  const [viewRunsSort, setViewRunsSort] = useState<{
    key: ViewRunsSortKey;
    direction: ViewRunsSortDirection;
  }>({
    key: 'analysis_run_id',
    direction: 'desc',
  });
  const [dailyAnalyses, setDailyAnalyses] = useState<AnalysisDailyCount[]>([]);
  const [dailyViews, setDailyViews] = useState<ViewsDailyCount[]>([]);

  const [missionItems, setMissionItems] = useState<MissionControlTickerItem[]>([]);
  const [selectedMissionTickers, setSelectedMissionTickers] = useState<string[]>([]);
  const [missionLoading, setMissionLoading] = useState(false);
  const [runningAnalyses, setRunningAnalyses] = useState<RunningAnalysisItem[]>([]);
  const [runningAnalysesLoading, setRunningAnalysesLoading] = useState(false);
  const [stoppingRunId, setStoppingRunId] = useState<number | null>(null);
  const [missionError, setMissionError] = useState<string | null>(null);
  const [missionActionError, setMissionActionError] = useState<string | null>(null);
  const [missionActionInfo, setMissionActionInfo] = useState<string | null>(null);
  const [missionRunningForTicker, setMissionRunningForTicker] = useState<string | null>(null);
  const [missionBulkRunning, setMissionBulkRunning] = useState(false);
  const [missionForceRerun, setMissionForceRerun] = useState(false);
  const [missionTickerFilter, setMissionTickerFilter] = useState('');
  const [missionSort, setMissionSort] = useState<{
    key: MissionSortKey;
    direction: MissionSortDirection;
  }>({
    key: 'market_cap',
    direction: 'desc',
  });

  const filteredAnalyses = useMemo(
    () =>
      analyses.filter((a) => {
        const tickerOk =
          !analysisTickerFilter ||
          a.ticker.toLowerCase().includes(analysisTickerFilter.trim().toLowerCase());
        const creatorOk =
          !analysisCreatorFilter ||
          a.creator_email.toLowerCase().includes(analysisCreatorFilter.trim().toLowerCase());
        return tickerOk && creatorOk;
      }),
    [analyses, analysisTickerFilter, analysisCreatorFilter],
  );

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addingForUserId, setAddingForUserId] = useState<number | null>(null);
  const [addTokensError, setAddTokensError] = useState<string | null>(null);
  const [addAmountByUser, setAddAmountByUser] = useState<Record<number, string>>({});
  const [latestReportsCollapsed, setLatestReportsCollapsed] = useState(true);
  const [expandedSubscriptionUserIds, setExpandedSubscriptionUserIds] = useState<Set<number>>(new Set());
  const reportDetailsRef = useRef<Record<number, AdminReportDetail>>({});
  const reportDetailRequestRef = useRef(0);

  // Sync URL -> tab state (reload / back restores tab)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && ADMIN_TAB_IDS.includes(tabParam as AdminTab)) {
      setActiveTab(tabParam as AdminTab);
    }
  }, [searchParams]);

  const handleAdminTabChange = useCallback((tab: AdminTab) => {
    setActiveTab(tab);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', tab);
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  const subscriptionsByUser = useMemo(() => {
    const byUser = new Map<number, { user_email: string; subscriptions: AdminSubscriptionItem[] }>();
    for (const s of subscriptions) {
      const existing = byUser.get(s.user_id);
      if (existing) {
        existing.subscriptions.push(s);
      } else {
        byUser.set(s.user_id, { user_email: s.user_email, subscriptions: [s] });
      }
    }
    return [...byUser.entries()]
      .map(([user_id, { user_email, subscriptions: subs }]) => ({ user_id, user_email, subscriptions: subs }))
      .sort((a, b) => a.user_email.localeCompare(b.user_email, undefined, { sensitivity: 'base' }));
  }, [subscriptions]);

  const filteredMissionItems = useMemo(() => {
    const query = missionTickerFilter.trim().toLowerCase();
    if (!query) return missionItems;
    return missionItems.filter((item) => {
      const tickerMatches = item.ticker.toLowerCase().includes(query);
      const companyMatches = String(item.name ?? '').toLowerCase().includes(query);
      return tickerMatches || companyMatches;
    });
  }, [missionItems, missionTickerFilter]);

  const sortedMissionItems = useMemo(
    () =>
      [...filteredMissionItems].sort((a, b) => {
        let cmp = 0;
        switch (missionSort.key) {
          case 'ticker':
            cmp = a.ticker.localeCompare(b.ticker, undefined, { sensitivity: 'base' });
            break;
          case 'company':
            cmp = compareNullableString(a.name, b.name);
            break;
          case 'type': {
            const rankDiff = quoteTypeSortRank(a.quote_type) - quoteTypeSortRank(b.quote_type);
            cmp = rankDiff !== 0 ? rankDiff : compareNullableString(a.quote_type, b.quote_type);
            break;
          }
          case 'market_cap':
            cmp = compareNullableNumber(a.market_cap, b.market_cap);
            break;
          case 'sector':
            cmp = compareNullableString(a.sector, b.sector);
            break;
          case 'industry':
            cmp = compareNullableString(a.industry, b.industry);
            break;
          case 'last_completed': {
            const aTime = a.last_completed_at ? new Date(a.last_completed_at).getTime() : null;
            const bTime = b.last_completed_at ? new Date(b.last_completed_at).getTime() : null;
            cmp = compareNullableNumber(aTime, bTime);
            break;
          }
          case 'reports':
            cmp = compareNullableNumber(a.report_count, b.report_count);
            break;
          case 'status':
            cmp = Number(a.is_running) - Number(b.is_running);
            break;
          case 'priority':
            cmp = (a.priority_score ?? 0) - (b.priority_score ?? 0);
            break;
          case 'subscriptions':
            cmp = (a.subscription_count ?? 0) - (b.subscription_count ?? 0);
            break;
          default:
            cmp = 0;
        }
        if (missionSort.direction === 'desc') cmp *= -1;
        if (cmp !== 0) return cmp;
        return a.ticker.localeCompare(b.ticker);
      }),
    [filteredMissionItems, missionSort],
  );

  const sortedViewRuns = useMemo(
    () =>
      [...viewRuns].sort((a, b) => {
        let cmp = 0;
        switch (viewRunsSort.key) {
          case 'ticker':
            cmp = a.ticker.localeCompare(b.ticker, undefined, { sensitivity: 'base' });
            break;
          case 'analysis_run_id':
            cmp = a.analysis_run_id - b.analysis_run_id;
            break;
          case 'unique_views':
            cmp = a.unique_views - b.unique_views;
            break;
          case 'viewed': {
            const aTime = a.last_viewed_at ? new Date(a.last_viewed_at).getTime() : null;
            const bTime = b.last_viewed_at ? new Date(b.last_viewed_at).getTime() : null;
            cmp = compareNullableNumber(aTime, bTime);
            break;
          }
          default:
            cmp = 0;
        }
        if (viewRunsSort.direction === 'desc') cmp *= -1;
        if (cmp !== 0) return cmp;

        const byRunIdDesc = b.analysis_run_id - a.analysis_run_id;
        if (byRunIdDesc !== 0) return byRunIdDesc;
        return a.ticker.localeCompare(b.ticker, undefined, { sensitivity: 'base' });
      }),
    [viewRuns, viewRunsSort],
  );

  const selectedMissionTickerSet = new Set(selectedMissionTickers);
  const allMissionTickers = sortedMissionItems.map((item) => item.ticker);
  const allMissionSelected =
    sortedMissionItems.length > 0 && allMissionTickers.every((ticker) => selectedMissionTickerSet.has(ticker));

  const toggleMissionSort = (key: MissionSortKey) => {
    setMissionSort((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      const defaultDirection: MissionSortDirection =
        key === 'market_cap' || key === 'last_completed' || key === 'reports' || key === 'status' || key === 'priority' || key === 'subscriptions' ? 'desc' : 'asc';
      return { key, direction: defaultDirection };
    });
  };

  const sortIndicator = (key: MissionSortKey): string =>
    missionSort.key === key ? (missionSort.direction === 'asc' ? '↑' : '↓') : '↕';

  const toggleViewRunsSort = (key: ViewRunsSortKey) => {
    setViewRunsSort((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      const defaultDirection: ViewRunsSortDirection =
        key === 'unique_views' || key === 'viewed' || key === 'analysis_run_id' ? 'desc' : 'asc';
      return { key, direction: defaultDirection };
    });
  };

  const viewRunsSortIndicator = (key: ViewRunsSortKey): string =>
    viewRunsSort.key === key ? (viewRunsSort.direction === 'asc' ? '↑' : '↓') : '↕';

  const getSortedRunViews = (runViews: AdminReportViewItem[]): AdminReportViewItem[] => {
    if (runViews.length <= 1) return runViews;
    const sorted = [...runViews];
    if (viewRunsSort.key === 'viewed') {
      sorted.sort((a, b) => new Date(a.viewed_at).getTime() - new Date(b.viewed_at).getTime());
      if (viewRunsSort.direction === 'desc') sorted.reverse();
      return sorted;
    }
    sorted.sort((a, b) => new Date(b.viewed_at).getTime() - new Date(a.viewed_at).getTime());
    return sorted;
  };

  const loadViewsForRun = async (analysisRunId: number, runKey: string) => {
    if (viewsByRun[runKey] || loadingRunViewKeys.has(runKey)) {
      return;
    }
    setLoadingRunViewKeys((prev) => {
      const next = new Set(prev);
      next.add(runKey);
      return next;
    });
    try {
      const res = await adminApi.getViewsForRun(analysisRunId, 5000, 0);
      setViewsByRun((prev) => ({ ...prev, [runKey]: res.views }));
    } catch {
      setViewsByRun((prev) => ({ ...prev, [runKey]: [] }));
    } finally {
      setLoadingRunViewKeys((prev) => {
        const next = new Set(prev);
        next.delete(runKey);
        return next;
      });
    }
  };

  const toggleRunExpanded = (ticker: string, analysisRunId: number) => {
    const runKey = `${ticker}::${analysisRunId}`;
    const isExpanded = expandedViewRunKeys.has(runKey);
    if (!isExpanded && !viewsByRun[runKey]) {
      void loadViewsForRun(analysisRunId, runKey);
    }
    setExpandedViewRunKeys((prev) => {
      const next = new Set(prev);
      if (next.has(runKey)) {
        next.delete(runKey);
      } else {
        next.add(runKey);
      }
      return next;
    });
  };

  const refreshRunningAnalyses = async () => {
    setRunningAnalysesLoading(true);
    try {
      const list = await adminApi.getRunningAnalyses();
      setRunningAnalyses(list);
    } catch {
      setRunningAnalyses([]);
    } finally {
      setRunningAnalysesLoading(false);
    }
  };

  const handleStopRunningAnalysis = async (runId: number) => {
    setStoppingRunId(runId);
    try {
      await adminApi.stopRunningAnalysis(runId);
      await Promise.all([refreshRunningAnalyses(), refreshMissionControl()]);
    } finally {
      setStoppingRunId(null);
    }
  };

  const refreshMissionControl = async () => {
    setMissionLoading(true);
    setMissionError(null);
    try {
      const [res, running] = await Promise.all([
        adminApi.getMissionControl(),
        adminApi.getRunningAnalyses(),
      ]);
      setMissionItems(res.items);
      setRunningAnalyses(running);
      setSelectedMissionTickers((prev) => {
        const valid = new Set(res.items.map((item) => item.ticker));
        return prev.filter((ticker) => valid.has(ticker));
      });
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setMissionError(ax.response?.data?.detail ?? 'Failed to load mission control');
    } finally {
      setMissionLoading(false);
    }
  };

  const closeReportDetail = useCallback(() => {
    reportDetailRequestRef.current += 1;
    setSelectedReport(null);
    setSelectedReportDetail(null);
    setReportDetailError(null);
    setLoadingReportDetail(false);
  }, []);

  const openReportDetail = useCallback(async (report: AdminReportItem) => {
    const requestId = reportDetailRequestRef.current + 1;
    reportDetailRequestRef.current = requestId;

    setSelectedReport(report);
    setSelectedReportDetail(null);
    setReportDetailError(null);

    const cached = reportDetailsRef.current[report.id];
    if (cached) {
      setSelectedReportDetail(cached);
      setLoadingReportDetail(false);
      return;
    }

    setLoadingReportDetail(true);
    try {
      const detail = await adminApi.getReport(report.id);
      if (reportDetailRequestRef.current !== requestId) return;
      reportDetailsRef.current[report.id] = detail;
      setSelectedReportDetail(detail);
    } catch (err: unknown) {
      if (reportDetailRequestRef.current !== requestId) return;
      const ax = err as { response?: { data?: { detail?: string } } };
      setReportDetailError(ax.response?.data?.detail ?? 'Failed to load report details');
    } finally {
      if (reportDetailRequestRef.current === requestId) {
        setLoadingReportDetail(false);
      }
    }
  }, []);

  const selectedReportPayload = useMemo(() => {
    if (!selectedReportDetail) return null;
    return {
      id: selectedReportDetail.id,
      ticker: selectedReportDetail.ticker,
      analysis_run_id: selectedReportDetail.analysis_run_id,
      report_type: selectedReportDetail.report_type,
      created_at: selectedReportDetail.created_at,
      input_tokens: selectedReportDetail.input_tokens ?? null,
      output_tokens: selectedReportDetail.output_tokens ?? null,
      total_tokens: selectedReportDetail.total_tokens ?? null,
      cost_usd: selectedReportDetail.cost_usd ?? null,
      metadata: selectedReportDetail.metadata ?? null,
      ...(selectedReportDetail.metadata == null && selectedReportDetail.metadata_raw
        ? { metadata_raw: selectedReportDetail.metadata_raw }
        : {}),
    };
  }, [selectedReportDetail]);

  const runMissionForTickers = async (tickers: string[], forceOverride?: boolean) => {
    if (tickers.length === 0) return;
    setMissionActionError(null);
    setMissionActionInfo(null);
    try {
      const force = forceOverride ?? missionForceRerun;
      const result = await adminApi.runMissionControl(tickers, force);
      setMissionActionInfo(summarizeMissionRunResult(result));
      if (result.failed.length > 0) {
        const failures = result.failed.map((item) => `${item.ticker}: ${item.error}`).join(' | ');
        setMissionActionError(failures);
      }
      const today = new Date().toISOString().slice(0, 10);
      const fromRun = [
        ...result.triggered,
        ...result.already_running,
      ].map((item) => ({
        analysis_run_id: item.analysis_run_id,
        ticker: item.ticker,
        date: today,
        status: 'running',
        agent_statuses: {},
        current_agent: null,
        current_agents: [],
        updated_at: new Date().toISOString(),
      }));
      setRunningAnalyses((prev) => {
        const byId = new Map(prev.map((r) => [r.analysis_run_id, r]));
        fromRun.forEach((r) => byId.set(r.analysis_run_id, r));
        return Array.from(byId.values());
      });
      setMissionItems((prev) =>
        prev.map((item) => {
          const run = fromRun.find((r) => r.ticker === item.ticker);
          if (!run) return item;
          return { ...item, is_running: true, running_analysis_id: run.analysis_run_id };
        }),
      );
      await refreshMissionControl();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } };
      setMissionActionError(ax.response?.data?.detail ?? 'Failed to run mission control action');
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [s, u, r, a, subs, vr] = await Promise.all([
          adminApi.getStats(),
          adminApi.getUsers(100, 0),
          adminApi.getReports(200),
          adminApi.getAnalyses(50, 0),
          adminApi.getSubscriptions(500, 0),
          adminApi.getViewRuns(500),
        ]);
        setStats(s);
        setUsers(u.users);
        setUsersTotal(u.total);
        setReports(r.reports);
        setReportsTotal(r.total);
        setAnalyses(a.analyses);
        setAnalysesTotal(a.total);
        setSubscriptions(subs.subscriptions);
        setSubscriptionsTotal(subs.total);
        setViewRuns(vr.runs);
        setViewRunsTotal(vr.total_runs_with_views);
        // Daily analyses and views would need API endpoints
        setDailyAnalyses([]);
        setDailyViews([]);
      } catch (err: unknown) {
        const ax = err as { response?: { data?: { detail?: string } } };
        setError(ax.response?.data?.detail ?? 'Failed to load admin data');
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, []);

  useEffect(() => {
    if (activeTab === 'mission-control') {
      void refreshMissionControl();
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== 'mission-control') return;
    const interval = setInterval(() => {
      void refreshRunningAnalyses();
    }, 10000);
    return () => clearInterval(interval);
  }, [activeTab]);

  // Scroll handler for loading more analyses
  const handleAnalysesScroll = useCallback(async () => {
    const container = analysesContainerRef.current;
    if (!container || loadingMoreAnalyses || analyses.length >= analysesTotal) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const scrollPercentage = (scrollTop + clientHeight) / scrollHeight;

    // Load more when scrolled 80% down
    if (scrollPercentage > 0.8) {
      setLoadingMoreAnalyses(true);
      try {
        const result = await adminApi.getAnalyses(50, analyses.length);
        setAnalyses((prev) => [...prev, ...result.analyses]);
        setAnalysesTotal(result.total);
      } catch (err) {
        console.error('Failed to load more analyses:', err);
      } finally {
        setLoadingMoreAnalyses(false);
      }
    }
  }, [analyses.length, analysesTotal, loadingMoreAnalyses]);

  useEffect(() => {
    const container = analysesContainerRef.current;
    if (!container) return;

    container.addEventListener('scroll', handleAnalysesScroll);
    return () => container.removeEventListener('scroll', handleAnalysesScroll);
  }, [handleAnalysesScroll]);

  if (!user) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-lg mx-auto text-center text-gray-400">
          <p className="mb-4">Please log in to access the admin dashboard.</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300">
            Go to home
          </Link>
        </div>
      </div>
    );
  }

  if (!user.is_admin) {
    return <Navigate to="/" replace />;
  }

  if (loading && !stats) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <svg className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-gray-400 text-sm">Loading admin dashboard…</p>
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-lg mx-auto text-center text-gray-400">
          <p className="mb-4">{error}</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300">
            Go to home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      <PageHeader
        title="Admin"
        icon={
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        }
      />
      <div className="flex-1 p-6 md:p-8">
        <div className="max-w-layout mx-auto">
          <div className="border-b border-slate-700 mb-8">
            <div className="flex flex-wrap gap-0.5">
              <button
                type="button"
                onClick={() => handleAdminTabChange('overview')}
                className={`px-2 py-1.5 text-sm font-medium transition-colors ${
                  activeTab === 'overview'
                    ? 'border-b-2 border-blue-500 text-blue-400'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                Overview
              </button>
              <button
                type="button"
                onClick={() => handleAdminTabChange('mission-control')}
                className={`px-2 py-1.5 text-sm font-medium transition-colors ${
                  activeTab === 'mission-control'
                    ? 'border-b-2 border-blue-500 text-blue-400'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                Mission control
              </button>
              <button
                type="button"
                onClick={() => handleAdminTabChange('users')}
                className={`px-2 py-1.5 text-sm font-medium transition-colors ${
                  activeTab === 'users'
                    ? 'border-b-2 border-blue-500 text-blue-400'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                Users
              </button>
            </div>
          </div>

          {activeTab === 'overview' && (
            <OverviewTab
              stats={stats}
              dailyAnalyses={dailyAnalyses}
              dailyViews={dailyViews}
              analyses={analyses}
              analysesTotal={analysesTotal}
              filteredAnalyses={filteredAnalyses}
              analysisTickerFilter={analysisTickerFilter}
              analysisCreatorFilter={analysisCreatorFilter}
              setAnalysisTickerFilter={setAnalysisTickerFilter}
              setAnalysisCreatorFilter={setAnalysisCreatorFilter}
              loadingMoreAnalyses={loadingMoreAnalyses}
              reports={reports}
              reportsTotal={reportsTotal}
              latestReportsCollapsed={latestReportsCollapsed}
              setLatestReportsCollapsed={setLatestReportsCollapsed}
              openReportDetail={openReportDetail}
              setStats={setStats}
              setAnalyses={setAnalyses}
              setAnalysesTotal={setAnalysesTotal}
              setReports={setReports}
              setReportsTotal={setReportsTotal}
              analysesContainerRef={analysesContainerRef}
            />
          )}

          {activeTab === 'mission-control' && (
            <MissionControlTab
              runningAnalyses={runningAnalyses}
              runningAnalysesLoading={runningAnalysesLoading}
              missionLoading={missionLoading}
              stoppingRunId={stoppingRunId}
              handleStopRunningAnalysis={handleStopRunningAnalysis}
              missionTickerFilter={missionTickerFilter}
              setMissionTickerFilter={setMissionTickerFilter}
              refreshMissionControl={refreshMissionControl}
              missionForceRerun={missionForceRerun}
              setMissionForceRerun={setMissionForceRerun}
              selectedMissionTickers={selectedMissionTickers}
              setSelectedMissionTickers={setSelectedMissionTickers}
              missionBulkRunning={missionBulkRunning}
              setMissionBulkRunning={setMissionBulkRunning}
              runMissionForTickers={runMissionForTickers}
              missionActionInfo={missionActionInfo}
              missionActionError={missionActionError}
              missionError={missionError}
              sortedMissionItems={sortedMissionItems}
              missionItems={missionItems}
              selectedMissionTickerSet={selectedMissionTickerSet}
              allMissionTickers={allMissionTickers}
              allMissionSelected={allMissionSelected}
              missionSort={missionSort}
              toggleMissionSort={toggleMissionSort}
              sortIndicator={sortIndicator}
              missionRunningForTicker={missionRunningForTicker}
              setMissionRunningForTicker={setMissionRunningForTicker}
            />
          )}

          {activeTab === 'users' && (
            <UsersTab
              users={users}
              usersTotal={usersTotal}
              addTokensError={addTokensError}
              setAddTokensError={setAddTokensError}
              addAmountByUser={addAmountByUser}
              setAddAmountByUser={setAddAmountByUser}
              addingForUserId={addingForUserId}
              setAddingForUserId={setAddingForUserId}
              setUsers={setUsers}
              stats={stats}
              viewRuns={viewRuns}
              viewRunsTotal={viewRunsTotal}
              sortedViewRuns={sortedViewRuns}
              viewsByRun={viewsByRun}
              expandedViewRunKeys={expandedViewRunKeys}
              loadingRunViewKeys={loadingRunViewKeys}
              toggleRunExpanded={toggleRunExpanded}
              getSortedRunViews={getSortedRunViews}
              viewRunsSort={viewRunsSort}
              toggleViewRunsSort={toggleViewRunsSort}
              viewRunsSortIndicator={viewRunsSortIndicator}
              subscriptionsByUser={subscriptionsByUser}
              subscriptionsTotal={subscriptionsTotal}
              expandedSubscriptionUserIds={expandedSubscriptionUserIds}
              setExpandedSubscriptionUserIds={setExpandedSubscriptionUserIds}
            />
          )}
        </div>
      </div>

      {selectedReport && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={closeReportDetail}
          role="dialog"
          aria-modal="true"
          aria-labelledby="admin-report-raw-data-title"
        >
          <div
            className="flex max-h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-gray-800 px-5 py-4">
              <div>
                <h2 id="admin-report-raw-data-title" className="text-lg font-semibold text-white">
                  Report raw data
                </h2>
                <p className="mt-1 text-sm text-gray-400">
                  {selectedReport.ticker} • {selectedReport.report_type} • run {selectedReport.analysis_run_id}
                </p>
              </div>
              <button
                type="button"
                onClick={closeReportDetail}
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 transition hover:border-gray-600 hover:text-white"
              >
                Close
              </button>
            </div>

            <div className="space-y-4 overflow-y-auto px-5 py-4">
              {loadingReportDetail ? (
                <div className="flex min-h-40 items-center justify-center">
                  <div className="text-center">
                    <svg className="mx-auto mb-3 h-7 w-7 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <p className="text-sm text-gray-400">Loading report payload…</p>
                  </div>
                </div>
              ) : reportDetailError ? (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                  {reportDetailError}
                </div>
              ) : selectedReportDetail ? (
                <>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-xl border border-gray-800 bg-gray-950/60 px-4 py-3">
                      <p className="text-xs uppercase tracking-wide text-gray-500">Created</p>
                      <p className="mt-1 text-sm text-gray-200">{formatDate(selectedReportDetail.created_at, true)}</p>
                    </div>
                    <div className="rounded-xl border border-gray-800 bg-gray-950/60 px-4 py-3">
                      <p className="text-xs uppercase tracking-wide text-gray-500">Input tokens</p>
                      <p className="mt-1 text-sm text-gray-200">
                        {selectedReportDetail.input_tokens != null
                          ? selectedReportDetail.input_tokens.toLocaleString()
                          : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-gray-800 bg-gray-950/60 px-4 py-3">
                      <p className="text-xs uppercase tracking-wide text-gray-500">Output tokens</p>
                      <p className="mt-1 text-sm text-gray-200">
                        {selectedReportDetail.output_tokens != null
                          ? selectedReportDetail.output_tokens.toLocaleString()
                          : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl border border-gray-800 bg-gray-950/60 px-4 py-3">
                      <p className="text-xs uppercase tracking-wide text-gray-500">Cost</p>
                      <p className="mt-1 text-sm text-gray-200">
                        {selectedReportDetail.cost_usd != null
                          ? `$${selectedReportDetail.cost_usd.toFixed(4)}`
                          : '—'}
                      </p>
                    </div>
                  </div>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold text-white">Raw payload</h3>
                    <JsonViewer data={selectedReportPayload} />
                  </section>

                  {selectedReportDetail.content && (
                    <section>
                      <h3 className="mb-2 text-sm font-semibold text-white">Content</h3>
                      <pre className="max-h-72 overflow-auto rounded-xl border border-gray-800 bg-gray-950/80 p-4 text-xs text-gray-200 whitespace-pre-wrap break-words">
                        {selectedReportDetail.content}
                      </pre>
                    </section>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Made with Bob
