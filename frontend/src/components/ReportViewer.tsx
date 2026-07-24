import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TpsPlanCard from './TpsPlanCard';
import { useAuth } from '../contexts/AuthContext';
import MermaidBlock from './MermaidBlock';

export interface ReportResource {
  type?: string;
  url?: string;
  title?: string;
  ticker?: string;
  description?: string;
  tool?: string;
  args?: unknown;
  /** Tool that was executed (e.g. get_news, get_global_news) */
  tool_name?: string;
  /** JSON or string summary of tool arguments */
  tool_input?: unknown;
  /** Full saved tool output snapshot at report-generation time */
  tool_output?: unknown;
  /** Truncated tool result for inspection */
  tool_output_preview?: string;
  captured_at?: string;
}

export interface AgentStep {
  agent?: string;
  phase?: string;
  kind?: string;
  report_key?: string;
  iteration?: number;
  round_number?: number;
  status?: string;
  summary?: string;
  message_preview?: string;
  output_preview?: string;
  observation_preview?: string;
  tool_name?: string;
  tool_args?: unknown;
  tool_calls?: Array<{ id?: string; name?: string; args?: unknown }>;
  usage?: {
    input_tokens?: number | null;
    output_tokens?: number | null;
    total_tokens?: number | null;
    cost_usd?: number | null;
  } | null;
  extra?: Record<string, unknown> | null;
  captured_at?: string;
}

interface ReportViewerProps {
  content: string | null;
  score?: number | null;
  scoreLabel?: string | null;
  keyTakeaways?: string[];
  analysisDate?: string | null;
  reportType?: string | null;
  bullViewpoint?: string[] | null;
  bearViewpoint?: string[] | null;
  riskyViewpoint?: string[] | null;
  safeViewpoint?: string[] | null;
  neutralViewpoint?: string[] | null;
  /** TPS-YAML v0.1 structured trading plan (trader report only) */
  tpsPlan?: string | null;
  /** Sources used for this report (news, SEC filings, Reddit, etc.) */
  resources?: ReportResource[] | null;
  /** Persisted execution trace for this report */
  agentSteps?: AgentStep[] | null;
  valuationBridge?: {
    current_price?: number | null;
    growth_premium?: number | null;
    multiple_expansion?: number | null;
    risk_discount?: number | null;
    fair_value?: number | null;
  } | null;
  valuationSensitivity?: {
    fcf_growth_rate?: { delta?: number | null; low?: number | null; high?: number | null } | null;
    wacc?: { delta?: number | null; low?: number | null; high?: number | null } | null;
    terminal_growth?: { delta?: number | null; low?: number | null; high?: number | null } | null;
    exit_multiple?: { delta?: number | null; low?: number | null; high?: number | null } | null;
  } | null;
}

const REPORT_METADATA: Record<string, { title: string; contains: string; aspects: string; methodology: string }> = {
  market_report: {
    title: 'Market',
    contains: 'A technical analysis of price action, trends, and momentum. The report interprets multiple indicators, explains their signals in context, and concludes with a summary table and a Market Score (1–5).',
    aspects: 'Up to 8 complementary indicators: 50-day SMA, 200-day SMA, 10-day EMA (trend); MACD, MACD Signal, MACD Histogram (momentum); RSI (overbought/oversold); Bollinger Bands; ATR (volatility); VWMA (volume-weighted). Each is analyzed for trend direction, momentum strength, and support/resistance implications.',
    methodology: 'First in the analysis chain. The Market Analyst uses historical price data and indicator values, selects relevant indicators, interprets their signals together, and writes a detailed narrative. The goal is fine-grained analysis that avoids redundancy and explains why each indicator matters for the current market.',
  },
  sentiment_report: {
    title: 'News & Sentiment',
    contains: 'A combined analysis of recent news and catalysts together with crowd sentiment. Covers company-specific news, macroeconomic trends, insider activity, social media discussions, and prediction-market signals from the past week. Assigns a combined Sentiment Score (1–5).',
    aspects: 'Deterministic catalyst events, company-specific and global/macroeconomic headlines, insider buying/selling, Reddit finance discussions, and Polymarket prediction-market pricing. The news narrative and crowd sentiment are reconciled, with divergences called out explicitly.',
    methodology: 'Runs in the analyst chain. The News & Sentiment Analyst gathers the news/catalyst narrative (events, headlines, macro, insider transactions) and crowd-sentiment signals (Reddit, prediction markets), reconciles the two layers, and produces one integrated report with an overall assessment.',
  },
  fundamentals_report: {
    title: 'Fundamentals',
    contains: 'A view of the company\'s financial health: financial documents, company profile, and financial history. Assigns a Fundamentals Score (1–5).',
    aspects: 'Company overview, balance sheet, cash flow, income statement, valuation ratios, 52-week range, moving averages, profitability trends, revenue growth, debt levels, and financial stability. When data is sparse (e.g. for indices), the report reflects what is available and any limitations.',
    methodology: 'Runs in the analyst chain. The Fundamentals Analyst reviews financial statements and key metrics, evaluates financial health and sustainability, and produces a report. For indices or thinly covered securities, the analysis is limited to available data.',
  },
  sec_report: {
    title: 'SEC / Regulatory',
    contains: 'Analysis of SEC EDGAR filings (10-K/10-Q): risk factors, management\'s discussion and analysis (MD&A), and competition. Assigns an SEC Score (1–5) reflecting regulatory and disclosure risk.',
    aspects: 'Risk Factors (Item 1A), Management\'s Discussion and Analysis (Item 7 or Part I Item 2), Competition subsection from Business (Item 1), and optionally legal proceedings and market risk disclosures. Focus is on implications for traders.',
    methodology: 'Runs in the analyst chain when the SEC analyst is selected. The backend fetches the filing from SEC EDGAR, extracts sections via LLM, and the SEC Analyst summarizes management, competition, and risk into a report. For non-US companies, no SEC content is available.',
  },
  technical_report: {
    title: 'Technical Analysis',
    contains: 'An advanced technical report on regime, support/resistance, and divergences. Provides actionable recommendations with specific price levels.',
    aspects: 'Divergence detection (bullish/bearish between price and RSI or MACD); regime detection (trending vs ranging, volatility level); support/resistance via price clustering, volume profile, recent highs/lows, and moving averages; entry/exit targets and stop-loss levels.',
    methodology: 'Runs in the analyst chain when technical analysis is selected. The Technical Analyst follows a sequence: assess market regime, identify support and resistance, check for divergences, then synthesize findings into recommendations and a Technical Score (1–5).',
  },
  valuation_report: {
    title: 'Valuation',
    contains: 'A multi-method fair value analysis with scenario-based valuation ranges and an overall Valuation Score (1–5).',
    aspects: 'DCF inputs, peer multiple comparisons, growth and discount-rate assumptions, bear/base/bull fair values, current premium or discount versus base fair value, and the key assumptions driving the estimate.',
    methodology: 'Runs in the analyst chain when valuation analysis is selected. The Valuation Analyst gathers quote, fundamentals, financial statements, peer comps, growth assumptions, and WACC inputs, then synthesizes them into a fair value range and narrative assessment.',
  },
  investment_plan: {
    title: 'Research',
    contains: 'The authoritative investment recommendation (Buy/Sell/Hold) with rationale and strategic actions. Includes expected return ranges (base, bear, bull) and a Conviction Score (1–5). The Conviction Score reflects how strongly and clearly the directional thesis (bullish, bearish, or hold) is supported by the debate — it is not a quality rating of the recommendation itself, but a measure of how much conviction the Research Manager has in the directional call.',
    aspects: 'Summary of key points from the Bull, Bear, and Neutral researchers; which side the judge aligns with and why; strategic actions, position sizing, and monitoring; expected, bear-case, and bull-case percentage returns from current price over the investment horizon.',
    methodology: 'Produced after the Bull / Bear / Neutral debate. The three researchers take turns arguing, drawing on all prior reports. The Research Manager acts as judge, weighs all three perspectives, commits to the final Buy/Sell/Hold recommendation, and produces the investment plan with expected return scenarios. The Conviction Score is derived from the debate quality: clarity of signals, strength of arguments, and alignment of evidence.',
  },
  trader_investment_plan: {
    title: 'Trader',
    contains: 'The trader\'s execution-oriented plan translated from research into an actionable trading stance.',
    aspects: 'Concrete trade direction, rationale, and execution notes derived from analyst and research-manager outputs.',
    methodology: 'Produced after the Research Manager\'s investment plan. The Trader agent converts the research recommendation into a practical, executable trading plan (including the structured TPS levels). This is the final step in the pipeline.',
  },
  final_trade_decision: {
    title: 'Risk & Confidence',
    contains: 'A detailed risk analysis and refined trader plan. Includes a Risk Score (1–5) and key takeaways for traders. The Risk Score measures confidence in the quality and clarity of the risk assessment — not the direction of the trade. It is quantitatively anchored to the average and dispersion (standard deviation) of all upstream scores (market, sentiment, news, fundamentals, SEC, technical, and conviction), then adjusted based on the debate quality.',
    aspects: 'Summary of the Risky, Neutral, and Safe analysts\' arguments; rationale for the risk assessment; refined plan incorporating risk insights; lessons from past decisions; 3–5 key takeaways; and the final BUY/SELL/HOLD recommendation shown in the UI.',
    methodology: 'Final step in the analysis. The Risky, Neutral, and Safe analysts debate the Trader\'s plan — each arguing for high-risk, balanced, or low-risk approaches using all prior reports. The Risk Judge weighs their arguments, computes a baseline from all upstream scores, penalises or boosts confidence based on score dispersion, and produces the final risk analysis plus final recommendation. This is the end of the pipeline.',
  },
};

function ReportMoreInfo({ reportType }: { reportType: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const meta = REPORT_METADATA[reportType];
  if (!meta) return null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-700/40 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-700/40 transition-colors"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-slate-400">
          <svg className="w-5 h-5 text-blue-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          What does this report contain & how was it created?
        </span>
        <svg
          className={`w-5 h-5 text-slate-400 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-1 space-y-4 text-sm">
          <div>
            <div className="font-semibold text-slate-200 mb-1.5">What it contains</div>
            <p className="text-slate-400 leading-relaxed">{meta.contains}</p>
          </div>
          <div>
            <div className="font-semibold text-slate-200 mb-1.5">Aspects investigated</div>
            <p className="text-slate-400 leading-relaxed">{meta.aspects}</p>
          </div>
          <div>
            <div className="font-semibold text-slate-200 mb-1.5">How it was done</div>
            <p className="text-slate-400 leading-relaxed">{meta.methodology}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function formatResourceValue(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatCurrencyValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A';
  return `$${value.toFixed(2)}`;
}

function buildDeterministicValuationBridgeMarkdown(
  valuationBridge?: {
    current_price?: number | null;
    growth_premium?: number | null;
    multiple_expansion?: number | null;
    risk_discount?: number | null;
    fair_value?: number | null;
  } | null,
): string | null {
  if (!valuationBridge) return null;
  const currentPrice = typeof valuationBridge.current_price === 'number' ? valuationBridge.current_price : null;
  const growthPremium = typeof valuationBridge.growth_premium === 'number' ? valuationBridge.growth_premium : null;
  const multipleExpansion = typeof valuationBridge.multiple_expansion === 'number' ? valuationBridge.multiple_expansion : null;
  const riskDiscount = typeof valuationBridge.risk_discount === 'number' ? valuationBridge.risk_discount : null;
  const fairValue = typeof valuationBridge.fair_value === 'number' ? valuationBridge.fair_value : null;
  if ([currentPrice, growthPremium, multipleExpansion, riskDiscount, fairValue].every((value) => value == null)) {
    return null;
  }
  return [
    '### 3. Valuation Bridge',
    `- Current Price: ${formatCurrencyValue(currentPrice)}`,
    `- Plus: Growth premium (${formatCurrencyValue(growthPremium)})`,
    `- Plus: Multiple expansion (${formatCurrencyValue(multipleExpansion)})`,
    `- Less: Risk discount (${formatCurrencyValue(riskDiscount)})`,
    `- **Fair Value: ${formatCurrencyValue(fairValue)}**`,
  ].join('\n');
}

function buildDeterministicValuationSensitivityMarkdown(
  valuationSensitivity?: {
    fcf_growth_rate?: { delta?: number | null; low?: number | null; high?: number | null } | null;
    wacc?: { delta?: number | null; low?: number | null; high?: number | null } | null;
    terminal_growth?: { delta?: number | null; low?: number | null; high?: number | null } | null;
    exit_multiple?: { delta?: number | null; low?: number | null; high?: number | null } | null;
  } | null,
): string | null {
  if (!valuationSensitivity) return null;
  const fcf = valuationSensitivity.fcf_growth_rate;
  const wacc = valuationSensitivity.wacc;
  const terminal = valuationSensitivity.terminal_growth;
  const exit = valuationSensitivity.exit_multiple;
  if (!fcf && !wacc && !terminal && !exit) return null;

  return [
    '### 5. Sensitivity Analysis',
    `- FCF Growth Rate: ±2% -> Fair value range: ${formatCurrencyValue(fcf?.low)} to ${formatCurrencyValue(fcf?.high)}`,
    `- WACC: ±1% -> Fair value range: ${formatCurrencyValue(wacc?.low)} to ${formatCurrencyValue(wacc?.high)}`,
    `- Terminal Growth: ±0.5% -> Fair value range: ${formatCurrencyValue(terminal?.low)} to ${formatCurrencyValue(terminal?.high)}`,
    `- Exit Multiple: ±2x -> Fair value range: ${formatCurrencyValue(exit?.low)} to ${formatCurrencyValue(exit?.high)}`,
  ].join('\n');
}

function replaceMarkdownSection(content: string, sectionHeading: string, replacement: string): string {
  const escapedHeading = sectionHeading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`${escapedHeading}\\b[\\s\\S]*?(?=\\n### |\\n## |$)`, 'm');
  if (pattern.test(content)) {
    return content.replace(pattern, replacement);
  }
  return `${replacement}\n\n${content}`;
}

function toDateOnly(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  const direct = value.match(/^(\d{4}-\d{2}-\d{2})/);
  if (direct?.[1]) return direct[1];
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}

function isResourceRelevantForAnalysisDate(
  resource: ReportResource,
  analysisDate?: string | null,
): boolean {
  const hasSavedData =
    resource.tool_output != null ||
    Boolean(resource.tool_output_preview) ||
    Boolean(resource.url) ||
    Boolean(resource.title) ||
    Boolean(resource.description);

  if (!analysisDate) return hasSavedData;

  const analysisDay = toDateOnly(analysisDate);
  if (!analysisDay) return hasSavedData;

  const rawInput = resource.tool_input ?? resource.args;
  const toolInput =
    typeof rawInput === 'object' && rawInput !== null
      ? rawInput as Record<string, unknown>
      : null;
  const startDay = toDateOnly(toolInput?.start_date);
  const endDay = toDateOnly(toolInput?.end_date ?? toolInput?.curr_date);
  const capturedDay = toDateOnly(resource.captured_at);

  if (startDay && endDay) return analysisDay >= startDay && analysisDay <= endDay;
  if (endDay) return analysisDay === endDay;
  if (capturedDay) return analysisDay === capturedDay;
  return hasSavedData;
}

function ResourceToolDetail({ resource }: { resource: ReportResource }) {
  const [show, setShow] = useState(false);
  const toolName = resource.tool_name || resource.tool;
  const toolInput = resource.tool_input ?? resource.args;
  const toolOutput = resource.tool_output;
  const hasTool = toolName || toolInput != null || resource.tool_output_preview || toolOutput != null;
  if (!hasTool) return null;
  return (
    <div className="mt-1.5 rounded border border-slate-600 bg-slate-800/60 overflow-hidden text-xs">
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="w-full px-2.5 py-1.5 flex items-center justify-between gap-2 text-left text-slate-400 hover:text-slate-300 hover:bg-slate-700/40"
      >
        <span className="font-medium">Tool: {toolName || '—'}</span>
        <svg className={`w-3 h-3 flex-shrink-0 ${show ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
      {show && (
        <div className="px-2.5 pb-2 space-y-1.5 font-mono text-slate-400">
          {resource.captured_at && (
            <div className="text-slate-500">
              Saved at {resource.captured_at}
            </div>
          )}
          {toolInput != null && formatResourceValue(toolInput) !== '' && (
            <div>
              <div className="text-slate-500 mb-0.5">Input</div>
              <pre className="whitespace-pre-wrap break-all rounded bg-slate-900/80 p-1.5 text-[11px] max-h-24 overflow-y-auto">{formatResourceValue(toolInput)}</pre>
            </div>
          )}
          {toolOutput != null && formatResourceValue(toolOutput) !== '' ? (
            <div>
              <div className="text-slate-500 mb-0.5">Saved Output Snapshot</div>
              <pre className="whitespace-pre-wrap break-all rounded bg-slate-900/80 p-1.5 text-[11px] max-h-56 overflow-y-auto">{formatResourceValue(toolOutput)}</pre>
            </div>
          ) : resource.tool_output_preview != null && resource.tool_output_preview !== '' ? (
            <div>
              <div className="text-slate-500 mb-0.5">Output (preview)</div>
              <pre className="whitespace-pre-wrap break-all rounded bg-slate-900/80 p-1.5 text-[11px] max-h-32 overflow-y-auto">{resource.tool_output_preview}</pre>
            </div>
          ) : null}
          {resource.url && (
            <div className="text-slate-500">
              External link available above.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ReportResourcesSection({
  resources,
  analysisDate,
}: {
  resources: ReportResource[];
  analysisDate?: string | null;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const visibleResources = resources.filter((resource) =>
    isResourceRelevantForAnalysisDate(resource, analysisDate),
  );
  if (visibleResources.length === 0) return null;

  return (
    <div className="pt-3 border-t border-slate-700">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-400 hover:text-white"
      >
        <svg
          className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-90 text-emerald-300' : 'text-slate-500'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span>Resources</span>
        <span className="text-xs text-slate-500">({visibleResources.length})</span>
      </button>
      {isOpen && (
        <ul className="mt-1.5 space-y-1.5 text-sm text-slate-300">
          {visibleResources.map((ref, idx) => {
            const label =
              ref.title ||
              ref.description ||
              (ref.type && ref.ticker ? `${ref.type} (${ref.ticker})` : ref.type) ||
              ref.tool_name ||
              ref.tool ||
              'Source';
            const source = ref.type || ref.description || ref.tool_name || ref.tool;
            return (
              <li key={idx} className="flex flex-col">
                <span className="font-medium">{label}</span>
                <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                  {source && <span>{source}</span>}
                  {analysisDate && <span>Analysis date: {analysisDate}</span>}
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
                  {ref.ticker && <span>Ticker: {ref.ticker}</span>}
                </div>
                <ResourceToolDetail resource={ref} />
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function prettifyToken(value: string | undefined): string {
  if (!value) return 'Unknown';
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function AgentStepDetail({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  const text = formatResourceValue(value);
  if (!text) return null;
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap break-all rounded bg-slate-900/80 p-2 text-[11px] text-slate-300">{text}</pre>
    </div>
  );
}

interface TrajectoryItem {
  primary: AgentStep;
  result?: AgentStep;
}

const PHASE_ORDER: Record<string, number> = {
  analysis: 10,
  investment_debate: 20,
  investment_decision: 30,
  trade_execution: 40,
  risk_debate: 50,
  risk_decision: 60,
};

const KIND_ORDER: Record<string, number> = {
  llm_decision: 10,
  tool_call: 20,
  tool_result: 30,
  debate_turn: 40,
  report_synthesis: 50,
};

function getMessagePreviewLabel(step: AgentStep): string {
  if (step.kind === 'debate_turn') return 'Input Preview';
  return 'Message Preview';
}

function parseCapturedAt(value?: string): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function sortAgentSteps(agentSteps: AgentStep[]): AgentStep[] {
  return agentSteps
    .map((step, index) => ({ step, index }))
    .sort((a, b) => {
      const aTs = parseCapturedAt(a.step.captured_at);
      const bTs = parseCapturedAt(b.step.captured_at);
      if (aTs == null && bTs != null) return 1;
      if (aTs != null && bTs == null) return -1;
      if (aTs != null && bTs != null && aTs !== bTs) return aTs - bTs;

      const aPhase = PHASE_ORDER[a.step.phase ?? ''] ?? 999;
      const bPhase = PHASE_ORDER[b.step.phase ?? ''] ?? 999;
      if (aPhase !== bPhase) return aPhase - bPhase;

      const aRound = a.step.round_number ?? Number.MAX_SAFE_INTEGER;
      const bRound = b.step.round_number ?? Number.MAX_SAFE_INTEGER;
      if (aRound !== bRound) return aRound - bRound;

      const aIteration = a.step.iteration ?? Number.MAX_SAFE_INTEGER;
      const bIteration = b.step.iteration ?? Number.MAX_SAFE_INTEGER;
      if (aIteration !== bIteration) return aIteration - bIteration;

      const aKind = KIND_ORDER[a.step.kind ?? ''] ?? 999;
      const bKind = KIND_ORDER[b.step.kind ?? ''] ?? 999;
      if (aKind !== bKind) return aKind - bKind;

      const aAgent = a.step.agent ?? '';
      const bAgent = b.step.agent ?? '';
      if (aAgent !== bAgent) return aAgent.localeCompare(bAgent);

      const aTool = a.step.tool_name ?? '';
      const bTool = b.step.tool_name ?? '';
      if (aTool !== bTool) return aTool.localeCompare(bTool);

      return a.index - b.index;
    })
    .map(({ step }) => step);
}

function shouldCombineToolSteps(primary: AgentStep, next?: AgentStep): boolean {
  if (!next) return false;
  if (primary.kind !== 'tool_call' || next.kind !== 'tool_result') return false;
  return (
    primary.agent === next.agent &&
    primary.phase === next.phase &&
    primary.iteration === next.iteration &&
    primary.tool_name === next.tool_name
  );
}

function buildTrajectoryItems(agentSteps: AgentStep[]): TrajectoryItem[] {
  const items: TrajectoryItem[] = [];
  const orderedSteps = sortAgentSteps(agentSteps);
  for (let index = 0; index < orderedSteps.length; index += 1) {
    const primary = orderedSteps[index];
    const next = orderedSteps[index + 1];
    if (shouldCombineToolSteps(primary, next)) {
      items.push({ primary, result: next });
      index += 1;
      continue;
    }
    items.push({ primary });
  }
  return items;
}

export function ReportAgentTrajectorySection({
  agentSteps,
  canViewCost = false,
}: {
  agentSteps: AgentStep[];
  canViewCost?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  if (agentSteps.length === 0) return null;
  const trajectoryItems = buildTrajectoryItems(agentSteps);

  return (
    <div className="pt-3 border-t border-slate-700">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-400 hover:text-white"
      >
        <svg
          className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-90 text-sky-300' : 'text-slate-500'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span>Agent trajectory</span>
        <span className="text-xs text-slate-500">({trajectoryItems.length})</span>
      </button>
      {isOpen && (
        <ol className="mt-2 space-y-2">
          {trajectoryItems.map((item, idx) => {
            const step = item.primary;
            const resultStep = item.result;
            const title = step.summary || step.tool_name || prettifyToken(step.kind) || `Step ${idx + 1}`;
            const badges = [
              step.agent,
              step.phase ? prettifyToken(step.phase) : null,
              step.kind ? prettifyToken(step.kind) : null,
              step.status ? prettifyToken(step.status) : null,
            ].filter(Boolean) as string[];

            return (
              <li key={`${idx}-${step.agent ?? 'agent'}-${step.kind ?? 'step'}-${step.tool_name ?? ''}`}>
                <details className="rounded-lg border border-slate-700 bg-slate-800/60">
                  <summary className="cursor-pointer list-none px-3 py-2">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-700 text-[11px] font-semibold text-slate-200">
                        {idx + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-slate-200">{title}</div>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {badges.map((badge) => (
                            <span
                              key={`${idx}-${badge}`}
                              className="rounded-full border border-slate-600 bg-slate-900/70 px-2 py-0.5 text-[11px] text-slate-400"
                            >
                              {badge}
                            </span>
                          ))}
                          {step.iteration != null && (
                            <span className="rounded-full border border-slate-600 bg-slate-900/70 px-2 py-0.5 text-[11px] text-slate-400">
                              Iteration {step.iteration}
                            </span>
                          )}
                          {step.round_number != null && (
                            <span className="rounded-full border border-slate-600 bg-slate-900/70 px-2 py-0.5 text-[11px] text-slate-400">
                              Round {step.round_number}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </summary>
                  <div className="space-y-2 border-t border-slate-700 px-3 py-3 text-xs text-slate-400">
                    {step.tool_name && (
                      <div className="text-slate-300">
                        Tool: <span className="font-mono text-sky-300">{step.tool_name}</span>
                      </div>
                    )}
                    {resultStep && (
                      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
                        <span>Result: {prettifyToken(resultStep.status)}</span>
                        {resultStep.kind && <span>{prettifyToken(resultStep.kind)}</span>}
                      </div>
                    )}
                    {step.tool_calls && step.tool_calls.length > 0 && (
                      <div className="rounded border border-slate-700 bg-slate-900/50 p-2">
                        <div className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Tool calls requested</div>
                        <div className="space-y-1">
                          {step.tool_calls.map((toolCall, toolIdx) => (
                            <div key={`${idx}-tool-${toolIdx}`} className="text-slate-300">
                              <span className="font-mono text-sky-300">{toolCall.name || 'tool'}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <AgentStepDetail label="Tool Args" value={step.tool_args} />
                    <AgentStepDetail label={getMessagePreviewLabel(step)} value={step.message_preview} />
                    <AgentStepDetail label="Observation" value={resultStep?.observation_preview ?? step.observation_preview} />
                    <AgentStepDetail label="Output Preview" value={step.output_preview} />
                    <AgentStepDetail label="Extra" value={resultStep?.extra ?? step.extra} />
                    {(resultStep?.usage ?? step.usage) && (
                      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
                        {(resultStep?.usage ?? step.usage)?.input_tokens != null && <span>In: {(resultStep?.usage ?? step.usage)?.input_tokens}</span>}
                        {(resultStep?.usage ?? step.usage)?.output_tokens != null && <span>Out: {(resultStep?.usage ?? step.usage)?.output_tokens}</span>}
                        {(resultStep?.usage ?? step.usage)?.total_tokens != null && <span>Total: {(resultStep?.usage ?? step.usage)?.total_tokens}</span>}
                        {canViewCost && (resultStep?.usage ?? step.usage)?.cost_usd != null && <span>Cost: ${Number((resultStep?.usage ?? step.usage)?.cost_usd).toFixed(6)}</span>}
                      </div>
                    )}
                  </div>
                </details>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

export default function ReportViewer({ content, score, scoreLabel, keyTakeaways, analysisDate, reportType, bullViewpoint, bearViewpoint, riskyViewpoint, safeViewpoint, neutralViewpoint, tpsPlan, resources, agentSteps, valuationBridge, valuationSensitivity }: ReportViewerProps) {
  const { user } = useAuth();
  const deterministicValuationBridge = reportType === 'valuation_report'
    ? buildDeterministicValuationBridgeMarkdown(valuationBridge)
    : null;
  const deterministicValuationSensitivity = reportType === 'valuation_report'
    ? buildDeterministicValuationSensitivityMarkdown(valuationSensitivity)
    : null;
  let renderedContent = content;
  if (renderedContent && deterministicValuationBridge) {
    renderedContent = replaceMarkdownSection(renderedContent, '### 3. Valuation Bridge', deterministicValuationBridge);
  }
  if (renderedContent && deterministicValuationSensitivity) {
    renderedContent = replaceMarkdownSection(renderedContent, '### 5. Sensitivity Analysis', deterministicValuationSensitivity);
  }
  const hasContent = renderedContent && renderedContent.trim().length > 0;
  const hasBullBear = (bullViewpoint && bullViewpoint.length > 0) || (bearViewpoint && bearViewpoint.length > 0);
  const hasRiskViewpoints = (riskyViewpoint && riskyViewpoint.length > 0) || (safeViewpoint && safeViewpoint.length > 0) || (neutralViewpoint && neutralViewpoint.length > 0);
  const hasViewpoints = hasBullBear || hasRiskViewpoints;
  const hasResources = resources?.some((resource) => isResourceRelevantForAnalysisDate(resource, analysisDate)) ?? false;
  const hasAgentSteps = (agentSteps?.length ?? 0) > 0;
  const canViewCost = user?.is_admin === true;

  if (!hasContent && !hasViewpoints && !hasResources && !hasAgentSteps) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center text-gray-400">
        No report content available
      </div>
    );
  }

  const getScoreColor = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'text-gray-400';
    if (score <= 1.5) return 'text-red-400';
    if (score <= 2.5) return 'text-yellow-400';
    if (score <= 3.5) return 'text-blue-400';
    return 'text-green-400';
  };

  const getScoreBgColor = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'bg-gray-700';
    if (score <= 1.5) return 'bg-red-500/20 border-red-500/50';
    if (score <= 2.5) return 'bg-yellow-500/20 border-yellow-500/50';
    if (score <= 3.5) return 'bg-blue-500/20 border-blue-500/50';
    return 'bg-green-500/20 border-green-500/50';
  };

  return (
    <div className="space-y-4">
      {reportType && REPORT_METADATA[reportType] && (
        <ReportMoreInfo reportType={reportType} />
      )}
      {score !== null && score !== undefined && (
        <div className={`bg-slate-800 rounded-lg border border-slate-700 p-4 ${getScoreBgColor(score)}`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-400 mb-1">
                {scoreLabel || 'Score'}
              </div>
              <div className={`text-3xl font-bold ${getScoreColor(score)}`}>
                {score}/5
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-400 mb-1">Rating</div>
              <div className={`text-sm font-semibold ${getScoreColor(score)}`}>
                {score <= 1.5 ? 'Poor' : score <= 2.5 ? 'Fair' : score <= 3.5 ? 'Good' : 'Excellent'}
              </div>
            </div>
          </div>
        </div>
      )}
      {keyTakeaways && keyTakeaways.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/80 p-4">
          <div className="mb-2 text-sm font-semibold text-slate-300">Key takeaways</div>
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-400">
            {keyTakeaways.map((t, i) => (
              <li key={`${i}-${t.slice(0, 40)}`}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      {reportType === 'trader_investment_plan' && tpsPlan && tpsPlan.trim().length > 0 && (
        <TpsPlanCard tpsPlan={tpsPlan} title="TPS v0.1 — Structured Trading Plan" />
      )}
      {reportType === 'investment_plan' && (bullViewpoint?.length || bearViewpoint?.length || neutralViewpoint?.length) ? (
        <div className="rounded-lg border border-slate-600 bg-slate-900/40 p-4 space-y-4">
          <div className="text-xs font-semibold uppercase tracking-widest text-slate-500 pb-1 border-b border-slate-700">
            Researcher Viewpoints
          </div>
          <div className="grid grid-cols-1 gap-4">
            {bullViewpoint && bullViewpoint.length > 0 && (
              <div className="rounded-lg border border-green-900/50 bg-green-950/30 p-4">
                <div className="mb-2 text-sm font-semibold text-green-400">Bull Viewpoint</div>
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                  {bullViewpoint.map((p, i) => (
                    <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
            {bearViewpoint && bearViewpoint.length > 0 && (
              <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4">
                <div className="mb-2 text-sm font-semibold text-red-400">Bear Viewpoint</div>
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                  {bearViewpoint.map((p, i) => (
                    <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
            {neutralViewpoint && neutralViewpoint.length > 0 && (
              <div className="rounded-lg border border-gray-500/50 bg-gray-700/40 p-4">
                <div className="mb-2 text-sm font-semibold text-gray-300">Neutral Viewpoint</div>
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                  {neutralViewpoint.map((p, i) => (
                    <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      ) : null}
      {reportType === 'final_trade_decision' && hasRiskViewpoints ? (
        <div className="rounded-lg border border-slate-600 bg-slate-900/40 p-4 space-y-4">
          <div className="text-xs font-semibold uppercase tracking-widest text-slate-500 pb-1 border-b border-slate-700">
            Analyst Viewpoints
          </div>
          {riskyViewpoint && riskyViewpoint.length > 0 && (
            <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 p-4">
              <div className="mb-2 text-sm font-semibold text-amber-400">Risky Analyst Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {riskyViewpoint.map((p, i) => (
                  <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {neutralViewpoint && neutralViewpoint.length > 0 && (
            <div className="rounded-lg border border-gray-500/50 bg-gray-700/40 p-4">
              <div className="mb-2 text-sm font-semibold text-gray-300">Neutral Analyst Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {neutralViewpoint.map((p, i) => (
                  <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {safeViewpoint && safeViewpoint.length > 0 && (
            <div className="rounded-lg border border-blue-900/50 bg-blue-950/30 p-4">
              <div className="mb-2 text-sm font-semibold text-blue-400">Safe Analyst Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {safeViewpoint.map((p, i) => (
                  <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : null}
      {hasContent && (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
        <div className="prose prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ node, ...props }) => <h1 className="text-3xl font-bold text-white mb-4" {...props} />,
            h2: ({ node, ...props }) => <h2 className="text-2xl font-semibold text-white mb-3 mt-6" {...props} />,
            h3: ({ node, ...props }) => <h3 className="text-xl font-semibold text-white mb-2 mt-4" {...props} />,
            p: ({ node, ...props }) => <p className="text-slate-300 mb-4 leading-relaxed" {...props} />,
            ul: ({ node, ...props }) => <ul className="list-disc list-inside text-slate-300 mb-4 space-y-2" {...props} />,
            ol: ({ node, ...props }) => <ol className="list-decimal list-outside pl-6 text-slate-300 mb-4 space-y-2" {...props} />,
            li: ({ node, ...props }) => <li className="text-slate-300" {...props} />,
            strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
            code: ({ node, className, children, ...props }) => {
              if (className === 'language-mermaid') {
                return <MermaidBlock code={String(children).trim()} />;
              }
              return <code className="bg-slate-900 px-2 py-1 rounded text-sm text-green-400" {...props}>{children}</code>;
            },
            pre: ({ node, ...props }) => (
              <pre className="bg-slate-900 p-4 rounded-lg overflow-x-auto mb-4" {...props} />
            ),
            table: ({ node, ...props }) => (
              <div className="overflow-x-auto my-4 rounded-lg border border-slate-600">
                <table className="min-w-full border-collapse text-sm" {...props} />
              </div>
            ),
            thead: ({ node, ...props }) => (
              <thead className="bg-slate-700/80 text-slate-200" {...props} />
            ),
            tbody: ({ node, ...props }) => (
              <tbody className="divide-y divide-slate-600" {...props} />
            ),
            tr: ({ node, ...props }) => (
              <tr className="hover:bg-slate-700/40 transition-colors" {...props} />
            ),
            th: ({ node, ...props }) => (
              <th className="px-4 py-3 text-left font-semibold text-white border-b border-slate-600" {...props} />
            ),
            td: ({ node, ...props }) => (
              <td className="px-4 py-3 text-slate-300" {...props} />
            ),
          }}
        >
          {renderedContent}
        </ReactMarkdown>
        </div>
      </div>
      )}
      {hasResources && <ReportResourcesSection resources={resources!} analysisDate={analysisDate} />}
      {hasAgentSteps && <ReportAgentTrajectorySection agentSteps={agentSteps!} canViewCost={canViewCost} />}
    </div>
  );
}
