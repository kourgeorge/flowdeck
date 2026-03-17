import { type ReactNode, useEffect, useMemo, useState } from 'react';
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
import { formatReportKey, getAnalysisScoreEntries, getScoreColor } from './AspectSpiderChart';
import DashboardPriceTrendsChart from './DashboardPriceTrendsChart';
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

function formatMaybePrice(value: number | null | undefined, currency?: string | null): string {
  if (value == null || Number.isNaN(value)) return '—';
  return formatPrice(value, currency);
}

function normalizeRecommendation(value: string | null | undefined): 'BUY' | 'HOLD' | 'SELL' | 'NO AI' {
  if (!value) return 'NO AI';
  const upper = value.toUpperCase();
  if (upper === 'BUY' || upper === 'HOLD' || upper === 'SELL') return upper;
  return 'NO AI';
}

function badgeClassForRecommendation(value: string | null | undefined): string {
  const normalized = normalizeRecommendation(value);
  if (normalized === 'BUY') return 'border-emerald-400/40 bg-emerald-500/15 text-emerald-300';
  if (normalized === 'SELL') return 'border-rose-400/40 bg-rose-500/15 text-rose-300';
  if (normalized === 'HOLD') return 'border-amber-400/40 bg-amber-500/15 text-amber-300';
  return 'border-slate-500/40 bg-slate-500/15 text-slate-300';
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
    <div className={`rounded-[1rem] border border-slate-700/70 bg-slate-950/40 px-3.5 py-3 ${accentClass ?? ''}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-1.5 text-[1.35rem] font-semibold text-white">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
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

function RecommendationDonut({
  data,
  total,
}: {
  data: Array<{ name: string; value: number }>;
  total: number;
}) {
  if (total === 0) {
    return <div className="flex h-[180px] items-center justify-center text-sm text-slate-500">No portfolio signals yet.</div>;
  }

  return (
    <div className="relative h-[180px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={48}
            outerRadius={72}
            paddingAngle={2}
            stroke="rgba(15, 23, 42, 0.7)"
            strokeWidth={2}
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={RECOMMENDATION_COLORS[entry.name] ?? '#64748b'} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: '#0f172a',
              border: '1px solid rgba(71, 85, 105, 0.9)',
              borderRadius: '0.75rem',
              color: '#e2e8f0',
            }}
            formatter={(value, name) => [`${value ?? 0}`, name]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Coverage</span>
        <span className="text-3xl font-semibold text-white">{total}</span>
        <span className="text-xs text-slate-500">tracked names</span>
      </div>
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
        return (
          <button
            key={`${symbol}-${row.shortName ?? ''}`}
            type="button"
            onClick={() => symbol && onSelectTicker(symbol)}
            className="grid w-full grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-white">{symbol || '—'}</span>
                <span className="truncate text-[11px] text-slate-400">{row.shortName || 'Unknown name'}</span>
              </div>
              <div className="mt-0.5 truncate text-[10px] text-slate-500">
                {row.sector || 'Sector n/a'}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-xs font-semibold text-slate-200">{formatMaybePrice(row.regularMarketPrice)}</div>
              <div className="text-[10px] text-slate-500">Vol {formatCompactNumber(row.regularMarketVolume)}</div>
            </div>
            <div className={`shrink-0 text-right text-xs font-semibold ${((row.regularMarketChangePercent ?? 0) >= 0) ? 'text-emerald-300' : 'text-rose-300'}`}>
              {formatPercent(row.regularMarketChangePercent)}
            </div>
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
  const [latestBrief, setLatestBrief] = useState<DigestBriefItem | null>(null);
  const [isLoadingCompanyInfo, setIsLoadingCompanyInfo] = useState(false);
  const [isLoadingMarket, setIsLoadingMarket] = useState(true);
  const [isLoadingBrief, setIsLoadingBrief] = useState(false);
  const [moversTab, setMoversTab] = useState<'gainers' | 'losers' | 'most_active'>('gainers');

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

    const fetchLatestBrief = async () => {
      setIsLoadingBrief(true);
      try {
        const datesResponse = await digestApi.getDigestDates(21, browserTimezone);
        const latestSlot = datesResponse.dates[datesResponse.dates.length - 1];
        if (!latestSlot) {
          if (!cancelled) setLatestBrief(null);
          return;
        }

        const briefsResponse = await digestApi.getDigestsForDate(latestSlot, browserTimezone);
        if (!cancelled) {
          setLatestBrief(briefsResponse.briefs[0] ?? null);
        }
      } catch {
        if (!cancelled) setLatestBrief(null);
      } finally {
        if (!cancelled) setIsLoadingBrief(false);
      }
    };

    fetchLatestBrief().catch(() => {
      if (!cancelled) {
        setLatestBrief(null);
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

  const focusSnapshotEntries = useMemo(() => {
    if (!latestBrief?.focus_snapshot) return [];
    return Object.entries(latestBrief.focus_snapshot).slice(0, 5);
  }, [latestBrief]);

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

    return `${positiveCount}/${total} tracked names are green today. Best relative move: ${best}. Market leadership is coming from ${leaderSector}.`;
  }, [marketSummary.leader, portfolioSummary.advancers, portfolioSummary.bestPerformer, widgets.length]);

  const marketMoverRows = marketMovers[moversTab] ?? [];
  const topExposureMax = Math.max(1, ...(portfolioSummary.sectorExposure.slice(0, 6).map((item) => item.count)));

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
                <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-300">{heroSummary}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to="/brief"
                  className="inline-flex items-center rounded-full border border-emerald-400/30 bg-emerald-500/15 px-3.5 py-2 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/20"
                >
                  Open Brief
                </Link>
                <Link
                  to="/market"
                  className="inline-flex items-center rounded-full border border-slate-500/60 bg-slate-900/60 px-3.5 py-2 text-sm font-medium text-slate-100 transition-colors hover:border-slate-400 hover:bg-slate-800"
                >
                  Market View
                </Link>
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

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">AI score ribbon</p>
                  {portfolioSummary.avgConfidence != null && (
                    <div className="rounded-full border border-slate-600/80 bg-slate-900/70 px-2.5 py-1 text-[11px] text-slate-300">
                      Confidence <span className="font-semibold text-white">{portfolioSummary.avgConfidence.toFixed(0)}%</span>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {portfolioSummary.averageScores.length > 0 ? (
                    portfolioSummary.averageScores.map((scoreRow) => (
                      <div key={scoreRow.reportType} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs text-slate-300">{scoreRow.label}</span>
                          <span className={`text-xs font-semibold ${getScoreColor(scoreRow.averageScore ?? null)}`}>
                            {(scoreRow.averageScore ?? 0).toFixed(1)}/10
                          </span>
                        </div>
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className={`h-full rounded-full ${
                              (scoreRow.averageScore ?? 0) >= 7
                                ? 'bg-emerald-400'
                                : (scoreRow.averageScore ?? 0) >= 5
                                  ? 'bg-amber-400'
                                  : 'bg-rose-400'
                            }`}
                            style={{ width: `${((scoreRow.averageScore ?? 0) / 10) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-[0.95rem] border border-dashed border-slate-700 bg-slate-950/40 px-3 py-4 text-sm text-slate-500">
                      No scored analysis runs yet.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Market tape</p>
                  {marketSummary.leader && (
                    <span className="text-[11px] text-slate-400">Leader {marketSummary.leader.ticker}</span>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {(overview?.indices ?? []).slice(0, 4).map((indexItem) => (
                    <div key={indexItem.ticker} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-2">
                      <div className="min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-xs font-semibold text-white">{indexItem.ticker}</p>
                          <ChangePill value={indexItem.changePercent} />
                        </div>
                        <p className="mt-0.5 truncate text-[11px] text-slate-400">{indexItem.name}</p>
                        <p className="mt-1 text-xs font-semibold text-slate-200">{formatMaybePrice(indexItem.price)}</p>
                      </div>
                    </div>
                  ))}
                  {(!overview || overview.indices.length === 0) && (
                    <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-5 text-sm text-slate-500">
                      {isLoadingMarket ? 'Loading market overview...' : 'Market overview unavailable.'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-[1.1rem] border border-slate-700/80 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(17,24,39,0.84))] p-4 shadow-[0_14px_40px_rgba(2,6,23,0.28)]">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Latest Brief</p>
              <p className="mt-0.5 text-xs text-slate-400">Saved AI market-plus-portfolio narrative.</p>
            </div>
            <Link
              to="/brief"
              className="rounded-full border border-slate-600/80 bg-slate-900/60 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:border-slate-400 hover:bg-slate-800"
            >
              History
            </Link>
          </div>
          {isLoadingBrief ? (
            <div className="space-y-2.5">
              <div className="h-4 w-1/3 animate-pulse rounded bg-slate-800" />
              <div className="h-16 animate-pulse rounded-[1rem] bg-slate-800" />
              <div className="h-14 animate-pulse rounded-[1rem] bg-slate-800" />
            </div>
          ) : latestBrief ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                <span className="rounded-full border border-slate-600/80 bg-slate-900/70 px-2.5 py-1">{latestBrief.span_label || latestBrief.span_type || 'Daily'}</span>
                <span>{latestBrief.digest_date}</span>
              </div>
              <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
                <p className="text-sm leading-6 text-slate-200">{getExcerpt(latestBrief.narrative, 250)}</p>
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
                <p className="mt-1.5 text-sm leading-6 text-emerald-50">{getExcerpt(latestBrief.what_to_watch, 120)}</p>
              </div>
            </div>
          ) : (
            <div className="rounded-[1rem] border border-dashed border-slate-700 px-4 py-7 text-center">
              <p className="text-sm text-slate-300">No saved brief yet.</p>
              <Link
                to="/brief"
                className="mt-3 inline-flex rounded-full border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/20"
              >
                Generate brief
              </Link>
            </div>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="min-h-[360px]">
          <DashboardPriceTrendsChart tickers={tickers} period="6mo" height={360} />
        </div>

        <DashboardPanel
          title="Signals & Positioning"
          subtitle="Portfolio call mix, conviction, sector tilt, and market sector leaders."
        >
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[0.92fr_1.08fr]">
            <div className="space-y-3">
              <RecommendationDonut data={recommendationBreakdown} total={widgets.length} />
              <div className="grid grid-cols-2 gap-2">
                {recommendationBreakdown.map((entry) => (
                  <div key={entry.name} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: RECOMMENDATION_COLORS[entry.name] ?? '#64748b' }} />
                      <span className="text-xs font-medium text-slate-300">{entry.name}</span>
                    </div>
                    <div className="mt-1 text-base font-semibold text-white">{entry.value}</div>
                  </div>
                ))}
              </div>
              <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Sector exposure</p>
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
            </div>

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

              <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Highest conviction</p>
                <div className="space-y-2">
                  {portfolioSummary.convictionRows.length > 0 ? (
                    portfolioSummary.convictionRows.slice(0, 4).map((row) => (
                      <button
                        key={row.ticker}
                        type="button"
                        onClick={() => navigate(`/tickers/${row.ticker}`)}
                        className="flex w-full items-center justify-between rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-2.5 text-left transition-colors hover:border-slate-500/70 hover:bg-slate-900"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-white">{row.ticker}</span>
                            <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${badgeClassForRecommendation(row.recommendation)}`}>
                              {row.recommendation}
                            </span>
                          </div>
                          <p className="mt-1 truncate text-[11px] text-slate-500">{row.name}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs font-semibold text-white">{row.signalScore != null ? `${row.signalScore.toFixed(1)}/10` : '—'}</p>
                          <p className={`text-[11px] font-semibold ${row.dailyChangePercent >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                            {formatPercent(row.dailyChangePercent)}
                          </p>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-3 py-5 text-sm text-slate-500">
                      Run AI analysis on subscribed names to populate conviction signals.
                    </div>
                  )}
                </div>
              </div>

              {overview ? (
                <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Sector board</p>
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
          </div>
        </DashboardPanel>

        <DashboardPanel
          title="Flow & News"
          subtitle="Market movers plus a constrained alternating headline feed."
          action={
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
          }
        >
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-2.5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Portfolio best</p>
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
                  <p className="mt-2 text-sm text-slate-500">No tracked names yet.</p>
                )}
              </div>
              <div className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-2.5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Portfolio weakest</p>
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
                  <p className="mt-2 text-sm text-slate-500">No tracked names yet.</p>
                )}
              </div>
            </div>

            <MoversList rows={marketMoverRows.slice(0, 4)} onSelectTicker={(ticker) => navigate(`/tickers/${ticker}`)} />

            <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-2">
              <div className="mb-2 flex items-center justify-between px-2 py-1">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">News radar</p>
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
            <DashboardPanel title="Regional Markets" subtitle="Cross-asset map of the international backdrop." className="h-full">
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
