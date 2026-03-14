import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReportTabs from '../components/ReportTabs';
import ReportViewer from '../components/ReportViewer';
import { API_BASE_URL } from '../services/api';

const REPORT_ORDER = [
  'market_report', 'sentiment_report', 'news_report', 'technical_report',
  'fundamentals_report', 'sec_report', 'investment_plan', 'trader_investment_plan', 'final_trade_decision',
];

interface SharedReportData {
  ticker: string;
  execution_id: number;
  report_date: string | null;
  reports: Record<string, {
    content?: string | null;
    score?: number | null;
    score_label?: string | null;
    key_takeaways?: string[];
    bull_viewpoint?: string[] | null;
    bear_viewpoint?: string[] | null;
    risky_viewpoint?: string[] | null;
    safe_viewpoint?: string[] | null;
    neutral_viewpoint?: string[] | null;
    tps_plan?: string | null;
    [key: string]: unknown;
  }>;
}

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
        const keys = Object.keys(json.reports || {});
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
  const reportScores: Record<string, { score: number | null; score_label: string | null }> = {};
  Object.entries(reports).forEach(([k, v]) => {
    reportScores[k] = { score: v.score ?? null, score_label: v.score_label ?? null };
  });

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="border-b border-gray-700 bg-gray-800/80 px-4 py-3">
        <div className="max-w-4xl mx-auto flex flex-wrap items-center justify-between gap-2">
          <Link to="/" className="text-lg font-semibold text-white hover:text-blue-400 transition-colors">
            Flowdeck
          </Link>
          <span className="text-gray-400 text-sm">
            Shared report · {data.ticker}
            {data.report_date && ` · ${data.report_date}`}
          </span>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">
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
              reportType={selectedReport ?? undefined}
              bullViewpoint={current?.bull_viewpoint ?? null}
              bearViewpoint={current?.bear_viewpoint ?? null}
              riskyViewpoint={current?.risky_viewpoint ?? null}
              safeViewpoint={current?.safe_viewpoint ?? null}
              neutralViewpoint={current?.neutral_viewpoint ?? null}
              tpsPlan={current?.tps_plan ?? null}
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
