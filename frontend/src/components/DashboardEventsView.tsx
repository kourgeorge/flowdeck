import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { tickerApi } from '../services/api';
import type { TickerWidget } from '../services/types';
import { EventIcon, formatDominantEventLabel } from './EventsPanel';
import { formatPrice } from '../utils/currency';

type Strength = 'low' | 'medium' | 'high';
type Domain = 'price_technical' | 'news_information' | 'fundamental';
type StrengthFilter = 'all' | Strength;
type DomainFilter = 'all' | Domain;
type TickerEventsResponse = Awaited<ReturnType<typeof tickerApi.getEvents>>;
type DetectedEvent = TickerEventsResponse['events'][number];

interface DashboardEventsViewProps {
  widgets: TickerWidget[];
  tickerToName: Record<string, string>;
  dashboardLoading?: boolean;
  compact?: boolean;
}

type EventBundle = {
  ticker: string;
  name: string;
  currentPrice: number;
  dailyChangePercent: number;
  currency?: string | null;
  eventScore: number;
  eventCount: number;
  dominantEvents: string[];
  events: DetectedEvent[];
};

const STRENGTH_META: Record<Strength, { label: string; chip: string }> = {
  low: {
    label: 'Low',
    chip: 'border-emerald-700/50 bg-emerald-900/30 text-emerald-300',
  },
  medium: {
    label: 'Medium',
    chip: 'border-violet-700/50 bg-violet-900/30 text-violet-300',
  },
  high: {
    label: 'High',
    chip: 'border-blue-700/50 bg-blue-900/30 text-blue-300',
  },
};

const DOMAIN_META: Record<Domain, { label: string; chip: string; icon: string }> = {
  price_technical: {
    label: 'Price & technical',
    chip: 'border-slate-700 bg-slate-800 text-slate-300',
    icon: 'border-slate-700 bg-slate-800 text-slate-300',
  },
  news_information: {
    label: 'News & information',
    chip: 'border-teal-800/50 bg-teal-950/30 text-teal-300',
    icon: 'border-teal-800/50 bg-teal-950/30 text-teal-300',
  },
  fundamental: {
    label: 'Fundamental',
    chip: 'border-amber-800/50 bg-amber-950/30 text-amber-300',
    icon: 'border-amber-800/50 bg-amber-950/30 text-amber-300',
  },
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

const STRENGTH_MULTIPLIERS: Record<Strength, number> = {
  low: 1.0,
  medium: 1.5,
  high: 2.0,
};

function formatShortDate(value: string | null): string {
  if (!value) return 'Recent';
  const dateOnlyMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch;
    const parsed = new Date(Number(year), Number(month) - 1, Number(day));
    return parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatMetricValue(value: number | null, eventType: string): string | null {
  if (value == null || Number.isNaN(value)) return null;
  if (['price_spike_up', 'price_spike_down', 'price_gap_up', 'price_gap_down'].includes(eventType)) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  }
  if (eventType === 'earnings_upcoming') {
    return `${value.toFixed(0)}d`;
  }
  if (['volatility_expansion', 'volatility_compression', 'volume_spike'].includes(eventType)) {
    return `${value.toFixed(2)}x`;
  }
  if (['insider_buying', 'insider_selling'].includes(eventType)) {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
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

function formatMetadataValue(value: unknown): string {
  if (typeof value === 'number') return value.toFixed(2);
  return String(value);
}

function strengthRank(strength: Strength): number {
  if (strength === 'high') return 3;
  if (strength === 'medium') return 2;
  return 1;
}

function eventSortValue(event: DetectedEvent): number {
  const detectedAt = event.detected_on ? new Date(event.detected_on).getTime() : 0;
  return strengthRank(event.strength) * 1_000_000_000_000 + detectedAt;
}

function bundleSortValue(bundle: EventBundle): number {
  const newestEvent = bundle.events[0] ? eventSortValue(bundle.events[0]) : 0;
  return newestEvent + bundle.eventScore * 1000 + bundle.eventCount;
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border px-3 py-1.5 text-xs font-medium transition-colors ${
        active
          ? 'rounded-sm border-blue-600 bg-blue-600 text-white'
          : 'rounded-sm border-gray-700 bg-gray-800 text-gray-300 hover:border-gray-600 hover:bg-gray-700 hover:text-white'
      }`}
    >
      {label}
    </button>
  );
}

export default function DashboardEventsView({
  widgets,
  tickerToName,
  dashboardLoading = false,
  compact = false,
}: DashboardEventsViewProps) {
  const [bundles, setBundles] = useState<EventBundle[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [failedTickers, setFailedTickers] = useState<string[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>('all');
  const [selectedStrength, setSelectedStrength] = useState<StrengthFilter>('all');
  const [selectedDomain, setSelectedDomain] = useState<DomainFilter>('all');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;

    if (widgets.length === 0) {
      setBundles([]);
      setLoadError(null);
      setFailedTickers([]);
      setIsLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const load = async () => {
      setIsLoading(true);
      setLoadError(null);

      const settled = await Promise.allSettled(
        widgets.map(async (widget) => {
          const response = await tickerApi.getEvents(widget.ticker);
          return { widget, response };
        }),
      );

      if (cancelled) return;

      const nextBundles: EventBundle[] = [];
      const nextFailed: string[] = [];

      settled.forEach((result, index) => {
        const widget = widgets[index];
        if (result.status !== 'fulfilled') {
          nextFailed.push(widget.ticker);
          return;
        }

        const { response } = result.value;
        if (response.error) {
          nextFailed.push(widget.ticker);
          return;
        }

        nextBundles.push({
          ticker: widget.ticker,
          name: widget.name || tickerToName[widget.ticker] || widget.ticker,
          currentPrice: widget.current_price,
          dailyChangePercent: widget.daily_change_percent,
          currency: widget.currency,
          eventScore: response.event_score ?? 0,
          eventCount: response.event_count ?? response.events.length,
          dominantEvents: response.dominant_events ?? [],
          events: [...response.events].sort((left, right) => eventSortValue(right) - eventSortValue(left)),
        });
      });

      setBundles(nextBundles.sort((left, right) => bundleSortValue(right) - bundleSortValue(left)));
      setFailedTickers(nextFailed);
      setLastUpdated(new Date());
      setLoadError(nextBundles.length === 0 ? 'Unable to load portfolio events right now.' : null);
      setIsLoading(false);
    };

    load().catch(() => {
      if (cancelled) return;
      setBundles([]);
      setFailedTickers(widgets.map((widget) => widget.ticker));
      setLoadError('Unable to load portfolio events right now.');
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [refreshIndex, tickerToName, widgets]);

  useEffect(() => {
    if (selectedTicker === 'all') return;
    if (!bundles.some((bundle) => bundle.ticker === selectedTicker)) {
      setSelectedTicker('all');
    }
  }, [bundles, selectedTicker]);

  const quietBundles = useMemo(
    () => bundles.filter((bundle) => bundle.events.length === 0),
    [bundles],
  );

  const eventfulBundles = useMemo(
    () => bundles.filter((bundle) => bundle.events.length > 0),
    [bundles],
  );

  const visibleBundles = useMemo(() => {
    return eventfulBundles
      .map((bundle) => {
        if (selectedTicker !== 'all' && bundle.ticker !== selectedTicker) return null;
        const filteredEvents = bundle.events.filter((event) => {
          if (selectedStrength !== 'all' && event.strength !== selectedStrength) return false;
          if (selectedDomain !== 'all' && event.domain !== selectedDomain) return false;
          return true;
        });
        if (filteredEvents.length === 0) return null;
        return {
          ...bundle,
          events: filteredEvents,
        };
      })
      .filter((bundle): bundle is EventBundle => bundle !== null);
  }, [eventfulBundles, selectedDomain, selectedStrength, selectedTicker]);

  const visibleEventCount = useMemo(
    () => visibleBundles.reduce((sum, bundle) => sum + bundle.events.length, 0),
    [visibleBundles],
  );

  const visibleHighPriorityCount = useMemo(
    () => visibleBundles.reduce((sum, bundle) => sum + bundle.events.filter((event) => event.strength === 'high').length, 0),
    [visibleBundles],
  );

  const visibleFeed = useMemo(() => {
    const entries = visibleBundles.flatMap((bundle) => (
      bundle.events.map((event) => ({ bundle, event }))
    ));
    const sorted = entries
      .sort((left, right) => eventSortValue(right.event) - eventSortValue(left.event));
    return compact ? sorted : sorted.slice(0, 40);
  }, [compact, visibleBundles]);

  const toggleEventExpanded = (eventKey: string) => {
    setExpandedEvents((current) => ({
      ...current,
      [eventKey]: !current[eventKey],
    }));
  };

  if (widgets.length === 0 && dashboardLoading) {
    return (
      <div className="border border-gray-700 bg-gray-800/50 p-3 sm:p-4">
        {[1, 2, 3, 4, 5].map((item) => (
          <div key={item} className="animate-pulse border-b border-gray-700/70 px-2 py-4 last:border-b-0 sm:px-3">
            <div className="flex items-start gap-3">
              <div className="h-9 w-9 rounded-sm bg-gray-700/60" />
              <div className="flex-1 space-y-2">
                <div className="flex flex-wrap gap-2">
                  <div className="h-5 w-28 rounded-sm bg-gray-700/60" />
                  <div className="h-5 w-20 rounded-sm bg-gray-700/60" />
                </div>
                <div className="h-4 w-40 rounded-sm bg-gray-700/60" />
                <div className="h-4 w-64 rounded-sm bg-gray-700/50" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (widgets.length === 0) {
    return (
      <div className="border border-gray-700 bg-gray-800/50 px-6 py-10 text-center">
        <p className="text-sm font-medium text-white">No subscribed tickers yet.</p>
        <p className="mt-2 text-sm text-gray-400">
          Subscribe to stocks first, then this view will become a live event monitor for your portfolio.
        </p>
      </div>
    );
  }

  if (compact) {
    if (isLoading && bundles.length === 0) {
      return (
        <div className="flex h-full min-h-0 flex-col">
          <div className="space-y-1">
          {[1, 2, 3, 4, 5, 6].map((item) => (
            <div key={item} className="animate-pulse rounded-[0.9rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2">
              <div className="flex items-center gap-2">
                <div className="h-4 w-14 rounded-full bg-slate-700/70" />
                <div className="h-3 flex-1 rounded-full bg-slate-700/60" />
                <div className="h-4 w-12 rounded-full bg-slate-700/70" />
              </div>
            </div>
          ))}
          </div>
        </div>
      );
    }

    if (loadError) {
      return (
        <div className="rounded-[0.95rem] border border-rose-500/20 bg-rose-500/10 px-3 py-4 text-sm text-rose-100">
          {loadError}
        </div>
      );
    }

    if (!isLoading && visibleFeed.length === 0) {
      return (
        <div className="rounded-[0.95rem] border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-400">
          No active portfolio events right now.
        </div>
      );
    }

    return (
      <div className="flex h-full min-h-0 flex-col space-y-2">
        {failedTickers.length > 0 && (
          <div className="rounded-[0.9rem] border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-100">
            Partial coverage: {failedTickers.join(', ')}
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto pr-1 max-h-[39.75rem]">
          <div className="space-y-1">
            {visibleFeed.map(({ bundle, event }, index) => {
              const domainMeta = DOMAIN_META[event.domain];
              const score = getEventContribution(event).toFixed(2);
              return (
                <Link
                  key={`${bundle.ticker}-${event.event_type}-${event.detected_on ?? 'recent'}-${index}`}
                  to={`/tickers/${bundle.ticker}`}
                  className="flex h-9 items-center justify-between gap-3 overflow-hidden rounded-[0.9rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2 transition-colors hover:border-slate-500/70 hover:bg-slate-900"
                >
                  <div className="min-w-0 flex items-center gap-2">
                    <span className="shrink-0 rounded-full border border-slate-600/80 bg-slate-900/80 px-2 py-0.5 text-[10px] font-semibold text-white">
                      {bundle.ticker}
                    </span>
                    <span className="truncate text-xs text-slate-200">
                      {formatDominantEventLabel(event.event_type)}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5 text-[10px]">
                    <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 font-mono font-semibold text-sky-100">
                      {score}
                    </span>
                    <span className={`rounded-full border px-2 py-0.5 font-medium ${STRENGTH_META[event.strength].chip}`}>
                      {STRENGTH_META[event.strength].label}
                    </span>
                    <span className={`hidden rounded-full border px-2 py-0.5 font-medium md:inline-flex ${domainMeta.chip}`}>
                      {domainMeta.label}
                    </span>
                    <span className="text-slate-500">
                      {formatShortDate(event.detected_on)}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <section className="px-1 sm:px-0">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gray-500">Portfolio Events</p>
            <h2 className="text-2xl font-semibold tracking-tight text-white">
              Key events across your portfolio.
            </h2>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-sm border border-blue-700/50 bg-blue-900/30 px-2.5 py-1 text-blue-300">
                <span className="font-semibold text-white">{visibleEventCount}</span> matching
              </span>
              <span className="rounded-sm border border-violet-700/50 bg-violet-900/30 px-2.5 py-1 text-violet-300">
                <span className="font-semibold text-white">{visibleBundles.length}</span> active
              </span>
              <span className="rounded-sm border border-blue-700/50 bg-blue-900/30 px-2.5 py-1 text-blue-300">
                <span className="font-semibold text-white">{visibleHighPriorityCount}</span> high
              </span>
              <span className="rounded-sm border border-emerald-700/50 bg-emerald-900/30 px-2.5 py-1 text-emerald-300">
                <span className="font-semibold text-white">{quietBundles.length}</span> quiet
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {lastUpdated && (
              <div className="rounded-sm border border-gray-700 bg-gray-800 px-3 py-1 text-xs text-gray-400">
                Updated {lastUpdated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
              </div>
            )}
            <button
              type="button"
              onClick={() => setRefreshIndex((value) => value + 1)}
              disabled={isLoading}
              className="rounded-sm border border-blue-600 bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-default disabled:opacity-60"
            >
              {isLoading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>

        <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,15rem)_1fr_1fr]">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-gray-300">Ticker Focus</span>
            <select
              value={selectedTicker}
              onChange={(event) => setSelectedTicker(event.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All active tickers</option>
              {eventfulBundles.map((bundle) => (
                <option key={bundle.ticker} value={bundle.ticker}>
                  {bundle.ticker} ({bundle.events.length})
                </option>
              ))}
            </select>
          </label>

          <div>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">Strength</p>
            <div className="flex flex-wrap gap-2">
              {(['all', 'high', 'medium', 'low'] as const).map((strength) => (
                <FilterChip
                  key={strength}
                  label={strength === 'all' ? 'All strengths' : STRENGTH_META[strength].label}
                  active={selectedStrength === strength}
                  onClick={() => setSelectedStrength(strength)}
                />
              ))}
            </div>
          </div>

          <div>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">Domain</p>
            <div className="flex flex-wrap gap-2">
              <FilterChip
                label="All domains"
                active={selectedDomain === 'all'}
                onClick={() => setSelectedDomain('all')}
              />
              {(['price_technical', 'news_information', 'fundamental'] as const).map((domain) => (
                <FilterChip
                  key={domain}
                  label={DOMAIN_META[domain].label}
                  active={selectedDomain === domain}
                  onClick={() => setSelectedDomain(domain)}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      {failedTickers.length > 0 && (
        <div className="border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Partial coverage. Events did not load for: {failedTickers.join(', ')}.
        </div>
      )}

      {loadError && (
        <div className="border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {loadError}
        </div>
      )}

      {isLoading && bundles.length === 0 && (
        <div className="border border-gray-700 bg-gray-800/50 p-3 sm:p-4">
          {[1, 2, 3, 4, 5].map((item) => (
            <div key={item} className="animate-pulse border-b border-gray-700 px-2 py-4 last:border-b-0">
              <div className="h-4 w-24 rounded bg-gray-700" />
              <div className="mt-3 h-5 w-1/2 rounded bg-gray-700" />
              <div className="mt-3 flex gap-2">
                <div className="h-6 w-24 rounded-full bg-gray-700" />
                <div className="h-6 w-20 rounded-full bg-gray-700" />
                <div className="h-6 w-28 rounded-full bg-gray-700" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLoading && visibleBundles.length === 0 && bundles.length > 0 && (
        <div className="border border-gray-700 bg-gray-800/50 px-6 py-10 text-center">
          <p className="text-sm font-medium text-white">No signals match the current filters.</p>
          <p className="mt-2 text-sm text-gray-400">Broaden the ticker, strength, or domain filter to restore the full event feed.</p>
        </div>
      )}

      {visibleFeed.length > 0 && (
        <section className="border border-gray-700 bg-gray-900">
          <div className="divide-y divide-gray-700">
            {visibleFeed.map(({ bundle, event }, index) => {
              const metricValue = formatMetricValue(event.metric_value, event.event_type);
              const thresholdValue = formatMetricValue(event.threshold_value, event.event_type);
              const priceChangeColor = bundle.dailyChangePercent >= 0 ? 'text-emerald-300' : 'text-rose-300';
              const metadataEntries = Object.entries(event.metadata ?? {});
              const domainMeta = DOMAIN_META[event.domain];
              const eventKey = `${bundle.ticker}-${event.event_type}-${event.detected_on ?? 'recent'}-${event.window_start ?? 'na'}-${event.window_end ?? 'na'}`;
              const isExpanded = expandedEvents[eventKey] ?? false;

              return (
                <article
                  key={`${bundle.ticker}-${event.event_type}-${event.detected_on ?? 'recent'}-${index}`}
                  className="grid gap-3 px-5 py-4 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto]"
                >
                  <div className="flex gap-3">
                    <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border ${domainMeta.icon}`}>
                      <EventIcon eventType={event.event_type} className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="rounded-sm border border-gray-700 bg-gray-800 px-2.5 py-1 text-gray-400">
                          {formatShortDate(event.detected_on)}
                        </span>
                        <span className={`rounded-sm border px-2.5 py-1 font-medium ${STRENGTH_META[event.strength].chip}`}>
                          {STRENGTH_META[event.strength].label}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
                        <Link to={`/tickers/${bundle.ticker}`} className="text-sm font-semibold text-white hover:text-slate-200">
                          {bundle.ticker}
                        </Link>
                        <span className="text-sm text-gray-400">{bundle.name}</span>
                        <span className="text-gray-600">•</span>
                        <span className="font-mono text-gray-300">
                          {bundle.currentPrice > 0 ? formatPrice(bundle.currentPrice, bundle.currency) : '—'}
                        </span>
                        <span className={`font-mono ${priceChangeColor}`}>
                          {bundle.dailyChangePercent >= 0 ? '+' : ''}
                          {bundle.dailyChangePercent.toFixed(2)}%
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-white">
                          {formatDominantEventLabel(event.event_type)}
                        </p>
                        <span className={`rounded-sm border px-2.5 py-1 text-[11px] font-medium ${domainMeta.chip}`}>
                          {domainMeta.label}
                        </span>
                      </div>
                      {event.description && (
                        <p className="mt-1 text-sm leading-6 text-gray-400">{event.description}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-start justify-end gap-2 lg:max-w-sm">
                    {event.window_start && event.window_end && (
                      <span className="rounded-sm border border-gray-700 bg-gray-800 px-2.5 py-1 text-[11px] text-gray-300">
                        Window <span className="ml-1 font-mono text-white">{formatShortDate(event.window_start)} to {formatShortDate(event.window_end)}</span>
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => toggleEventExpanded(eventKey)}
                      className="flex items-center justify-center rounded-sm p-1.5 text-gray-500 transition-colors hover:text-gray-300"
                      aria-expanded={isExpanded}
                      aria-label={isExpanded ? 'Hide details' : 'Show details'}
                    >
                      <svg
                        className={`h-4 w-4 shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="lg:col-span-2">
                      <div className="mt-1">
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                          <div className="inline-flex items-baseline gap-1.5">
                            <span className="text-sm text-gray-400">Score</span>
                            <span className="text-sm font-mono text-gray-200">{getEventContribution(event).toFixed(2)}</span>
                          </div>
                          <div className="inline-flex items-baseline gap-1.5">
                            <span className="text-sm text-gray-400">Base Weight</span>
                            <span className="text-sm font-mono text-gray-200">{getEventWeight(event).toFixed(2)}</span>
                          </div>
                          {metricValue && (
                            <div className="inline-flex items-baseline gap-1.5">
                              <span className="text-sm text-gray-400">Value</span>
                              <span className="text-sm font-mono text-gray-200">{metricValue}</span>
                            </div>
                          )}
                          {thresholdValue && (
                            <div className="inline-flex items-baseline gap-1.5">
                              <span className="text-sm text-gray-400">Threshold</span>
                              <span className="text-sm font-mono text-gray-200">{thresholdValue}</span>
                            </div>
                          )}
                        </div>

                        {metadataEntries.length > 0 && (
                          <div className="mt-3 space-y-1 border-t border-gray-700 pt-2 text-xs">
                            {metadataEntries.map(([key, value]) => (
                              <div key={key} className="flex items-center justify-between gap-3 text-gray-300">
                                <span className="text-xs text-gray-400">{key.replace(/_/g, ' ')}:</span>
                                <span className="text-right font-mono text-xs text-gray-200">
                                  {formatMetadataValue(value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      )}

      {!isLoading && quietBundles.length > 0 && selectedTicker === 'all' && (
        <section className="border border-gray-700 bg-gray-900 px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">Quiet Watchlist</p>
              <p className="mt-1 text-sm text-gray-400">Names without an active flagged event right now.</p>
            </div>
            <div className="rounded-sm border border-emerald-700/50 bg-emerald-900/30 px-3 py-1.5 text-xs text-emerald-300">
              {quietBundles.length} quiet {quietBundles.length === 1 ? 'ticker' : 'tickers'}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {quietBundles.map((bundle) => (
              <Link
                key={bundle.ticker}
                to={`/tickers/${bundle.ticker}`}
                className="rounded-sm border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-blue-600/60 hover:bg-gray-700 hover:text-white"
              >
                {bundle.ticker}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
