import { useState, useEffect, useRef } from 'react';

/** Report keys in pipeline order (for stage count). */
const REPORT_ORDER = [
  'market_report',
  'sentiment_report',
  'news_report',
  'fundamentals_report',
  'technical_report',
  'sec_report',
  'investment_plan',
  'trader_investment_plan',
  'final_trade_decision',
] as const;

const TOTAL_STAGES = REPORT_ORDER.length;

interface AIAnalysisLoadingViewProps {
  /** Report keys that already exist on the server (from stockData.reports). */
  existingReportKeys?: string[];
  agentStatuses?: Record<string, string> | null;
  /** Current agent name from backend (e.g. "Market Analyst"). Shown as-is when analysis is running. */
  currentAgent?: string | null;
}

export default function AIAnalysisLoadingView({
  existingReportKeys = [],
  currentAgent = null,
}: AIAnalysisLoadingViewProps) {
  const completedCount = REPORT_ORDER.filter((k) => existingReportKeys.includes(k)).length;
  const currentStage = Math.min(completedCount + 1, TOTAL_STAGES);
  const stageLabel = `${currentStage}/${TOTAL_STAGES}`;

  const agentMessage =
    currentAgent != null && currentAgent !== ''
      ? currentAgent
      : 'Running analysis…';
  const displayMessage = `${agentMessage} · ${stageLabel}`;

  const [opacity, setOpacity] = useState(1);
  const [shownMessage, setShownMessage] = useState(displayMessage);
  const prevMessageRef = useRef(displayMessage);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (displayMessage === prevMessageRef.current) return;
    setOpacity(0);
    timeoutRef.current = window.setTimeout(() => {
      prevMessageRef.current = displayMessage;
      setShownMessage(displayMessage);
      setOpacity(1);
      timeoutRef.current = null;
    }, 280);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [displayMessage]);

  return (
    <div className="flex items-center gap-3 rounded-lg border border-blue-500/30 bg-blue-500/5 px-5 py-4">
      <div className="flex shrink-0 items-center gap-1">
        <span className="h-2 w-2 animate-[analysis-dot_1.4s_ease-in-out_infinite] rounded-full bg-blue-400" />
        <span className="h-2 w-2 animate-[analysis-dot_1.4s_ease-in-out_0.2s_infinite] rounded-full bg-blue-400" />
        <span className="h-2 w-2 animate-[analysis-dot_1.4s_ease-in-out_0.4s_infinite] rounded-full bg-blue-400" />
      </div>
      <style>{`
        @keyframes analysis-dot {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
      `}</style>
      <div className="min-w-0 flex-1">
        <p
          className="text-sm text-gray-300 transition-opacity duration-300"
          style={{ opacity }}
        >
          {shownMessage}
        </p>
      </div>
    </div>
  );
}
