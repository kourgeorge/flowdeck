import { Link } from 'react-router-dom';
import {
  type MissionControlTickerItem,
  type RunningAnalysisItem,
} from '../../services/adminApi';
import { formatDate, formatMarketCap } from './adminUtils';

type MissionSortKey = 'ticker' | 'company' | 'type' | 'market_cap' | 'sector' | 'industry' | 'last_completed' | 'reports' | 'status' | 'priority' | 'subscriptions';
type MissionSortDirection = 'asc' | 'desc';

interface MissionControlTabProps {
  runningAnalyses: RunningAnalysisItem[];
  runningAnalysesLoading: boolean;
  missionLoading: boolean;
  stoppingRunId: number | null;
  handleStopRunningAnalysis: (runId: number) => Promise<void>;
  missionTickerFilter: string;
  setMissionTickerFilter: (value: string) => void;
  refreshMissionControl: () => Promise<void>;
  missionForceRerun: boolean;
  setMissionForceRerun: (value: boolean) => void;
  selectedMissionTickers: string[];
  setSelectedMissionTickers: React.Dispatch<React.SetStateAction<string[]>>;
  missionBulkRunning: boolean;
  setMissionBulkRunning: (value: boolean) => void;
  runMissionForTickers: (tickers: string[], forceOverride?: boolean) => Promise<void>;
  missionActionInfo: string | null;
  missionActionError: string | null;
  missionError: string | null;
  sortedMissionItems: MissionControlTickerItem[];
  missionItems: MissionControlTickerItem[];
  selectedMissionTickerSet: Set<string>;
  allMissionTickers: string[];
  allMissionSelected: boolean;
  missionSort: { key: MissionSortKey; direction: MissionSortDirection };
  toggleMissionSort: (key: MissionSortKey) => void;
  sortIndicator: (key: MissionSortKey) => string;
  missionRunningForTicker: string | null;
  setMissionRunningForTicker: (ticker: string | null) => void;
}

export default function MissionControlTab({
  runningAnalyses,
  runningAnalysesLoading,
  missionLoading,
  stoppingRunId,
  handleStopRunningAnalysis,
  missionTickerFilter,
  setMissionTickerFilter,
  refreshMissionControl,
  missionForceRerun,
  setMissionForceRerun,
  selectedMissionTickers,
  setSelectedMissionTickers,
  missionBulkRunning,
  setMissionBulkRunning,
  runMissionForTickers,
  missionActionInfo,
  missionActionError,
  missionError,
  sortedMissionItems,
  missionItems,
  selectedMissionTickerSet,
  allMissionTickers,
  allMissionSelected,
  toggleMissionSort,
  sortIndicator,
  missionRunningForTicker,
  setMissionRunningForTicker,
}: MissionControlTabProps) {
  return (
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
                    <td className="px-3 py-2 text-gray-300">
                      {r.current_agents && r.current_agents.length > 0
                        ? r.current_agents.length === 1
                          ? r.current_agents[0]
                          : `${r.current_agents[0]} +${r.current_agents.length - 1}`
                        : r.current_agent ?? '—'}
                    </td>
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
  );
}

// Made with Bob
