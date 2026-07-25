import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { tickerApi } from '../services/api';

interface FilingRef {
  form: string;
  filing_date: string;
  accession_number: string;
  url?: string;
}

interface SecFilingModalProps {
  ticker: string;
  filing: FilingRef;
  onClose: () => void;
}

// sec2md emits image/link URLs relative to the filing's archive directory on
// sec.gov (e.g. "aapl-20260328_g1.jpg"). Resolve them against the filing URL so
// images display and internal links work instead of pointing at our own origin.
function resolveUrl(src: string | undefined, base: string | undefined): string | undefined {
  if (!src || !base) return src;
  try {
    return new URL(src, base).href;
  } catch {
    return src;
  }
}

// Shared markdown component overrides (matches ReportViewer styling), tuned for
// the dense tables that SEC filings (via sec2md) contain. `baseUrl` resolves
// relative image/link paths.
const buildMarkdownComponents = (baseUrl?: string) => ({
  h1: ({ node, ...props }: any) => <h1 className="text-2xl font-bold text-white mb-4 mt-6" {...props} />,
  h2: ({ node, ...props }: any) => <h2 className="text-xl font-semibold text-white mb-3 mt-6" {...props} />,
  h3: ({ node, ...props }: any) => <h3 className="text-lg font-semibold text-white mb-2 mt-4" {...props} />,
  p: ({ node, ...props }: any) => <p className="text-slate-300 mb-4 leading-relaxed" {...props} />,
  ul: ({ node, ...props }: any) => <ul className="list-disc list-inside text-slate-300 mb-4 space-y-1" {...props} />,
  ol: ({ node, ...props }: any) => <ol className="list-decimal list-outside pl-6 text-slate-300 mb-4 space-y-1" {...props} />,
  li: ({ node, ...props }: any) => <li className="text-slate-300" {...props} />,
  strong: ({ node, ...props }: any) => <strong className="font-semibold text-white" {...props} />,
  a: ({ node, href, ...props }: any) => <a href={resolveUrl(href, baseUrl)} className="text-blue-400 hover:text-blue-300 underline" target="_blank" rel="noopener noreferrer" {...props} />,
  img: ({ node, src, alt, ...props }: any) => <img src={resolveUrl(src, baseUrl)} alt={alt ?? ''} className="max-w-full h-auto my-4 rounded bg-white" loading="lazy" {...props} />,
  code: ({ node, ...props }: any) => <code className="bg-slate-900 px-1.5 py-0.5 rounded text-sm text-green-400" {...props} />,
  pre: ({ node, ...props }: any) => <pre className="bg-slate-900 p-4 rounded-lg overflow-x-auto mb-4" {...props} />,
  table: ({ node, ...props }: any) => (
    <div className="overflow-x-auto my-4 rounded-lg border border-slate-600">
      <table className="min-w-full border-collapse text-sm" {...props} />
    </div>
  ),
  thead: ({ node, ...props }: any) => <thead className="bg-slate-700/80 text-slate-200" {...props} />,
  tbody: ({ node, ...props }: any) => <tbody className="divide-y divide-slate-600" {...props} />,
  tr: ({ node, ...props }: any) => <tr className="hover:bg-slate-700/40 transition-colors" {...props} />,
  th: ({ node, ...props }: any) => <th className="px-3 py-2 text-left font-semibold text-white border-b border-slate-600 whitespace-nowrap" {...props} />,
  td: ({ node, ...props }: any) => <td className="px-3 py-2 text-slate-300" {...props} />,
});

export default function SecFilingModal({ ticker, filing, onClose }: SecFilingModalProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleCopy = async () => {
    if (!content) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        // Fallback for non-secure contexts / older browsers.
        const ta = document.createElement('textarea');
        ta.value = content;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked — leave the button state unchanged.
    }
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setContent(null);
    tickerApi
      .getEdgarFilingContent(ticker, filing.accession_number)
      .then((data) => {
        if (cancelled) return;
        if (data.error) {
          setError(data.error);
          return;
        }
        const doc = data.filings?.[0];
        if (!doc || !doc.text) {
          setError('This filing could not be rendered as text.');
          return;
        }
        setContent(doc.text);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(typeof msg === 'string' ? msg : 'Failed to load filing content.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, filing.accession_number]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 border border-gray-700 rounded-xl shadow-xl w-full max-w-4xl h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-4 border-b border-gray-700 px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-white">
              {ticker.toUpperCase()} · {filing.form}
            </h2>
            <p className="text-xs text-gray-400 truncate">
              Filed {filing.filing_date} · Accession {filing.accession_number}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={handleCopy}
              disabled={!content}
              className="text-sm px-2.5 py-1 rounded border border-gray-600 text-gray-200 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Copy the filing as Markdown"
            >
              {copied ? 'Copied!' : 'Copy .md'}
            </button>
            {filing.url && (
              <a
                href={filing.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-400 hover:text-blue-300 underline"
              >
                View on SEC.gov
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors p-1"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-6 bg-gray-700 rounded w-1/3" />
              <div className="h-4 bg-gray-700 rounded w-full" />
              <div className="h-4 bg-gray-700 rounded w-5/6" />
              <div className="h-4 bg-gray-700 rounded w-4/6" />
              <div className="h-40 bg-gray-700 rounded w-full mt-4" />
            </div>
          ) : error ? (
            <p className="text-amber-400 text-sm">{error}</p>
          ) : content ? (
            <div className="prose prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={buildMarkdownComponents(filing.url)}>
                {content}
              </ReactMarkdown>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
