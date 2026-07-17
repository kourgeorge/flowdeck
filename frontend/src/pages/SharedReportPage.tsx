import { useEffect, useState, type ComponentProps } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ReportTabs from '../components/ReportTabs';
import ReportViewer, {
  ReportAgentTrajectorySection,
  ReportResourcesSection,
  type AgentStep,
  type ReportResource,
} from '../components/ReportViewer';
import AspectSpiderChart, { getAnalysisScoreEntries } from '../components/AspectSpiderChart';
import ReturnScenarioBar from '../components/ReturnScenarioBar';
import { API_BASE_URL } from '../services/api';
import { LOGO_PATH } from '../config';
import { parseReportDate } from '../utils/date';

const REPORT_ORDER = [
  'market_report', 'sentiment_report', 'technical_report',
  'fundamentals_report', 'sec_report', 'valuation_report', 'investment_plan', 'trader_investment_plan', 'final_trade_decision',
];
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

function normalizeOptionalString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

interface SharedTickerReport {
  type: 'ticker';
  ticker: string;
  company_name?: string | null;
  execution_id: number;
  report_date: string | null;
  reports: Record<string, {
    content?: string | null;
    score?: number | null;
    score_label?: string | null;
    recommendation?: string | null;
    confidence?: number | null;
    expected_return_pct?: number | null;
    bear_case_return_pct?: number | null;
    bull_case_return_pct?: number | null;
    current_price?: number | null;
    currency?: string | null;
    key_takeaways?: string[];
    bull_viewpoint?: string[] | null;
    bear_viewpoint?: string[] | null;
    risky_viewpoint?: string[] | null;
    safe_viewpoint?: string[] | null;
    neutral_viewpoint?: string[] | null;
    tps_plan?: string | null;
    resources?: ReportResource[] | null;
    agent_steps?: AgentStep[] | null;
    [key: string]: unknown;
  }>;
}

interface SharedDigestReport {
  type: 'digest';
  execution_id: number;
  narrative: string;
  what_to_watch: string;
  digest_date: string;
  span_type: string;
  span_label: string;
  priority_tickers: string[];
  important_events?: {
    ticker: string;
    importance_score: number;
    event: {
      event_type: string;
      domain: string;
      detected_on?: string | null;
      strength: string;
      metric_value?: number | null;
      description?: string;
    };
  }[];
  references?: unknown[] | null;
  resources?: ReportResource[] | null;
  agent_steps?: AgentStep[] | null;
}

function formatImportantEventLabel(eventType: string): string {
  return IMPORTANT_EVENT_LABELS[eventType] ?? eventType.replace(/_/g, ' ');
}

function formatImportantEventMetric(
  importantEvent: NonNullable<SharedDigestReport['important_events']>[number],
): string | null {
  const metricValue = importantEvent.event.metric_value;
  if (typeof metricValue !== 'number') return null;
  if (['price_spike_up', 'price_spike_down', 'price_gap_up', 'price_gap_down'].includes(importantEvent.event.event_type)) {
    return `${metricValue >= 0 ? '+' : ''}${metricValue.toFixed(1)}%`;
  }
  if (importantEvent.event.event_type === 'earnings_upcoming') {
    return `${metricValue.toFixed(0)}d`;
  }
  if (['volatility_expansion', 'volatility_compression', 'volume_spike'].includes(importantEvent.event.event_type)) {
    return `${metricValue.toFixed(2)}x`;
  }
  if (['insider_buying', 'insider_selling'].includes(importantEvent.event.event_type)) {
    return `$${metricValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return `${metricValue.toFixed(2)}`;
}

type SharedReportData = SharedTickerReport | SharedDigestReport;

export default function SharedReportPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<SharedReportData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError('Missing link');
      setLoading(false);
      return;
    }
    const url = `${API_BASE_URL || ''}/api/share/${encodeURIComponent(token)}`;
    fetch(url, { credentials: 'include' })
      .then((res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error('Invalid or expired link');
          throw new Error('Failed to load report');
        }
        return res.json();
      })
      .then((json: SharedReportData) => {
        setData(json);
        if (json.type === 'ticker' && json.reports) {
          const keys = Object.keys(json.reports);
          const sorted = [...keys].sort((a, b) => {
            const idxA = REPORT_ORDER.indexOf(a);
            const idxB = REPORT_ORDER.indexOf(b);
            if (idxA === -1 && idxB === -1) return a.localeCompare(b);
            if (idxA === -1) return 1;
            if (idxB === -1) return -1;
            return idxA - idxB;
          });
          setSelectedReport(
            sorted.includes('final_trade_decision') ? 'final_trade_decision' : sorted[0] ?? null
          );
        }
      })
      .catch((e: Error) => setError(e.message || 'Invalid or expired link'))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-gray-400">Loading report…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <p className="text-red-400 mb-4">{error ?? 'Invalid or expired link'}</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300 underline">Go to Flowdeck</Link>
        </div>
      </div>
    );
  }

  if (data.type === 'digest') {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <header className="border-b border-gray-700 bg-gray-800/80 px-4 py-4">
          <div className="max-w-4xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
              <img src={LOGO_PATH} alt="" className="w-10 h-10 sm:w-12 sm:h-12 object-contain shrink-0" />
              <span className="text-xl font-bold text-white tracking-wide">Flowdeck</span>
            </Link>
            <span className="text-gray-400 text-sm">
              Shared brief · {data.span_label !== 'Daily' ? `${data.span_label} · ` : ''}{data.digest_date}
            </span>
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-4 py-6">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 sm:p-6">
            <h1 className="text-lg font-semibold text-white mb-1">
              Briefing
              {data.digest_date && (
                <span className="text-gray-400 font-normal ml-2">{data.digest_date}</span>
              )}
            </h1>
            {data.priority_tickers?.length > 0 && (
              <p className="text-sm text-gray-400 mb-4">
                Focus: {data.priority_tickers.join(', ')}
              </p>
            )}
            <div className="prose prose-invert prose-sm max-w-none text-slate-300">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h2: ({ children, ...props }: ComponentProps<'h2'>) => (
                    <h2 className="text-sm font-semibold text-emerald-300 mb-1 mt-4 first:mt-0" {...props}>{children}</h2>
                  ),
                  p: ({ children, ...props }: ComponentProps<'p'>) => (
                    <p className="whitespace-pre-wrap leading-relaxed my-0 text-slate-300" {...props}>{children}</p>
                  ),
                  ul: ({ children, ...props }: ComponentProps<'ul'>) => (
                    <ul className="list-disc pl-5 my-0 space-y-1 text-slate-300" {...props}>{children}</ul>
                  ),
                  li: ({ children, ...props }: ComponentProps<'li'>) => (
                    <li className="leading-relaxed text-slate-300" {...props}>{children}</li>
                  ),
                  table: ({ children, ...props }: ComponentProps<'table'>) => (
                    <div className="overflow-x-auto my-4">
                      <table className="min-w-full text-sm border-collapse" {...props}>
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children, ...props }: ComponentProps<'thead'>) => (
                    <thead className="bg-slate-800/50" {...props}>
                      {children}
                    </thead>
                  ),
                  tbody: ({ children, ...props }: ComponentProps<'tbody'>) => (
                    <tbody className="divide-y divide-slate-700/50" {...props}>
                      {children}
                    </tbody>
                  ),
                  tr: ({ children, ...props }: ComponentProps<'tr'>) => (
                    <tr className="hover:bg-slate-800/30 transition-colors" {...props}>
                      {children}
                    </tr>
                  ),
                  th: ({ children, ...props }: ComponentProps<'th'>) => (
                    <th className="px-3 py-2 text-left text-xs font-semibold text-emerald-200 uppercase tracking-wider border-b border-slate-700" {...props}>
                      {children}
                    </th>
                  ),
                  td: ({ children, ...props }: ComponentProps<'td'>) => (
                    <td className="px-3 py-2 text-sm text-slate-300 border-b border-slate-800/50" {...props}>
                      {children}
                    </td>
                  ),
                }}
              >
                {/##\s*(Market Highlights|What to Watch|Risks\s*&\s*Opportunities)/i.test(data.narrative)
                  ? (() => {
                      const tokens = new Set(['market_highlights', 'key_signals', 'what_to_watch', 'risks_opportunities']);
                      return data.narrative
                        .split('\n')
                        .filter((line) => !tokens.has(line.trim()))
                        .join('\n');
                    })()
                  : data.narrative}
              </ReactMarkdown>
            </div>
            {data.what_to_watch && !/##\s*(Market Highlights|What to Watch|Risks\s*&\s*Opportunities)/i.test(data.narrative) && (
              <div className="mt-6 pt-4 border-t border-gray-700">
                <h2 className="text-sm font-semibold text-white mb-2">What to watch</h2>
                <div className="prose prose-invert prose-sm max-w-none text-slate-300">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children, ...props }: ComponentProps<'p'>) => (
                        <p className="text-sm whitespace-pre-wrap leading-relaxed my-0 text-slate-300" {...props}>{children}</p>
                      ),
                      ul: ({ children, ...props }: ComponentProps<'ul'>) => (
                        <ul className="list-disc pl-5 my-0 space-y-1 text-sm text-slate-300" {...props}>{children}</ul>
                      ),
                      li: ({ children, ...props }: ComponentProps<'li'>) => (
                        <li className="leading-relaxed text-slate-300" {...props}>{children}</li>
                      ),
                      table: ({ children, ...props }: ComponentProps<'table'>) => (
                        <div className="overflow-x-auto my-4">
                          <table className="min-w-full text-sm border-collapse" {...props}>
                            {children}
                          </table>
                        </div>
                      ),
                      thead: ({ children, ...props }: ComponentProps<'thead'>) => (
                        <thead className="bg-slate-800/50" {...props}>
                          {children}
                        </thead>
                      ),
                      tbody: ({ children, ...props }: ComponentProps<'tbody'>) => (
                        <tbody className="divide-y divide-slate-700/50" {...props}>
                          {children}
                        </tbody>
                      ),
                      tr: ({ children, ...props }: ComponentProps<'tr'>) => (
                        <tr className="hover:bg-slate-800/30 transition-colors" {...props}>
                          {children}
                        </tr>
                      ),
                      th: ({ children, ...props }: ComponentProps<'th'>) => (
                        <th className="px-3 py-2 text-left text-xs font-semibold text-emerald-200 uppercase tracking-wider border-b border-slate-700" {...props}>
                          {children}
                        </th>
                      ),
                      td: ({ children, ...props }: ComponentProps<'td'>) => (
                        <td className="px-3 py-2 text-sm text-slate-300 border-b border-slate-800/50" {...props}>
                          {children}
                        </td>
                      ),
                    }}
                  >
                    {data.what_to_watch}
                  </ReactMarkdown>
                </div>
              </div>
            )}
            {data.important_events && data.important_events.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h2 className="text-sm font-semibold text-white mb-2">Important events</h2>
                <div className="space-y-2">
                  {data.important_events.map((item, idx) => {
                    const metric = formatImportantEventMetric(item);
                    return (
                      <div
                        key={`${item.ticker}-${item.event.event_type}-${idx}`}
                        className="flex items-start justify-between gap-3 rounded-lg border border-gray-700 bg-gray-900/50 px-3 py-2"
                      >
                        <div className="min-w-0">
                          <div className="text-sm text-gray-100">
                            <span className="font-semibold text-emerald-300">{item.ticker}</span>
                            <span className="mx-2 text-gray-600">·</span>
                            <span>{formatImportantEventLabel(item.event.event_type)}</span>
                          </div>
                          <div className="mt-0.5 text-xs text-gray-400">
                            {item.event.strength}
                            {item.event.detected_on ? ` · ${item.event.detected_on}` : ''}
                          </div>
                          {item.event.description && (
                            <div className="mt-1 text-xs leading-5 text-gray-400 max-w-2xl">
                              {item.event.description}
                            </div>
                          )}
                        </div>
                        {metric && <span className="shrink-0 font-mono text-sm text-gray-300">{metric}</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {data.references && data.references.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h2 className="text-sm font-semibold text-white mb-2">References</h2>
                <ul className="text-sm text-gray-400 space-y-1">
                  {data.references.map((ref: unknown, idx: number) => {
                    const r = ref as { label?: string; url?: string };
                    return (
                      <li key={idx}>
                        {r.label}
                        {r.url && <span className="ml-1">· {r.url}</span>}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            {data.resources && data.resources.length > 0 && (
              <ReportResourcesSection resources={data.resources} analysisDate={data.digest_date} />
            )}
            {data.agent_steps && data.agent_steps.length > 0 && (
              <ReportAgentTrajectorySection agentSteps={data.agent_steps} canViewCost={false} />
            )}
          </div>
          <p className="text-xs text-gray-500 mt-4 text-center">
            For informational purposes only. Not investment advice.
          </p>
        </main>
      </div>
    );
  }

  const reports = data.reports || {};
  const availableReports = Object.keys(reports).sort((a, b) => {
    const idxA = REPORT_ORDER.indexOf(a);
    const idxB = REPORT_ORDER.indexOf(b);
    if (idxA === -1 && idxB === -1) return a.localeCompare(b);
    if (idxA === -1) return 1;
    if (idxB === -1) return -1;
    return idxA - idxB;
  });
  const current = selectedReport ? reports[selectedReport] : null;
  const currentAnalysisDate =
    normalizeOptionalString(current?.analysis_date) ??
    normalizeOptionalString(data.report_date) ??
    null;
  const reportScores: Record<string, { score: number | null; score_label: string | null }> = {};
  Object.entries(reports).forEach(([k, v]) => {
    reportScores[k] = { score: v.score ?? null, score_label: v.score_label ?? null };
  });

  const ftd = reports.final_trade_decision;
  const tip = reports.trader_investment_plan;
  const plan = reports.investment_plan;
  const recommendation = (ftd?.recommendation ?? tip?.recommendation) ?? null;
  const confidence = (ftd?.confidence ?? tip?.confidence) ?? null;
  const normalizedConfidence = confidence != null && confidence <= 1 ? confidence : (confidence != null ? confidence / 10 : null);
  const expectedPct = plan?.expected_return_pct ?? null;
  const bearPct = plan?.bear_case_return_pct ?? null;
  const bullPct = plan?.bull_case_return_pct ?? null;
  const hasReturnScenarios = expectedPct != null || bearPct != null || bullPct != null;
  const summaryScoreEntries = getAnalysisScoreEntries(reportScores);
  const reportDateFormatted = data.report_date
    ? parseReportDate(data.report_date)?.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) ?? data.report_date
    : null;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="border-b border-gray-700 bg-gray-800/80 px-4 py-4">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
            <img src={LOGO_PATH} alt="" className="w-10 h-10 sm:w-12 sm:h-12 object-contain shrink-0" />
            <span className="text-xl font-bold text-white tracking-wide">Flowdeck</span>
          </Link>
          <span className="text-gray-400 text-sm">
            Shared report · {data.ticker}
            {data.report_date && ` · ${data.report_date}`}
          </span>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6 space-y-4">
        {/* AI analysis header (gradient block with company, date, radar, decision, return scenarios) */}
        <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg border border-blue-700/50 p-5">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-white mb-1">
                {data.company_name || data.ticker}
                <span className="text-gray-400 font-normal ml-2">({data.ticker})</span>
              </h2>
              <div className="text-sm text-gray-400 mb-0.5">Last Analysis Date</div>
              <div className="text-lg font-semibold text-white">
                {reportDateFormatted ?? data.report_date ?? 'N/A'}
              </div>
            </div>
            <div className="flex items-center gap-4 shrink-0">
              {summaryScoreEntries.length >= 3 && (
                <AspectSpiderChart scoreEntries={summaryScoreEntries} size={80} />
              )}
              <div className="text-right">
                <div className="text-sm text-gray-400 mb-0.5">AI Decision</div>
                <div className={`text-2xl font-bold ${recommendation === 'BUY' ? 'text-green-400' : recommendation === 'SELL' ? 'text-red-400' : recommendation === 'HOLD' ? 'text-yellow-400' : 'text-white'}`}>
                  {recommendation ?? 'N/A'}
                </div>
                {normalizedConfidence != null && (
                  <div className="text-sm text-gray-400 mt-0.5">Confidence: {(normalizedConfidence * 100).toFixed(0)}%</div>
                )}
              </div>
            </div>
          </div>
          {hasReturnScenarios && (
            <div className="mt-3 pt-3 border-t border-gray-600/50">
              <ReturnScenarioBar
                expected={expectedPct}
                bear={bearPct}
                bull={bullPct}
                referencePrice={plan?.current_price ?? null}
                currency={plan?.currency ?? null}
                compact
              />
            </div>
          )}
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <ReportTabs
            availableReports={availableReports}
            selectedReport={selectedReport}
            onSelectReport={setSelectedReport}
            reportScores={reportScores}
          />
          <div className="mt-4">
            <ReportViewer
              content={current?.content ?? null}
              score={current?.score ?? null}
              scoreLabel={current?.score_label ?? null}
              keyTakeaways={current?.key_takeaways}
              analysisDate={currentAnalysisDate}
              reportType={selectedReport ?? undefined}
              bullViewpoint={current?.bull_viewpoint ?? null}
              bearViewpoint={current?.bear_viewpoint ?? null}
              riskyViewpoint={current?.risky_viewpoint ?? null}
              safeViewpoint={current?.safe_viewpoint ?? null}
              neutralViewpoint={current?.neutral_viewpoint ?? null}
              tpsPlan={current?.tps_plan ?? null}
              resources={current?.resources ?? undefined}
              agentSteps={current?.agent_steps ?? undefined}
              valuationBridge={(current?.valuation_bridge as {
                current_price?: number | null;
                growth_premium?: number | null;
                multiple_expansion?: number | null;
                risk_discount?: number | null;
                fair_value?: number | null;
              } | null | undefined) ?? null}
              valuationSensitivity={(current?.valuation_sensitivity as {
                fcf_growth_rate?: { delta?: number | null; low?: number | null; high?: number | null } | null;
                wacc?: { delta?: number | null; low?: number | null; high?: number | null } | null;
                terminal_growth?: { delta?: number | null; low?: number | null; high?: number | null } | null;
                exit_multiple?: { delta?: number | null; low?: number | null; high?: number | null } | null;
              } | null | undefined) ?? null}
            />
          </div>
        </div>

        <p className="text-xs text-gray-500 mt-4 text-center">
          For informational purposes only. Not investment advice.
        </p>
      </main>
    </div>
  );
}
