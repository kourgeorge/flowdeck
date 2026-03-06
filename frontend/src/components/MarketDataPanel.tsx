import type { TickerQuote } from '../services/types';

interface MarketDataPanelProps {
  quote: TickerQuote;
}

export default function MarketDataPanel({ quote }: MarketDataPanelProps) {
  const changeColor = quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400';
  const changeBgColor = quote.daily_change_percent >= 0 
    ? 'bg-green-500/20 border-green-500' 
    : 'bg-red-500/20 border-red-500';

  const get52WeekPosition = () => {
    if (!quote.fifty_two_week_low || !quote.fifty_two_week_high) return 0;
    const range = quote.fifty_two_week_high - quote.fifty_two_week_low;
    if (range === 0) return 0;
    return ((quote.current_price - quote.fifty_two_week_low) / range) * 100;
  };

  const getDayPosition = () => {
    if (!quote.day_low || !quote.day_high) return 0;
    const range = quote.day_high - quote.day_low;
    if (range === 0) return 0;
    return ((quote.current_price - quote.day_low) / range) * 100;
  };

  const formatNumber = (num: number | null) => {
    if (num === null) return 'N/A';
    return num.toLocaleString();
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Price Section */}
        <div className={`${changeBgColor} border-2 rounded-lg p-6`}>
          <div className="text-sm text-gray-300 mb-2">Current Price</div>
          <div className="text-5xl font-bold text-white mb-2">
            ${quote.current_price.toFixed(2)}
          </div>
          <div className={`text-2xl font-semibold ${changeColor}`}>
            {quote.daily_change >= 0 ? '+' : ''}{quote.daily_change.toFixed(2)} ({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%)
          </div>
          <div className="text-xs text-gray-400 mt-2">
            {new Date(quote.last_update_time).toLocaleString()}
          </div>
        </div>

        {/* Trading Info */}
        <div className="bg-gray-700/50 rounded-lg p-6">
          <div className="space-y-4">
            <div>
              <div className="text-sm text-gray-400">Bid</div>
              <div className="text-lg text-white">
                ${quote.bid_price?.toFixed(2) || 'N/A'} {quote.bid_size ? `X${quote.bid_size}` : ''}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Ask</div>
              <div className="text-lg text-white">
                ${quote.ask_price?.toFixed(2) || 'N/A'} {quote.ask_size ? `X${quote.ask_size}` : ''}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Volume</div>
              <div className="text-lg text-white">{formatNumber(quote.volume)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Market Status</div>
              <div className="text-lg text-white">{quote.market_status}</div>
            </div>
          </div>
        </div>
      </div>

      {/* 52 Week Range */}
      {quote.fifty_two_week_low && quote.fifty_two_week_high && (
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-400 mb-2">
            <span>52 Week Range</span>
            <span>${quote.fifty_two_week_low.toFixed(2)} - ${quote.fifty_two_week_high.toFixed(2)}</span>
          </div>
          <div className="relative h-4 bg-gray-700 rounded-full overflow-hidden">
            <div className="absolute inset-0 flex">
              <div 
                className="bg-red-500" 
                style={{ width: `${get52WeekPosition()}%` }}
              ></div>
              <div 
                className="bg-green-500" 
                style={{ width: `${100 - get52WeekPosition()}%` }}
              ></div>
            </div>
            <div 
              className="absolute top-0 w-0.5 h-full bg-white z-10"
              style={{ left: `${get52WeekPosition()}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Today's Range */}
      {quote.day_low && quote.day_high && (
        <div>
          <div className="flex justify-between text-sm text-gray-400 mb-2">
            <span>Today's Range</span>
            <span>${quote.day_low.toFixed(2)} - ${quote.day_high.toFixed(2)}</span>
          </div>
          <div className="relative h-4 bg-gray-700 rounded-full overflow-hidden">
            <div className="absolute inset-0 flex">
              <div 
                className="bg-red-500" 
                style={{ width: `${getDayPosition()}%` }}
              ></div>
              <div 
                className="bg-green-500" 
                style={{ width: `${100 - getDayPosition()}%` }}
              ></div>
            </div>
            <div 
              className="absolute top-0 w-0.5 h-full bg-white z-10"
              style={{ left: `${getDayPosition()}%` }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
}

