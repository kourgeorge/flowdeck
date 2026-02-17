import type { RefObject } from 'react';
import { useNavigate } from 'react-router-dom';
import type { StockWidget as StockWidgetType } from '../services/types';
import { parseReportDate } from '../utils/date';

/** Fixed height for all stock tables; overflow scrolls inside. */
const STOCK_TABLE_HEIGHT = '700px';

interface StockListViewProps {
  widgets: StockWidgetType[];
  tickerToName: Record<string, string>;
  /** Optional ref for the scroll container (e.g. for load-more). */
  scrollRef?: RefObject<HTMLDivElement>;
  /** Optional scroll handler (e.g. for infinite load). */
  onScroll?: () => void;
  /** Optional content rendered below the table inside the scroll area. */
  footer?: React.ReactNode;
}

const REPORT_LABELS: Record<string, string> = {
  fundamentals_report: 'Fundamentals',
  market_report: 'Market',
  news_report: 'News',
  sec_report: 'SEC',
  investment_plan: 'Research',
  final_trade_decision: 'Confidence',
  research_report: 'Research',
  marker: 'Marker',
  risk: 'Risk',
};

/** Order: Market, News, Fundamentals, SEC, Research, Confidence. */
const REPORT_ORDER: string[] = [
  'market_report',
  'news_report',
  'fundamentals_report',
  'sec_report',
  'investment_plan',
  'final_trade_decision', // Confidence last
];

function scoreEntryOrder([key]: [string, unknown]): number {
  const i = REPORT_ORDER.indexOf(key);
  if (i >= 0) return i;
  return REPORT_ORDER.length - 0.5; // unknown reports before Confidence
}

function formatReportKey(key: string): string {
  const label = REPORT_LABELS[key];
  if (label) return label;
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function getScoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-gray-400';
  if (score <= 3) return 'text-red-400';
  if (score <= 5) return 'text-yellow-400';
  if (score <= 7) return 'text-blue-400';
  return 'text-green-400';
}

function formatDate(dateStr: string | null): string {
  const date = parseReportDate(dateStr);
  if (!date) return '—';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getRecommendationBadge(rec: string | null, confidence?: number | null) {
  if (!rec) return <span className="text-gray-500">—</span>;
  const colors: Record<string, string> = {
    BUY: 'bg-green-500/20 text-green-400 border-green-500/50',
    SELL: 'bg-red-500/20 text-red-400 border-red-500/50',
    HOLD: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
  };
  const c = colors[rec.toUpperCase()] || 'bg-gray-500/20 text-gray-400 border-gray-500/50';
  const confidencePct =
    confidence != null && confidence >= 0 && confidence <= 1
      ? `${Math.round(confidence * 100)}%`
      : null;
  return (
    <span className="inline-flex items-center gap-x-1.5 whitespace-nowrap max-w-full min-w-0">
      <span className={`px-2 py-0.5 rounded text-xs font-semibold border shrink-0 ${c}`}>
        {rec.toUpperCase()}
      </span>
      {confidencePct != null && (
        <span className="text-gray-400 text-xs font-medium truncate">Confidence: {confidencePct}</span>
      )}
    </span>
  );
}

function getConfidenceValue(widget: StockWidgetType): number {
  const c = widget.confidence;
  if (c != null && c >= 0 && c <= 1) return c;
  return -1;
}

export default function StockListView({ widgets, tickerToName, scrollRef, onScroll, footer }: StockListViewProps) {
  const navigate = useNavigate();
  const sortedWidgets = [...widgets].sort(
    (a, b) => getConfidenceValue(b) - getConfidenceValue(a)
  );

  return (
    <div className="w-full min-w-0 max-w-full rounded-lg border border-gray-700 bg-gray-800/80" role="region" aria-label="Stock list table">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="overflow-auto min-h-0 w-full"
        style={{ height: STOCK_TABLE_HEIGHT }}
      >
        <table className="table-fixed text-left w-full min-w-[960px]" style={{ tableLayout: 'fixed' }}>
        <colgroup>
          <col className="w-[7%]" />
          <col className="w-[16%]" />
          <col className="w-[8%]" />
          <col className="w-[8%]" />
          <col className="w-[15%]" />
          <col className="w-[38%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-gray-800 shadow-[0_1px_0_0_rgba(55,65,81,1)]">
          <tr className="border-b border-gray-700 text-gray-400 text-sm">
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Ticker</th>
            <th className="py-3 px-2 font-semibold truncate" title="Name">Name</th>
            <th className="py-3 px-2 font-semibold text-right whitespace-nowrap">Price</th>
            <th className="py-3 px-2 font-semibold text-right whitespace-nowrap">Change</th>
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Recommendation</th>
            <th className="py-3 px-2 font-semibold min-w-0">AI analysis scores</th>
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Report date</th>
          </tr>
        </thead>
        <tbody>
          {sortedWidgets.map((widget) => {
            const changeColor = widget.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400';
            const name = tickerToName[widget.ticker] || widget.ticker;
            const scores = widget.report_scores && Object.keys(widget.report_scores).length > 0
              ? widget.report_scores
              : null;

            return (
              <tr
                key={widget.ticker}
                onClick={() => navigate(`/stocks/${widget.ticker}`)}
                className="border-b border-gray-700/80 hover:bg-gray-700/50 cursor-pointer transition-colors"
              >
                <td className="py-3 px-2 font-bold text-white whitespace-nowrap truncate" title={widget.ticker}>{widget.ticker}</td>
                <td className="py-3 px-2 text-gray-300 min-w-0 truncate" title={name}>
                  {name}
                </td>
                <td className="py-3 px-2 text-right text-white font-mono whitespace-nowrap">
                  {widget.current_price > 0 ? `$${widget.current_price.toFixed(2)}` : '—'}
                </td>
                <td className={`py-3 px-2 text-right font-mono font-medium whitespace-nowrap ${changeColor}`}>
                  {widget.current_price > 0
                    ? `${widget.daily_change_percent >= 0 ? '+' : ''}${widget.daily_change_percent.toFixed(2)}%`
                    : '—'}
                </td>
                <td className="py-3 px-2 min-w-0 truncate">{getRecommendationBadge(widget.recommendation, widget.confidence)}</td>
                <td className="py-3 px-2 min-w-0">
                  {scores ? (
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(scores)
                        .filter(([reportType]) => reportType !== 'final_trade_decision' && reportType !== 'trader_investment_plan')
                        .sort((a, b) => scoreEntryOrder(a) - scoreEntryOrder(b))
                        .map(([reportType, data]) => {
                        const label = formatReportKey(reportType);
                        const value = data.score != null ? `${data.score}/10` : '—';
                        return (
                          <div
                            key={reportType}
                            className="flex items-center gap-1 bg-gray-700/60 rounded px-2 py-1 text-sm"
                          >
                            <span className="text-gray-400">{label}:</span>
                            <span className={data.score != null ? `font-semibold ${getScoreColor(data.score)}` : 'text-gray-500'}>
                              {value}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <span className="text-gray-500 text-sm">No scores</span>
                  )}
                </td>
                <td className="py-3 px-2 text-gray-400 text-sm whitespace-nowrap truncate" title={formatDate(widget.report_date)}>{formatDate(widget.report_date)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
        {footer}
      </div>
    </div>
  );
}
