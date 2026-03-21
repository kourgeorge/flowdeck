import { useNavigate } from 'react-router-dom';
import type { TickerWidget as TickerWidgetType } from '../services/types';
import { parseReportDate } from '../utils/date';
import { formatPrice } from '../utils/currency';
import AspectSpiderChart, { getAnalysisScoreEntries, getScoreColor, formatReportKey } from './AspectSpiderChart';
import { EventIcon, formatDominantEventLabel } from './EventsPanel';

interface MajorStockWidgetsProps {
  widgets: TickerWidgetType[];
  tickerToName: Record<string, string>;
}

function formatDate(dateStr: string | null): string {
  const date = parseReportDate(dateStr);
  if (!date) return 'No report date';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getRecommendationBadge(rec: string | null) {
  if (!rec) {
    return (
      <span className="inline-flex items-center rounded-full border border-gray-700 bg-gray-700/50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">
        No call
      </span>
    );
  }

  const colors: Record<string, string> = {
    BUY: 'bg-green-500/20 text-green-400 border-green-500/50',
    SELL: 'bg-red-500/20 text-red-400 border-red-500/50',
    HOLD: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
  };
  const tone = colors[rec.toUpperCase()] || 'bg-gray-500/20 text-gray-400 border-gray-500/50';

  return (
      <span className={`inline-flex items-center rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${tone}`}>
        {rec.toUpperCase()}
      </span>
    );
}

function getMarketStatusLabel(status: string | null | undefined): string {
  if (!status) return 'Market';
  return status.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function getAverageScore(scoreEntries: [string, { score: number | null }][]): number | null {
  const values = scoreEntries
    .map(([, data]) => data.score)
    .filter((score): score is number => score != null);
  if (values.length === 0) return null;
  return values.reduce((sum, score) => sum + score, 0) / values.length;
}

function renderEventChips(widget: TickerWidgetType) {
  const dominantEvents = widget.dominant_events ?? [];

  if (dominantEvents.length === 0) {
    return <span className="text-[11px] text-slate-500">No dominant signals.</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {dominantEvents.slice(0, 3).map((eventType) => (
        <span
          key={eventType}
          className="inline-flex items-center gap-1 rounded-full border border-gray-700 bg-gray-700/50 px-2 py-1 text-[10px] font-medium text-slate-300"
          title={formatDominantEventLabel(eventType)}
        >
          <EventIcon eventType={eventType} className="h-3 w-3 shrink-0 text-sky-300" />
          <span className="truncate max-w-[128px]">{formatDominantEventLabel(eventType)}</span>
        </span>
      ))}
      {dominantEvents.length > 3 ? (
        <span className="inline-flex items-center rounded-full border border-gray-700 bg-gray-700/50 px-2 py-1 text-[10px] font-medium text-slate-400">
          +{dominantEvents.length - 3}
        </span>
      ) : null}
    </div>
  );
}

export default function MajorStockWidgets({ widgets, tickerToName }: MajorStockWidgetsProps) {
  const navigate = useNavigate();

  return (
    <div className="grid auto-rows-fr grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {widgets.map((widget) => {
        const name = widget.name || tickerToName[widget.ticker] || widget.ticker;
        const scoreEntries = getAnalysisScoreEntries(widget.report_scores);
        const averageScore = getAverageScore(scoreEntries);
        const isPositive = widget.daily_change_percent >= 0;
        const confidencePercent = widget.confidence != null ? Math.round(widget.confidence * 100) : null;
        const priceChangeLabel = widget.current_price > 0
          ? `${formatPrice(widget.daily_change, widget.currency)} (${isPositive ? '+' : ''}${widget.daily_change_percent.toFixed(2)}%)`
          : 'Price unavailable';

        return (
          <button
            key={widget.ticker}
            type="button"
            onClick={() => navigate(`/tickers/${widget.ticker}`)}
            className="group relative h-full overflow-hidden rounded-2xl border border-gray-700 bg-gray-800/70 p-4 text-left shadow-[0_20px_60px_-36px_rgba(15,23,42,0.85)] transition-all duration-200 hover:-translate-y-0.5 hover:border-gray-600 hover:bg-gray-800/80 hover:shadow-[0_28px_80px_-36px_rgba(15,23,42,0.95)]"
          >
            <div className="relative flex h-full flex-col gap-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-1.5">
                    <span className="inline-flex items-center rounded-full border border-gray-700 bg-gray-700/50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                      {getMarketStatusLabel(widget.market_status)}
                    </span>
                    {getRecommendationBadge(widget.recommendation)}
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-[1.35rem] font-semibold tracking-[-0.03em] text-white">{widget.ticker}</h3>
                    <p className="truncate text-sm text-slate-400">{name}</p>
                  </div>
                </div>

                <div className="shrink-0 text-right">
                  <div className="text-xl font-semibold tracking-[-0.03em] text-white">
                    {widget.current_price > 0 ? formatPrice(widget.current_price, widget.currency) : '—'}
                  </div>
                  <div className={`mt-1 text-sm font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                    {priceChangeLabel}
                  </div>
                  {confidencePercent != null ? (
                    <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      Confidence {confidencePercent}%
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="p-1">
                <div className="mb-2 flex items-center justify-between">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Radar</div>
                  {averageScore != null ? (
                    <div className="rounded-full border border-gray-700 bg-gray-700/50 px-2 py-1 text-[10px] font-semibold tabular-nums text-slate-300">
                      {averageScore.toFixed(1)}/10
                    </div>
                  ) : null}
                </div>
                <div className="flex items-center justify-center rounded-[1.25rem] border border-gray-700 bg-gray-800 py-2">
                  {scoreEntries.length > 0 ? (
                    <AspectSpiderChart scoreEntries={scoreEntries} size={112} />
                  ) : (
                    <div className="flex h-[112px] w-[112px] items-center justify-center rounded-full border border-dashed border-gray-700 text-[11px] text-slate-500">
                      No scores
                    </div>
                  )}
                </div>
              </div>

              <div className="min-w-0 p-1">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    AI Analysis
                  </div>
                  <span className="rounded-full border border-gray-700 bg-gray-700/50 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">
                    {scoreEntries.length} factors
                  </span>
                </div>
                {scoreEntries.length > 0 ? (
                  <div className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800/80">
                    <div className="grid grid-cols-2 gap-px bg-gray-700/70">
                      {scoreEntries.map(([reportType, data]) => (
                        <div
                          key={reportType}
                          className="flex items-center justify-between gap-2 bg-gray-800 px-2.5 py-2"
                        >
                          <div className="min-w-0 truncate text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">
                            {formatReportKey(reportType)}
                          </div>
                          <div className={`shrink-0 text-[12px] font-semibold tabular-nums ${getScoreColor(data.score)}`}>
                            {data.score != null ? `${data.score}/10` : '—'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-500">No AI score breakdown yet.</p>
                )}
              </div>

              <div className="p-1">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h4 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Signals</h4>
                  <span className="text-[10px] text-slate-500">
                    {widget.event_count != null ? `${widget.event_count} tracked` : `${widget.dominant_events?.length ?? 0} shown`}
                  </span>
                </div>
                {renderEventChips(widget)}
              </div>

              <div className="mt-auto flex items-center justify-between gap-3 border-t border-gray-700 pt-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Latest report</div>
                  <div className="mt-1 text-sm font-medium text-slate-300">{formatDate(widget.report_date)}</div>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full border border-gray-700 bg-gray-700/50 px-3 py-1.5 text-[11px] font-medium text-slate-300 transition-colors group-hover:border-gray-600 group-hover:bg-gray-700 group-hover:text-white">
                  Open analysis
                  <svg className="h-4 w-4 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5l7 7-7 7" />
                  </svg>
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
