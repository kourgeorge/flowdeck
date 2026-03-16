/**
 * Panel with Briefing title, collapsible brief options (style, note, focus tickers), and Run digest button.
 * Rendered above the Brief history panel on the digest tab.
 */
import { type ChangeEvent, useState, useRef, useEffect } from 'react';

export type DigestNarrativeStyle = 'default' | 'concise' | 'professional' | 'technical';
export type DigestSpan = 'daily' | 'weekly';

export interface DailyDigestRunPanelProps {
  digestUserNote: string;
  onDigestUserNoteChange: (value: string) => void;
  digestNarrativeStyle: DigestNarrativeStyle;
  onDigestNarrativeStyleChange: (value: DigestNarrativeStyle) => void;
  digestSpan: DigestSpan;
  onDigestSpanChange: (value: DigestSpan) => void;
  digestInputExpanded: boolean;
  onDigestInputExpandedChange: (value: boolean) => void;
  selectedFocusTickers: string[];
  onSelectedFocusTickersChange: (tickers: string[]) => void;
  subscribedTickers: string[];
  onRunDigest: () => void;
  digestLoading: boolean;
}

export default function DailyDigestRunPanel({
  digestUserNote,
  onDigestUserNoteChange,
  digestNarrativeStyle,
  onDigestNarrativeStyleChange,
  digestSpan,
  onDigestSpanChange,
  digestInputExpanded,
  onDigestInputExpandedChange,
  selectedFocusTickers,
  onSelectedFocusTickersChange,
  subscribedTickers,
  onRunDigest,
  digestLoading,
}: DailyDigestRunPanelProps) {
  const [spanOpen, setSpanOpen] = useState(false);
  const [styleOpen, setStyleOpen] = useState(false);
  const spanRef = useRef<HTMLDivElement>(null);
  const styleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (spanRef.current && !spanRef.current.contains(target)) setSpanOpen(false);
      if (styleRef.current && !styleRef.current.contains(target)) setStyleOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const spanOptions: { value: DigestSpan; label: string }[] = [
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
  ];
  const styleOptions: { value: DigestNarrativeStyle; label: string }[] = [
    { value: 'default', label: 'Balanced (default)' },
    { value: 'concise', label: 'Concise' },
    { value: 'professional', label: 'Professional' },
    { value: 'technical', label: 'Technical (more detail)' },
  ];

  const spanLabel = digestSpan === 'weekly' ? 'Weekly' : 'Daily';

  return (
    <div className="bg-[#020617] rounded-xl border border-slate-700 p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-emerald-100 mb-1 flex items-center justify-between">
          <span>Briefing</span>
          <span className="text-[11px] font-mono text-emerald-300 uppercase tracking-widest">
            {spanLabel}
          </span>
        </h2>
        <p className="text-xs text-slate-400">
          Generate a short narrative summary of {digestSpan === 'weekly' ? "the past week's" : "today's"} market and your subscribed tickers.
        </p>
      </div>

      <div className="flex items-center gap-3" ref={spanRef}>
        <label htmlFor="digest-span" className="text-sm font-medium text-emerald-100">
          Time span
        </label>
        <div className="relative">
          <button
            type="button"
            id="digest-span"
            onClick={() => { setSpanOpen((o) => !o); setStyleOpen(false); }}
            className="min-w-[7rem] flex items-center justify-between gap-2 rounded-lg border border-slate-600 bg-slate-950/80 py-2 px-3 text-sm text-slate-50 shadow-sm transition-colors hover:border-emerald-500 hover:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/70 focus:border-emerald-400"
          >
            <span>{spanOptions.find((o) => o.value === digestSpan)?.label ?? digestSpan}</span>
            <svg className={`w-4 h-4 text-emerald-300 shrink-0 transition-transform ${spanOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {spanOpen && (
            <div className="absolute top-full left-0 z-10 mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 shadow-xl py-1 min-w-[7rem]">
              {spanOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { onDigestSpanChange(opt.value); setSpanOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    opt.value === digestSpan
                      ? 'bg-emerald-500/15 text-emerald-100 font-medium'
                      : 'text-slate-100 hover:bg-slate-800/80'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="border border-slate-700 rounded-md bg-slate-950/60 overflow-hidden">
        <button
          type="button"
          onClick={() => onDigestInputExpandedChange(!digestInputExpanded)}
          className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm font-medium text-slate-100 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <span>Brief options</span>
          <svg
            className={`w-3.5 h-3.5 transition-transform ${digestInputExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {digestInputExpanded && (
          <div className="space-y-3 px-3 pb-3 pt-0">
            <div className="space-y-1" ref={styleRef}>
              <label htmlFor="digest-style" className="block text-sm font-medium text-emerald-100">
                Brief style
              </label>
              <div className="relative w-full max-w-xs">
                <button
                  type="button"
                  id="digest-style"
                  onClick={() => { setStyleOpen((o) => !o); setSpanOpen(false); }}
                  className="w-full flex items-center justify-between gap-2 rounded-lg border border-slate-600 bg-slate-950/80 py-2.5 pl-3 pr-3 text-sm text-slate-50 shadow-sm transition-colors hover:border-emerald-500 hover:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/70 focus:border-emerald-400"
                >
                  <span>{styleOptions.find((o) => o.value === digestNarrativeStyle)?.label ?? digestNarrativeStyle}</span>
                  <svg className={`w-4 h-4 text-emerald-300 shrink-0 transition-transform ${styleOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {styleOpen && (
                  <div className="absolute top-full left-0 z-10 mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 shadow-xl py-1 max-w-xs">
                    {styleOptions.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => { onDigestNarrativeStyleChange(opt.value); setStyleOpen(false); }}
                        className={`w-full text-left px-3 py-2 text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                          opt.value === digestNarrativeStyle
                            ? 'bg-emerald-500/15 text-emerald-100 font-medium'
                            : 'text-slate-100 hover:bg-slate-800/80'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-1">
              <label htmlFor="digest-user-note" className="block text-sm font-medium text-emerald-100">
                Optional note for this brief
              </label>
              <textarea
                id="digest-user-note"
                rows={2}
                value={digestUserNote}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onDigestUserNoteChange(e.target.value)}
                maxLength={2000}
                placeholder="E.g. Focus on earnings next week, I'm worried about tech exposure, cash needs in 3 months…"
                className="w-full rounded-md border border-slate-700 bg-slate-950/60 px-2.5 py-1.5 text-xs text-slate-50 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-400 resize-none"
              />
              <p className="text-sm text-slate-500">
                Style and note apply only to the next run and are considered when writing the narrative and
                &quot;What to watch&quot;.
              </p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-emerald-100">
                  Focus tickers (optional)
                </label>
                {selectedFocusTickers.length > 0 && (
                  <button
                    type="button"
                    onClick={() => onSelectedFocusTickersChange([])}
                    className="text-xs text-emerald-300 hover:text-emerald-200 underline-offset-2 hover:underline"
                  >
                    Clear
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-500 mb-0.5">
                Choose a subset of your portfolio to highlight. Leave empty to let the system pick based on
                moves and news.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {subscribedTickers.map((t) => {
                  const selected = selectedFocusTickers.includes(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => {
                        onSelectedFocusTickersChange(
                          selected ? selectedFocusTickers.filter((x) => x !== t) : [...selectedFocusTickers, t],
                        );
                      }}
                      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-xs transition-colors ${
                        selected
                          ? 'bg-emerald-500/15 border-emerald-400 text-emerald-100'
                          : 'bg-slate-950 border-slate-700 text-slate-200 hover:border-emerald-400 hover:text-emerald-100'
                      }`}
                    >
                      {t}
                    </button>
                  );
                })}
                {subscribedTickers.length === 0 && (
                  <span className="text-xs text-slate-500">
                    Subscribe to tickers on your dashboard to choose a manual focus set.
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div>
        <button
          type="button"
          onClick={onRunDigest}
          disabled={digestLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-950 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-60 disabled:cursor-not-allowed rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-950"
        >
          {digestLoading ? (
            <>
              <span
                className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"
                aria-hidden
              />
              Building…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Run digest
            </>
          )}
        </button>
        <p className="mt-1 text-[11px] text-slate-400">
          Each brief (daily or weekly) costs <span className="font-semibold text-emerald-200">20 DECK tokens</span>.
        </p>
      </div>
    </div>
  );
}
