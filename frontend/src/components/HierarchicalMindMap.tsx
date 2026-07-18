import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReportData } from '../services/types';
import { getScoreColor } from './AspectSpiderChart';
import TpsPlanCard from './TpsPlanCard';

const REPORT_LABELS: Record<string, string> = {
  market_report: 'Market',
  sentiment_report: 'News & Sentiment',
  fundamentals_report: 'Fundamentals',
  sec_report: 'SEC',
  technical_report: 'Technical',
  valuation_report: 'Valuation',
  investment_plan: 'Research',
  trader_investment_plan: 'Trader',
  final_trade_decision: 'Risk Analysis',
};

// Evidence analysts are split across two lines: market signals on the first line,
// financial/regulatory analysis on the second.
const EVIDENCE_ROW_1_KEYS = ['market_report', 'technical_report', 'sentiment_report'] as const;
const EVIDENCE_ROW_2_KEYS = ['fundamentals_report', 'sec_report', 'valuation_report'] as const;
// Research Manager (investment_plan) is the authoritative decision; it sits next to the
// Trader plan on the third line. final_trade_decision is retained on a further line for
// historical runs produced before the Research/Risk report merge.
const SYNTHESIS_KEYS = ['investment_plan', 'trader_investment_plan'] as const;
const DECISION_KEYS = ['final_trade_decision'] as const;

export interface HierarchicalMindMapProps {
  ticker: string;
  companyName?: string | null;
  recommendation: string | null;
  reports: Record<string, ReportData>;
  /** When provided, the modal shows a "Read full report" link that opens this report tab */
  onOpenReport?: (reportKey: string) => void;
}

function getRecommendationClass(rec: string | null): string {
  if (rec === 'BUY') return 'text-green-400';
  if (rec === 'SELL') return 'text-red-400';
  if (rec === 'HOLD') return 'text-yellow-400';
  return 'text-white';
}

export default function HierarchicalMindMap({ ticker, companyName, recommendation, reports, onOpenReport }: HierarchicalMindMapProps) {
  const [selectedReportKey, setSelectedReportKey] = useState<string | null>(null);

  if (!reports || Object.keys(reports).length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center text-gray-400">
        No report data available
      </div>
    );
  }

  const evidenceRow1Nodes = EVIDENCE_ROW_1_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));
  const evidenceRow2Nodes = EVIDENCE_ROW_2_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));
  const synthesisNodes = SYNTHESIS_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));
  const decisionNodes = DECISION_KEYS.filter((k) => reports[k]).map((key) => ({ key, data: reports[key]! }));

  const selectedData = selectedReportKey ? reports[selectedReportKey] : null;
  const selectedLabel = selectedReportKey ? (REPORT_LABELS[selectedReportKey] ?? selectedReportKey.replace(/_/g, ' ')) : null;

  const renderNode = (reportKey: string, data: ReportData) => {
    const label = REPORT_LABELS[reportKey] ?? reportKey.replace(/_/g, ' ');
    const score = data.score;
    const showScore = reportKey !== 'trader_investment_plan';
    const scoreLabel = showScore && score != null ? `${score}/5` : '—';
    const isSelected = selectedReportKey === reportKey;
    const allTakeaways = data.key_takeaways ?? [];
    const keyPoints = allTakeaways.slice(0, 1);
    const moreCount = allTakeaways.length > 1 ? allTakeaways.length - 1 : 0;

    return (
      <button
        key={reportKey}
        type="button"
        onClick={() => setSelectedReportKey((prev) => (prev === reportKey ? null : reportKey))}
        className={`w-full h-[10rem] text-left bg-gray-800 border rounded-md p-2.5 mb-1.5 last:mb-0 transition-colors flex flex-col gap-1.5 min-w-0 ${
          isSelected ? 'border-blue-500 ring-1 ring-blue-500/50' : 'border-gray-700 hover:border-gray-600'
        }`}
      >
        <div className="flex items-center justify-between gap-2 shrink-0 min-w-0 w-full">
          <span className="text-sm font-semibold text-slate-400 min-w-0 break-words">{label}</span>
          <span className={`text-xs font-bold flex-shrink-0 ${getScoreColor(score)}`}>{scoreLabel}</span>
        </div>
        {keyPoints.length > 0 && (
          <>
            <ul className="w-full min-w-0 list-none pl-0 space-y-1 shrink-0">
              {keyPoints.map((item, i) => (
                <li key={i} className="w-full min-w-0">
                  <span className="text-sm text-slate-300 leading-snug line-clamp-3 break-words block">{item}</span>
                </li>
              ))}
            </ul>
            {moreCount > 0 && (
              <span className="text-[0.65rem] text-slate-500 italic mt-auto shrink-0">+{moreCount} more</span>
            )}
          </>
        )}
      </button>
    );
  };

  return (
    <div className="w-full">
      <div className="text-center">
        <div className="inline-block text-center py-3.5 px-6 border-2 border-gray-700 rounded-lg bg-gray-900 mb-6">
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
        {/* Evidence line 1: market signals (Market, Technical, News & Sentiment) */}
        <div className="row flex flex-col items-center w-full gap-2 mb-2">
          {evidenceRow1Nodes.length > 0 ? (
            <div className="flex flex-wrap justify-center gap-2 w-full">
              {evidenceRow1Nodes.map(({ key, data }) => (
                <div key={key} className="min-w-[220px] flex-1 max-w-[280px]">{renderNode(key, data)}</div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500">—</div>
          )}
        </div>
        {/* Evidence line 2: financial & regulatory (Fundamentals, SEC, Valuation) */}
        {evidenceRow2Nodes.length > 0 && (
          <div className="row flex flex-col items-center w-full gap-2 mb-2">
            <div className="flex flex-wrap justify-center gap-2 w-full">
              {evidenceRow2Nodes.map(({ key, data }) => (
                <div key={key} className="min-w-[220px] flex-1 max-w-[280px]">{renderNode(key, data)}</div>
              ))}
            </div>
          </div>
        )}
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
        {decisionNodes.length > 0 && (
          <div className="row flex flex-col items-center w-full gap-2 mb-2">
            <div className="flex w-full items-center mb-0">
              <div className="flex-1 min-w-0" />
              <div className="connector w-0.5 h-5 bg-slate-500 shrink-0 rounded-full" aria-hidden />
              <div className="flex-1 min-w-0 flex items-center justify-start pl-2">
                <span className="level-label text-[0.7rem] font-bold uppercase tracking-wider text-slate-400">Risk</span>
              </div>
            </div>
            <div className="flex flex-wrap justify-center gap-2 w-full">
              {decisionNodes.map(({ key, data }) => (
                <div key={key} className="min-w-[220px] flex-1 max-w-[280px]">{renderNode(key, data)}</div>
              ))}
            </div>
          </div>
        )}
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
            <div className="flex items-center justify-between shrink-0 px-4 py-3 border-b border-gray-700 gap-3">
              <h2 id="mindmap-modal-title" className="text-[0.72rem] font-bold uppercase tracking-wide text-slate-500">
                {selectedLabel} — Key Takeaways
              </h2>
              <div className="flex items-center gap-2">
                {onOpenReport && selectedReportKey && (
                  <button
                    type="button"
                    onClick={() => {
                      onOpenReport(selectedReportKey);
                      setSelectedReportKey(null);
                    }}
                    className="text-xs font-medium text-blue-400 hover:text-blue-300 underline underline-offset-2"
                  >
                    Read full report
                  </button>
                )}
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

              {selectedReportKey === 'investment_plan' && (selectedData.bull_viewpoint?.length || selectedData.bear_viewpoint?.length || selectedData.neutral_viewpoint?.length) ? (
                <div className="rounded-lg border border-slate-600 bg-slate-900/40 p-4 space-y-4">
                  <div className="text-xs font-semibold uppercase tracking-widest text-slate-500 pb-1 border-b border-slate-700">
                    Researcher Viewpoints
                  </div>
                  <div className="grid grid-cols-1 gap-4">
                    {selectedData.bull_viewpoint && selectedData.bull_viewpoint.length > 0 && (
                      <div className="rounded-lg border border-green-900/50 bg-green-950/30 p-4">
                        <div className="mb-2 text-sm font-semibold text-green-400">Bull Viewpoint</div>
                        <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                          {selectedData.bull_viewpoint.map((p, i) => (
                            <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selectedData.bear_viewpoint && selectedData.bear_viewpoint.length > 0 && (
                      <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4">
                        <div className="mb-2 text-sm font-semibold text-red-400">Bear Viewpoint</div>
                        <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                          {selectedData.bear_viewpoint.map((p, i) => (
                            <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selectedData.neutral_viewpoint && selectedData.neutral_viewpoint.length > 0 && (
                      <div className="rounded-lg border border-gray-500/50 bg-gray-700/40 p-4">
                        <div className="mb-2 text-sm font-semibold text-gray-300">Neutral Viewpoint</div>
                        <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                          {selectedData.neutral_viewpoint.map((p, i) => (
                            <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ) : selectedReportKey === 'investment_plan' ? (
                <p className="text-sm text-slate-500">No researcher viewpoints in this report.</p>
              ) : null}

              {selectedReportKey === 'trader_investment_plan' && selectedData.tps_plan && selectedData.tps_plan.trim().length > 0 && (
                <div className="space-y-3 pt-2 border-t border-gray-700">
                  <h4 className="text-[0.72rem] font-bold uppercase tracking-wide text-slate-500">TPS</h4>
                  <TpsPlanCard tpsPlan={selectedData.tps_plan!} />
                </div>
              )}

              {selectedReportKey === 'final_trade_decision' && (selectedData.risky_viewpoint?.length || selectedData.safe_viewpoint?.length || selectedData.neutral_viewpoint?.length) ? (
                <div className="rounded-lg border border-slate-600 bg-slate-900/40 p-4 space-y-4">
                  <div className="text-xs font-semibold uppercase tracking-widest text-slate-500 pb-1 border-b border-slate-700">
                    Analyst Viewpoints
                  </div>
                  {selectedData.risky_viewpoint && selectedData.risky_viewpoint.length > 0 && (
                    <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 p-4">
                      <div className="mb-2 text-sm font-semibold text-amber-400">Risky Analyst Viewpoint</div>
                      <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                        {selectedData.risky_viewpoint.map((p, i) => (
                          <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedData.neutral_viewpoint && selectedData.neutral_viewpoint.length > 0 && (
                    <div className="rounded-lg border border-gray-500/50 bg-gray-700/40 p-4">
                      <div className="mb-2 text-sm font-semibold text-gray-300">Neutral Analyst Viewpoint</div>
                      <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                        {selectedData.neutral_viewpoint.map((p, i) => (
                          <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedData.safe_viewpoint && selectedData.safe_viewpoint.length > 0 && (
                    <div className="rounded-lg border border-blue-900/50 bg-blue-950/30 p-4">
                      <div className="mb-2 text-sm font-semibold text-blue-400">Safe Analyst Viewpoint</div>
                      <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                        {selectedData.safe_viewpoint.map((p, i) => (
                          <li key={`${i}-${p.slice(0, 40)}`}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : selectedReportKey === 'final_trade_decision' ? (
                <p className="text-sm text-slate-500">No analyst viewpoints in this report.</p>
              ) : null}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
