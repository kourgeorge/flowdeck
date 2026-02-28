import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StockListView from '../components/StockListView';
import StockSearch from '../components/StockSearch';
import AuthModal from '../components/AuthModal';
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
  const [showAuthModal, setShowAuthModal] = useState(false);

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
          <div className="flex flex-col items-center mb-5">
            <img src={LOGO_PATH} alt="" className="w-20 h-20 sm:w-24 sm:h-24 object-contain" />
            <span className="text-white text-2xl font-bold mt-2 tracking-wide">FlowDeck</span>
          </div>

          {/* Headline - 2-tone */}
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-center mb-4 leading-tight">
            <span className="text-white">Invest with the Odds in Your Favor</span>
            <br />
            <span className="text-blue-400">With AI-Powered Actionable Insights.</span>
          </h1>

          {/* Subtext */}
          <p className="text-gray-400 text-center text-base sm:text-lg max-w-3xl mx-auto mb-3 leading-relaxed">
            A committee of specialized AI agents analyzes market data, news, fundamentals, and risk —
            then delivers a clear recommendation with full reasoning.
          </p>

          {/* Trader Copilot pill */}
          <div className="flex justify-center mb-5">
            <Link
              to="/copilot"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-900/40 border border-blue-700/50 hover:bg-blue-900/60 hover:border-blue-600 transition-colors group"
            >
              <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span className="text-blue-300 text-sm font-medium">New: Trader Copilot</span>
              <span className="text-gray-500 text-sm">— research & chat side by side</span>
              <svg className="w-3.5 h-3.5 text-blue-400 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>

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
          {/* Ticker Search */}
          <div className="mb-6">
            <StockSearch />
          </div>

          <h2 className="text-2xl font-bold text-white mb-4">Major Stocks</h2>

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

      {/* SECTION 3: TRADER COPILOT SPOTLIGHT */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Left: copy */}
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-900/40 border border-blue-700/50 mb-5">
                <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span className="text-blue-300 text-xs font-semibold uppercase tracking-wider">Trader Copilot</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4 leading-tight">
                Research and Chat,<br />
                <span className="text-blue-400">Side by Side</span>
              </h2>
              <p className="text-gray-400 text-base leading-relaxed mb-6">
                The Trader Copilot is a three-panel workspace: your watchlist on the left, full stock detail in the middle, and an AI chat on the right. Ask follow-up questions while you read the report — no switching tabs, no copy-pasting tickers.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  { icon: '📊', text: 'Live quote, AI recommendation, and all report tabs in one view' },
                  { icon: '🤖', text: 'AI chat with full context — selected ticker, watchlist, live data, and reports' },
                  { icon: '💬', text: 'Ask anything: risks, technicals, news, fundamentals, comparisons' },
                  { icon: '⚡', text: 'Responses stream in real-time with transparent tool usage' },
                ].map(({ icon, text }) => (
                  <li key={text} className="flex items-start gap-3">
                    <span className="text-lg leading-none mt-0.5">{icon}</span>
                    <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
              <Link
                to={user ? '/copilot' : '#'}
                onClick={!user ? () => setShowAuthModal(true) : undefined}
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Open Trader Copilot
              </Link>
            </div>

            {/* Right: visual mockup of the 3-panel layout */}
            <div className="rounded-2xl border border-gray-700 bg-gray-800/60 overflow-hidden shadow-2xl">
              {/* Fake window chrome */}
              <div className="flex items-center gap-1.5 px-4 py-2.5 bg-gray-800 border-b border-gray-700">
                <span className="w-3 h-3 rounded-full bg-red-500/70" />
                <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
                <span className="w-3 h-3 rounded-full bg-green-500/70" />
                <div className="flex items-center gap-1.5 ml-3">
                  <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="text-xs text-gray-400 font-medium">Copilot</span>
                </div>
              </div>
              {/* Three-panel layout preview */}
              <div className="flex h-64 text-xs">
                {/* Sidebar */}
                <div className="w-28 shrink-0 border-r border-gray-700 bg-gray-800/80 p-2 flex flex-col gap-1.5">
                  <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-1 px-1">Watchlist</div>
                  {['AAPL', 'NVDA', 'MSFT', 'TSLA', 'GOOGL'].map((t, i) => (
                    <div
                      key={t}
                      className={`flex items-center justify-between px-2 py-1.5 rounded-lg ${i === 1 ? 'bg-blue-600/30 border border-blue-600/50' : 'hover:bg-gray-700/50'}`}
                    >
                      <span className={`font-semibold ${i === 1 ? 'text-white' : 'text-gray-300'}`}>{t}</span>
                      <span className={`text-[10px] ${i % 2 === 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {i % 2 === 0 ? '+1.2%' : '-0.8%'}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Stock detail */}
                <div className="flex-1 min-w-0 border-r border-gray-700 bg-gray-900 p-3 flex flex-col gap-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-white font-bold text-sm">NVDA</div>
                      <div className="text-gray-400 text-[10px]">NVIDIA Corporation</div>
                    </div>
                    <div className="text-right">
                      <div className="text-white font-semibold text-sm">$875.40</div>
                      <div className="text-green-400 text-[10px]">+2.34%</div>
                    </div>
                  </div>
                  <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-900/40 border border-green-700/50 self-start">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                    <span className="text-green-300 text-[10px] font-semibold">BUY</span>
                  </div>
                  <div className="flex gap-1 mt-1">
                    {['Market', 'News', 'Fundamentals', 'Technical'].map((tab, i) => (
                      <div
                        key={tab}
                        className={`px-2 py-0.5 rounded text-[9px] font-medium ${i === 0 ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'}`}
                      >
                        {tab}
                      </div>
                    ))}
                  </div>
                  <div className="flex-1 bg-gray-800/50 rounded-lg p-2 mt-1">
                    <div className="h-2 bg-gray-700 rounded mb-1.5 w-full" />
                    <div className="h-2 bg-gray-700 rounded mb-1.5 w-4/5" />
                    <div className="h-2 bg-gray-700 rounded w-3/5" />
                  </div>
                </div>
                {/* Chat panel */}
                <div className="w-44 shrink-0 bg-gray-900 flex flex-col">
                  <div className="px-2.5 py-2 border-b border-gray-700 bg-gray-800/80 flex items-center gap-1.5">
                    <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                    </div>
                    <span className="text-white text-[10px] font-semibold">Copilot</span>
                  </div>
                  <div className="flex-1 p-2 flex flex-col gap-2 overflow-hidden">
                    <div className="self-end bg-blue-600 text-white rounded-xl rounded-br-sm px-2 py-1 text-[9px] max-w-[90%]">
                      What are the key risks for NVDA?
                    </div>
                    <div className="bg-gray-700/80 text-gray-200 rounded-xl rounded-tl-sm px-2 py-1.5 text-[9px] leading-relaxed">
                      <div className="h-1.5 bg-gray-600 rounded mb-1 w-full" />
                      <div className="h-1.5 bg-gray-600 rounded mb-1 w-4/5" />
                      <div className="h-1.5 bg-gray-600 rounded w-3/5" />
                    </div>
                    <div className="self-end bg-blue-600 text-white rounded-xl rounded-br-sm px-2 py-1 text-[9px] max-w-[90%]">
                      Compare with AMD
                    </div>
                  </div>
                  <div className="px-2 pb-2">
                    <div className="bg-gray-700/80 rounded-lg border border-gray-600 px-2 py-1.5 flex items-center gap-1">
                      <span className="text-gray-500 text-[9px] flex-1">Ask about NVDA…</span>
                      <div className="w-4 h-4 rounded bg-blue-600 flex items-center justify-center">
                        <svg className="w-2.5 h-2.5 text-white rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 4: PLATFORM OVERVIEW (How It Works + Features) */}
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
              <h4 className="text-lg font-semibold text-white mb-2">Live Market Data</h4>
              <p className="text-gray-400 text-sm">
                Real-time prices, volume, and ranges — plus AI-driven recommendations synthesized from news, SEC filings, fundamentals, technicals, and sentiment.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Multi-Agent AI Analysis</h4>
              <p className="text-gray-400 text-sm">
                Specialized agents collaborate to analyze every angle before making a recommendation.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Transparent Reports & Recommendations</h4>
              <p className="text-gray-400 text-sm">
                Get clear <strong className="text-white">BUY / SELL / HOLD</strong> recommendations backed by comprehensive AI analysis — and read the full reasoning across multiple report tabs.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Stock Subscriptions & Dashboard</h4>
              <p className="text-gray-400 text-sm">
                Subscribe to stocks and get email updates when new analysis reports are available. Track your watchlist and portfolio performance from a personalized dashboard.
              </p>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">On-Demand Reports</h4>
              <p className="text-gray-400 text-sm">
                Generate fresh AI analysis for any stock, any time — using your token balance.
              </p>
            </div>
            <div className="bg-blue-900/20 border border-blue-700/50 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Trader Copilot & AI Analyst</h4>
              <p className="text-gray-400 text-sm">
                Research stocks and chat with the AI side by side in the Copilot workspace, or use the standalone AI Analyst Agent for deep-dive conversations with live market data access.
              </p>
            </div>
          </div>

          {/* How It Works — 3 steps */}
          <div className="border border-gray-700 rounded-2xl p-8 bg-gray-800/30">
            <h3 className="text-lg font-semibold text-gray-300 uppercase tracking-wider mb-6">
              How the AI Works
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
                <h4 className="text-lg font-semibold text-white mb-2">1. Specialized Analysts</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Market, News, Fundamentals, Technical, and Sentiment analysts each produce
                  focused reports with scores. No single perspective dominates.
                </p>
              </div>
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
                <h4 className="text-lg font-semibold text-white mb-2">2. Bull vs. Bear Debate</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  AI researchers argue both sides across multiple rounds, stress-testing
                  the investment case. What could go right? What could go wrong?
                </p>
              </div>
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
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
        </div>
      </section>

      {/* SECTION 5: FINAL CTA */}
      <section className="px-4 py-10 sm:py-12 bg-gray-900 border-t border-gray-700">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-4">
            Ready to Invest Smarter?
          </h2>
          {user ? (
            <p className="text-gray-400 text-base sm:text-lg mb-8 max-w-2xl mx-auto">
              Start exploring stocks and generating AI analysis reports with your token balance.
            </p>
          ) : (
            <div className="mb-8 max-w-2xl mx-auto">
              <p className="text-gray-400 text-base sm:text-lg mb-4">
                Sign up free and get instant access to:
              </p>
              <ul className="text-left text-gray-300 space-y-2 inline-block">
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">1,000 free tokens</strong> to generate AI analysis reports</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">Full report access</strong> to any previously generated analysis</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">Personalized dashboard</strong> to track your portfolio</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">Stock subscriptions</strong> with email updates</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">Trader Copilot</strong> — research and chat side by side</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">AI Analyst Agent</strong> — chat with live market data and analysis</span>
                </li>
              </ul>
            </div>
          )}
          <div className="flex flex-col items-center justify-center gap-6">
            {user ? (
              <div className="flex flex-wrap gap-4 justify-center">
                <Link
                  to="/dashboard"
                  className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-lg transition-colors"
                >
                  Go to Dashboard →
                </Link>
                <Link
                  to="/copilot"
                  className="px-8 py-4 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold text-lg transition-colors flex items-center gap-2"
                >
                  <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Open Copilot
                </Link>
              </div>
            ) : (
              <button
                onClick={() => setShowAuthModal(true)}
                className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-lg transition-colors"
              >
                Get Started Free →
              </button>
            )}
          </div>
        </div>
      </section>

      {/* SECTION 6: TOKEN ECONOMY */}
      <section className="px-4 py-8 sm:py-10 bg-gray-900">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-3">
              Generate Reports with Tokens
            </h2>
            <p className="text-gray-400 text-base sm:text-lg max-w-2xl mx-auto">
              Each AI analysis report costs tokens. New users get <strong className="text-blue-400">1,000 free tokens</strong> on
              sign-up — enough to generate <strong className="text-white">multiple reports</strong> and fully explore the platform.
            </p>
          </div>

          {/* Token Packages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-center">
              <h3 className="text-lg font-semibold text-white mb-1">Starter Pack</h3>
              <div className="text-3xl font-bold text-white mb-0.5">500</div>
              <div className="text-gray-400 text-sm mb-2">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$5.00</div>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-center">
              <h3 className="text-lg font-semibold text-white mb-1">Popular Pack</h3>
              <div className="text-3xl font-bold text-white mb-0.5">1,000</div>
              <div className="text-gray-400 text-sm mb-2">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$9.00</div>
              <div className="text-green-400 text-xs mt-1">Save 10%</div>
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-center">
              <h3 className="text-lg font-semibold text-white mb-1">Best Value Pack</h3>
              <div className="text-3xl font-bold text-white mb-0.5">2,500</div>
              <div className="text-gray-400 text-sm mb-2">tokens</div>
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
              <button
                onClick={() => setShowAuthModal(true)}
                className="inline-flex items-center px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-lg transition-colors"
              >
                Buy Tokens →
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Auth Modal */}
      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          message="Please sign in to purchase tokens."
        />
      )}
    </div>
  );
}

// Made with Bob
