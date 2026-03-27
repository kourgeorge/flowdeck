import { useEffect, useState, type ComponentProps } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import DailyDigestRunPanel from '../components/DailyDigestRunPanel';
import PageHeader from '../components/PageHeader';
import TickerSearch from '../components/TickerSearch';
import { useAuth } from '../contexts/AuthContext';
import { useDashboardData } from '../hooks/useDashboardData';
import { digestApi, type DigestBriefItem, type DigestResponse } from '../services/api';
import { getErrorMessage } from '../utils/errorHandling';

const BRIEF_SECTION_TOKENS = ['market_highlights', 'key_signals', 'what_to_watch', 'risks_opportunities'];
const IMPORTANT_EVENT_LABELS: Record<string, string> = {
  price_spike_up: 'Price spike up',
  price_spike_down: 'Price spike down',
  price_gap_up: 'Gap up',
  price_gap_down: 'Gap down',
  volatility_expansion: 'Volatility expansion',
  volatility_compression: 'Volatility compression',
  moving_average_cross: 'Moving average cross',
  new_52w_high: 'New 52-week high',
  new_52w_low: 'New 52-week low',
  volume_spike: 'Volume spike',
  earnings_upcoming: 'Upcoming earnings',
  insider_buying: 'Insider buying',
  insider_selling: 'Insider selling',
  rsi_bullish_divergence: 'RSI bullish divergence',
  rsi_bearish_divergence: 'RSI bearish divergence',
};

function briefHasStructuredSections(narrative: string): boolean {
  return /##\s*(Market Highlights|What to Watch|Risks\s*&\s*Opportunities)/i.test(narrative);
}

function narrativeForDisplay(narrative: string): string {
  if (!briefHasStructuredSections(narrative)) return narrative;
  const tokenSet = new Set(BRIEF_SECTION_TOKENS);
  return narrative
    .split('\n')
    .filter((line) => !tokenSet.has(line.trim()))
    .join('\n');
}

function formatImportantEventLabel(eventType: string): string {
  return IMPORTANT_EVENT_LABELS[eventType] ?? eventType.replace(/_/g, ' ');
}

function formatImportantEventMetric(
  importantEvent: NonNullable<DigestResponse['important_events']>[number],
): string | null {
  const { event } = importantEvent;
  if (typeof event.metric_value !== 'number') return null;
  if (['price_spike_up', 'price_spike_down', 'price_gap_up', 'price_gap_down'].includes(event.event_type)) {
    return `${event.metric_value >= 0 ? '+' : ''}${event.metric_value.toFixed(1)}%`;
  }
  if (event.event_type === 'earnings_upcoming') {
    return `${event.metric_value.toFixed(0)}d`;
  }
  if (['volatility_expansion', 'volatility_compression', 'volume_spike'].includes(event.event_type)) {
    return `${event.metric_value.toFixed(2)}x`;
  }
  if (['insider_buying', 'insider_selling'].includes(event.event_type)) {
    return `$${event.metric_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return `${event.metric_value.toFixed(2)}`;
}

const briefMarkdownComponents = {
  h2: ({ children, ...props }: ComponentProps<'h2'>) => (
    <h2
      className="text-sm font-semibold text-emerald-200 mb-1 mt-4 first:mt-0 tracking-wide"
      {...props}
    >
      {children}
    </h2>
  ),
  p: ({ children, ...props }: ComponentProps<'p'>) => (
    <p
      className="whitespace-pre-wrap leading-relaxed text-sm my-0 text-slate-300"
      style={{ fontFamily: 'Menlo, Monaco, "Courier New", monospace' }}
      {...props}
    >
      {children}
    </p>
  ),
  ul: ({ children, ...props }: ComponentProps<'ul'>) => (
    <ul
      className="list-disc pl-5 my-0 space-y-1 text-sm text-slate-300"
      style={{ fontFamily: 'Menlo, Monaco, "Courier New", monospace' }}
      {...props}
    >
      {children}
    </ul>
  ),
  li: ({ children, ...props }: ComponentProps<'li'>) => (
    <li className="leading-relaxed text-slate-300" {...props}>{children}</li>
  ),
};

function BriefIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
      />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" fill="none" viewBox="0 0 24 24" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

export default function BriefPage() {
  const { user } = useAuth();
  const { widgets } = useDashboardData({ enableRecentAnalyzed: false });
  const canViewRawDigest = user?.is_admin === true;
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;

  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [digestError, setDigestError] = useState<string | null>(null);
  const [digestDates, setDigestDates] = useState<string[]>([]);
  const [digestCountByDate, setDigestCountByDate] = useState<Record<string, number>>({});
  const [selectedDigestDate, setSelectedDigestDate] = useState<string | null>(null);
  const [digestBriefsForDay, setDigestBriefsForDay] = useState<DigestBriefItem[]>([]);
  const [selectedBrief, setSelectedBrief] = useState<DigestBriefItem | null>(null);
  const [calendarMonth, setCalendarMonth] = useState<Date>(new Date());
  const [digestUserNote, setDigestUserNote] = useState<string>('');
  const [digestNarrativeStyle, setDigestNarrativeStyle] = useState<'default' | 'concise' | 'professional' | 'technical'>('default');
  const [digestSpan, setDigestSpan] = useState<'daily' | 'weekly'>('daily');
  const [selectedFocusTickers, setSelectedFocusTickers] = useState<string[]>([]);
  const [showReferences, setShowReferences] = useState<boolean>(false);
  const [showRawDigest, setShowRawDigest] = useState<boolean>(false);
  const [digestInputExpanded, setDigestInputExpanded] = useState<boolean>(false);
  const [shareLinkCopied, setShareLinkCopied] = useState<boolean>(false);
  const [copyBriefCopied, setCopyBriefCopied] = useState<boolean>(false);
  const [emailBriefSentId, setEmailBriefSentId] = useState<number | null>(null);
  const [emailBriefSendingId, setEmailBriefSendingId] = useState<number | null>(null);
  const [newBriefModalOpen, setNewBriefModalOpen] = useState<boolean>(false);

  useEffect(() => {
    if (!user || digestDates.length > 0) return;
    (async () => {
      try {
        const res = await digestApi.getDigestDates(90, browserTimezone);
        const dates = res.dates ?? [];
        setDigestDates(dates);
        setDigestCountByDate(res.count_by_date ?? {});
        if (dates.length > 0) {
          const latestSlot = dates[dates.length - 1];
          setSelectedDigestDate(latestSlot);
          setDigest(null);
          setDigestLoading(true);
          try {
            const listRes = await digestApi.getDigestsForDate(latestSlot, browserTimezone);
            setDigestBriefsForDay(listRes.briefs);
            setSelectedBrief(listRes.briefs[0] ?? null);
          } catch {
            setDigestBriefsForDay([]);
            setSelectedBrief(null);
          } finally {
            setDigestLoading(false);
          }
        }
      } catch {
        // History is best-effort.
      }
    })();
  }, [browserTimezone, digestDates.length, user]);

  const handleRunDigest = async () => {
    setDigestError(null);
    setDigest(null);
    setDigestLoading(true);
    try {
      const trimmedNote = digestUserNote.trim();
      const styleParam = digestNarrativeStyle === 'default' ? undefined : digestNarrativeStyle;
      const params: {
        span?: 'daily' | 'weekly';
        user_note?: string;
        narrative_style?: string;
        user_focus_tickers?: string[];
        timezone?: string;
      } = {};
      if (digestSpan !== 'daily') params.span = digestSpan;
      if (trimmedNote) params.user_note = trimmedNote;
      if (styleParam) params.narrative_style = styleParam;
      if (selectedFocusTickers.length > 0) params.user_focus_tickers = selectedFocusTickers;
      params.timezone = browserTimezone;
      const data = await digestApi.getDigest(params);
      setDigest(data);
      const slot = data.span_type === 'weekly' ? `w:${data.digest_date}` : data.digest_date;
      setSelectedDigestDate(slot);
      setDigestDates((prev) => (prev.includes(slot) ? prev : [...prev, slot].sort()));
      setDigestCountByDate((prev) => ({
        ...prev,
        [slot]: (prev[slot] ?? 0) + 1,
      }));
      if (trimmedNote) {
        setDigestUserNote('');
      }
      const listRes = await digestApi.getDigestsForDate(slot, browserTimezone);
      setDigestBriefsForDay(listRes.briefs);
      setSelectedBrief(listRes.briefs[0] ?? null);
    } catch (e: unknown) {
      setDigestError(getErrorMessage(e, 'Failed to generate brief. Please try again.'));
    } finally {
      setDigestLoading(false);
    }
  };

  const handleSelectDigestDate = async (date: string) => {
    setDigestError(null);
    setDigestLoading(true);
    setSelectedDigestDate(date);
    try {
      const res = await digestApi.getDigestsForDate(date, browserTimezone);
      setDigestBriefsForDay(res.briefs);
      setSelectedBrief(res.briefs[0] ?? null);
      setDigest(null);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
      setDigestBriefsForDay([]);
      setSelectedBrief(null);
    } finally {
      setDigestLoading(false);
    }
  };

  const goToPrevMonth = () => {
    setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };

  const goToNextMonth = () => {
    setCalendarMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const formatDate = (y: number, mZeroBased: number, d: number) => {
    const m = mZeroBased + 1;
    const mm = m < 10 ? `0${m}` : String(m);
    const dd = d < 10 ? `0${d}` : String(d);
    return `${y}-${mm}-${dd}`;
  };

  const dailyDigestDates = digestDates.filter((d) => !d.startsWith('w:'));
  const weeklyDigestSlots = digestDates.filter((d) => d.startsWith('w:'));
  const digestDateSet = new Set(dailyDigestDates);

  const formatBriefTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  const formatBriefForClipboard = (brief: DigestResponse | DigestBriefItem) => {
    const lines: string[] = [];
    if (brief.digest_date) {
      lines.push(`Briefing – ${brief.digest_date}`);
    } else {
      lines.push('Briefing');
    }
    if (brief.priority_tickers && brief.priority_tickers.length > 0) {
      lines.push(`Focus: ${brief.priority_tickers.join(', ')}`);
    }
    const importantEvents = brief.important_events ?? [];
    if (importantEvents.length > 0) {
      lines.push(`Important events: ${importantEvents.map((item) => `${item.ticker} ${formatImportantEventLabel(item.event.event_type)}`).join(', ')}`);
    }
    lines.push('');
    lines.push(brief.narrative.trim());
    if (brief.what_to_watch && !briefHasStructuredSections(brief.narrative)) {
      lines.push('');
      lines.push('What to watch');
      lines.push(brief.what_to_watch.trim());
    }
    const anyBrief = brief as any;
    const refs = anyBrief?.references as
      | { label: string; url?: string | null; source?: string | null; tickers?: string[] | null }[]
      | null
      | undefined;
    if (refs && refs.length > 0) {
      lines.push('');
      lines.push('References');
      refs.forEach((ref, idx) => {
        const parts: string[] = [];
        parts.push(`${idx + 1}. ${ref.label}`);
        const meta: string[] = [];
        if (ref.source) meta.push(ref.source);
        if (ref.url) meta.push(ref.url);
        if (ref.tickers && ref.tickers.length > 0) {
          meta.push(`Tickers: ${ref.tickers.join(', ')}`);
        }
        if (meta.length > 0) {
          parts.push(`(${meta.join(' • ')})`);
        }
        lines.push(parts.join(' '));
      });
    }
    return lines.join('\n');
  };

  const formatBriefRaw = (brief: DigestResponse | DigestBriefItem) => {
    const anyBrief = brief as any;
    const payload = {
      narrative: brief.narrative,
      what_to_watch: brief.what_to_watch,
      digest_date: brief.digest_date,
      priority_tickers: brief.priority_tickers,
      important_events: anyBrief?.important_events ?? null,
      user_note: anyBrief?.user_note ?? null,
      narrative_style: anyBrief?.narrative_style ?? null,
      user_focus_tickers: anyBrief?.user_focus_tickers ?? null,
      references: anyBrief?.references ?? null,
      metadata: anyBrief?.raw_metadata ?? null,
    };
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return String(payload);
    }
  };

  const tickerWidgetByTicker = new Map(widgets.map((w) => [w.ticker.toUpperCase(), w]));

  const renderBriefContentCard = (brief: DigestResponse | DigestBriefItem) => {
    const focusTickers = brief.priority_tickers ?? [];
    const importantEvents = brief.important_events ?? [];
    const spanLabel = brief.span_label && brief.span_label !== 'Daily' ? brief.span_label : 'Daily';
    const overviewLabel =
      spanLabel.toLowerCase().startsWith('week') || brief.span_type === 'weekly'
        ? "This week's overview"
        : "Today's overview";
    const anyBrief = brief as any;
    const focusSnapshot = (anyBrief?.focus_snapshot ?? anyBrief?.raw_metadata?.focus_snapshot) as
      | Record<string, { name?: string | null; price?: number | null; change_pct?: number | null; span_type?: string }>
      | undefined;

    return (
      <div className="mt-3 pt-3 border-t border-slate-800 space-y-4 text-base">
        <div>
          <div className="text-sm font-mono text-emerald-300 uppercase tracking-[0.18em] mb-1">
            {overviewLabel}
          </div>
          <div
            className="prose prose-invert prose-sm max-w-none text-slate-300 text-sm"
            style={{ fontFamily: 'Menlo, Monaco, "Courier New", monospace' }}
          >
            <ReactMarkdown components={briefMarkdownComponents}>
              {briefHasStructuredSections(brief.narrative) ? narrativeForDisplay(brief.narrative) : brief.narrative}
            </ReactMarkdown>
          </div>
        </div>

        {brief.what_to_watch && !briefHasStructuredSections(brief.narrative) && (
          <div className="pt-3 border-t border-slate-700/80 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-mono text-slate-300 uppercase tracking-[0.18em]">
                What to watch next
              </span>
            </div>
            <ReactMarkdown components={briefMarkdownComponents}>
              {brief.what_to_watch}
            </ReactMarkdown>
          </div>
        )}

        {focusTickers.length > 0 && (
          <div className="pt-3 border-t border-slate-700/80 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-mono font-semibold text-emerald-300 uppercase tracking-[0.18em]">
                Focus tickers
              </span>
            </div>
            <div className="space-y-1">
              {focusTickers.map((t) => {
                const upper = t.toUpperCase();
                const snap = focusSnapshot?.[upper] ?? focusSnapshot?.[t];
                const displayName = typeof snap?.name === 'string' && snap.name.trim() ? snap.name.trim() : null;
                const price = typeof snap?.price === 'number' ? snap.price : undefined;
                const change = typeof snap?.change_pct === 'number'
                  ? snap.change_pct
                  : tickerWidgetByTicker.get(upper)?.daily_change_percent;
                const changeStr =
                  typeof change === 'number'
                    ? `${change >= 0 ? '+' : ''}${change.toFixed(1)}%`
                    : null;
                const changeClass =
                  typeof change === 'number'
                    ? change >= 0
                      ? 'text-emerald-300'
                      : 'text-red-300'
                    : 'text-slate-400';
                return (
                  <div key={t} className="flex items-center justify-between text-sm text-slate-300">
                    <span className="mr-3">
                      {displayName ? `${displayName} (${t})` : t}
                    </span>
                    <span className="flex items-center gap-3">
                      {typeof price === 'number' && (
                        <span className="text-sm text-slate-400">${price.toFixed(2)}</span>
                      )}
                      {changeStr && <span className={changeClass}>{changeStr}</span>}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {importantEvents.length > 0 && (
          <div className="pt-3 border-t border-slate-700/80 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-mono font-semibold text-emerald-300 uppercase tracking-[0.18em]">
                Important events
              </span>
            </div>
            <div className="space-y-2">
              {importantEvents.map((item, idx) => {
                const metric = formatImportantEventMetric(item);
                const detectedOn = item.event.detected_on;
                return (
                  <div
                    key={`${item.ticker}-${item.event.event_type}-${idx}`}
                    className="flex items-start justify-between gap-3 rounded-lg border border-slate-700/80 bg-slate-950/50 px-3 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <div className="text-slate-100">
                        <span className="font-semibold text-emerald-200">{item.ticker}</span>
                        <span className="mx-2 text-slate-500">·</span>
                        <span>{formatImportantEventLabel(item.event.event_type)}</span>
                      </div>
                      <div className="mt-0.5 text-xs text-slate-400">
                        {item.event.strength}
                        {detectedOn ? ` · ${detectedOn}` : ''}
                      </div>
                      {item.event.description && (
                        <div className="mt-1 text-xs leading-5 text-slate-400 max-w-2xl">
                          {item.event.description}
                        </div>
                      )}
                    </div>
                    {metric && (
                      <span className="shrink-0 font-mono text-slate-300">
                        {metric}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  };

  const handleSendBriefEmail = async (executionId: number) => {
    setDigestError(null);
    setEmailBriefSendingId(executionId);
    try {
      await digestApi.sendBriefToEmail(executionId);
      setEmailBriefSentId(executionId);
      window.setTimeout(() => {
        setEmailBriefSentId((currentId) => (currentId === executionId ? null : currentId));
      }, 2000);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
    } finally {
      setEmailBriefSendingId((currentId) => (currentId === executionId ? null : currentId));
    }
  };

  const handleDeleteBrief = async () => {
    if (!selectedBrief || !selectedDigestDate) return;
    if (!window.confirm('Delete this brief? This cannot be undone.')) return;
    setDigestError(null);
    try {
      await digestApi.deleteBrief(selectedBrief.execution_id);
      const listRes = await digestApi.getDigestsForDate(selectedDigestDate, browserTimezone);
      setDigestBriefsForDay(listRes.briefs);
      setSelectedBrief(listRes.briefs[0] ?? null);
      const datesRes = await digestApi.getDigestDates(90, browserTimezone);
      setDigestDates(datesRes.dates);
      setDigestCountByDate(datesRes.count_by_date);
      if (listRes.briefs.length === 0) {
        setSelectedDigestDate(null);
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setDigestError(message);
    }
  };

  const handleCopyBrief = (brief: DigestResponse | DigestBriefItem) => {
    const text = formatBriefForClipboard(brief);
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopyBriefCopied(true);
        setTimeout(() => setCopyBriefCopied(false), 2000);
      }).catch(() => {});
    }
  };

  const handleCopyShareLink = (shareUrl: string) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(shareUrl);
      setShareLinkCopied(true);
      setTimeout(() => setShareLinkCopied(false), 2000);
    }
  };

  if (!user) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8 flex items-center justify-center">
        <div className="max-w-md text-center">
          <p className="text-gray-400 mb-6">Sign in to view and manage your briefs.</p>
          <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  const subscribedTickers = widgets.map((w) => w.ticker);
  const showEmptyDigestState =
    !digestLoading &&
    !digestError &&
    !digest &&
    (!selectedDigestDate || digestBriefsForDay.length === 0);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Briefing Desk" icon={<BriefIcon />} />

      <div className="px-4 pt-2 border-b border-gray-700 bg-gray-900 shrink-0">
        <div className="pb-2">
          <TickerSearch compact />
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 py-6 sm:p-6 lg:p-8">
          <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
            <div className="mb-6 overflow-hidden rounded-2xl border border-emerald-500/20 bg-slate-950 shadow-lg">
              <div className="grid gap-4 px-5 py-5 sm:px-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(360px,420px)] lg:items-start lg:px-7">
                <div className="min-w-0">
                  <p className="text-[11px] font-mono uppercase tracking-[0.24em] text-emerald-300/80">
                    FlowDeck AI Briefing
                  </p>
                  <h2 className="mt-2 max-w-4xl text-2xl font-semibold tracking-tight text-white sm:text-[1.9rem]">
                    Personalized market and portfolio briefs.
                  </h2>
                  <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
                    Get a concise daily or weekly read on the stories, signals, and holdings that matter most.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 lg:min-w-[360px]">
                  <div className="rounded-xl border border-slate-700/80 bg-slate-950/70 p-3.5">
                    <p className="text-xs font-mono uppercase tracking-[0.2em] text-emerald-300">Daily</p>
                    <p className="mt-1.5 text-sm leading-6 text-slate-300">
                      Market context and portfolio moves.
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-700/80 bg-slate-950/70 p-3.5">
                    <p className="text-xs font-mono uppercase tracking-[0.2em] text-emerald-300">Weekly</p>
                    <p className="mt-1.5 text-sm leading-6 text-slate-300">
                      Themes, follow-through, and next signals.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col lg:flex-row gap-6">
              <div className="lg:w-72 xl:w-80 shrink-0">
                <div className="bg-[#020617] rounded-xl border border-slate-700 overflow-hidden shadow-lg">
                  <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-700 bg-slate-950/80">
                    <span className="text-xs font-medium uppercase tracking-wider text-emerald-300">Briefs</span>
                    <button
                      type="button"
                      onClick={() => setNewBriefModalOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300/80 bg-emerald-400 px-3 py-1.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-300/70"
                      title="Create new brief"
                      aria-label="Create new brief"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                      </svg>
                      <span>New</span>
                    </button>
                  </div>

                  <div className="p-4 pt-3">
                    <div className="flex items-center justify-between mb-3">
                      <button
                        type="button"
                        onClick={goToPrevMonth}
                        className="p-1.5 text-emerald-200 hover:text-white hover:bg-slate-800 rounded"
                        aria-label="Previous month"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <span className="text-sm font-semibold text-emerald-100">
                        {calendarMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' })}
                      </span>
                      <button
                        type="button"
                        onClick={goToNextMonth}
                        className="p-1.5 text-emerald-200 hover:text-white hover:bg-slate-800 rounded"
                        aria-label="Next month"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                    <div className="grid grid-cols-7 gap-0.5 text-xs text-center text-slate-500 mb-1">
                      {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d) => (
                        <div key={d}>{d}</div>
                      ))}
                    </div>
                    <div className="grid grid-cols-7 gap-0.5 text-xs">
                      {(() => {
                        const year = calendarMonth.getFullYear();
                        const monthIndex = calendarMonth.getMonth();
                        const firstOfMonth = new Date(year, monthIndex, 1);
                        const startWeekday = firstOfMonth.getDay();
                        const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
                        const today = new Date();
                        const todayStr = formatDate(today.getFullYear(), today.getMonth(), today.getDate());
                        return (
                          <>
                            {Array.from({ length: startWeekday }).map((_, idx) => (
                              <div key={`b-${idx}`} />
                            ))}
                            {Array.from({ length: daysInMonth }).map((_, idx) => {
                              const day = idx + 1;
                              const dateStr = formatDate(year, monthIndex, day);
                              const hasDigest = digestDateSet.has(dateStr);
                              const count = digestCountByDate[dateStr] ?? 0;
                              const isSelected = selectedDigestDate === dateStr;
                              const isToday = dateStr === todayStr;
                              const isCreatingReport = digestLoading && isToday;
                              const baseClasses =
                                'h-8 relative flex items-center justify-center rounded cursor-pointer border text-xs font-mono';
                              const variant = hasDigest
                                ? isSelected
                                  ? 'bg-emerald-400 border-emerald-300 text-slate-950'
                                  : 'bg-slate-900/80 border-emerald-500/60 text-emerald-100 hover:bg-slate-800'
                                : 'bg-slate-900 border-slate-800 text-slate-500';
                              const loadingClasses = isCreatingReport ? 'animate-pulse ring-2 ring-emerald-400/50' : '';
                              return (
                                <button
                                  key={dateStr}
                                  type="button"
                                  className={`${baseClasses} ${variant} ${loadingClasses} min-w-0`}
                                  disabled={!hasDigest && !isCreatingReport}
                                  onClick={() => hasDigest && handleSelectDigestDate(dateStr)}
                                  title={
                                    isCreatingReport
                                      ? 'Creating new brief...'
                                      : hasDigest
                                      ? `${count} brief${count !== 1 ? 's' : ''} on ${dateStr}`
                                      : 'No brief for this day'
                                  }
                                >
                                  {isCreatingReport ? (
                                    <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                  ) : (
                                    day
                                  )}
                                  {hasDigest && count > 1 && !isCreatingReport && (
                                    <span className="absolute bottom-0 right-0.5 text-[9px] leading-none opacity-80">x{count}</span>
                                  )}
                                </button>
                              );
                            })}
                          </>
                        );
                      })()}
                    </div>
                    <p className="mt-2 text-xs text-slate-400">
                      Green = briefs. Click a day to view.
                    </p>
                    {weeklyDigestSlots.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-800">
                        <p className="text-xs font-medium text-slate-300 mb-1.5">Weekly briefs</p>
                        <div className="flex flex-wrap gap-1">
                          {weeklyDigestSlots.map((slot) => {
                            const endDate = slot.startsWith('w:') ? slot.slice(2) : slot;
                            const isSelected = selectedDigestDate === slot;
                            return (
                              <button
                                key={slot}
                                type="button"
                                onClick={() => handleSelectDigestDate(slot)}
                                className={`px-2 py-0.5 text-xs rounded border transition-colors font-mono ${
                                  isSelected
                                    ? 'bg-emerald-400 border-emerald-300 text-slate-950'
                                    : 'bg-slate-900 border-slate-700 text-slate-200 hover:bg-slate-800'
                                }`}
                                title={endDate}
                              >
                                Week {endDate}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {selectedDigestDate && digestBriefsForDay.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-800">
                        <p className="text-xs font-medium text-slate-300 mb-1.5">
                          {selectedDigestDate.startsWith('w:') ? 'This week' : 'This day'}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {digestBriefsForDay.map((brief, i) => (
                            <button
                              key={brief.execution_id}
                              type="button"
                              onClick={() => setSelectedBrief(brief)}
                              className={`px-2 py-0.5 text-xs rounded border transition-colors font-mono ${
                                selectedBrief?.execution_id === brief.execution_id
                                  ? 'bg-emerald-400 border-emerald-300 text-slate-950'
                                  : 'bg-slate-900 border-slate-700 text-slate-200 hover:bg-slate-800'
                              }`}
                              title={brief.created_at}
                            >
                              {formatBriefTime(brief.created_at) || `#${i + 1}`}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {newBriefModalOpen && (
                <div
                  className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
                  onClick={() => setNewBriefModalOpen(false)}
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="new-brief-modal-title"
                >
                  <div
                    className="bg-[#020617] border border-slate-700 rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="sticky top-0 flex justify-between items-center px-4 py-3 border-b border-slate-700 bg-slate-950 z-10">
                      <h2 id="new-brief-modal-title" className="text-base font-semibold text-emerald-100 tracking-wide">
                        Create new brief
                      </h2>
                      <button
                        type="button"
                        onClick={() => setNewBriefModalOpen(false)}
                        className="p-1.5 text-emerald-200 hover:text-white rounded-lg transition-colors"
                        aria-label="Close"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <div className="p-4">
                      <DailyDigestRunPanel
                        digestUserNote={digestUserNote}
                        onDigestUserNoteChange={setDigestUserNote}
                        digestNarrativeStyle={digestNarrativeStyle}
                        onDigestNarrativeStyleChange={setDigestNarrativeStyle}
                        digestSpan={digestSpan}
                        onDigestSpanChange={setDigestSpan}
                        digestInputExpanded={digestInputExpanded}
                        onDigestInputExpandedChange={setDigestInputExpanded}
                        selectedFocusTickers={selectedFocusTickers}
                        onSelectedFocusTickersChange={setSelectedFocusTickers}
                        subscribedTickers={subscribedTickers}
                        onRunDigest={() => {
                          handleRunDigest();
                          setNewBriefModalOpen(false);
                        }}
                        digestLoading={digestLoading}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div className={`flex-1 min-w-0 rounded-xl border border-slate-800 overflow-hidden shadow-lg ${showEmptyDigestState ? 'bg-transparent' : 'bg-black'}`}>
                <div className={`${digestLoading || showEmptyDigestState ? 'bg-transparent' : 'bg-slate-950'} min-h-[200px] px-4 sm:px-6 pt-3 sm:pt-4 pb-4 sm:pb-6 space-y-3`}>
                  {digestLoading && (
                    <div className="flex flex-col items-center justify-center min-h-[280px] py-12 px-4">
                      <div className="relative">
                        <div className="w-16 h-16 rounded-2xl border-2 border-emerald-400/40 bg-transparent flex items-center justify-center">
                          <svg className="w-8 h-8 text-emerald-300/90 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <span className="absolute -inset-1 rounded-2xl border border-emerald-400/30 animate-ping opacity-40" aria-hidden />
                      </div>
                      <p className="mt-5 text-base font-semibold text-emerald-50">Generating your brief</p>
                      <p className="mt-1 text-sm text-slate-400">Analyzing market and portfolio…</p>
                      <p className="mt-2 text-xs text-emerald-300/70 flex items-center justify-center gap-1.5">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        <span>An email will be sent when ready</span>
                      </p>
                      <div className="mt-6 w-48 h-1 rounded-full bg-slate-800 overflow-hidden">
                        <div className="h-full w-1/2 rounded-full bg-emerald-400 [animation:briefShimmer_1.8s_ease-in-out_infinite]" />
                      </div>
                      <style>{`@keyframes briefShimmer { 0%, 100% { transform: translateX(-100%); } 50% { transform: translateX(200%); } }`}</style>
                    </div>
                  )}

                  {digestError && <p className="text-sm text-red-400">{digestError}</p>}

                  {!digestLoading && selectedDigestDate && digestBriefsForDay.length > 0 && selectedBrief && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between gap-2 flex-nowrap">
                        <span className="text-xs sm:text-sm text-gray-500 whitespace-nowrap shrink-0">
                          <span className="font-mono text-sm text-emerald-300 uppercase tracking-wider">
                            {selectedBrief.span_label && selectedBrief.span_label !== 'Daily'
                              ? selectedBrief.span_label
                              : 'Daily'}
                          </span>
                          {selectedBrief.digest_date && (
                            <span className="ml-2 text-gray-300">{selectedBrief.digest_date}</span>
                          )}
                          {selectedBrief.created_at && (
                            <span className="ml-1.5 text-gray-500">· {formatBriefTime(selectedBrief.created_at)}</span>
                          )}
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleCopyBrief(selectedBrief)}
                            className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${copyBriefCopied ? 'border-emerald-500/70 text-emerald-400' : 'border-gray-500 text-gray-300'}`}
                            title={copyBriefCopied ? 'Copied!' : 'Copy brief'}
                            aria-label="Copy brief"
                          >
                            {copyBriefCopied ? (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                              </svg>
                            ) : (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                            )}
                          </button>
                          {selectedBrief.execution_id && (
                            <button
                              type="button"
                              onClick={() => handleSendBriefEmail(selectedBrief.execution_id)}
                              disabled={emailBriefSendingId === selectedBrief.execution_id}
                              className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${
                                emailBriefSentId === selectedBrief.execution_id
                                  ? 'border-emerald-500/70 text-emerald-400'
                                  : 'border-gray-500 text-gray-300'
                              } disabled:opacity-60 disabled:cursor-not-allowed`}
                              title={
                                emailBriefSendingId === selectedBrief.execution_id
                                  ? 'Sending email…'
                                  : emailBriefSentId === selectedBrief.execution_id
                                    ? 'Emailed!'
                                    : 'Email this brief to me'
                              }
                              aria-label={
                                emailBriefSendingId === selectedBrief.execution_id
                                  ? 'Sending email'
                                  : emailBriefSentId === selectedBrief.execution_id
                                    ? 'Emailed!'
                                    : 'Email this brief to me'
                              }
                            >
                              {emailBriefSendingId === selectedBrief.execution_id ? (
                                <SpinnerIcon />
                              ) : emailBriefSentId === selectedBrief.execution_id ? (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4h16v12H4z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4l8 6 8-6" />
                                </svg>
                              )}
                            </button>
                          )}
                          {selectedBrief.share_url && (
                            <button
                              type="button"
                              onClick={() => handleCopyShareLink(selectedBrief.share_url!)}
                              className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${shareLinkCopied ? 'border-emerald-500/70 text-emerald-400' : 'border-gray-500 text-gray-300'}`}
                              title={shareLinkCopied ? 'Link copied!' : 'Copy share link'}
                              aria-label="Copy share link"
                            >
                              {shareLinkCopied ? (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                                </svg>
                              )}
                            </button>
                          )}
                          {canViewRawDigest && (
                            <button
                              type="button"
                              onClick={() => setShowRawDigest((v) => !v)}
                              className="inline-flex items-center justify-center p-1.5 rounded border border-gray-500 text-gray-300 hover:bg-gray-800/80"
                              title={showRawDigest ? 'Hide raw' : 'Show raw'}
                              aria-label={showRawDigest ? 'Hide raw' : 'Show raw'}
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                              </svg>
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={handleDeleteBrief}
                            className="inline-flex items-center justify-center p-1.5 rounded border border-red-500/70 text-red-300 hover:bg-red-600/20"
                            title="Delete this brief"
                            aria-label="Delete this brief"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                      {renderBriefContentCard(selectedBrief)}
                      {(selectedBrief.user_note ||
                        selectedBrief.narrative_style ||
                        selectedBrief.user_focus_tickers?.length) && (
                        <div className="space-y-1 text-sm text-gray-300 bg-gray-900/60 border border-gray-700 rounded px-3 py-2">
                          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Run inputs</p>
                          {selectedBrief.narrative_style && (
                            <p><span className="text-gray-500 mr-1">Style:</span>{selectedBrief.narrative_style}</p>
                          )}
                          {selectedBrief.user_focus_tickers?.length ? (
                            <p><span className="text-gray-500 mr-1">User focus:</span>{selectedBrief.user_focus_tickers.join(', ')}</p>
                          ) : null}
                          {selectedBrief.user_note && (
                            <p><span className="text-gray-500 mr-1">User note:</span><span className="whitespace-pre-wrap align-top">{selectedBrief.user_note}</span></p>
                          )}
                        </div>
                      )}
                      {canViewRawDigest && showRawDigest && (
                        <div className="mt-2 rounded border border-gray-700 bg-black/50 p-2">
                          <pre className="text-xs whitespace-pre-wrap text-gray-200">
                            {formatBriefRaw(selectedBrief)}
                          </pre>
                        </div>
                      )}
                      {selectedBrief.references && selectedBrief.references.length > 0 && (
                        <div className="pt-3 border-t border-gray-700">
                          <button
                            type="button"
                            onClick={() => setShowReferences((v) => !v)}
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-white"
                          >
                            <svg
                              className={`w-3 h-3 transition-transform ${
                                showReferences ? 'rotate-90 text-emerald-300' : 'text-gray-400'
                              }`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                            <span>References</span>
                            <span className="text-xs text-gray-500">({selectedBrief.references.length})</span>
                          </button>
                          {showReferences && (
                            <ul className="mt-1.5 space-y-1.5 text-sm text-gray-300">
                              {selectedBrief.references.map((ref, idx) => (
                                <li key={idx} className="flex flex-col">
                                  <span className="font-medium">{ref.label}</span>
                                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                                    {ref.source && <span>{ref.source}</span>}
                                    {ref.url && (
                                      <a
                                        href={ref.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="underline underline-offset-2 text-emerald-300 hover:text-emerald-200"
                                      >
                                        Link
                                      </a>
                                    )}
                                    {ref.tickers && ref.tickers.length > 0 && (
                                      <span>Tickers: {ref.tickers.join(', ')}</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {!digestLoading && digest && (!selectedDigestDate || digestBriefsForDay.length === 0) && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between gap-2 flex-nowrap">
                        <span className="text-xs sm:text-sm text-gray-500 whitespace-nowrap shrink-0">
                          <span className="font-mono text-sm text-emerald-300 uppercase tracking-wider">
                            {digest.span_label && digest.span_label !== 'Daily' ? digest.span_label : 'Daily'}
                          </span>
                          {digest.digest_date && (
                            <span className="ml-2 text-gray-300">{digest.digest_date}</span>
                          )}
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleCopyBrief(digest)}
                            className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${copyBriefCopied ? 'border-emerald-500/70 text-emerald-400' : 'border-gray-500 text-gray-300'}`}
                            title={copyBriefCopied ? 'Copied!' : 'Copy brief'}
                            aria-label="Copy brief"
                          >
                            {copyBriefCopied ? (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                              </svg>
                            ) : (
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                            )}
                          </button>
                          {digest.execution_id != null && (
                            <button
                              type="button"
                              onClick={() => handleSendBriefEmail(digest.execution_id!)}
                              disabled={emailBriefSendingId === digest.execution_id}
                              className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${
                                emailBriefSentId === digest.execution_id
                                  ? 'border-emerald-500/70 text-emerald-400'
                                  : 'border-gray-500 text-gray-300'
                              } disabled:opacity-60 disabled:cursor-not-allowed`}
                              title={
                                emailBriefSendingId === digest.execution_id
                                  ? 'Sending email…'
                                  : emailBriefSentId === digest.execution_id
                                    ? 'Emailed!'
                                    : 'Email this brief to me'
                              }
                              aria-label={
                                emailBriefSendingId === digest.execution_id
                                  ? 'Sending email'
                                  : emailBriefSentId === digest.execution_id
                                    ? 'Emailed!'
                                    : 'Email this brief to me'
                              }
                            >
                              {emailBriefSendingId === digest.execution_id ? (
                                <SpinnerIcon />
                              ) : emailBriefSentId === digest.execution_id ? (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4h16v12H4z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4l8 6 8-6" />
                                </svg>
                              )}
                            </button>
                          )}
                          {digest.share_url && (
                            <button
                              type="button"
                              onClick={() => handleCopyShareLink(digest.share_url!)}
                              className={`inline-flex items-center justify-center p-1.5 rounded border hover:bg-gray-800/80 ${shareLinkCopied ? 'border-emerald-500/70 text-emerald-400' : 'border-gray-500 text-gray-300'}`}
                              title={shareLinkCopied ? 'Link copied!' : 'Copy share link'}
                              aria-label="Copy share link"
                            >
                              {shareLinkCopied ? (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                                </svg>
                              )}
                            </button>
                          )}
                          {canViewRawDigest && (
                            <button
                              type="button"
                              onClick={() => setShowRawDigest((v) => !v)}
                              className="inline-flex items-center justify-center p-1.5 rounded border border-gray-500 text-gray-300 hover:bg-gray-800/80"
                              title={showRawDigest ? 'Hide raw' : 'Show raw'}
                              aria-label={showRawDigest ? 'Hide raw' : 'Show raw'}
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                      {renderBriefContentCard(digest)}
                      {(digest.user_note || digest.narrative_style || digest.user_focus_tickers?.length) && (
                        <div className="space-y-1 text-sm text-gray-300 bg-gray-900/60 border border-gray-700 rounded px-3 py-2">
                          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Run inputs</p>
                          {digest.narrative_style && (
                            <p><span className="text-gray-500 mr-1">Style:</span>{digest.narrative_style}</p>
                          )}
                          {digest.user_focus_tickers?.length ? (
                            <p><span className="text-gray-500 mr-1">User focus:</span>{digest.user_focus_tickers.join(', ')}</p>
                          ) : null}
                          {digest.user_note && (
                            <p><span className="text-gray-500 mr-1">User note:</span><span className="whitespace-pre-wrap align-top">{digest.user_note}</span></p>
                          )}
                        </div>
                      )}
                      {canViewRawDigest && showRawDigest && (
                        <div className="mt-2 rounded border border-gray-700 bg-black/50 p-2">
                          <pre className="text-xs whitespace-pre-wrap text-gray-200">
                            {formatBriefRaw(digest)}
                          </pre>
                        </div>
                      )}
                      {digest.what_to_watch && !briefHasStructuredSections(digest.narrative) && (
                        <div className="pt-3 border-t border-gray-700 space-y-2">
                          <div>
                            <h3 className="text-sm font-semibold text-white mb-1">What to watch</h3>
                            <p className="text-gray-200 text-sm whitespace-pre-wrap leading-relaxed">
                              {digest.what_to_watch}
                            </p>
                          </div>
                        </div>
                      )}
                      {digest.references && digest.references.length > 0 && (
                        <div className="pt-3 border-t border-gray-700">
                          <button
                            type="button"
                            onClick={() => setShowReferences((v) => !v)}
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-white"
                          >
                            <svg
                              className={`w-3 h-3 transition-transform ${
                                showReferences ? 'rotate-90 text-emerald-300' : 'text-gray-400'
                              }`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                            <span>References</span>
                            <span className="text-xs text-gray-500">({digest.references.length})</span>
                          </button>
                          {showReferences && (
                            <ul className="mt-1.5 space-y-1.5 text-sm text-gray-300">
                              {digest.references.map((ref, idx) => (
                                <li key={idx} className="flex flex-col">
                                  <span className="font-medium">{ref.label}</span>
                                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                                    {ref.source && <span>{ref.source}</span>}
                                    {ref.url && (
                                      <a
                                        href={ref.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="underline underline-offset-2 text-emerald-300 hover:text-emerald-200"
                                      >
                                        Link
                                      </a>
                                    )}
                                    {ref.tickers && ref.tickers.length > 0 && (
                                      <span>Tickers: {ref.tickers.join(', ')}</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {showEmptyDigestState && (
                      <p className="text-sm text-gray-400">
                        Click &ldquo;Create brief&rdquo; to generate today&apos;s summary, or select a highlighted day in
                        the calendar to view that day&apos;s briefs.
                      </p>
                    )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
