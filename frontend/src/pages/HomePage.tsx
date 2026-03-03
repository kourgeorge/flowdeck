import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StockListView from '../components/StockListView';
import StockSearch from '../components/StockSearch';
import AuthModal from '../components/AuthModal';
import { stockApi, API_BASE_URL } from '../services/api';
import type { StockWidget as StockWidgetType } from '../services/types';
import { LOGO_PATH, COPILOT_NAME } from '../config';
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

          {/* Trading Copilot — {COPILOT_NAME} pill */}
          <div className="flex justify-center mb-5">
            <Link
              to="/copilot"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-900/40 border border-blue-700/50 hover:bg-blue-900/60 hover:border-blue-600 transition-colors group"
            >
              <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span className="text-blue-300 text-sm font-medium">New: {COPILOT_NAME}</span>
              <span className="text-gray-500 text-sm">— your trading assistant - an agent that accesses all information needed to answer your trading questions</span>
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
                <span className="text-blue-300 text-xs font-semibold uppercase tracking-wider">Trading Copilot — {COPILOT_NAME}</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4 leading-tight">
                Research and Chat,<br />
                <span className="text-blue-400">Side by Side</span>
              </h2>
              <p className="text-gray-400 text-base leading-relaxed mb-6">
                {COPILOT_NAME} is your Trading Copilot — a three-panel workspace: your watchlist on the left, full stock detail in the middle, and an AI chat on the right. Ask follow-up questions while you read the report — no switching tabs, no copy-pasting tickers.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  { icon: '📊', text: 'Live quote, AI recommendation, and all report tabs in one view' },
                  { icon: '🤖', text: 'AI chat with full context — selected ticker, watchlist, live data, and reports' },
                  { icon: '🌐', text: 'Searches the live web for breaking news, earnings, analyst upgrades, and macro events' },
                  { icon: '🐍', text: 'Writes and executes Python analysis code — correlations, return scenarios, statistical models' },
                  { icon: '📈', text: 'Generates interactive charts — line, bar, area, and scatter — rendered inline in the chat' },
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
                Open {COPILOT_NAME}
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
                  <span className="text-xs text-gray-400 font-medium">{COPILOT_NAME}</span>
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
                    <span className="text-white text-[10px] font-semibold">{COPILOT_NAME}</span>
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

      {/* SECTION 3b: TPS — TRADING PLAN SPECIFICATION */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Left: TPS JSON mockup */}
            <div className="rounded-2xl border border-indigo-700/50 bg-indigo-950/20 overflow-hidden shadow-2xl order-2 lg:order-1">
              {/* Window chrome */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-indigo-900/30 border-b border-indigo-700/40">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-indigo-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <span className="text-xs font-semibold uppercase tracking-widest text-indigo-300">TPS v0.1 — Trader Tab</span>
                </div>
                <span className="text-xs text-indigo-500 font-mono">JSON</span>
              </div>
              {/* JSON body */}
              <div className="p-4 font-mono text-xs leading-relaxed">
                <pre className="bg-slate-900/80 rounded-lg p-4 overflow-x-auto whitespace-pre text-left">
                  <span className="text-slate-400">{'{'}</span>{'\n'}
                  <span className="text-slate-400">{'  '}</span><span className="text-sky-300">"instrument"</span><span className="text-slate-400">: </span><span className="text-amber-300">"NVDA"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'  '}</span><span className="text-sky-300">"timeframe"</span><span className="text-slate-400">: </span><span className="text-amber-300">"1D"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'  '}</span><span className="text-sky-300">"side"</span><span className="text-slate-400">: </span><span className="text-amber-300">"long"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'  '}</span><span className="text-sky-300">"entry"</span><span className="text-slate-400">: {'{'}</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"near"</span><span className="text-slate-400">: </span><span className="text-amber-300">"875.40 ±1%"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"scale"</span><span className="text-slate-400">: </span><span className="text-amber-300">"40/30/30"</span>{'\n'}
                  <span className="text-slate-400">{'  }'}</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'  '}</span><span className="text-sky-300">"risk"</span><span className="text-slate-400">: {'{'}</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"max_loss"</span><span className="text-slate-400">: </span><span className="text-amber-300">"1%"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"stop"</span><span className="text-slate-400">: </span><span className="text-green-300">850.00</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"max_position"</span><span className="text-slate-400">: </span><span className="text-amber-300">"5%"</span>{'\n'}
                  <span className="text-slate-400">{'  }'}</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'  '}</span><span className="text-sky-300">"take_profit"</span><span className="text-slate-400">: {'{'}</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"tp1"</span><span className="text-slate-400">: </span><span className="text-amber-300">"940.00 sell 50%"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">{'    '}</span><span className="text-sky-300">"trail"</span><span className="text-slate-400">: </span><span className="text-amber-300">"4%"</span>{'\n'}
                  <span className="text-slate-400">{'  }'}</span>{'\n'}
                  <span className="text-slate-400">{'}'}</span>
                </pre>
              </div>
            </div>

            {/* Right: copy */}
            <div className="order-1 lg:order-2">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-900/40 border border-indigo-700/50 mb-5">
                <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <span className="text-indigo-300 text-xs font-semibold uppercase tracking-wider">TPS v0.1 — Trading Plan Specification</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4 leading-tight">
                Every Analysis Includes<br />
                <span className="text-indigo-400">a Structured Trade Plan</span>
              </h2>
              <p className="text-gray-400 text-base leading-relaxed mb-6">
                After the AI Trader agent produces its narrative recommendation, FlowDeck automatically generates a <strong className="text-white">TPS (Trading Plan Specification)</strong> — a compact, machine-readable JSON object that captures the full trade decision without ambiguity.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  { icon: '🎯', text: 'Entry zone, stop-loss, and take-profit levels — all in one structured object' },
                  { icon: '📐', text: 'Tranche sizing (e.g. 40/30/30), max position size, and risk per trade' },
                  { icon: '🛡️', text: 'Volatility guards and invalidation rules that auto-expire the plan if the thesis breaks' },
                  { icon: '✅', text: 'Schema-validated by Pydantic — required fields are always present, no fabricated prices' },
                  { icon: '📋', text: 'Found in the Trader tab of every AI Analysis report' },
                ].map(({ icon, text }) => (
                  <li key={text} className="flex items-start gap-3">
                    <span className="text-lg leading-none mt-0.5">{icon}</span>
                    <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/tps"
                className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-700 hover:bg-indigo-600 text-white rounded-lg font-semibold transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Read the TPS Specification →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 3c: API ACCESS */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Left: Code example */}
            <div className="rounded-2xl border border-emerald-700/50 bg-emerald-950/20 overflow-hidden shadow-2xl order-2 lg:order-1">
              {/* Window chrome */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-emerald-900/30 border-b border-emerald-700/40">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                  <span className="text-xs font-semibold uppercase tracking-widest text-emerald-300">API Example</span>
                </div>
                <span className="text-xs text-emerald-500 font-mono">Python</span>
              </div>
              {/* Code body */}
              <div className="p-4 font-mono text-xs leading-relaxed">
                <pre className="bg-slate-900/80 rounded-lg p-4 overflow-x-auto whitespace-pre text-left">
                  <span className="text-purple-400">import</span> <span className="text-white">requests</span>{'\n\n'}
                  <span className="text-slate-400"># Your API key from Profile page</span>{'\n'}
                  <span className="text-sky-300">API_KEY</span> <span className="text-slate-400">=</span> <span className="text-amber-300">"fd_live_your_key_here"</span>{'\n'}
                  <span className="text-sky-300">BASE_URL</span> <span className="text-slate-400">=</span> <span className="text-amber-300">"https://flowdeck.biz"</span>{'\n\n'}
                  <span className="text-sky-300">headers</span> <span className="text-slate-400">=</span> {'{'}{'\n'}
                  <span className="text-slate-400">    </span><span className="text-amber-300">"Authorization"</span><span className="text-slate-400">:</span> <span className="text-green-300">f</span><span className="text-amber-300">"Bearer </span>{'{'}<span className="text-sky-300">API_KEY</span>{'}'}<span className="text-amber-300">"</span>{'\n'}
                  <span className="text-slate-400">{'}'}</span>{'\n\n'}
                  <span className="text-slate-400"># Get AI analysis report</span>{'\n'}
                  <span className="text-sky-300">response</span> <span className="text-slate-400">=</span> <span className="text-white">requests</span><span className="text-slate-400">.</span><span className="text-green-300">get</span><span className="text-slate-400">(</span>{'\n'}
                  <span className="text-slate-400">    </span><span className="text-green-300">f</span><span className="text-amber-300">"</span>{'{'}<span className="text-sky-300">BASE_URL</span>{'}'}<span className="text-amber-300">/api/data/reports/AAPL"</span><span className="text-slate-400">,</span>{'\n'}
                  <span className="text-slate-400">    </span><span className="text-sky-300">headers</span><span className="text-slate-400">=</span><span className="text-sky-300">headers</span>{'\n'}
                  <span className="text-slate-400">)</span>{'\n\n'}
                  <span className="text-sky-300">report</span> <span className="text-slate-400">=</span> <span className="text-sky-300">response</span><span className="text-slate-400">.</span><span className="text-green-300">json</span><span className="text-slate-400">()</span>{'\n'}
                  <span className="text-purple-400">print</span><span className="text-slate-400">(</span><span className="text-sky-300">report</span><span className="text-slate-400">[</span><span className="text-amber-300">'reports'</span><span className="text-slate-400">][</span><span className="text-amber-300">'final_trade_decision'</span><span className="text-slate-400">])</span>
                </pre>
              </div>
            </div>

            {/* Right: copy */}
            <div className="order-1 lg:order-2">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-900/40 border border-emerald-700/50 mb-5">
                <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                <span className="text-emerald-300 text-xs font-semibold uppercase tracking-wider">Programmatic API Access</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4 leading-tight">
                Integrate FlowDeck<br />
                <span className="text-emerald-400">Into Your Trading Systems</span>
              </h2>
              <p className="text-gray-400 text-base leading-relaxed mb-6">
                Access FlowDeck's AI-powered analysis programmatically with our REST API. Perfect for algorithmic trading systems, portfolio management tools, and custom integrations.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  { icon: '🔑', text: 'Secure API keys with optional expiration — never expire by default' },
                  { icon: '📊', text: 'Access all AI reports, recommendations, and TPS trade plans via REST endpoints' },
                  { icon: '💬', text: 'Chat with the AI analyst programmatically — get answers to any trading question' },
                  { icon: '📈', text: 'Fetch real-time quotes, fundamentals, and news for any stock' },
                  { icon: '🔄', text: 'Batch requests for multiple tickers in a single API call' },
                  { icon: '🐍', text: 'Python, JavaScript, cURL examples — easy integration in any language' },
                  { icon: '⚡', text: 'Same token economy — use your existing token balance' },
                ].map(({ icon, text }) => (
                  <li key={text} className="flex items-start gap-3">
                    <span className="text-lg leading-none mt-0.5">{icon}</span>
                    <span className="text-gray-300 text-sm leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-3">
                <Link
                  to="/api-docs"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg font-semibold transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  View API Documentation
                </Link>
                <Link
                  to={user ? '/profile#api-keys' : '#'}
                  onClick={!user ? () => setShowAuthModal(true) : undefined}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-semibold transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                  Create API Key
                </Link>
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
              <h4 className="text-lg font-semibold text-white mb-2">Deep AI Analysis, On Demand</h4>
              <p className="text-gray-400 text-sm">
                Trigger a full multi-agent analysis for any stock, any time. A committee of specialized AI analysts — covering market data, news, fundamentals, technicals, and risk — each produce their own report before a final recommendation is synthesized. Every angle covered, every time.
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
            <div className="bg-indigo-900/20 border border-indigo-700/50 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <Link to="/tps" className="hover:text-indigo-300 transition-colors">TPS — Structured Trade Plans</Link>
              </h4>
              <p className="text-gray-400 text-sm">
                Every AI analysis automatically produces a <strong className="text-white">Trading Plan Specification (TPS)</strong> — a schema-validated JSON object with entry zone, stop-loss, take-profit targets, position sizing, and invalidation rules. No ambiguity, no prose to interpret.
              </p>
            </div>
            <div className="bg-blue-900/20 border border-blue-700/50 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">{COPILOT_NAME} — A Powerful Trading Assistant</h4>
              <p className="text-gray-400 text-sm">
                {COPILOT_NAME} can <strong className="text-white">search the live web</strong> for breaking news and analyst updates, <strong className="text-white">write and execute Python code</strong> for financial modelling and statistical analysis, and <strong className="text-white">generate interactive charts</strong> — line, bar, area, and scatter — rendered directly in the chat. All of FlowDeck's proprietary reports are accessible in the same conversation.
              </p>
            </div>
            <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <Link to="/api-docs" className="hover:text-emerald-300 transition-colors">REST API — Programmatic Access</Link>
              </h4>
              <p className="text-gray-400 text-sm">
                Integrate FlowDeck into your trading systems with our <strong className="text-white">REST API</strong>. Create secure API keys, access all AI reports and recommendations programmatically, chat with the AI analyst via API, and fetch real-time market data. Perfect for algorithmic trading, portfolio management tools, and custom integrations.
              </p>
            </div>
            <div className="bg-purple-900/20 border border-purple-700/50 rounded-xl p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <a href="https://flowdeck.biz/api/SKILL.md" target="_blank" rel="noopener noreferrer" className="hover:text-purple-300 transition-colors inline-flex items-center gap-1">
                  SKILL.md — Autonomous Agent Integration
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </h4>
              <p className="text-gray-400 text-sm">
                A comprehensive API guide for AI agents to autonomously interact with FlowDeck. Agents can register, fetch market data, chat with the AI analyst, and start analyses — all without human intervention. <a href="https://flowdeck.biz/api/SKILL.md" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline">View SKILL.md →</a>
              </p>
            </div>
          </div>

          {/* How It Works — 3 steps */}
          <div className="border border-gray-700 rounded-2xl p-8 bg-gray-800/30">
            <h3 className="text-lg font-semibold text-gray-300 uppercase tracking-wider mb-6">
              How the AI Analysis Team Works
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
                <h4 className="text-lg font-semibold text-white mb-2">1. Analyst Team</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Six specialized AI analysts — covering market trends, news, fundamentals, SEC filings, technicals, and social sentiment — each independently research the stock and produce a scored report. Every angle is covered before any debate begins.
                </p>
              </div>
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
                <h4 className="text-lg font-semibold text-white mb-2">2. Investment Debate → Trade Plan</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Bull and Bear researchers argue the investment case across multiple rounds using all analyst reports. A Research Manager then adjudicates, producing a conviction score, return scenarios, and a structured investment plan — which a Trader agent refines into an actionable trade strategy.
                </p>
              </div>
              <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
                <h4 className="text-lg font-semibold text-white mb-2">3. Risk Debate → Final Decision</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Three risk agents — Aggressive, Cautious, and Neutral — debate the trade plan in round-robin. A Risk Judge weighs all upstream scores and risk arguments to produce the final verdict: <strong className="text-green-400">BUY</strong>, <strong className="text-red-400">SELL</strong>, or <strong className="text-yellow-400">HOLD</strong>.
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
                  <span><strong className="text-white">1,000 free tokens</strong> to generate AI analysis reports and chat with {COPILOT_NAME}</span>
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
                  <span><strong className="text-white">{COPILOT_NAME}</strong> — your Trading Copilot, research and chat side by side</span>
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
                  Open {COPILOT_NAME}
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
              sign-up — enough to generate <strong className="text-white">multiple reports</strong>, chat with <strong className="text-white">{COPILOT_NAME}</strong> the trader assistant, and fully explore the platform.
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
