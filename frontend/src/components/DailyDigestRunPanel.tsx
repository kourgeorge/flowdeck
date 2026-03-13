/**
 * Panel with User Daily Brief title, collapsible brief options (style, note, focus tickers), and Run digest button.
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

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-white mb-1">User Daily Brief (beta)</h2>
        <p className="text-xs text-gray-400">
          Generate a short narrative summary of {digestSpan === 'weekly' ? 'the past week\'s' : 'today\'s'} market and your subscribed tickers.
        </p>
      </div>

      <div className="flex items-center gap-3" ref={spanRef}>
        <label htmlFor="digest-span" className="text-sm font-medium text-gray-300">
          Time span
        </label>
        <div className="relative">
          <button
            type="button"
            id="digest-span"
            onClick={() => { setSpanOpen((o) => !o); setStyleOpen(false); }}
            className="min-w-[7rem] flex items-center justify-between gap-2 rounded-lg border border-gray-600 bg-gray-900/80 py-2 px-3 text-sm text-gray-100 shadow-sm transition-colors hover:border-gray-500 hover:bg-gray-800/80 focus:outline-none focus:ring-2 focus:ring-emerald-500/60 focus:border-emerald-500/70"
          >
            <span>{spanOptions.find((o) => o.value === digestSpan)?.label ?? digestSpan}</span>
            <svg className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${spanOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {spanOpen && (
            <div className="absolute top-full left-0 z-10 mt-1 w-full rounded-lg border border-gray-600 bg-gray-900 shadow-xl py-1 min-w-[7rem]">
              {spanOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { onDigestSpanChange(opt.value); setSpanOpen(false); }}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    opt.value === digestSpan
                      ? 'bg-emerald-900/50 text-emerald-100 font-medium'
                      : 'text-gray-200 hover:bg-gray-700/80'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="border border-gray-700/80 rounded-md bg-gray-900/60 overflow-hidden">
        <button
          type="button"
          onClick={() => onDigestInputExpandedChange(!digestInputExpanded)}
          className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-[11px] font-medium text-gray-300 hover:text-white hover:bg-gray-800/60 transition-colors"
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
              <label htmlFor="digest-style" className="block text-sm font-medium text-gray-300">
                Brief style
              </label>
              <div className="relative w-full max-w-xs">
                <button
                  type="button"
                  id="digest-style"
                  onClick={() => { setStyleOpen((o) => !o); setSpanOpen(false); }}
                  className="w-full flex items-center justify-between gap-2 rounded-lg border border-gray-600 bg-gray-900/80 py-2.5 pl-3 pr-3 text-sm text-gray-100 shadow-sm transition-colors hover:border-gray-500 hover:bg-gray-800/80 focus:outline-none focus:ring-2 focus:ring-emerald-500/60 focus:border-emerald-500/70"
                >
                  <span>{styleOptions.find((o) => o.value === digestNarrativeStyle)?.label ?? digestNarrativeStyle}</span>
                  <svg className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${styleOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {styleOpen && (
                  <div className="absolute top-full left-0 z-10 mt-1 w-full rounded-lg border border-gray-600 bg-gray-900 shadow-xl py-1 max-w-xs">
                    {styleOptions.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => { onDigestNarrativeStyleChange(opt.value); setStyleOpen(false); }}
                        className={`w-full text-left px-3 py-2 text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                          opt.value === digestNarrativeStyle
                            ? 'bg-emerald-900/50 text-emerald-100 font-medium'
                            : 'text-gray-200 hover:bg-gray-700/80'
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
              <label htmlFor="digest-user-note" className="block text-[11px] font-medium text-gray-300">
                Optional note for today&apos;s brief
              </label>
              <textarea
                id="digest-user-note"
                rows={2}
                value={digestUserNote}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onDigestUserNoteChange(e.target.value)}
                maxLength={2000}
                placeholder="E.g. Focus on earnings next week, I'm worried about tech exposure, cash needs in 3 months…"
                className="w-full rounded-md border border-gray-700 bg-gray-950/60 px-2.5 py-1.5 text-xs text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 resize-none"
              />
              <p className="text-[10px] text-gray-500">
                Style and note apply only to the next run and are considered when writing the narrative and
                &quot;What to watch&quot;.
              </p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-[11px] font-medium text-gray-300">
                  Focus tickers (optional)
                </label>
                {selectedFocusTickers.length > 0 && (
                  <button
                    type="button"
                    onClick={() => onSelectedFocusTickersChange([])}
                    className="text-[10px] text-emerald-300 hover:text-emerald-200 underline-offset-2 hover:underline"
                  >
                    Clear
                  </button>
                )}
              </div>
              <p className="text-[10px] text-gray-500 mb-0.5">
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
                      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] transition-colors ${
                        selected
                          ? 'bg-emerald-900/50 border-emerald-500 text-emerald-100'
                          : 'bg-gray-900 border-gray-700 text-gray-300 hover:border-emerald-500 hover:text-emerald-100'
                      }`}
                    >
                      {t}
                    </button>
                  );
                })}
                {subscribedTickers.length === 0 && (
                  <span className="text-[10px] text-gray-500">
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
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-gray-900"
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
      </div>
    </div>
  );
}
