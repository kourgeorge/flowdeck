import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ReportViewerProps {
  content: string | null;
  score?: number | null;
  scoreLabel?: string | null;
  keyTakeaways?: string[];
  reportType?: string | null;
  bullViewpoint?: string[] | null;
  bearViewpoint?: string[] | null;
  riskyViewpoint?: string[] | null;
  safeViewpoint?: string[] | null;
  neutralViewpoint?: string[] | null;
}

const REPORT_METADATA: Record<string, { title: string; contains: string; aspects: string; methodology: string }> = {
  market_report: {
    title: 'Market',
    contains: 'A technical analysis of price action, trends, and momentum. The report interprets multiple indicators, explains their signals in context, and concludes with a summary table and a Market Score (1–10).',
    aspects: 'Up to 8 complementary indicators: 50-day SMA, 200-day SMA, 10-day EMA (trend); MACD, MACD Signal, MACD Histogram (momentum); RSI (overbought/oversold); Bollinger Bands; ATR (volatility); VWMA (volume-weighted). Each is analyzed for trend direction, momentum strength, and support/resistance implications.',
    methodology: 'First in the analysis chain. The Market Analyst uses historical price data and indicator values, selects relevant indicators, interprets their signals together, and writes a detailed narrative. The goal is fine-grained analysis that avoids redundancy and explains why each indicator matters for the current market.',
  },
  sentiment_report: {
    title: 'Sentiment Analysis',
    contains: 'An analysis of public sentiment, social media discussions, and company-specific news from the past week. Assigns a Sentiment Score (1–10).',
    aspects: 'Social media posts and discussions, sentiment polarity (bullish vs bearish), recent company news, public perception, community engagement, and sentiment trends. All available sources are used to assess the overall tone around the security.',
    methodology: 'Runs early in the chain. The Social Analyst gathers company-related news and social discussions, synthesizes what people are saying and feeling, and produces a report with an overall sentiment assessment.',
  },
  news_report: {
    title: 'News',
    contains: 'A report on the current state of the world relevant to trading and macroeconomics. Covers global economic trends, market-moving events, and company-specific news from the past week.',
    aspects: 'Inflation and interest rates, supply chain issues, U.S. and global market performance, oil prices, geopolitical tensions, broader investor sentiment, and company-specific headlines. Focus is on how macro and company-level news may impact the security.',
    methodology: 'Runs in the analyst chain. The News Analyst gathers company-specific news and broader macroeconomic headlines, synthesizes developments into a coherent narrative, and assesses their implications for the security.',
  },
  fundamentals_report: {
    title: 'Fundamentals',
    contains: 'A view of the company\'s financial health: financial documents, company profile, and financial history. Assigns a Fundamentals Score (1–10).',
    aspects: 'Company overview, balance sheet, cash flow, income statement, valuation ratios, 52-week range, moving averages, profitability trends, revenue growth, debt levels, and financial stability. When data is sparse (e.g. for indices), the report reflects what is available and any limitations.',
    methodology: 'Runs in the analyst chain. The Fundamentals Analyst reviews financial statements and key metrics, evaluates financial health and sustainability, and produces a report. For indices or thinly covered securities, the analysis is limited to available data.',
  },
  technical_report: {
    title: 'Technical Analysis',
    contains: 'An advanced technical report on regime, support/resistance, and divergences. Provides actionable recommendations with specific price levels.',
    aspects: 'Divergence detection (bullish/bearish between price and RSI or MACD); regime detection (trending vs ranging, volatility level); support/resistance via price clustering, volume profile, recent highs/lows, and moving averages; entry/exit targets and stop-loss levels.',
    methodology: 'Runs in the analyst chain when technical analysis is selected. The Technical Analyst follows a sequence: assess market regime, identify support and resistance, check for divergences, then synthesize findings into recommendations and a Technical Score (1–10).',
  },
  investment_plan: {
    title: 'Research',
    contains: 'A definitive investment recommendation (Buy/Sell/Hold) with rationale and strategic actions. Includes expected return ranges (base, bear, bull) and a Recommendation Score (1–10).',
    aspects: 'Summary of key points from both Bull and Bear; which side the judge aligns with and why; strategic actions, position sizing, and monitoring; expected, bear-case, and bull-case percentage returns from current price over the investment horizon.',
    methodology: 'Produced after the Bull vs Bear debate. The Bull and Bear researchers take turns arguing, drawing on all prior reports. The Research Manager acts as judge, evaluates both sides, commits to Buy/Sell/Hold, and produces the investment plan with expected return scenarios.',
  },
  final_trade_decision: {
    title: 'Risk & Confidence',
    contains: 'The ultimate BUY/SELL/HOLD decision with detailed reasoning. Includes a Confidence Score (1–10) and key takeaways for traders.',
    aspects: 'Summary of the Risky, Safe, and Neutral analysts\' arguments; rationale for the final decision; refined plan incorporating risk insights; lessons from past decisions; and 3–5 key takeaways.',
    methodology: 'Final step in the analysis. The Risky, Safe, and Neutral analysts debate the Trader\'s plan—each arguing for high-risk, low-risk, or balanced approaches using all prior reports. The Risk Judge weighs their arguments, refines the plan, and produces the final trade decision with a confidence score. This is the end of the pipeline.',
  },
};

function ReportMoreInfo({ reportType }: { reportType: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const meta = REPORT_METADATA[reportType];
  if (!meta) return null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/60 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-700/40 transition-colors"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-slate-300">
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

export default function ReportViewer({ content, score, scoreLabel, keyTakeaways, reportType, bullViewpoint, bearViewpoint, riskyViewpoint, safeViewpoint, neutralViewpoint }: ReportViewerProps) {
  const hasContent = content && content.trim().length > 0;
  const hasBullBear = (bullViewpoint && bullViewpoint.length > 0) || (bearViewpoint && bearViewpoint.length > 0);
  const hasRiskViewpoints = (riskyViewpoint && riskyViewpoint.length > 0) || (safeViewpoint && safeViewpoint.length > 0) || (neutralViewpoint && neutralViewpoint.length > 0);
  const hasViewpoints = hasBullBear || hasRiskViewpoints;
  if (!hasContent && !hasViewpoints) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center text-gray-400">
        No report content available
      </div>
    );
  }

  const getScoreColor = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'text-gray-400';
    if (score <= 3) return 'text-red-400';
    if (score <= 5) return 'text-yellow-400';
    if (score <= 7) return 'text-blue-400';
    return 'text-green-400';
  };

  const getScoreBgColor = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'bg-gray-700';
    if (score <= 3) return 'bg-red-500/20 border-red-500/50';
    if (score <= 5) return 'bg-yellow-500/20 border-yellow-500/50';
    if (score <= 7) return 'bg-blue-500/20 border-blue-500/50';
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
                {score}/10
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-400 mb-1">Rating</div>
              <div className={`text-sm font-semibold ${getScoreColor(score)}`}>
                {score <= 3 ? 'Poor' : score <= 5 ? 'Fair' : score <= 7 ? 'Good' : 'Excellent'}
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
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
      {reportType === 'investment_plan' && (bullViewpoint?.length || bearViewpoint?.length) ? (
        <div className="space-y-4">
          {bullViewpoint && bullViewpoint.length > 0 && (
            <div className="rounded-lg border border-green-900/50 bg-green-950/30 p-4">
              <div className="mb-2 text-sm font-semibold text-green-400">Bull Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {bullViewpoint.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {bearViewpoint && bearViewpoint.length > 0 && (
            <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4">
              <div className="mb-2 text-sm font-semibold text-red-400">Bear Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {bearViewpoint.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : null}
      {reportType === 'final_trade_decision' && hasRiskViewpoints ? (
        <div className="space-y-4">
          {riskyViewpoint && riskyViewpoint.length > 0 && (
            <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 p-4">
              <div className="mb-2 text-sm font-semibold text-amber-400">Risky Analyst Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {riskyViewpoint.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {safeViewpoint && safeViewpoint.length > 0 && (
            <div className="rounded-lg border border-blue-900/50 bg-blue-950/30 p-4">
              <div className="mb-2 text-sm font-semibold text-blue-400">Safe Analyst Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {safeViewpoint.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {neutralViewpoint && neutralViewpoint.length > 0 && (
            <div className="rounded-lg border border-slate-600 bg-slate-800/50 p-4">
              <div className="mb-2 text-sm font-semibold text-slate-400">Neutral Analyst Viewpoint</div>
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                {neutralViewpoint.map((p, i) => (
                  <li key={i}>{p}</li>
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
            code: ({ node, ...props }) => (
              <code className="bg-slate-900 px-2 py-1 rounded text-sm text-green-400" {...props} />
            ),
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
          {content}
        </ReactMarkdown>
        </div>
      </div>
      )}
    </div>
  );
}

