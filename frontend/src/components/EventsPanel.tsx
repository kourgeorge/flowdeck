import { useMemo, useState } from 'react';

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

export const EVENT_LABELS: Record<string, string> = {
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
  price_technical: 'border-l-slate-500',
  news_information: 'border-l-slate-500',
  fundamental: 'border-l-slate-500',
};

const STRENGTH_BADGES: Record<string, string> = {
  low: 'bg-yellow-900/40 text-yellow-200 border-yellow-700/50',
  medium: 'bg-orange-900/40 text-orange-200 border-orange-700/50',
  high: 'bg-red-900/40 text-red-200 border-red-700/50',
};

const EVENT_WEIGHTS: Record<string, number> = {
  price_spike_up: 2.0,
  price_spike_down: 2.0,
  price_gap_up: 2.0,
  price_gap_down: 2.0,
  volatility_expansion: 1.25,
  volatility_compression: 1.0,
  moving_average_cross: 1.5,
  new_52w_high: 2.5,
  new_52w_low: 2.5,
  volume_spike: 1.5,
  earnings_upcoming: 1.25,
  insider_buying: 1.75,
  insider_selling: 1.75,
  rsi_bullish_divergence: 2.0,
  rsi_bearish_divergence: 2.0,
};

const STRENGTH_MULTIPLIERS: Record<DetectedEvent['strength'], number> = {
  low: 1.0,
  medium: 1.5,
  high: 2.0,
};

const PANEL_SHELL =
  'rounded-lg border border-gray-700 bg-gray-800';

const EVENTS_PANEL_METADATA = {
  contains:
    'A structured view of the most important analytic signals detected for this ticker, including automatically identified anomalies, event score, dominant signals, event strength, measured values, thresholds, and detection dates.',
  aspects:
    'Price and technical signals such as spikes, gaps, volatility expansion or compression, moving-average crosses, 52-week highs or lows, volume spikes, and RSI divergences, plus currently supported fundamental and ownership events such as upcoming earnings and insider buying or selling.',
  methodology:
    'FlowDeck detects these signals automatically using deterministic rules over cached normalized market data. Each event type uses explicit trigger thresholds and severity bands to classify low, medium, or high strength. No LLM is used in the extraction layer.',
};

export function formatDominantEventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType.replace(/_/g, ' ');
}

export function EventIcon({ eventType, className = 'h-4 w-4' }: { eventType: string; className?: string }) {
  const shared = {
    className,
    fill: 'none',
    stroke: 'currentColor',
    viewBox: '0 0 24 24',
    'aria-hidden': true as const,
  };

  switch (eventType) {
    case 'price_spike_up':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 18h16M6 15l4-4 3 2 5-6" />
        </svg>
      );
    case 'price_spike_down':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 18h16M6 9l4 4 3-2 5 6" />
        </svg>
      );
    case 'price_gap_up':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 18V7m0 0-4 4m4-4 4 4" />
        </svg>
      );
    case 'price_gap_down':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 6v11m0 0-4-4m4 4 4-4" />
        </svg>
      );
    case 'volatility_expansion':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 12h4l2-5 4 10 2-5h4" />
        </svg>
      );
    case 'volatility_compression':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 12h5m6 0h5M11 9l-2 3 2 3m2-6 2 3-2 3" />
        </svg>
      );
    case 'moving_average_cross':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 8c3 0 4 8 8 8s5-8 8-8M4 16c3 0 4-8 8-8s5 8 8 8" />
        </svg>
      );
    case 'new_52w_high':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 19V7m0 0-4 4m4-4 4 4M5 5h14" />
        </svg>
      );
    case 'new_52w_low':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 5v12m0 0-4-4m4 4 4-4M5 19h14" />
        </svg>
      );
    case 'volume_spike':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18V11m6 7V7m6 11v-5" />
        </svg>
      );
    case 'earnings_upcoming':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 3v3m8-3v3M5 9h14M6 6h12a1 1 0 0 1 1 1v11a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V7a1 1 0 0 1 1-1Z" />
        </svg>
      );
    case 'insider_buying':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 19V7m0 0-4 4m4-4 4 4M7 19h10" />
        </svg>
      );
    case 'insider_selling':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 5v12m0 0-4-4m4 4 4-4M7 5h10" />
        </svg>
      );
    case 'rsi_bullish_divergence':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 16c2.5 0 3-8 6-8s3.5 8 8 8M5 10c2.5 0 3 8 6 8s3.5-8 8-8" />
        </svg>
      );
    case 'rsi_bearish_divergence':
      return (
        <svg {...shared}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M5 8c2.5 0 3 8 6 8s3.5-8 8-8M5 14c2.5 0 3-8 6-8s3.5 8 8 8" />
        </svg>
      );
    default:
      return (
        <svg {...shared}>
          <circle cx="12" cy="12" r="3" strokeWidth={1.8} />
        </svg>
      );
  }
}

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

function getEventContribution(event: DetectedEvent): number {
  const weight = EVENT_WEIGHTS[event.event_type] ?? 1.0;
  const multiplier = STRENGTH_MULTIPLIERS[event.strength] ?? 1.0;
  return weight * multiplier;
}

function getEventWeight(event: DetectedEvent): number {
  return EVENT_WEIGHTS[event.event_type] ?? 1.0;
}

function getEventSortTimestamp(event: DetectedEvent): number {
  const candidates = [event.detected_on, event.window_end, event.window_start];

  for (const candidate of candidates) {
    if (!candidate) continue;
    const timestamp = new Date(candidate).getTime();
    if (!Number.isNaN(timestamp)) return timestamp;
  }

  return 0;
}

function EventsMoreInfo() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-700/30"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <svg className="h-5 w-5 shrink-0 text-sky-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          What analytic signals are shown here and how are they identified?
        </span>
        <svg
          className={`h-5 w-5 shrink-0 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="space-y-4 border-t border-gray-700 px-4 pb-4 pt-3 text-sm">
          <div>
            <div className="mb-1.5 font-semibold text-gray-200">What it contains</div>
            <p className="leading-relaxed text-gray-400">{EVENTS_PANEL_METADATA.contains}</p>
          </div>
          <div>
            <div className="mb-1.5 font-semibold text-gray-200">Aspects investigated</div>
            <p className="leading-relaxed text-gray-400">{EVENTS_PANEL_METADATA.aspects}</p>
          </div>
          <div>
            <div className="mb-1.5 font-semibold text-gray-200">How it was done</div>
            <p className="leading-relaxed text-gray-400">{EVENTS_PANEL_METADATA.methodology}</p>
          </div>
        </div>
      )}
    </div>
  );
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

  const sortedEvents = useMemo(
    () => [...events].sort((a, b) => getEventSortTimestamp(b) - getEventSortTimestamp(a)),
    [events],
  );

  if (error) {
    return (
      <div className={`${PANEL_SHELL} p-4`}>
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
      <div className={`${PANEL_SHELL} p-4 space-y-4 animate-pulse`}>
        <div className="h-6 bg-sky-900/40 rounded w-40" />
        <div className="space-y-2">
          <div className="h-4 bg-sky-900/30 rounded w-full" />
          <div className="h-4 bg-sky-900/30 rounded w-5/6" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Score Summary */}
      <div className={`${PANEL_SHELL} p-4`}>
        <div className="flex items-center justify-between gap-4 mb-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.14em] text-gray-300">Analytic Signals</p>
            <p className="text-sm text-gray-400 mt-1">Automatically identified anomalies and important events for this ticker.</p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-sm text-gray-400 mb-1">Event Score</p>
            <p className={`text-2xl font-semibold ${scoreColor}`}>{eventScore.toFixed(1)}</p>
            <p className="text-sm text-gray-400 mt-0.5">{scoreLabel}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Total Events</p>
            <p className="text-2xl font-semibold text-gray-200">{sortedEvents.length}</p>
            <p className="text-sm text-gray-400 mt-0.5">{sortedEvents.length === 1 ? 'event' : 'events'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Dominant Signals</p>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {dominantEvents.slice(0, 3).map((eventType) => (
                <span key={eventType} className="inline-flex items-center gap-2 rounded border border-gray-700 bg-gray-900 px-2.5 py-1.5 text-sm font-medium text-gray-200">
                  <EventIcon eventType={eventType} className="h-4 w-4 shrink-0 text-sky-300" />
                  <span>{formatDominantEventLabel(eventType)}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <EventsMoreInfo />

      {/* Events List */}
      {sortedEvents.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {sortedEvents.map((event, idx) => (
            <div key={idx} className={`rounded-lg border border-gray-700 border-l-2 bg-gray-800 p-3 ${DOMAIN_COLORS[event.domain]}`}>
              {/* Header: Icon, Label, Strength */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                  <span className="shrink-0 text-sky-300 mt-0.5">
                    <EventIcon eventType={event.event_type} className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-200 leading-5">
                      {EVENT_LABELS[event.event_type] || event.event_type}
                    </p>
                    <p className="text-sm text-gray-400 mt-0.5">
                      {event.domain.replace(/_/g, ' ').charAt(0).toUpperCase() + event.domain.replace(/_/g, ' ').slice(1)}
                    </p>
                    {event.description && (
                      <p className="text-sm text-gray-400 mt-1 leading-5">
                        {event.description}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-end gap-2">
                  {event.detected_on && (
                    <div className="text-right">
                      <div className="text-xs text-gray-400">Detected</div>
                      <div className="text-sm font-mono text-gray-200">{event.detected_on}</div>
                    </div>
                  )}
                  <span className={`inline-block px-2 py-0.5 rounded text-sm font-semibold border whitespace-nowrap ${STRENGTH_BADGES[event.strength]}`}>
                    {event.strength.charAt(0).toUpperCase() + event.strength.slice(1)}
                  </span>
                </div>
              </div>

              {/* Metrics */}
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <div className="inline-flex items-baseline gap-1.5">
                  <span className="text-sm text-gray-400">Score</span>
                  <span className="text-sm text-gray-200 font-mono">{getEventContribution(event).toFixed(2)}</span>
                </div>
                <div className="inline-flex items-baseline gap-1.5">
                  <span className="text-sm text-gray-400">Base Weight</span>
                  <span className="text-sm text-gray-200 font-mono">{getEventWeight(event).toFixed(2)}</span>
                </div>
                {event.metric_value !== null && (
                  <div className="inline-flex items-baseline gap-1.5">
                    <span className="text-sm text-gray-400">Value</span>
                    <span className="text-sm text-gray-200 font-mono">{formatMetricValue(event.metric_value, event.event_type)}</span>
                  </div>
                )}
                {event.threshold_value !== null && (
                  <div className="inline-flex items-baseline gap-1.5">
                    <span className="text-sm text-gray-400">Threshold</span>
                    <span className="text-sm text-gray-200 font-mono">{formatMetricValue(event.threshold_value, event.event_type)}</span>
                  </div>
                )}
              </div>

              {/* Metadata */}
              {Object.keys(event.metadata).length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-700 space-y-1 text-xs">
                  {Object.entries(event.metadata).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between gap-3 text-gray-300">
                      <span className="text-xs text-gray-400">{key.replace(/_/g, ' ')}:</span>
                      <span className="font-mono text-xs text-gray-200 text-right">
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
        <div className={`${PANEL_SHELL} p-8 text-center`}>
          <svg className="w-12 h-12 text-gray-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <p className="text-gray-300 text-sm">No significant events detected for {ticker}</p>
          <p className="text-gray-400 text-xs mt-2">The platform event layer did not flag a notable signal.</p>
        </div>
      )}
    </div>
  );
}
