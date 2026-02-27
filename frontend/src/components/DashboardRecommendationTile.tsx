import { Link } from 'react-router-dom';

interface DashboardRecommendationTileProps {
  ticker: string;
  recommendation: string | null;
  confidence: number | null;
  reportDate: string | null;
  hasReport: boolean;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export default function DashboardRecommendationTile({
  ticker,
  recommendation,
  confidence,
  reportDate,
  hasReport,
}: DashboardRecommendationTileProps) {
  const getAccentBorderClass = (rec: string) => {
    switch (rec.toUpperCase()) {
      case 'BUY':
        return 'border-l-green-500';
      case 'SELL':
        return 'border-l-red-500';
      case 'HOLD':
        return 'border-l-amber-500';
      default:
        return 'border-l-gray-500';
    }
  };

  const getBadgeClass = (rec: string) => {
    switch (rec.toUpperCase()) {
      case 'BUY':
        return 'bg-green-500/20 text-green-400 border-green-500/40';
      case 'SELL':
        return 'bg-red-500/20 text-red-400 border-red-500/40';
      case 'HOLD':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/40';
    }
  };

  if (!hasReport || !recommendation) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 h-full flex flex-col justify-center min-h-[120px]">
        <p className="text-gray-500 text-sm mb-2">No report yet</p>
        <Link
          to={`/tickers/${ticker}`}
          className="text-sm text-blue-400 hover:text-blue-300 font-medium"
        >
          Generate report →
        </Link>
      </div>
    );
  }

  return (
    <div
      className={`bg-gray-800 rounded-lg border border-gray-700 border-l-4 ${getAccentBorderClass(recommendation)} p-4 h-full flex flex-col justify-center min-h-[120px]`}
    >
      <div className="text-xs text-gray-400 mb-1">Recommendation</div>
      <span className={`inline-flex w-fit px-2.5 py-1 rounded text-sm font-semibold border ${getBadgeClass(recommendation)}`}>
        {recommendation}
      </span>
      {confidence != null && (
        <div className="text-xs text-gray-400 mt-2">
          Confidence: {(confidence * 100).toFixed(0)}%
        </div>
      )}
      <div className="text-xs text-gray-500 mt-0.5">{formatDate(reportDate)}</div>
    </div>
  );
}
