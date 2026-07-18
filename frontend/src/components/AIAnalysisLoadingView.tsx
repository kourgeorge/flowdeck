import type { AnalysisLiveActivity, AnalysisTraceStep } from '../services/types';

const ALL_AGENTS = [
  'Market Analyst',
  'News & Sentiment Analyst',
  'Fundamentals Analyst',
  'Technical Analyst',
  'SEC Analyst',
  'Valuation Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Neutral Researcher',
  'Research Manager',
  'Trader',
] as const;

interface AIAnalysisLoadingViewProps {
  existingReportKeys?: string[];
  agentStatuses?: Record<string, string> | null;
  currentAgent?: string | null;
  currentAgents?: string[] | null;
  liveActivities?: AnalysisLiveActivity[] | null;
  liveTrace?: AnalysisTraceStep[] | null;
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

export default function AIAnalysisLoadingView({
  existingReportKeys = [],
  agentStatuses = null,
  currentAgent = null,
  currentAgents = null,
  liveActivities = null,
  liveTrace = null,
}: AIAnalysisLoadingViewProps) {
  const activeAgents = currentAgents && currentAgents.length > 0
    ? currentAgents
    : currentAgent
    ? [currentAgent]
    : [];
  const activeAgentSet = new Set(activeAgents);
  const completedCount = Object.values(agentStatuses || {}).filter((status) => status === 'completed').length;
  // Show only the agents that are actually part of this run. The backend seeds
  // agentStatuses with just the relevant agents (e.g. SEC/Fundamentals analysts are
  // excluded for ETFs), so derive the chip list from it and keep the canonical order.
  const displayAgents = agentStatuses && Object.keys(agentStatuses).length > 0
    ? ALL_AGENTS.filter((agent) => agent in agentStatuses)
    : ALL_AGENTS;
  const pendingCount = displayAgents.length - completedCount - activeAgents.length;
  
  // Use live trace if available (shows complete tool sequence), otherwise fall back to activities
  const displayItems = liveTrace && liveTrace.length > 0
    ? liveTrace.slice(-50)
    : (liveActivities || []).slice(-20);
  const isUsingTrace = liveTrace && liveTrace.length > 0;

  // Group items by agent
  const agentGroups = displayItems.reduce((groups, item) => {
    const isLiveActivity = 'detail' in item;
    const agent = isLiveActivity ? (item as AnalysisLiveActivity).agent : (item as AnalysisTraceStep).agent;
    const agentName = agent || 'Unknown Agent';
    
    if (!groups[agentName]) {
      groups[agentName] = [];
    }
    groups[agentName].push(item);
    return groups;
  }, {} as Record<string, (AnalysisLiveActivity | AnalysisTraceStep)[]>);

  activeAgents.forEach((agentName) => {
    if (!agentGroups[agentName]) {
      agentGroups[agentName] = [];
    }
  });

  const sortedAgents = Object.keys(agentGroups).sort((a, b) => {
    // Maintain the original order from ALL_AGENTS array
    const aIndex = ALL_AGENTS.indexOf(a as typeof ALL_AGENTS[number]);
    const bIndex = ALL_AGENTS.indexOf(b as typeof ALL_AGENTS[number]);
    
    // If both agents are in ALL_AGENTS, sort by their original order
    if (aIndex !== -1 && bIndex !== -1) {
      return aIndex - bIndex;
    }
    
    // If only one is in ALL_AGENTS, prioritize it
    if (aIndex !== -1) return -1;
    if (bIndex !== -1) return 1;
    
    // For agents not in ALL_AGENTS (e.g., "Unknown Agent"), sort alphabetically
    return a.localeCompare(b);
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300/80">Live Analysis</p>
          <h3 className="mt-1 text-lg font-semibold text-white">Multi-Agent Analysis Running</h3>
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

      <div className="flex flex-wrap items-center gap-2">
          {displayAgents.map((agent, index) => {
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
                {index < displayAgents.length - 1 && (
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

      <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-white">Agent Activity</h4>
              <p className="mt-1 text-xs text-slate-400">
                {isUsingTrace
                  ? 'Tool calls and results grouped by agent'
                  : 'Recent operations grouped by agent'}
              </p>
            </div>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-2.5 py-1 text-[11px] uppercase tracking-wide text-slate-400">
              {sortedAgents.length} agents
            </span>
          </div>

          {sortedAgents.length > 0 ? (
            <div className="mt-4 space-y-3">
              {sortedAgents.map((agentName) => {
                const agentItems = agentGroups[agentName];
                const toolCount = agentItems.filter((item: AnalysisLiveActivity | AnalysisTraceStep) => {
                  const isLiveActivity = 'detail' in item;
                  return isLiveActivity
                    ? (item as AnalysisLiveActivity).tool_name
                    : (item as AnalysisTraceStep).tool_name;
                }).length;

                // Check if agent is currently active
                const agentStatus = agentStatuses?.[agentName];
                const isActive = activeAgentSet.has(agentName);
                const isCompleted = agentStatus === 'completed';

                return (
                  <details key={agentName} className="overflow-hidden rounded-xl border border-sky-400/30 bg-slate-900/70">
                    <summary className="cursor-pointer list-none px-4 py-3 hover:bg-sky-500/5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          {isActive ? (
                            <span className="relative flex h-2 w-2">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400/60" />
                              <span className="relative inline-flex h-2 w-2 rounded-full bg-sky-300" />
                            </span>
                          ) : isCompleted ? (
                            <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
                          ) : (
                            <span className="flex h-2 w-2 rounded-full bg-slate-600" />
                          )}
                          <h5 className="text-sm font-semibold text-white">{agentName}</h5>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="rounded-full border border-slate-600 bg-slate-800/80 px-2 py-1 text-[11px] text-slate-300">
                            {agentItems.length} steps
                          </span>
                          <span className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[11px] text-cyan-200">
                            {toolCount} tools
                          </span>
                          <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </summary>
                    <div className="border-t border-slate-700/50 bg-slate-950/30 px-4 py-3">
                      {agentItems.length > 0 ? (
                        <ol className="space-y-2">
                          {(() => {
                            const pairedItems: JSX.Element[] = [];
                            let skipNext = false;

                            agentItems.forEach((item, idx) => {
                              if (skipNext) {
                                skipNext = false;
                                return;
                              }

                              const isLiveActivity = 'detail' in item;
                              const traceStep = item as AnalysisTraceStep;
                              const activity = isLiveActivity ? item as AnalysisLiveActivity : {
                                id: undefined,
                                agent: traceStep.agent || null,
                                kind: traceStep.kind || null,
                                status: traceStep.status || null,
                                summary: traceStep.summary || (traceStep.tool_name ? `Called ${traceStep.tool_name}` : 'Processing'),
                                detail: traceStep.message_preview || traceStep.observation_preview || traceStep.output_preview || null,
                                tool_name: traceStep.tool_name || null,
                                captured_at: traceStep.captured_at || null,
                              };
                              const toolArgs = !isLiveActivity ? traceStep.tool_args : null;

                              if (activity.kind === 'status' && activity.summary?.toLowerCase().includes('started')) {
                                return;
                              }

                              let resultActivity = null;
                              if (activity.kind === 'tool_call' && idx + 1 < agentItems.length) {
                                const nextItem = agentItems[idx + 1];
                                const nextIsLiveActivity = 'detail' in nextItem;
                                const nextActivity = nextIsLiveActivity ? nextItem as AnalysisLiveActivity : {
                                  kind: (nextItem as AnalysisTraceStep).kind || null,
                                  tool_name: (nextItem as AnalysisTraceStep).tool_name || null,
                                  detail: (nextItem as AnalysisTraceStep).message_preview || (nextItem as AnalysisTraceStep).observation_preview || (nextItem as AnalysisTraceStep).output_preview || null,
                                };

                                if (nextActivity.kind === 'tool_result' && nextActivity.tool_name === activity.tool_name) {
                                  resultActivity = nextActivity;
                                  skipNext = true;
                                }
                              }

                              pairedItems.push(
                                <li key={`${agentName}-${idx}`} className={`rounded-lg border px-2 py-2 text-xs ${getActivityTone(activity.kind)}`}>
                                  <div className="flex items-center gap-2">
                                    <span className="rounded border border-current/20 bg-black/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase">
                                      {getActivityGlyph(activity.kind)}
                                    </span>
                                    {activity.tool_name && (
                                      <span className="font-mono font-semibold">🔧 {activity.tool_name}</span>
                                    )}
                                    {!activity.tool_name && activity.summary && (
                                      <span>{activity.summary}</span>
                                    )}
                                  </div>
                                  {toolArgs != null && (
                                    <div className="mt-1.5 border-t border-current/10 pt-1.5 text-[11px] opacity-75">
                                      <div className="mb-1 text-[10px] font-semibold uppercase opacity-60">Parameters</div>
                                      <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-black/20 px-2 py-1 font-mono text-[10px]">
                                        {JSON.stringify(toolArgs, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                  {toolArgs == null && activity.detail && (
                                    <div className="mt-1.5 border-t border-current/10 pt-1.5 text-[11px] opacity-75">
                                      <div className="mb-1 text-[10px] font-semibold uppercase opacity-60">Request</div>
                                      <div>{activity.detail.substring(0, 150)}{activity.detail.length > 150 ? '...' : ''}</div>
                                    </div>
                                  )}
                                  {resultActivity?.detail && (
                                    <div className="mt-1.5 border-t border-emerald-400/20 pt-1.5 text-[11px] text-emerald-200/90">
                                      <div className="mb-1 text-[10px] font-semibold uppercase opacity-60">Response</div>
                                      <div>{resultActivity.detail.substring(0, 150)}{resultActivity.detail.length > 150 ? '...' : ''}</div>
                                    </div>
                                  )}
                                </li>
                              );
                            });

                            return pairedItems;
                          })()}
                        </ol>
                      ) : (
                        <div className="rounded-lg border border-dashed border-slate-700 px-3 py-4 text-xs text-slate-400">
                          Waiting for live activity...
                        </div>
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-500">
              No agent activity yet.
            </div>
        )}
      </div>
    </div>
  );
}
