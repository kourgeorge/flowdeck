
/** Special virtual tab key for the AI chat panel */
export const CHAT_TAB_KEY = '__chat__';

interface ReportScore {
  score: number | null;
  score_label: string | null;
}

interface ReportTabsProps {
  availableReports: string[];
  selectedReport: string | null;
  onSelectReport: (reportType: string) => void;
  reportScores?: Record<string, ReportScore>;
  /** Whether to show the Chat tab at the end */
  showChatTab?: boolean;
}

export default function ReportTabs({ availableReports, selectedReport, onSelectReport, reportScores, showChatTab }: ReportTabsProps) {
  const allTabs = showChatTab ? [...availableReports, CHAT_TAB_KEY] : availableReports;

  const activeTab = selectedReport && allTabs.includes(selectedReport)
    ? selectedReport
    : (availableReports.length > 0 ? availableReports[0] : null);

  const handleTabClick = (reportType: string) => {
    onSelectReport(reportType);
  };

  // Custom labels for AI analysis tabs and plan names
  const REPORT_LABELS: Record<string, string> = {
    market_report: 'Market',
    fundamentals_report: 'Fundamentals',
    technical_report: 'Technical',
    news_report: 'News',
    sec_report: 'SEC',
    investment_plan: 'Research',
    trader_investment_plan: 'Trader',
    final_trade_decision: 'Risk Analysis',
  };

  const formatReportName = (name: string) => {
    if (name === CHAT_TAB_KEY) return 'Chat';
    if (REPORT_LABELS[name]) return REPORT_LABELS[name];
    return name
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getScoreColor = (score: number | null): string => {
    if (score === null) return 'text-gray-400';
    if (score <= 3) return 'text-red-400';
    if (score <= 5) return 'text-yellow-400';
    if (score <= 7) return 'text-blue-400';
    return 'text-green-400';
  };

  if (availableReports.length === 0 && !showChatTab) {
    return null;
  }

  return (
    <div className="border-b border-slate-700 mb-6">
      <div className="flex flex-wrap gap-0.5">
        {availableReports.map((reportType) => {
          const scoreData = reportScores?.[reportType];
          const score = scoreData?.score;

          return (
            <button
              key={reportType}
              onClick={() => handleTabClick(reportType)}
              className={`
                px-2 py-1.5 text-sm font-medium transition-colors flex items-center gap-1
                ${
                  activeTab === reportType
                    ? 'border-b-2 border-blue-500 text-blue-400'
                    : 'text-slate-400 hover:text-slate-300'
                }
              `}
            >
              <span>{formatReportName(reportType)}</span>
              {score !== null && score !== undefined && (
                <span className={`text-xs font-bold ${getScoreColor(score)}`}>
                  {score}/10
                </span>
              )}
            </button>
          );
        })}

        {showChatTab && (
          <button
            onClick={() => handleTabClick(CHAT_TAB_KEY)}
            className={`
              px-2 py-1.5 text-sm font-medium transition-colors flex items-center gap-1.5 ml-1
              ${
                activeTab === CHAT_TAB_KEY
                  ? 'border-b-2 border-blue-500 text-blue-400'
                  : 'text-slate-400 hover:text-slate-300'
              }
            `}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
            <span>Chat</span>
          </button>
        )}
      </div>
    </div>
  );
}
