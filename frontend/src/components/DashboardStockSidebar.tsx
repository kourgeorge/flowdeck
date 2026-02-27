import type { StockWidget as StockWidgetType } from '../services/types';

interface StockSidebarItem {
  ticker: string;
  name: string;
  current_price: number;
  daily_change_percent: number;
  recommendation: string | null;
  has_report: boolean;
  /** 'subscribed' | 'recent' | 'radar' */
  source: 'subscribed' | 'recent' | 'radar';
}

interface DashboardStockSidebarProps {
  subscribedWidgets: StockWidgetType[];
  recentWidgets: StockWidgetType[];
  tickerToName: Record<string, string>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
}

function getRecBadge(rec: string | null) {
  if (!rec) return null;
  const colors: Record<string, string> = {
    BUY: 'bg-green-500/20 text-green-400 border-green-500/40',
    SELL: 'bg-red-500/20 text-red-400 border-red-500/40',
    HOLD: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
  };
  const c = colors[rec.toUpperCase()] || 'bg-gray-500/20 text-gray-400 border-gray-500/40';
  return (
    <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${c}`}>
      {rec.toUpperCase()}
    </span>
  );
}

function SidebarRow({
  item,
  isSelected,
  onSelect,
}: {
  item: StockSidebarItem;
  isSelected: boolean;
  onSelect: (ticker: string) => void;
}) {
  const up = item.daily_change_percent >= 0;
  const changeColor = up ? 'text-green-400' : 'text-red-400';

  return (
    <button
      type="button"
      onClick={() => onSelect(item.ticker)}
      className={`w-full text-left px-3 py-2.5 flex items-center gap-2 transition-colors border-b border-gray-700/60 last:border-0 ${
        isSelected
          ? 'bg-blue-600/20 border-l-2 border-l-blue-500'
          : 'hover:bg-gray-700/50 border-l-2 border-l-transparent'
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="font-semibold text-white text-sm truncate">{item.ticker}</span>
          {item.has_report && getRecBadge(item.recommendation)}
        </div>
        <div className="text-xs text-gray-400 truncate">{item.name}</div>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-sm font-mono text-white">
          {item.current_price > 0 ? `$${item.current_price.toFixed(2)}` : '—'}
        </div>
        {item.current_price > 0 && (
          <div className={`text-xs font-mono ${changeColor}`}>
            {up ? '+' : ''}{item.daily_change_percent.toFixed(2)}%
          </div>
        )}
      </div>
    </button>
  );
}

export default function DashboardStockSidebar({
  subscribedWidgets,
  recentWidgets,
  tickerToName,
  selectedTicker,
  onSelect,
}: DashboardStockSidebarProps) {
  const subscribedTickers = new Set(subscribedWidgets.map((w) => w.ticker));
  const recentOnly = recentWidgets.filter((w) => !subscribedTickers.has(w.ticker));

  const toItem = (w: StockWidgetType, source: StockSidebarItem['source']): StockSidebarItem => ({
    ticker: w.ticker,
    name: tickerToName[w.ticker] || w.ticker,
    current_price: w.current_price,
    daily_change_percent: w.daily_change_percent,
    recommendation: w.recommendation,
    has_report: w.has_report,
    source,
  });

  const subscribedItems = subscribedWidgets.map((w) => toItem(w, 'subscribed'));
  const recentItems = recentOnly.map((w) => toItem(w, 'recent'));

  const hasSubscribed = subscribedItems.length > 0;
  const hasRecent = recentItems.length > 0;

  if (!hasSubscribed && !hasRecent) {
    return (
      <div className="p-4 text-center text-gray-500 text-sm">
        No stocks yet. Search above to add stocks.
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0 overflow-y-auto">
      {hasSubscribed && (
        <div>
          <div className="px-3 py-2 text-xs font-semibold text-amber-400/80 uppercase tracking-wider bg-gray-800/60 border-b border-gray-700 sticky top-0 z-10">
            Subscribed
          </div>
          {subscribedItems.map((item) => (
            <SidebarRow
              key={item.ticker}
              item={item}
              isSelected={selectedTicker === item.ticker}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
      {hasRecent && (
        <div>
          <div className="px-3 py-2 text-xs font-semibold text-blue-400/80 uppercase tracking-wider bg-gray-800/60 border-b border-gray-700 sticky top-0 z-10">
            Recently Analyzed
          </div>
          {recentItems.map((item) => (
            <SidebarRow
              key={item.ticker}
              item={item}
              isSelected={selectedTicker === item.ticker}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Made with Bob
