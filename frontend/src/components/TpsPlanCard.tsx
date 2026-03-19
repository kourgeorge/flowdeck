import { useState } from 'react';

interface TpsPlanCardProps {
  tpsPlan: string;
  title?: string;
}

function formatTpsPlan(tpsPlan: string): string {
  try {
    return JSON.stringify(JSON.parse(tpsPlan), null, 2);
  } catch {
    return tpsPlan;
  }
}

export default function TpsPlanCard({ tpsPlan, title = 'TPS v0.1' }: TpsPlanCardProps) {
  const [copied, setCopied] = useState(false);
  const displayText = formatTpsPlan(tpsPlan);

  const handleCopy = () => {
    if (!navigator?.clipboard?.writeText) return;
    navigator.clipboard.writeText(displayText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  };

  return (
    <div className="rounded-lg border border-indigo-700/60 bg-indigo-950/30 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-indigo-700/40 bg-indigo-900/30">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-indigo-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span className="text-xs font-semibold uppercase tracking-widest text-indigo-300">
            {title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-indigo-500 font-mono">JSON</span>
          <button
            type="button"
            onClick={handleCopy}
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
              copied
                ? 'border-emerald-500/70 bg-emerald-500/10 text-emerald-300'
                : 'border-indigo-500/40 text-indigo-200 hover:bg-indigo-500/10'
            }`}
            title={copied ? 'Copied!' : 'Copy JSON plan'}
            aria-label="Copy JSON plan"
          >
            {copied ? (
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
            <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
          </button>
        </div>
      </div>
      <div className="p-4">
        <pre className="bg-slate-900 rounded-lg p-4 overflow-x-auto text-sm font-mono leading-relaxed whitespace-pre">
          {displayText.split('\n').map((line, i) => {
            const keyMatch = line.match(/^(\s*)("[\w_]+")(\s*:\s*)(.*)$/);
            if (keyMatch) {
              const [, indent, key, colon, val] = keyMatch;
              const isString = val.startsWith('"');
              const isNumber = /^-?\d/.test(val.trim());
              const isBool = val.trim() === 'true' || val.trim() === 'false';
              const isNull = val.trim() === 'null';
              return (
                <span key={i}>
                  {indent}
                  <span className="text-sky-300">{key}</span>
                  <span className="text-slate-400">{colon}</span>
                  <span className={
                    isString ? 'text-amber-300' :
                    isNumber ? 'text-green-300' :
                    isBool || isNull ? 'text-purple-300' :
                    'text-slate-300'
                  }>{val}</span>
                  {'\n'}
                </span>
              );
            }
            return <span key={i} className="text-slate-400">{line}{'\n'}</span>;
          })}
        </pre>
      </div>
    </div>
  );
}
