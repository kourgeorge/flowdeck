import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReportData } from '../services/types';

const REPORT_LABELS: Record<string, string> = {
  market_report: 'Market',
  sentiment_report: 'Sentiment',
  news_report: 'News',
  fundamentals_report: 'Fundamentals',
  sec_report: 'SEC',
  technical_report: 'Technical',
  investment_plan: 'Research',
  trader_investment_plan: 'Trader',
  final_trade_decision: 'Risk Analysis',
};

const EVIDENCE_KEYS = ['market_report', 'sentiment_report', 'news_report', 'fundamentals_report', 'sec_report', 'technical_report'] as const;
const SYNTHESIS_KEYS = ['investment_plan', 'trader_investment_plan'] as const;
const DECISION_KEYS = ['final_trade_decision'] as const;

export interface HierarchicalMindMapProps {
  ticker: string;
  companyName?: string | null;
  recommendation: string | null;
  reports: Record<string, ReportData>;
}

function getScoreClass(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'text-gray-400';
  if (score < 5) return 'text-red-400';
  if (score <= 7) return 'text-yellow-400';
  return 'text-green-400';
}

function getRecommendationClass(rec: string | null): string {
  if (rec === 'BUY') return 'text-green-400';
  if (rec === 'SELL') return 'text-red-400';
  if (rec === 'HOLD') return 'text-yellow-400';
  return 'text-white';
}

export default function HierarchicalMindMap({ ticker, companyName, recommendation, reports }: HierarchicalMindMapProps) {
  const [selectedReportKey, setSelectedReportKey] = useState<string | null>(null);

  if (!reports || Object.keys(reports).length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center text-gray-400">
        No report data available
      </div>
    );
  }

  const evidenceNodes = EVIDENCE_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));
  const synthesisNodes = SYNTHESIS_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));
  const decisionNodes = DECISION_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));

  const selectedData = selectedReportKey ? reports[selectedReportKey] : null;
  const selectedLabel = selectedReportKey ? (REPORT_LABELS[selectedReportKey] ?? selectedReportKey.replace(/_/g, ' ')) : null;

  const renderNode = (reportKey: string, data: ReportData) => {
    const label = REPORT_LABELS[reportKey] ?? reportKey.replace(/_/g, ' ');
    const score = data.score;
    const showScore = reportKey !== 'trader_investment_plan';
    const scoreLabel = showScore && score != null ? `${score}/10` : '—';
    const isSelected = selectedReportKey === reportKey;
    const allTakeaways = data.key_takeaways ?? [];
    const keyPoints = allTakeaways.slice(0, 1);
    const moreCount = allTakeaways.length > 1 ? allTakeaways.length - 1 : 0;

    return (
      <button
        key={reportKey}
        type="button"
        onClick={() => setSelectedReportKey((prev) => (prev === reportKey ? null : reportKey))}
        className={`w-full text-left bg-gray-800 border rounded-md p-2.5 mb-1.5 last:mb-0 transition-colors min-h-[4rem] flex flex-col gap-1.5 min-w-0 ${
          isSelected ? 'border-blue-500 ring-1 ring-blue-500/50' : 'border-gray-700 hover:border-gray-600'
        }`}
      >
        <div className="flex items-center justify-between gap-2 shrink-0 min-w-0 w-full">
          <span className="text-sm font-semibold text-slate-400 min-w-0 break-words">{label}</span>
          <span className={`text-xs font-bold flex-shrink-0 ${getScoreClass(score)}`}>{scoreLabel}</span>
        </div>
        {keyPoints.length > 0 && (
          <>
            <ul className="w-full min-w-0 list-none pl-0 space-y-1">
              {keyPoints.map((item, i) => (
                <li key={i} className="w-full min-w-0">
                  <span className="text-xs text-slate-300 leading-snug line-clamp-2 break-words block">{item}</span>
                </li>
              ))}
            </ul>
            {moreCount > 0 && (
              <span className="text-[0.65rem] text-slate-500 italic">+{moreCount} more</span>
            )}
          </>
        )}
      </button>
    );
  };

  return (
    <div className="w-full">
      <div className="text-center">
        <div className="inline-block text-center py-3.5 px-6 border-2 border-gray-700 rounded-lg bg-gray-800 mb-6">
          <div className="text-xl font-bold text-slate-100">{ticker}</div>
          <div className={`text-sm font-semibold mt-0.5 ${getRecommendationClass(recommendation)}`}>
            {recommendation ?? '—'}
          </div>
          {companyName && <div className="text-xs text-slate-400 mt-1">{companyName}</div>}
        </div>
      </div>
      <div className="flex flex-col items-center w-full tree">
        <div className="connector wide w-full max-w-4xl h-0.5 bg-slate-500 mx-auto mb-0" aria-hidden />
        <div className="flex w-full items-center mb-2">
          <div className="flex-1 min-w-0" />
          <div className="connector w-0.5 h-4 bg-slate-500 shrink-0 rounded-full" aria-hidden />
          <div className="flex-1 min-w-0" />
        </div>
        {/* Evidence: one row of nodes */}
        <div className="row flex flex-col items-center w-full gap-2 mb-2">
          {evidenceNodes.length > 0 ? (
            <div className="flex flex-wrap justify-center gap-2 w-full">
              {evidenceNodes.map(({ key, data }) => (
                <div key={key} className="min-w-[220px] flex-1 max-w-[280px]">{renderNode(key, data)}</div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500">—</div>
          )}
        </div>
        <div className="row flex flex-col items-center w-full gap-2 mb-2">
          <div className="flex w-full items-center mb-0">
            <div className="flex-1 min-w-0" />
            <div className="connector w-0.5 h-5 bg-slate-500 shrink-0 rounded-full" aria-hidden />
            <div className="flex-1 min-w-0 flex items-center justify-start pl-2">
              <span className="level-label text-[0.7rem] font-bold uppercase tracking-wider text-slate-400">Synthesis</span>
            </div>
          </div>
          <div className="flex flex-wrap justify-center gap-2 w-full">
            {synthesisNodes.length > 0 ? synthesisNodes.map(({ key, data }) => (
              <div key={key} className="min-w-[220px] flex-1 max-w-[280px]">{renderNode(key, data)}</div>
            )) : <div className="text-xs text-slate-500">—</div>}
          </div>
        </div>
        <div className="row flex flex-col items-center w-full gap-2 mb-2">
          <div className="flex w-full items-center mb-0">
            <div className="flex-1 min-w-0" />
            <div className="connector w-0.5 h-5 bg-slate-500 shrink-0 rounded-full" aria-hidden />
            <div className="flex-1 min-w-0 flex items-center justify-start pl-2">
              <span className="level-label text-[0.7rem] font-bold uppercase tracking-wider text-slate-400">Decision</span>
            </div>
          </div>
          <div className="flex flex-wrap justify-center gap-2 w-full">
            {decisionNodes.map(({ key, data }) => (
              <div key={key} className="min-w-[220px] flex-1 max-w-[280px]">{renderNode(key, data)}</div>
            ))}
            <div className="min-w-[220px] flex-1 max-w-[280px]">
              <div className="bg-slate-900 border border-gray-700 rounded-md p-2.5 min-h-[4rem] flex flex-col justify-center">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-sm font-semibold text-slate-400">Final</span>
                  <span className={`text-xs font-bold flex-shrink-0 ${getRecommendationClass(recommendation)}`}>{recommendation ?? '—'}</span>
                </div>
                <div className="text-xs text-slate-400 leading-snug">Recommendation after full pipeline.</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {selectedData && selectedLabel && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          role="dialog"
          aria-modal
          aria-labelledby="mindmap-modal-title"
          onClick={() => setSelectedReportKey(null)}
        >
          <div
            className="bg-gray-800 border border-gray-700 rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between shrink-0 px-4 py-3 border-b border-gray-700">
              <h2 id="mindmap-modal-title" className="text-[0.72rem] font-bold uppercase tracking-wide text-slate-500">
                {selectedLabel} — Key Takeaways
              </h2>
              <button
                type="button"
                onClick={() => setSelectedReportKey(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-gray-700 transition-colors"
                aria-label="Close"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="overflow-y-auto p-4 space-y-4">
              {selectedData.key_takeaways && selectedData.key_takeaways.length > 0 ? (
                <ul className="text-sm text-slate-300 leading-relaxed pl-5 list-disc space-y-1">
                  {selectedData.key_takeaways.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No key takeaways for this report.</p>
              )}

              {selectedReportKey === 'investment_plan' && (
                <div className="space-y-3 pt-2 border-t border-gray-700">
                  <h4 className="text-[0.72rem] font-bold uppercase tracking-wide text-slate-500">Bullish &amp; bearish</h4>
                  {selectedData.bull_viewpoint && selectedData.bull_viewpoint.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-green-400/90 mb-1">Bullish</div>
                      <ul className="text-sm text-slate-300 leading-relaxed pl-5 list-disc space-y-0.5">
                        {selectedData.bull_viewpoint.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedData.bear_viewpoint && selectedData.bear_viewpoint.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-red-400/90 mb-1">Bearish</div>
                      <ul className="text-sm text-slate-300 leading-relaxed pl-5 list-disc space-y-0.5">
                        {selectedData.bear_viewpoint.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(!selectedData.bull_viewpoint || selectedData.bull_viewpoint.length === 0) &&
                    (!selectedData.bear_viewpoint || selectedData.bear_viewpoint.length === 0) && (
                    <p className="text-sm text-slate-500">No bullish/bearish viewpoints in this report.</p>
                  )}
                </div>
              )}

              {selectedReportKey === 'trader_investment_plan' && selectedData.tps_plan && selectedData.tps_plan.trim().length > 0 && (
                <div className="space-y-3 pt-2 border-t border-gray-700">
                  <h4 className="text-[0.72rem] font-bold uppercase tracking-wide text-slate-500">TPS — Structured Trading Plan</h4>
                  <div className="rounded-lg border border-indigo-700/60 bg-indigo-950/30 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2.5 border-b border-indigo-700/40 bg-indigo-900/30">
                      <span className="text-xs font-semibold uppercase tracking-widest text-indigo-300">TPS v0.1</span>
                      <span className="text-xs text-indigo-500 font-mono">JSON</span>
                    </div>
                    <div className="p-4">
                      <pre className="bg-slate-900 rounded-lg p-4 overflow-x-auto text-sm font-mono leading-relaxed whitespace-pre text-slate-300">
                        {(() => {
                          let parsed: unknown = null;
                          try {
                            parsed = JSON.parse(selectedData.tps_plan!);
                          } catch {
                            /* not JSON */
                          }
                          return parsed !== null ? JSON.stringify(parsed, null, 2) : selectedData.tps_plan;
                        })()}
                      </pre>
                    </div>
                  </div>
                </div>
              )}

              {selectedReportKey === 'final_trade_decision' && (
                <div className="space-y-3 pt-2 border-t border-gray-700">
                  <h4 className="text-[0.72rem] font-bold uppercase tracking-wide text-slate-500">Analyst viewpoints</h4>
                  {selectedData.risky_viewpoint && selectedData.risky_viewpoint.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-amber-400/90 mb-1">Risky</div>
                      <ul className="text-sm text-slate-300 leading-relaxed pl-5 list-disc space-y-0.5">
                        {selectedData.risky_viewpoint.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedData.safe_viewpoint && selectedData.safe_viewpoint.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-green-400/90 mb-1">Safe</div>
                      <ul className="text-sm text-slate-300 leading-relaxed pl-5 list-disc space-y-0.5">
                        {selectedData.safe_viewpoint.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedData.neutral_viewpoint && selectedData.neutral_viewpoint.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-slate-400 mb-1">Neutral</div>
                      <ul className="text-sm text-slate-300 leading-relaxed pl-5 list-disc space-y-0.5">
                        {selectedData.neutral_viewpoint.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(!selectedData.risky_viewpoint || selectedData.risky_viewpoint.length === 0) &&
                    (!selectedData.safe_viewpoint || selectedData.safe_viewpoint.length === 0) &&
                    (!selectedData.neutral_viewpoint || selectedData.neutral_viewpoint.length === 0) && (
                    <p className="text-sm text-slate-500">No analyst viewpoints in this report.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
