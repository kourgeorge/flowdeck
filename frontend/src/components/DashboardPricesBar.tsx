import { useNavigate } from 'react-router-dom';
import type { TickerWidget as StockWidgetType } from '../services/types';

interface DashboardPricesBarProps {
  widgets: StockWidgetType[];
}

export default function DashboardPricesBar({ widgets }: DashboardPricesBarProps) {
  const navigate = useNavigate();

  if (widgets.length === 0) return null;

  return (
    <div className="bg-gray-800/90 border-y border-gray-700 overflow-x-auto shrink-0">
      <div className="flex items-center gap-0 min-w-max py-2 px-2">
        {widgets.map((w) => {
          const up = w.daily_change_percent >= 0;
          const changeColor = up ? 'text-green-400' : 'text-red-400';
          return (
            <button
              key={w.ticker}
              type="button"
              onClick={() => navigate(`/tickers/${w.ticker}`)}
              className="flex items-center gap-3 px-4 py-2 rounded-lg hover:bg-gray-700/80 transition-colors text-left shrink-0"
            >
              <span className="font-semibold text-white">{w.ticker}</span>
              <span className="text-gray-300 tabular-nums">
                ${w.current_price > 0 ? w.current_price.toFixed(2) : '—'}
              </span>
              <span className={`text-sm font-medium tabular-nums ${changeColor}`}>
                {w.current_price > 0
                  ? `${up ? '+' : ''}${w.daily_change_percent.toFixed(2)}%`
                  : '—'}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
