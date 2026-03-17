import { type ComponentProps, type ReactNode, useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link, useNavigate } from 'react-router-dom';
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { digestApi, tickerApi, type DigestBriefItem } from '../services/api';
import type { TickerWidget } from '../services/types';
import AspectSpiderChart, { formatReportKey, getAnalysisScoreEntries, getScoreColor } from './AspectSpiderChart';
import DashboardPriceTrendsChart from './DashboardPriceTrendsChart';
import { SubscribedChangeColumnsChart } from './OverviewStatsPanel';
import WorldMapRegionalStocks from './WorldMapRegionalStocks';
import { formatPrice } from '../utils/currency';

type CompanyInfo = {
  name: string;
  sector: string;
  industry: string;
  exchange: string;
  country: string;
  website: string;
  quoteType?: string;
};

type OverviewItem = {
  ticker: string;
  name: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
};

type MarketOverviewResponse = {
  indices: OverviewItem[];
  sectors: OverviewItem[];
  international: OverviewItem[];
  commodities: OverviewItem[];
  totalIndices: number;
  totalSectors: number;
  totalRegions: number;
  totalCommodities: number;
};

type MarketMoverRow = {
  symbol: string | null;
  shortName: string | null;
  sector?: string | null;
  industry?: string | null;
  regularMarketPrice: number | null;
  regularMarketChange: number | null;
  regularMarketChangePercent: number | null;
  regularMarketPreviousClose: number | null;
  regularMarketVolume: number | null;
};

type NewsArticle = {
  uuid: string;
  title: string;
  summary?: string | null;
  publisher?: string;
  link: string;
  published_time: string | null;
  published_timestamp: number;
  type?: string;
  thumbnail?: string | null;
  tickers: string[];
};

type SparklineData = {
  closes: number[];
  openPrice: number;
};

interface PortfolioPulseDashboardProps {
  widgets: TickerWidget[];
  tickerToName: Record<string, string>;
}

const RECOMMENDATION_COLORS: Record<string, string> = {
  BUY: '#34d399',
  HOLD: '#f59e0b',
  SELL: '#f87171',
  'NO AI': '#64748b',
};

const SCORE_ORDER = [
  'market_report',
  'news_report',
  'fundamentals_report',
  'technical_report',
  'investment_plan',
  'final_trade_decision',
];

const MARKET_TAPE_PERIODS = [
  { label: '1D', period: '1d', interval: '5m' },
  { label: '1W', period: '5d', interval: '1d' },
  { label: '1M', period: '1mo', interval: '1d' },
  { label: '1Y', period: '1y', interval: '1d' },
] as const;

const BRIEF_FONT_FAMILY = 'Menlo, Monaco, "Courier New", monospace';
const BRIEF_SECTION_TOKENS = ['market_highlights', 'key_signals', 'what_to_watch', 'risks_opportunities'];

const latestBriefMarkdownComponents = {
  h2: ({ children, ...props }: ComponentProps<'h2'>) => (
    <h2 className="mb-1 mt-4 text-sm font-semibold tracking-wide text-emerald-200 first:mt-0" {...props}>
      {children}
    </h2>
  ),
  p: ({ children, ...props }: ComponentProps<'p'>) => (
    <p className="my-0 whitespace-pre-wrap text-xs leading-5 text-slate-200" style={{ fontFamily: BRIEF_FONT_FAMILY }} {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }: ComponentProps<'ul'>) => (
    <ul className="my-0 list-disc space-y-1 pl-5 text-xs text-slate-200" style={{ fontFamily: BRIEF_FONT_FAMILY }} {...props}>
      {children}
    </ul>
  ),
  li: ({ children, ...props }: ComponentProps<'li'>) => (
    <li className="leading-5" {...props}>{children}</li>
  ),
};

function average(values: Array<number | null | undefined>): number | null {
  const valid = values.filter((value): value is number => value != null && Number.isFinite(value));
  if (valid.length === 0) return null;
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

function formatPercent(value: number | null | undefined, digits: number = 2): string {
  if (value == null || Number.isNaN(value)) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}%`;
}

function formatCompactNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

function formatSectorAbbreviation(value: string | null | undefined): string {
  if (!value) return 'UNKN';

  const normalized = value.trim().toLowerCase();
  const sectorMap: Record<string, string> = {
    technology: 'TECH',
    healthcare: 'HLTH',
    'financial services': 'FINS',
    'consumer cyclical': 'CYCL',
    'consumer defensive': 'DEFE',
    'communication services': 'COMM',
    industrials: 'INDS',
    energy: 'ENER',
    utilities: 'UTIL',
    'real estate': 'REAL',
    'basic materials': 'MATR',
    materials: 'MATR',
    'consumer staples': 'STAP',
  };

  if (sectorMap[normalized]) return sectorMap[normalized];

  const compact = normalized.replace(/[^a-z]/g, '').toUpperCase();
  if (compact.length >= 4) return compact.slice(0, 4);
  return compact.padEnd(4, 'X');
}

function formatMaybePrice(value: number | null | undefined, currency?: string | null): string {
  if (value == null || Number.isNaN(value)) return '—';
  return formatPrice(value, currency);
}

function MiniSparkline({
  chartData,
  isPositive,
}: {
  chartData: SparklineData | null;
  isPositive: boolean;
}) {
  const width = 72;
  const height = 18;
  const pad = 1;

  if (!chartData || chartData.closes.length < 2) {
    return <div className="h-[18px] w-[72px] shrink-0 rounded bg-slate-800/80" />;
  }

  const { closes: points, openPrice } = chartData;
  const min = Math.min(...points, openPrice);
  const max = Math.max(...points, openPrice);
  const range = max - min || 1;
  const xs = points.map((_, i) => pad + (i / (points.length - 1)) * (width - 2 * pad));
  const ys = points.map((p) => height - pad - ((p - min) / range) * (height - 2 * pad));
  const d = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x} ${ys[i]}`).join(' ');
  const stroke = isPositive ? '#34d399' : '#f87171';
  const openY = height - pad - ((openPrice - min) / range) * (height - 2 * pad);

  return (
    <svg width={width} height={height} className="shrink-0 overflow-hidden rounded" aria-hidden>
      <line
        x1={pad}
        y1={openY}
        x2={width - pad}
        y2={openY}
        stroke="#64748b"
        strokeWidth="0.8"
        strokeDasharray="2 1"
      />
      <path d={d} fill="none" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function normalizeRecommendation(value: string | null | undefined): 'BUY' | 'HOLD' | 'SELL' | 'NO AI' {
  if (!value) return 'NO AI';
  const upper = value.toUpperCase();
  if (upper === 'BUY' || upper === 'HOLD' || upper === 'SELL') return upper;
  return 'NO AI';
}

function formatRecommendationLabel(value: string | null | undefined): string {
  return normalizeRecommendation(value) === 'NO AI' ? 'N/A' : normalizeRecommendation(value);
}

function badgeClassForRecommendation(value: string | null | undefined): string {
  const normalized = normalizeRecommendation(value);
  if (normalized === 'BUY') return 'border-emerald-400/40 bg-emerald-500/15 text-emerald-300';
  if (normalized === 'SELL') return 'border-rose-400/40 bg-rose-500/15 text-rose-300';
  if (normalized === 'HOLD') return 'border-amber-400/40 bg-amber-500/15 text-amber-300';
  return 'border-slate-500/40 bg-slate-500/15 text-slate-300';
}

function cardClassForRecommendation(value: string): string {
  if (value === 'BUY') return 'border border-emerald-400/20 bg-[linear-gradient(180deg,rgba(16,185,129,0.18),rgba(6,78,59,0.38))] text-emerald-50';
  if (value === 'SELL') return 'border border-rose-400/20 bg-[linear-gradient(180deg,rgba(244,63,94,0.18),rgba(76,5,25,0.38))] text-rose-50';
  if (value === 'HOLD') return 'border border-amber-400/20 bg-[linear-gradient(180deg,rgba(245,158,11,0.2),rgba(120,53,15,0.38))] text-amber-50';
  return 'border border-slate-500/20 bg-[linear-gradient(180deg,rgba(100,116,139,0.18),rgba(30,41,59,0.42))] text-slate-50';
}

function getWidgetConfidence(widget: TickerWidget): number | null {
  if (widget.confidence != null && widget.confidence >= 0 && widget.confidence <= 1) {
    return widget.confidence;
  }
  const finalDecision = widget.report_scores?.final_trade_decision?.score;
  if (finalDecision != null && finalDecision >= 0 && finalDecision <= 10) {
    return finalDecision / 10;
  }
  return null;
}

function getCompositeSignalScore(widget: TickerWidget): number | null {
  const research = widget.report_scores?.investment_plan?.score ?? null;
  const finalDecision = widget.report_scores?.final_trade_decision?.score ?? null;
  const confidence = getWidgetConfidence(widget);
  return average([research, finalDecision, confidence != null ? confidence * 10 : null]);
}

function getExcerpt(text: string, maxLength: number): string {
  const trimmed = text.trim().replace(/\s+/g, ' ');
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength).trimEnd()}...`;
}

function briefHasStructuredSections(narrative: string): boolean {
  return /##\s*(Market Highlights|What to Watch|Risks\s*&\s*Opportunities)/i.test(narrative);
}

function narrativeForDisplay(narrative: string): string {
  if (!briefHasStructuredSections(narrative)) return narrative;
  const tokenSet = new Set(BRIEF_SECTION_TOKENS);
  return narrative
    .split('\n')
    .filter((line) => !tokenSet.has(line.trim()))
    .join('\n');
}

function getMarkdownExcerpt(text: string, maxLength: number): string {
  const trimmed = text.trim();
  if (trimmed.length <= maxLength) return trimmed;
  const slice = trimmed.slice(0, maxLength);
  const lastBreak = Math.max(slice.lastIndexOf('\n'), slice.lastIndexOf(' '));
  const cutoff = lastBreak >= Math.floor(maxLength * 0.6) ? lastBreak : maxLength;
  return `${slice.slice(0, cutoff).trimEnd()}\n\n...`;
}

function DashboardPanel({
  title,
  subtitle,
  action,
  children,
  className = '',
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-[1.1rem] border border-slate-700/80 bg-slate-900/80 shadow-[0_14px_40px_rgba(2,6,23,0.28)] backdrop-blur-sm ${className}`}>
      <div className="flex items-start justify-between gap-4 border-b border-slate-700/70 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function StatTile({
  label,
  value,
  hint,
  accentClass,
}: {
  label: string;
  value: string;
  hint?: string;
  accentClass?: string;
}) {
  return (
    <div className={`rounded-[0.9rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2 ${accentClass ?? ''}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className="mt-1 text-[1.1rem] font-semibold leading-none text-white">{value}</p>
      {hint && <p className="mt-1 truncate text-[11px] text-slate-400">{hint}</p>}
    </div>
  );
}

function ChangePill({ value }: { value: number | null | undefined }) {
  const positive = (value ?? 0) >= 0;
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold tabular-nums ${
      value == null
        ? 'border-slate-600/70 bg-slate-800/60 text-slate-300'
        : positive
          ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-300'
          : 'border-rose-400/30 bg-rose-500/15 text-rose-300'
    }`}>
      {formatPercent(value)}
    </span>
  );
}

function ScoreFillLine({
  label,
  score,
}: {
  label: string;
  score: number | null;
}) {
  if (score == null) {
    return (
      <div className="rounded-[0.95rem] border border-dashed border-slate-700 bg-slate-950/40 px-3 py-4 text-sm text-slate-500">
        No score data
      </div>
    );
  }

  const clamped = Math.max(0, Math.min(10, score));
  const barClass =
    clamped >= 7
      ? 'bg-emerald-400'
      : clamped >= 5
        ? 'bg-amber-400'
        : 'bg-rose-400';

  return (
    <div className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-300">{label}</span>
        <span className={`text-xs font-semibold ${getScoreColor(clamped)}`}>{clamped.toFixed(1)}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full ${barClass}`}
          style={{ width: `${(clamped / 10) * 100}%` }}
        />
      </div>
    </div>
  );
}

function RecommendationDonut({
  data,
  total,
}: {
  data: Array<{ name: string; value: number }>;
  total: number;
}) {
  if (total === 0) {
    return <div className="flex h-[190px] items-center justify-center text-sm text-slate-500">No portfolio signals yet.</div>;
  }

  return (
    <div className="mx-auto h-[160px] w-full max-w-[220px] sm:h-[190px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="44%"
            outerRadius="72%"
            paddingAngle={2}
            stroke="rgba(15, 23, 42, 0.7)"
            strokeWidth={2}
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={RECOMMENDATION_COLORS[entry.name] ?? '#64748b'} />
            ))}
          </Pie>
          <Tooltip
            cursor={false}
            content={({ active, payload }) => {
              if (!active || !payload || payload.length === 0) return null;
              const point = payload[0] as { name?: string; value?: number };
              const value = point.value ?? 0;
              const percent = total > 0 ? (value / total) * 100 : 0;

              return (
                <div className="rounded-xl border border-slate-600/80 bg-slate-950/95 px-3 py-2 shadow-[0_12px_30px_rgba(2,6,23,0.45)]">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    {formatRecommendationLabel(point.name)}
                  </div>
                  <div className="mt-1 text-sm font-semibold text-white">{value} tracked tickers</div>
                  <div className="text-[11px] text-slate-400">{percent.toFixed(0)}% of coverage</div>
                </div>
              );
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function MoversList({
  rows,
  onSelectTicker,
}: {
  rows: MarketMoverRow[];
  onSelectTicker: (ticker: string) => void;
}) {
  if (rows.length === 0) {
    return <div className="rounded-2xl border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-500">No mover data available.</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
      {rows.map((row) => {
        const symbol = row.symbol ?? '';
        const sectorLabel = formatSectorAbbreviation(row.sector || row.industry);
        const companyName = row.shortName || 'Unknown company';
        return (
          <button
            key={`${symbol}-${row.shortName ?? ''}`}
            type="button"
            onClick={() => symbol && onSelectTicker(symbol)}
            className="grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 overflow-hidden rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2.5 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
          >
            <span className="truncate text-[11px] font-semibold text-white">{symbol || '—'}</span>
            <span className={`shrink-0 whitespace-nowrap text-right text-xs font-semibold ${((row.regularMarketChangePercent ?? 0) >= 0) ? 'text-emerald-300' : 'text-rose-300'}`}>
              {formatPercent(row.regularMarketChangePercent)}
            </span>
            <p className="truncate text-[11px] leading-4 text-slate-400">{sectorLabel}</p>
            <p className="shrink-0 whitespace-nowrap text-right text-[11px] leading-4 text-slate-400">
              {formatCompactNumber(row.regularMarketVolume)}
            </p>
            <p className="col-span-2 truncate text-[11px] leading-4 text-slate-300">{companyName}</p>
          </button>
        );
      })}
    </div>
  );
}

export default function PortfolioPulseDashboard({
  widgets,
  tickerToName,
}: PortfolioPulseDashboardProps) {
  const navigate = useNavigate();
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  const tickers = useMemo(() => widgets.map((widget) => widget.ticker), [widgets]);
  const tickersKey = tickers.join(',');
  const [companyInfoMap, setCompanyInfoMap] = useState<Record<string, CompanyInfo>>({});
  const [overview, setOverview] = useState<MarketOverviewResponse | null>(null);
  const [marketMovers, setMarketMovers] = useState<{
    gainers: MarketMoverRow[];
    losers: MarketMoverRow[];
    most_active: MarketMoverRow[];
  }>({ gainers: [], losers: [], most_active: [] });
  const [portfolioNews, setPortfolioNews] = useState<NewsArticle[]>([]);
  const [latestBriefs, setLatestBriefs] = useState<{ daily: DigestBriefItem | null; weekly: DigestBriefItem | null }>({
    daily: null,
    weekly: null,
  });
  const [marketTapeCharts, setMarketTapeCharts] = useState<Record<string, SparklineData>>({});
  const [isLoadingCompanyInfo, setIsLoadingCompanyInfo] = useState(false);
  const [isLoadingMarket, setIsLoadingMarket] = useState(true);
  const [isLoadingBrief, setIsLoadingBrief] = useState(false);
  const [latestBriefMode, setLatestBriefMode] = useState<'daily' | 'weekly'>('daily');
  const [moversTab, setMoversTab] = useState<'gainers' | 'losers' | 'most_active'>('gainers');
  const [marketTapePeriod, setMarketTapePeriod] = useState<(typeof MARKET_TAPE_PERIODS)[number]['period']>('1mo');

  useEffect(() => {
    let cancelled = false;

    if (widgets.length === 0) {
      setCompanyInfoMap({});
      setIsLoadingCompanyInfo(false);
      return () => {
        cancelled = true;
      };
    }

    const fetchCompanyInfo = async () => {
      setIsLoadingCompanyInfo(true);
      try {
        const results = await Promise.allSettled(
          widgets.map(async (widget) => [widget.ticker, await tickerApi.getCompanyInfo(widget.ticker)] as const)
        );

        if (cancelled) return;

        const nextMap: Record<string, CompanyInfo> = {};
        results.forEach((result) => {
          if (result.status === 'fulfilled') {
            const [ticker, info] = result.value;
            nextMap[ticker] = info;
          }
        });
        setCompanyInfoMap(nextMap);
      } finally {
        if (!cancelled) setIsLoadingCompanyInfo(false);
      }
    };

    fetchCompanyInfo().catch(() => {
      if (!cancelled) {
        setCompanyInfoMap({});
        setIsLoadingCompanyInfo(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [tickersKey, widgets]);

  useEffect(() => {
    let cancelled = false;

    const fetchMarketData = async () => {
      setIsLoadingMarket(true);
      try {
        const [overviewResult, moversResult, newsResult] = await Promise.allSettled([
          tickerApi.getMarketOverview({
            limit_indices: 6,
            limit_sectors: 8,
            limit_regions: 20,
            limit_commodities: 4,
            range: '1d',
          }),
          tickerApi.getMarketMovers(6),
          tickers.length > 0 ? tickerApi.getNewsBatch(tickers) : Promise.resolve({ articles: [], count: 0 }),
        ]);

        if (cancelled) return;

        setOverview(overviewResult.status === 'fulfilled' ? overviewResult.value : null);
        setMarketMovers(moversResult.status === 'fulfilled'
          ? moversResult.value
          : { gainers: [], losers: [], most_active: [] });
        setPortfolioNews(newsResult.status === 'fulfilled' ? newsResult.value.articles.slice(0, 8) : []);
      } finally {
        if (!cancelled) setIsLoadingMarket(false);
      }
    };

    fetchMarketData().catch(() => {
      if (!cancelled) {
        setOverview(null);
        setMarketMovers({ gainers: [], losers: [], most_active: [] });
        setPortfolioNews([]);
        setIsLoadingMarket(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [tickersKey, tickers]);

  useEffect(() => {
    let cancelled = false;
    const tapeTickers = (overview?.indices ?? []).slice(0, 6).map((item) => item.ticker).filter(Boolean);
    const tapePeriodConfig = MARKET_TAPE_PERIODS.find((option) => option.period === marketTapePeriod) ?? MARKET_TAPE_PERIODS[2];

    if (tapeTickers.length === 0) {
      setMarketTapeCharts({});
      return () => {
        cancelled = true;
      };
    }

    const fetchTapeCharts = async () => {
      try {
        const results = await Promise.allSettled(
          tapeTickers.map(async (ticker) => {
            const res = await tickerApi.getHistoricalPrices(ticker, tapePeriodConfig.period, tapePeriodConfig.interval);
            const points = (res?.data ?? []).map((item: { open: number; close: number }) => item.close).filter((close: number) => close > 0);
            const firstOpen = res?.data?.[0]?.open;
            if (points.length < 2) return null;
            return [
              ticker,
              {
                closes: points,
                openPrice: firstOpen != null && firstOpen > 0 ? firstOpen : points[0],
              },
            ] as const;
          })
        );

        if (cancelled) return;

        const next: Record<string, SparklineData> = {};
        results.forEach((result) => {
          if (result.status === 'fulfilled' && result.value) {
            const [ticker, data] = result.value;
            next[ticker] = data;
          }
        });
        setMarketTapeCharts(next);
      } catch {
        if (!cancelled) setMarketTapeCharts({});
      }
    };

    fetchTapeCharts();

    return () => {
      cancelled = true;
    };
  }, [marketTapePeriod, overview]);

  useEffect(() => {
    let cancelled = false;

    const fetchLatestBrief = async () => {
      setIsLoadingBrief(true);
      try {
        const datesResponse = await digestApi.getDigestDates(21, browserTimezone);
        const dailySlots = datesResponse.dates.filter((slot) => !slot.startsWith('w:'));
        const weeklySlots = datesResponse.dates.filter((slot) => slot.startsWith('w:'));
        const latestDailySlot = dailySlots[dailySlots.length - 1] ?? null;
        const latestWeeklySlot = weeklySlots[weeklySlots.length - 1] ?? null;

        const [dailyResponse, weeklyResponse] = await Promise.allSettled([
          latestDailySlot ? digestApi.getDigestsForDate(latestDailySlot, browserTimezone) : Promise.resolve({ date: '', briefs: [] }),
          latestWeeklySlot ? digestApi.getDigestsForDate(latestWeeklySlot, browserTimezone) : Promise.resolve({ date: '', briefs: [] }),
        ]);

        if (!cancelled) {
          const dailyBrief = dailyResponse.status === 'fulfilled' ? dailyResponse.value.briefs[0] ?? null : null;
          const weeklyBrief = weeklyResponse.status === 'fulfilled' ? weeklyResponse.value.briefs[0] ?? null : null;
          setLatestBriefs({ daily: dailyBrief, weekly: weeklyBrief });
          setLatestBriefMode((prev) => {
            if (prev === 'weekly' && !weeklyBrief && dailyBrief) return 'daily';
            if (prev === 'daily' && !dailyBrief && weeklyBrief) return 'weekly';
            return prev;
          });
        }
      } catch {
        if (!cancelled) setLatestBriefs({ daily: null, weekly: null });
      } finally {
        if (!cancelled) setIsLoadingBrief(false);
      }
    };

    fetchLatestBrief().catch(() => {
      if (!cancelled) {
        setLatestBriefs({ daily: null, weekly: null });
        setIsLoadingBrief(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [browserTimezone, tickersKey]);

  const recommendationBreakdown = useMemo(() => {
    const counts = new Map<string, number>([
      ['BUY', 0],
      ['HOLD', 0],
      ['SELL', 0],
      ['NO AI', 0],
    ]);

    widgets.forEach((widget) => {
      const key = normalizeRecommendation(widget.recommendation);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });

    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .filter((entry) => entry.value > 0);
  }, [widgets]);
  const recommendationCards = useMemo(
    () => ['BUY', 'HOLD', 'SELL', 'NO AI'].map((name) => ({
      name,
      value: recommendationBreakdown.find((entry) => entry.name === name)?.value ?? 0,
    })),
    [recommendationBreakdown]
  );

  const portfolioSummary = useMemo(() => {
    const reportCoverage = widgets.filter((widget) => widget.has_report).length;
    const advancers = widgets.filter((widget) => widget.daily_change_percent > 0).length;
    const decliners = widgets.filter((widget) => widget.daily_change_percent < 0).length;
    const avgMove = average(widgets.map((widget) => widget.daily_change_percent));
    const avgConfidence = average(widgets.map((widget) => {
      const confidence = getWidgetConfidence(widget);
      return confidence != null ? confidence * 100 : null;
    }));
    const bestPerformer = [...widgets].sort((a, b) => b.daily_change_percent - a.daily_change_percent)[0] ?? null;
    const worstPerformer = [...widgets].sort((a, b) => a.daily_change_percent - b.daily_change_percent)[0] ?? null;

    const sectorCounts = new Map<string, number>();
    const countryCounts = new Map<string, number>();
    const exchangeCounts = new Map<string, number>();
    const reportScoreSums = new Map<string, { sum: number; count: number }>();

    widgets.forEach((widget) => {
      const companyInfo = companyInfoMap[widget.ticker];
      const sector = companyInfo?.sector?.trim() || 'Unclassified';
      const country = companyInfo?.country?.trim() || 'Unknown';
      const exchange = companyInfo?.exchange?.trim() || 'Unknown';

      sectorCounts.set(sector, (sectorCounts.get(sector) ?? 0) + 1);
      countryCounts.set(country, (countryCounts.get(country) ?? 0) + 1);
      exchangeCounts.set(exchange, (exchangeCounts.get(exchange) ?? 0) + 1);

      getAnalysisScoreEntries(widget.report_scores).forEach(([reportType, scoreSummary]) => {
        if (scoreSummary.score == null) return;
        const current = reportScoreSums.get(reportType) ?? { sum: 0, count: 0 };
        reportScoreSums.set(reportType, {
          sum: current.sum + scoreSummary.score,
          count: current.count + 1,
        });
      });
    });

    const sectorExposure = Array.from(sectorCounts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
    const countryExposure = Array.from(countryCounts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
    const exchangeExposure = Array.from(exchangeCounts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
    const averageScores = SCORE_ORDER
      .map((reportType) => {
        const stats = reportScoreSums.get(reportType);
        return {
          reportType,
          label: formatReportKey(reportType),
          averageScore: stats && stats.count > 0 ? stats.sum / stats.count : null,
          count: stats?.count ?? 0,
        };
      })
      .filter((item) => item.averageScore != null);

    const convictionRows = widgets
      .map((widget) => ({
        ticker: widget.ticker,
        name: widget.name || tickerToName[widget.ticker] || widget.ticker,
        recommendation: normalizeRecommendation(widget.recommendation),
        confidence: getWidgetConfidence(widget),
        signalScore: getCompositeSignalScore(widget),
        dailyChangePercent: widget.daily_change_percent,
        reportDate: widget.report_date,
      }))
      .sort((a, b) => {
        const scoreA = a.signalScore ?? -1;
        const scoreB = b.signalScore ?? -1;
        if (scoreA !== scoreB) return scoreB - scoreA;
        const confidenceA = a.confidence ?? -1;
        const confidenceB = b.confidence ?? -1;
        return confidenceB - confidenceA;
      });

    return {
      reportCoverage,
      advancers,
      decliners,
      avgMove,
      avgConfidence,
      bestPerformer,
      worstPerformer,
      sectorExposure,
      countryExposure,
      exchangeExposure,
      averageScores,
      convictionRows,
    };
  }, [companyInfoMap, tickerToName, widgets]);

  const marketSummary = useMemo(() => {
    if (!overview) {
      return {
        sectorsUp: 0,
        sectorsDown: 0,
        leader: null as OverviewItem | null,
        laggard: null as OverviewItem | null,
      };
    }

    const sortedSectors = [...overview.sectors].sort(
      (a, b) => (b.changePercent ?? -Infinity) - (a.changePercent ?? -Infinity)
    );
    return {
      sectorsUp: overview.sectors.filter((sector) => (sector.changePercent ?? 0) > 0).length,
      sectorsDown: overview.sectors.filter((sector) => (sector.changePercent ?? 0) < 0).length,
      leader: sortedSectors[0] ?? null,
      laggard: sortedSectors[sortedSectors.length - 1] ?? null,
    };
  }, [overview]);

  const activeBrief = latestBriefs[latestBriefMode];
  const briefNarrativePreview = activeBrief
    ? getMarkdownExcerpt(
      briefHasStructuredSections(activeBrief.narrative)
        ? narrativeForDisplay(activeBrief.narrative)
        : activeBrief.narrative,
      800,
    )
    : '';
  const briefWatchPreview = activeBrief ? getExcerpt(activeBrief.what_to_watch, 120) : '';

  const focusSnapshotEntries = useMemo(() => {
    if (!activeBrief?.focus_snapshot) return [];
    return Object.entries(activeBrief.focus_snapshot).slice(0, 5);
  }, [activeBrief]);

  const heroSummary = useMemo(() => {
    if (widgets.length === 0) {
      return 'Build a tracked portfolio to combine Flowdeck analysis with live market breadth, sectors, movers, and headline risk.';
    }

    const positiveCount = portfolioSummary.advancers;
    const total = widgets.length;
    const best = portfolioSummary.bestPerformer
      ? `${portfolioSummary.bestPerformer.ticker} ${formatPercent(portfolioSummary.bestPerformer.daily_change_percent)}`
      : 'No clear leader';
    const leaderSector = marketSummary.leader
      ? `${marketSummary.leader.name} ${formatPercent(marketSummary.leader.changePercent)}`
      : 'Sector leadership unavailable';

    return `${positiveCount}/${total} tracked tickers are green today. Best relative move: ${best}. Market leadership is coming from ${leaderSector}.`;
  }, [marketSummary.leader, portfolioSummary.advancers, portfolioSummary.bestPerformer, widgets.length]);

  const marketMoverRows = marketMovers[moversTab] ?? [];
  const topExposureMax = Math.max(1, ...(portfolioSummary.sectorExposure.slice(0, 6).map((item) => item.count)));
  const topConvictionRows = [
    ...portfolioSummary.convictionRows.slice(0, 6),
    ...Array.from({ length: Math.max(0, 6 - portfolioSummary.convictionRows.length) }, () => null),
  ];
  const radarWidgets = widgets
    .map((widget) => ({
      widget,
      scoreEntries: getAnalysisScoreEntries(widget.report_scores),
    }))
    .filter(({ scoreEntries }) => scoreEntries.some(([, score]) => score.score != null))
    .slice(0, 8);
  const latestBriefPanel = (
    <section className="rounded-[1.1rem] border border-slate-700/80 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(17,24,39,0.84))] p-4 shadow-[0_14px_40px_rgba(2,6,23,0.28)]">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Brief Snapshot</p>
          <p className="mt-0.5 text-xs text-slate-400">Saved AI market-plus-portfolio narrative.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-full border border-slate-700/70 bg-slate-950/40 p-1">
            {([
              ['daily', 'Daily'],
              ['weekly', 'Weekly'],
            ] as const).map(([mode, label]) => {
              const hasBrief = latestBriefs[mode] != null;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => hasBrief && setLatestBriefMode(mode)}
                  disabled={!hasBrief}
                  className={`rounded-full px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                    latestBriefMode === mode
                      ? 'bg-slate-200 text-slate-900'
                      : hasBrief
                        ? 'text-slate-300 hover:bg-slate-800'
                        : 'cursor-not-allowed text-slate-600'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <Link
            to="/brief"
            className="rounded-full border border-emerald-400/30 bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-100 transition-colors hover:bg-emerald-500/20"
          >
            Open Brief
          </Link>
        </div>
      </div>
      {isLoadingBrief ? (
        <div className="space-y-2.5">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-800" />
          <div className="h-16 animate-pulse rounded-[1rem] bg-slate-800" />
          <div className="h-14 animate-pulse rounded-[1rem] bg-slate-800" />
        </div>
      ) : activeBrief ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span className="rounded-full border border-slate-600/80 bg-slate-900/70 px-2.5 py-1">{activeBrief.span_label || activeBrief.span_type || (latestBriefMode === 'weekly' ? 'Weekly' : 'Daily')}</span>
            <span>{activeBrief.digest_date}</span>
          </div>
          <div className="min-h-[240px] rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown components={latestBriefMarkdownComponents}>
                {briefNarrativePreview}
              </ReactMarkdown>
            </div>
          </div>
          {focusSnapshotEntries.length > 0 && (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {focusSnapshotEntries.slice(0, 4).map(([ticker, snapshot]) => (
                <button
                  key={ticker}
                  type="button"
                  onClick={() => navigate(`/tickers/${ticker}`)}
                  className="flex items-center justify-between rounded-[0.95rem] border border-slate-700/70 bg-slate-900/60 px-3 py-2 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
                >
                  <div>
                    <p className="text-sm font-semibold text-white">{ticker}</p>
                    <p className="text-[11px] text-slate-500">{snapshot.name || tickerToName[ticker] || 'Focus name'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-200">{formatMaybePrice(snapshot.price ?? null)}</p>
                    <p className={`text-[11px] font-semibold ${(snapshot.change_pct ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {formatPercent(snapshot.change_pct)}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="rounded-[1rem] border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5">
            <p className="text-[11px] uppercase tracking-[0.18em] text-emerald-100/80">Watch</p>
            <p
              className="mt-1.5 text-sm leading-6 text-emerald-50"
              style={{ fontFamily: BRIEF_FONT_FAMILY }}
            >
              {briefWatchPreview}
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-[1rem] border border-dashed border-slate-700 px-4 py-7 text-center">
          <p className="text-sm text-slate-300">No saved {latestBriefMode} brief yet.</p>
          <Link
            to="/brief"
            className="mt-3 inline-flex rounded-full border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/20"
          >
            Generate brief
          </Link>
        </div>
      )}
    </section>
  );
  const recommendationPanel = (
    <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
      <div className="mb-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Recommendation Mix</p>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.18fr_0.82fr] lg:items-center">
        <RecommendationDonut data={recommendationBreakdown} total={widgets.length} />
        <div>
          {widgets.length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {recommendationCards.map((entry) => (
                <div
                  key={entry.name}
                  className={`flex min-h-[84px] flex-col items-center justify-between rounded-[0.95rem] px-3 py-2 ${cardClassForRecommendation(entry.name)}`}
                >
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-80">{formatRecommendationLabel(entry.name)}</div>
                  <div className="text-2xl font-semibold tabular-nums">{entry.value}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-5 text-sm text-slate-500">
              No recommendation mix available yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
  const moversControls = (
    <div className="flex items-center gap-1 rounded-full border border-slate-700/70 bg-slate-950/40 p-1">
      {([
        ['gainers', 'Gainers'],
        ['losers', 'Losers'],
        ['most_active', 'Active'],
      ] as const).map(([tabId, label]) => (
        <button
          key={tabId}
          type="button"
          onClick={() => setMoversTab(tabId)}
          className={`rounded-full px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
            moversTab === tabId
              ? 'bg-slate-200 text-slate-900'
              : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
  const sectorExposurePanel = (
    <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Portfolio Sector Exposure</p>
        {isLoadingCompanyInfo && <span className="text-[11px] text-slate-500">Refreshing...</span>}
      </div>
      {portfolioSummary.sectorExposure.length > 0 ? (
        <div className="space-y-2">
          {portfolioSummary.sectorExposure.slice(0, 5).map((item) => (
            <div key={item.label}>
              <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                <span className="truncate text-slate-300">{item.label}</span>
                <span className="font-semibold text-white">{item.count}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,#22d3ee,#34d399)]"
                  style={{ width: `${(item.count / topExposureMax) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-5 text-sm text-slate-500">
          Subscribe to stocks to reveal sector distribution.
        </div>
      )}
    </div>
  );
  const portfolioExtremesPanel = (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Top Gainer</p>
        {portfolioSummary.bestPerformer ? (
          <button
            type="button"
            onClick={() => navigate(`/tickers/${portfolioSummary.bestPerformer.ticker}`)}
            className="mt-1.5 flex w-full items-center justify-between rounded-[0.8rem] border border-slate-700/70 bg-slate-900/70 px-2.5 py-2 text-left transition-colors hover:border-slate-500/70"
          >
            <div>
              <p className="text-xs font-semibold text-white">{portfolioSummary.bestPerformer.ticker}</p>
              <p className="text-[11px] text-slate-500">{portfolioSummary.bestPerformer.name || tickerToName[portfolioSummary.bestPerformer.ticker] || portfolioSummary.bestPerformer.ticker}</p>
            </div>
            <div className="text-right">
              <p className="text-[11px] text-slate-200">{formatPrice(portfolioSummary.bestPerformer.current_price, portfolioSummary.bestPerformer.currency)}</p>
              <p className="text-[11px] font-semibold text-emerald-300">{formatPercent(portfolioSummary.bestPerformer.daily_change_percent)}</p>
            </div>
          </button>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No tracked tickers yet.</p>
        )}
      </div>
      <div className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Biggest Decliner</p>
        {portfolioSummary.worstPerformer ? (
          <button
            type="button"
            onClick={() => navigate(`/tickers/${portfolioSummary.worstPerformer.ticker}`)}
            className="mt-1.5 flex w-full items-center justify-between rounded-[0.8rem] border border-slate-700/70 bg-slate-900/70 px-2.5 py-2 text-left transition-colors hover:border-slate-500/70"
          >
            <div>
              <p className="text-xs font-semibold text-white">{portfolioSummary.worstPerformer.ticker}</p>
              <p className="text-[11px] text-slate-500">{portfolioSummary.worstPerformer.name || tickerToName[portfolioSummary.worstPerformer.ticker] || portfolioSummary.worstPerformer.ticker}</p>
            </div>
            <div className="text-right">
              <p className="text-[11px] text-slate-200">{formatPrice(portfolioSummary.worstPerformer.current_price, portfolioSummary.worstPerformer.currency)}</p>
              <p className="text-[11px] font-semibold text-rose-300">{formatPercent(portfolioSummary.worstPerformer.daily_change_percent)}</p>
            </div>
          </button>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No tracked tickers yet.</p>
        )}
      </div>
    </div>
  );
  const marketMoversPanel = (
    <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Broader Market Movers</p>
        {moversControls}
      </div>
      <MoversList rows={marketMoverRows.slice(0, 6)} onSelectTicker={(ticker) => navigate(`/tickers/${ticker}`)} />
    </div>
  );
  const signalsPanel = (
    <DashboardPanel
      title="Market Snapshot & Movers"
      subtitle="Sector breadth, standout movers, and index action around your tracked tickers."
    >
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-[0.95rem] border border-emerald-400/20 bg-emerald-500/10 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-100/80">Leader</p>
                <p className="mt-1.5 text-sm font-semibold text-white">{marketSummary.leader?.name || '—'}</p>
                <p className="mt-1 text-xs text-emerald-100/80">{formatPercent(marketSummary.leader?.changePercent)}</p>
              </div>
              <div className="rounded-[0.95rem] border border-rose-400/20 bg-rose-500/10 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-100/80">Laggard</p>
                <p className="mt-1.5 text-sm font-semibold text-white">{marketSummary.laggard?.name || '—'}</p>
                <p className="mt-1 text-xs text-rose-100/80">{formatPercent(marketSummary.laggard?.changePercent)}</p>
              </div>
            </div>

            {overview ? (
              <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Sector Breadth</p>
                  <span className="text-[11px] text-slate-400">
                    Breadth {overview.sectors.length > 0 ? `${marketSummary.sectorsUp}/${overview.sectors.length}` : '—'}
                  </span>
                </div>
                <div className="h-[180px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[...overview.sectors]
                        .sort((a, b) => (b.changePercent ?? -Infinity) - (a.changePercent ?? -Infinity))
                        .slice(0, 6)
                        .map((item) => ({
                          name: item.name.replace(' Select Sector SPDR Fund', '').replace('Communication Services', 'Comm'),
                          changePercent: item.changePercent ?? 0,
                        }))}
                      margin={{ top: 8, right: 8, left: -20, bottom: 0 }}
                    >
                      <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(value) => `${value}%`} />
                      <Tooltip
                        contentStyle={{
                          background: '#0f172a',
                          border: '1px solid rgba(71, 85, 105, 0.9)',
                          borderRadius: '0.75rem',
                          color: '#e2e8f0',
                        }}
                        formatter={(value) => [formatPercent(typeof value === 'number' ? value : null), 'Change']}
                      />
                      <Bar dataKey="changePercent" radius={[8, 8, 0, 0]}>
                        {[...overview.sectors]
                          .sort((a, b) => (b.changePercent ?? -Infinity) - (a.changePercent ?? -Infinity))
                          .slice(0, 6)
                          .map((item) => (
                            <Cell key={item.ticker} fill={(item.changePercent ?? 0) >= 0 ? '#34d399' : '#f87171'} />
                          ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-5 text-sm text-slate-500">
                {isLoadingMarket ? 'Loading market pulse...' : 'Market pulse unavailable.'}
              </div>
            )}
          </div>
          {marketMoversPanel}
        </div>

        <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Index Tape</p>
              {marketSummary.leader && (
                <span className="text-[11px] text-slate-400">Leader {marketSummary.leader.ticker}</span>
              )}
            </div>
            <div className="flex items-center gap-1 rounded-full border border-slate-700/70 bg-slate-900/70 p-1">
              {MARKET_TAPE_PERIODS.map((option) => (
                <button
                  key={option.period}
                  type="button"
                  onClick={() => setMarketTapePeriod(option.period)}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
                    marketTapePeriod === option.period
                      ? 'bg-slate-200 text-slate-900'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {(overview?.indices ?? []).slice(0, 6).map((indexItem) => (
              <button
                key={indexItem.ticker}
                type="button"
                onClick={() => navigate(`/tickers/${indexItem.ticker}`)}
                className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-2 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
              >
                <div className="min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-xs font-semibold text-white">{indexItem.ticker}</p>
                    <ChangePill value={indexItem.changePercent} />
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-slate-400">{indexItem.name}</p>
                  <div className="mt-1 flex items-end justify-between gap-2">
                    <p className="text-xs font-semibold text-slate-200">{formatMaybePrice(indexItem.price)}</p>
                    <MiniSparkline
                      chartData={marketTapeCharts[indexItem.ticker] ?? null}
                      isPositive={(indexItem.changePercent ?? 0) >= 0}
                    />
                  </div>
                </div>
              </button>
            ))}
            {(!overview || overview.indices.length === 0) && (
              <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-5 text-sm text-slate-500">
                {isLoadingMarket ? 'Loading market overview...' : 'Market overview unavailable.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardPanel>
  );

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <section className="relative overflow-hidden rounded-[1.25rem] border border-cyan-500/20 bg-[linear-gradient(135deg,rgba(8,47,73,0.55),rgba(15,23,42,0.95)_36%,rgba(30,41,59,0.98)_100%)] px-5 py-5 shadow-[0_20px_60px_rgba(8,47,73,0.18)] xl:col-span-2">
          <div className="pointer-events-none absolute -right-16 top-0 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="pointer-events-none absolute bottom-0 left-1/3 h-32 w-32 rounded-full bg-emerald-400/10 blur-3xl" />
          <div className="relative space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-2xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-200/80">Portfolio x Market Pulse</p>
                <div className="mt-1.5 flex items-start justify-between gap-4">
                  <p className="text-sm leading-6 text-slate-300">{heroSummary}</p>
                  <Link
                    to="/market"
                    className="inline-flex shrink-0 items-center rounded-full border border-slate-500/60 bg-slate-900/60 px-3.5 py-2 text-sm font-medium text-slate-100 transition-colors hover:border-slate-400 hover:bg-slate-800"
                  >
                    Market View
                  </Link>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
              <StatTile
                label="Tracked"
                value={`${widgets.length}`}
                hint={portfolioSummary.sectorExposure[0] ? portfolioSummary.sectorExposure[0].label : 'Add names'}
                accentClass="bg-cyan-950/20"
              />
              <StatTile
                label="AI Coverage"
                value={widgets.length > 0 ? `${Math.round((portfolioSummary.reportCoverage / widgets.length) * 100)}%` : '0%'}
                hint={`${portfolioSummary.reportCoverage} reports`}
                accentClass="bg-emerald-950/20"
              />
              <StatTile
                label="Avg Move"
                value={formatPercent(portfolioSummary.avgMove)}
                hint={`${portfolioSummary.advancers} up / ${portfolioSummary.decliners} down`}
                accentClass="bg-sky-950/20"
              />
              <StatTile
                label="Breadth"
                value={overview ? `${marketSummary.sectorsUp}/${overview.sectors.length}` : '—'}
                hint="sectors green"
                accentClass="bg-indigo-950/20"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_0.95fr_1.05fr]">
              <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Average AI Scores</p>
                  {portfolioSummary.avgConfidence != null && (
                    <div className="rounded-full border border-slate-600/80 bg-slate-900/70 px-2.5 py-1 text-[11px] text-slate-300">
                      Confidence <span className="font-semibold text-white">{portfolioSummary.avgConfidence.toFixed(0)}%</span>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {portfolioSummary.averageScores.length > 0 ? (
                    portfolioSummary.averageScores.map((scoreRow) => (
                      <ScoreFillLine
                        key={scoreRow.reportType}
                        label={scoreRow.label}
                        score={scoreRow.averageScore}
                      />
                    ))
                  ) : (
                    <div className="rounded-[0.95rem] border border-dashed border-slate-700 bg-slate-950/40 px-3 py-4 text-sm text-slate-500">
                      No scored analysis runs yet.
                    </div>
                  )}
                </div>
              </div>

              {recommendationPanel}

              <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Top Conviction Names</p>
                <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                  {topConvictionRows.map((row, index) => (
                    row ? (
                      <button
                        key={row.ticker}
                        type="button"
                        onClick={() => navigate(`/tickers/${row.ticker}`)}
                        className="grid min-h-[64px] w-full grid-cols-[minmax(0,1fr)_auto] gap-x-2 gap-y-1 rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-2.5 py-2 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
                      >
                        <p className="truncate text-[13px] font-semibold text-white">{row.ticker}</p>
                        <p className="text-right text-[11px] font-semibold text-white">
                          {row.signalScore != null ? `${row.signalScore.toFixed(1)}/10` : '—'}
                        </p>
                        <span className={`inline-flex w-fit rounded-full border px-1.5 py-0.5 text-[10px] font-semibold ${badgeClassForRecommendation(row.recommendation)}`}>
                          {formatRecommendationLabel(row.recommendation)}
                        </span>
                        <p className={`text-right text-[10px] font-semibold ${row.dailyChangePercent >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {formatPercent(row.dailyChangePercent)}
                        </p>
                      </button>
                    ) : (
                      <div
                        key={`conviction-placeholder-${index}`}
                        className="flex min-h-[64px] items-center rounded-[0.95rem] border border-dashed border-slate-700 px-2.5 py-2 text-[13px] text-slate-500"
                      >
                        Run AI analysis to fill this slot.
                      </div>
                    )
                  ))}
                </div>
              </div>
            </div>

            {radarWidgets.length > 0 && (
              <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Analyzed Ticker Radar</p>
                  <span className="text-[11px] text-slate-500">Subscribed tickers with analysis</span>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
                  {radarWidgets.map(({ widget, scoreEntries }) => (
                    <button
                      key={widget.ticker}
                      type="button"
                      onClick={() => navigate(`/tickers/${widget.ticker}`)}
                      className="flex items-center gap-3 rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-3 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
                    >
                      <AspectSpiderChart scoreEntries={scoreEntries} size={68} />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white">{widget.ticker}</p>
                        <p className="mt-0.5 text-[11px] text-slate-400">
                          {widget.recommendation || 'AI scored'}
                        </p>
                        <p className={`mt-1 text-[11px] font-semibold ${widget.daily_change_percent >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {formatPercent(widget.daily_change_percent)}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {signalsPanel}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="flex min-h-[360px] flex-col gap-4">
          <DashboardPriceTrendsChart tickers={tickers} period="6mo" height={360} />
          <div className="min-h-[320px]">
            <SubscribedChangeColumnsChart widgets={widgets} height={320} />
          </div>
        </div>

        {latestBriefPanel}

        <DashboardPanel
          title="Portfolio Extremes & News"
          subtitle="Best and worst performers, sector concentration, and the latest portfolio headlines."
        >
          <div className="space-y-3">
            {portfolioExtremesPanel}
            {sectorExposurePanel}

            <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-2">
              <div className="mb-2 flex items-center justify-between px-2 py-1">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Portfolio News Feed</p>
                <span className="text-[11px] text-slate-500">{portfolioNews.length} items</span>
              </div>
              {portfolioNews.length > 0 ? (
                <div className="max-h-[380px] overflow-y-auto pr-1">
                  <div className="space-y-1.5">
                    {portfolioNews.slice(0, 10).map((article, index) => (
                      <a
                        key={article.uuid || article.link}
                        href={article.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`block rounded-[0.9rem] border px-3 py-2.5 transition-colors hover:border-slate-500/70 hover:bg-slate-900 ${
                          index % 2 === 0
                            ? 'border-slate-700/60 bg-slate-900/70'
                            : 'border-slate-800/80 bg-slate-950/60'
                        }`}
                      >
                        <div className="flex flex-wrap gap-1.5">
                          {article.tickers.slice(0, 4).map((ticker) => (
                            <span key={ticker} className="rounded-full border border-slate-600/80 bg-slate-800/80 px-2 py-0.5 text-[10px] font-medium text-slate-200">
                              {ticker}
                            </span>
                          ))}
                        </div>
                        <h3 className="mt-2 text-sm font-semibold leading-5 text-white">{article.title}</h3>
                        {article.summary && (
                          <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-slate-400">
                            {article.summary}
                          </p>
                        )}
                        <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
                          <span>{article.publisher || 'Source unavailable'}</span>
                          {article.published_time && <span>{article.published_time}</span>}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-8 text-sm text-slate-500">
                  {isLoadingMarket ? 'Loading portfolio news...' : 'No portfolio headlines right now.'}
                </div>
              )}
            </div>
          </div>
        </DashboardPanel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="min-h-[500px] xl:col-span-3">
          {overview ? (
            <WorldMapRegionalStocks
              regionalItems={overview.international}
              usIndices={overview.indices}
              onSelectTicker={(ticker) => navigate(`/tickers/${ticker}`)}
            />
          ) : (
            <DashboardPanel title="Regional Market Map" subtitle="Cross-asset view of the international backdrop." className="h-full">
              <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-4 py-14 text-center text-sm text-slate-500">
                {isLoadingMarket ? 'Loading regional map...' : 'Regional market map unavailable.'}
              </div>
            </DashboardPanel>
          )}
        </div>
      </div>
    </div>
  );
}
