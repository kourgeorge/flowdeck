import { Fragment, useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
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
  type MissionControlRunResponse,
  type RunningAnalysisItem,
} from '../services/adminApi';

type AdminTab = 'overview' | 'mission-control' | 'users';
const ADMIN_TAB_IDS: AdminTab[] = ['overview', 'mission-control', 'users'];
type MissionSortKey = 'ticker' | 'company' | 'type' | 'market_cap' | 'sector' | 'industry' | 'last_completed' | 'reports' | 'status' | 'priority' | 'subscriptions';
type MissionSortDirection = 'asc' | 'desc';
type ViewRunsSortKey = 'ticker' | 'analysis_run_id' | 'unique_views' | 'viewed';
type ViewRunsSortDirection = 'asc' | 'desc';

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function formatJsonPrimitive(value: unknown): string {
  if (typeof value === 'string') return `"${value}"`;
  if (value === null) return 'null';
  return String(value);
}

function JsonViewerNode({
  label,
  value,
  defaultExpanded = false,
}: {
  label?: string;
  value: unknown;
  defaultExpanded?: boolean;
}) {
  const isArray = Array.isArray(value);
  const isObject = isJsonObject(value);
  const isContainer = isArray || isObject;
  const entries = isArray
    ? value.map((item, index) => [String(index), item] as const)
    : isObject
      ? Object.entries(value)
      : [];
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (!isContainer) {
    return (
      <div className="flex flex-wrap items-start gap-2 py-0.5">
        {label && <span className="font-medium text-sky-300">{label}:</span>}
        <span
          className={
            typeof value === 'string'
              ? 'break-all text-emerald-300'
              : value === null
                ? 'text-fuchsia-300'
                : typeof value === 'number'
                  ? 'text-amber-300'
                  : typeof value === 'boolean'
                    ? 'text-violet-300'
                    : 'text-gray-200'
          }
        >
          {formatJsonPrimitive(value)}
        </span>
      </div>
    );
  }

  const isEmpty = entries.length === 0;
  const summary = isArray ? `[${entries.length}]` : `{${entries.length}}`;

  return (
    <div className="py-0.5">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-2 text-left text-gray-200 transition-colors hover:text-white"
      >
        <span className={`inline-block text-[10px] text-gray-500 transition-transform ${expanded ? 'rotate-90' : ''}`}>
          ▶
        </span>
        {label && <span className="font-medium text-sky-300">{label}:</span>}
        <span className="text-gray-400">{isEmpty ? (isArray ? '[]' : '{}') : summary}</span>
      </button>

      {expanded && !isEmpty && (
        <div className="mt-1 ml-2 border-l border-gray-800 pl-3">
          {entries.map(([entryKey, entryValue]) => (
            <JsonViewerNode
              key={entryKey}
              label={isArray ? undefined : entryKey}
              value={entryValue}
              defaultExpanded={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function JsonViewer({ data }: { data: unknown }) {
  return (
    <div className="max-h-[45vh] overflow-auto rounded-xl border border-gray-800 bg-gray-950/80 p-4 text-xs font-mono text-gray-200">
      <JsonViewerNode value={data} defaultExpanded />
    </div>
  );
}

function formatDate(s?: string | null, use24Hour = false): string {
  if (!s) return '—';
  try {
    const d = new Date(s);
    return d.toLocaleString(undefined, {
      dateStyle: 'short',
      timeStyle: 'short',
      ...(use24Hour ? { hour12: false } : {}),
    });
  } catch {
    return s;
  }
}

function formatMarketCap(value?: number | null): string {
  if (value == null || !Number.isFinite(value) || value <= 0) return '—';
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  return value.toLocaleString();
}

function quoteTypeSortRank(value?: string | null): number {
  return String(value ?? '').toUpperCase() === 'EQUITY' ? 0 : 1;
}

function compareNullableNumber(a?: number | null, b?: number | null): number {
  const aValid = typeof a === 'number' && Number.isFinite(a);
  const bValid = typeof b === 'number' && Number.isFinite(b);
  if (!aValid && !bValid) return 0;
  if (!aValid) return 1;
  if (!bValid) return -1;
  return a - b;
}

function compareNullableString(a?: string | null, b?: string | null): number {
  const aVal = String(a ?? '').trim();
  const bVal = String(b ?? '').trim();
  if (!aVal && !bVal) return 0;
  if (!aVal) return 1;
  if (!bVal) return -1;
  return aVal.localeCompare(bVal, undefined, { sensitivity: 'base' });
}

function summarizeMissionRunResult(result: MissionControlRunResponse): string {
  const parts: string[] = [];
  if (result.triggered.length > 0) parts.push(`started ${result.triggered.length}`);
  if (result.already_running.length > 0) parts.push(`already running ${result.already_running.length}`);
  if (result.skipped_existing.length > 0) parts.push(`skipped existing ${result.skipped_existing.length}`);
  if (result.invalid_tickers.length > 0) parts.push(`invalid ${result.invalid_tickers.length}`);
  if (result.failed.length > 0) parts.push(`failed ${result.failed.length}`);
  return parts.length > 0 ? parts.join(' • ') : 'No changes';
}

function DailyBarChart({
  data,
  color,
  label,
}: {
  data: { date: string; count: number }[];
  color: string;
  label: string;
}) {
  if (data.length === 0) return null;
  const total = data.reduce((s, d) => s + d.count, 0);

  const chartData = data.map((item) => ({
    date: new Date(item.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    count: item.count,
  }));

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 flex-1 min-w-0">
      <p className="text-sm font-semibold text-white mb-2">
        {label} — total: {total}
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#9ca3af"
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis stroke="#9ca3af" tick={{ fill: '#9ca3af', fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '0.5rem',
              color: '#fff',
            }}
            labelStyle={{ color: '#9ca3af' }}
          />
          <Bar dataKey="count" fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

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
    if (!user?.is_admin) return;
    let cancelled = false;
    Promise.all([
      adminApi.getStats(),
      adminApi.getUsers(50, 0),
      adminApi.getReports(200),
      adminApi.getAnalyses(50),
      adminApi.getSubscriptions(100, 0),
      adminApi.getViewRuns(100),
      adminApi.getAnalysesDaily(30),
      adminApi.getViewsDaily(30),
      adminApi.getMissionControl(),
      adminApi.getRunningAnalyses(),
    ])
      .then(([s, u, r, a, sub, viewRunsRes, dailyA, dailyV, mission, running]) => {
        if (cancelled) return;
        setStats(s);
        setUsers(u.users);
        setUsersTotal(u.total);
        setReports(r.reports);
        setReportsTotal(r.total);
        setAnalyses(a.analyses);
        setAnalysesTotal(a.total);
        setSubscriptions(sub.subscriptions);
        setSubscriptionsTotal(sub.total);
        setViewRuns(viewRunsRes.runs);
        setViewRunsTotal(viewRunsRes.total_runs_with_views);
        setViewsByRun({});
        setExpandedViewRunKeys(new Set());
        setLoadingRunViewKeys(new Set());
        setDailyAnalyses(dailyA.data);
        setDailyViews(dailyV.data);
        setMissionItems(mission.items);
        setRunningAnalyses(running);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail ?? 'Failed to load admin data');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.is_admin]);

  useEffect(() => {
    if (!user?.is_admin || activeTab !== 'mission-control') return;
    if (missionItems.length > 0 || missionLoading) return;
    void refreshMissionControl();
  }, [activeTab, missionItems.length, missionLoading, user?.is_admin]);

  useEffect(() => {
    if (!selectedReport) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeReportDetail();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedReport, closeReportDetail]);

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

        {activeTab === 'users' ? (
          <section className="space-y-10">
            <h2 className="text-lg font-semibold text-white">Users ({usersTotal})</h2>
            {addTokensError && (
              <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm text-red-200">
                {addTokensError}
                <button
                  type="button"
                  onClick={() => setAddTokensError(null)}
                  className="ml-2 text-red-400 hover:text-red-100"
                  aria-label="Dismiss"
                >
                  ×
                </button>
              </div>
            )}
            <div className="overflow-x-auto rounded-lg border border-gray-700 bg-gray-800/80">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead className="sticky top-0 bg-gray-800 z-10">
                  <tr className="border-b border-gray-700">
                    <th className="px-4 py-3 text-gray-400 font-medium">Email</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Name</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Tokens</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Subscriptions</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const amountStr = addAmountByUser[u.id] ?? '200';
                    const amount = Math.max(1, parseInt(amountStr, 10) || 0);
                    const isAdding = addingForUserId === u.id;
                    return (
                      <tr key={u.id} className="border-b border-gray-700/50">
                        <td className="px-4 py-3 text-gray-300">{u.email}</td>
                        <td className="px-4 py-3 text-gray-300">{u.name ?? '—'}</td>
                        <td className="px-4 py-3 text-white">{u.token_balance.toLocaleString()}</td>
                        <td className="px-4 py-3 text-gray-300">{u.subscription_count}</td>
                        <td className="px-4 py-3 text-gray-400">{formatDate(u.created_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              min={1}
                              max={10000}
                              value={amountStr}
                              onChange={(e) =>
                                setAddAmountByUser((prev) => ({ ...prev, [u.id]: e.target.value }))
                              }
                              className="w-20 rounded border border-gray-600 bg-gray-700 px-2 py-1 text-white text-right"
                              disabled={isAdding}
                              aria-label={`Tokens to add for ${u.email}`}
                            />
                            <button
                              type="button"
                              onClick={async () => {
                                setAddTokensError(null);
                                setAddingForUserId(u.id);
                                try {
                                  const res = await adminApi.addTokensToUser(u.id, amount);
                                  setUsers((prev) =>
                                    prev.map((x) =>
                                      x.id === u.id ? { ...x, token_balance: res.token_balance } : x,
                                    ),
                                  );
                                } catch (err: unknown) {
                                  const ax = err as { response?: { data?: { detail?: string } } };
                                  setAddTokensError(
                                    ax.response?.data?.detail ?? 'Failed to add tokens',
                                  );
                                } finally {
                                  setAddingForUserId(null);
                                }
                              }}
                              disabled={isAdding || amount < 1}
                              className="rounded bg-blue-600 px-2 py-1 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                            >
                              {isAdding ? '…' : 'Add tokens'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <section className="mb-10">
              <h2 className="text-lg font-semibold text-white mb-4">
                Report views (runs: {viewRunsTotal}, views: {stats?.total_report_views ?? 0})
              </h2>
              <div className="overflow-x-auto overflow-y-auto max-h-[36rem] rounded-lg border border-gray-700 bg-gray-800/80">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="sticky top-0 bg-gray-800 z-10">
                    <tr className="border-b border-gray-700">
                      <th className="px-4 py-3 text-gray-400 font-medium">
                        <button
                          type="button"
                          onClick={() => toggleViewRunsSort('ticker')}
                          className="inline-flex items-center gap-1 hover:text-white transition-colors"
                        >
                          Ticker <span className="text-xs">{viewRunsSortIndicator('ticker')}</span>
                        </button>
                      </th>
                      <th className="px-4 py-3 text-gray-400 font-medium">
                        <button
                          type="button"
                          onClick={() => toggleViewRunsSort('analysis_run_id')}
                          className="inline-flex items-center gap-1 hover:text-white transition-colors"
                        >
                          Run ID <span className="text-xs">{viewRunsSortIndicator('analysis_run_id')}</span>
                        </button>
                      </th>
                      <th className="px-4 py-3 text-gray-400 font-medium">
                        <button
                          type="button"
                          onClick={() => toggleViewRunsSort('unique_views')}
                          className="inline-flex items-center gap-1 hover:text-white transition-colors"
                        >
                          Unique views <span className="text-xs">{viewRunsSortIndicator('unique_views')}</span>
                        </button>
                      </th>
                      <th className="px-4 py-3 text-gray-400 font-medium">Viewer email</th>
                      <th className="px-4 py-3 text-gray-400 font-medium">
                        <button
                          type="button"
                          onClick={() => toggleViewRunsSort('viewed')}
                          className="inline-flex items-center gap-1 hover:text-white transition-colors"
                        >
                          Viewed <span className="text-xs">{viewRunsSortIndicator('viewed')}</span>
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedViewRuns.map((run) => {
                      const runKey = `${run.ticker}::${run.analysis_run_id}`;
                      const runViews = viewsByRun[runKey] ?? [];
                      const sortedRunViews = getSortedRunViews(runViews);
                      const isExpanded = expandedViewRunKeys.has(runKey);
                      const isLoadingRunViews = loadingRunViewKeys.has(runKey);

                      return (
                        <Fragment key={runKey}>
                          <tr key={runKey} className="border-b border-gray-700/50 bg-gray-800">
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                onClick={() => toggleRunExpanded(run.ticker, run.analysis_run_id)}
                                className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 font-medium"
                                aria-expanded={isExpanded}
                                aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${run.ticker} ${run.analysis_run_id}`}
                              >
                                <span className={`inline-block transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
                                  ▶
                                </span>
                                <span>{run.ticker}</span>
                              </button>
                            </td>
                            <td className="px-4 py-3 text-gray-300 font-mono text-xs">{run.analysis_run_id}</td>
                            <td className="px-4 py-3 text-white">{run.unique_views.toLocaleString()}</td>
                            <td className="px-4 py-3 text-gray-500">
                              {isExpanded
                                ? isLoadingRunViews
                                  ? 'Loading viewers...'
                                  : `${runViews.length} viewer${runViews.length === 1 ? '' : 's'}`
                                : 'Expand to view viewers'}
                            </td>
                            <td className="px-4 py-3 text-gray-400">{formatDate(run.last_viewed_at)}</td>
                          </tr>
                          {isExpanded &&
                            !isLoadingRunViews &&
                            sortedRunViews.map((view) => (
                              <tr key={view.id} className="border-b border-gray-700/30 bg-gray-900/40">
                                <td className="px-4 py-2 text-gray-500">↳</td>
                                <td className="px-4 py-2 text-gray-600 font-mono text-xs">{view.analysis_run_id}</td>
                                <td className="px-4 py-2 text-gray-600">-</td>
                                <td className="px-4 py-2 text-gray-300">{view.viewer_email}</td>
                                <td className="px-4 py-2 text-gray-400">{formatDate(view.viewed_at)}</td>
                              </tr>
                            ))}
                          {isExpanded && !isLoadingRunViews && runViews.length === 0 && (
                            <tr className="border-b border-gray-700/30 bg-gray-900/40">
                              <td className="px-4 py-2 text-gray-500">↳</td>
                              <td className="px-4 py-2 text-gray-600 font-mono text-xs">{run.analysis_run_id}</td>
                              <td className="px-4 py-2 text-gray-600">-</td>
                              <td className="px-4 py-2 text-gray-500" colSpan={2}>
                                No viewer rows found for this run.
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                    {viewRuns.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-6 text-center text-gray-400">
                          No report views yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <h2 className="text-lg font-semibold text-white">Subscriptions ({subscriptionsTotal})</h2>
            <div className="overflow-x-auto rounded-lg border border-gray-700 bg-gray-800/80">
              <table className="w-full min-w-[400px] text-left text-sm">
                <thead className="sticky top-0 bg-gray-800 z-10">
                  <tr className="border-b border-gray-700">
                    <th className="px-4 py-3 text-gray-400 font-medium w-10" aria-label="Expand" />
                    <th className="px-4 py-3 text-gray-400 font-medium">User / Ticker</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Email updates</th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {subscriptionsByUser.map(({ user_id, user_email, subscriptions: userSubs }) => {
                    const isExpanded = expandedSubscriptionUserIds.has(user_id);
                    const sortedSubs = [...userSubs].sort((a, b) =>
                      a.ticker.localeCompare(b.ticker, undefined, { sensitivity: 'base' }),
                    );
                    return (
                      <Fragment key={user_id}>
                        <tr className="border-b border-gray-700/50 bg-gray-800">
                          <td className="px-4 py-3">
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedSubscriptionUserIds((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(user_id)) next.delete(user_id);
                                  else next.add(user_id);
                                  return next;
                                })
                              }
                              className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-200"
                              aria-expanded={isExpanded}
                              aria-label={isExpanded ? 'Collapse' : 'Expand'}
                            >
                              <span
                                className={`inline-block transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                              >
                                ▶
                              </span>
                            </button>
                          </td>
                          <td className="px-4 py-3 text-white font-medium" colSpan={3}>
                            {user_email}
                            <span className="ml-2 text-gray-400 font-normal">
                              ({userSubs.length} subscription{userSubs.length === 1 ? '' : 's'})
                            </span>
                          </td>
                        </tr>
                        {isExpanded &&
                          sortedSubs.map((s) => (
                            <tr key={s.id} className="border-b border-gray-700/30 bg-gray-900/40">
                              <td className="px-4 py-2 text-gray-500">↳</td>
                              <td className="px-4 py-2">
                                <Link
                                  to={`/tickers/${s.ticker}`}
                                  className="text-blue-400 hover:text-blue-300 font-medium"
                                >
                                  {s.ticker}
                                </Link>
                              </td>
                              <td className="px-4 py-2 text-gray-400">{s.email_updates ? 'Yes' : 'No'}</td>
                              <td className="px-4 py-2 text-gray-400">{formatDate(s.created_at)}</td>
                            </tr>
                          ))}
                      </Fragment>
                    );
                  })}
                  {subscriptionsByUser.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-gray-400">
                        No subscriptions.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        ) : activeTab === 'mission-control' ? (
          <section>
            {/* Running analyses: list + stop */}
            <div className="mb-4 rounded-lg border border-gray-700 bg-gray-800/80 p-4">
              <h3 className="mb-2 text-sm font-semibold text-gray-300">
                Running analyses {runningAnalyses.length > 0 ? `(${runningAnalyses.length})` : ''}
              </h3>
              {(missionLoading || runningAnalysesLoading) && runningAnalyses.length === 0 ? (
                <p className="text-sm text-gray-500">Loading…</p>
              ) : runningAnalyses.length === 0 ? (
                <p className="text-sm text-gray-500">No analyses currently running.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-gray-700 text-gray-400">
                        <th className="px-3 py-2 font-medium">Ticker</th>
                        <th className="px-3 py-2 font-medium">Date</th>
                        <th className="px-3 py-2 font-medium">Current agent</th>
                        <th className="px-3 py-2 font-medium">Updated</th>
                        <th className="px-3 py-2 font-medium w-20">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runningAnalyses.map((r) => (
                        <tr key={r.analysis_run_id} className="border-b border-gray-700/80">
                          <td className="px-3 py-2 font-mono">
                            <Link
                              to={`/tickers/${r.ticker}`}
                              className="text-blue-400 hover:text-blue-300"
                            >
                              {r.ticker}
                            </Link>
                          </td>
                          <td className="px-3 py-2 text-gray-300">{r.date ?? '—'}</td>
                          <td className="px-3 py-2 text-gray-300">{r.current_agent ?? '—'}</td>
                          <td className="px-3 py-2 text-gray-500">{formatDate(r.updated_at, true)}</td>
                          <td className="px-3 py-2">
                            <button
                              type="button"
                              onClick={() => void handleStopRunningAnalysis(r.analysis_run_id)}
                              disabled={stoppingRunId === r.analysis_run_id}
                              className="rounded bg-red-700/80 px-2 py-1 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
                            >
                              {stoppingRunId === r.analysis_run_id ? 'Stopping…' : 'Stop'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="mb-4 flex flex-wrap items-center gap-3">
              <div className="min-w-[260px] flex-1 max-w-md">
                <label htmlFor="mission-ticker-filter" className="sr-only">
                  Filter mission control by ticker or company name
                </label>
                <input
                  id="mission-ticker-filter"
                  type="text"
                  value={missionTickerFilter}
                  onChange={(e) => setMissionTickerFilter(e.target.value)}
                  placeholder="Filter by ticker or company"
                  className="w-full rounded border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-white placeholder:text-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <button
                type="button"
                onClick={() => {
                  void refreshMissionControl();
                }}
                disabled={missionLoading}
                className="rounded bg-gray-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-600 disabled:opacity-50"
              >
                {missionLoading ? 'Refreshing…' : 'Refresh'}
              </button>
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="checkbox"
                  checked={missionForceRerun}
                  onChange={(e) => setMissionForceRerun(e.target.checked)}
                />
                Force rerun
              </label>
              <button
                type="button"
                onClick={() => {
                  const tickers = selectedMissionTickers;
                  setSelectedMissionTickers([]);
                  setMissionBulkRunning(true);
                  void runMissionForTickers(tickers).finally(() => {
                    setMissionBulkRunning(false);
                  });
                }}
                disabled={missionBulkRunning || selectedMissionTickers.length === 0}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {missionBulkRunning ? 'Running…' : `Run selected (${selectedMissionTickers.length})`}
              </button>
              {missionActionInfo && (
                <div className="inline-flex items-center gap-2 rounded-lg border border-emerald-700/60 bg-emerald-950/40 px-3 py-1.5 text-sm text-emerald-200">
                  <span className="text-emerald-300">Status</span>
                  <span>{missionActionInfo}</span>
                </div>
              )}
            </div>

            {missionActionError && (
              <div className="mb-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm text-red-200">
                {missionActionError}
              </div>
            )}
            {missionError && (
              <div className="mb-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm text-red-200">
                {missionError}
              </div>
            )}

            {missionTickerFilter.trim() && (
              <div className="mb-3 text-sm text-gray-400">
                Showing {sortedMissionItems.length} of {missionItems.length} mission-control rows.
              </div>
            )}

            <div className="overflow-x-auto overflow-y-auto max-h-[70vh] rounded-lg border border-gray-700 bg-gray-800/80">
              <table className="w-full min-w-[1280px] text-left text-sm">
                <thead className="sticky top-0 bg-gray-800 z-10">
                  <tr className="border-b border-gray-700">
                    <th className="px-4 py-3 text-gray-400 font-medium w-10">
                      <input
                        type="checkbox"
                        checked={allMissionSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedMissionTickers((prev) => Array.from(new Set([...prev, ...allMissionTickers])));
                          } else {
                            setSelectedMissionTickers((prev) => prev.filter((ticker) => !allMissionTickers.includes(ticker)));
                          }
                        }}
                        aria-label="Select all major tickers"
                      />
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('ticker')}
                      >
                        Ticker <span className="text-xs">{sortIndicator('ticker')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('company')}
                      >
                        Company <span className="text-xs">{sortIndicator('company')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('type')}
                      >
                        Type <span className="text-xs">{sortIndicator('type')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('market_cap')}
                      >
                        Market cap <span className="text-xs">{sortIndicator('market_cap')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('sector')}
                      >
                        Sector <span className="text-xs">{sortIndicator('sector')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('industry')}
                      >
                        Industry <span className="text-xs">{sortIndicator('industry')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('last_completed')}
                      >
                        Last completed <span className="text-xs">{sortIndicator('last_completed')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('reports')}
                      >
                        Reports <span className="text-xs">{sortIndicator('reports')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('subscriptions')}
                      >
                        Subs <span className="text-xs">{sortIndicator('subscriptions')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('priority')}
                      >
                        Priority <span className="text-xs">{sortIndicator('priority')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-gray-200"
                        onClick={() => toggleMissionSort('status')}
                      >
                        Status <span className="text-xs">{sortIndicator('status')}</span>
                      </button>
                    </th>
                    <th className="px-4 py-3 text-gray-400 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedMissionItems.map((item) => {
                    const isSelected = selectedMissionTickerSet.has(item.ticker);
                    const isRunningThisTicker = missionRunningForTicker === item.ticker;
                    const isRunDisabled = isRunningThisTicker || item.is_running;
                    return (
                      <tr key={item.ticker} className="border-b border-gray-700/50">
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => {
                              setSelectedMissionTickers((prev) => {
                                if (e.target.checked) {
                                  return prev.includes(item.ticker) ? prev : [...prev, item.ticker];
                                }
                                return prev.filter((ticker) => ticker !== item.ticker);
                              });
                            }}
                            aria-label={`Select ${item.ticker}`}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <Link
                            to={`/tickers/${item.ticker}`}
                            className="text-blue-400 hover:text-blue-300 font-medium"
                          >
                            {item.ticker}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-gray-300 max-w-[280px] truncate" title={item.name ?? undefined}>
                          {item.name ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-300">{item.quote_type ?? '—'}</td>
                        <td className="px-4 py-3 text-gray-300">{formatMarketCap(item.market_cap)}</td>
                        <td className="px-4 py-3 text-gray-300">{item.sector ?? '—'}</td>
                        <td className="px-4 py-3 text-gray-300">{item.industry ?? '—'}</td>
                        <td className="px-4 py-3 text-gray-300">{formatDate(item.last_completed_at, true)}</td>
                        <td className="px-4 py-3 text-gray-300">
                          {item.report_count != null ? item.report_count : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-300">
                          {item.subscription_count ?? 0}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`font-medium ${
                            (item.priority_score ?? 0) >= 70 ? 'text-red-400' :
                            (item.priority_score ?? 0) >= 50 ? 'text-orange-400' :
                            (item.priority_score ?? 0) >= 30 ? 'text-yellow-400' :
                            'text-gray-400'
                          }`}>
                            {item.priority_score?.toFixed(1) ?? '0.0'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {item.is_running ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-900/50 text-blue-300 border border-blue-700">
                              Running
                            </span>
                          ) : item.last_status === 'completed' ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-900/50 text-green-300 border border-green-700">
                              Completed
                            </span>
                          ) : item.last_status === 'failed' ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-900/50 text-red-300 border border-red-700">
                              Failed
                            </span>
                          ) : (
                            <span className="text-gray-500">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            disabled={isRunDisabled}
                            onClick={() => {
                              setMissionRunningForTicker(item.ticker);
                              void runMissionForTickers([item.ticker], true).finally(() => {
                                setMissionRunningForTicker(null);
                              });
                            }}
                            className="rounded border border-gray-600 bg-gray-800 px-2 py-1 text-sm font-medium text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                          >
                            Run
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {sortedMissionItems.length === 0 && (
                    <tr>
                      <td colSpan={13} className="px-4 py-6 text-center text-gray-400">
                        No mission-control rows found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <>
            {stats && (
              <section className="mb-10">
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  <div className="flex flex-col gap-0.5 rounded-lg px-3 py-2 border bg-gray-700/40 border-gray-600/50">
                    <div className="flex items-center gap-1.5 text-gray-400 text-xs font-medium uppercase tracking-wide">
                      <span className="w-4 h-4 flex items-center justify-center">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5V4H2v16h5m10 0v-2a3 3 0 00-3-3H10a3 3 0 00-3 3v2m10 0H7m8-12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </span>
                      Total users
                    </div>
                    <div className="text-lg font-bold leading-tight text-white">{stats.total_users.toLocaleString()}</div>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg px-3 py-2 border bg-gray-700/40 border-gray-600/50">
                    <div className="flex items-center gap-1.5 text-gray-400 text-xs font-medium uppercase tracking-wide">
                      <span className="w-4 h-4 flex items-center justify-center">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h6l5 5v11a2 2 0 01-2 2z" />
                        </svg>
                      </span>
                      Total reports
                    </div>
                    <div className="text-lg font-bold leading-tight text-white">{stats.total_reports.toLocaleString()}</div>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg px-3 py-2 border bg-gray-700/40 border-gray-600/50">
                    <div className="flex items-center gap-1.5 text-gray-400 text-xs font-medium uppercase tracking-wide">
                      <span className="w-4 h-4 flex items-center justify-center">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3v18m0 0l-4-4m4 4l4-4M4 7h5m6 0h5" />
                        </svg>
                      </span>
                      Analyses (7d)
                    </div>
                    <div className="text-lg font-bold leading-tight text-white">{stats.analyses_last_7d.toLocaleString()}</div>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg px-3 py-2 border bg-gray-700/40 border-gray-600/50">
                    <div className="flex items-center gap-1.5 text-gray-400 text-xs font-medium uppercase tracking-wide">
                      <span className="w-4 h-4 flex items-center justify-center">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </span>
                      Report views
                    </div>
                    <div className="text-lg font-bold leading-tight text-white">{stats.total_report_views.toLocaleString()}</div>
                  </div>
                  <div className="flex flex-col gap-0.5 rounded-lg px-3 py-2 border bg-gray-700/40 border-gray-600/50">
                    <div className="flex items-center gap-1.5 text-gray-400 text-xs font-medium uppercase tracking-wide">
                      <span className="w-4 h-4 flex items-center justify-center">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                        </svg>
                      </span>
                      Subscriptions
                    </div>
                    <div className="text-lg font-bold leading-tight text-white">{stats.total_subscriptions.toLocaleString()}</div>
                  </div>
                </div>
              </section>
            )}

            {(dailyAnalyses.length > 0 || dailyViews.length > 0) && (
              <section className="mb-10">
                <h2 className="text-lg font-semibold text-white mb-4">Activity (last 30 days)</h2>
                <div className="flex flex-col md:flex-row gap-4">
                  <DailyBarChart
                    data={dailyAnalyses}
                    color="#3b82f6"
                    label="Analyses per day"
                  />
                  <DailyBarChart
                    data={dailyViews}
                    color="#10b981"
                    label="Report views per day"
                  />
                </div>
              </section>
            )}

            <section className="mb-10">
              <h2 className="text-lg font-semibold text-white mb-2">Recent analyses ({analysesTotal})</h2>
              <div className="flex flex-wrap gap-3 mb-3 text-xs md:text-sm">
                <div className="flex items-center gap-2">
                  <label htmlFor="analysis-ticker-filter" className="text-gray-400">
                    Ticker:
                  </label>
                  <input
                    id="analysis-ticker-filter"
                    type="text"
                    value={analysisTickerFilter}
                    onChange={(e) => setAnalysisTickerFilter(e.target.value)}
                    className="px-2 py-1 rounded-md bg-gray-900 border border-gray-700 text-gray-100 placeholder-gray-500 text-xs md:text-sm"
                    placeholder="e.g. AAPL"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label htmlFor="analysis-creator-filter" className="text-gray-400">
                    Creator:
                  </label>
                  <input
                    id="analysis-creator-filter"
                    type="text"
                    value={analysisCreatorFilter}
                    onChange={(e) => setAnalysisCreatorFilter(e.target.value)}
                    className="px-2 py-1 rounded-md bg-gray-900 border border-gray-700 text-gray-100 placeholder-gray-500 text-xs md:text-sm"
                    placeholder="email contains…"
                  />
                </div>
              </div>
              <div
                ref={analysesContainerRef}
                className="overflow-x-auto overflow-y-auto max-h-96 rounded-lg border border-gray-700 bg-gray-800/80"
              >
                <table className="w-full min-w-[500px] text-left text-sm">
                    <thead className="sticky top-0 bg-gray-800 z-10">
                      <tr className="border-b border-gray-700">
                        <th className="px-4 py-3 text-gray-400 font-medium">Ticker</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Run ID</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Creator</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Status</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Earned tokens</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">In tokens</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Out tokens</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">LLM cost</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                        <th className="px-4 py-3 text-gray-400 font-medium w-20">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                    {filteredAnalyses.map((a) => (
                      <tr key={a.id} className="border-b border-gray-700/50">
                        <td className="px-4 py-3">
                          <Link
                            to={`/tickers/${a.ticker}`}
                            className="text-blue-400 hover:text-blue-300 font-medium"
                          >
                            {a.ticker}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-gray-300 font-mono text-xs">{a.id}</td>
                        <td className="px-4 py-3 text-gray-300">{a.creator_email}</td>
                        <td className="px-4 py-3">
                          {a.status === 'completed' ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-900/50 text-green-300 border border-green-700">
                              Completed
                            </span>
                          ) : a.status === 'failed' ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-900/50 text-red-300 border border-red-700">
                              Failed
                            </span>
                          ) : a.status === 'running' ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-900/50 text-blue-300 border border-blue-700">
                              Running
                            </span>
                          ) : (
                            <span className="text-gray-500">{a.status}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-white">{a.earned_tokens}</td>
                        <td className="px-4 py-3 text-gray-400 tabular-nums">
                          {a.input_tokens != null && a.input_tokens > 0
                            ? a.input_tokens.toLocaleString()
                            : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-400 tabular-nums">
                          {a.output_tokens != null && a.output_tokens > 0
                            ? a.output_tokens.toLocaleString()
                            : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-400 tabular-nums">
                          {a.cost_usd != null && a.cost_usd > 0
                            ? `$${a.cost_usd.toFixed(4)}`
                            : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-400">{formatDate(a.created_at)}</td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={async () => {
                              if (!window.confirm(`Delete analysis run ${a.id} (${a.ticker})? This cannot be undone.`)) return;
                              await adminApi.deleteAnalysis(a.id);
                              const [s, aRes, rRes] = await Promise.all([
                                adminApi.getStats(),
                                adminApi.getAnalyses(50),
                                adminApi.getReports(200),
                              ]);
                              setStats(s);
                              setAnalyses(aRes.analyses);
                              setAnalysesTotal(aRes.total);
                              setReports(rRes.reports);
                              setReportsTotal(rRes.total);
                            }}
                            className="text-red-400 hover:text-red-300 hover:underline text-sm font-medium"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                    {loadingMoreAnalyses && (
                      <tr>
                        <td colSpan={9} className="px-4 py-3 text-center text-gray-400">
                          Loading more analyses...
                        </td>
                      </tr>
                    )}
                    {!loadingMoreAnalyses && analyses.length < analysesTotal && (
                      <tr>
                        <td colSpan={9} className="px-4 py-3 text-center text-gray-500 text-xs">
                          Scroll down to load more ({analyses.length} of {analysesTotal})
                        </td>
                      </tr>
                    )}
                 </tbody>
               </table>
             </div>
            </section>

            <section className="mb-10">
              <div className="mb-4">
                <button
                  type="button"
                  onClick={() => setLatestReportsCollapsed((prev) => !prev)}
                  className="group flex w-full items-center gap-3 text-left"
                  aria-expanded={!latestReportsCollapsed}
                  aria-controls="latest-reports-table"
                >
                  <h2 className="text-lg font-semibold text-white">Latest reports ({reportsTotal})</h2>
                  <span className="h-px flex-1 bg-gray-700 transition-colors group-hover:bg-gray-600" />
                  <span className="inline-flex items-center gap-1 text-sm text-gray-300">
                    {latestReportsCollapsed ? 'Show' : 'Hide'}
                    <svg
                      className={`h-4 w-4 transition-transform ${latestReportsCollapsed ? '' : 'rotate-180'}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </span>
                </button>
              </div>
              {!latestReportsCollapsed && (
                <div className="space-y-3">
                  <p className="text-sm text-gray-400">Click any report row to inspect its raw payload and metadata.</p>
                  <div
                    id="latest-reports-table"
                    className="overflow-x-auto overflow-y-auto max-h-96 rounded-lg border border-gray-700 bg-gray-800/80"
                  >
                  <table className="w-full min-w-[500px] text-left text-sm">
                    <thead className="sticky top-0 bg-gray-800 z-10">
                      <tr className="border-b border-gray-700">
                        <th className="px-4 py-3 text-gray-400 font-medium">Ticker</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Run ID</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Type</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">In tokens</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Out tokens</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Cost</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reports.map((r) => (
                        <tr
                          key={r.id}
                          className="border-b border-gray-700/50 cursor-pointer transition-colors hover:bg-gray-700/30 focus:bg-gray-700/30"
                          role="button"
                          tabIndex={0}
                          aria-label={`Open raw report data for ${r.ticker} ${r.report_type}`}
                          onClick={() => void openReportDetail(r)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault();
                              void openReportDetail(r);
                            }
                          }}
                        >
                          <td className="px-4 py-3">
                            <Link
                              to={`/tickers/${r.ticker}`}
                              className="text-blue-400 hover:text-blue-300 font-medium"
                              onClick={(event) => event.stopPropagation()}
                            >
                              {r.ticker}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-gray-300 font-mono text-xs">{r.analysis_run_id}</td>
                          <td className="px-4 py-3 text-gray-300">{r.report_type}</td>
                          <td className="px-4 py-3 text-gray-400 tabular-nums">
                            {r.input_tokens != null ? r.input_tokens.toLocaleString() : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-400 tabular-nums">
                            {r.output_tokens != null ? r.output_tokens.toLocaleString() : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-400 tabular-nums">
                            {r.cost_usd != null ? `$${r.cost_usd.toFixed(4)}` : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-400">{formatDate(r.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </div>
              )}
            </section>
          </>
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
