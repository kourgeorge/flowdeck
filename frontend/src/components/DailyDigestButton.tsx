import { useState } from 'react';
import { digestApi, type DigestResponse } from '../services/api';

export default function DailyDigestButton() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [digest, setDigest] = useState<DigestResponse | null>(null);

  const handleFetch = async () => {
    setError(null);
    setDigest(null);
    setLoading(true);
    setOpen(true);
    try {
      const data = await digestApi.getDigest();
      setDigest(data);
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
              <h2 id="digest-modal-title" className="text-lg font-semibold text-white">
                User Daily Brief
              </h2>
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
                    <p className="text-xs text-gray-500">
                      {digest.digest_date}
                      {digest.priority_tickers?.length > 0 && (
                        <span className="ml-2">· Focus: {digest.priority_tickers.join(', ')}</span>
                      )}
                    </p>
                  )}
                  <div className="prose prose-invert prose-sm max-w-none">
                    <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {digest.narrative}
                    </p>
                  </div>
                  {digest.what_to_watch && (
                    <div className="pt-3 border-t border-gray-600">
                      <h3 className="text-sm font-semibold text-white mb-1">What to watch</h3>
                      <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">
                        {digest.what_to_watch}
                      </p>
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
