import { useNavigate } from 'react-router-dom';
import type { StockWidget as StockWidgetType } from '../services/types';

interface StockWidgetProps {
  widget: StockWidgetType;
}

export default function StockWidget({ widget }: StockWidgetProps) {
  const navigate = useNavigate();

  const getRecommendationColor = (rec: string | null) => {
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
    if (!dateStr) return 'No report';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const changeColor = widget.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400';
  const changeIcon = widget.daily_change_percent >= 0 ? '▲' : '▼';

  return (
    <div
      onClick={() => navigate(`/stocks/${widget.ticker}`)}
      className={`
        bg-gray-800 rounded-lg border-2 p-6 cursor-pointer
        transition-all duration-200 hover:scale-105 hover:shadow-lg
        ${getRecommendationColor(widget.recommendation)}
      `}
    >
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-2xl font-bold text-white">{widget.ticker}</h3>
        {widget.has_report && widget.recommendation && getRecommendationBadge(widget.recommendation)}
      </div>

      <div className="mb-4">
        {widget.current_price > 0 ? (
          <>
            <div className="text-4xl font-bold text-white mb-1">
              ${widget.current_price.toFixed(2)}
            </div>
            <div className={`text-lg font-semibold ${changeColor}`}>
              {widget.daily_change >= 0 ? '+' : ''}{widget.daily_change.toFixed(2)} ({widget.daily_change_percent >= 0 ? '+' : ''}{widget.daily_change_percent.toFixed(2)}%) {changeIcon}
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-400">Price unavailable</div>
        )}
      </div>

      <div className="pt-4 border-t border-gray-700">
        {widget.has_report ? (
          <div className="text-sm text-gray-400">
            Report: {formatDate(widget.report_date)}
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

