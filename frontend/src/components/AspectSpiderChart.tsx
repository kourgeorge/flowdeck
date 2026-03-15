import { useMemo, useState } from 'react';

/** Radians for angle at 12 o'clock (top), then clockwise; index i => angle in rad */
function angleAt(i: number, n: number): number {
  return Math.PI / 2 - (2 * Math.PI * i) / n;
}

function polarToCart(cx: number, cy: number, r: number, angleRad: number): { x: number; y: number } {
  return {
    x: cx + r * Math.cos(angleRad),
    y: cy - r * Math.sin(angleRad),
  };
}

function dist(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** Build a closed path with slightly rounded corners using quadratic curves. */
function roundedPolygonPath(
  points: { x: number; y: number }[],
  cornerRadius: number
): string {
  const n = points.length;
  if (n < 2) return '';
  if (n === 2) return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;

  const radius = Math.max(0.5, cornerRadius);
  const p = (i: number) => points[(i + n) % n];

  const trim = (curr: { x: number; y: number }, next: { x: number; y: number }, r: number) => {
    const d = dist(curr, next);
    const t = d > 1e-6 ? Math.min(r / d, 0.5) : 0;
    return { x: curr.x + (next.x - curr.x) * t, y: curr.y + (next.y - curr.y) * t };
  };

  const endPoints = points.map((curr, i) => trim(curr, p(i + 1), radius));
  const segments = points.map((curr, i) => `Q ${curr.x} ${curr.y} ${endPoints[i].x} ${endPoints[i].y}`);
  return `M ${endPoints[n - 1].x} ${endPoints[n - 1].y} ${segments.join(' ')} Z`;
}

const REPORT_LABELS: Record<string, string> = {
  fundamentals_report: 'Fundamentals',
  market_report: 'Market',
  sentiment_report: 'Sentiment',
  news_report: 'News',
  technical_report: 'Technical',
  sec_report: 'SEC',
  investment_plan: 'Research',
  final_trade_decision: 'Low Risk',
  research_report: 'Research',
};

/** Radar axis labels: max 5 characters each */
const SHORT_AXIS_LABELS: Record<string, string> = {
  Market: 'Mkt',
  Sentiment: 'Sent',
  News: 'News',
  Fundamentals: 'Fund',
  Technical: 'Tech',
  SEC: 'SEC',
  Research: 'Res',
  'Low Risk': 'Risk',
};

function getAxisLabel(aspect: string, maxLen: number = 5): string {
  const short = SHORT_AXIS_LABELS[aspect];
  if (short) return short;
  return aspect.length <= maxLen ? aspect : aspect.slice(0, maxLen);
}

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
    'market_report', 'sentiment_report', 'news_report', 'fundamentals_report', 'technical_report',
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
  if (avgScore <= 6) return '#facc15';
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
}

/**
 * Compact radar/spider chart showing AI analysis dimension scores.
 * Used in the AI Analysis summary tile and in the stock list table.
 */
export default function AspectSpiderChart({ scoreEntries, size = 80 }: AspectSpiderChartProps) {
  const spiderData = getSpiderData(scoreEntries);
  const avgScore = calculateAverageAnalystScore(scoreEntries);
  const radarColor = getRadarFillColor(avgScore);

  if (spiderData.length < 3) {
    return (
      <div
        className="shrink-0 rounded border border-gray-700/80 bg-gray-900/50 flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        <span className="text-xs text-gray-500">N/A</span>
      </div>
    );
  }

  return (
    <PentagonalRadar
      spiderData={spiderData}
      radarColor={radarColor}
      size={size}
    />
  );
}

const GRID_RINGS = 4;
const SCORE_MAX = 10;

interface PentagonalRadarProps {
  spiderData: { aspect: string; score: number }[];
  radarColor: string;
  size: number;
}

function PentagonalRadar({ spiderData, radarColor, size }: PentagonalRadarProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const { cx, cy, segments, gridCircles, bands, radialAxes, dataPoints, labelPoints } = useMemo(() => {
    const n = spiderData.length;
    const padding = size * 0.12;
    const cx = size / 2;
    const cy = size / 2;
    const outerR = Math.min(cx, cy) - padding;

    const segments: { d: string; index: number }[] = [];
    const labelR = outerR + padding * 0.5;
    const labelPoints: { x: number; y: number; aspect: string; rotation: number }[] = [];
    for (let i = 0; i < n; i++) {
      const a0 = angleAt(i, n);
      const a1 = angleAt(i + 1, n);
      const p0 = polarToCart(cx, cy, outerR, a0);
      const p1 = polarToCart(cx, cy, outerR, a1);
      segments.push({
        d: `M ${cx} ${cy} L ${p0.x} ${p0.y} L ${p1.x} ${p1.y} Z`,
        index: i,
      });
      const lp = polarToCart(cx, cy, labelR, a0);
      const angleDeg = (Math.atan2(lp.y - cy, lp.x - cx) * 180) / Math.PI;
      const isTop = angleDeg >= -115 && angleDeg <= -65;
      const aspectLabel = getAxisLabel(spiderData[i].aspect);
      labelPoints.push({
        x: lp.x,
        y: lp.y,
        aspect: aspectLabel,
        rotation: isTop ? 0 : angleDeg + 90,
      });
    }

    const gridCircles: number[] = [];
    for (let ring = 1; ring <= GRID_RINGS; ring++) {
      gridCircles.push((outerR * ring) / GRID_RINGS);
    }

    const bands: { innerR: number; outerR: number; dark: boolean }[] = [];
    for (let i = 0; i < GRID_RINGS; i++) {
      bands.push({
        innerR: i === 0 ? 0 : gridCircles[i - 1],
        outerR: gridCircles[i],
        dark: i % 2 === 1,
      });
    }

    const radialAxes = Array.from({ length: n }, (_, i) =>
      polarToCart(cx, cy, outerR, angleAt(i, n))
    );

    const dataPoints = spiderData.map((d, i) => {
      const r = (d.score / SCORE_MAX) * outerR;
      return polarToCart(cx, cy, r, angleAt(i, n));
    });

    return { cx, cy, segments, gridCircles, bands, radialAxes, dataPoints, labelPoints };
  }, [spiderData, size]);

  const cornerRadius = Math.max(1.5, size * 0.04);
  const dataPath =
    dataPoints.length > 0 ? roundedPolygonPath(dataPoints, cornerRadius) : '';

  const hoverEntry = hoverIndex != null ? spiderData[hoverIndex] : null;

  return (
    <div
      className="shrink-0 overflow-hidden relative"
      style={{ width: size, height: size, outline: 'none' }}
      aria-label="AI aspect score radar chart"
      tabIndex={-1}
      onMouseDown={(e) => e.preventDefault()}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size + 5}`} className="block">
        {/* Banded concentric rings (alternating darker / lighter background) */}
        <g fillRule="evenodd">
          {bands.map(({ innerR, outerR, dark }, i) => {
            const fill = dark ? '#1f2937' : '#374151';
            const opacity = dark ? 0.55 : 0.4;
            if (innerR === 0) {
              return <circle key={i} cx={cx} cy={cy} r={outerR} fill={fill} fillOpacity={opacity} />;
            }
            const outer = `M ${cx + outerR} ${cy} A ${outerR} ${outerR} 0 1 1 ${cx - outerR} ${cy} A ${outerR} ${outerR} 0 1 1 ${cx + outerR} ${cy}`;
            const inner = `M ${cx + innerR} ${cy} A ${innerR} ${innerR} 0 1 0 ${cx - innerR} ${cy} A ${innerR} ${innerR} 0 1 0 ${cx + innerR} ${cy}`;
            return <path key={i} d={`${outer} ${inner}`} fill={fill} fillOpacity={opacity} />;
          })}
        </g>
        {/* Circle strokes on top of bands */}
        <g fill="none" stroke="#4b5563" strokeWidth={0.5}>
          {gridCircles.map((r, i) => (
            <circle key={i} cx={cx} cy={cy} r={r} />
          ))}
        </g>
        {/* Radial axes (center to outer vertex per dimension) */}
        <g fill="none" stroke="#374151" strokeWidth={0.5}>
          {radialAxes.map((end, i) => (
            <line key={i} x1={cx} y1={cy} x2={end.x} y2={end.y} />
          ))}
        </g>
        {/* Wedge segments (transparent hit areas only) */}
        <g>
          {segments.map(({ d, index }) => (
            <path
              key={index}
              d={d}
              fill="transparent"
              className="cursor-pointer"
              onMouseEnter={() => setHoverIndex(index)}
              onMouseLeave={() => setHoverIndex(null)}
              data-cy-id={`segment-${spiderData[index].aspect.toLowerCase().replace(/\s+/g, '-')}`}
            />
          ))}
        </g>
        {/* Filled data polygon (radar shape) */}
        <path
          d={dataPath}
          fill={radarColor}
          fillOpacity={0.6}
          stroke={radarColor}
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        {/* Axis labels (title of each axis, rotated to read outward; top stays horizontal) */}
        {labelPoints.map((lp, i) => (
          <text
            key={i}
            x={lp.x}
            y={lp.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#e5e7eb"
            fillOpacity={0.95}
            fontSize={Math.max(9, Math.round(size * 0.11))}
            fontFamily="system-ui, -apple-system, 'Segoe UI', sans-serif"
            letterSpacing="0.02em"
            transform={`rotate(${lp.rotation} ${lp.x} ${lp.y})`}
          >
            {lp.aspect.toUpperCase()}
          </text>
        ))}
      </svg>
      {/* Tooltip */}
      {hoverEntry != null && (
        <div
          className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs shadow-lg pointer-events-none z-10"
          style={{ maxWidth: size }}
        >
          <span className="text-gray-300">{hoverEntry.aspect}: </span>
          <span className="font-semibold text-white">{hoverEntry.score}/10</span>
        </div>
      )}
    </div>
  );
}

