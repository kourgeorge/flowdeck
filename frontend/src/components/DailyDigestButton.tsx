import { useState } from 'react';
import { digestApi, type DigestResponse } from '../services/api';

export default function DailyDigestButton() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [userNote, setUserNote] = useState<string>('');
  const [narrativeStyle, setNarrativeStyle] = useState<'default' | 'concise' | 'professional' | 'technical'>('default');
  const [showOptions, setShowOptions] = useState<boolean>(false);
  const [showReferences, setShowReferences] = useState<boolean>(false);

  const formatBriefForClipboard = (brief: DigestResponse) => {
    const lines: string[] = [];
    if (brief.digest_date) {
      lines.push(`User Daily Brief – ${brief.digest_date}`);
    } else {
      lines.push('User Daily Brief');
    }
    if (brief.priority_tickers && brief.priority_tickers.length > 0) {
      lines.push(`Focus: ${brief.priority_tickers.join(', ')}`);
    }
    lines.push('');
    lines.push(brief.narrative.trim());
    if (brief.what_to_watch) {
      lines.push('');
      lines.push('What to watch');
      lines.push(brief.what_to_watch.trim());
    }
    return lines.join('\n');
  };

  const handleCopy = () => {
    if (!digest) return;
    const text = formatBriefForClipboard(digest);
    if (navigator && 'clipboard' in navigator && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => {
        // best-effort; ignore copy failures
      });
    }
  };

  const handleFetch = async () => {
    setError(null);
    setDigest(null);
    setLoading(true);
    setOpen(true);
    try {
      const trimmedNote = userNote.trim();
      const styleParam = narrativeStyle === 'default' ? undefined : narrativeStyle;
      const params: { user_note?: string; narrative_style?: string } = {};
      if (trimmedNote) params.user_note = trimmedNote;
      if (styleParam) params.narrative_style = styleParam;
      const data = await digestApi.getDigest(
        Object.keys(params).length ? params : undefined,
      );
      setDigest(data);
      if (trimmedNote) {
        setUserNote('');
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={handleFetch}
        disabled={loading}
        className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-gray-900"
      >
        {loading ? (
          <>
            <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" aria-hidden />
            Generating…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Get User Daily Brief
          </>
        )}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60"
          role="dialog"
          aria-modal="true"
          aria-labelledby="digest-modal-title"
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div
            className="bg-gray-800 border border-gray-600 rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-600">
              <div className="flex items-center gap-3">
                <h2 id="digest-modal-title" className="text-lg font-semibold text-white">
                  User Daily Brief
                </h2>
                {digest && !loading && (
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded border border-emerald-500 text-emerald-300 hover:bg-emerald-600/10"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                    Copy brief
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Close"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <p className="text-[11px] text-gray-300 font-medium">
                    Brief options
                  </p>
                  <p className="text-[10px] text-gray-500">
                    Choose style and add an optional note for this run.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowOptions((v) => !v)}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors ${
                    showOptions
                      ? 'border-emerald-400/70 text-emerald-200 bg-emerald-900/40'
                      : 'border-gray-600 text-gray-300 bg-gray-800/70 hover:border-emerald-400/80 hover:text-emerald-200'
                  }`}
                >
                  <svg
                    className={`w-3 h-3 transition-transform ${showOptions ? 'rotate-90 text-emerald-300' : 'text-gray-400'}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  <span>{showOptions ? 'Hide options' : 'Show options'}</span>
                </button>
              </div>
              {showOptions && (
                <div className="space-y-2 border border-gray-700/80 rounded-md bg-gray-900/70 px-3 py-2.5">
                  <div className="space-y-1">
                    <label htmlFor="digest-style-inline" className="block text-xs font-medium text-gray-200">
                      Brief style
                    </label>
                    <select
                      id="digest-style-inline"
                      value={narrativeStyle}
                      onChange={(e) => setNarrativeStyle(e.target.value as any)}
                      className="w-full max-w-xs rounded-md border border-gray-700 bg-gray-950/70 px-2.5 py-1.5 text-xs text-gray-100 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                    >
                      <option value="default">Balanced (default)</option>
                      <option value="concise">Concise</option>
                      <option value="professional">Professional</option>
                      <option value="technical">Technical (more detail)</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label htmlFor="digest-user-note-inline" className="block text-xs font-medium text-gray-200">
                      Optional note for today&apos;s brief
                    </label>
                    <textarea
                      id="digest-user-note-inline"
                      rows={2}
                      value={userNote}
                      onChange={(e) => setUserNote(e.target.value)}
                      maxLength={2000}
                      placeholder="E.g. Focus on upcoming earnings, concerns about sector risk, cash needs…"
                      className="w-full rounded-md border border-gray-700 bg-gray-950/70 px-2.5 py-1.5 text-xs text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 resize-none"
                    />
                  </div>
                </div>
              )}
              {loading && (
                <div className="flex items-center justify-center py-12 text-gray-400">
                  <span className="inline-block w-8 h-8 border-2 border-gray-500 border-t-blue-400 rounded-full animate-spin mr-2" />
                  Building your brief…
                </div>
              )}
              {error && (
                <p className="text-red-400 text-sm">{error}</p>
              )}
              {!loading && digest && (
                <>
                  {digest.digest_date && (
                    <div className="space-y-1">
                      <p className="text-xs text-gray-500">
                        {digest.digest_date}
                      </p>
                      {digest.priority_tickers?.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] uppercase tracking-wide text-gray-500">
                            Focus
                          </span>
                          {digest.priority_tickers.map((t) => (
                            <span
                              key={t}
                              className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-900/40 border border-emerald-600/60 text-[11px] text-emerald-100"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="prose prose-invert prose-sm max-w-none">
                    <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {digest.narrative}
                    </p>
                  </div>
                  {digest.what_to_watch && (
                    <div className="pt-3 border-t border-gray-600 space-y-2">
                      <div>
                        <h3 className="text-sm font-semibold text-white mb-1">What to watch</h3>
                        <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">
                          {digest.what_to_watch}
                        </p>
                      </div>
                      {digest.references && digest.references.length > 0 && (
                        <div className="pt-2 border-t border-gray-700">
                          <button
                            type="button"
                            onClick={() => setShowReferences((v) => !v)}
                            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-300 hover:text-white"
                          >
                            <svg
                              className={`w-3 h-3 transition-transform ${showReferences ? 'rotate-90 text-emerald-300' : 'text-gray-400'}`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                            <span>References</span>
                            <span className="text-[10px] text-gray-500">
                              ({digest.references.length})
                            </span>
                          </button>
                          {showReferences && (
                            <ul className="mt-1.5 space-y-1.5 text-[11px] text-gray-300">
                              {digest.references.map((ref, idx) => (
                                <li key={idx} className="flex flex-col">
                                  <span className="font-medium">{ref.label}</span>
                                  <div className="flex flex-wrap gap-2 text-[10px] text-gray-500">
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
                                      <span>
                                        Tickers: {ref.tickers.join(', ')}
                                      </span>
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
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
