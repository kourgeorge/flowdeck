import { useState } from 'react';

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function formatJsonPrimitive(value: unknown): string {
  if (typeof value === 'string') return `"${value}"`;
  if (value === null) return 'null';
  return String(value);
}

function JsonViewerNode({
  label,
  value,
  defaultExpanded = false,
}: {
  label?: string;
  value: unknown;
  defaultExpanded?: boolean;
}) {
  const isArray = Array.isArray(value);
  const isObject = isJsonObject(value);
  const isContainer = isArray || isObject;
  const entries = isArray
    ? value.map((item, index) => [String(index), item] as const)
    : isObject
      ? Object.entries(value)
      : [];
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (!isContainer) {
    return (
      <div className="flex flex-wrap items-start gap-2 py-0.5">
        {label && <span className="font-medium text-sky-300">{label}:</span>}
        <span
          className={
            typeof value === 'string'
              ? 'break-all text-emerald-300'
              : value === null
                ? 'text-fuchsia-300'
                : typeof value === 'number'
                  ? 'text-amber-300'
                  : typeof value === 'boolean'
                    ? 'text-violet-300'
                    : 'text-gray-200'
          }
        >
          {formatJsonPrimitive(value)}
        </span>
      </div>
    );
  }

  const isEmpty = entries.length === 0;
  const summary = isArray ? `[${entries.length}]` : `{${entries.length}}`;

  return (
    <div className="py-0.5">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-2 text-left text-gray-200 transition-colors hover:text-white"
      >
        <span className={`inline-block text-[10px] text-gray-500 transition-transform ${expanded ? 'rotate-90' : ''}`}>
          ▶
        </span>
        {label && <span className="font-medium text-sky-300">{label}:</span>}
        <span className="text-gray-400">{summary}</span>
      </button>
      {expanded && !isEmpty && (
        <div className="ml-4 border-l border-gray-700 pl-3">
          {entries.map(([key, val]) => (
            <JsonViewerNode key={key} label={key} value={val} defaultExpanded={false} />
          ))}
        </div>
      )}
      {expanded && isEmpty && (
        <div className="ml-4 border-l border-gray-700 pl-3 text-gray-500">
          {isArray ? '(empty array)' : '(empty object)'}
        </div>
      )}
    </div>
  );
}

export default function JsonViewer({ data }: { data: unknown }) {
  return (
    <div className="max-h-96 overflow-auto rounded-xl border border-gray-800 bg-gray-950/80 p-4 font-mono text-xs">
      <JsonViewerNode value={data} defaultExpanded />
    </div>
  );
}

// Made with Bob
