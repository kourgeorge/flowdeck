import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { stockApi } from '../services/api';
import type { StockWidget as StockWidgetType } from '../services/types';

const SPARKLINE_WIDTH = 88;
const SPARKLINE_HEIGHT = 20;

/** Sparkline data for the same period as the delta (e.g. 1 month). */
export type SparklineData = { closes: number[]; openPrice: number };

/** Compute 1-month % change from sparkline data: (lastClose - openPrice) / openPrice * 100 */
function oneMonthChangePercent(data: SparklineData): number | null {
  const { closes, openPrice } = data;
  if (closes.length === 0 || openPrice <= 0) return null;
  const lastClose = closes[closes.length - 1];
  return ((lastClose - openPrice) / openPrice) * 100;
}

function TileSparkline({
  chartData,
  isPositive,
}: {
  chartData: SparklineData | null;
  isPositive: boolean;
}) {
  if (!chartData || chartData.closes.length < 2) return <div className="h-5 w-[88px] shrink-0 bg-gray-700/50 rounded" />;

  const { closes: points, openPrice } = chartData;
  const min = Math.min(...points, openPrice);
  const max = Math.max(...points, openPrice);
  const range = max - min || 1;
  const w = SPARKLINE_WIDTH;
  const h = SPARKLINE_HEIGHT;
  const pad = 1;
  const xs = points.map((_, i) => pad + (i / (points.length - 1)) * (w - 2 * pad));
  const ys = points.map((p) => h - pad - ((p - min) / range) * (h - 2 * pad));
  const d = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x} ${ys[i]}`).join(' ');
  const stroke = isPositive ? '#34d399' : '#f87171';
  const openY = h - pad - ((openPrice - min) / range) * (h - 2 * pad);

  return (
    <svg
      width={w}
      height={h}
      className="shrink-0 rounded overflow-hidden"
      aria-hidden
    >
      {/* Opening price horizontal line */}
      <line
        x1={pad}
        y1={openY}
        x2={w - pad}
        y2={openY}
        stroke="#6b7280"
        strokeWidth="0.8"
        strokeDasharray="2 1"
      />
      <path d={d} fill="none" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface DashboardTopTilesProps {
  /** Subscribed stocks – shown with yellowish background */
  subscribedWidgets: StockWidgetType[];
  /** Recently analyzed stocks (excluding subscribed) – shown with orangish background */
  recentAnalyzedWidgets: StockWidgetType[];
  /** Optional: called when a tile is clicked; if provided, prevents navigation */
  onSelectTicker?: (ticker: string) => void;
}

function getRecColors(rec: string | null) {
  if (!rec) return { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500/40' };
  switch (rec.toUpperCase()) {
    case 'BUY':
      return { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/40' };
    case 'SELL':
      return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/40' };
    case 'HOLD':
      return { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/40' };
    default:
      return { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500/40' };
  }
}

const SUBSCRIBED_TILE_CLASS =
  'bg-amber-500/15 border-amber-500/50 hover:bg-amber-500/25 hover:border-amber-500/70';
const RECENTLY_ANALYZED_TILE_CLASS =
  'bg-blue-500/15 border-blue-500/50 hover:bg-blue-500/25 hover:border-blue-500/70';

function DashboardTile({
  w,
  tileClass,
  onNavigate,
}: {
  w: StockWidgetType;
  tileClass: string;
  onNavigate: (ticker: string) => void;
}) {
  const [chartData, setChartData] = useState<SparklineData | null>(null);
  useEffect(() => {
    let cancelled = false;
    stockApi
      .getHistoricalPrices(w.ticker, '1mo', '1d')
      .then((res: { data?: Array<{ open: number; close: number }> }) => {
        if (cancelled || !res?.data?.length) return;
        const closes = res.data.map((d) => d.close).filter((c) => c > 0);
        const firstOpen = res.data[0]?.open;
        if (closes.length > 0) {
          setChartData({
            closes,
            openPrice: firstOpen != null && firstOpen > 0 ? firstOpen : closes[0],
          });
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [w.ticker]);

  const periodChangePercent = chartData != null ? oneMonthChangePercent(chartData) : null;
  const up = periodChangePercent != null ? periodChangePercent >= 0 : w.daily_change_percent >= 0;
  const changeColor = up ? 'text-green-400' : 'text-red-400';
  const recColors = getRecColors(w.recommendation);
  const displayPercent =
    periodChangePercent != null ? periodChangePercent : w.daily_change_percent;
  const showPercent = periodChangePercent != null || w.current_price > 0;

  return (
    <button
      type="button"
      onClick={() => onNavigate(w.ticker)}
      className={`flex flex-col items-start gap-0.5 px-3 py-2 rounded-lg border transition-colors text-left shrink-0 min-w-[100px] max-w-[140px] ${tileClass}`}
    >
      <div className="flex items-center justify-between w-full gap-2">
        <span className="font-semibold text-white text-sm truncate">{w.ticker}</span>
        {w.has_report && w.recommendation && (
          <span
            className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${recColors.bg} ${recColors.text} ${recColors.border}`}
          >
            {w.recommendation.toUpperCase()}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5 flex-wrap">
        <span className="text-gray-200 text-sm tabular-nums font-medium">
          {w.current_price > 0 ? `$${w.current_price.toFixed(2)}` : '—'}
        </span>
        {showPercent && (
          <span className={`text-xs tabular-nums ${changeColor}`} title={periodChangePercent != null ? '1 month change' : "Today's change"}>
            {up ? '+' : ''}{displayPercent.toFixed(2)}%{periodChangePercent != null ? ' (1M)' : ''}
          </span>
        )}
      </div>
      <TileSparkline chartData={chartData} isPositive={up} />
      {w.has_report && w.confidence != null && (
        <div className="text-[10px] text-gray-500">
          AI confidence {(w.confidence * 100).toFixed(0)}%
        </div>
      )}
    </button>
  );
}

export default function DashboardTopTiles({
  subscribedWidgets,
  recentAnalyzedWidgets,
  onSelectTicker,
}: DashboardTopTilesProps) {
  const navigate = useNavigate();
  const subscribedTickers = new Set(subscribedWidgets.map((w) => w.ticker));
  const recentOnly = recentAnalyzedWidgets.filter((w) => !subscribedTickers.has(w.ticker));
  const hasSubscribed = subscribedWidgets.length > 0;
  const hasRecent = recentOnly.length > 0;

  if (!hasSubscribed && !hasRecent) return null;

  const handleNavigate = (ticker: string) => {
    if (onSelectTicker) {
      onSelectTicker(ticker);
    } else {
      navigate(`/tickers/${ticker}`);
    }
  };

  return (
    <div className="w-full border-y border-gray-700 bg-gray-800/80 shrink-0 overflow-hidden">
      <div className="flex items-stretch gap-2 py-2 px-2 w-max animate-tiles-scroll">
        {[1, 2].map((copy) => (
          <div key={copy} className="flex items-stretch gap-2 shrink-0">
            {hasSubscribed && (
              <div className="flex items-stretch gap-2 shrink-0 border-r border-gray-700 pr-2">
                {subscribedWidgets.map((w) => (
                  <DashboardTile key={`${copy}-sub-${w.ticker}`} w={w} tileClass={SUBSCRIBED_TILE_CLASS} onNavigate={handleNavigate} />
                ))}
              </div>
            )}
            {hasRecent && (
              <div className="flex items-stretch gap-2 shrink-0">
                {recentOnly.map((w) => (
                  <DashboardTile key={`${copy}-recent-${w.ticker}`} w={w} tileClass={RECENTLY_ANALYZED_TILE_CLASS} onNavigate={handleNavigate} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
