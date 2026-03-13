/**
 * Panel with User Daily Brief title, collapsible brief options (style, note, focus tickers), and Run digest button.
 * Rendered above the Brief history panel on the digest tab.
 */
import type { ChangeEvent } from 'react';

export type DigestNarrativeStyle = 'default' | 'concise' | 'professional' | 'technical';

export interface DailyDigestRunPanelProps {
  digestUserNote: string;
  onDigestUserNoteChange: (value: string) => void;
  digestNarrativeStyle: DigestNarrativeStyle;
  onDigestNarrativeStyleChange: (value: DigestNarrativeStyle) => void;
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
  digestInputExpanded,
  onDigestInputExpandedChange,
  selectedFocusTickers,
  onSelectedFocusTickersChange,
  subscribedTickers,
  onRunDigest,
  digestLoading,
}: DailyDigestRunPanelProps) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-white mb-1">User Daily Brief (beta)</h2>
        <p className="text-xs text-gray-400">
          Generate a short narrative summary of today&apos;s market and your subscribed tickers.
        </p>
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
            <div className="space-y-1">
              <label htmlFor="digest-style" className="block text-[11px] font-medium text-gray-300">
                Brief style
              </label>
              <div className="relative w-full max-w-xs">
                <select
                  id="digest-style"
                  value={digestNarrativeStyle}
                  onChange={(e) => onDigestNarrativeStyleChange(e.target.value as DigestNarrativeStyle)}
                  className="w-full appearance-none rounded-lg border border-gray-600 bg-gray-800/80 py-2.5 pl-3 pr-9 text-sm text-gray-100 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500/60 focus:border-emerald-500/70 hover:border-gray-500"
                >
                  <option value="default">Balanced (default)</option>
                  <option value="concise">Concise</option>
                  <option value="professional">Professional</option>
                  <option value="technical">Technical (more detail)</option>
                </select>
                <svg
                  className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
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
