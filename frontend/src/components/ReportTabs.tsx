
interface ReportScore {
  score: number | null;
  score_label: string | null;
}

interface ReportTabsProps {
  availableReports: string[];
  selectedReport: string | null;
  onSelectReport: (reportType: string) => void;
  reportScores?: Record<string, ReportScore>;
}

export default function ReportTabs({ availableReports, selectedReport, onSelectReport, reportScores }: ReportTabsProps) {
  const activeTab = selectedReport && availableReports.includes(selectedReport)
    ? selectedReport
    : (availableReports.length > 0 ? availableReports[0] : null);

  const handleTabClick = (reportType: string) => {
    onSelectReport(reportType);
  };

  // Custom labels for AI analysis tabs and plan names
  const REPORT_LABELS: Record<string, string> = {
    market_report: 'Market',
    fundamentals_report: 'Fundamentals',
    news_report: 'News',
    sec_report: 'SEC',
    investment_plan: 'Research',
    final_trade_decision: 'Thesis',
  };

  const formatReportName = (name: string) => {
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

  if (availableReports.length === 0) {
    return null;
  }

  return (
    <div className="border-b border-slate-700 mb-6">
      <div className="flex flex-wrap gap-2">
        {availableReports.map((reportType) => {
          const scoreData = reportScores?.[reportType];
          const score = scoreData?.score;
          
          return (
            <button
              key={reportType}
              onClick={() => handleTabClick(reportType)}
              className={`
                px-4 py-2 font-medium transition-colors flex items-center gap-2
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
      </div>
    </div>
  );
}

