import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

function RadarTooltip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const { aspect, score } = payload[0]?.payload ?? {};
  if (aspect == null) return null;
  return (
    <div className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs shadow-lg pointer-events-none">
      <span className="text-gray-300">{aspect}: </span>
      <span className="font-semibold text-white">{score != null ? `${score}/10` : '—'}</span>
    </div>
  );
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
};

const EXCLUDED_REPORT_TYPES = new Set(['trader_investment_plan']);

export type ReportScoreMap = Record<string, { score: number | null; score_label?: string | null }>;

export function formatReportKey(key: string): string {
  const label = REPORT_LABELS[key];
  if (label) return label;
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getAnalysisScoreEntries(scores: ReportScoreMap | null | undefined): [string, { score: number | null }][] {
  if (!scores || Object.keys(scores).length === 0) return [];
  const REPORT_ORDER = [
    'market_report', 'news_report', 'fundamentals_report', 'technical_report',
    'sec_report', 'investment_plan', 'final_trade_decision',
  ];
  return (Object.entries(scores) as [string, { score: number | null }][])
    .filter(([reportType]) => !EXCLUDED_REPORT_TYPES.has(reportType))
    .sort((a, b) => {
      const ia = REPORT_ORDER.indexOf(a[0]);
      const ib = REPORT_ORDER.indexOf(b[0]);
      if (ia === -1 && ib === -1) return a[0].localeCompare(b[0]);
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
}

function getSpiderData(scoreEntries: [string, { score: number | null }][]) {
  return scoreEntries
    .filter(([, data]) => data.score != null)
    .map(([reportType, data]) => ({
      aspect: formatReportKey(reportType),
      score: data.score as number,
    }));
}

function calculateAverageAnalystScore(scoreEntries: [string, { score: number | null }][]): number | null {
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

export function getScoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-gray-400';
  if (score <= 3) return 'text-red-400';
  if (score <= 5) return 'text-yellow-400';
  if (score <= 7) return 'text-blue-400';
  return 'text-green-400';
}

interface AspectSpiderChartProps {
  scoreEntries: [string, { score: number | null }][];
  /** Size in pixels (width = height). Default: 80 */
  size?: number;
  /** Show axis labels. Default: false */
  showLabels?: boolean;
}

/**
 * Compact radar/spider chart showing AI analysis dimension scores.
 * Used in the AI Analysis summary tile and in the stock list table.
 */
export default function AspectSpiderChart({ scoreEntries, size = 80, showLabels = false }: AspectSpiderChartProps) {
  const spiderData = getSpiderData(scoreEntries);
  const avgScore = calculateAverageAnalystScore(scoreEntries);
  const radarColor = getRadarFillColor(avgScore);

  if (spiderData.length < 3) {
    return (
      <div
        className="shrink-0 rounded border border-gray-700/80 bg-gray-900/50 flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        <span className="text-[10px] text-gray-500">N/A</span>
      </div>
    );
  }

  return (
    <div
      className="shrink-0 overflow-hidden outline-none focus:outline-none"
      style={{ width: size, height: size }}
      aria-label="AI aspect score spider chart"
      tabIndex={-1}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={spiderData} cx="50%" cy="50%" outerRadius="90%" margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <PolarGrid stroke="#4b5563" />
          <PolarAngleAxis
            dataKey="aspect"
            tick={showLabels ? { fill: '#9ca3af', fontSize: 9 } : false}
            axisLine={false}
          />
          <PolarRadiusAxis
            type="number"
            domain={[0, 10]}
            tickCount={6}
            allowDecimals={false}
            tick={false}
            axisLine={false}
          />
          <Radar
            dataKey="score"
            stroke={radarColor}
            fill={radarColor}
            fillOpacity={0.6}
            isAnimationActive={false}
          />
          <Tooltip content={<RadarTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Made with Bob
