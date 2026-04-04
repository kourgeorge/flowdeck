/** All agents in pipeline order */
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
  /** Report keys that already exist on the server (from stockData.reports). */
  existingReportKeys?: string[];
  agentStatuses?: Record<string, string> | null;
  /** Current agent name from backend (e.g. "Market Analyst"). Shown as-is when analysis is running.
   * @deprecated Use currentAgents array instead for concurrent execution support */
  currentAgent?: string | null;
  /** Current agents array from backend (e.g. ["Market Analyst", "News Analyst"]). Shows multiple concurrent agents. */
  currentAgents?: string[] | null;
}

export default function AIAnalysisLoadingView({
  agentStatuses = null,
  currentAgent = null,
  currentAgents = null,
}: AIAnalysisLoadingViewProps) {
  // Support both old (currentAgent) and new (currentAgents) formats for backward compatibility
  const activeAgents = currentAgents && currentAgents.length > 0
    ? currentAgents
    : currentAgent
    ? [currentAgent]
    : [];

  const activeAgentSet = new Set(activeAgents);

  // Debug logging
  console.log('[AIAnalysisLoadingView] Render:', {
    currentAgent,
    currentAgents,
    activeAgents,
    agentStatuses,
    completedCount: Object.values(agentStatuses || {}).filter(s => s === 'completed').length,
    pendingCount: Object.values(agentStatuses || {}).filter(s => s === 'pending').length
  });

  return (
    <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        {ALL_AGENTS.map((agent, index) => {
          const status = agentStatuses?.[agent] || 'pending';
          const isActive = activeAgentSet.has(agent);
          const isCompleted = status === 'completed';
          
          return (
            <div key={agent} className="flex items-center gap-2">
              {/* Agent badge */}
              <div
                className={`
                  relative rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-300
                  ${isActive
                    ? 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-400/50 animate-pulse'
                    : isCompleted
                    ? 'bg-green-500/20 text-green-300 ring-1 ring-green-400/30'
                    : 'bg-gray-700/30 text-gray-500'
                  }
                `}
              >
                {/* Status indicator dot */}
                <span className={`
                  absolute -left-1 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full
                  ${isActive
                    ? 'bg-blue-400 animate-ping'
                    : isCompleted
                    ? 'bg-green-400'
                    : 'bg-gray-600'
                  }
                `} />
                <span className={`
                  absolute -left-1 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full
                  ${isActive
                    ? 'bg-blue-400'
                    : isCompleted
                    ? 'bg-green-400'
                    : 'bg-gray-600'
                  }
                `} />
                {agent}
              </div>
              
              {/* Arrow connector (except for last item) */}
              {index < ALL_AGENTS.length - 1 && (
                <svg
                  className={`h-4 w-4 shrink-0 transition-colors duration-300 ${
                    isCompleted ? 'text-green-400/50' : 'text-gray-600'
                  }`}
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
      
      {/* Progress summary */}
      <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
          <span>Running: {activeAgents.length}</span>
        </div>
        <span className="text-gray-600">•</span>
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
          <span>Completed: {Object.values(agentStatuses || {}).filter(s => s === 'completed').length}</span>
        </div>
        <span className="text-gray-600">•</span>
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-gray-600" />
          <span>Pending: {Object.values(agentStatuses || {}).filter(s => s === 'pending').length}</span>
        </div>
      </div>
    </div>
  );
}
