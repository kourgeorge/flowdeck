import { useState, useEffect, useMemo } from 'react';
import { Link, Navigate } from 'react-router-dom';
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
import {
  adminApi,
  type AdminStats,
  type AdminUserItem,
  type AdminReportItem,
  type AdminAnalysisItem,
  type AdminSubscriptionItem,
  type AnalysisDailyCount,
  type ViewsDailyCount,
  type MissionControlTickerItem,
  type MissionControlRunResponse,
} from '../services/adminApi';

type AdminTab = 'overview' | 'mission-control';
type MissionSortKey = 'ticker' | 'type' | 'market_cap' | 'sector' | 'industry' | 'last_completed' | 'status';
type MissionSortDirection = 'asc' | 'desc';

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
  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [reports, setReports] = useState<AdminReportItem[]>([]);
  const [reportsTotal, setReportsTotal] = useState(0);
  const [analyses, setAnalyses] = useState<AdminAnalysisItem[]>([]);
  const [analysesTotal, setAnalysesTotal] = useState(0);
  const [subscriptions, setSubscriptions] = useState<AdminSubscriptionItem[]>([]);
  const [subscriptionsTotal, setSubscriptionsTotal] = useState(0);
  const [dailyAnalyses, setDailyAnalyses] = useState<AnalysisDailyCount[]>([]);
  const [dailyViews, setDailyViews] = useState<ViewsDailyCount[]>([]);

  const [missionItems, setMissionItems] = useState<MissionControlTickerItem[]>([]);
  const [selectedMissionTickers, setSelectedMissionTickers] = useState<string[]>([]);
  const [missionLoading, setMissionLoading] = useState(false);
  const [missionError, setMissionError] = useState<string | null>(null);
  const [missionActionError, setMissionActionError] = useState<string | null>(null);
  const [missionActionInfo, setMissionActionInfo] = useState<string | null>(null);
  const [missionRunningForTicker, setMissionRunningForTicker] = useState<string | null>(null);
  const [missionBulkRunning, setMissionBulkRunning] = useState(false);
  const [missionForceRerun, setMissionForceRerun] = useState(false);
  const [missionSort, setMissionSort] = useState<{
    key: MissionSortKey;
    direction: MissionSortDirection;
  }>({
    key: 'type',
    direction: 'asc',
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addingForUserId, setAddingForUserId] = useState<number | null>(null);
  const [addTokensError, setAddTokensError] = useState<string | null>(null);
  const [addAmountByUser, setAddAmountByUser] = useState<Record<number, string>>({});
  const [latestReportsCollapsed, setLatestReportsCollapsed] = useState(true);
  const [subscriptionsCollapsed, setSubscriptionsCollapsed] = useState(true);

  const sortedMissionItems = useMemo(
    () =>
      [...missionItems].sort((a, b) => {
        let cmp = 0;
        switch (missionSort.key) {
          case 'ticker':
            cmp = a.ticker.localeCompare(b.ticker, undefined, { sensitivity: 'base' });
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
          case 'status':
            cmp = Number(a.is_running) - Number(b.is_running);
            break;
          default:
            cmp = 0;
        }
        if (missionSort.direction === 'desc') cmp *= -1;
        if (cmp !== 0) return cmp;
        return a.ticker.localeCompare(b.ticker);
      }),
    [missionItems, missionSort],
  );
  const selectedMissionTickerSet = new Set(selectedMissionTickers);
  const allMissionTickers = sortedMissionItems.map((item) => item.ticker);
  const allMissionSelected =
    sortedMissionItems.length > 0 && selectedMissionTickers.length === sortedMissionItems.length;

  const toggleMissionSort = (key: MissionSortKey) => {
    setMissionSort((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      const defaultDirection: MissionSortDirection =
        key === 'market_cap' || key === 'last_completed' || key === 'status' ? 'desc' : 'asc';
      return { key, direction: defaultDirection };
    });
  };

  const sortIndicator = (key: MissionSortKey): string =>
    missionSort.key === key ? (missionSort.direction === 'asc' ? '↑' : '↓') : '↕';

  const refreshMissionControl = async () => {
    setMissionLoading(true);
    setMissionError(null);
    try {
      const res = await adminApi.getMissionControl();
      setMissionItems(res.items);
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
      adminApi.getAnalysesDaily(30),
      adminApi.getViewsDaily(30),
      adminApi.getMissionControl(),
    ])
      .then(([s, u, r, a, sub, dailyA, dailyV, mission]) => {
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
        setDailyAnalyses(dailyA.data);
        setDailyViews(dailyV.data);
        setMissionItems(mission.items);
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
      <div className="min-h-screen p-8">
        <div className="max-w-layout mx-auto text-gray-400">Loading admin dashboard…</div>
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
    <div className="min-h-screen p-6 md:p-8">
      <div className="max-w-layout mx-auto">
        <h1 className="text-2xl font-bold text-white mb-4">Admin dashboard</h1>

        <div className="border-b border-slate-700 mb-8">
          <div className="flex flex-wrap gap-0.5">
            <button
              type="button"
              onClick={() => setActiveTab('overview')}
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
              onClick={() => setActiveTab('mission-control')}
              className={`px-2 py-1.5 text-sm font-medium transition-colors ${
                activeTab === 'mission-control'
                  ? 'border-b-2 border-blue-500 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              Mission control
            </button>
          </div>
        </div>

        {activeTab === 'mission-control' ? (
          <section>
            <div className="mb-4 flex flex-wrap items-center gap-3">
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
                  setMissionBulkRunning(true);
                  void runMissionForTickers(selectedMissionTickers).finally(() => {
                    setMissionBulkRunning(false);
                  });
                }}
                disabled={missionBulkRunning || selectedMissionTickers.length === 0}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {missionBulkRunning ? 'Running…' : `Run selected (${selectedMissionTickers.length})`}
              </button>
            </div>

            {missionActionInfo && (
              <div className="mb-3 rounded-lg border border-emerald-800 bg-emerald-950/50 px-4 py-2 text-sm text-emerald-200">
                {missionActionInfo}
              </div>
            )}
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

            <div className="overflow-x-auto overflow-y-auto max-h-[70vh] rounded-lg border border-gray-700 bg-gray-800/80">
              <table className="w-full min-w-[1120px] text-left text-sm">
                <thead className="sticky top-0 bg-gray-800 z-10">
                  <tr className="border-b border-gray-700">
                    <th className="px-4 py-3 text-gray-400 font-medium w-10">
                      <input
                        type="checkbox"
                        checked={allMissionSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedMissionTickers(allMissionTickers);
                          } else {
                            setSelectedMissionTickers([]);
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
                        <td className="px-4 py-3 text-gray-300">{item.quote_type ?? '—'}</td>
                        <td className="px-4 py-3 text-gray-300">{formatMarketCap(item.market_cap)}</td>
                        <td className="px-4 py-3 text-gray-300">{item.sector ?? '—'}</td>
                        <td className="px-4 py-3 text-gray-300">{item.industry ?? '—'}</td>
                        <td className="px-4 py-3 text-gray-300">{formatDate(item.last_completed_at, true)}</td>
                        <td className="px-4 py-3 text-gray-300">
                          {item.is_running ? (
                            <div>
                              <p className="text-blue-300 font-medium">Running</p>
                            </div>
                          ) : (
                            <span className="text-gray-400">Idle</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            disabled={isRunningThisTicker}
                            onClick={() => {
                              setMissionRunningForTicker(item.ticker);
                              void runMissionForTickers([item.ticker], true).finally(() => {
                                setMissionRunningForTicker(null);
                              });
                            }}
                            className="rounded border border-gray-600 bg-gray-800 px-2 py-1 text-sm font-medium text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                          >
                            {isRunningThisTicker ? 'Running…' : 'Run'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {sortedMissionItems.length === 0 && (
                    <tr>
                      <td colSpan={9} className="px-4 py-6 text-center text-gray-400">
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
                <h2 className="text-lg font-semibold text-white mb-4">Overview</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Total users</p>
                    <p className="text-2xl font-bold text-white">{stats.total_users.toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Total reports</p>
                    <p className="text-2xl font-bold text-white">{stats.total_reports.toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Analyses (7d)</p>
                    <p className="text-2xl font-bold text-white">{stats.analyses_last_7d.toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Report views</p>
                    <p className="text-2xl font-bold text-white">{stats.total_report_views.toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Subscriptions</p>
                    <p className="text-2xl font-bold text-white">{stats.total_subscriptions.toLocaleString()}</p>
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
              <h2 className="text-lg font-semibold text-white mb-4">Users ({usersTotal})</h2>
              {addTokensError && (
                <div className="mb-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-2 text-sm text-red-200">
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
            </section>

            <section className="mb-10">
              <h2 className="text-lg font-semibold text-white mb-4">Recent analyses ({analysesTotal})</h2>
              <div className="overflow-x-auto overflow-y-auto max-h-96 rounded-lg border border-gray-700 bg-gray-800/80">
                <table className="w-full min-w-[500px] text-left text-sm">
                  <thead className="sticky top-0 bg-gray-800 z-10">
                    <tr className="border-b border-gray-700">
                      <th className="px-4 py-3 text-gray-400 font-medium">Ticker</th>
                      <th className="px-4 py-3 text-gray-400 font-medium">Run ID</th>
                      <th className="px-4 py-3 text-gray-400 font-medium">Creator</th>
                      <th className="px-4 py-3 text-gray-400 font-medium">Earned tokens</th>
                      <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyses.map((a) => (
                      <tr key={a.id} className="border-b border-gray-700/50">
                        <td className="px-4 py-3">
                          <Link
                            to={`/tickers/${a.ticker}`}
                            className="text-blue-400 hover:text-blue-300 font-medium"
                          >
                            {a.ticker}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-gray-300 font-mono text-xs">{a.run_id}</td>
                        <td className="px-4 py-3 text-gray-300">{a.creator_email}</td>
                        <td className="px-4 py-3 text-white">{a.earned_tokens}</td>
                        <td className="px-4 py-3 text-gray-400">{formatDate(a.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="mb-10">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-white">Latest reports ({reportsTotal})</h2>
                <button
                  type="button"
                  onClick={() => setLatestReportsCollapsed((prev) => !prev)}
                  className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700"
                  aria-expanded={!latestReportsCollapsed}
                  aria-controls="latest-reports-table"
                >
                  {latestReportsCollapsed ? 'Show reports' : 'Hide reports'}
                </button>
              </div>
              {!latestReportsCollapsed && (
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
                        <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reports.map((r) => (
                        <tr key={r.id} className="border-b border-gray-700/50">
                          <td className="px-4 py-3">
                            <Link
                              to={`/tickers/${r.ticker}`}
                              className="text-blue-400 hover:text-blue-300 font-medium"
                            >
                              {r.ticker}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-gray-300 font-mono text-xs">{r.run_id}</td>
                          <td className="px-4 py-3 text-gray-300">{r.report_type}</td>
                          <td className="px-4 py-3 text-gray-400">{formatDate(r.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-white">Subscriptions ({subscriptionsTotal})</h2>
                <button
                  type="button"
                  onClick={() => setSubscriptionsCollapsed((prev) => !prev)}
                  className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700"
                  aria-expanded={!subscriptionsCollapsed}
                  aria-controls="subscriptions-table"
                >
                  {subscriptionsCollapsed ? 'Show subscriptions' : 'Hide subscriptions'}
                </button>
              </div>
              {!subscriptionsCollapsed && (
                <div
                  id="subscriptions-table"
                  className="overflow-x-auto rounded-lg border border-gray-700 bg-gray-800/80"
                >
                  <table className="w-full min-w-[400px] text-left text-sm">
                    <thead className="sticky top-0 bg-gray-800 z-10">
                      <tr className="border-b border-gray-700">
                        <th className="px-4 py-3 text-gray-400 font-medium">User email</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Ticker</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Email updates</th>
                        <th className="px-4 py-3 text-gray-400 font-medium">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subscriptions.map((s) => (
                        <tr key={s.id} className="border-b border-gray-700/50">
                          <td className="px-4 py-3 text-gray-300">{s.user_email}</td>
                          <td className="px-4 py-3">
                            <Link
                              to={`/tickers/${s.ticker}`}
                              className="text-blue-400 hover:text-blue-300 font-medium"
                            >
                              {s.ticker}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-gray-400">{s.email_updates ? 'Yes' : 'No'}</td>
                          <td className="px-4 py-3 text-gray-400">{formatDate(s.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
