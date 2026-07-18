import type { RefObject } from 'react';
import { useNavigate } from 'react-router-dom';
import type { TickerWidget as TickerWidgetType } from '../services/types';
import { parseReportDate } from '../utils/date';
import { formatPrice } from '../utils/currency';
import AspectSpiderChart, { getScoreColor, formatReportKey, getAnalysisScoreEntries } from './AspectSpiderChart';
import { EventIcon, formatDominantEventLabel } from './EventsPanel';

/** Min and max number of visible stock rows; table height is dynamic within these limits. */
const MIN_VISIBLE_ROWS = 3;
const MAX_VISIBLE_ROWS = 12;
const ROW_HEIGHT_PX = 84;
const TABLE_HEADER_HEIGHT_PX = 52;
const TABLE_FOOTER_HEIGHT_PX = 40;

function getTableHeightPx(rowCount: number, hasFooter: boolean): number {
  const visibleRows = Math.min(MAX_VISIBLE_ROWS, Math.max(MIN_VISIBLE_ROWS, rowCount));
  return TABLE_HEADER_HEIGHT_PX + visibleRows * ROW_HEIGHT_PX + (hasFooter ? TABLE_FOOTER_HEIGHT_PX : 0);
}

interface TickerListViewProps {
  widgets: TickerWidgetType[];
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

function getWidgetConfidence(widget: TickerWidgetType): number | null {
  const direct = widget.confidence;
  if (direct != null && direct >= 0 && direct <= 1) return direct;
  // investment_plan (Research) is the authoritative score; final_trade_decision kept for historical runs.
  const finalScore = widget.report_scores?.investment_plan?.score
    ?? widget.report_scores?.final_trade_decision?.score;
  if (finalScore != null && finalScore >= 0 && finalScore <= 5) return finalScore / 5;
  return null;
}

function getConfidenceValue(widget: TickerWidgetType): number {
  return getWidgetConfidence(widget) ?? -1;
}

function renderEventChips(widget: TickerWidgetType) {
  if (widget.dominant_events == null && widget.event_count == null) {
    return <span className="text-xs text-gray-500">Loading signals…</span>;
  }

  const dominantEvents = widget.dominant_events ?? [];
  if (dominantEvents.length === 0) {
    return <span className="text-xs text-gray-500">No signals</span>;
  }

  const visibleEvents = dominantEvents.slice(0, 2);
  const hiddenCount = Math.max(0, dominantEvents.length - visibleEvents.length);

  return (
    <div className="flex flex-wrap gap-1.5">
      {visibleEvents.map((eventType) => (
        <span
          key={eventType}
          className="inline-flex items-center gap-1.5 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs font-medium text-gray-200"
          title={formatDominantEventLabel(eventType)}
        >
          <EventIcon eventType={eventType} className="h-3.5 w-3.5 shrink-0 text-sky-300" />
          <span className="truncate">{formatDominantEventLabel(eventType)}</span>
        </span>
      ))}
      {hiddenCount > 0 ? (
        <span className="inline-flex items-center rounded border border-gray-700 bg-gray-900 px-2 py-1 text-xs font-medium text-gray-400">
          +{hiddenCount}
        </span>
      ) : null}
    </div>
  );
}

export default function TickerListView({ widgets, tickerToName, scrollRef, onScroll, footer, preserveOrder = false }: TickerListViewProps) {
  const navigate = useNavigate();
  const sortedWidgets = preserveOrder
    ? widgets
    : [...widgets].sort((a, b) => getConfidenceValue(b) - getConfidenceValue(a));
  const tableHeightPx = getTableHeightPx(sortedWidgets.length, Boolean(footer));

  return (
    <div className="w-full min-w-0 max-w-full rounded-lg border border-gray-700 bg-gray-800/80" role="region" aria-label="Stock list table">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="overflow-auto min-h-0 w-full scrollbar-hide-x"
        style={{ height: `${tableHeightPx}px` }}
      >
        <table className="table-fixed text-left w-full min-w-[980px]" style={{ tableLayout: 'fixed' }}>
        <colgroup>
          <col className="w-[12%]" />
          <col className="w-[9%]" />
          <col className="w-[14%]" />
          <col className="w-[45%]" />
          <col className="w-[13%]" />
          <col className="w-[7%]" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-gray-800 shadow-[0_1px_0_0_rgba(55,65,81,1)]">
          <tr className="border-b border-gray-700 text-gray-400 text-sm">
            <th className="py-3 px-2 font-semibold"></th>
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Ticker</th>
            <th className="py-3 px-2 font-semibold text-right whitespace-nowrap">Price / Change</th>
            <th className="py-3 px-2 font-semibold min-w-0">AI analysis scores</th>
            <th className="py-3 px-2 font-semibold min-w-0">Events</th>
            <th className="py-3 px-2 font-semibold whitespace-nowrap">Report date</th>
          </tr>
        </thead>
        <tbody>
          {sortedWidgets.map((widget) => {
            const changeColor = widget.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400';
            const name = widget.name || tickerToName[widget.ticker] || widget.ticker;
            const scoreEntries = getAnalysisScoreEntries(widget.report_scores);

            return (
              <tr
                key={widget.ticker}
                onClick={() => navigate(`/tickers/${widget.ticker}`)}
                className="border-b border-gray-700/80 hover:bg-gray-700/50 cursor-pointer transition-colors"
              >
                <td className="py-3 px-2">
                  {scoreEntries.length > 0 ? (
                    <div className="flex items-center justify-center">
                      <AspectSpiderChart scoreEntries={scoreEntries} size={80} />
                    </div>
                  ) : null}
                </td>
                <td className="py-3 px-2 min-w-0" title={`${widget.ticker} ${name}`}>
                  <div className="min-w-0">
                    <div className="font-bold text-white whitespace-nowrap truncate">{widget.ticker}</div>
                    <div className="text-xs leading-tight text-gray-400 truncate">{name}</div>
                  </div>
                </td>
                <td className="py-3 px-2 text-right min-w-0">
                  <div className="min-w-0">
                    <div className="text-white font-mono whitespace-nowrap truncate">
                      {widget.current_price > 0 ? formatPrice(widget.current_price, widget.currency) : '—'}
                    </div>
                    <div className={`text-xs font-mono font-medium whitespace-nowrap truncate ${changeColor}`}>
                      {widget.current_price > 0
                        ? `${formatPrice(widget.daily_change, widget.currency)} (${widget.daily_change_percent >= 0 ? '+' : ''}${widget.daily_change_percent.toFixed(2)}%)`
                        : '—'}
                    </div>
                  </div>
                </td>
                <td className="py-3 px-2 min-w-0">
                  {scoreEntries.length > 0 || widget.recommendation ? (
                    <div className="flex flex-wrap gap-2 min-w-0">
                      {widget.recommendation ? (
                        <div className="flex items-center gap-1 bg-gray-700/60 rounded px-2 py-1 text-sm">
                          <span className="text-gray-400">Call:</span>
                          {getRecommendationBadge(widget.recommendation)}
                        </div>
                      ) : null}
                      {scoreEntries.map(([reportType, data]) => {
                        const label = formatReportKey(reportType);
                        const value = data.score != null ? `${data.score}/5` : '—';
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
                <td className="py-3 px-2 min-w-0">
                  {renderEventChips(widget)}
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
