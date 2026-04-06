import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  type AdminStats,
  type AdminAnalysisItem,
  type AdminReportItem,
  type AnalysisDailyCount,
  type ViewsDailyCount,
  adminApi,
} from '../../services/adminApi';
import { formatDate } from './adminUtils';
import DailyBarChart from './DailyBarChart';

interface OverviewTabProps {
  stats: AdminStats | null;
  dailyAnalyses: AnalysisDailyCount[];
  dailyViews: ViewsDailyCount[];
  analyses: AdminAnalysisItem[];
  analysesTotal: number;
  filteredAnalyses: AdminAnalysisItem[];
  analysisTickerFilter: string;
  analysisCreatorFilter: string;
  setAnalysisTickerFilter: (value: string) => void;
  setAnalysisCreatorFilter: (value: string) => void;
  loadingMoreAnalyses: boolean;
  reports: AdminReportItem[];
  reportsTotal: number;
  latestReportsCollapsed: boolean;
  setLatestReportsCollapsed: (value: boolean | ((prev: boolean) => boolean)) => void;
  openReportDetail: (report: AdminReportItem) => void;
  onDownloadAnalysis: (analysisRunId: number) => Promise<void>;
  downloadingAnalysisIds: Set<number>;
  setStats: (stats: AdminStats) => void;
  setAnalyses: (analyses: AdminAnalysisItem[]) => void;
  setAnalysesTotal: (total: number) => void;
  setReports: (reports: AdminReportItem[]) => void;
  setReportsTotal: (total: number) => void;
  analysesContainerRef: React.RefObject<HTMLDivElement>;
}

export default function OverviewTab({
  stats,
  dailyAnalyses,
  dailyViews,
  analyses,
  analysesTotal,
  filteredAnalyses,
  analysisTickerFilter,
  analysisCreatorFilter,
  setAnalysisTickerFilter,
  setAnalysisCreatorFilter,
  loadingMoreAnalyses,
  reports,
  reportsTotal,
  latestReportsCollapsed,
  setLatestReportsCollapsed,
  openReportDetail,
  onDownloadAnalysis,
  downloadingAnalysisIds,
  setStats,
  setAnalyses,
  setAnalysesTotal,
  setReports,
  setReportsTotal,
  analysesContainerRef,
}: OverviewTabProps) {
  return (
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
                <Fragment key={a.id}>
                  <tr className="border-b border-gray-700/50">
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
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => void onDownloadAnalysis(a.id)}
                          disabled={downloadingAnalysisIds.has(a.id)}
                          className="text-blue-400 hover:text-blue-300 hover:underline text-sm font-medium disabled:cursor-not-allowed disabled:text-gray-500"
                        >
                          {downloadingAnalysisIds.has(a.id) ? 'Downloading…' : 'Download'}
                        </button>
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
                      </div>
                    </td>
                  </tr>
                  {a.status === 'failed' && a.error_message && (
                    <tr className="border-b border-gray-700/50 bg-red-900/10">
                      <td colSpan={10} className="px-4 py-2">
                        <div className="flex items-start gap-2">
                          <span className="text-red-400 font-medium text-xs">Error:</span>
                          <span className="text-red-300 text-xs break-all">{a.error_message}</span>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
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
  );
}

// Made with Bob
