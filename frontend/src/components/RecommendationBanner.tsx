import type { Recommendation } from '../services/types';

interface RecommendationBannerProps {
  recommendation: Recommendation | null;
}

export default function RecommendationBanner({ recommendation }: RecommendationBannerProps) {
  if (!recommendation) {
    return null;
  }

  const getColorClass = (rec: string) => {
    switch (rec.toUpperCase()) {
      case 'BUY':
        return 'bg-gradient-to-r from-green-500 to-green-600';
      case 'SELL':
        return 'bg-gradient-to-r from-red-500 to-red-600';
      case 'HOLD':
        return 'bg-gradient-to-r from-hold to-yellow-600';
      default:
        return 'bg-gray-600';
    }
  };

  return (
    <div className={`${getColorClass(recommendation.recommendation)} rounded-lg p-6 mb-6 text-white`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm opacity-90 mb-1">Recommendation</div>
          <div className="text-4xl font-bold">{recommendation.recommendation}</div>
          {recommendation.confidence && (
            <div className="text-sm opacity-75 mt-1">
              Confidence: {(recommendation.confidence * 100).toFixed(0)}%
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-sm opacity-90">Source</div>
          <div className="text-lg font-semibold">{recommendation.source.replace('_', ' ')}</div>
          <div className="text-sm opacity-75 mt-1">{recommendation.date}</div>
        </div>
      </div>
    </div>
  );
}

