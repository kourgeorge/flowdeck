import { useState, useEffect } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  adminApi,
  type AdminStats,
  type AdminUserItem,
  type AdminReportItem,
  type AdminAnalysisItem,
  type AdminSubscriptionItem,
  type AnalysisDailyCount,
} from '../services/adminApi';

function formatDate(s: string): string {
  try {
    const d = new Date(s);
    return d.toLocaleString(undefined, {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  } catch {
    return s;
  }
}

export default function AdminDashboardPage() {
  const { user } = useAuth();
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addingForUserId, setAddingForUserId] = useState<number | null>(null);
  const [addTokensError, setAddTokensError] = useState<string | null>(null);
  const [addAmountByUser, setAddAmountByUser] = useState<Record<number, string>>({});

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
    ])
      .then(([s, u, r, a, sub, daily]) => {
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
        setDailyAnalyses(daily.data);
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
        <div className="max-w-6xl mx-auto text-gray-400">Loading admin dashboard…</div>
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
      <div className="max-w-6xl mx-auto">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-6"
        >
          ← Back to Flowdeck
        </Link>
        <h1 className="text-2xl font-bold text-white mb-8">Admin dashboard</h1>

        {/* Stats */}
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

        {/* Daily Analyses Chart */}
        {dailyAnalyses.length > 0 && (() => {
          const chartH = 160;
          const chartW = 800;
          const padLeft = 32;
          const padBottom = 28;
          const padTop = 16;
          const padRight = 8;
          const innerW = chartW - padLeft - padRight;
          const innerH = chartH - padBottom - padTop;
          const maxCount = Math.max(...dailyAnalyses.map((d) => d.count), 1);
          const barW = innerW / dailyAnalyses.length;
          const barGap = Math.max(1, barW * 0.15);
          const totalAnalyses = dailyAnalyses.reduce((s, d) => s + d.count, 0);

          // Y-axis ticks
          const yTicks = [0, Math.round(maxCount / 2), maxCount];

          return (
            <section className="mb-10">
              <h2 className="text-lg font-semibold text-white mb-4">
                Analyses per day (last 30 days) — total: {totalAnalyses}
              </h2>
              <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 overflow-x-auto">
                <svg
                  viewBox={`0 0 ${chartW} ${chartH}`}
                  className="w-full"
                  style={{ minWidth: '400px', height: `${chartH}px` }}
                >
                  {/* Y-axis grid lines and labels */}
                  {yTicks.map((tick) => {
                    const y = padTop + innerH - (tick / maxCount) * innerH;
                    return (
                      <g key={tick}>
                        <line
                          x1={padLeft}
                          y1={y}
                          x2={chartW - padRight}
                          y2={y}
                          stroke="#374151"
                          strokeWidth="1"
                          strokeDasharray={tick === 0 ? undefined : '3,3'}
                        />
                        <text
                          x={padLeft - 4}
                          y={y + 4}
                          textAnchor="end"
                          fontSize="10"
                          fill="#9ca3af"
                        >
                          {tick}
                        </text>
                      </g>
                    );
                  })}

                  {/* Bars */}
                  {dailyAnalyses.map((item, i) => {
                    const barHeight = (item.count / maxCount) * innerH;
                    const x = padLeft + i * barW + barGap / 2;
                    const y = padTop + innerH - barHeight;
                    const w = barW - barGap;
                    const date = new Date(item.date);
                    const dayLabel = date.toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                    });
                    const showLabel = i === 0 || i === dailyAnalyses.length - 1 || i % 5 === 0;
                    return (
                      <g key={item.date}>
                        <rect
                          x={x}
                          y={item.count > 0 ? y : padTop + innerH - 2}
                          width={Math.max(w, 1)}
                          height={item.count > 0 ? barHeight : 2}
                          fill={item.count > 0 ? '#3b82f6' : '#374151'}
                          rx="2"
                        >
                          <title>{`${dayLabel}: ${item.count} analyses`}</title>
                        </rect>
                        {item.count > 0 && (
                          <text
                            x={x + w / 2}
                            y={y - 3}
                            textAnchor="middle"
                            fontSize="9"
                            fill="#93c5fd"
                          >
                            {item.count}
                          </text>
                        )}
                        {showLabel && (
                          <text
                            x={x + w / 2}
                            y={chartH - 4}
                            textAnchor="middle"
                            fontSize="9"
                            fill="#6b7280"
                          >
                            {dayLabel}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </svg>
              </div>
            </section>
          );
        })()}

        {/* Customers */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-white mb-4">Customers ({usersTotal})</h2>
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

        {/* Recent analyses */}
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
                        to={`/stocks/${a.ticker}`}
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

        {/* Latest reports */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-white mb-4">Latest reports ({reportsTotal})</h2>
          <div className="overflow-x-auto overflow-y-auto max-h-96 rounded-lg border border-gray-700 bg-gray-800/80">
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
                        to={`/stocks/${r.ticker}`}
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
        </section>

        {/* Subscriptions */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">Subscriptions ({subscriptionsTotal})</h2>
          <div className="overflow-x-auto rounded-lg border border-gray-700 bg-gray-800/80">
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
                        to={`/stocks/${s.ticker}`}
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
        </section>
      </div>
    </div>
  );
}
