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

const STRENGTH_STYLES: Record<Strength, string> = {
  low: 'border-amber-500/35 bg-amber-500/12 text-amber-200',
  medium: 'border-orange-500/35 bg-orange-500/12 text-orange-200',
  high: 'border-rose-500/35 bg-rose-500/12 text-rose-200',
};

const DOMAIN_META: Record<Domain, { label: string; chip: string }> = {
  price_technical: {
    label: 'Price & technical',
    chip: 'border-sky-500/30 bg-sky-500/10 text-sky-100',
  },
  news_information: {
    label: 'News & information',
    chip: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
  },
  fundamental: {
    label: 'Fundamental',
    chip: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100',
  },
};

function formatDetectedLabel(value: string | null): string {
  if (!value) return 'Recent';
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

function strongestStrength(events: DetectedEvent[]): Strength | null {
  if (events.some((event) => event.strength === 'high')) return 'high';
  if (events.some((event) => event.strength === 'medium')) return 'medium';
  if (events.some((event) => event.strength === 'low')) return 'low';
  return null;
}

function eventSortValue(event: DetectedEvent): number {
  const strengthWeight = event.strength === 'high' ? 3 : event.strength === 'medium' ? 2 : 1;
  const detectedAt = event.detected_on ? new Date(event.detected_on).getTime() : 0;
  return strengthWeight * 1_000_000_000_000 + detectedAt;
}

function bundleSortValue(bundle: EventBundle): number {
  return bundle.eventScore * 1000 + bundle.eventCount;
}

function SummaryCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-700/70 bg-slate-950/70 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-400">{detail}</p>
    </div>
  );
}

export default function DashboardEventsView({ widgets, tickerToName }: DashboardEventsViewProps) {
  const [bundles, setBundles] = useState<EventBundle[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [failedTickers, setFailedTickers] = useState<string[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>('all');
  const [selectedStrength, setSelectedStrength] = useState<StrengthFilter>('all');
  const [selectedDomain, setSelectedDomain] = useState<DomainFilter>('all');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

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
      setLoadError(nextBundles.length === 0 ? 'Unable to load watchlist events right now.' : null);
      setIsLoading(false);
    };

    load().catch(() => {
      if (cancelled) return;
      setBundles([]);
      setFailedTickers(widgets.map((widget) => widget.ticker));
      setLoadError('Unable to load watchlist events right now.');
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

  const totalEvents = useMemo(
    () => bundles.reduce((sum, bundle) => sum + bundle.events.length, 0),
    [bundles],
  );

  const highPriorityEvents = useMemo(
    () => bundles.reduce((sum, bundle) => sum + bundle.events.filter((event) => event.strength === 'high').length, 0),
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

  if (widgets.length === 0) {
    return (
      <div className="rounded-[1.75rem] border border-slate-700/70 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] p-8 text-center">
        <p className="text-sm font-medium text-white">No subscribed tickers yet.</p>
        <p className="mt-2 text-sm text-slate-400">
          Subscribe to stocks first, then this tab will show the full event stream across your watchlist.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-[1.75rem] border border-slate-700/70 bg-[radial-gradient(circle_at_top_left,rgba(52,211,153,0.10),transparent_30%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.10),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] shadow-[0_24px_80px_-42px_rgba(2,6,23,0.95)]">
        <div className="border-b border-slate-700/70 px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-300/80">Watchlist Event Radar</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-[1.9rem]">
                All subscribed-ticker signals in one board.
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Uses the same deterministic event feed as each ticker page, then rolls those signals up into a watchlist-wide event monitor.
              </p>
            </div>

            <div className="flex flex-wrap gap-2 xl:justify-end">
              <div className="rounded-full border border-slate-700 bg-slate-900/65 px-3 py-2 text-sm text-slate-300">
                <span className="font-semibold text-white">{totalEvents}</span> live signals
              </div>
              <div className="rounded-full border border-slate-700 bg-slate-900/65 px-3 py-2 text-sm text-slate-300">
                <span className="font-semibold text-white">{eventfulBundles.length}</span> active tickers
              </div>
              {lastUpdated && (
                <div className="rounded-full border border-slate-700 bg-slate-900/65 px-3 py-2 text-sm text-slate-300">
                  Updated {lastUpdated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                </div>
              )}
              <button
                type="button"
                onClick={() => setRefreshIndex((value) => value + 1)}
                disabled={isLoading}
                className="rounded-full border border-emerald-500/35 bg-emerald-500/12 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:border-emerald-400/45 hover:bg-emerald-500/18 disabled:cursor-default disabled:opacity-60"
              >
                {isLoading ? 'Refreshing…' : 'Refresh events'}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              label="Subscribed"
              value={String(widgets.length)}
              detail="Tickers scanned through the shared ticker-page event pipeline."
            />
            <SummaryCard
              label="Eventful"
              value={String(eventfulBundles.length)}
              detail={`${quietBundles.length} quiet ${quietBundles.length === 1 ? 'name' : 'names'} currently without flagged signals.`}
            />
            <SummaryCard
              label="High Priority"
              value={String(highPriorityEvents)}
              detail="Signals marked high strength across your watchlist."
            />
            <SummaryCard
              label="Coverage"
              value={`${Math.round((eventfulBundles.length / Math.max(widgets.length, 1)) * 100)}%`}
              detail="Share of subscribed names with at least one active deterministic event."
            />
          </div>
        </div>

        <div className="px-5 py-4 sm:px-6">
          <div className="flex flex-col gap-4">
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Ticker focus</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedTicker('all')}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    selectedTicker === 'all'
                      ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-100'
                      : 'border-slate-600 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                  }`}
                >
                  All eventful
                </button>
                {eventfulBundles.map((bundle) => (
                  <button
                    key={bundle.ticker}
                    type="button"
                    onClick={() => setSelectedTicker(bundle.ticker)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                      selectedTicker === bundle.ticker
                        ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-100'
                        : 'border-slate-600 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                    }`}
                  >
                    {bundle.ticker}
                    <span className={`ml-1.5 ${selectedTicker === bundle.ticker ? 'text-emerald-100/90' : 'text-slate-500'}`}>
                      {bundle.events.length}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Strength</p>
                <div className="flex flex-wrap gap-2">
                  {(['all', 'high', 'medium', 'low'] as const).map((strength) => (
                    <button
                      key={strength}
                      type="button"
                      onClick={() => setSelectedStrength(strength)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                        selectedStrength === strength
                          ? 'border-cyan-400/35 bg-cyan-500/14 text-cyan-100'
                          : 'border-slate-600 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                      }`}
                    >
                      {strength === 'all' ? 'All strengths' : `${strength.charAt(0).toUpperCase()}${strength.slice(1)} only`}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Domain</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedDomain('all')}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                      selectedDomain === 'all'
                        ? 'border-cyan-400/35 bg-cyan-500/14 text-cyan-100'
                        : 'border-slate-600 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                    }`}
                  >
                    All domains
                  </button>
                  {(['price_technical', 'news_information', 'fundamental'] as const).map((domain) => (
                    <button
                      key={domain}
                      type="button"
                      onClick={() => setSelectedDomain(domain)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                        selectedDomain === domain
                          ? 'border-cyan-400/35 bg-cyan-500/14 text-cyan-100'
                          : 'border-slate-600 bg-slate-900/60 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                      }`}
                    >
                      {DOMAIN_META[domain].label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {failedTickers.length > 0 && (
        <div className="rounded-2xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Loaded partial watchlist coverage. Missing events for: {failedTickers.join(', ')}.
        </div>
      )}

      {loadError && (
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {loadError}
        </div>
      )}

      {isLoading && bundles.length === 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="animate-pulse rounded-[1.5rem] border border-slate-700/70 bg-slate-900/75 p-5">
              <div className="h-4 w-28 rounded bg-slate-700/80" />
              <div className="mt-3 h-7 w-2/3 rounded bg-slate-700/70" />
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                <div className="h-28 rounded-2xl bg-slate-800/80" />
                <div className="h-28 rounded-2xl bg-slate-800/80" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLoading && visibleBundles.length === 0 && bundles.length > 0 && (
        <div className="rounded-[1.5rem] border border-slate-700/70 bg-slate-950/70 px-6 py-10 text-center">
          <p className="text-sm font-medium text-white">No signals match the current filters.</p>
          <p className="mt-2 text-sm text-slate-400">Try broadening the strength or domain filter to restore the full event feed.</p>
        </div>
      )}

      {visibleBundles.map((bundle) => {
        const strongest = strongestStrength(bundle.events);
        const strongestLabel = strongest ? `${strongest.charAt(0).toUpperCase()}${strongest.slice(1)}` : 'Quiet';
        const priceChangeColor = bundle.dailyChangePercent >= 0 ? 'text-emerald-300' : 'text-rose-300';

        return (
          <section
            key={bundle.ticker}
            className="overflow-hidden rounded-[1.5rem] border border-slate-700/70 bg-[linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] shadow-[0_16px_46px_-32px_rgba(2,6,23,0.92)]"
          >
            <div className="border-b border-slate-700/70 px-5 py-4 sm:px-6">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/tickers/${bundle.ticker}`}
                      className="inline-flex items-center rounded-full border border-slate-600 bg-slate-900/80 px-3 py-1 text-sm font-semibold text-white transition-colors hover:border-slate-500 hover:bg-slate-800"
                    >
                      {bundle.ticker}
                    </Link>
                    <span className="truncate text-sm text-slate-300">{bundle.name}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-mono text-slate-100">
                      {bundle.currentPrice > 0 ? formatPrice(bundle.currentPrice, bundle.currency) : '—'}
                    </span>
                    <span className={`font-mono ${priceChangeColor}`}>
                      {bundle.dailyChangePercent >= 0 ? '+' : ''}{bundle.dailyChangePercent.toFixed(2)}%
                    </span>
                    <span className="rounded-full border border-slate-700 bg-slate-900/65 px-2.5 py-1 text-xs font-medium text-slate-300">
                      {bundle.events.length} active {bundle.events.length === 1 ? 'signal' : 'signals'}
                    </span>
                  </div>
                  {bundle.dominantEvents.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {bundle.dominantEvents.slice(0, 4).map((eventType) => (
                        <span
                          key={eventType}
                          className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900/70 px-2.5 py-1 text-xs font-medium text-slate-200"
                        >
                          <EventIcon eventType={eventType} className="h-3.5 w-3.5 shrink-0 text-sky-300" />
                          <span>{formatDominantEventLabel(eventType)}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-3 xl:min-w-[22rem]">
                  <div className="rounded-2xl border border-slate-700/70 bg-slate-950/70 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Event score</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{bundle.eventScore.toFixed(1)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/70 bg-slate-950/70 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Strongest</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{strongestLabel}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-700/70 bg-slate-950/70 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Detected</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{formatDetectedLabel(bundle.events[0]?.detected_on ?? null)}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 p-5 sm:p-6 xl:grid-cols-2">
              {bundle.events.map((event, index) => {
                const metricValue = formatMetricValue(event.metric_value, event.event_type);
                const thresholdValue = formatMetricValue(event.threshold_value, event.event_type);
                const domainMeta = DOMAIN_META[event.domain];
                return (
                  <article
                    key={`${bundle.ticker}-${event.event_type}-${index}`}
                    className="rounded-[1.15rem] border border-slate-700/70 bg-slate-950/72 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="rounded-full border border-slate-700 bg-slate-900/80 p-1.5 text-sky-300">
                            <EventIcon eventType={event.event_type} className="h-4 w-4" />
                          </span>
                          <p className="truncate text-sm font-semibold text-white">{formatDominantEventLabel(event.event_type)}</p>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${domainMeta.chip}`}>
                            {domainMeta.label}
                          </span>
                          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${STRENGTH_STYLES[event.strength]}`}>
                            {event.strength.charAt(0).toUpperCase() + event.strength.slice(1)}
                          </span>
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Detected</p>
                        <p className="mt-1 text-sm font-medium text-slate-200">{formatDetectedLabel(event.detected_on)}</p>
                      </div>
                    </div>

                    {event.description && (
                      <p className="mt-3 text-sm leading-6 text-slate-300">{event.description}</p>
                    )}

                    <div className="mt-4 flex flex-wrap gap-2">
                      {metricValue && (
                        <div className="rounded-full border border-slate-700 bg-slate-900/75 px-3 py-1.5 text-xs text-slate-300">
                          Value <span className="ml-1 font-mono text-white">{metricValue}</span>
                        </div>
                      )}
                      {thresholdValue && (
                        <div className="rounded-full border border-slate-700 bg-slate-900/75 px-3 py-1.5 text-xs text-slate-300">
                          Threshold <span className="ml-1 font-mono text-white">{thresholdValue}</span>
                        </div>
                      )}
                      {event.window_start && event.window_end && (
                        <div className="rounded-full border border-slate-700 bg-slate-900/75 px-3 py-1.5 text-xs text-slate-300">
                          Window <span className="ml-1 font-mono text-white">{formatDetectedLabel(event.window_start)} to {formatDetectedLabel(event.window_end)}</span>
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        );
      })}

      {!isLoading && quietBundles.length > 0 && selectedTicker === 'all' && (
        <section className="rounded-[1.5rem] border border-slate-700/70 bg-slate-950/70 px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Quiet watchlist</p>
              <p className="mt-1 text-sm text-slate-300">Subscribed names without currently flagged deterministic signals.</p>
            </div>
            <div className="rounded-full border border-slate-700 bg-slate-900/65 px-3 py-2 text-sm text-slate-300">
              {quietBundles.length} quiet {quietBundles.length === 1 ? 'ticker' : 'tickers'}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {quietBundles.map((bundle) => (
              <Link
                key={bundle.ticker}
                to={`/tickers/${bundle.ticker}`}
                className="rounded-full border border-slate-700 bg-slate-900/75 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-slate-500 hover:bg-slate-800 hover:text-white"
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
