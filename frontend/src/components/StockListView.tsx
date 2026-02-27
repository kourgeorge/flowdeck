import type { RefObject } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts';
import type { StockWidget as StockWidgetType } from '../services/types';
import { parseReportDate } from '../utils/date';

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

const REPORT_LABELS: Record<string, string> = {
  fundamentals_report: 'Fundamentals',
  market_report: 'Market',
  news_report: 'News',
  technical_report: 'Technical',
  sec_report: 'SEC',
  investment_plan: 'Research',
  final_trade_decision: 'Low Risk',
  research_report: 'Research',
  marker: 'Marker',
  risk: 'Risk',
};

/** Order: Market, News, Fundamentals, Technical, SEC, Research, Confidence. */
const REPORT_ORDER: string[] = [
  'market_report',
  'news_report',
  'fundamentals_report',
  'technical_report',
  'sec_report',
  'investment_plan',
  'final_trade_decision', // Confidence last
];

const EXCLUDED_REPORT_TYPES = new Set(['trader_investment_plan']);

type ReportScoreMap = NonNullable<StockWidgetType['report_scores']>;
type ReportScoreEntry = [string, ReportScoreMap[string]];

function scoreEntryOrder(key: string): number {
  const i = REPORT_ORDER.indexOf(key);
  if (i >= 0) return i;
  return REPORT_ORDER.length - 0.5; // unknown reports before Confidence
}

function getAnalysisScoreEntries(scores: StockWidgetType['report_scores']): ReportScoreEntry[] {
  if (!scores || Object.keys(scores).length === 0) return [];
  return (Object.entries(scores) as ReportScoreEntry[])
    .filter(([reportType]) => !EXCLUDED_REPORT_TYPES.has(reportType))
    .sort((a, b) => scoreEntryOrder(a[0]) - scoreEntryOrder(b[0]));
}

function getSpiderData(scoreEntries: ReportScoreEntry[]) {
  return scoreEntries
    .filter(([, data]) => data.score != null)
    .map(([reportType, data]) => ({
      aspect: formatReportKey(reportType),
      score: data.score as number,
    }));
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

function calculateAverageAnalystScore(scoreEntries: ReportScoreEntry[]): number | null {
  const analystReports = ['market_report', 'news_report', 'fundamentals_report', 'technical_report', 'sec_report'];
  const analystScores = scoreEntries
    .filter(([type]) => analystReports.includes(type))
    .map(([, data]) => data.score)
    .filter((score): score is number => score != null);
  
  if (analystScores.length === 0) return null;
  return analystScores.reduce((sum, score) => sum + score, 0) / analystScores.length;
}

function getRadarFillColor(avgScore: number | null): string {
  if (avgScore == null) return '#38bdf8';
  if (avgScore <= 3) return '#f87171';
  if (avgScore <= 5) return '#facc15';
  if (avgScore <= 7) return '#38bdf8';
  return '#4ade80';
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

function AspectSpiderWidget({ scoreEntries }: { scoreEntries: ReportScoreEntry[] }) {
  const spiderData = getSpiderData(scoreEntries);
  const avgScore = calculateAverageAnalystScore(scoreEntries);
  const radarColor = getRadarFillColor(avgScore);
  
  if (spiderData.length < 3) {
    return (
      <div className="h-20 w-20 shrink-0 rounded border border-gray-700/80 bg-gray-900/50 flex items-center justify-center">
        <span className="text-[10px] text-gray-500">N/A</span>
      </div>
    );
  }
  return (
    <div className="h-20 w-20 shrink-0 overflow-hidden" aria-label="AI aspect score spider chart">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={spiderData} cx="50%" cy="50%" outerRadius="95%" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <PolarGrid stroke="#4b5563" />
          <PolarAngleAxis dataKey="aspect" tick={false} axisLine={false} />
          <PolarRadiusAxis type="number" domain={[0, 10]} tickCount={6} allowDecimals={false} tick={false} axisLine={false} />
          <Radar dataKey="score" stroke={radarColor} fill={radarColor} fillOpacity={0.6} isAnimationActive={false} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
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
                      <AspectSpiderWidget scoreEntries={scoreEntries} />
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
