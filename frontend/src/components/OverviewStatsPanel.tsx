import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import { tickerApi } from '../services/api';
import type { TickerWidget as StockWidgetType } from '../services/types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface TickerInfo {
  ticker: string;
  exchange: string;
  country: string;
  sector: string;
  quoteType: string;
}

interface MarketGroup {
  label: string;
  exchange: string;
  country: string;
  tickers: StockWidgetType[];
}

interface OverviewStatsPanelProps {
  widgets: StockWidgetType[];
  tickerToName: Record<string, string>;
  hideByMarket?: boolean;
}

interface SubscribedChangeColumnsChartProps {
  widgets: StockWidgetType[];
  height?: number;
}

interface HistoricalPricePoint {
  close: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const EXCHANGE_LABELS: Record<string, string> = {
  NMS: 'NASDAQ', NGM: 'NASDAQ', NCM: 'NASDAQ',
  NYQ: 'NYSE', ASE: 'NYSE American', PCX: 'NYSE Arca',
  BTS: 'BATS', OBB: 'OTC', PNK: 'OTC Pink',
  LSE: 'London SE', FRA: 'Frankfurt', PAR: 'Euronext Paris',
  AMS: 'Euronext Amsterdam', BRU: 'Euronext Brussels',
  LIS: 'Euronext Lisbon', MIL: 'Borsa Italiana',
  MCE: 'Madrid SE', STO: 'Nasdaq Stockholm',
  CPH: 'Nasdaq Copenhagen', HEL: 'Nasdaq Helsinki',
  OSL: 'Oslo Børs', VIE: 'Vienna SE', ZRH: 'SIX Swiss',
  TSX: 'Toronto SE', TOR: 'Toronto SE',
  ASX: 'ASX', HKG: 'Hong Kong SE', SHH: 'Shanghai SE',
  SHZ: 'Shenzhen SE', TYO: 'Tokyo SE', KRX: 'Korea SE',
  BSE: 'BSE India', NSE: 'NSE India', TAE: 'Tel Aviv SE',
  SAO: 'B3 Brazil', MEX: 'BMV Mexico',
  NASDAQ: 'NASDAQ', NYSE: 'NYSE',
};

function friendlyExchange(raw: string): string {
  if (!raw) return 'Unknown';
  const upper = raw.toUpperCase();
  return EXCHANGE_LABELS[upper] || EXCHANGE_LABELS[raw] || raw;
}

// Map quoteType to a friendly asset-type label
function friendlyAssetType(quoteType: string): string {
  if (!quoteType) return 'Stock';
  switch (quoteType.toUpperCase()) {
    case 'EQUITY': return 'Stock';
    case 'ETF': return 'ETF';
    case 'MUTUALFUND': return 'Mutual Fund';
    case 'INDEX': return 'Index';
    case 'CRYPTOCURRENCY': return 'Crypto';
    case 'CURRENCY': return 'Currency';
    case 'FUTURE': return 'Future';
    case 'OPTION': return 'Option';
    default: return quoteType;
  }
}

function countryFlag(country: string): string {
  if (!country || country.length < 2) return '';
  const nameToCode: Record<string, string> = {
    'UNITED STATES': 'US', 'USA': 'US', 'US': 'US',
    'UNITED KINGDOM': 'GB', 'UK': 'GB', 'GB': 'GB',
    'GERMANY': 'DE', 'DE': 'DE', 'FRANCE': 'FR', 'FR': 'FR',
    'JAPAN': 'JP', 'JP': 'JP', 'CHINA': 'CN', 'CN': 'CN',
    'HONG KONG': 'HK', 'HK': 'HK', 'CANADA': 'CA', 'CA': 'CA',
    'AUSTRALIA': 'AU', 'AU': 'AU', 'INDIA': 'IN', 'IN': 'IN',
    'SOUTH KOREA': 'KR', 'KR': 'KR', 'ISRAEL': 'IL', 'IL': 'IL',
    'BRAZIL': 'BR', 'BR': 'BR', 'MEXICO': 'MX', 'MX': 'MX',
    'NETHERLANDS': 'NL', 'NL': 'NL', 'SWITZERLAND': 'CH', 'CH': 'CH',
    'SWEDEN': 'SE', 'SE': 'SE', 'NORWAY': 'NO', 'NO': 'NO',
    'DENMARK': 'DK', 'DK': 'DK', 'FINLAND': 'FI', 'FI': 'FI',
    'SPAIN': 'ES', 'ES': 'ES', 'ITALY': 'IT', 'IT': 'IT',
    'AUSTRIA': 'AT', 'AT': 'AT', 'BELGIUM': 'BE', 'BE': 'BE',
    'PORTUGAL': 'PT', 'PT': 'PT',
  };
  const iso2 = nameToCode[country.toUpperCase()] || country.toUpperCase().slice(0, 2);
  if (iso2.length !== 2) return '';
  return iso2
    .split('')
    .map((c) => String.fromCodePoint(0x1f1e0 - 65 + c.charCodeAt(0)))
    .join('');
}

// ─── Pie chart colours ────────────────────────────────────────────────────────

const PIE_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899',
  '#06b6d4', '#84cc16', '#f97316', '#6366f1', '#14b8a6',
  '#a855f7', '#eab308', '#22c55e', '#ef4444', '#64748b',
  '#0ea5e9', '#d946ef', '#fb923c', '#4ade80', '#facc15',
];

const CHANGE_PERIODS = [
  { label: '1D', value: '1d' },
  { label: '1W', value: '5d' },
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: 'YTD', value: 'ytd' },
  { label: '1Y', value: '1y' },
  { label: '5Y', value: '5y' },
  { label: '10Y', value: '10y' },
  { label: 'MAX', value: 'max' },
];

function pieColor(i: number) {
  return PIE_COLORS[i % PIE_COLORS.length];
}

function signedPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function changeBarColor(value: number): string {
  if (value > 0) return '#4ade80';
  if (value < 0) return '#f87171';
  return '#94a3b8';
}

function getNiceTickStep(range: number, targetTickCount: number): number {
  if (!Number.isFinite(range) || range <= 0) return 1;
  const rawStep = range / Math.max(1, targetTickCount - 1);
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const residual = rawStep / magnitude;
  if (residual <= 1) return 1 * magnitude;
  if (residual <= 2) return 2 * magnitude;
  if (residual <= 5) return 5 * magnitude;
  return 10 * magnitude;
}

// Build [{name, value}] from a string-keyed count map, sorted desc
function buildPieData(counts: Map<string, number>): { name: string; value: number }[] {
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }));
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-gray-700/50 rounded-lg px-4 py-3 flex flex-col gap-0.5 min-w-[110px] justify-center">
      <span className="text-gray-400 text-xs font-medium uppercase tracking-wide">{label}</span>
      <span className={`text-xl font-bold tabular-nums ${color ?? 'text-white'}`}>{value}</span>
      {sub && <span className="text-gray-500 text-xs">{sub}</span>}
    </div>
  );
}

function ChangeChip({ pct }: { pct: number }) {
  const up = pct >= 0;
  return (
    <span className={`text-xs font-semibold tabular-nums px-1.5 py-0.5 rounded ${up ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
      {up ? '+' : ''}{pct.toFixed(2)}%
    </span>
  );
}

function RecBadge({ rec }: { rec: string | null }) {
  if (!rec) return <span className="text-gray-500 text-xs">—</span>;
  const colors: Record<string, string> = {
    BUY: 'bg-green-500/20 text-green-400 border-green-500/40',
    SELL: 'bg-red-500/20 text-red-400 border-red-500/40',
    HOLD: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
  };
  const c = colors[rec.toUpperCase()] || 'bg-gray-500/20 text-gray-400 border-gray-500/40';
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${c}`}>
      {rec.toUpperCase()}
    </span>
  );
}

// Custom tooltip for pie charts
function PieTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number; payload: { name: string; value: number } }> }) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0].payload;
  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm shadow-lg">
      <span className="text-white font-medium">{name}</span>
      <span className="text-gray-400 ml-2">{value} stock{value !== 1 ? 's' : ''}</span>
    </div>
  );
}

function ChangeBarsTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { ticker: string; changePct: number } }> }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm shadow-lg">
      <div className="text-white font-semibold">{point.ticker}</div>
      <div className={point.changePct >= 0 ? 'text-green-400' : 'text-red-400'}>
        {signedPercent(point.changePct)}
      </div>
    </div>
  );
}

export function SubscribedChangeColumnsChart({ widgets, height = 340 }: SubscribedChangeColumnsChartProps) {
  const [selectedPeriod, setSelectedPeriod] = useState('1d');
  const [periodChangeMap, setPeriodChangeMap] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPeriodLabel = CHANGE_PERIODS.find((p) => p.value === selectedPeriod)?.label ?? selectedPeriod.toUpperCase();

  useEffect(() => {
    if (widgets.length === 0) {
      setPeriodChangeMap({});
      setLoading(false);
      setError(null);
      return;
    }

    if (selectedPeriod === '1d') {
      setPeriodChangeMap({});
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    const fallbackMap: Record<string, number> = Object.fromEntries(
      widgets.map((w) => [w.ticker, w.daily_change_percent])
    );

    const fetchPeriodChanges = async () => {
      setLoading(true);
      setError(null);
      try {
        const results = await Promise.allSettled(
          widgets.map((w) => tickerApi.getHistoricalPrices(w.ticker, selectedPeriod, '1d'))
        );
        const next: Record<string, number> = { ...fallbackMap };
        let successCount = 0;

        results.forEach((result, i) => {
          if (result.status !== 'fulfilled') return;
          const ticker = widgets[i].ticker;
          const prices = (result.value?.data as HistoricalPricePoint[] | undefined) ?? [];
          if (prices.length < 2) return;
          const firstClose = prices[0]?.close;
          const lastClose = prices[prices.length - 1]?.close;
          if (firstClose == null || lastClose == null || firstClose <= 0) return;
          const pct = ((lastClose - firstClose) / firstClose) * 100;
          if (!Number.isFinite(pct)) return;
          next[ticker] = pct;
          successCount += 1;
        });

        if (!cancelled) {
          setPeriodChangeMap(next);
          if (successCount === 0) {
            setError(`Could not load ${selectedPeriodLabel} historical changes; showing daily values.`);
          }
        }
      } catch {
        if (!cancelled) {
          setPeriodChangeMap(fallbackMap);
          setError(`Could not load ${selectedPeriodLabel} historical changes; showing daily values.`);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchPeriodChanges();
    return () => {
      cancelled = true;
    };
  }, [selectedPeriod, selectedPeriodLabel, widgets]);

  const changeBarsData = useMemo(() => {
    return widgets
      .map((w) => ({
        ticker: w.ticker,
        changePct:
          selectedPeriod === '1d'
            ? w.daily_change_percent
            : (periodChangeMap[w.ticker] ?? w.daily_change_percent),
      }))
      .sort((a, b) => b.changePct - a.changePct);
  }, [widgets, periodChangeMap, selectedPeriod]);

  const maxAbsChange = useMemo(() => {
    const max = changeBarsData.reduce((acc, row) => Math.max(acc, Math.abs(row.changePct)), 0);
    return Math.max(1, max);
  }, [changeBarsData]);

  const { yAxisMax, yAxisTicks } = useMemo(() => {
    const padded = maxAbsChange * 1.15;
    const step = getNiceTickStep(padded * 2, 7);
    const axisMax = Math.ceil(padded / step) * step;
    const ticks: number[] = [];
    for (let value = -axisMax; value <= axisMax + step / 2; value += step) {
      ticks.push(Number(value.toFixed(10)));
    }
    return { yAxisMax: axisMax, yAxisTicks: ticks };
  }, [maxAbsChange]);

  const chartHeight = Math.max(220, height);

  if (changeBarsData.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 h-full">
        <h3 className="text-lg font-semibold text-white mb-2">% change by ticker</h3>
        <p className="text-gray-400 text-sm">Subscribe to stocks to see % change columns.</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 sm:p-6 h-full flex flex-col">
      <div className="mb-2 shrink-0">
        <h3 className="text-lg font-semibold text-white">% change by ticker</h3>
        <p className="text-gray-500 text-xs sm:text-sm mt-0.5">
          All subscribed tickers, sorted by {selectedPeriodLabel} % change.
        </p>
      </div>
      <div className="mb-2 shrink-0 flex flex-wrap gap-1.5 justify-end">
        {CHANGE_PERIODS.map((p) => (
          <button
            key={p.value}
            type="button"
            onClick={() => setSelectedPeriod(p.value)}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              selectedPeriod === p.value
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {loading && selectedPeriod !== '1d' && (
        <div className="text-gray-400 text-xs mb-2">Loading {selectedPeriodLabel} changes…</div>
      )}
      {error && (
        <div className="text-amber-400 text-xs mb-2">{error}</div>
      )}
      <div className="overflow-x-auto pb-1">
        <div className="min-w-full" style={{ width: Math.max(620, changeBarsData.length * 56), height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            {/* Extra left spacing prevents Y-axis percent labels from clipping (especially negatives). */}
            <BarChart data={changeBarsData} margin={{ top: 8, right: 12, left: 16, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="ticker"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                interval={0}
                height={changeBarsData.length > 12 ? 48 : 24}
                angle={changeBarsData.length > 12 ? -30 : 0}
                textAnchor={changeBarsData.length > 12 ? 'end' : 'middle'}
              />
              <YAxis
                width={56}
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                ticks={yAxisTicks}
                tickFormatter={(v: number) => `${v.toFixed(2)}%`}
                domain={[-yAxisMax, yAxisMax]}
              />
              <ReferenceLine y={0} stroke="rgba(148, 163, 184, 0.45)" strokeDasharray="4 4" />
              <Tooltip content={<ChangeBarsTooltip />} />
              <Bar dataKey="changePct" isAnimationActive={false}>
                {changeBarsData.map((row) => (
                  <Cell key={row.ticker} fill={changeBarColor(row.changePct)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}


// Small inline pie tile — no legend, tooltip on hover
function MiniPieTile({ title, data, loading }: { title: string; data: { name: string; value: number }[]; loading?: boolean }) {
  const SIZE = 72;
  const INNER = 22;
  const OUTER = 34;
  return (
    <div className="bg-gray-700/50 rounded-lg px-3 py-3 flex flex-col items-center justify-center gap-1 min-w-[90px]">
      <span className="text-gray-400 text-xs font-medium uppercase tracking-wide text-center">{title}</span>
      {loading ? (
        <div className="w-[72px] h-[72px] rounded-full bg-gray-600 animate-pulse" />
      ) : data.length === 0 ? (
        <div className="w-[72px] h-[72px] flex items-center justify-center text-gray-500 text-[10px]">No data</div>
      ) : (
        <div style={{ width: SIZE, height: SIZE }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={INNER}
                outerRadius={OUTER}
                paddingAngle={2}
                dataKey="value"
                isAnimationActive={false}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={pieColor(i)} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip content={<PieTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function MarketGroupCard({ group, tickerToName }: { group: MarketGroup; tickerToName: Record<string, string> }) {
  const navigate = useNavigate();
  const { tickers } = group;

  const withPrice = tickers.filter((w) => w.current_price > 0);
  const gainers = withPrice.filter((w) => w.daily_change_percent > 0);
  const losers = withPrice.filter((w) => w.daily_change_percent < 0);
  const flat = withPrice.filter((w) => w.daily_change_percent === 0);

  const avgChange =
    withPrice.length > 0
      ? withPrice.reduce((sum, w) => sum + w.daily_change_percent, 0) / withPrice.length
      : null;

  const best = withPrice.length > 0
    ? withPrice.reduce((a, b) => (a.daily_change_percent > b.daily_change_percent ? a : b))
    : null;
  const worst = withPrice.length > 0
    ? withPrice.reduce((a, b) => (a.daily_change_percent < b.daily_change_percent ? a : b))
    : null;

  const withRec = tickers.filter((w) => w.recommendation);
  const buys = withRec.filter((w) => w.recommendation?.toUpperCase() === 'BUY').length;
  const sells = withRec.filter((w) => w.recommendation?.toUpperCase() === 'SELL').length;
  const holds = withRec.filter((w) => w.recommendation?.toUpperCase() === 'HOLD').length;

  const flag = countryFlag(group.country);

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between gap-2 bg-gray-800/80">
        <div className="flex items-center gap-2 min-w-0">
          {flag && <span className="text-xl leading-none shrink-0">{flag}</span>}
          <div className="min-w-0">
            <h3 className="text-white font-semibold text-sm truncate">{group.exchange}</h3>
            {group.country && <p className="text-gray-400 text-xs truncate">{group.country}</p>}
          </div>
        </div>
        <span className="shrink-0 text-xs text-gray-400 bg-gray-700/60 px-2 py-0.5 rounded-full">
          {tickers.length} stock{tickers.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Stats row */}
      <div className="px-4 py-3 flex flex-wrap gap-3 border-b border-gray-700/60">
        <div className="flex items-center gap-2">
          <span className="text-green-400 font-semibold text-sm tabular-nums">▲ {gainers.length}</span>
          <span className="text-gray-600">·</span>
          <span className="text-red-400 font-semibold text-sm tabular-nums">▼ {losers.length}</span>
          {flat.length > 0 && (
            <>
              <span className="text-gray-600">·</span>
              <span className="text-gray-400 font-semibold text-sm tabular-nums">— {flat.length}</span>
            </>
          )}
        </div>
        {avgChange != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400 text-xs">Avg:</span>
            <ChangeChip pct={avgChange} />
          </div>
        )}
        {withRec.length > 0 && (
          <div className="flex items-center gap-1.5 ml-auto">
            {buys > 0 && <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/40 px-1.5 py-0.5 rounded font-semibold">{buys} BUY</span>}
            {holds > 0 && <span className="text-xs bg-amber-500/20 text-amber-400 border border-amber-500/40 px-1.5 py-0.5 rounded font-semibold">{holds} HOLD</span>}
            {sells > 0 && <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/40 px-1.5 py-0.5 rounded font-semibold">{sells} SELL</span>}
          </div>
        )}
      </div>

      {/* Best / Worst */}
      {(best || worst) && (
        <div className="px-4 py-2 flex gap-4 border-b border-gray-700/60 text-xs">
          {best && (
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-gray-500 shrink-0">Best:</span>
              <button type="button" onClick={() => navigate(`/tickers/${best.ticker}`)} className="font-semibold text-white hover:text-blue-400 transition-colors truncate">
                {best.ticker}
              </button>
              <ChangeChip pct={best.daily_change_percent} />
            </div>
          )}
          {worst && worst.ticker !== best?.ticker && (
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-gray-500 shrink-0">Worst:</span>
              <button type="button" onClick={() => navigate(`/tickers/${worst.ticker}`)} className="font-semibold text-white hover:text-blue-400 transition-colors truncate">
                {worst.ticker}
              </button>
              <ChangeChip pct={worst.daily_change_percent} />
            </div>
          )}
        </div>
      )}

      {/* Ticker list */}
      <div className="divide-y divide-gray-700/50">
        {tickers.map((w) => {
          const name = w.name || tickerToName[w.ticker] || w.ticker;
          return (
            <button
              key={w.ticker}
              type="button"
              onClick={() => navigate(`/tickers/${w.ticker}`)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-700/40 transition-colors text-left"
            >
              <span className="font-semibold text-white text-sm w-16 shrink-0 truncate">{w.ticker}</span>
              <span className="text-gray-400 text-xs flex-1 min-w-0 truncate">{name}</span>
              <span className="text-white text-sm tabular-nums font-mono shrink-0">
                {w.current_price > 0 ? `$${w.current_price.toFixed(2)}` : '—'}
              </span>
              {w.current_price > 0 && (
                <span className="shrink-0"><ChangeChip pct={w.daily_change_percent} /></span>
              )}
              <span className="shrink-0"><RecBadge rec={w.recommendation} /></span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function OverviewStatsPanel({ widgets, tickerToName, hideByMarket }: OverviewStatsPanelProps) {
  const [tickerInfoMap, setTickerInfoMap] = useState<Record<string, TickerInfo>>({});
  const [loading, setLoading] = useState(false);

  // Fetch company info for all subscribed tickers
  useEffect(() => {
    if (widgets.length === 0) return;
    const tickers = widgets.map((w) => w.ticker);
    const missing = tickers.filter((t) => !(t in tickerInfoMap));
    if (missing.length === 0) return;

    setLoading(true);
    Promise.allSettled(
      missing.map((ticker) =>
        tickerApi.getCompanyInfo(ticker).then((info) => ({ ticker, info }))
      )
    ).then((results) => {
      const updates: Record<string, TickerInfo> = {};
      results.forEach((r) => {
        if (r.status === 'fulfilled') {
          const { ticker, info } = r.value;
          updates[ticker] = {
            ticker,
            exchange: friendlyExchange(info.exchange || ''),
            country: info.country || '',
            sector: info.sector || '',
            quoteType: friendlyAssetType(info.quoteType || ''),
          };
        }
      });
      setTickerInfoMap((prev) => ({ ...prev, ...updates }));
    }).finally(() => setLoading(false));
  }, [widgets.map((w) => w.ticker).join(',')]);

  // ── Derived data ────────────────────────────────────────────────────────────

  // Market groups (exchange + country)
  const groups = useMemo<MarketGroup[]>(() => {
    const map = new Map<string, MarketGroup>();
    widgets.forEach((w) => {
      const info = tickerInfoMap[w.ticker];
      const exchange = info?.exchange || 'Unknown';
      const country = info?.country || '';
      const key = `${exchange}||${country}`;
      if (!map.has(key)) {
        const label = country ? `${exchange} · ${country}` : exchange;
        map.set(key, { label, exchange, country, tickers: [] });
      }
      map.get(key)!.tickers.push(w);
    });
    return Array.from(map.values()).sort((a, b) => {
      if (b.tickers.length !== a.tickers.length) return b.tickers.length - a.tickers.length;
      return a.label.localeCompare(b.label);
    });
  }, [widgets, tickerInfoMap]);

  // Pie chart data — sector distribution
  const sectorPieData = useMemo(() => {
    const counts = new Map<string, number>();
    widgets.forEach((w) => {
      const sector = tickerInfoMap[w.ticker]?.sector || 'Unknown';
      counts.set(sector, (counts.get(sector) ?? 0) + 1);
    });
    return buildPieData(counts);
  }, [widgets, tickerInfoMap]);

  // Pie chart data — country distribution
  const countryPieData = useMemo(() => {
    const counts = new Map<string, number>();
    widgets.forEach((w) => {
      const country = tickerInfoMap[w.ticker]?.country || 'Unknown';
      const flag = countryFlag(country);
      const label = flag ? `${flag} ${country}` : country;
      counts.set(label, (counts.get(label) ?? 0) + 1);
    });
    return buildPieData(counts);
  }, [widgets, tickerInfoMap]);

  // Pie chart data — asset type distribution
  const typePieData = useMemo(() => {
    const counts = new Map<string, number>();
    widgets.forEach((w) => {
      const type = tickerInfoMap[w.ticker]?.quoteType || 'Stock';
      counts.set(type, (counts.get(type) ?? 0) + 1);
    });
    return buildPieData(counts);
  }, [widgets, tickerInfoMap]);

  // Overall portfolio stats
  const withPrice = widgets.filter((w) => w.current_price > 0);
  const gainers = withPrice.filter((w) => w.daily_change_percent > 0).length;
  const losers = withPrice.filter((w) => w.daily_change_percent < 0).length;
  const avgChange =
    withPrice.length > 0
      ? withPrice.reduce((s, w) => s + w.daily_change_percent, 0) / withPrice.length
      : null;
  const withRec = widgets.filter((w) => w.recommendation);
  const buys = withRec.filter((w) => w.recommendation?.toUpperCase() === 'BUY').length;
  const sells = withRec.filter((w) => w.recommendation?.toUpperCase() === 'SELL').length;
  const holds = withRec.filter((w) => w.recommendation?.toUpperCase() === 'HOLD').length;
  const markets = groups.filter((g) => g.exchange !== 'Unknown').length;

  // Determine if we have enough info loaded to show pie charts
  const infoLoaded = Object.keys(tickerInfoMap).length > 0;

  return (
    <div className="space-y-6">

      {/* ── Portfolio summary ── */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-5">
        <h2 className="text-white font-semibold text-base mb-3">Portfolio Summary</h2>
        <div className="flex flex-wrap gap-3 items-stretch">
          <StatCard label="Subscribed" value={widgets.length} sub="stocks" />
          <StatCard label="Markets" value={loading && markets === 0 ? '…' : markets} sub="exchanges" />
          <div className="bg-gray-700/50 rounded-lg px-4 py-3 flex flex-col gap-0.5 min-w-[110px] justify-center">
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wide">Today</span>
            <div className="flex items-center gap-3 mt-1">
              <div className="flex flex-col items-center gap-0.5">
                <span className="text-xl font-bold tabular-nums text-green-400">{gainers}</span>
                <span className="text-gray-500 text-[10px]">Gainers</span>
              </div>
              <span className="text-gray-600 text-lg">·</span>
              <div className="flex flex-col items-center gap-0.5">
                <span className="text-xl font-bold tabular-nums text-red-400">{losers}</span>
                <span className="text-gray-500 text-[10px]">Losers</span>
              </div>
            </div>
          </div>
          {avgChange != null && (
            <StatCard
              label="Avg Change"
              value={`${avgChange >= 0 ? '+' : ''}${avgChange.toFixed(2)}%`}
              sub="today"
              color={avgChange >= 0 ? 'text-green-400' : 'text-red-400'}
            />
          )}
          {withRec.length > 0 && (
            <div className="bg-gray-700/50 rounded-lg px-4 py-3 flex flex-col gap-0.5 min-w-[110px] justify-center">
              <span className="text-gray-400 text-xs font-medium uppercase tracking-wide">AI Signals</span>
              <div className="flex items-center gap-3 mt-1">
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-xl font-bold tabular-nums text-green-400">{buys}</span>
                  <span className="text-gray-500 text-[10px]">Buys</span>
                </div>
                <span className="text-gray-600 text-lg">·</span>
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-xl font-bold tabular-nums text-amber-400">{holds}</span>
                  <span className="text-gray-500 text-[10px]">Holds</span>
                </div>
                <span className="text-gray-600 text-lg">·</span>
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-xl font-bold tabular-nums text-red-400">{sells}</span>
                  <span className="text-gray-500 text-[10px]">Sells</span>
                </div>
              </div>
            </div>
          )}
          {/* ── Inline distribution mini-pies ── */}
          {infoLoaded && (
            <>
              <MiniPieTile title="Sector" data={sectorPieData} loading={loading && !infoLoaded} />
              <MiniPieTile title="Country" data={countryPieData} loading={loading && !infoLoaded} />
              <MiniPieTile title="Asset Type" data={typePieData} loading={loading && !infoLoaded} />
            </>
          )}
        </div>
      </div>

      {/* ── Per-market groups ── */}
      {!hideByMarket && ((loading && groups.length === 0) || groups.length > 0) ? (
        <div>
          <h2 className="text-white font-semibold text-base mb-3">By Market</h2>
          {loading && groups.length === 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {widgets.slice(0, 3).map((_, i) => (
                <div key={i} className="bg-gray-800 rounded-xl border border-gray-700 h-48 animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {groups.map((group) => (
                <MarketGroupCard
                  key={`${group.exchange}||${group.country}`}
                  group={group}
                  tickerToName={tickerToName}
                />
              ))}
            </div>
          )}
        </div>
      ) : null}

    </div>
  );
}

// ─── Standalone By Market section (for use outside OverviewStatsPanel) ─────────

interface ByMarketSectionProps {
  widgets: StockWidgetType[];
  tickerToName: Record<string, string>;
}

export function ByMarketSection({ widgets, tickerToName }: ByMarketSectionProps) {
  const [tickerInfoMap, setTickerInfoMap] = useState<Record<string, TickerInfo>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (widgets.length === 0) return;
    const tickers = widgets.map((w) => w.ticker);
    const missing = tickers.filter((t) => !(t in tickerInfoMap));
    if (missing.length === 0) return;

    setLoading(true);
    Promise.allSettled(
      missing.map((ticker) =>
        tickerApi.getCompanyInfo(ticker).then((info) => ({ ticker, info }))
      )
    ).then((results) => {
      const updates: Record<string, TickerInfo> = {};
      results.forEach((r) => {
        if (r.status === 'fulfilled') {
          const { ticker, info } = r.value;
          updates[ticker] = {
            ticker,
            exchange: friendlyExchange(info.exchange || ''),
            country: info.country || '',
            sector: info.sector || '',
            quoteType: friendlyAssetType(info.quoteType || ''),
          };
        }
      });
      setTickerInfoMap((prev) => ({ ...prev, ...updates }));
    }).finally(() => setLoading(false));
  }, [widgets.map((w) => w.ticker).join(',')]);

  const groups = useMemo<MarketGroup[]>(() => {
    const map = new Map<string, MarketGroup>();
    widgets.forEach((w) => {
      const info = tickerInfoMap[w.ticker];
      const exchange = info?.exchange || 'Unknown';
      const country = info?.country || '';
      const key = `${exchange}||${country}`;
      if (!map.has(key)) {
        const label = country ? `${exchange} · ${country}` : exchange;
        map.set(key, { label, exchange, country, tickers: [] });
      }
      map.get(key)!.tickers.push(w);
    });
    return Array.from(map.values()).sort((a, b) => {
      if (b.tickers.length !== a.tickers.length) return b.tickers.length - a.tickers.length;
      return a.label.localeCompare(b.label);
    });
  }, [widgets, tickerInfoMap]);

  if (!loading && groups.length === 0) return null;

  return (
    <div>
      <h2 className="text-white font-semibold text-base mb-3">By Market</h2>
      {loading && groups.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {widgets.slice(0, 3).map((_, i) => (
            <div key={i} className="bg-gray-800 rounded-xl border border-gray-700 h-48 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {groups.map((group) => (
            <MarketGroupCard
              key={`${group.exchange}||${group.country}`}
              group={group}
              tickerToName={tickerToName}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Made with Bob
