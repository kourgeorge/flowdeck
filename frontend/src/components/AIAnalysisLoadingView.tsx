import { useState, useEffect, useRef } from 'react';


/** Report keys in pipeline order (matches server writing order). */
const REPORT_ORDER = [
  'market_report',
  // 'sentiment_report',
  'news_report',
  'fundamentals_report',
  'technical_report',
  'sec_report',
  'investment_plan',
  'trader_investment_plan',
  'final_trade_decision',
] as const;

/** Short “doing” label per report (from server JSON files). */
const REPORT_LABELS: Record<string, string> = {
  market_report: 'Analyzing Market...',
  sentiment_report: 'Analyzing indicators…',
  news_report: 'Reviewing news…',
  fundamentals_report: 'Evaluating fundamentals…',
  technical_report: 'Running technical analysis…',
  sec_report: 'Analyzing SEC filings…',
  investment_plan: 'Running bull vs bear debate…',
  trader_investment_plan: 'Translating to trading plan…',
  final_trade_decision: 'Finalizing decision…',
};

/** Fallback when no report keys yet. */
const FALLBACK_PHRASES = [
  'Starting analysis…',
  'Fetching market data…',
  'Loading data…',
];

interface AIAnalysisLoadingViewProps {
  /** Report keys that already exist on the server (from stockData.reports). */
  existingReportKeys?: string[];
  agentStatuses?: Record<string, string> | null;
  currentAgent?: string | null;
}

export default function AIAnalysisLoadingView({
  existingReportKeys = [],
}: AIAnalysisLoadingViewProps) {
  const completedCount = REPORT_ORDER.filter((k) => existingReportKeys.includes(k)).length;
  const nextKey = REPORT_ORDER.find((k) => !existingReportKeys.includes(k));
  const totalSteps = REPORT_ORDER.length;

  const statusMessage =
    nextKey != null
      ? REPORT_LABELS[nextKey] ?? 'Processing…'
      : completedCount >= totalSteps
        ? 'Almost there…'
        : null;
  const fallbackIndex = completedCount % FALLBACK_PHRASES.length;
  const displayMessage =
    statusMessage ?? FALLBACK_PHRASES[fallbackIndex];

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

  const progressLabel =
    completedCount > 0 && completedCount < totalSteps
      ? `${completedCount} of ${totalSteps} reports ready`
      : null;

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
        {progressLabel && (
          <p className="mt-0.5 text-xs text-gray-500">{progressLabel}</p>
        )}
      </div>
    </div>
  );
}
