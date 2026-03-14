import { useState, useEffect, useRef } from 'react';
import Fuse from 'fuse.js';
import type { TickerWidget as TickerWidgetType } from '../services/types';
import { formatPrice } from '../utils/currency';

interface Ticker {
  ticker: string;
  name: string;
}

function SidebarTickerSearch({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<Ticker[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [fuse, setFuse] = useState<Fuse<Ticker> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((data: Ticker[]) => {
        const fuseInstance = new Fuse(data, {
          keys: [
            { name: 'ticker', weight: 0.7 },
            { name: 'name', weight: 0.3 },
          ],
          threshold: 0.3,
          includeScore: true,
          minMatchCharLength: 1,
        });
        setFuse(fuseInstance);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchTerm(value);
    setSelectedIndex(-1);
    if (value.trim().length === 0) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    if (fuse) {
      const results = fuse.search(value);
      const matches = results.slice(0, 8).map((r) => r.item);
      setSuggestions(matches);
      setShowSuggestions(matches.length > 0);
    }
  };

  const handleSelect = (stock: Ticker) => {
    setSearchTerm('');
    setSuggestions([]);
    setShowSuggestions(false);
    onSelect(stock.ticker);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = searchTerm.trim().toUpperCase();
    if (ticker) {
      setSearchTerm('');
      setSuggestions([]);
      setShowSuggestions(false);
      onSelect(ticker);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter') handleSubmit(e);
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : prev));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
          handleSelect(suggestions[selectedIndex]);
        } else {
          handleSubmit(e);
        }
        break;
      case 'Escape':
        setShowSuggestions(false);
        setSelectedIndex(-1);
        break;
    }
  };

  return (
    <div className="relative px-2 py-2 border-b border-gray-700 bg-gray-800/80 shrink-0">
      <form onSubmit={handleSubmit}>
        <div className="relative flex items-center">
          <svg className="absolute left-2.5 w-3.5 h-3.5 text-gray-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={searchTerm}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            placeholder="Add ticker (Yahoo symbol)…"
            title="Use any Yahoo Finance symbol — even if it doesn't appear in the dropdown."
            className="w-full pl-8 pr-3 py-1.5 bg-gray-700/60 border border-gray-600 rounded text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </form>
      {showSuggestions && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute z-50 left-2 right-2 mt-1 bg-gray-950 border border-gray-600 rounded-lg shadow-xl max-h-60 overflow-y-auto"
        >
          {suggestions.map((stock, index) => (
            <div
              key={stock.ticker}
              onMouseDown={() => handleSelect(stock)}
              className={`px-3 py-2 cursor-pointer transition-colors ${
                index === selectedIndex ? 'bg-blue-600/60 text-white' : 'hover:bg-gray-700/80 text-gray-200'
              }`}
            >
              <div className="font-semibold text-white text-sm">{stock.ticker}</div>
              <div className="text-xs text-gray-400 truncate">{stock.name}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


interface TickerSidebarItem {
  ticker: string;
  name: string;
  current_price: number;
  daily_change_percent: number;
  recommendation: string | null;
  has_report: boolean;
  /** 'subscribed' | 'recent' | 'radar' */
  source: 'subscribed' | 'recent' | 'radar';
  currency?: string | null;
}

interface DashboardTickerSidebarProps {
  subscribedWidgets: TickerWidgetType[];
  recentWidgets: TickerWidgetType[];
  tickerToName: Record<string, string>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
  /** If provided, the search box calls this instead of onSelect */
  onAdd?: (ticker: string) => void;
  /** If provided, each row shows a remove (×) button */
  onRemove?: (ticker: string) => void;
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
  onRemove,
}: {
  item: TickerSidebarItem;
  isSelected: boolean;
  onSelect: (ticker: string) => void;
  onRemove?: (ticker: string) => void;
}) {
  const up = item.daily_change_percent >= 0;
  const changeColor = up ? 'text-green-400' : 'text-red-400';

  return (
    <div
      className={`group w-full flex items-center border-b border-gray-700/60 last:border-0 ${
        isSelected
          ? 'bg-blue-600/30 border-l-2 border-l-blue-400'
          : 'hover:bg-gray-700/50 border-l-2 border-l-transparent'
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect(item.ticker)}
        className="flex-1 min-w-0 text-left px-3 py-2.5 flex items-center gap-2"
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
            {item.current_price > 0 ? formatPrice(item.current_price, item.currency) : '—'}
          </div>
          {item.current_price > 0 && (
            <div className={`text-xs font-mono ${changeColor}`}>
              {up ? '+' : ''}{item.daily_change_percent.toFixed(2)}%
            </div>
          )}
        </div>
      </button>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(item.ticker); }}
          title={`Remove ${item.ticker} from list`}
          className="shrink-0 mr-2 w-5 h-5 flex items-center justify-center rounded text-gray-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default function DashboardTickerSidebar({
  subscribedWidgets,
  recentWidgets,
  tickerToName,
  selectedTicker,
  onSelect,
  onAdd,
  onRemove,
}: DashboardTickerSidebarProps) {
  const subscribedTickers = new Set(subscribedWidgets.map((w) => w.ticker));
  const recentOnly = recentWidgets.filter((w) => !subscribedTickers.has(w.ticker));

  const toItem = (w: TickerWidgetType, source: TickerSidebarItem['source']): TickerSidebarItem => ({
    ticker: w.ticker,
    name: w.name || tickerToName[w.ticker] || w.ticker,
    current_price: w.current_price,
    daily_change_percent: w.daily_change_percent,
    recommendation: w.recommendation,
    has_report: w.has_report,
    source,
    currency: w.currency,
  });

  const subscribedItems = subscribedWidgets.map((w) => toItem(w, 'subscribed'));
  const recentItems = recentOnly.map((w) => toItem(w, 'recent'));

  const hasSubscribed = subscribedItems.length > 0;
  const hasRecent = recentItems.length > 0;

  // The search box adds to the list when onAdd is provided, otherwise selects
  const handleSearchSelect = (ticker: string) => {
    if (onAdd) {
      onAdd(ticker);
    } else {
      onSelect(ticker);
    }
  };

  if (!hasSubscribed && !hasRecent) {
    return (
      <div className="flex flex-col min-h-0">
        <div className="shrink-0">
          <SidebarTickerSearch onSelect={handleSearchSelect} />
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto p-4 text-center text-gray-500 text-sm">
          No tickers yet. Search above to add tickers.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">
      <div className="shrink-0">
        <SidebarTickerSearch onSelect={handleSearchSelect} />
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        {hasSubscribed && (
          <div>
            {subscribedItems.map((item) => (
              <SidebarRow
                key={item.ticker}
                item={item}
                isSelected={selectedTicker === item.ticker}
                onSelect={onSelect}
                onRemove={onRemove}
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
                onRemove={onRemove}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Made with Bob
