import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StockListView from '../components/StockListView';
import StockSearch from '../components/StockSearch';
import { stockApi, API_BASE_URL } from '../services/api';
import type { StockWidget as StockWidgetType } from '../services/types';
import { LOGO_PATH } from '../config';
import { useAuth } from '../contexts/AuthContext';

interface PublicStats {
  total_analyses: number;
  total_reports: number;
  unique_tickers_analyzed: number;
}

export default function HomePage() {
  const { user } = useAuth();
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [publicStats, setPublicStats] = useState<PublicStats | null>(null);

  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((arr: Array<{ ticker: string; name: string }>) => {
        const map: Record<string, string> = {};
        arr.forEach(({ ticker, name }) => {
          map[ticker] = name;
        });
        setTickerToName(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const stats = await stockApi.getPublicStats();
        setPublicStats(stats);
      } catch (err) {
        console.error('Failed to load public stats:', err);
      }
    };
    loadStats();
  }, []);

  const loadWidgets = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const today = new Date().toISOString().slice(0, 10);
      const response = await stockApi.getWidgets(undefined, today);
      setWidgets(response.widgets);
    } catch (err: any) {
      console.error('Failed to load widgets:', err);
      const errorMessage = err?.response?.data?.detail || err?.message || 'Failed to load stock data.';
      const backendHint = API_BASE_URL ? ` (${API_BASE_URL})` : '';
      setError(`Failed to load stock data: ${errorMessage}. Please check if the backend is running${backendHint}.`);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadWidgets();
    const interval = setInterval(loadWidgets, 60000);
    return () => clearInterval(interval);
  }, []);

  const MAJOR_STOCKS_LIMIT = 10;
  const hasMajorFlag = widgets.some((w) => w.is_major === true || w.is_major === false);
  const majorFiltered = hasMajorFlag
    ? widgets.filter((w) => w.is_major === true)
    : widgets;
  const majorWidgets = majorFiltered.slice(0, MAJOR_STOCKS_LIMIT);

  if (isLoading && widgets.length === 0) {
    return (
      <div className="min-h-screen">
        {/* Hero Section - Loading */}
        <section className="bg-gradient-to-b from-[#0d1117] to-gray-900 px-4 py-16 sm:py-20 lg:py-24">
          <div className="max-w-6xl mx-auto text-center">
            <div className="flex justify-center mb-6">
              <img src={LOGO_PATH} alt="" className="w-24 h-24 object-contain animate-pulse" />
            </div>
            <div className="h-16 bg-gray-800 rounded-lg mb-4 mx-auto max-w-3xl animate-pulse"></div>
            <div className="h-12 bg-gray-800 rounded-lg mb-8 mx-auto max-w-2xl animate-pulse"></div>
            <div className="h-6 bg-gray-800 rounded-lg mb-12 mx-auto max-w-xl animate-pulse"></div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* SECTION 1: HERO */}
      <section className="bg-gray-900 px-4 py-10 sm:py-12 lg:py-14 pb-6 sm:pb-6 lg:pb-6">
        <div className="max-w-6xl mx-auto">
          {/* Logo */}
          <div className="flex justify-center mb-5">
            <img src={LOGO_PATH} alt="" className="w-20 h-20 sm:w-24 sm:h-24 object-contain" />
          </div>

          {/* Headline - 2-tone */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-center mb-4 leading-tight">
            <span className="text-white">Invest with the Odds in Your Favor</span>
            <br />
            <span className="text-blue-400">With AI-Powered BUY/SELL/HOLD Insights.</span>
          </h1>

          {/* Subtext */}
          <p className="text-gray-400 text-center text-base sm:text-lg max-w-3xl mx-auto mb-5 leading-relaxed">
            A committee of specialized AI agents analyzes market data, news, fundamentals, and risk —
            then delivers a clear recommendation with full reasoning.
          </p>

          {/* Social Proof */}
          <p className="text-gray-500 text-center text-sm mb-6">
            Transparent AI analysis for independent investors who want to understand the <em>why</em>.
          </p>

          {/* Stats Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-4xl mx-auto">
            <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-6 text-center">
              <div className="text-2xl font-bold text-blue-300 mb-1">
                {publicStats ? publicStats.total_analyses.toLocaleString() : '—'}
              </div>
              <div className="text-blue-400/80 text-sm">AI Analyses Generated</div>
            </div>
            <div className="bg-violet-900/30 border border-violet-700/50 rounded-lg p-6 text-center">
              <div className="text-2xl font-bold text-violet-300 mb-1">
                {publicStats ? publicStats.total_reports.toLocaleString() : '—'}
              </div>
              <div className="text-violet-400/80 text-sm">Reports Created</div>
            </div>
            <div className="bg-emerald-900/30 border border-emerald-700/50 rounded-lg p-6 text-center">
              <div className="text-2xl font-bold text-emerald-300 mb-1">
                {publicStats ? publicStats.unique_tickers_analyzed.toLocaleString() : '—'}
              </div>
              <div className="text-emerald-400/80 text-sm">Stocks Analyzed</div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 2: LIVE MARKET SNAPSHOT */}
      <section className="px-4 py-6 sm:py-8 bg-gray-900">
        <div className="max-w-layout mx-auto">
          <h2 className="text-2xl font-bold text-white mb-6">Major Stocks</h2>
          
          {error && (
            <div className="bg-red-500/10 border border-red-500 text-red-400 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          {widgets.length === 0 ? (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
              <p className="text-gray-400 mb-4">No stock data available</p>
              <button
                onClick={loadWidgets}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                Retry
              </button>
            </div>
          ) : (
            <StockListView widgets={majorWidgets} tickerToName={tickerToName} />
          )}
        </div>
      </section>

      {/* SECTION 3: PLATFORM OVERVIEW (How It Works + Features) */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-3">
              Everything You Need to Know
            </h2>
            <p className="text-gray-400 text-base sm:text-lg">
              A transparent, multi-step AI process — and all the tools to act on it
            </p>
          </div>

          {/* Feature Highlights */}
          <h3 className="text-lg font-semibold text-gray-300 uppercase tracking-wider mb-6">
            Platform Features
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-4xl mb-3">📡</div>
              <h4 className="text-lg font-semibold text-white mb-2">Live Market Data</h4>
              <p className="text-gray-400 text-sm">
                Real-time prices, volume, bid/ask, and 52-week ranges for all major stocks.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-4xl mb-3">🤖</div>
              <h4 className="text-lg font-semibold text-white mb-2">Multi-Agent AI Analysis</h4>
              <p className="text-gray-400 text-sm">
                Specialized agents collaborate to analyze every angle before making a recommendation.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-4xl mb-3">📋</div>
              <h4 className="text-lg font-semibold text-white mb-2">Transparent Reports</h4>
              <p className="text-gray-400 text-sm">
                Read the full reasoning behind every recommendation across multiple report tabs.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-4xl mb-3">🎯</div>
              <h4 className="text-lg font-semibold text-white mb-2">BUY/SELL/HOLD Recommendations</h4>
              <p className="text-gray-400 text-sm">
                Clear, actionable recommendations backed by comprehensive AI analysis.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-4xl mb-3">🔔</div>
              <h4 className="text-lg font-semibold text-white mb-2">Stock Subscriptions</h4>
              <p className="text-gray-400 text-sm">
                Subscribe to stocks and get email updates when new analysis reports are available.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-4xl mb-3">📈</div>
              <h4 className="text-lg font-semibold text-white mb-2">On-Demand Reports</h4>
              <p className="text-gray-400 text-sm">
                Generate fresh AI analysis for any stock, any time — using your token balance.
              </p>
            </div>
          </div>

          {/* How It Works — 3 steps */}
          <h3 className="text-lg font-semibold text-gray-300 uppercase tracking-wider mb-6">
            How the AI Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-5xl mb-4">🔍</div>
              <h4 className="text-lg font-semibold text-white mb-2">1. Specialized Analysts</h4>
              <p className="text-gray-400 text-sm leading-relaxed">
                Market, News, Fundamentals, Technical, and Sentiment analysts each produce
                focused reports with scores. No single perspective dominates.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-5xl mb-4">⚖️</div>
              <h4 className="text-lg font-semibold text-white mb-2">2. Bull vs. Bear Debate</h4>
              <p className="text-gray-400 text-sm leading-relaxed">
                AI researchers argue both sides across multiple rounds, stress-testing
                the investment case. What could go right? What could go wrong?
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <div className="text-5xl mb-4">🎯</div>
              <h4 className="text-lg font-semibold text-white mb-2">3. Risk Check → Recommendation</h4>
              <p className="text-gray-400 text-sm leading-relaxed">
                A final risk debate (aggressive, cautious, neutral) produces the
                recommendation you see: <strong className="text-green-400">BUY</strong>, <strong className="text-red-400">SELL</strong>, or <strong className="text-yellow-400">HOLD</strong>.
              </p>
            </div>
          </div>

          <div className="text-center">
            <Link
              to="/how-it-works"
              className="inline-flex items-center px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
            >
              Read full explanation →
            </Link>
          </div>
        </div>
      </section>

      {/* SECTION 5: TOKEN ECONOMY */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-3">
              Generate Reports with Tokens
            </h2>
            <p className="text-gray-400 text-base sm:text-lg max-w-2xl mx-auto">
              Each AI analysis report costs tokens. New users get <strong className="text-blue-400">1,000 free tokens</strong> on
              sign-up — enough to generate your first reports and explore the platform.
            </p>
          </div>

          {/* Token Packages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 text-center">
              <h3 className="text-lg font-semibold text-white mb-2">Starter Pack</h3>
              <div className="text-3xl font-bold text-white mb-1">500</div>
              <div className="text-gray-400 text-sm mb-3">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$5.00</div>
            </div>
            <div className="bg-gray-800 border border-blue-600 rounded-xl p-6 text-center relative">
              <div className="absolute top-4 right-4 bg-blue-600 text-white text-xs px-2 py-1 rounded">
                Popular
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Popular Pack</h3>
              <div className="text-3xl font-bold text-white mb-1">1,000</div>
              <div className="text-gray-400 text-sm mb-3">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$9.00</div>
              <div className="text-green-400 text-xs mt-1">Save 10%</div>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 text-center relative">
              <div className="absolute top-4 right-4 bg-green-600 text-white text-xs px-2 py-1 rounded">
                Best Value
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Best Value Pack</h3>
              <div className="text-3xl font-bold text-white mb-1">2,500</div>
              <div className="text-gray-400 text-sm mb-3">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$20.00</div>
              <div className="text-green-400 text-xs mt-1">Save 20%</div>
            </div>
          </div>

          <div className="text-center">
            {user ? (
              <Link
                to="/profile#purchase-tokens"
                className="inline-flex items-center px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-lg transition-colors"
              >
                Buy Tokens →
              </Link>
            ) : (
              <p className="text-gray-400 text-sm">
                Sign up to get your free tokens and purchase more as needed
              </p>
            )}
          </div>
        </div>
      </section>

      {/* SECTION 6: FINAL CTA */}
      <section className="px-4 py-16 sm:py-20 bg-gray-900">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-4">
            Ready to Invest Smarter?
          </h2>
          <p className="text-gray-400 text-base sm:text-lg mb-8 max-w-2xl mx-auto">
            {user ? (
              <>Start exploring stocks and generating AI analysis reports with your token balance.</>
            ) : (
              <>Sign up free and get <strong className="text-blue-400">1,000 tokens</strong> to generate your first AI analysis reports.</>
            )}
          </p>
          <div className="flex flex-col items-center justify-center gap-6">
            {user ? (
              <>
                <div className="w-full max-w-4xl">
                  <StockSearch />
                </div>
                <Link
                  to="/dashboard"
                  className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-lg transition-colors"
                >
                  Go to Dashboard →
                </Link>
              </>
            ) : (
              <>
                <div className="w-full max-w-4xl">
                  <StockSearch />
                </div>
                <button
                  onClick={() => {
                    window.location.href = '/profile';
                  }}
                  className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-lg transition-colors"
                >
                  Get Started Free →
                </button>
              </>
            )}
          </div>
          <p className="text-gray-500 text-sm mt-6">
            No credit card required · {user ? 'Start analyzing' : '1,000 free tokens on sign-up'}
          </p>
        </div>
      </section>
    </div>
  );
}

// Made with Bob
