import { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../services/api';

// Collapsible info component
function CalculationMethodology() {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <div className="mb-4 bg-gray-700/30 rounded-lg overflow-hidden border border-gray-600/30">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-medium text-gray-300">How are Sentiment & Confidence calculated?</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {isExpanded && (
        <div className="p-4 pt-0 space-y-4 text-sm text-gray-300">
          {/* Overall Sentiment */}
          <div>
            <h4 className="font-semibold text-white mb-2 flex items-center gap-2">
              <span className="w-2 h-2 bg-purple-400 rounded-full"></span>
              Overall Sentiment (0-100%)
            </h4>
            <p className="text-gray-400 mb-2">
              Aggregated probability from relevant Polymarket prediction markets, weighted by:
            </p>
            <ul className="space-y-1 ml-4 text-gray-400">
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">•</span>
                <span><strong className="text-gray-300">Trading Volume:</strong> Markets with higher volume (more money backing predictions) carry more weight</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">•</span>
                <span><strong className="text-gray-300">Relevance Score:</strong> How closely the market relates to the stock (direct mentions score higher)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">•</span>
                <span><strong className="text-gray-300">Time Decay:</strong> Near-term markets (resolving soon) are weighted higher than long-term ones</span>
              </li>
            </ul>
            <div className="mt-2 p-2 bg-gray-800/50 rounded text-xs text-gray-400">
              <strong className="text-gray-300">Scale:</strong> 0-40% = Bearish, 40-60% = Neutral, 60-100% = Bullish
            </div>
          </div>

          {/* Confidence */}
          <div>
            <h4 className="font-semibold text-white mb-2 flex items-center gap-2">
              <span className="w-2 h-2 bg-blue-400 rounded-full"></span>
              Confidence (0-100%)
            </h4>
            <p className="text-gray-400 mb-2">
              Measures the reliability of the sentiment signal based on:
            </p>
            <ul className="space-y-1 ml-4 text-gray-400">
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">•</span>
                <span><strong className="text-gray-300">Total Trading Volume:</strong> Higher total volume across all markets = higher confidence</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">•</span>
                <span><strong className="text-gray-300">Market Liquidity:</strong> More liquid markets indicate stronger conviction</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">•</span>
                <span><strong className="text-gray-300">Number of Markets:</strong> More relevant markets provide a more robust signal</span>
              </li>
            </ul>
            <div className="mt-2 p-2 bg-gray-800/50 rounded text-xs text-gray-400">
              <strong className="text-gray-300">Formula:</strong> Confidence = min(log₁₀(total_volume + 1) / 6, 1.0)
              <br />
              <span className="text-gray-500">Example: $1M volume ≈ 100% confidence, $100K ≈ 83% confidence</span>
            </div>
          </div>

          {/* Market Selection */}
          <div>
            <h4 className="font-semibold text-white mb-2 flex items-center gap-2">
              <span className="w-2 h-2 bg-green-400 rounded-full"></span>
              Market Selection Process
            </h4>
            <ol className="space-y-1 ml-4 text-gray-400 list-decimal">
              <li><strong className="text-gray-300">Narrative Mapping:</strong> Generate relevant search queries (company name, sector, macro factors)</li>
              <li><strong className="text-gray-300">Market Fetching:</strong> Search Polymarket for markets matching these narratives</li>
              <li><strong className="text-gray-300">Relevance Scoring:</strong> Score each market on keyword match, liquidity, time relevance, and clarity</li>
              <li><strong className="text-gray-300">Diversity Filtering:</strong> Select top markets while ensuring topic diversity</li>
              <li><strong className="text-gray-300">Sentiment Aggregation:</strong> Calculate weighted average of market probabilities</li>
            </ol>
          </div>

          {/* Why This Matters */}
          <div className="pt-3 border-t border-gray-600/30">
            <h4 className="font-semibold text-white mb-2 flex items-center gap-2">
              <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              Why Prediction Markets?
            </h4>
            <p className="text-gray-400">
              Unlike social media sentiment, prediction markets represent <strong className="text-gray-300">money-backed forecasts</strong>.
              Traders put real capital at risk, creating a more reliable signal than free opinions. Markets aggregate diverse
              information sources and self-correct as new data emerges.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

interface Market {
  id: string;
  question: string;
  description: string;
  probability: number;
  change_24h: number;
  volume: number;
  liquidity: number;
  end_date: string;
  category: string;
  relevance_score?: number;
  narrative?: string;
  matched_keyword?: string;
  url: string;
  event_title?: string;
  event_slug?: string;
  event_description?: string;
}

interface GroupedEvent {
  event_title: string;
  event_slug: string;
  event_description: string;
  markets: Market[];
  total_volume: number;
  url: string;
}

interface NarrativeSentiment {
  sentiment: number;
  confidence: number;
  market_count: number;
  trend: string;
}

interface PolymarketSentiment {
  ticker: string;
  overall_sentiment: number;
  confidence: number;
  trend: string;
  narratives: Record<string, NarrativeSentiment>;
  top_markets: Market[];
  last_updated: string;
  market_count: number;
  error?: string;
}

interface PredictionMarketWidgetProps {
  ticker: string;
}

export default function PredictionMarketWidget({ ticker }: PredictionMarketWidgetProps) {
  const [data, setData] = useState<PolymarketSentiment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        
        const url = `${API_BASE_URL}/api/polymarket/ticker/${ticker}`;
        const response = await axios.get(url);
        
        // Debug: Log market data to check matched_keyword
        if (response.data?.top_markets?.length > 0) {
          console.log('Polymarket data received:', {
            marketCount: response.data.top_markets.length,
            firstMarket: response.data.top_markets[0],
            hasMatchedKeyword: !!response.data.top_markets[0].matched_keyword,
            matchedKeyword: response.data.top_markets[0].matched_keyword,
            allKeywords: response.data.top_markets.map((m: Market) => m.matched_keyword).filter(Boolean)
          });
        }
        
        if (mounted) {
          setData(response.data);
        }
      } catch (err: any) {
        if (mounted) {
          setError(err.response?.data?.detail || 'Failed to load prediction market data');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      mounted = false;
    };
  }, [ticker]);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white">Prediction Markets</h3>
        </div>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-700 rounded w-3/4"></div>
          <div className="h-4 bg-gray-700 rounded w-1/2"></div>
          <div className="h-4 bg-gray-700 rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  if (error || data?.error) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white">Prediction Markets</h3>
        </div>
        <div className="text-sm text-gray-400">
          {error || data?.error || 'No prediction market data available'}
        </div>
      </div>
    );
  }

  if (!data || data.top_markets.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white">Prediction Markets</h3>
        </div>
        <div className="text-sm text-gray-400">
          No relevant prediction markets found for {ticker}
        </div>
      </div>
    );
  }

  const sentimentColor = 
    data.overall_sentiment >= 0.6 ? 'text-green-400' :
    data.overall_sentiment <= 0.4 ? 'text-red-400' :
    'text-gray-400';

  const sentimentBg = 
    data.overall_sentiment >= 0.6 ? 'bg-green-500/20' :
    data.overall_sentiment <= 0.4 ? 'bg-red-500/20' :
    'bg-gray-500/20';

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Prediction Markets</h3>
            <p className="text-xs text-gray-400">Money-backed sentiment from Polymarket</p>
          </div>
        </div>
        <a
          href="https://polymarket.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-purple-400 hover:text-purple-300 transition-colors"
        >
          View on Polymarket →
        </a>
      </div>

      {/* Calculation Methodology - Collapsible */}
      <CalculationMethodology />

      {/* Overall Sentiment */}
      <div className="mb-6 p-4 bg-gray-700/50 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">Overall Sentiment</span>
          <span className={`text-sm font-medium ${sentimentColor} capitalize`}>
            {data.trend}
          </span>
        </div>
        
        {/* Sentiment Bar */}
        <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden mb-2">
          <div
            className={`absolute left-0 top-0 h-full ${sentimentBg} transition-all duration-500`}
            style={{ width: `${data.overall_sentiment * 100}%` }}
          />
        </div>
        
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Bearish</span>
          <span className={`font-medium ${sentimentColor}`}>
            {(data.overall_sentiment * 100).toFixed(0)}%
          </span>
          <span className="text-gray-500">Bullish</span>
        </div>
        
        {/* Confidence */}
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-400">Confidence:</span>
          <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500/50 transition-all duration-500"
              style={{ width: `${data.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-300">
            {(data.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Top Markets - Grouped by Event */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-gray-300 mb-3">
          Top Relevant Markets ({data.top_markets.length})
        </h4>
        
        {groupMarketsByEvent(data.top_markets).map((group, idx) => (
          <EventGroup key={group.event_slug || idx} group={group} />
        ))}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-between text-xs text-gray-500">
        <span>{data.market_count} markets analyzed</span>
        <span>Updated {new Date(data.last_updated).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}

// Helper function to group markets by event
function groupMarketsByEvent(markets: Market[]): GroupedEvent[] {
  const eventMap = new Map<string, GroupedEvent>();
  
  markets.forEach(market => {
    const eventKey = market.event_slug || market.event_title || market.id;
    
    if (!eventMap.has(eventKey)) {
      eventMap.set(eventKey, {
        event_title: market.event_title || market.question,
        event_slug: market.event_slug || '',
        event_description: market.event_description || market.description,
        markets: [],
        total_volume: 0,
        url: market.event_slug
          ? `https://polymarket.com/event/${market.event_slug}`
          : market.url
      });
    }
    
    const group = eventMap.get(eventKey)!;
    group.markets.push(market);
    group.total_volume += market.volume;
  });
  
  // Convert to array and sort by total volume
  return Array.from(eventMap.values())
    .sort((a, b) => b.total_volume - a.total_volume)
    .slice(0, 15); // Show top 15 events (increased from 5)
}

// Component to display an event group
function EventGroup({ group }: { group: GroupedEvent }) {
  const [isExpanded, setIsExpanded] = useState(group.markets.length === 1);
  
  const formatVolume = (vol: number) => {
    if (vol >= 1000000) return `$${(vol / 1000000).toFixed(1)}M`;
    if (vol >= 1000) return `$${(vol / 1000).toFixed(0)}K`;
    return `$${vol}`;
  };
  
  // If only one market, show it directly without grouping
  if (group.markets.length === 1) {
    return <MarketCard market={group.markets[0]} />;
  }
  
  return (
    <div className="bg-gray-700/30 rounded-lg overflow-hidden">
      {/* Event Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h5 className="text-sm font-medium text-gray-200 truncate">
              {group.event_title}
            </h5>
            <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs font-medium shrink-0">
              {group.markets.length} markets
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {formatVolume(group.total_volume)} total
            </span>
          </div>
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {/* Markets List */}
      {isExpanded && (
        <div className="border-t border-gray-700">
          {group.markets.map((market, idx) => (
            <div
              key={market.id}
              className={idx > 0 ? 'border-t border-gray-700/50' : ''}
            >
              <MarketCard market={market} compact />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MarketCard({ market, compact }: { market: Market; compact?: boolean }) {
  const probabilityColor = 
    market.probability >= 0.6 ? 'text-green-400' :
    market.probability <= 0.4 ? 'text-red-400' :
    'text-gray-400';

  const changeColor = 
    market.change_24h > 0 ? 'text-green-400' :
    market.change_24h < 0 ? 'text-red-400' :
    'text-gray-400';

  const formatVolume = (vol: number) => {
    if (vol >= 1000000) return `$${(vol / 1000000).toFixed(1)}M`;
    if (vol >= 1000) return `$${(vol / 1000).toFixed(0)}K`;
    return `$${vol}`;
  };

  const containerClass = compact
    ? "block p-3 hover:bg-gray-700/30 transition-colors group"
    : "block p-3 bg-gray-700/30 hover:bg-gray-700/50 rounded-lg transition-colors group";
  
  return (
    <a
      href={market.url}
      target="_blank"
      rel="noopener noreferrer"
      className={containerClass}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className={`text-gray-200 group-hover:text-white transition-colors flex-1 ${compact ? 'text-xs line-clamp-1' : 'text-sm line-clamp-2'}`}>
          {market.question}
        </p>
        <div className="flex flex-col items-end shrink-0">
          <span className={`${compact ? 'text-base' : 'text-lg'} font-bold ${probabilityColor}`}>
            {(market.probability * 100).toFixed(0)}%
          </span>
          {market.change_24h !== 0 && (
            <span className={`text-xs ${changeColor}`}>
              {market.change_24h > 0 ? '+' : ''}
              {(market.change_24h * 100).toFixed(1)}%
            </span>
          )}
        </div>
      </div>
      
      {!compact && (
        <div className="flex items-center gap-2 text-xs flex-wrap">
          <span className="flex items-center gap-1 text-gray-500">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {formatVolume(market.volume)}
          </span>
          {market.matched_keyword && market.matched_keyword.trim() && (
            <span className="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded text-xs font-medium">
              🔍 {market.matched_keyword}
            </span>
          )}
          {market.narrative && (
            <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs">
              {market.narrative.replace(/_/g, ' ')}
            </span>
          )}
          {market.relevance_score && (
            <span className="text-gray-600">
              {(market.relevance_score * 100).toFixed(0)}% relevant
            </span>
          )}
        </div>
      )}
      
      {compact && (
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {formatVolume(market.volume)}
          </span>
        </div>
      )}
    </a>
  );
}

// Made with Bob
