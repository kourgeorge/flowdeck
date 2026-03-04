import { useState, useEffect } from 'react';
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
  
  // Format data for Recharts
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
      adminApi.getViewsDaily(30),
    ])
      .then(([s, u, r, a, sub, dailyA, dailyV]) => {
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

        {/* Daily Charts: Analyses + Views side by side */}
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

        {/* Users */}
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
        </section>
      </div>
    </div>
  );
}
