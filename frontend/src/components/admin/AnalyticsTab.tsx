import { useEffect, useState } from 'react';
import {
  adminApi,
  type AnalyticsCostBreakdown,
  type AnalyticsCostPerUser,
  type AnalyticsExpensiveOperations,
  type AnalyticsModelDistribution,
  type AnalyticsRecommendations,
  type AnalyticsUsageTrends,
} from '../../services/adminApi';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const COLORS = ['#60a5fa', '#34d399', '#f59e0b', '#f87171', '#a78bfa', '#f472b6'];
const CHART_GRID = '#334155';
const CHART_TICK = '#94a3b8';
const CHART_TOOLTIP_STYLE = {
  backgroundColor: '#020617',
  border: '1px solid #334155',
  borderRadius: '12px',
  color: '#e2e8f0',
};

const SECTION_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'trends', label: 'Trends' },
  { id: 'users', label: 'Users' },
  { id: 'operations', label: 'Operations' },
  { id: 'models', label: 'Models' },
  { id: 'recommendations', label: 'Recommendations' },
] as const;

type AnalyticsSection = (typeof SECTION_TABS)[number]['id'];

interface AnalyticsTabProps {
  days: number;
  onDaysChange: (days: number) => void;
}

function AnalyticsPanel({
  title,
  description,
  children,
  className = '',
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-gray-700 bg-gray-800/80 p-5 shadow-[0_16px_48px_rgba(2,6,23,0.24)] ${className}`.trim()}
    >
      <div className="mb-5 flex flex-col gap-1">
        <h3 className="text-base font-semibold text-white">{title}</h3>
        {description ? <p className="text-sm text-gray-400">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex min-h-52 items-center justify-center rounded-2xl border border-dashed border-gray-700 bg-gray-900/50 px-6 py-10 text-center">
      <div className="max-w-md">
        <p className="text-sm font-medium text-gray-200">{title}</p>
        <p className="mt-2 text-sm text-gray-500">{description}</p>
      </div>
    </div>
  );
}

function formatChartDate(value: string) {
  const date = new Date(value);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function formatDateTime(value: string) {
  const date = new Date(value);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatCurrencyAxis(value: number) {
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  }
  if (value >= 1) {
    return `$${value.toFixed(value >= 10 ? 0 : 2)}`;
  }
  return `$${value.toFixed(3)}`;
}

function truncateLabel(value: string, maxLength = 18) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1)}…`;
}

export default function AnalyticsTab({ days, onDaysChange }: AnalyticsTabProps) {
  const [costBreakdown, setCostBreakdown] = useState<AnalyticsCostBreakdown | null>(null);
  const [costPerUser, setCostPerUser] = useState<AnalyticsCostPerUser | null>(null);
  const [expensiveOps, setExpensiveOps] = useState<AnalyticsExpensiveOperations | null>(null);
  const [usageTrends, setUsageTrends] = useState<AnalyticsUsageTrends | null>(null);
  const [modelDist, setModelDist] = useState<AnalyticsModelDistribution | null>(null);
  const [recommendations, setRecommendations] = useState<AnalyticsRecommendations | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<AnalyticsSection>('overview');

  useEffect(() => {
    void loadAnalytics();
  }, [days]);

  const loadAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const [breakdown, perUser, expensive, trends, models, recs] = await Promise.all([
        adminApi.getAnalyticsCostBreakdown(days),
        adminApi.getAnalyticsCostPerUser(days, 100),
        adminApi.getAnalyticsExpensiveOperations(days, 50),
        adminApi.getAnalyticsUsageTrends(days),
        adminApi.getAnalyticsModelDistribution(days),
        adminApi.getAnalyticsRecommendations(days),
      ]);
      setCostBreakdown(breakdown);
      setCostPerUser(perUser);
      setExpensiveOps(expensive);
      setUsageTrends(trends);
      setModelDist(models);
      setRecommendations(recs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: value >= 1 ? 2 : 4,
      maximumFractionDigits: value >= 1 ? 4 : 6,
    }).format(value);

  const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value);

  const totalOperations =
    costBreakdown?.operations.reduce((sum, operation) => sum + operation.count, 0) ?? 0;
  const topOperation =
    costBreakdown?.operations.reduce((highest, operation) => {
      if (!highest || operation.total_cost_usd > highest.total_cost_usd) {
        return operation;
      }
      return highest;
    }, null as AnalyticsCostBreakdown['operations'][number] | null) ?? null;
  const usersWithCost = costPerUser?.users.length ?? 0;
  const topUser = costPerUser?.users[0] ?? null;
  const uniqueProviders = modelDist ? new Set(modelDist.models.map((model) => model.provider)).size : 0;

  if (loading) {
    return (
      <div className="rounded-2xl border border-gray-700 bg-gray-800/70 px-6 py-12">
        <div className="flex flex-col items-center justify-center gap-3 text-center">
          <svg className="h-7 w-7 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-gray-200">Loading analytics</p>
            <p className="mt-1 text-sm text-gray-500">Pulling cost, usage, and model data for the selected window.</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-800/70 bg-red-950/40 p-5">
        <p className="text-sm font-medium text-red-100">{error}</p>
        <button
          type="button"
          onClick={() => {
            void loadAnalytics();
          }}
          className="mt-3 rounded-lg border border-red-700/80 px-3 py-1.5 text-sm font-medium text-red-100 transition hover:border-red-600 hover:bg-red-900/40"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-gray-700 bg-gradient-to-br from-slate-900 via-gray-900 to-gray-800 px-5 py-6 shadow-[0_18px_64px_rgba(2,6,23,0.32)]">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-300/80">Admin analytics</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Usage and spend across chat, analysis, and digest workloads</h2>
            <p className="mt-2 text-sm text-gray-400">
              Review cost drivers, model mix, high-cost runs, and user activity without leaving the admin dashboard.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <label htmlFor="analytics-period" className="text-xs font-medium uppercase tracking-wide text-gray-400">
              Time window
            </label>
            <select
              id="analytics-period"
              value={days}
              onChange={(event) => onDaysChange(Number(event.target.value))}
              className="rounded-xl border border-gray-600 bg-gray-900 px-4 py-2 text-sm text-gray-100 shadow-sm transition focus:border-blue-500 focus:outline-none"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 180 days</option>
              <option value={365}>Last year</option>
            </select>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          {SECTION_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveSection(tab.id)}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                activeSection === tab.id
                  ? 'border-blue-500/60 bg-blue-500/15 text-blue-200 shadow-[0_0_0_1px_rgba(59,130,246,0.15)]'
                  : 'border-gray-700 bg-gray-900/70 text-gray-400 hover:border-gray-600 hover:text-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {activeSection === 'overview' && costBreakdown && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Total cost</p>
              <p className="mt-3 text-3xl font-semibold text-white">{formatCurrency(costBreakdown.total_cost_usd)}</p>
              <p className="mt-2 text-sm text-gray-500">Across the last {days} days.</p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Total tokens</p>
              <p className="mt-3 text-3xl font-semibold text-white">{formatNumber(costBreakdown.total_llm_tokens)}</p>
              <p className="mt-2 text-sm text-gray-500">Summed from tracked LLM usage metadata.</p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Operations</p>
              <p className="mt-3 text-3xl font-semibold text-white">{formatNumber(totalOperations)}</p>
              <p className="mt-2 text-sm text-gray-500">
                Avg cost per operation:{' '}
                <span className="text-gray-300">
                  {formatCurrency(totalOperations > 0 ? costBreakdown.total_cost_usd / totalOperations : 0)}
                </span>
              </p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Top spend category</p>
              <p className="mt-3 text-2xl font-semibold capitalize text-white">
                {topOperation ? topOperation.operation_type : 'No activity'}
              </p>
              <p className="mt-2 text-sm text-gray-500">
                {topOperation ? formatCurrency(topOperation.total_cost_usd) : 'Nothing recorded in this period.'}
              </p>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
            <AnalyticsPanel
              title="Cost breakdown by operation"
              description="Compare spend concentration across chats, analyses, and digests."
            >
              {costBreakdown.operations.some((operation) => operation.count > 0) ? (
                <div className="h-[320px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={costBreakdown.operations} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke={CHART_GRID} vertical={false} strokeDasharray="3 3" />
                      <XAxis
                        dataKey="operation_type"
                        tick={{ fill: CHART_TICK, fontSize: 12 }}
                        axisLine={{ stroke: CHART_GRID }}
                        tickLine={{ stroke: CHART_GRID }}
                      />
                      <YAxis
                        tickFormatter={(value: number) => formatCurrencyAxis(value)}
                        tick={{ fill: CHART_TICK, fontSize: 12 }}
                        axisLine={{ stroke: CHART_GRID }}
                        tickLine={{ stroke: CHART_GRID }}
                        width={70}
                      />
                      <Tooltip
                        cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
                        contentStyle={CHART_TOOLTIP_STYLE}
                        formatter={(value, name) => {
                          const numericValue = Number(value ?? 0);
                          if (name === 'Cost') return [formatCurrency(numericValue), name];
                          if (name === 'Operations') return [formatNumber(numericValue), name];
                          return [numericValue, name];
                        }}
                      />
                      <Bar dataKey="total_cost_usd" name="Cost" radius={[10, 10, 0, 0]}>
                        {costBreakdown.operations.map((operation, index) => (
                          <Cell key={operation.operation_type} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState
                  title="No operation costs recorded"
                  description="This period does not include any tracked chat, analysis, or digest spend yet."
                />
              )}
            </AnalyticsPanel>

            <AnalyticsPanel
              title="Operation detail"
              description="Use this as a quick-read summary next to the chart."
            >
              <div className="space-y-3">
                {costBreakdown.operations.map((operation, index) => (
                  <div
                    key={operation.operation_type}
                    className="rounded-2xl border border-gray-700 bg-gray-900/70 p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-block h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: COLORS[index % COLORS.length] }}
                          />
                          <p className="text-sm font-semibold capitalize text-white">{operation.operation_type}</p>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">
                          {formatNumber(operation.count)} runs, {formatNumber(operation.total_llm_tokens)} tokens
                        </p>
                      </div>
                      <p className="text-sm font-semibold text-gray-100">{formatCurrency(operation.total_cost_usd)}</p>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-gray-400">
                      <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-3 py-2">
                        Avg cost
                        <div className="mt-1 text-sm font-medium text-gray-200">
                          {formatCurrency(operation.avg_cost_usd)}
                        </div>
                      </div>
                      <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-3 py-2">
                        Avg tokens
                        <div className="mt-1 text-sm font-medium text-gray-200">
                          {formatNumber(Math.round(operation.avg_llm_tokens))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </AnalyticsPanel>
          </div>
        </div>
      )}

      {activeSection === 'trends' && usageTrends && (
        <div className="space-y-6">
          <AnalyticsPanel
            title="Cost trends"
            description="Daily spend split by workflow, with operation volume overlaid for context."
          >
            {usageTrends.daily_data.length > 0 ? (
              <div className="h-[360px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={usageTrends.daily_data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatChartDate}
                      tick={{ fill: CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: CHART_GRID }}
                      tickLine={{ stroke: CHART_GRID }}
                    />
                    <YAxis
                      yAxisId="cost"
                      tickFormatter={(value: number) => formatCurrencyAxis(value)}
                      tick={{ fill: CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: CHART_GRID }}
                      tickLine={{ stroke: CHART_GRID }}
                      width={70}
                    />
                    <YAxis
                      yAxisId="ops"
                      orientation="right"
                      tickFormatter={(value: number) => formatNumber(value)}
                      tick={{ fill: CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: CHART_GRID }}
                      tickLine={{ stroke: CHART_GRID }}
                      width={60}
                    />
                    <Tooltip
                      contentStyle={CHART_TOOLTIP_STYLE}
                      labelFormatter={(label) => formatChartDate(String(label ?? ''))}
                      formatter={(value, name) => {
                        const numericValue = Number(value ?? 0);
                        if (name === 'Operations') return [formatNumber(numericValue), name];
                        return [formatCurrency(numericValue), name];
                      }}
                    />
                    <Line yAxisId="cost" type="monotone" dataKey="total_cost_usd" name="Total cost" stroke="#60a5fa" strokeWidth={2.5} dot={false} />
                    <Line yAxisId="cost" type="monotone" dataKey="chat_cost" name="Chat" stroke="#34d399" strokeWidth={2} dot={false} />
                    <Line yAxisId="cost" type="monotone" dataKey="analysis_cost" name="Analysis" stroke="#f59e0b" strokeWidth={2} dot={false} />
                    <Line yAxisId="cost" type="monotone" dataKey="digest_cost" name="Digest" stroke="#f87171" strokeWidth={2} dot={false} />
                    <Line yAxisId="ops" type="monotone" dataKey="operation_count" name="Operations" stroke="#a78bfa" strokeDasharray="6 6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState
                title="No daily trend data"
                description="Once the selected period includes tracked usage, daily cost and volume will render here."
              />
            )}
          </AnalyticsPanel>

          <AnalyticsPanel
            title="Token usage over time"
            description="Daily LLM token volume for the same period."
          >
            {usageTrends.daily_data.length > 0 ? (
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={usageTrends.daily_data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatChartDate}
                      tick={{ fill: CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: CHART_GRID }}
                      tickLine={{ stroke: CHART_GRID }}
                    />
                    <YAxis
                      tickFormatter={(value: number) => formatNumber(value)}
                      tick={{ fill: CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: CHART_GRID }}
                      tickLine={{ stroke: CHART_GRID }}
                    />
                    <Tooltip
                      contentStyle={CHART_TOOLTIP_STYLE}
                      labelFormatter={(label) => formatChartDate(String(label ?? ''))}
                      formatter={(value) => [formatNumber(Number(value ?? 0)), 'Tokens']}
                    />
                    <Bar dataKey="total_llm_tokens" name="Tokens" fill="#60a5fa" radius={[10, 10, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState
                title="No token data yet"
                description="Token volume needs tracked usage inside the selected window before it can be charted."
              />
            )}
          </AnalyticsPanel>
        </div>
      )}

      {activeSection === 'users' && costPerUser && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Users with activity</p>
              <p className="mt-3 text-3xl font-semibold text-white">{formatNumber(usersWithCost)}</p>
              <p className="mt-2 text-sm text-gray-500">Only users with tracked cost or tokens are listed.</p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Avg cost per active user</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {formatCurrency(usersWithCost > 0 && costBreakdown ? costBreakdown.total_cost_usd / usersWithCost : 0)}
              </p>
              <p className="mt-2 text-sm text-gray-500">Based on the users returned for this window.</p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Highest spender</p>
              <p className="mt-3 text-lg font-semibold text-white">{topUser?.email ?? 'No users'}</p>
              <p className="mt-2 text-sm text-gray-500">
                {topUser ? formatCurrency(topUser.total_cost_usd) : 'No tracked spend in this period.'}
              </p>
            </div>
          </div>

          <AnalyticsPanel
            title="Cost per user"
            description={`Top ${costPerUser.users.length} users ranked by spend during the last ${days} days.`}
            className="p-0"
          >
            {costPerUser.users.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-sm">
                  <thead className="sticky top-0 bg-gray-800">
                    <tr className="border-b border-gray-700">
                      <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-gray-400">#</th>
                      <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-gray-400">User</th>
                      <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Cost</th>
                      <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Tokens</th>
                      <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Operations</th>
                      <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Chat</th>
                      <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Analysis</th>
                      <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Digest</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costPerUser.users.map((user, index) => (
                      <tr key={user.user_id} className="border-b border-gray-700/60 transition hover:bg-gray-900/40">
                        <td className="px-5 py-4 text-gray-500">{index + 1}</td>
                        <td className="px-5 py-4">
                          <p className="font-medium text-gray-100">{user.email}</p>
                          <p className="mt-1 text-xs text-gray-500">User ID {user.user_id}</p>
                        </td>
                        <td className="px-5 py-4 text-right font-semibold tabular-nums text-white">
                          {formatCurrency(user.total_cost_usd)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-gray-300">
                          {formatNumber(user.total_llm_tokens)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-gray-300">
                          {formatNumber(user.operation_count)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-gray-400">
                          {formatNumber(user.chat_count)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-gray-400">
                          {formatNumber(user.analysis_count)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-gray-400">
                          {formatNumber(user.digest_count)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-5">
                <EmptyState
                  title="No user-level analytics"
                  description="User cost rows will appear here after tracked activity is recorded."
                />
              </div>
            )}
          </AnalyticsPanel>
        </div>
      )}

      {activeSection === 'operations' && expensiveOps && (
        <AnalyticsPanel
          title="Most expensive operations"
          description={`The ${expensiveOps.operations.length} highest-cost individual runs in the selected window.`}
          className="p-0"
        >
          {expensiveOps.operations.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1080px] text-left text-sm">
                <thead className="sticky top-0 bg-gray-800">
                  <tr className="border-b border-gray-700">
                    <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-gray-400">Type</th>
                    <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-gray-400">Subject</th>
                    <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-gray-400">User</th>
                    <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Cost</th>
                    <th className="px-5 py-4 text-right text-xs font-medium uppercase tracking-wide text-gray-400">Tokens</th>
                    <th className="px-5 py-4 text-xs font-medium uppercase tracking-wide text-gray-400">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {expensiveOps.operations.map((operation, index) => (
                    <tr
                      key={`${operation.operation_type}-${operation.operation_id}-${index}`}
                      className="border-b border-gray-700/60 transition hover:bg-gray-900/40"
                    >
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-1 text-xs font-medium capitalize text-blue-200">
                          {operation.operation_type}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <p className="max-w-[24rem] truncate text-gray-100" title={operation.subject}>
                          {operation.subject}
                        </p>
                      </td>
                      <td className="px-5 py-4">
                        <p className="max-w-[18rem] truncate text-gray-300" title={operation.user_email}>
                          {operation.user_email}
                        </p>
                      </td>
                      <td className="px-5 py-4 text-right font-semibold tabular-nums text-white">
                        {formatCurrency(operation.cost_usd)}
                      </td>
                      <td className="px-5 py-4 text-right tabular-nums text-gray-300">
                        {formatNumber(operation.llm_tokens)}
                      </td>
                      <td className="px-5 py-4 text-gray-400">{formatDateTime(operation.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-5">
              <EmptyState
                title="No expensive operations recorded"
                description="Once tracked workloads land in this period, the highest-cost runs will show up here."
              />
            </div>
          )}
        </AnalyticsPanel>
      )}

      {activeSection === 'models' && modelDist && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Tracked models</p>
              <p className="mt-3 text-3xl font-semibold text-white">{formatNumber(modelDist.models.length)}</p>
              <p className="mt-2 text-sm text-gray-500">Distinct model identifiers used in the selected range.</p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Providers</p>
              <p className="mt-3 text-3xl font-semibold text-white">{formatNumber(uniqueProviders)}</p>
              <p className="mt-2 text-sm text-gray-500">Distinct LLM providers represented in the model mix.</p>
            </div>
            <div className="rounded-2xl border border-gray-700 bg-gray-800/80 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Top model by cost</p>
              <p className="mt-3 text-lg font-semibold text-white">{modelDist.models[0]?.model ?? 'No models'}</p>
              <p className="mt-2 text-sm text-gray-500">
                {modelDist.models[0] ? formatCurrency(modelDist.models[0].total_cost_usd) : 'No spend recorded.'}
              </p>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
            <AnalyticsPanel
              title="Model cost distribution"
              description="Cost weighted by model so spend concentration is obvious."
            >
              {modelDist.models.length > 0 ? (
                <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_220px]">
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={modelDist.models}
                        layout="vertical"
                        margin={{ top: 4, right: 24, left: 0, bottom: 0 }}
                      >
                        <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" horizontal={false} />
                        <XAxis
                          type="number"
                          tickFormatter={(value: number) => formatCurrencyAxis(value)}
                          tick={{ fill: CHART_TICK, fontSize: 12 }}
                          axisLine={{ stroke: CHART_GRID }}
                          tickLine={{ stroke: CHART_GRID }}
                        />
                        <YAxis
                          type="category"
                          dataKey="model"
                          width={150}
                          tickFormatter={(value: string) => truncateLabel(value, 20)}
                          tick={{ fill: CHART_TICK, fontSize: 12 }}
                          axisLine={{ stroke: CHART_GRID }}
                          tickLine={{ stroke: CHART_GRID }}
                        />
                        <Tooltip
                          contentStyle={CHART_TOOLTIP_STYLE}
                          formatter={(value) => [formatCurrency(Number(value ?? 0)), 'Cost']}
                        />
                        <Bar dataKey="total_cost_usd" radius={[0, 10, 10, 0]}>
                          {modelDist.models.map((model, index) => (
                            <Cell key={`${model.provider}-${model.model}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="flex items-center justify-center">
                    <div className="h-[220px] w-[220px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={modelDist.models}
                            dataKey="total_cost_usd"
                            nameKey="model"
                            innerRadius={62}
                            outerRadius={90}
                            paddingAngle={2}
                            stroke="transparent"
                          >
                            {modelDist.models.map((model, index) => (
                              <Cell key={`pie-${model.provider}-${model.model}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={CHART_TOOLTIP_STYLE}
                            formatter={(value, _name, item) => [
                              formatCurrency(Number(value ?? 0)),
                              typeof item.payload?.model === 'string' ? item.payload.model : 'Model',
                            ]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No model usage"
                  description="Model distribution depends on tracked provider and model metadata."
                />
              )}
            </AnalyticsPanel>

            <AnalyticsPanel
              title="Model detail"
              description="Cross-check provider, cost, and token volume model by model."
            >
              <div className="space-y-3">
                {modelDist.models.map((model, index) => (
                  <div key={`${model.provider}-${model.model}`} className="rounded-2xl border border-gray-700 bg-gray-900/70 p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-block h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: COLORS[index % COLORS.length] }}
                          />
                          <p className="truncate text-sm font-semibold text-white" title={model.model}>
                            {model.model}
                          </p>
                        </div>
                        <p className="mt-1 text-xs uppercase tracking-wide text-gray-500">{model.provider}</p>
                      </div>
                      <p className="text-sm font-semibold text-gray-100">{formatCurrency(model.total_cost_usd)}</p>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-gray-400">
                      <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-3 py-2">
                        Operations
                        <div className="mt-1 text-sm font-medium text-gray-200">{formatNumber(model.count)}</div>
                      </div>
                      <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-3 py-2">
                        Tokens
                        <div className="mt-1 text-sm font-medium text-gray-200">
                          {formatNumber(model.total_tokens)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {modelDist.models.length === 0 ? (
                  <EmptyState
                    title="No model-level rows"
                    description="Once model metadata is present, this panel will break spend down by model and provider."
                  />
                ) : null}
              </div>
            </AnalyticsPanel>
          </div>
        </div>
      )}

      {activeSection === 'recommendations' && recommendations && (
        <AnalyticsPanel
          title="Cost optimization recommendations"
          description={`Suggestions generated from the last ${days} days of usage patterns.`}
        >
          {recommendations.recommendations.length > 0 ? (
            <div className="space-y-4">
              {recommendations.recommendations.map((recommendation, index) => {
                const priorityStyles =
                  recommendation.priority === 'high'
                    ? {
                        container: 'border-red-800/70 bg-red-950/30',
                        pill: 'border-red-500/30 bg-red-500/10 text-red-200',
                        savings: 'text-red-200',
                      }
                    : recommendation.priority === 'medium'
                      ? {
                          container: 'border-amber-800/70 bg-amber-950/30',
                          pill: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
                          savings: 'text-amber-200',
                        }
                      : {
                          container: 'border-blue-800/70 bg-blue-950/30',
                          pill: 'border-blue-500/30 bg-blue-500/10 text-blue-200',
                          savings: 'text-blue-200',
                        };

                return (
                  <div
                    key={`${recommendation.category}-${recommendation.title}-${index}`}
                    className={`rounded-2xl border p-4 ${priorityStyles.container}`}
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${priorityStyles.pill}`}>
                            {recommendation.priority}
                          </span>
                          <span className="text-xs uppercase tracking-wide text-gray-500">
                            {recommendation.category}
                          </span>
                        </div>
                        <h4 className="mt-3 text-base font-semibold text-white">{recommendation.title}</h4>
                        <p className="mt-2 text-sm leading-6 text-gray-300">{recommendation.description}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/10 px-4 py-3 text-right">
                        <p className="text-xs uppercase tracking-wide text-gray-500">Potential savings</p>
                        <p className={`mt-1 text-lg font-semibold ${priorityStyles.savings}`}>
                          {formatCurrency(recommendation.potential_savings_usd)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No optimization recommendations"
              description="Current usage looks balanced for the selected period, so there is nothing to flag right now."
            />
          )}
        </AnalyticsPanel>
      )}
    </div>
  );
}
