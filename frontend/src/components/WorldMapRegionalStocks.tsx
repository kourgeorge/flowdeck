import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps';

type GeoFeature = {
  rsmKey: string;
  properties?: { name?: string; NAME?: string; [key: string]: unknown };
};

type OverviewItem = {
  ticker: string;
  name: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
};

type RegionMeta = {
  coords: [number, number];
  location: string;
  market: string;
};

type MappedItem = OverviewItem & {
  coords: [number, number];
  location: string;
  market: string;
  category: 'region' | 'anchor';
};

type CountryFlagMeta = {
  code: string;
  label: string;
};

const REGION_META: Record<string, RegionMeta> = {
  '^GSPC': { coords: [-74.01, 40.71], location: 'New York, United States', market: 'S&P 500 anchor' },
  '^DJI': { coords: [-73.97, 40.75], location: 'New York, United States', market: 'Dow Jones anchor' },
  '^RUT': { coords: [-87.62, 41.88], location: 'Chicago, United States', market: 'Russell 2000 anchor' },
  DIA: { coords: [-71.1, 42.37], location: 'Boston, United States', market: 'Dow ETF' },
  IWM: { coords: [-74.0, 40.76], location: 'New York, United States', market: 'Russell 2000 ETF' },
  MDY: { coords: [-71.13, 42.39], location: 'Boston, United States', market: 'Mid-cap ETF' },
  VTI: { coords: [-75.45, 39.72], location: 'Malvern, United States', market: 'Total market ETF' },
  '^IXIC': { coords: [-73.99, 40.76], location: 'New York, United States', market: 'Nasdaq Composite anchor' },
  '^NDX': { coords: [-74.0, 40.75], location: 'New York, United States', market: 'Nasdaq 100 anchor' },
  QQQ: { coords: [-84.39, 33.75], location: 'Atlanta, United States', market: 'Nasdaq 100 ETF' },
  '^VIX': { coords: [-87.65, 41.88], location: 'Chicago, United States', market: 'Volatility index' },
  '^TA125.TA': { coords: [34.78, 32.08], location: 'Tel Aviv, Israel', market: 'TA-125' },
  '^TASI.SR': { coords: [46.72, 24.71], location: 'Riyadh, Saudi Arabia', market: 'Tadawul' },
  KSA: { coords: [46.72, 24.71], location: 'Riyadh, Saudi Arabia', market: 'Saudi Arabia ETF' },
  UAE: { coords: [55.27, 25.2], location: 'Dubai, United Arab Emirates', market: 'UAE ETF' },
  QAT: { coords: [51.53, 24], location: 'Doha, Qatar', market: 'Qatar ETF' },
  BAX: { coords: [50.58, 26.23], location: 'Manama, Bahrain', market: 'Bahrain market' },
  KWT: { coords: [47.98, 29.38], location: 'Kuwait City, Kuwait', market: 'Kuwait market' },
  '^FTSE': { coords: [-0.13, 51.51], location: 'London, United Kingdom', market: 'FTSE 100' },
  '^GDAXI': { coords: [8.68, 50.11], location: 'Frankfurt, Germany', market: 'DAX' },
  '^FCHI': { coords: [2.35, 48.86], location: 'Paris, France', market: 'CAC 40' },
  '^STOXX50E': { coords: [4.35, 50.85], location: 'Brussels, Belgium', market: 'Euro Stoxx 50' },
  EWG: { coords: [8.68, 50.11], location: 'Frankfurt, Germany', market: 'Germany ETF' },
  EWU: { coords: [-0.13, 51.51], location: 'London, United Kingdom', market: 'United Kingdom ETF' },
  '^IBEX': { coords: [-3.7, 40.42], location: 'Madrid, Spain', market: 'IBEX 35' },
  '^AEX': { coords: [4.9, 52.37], location: 'Amsterdam, Netherlands', market: 'AEX' },
  '^SSMI': { coords: [8.54, 47.38], location: 'Zurich, Switzerland', market: 'SMI' },
  '^OMXSPI': { coords: [18.07, 59.33], location: 'Stockholm, Sweden', market: 'OMX Stockholm' },
  '^ATX': { coords: [16.37, 48.21], location: 'Vienna, Austria', market: 'ATX' },
  '^BFX': { coords: [4.35, 50.85], location: 'Brussels, Belgium', market: 'BEL 20' },
  '^OMXC20': { coords: [12.57, 55.68], location: 'Copenhagen, Denmark', market: 'OMX Copenhagen' },
  '^OMXH25': { coords: [24.94, 60.17], location: 'Helsinki, Finland', market: 'OMX Helsinki' },
  'GD.AT': { coords: [23.73, 37.98], location: 'Athens, Greece', market: 'Athens index' },
  EIRL: { coords: [-6.26, 53.35], location: 'Dublin, Ireland', market: 'Ireland ETF' },
  '^OSEAX': { coords: [10.75, 59.91], location: 'Oslo, Norway', market: 'Oslo market' },
  '^N225': { coords: [139.69, 35.69], location: 'Tokyo, Japan', market: 'Nikkei 225' },
  '^HSI': { coords: [114.17, 22.32], location: 'Hong Kong', market: 'Hang Seng' },
  '^STI': { coords: [103.85, 1.29], location: 'Singapore', market: 'Straits Times' },
  '^AXJO': { coords: [133.88, -23.7], location: 'Central Australia', market: 'ASX 200' },
  '^KS11': { coords: [126.98, 37.57], location: 'Seoul, South Korea', market: 'KOSPI' },
  '^TWII': { coords: [121.57, 25.03], location: 'Taipei, Taiwan', market: 'Taiwan Weighted' },
  '^BSESN': { coords: [72.88, 19.08], location: 'Mumbai, India', market: 'Sensex' },
  '^NSEI': { coords: [77.21, 28.61], location: 'New Delhi, India', market: 'Nifty 50' },
  '^JKSE': { coords: [106.83, -6.21], location: 'Jakarta, Indonesia', market: 'Jakarta Composite' },
  '^KLSE': { coords: [101.69, 3.14], location: 'Kuala Lumpur, Malaysia', market: 'Malaysia market' },
  '000001.SS': { coords: [121.47, 31.23], location: 'Shanghai, China', market: 'Shanghai Composite' },
  '^SET.BK': { coords: [100.5, 13.76], location: 'Bangkok, Thailand', market: 'SET index' },
  'PSEI.PS': { coords: [121, 14.6], location: 'Manila, Philippines', market: 'PSEi' },
  VNM: { coords: [106.7, 10.78], location: 'Ho Chi Minh City, Vietnam', market: 'Vietnam ETF' },
  'XBAK.DE': { coords: [67.01, 24.86], location: 'Karachi, Pakistan', market: 'Pakistan market' },
  '^NZ50': { coords: [146.82, -41.45], location: 'Tasmania', market: 'NZX 50' },
  ENZL: { coords: [146.82, -41.45], location: 'Tasmania', market: 'New Zealand ETF' },
  EWJ: { coords: [139.69, 35.69], location: 'Tokyo, Japan', market: 'Japan ETF' },
  FXI: { coords: [104.2, 35.9], location: 'Central China', market: 'China large-cap ETF' },
  INDA: { coords: [77.21, 28.61], location: 'New Delhi, India', market: 'India ETF' },
  EWM: { coords: [101.69, 3.14], location: 'Kuala Lumpur, Malaysia', market: 'Malaysia ETF' },
  EIDO: { coords: [106.83, -6.21], location: 'Jakarta, Indonesia', market: 'Indonesia ETF' },
  'XU100.IS': { coords: [28.98, 41.01], location: 'Istanbul, Turkey', market: 'BIST 100' },
  TUR: { coords: [28.98, 41.01], location: 'Istanbul, Turkey', market: 'Turkey ETF' },
  '^GSPTSE': { coords: [-79.38, 43.65], location: 'Toronto, Canada', market: 'S&P/TSX' },
  '^BVSP': { coords: [-46.63, -23.55], location: 'Sao Paulo, Brazil', market: 'Ibovespa' },
  '^MXX': { coords: [-99.13, 19.43], location: 'Mexico City, Mexico', market: 'IPC Mexico' },
  '^IPSA': { coords: [-70.65, -33.45], location: 'Santiago, Chile', market: 'IPSA' },
  '^MERV': { coords: [-58.38, -34.6], location: 'Buenos Aires, Argentina', market: 'MERVAL' },
  'ICOLCAP.CL': { coords: [-74.07, 4.71], location: 'Bogota, Colombia', market: 'Colombia market' },
  EPU: { coords: [-77.04, -12.05], location: 'Lima, Peru', market: 'Peru ETF' },
  EWC: { coords: [-79.38, 43.65], location: 'Toronto, Canada', market: 'Canada ETF' },
  EWZ: { coords: [-46.63, -23.55], location: 'Sao Paulo, Brazil', market: 'Brazil ETF' },
  EWA: { coords: [133.88, -23.7], location: 'Central Australia', market: 'Australia ETF' },
  AFK: { coords: [15, -8], location: 'Pan-Africa', market: 'Africa ETF' },
  '^JN0U.JO': { coords: [28.05, -26.2], location: 'Johannesburg, South Africa', market: 'JSE All Share' },
  EZA: { coords: [28.05, -26.2], location: 'Johannesburg, South Africa', market: 'South Africa ETF' },
  EFA: { coords: [-0.13, 51.51], location: 'Developed markets', market: 'Developed markets ETF' },
  EEM: { coords: [114.17, 22.32], location: 'Emerging markets', market: 'Emerging markets ETF' },
  VEA: { coords: [2.35, 48.86], location: 'Developed ex-US markets', market: 'Developed markets ETF' },
  VWO: { coords: [106.83, -6.21], location: 'Emerging markets', market: 'Emerging markets ETF' },
};

const PRIMARY_TICKERS = new Set(['^GSPC', '^IXIC', '^VIX', '^JN0U.JO']);

const COUNTRY_BY_TICKER_OVERRIDES: Record<string, CountryFlagMeta> = {
  '^NZ50': { code: 'NZ', label: 'New Zealand' },
  ENZL: { code: 'NZ', label: 'New Zealand' },
};

const COUNTRY_MATCHES: Array<CountryFlagMeta & { match: string }> = [
  { match: 'hong kong', code: 'HK', label: 'Hong Kong' },
  { match: 'united states', code: 'US', label: 'United States' },
  { match: 'israel', code: 'IL', label: 'Israel' },
  { match: 'saudi arabia', code: 'SA', label: 'Saudi Arabia' },
  { match: 'united arab emirates', code: 'AE', label: 'United Arab Emirates' },
  { match: 'qatar', code: 'QA', label: 'Qatar' },
  { match: 'bahrain', code: 'BH', label: 'Bahrain' },
  { match: 'kuwait', code: 'KW', label: 'Kuwait' },
  { match: 'united kingdom', code: 'GB', label: 'United Kingdom' },
  { match: 'germany', code: 'DE', label: 'Germany' },
  { match: 'france', code: 'FR', label: 'France' },
  { match: 'belgium', code: 'BE', label: 'Belgium' },
  { match: 'spain', code: 'ES', label: 'Spain' },
  { match: 'netherlands', code: 'NL', label: 'Netherlands' },
  { match: 'switzerland', code: 'CH', label: 'Switzerland' },
  { match: 'sweden', code: 'SE', label: 'Sweden' },
  { match: 'austria', code: 'AT', label: 'Austria' },
  { match: 'denmark', code: 'DK', label: 'Denmark' },
  { match: 'finland', code: 'FI', label: 'Finland' },
  { match: 'greece', code: 'GR', label: 'Greece' },
  { match: 'ireland', code: 'IE', label: 'Ireland' },
  { match: 'norway', code: 'NO', label: 'Norway' },
  { match: 'japan', code: 'JP', label: 'Japan' },
  { match: 'singapore', code: 'SG', label: 'Singapore' },
  { match: 'australia', code: 'AU', label: 'Australia' },
  { match: 'south korea', code: 'KR', label: 'South Korea' },
  { match: 'taiwan', code: 'TW', label: 'Taiwan' },
  { match: 'india', code: 'IN', label: 'India' },
  { match: 'indonesia', code: 'ID', label: 'Indonesia' },
  { match: 'malaysia', code: 'MY', label: 'Malaysia' },
  { match: 'china', code: 'CN', label: 'China' },
  { match: 'thailand', code: 'TH', label: 'Thailand' },
  { match: 'philippines', code: 'PH', label: 'Philippines' },
  { match: 'vietnam', code: 'VN', label: 'Vietnam' },
  { match: 'pakistan', code: 'PK', label: 'Pakistan' },
  { match: 'turkey', code: 'TR', label: 'Turkey' },
  { match: 'canada', code: 'CA', label: 'Canada' },
  { match: 'brazil', code: 'BR', label: 'Brazil' },
  { match: 'mexico', code: 'MX', label: 'Mexico' },
  { match: 'chile', code: 'CL', label: 'Chile' },
  { match: 'argentina', code: 'AR', label: 'Argentina' },
  { match: 'colombia', code: 'CO', label: 'Colombia' },
  { match: 'peru', code: 'PE', label: 'Peru' },
  { match: 'south africa', code: 'ZA', label: 'South Africa' },
];

const MIN_RADIUS = 4;
const MAX_RADIUS = 12;
const MAX_CHANGE_FOR_SCALE = 5;
const FLAT_MOVE_THRESHOLD = 0.15;

function getMeta(ticker: string | null | undefined): RegionMeta | null {
  const normalized = ticker?.trim();
  if (!normalized) return null;
  return REGION_META[normalized] ?? REGION_META[normalized.toUpperCase()] ?? null;
}

function countryCodeToFlagEmoji(code: string): string {
  return code
    .toUpperCase()
    .replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
}

function getCountryFlagMeta(item: Pick<MappedItem, 'ticker' | 'location' | 'market'>): CountryFlagMeta | null {
  const normalizedTicker = item.ticker.trim().toUpperCase();
  const override = COUNTRY_BY_TICKER_OVERRIDES[normalizedTicker];
  if (override) return override;

  const haystack = `${item.location} ${item.market}`.toLowerCase();
  return COUNTRY_MATCHES.find((entry) => haystack.includes(entry.match)) ?? null;
}

function toMappedItem(item: OverviewItem, category: 'region' | 'anchor'): MappedItem | null {
  const meta = getMeta(item.ticker);
  if (!meta) return null;
  return {
    ...item,
    coords: meta.coords,
    location: meta.location,
    market: meta.market,
    category,
  };
}

function dedupeByLocation(items: MappedItem[]): MappedItem[] {
  const seen = new Set<string>();
  const sorted = [...items].sort((a, b) => {
    const primaryA = PRIMARY_TICKERS.has(a.ticker) ? 0 : 1;
    const primaryB = PRIMARY_TICKERS.has(b.ticker) ? 0 : 1;
    if (primaryA !== primaryB) return primaryA - primaryB;
    const benchmarkA = a.ticker.startsWith('^') ? 0 : 1;
    const benchmarkB = b.ticker.startsWith('^') ? 0 : 1;
    if (benchmarkA !== benchmarkB) return benchmarkA - benchmarkB;
    return Math.abs(b.changePercent ?? 0) - Math.abs(a.changePercent ?? 0);
  });

  return sorted.filter((item) => {
    const key = `${Math.round(item.coords[0] * 2) / 2},${Math.round(item.coords[1] * 2) / 2}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function formatPrice(value: number | null): string {
  if (value == null) return '—';
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPct(value: number | null): string {
  if (value == null) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatMove(value: number | null): string {
  if (value == null) return 'No move data';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)} pts`;
}

function getMarkerRadius(changePercent: number | null): number {
  if (changePercent == null) return MIN_RADIUS;
  const scale = Math.min(Math.abs(changePercent) / MAX_CHANGE_FOR_SCALE, 1);
  return MIN_RADIUS + scale * (MAX_RADIUS - MIN_RADIUS);
}

function getTone(changePercent: number | null) {
  if (changePercent == null) {
    return {
      badge: 'border-gray-700 bg-gray-700/50 text-slate-300',
      card: 'border-gray-700 bg-gray-800/80',
      text: 'text-slate-300',
      fill: 'rgba(148, 163, 184, 0.6)',
      stroke: 'rgba(226, 232, 240, 0.55)',
      glow: 'rgba(148, 163, 184, 0.14)',
    };
  }
  if (changePercent >= 0) {
    return {
      badge: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
      card: 'border-emerald-500/20 bg-gray-800/82',
      text: 'text-emerald-200',
      fill: 'rgba(16, 185, 129, 0.78)',
      stroke: 'rgba(167, 243, 208, 0.92)',
      glow: 'rgba(16, 185, 129, 0.22)',
    };
  }
  return {
    badge: 'border-rose-400/20 bg-rose-400/10 text-rose-200',
    card: 'border-rose-500/20 bg-gray-800/82',
    text: 'text-rose-200',
    fill: 'rgba(244, 63, 94, 0.78)',
    stroke: 'rgba(254, 205, 211, 0.92)',
    glow: 'rgba(244, 63, 94, 0.24)',
  };
}

function StatCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/70 px-3.5 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <div className="truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</div>
        <div className="shrink-0 text-[18px] font-semibold tracking-tight text-white">{value}</div>
      </div>
      <div className="mt-1 text-[13px] leading-snug text-slate-300">{detail}</div>
    </div>
  );
}

function CountryFlagBadge({ item }: { item: Pick<MappedItem, 'ticker' | 'location' | 'market'> }) {
  const country = getCountryFlagMeta(item);
  if (!country) return null;

  return (
    <span
      className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-gray-700 bg-gray-700/50 text-sm shadow-[0_8px_18px_-14px_rgba(15,23,42,1)]"
      title={country.label}
      aria-label={country.label}
    >
      {countryCodeToFlagEmoji(country.code)}
    </span>
  );
}

function SelectedMarketCard({
  item,
  onClear,
  onSelectTicker,
  compact = false,
}: {
  item: MappedItem;
  onClear: () => void;
  onSelectTicker?: (ticker: string) => void;
  compact?: boolean;
}) {
  const tone = getTone(item.changePercent);
  const shellClass = compact ? 'rounded-lg p-2.5' : 'rounded-lg p-2.5';
  const statGridClass = compact ? 'grid-cols-1' : 'grid-cols-2';

  return (
    <div className={`border border-gray-700 bg-gray-800/90 shadow-[0_10px_22px_-22px_rgba(2,6,23,0.95)] ${shellClass}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <CountryFlagBadge item={item} />
            <span className="text-sm font-semibold tracking-tight text-white">{item.ticker}</span>
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${tone.badge}`}>
              {formatPct(item.changePercent)}
            </span>
          </div>
          <div className="mt-1 text-[13px] font-medium leading-snug text-slate-100">{item.name}</div>
          <div className="mt-0.5 truncate text-[10px] leading-snug text-slate-400" title={`${item.market} · ${item.location}`}>
            {item.market} · {item.location}
          </div>
          <div className={`mt-1 flex ${compact ? 'flex-col items-start gap-1.5' : 'flex-wrap items-center gap-1.5'} text-[10px] leading-snug text-slate-500`}>
            {onSelectTicker && item.ticker && !item.ticker.startsWith('^') ? (
              <button
                type="button"
                onClick={() => onSelectTicker(item.ticker)}
                className="inline-flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-700/60 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-200 transition hover:border-gray-600 hover:bg-gray-700"
              >
                Open
                <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M13 5l7 7-7 7" />
                </svg>
              </button>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          onClick={onClear}
          className="rounded-full border border-gray-700 bg-transparent p-1.5 text-slate-500 transition hover:border-gray-600 hover:bg-gray-700/40 hover:text-slate-200"
          aria-label="Clear selection"
        >
          <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className={`mt-2.5 grid gap-1.5 border-t border-white/8 pt-2 ${statGridClass}`}>
        <div className="rounded-md border border-gray-700 bg-gray-700/35 px-2.5 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Price</div>
          <div className="mt-0.5 text-[12px] font-semibold tracking-tight text-white">{formatPrice(item.price)}</div>
        </div>
        <div className="rounded-md border border-gray-700 bg-gray-700/35 px-2.5 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Point move</div>
          <div className={`mt-0.5 text-[12px] font-semibold tracking-tight ${tone.text}`}>{formatMove(item.change)}</div>
        </div>
      </div>
    </div>
  );
}

interface WorldMapRegionalStocksProps {
  regionalItems: OverviewItem[];
  usIndices?: OverviewItem[];
  onSelectTicker?: (ticker: string) => void;
}

type CountryTooltip = { name: string; x: number; y: number };

export default function WorldMapRegionalStocks({
  regionalItems,
  usIndices = [],
  onSelectTicker,
}: WorldMapRegionalStocksProps) {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [selectionDismissed, setSelectionDismissed] = useState(false);
  const [countryTooltip, setCountryTooltip] = useState<CountryTooltip | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  const handleCountryMouseEnter = useCallback((name: string) => (event: React.MouseEvent) => {
    const container = mapContainerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    setCountryTooltip({
      name,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  }, []);

  const handleCountryMouseMove = useCallback((event: React.MouseEvent) => {
    const container = mapContainerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    setCountryTooltip((current) =>
      current
        ? {
            ...current,
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
          }
        : null
    );
  }, []);

  const handleCountryMouseLeave = useCallback(() => {
    setCountryTooltip(null);
  }, []);

  const allItems = useMemo(() => {
    const regionalMapped = regionalItems
      .map((item) => toMappedItem(item, 'region'))
      .filter((item): item is MappedItem => item != null);
    const anchorMapped = usIndices
      .map((item) => toMappedItem(item, 'anchor'))
      .filter((item): item is MappedItem => item != null);
    return dedupeByLocation([...regionalMapped, ...anchorMapped]);
  }, [regionalItems, usIndices]);

  const filteredItems = useMemo(
    () => [...allItems].sort((a, b) => Math.abs(b.changePercent ?? 0) - Math.abs(a.changePercent ?? 0)),
    [allItems]
  );

  useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedTicker(null);
      setSelectionDismissed(false);
      return;
    }

    const selectedStillVisible = selectedTicker && filteredItems.some((item) => item.ticker === selectedTicker);
    if (selectedStillVisible) return;

    if (selectionDismissed) {
      setSelectedTicker(null);
      return;
    }

    if (!selectedStillVisible) {
      setSelectedTicker(filteredItems[0].ticker);
    }
  }, [filteredItems, selectedTicker, selectionDismissed]);

  const selectedItem = useMemo(
    () => filteredItems.find((item) => item.ticker === selectedTicker) ?? null,
    [filteredItems, selectedTicker]
  );

  const positiveCount = useMemo(
    () => filteredItems.filter((item) => (item.changePercent ?? 0) >= FLAT_MOVE_THRESHOLD).length,
    [filteredItems]
  );

  const negativeCount = useMemo(
    () => filteredItems.filter((item) => (item.changePercent ?? 0) <= -FLAT_MOVE_THRESHOLD).length,
    [filteredItems]
  );

  const strongestItem = filteredItems[0] ?? null;
  const averageAbsMove = useMemo(() => {
    const withMoves = filteredItems.filter((item) => item.changePercent != null);
    if (withMoves.length === 0) return null;
    const total = withMoves.reduce((sum, item) => sum + Math.abs(item.changePercent ?? 0), 0);
    return total / withMoves.length;
  }, [filteredItems]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Coverage"
          value={`${filteredItems.length}`}
          detail="Mapped regional markets and U.S. anchors."
        />
        <StatCard
          label="Advancers"
          value={`${positiveCount}`}
          detail={`${negativeCount} red, ${Math.max(filteredItems.length - positiveCount - negativeCount, 0)} flat.`}
        />
        <StatCard
          label="Avg swing"
          value={averageAbsMove == null ? '—' : `${averageAbsMove.toFixed(2)}%`}
          detail="Average absolute move."
        />
        <StatCard
          label="Strongest"
          value={strongestItem?.ticker || '—'}
          detail={strongestItem ? `${strongestItem.name} at ${formatPct(strongestItem.changePercent)}` : 'No mapped benchmarks match the current filters.'}
        />
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800/80 shadow-[0_20px_48px_-34px_rgba(15,23,42,0.85)]">
        <div className="grid gap-4 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_330px]">
          <div
            ref={mapContainerRef}
            className="relative overflow-hidden rounded-lg bg-gray-800/85"
          >
            <div className="relative border-b border-gray-700 px-4 py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Mapped benchmarks</div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-700/50 px-2.5 py-1">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                    Up
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-700/50 px-2.5 py-1">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
                    Down
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-700/50 px-2.5 py-1">
                    <span className="h-2.5 w-2.5 rounded-full bg-slate-300/60" />
                    Flat / no data
                  </span>
                </div>
              </div>
            </div>

            <div className="relative" style={{ aspectRatio: '16 / 9' }}>
              <ComposableMap
                projection="geoMercator"
                projectionConfig={{
                  scale: 235,
                  center: [20, 15],
                }}
                className="h-full w-full"
              >
                <Geographies geography="https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json">
                  {({ geographies }: { geographies: GeoFeature[] }) =>
                    geographies.map((geo: GeoFeature) => {
                      const countryName = (geo.properties?.name ?? geo.properties?.NAME ?? '') as string;
                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          fill="rgba(51, 65, 85, 0.85)"
                          stroke="rgba(100, 116, 139, 0.32)"
                          strokeWidth={0.35}
                          style={{
                            default: { outline: 'none' },
                            hover: { outline: 'none', fill: 'rgba(71, 85, 105, 0.96)' },
                            pressed: { outline: 'none' },
                          }}
                          onMouseEnter={countryName ? handleCountryMouseEnter(countryName) : undefined}
                          onMouseMove={handleCountryMouseMove}
                          onMouseLeave={handleCountryMouseLeave}
                        />
                      );
                    })
                  }
                </Geographies>

                {filteredItems.map((item) => {
                  const tone = getTone(item.changePercent);
                  const radius = getMarkerRadius(item.changePercent);
                  const isSelected = item.ticker === selectedTicker;

                  return (
                    <Marker key={item.ticker} coordinates={item.coords}>
                      <g
                        role="button"
                        tabIndex={0}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectionDismissed(false);
                          setSelectedTicker(item.ticker);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            setSelectionDismissed(false);
                            setSelectedTicker(item.ticker);
                          }
                        }}
                        style={{ cursor: 'pointer' }}
                      >
                        <circle r={radius + 5} fill={tone.glow} />
                        {isSelected ? <circle r={radius + 8} fill="none" stroke={tone.stroke} strokeWidth={1.25} opacity={0.95} /> : null}
                        <circle r={radius} fill={tone.fill} stroke={tone.stroke} strokeWidth={isSelected ? 1.8 : 1.2} />
                        <circle r={Math.max(radius * 0.35, 1.75)} fill="rgba(255,255,255,0.9)" opacity={0.92} />
                        <title>{`${item.ticker} · ${item.name} · ${item.location}`}</title>
                      </g>
                    </Marker>
                  );
                })}
              </ComposableMap>

              {filteredItems.length === 0 ? (
                  <div className="absolute inset-0 flex items-center justify-center px-6">
                  <div className="max-w-sm rounded-lg border border-gray-700 bg-gray-800/92 px-6 py-5 text-center shadow-[0_18px_40px_-28px_rgba(15,23,42,1)]">
                    <div className="text-sm font-medium text-white">No markets match the current filters</div>
                    <div className="mt-2 text-xs leading-relaxed text-slate-400">
                      Reset filters or broaden the search to bring benchmarks back onto the map.
                    </div>
                  </div>
                </div>
              ) : null}

              {countryTooltip ? (
                <div
                  className="pointer-events-none absolute z-10 whitespace-nowrap rounded-full border border-gray-700 bg-gray-800/95 px-2.5 py-1 text-[11px] font-medium text-slate-200 shadow-lg"
                  style={{
                    left: countryTooltip.x,
                    top: countryTooltip.y,
                    transform: 'translate(12px, -75%)',
                  }}
                >
                  {countryTooltip.name}
                </div>
              ) : null}

              {selectedItem ? (
                <div className="absolute right-4 top-4 z-10 hidden w-[min(14.5rem,calc(100%-2rem))] sm:block">
                  <SelectedMarketCard
                    item={selectedItem}
                    onClear={() => {
                      setSelectionDismissed(true);
                      setSelectedTicker(null);
                    }}
                    onSelectTicker={onSelectTicker}
                  />
                </div>
              ) : null}
            </div>
          </div>

          {selectedItem ? (
            <div className="sm:hidden">
              <SelectedMarketCard
                item={selectedItem}
                onClear={() => {
                  setSelectionDismissed(true);
                  setSelectedTicker(null);
                }}
                onSelectTicker={onSelectTicker}
                compact
              />
            </div>
          ) : null}

          <aside className="min-h-0 overflow-hidden rounded-lg border border-gray-700 bg-gray-800/70">
            <div className="border-b border-gray-700 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">Compare mapped markets</div>
                </div>
                <span className="rounded-full border border-gray-700 bg-gray-700/50 px-2.5 py-1 text-[11px] font-medium text-slate-300">
                  {filteredItems.length}
                </span>
              </div>
            </div>

            <div className="max-h-[620px] space-y-2 overflow-y-auto p-3">
              {filteredItems.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-700 bg-gray-800/50 px-4 py-5 text-center text-sm text-slate-500">
                  Nothing to compare right now.
                </div>
              ) : (
                filteredItems.map((item) => {
                  const tone = getTone(item.changePercent);
                  const selected = item.ticker === selectedTicker;

                  return (
                    <button
                      key={item.ticker}
                      type="button"
                      onClick={() => {
                        setSelectionDismissed(false);
                        setSelectedTicker(item.ticker);
                      }}
                      className={`w-full rounded-lg border px-3.5 py-3 text-left transition ${
                        selected
                          ? `${tone.card} shadow-[0_18px_36px_-30px_rgba(15,23,42,1)]`
                          : 'border-gray-700 bg-gray-800/55 hover:border-gray-600 hover:bg-gray-700/45'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <CountryFlagBadge item={item} />
                            <span className="text-sm font-semibold text-white">{item.ticker}</span>
                            <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              {item.category === 'anchor' ? 'Anchor' : 'Regional'}
                            </span>
                          </div>
                          <div className="mt-1 truncate text-sm text-slate-300" title={item.name}>
                            {item.name}
                          </div>
                          <div className="mt-1 truncate text-xs text-slate-500" title={item.location}>
                            {item.location}
                          </div>
                        </div>
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold tabular-nums ${tone.badge}`}>
                          {formatPct(item.changePercent)}
                        </span>
                      </div>

                      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
                        <div className="text-slate-400">{formatPrice(item.price)}</div>
                        <div className={`font-medium ${tone.text}`}>{formatMove(item.change)}</div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
