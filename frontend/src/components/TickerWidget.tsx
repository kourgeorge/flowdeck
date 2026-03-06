import { useNavigate } from 'react-router-dom';
import type { TickerWidget as TickerWidgetType } from '../services/types';
import { parseReportDate } from '../utils/date';

const DASHBOARD_TILE_COLORS = [
  'bg-red-500/15 border-red-500/40',
  'bg-blue-500/15 border-blue-500/40',
  'bg-orange-500/15 border-orange-500/40',
  'bg-gray-500/15 border-gray-500/40',
  'bg-green-500/15 border-green-500/40',
  'bg-indigo-500/15 border-indigo-500/40',
];

function getDashboardTileColor(ticker: string): string {
  let hash = 0;
  for (let i = 0; i < ticker.length; i++) {
    hash = (hash << 5) - hash + ticker.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % DASHBOARD_TILE_COLORS.length;
  return DASHBOARD_TILE_COLORS[index];
}

interface TickerWidgetProps {
  widget: TickerWidgetType;
  /** Dashboard variant: larger tile with company name and distinct accent color */
  variant?: 'default' | 'dashboard';
  /** Company name for dashboard variant (e.g. from stocks.json) */
  companyName?: string;
}

export default function TickerWidget({ widget, variant = 'default', companyName }: TickerWidgetProps) {
  const navigate = useNavigate();

  const getRecommendationColor = (rec: string | null) => {
    if (variant === 'dashboard') {
      return getDashboardTileColor(widget.ticker);
    }
    if (!rec) return 'border-gray-600 bg-gray-800';
    switch (rec.toUpperCase()) {
      case 'BUY':
        return 'border-green-500 bg-green-500/10';
      case 'SELL':
        return 'border-red-500 bg-red-500/10';
      case 'HOLD':
        return 'border-hold bg-hold/10';
      default:
        return 'border-gray-600 bg-gray-800';
    }
  };

  const getRecommendationBadge = (rec: string | null) => {
    if (!rec) return null;
    const colors = {
      BUY: 'bg-green-500 text-white',
      SELL: 'bg-red-500 text-white',
      HOLD: 'bg-hold text-white',
    };
    const color = colors[rec.toUpperCase() as keyof typeof colors] || 'bg-gray-500';
    return (
      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${color}`}>
        {rec.toUpperCase()}
      </span>
    );
  };

  const formatDate = (dateStr: string | null) => {
    const date = parseReportDate(dateStr);
    if (!date) return 'No report';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const changeColor = widget.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400';
  const changeIcon = widget.daily_change_percent >= 0 ? '▲' : '▼';

  const isDashboard = variant === 'dashboard';
  return (
    <div
      onClick={() => navigate(`/tickers/${widget.ticker}`)}
      className={`
        rounded-lg border-2 cursor-pointer
        transition-all duration-200 hover:scale-[1.02] hover:shadow-lg
        ${getRecommendationColor(widget.recommendation)}
        ${isDashboard ? 'p-6 min-h-[140px]' : 'bg-gray-800 p-6'}
      `}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className={`font-bold text-white ${isDashboard ? 'text-2xl' : 'text-2xl'}`}>
            {widget.ticker}
          </h3>
          {isDashboard && companyName && (
            <p className="text-sm text-gray-400 mt-0.5 truncate max-w-[200px]" title={companyName}>
              {companyName}
            </p>
          )}
        </div>
        {widget.has_report && widget.recommendation && getRecommendationBadge(widget.recommendation)}
      </div>

      <div className={isDashboard ? 'mb-2' : 'mb-4'}>
        {widget.current_price > 0 ? (
          <>
            <div className={`font-bold text-white mb-1 ${isDashboard ? 'text-3xl' : 'text-4xl'}`}>
              ${widget.current_price.toFixed(2)}
            </div>
            <div className={`font-semibold ${changeColor} ${isDashboard ? 'text-base' : 'text-lg'}`}>
              {widget.daily_change >= 0 ? '+' : ''}{widget.daily_change.toFixed(2)} ({widget.daily_change_percent >= 0 ? '+' : ''}{widget.daily_change_percent.toFixed(2)}%) {changeIcon}
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-400">Price unavailable</div>
        )}
      </div>

      <div className={`pt-3 border-t border-gray-700/80 ${!isDashboard ? 'pt-4' : ''}`}>
        {widget.has_report ? (
          <div className="text-sm text-gray-400">
            Report: {formatDate(widget.report_date)}
            {isDashboard && widget.confidence != null && (
              <span className="ml-2">· Confidence {(widget.confidence * 100).toFixed(0)}%</span>
            )}
          </div>
        ) : (
          <div className="text-sm text-gray-500">
            No report available
          </div>
        )}
        {widget.market_status && widget.market_status !== 'UNKNOWN' && (
          <div className="text-xs text-gray-500 mt-1">
            {widget.market_status.replace(/_/g, ' ')}
          </div>
        )}
      </div>
    </div>
  );
}

