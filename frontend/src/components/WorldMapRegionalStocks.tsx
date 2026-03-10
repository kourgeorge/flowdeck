import { useState, useRef, useCallback } from 'react';
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps';

/** GeoJSON-like feature used by Geographies render prop */
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

/** Ticker -> [lon, lat]. Coordinates are [longitude, latitude]. */
const REGION_COORDS: Record<string, [number, number]> = {
  // US indices – spread along the East Coast (city [lon, lat])
  '^GSPC': [-71.06, 42.36],   // Boston
  '^DJI': [-74.01, 40.71],    // New York
  '^RUT': [-75.17, 39.95],    // Philadelphia
  SPY: [-76.61, 39.29],       // Baltimore
  DIA: [-77.04, 38.91],       // Washington DC
  IWM: [-80.84, 35.23],       // Charlotte
  MDY: [-84.39, 33.75],       // Atlanta
  VOO: [-81.66, 30.33],       // Jacksonville
  VTI: [-80.19, 25.77],       // Miami
  '^IXIC': [-74.17, 40.74],   // Newark (NYC metro)
  '^NDX': [-74.08, 40.72],   // Jersey City (NYC metro)
  QQQ: [-73.98, 40.76],       // New York midtown
  '^VIX': [-87.65, 41.88],    // Chicago (CBOE)
  // Israel
  '^TA125.TA': [34.78, 32.08],
  'TA35.TA': [34.78, 32.08],
  // Gulf / Middle East
  '^TASI.SR': [46.72, 24.71],
  KSA: [46.72, 24.71],
  UAE: [55.27, 25.2],
  QAT: [51.53, 25.28],   // iShares MSCI Qatar ETF
  BAX: [50.58, 26.23],
  KWT: [47.98, 29.38],
  EGPT: [31.24, 30.04],
  '^CASE30': [31.24, 30.04],
  'MASI': [-7.61, 33.59],
  '^NQMA': [-7.61, 33.59],
  // Europe
  '^FTSE': [-0.13, 51.51],
  '^GDAXI': [8.68, 50.11],
  '^FCHI': [2.35, 48.86],
  '^STOXX50E': [4.35, 50.85],
  EWG: [8.68, 50.11],
  EWU: [-0.13, 51.51],
  'FTSEMIB.MI': [9.19, 45.46],
  '^IBEX': [-3.70, 40.42],
  '^AEX': [4.9, 52.37],
  '^SSMI': [8.54, 47.38],
  '^OMXSPI': [18.07, 59.33],
  'WIG20.WA': [21.01, 52.23],
  '^ATX': [16.37, 48.21],
  '^BFX': [4.35, 50.85],
  '^OMXC20': [12.57, 55.68],
  '^OMXH25': [24.94, 60.17],
  'GD.AT': [23.73, 37.98],
  'FPXAA.PR': [-9.14, 38.72],
  EIRL: [-6.26, 53.35],
  '^OSEAX': [10.75, 59.91],
  '^BUX.BD': [19.04, 47.5],
  'IMOEX.ME': [37.62, 55.75],   // Russia MOEX
  // Asia-Pacific
  '^N225': [139.69, 35.69],
  '^HSI': [114.17, 22.32],
  '^STI': [103.85, 1.29],
  '^AXJO': [151.21, -33.87],
  '^KS11': [126.98, 37.57],
  '^TWII': [121.57, 25.03],
  '^BSESN': [72.88, 19.08],
  '^NSEI': [77.21, 28.61],
  '^JKSE': [106.83, -6.21],
  '^KLSE': [101.69, 3.14],
  '000001.SS': [121.47, 31.23],   // Shanghai (SSE)
  '^SET.BK': [100.5, 13.76],
  'PSEI.PS': [121.0, 14.6],
  VNM: [106.7, 10.78],
  'XBAK.DE': [67.01, 24.86],
  '^NZ50': [174.78, -41.29],
  ENZL: [174.78, -41.29],
  EWJ: [139.69, 35.69],
  FXI: [104.2, 35.9],              // iShares China – central China
  INDA: [77.21, 28.61],
  EWM: [101.69, 3.14],
  EIDO: [106.83, -6.21],
  // Turkey
  'XU100.IS': [28.98, 41.01],
  TUR: [28.98, 41.01],
  // Americas
  '^GSPTSE': [-79.38, 43.65],
  '^BVSP': [-46.63, -23.55],
  '^MXX': [-99.13, 19.43],
  '^IPSA': [-70.65, -33.45],
  '^MERV': [-58.38, -34.6],
  'ICOLCAP.CL': [-74.07, 4.71],
  EPU: [-77.04, -12.05],
  'IBC.CR': [-84.09, 9.93],
  EWC: [-79.38, 43.65],
  EWZ: [-46.63, -23.55],
  EWA: [151.21, -33.87],
  // Africa
  '^SPAFREP': [20, -5],       // Africa (S&P Pan Africa)
  AFK: [15, -8],              // Pan-Africa ETF
  '^JN0U.JO': [28.05, -26.2],
  EZA: [28.05, -26.2],
  NGE: [3.39, 6.45],          // Global X MSCI Nigeria ETF
  'FNKEN2.L': [36.82, -1.29], // Kenya FNKEN2 (NSE 20)
  FM: [31.24, 30.04],
  // Generic ETFs - place at representative locations
  EFA: [-0.13, 51.51],
  EEM: [114.17, 22.32],
  VEA: [2.35, 48.86],
  VWO: [106.83, -6.21],
};

function getCoords(item: OverviewItem): [number, number] | null {
  const t = item.ticker?.trim();
  if (!t) return null;
  return REGION_COORDS[t] ?? REGION_COORDS[t.toUpperCase()] ?? null;
}

// Primary ticker to show when multiple items share the same location (US exchanges, South Africa, etc.)
const PRIMARY_TICKERS = new Set(['^GSPC', '^IXIC', '^VIX', '^JN0U.JO', '^CASE30', '^NQMA']);

// Dedupe by approximate coords (same rounded lon,lat) to avoid stacked markers.
// For US exchanges we keep the primary index (e.g. ^GSPC for NYSE, ^IXIC for NASDAQ).
function dedupeByLocation(items: OverviewItem[]): OverviewItem[] {
  const seen = new Set<string>();
  const sorted = [...items].sort((a, b) => {
    const tickerA = (a.ticker ?? '').trim();
    const tickerB = (b.ticker ?? '').trim();
    const primaryA = PRIMARY_TICKERS.has(tickerA) ? 0 : 1;
    const primaryB = PRIMARY_TICKERS.has(tickerB) ? 0 : 1;
    return primaryA - primaryB;
  });
  return sorted.filter((item) => {
    const c = getCoords(item);
    if (!c) return false;
    const key = `${Math.round(c[0] * 2) / 2},${Math.round(c[1] * 2) / 2}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function formatPrice(n: number | null): string {
  if (n == null) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPct(n: number | null): string {
  if (n == null) return '—';
  const s = n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2);
  return `${s}%`;
}

const MIN_RADIUS = 2;
const MAX_RADIUS = 9;
const MAX_CHANGE_FOR_SCALE = 5;

function getMarkerRadius(changePercent: number | null): number {
  if (changePercent == null) return MIN_RADIUS;
  const abs = Math.abs(changePercent);
  if (abs <= 0) return MIN_RADIUS;
  const t = Math.min(abs / MAX_CHANGE_FOR_SCALE, 1);
  return MIN_RADIUS + t * (MAX_RADIUS - MIN_RADIUS);
}

interface WorldMapRegionalStocksProps {
  regionalItems: OverviewItem[];
  usIndices?: OverviewItem[];
  onSelectTicker?: (ticker: string) => void;
}

type ChangeFilter = 'all' | 'gainers' | 'losers';

type CountryTooltip = { name: string; x: number; y: number };

export default function WorldMapRegionalStocks({ regionalItems, usIndices = [], onSelectTicker }: WorldMapRegionalStocksProps) {
  const [changeFilter, setChangeFilter] = useState<ChangeFilter>('all');
  const [selectedItem, setSelectedItem] = useState<OverviewItem | null>(null);
  const [countryTooltip, setCountryTooltip] = useState<CountryTooltip | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  const handleCountryMouseEnter = useCallback((name: string) => (evt: React.MouseEvent) => {
    const el = mapContainerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setCountryTooltip({
      name,
      x: evt.clientX - rect.left,
      y: evt.clientY - rect.top,
    });
  }, []);

  const handleCountryMouseMove = useCallback((evt: React.MouseEvent) => {
    const el = mapContainerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setCountryTooltip((prev) => prev ? { ...prev, x: evt.clientX - rect.left, y: evt.clientY - rect.top } : null);
  }, []);

  const handleCountryMouseLeave = useCallback(() => {
    setCountryTooltip(null);
  }, []);

  let combined = [...regionalItems, ...usIndices];

  if (changeFilter === 'gainers') {
    combined = combined.filter((i) => (i.changePercent ?? 0) > 0);
  } else if (changeFilter === 'losers') {
    combined = combined.filter((i) => (i.changePercent ?? 0) < 0);
  }

  const withCoords = combined.filter((i) => getCoords(i) != null);
  const mappable = dedupeByLocation(withCoords);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/60 overflow-hidden">
      <div className="px-2.5 py-1.5 border-b border-gray-700 bg-gray-800/80 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Regional markets</h3>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1 text-[10px]">
            <span className="font-medium text-gray-400">Filter</span>
            {(['all', 'gainers', 'losers'] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setChangeFilter(f)}
                className={`px-2 py-0.5 rounded capitalize ${
                  changeFilter === f ? 'bg-gray-600 text-white' : 'text-gray-400 hover:text-gray-300'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="flex flex-col sm:flex-row gap-0 sm:gap-4 p-2 sm:p-4">
        <div ref={mapContainerRef} className="relative flex-1 min-w-0" style={{ aspectRatio: '2 / 1' }}>
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{
            // Slight zoom-in over the original, but not enough to clip New Zealand
            scale: 235,
            center: [20, 15],
          }}
          className="w-full h-full"
        >
          <Geographies geography="https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json">
            {({ geographies }: { geographies: GeoFeature[] }) =>
              geographies.map((geo: GeoFeature) => {
                const countryName = (geo.properties?.name ?? geo.properties?.NAME ?? '') as string;
                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill="#374151"
                    stroke="#4b5563"
                    strokeWidth={0.25}
                    style={{
                      default: { outline: 'none' },
                      hover: { outline: 'none', fill: '#4b5563' },
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
          {mappable.length === 0 ? null : mappable.map((item) => {
            const coords = getCoords(item);
            if (!coords) return null;
            const hasChange = item.changePercent != null;
            const positive = (item.changePercent ?? 0) >= 0;
            const fillColor = !hasChange
              ? 'rgba(156, 163, 175, 0.45)'
              : positive
                ? 'rgba(34, 197, 94, 0.5)'
                : 'rgba(239, 68, 68, 0.5)';
            const radius = getMarkerRadius(item.changePercent);
            return (
              <Marker key={item.ticker} coordinates={coords}>
                <g
                  role="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedItem((prev) => (prev?.ticker === item.ticker ? null : item));
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  <circle r={radius} fill={fillColor} />
                  <title>{item.name}</title>
                </g>
              </Marker>
            );
          })}
        </ComposableMap>
        {countryTooltip && (
          <div
            className="pointer-events-none absolute z-10 rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs font-medium text-gray-200 shadow-lg"
            style={{
              left: countryTooltip.x + 12,
              top: countryTooltip.y + 8,
            }}
          >
            {countryTooltip.name}
          </div>
        )}
        {selectedItem && (
          <div
            className="absolute top-3 right-3 min-w-[180px] rounded border border-gray-600 bg-gray-800 px-2.5 py-2 shadow-lg"
            role="dialog"
            aria-label="Market details"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline justify-between gap-1 min-w-0">
                  <span className="text-gray-300 text-xs font-medium truncate min-w-0" title={selectedItem.name}>
                    {selectedItem.name}
                  </span>
                  {selectedItem.ticker && (
                    <span className="text-gray-500 text-xs shrink-0 tabular-nums">{selectedItem.ticker}</span>
                  )}
                </div>
                <div className="mt-0.5 flex items-baseline justify-between gap-1 min-w-0">
                  <span
                    className="text-white text-xs font-semibold tabular-nums min-w-0 truncate"
                    title={formatPrice(selectedItem.price)}
                  >
                    {formatPrice(selectedItem.price)}
                  </span>
                  <span
                    className={`text-xs font-medium tabular-nums shrink-0 ${
                      selectedItem.changePercent == null
                        ? 'text-gray-400'
                        : (selectedItem.changePercent ?? 0) >= 0
                          ? 'text-green-400'
                          : 'text-red-400'
                    }`}
                  >
                    {formatPct(selectedItem.changePercent)}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedItem(null)}
                className="shrink-0 p-0.5 rounded text-gray-500 hover:text-gray-300 hover:bg-gray-700 transition-colors"
                aria-label="Close"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {onSelectTicker && selectedItem.ticker && !selectedItem.ticker.startsWith('^') && (
              <button
                type="button"
                onClick={() => onSelectTicker(selectedItem.ticker)}
                className="mt-2 w-full py-1.5 text-xs font-medium text-center rounded border border-gray-600 bg-gray-700 text-gray-300 hover:border-gray-500 hover:bg-gray-600 hover:text-white transition-colors"
              >
                View
              </button>
            )}
          </div>
        )}
        {/* Legend overlay */}
        <div className="absolute bottom-2 right-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500/50" aria-hidden />
            Up
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500/50" aria-hidden />
            Down
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-gray-400/45" aria-hidden />
            No data
          </span>
          <span className="flex items-center gap-2">
            Size ∝ |change|
            <span className="flex items-center gap-1">
              <span className="inline-block rounded-full bg-gray-500/50" style={{ width: 4, height: 4 }} aria-hidden />
              small
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block rounded-full bg-gray-500/50" style={{ width: 9, height: 9 }} aria-hidden />
              large
            </span>
          </span>
        </div>
        </div>
        {/* Tickers on map widget */}
        <div className="mt-4 sm:mt-0 sm:w-56 shrink-0 max-h-[min(85vh,36rem)] rounded-lg border border-gray-700 bg-gray-800/80 overflow-hidden flex flex-col min-h-0">
          <div className="px-2.5 py-1.5 border-b border-gray-700 shrink-0">
            <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">On map ({mappable.length})</h4>
          </div>
          <div className="overflow-y-auto flex-1 min-h-0 py-1 overscroll-contain">
            {mappable.length === 0 ? (
              <p className="px-2.5 py-2 text-gray-500 text-xs">No tickers match the current filter.</p>
            ) : (
              <ul className="space-y-0.5" role="list">
                {mappable.map((item) => {
                  const hasChange = item.changePercent != null;
                  const positive = (item.changePercent ?? 0) >= 0;
                  const changeClass = !hasChange ? 'text-gray-400' : positive ? 'text-green-400' : 'text-red-400';
                  const isSelected = selectedItem?.ticker === item.ticker;
                  return (
                    <li key={item.ticker}>
                      <button
                        type="button"
                        onClick={() => setSelectedItem((prev) => (prev?.ticker === item.ticker ? null : item))}
                        className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition-colors ${
                          isSelected ? 'bg-gray-600/80' : 'hover:bg-gray-700/60'
                        }`}
                      >
                        <div className="flex items-baseline justify-between gap-1 min-w-0">
                          <span className="font-medium text-gray-200 truncate" title={item.name}>
                            {item.ticker}
                          </span>
                          <span className={`shrink-0 tabular-nums ${changeClass}`}>
                            {formatPct(item.changePercent)}
                          </span>
                        </div>
                        <div className="mt-0.5 truncate text-gray-500" title={item.name}>
                          {item.name}
                        </div>
                        {item.price != null && (
                          <div className="mt-0.5 text-gray-400 tabular-nums">
                            {formatPrice(item.price)}
                          </div>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
