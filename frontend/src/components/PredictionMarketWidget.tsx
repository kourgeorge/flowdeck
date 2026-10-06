import { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../services/api';

// Collapsible info component
function CalculationMethodology() {
  return <p className="mb-4 text-sm text-gray-400">Each percentage is the market's implied probability of its stated outcome. It does not indicate whether that outcome is bullish or bearish for this stock. Trading volume is not forecast confidence.</p>;
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
  confidence: number | null;
  market_count: number;
  trend: string;
}

interface PolymarketSentiment {
  ticker: string;
  overall_sentiment: number | null;
  confidence: number | null;
  trend: string;
  narratives: Record<string, NarrativeSentiment>;
  top_markets: Market[];
  last_updated: string;
  market_count: number;
  search_keywords?: string[];
  error?: string;
}

// Small reusable list of the keywords used to search Polymarket.
function SearchKeywords({ keywords }: { keywords?: string[] }) {
  if (!keywords || keywords.length === 0) return null;
  return (
    <div className="mt-4 pt-4 border-t border-gray-700">
      <p className="text-xs text-gray-400 mb-2">Searched Polymarket for:</p>
      <div className="flex flex-wrap gap-1.5">
        {keywords.map((kw, idx) => (
          <span
            key={`${kw}-${idx}`}
            className="px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 text-xs border border-purple-500/20"
          >
            {kw}
          </span>
        ))}
      </div>
    </div>
  );
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
        <SearchKeywords keywords={data?.search_keywords} />
      </div>
    );
  }


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
            <p className="text-xs text-gray-400">Event probabilities from Polymarket</p>
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

      <p className="mb-6 text-sm text-gray-400">Stock-price direction: unavailable. Review the individual events below.</p>

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

      {/* Search keywords used to find these markets */}
      <SearchKeywords keywords={data.search_keywords} />
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
  const probabilityColor = 'text-blue-300';

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
