import type { AnalysisLiveActivity } from '../services/types';

const ALL_AGENTS = [
  'Market Analyst',
  'Social Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Technical Analyst',
  'SEC Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Research Manager',
  'Trader',
  'Risky Analyst',
  'Safe Analyst',
  'Neutral Analyst',
  'Portfolio Manager',
] as const;

interface AIAnalysisLoadingViewProps {
  existingReportKeys?: string[];
  agentStatuses?: Record<string, string> | null;
  currentAgent?: string | null;
  currentAgents?: string[] | null;
  liveActivities?: AnalysisLiveActivity[] | null;
}

function prettifyToken(value: string | null | undefined): string {
  if (!value) return '';
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function getActivityTone(kind: string | null | undefined): string {
  switch (kind) {
    case 'tool_call':
      return 'border-cyan-400/30 bg-cyan-500/10 text-cyan-200';
    case 'tool_result':
      return 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200';
    case 'report_synthesis':
      return 'border-violet-400/30 bg-violet-500/10 text-violet-200';
    case 'status':
      return 'border-amber-400/30 bg-amber-500/10 text-amber-200';
    default:
      return 'border-slate-600/80 bg-slate-800/70 text-slate-200';
  }
}

function getActivityGlyph(kind: string | null | undefined): string {
  switch (kind) {
    case 'tool_call':
      return 'Tool';
    case 'tool_result':
      return 'Data';
    case 'report_synthesis':
      return 'Draft';
    case 'status':
      return 'State';
    default:
      return 'Think';
  }
}

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return '';
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return '';
  const diffSeconds = Math.max(0, Math.floor((Date.now() - parsed) / 1000));
  if (diffSeconds < 5) return 'just now';
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  return `${diffHours}h ago`;
}

function getLatestAgentActivity(
  liveActivities: AnalysisLiveActivity[] | null | undefined,
  agent: string,
): AnalysisLiveActivity | null {
  if (!liveActivities?.length) return null;
  for (let index = liveActivities.length - 1; index >= 0; index -= 1) {
    const activity = liveActivities[index];
    if (activity.agent === agent) {
      return activity;
    }
  }
  return null;
}

export default function AIAnalysisLoadingView({
  existingReportKeys = [],
  agentStatuses = null,
  currentAgent = null,
  currentAgents = null,
  liveActivities = null,
}: AIAnalysisLoadingViewProps) {
  const activeAgents = currentAgents && currentAgents.length > 0
    ? currentAgents
    : currentAgent
    ? [currentAgent]
    : [];
  const activeAgentSet = new Set(activeAgents);
  const completedCount = Object.values(agentStatuses || {}).filter((status) => status === 'completed').length;
  const pendingCount = ALL_AGENTS.length - completedCount - activeAgents.length;
  const recentActivities = (liveActivities || []).slice(-8).reverse();

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-900/90 shadow-[0_20px_60px_-32px_rgba(56,189,248,0.45)]">
      <div className="border-b border-slate-700 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_45%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.16),_transparent_38%)] px-5 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300/80">Live Analysis</p>
            <h3 className="mt-1 text-lg font-semibold text-white">Agents are working through the pipeline</h3>
            <p className="mt-1 max-w-2xl text-sm text-slate-400">
              Live operations below are streamed from the active analysis run: thinking, tool calls, tool results, and report synthesis.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div className="rounded-xl border border-sky-400/20 bg-sky-500/10 px-3 py-2 text-sky-100">
              <div className="text-[11px] uppercase tracking-wide text-sky-300/75">Running</div>
              <div className="mt-1 text-lg font-semibold">{activeAgents.length}</div>
            </div>
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-emerald-100">
              <div className="text-[11px] uppercase tracking-wide text-emerald-300/75">Completed</div>
              <div className="mt-1 text-lg font-semibold">{completedCount}</div>
            </div>
            <div className="rounded-xl border border-slate-600 bg-slate-800/80 px-3 py-2 text-slate-100">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">Pending</div>
              <div className="mt-1 text-lg font-semibold">{Math.max(pendingCount, 0)}</div>
            </div>
            <div className="rounded-xl border border-violet-400/20 bg-violet-500/10 px-3 py-2 text-violet-100">
              <div className="text-[11px] uppercase tracking-wide text-violet-300/75">Reports Ready</div>
              <div className="mt-1 text-lg font-semibold">{existingReportKeys.length}</div>
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(activeAgents.length > 0 ? activeAgents : ['Pipeline']).map((agent) => {
            const latestActivity = agent === 'Pipeline' ? recentActivities[0] ?? null : getLatestAgentActivity(liveActivities, agent);
            return (
              <div
                key={agent}
                className="relative overflow-hidden rounded-2xl border border-sky-400/20 bg-slate-950/70 px-4 py-4"
              >
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-sky-300/70 to-transparent" />
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400/60" />
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-300" />
                      </span>
                      <span className="text-sm font-semibold text-white">{agent}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-300">
                      {latestActivity?.summary || 'Preparing the next operation'}
                    </p>
                  </div>
                  <span className="rounded-full border border-sky-400/20 bg-sky-500/10 px-2 py-1 text-[11px] uppercase tracking-wide text-sky-200">
                    {prettifyToken(latestActivity?.kind || 'running')}
                  </span>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full w-2/3 animate-pulse rounded-full bg-gradient-to-r from-sky-500 via-cyan-300 to-sky-500" />
                  </div>
                  <div className="flex gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                      <div className="h-full w-1/2 animate-pulse rounded-full bg-slate-500/70" />
                    </div>
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-800">
                      <div className="h-full w-3/4 animate-pulse rounded-full bg-slate-500/50" />
                    </div>
                  </div>
                </div>
                {latestActivity?.tool_name && (
                  <div className="mt-3 text-xs text-slate-400">
                    Tool: <span className="font-mono text-cyan-300">{latestActivity.tool_name}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="px-5 py-5">
        <div className="flex flex-wrap items-center gap-2">
          {ALL_AGENTS.map((agent, index) => {
            const status = agentStatuses?.[agent] || 'pending';
            const isActive = activeAgentSet.has(agent);
            const isCompleted = status === 'completed';

            return (
              <div key={agent} className="flex items-center gap-2">
                <div
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    isActive
                      ? 'border-sky-400/40 bg-sky-500/15 text-sky-200'
                      : isCompleted
                      ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200'
                      : 'border-slate-700 bg-slate-800/80 text-slate-500'
                  }`}
                >
                  {agent}
                </div>
                {index < ALL_AGENTS.length - 1 && (
                  <svg
                    className={`h-4 w-4 shrink-0 ${isCompleted ? 'text-emerald-400/50' : 'text-slate-700'}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-5 rounded-2xl border border-slate-700 bg-slate-950/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-white">Live Operations</h4>
              <p className="mt-1 text-xs text-slate-400">Recent backend events from the running analysis</p>
            </div>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-2.5 py-1 text-[11px] uppercase tracking-wide text-slate-400">
              {recentActivities.length} visible
            </span>
          </div>

          {recentActivities.length > 0 ? (
            <ol className="mt-4 space-y-3">
              {recentActivities.map((activity) => (
                <li
                  key={activity.id || `${activity.agent || 'agent'}-${activity.summary || 'step'}-${activity.captured_at || ''}`}
                  className={`rounded-xl border px-3 py-3 ${getActivityTone(activity.kind)}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-current/20 bg-black/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide">
                          {getActivityGlyph(activity.kind)}
                        </span>
                        {activity.agent && (
                          <span className="text-xs font-medium text-white">{activity.agent}</span>
                        )}
                        {activity.tool_name && (
                          <span className="font-mono text-xs opacity-90">{activity.tool_name}</span>
                        )}
                      </div>
                      <p className="mt-2 text-sm leading-5 text-white">{activity.summary}</p>
                      {activity.detail && (
                        <p className="mt-1 text-xs leading-5 opacity-80">{activity.detail}</p>
                      )}
                    </div>
                    <div className="shrink-0 text-[11px] uppercase tracking-wide opacity-70">
                      {formatRelativeTime(activity.captured_at)}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-500">
              Waiting for the first streamed operation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
