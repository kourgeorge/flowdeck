import type { RefObject } from 'react';
import { useNavigate } from 'react-router-dom';
import type { StockWidget as StockWidgetType } from '../services/types';
import { parseReportDate } from '../utils/date';
import AspectSpiderChart, { getScoreColor, formatReportKey, getAnalysisScoreEntries } from './AspectSpiderChart';

/** Min and max number of visible stock rows; table height is dynamic within these limits. */
const MIN_VISIBLE_ROWS = 3;
const MAX_VISIBLE_ROWS = 12;
const ROW_HEIGHT_PX = 72;
const TABLE_HEADER_HEIGHT_PX = 52;

function getTableHeightPx(rowCount: number): number {
  const visibleRows = Math.min(MAX_VISIBLE_ROWS, Math.max(MIN_VISIBLE_ROWS, rowCount));
  return TABLE_HEADER_HEIGHT_PX + visibleRows * ROW_HEIGHT_PX;
}

interface StockListViewProps {
  widgets: StockWidgetType[];
  tickerToName: Record<string, string>;
  /** Optional ref for the scroll container (e.g. for load-more). */
  scrollRef?: RefObject<HTMLDivElement>;
  /** Optional scroll handler (e.g. for infinite load). */
  onScroll?: () => void;
  /** Optional content rendered below the table inside the scroll area. */
  footer?: React.ReactNode;
  /** If true, preserve the order from widgets array instead of sorting by confidence. Default: false */
  preserveOrder?: boolean;
}

function formatDate(dateStr: string | null): string {
  const date = parseReportDate(dateStr);
  if (!date) return '—';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getRecommendationBadge(rec: string | null) {
  if (!rec) return <span className="text-gray-500">—</span>;
  const colors: Record<string, string> = {
    BUY: 'bg-green-500/20 text-green-400 border-green-500/50',
    SELL: 'bg-red-500/20 text-red-400 border-red-500/50',
    HOLD: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
  };
  const c = colors[rec.toUpperCase()] || 'bg-gray-500/20 text-gray-400 border-gray-500/50';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${c}`}>
      {rec.toUpperCase()}
    </span>
  );
}

function getWidgetConfidence(widget: StockWidgetType): number | null {
  const direct = widget.confidence;
  if (direct != null && direct >= 0 && direct <= 1) return direct;
  const finalScore = widget.report_scores?.final_trade_decision?.score;
  if (finalScore != null && finalScore >= 0 && finalScore <= 10) return finalScore / 10;
  return null;
}

function getConfidenceValue(widget: StockWidgetType): number {
  return getWidgetConfidence(widget) ?? -1;
}

export default function StockListView({ widgets, tickerToName, scrollRef, onScroll, footer, preserveOrder = false }: StockListViewProps) {
  const navigate = useNavigate();
  const sortedWidgets = preserveOrder
    ? widgets
    : [...widgets].sort((a, b) => getConfidenceValue(b) - getConfidenceValue(a));
  const tableHeightPx = getTableHeightPx(sortedWidgets.length);

  return (
    <div className="w-full min-w-0 max-w-full rounded-lg border border-gray-700 bg-gray-800/80" role="region" aria-label="Stock list table">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="overflow-auto min-h-0 w-full scrollbar-hide-x"
        style={{ height: `${tableHeightPx}px` }}
      >
        <table className="table-fixed text-left w-full min-w-[960px]" style={{ tableLayout: 'fixed' }}>
        <colgroup>
          <col className="w-[7%]" />
          <col className="w-[16%]" />
          <col className="w-[8%]" />
          <col className="w-[8%]" />
          <col className="w-[7%]" />
          <col className="w-[46%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-gray-800 shadow-[0_1px_0_0_rgba(55,65,81,1)]">
          <tr className="border-b border-gray-700 text-gray-400 text-sm">
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Ticker</th>
            <th className="py-3 px-2 font-semibold truncate" title="Name">Name</th>
            <th className="py-3 px-2 font-semibold text-right whitespace-nowrap">Price</th>
            <th className="py-3 px-2 font-semibold text-right whitespace-nowrap">Change</th>
            <th className="py-3 px-2 font-semibold whitespace-nowrap text-center">Call</th>
            <th className="py-3 px-2 font-semibold min-w-0">AI analysis scores</th>
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Report date</th>
          </tr>
        </thead>
        <tbody>
          {sortedWidgets.map((widget) => {
            const changeColor = widget.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400';
            const name = tickerToName[widget.ticker] || widget.ticker;
            const scoreEntries = getAnalysisScoreEntries(widget.report_scores);

            return (
              <tr
                key={widget.ticker}
                onClick={() => navigate(`/tickers/${widget.ticker}`)}
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
                <td className="py-3 px-2 min-w-0 truncate text-center">{getRecommendationBadge(widget.recommendation)}</td>
                <td className="py-3 px-2 min-w-0">
                  {scoreEntries.length > 0 ? (
                    <div className="flex items-center gap-3 min-w-0">
                      <AspectSpiderChart scoreEntries={scoreEntries} size={80} />
                      <div className="flex flex-wrap gap-2 min-w-0">
                        {scoreEntries.map(([reportType, data]) => {
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
