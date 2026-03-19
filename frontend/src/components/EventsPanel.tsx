import { useMemo } from 'react';

interface DetectedEvent {
  event_type: string;
  domain: 'price_technical' | 'news_information' | 'fundamental';
  detected_on: string | null;
  window_start: string | null;
  window_end: string | null;
  strength: 'low' | 'medium' | 'high';
  metric_value: number | null;
  threshold_value: number | null;
  metadata: Record<string, any>;
  description?: string;
}

interface EventsPanelProps {
  ticker: string;
  eventScore: number;
  events: DetectedEvent[];
  dominantEvents: string[];
  isLoading?: boolean;
  error?: string;
}

const EVENT_ICONS: Record<string, string> = {
  price_spike_up: '📈',
  price_spike_down: '📉',
  price_gap_up: '⬆️',
  price_gap_down: '⬇️',
  volatility_expansion: '💨',
  volatility_compression: '🎯',
  moving_average_cross: '✖️',
  new_52w_high: '🔝',
  new_52w_low: '🔻',
  volume_spike: '📊',
  earnings_upcoming: '📢',
  insider_buying: '🟢',
  insider_selling: '🔴',
  rsi_bullish_divergence: '🚀',
  rsi_bearish_divergence: '⚠️',
};

const EVENT_LABELS: Record<string, string> = {
  price_spike_up: 'Price Spike Up',
  price_spike_down: 'Price Spike Down',
  price_gap_up: 'Gap Up',
  price_gap_down: 'Gap Down',
  volatility_expansion: 'Volatility Expansion',
  volatility_compression: 'Volatility Compression',
  moving_average_cross: 'Moving Average Cross',
  new_52w_high: '52-Week High',
  new_52w_low: '52-Week Low',
  volume_spike: 'Volume Spike',
  earnings_upcoming: 'Upcoming Earnings',
  insider_buying: 'Insider Buying',
  insider_selling: 'Insider Selling',
  rsi_bullish_divergence: 'RSI Bullish Divergence',
  rsi_bearish_divergence: 'RSI Bearish Divergence',
};

const DOMAIN_COLORS: Record<string, string> = {
  price_technical: 'bg-blue-900/30 border-blue-700/50',
  news_information: 'bg-purple-900/30 border-purple-700/50',
  fundamental: 'bg-amber-900/30 border-amber-700/50',
};

const STRENGTH_BADGES: Record<string, string> = {
  low: 'bg-yellow-900/40 text-yellow-200 border-yellow-700/50',
  medium: 'bg-orange-900/40 text-orange-200 border-orange-700/50',
  high: 'bg-red-900/40 text-red-200 border-red-700/50',
};

function formatMetricValue(value: number | null, eventType: string): string {
  if (value === null) return '—';
  
  // Format percentages for certain event types
  if (['price_spike_up', 'price_spike_down', 'price_gap_up', 'price_gap_down'].includes(eventType)) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  }

  if (eventType === 'earnings_upcoming') {
    return `${value.toFixed(0)}d`;
  }
  
  // Format ratios
  if (['volatility_expansion', 'volatility_compression', 'volume_spike'].includes(eventType)) {
    return `${value.toFixed(2)}x`;
  }

  if (['insider_buying', 'insider_selling'].includes(eventType)) {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  
  // Format prices for 52w events
  if (['new_52w_high', 'new_52w_low'].includes(eventType)) {
    return `$${value.toFixed(2)}`;
  }
  
  return value.toFixed(2);
}

export default function EventsPanel({
  ticker,
  eventScore,
  events,
  dominantEvents,
  isLoading = false,
  error,
}: EventsPanelProps) {
  const scoreColor = useMemo(() => {
    if (eventScore >= 10) return 'text-red-400';
    if (eventScore >= 5) return 'text-orange-400';
    if (eventScore >= 2) return 'text-yellow-400';
    return 'text-green-400';
  }, [eventScore]);

  const scoreLabel = useMemo(() => {
    if (eventScore >= 10) return 'Very High Activity';
    if (eventScore >= 5) return 'High Activity';
    if (eventScore >= 2) return 'Moderate Activity';
    return 'Low Activity';
  }, [eventScore]);

  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center gap-3 text-red-400">
          <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 space-y-4 animate-pulse">
        <div className="h-6 bg-gray-700 rounded w-40" />
        <div className="space-y-2">
          <div className="h-4 bg-gray-700 rounded w-full" />
          <div className="h-4 bg-gray-700 rounded w-5/6" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Score Summary */}
      <div className="bg-gradient-to-r from-gray-900/50 to-gray-800/50 rounded-lg border border-gray-700 p-5">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-gray-400 mb-1">Event Score</p>
            <p className={`text-3xl font-bold ${scoreColor}`}>{eventScore.toFixed(1)}</p>
            <p className="text-xs text-gray-400 mt-1">{scoreLabel}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Total Events</p>
            <p className="text-3xl font-bold text-blue-400">{events.length}</p>
            <p className="text-xs text-gray-400 mt-1">{events.length === 1 ? 'event' : 'events'}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Dominant Signals</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {dominantEvents.slice(0, 3).map((eventType) => (
                <span key={eventType} className="inline-block text-xs px-2 py-1 rounded bg-blue-900/40 text-blue-200 border border-blue-700/50">
                  {EVENT_ICONS[eventType] ?? '•'} {eventType.split('_').slice(0, 2).join(' ')}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Events List */}
      {events.length > 0 ? (
        <div className="space-y-3">
          {events.map((event, idx) => (
            <div key={idx} className={`rounded-lg border p-4 space-y-2 ${DOMAIN_COLORS[event.domain]}`}>
              {/* Header: Icon, Label, Strength */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3 flex-1">
                  <span className="text-2xl">{EVENT_ICONS[event.event_type] ?? '•'}</span>
                  <div>
                    <p className="font-semibold text-white">
                      {EVENT_LABELS[event.event_type] || event.event_type}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {event.domain.replace(/_/g, ' ').charAt(0).toUpperCase() + event.domain.replace(/_/g, ' ').slice(1)}
                    </p>
                    {event.description && (
                      <p className="text-xs text-gray-300 mt-1 leading-5 max-w-2xl">
                        {event.description}
                      </p>
                    )}
                  </div>
                </div>
                <span className={`inline-block px-2.5 py-1 rounded text-xs font-semibold border whitespace-nowrap ${STRENGTH_BADGES[event.strength]}`}>
                  {event.strength.charAt(0).toUpperCase() + event.strength.slice(1)}
                </span>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                {event.metric_value !== null && (
                  <div>
                    <p className="text-xs text-gray-400">Value</p>
                    <p className="text-white font-mono">{formatMetricValue(event.metric_value, event.event_type)}</p>
                  </div>
                )}
                {event.threshold_value !== null && (
                  <div>
                    <p className="text-xs text-gray-400">Threshold</p>
                    <p className="text-white font-mono">{formatMetricValue(event.threshold_value, event.event_type)}</p>
                  </div>
                )}
                {event.detected_on && (
                  <div>
                    <p className="text-xs text-gray-400">Detected</p>
                    <p className="text-white font-mono">{event.detected_on}</p>
                  </div>
                )}
              </div>

              {/* Metadata */}
              {Object.keys(event.metadata).length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-700/50 space-y-1 text-xs">
                  {Object.entries(event.metadata).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between text-gray-300">
                      <span className="text-gray-400">{key.replace(/_/g, ' ')}:</span>
                      <span className="font-mono text-gray-200">
                        {typeof value === 'number' ? value.toFixed(2) : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
          <svg className="w-12 h-12 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <p className="text-gray-400 text-sm">No significant events detected for {ticker}</p>
          <p className="text-gray-500 text-xs mt-2">Market conditions appear stable</p>
        </div>
      )}
    </div>
  );
}
