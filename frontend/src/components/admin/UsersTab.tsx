import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  type AdminStats,
  type AdminUserItem,
  type AdminSubscriptionItem,
  type AdminReportViewRunItem,
  type AdminReportViewItem,
  adminApi,
} from '../../services/adminApi';
import { formatDate } from './adminUtils';

type ViewRunsSortKey = 'ticker' | 'analysis_run_id' | 'unique_views' | 'viewed';
type ViewRunsSortDirection = 'asc' | 'desc';

interface SubscriptionsByUser {
  user_id: number;
  user_email: string;
  subscriptions: AdminSubscriptionItem[];
}

interface UsersTabProps {
  users: AdminUserItem[];
  usersTotal: number;
  addTokensError: string | null;
  setAddTokensError: (error: string | null) => void;
  addAmountByUser: Record<number, string>;
  setAddAmountByUser: React.Dispatch<React.SetStateAction<Record<number, string>>>;
  addingForUserId: number | null;
  setAddingForUserId: (id: number | null) => void;
  setUsers: React.Dispatch<React.SetStateAction<AdminUserItem[]>>;
  stats: AdminStats | null;
  viewRuns: AdminReportViewRunItem[];
  viewRunsTotal: number;
  sortedViewRuns: AdminReportViewRunItem[];
  viewsByRun: Record<string, AdminReportViewItem[]>;
  expandedViewRunKeys: Set<string>;
  loadingRunViewKeys: Set<string>;
  toggleRunExpanded: (ticker: string, analysisRunId: number) => void;
  getSortedRunViews: (runViews: AdminReportViewItem[]) => AdminReportViewItem[];
  viewRunsSort: { key: ViewRunsSortKey; direction: ViewRunsSortDirection };
  toggleViewRunsSort: (key: ViewRunsSortKey) => void;
  viewRunsSortIndicator: (key: ViewRunsSortKey) => string;
  subscriptionsByUser: SubscriptionsByUser[];
  subscriptionsTotal: number;
  expandedSubscriptionUserIds: Set<number>;
  setExpandedSubscriptionUserIds: React.Dispatch<React.SetStateAction<Set<number>>>;
}

export default function UsersTab({
  users,
  usersTotal,
  addTokensError,
  setAddTokensError,
  addAmountByUser,
  setAddAmountByUser,
  addingForUserId,
  setAddingForUserId,
  setUsers,
  stats,
  viewRuns,
  viewRunsTotal,
  sortedViewRuns,
  viewsByRun,
  expandedViewRunKeys,
  loadingRunViewKeys,
  toggleRunExpanded,
  getSortedRunViews,
  toggleViewRunsSort,
  viewRunsSortIndicator,
  subscriptionsByUser,
  subscriptionsTotal,
  expandedSubscriptionUserIds,
  setExpandedSubscriptionUserIds,
}: UsersTabProps) {
  return (
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
  );
}

// Made with Bob
