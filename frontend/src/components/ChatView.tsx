import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import MermaidBlock from './MermaidBlock';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { chatApi, formatSkillDisplayName, type ChatMessage, type ModelMetadataApi, type ToolCallEvent, type ChartSpec, type SkillActivationEvent, type ChatTurnStatus } from '../services/api';
import { convertAsciiTableToMarkdown } from '../utils/chatMarkdown';
import TickerMentionInput from './TickerMentionInput';
import { getErrorMessage, isInsufficientTokensError, isAuthenticationError } from '../utils/errorHandling';

// ── RTL Detection Utility ──────────────────────────────────────────────────
/**
 * Detects if text contains RTL (Right-to-Left) characters.
 * Checks for Hebrew, Arabic, and other RTL scripts.
 */
function detectRTL(text: string): boolean {
  // RTL Unicode ranges: Hebrew (0590-05FF), Arabic (0600-06FF, 0750-077F, 08A0-08FF),
  // Syriac (0700-074F), Thaana (0780-07BF), N'Ko (07C0-07FF)
  const rtlRegex = /[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F\u0750-\u077F\u0780-\u07BF\u07C0-\u07FF\u08A0-\u08FF]/;
  return rtlRegex.test(text);
}

/** Normalize inline bullet characters (•) into markdown list lines so they render as separate list items. */
function normalizeBulletsForMarkdown(content: string): string {
  if (!content) return content;
  return content
    .replace(/ • /g, '\n- ')
    .replace(/^\s*• /gm, '- ');
}

/** Remove the FOLLOW_UP_JSON:... line from content so it is not shown in the bubble (options appear below). */
function stripFollowUpJsonLine(content: string): string {
  if (!content) return content;
  return content
    .split('\n')
    .filter((line) => !/^\s*FOLLOW_UP_JSON:/.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const CHART_JSON_PREFIX = 'CHART_JSON:';

/** Extract chart specs from text that contains CHART_JSON:{...} (brace-matching). Used when backend did not emit chart events. */
function extractChartSpecsFromContent(text: string): ChartSpec[] {
  if (!text || !text.includes(CHART_JSON_PREFIX)) return [];
  const specs: ChartSpec[] = [];
  let i = 0;
  while (i < text.length) {
    const idx = text.indexOf(CHART_JSON_PREFIX, i);
    if (idx === -1) break;
    let start = idx + CHART_JSON_PREFIX.length;
    while (start < text.length && (text[start] === ' ' || text[start] === '\t')) start += 1;
    if (start >= text.length || text[start] !== '{') {
      i = idx + 1;
      continue;
    }
    let depth = 0;
    let end = start;
    for (let j = start; j < text.length; j++) {
      const c = text[j];
      if (c === '{') depth += 1;
      else if (c === '}') {
        depth -= 1;
        if (depth === 0) {
          end = j + 1;
          break;
        }
      }
    }
    if (depth !== 0) {
      i = idx + 1;
      continue;
    }
    const payload = text.slice(start, end);
    try {
      const spec = JSON.parse(payload) as ChartSpec;
      if (spec?.title != null && spec?.type && spec?.xKey && Array.isArray(spec?.yKeys) && Array.isArray(spec?.data)) {
        specs.push(spec);
      }
    } catch {
      // skip malformed JSON
    }
    i = end;
  }
  return specs;
}

/** Remove CHART_JSON:{...} segments from content so they are not shown as raw JSON in the bubble. */
function stripChartJsonFromContent(content: string): string {
  if (!content || !content.includes(CHART_JSON_PREFIX)) return content;
  let cleaned = content;
  let i = 0;
  while (i < cleaned.length) {
    const idx = cleaned.indexOf(CHART_JSON_PREFIX, i);
    if (idx === -1) break;
    let start = idx + CHART_JSON_PREFIX.length;
    while (start < cleaned.length && (cleaned[start] === ' ' || cleaned[start] === '\t')) start += 1;
    if (start >= cleaned.length || cleaned[start] !== '{') {
      i = idx + 1;
      continue;
    }
    let depth = 0;
    let end = start;
    for (let j = start; j < cleaned.length; j++) {
      const c = cleaned[j];
      if (c === '{') depth += 1;
      else if (c === '}') {
        depth -= 1;
        if (depth === 0) {
          end = j + 1;
          break;
        }
      }
    }
    if (depth !== 0) {
      i = idx + 1;
      continue;
    }
    cleaned = cleaned.slice(0, idx) + cleaned.slice(end);
    i = idx;
  }
  return cleaned.replace(/\n{3,}/g, '\n\n').trim();
}

// ── Friendly display names for tool names ──────────────────────────────────
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  get_ticker_quote: 'Ticker Quote',
  get_ticker_data: 'Historical Data',
  // Legacy aliases kept for rendering older stored chat events.
  get_stock_quote: 'Ticker Quote',
  get_platform_reports: 'AI Reports',
  get_news: 'Company News',
  get_fundamentals: 'Fundamentals',
  get_balance_sheet: 'Balance Sheet',
  get_cashflow: 'Cash Flow',
  get_income_statement: 'Income Statement',
  // Legacy alias kept for rendering older stored chat events.
  get_stock_data: 'Historical Data',
  get_indicators: 'Technical Indicators',
  get_insider_transactions: 'Insider Transactions',
  get_insider_sentiment: 'Insider Sentiment',
  get_global_news: 'Global News',
  web_search: 'Web Search',
  get_user_context: 'User Profile',
  get_user_subscriptions: 'Watchlist',
  get_portfolio_overview: 'Portfolio Overview',
};

function formatToolDisplayName(name: string): string {
  return TOOL_DISPLAY_NAMES[name] ?? name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Sub-components ─────────────────────────────────────────────────────────

export function StreamingCursor() {
  return <span className="inline-block w-0.5 h-3.5 bg-blue-400 ml-0.5 align-middle animate-pulse" />;
}

export function TypingIndicator({ status }: { status?: string | null }) {
  const displayStatus = status ? (/[.…]$/.test(status) ? status : `${status}…`) : 'Thinking…';

  return (
    <div className="mb-6 flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10 text-blue-300 shadow-[0_10px_24px_rgba(37,99,235,0.12)]">
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
        </svg>
      </div>
      <div className="rounded-lg border border-slate-800/80 bg-slate-900/90 px-4 py-3 shadow-[0_16px_40px_rgba(15,23,42,0.3)]">
        <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">AI Analyst</div>
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <svg className="h-3.5 w-3.5 shrink-0 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          <span>{displayStatus}</span>
        </div>
      </div>
    </div>
  );
}

function formatThinkingStatus(status?: string | null): string | null {
  if (status == null) return null;

  const trimmed = status.trim();
  if (!trimmed) return null;

  const runningWorkflowMatch = trimmed.match(/^Running\s+([a-z0-9_]+)\s+workflow(?:\.{3}|…)?$/i);
  if (runningWorkflowMatch) {
    return `Running ${formatSkillDisplayName(runningWorkflowMatch[1])} workflow`;
  }

  const callingToolsMatch = trimmed.match(/^Calling\s+(.+?)(?:\.{3}|…)?$/i);
  if (callingToolsMatch) {
    const formattedNames = callingToolsMatch[1]
      .split(/\s*,\s*/)
      .filter(Boolean)
      .map((name) => formatToolDisplayName(name))
      .join(', ');
    return `Calling ${formattedNames}`;
  }

  return trimmed;
}

export function ToolCallBlock({ toolCall }: { toolCall: ToolCallEvent }) {
  const [expanded, setExpanded] = useState(false);
  const displayName = formatToolDisplayName(toolCall.name);

  let inputDisplay = toolCall.input;
  try {
    const parsed = JSON.parse(toolCall.input);
    const vals = Object.values(parsed);
    if (vals.length === 1) inputDisplay = String(vals[0]);
    else if (vals.length > 1)
      inputDisplay = Object.entries(parsed)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ');
  } catch { /* use raw */ }

  return (
    <div className="mb-1.5 rounded-md border border-slate-600/60 bg-slate-800/60 overflow-hidden text-xs">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-slate-700/50 transition-colors text-left"
      >
        <svg className="w-3.5 h-3.5 text-violet-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span className="font-medium text-violet-300">{displayName}</span>
        {inputDisplay && (
          <span className="text-slate-400 truncate flex-1">
            <span className="text-slate-500 mr-1">·</span>{inputDisplay}
          </span>
        )}
        <svg
          className={`w-3.5 h-3.5 text-slate-500 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="border-t border-slate-600/60 divide-y divide-slate-700/60">
          {toolCall.input && (
            <div className="px-3 py-2">
              <div className="text-slate-500 uppercase tracking-wide text-[10px] font-semibold mb-1">Input</div>
              <pre className="text-slate-300 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed max-h-24 overflow-y-auto">
                {toolCall.input}
              </pre>
            </div>
          )}
          <div className="px-3 py-2">
            <div className="text-slate-500 uppercase tracking-wide text-[10px] font-semibold mb-1">Output</div>
            <pre className="text-slate-300 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed max-h-40 overflow-y-auto">
              {toolCall.output || '(empty)'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Skill display names ────────────────────────────────────────────────────
export function SkillActivationBlock({ event }: { event: SkillActivationEvent }) {
  const [expanded, setExpanded] = useState(false);
  const displayName = formatSkillDisplayName(event.name);

  const stepCount = event.steps.length;
  const failedCount = event.steps.filter((s) => !s.ok).length;

  return (
    <div className="mb-1.5 rounded-md border border-blue-500/40 bg-blue-950/30 overflow-hidden text-xs">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-blue-900/30 transition-colors text-left"
      >
        {/* ⚡ Lightning bolt — distinct from the ⚙️ gear used for tool calls */}
        <svg className="w-3.5 h-3.5 text-blue-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
        <span className="font-medium text-blue-300">{displayName}</span>
        <span className="text-blue-400/70 ml-1">
          · {stepCount} step{stepCount !== 1 ? 's' : ''}
          {failedCount > 0 && <span className="text-red-400 ml-1">({failedCount} failed)</span>}
        </span>
        <svg
          className={`w-3.5 h-3.5 text-slate-500 shrink-0 ml-auto transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded: show each step */}
      {expanded && stepCount > 0 && (
        <div className="border-t border-blue-500/30 divide-y divide-blue-900/40">
          {event.steps.map((step, i) => {
            const toolDisplay = formatToolDisplayName(step.tool);
            return (
              <div key={i} className="px-3 py-2">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${step.ok ? 'bg-green-400' : 'bg-red-400'}`} />
                  <span className="font-medium text-blue-200">{toolDisplay}</span>
                  {step.input && (
                    <span className="text-slate-400 truncate flex-1">
                      <span className="text-slate-500 mr-1">·</span>{step.input.slice(0, 80)}
                    </span>
                  )}
                </div>
                {step.output && (
                  <pre className="text-slate-400 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed max-h-20 overflow-y-auto pl-3">
                    {step.output.slice(0, 300)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export type ChatMessageWithMeta = ChatMessage & {
  tokens_used?: number;
  /** Platform tokens deducted (prefer this for display) */
  platform_tokens_used?: number;
  /** LLM provider, tokens, cost (from API/DB) */
  model_metadata?: ModelMetadataApi;
  cost_usd?: number;
  tools_called?: number;
  tool_call_events?: ToolCallEvent[];
  skill_activation_events?: SkillActivationEvent[];
  charts?: ChartSpec[];
  follow_up_questions?: string[];
};

// ── Copy helpers ───────────────────────────────────────────────────────────

/** One-click copy with a brief "Copied!" flash. Returns [copied, triggerCopy]. */
function useCopyText(text: string): [boolean, () => void] {
  const [copied, setCopied] = useState(false);
  const trigger = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }, [text]);
  return [copied, trigger];
}

/** Copy icon button — shows a checkmark for 2 s after copying. */
function CopyButton({ onClick, copied, title = 'Copy' }: { onClick: () => void; copied: boolean; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="flex h-6 w-6 items-center justify-center rounded-sm text-slate-400 transition-colors hover:bg-slate-600/60 hover:text-slate-200"
      aria-label={title}
    >
      {copied ? (
        <svg className="w-3.5 h-3.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}

/** Copy a chart SVG element as a PNG image to the clipboard. */
async function copyChartAsImage(containerEl: HTMLElement | null): Promise<boolean> {
  if (!containerEl) return false;
  const svgEl = containerEl.querySelector('svg');
  if (!svgEl) return false;

  try {
    const svgRect = svgEl.getBoundingClientRect();
    const width = svgRect.width || 600;
    const height = svgRect.height || 240;

    // Serialize SVG with explicit dimensions and white-on-dark background
    const svgClone = svgEl.cloneNode(true) as SVGElement;
    svgClone.setAttribute('width', String(width));
    svgClone.setAttribute('height', String(height));
    svgClone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

    // Prepend a dark background rect
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('width', '100%');
    bg.setAttribute('height', '100%');
    bg.setAttribute('fill', '#1e293b');
    svgClone.insertBefore(bg, svgClone.firstChild);

    const svgData = new XMLSerializer().serializeToString(svgClone);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = reject;
      img.src = url;
    });

    const canvas = document.createElement('canvas');
    const scale = window.devicePixelRatio || 1;
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext('2d')!;
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0, width, height);
    URL.revokeObjectURL(url);

    const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, 'image/png'));
    if (!blob) return false;

    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
    return true;
  } catch {
    return false;
  }
}

// ── ChartBlock ─────────────────────────────────────────────────────────────

const DEFAULT_COLORS = ['#60a5fa', '#34d399', '#f59e0b', '#f87171', '#a78bfa', '#fb923c'];

export function ChartBlock({ spec }: { spec: ChartSpec }) {
  const colors = spec.colors?.length ? spec.colors : DEFAULT_COLORS;
  const containerRef = useRef<HTMLDivElement>(null);
  const [imgCopied, setImgCopied] = useState(false);

  const handleCopyImage = useCallback(async () => {
    const ok = await copyChartAsImage(containerRef.current);
    if (ok) {
      setImgCopied(true);
      setTimeout(() => setImgCopied(false), 2000);
    }
  }, []);

  // Format X-axis tick labels: shorten ISO dates to MM/DD or MM/DD/YY
  const formatXTick = (val: string | number) => {
    if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}/.test(val)) {
      const d = new Date(val);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    }
    return String(val);
  };

  const commonProps = {
    data: spec.data,
    margin: { top: 4, right: 8, left: 0, bottom: 4 },
  };

  const axes = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
      <XAxis
        dataKey={spec.xKey}
        tickFormatter={formatXTick}
        tick={{ fill: '#9ca3af', fontSize: 11 }}
        axisLine={{ stroke: '#4b5563' }}
        tickLine={false}
        interval="preserveStartEnd"
      />
      <YAxis
        tick={{ fill: '#9ca3af', fontSize: 11 }}
        axisLine={false}
        tickLine={false}
        width={48}
        tickFormatter={(v: number) =>
          Math.abs(v) >= 1_000_000
            ? `${(v / 1_000_000).toFixed(1)}M`
            : Math.abs(v) >= 1_000
            ? `${(v / 1_000).toFixed(1)}K`
            : String(v)
        }
      />
      <Tooltip
        contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
        labelStyle={{ color: '#e2e8f0' }}
        itemStyle={{ color: '#94a3b8' }}
        labelFormatter={(label) => formatXTick(label)}
      />
      {spec.yKeys.length > 1 && (
        <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8', paddingTop: 4 }} />
      )}
    </>
  );

  const renderChart = () => {
    if (spec.type === 'bar') {
      return (
        <BarChart {...commonProps}>
          {axes}
          {spec.yKeys.map((key, i) => (
            <Bar key={key} dataKey={key} fill={colors[i % colors.length]} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      );
    }
    if (spec.type === 'area') {
      return (
        <AreaChart {...commonProps}>
          {axes}
          {spec.yKeys.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[i % colors.length]}
              fill={colors[i % colors.length]}
              fillOpacity={0.15}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </AreaChart>
      );
    }
    if (spec.type === 'scatter') {
      return (
        <ScatterChart {...commonProps}>
          {axes}
          {spec.yKeys.map((key, i) => (
            <Scatter key={key} name={key} dataKey={key} fill={colors[i % colors.length]} />
          ))}
        </ScatterChart>
      );
    }
    // default: line
    return (
      <LineChart {...commonProps}>
        {axes}
        {spec.yKeys.map((key, i) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={colors[i % colors.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    );
  };

  return (
    <div className="mt-3 rounded-md border border-slate-600/60 bg-slate-800/60 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700/60">
        <span className="text-xs font-semibold text-slate-300">{spec.title ?? ''}</span>
        <button
          type="button"
          onClick={handleCopyImage}
          title="Copy chart as image"
          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 hover:bg-slate-600/60 px-1.5 py-0.5 rounded transition-colors"
          aria-label="Copy chart as image"
        >
          {imgCopied ? (
            <>
              <svg className="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-green-400">Copied!</span>
            </>
          ) : (
            <>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>Copy image</span>
            </>
          )}
        </button>
      </div>
      <div className="px-2 py-3" ref={containerRef}>
        <ResponsiveContainer width="100%" height={220}>
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ── Ticker mention helpers ─────────────────────────────────────────────────

/** Extract all @TICKER mentions from a message string (uppercase, deduplicated). */
export function extractMentionedTickers(text: string): string[] {
  const matches = text.match(/@([A-Z0-9.]{1,10})/gi) ?? [];
  const tickers = matches.map((m) => m.slice(1).toUpperCase());
  return [...new Set(tickers)];
}

/**
 * Render a user message, turning @TICKER tokens into styled badge chips
 * and leaving the rest as plain text.
 */
function renderUserMessage(content: string) {
  // Split on @TICKER patterns, keeping the delimiters
  const parts = content.split(/(@[A-Za-z0-9.]{1,10})/g);
  return parts.map((part, i) => {
    if (/^@[A-Za-z0-9.]{1,10}$/.test(part)) {
      return (
        <span
          key={i}
          className="mx-0.5 inline-flex items-center gap-0.5 rounded-sm border border-blue-300/40 bg-blue-400/25 px-1.5 py-0.5 font-mono text-xs font-semibold text-blue-100"
        >
          {part}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export function MessageBubble({
  message,
  isStreaming = false,
  onFollowUpClick,
  showAdminUsageDetails = false,
}: {
  message: ChatMessageWithMeta;
  isStreaming?: boolean;
  onFollowUpClick?: (text: string) => void;
  showAdminUsageDetails?: boolean;
}) {
  const isUser = message.role === 'user';
  const [copied, triggerCopy] = useCopyText(stripChartJsonFromContent(stripFollowUpJsonLine(message.content ?? '')));

  // Detect if message contains RTL text
  const isRTL = detectRTL(message.content);
  const direction = isRTL ? 'rtl' : 'ltr';

  if (isUser) {
    return (
      <div className="mb-6 flex justify-end">
        <div className="max-w-[88%] md:max-w-[78%]">
          <div className="mb-1.5 text-right text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500">You</div>
          <div
            className="rounded-lg border border-slate-700/80 bg-transparent px-4 py-3 text-sm leading-relaxed text-white chat-message-content"
            dir={direction}
          >
            {renderUserMessage(message.content)}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-700/80 bg-slate-900/90 text-slate-300 shadow-[0_12px_28px_rgba(15,23,42,0.28)]">
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <div className="mb-1.5 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500">
          <span>AI Analyst</span>
        </div>
        {/* Skill activation blocks — shown above tool calls, with ⚡ icon */}
        {message.skill_activation_events && message.skill_activation_events.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.skill_activation_events.map((ev, i) => (
              <SkillActivationBlock key={i} event={ev} />
            ))}
          </div>
        )}
        {message.tool_call_events && message.tool_call_events.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.tool_call_events.map((tc, i) => (
              <ToolCallBlock key={i} toolCall={tc} />
            ))}
          </div>
        )}
        {/* Only render message bubble if there's content, streaming, or charts */}
        {(message.content || isStreaming || (message.charts && message.charts.length > 0) || extractChartSpecsFromContent(message.content ?? '').length > 0) && (
          <div
            className="rounded-lg border border-slate-800/80 bg-slate-900/92 px-4 py-3 text-sm leading-relaxed text-slate-100 shadow-[0_18px_40px_rgba(15,23,42,0.28)]"
            dir={direction}
          >
            <div className="prose prose-invert prose-sm max-w-none chat-message-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ node, ...props }) => <p className="mb-2 last:mb-0 text-slate-100 text-sm leading-relaxed" {...props} />,
                  ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-0.5 text-slate-100" {...props} />,
                  ol: ({ node, ...props }) => <ol className="list-decimal list-outside pl-4 mb-2 space-y-0.5 text-slate-100" {...props} />,
                  li: ({ node, ...props }) => <li className="text-slate-100 text-sm" {...props} />,
                  strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
                  em: ({ node, ...props }) => <em className="italic text-slate-200" {...props} />,
                  code: ({ node, className, children, ...props }) => {
                    if (className === 'language-mermaid') {
                      return <MermaidBlock code={String(children).trim()} />;
                    }
                    return <code className="bg-slate-800 px-1 py-0.5 rounded text-xs text-green-400 font-mono" {...props}>{children}</code>;
                  },
                  h1: ({ node, ...props }) => <h1 className="text-base font-bold text-white mb-2 mt-3 first:mt-0" {...props} />,
                  h2: ({ node, ...props }) => <h2 className="text-sm font-bold text-white mb-1.5 mt-3 first:mt-0" {...props} />,
                  h3: ({ node, ...props }) => <h3 className="text-sm font-semibold text-slate-200 mb-1 mt-2 first:mt-0" {...props} />,
                  blockquote: ({ node, ...props }) => <blockquote className="border-l-2 border-blue-500 pl-3 text-slate-300 italic my-2" {...props} />,
                  table: ({ node, ...props }) => (
                    <div className="overflow-x-auto my-2 rounded border border-slate-600">
                      <table className="min-w-full text-xs border-collapse" {...props} />
                    </div>
                  ),
                  thead: ({ node, ...props }) => <thead className="bg-slate-800 text-slate-200" {...props} />,
                  tbody: ({ node, ...props }) => <tbody className="divide-y divide-slate-600" {...props} />,
                  tr: ({ node, ...props }) => <tr className="hover:bg-slate-600/40" {...props} />,
                  th: ({ node, ...props }) => <th className="px-2 py-1.5 text-left font-semibold text-white" {...props} />,
                  td: ({ node, ...props }) => <td className="px-2 py-1.5 text-slate-300" {...props} />,
                }}
              >
                {normalizeBulletsForMarkdown(convertAsciiTableToMarkdown(stripChartJsonFromContent(stripFollowUpJsonLine(message.content ?? ''))))}
              </ReactMarkdown>
              {isStreaming && <StreamingCursor />}
            </div>
            {/* Render charts: from message.charts or extracted from content if backend didn't emit chart events */}
            {(() => {
              const chartsToShow = (message.charts?.length ?? 0) > 0 ? message.charts! : extractChartSpecsFromContent(message.content ?? '');
              if (chartsToShow.length === 0) return null;
              return (
                <div className="space-y-2 -mx-1">
                  {chartsToShow.map((spec, i) => (
                    <ChartBlock key={i} spec={spec} />
                  ))}
                </div>
              );
            })()}
          </div>
        )}
        {/* Copy button + token/tool metadata row */}
        <div className="mt-2 ml-1 flex flex-wrap items-center gap-2.5">
          {/* Copy text button — always visible once message is complete */}
          {!isStreaming && stripChartJsonFromContent(stripFollowUpJsonLine(message.content ?? '')) && (
            <CopyButton onClick={triggerCopy} copied={copied} title="Copy message" />
          )}
          {((message.platform_tokens_used != null || message.tokens_used != null) || (message.tools_called != null && message.tools_called > 0)) && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              {message.tools_called != null && message.tools_called > 0 && (
                <span className="flex items-center gap-1 rounded-sm border border-slate-700/80 bg-slate-900/70 px-2.5 py-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  {message.tools_called} tool{message.tools_called !== 1 ? 's' : ''} used
                </span>
              )}
              {(message.platform_tokens_used != null || message.tokens_used != null) && (
                <span className="rounded-sm border border-slate-700/80 bg-slate-900/70 px-2.5 py-1">
                  {(message.platform_tokens_used ?? message.tokens_used)!} {(message.platform_tokens_used ?? message.tokens_used) !== 1 ? 'DECKS' : 'DECK'} used
                  {showAdminUsageDetails && (message.tokens_used != null || message.cost_usd != null) && (
                    <span>
                      {' ('}
                      {message.tokens_used != null && message.tokens_used.toLocaleString()}
                      {message.tokens_used != null && message.cost_usd != null && ' · '}
                      {message.cost_usd != null && `${(message.cost_usd * 100).toFixed(2)} ¢`}
                      {')'}
                    </span>
                  )}
                </span>
              )}
            </div>
          )}
        </div>
        {/* Follow-up suggestions — clickable chips */}
        {!isStreaming && message.follow_up_questions && message.follow_up_questions.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Suggestions</p>
            <div className="flex flex-wrap gap-2">
              {message.follow_up_questions.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onFollowUpClick?.(q)}
                  className="rounded-md border border-slate-700/80 bg-slate-900/70 px-3.5 py-2.5 text-left text-[13px] text-slate-300 transition-all hover:border-slate-600 hover:bg-slate-800/80"
                >
                  <span className="text-blue-400 mr-1.5">→</span>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── useChatState hook — all chat state and streaming logic ─────────────────

export interface UseChatStateReturn {
  messages: ChatMessageWithMeta[];
  setMessages: (messages: ChatMessageWithMeta[] | ((prev: ChatMessageWithMeta[]) => ChatMessageWithMeta[])) => void;
  input: string;
  setInput: (v: string) => void;
  isLoading: boolean;
  isStreaming: boolean;
  thinkingStatus: string | null;
  error: string | null;
  setError: (v: string | null) => void;
  tokenBalance: number | null;
  setTokenBalance: (v: number | null) => void;
  /** Most recent locally streamed turn that fully completed. */
  lastCompletedTurn: ChatTurnStatus | null;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  sendMessage: (text: string) => void;
  clearChat: () => void;
  /** Clear loading/thinking state only (e.g. when switching to another conversation). */
  clearLoadingState: () => void;
  /** Restore a server-owned running turn when reopening a session. */
  restorePendingTurn: (status?: string | null) => void;
}

export function useChatState(
  onBalanceUpdate?: (balance: number) => void,
  context?: Record<string, unknown>,
  sessionId?: number | null,
  onStreamDone?: (newSessionId?: number) => void,
  onStreamStart?: (sessionId: number) => void,
  onTurnStarted?: (turn: ChatTurnStatus) => void,
  /** When provided and sessionId is null, called before send to create a session and show it in history immediately. */
  createSessionIfNeeded?: () => Promise<number | null>,
): UseChatStateReturn {
  const [messages, setMessages] = useState<ChatMessageWithMeta[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tokenBalance, setTokenBalance] = useState<number | null>(null);
  const [lastCompletedTurn, setLastCompletedTurn] = useState<ChatTurnStatus | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const lastHiddenAtRef = useRef<number>(0);
  const activeTurnRef = useRef<ChatTurnStatus | null>(null);
  /** Only callbacks from the current visible stream may update the UI. */
  const visibleStreamIdRef = useRef<number | null>(null);
  const nextStreamIdRef = useRef(0);

  // When the view unmounts, stop applying stream updates locally but let the
  // network request continue so the backend can finish and persist the turn.
  useEffect(() => {
    return () => {
      visibleStreamIdRef.current = null;
    };
  }, []);

  // Track when the tab is hidden so we can suppress spurious network errors if the user
  // returns within a few seconds. We do not abort the stream on tab switch so the agent
  // keeps thinking/streaming while the user is in another tab.
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) {
        lastHiddenAtRef.current = Date.now();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isStreaming]);

  const sendMessage = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || isStreaming) return;

    const doSend = async () => {
      const streamId = nextStreamIdRef.current + 1;
      nextStreamIdRef.current = streamId;
      visibleStreamIdRef.current = streamId;
      const isVisibleStream = () => visibleStreamIdRef.current === streamId;

      const userMessage: ChatMessage = { role: 'user', content: trimmed };
      const newMessages = [...messages, userMessage];
      setMessages(newMessages);
      setInput('');
      setIsLoading(true);
      setThinkingStatus(null);
      setError(null);
      activeTurnRef.current = null;

      const assistantIndex = newMessages.length;

      // Create session upfront when starting a new conversation so it appears in history immediately
      let effectiveSessionId = sessionId ?? undefined;
      if (effectiveSessionId == null && createSessionIfNeeded) {
        const newId = await createSessionIfNeeded();
        if (newId != null) effectiveSessionId = newId;
      }
      if (effectiveSessionId != null) onStreamStart?.(effectiveSessionId);

      // When sessionId is set, backend loads history from DB; send only the new user message
      const apiMessages =
        effectiveSessionId != null ? [userMessage] : newMessages.map((m) => ({ role: m.role, content: m.content }));

      // Extract @TICKER mentions from the user's message and merge into context
      const mentionedTickers = extractMentionedTickers(trimmed);
      const existingTickers: string[] = (context?.tickers as string[]) ?? [];
      const mergedTickers = mentionedTickers.length > 0
        ? [...new Set([...existingTickers, ...mentionedTickers])]
        : existingTickers;
      const mergedContext: Record<string, unknown> = {
        ...(context ?? {}),
        ...(mergedTickers.length > 0 ? { tickers: mergedTickers } : {}),
      };

      chatApi.streamMessage(
      apiMessages,
      (chunk) => {
        if (!isVisibleStream()) return;
        setIsLoading(false);
        setIsStreaming(true);
        setThinkingStatus(null);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              content: updated[assistantIndex].content + chunk,
            };
          } else {
            updated.splice(assistantIndex, 0, { role: 'assistant', content: chunk });
          }
          return updated;
        });
      },
      (tokensUsed, balance, toolsCalled, followUpQuestions, newSessionId, platformTokensUsed, costUsd) => {
        if (!isVisibleStream()) return;
        visibleStreamIdRef.current = null;
        const currentTurn = activeTurnRef.current;
        if (currentTurn && (newSessionId == null || currentTurn.session_id === newSessionId)) {
          setLastCompletedTurn({
            ...currentTurn,
            status: 'completed',
            last_thinking_status: null,
            error_message: null,
          });
        }
        activeTurnRef.current = null;
        setIsStreaming(false);
        setIsLoading(false);
        setThinkingStatus(null);
        if (balance >= 0) {
          setTokenBalance(balance);
          onBalanceUpdate?.(balance);
        }
        onStreamDone?.(newSessionId);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              tokens_used: tokensUsed,
              platform_tokens_used: platformTokensUsed,
              cost_usd: costUsd,
              tools_called: toolsCalled,
              follow_up_questions: followUpQuestions ?? undefined,
            };
          }
          return updated;
        });
      },
      (error) => {
        if (!isVisibleStream()) return;
        visibleStreamIdRef.current = null;
        activeTurnRef.current = null;
        setIsStreaming(false);
        setIsLoading(false);
        setThinkingStatus(null);
        
        // Suppress network/connection errors when app was recently in background (e.g. user left and came back).
        const errorMessage = typeof error === 'string' ? error : '';
        const isNetworkError = /network|fetch|failed|load failed|connection|stream failed/i.test(errorMessage);
        const recentlyHidden = Date.now() - lastHiddenAtRef.current < 3000;
        if (isNetworkError && (document.hidden || recentlyHidden)) {
          return;
        }
        
        // Use the error handling utility for consistent messaging
        if (isInsufficientTokensError(error)) {
          setError('Insufficient DECK coins. Please purchase more tokens to continue chatting.');
        } else if (isAuthenticationError(error)) {
          setError('You must be signed in to use the AI chat.');
        } else {
          setError(getErrorMessage(error, 'Failed to get a response. Please try again.'));
        }
      },
      (turn) => {
        activeTurnRef.current = turn;
        setLastCompletedTurn((prev) => (prev?.session_id === turn.session_id ? null : prev));
        onTurnStarted?.(turn);
      },
      (status) => {
        if (!isVisibleStream()) return;
        setThinkingStatus(formatThinkingStatus(status));
      },
      (toolCall) => {
        if (!isVisibleStream()) return;
        // Tool completed — clear the thinking status so the UI doesn't keep
        // showing the stale tool name while the LLM reasons over the results
        setThinkingStatus(null);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            const existing = updated[assistantIndex].tool_call_events ?? [];
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              tool_call_events: [...existing, toolCall],
            };
          } else {
            updated.splice(assistantIndex, 0, {
              role: 'assistant',
              content: '',
              tool_call_events: [toolCall],
            });
          }
          return updated;
        });
      },
      mergedContext,
      (chartSpec) => {
        if (!isVisibleStream()) return;
        // Chart emitted by execute_python — attach to the assistant message
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            const existing = updated[assistantIndex].charts ?? [];
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              charts: [...existing, chartSpec],
            };
          } else {
            updated.splice(assistantIndex, 0, {
              role: 'assistant',
              content: '',
              charts: [chartSpec],
            });
          }
          return updated;
        });
      },
      (skillEvent) => {
        if (!isVisibleStream()) return;
        // Skill workflow completed — attach to the assistant message
        setThinkingStatus(null);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            const existing = updated[assistantIndex].skill_activation_events ?? [];
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              skill_activation_events: [...existing, skillEvent],
            };
          } else {
            updated.splice(assistantIndex, 0, {
              role: 'assistant',
              content: '',
              skill_activation_events: [skillEvent],
            });
          }
          return updated;
        });
      },
      effectiveSessionId ?? undefined,
    );
    };

    doSend().catch((err) => {
      activeTurnRef.current = null;
      setIsLoading(false);
      setIsStreaming(false);
      setThinkingStatus(null);
      setError(err?.message ?? 'Failed to create conversation');
    });
  };

  const clearChat = () => {
    visibleStreamIdRef.current = null;
    setMessages([]);
    setError(null);
    setIsLoading(false);
    setIsStreaming(false);
    setThinkingStatus(null);
  };

  const clearLoadingState = () => {
    visibleStreamIdRef.current = null;
    setIsLoading(false);
    setIsStreaming(false);
    setThinkingStatus(null);
  };

  const restorePendingTurn = (status?: string | null) => {
    visibleStreamIdRef.current = null;
    setIsLoading(true);
    setIsStreaming(false);
    setThinkingStatus(formatThinkingStatus(status) ?? 'Working…');
    setError(null);
  };

  return {
    messages,
    setMessages,
    input,
    setInput,
    isLoading,
    isStreaming,
    thinkingStatus,
    error,
    setError,
    tokenBalance,
    setTokenBalance,
    lastCompletedTurn,
    messagesEndRef,
    inputRef,
    sendMessage,
    clearChat,
    clearLoadingState,
    restorePendingTurn,
  };
}

// ── ChatView — the full chat UI, layout-agnostic ───────────────────────────

export interface ChatViewProps {
  /** All chat state from useChatState() */
  chat: UseChatStateReturn;
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
  /** Whether raw token and cost internals should be visible */
  showAdminUsageDetails?: boolean;
  /** Suggested questions shown on the empty state */
  suggestedQuestions: string[];
  /** Optional welcome heading */
  welcomeHeading?: string;
  /** Optional welcome subtext */
  welcomeSubtext?: string;
  /** Placeholder text for the input */
  inputPlaceholder?: string;
  /** Extra content rendered above the input (e.g. disclaimer) */
  inputFooter?: React.ReactNode;
}

export default function ChatView({
  chat,
  isAuthenticated,
  showAdminUsageDetails = false,
  suggestedQuestions,
  welcomeHeading,
  welcomeSubtext,
  inputPlaceholder,
  inputFooter,
}: ChatViewProps) {
  const {
    messages,
    input,
    setInput,
    isLoading,
    isStreaming,
    thinkingStatus,
    error,
    setError,
    messagesEndRef,
    inputRef,
    sendMessage,
  } = chat;

  const isEmpty = messages.length === 0;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <>
      {/* Messages area */}
      <div className="flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden px-3 py-4 md:px-4 md:py-5">
        {isEmpty && (
          <div className="flex min-h-full items-center justify-center py-4">
            {!isAuthenticated ? (
              <div className="mx-auto max-w-md rounded-xl border border-slate-800/80 bg-slate-900/85 p-8 text-center shadow-[0_24px_60px_rgba(15,23,42,0.28)]">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10">
                  <svg className="h-6 w-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <p className="mb-2 text-lg font-semibold text-white">Sign in to use AI Analyst</p>
                <p className="text-sm leading-6 text-slate-400">
                  Create a free account to chat with the AI Analyst and get live market insights.
                </p>
              </div>
            ) : (
              <div className="mx-auto w-full max-w-5xl rounded-xl border border-slate-800/80 bg-slate-950/55 p-5 shadow-[0_26px_70px_rgba(15,23,42,0.32)] md:p-6">
                <div className="mb-4 flex items-start gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-blue-500/20 bg-blue-500/10">
                    <svg className="h-5 w-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                    </svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    {welcomeHeading && (
                      <p className="text-lg font-semibold tracking-tight text-white">{welcomeHeading}</p>
                    )}
                    {welcomeSubtext && (
                      <p className="mt-1.5 text-[13px] leading-5 text-slate-400">{welcomeSubtext}</p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <span className="rounded-sm border border-slate-800 bg-slate-900/80 px-2.5 py-0.5 text-[11px] text-slate-300">
                        Thesis
                      </span>
                      <span className="rounded-sm border border-slate-800 bg-slate-900/80 px-2.5 py-0.5 text-[11px] text-slate-300">
                        @Ticker
                      </span>
                      <span className="rounded-sm border border-slate-800 bg-slate-900/80 px-2.5 py-0.5 text-[11px] text-slate-300">
                        Charts
                      </span>
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-800/80 pt-4">
                  <div className="mb-3">
                    <p className="text-sm font-semibold text-white">Suggested starting points</p>
                  </div>
                  <div className="grid gap-2">
                    {suggestedQuestions.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => sendMessage(q)}
                        className="group rounded-md border border-slate-800/80 bg-slate-950/75 px-3 py-2 text-left transition-all hover:border-slate-700 hover:bg-slate-900"
                      >
                        <div className="flex items-start gap-2.5">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-sm bg-blue-500/10 text-blue-300 transition-colors group-hover:bg-blue-500/15 group-hover:text-blue-200">
                            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </span>
                          <span className="text-[13px] leading-5 text-slate-300">{q}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={`${msg.role}-${i}-${msg.content.slice(0, 24)}`}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
            showAdminUsageDetails={showAdminUsageDetails}
            onFollowUpClick={sendMessage}
          />
        ))}

        {isLoading && <TypingIndicator status={thinkingStatus} />}

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-md border border-red-800/80 bg-red-950/40 px-4 py-3 text-sm text-red-100">
            <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="ml-auto text-red-400 transition-colors hover:text-red-200"
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 px-3 pb-0 pt-1.5 md:px-4">
        <div className="overflow-hidden rounded-lg border border-slate-800/80 bg-slate-800/90 shadow-[0_18px_44px_rgba(15,23,42,0.24)] transition-colors focus-within:border-blue-500/60">
          <div className="px-4 pt-2.5">
            <TickerMentionInput
              inputRef={inputRef}
              value={input}
              onChange={setInput}
              onKeyDown={handleKeyDown}
              placeholder={inputPlaceholder ?? (isAuthenticated ? 'Ask about any stock…' : 'Sign in to start chatting…')}
              disabled={isLoading || isStreaming || !isAuthenticated}
              className="min-h-[56px] max-h-[160px] resize-none bg-transparent text-[14px] leading-6 text-white outline-none placeholder:text-slate-500 disabled:opacity-50"
            />
          </div>

          <div className="flex items-center justify-between gap-2 border-t border-slate-800/80 px-3 py-1.5">
            {isAuthenticated ? (
              <div className="min-w-0 flex items-center gap-1.5 text-[10px] text-slate-500">
                <span className="truncate rounded-sm border border-slate-800 bg-slate-950/70 px-2 py-0.5 leading-4">
                  Use <kbd className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">@</kbd> to mention a ticker
                </span>
              </div>
            ) : (
              <span className="min-w-0 truncate text-[10px] text-slate-500">Authentication required to send messages.</span>
            )}
            <button
              type="button"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading || isStreaming || !isAuthenticated}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white transition-colors hover:bg-blue-500 disabled:cursor-default disabled:bg-slate-700 disabled:text-slate-400"
              aria-label="Send message"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.25} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Optional footer below input */}
      {inputFooter}
    </>
  );
}

// Made with Bob
