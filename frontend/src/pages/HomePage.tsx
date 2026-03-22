import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import MajorStockWidgets from '../components/MajorStockWidgets';
import TickerSearch from '../components/TickerSearch';
import AuthModal from '../components/AuthModal';
import { tickerApi, API_BASE_URL } from '../services/api';
import type { TickerWidget as StockWidgetType } from '../services/types';
import { LOGO_PATH, COPILOT_NAME } from '../config';
import { SIGNIFICANT_SEVEN_RANK, SIGNIFICANT_SEVEN_TICKERS } from '../constants/majorTickers';
import { useAuth } from '../contexts/AuthContext';

interface PublicStats {
  total_analyses: number;
  total_reports: number;
  unique_tickers_analyzed: number;
}

type HomeTone = 'default' | 'blue' | 'violet' | 'emerald' | 'cyan' | 'indigo' | 'purple' | 'amber';

function HomeCard({
  tone = 'default',
  className = '',
  children,
}: {
  tone?: HomeTone;
  className?: string;
  children: ReactNode;
}) {
  const toneClass = {
    default: 'fd-card',
    blue: 'rounded-xl border border-sky-400/25 bg-sky-500/10 shadow-[0_18px_44px_rgba(14,165,233,0.08)]',
    violet: 'rounded-xl border border-violet-400/25 bg-violet-500/10 shadow-[0_18px_44px_rgba(139,92,246,0.08)]',
    emerald: 'rounded-xl border border-emerald-400/25 bg-emerald-500/10 shadow-[0_18px_44px_rgba(16,185,129,0.08)]',
    cyan: 'rounded-xl border border-cyan-400/25 bg-cyan-500/10 shadow-[0_18px_44px_rgba(34,211,238,0.08)]',
    indigo: 'rounded-xl border border-indigo-400/25 bg-indigo-500/10 shadow-[0_18px_44px_rgba(99,102,241,0.08)]',
    purple: 'rounded-xl border border-fuchsia-400/25 bg-fuchsia-500/10 shadow-[0_18px_44px_rgba(217,70,239,0.08)]',
    amber: 'rounded-xl border border-amber-400/25 bg-amber-500/12 shadow-[0_18px_44px_rgba(245,158,11,0.08)]',
  }[tone];

  return <div className={`${toneClass} min-w-0 ${className}`}>{children}</div>;
}

function HomePill({
  tone = 'default',
  className = '',
  children,
}: {
  tone?: HomeTone;
  className?: string;
  children: ReactNode;
}) {
  const toneClass = {
    default: 'fd-pill text-slate-300',
    blue: 'rounded-full border border-sky-400/30 bg-sky-500/12 text-sky-200',
    violet: 'rounded-full border border-violet-400/30 bg-violet-500/12 text-violet-200',
    emerald: 'rounded-full border border-emerald-400/30 bg-emerald-500/12 text-emerald-200',
    cyan: 'rounded-full border border-cyan-400/30 bg-cyan-500/12 text-cyan-200',
    indigo: 'rounded-full border border-indigo-400/30 bg-indigo-500/12 text-indigo-200',
    purple: 'rounded-full border border-fuchsia-400/30 bg-fuchsia-500/12 text-fuchsia-200',
    amber: 'rounded-full border border-amber-400/30 bg-amber-500/14 text-amber-100',
  }[tone];

  return <div className={`${toneClass} ${className}`}>{children}</div>;
}

function SignificantSevenSkeleton() {
  return (
    <div className="mx-auto grid max-w-6xl auto-rows-fr grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 animate-pulse">
      {SIGNIFICANT_SEVEN_TICKERS.map((ticker) => (
        <div
          key={ticker}
          className="relative h-full overflow-hidden rounded-xl border border-slate-600/60 bg-slate-900/94 p-4 shadow-[0_20px_60px_-36px_rgba(15,23,42,0.72)]"
        >
          <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-r from-slate-800 via-slate-700/60 to-slate-800 opacity-60" />

          <div className="relative flex h-full flex-col gap-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="h-3 w-14 rounded-full bg-slate-700" />
                <div className="mt-3 h-6 w-24 rounded-full bg-slate-600" />
                <div className="mt-2 h-4 w-32 rounded-full bg-slate-800" />
                <div className="mt-2 h-3 w-24 rounded-full bg-slate-800" />
              </div>
              <div className="h-7 w-16 rounded-full bg-slate-700" />
            </div>

            <div className="rounded-xl border border-slate-600/50 bg-slate-950/78 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="h-3 w-12 rounded-full bg-slate-700" />
                <div className="h-5 w-14 rounded-full bg-slate-700" />
              </div>
              <div className="mx-auto h-[112px] w-[112px] rounded-full border border-dashed border-slate-700 bg-slate-800/80" />
            </div>

            <div className="rounded-xl border border-slate-600/50 bg-slate-950/72 p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="h-3 w-16 rounded-full bg-slate-700" />
                <div className="h-5 w-16 rounded-full bg-slate-800" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[1, 2, 3, 4].map((item) => (
                  <div key={item} className="h-9 rounded-lg bg-slate-800" />
                ))}
              </div>
            </div>

            <div>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="h-3 w-14 rounded-full bg-slate-700" />
                <div className="h-3 w-12 rounded-full bg-slate-800" />
              </div>
              <div className="flex flex-wrap gap-2">
                {[1, 2, 3].map((item) => (
                  <div key={item} className="h-6 w-24 rounded-full bg-slate-800" />
                ))}
              </div>
            </div>

            <div className="mt-auto flex items-center justify-between gap-3 border-t border-gray-700 pt-3">
              <div>
                <div className="h-3 w-16 rounded-full bg-slate-800" />
                <div className="mt-2 h-4 w-24 rounded-full bg-slate-700" />
              </div>
              <div className="h-8 w-28 rounded-full bg-slate-700" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
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
        const stats = await tickerApi.getPublicStats();
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
      const response = await tickerApi.getWidgets([...SIGNIFICANT_SEVEN_TICKERS], today);
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

  const MAJOR_STOCKS_LIMIT = SIGNIFICANT_SEVEN_TICKERS.length;
  const hasMajorFlag = widgets.some((w) => w.is_major === true || w.is_major === false);
  const majorFiltered = hasMajorFlag
    ? widgets.filter((w) => w.is_major === true)
    : widgets;
  const majorWidgets = [...majorFiltered]
      .sort((a, b) => {
      const aRank = SIGNIFICANT_SEVEN_RANK.get(a.ticker) ?? Number.MAX_SAFE_INTEGER;
      const bRank = SIGNIFICANT_SEVEN_RANK.get(b.ticker) ?? Number.MAX_SAFE_INTEGER;
      if (aRank !== bRank) return aRank - bRank;
      return a.ticker.localeCompare(b.ticker);
    })
    .slice(0, MAJOR_STOCKS_LIMIT);

  return (
    <div className="min-h-screen overflow-x-hidden">
      {/* SECTION 1: HERO */}
      <section className="bg-gray-900 px-4 py-10 sm:py-12 lg:py-14 pb-6 sm:pb-6 lg:pb-6">
        <div className="max-w-6xl mx-auto">
          <div className="px-2 py-4 sm:px-4 sm:py-6">
            <div className="flex flex-col items-center mb-5">
              <img src={LOGO_PATH} alt="" className="w-20 h-20 sm:w-24 sm:h-24 object-contain" />
              <span className="text-white text-2xl font-bold mt-2 tracking-wide">FlowDeck</span>
            </div>

            <div className="flex justify-center mb-5">
              <Link
                to="/copilot"
                className="group"
              >
                <HomePill tone="blue" className="inline-flex max-w-full flex-wrap items-center justify-center gap-2 px-4 py-2 text-center text-sm font-medium sm:flex-nowrap">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span>New: {COPILOT_NAME}</span>
                  <span className="text-slate-400">Your AI trading copilot</span>
                  <svg className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </HomePill>
              </Link>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-center mb-4 leading-tight">
              <span className="text-white">Invest with the Odds in Your Favor</span>
              <br />
              <span className="text-blue-400">With AI-Powered Actionable Insights.</span>
            </h1>

            <p className="fd-section-copy text-center max-w-3xl mx-auto mb-6">
              A committee of specialized AI agents analyzes market data, news, fundamentals, and risk, then delivers a clear recommendation with full reasoning.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-3xl mx-auto">
              <HomeCard tone="blue" className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-300 mb-1">
                  {publicStats ? publicStats.total_analyses.toLocaleString() : '—'}
                </div>
                <div className="text-blue-400/80 text-sm">AI Analyses Generated</div>
              </HomeCard>
              <HomeCard tone="violet" className="p-4 text-center">
                <div className="text-2xl font-bold text-violet-300 mb-1">
                  {publicStats ? publicStats.total_reports.toLocaleString() : '—'}
                </div>
                <div className="text-violet-400/80 text-sm">Reports Created</div>
              </HomeCard>
              <HomeCard tone="emerald" className="p-4 text-center">
                <div className="text-2xl font-bold text-emerald-300 mb-1">
                  {publicStats ? publicStats.unique_tickers_analyzed.toLocaleString() : '—'}
                </div>
                <div className="text-emerald-400/80 text-sm">Stocks Analyzed</div>
              </HomeCard>
            </div>

            {!user && (
              <HomeCard tone="blue" className="max-w-2xl mx-auto mt-6 px-6 py-5 text-center">
                <p className="text-lg sm:text-xl font-semibold text-white mb-2">
                  Sign in or sign up free
                </p>
                <p className="text-slate-300 text-base mb-4">
                  Unlock access to <strong className="text-white">all company reports</strong>, full AI recommendations, and analysis with no credit card required.
                </p>
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="fd-action-primary"
                >
                  Get started free →
                </button>
              </HomeCard>
            )}
          </div>
        </div>
      </section>

      {/* SECTION 2: LIVE MARKET SNAPSHOT */}
      <section className="px-4 py-6 sm:py-8 bg-gray-900">
        <div className="max-w-6xl mx-auto">
          {/* Ticker Search */}
          <div className="mb-6 max-w-3xl mx-auto">
            <TickerSearch />
          </div>

          <div className="mb-5 text-center sm:text-left">
            <div>
              <h2 className="fd-section-title text-2xl sm:text-3xl">Major Stocks</h2>
              <p className="mt-1 text-sm text-slate-400">
                Live price action, AI scorecards, dominant signals, and the latest report date for the market leaders.
              </p>
            </div>
          </div>

          {error && (
            <div className="mb-6 rounded-md border border-red-500/40 bg-red-950/20 px-4 py-3 text-red-300">
              {error}
            </div>
          )}

          {isLoading && widgets.length === 0 ? (
            <div>
              <div className="mb-4 flex items-center gap-2 text-sm text-slate-400">
                <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Loading major stocks…</span>
              </div>
              <SignificantSevenSkeleton />
            </div>
          ) : widgets.length === 0 ? (
            <HomeCard className="p-12 text-center">
              <p className="text-slate-400 mb-4">No stock data available</p>
              <button
                onClick={loadWidgets}
                className="fd-action-primary"
              >
                Retry
              </button>
            </HomeCard>
          ) : (
            <MajorStockWidgets widgets={majorWidgets} tickerToName={tickerToName} />
          )}
        </div>
      </section>

      {/* SECTION 3: PLATFORM OVERVIEW (How It Works + Features) */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="fd-section-title mb-3">
              Everything You Need to Know
            </h2>
            <p className="fd-section-copy">
              A transparent, multi-step AI process — and all the tools to act on it
            </p>
          </div>

          <h3 className="text-lg font-semibold text-slate-300 uppercase tracking-wider mb-6">
            Platform Features
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
            <HomeCard className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Live Market Data</h4>
              <p className="text-slate-400 text-sm">
                Real-time prices, volume, and ranges — plus AI-driven recommendations synthesized from news, SEC filings, fundamentals, technicals, and sentiment.
              </p>
            </HomeCard>
            <HomeCard className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Analytic Signals</h4>
              <p className="text-slate-400 text-sm">
                FlowDeck automatically extracts important anomalies and market events for each ticker, including price spikes, volatility shifts, insider activity, earnings timing, and other deterministic signals surfaced directly in the platform.
              </p>
            </HomeCard>
            <HomeCard className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Deep AI Analysis, On Demand</h4>
              <p className="text-slate-400 text-sm">
                Trigger a full multi-agent analysis for any stock, any time. A committee of specialized AI analysts — covering market data, news, fundamentals, technicals, and risk — each produce their own report before a final recommendation is synthesized. Every angle covered, every time.
              </p>
            </HomeCard>
            <HomeCard className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Transparent Reports & Recommendations</h4>
              <p className="text-slate-400 text-sm">
                Get clear <strong className="text-white">BUY / SELL / HOLD</strong> recommendations backed by comprehensive AI analysis — and read the full reasoning across multiple report tabs.
              </p>
            </HomeCard>
            <HomeCard className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">Stock Subscriptions & Dashboard</h4>
              <p className="text-slate-400 text-sm">
                Subscribe to stocks and get email updates when new analysis reports are available. Track your watchlist and portfolio performance from a personalized dashboard.
              </p>
            </HomeCard>
            <HomeCard tone="blue" className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">{COPILOT_NAME} — A Powerful Trading Assistant</h4>
              <p className="text-slate-300 text-sm">
                {COPILOT_NAME} can <strong className="text-white">search the live web</strong> for breaking news and analyst updates, <strong className="text-white">write and execute Python code</strong> for financial modelling and statistical analysis, and <strong className="text-white">generate interactive charts</strong> — line, bar, area, and scatter — rendered directly in the chat. It also knows your watchlist and preferences, so all of FlowDeck's proprietary reports are accessible in the same conversation with personalized context.
              </p>
            </HomeCard>
            <HomeCard className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <Link to="/api-docs" className="hover:text-slate-200 transition-colors">REST API — Programmatic Access</Link>
              </h4>
              <p className="text-slate-400 text-sm">
                Integrate FlowDeck into your trading systems with our <strong className="text-white">REST API</strong>. The system is <strong className="text-white">autonomous-agent ready</strong>: agents can register, fetch market data, chat with the AI analyst, and start analyses without human intervention. Create secure API keys, access all AI reports and recommendations programmatically, and fetch real-time market data. Perfect for algorithmic trading, portfolio tools, and custom integrations. <a href="https://flowdeck.biz/api/SKILL.md" target="_blank" rel="noopener noreferrer" className="text-slate-300 hover:text-white underline">View SKILL.md →</a>
              </p>
            </HomeCard>
            <HomeCard tone="cyan" className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <Link to="/newsroom" className="hover:text-cyan-300 transition-colors">
                  Personal Newsroom
                </Link>
              </h4>
              <p className="text-slate-300 text-sm">
                Open a <strong className="text-white">personal newsroom curated specifically for you</strong> from your subscribed stocks. FlowDeck turns your watchlist into a clean, browsable stream with a lead story, fast-scan headlines, and a tailored news wire for your names.
              </p>
            </HomeCard>
            <HomeCard tone="indigo" className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <Link to="/tps" className="hover:text-indigo-300 transition-colors">TPS — Structured Trade Plans</Link>
              </h4>
              <p className="text-slate-300 text-sm">
                Every AI analysis automatically produces a <strong className="text-white">Trading Plan Specification (TPS)</strong> — a schema-validated JSON object with entry zone, stop-loss, take-profit targets, position sizing, and invalidation rules. No ambiguity, no prose to interpret.
              </p>
            </HomeCard>
            <HomeCard tone="purple" className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <a href="https://flowdeck.biz/api/SKILL.md" target="_blank" rel="noopener noreferrer" className="hover:text-purple-300 transition-colors inline-flex items-center gap-1">
                  SKILL.md — Autonomous Agent Integration
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </h4>
              <p className="text-slate-300 text-sm">
                A comprehensive API guide for AI agents to autonomously interact with FlowDeck. Agents can register, fetch market data, chat with the AI analyst, and start analyses — all without human intervention. <a href="https://flowdeck.biz/api/SKILL.md" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline">View SKILL.md →</a>
              </p>
            </HomeCard>
            <HomeCard tone="amber" className="p-6">
              <h4 className="text-lg font-semibold text-white mb-2">
                <Link to={user ? '/brief' : '#'} onClick={!user ? () => setShowAuthModal(true) : undefined} className="hover:text-amber-300 transition-colors">Briefing</Link>
              </h4>
              <p className="text-slate-300 text-sm">
                Get a personalized <strong className="text-white">daily or weekly brief</strong> that turns your watchlist into a concise, readable narrative. Control the tone (Balanced, Concise, Professional, Technical), add your own note, and let FlowDeck highlight what changed and what to watch next across your subscribed tickers. Runs directly from your dashboard using the same AI analysis stack that powers full reports.
              </p>
            </HomeCard>
          </div>

          <HomeCard className="p-8">
            <h3 className="text-lg font-semibold text-slate-300 uppercase tracking-wider mb-6">
              How the AI Analysis Team Works
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <HomeCard className="p-6">
                <h4 className="text-lg font-semibold text-white mb-2">1. Analyst Team</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Six specialized AI analysts — covering market trends, news, fundamentals, SEC filings, technicals, and social sentiment — each independently research the stock and produce a scored report. Every angle is covered before any debate begins.
                </p>
              </HomeCard>
              <HomeCard className="p-6">
                <h4 className="text-lg font-semibold text-white mb-2">2. Investment Debate → Trade Plan</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Bull and Bear researchers argue the investment case across multiple rounds using all analyst reports. A Research Manager then adjudicates, producing a conviction score, return scenarios, and a structured investment plan — which a Trader agent refines into an actionable trade strategy.
                </p>
              </HomeCard>
              <HomeCard className="p-6">
                <h4 className="text-lg font-semibold text-white mb-2">3. Risk Debate → Final Decision</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Three risk agents — Aggressive, Cautious, and Neutral — debate the trade plan in round-robin. A Risk Judge weighs all upstream scores and risk arguments to produce the final verdict: <strong className="text-green-400">BUY</strong>, <strong className="text-red-400">SELL</strong>, or <strong className="text-yellow-400">HOLD</strong>.
                </p>
              </HomeCard>
            </div>

            <div className="text-center">
              <Link
                to="/how-it-works"
                className="fd-action-secondary"
              >
                Read full explanation →
              </Link>
            </div>
          </HomeCard>
        </div>
      </section>

      {/* SECTION 4: TRADER COPILOT SPOTLIGHT */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Left: copy */}
            <div className="min-w-0">
              <HomePill tone="blue" className="inline-flex items-center gap-2 px-3 py-1.5 mb-5 text-xs font-semibold uppercase tracking-wider">
                <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span>Trading Copilot — {COPILOT_NAME}</span>
              </HomePill>
              <h2 className="fd-section-title mb-4 leading-tight">
                Research and Chat,<br />
                <span className="text-blue-400">Side by Side</span>
              </h2>
              <p className="fd-section-copy mb-6">
                {COPILOT_NAME} is your Trading Copilot — a three-panel workspace: your watchlist on the left, full stock detail in the middle, and an AI chat on the right. The agent knows your watchlist, your context, and your preferences, so follow-up questions stay personal and on track while you read the report.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  { icon: '📊', text: 'Live quote, AI recommendation, and all report tabs in one view' },
                  { icon: '🤖', text: 'AI chat with full context — selected ticker, watchlist, live data, reports, and your preferences' },
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
                className="fd-action-primary"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Open {COPILOT_NAME}
              </Link>
            </div>

            {/* Right: visual mockup of the 3-panel layout */}
            <HomeCard tone="blue" className="overflow-hidden">
              {/* Fake window chrome */}
              <div className="flex items-center gap-1.5 border-b border-sky-400/15 bg-sky-500/8 px-4 py-2.5">
                <span className="w-3 h-3 rounded-full bg-red-500/70" />
                <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
                <span className="w-3 h-3 rounded-full bg-green-500/70" />
                <div className="flex items-center gap-1.5 ml-3">
                  <svg className="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="text-xs font-medium text-slate-300">{COPILOT_NAME}</span>
                </div>
              </div>
              {/* Three-panel layout preview */}
              <div className="flex h-64 text-xs">
                {/* Sidebar */}
                <div className="flex w-28 shrink-0 flex-col gap-1.5 border-r border-slate-700 bg-slate-950/75 p-2">
                  <div className="text-slate-500 text-[10px] uppercase tracking-wider mb-1 px-1">Watchlist</div>
                  {['AAPL', 'NVDA', 'MSFT', 'TSLA', 'GOOGL'].map((t, i) => (
                    <div
                      key={t}
                      className={`flex items-center justify-between rounded-sm px-2 py-1.5 ${i === 1 ? 'border border-sky-400/30 bg-sky-500/15' : 'hover:bg-slate-800/60'}`}
                    >
                      <span className={`font-semibold ${i === 1 ? 'text-white' : 'text-slate-300'}`}>{t}</span>
                      <span className={`text-[10px] ${i % 2 === 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {i % 2 === 0 ? '+1.2%' : '-0.8%'}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Stock detail */}
                <div className="flex-1 min-w-0 border-r border-slate-700 bg-slate-950 p-3 flex flex-col gap-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-white font-bold text-sm">NVDA</div>
                      <div className="text-slate-400 text-[10px]">NVIDIA Corporation</div>
                    </div>
                    <div className="text-right">
                      <div className="text-white font-semibold text-sm">$875.40</div>
                      <div className="text-green-400 text-[10px]">+2.34%</div>
                    </div>
                  </div>
                  <div className="inline-flex self-start rounded-sm border border-emerald-400/30 bg-emerald-500/12 px-2 py-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                    <span className="text-green-300 text-[10px] font-semibold">BUY</span>
                  </div>
                  <div className="flex gap-1 mt-1">
                    {['Market', 'News', 'Fundamentals', 'Technical'].map((tab, i) => (
                      <div
                        key={tab}
                        className={`px-2 py-0.5 rounded text-[9px] font-medium ${i === 0 ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'}`}
                      >
                        {tab}
                      </div>
                    ))}
                  </div>
                  <div className="flex-1 bg-slate-900/70 rounded-sm p-2 mt-1">
                    <div className="h-2 bg-slate-700 rounded mb-1.5 w-full" />
                    <div className="h-2 bg-slate-700 rounded mb-1.5 w-4/5" />
                    <div className="h-2 bg-slate-700 rounded w-3/5" />
                  </div>
                </div>
                {/* Chat panel */}
                <div className="w-44 shrink-0 bg-slate-950 flex flex-col">
                  <div className="px-2.5 py-2 border-b border-slate-700 bg-slate-900/80 flex items-center gap-1.5">
                    <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                    </div>
                    <span className="text-white text-[10px] font-semibold">{COPILOT_NAME}</span>
                  </div>
                  <div className="flex-1 p-2 flex flex-col gap-2 overflow-hidden">
                    <div className="self-end bg-blue-600 text-white rounded-md px-2 py-1 text-[9px] max-w-[90%]">
                      What are the key risks for NVDA?
                    </div>
                    <div className="bg-slate-800/90 text-slate-200 rounded-md px-2 py-1.5 text-[9px] leading-relaxed">
                      <div className="h-1.5 bg-slate-700 rounded mb-1 w-full" />
                      <div className="h-1.5 bg-slate-700 rounded mb-1 w-4/5" />
                      <div className="h-1.5 bg-slate-700 rounded w-3/5" />
                    </div>
                    <div className="self-end bg-blue-600 text-white rounded-md px-2 py-1 text-[9px] max-w-[90%]">
                      Compare with AMD
                    </div>
                  </div>
                  <div className="px-2 pb-2">
                    <div className="bg-slate-800/90 rounded-sm border border-slate-700 px-2 py-1.5 flex items-center gap-1">
                      <span className="text-slate-500 text-[9px] flex-1">Ask about NVDA…</span>
                      <div className="w-4 h-4 rounded bg-blue-600 flex items-center justify-center">
                        <svg className="w-2.5 h-2.5 text-white rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </HomeCard>
          </div>
        </div>
      </section>

      {/* SECTION 4b: TPS — TRADING PLAN SPECIFICATION */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Left: TPS JSON mockup */}
            <HomeCard tone="indigo" className="order-2 overflow-hidden lg:order-1">
              {/* Window chrome */}
              <div className="flex items-center justify-between border-b border-indigo-400/20 bg-indigo-500/10 px-4 py-2.5">
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
                <pre className="bg-slate-900/80 rounded-sm p-4 overflow-x-auto whitespace-pre text-left">
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
            </HomeCard>

            {/* Right: copy */}
            <div className="order-1 min-w-0 lg:order-2">
              <HomePill tone="indigo" className="inline-flex items-center gap-2 px-3 py-1.5 mb-5 text-xs font-semibold uppercase tracking-wider">
                <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <span>TPS v0.1 — Trading Plan Specification</span>
              </HomePill>
              <h2 className="fd-section-title mb-4 leading-tight">
                Every Analysis Includes<br />
                <span className="text-indigo-400">a Structured Trade Plan</span>
              </h2>
              <p className="fd-section-copy mb-6">
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
                    <span className="text-slate-300 text-sm leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
              <Link
                to="/tps"
                className="fd-action-secondary"
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
            <HomeCard tone="emerald" className="order-2 overflow-hidden lg:order-1">
              {/* Window chrome */}
              <div className="flex items-center justify-between border-b border-emerald-400/20 bg-emerald-500/10 px-4 py-2.5">
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
                <pre className="bg-slate-900/80 rounded-sm p-4 overflow-x-auto whitespace-pre text-left">
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
            </HomeCard>

            {/* Right: copy */}
            <div className="order-1 min-w-0 lg:order-2">
              <HomePill tone="emerald" className="inline-flex items-center gap-2 px-3 py-1.5 mb-5 text-xs font-semibold uppercase tracking-wider">
                <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                <span>Programmatic API Access</span>
              </HomePill>
              <h2 className="fd-section-title mb-4 leading-tight">
                Integrate FlowDeck<br />
                <span className="text-emerald-400">Into Your Trading Systems</span>
              </h2>
              <p className="fd-section-copy mb-6">
                Access FlowDeck's AI-powered analysis programmatically with our REST API. Perfect for algorithmic trading systems, portfolio management tools, and custom integrations. The system is <strong className="text-emerald-300">autonomous-agent ready</strong> — AI agents can interact with FlowDeck, get market data and analyses, and act on recommendations without human intervention.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  { icon: '🤖', text: 'Autonomous-agent ready — let AI agents register, fetch data, chat with the analyst, and start analyses via API' },
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
                    <span className="text-slate-300 text-sm leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-3">
                <Link
                  to="/api-docs"
                  className="fd-action-primary"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  View API Documentation
                </Link>
                <Link
                  to={user ? '/profile#api-keys' : '#'}
                  onClick={!user ? () => setShowAuthModal(true) : undefined}
                  className="fd-action-secondary"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                  Create API Key
                </Link>
                <a
                  href="https://flowdeck.biz/api/SKILL.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="fd-action-secondary"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  SKILL.md — Agent Integration
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 3d: DAILY BRIEFING */}
      <section className="px-4 py-12 sm:py-16 bg-gray-900 border-t border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            {/* Left: copy */}
            <div className="min-w-0">
              <HomePill tone="amber" className="inline-flex items-center gap-2 px-3 py-1.5 mb-5 text-xs font-semibold uppercase tracking-wider">
                <svg className="w-3.5 h-3.5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l2.5 2.5M12 3a9 9 0 100 18 9 9 0 000-18z"
                  />
                </svg>
                <span>Briefing</span>
              </HomePill>
              <h2 className="fd-section-title mb-4 leading-tight">
                Your Market Briefing,<br />
                <span className="text-amber-300">Written for You</span>
              </h2>
              <p className="fd-section-copy mb-6">
                FlowDeck&apos;s briefing capability turns your watchlist and portfolio into a short, readable narrative you can
                actually keep up with. Choose a <strong className="text-white">daily or weekly</strong> brief, add your own note, and let the
                system highlight what changed and what to watch next across your subscribed tickers.
              </p>
              <ul className="space-y-3 mb-8">
                {[
                  {
                    icon: '📰',
                    text: 'Concise story of the market plus the moves in your subscribed tickers — not a wall of numbers.',
                  },
                  {
                    icon: '🎛️',
                    text: 'Control the tone (Balanced, Concise, Professional, Technical) and add a one-off note for each run.',
                  },
                  {
                    icon: '🎯',
                    text: 'Optionally pick focus tickers or let FlowDeck select the most important names based on moves and news.',
                  },
                  {
                    icon: '⚡',
                    text: 'Runs directly from your dashboard and uses the same AI analysis stack that powers full reports.',
                  },
                ].map(({ icon, text }) => (
                  <li key={text} className="flex items-start gap-3">
                    <span className="text-lg leading-none mt-0.5">{icon}</span>
                    <span className="text-slate-300 text-sm leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
              <Link
                to={user ? '/brief' : '#'}
                onClick={!user ? () => setShowAuthModal(true) : undefined}
                className="fd-action-secondary"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 8h5l-1.405 1.405A2 2 0 0118 10.828V17a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h7" />
                </svg>
                Open Daily Brief tab
              </Link>
            </div>

            {/* Right: visual mockup of a brief */}
            <HomeCard tone="amber" className="overflow-hidden">
              {/* Window chrome */}
              <div className="flex items-center justify-between border-b border-amber-400/20 bg-amber-500/10 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-red-500/70" />
                  <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
                  <span className="w-3 h-3 rounded-full bg-green-500/70" />
                  <span className="ml-3 text-xs text-slate-300 font-medium">Briefing</span>
                </div>
                <span className="text-[10px] text-amber-200 font-mono uppercase">Daily · Balanced</span>
              </div>
              <div className="p-4 space-y-3 text-sm">
                <div className="text-xs font-mono text-amber-200 uppercase tracking-widest">Today&apos;s overview</div>
                <div className="space-y-1.5 text-gray-100">
                  <div className="h-2.5 bg-slate-700 rounded w-11/12" />
                  <div className="h-2.5 bg-slate-700 rounded w-10/12" />
                  <div className="h-2.5 bg-slate-700 rounded w-9/12" />
                </div>
                <div className="pt-2 border-t border-slate-700/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                      What happened in your portfolio
                    </span>
                    <span className="text-[11px] text-emerald-300 font-mono">AAPL · NVDA · MSFT</span>
                  </div>
                  <div className="space-y-1.5 text-gray-100">
                    <div className="h-2.5 bg-slate-700 rounded w-10/12" />
                    <div className="h-2.5 bg-slate-700 rounded w-9/12" />
                    <div className="h-2.5 bg-slate-700 rounded w-8/12" />
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-700/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white uppercase tracking-wider">What to watch next</span>
                    <span className="text-[11px] font-mono font-semibold text-white">Focus tickers</span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-slate-200">
                      <span>AAPL earnings next week</span>
                      <span className="text-emerald-300">+1.8%</span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-200">
                      <span>NVDA breaks to new highs</span>
                      <span className="text-emerald-300">+3.2%</span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-200">
                      <span>MSFT pulls back to support</span>
                      <span className="text-red-300">-0.9%</span>
                    </div>
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-700/80 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">
                    Style: <span className="text-slate-200">Balanced</span> · Span:{' '}
                    <span className="text-slate-200 capitalize">daily</span>
                  </span>
                  <span className="text-[11px] text-amber-300">Built with your note</span>
                </div>
              </div>
            </HomeCard>
          </div>
        </div>
      </section>

      {/* SECTION 5: FINAL CTA */}
      <section className="px-4 py-10 sm:py-12 bg-gray-900 border-t border-gray-700">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="fd-section-title lg:text-5xl mb-4">
            Ready to Invest Smarter?
          </h2>
          {user ? (
            <p className="fd-section-copy mb-8 max-w-2xl mx-auto">
              Start exploring stocks and generating AI analysis reports with your token balance.
            </p>
          ) : (
            <div className="mb-8 max-w-2xl mx-auto">
              <p className="fd-section-copy mb-4">
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
                  <span><strong className="text-white">Personal Newsroom</strong> curated specifically for your subscribed stocks</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">Stock subscriptions</strong> with email updates</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">{COPILOT_NAME}</strong> — your Trading Copilot that knows you, your watchlist, and your preferences</span>
                </li>
                <li className="flex items-start">
                  <span className="text-blue-400 mr-2">✓</span>
                  <span><strong className="text-white">AI Analyst Agent</strong> — chat with live market data, analysis, and your personal context</span>
                </li>
              </ul>
            </div>
          )}
          <div className="flex flex-col items-center justify-center gap-6">
            {user ? (
              <div className="flex flex-wrap gap-4 justify-center">
                <Link
                  to="/dashboard"
                  className="fd-action-primary px-8 py-4 text-lg"
                >
                  Go to Dashboard →
                </Link>
                <Link
                  to="/copilot"
                  className="fd-action-secondary px-8 py-4 text-lg"
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
                className="fd-action-primary px-8 py-4 text-lg"
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
            <h2 className="fd-section-title mb-3">
              Generate Reports with Tokens
            </h2>
            <p className="fd-section-copy max-w-2xl mx-auto">
              Each AI analysis report costs tokens. New users get <strong className="text-blue-400">1,000 free tokens</strong> on
              sign-up — enough to generate <strong className="text-white">multiple reports</strong>, chat with <strong className="text-white">{COPILOT_NAME}</strong> the trader assistant, and fully explore the platform.
            </p>
          </div>

          {/* Token Packages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            <HomeCard className="px-4 py-3 text-center">
              <h3 className="text-lg font-semibold text-white mb-1">Starter Pack</h3>
              <div className="text-3xl font-bold text-white mb-0.5">500</div>
              <div className="text-slate-400 text-sm mb-2">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$5.00</div>
            </HomeCard>
            <HomeCard tone="blue" className="px-4 py-3 text-center">
              <h3 className="text-lg font-semibold text-white mb-1">Popular Pack</h3>
              <div className="text-3xl font-bold text-white mb-0.5">1,000</div>
              <div className="text-slate-300 text-sm mb-2">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$9.00</div>
              <div className="text-green-400 text-xs mt-1">Save 10%</div>
            </HomeCard>
            <HomeCard className="px-4 py-3 text-center">
              <h3 className="text-lg font-semibold text-white mb-1">Best Value Pack</h3>
              <div className="text-3xl font-bold text-white mb-0.5">2,500</div>
              <div className="text-slate-400 text-sm mb-2">tokens</div>
              <div className="text-2xl font-semibold text-blue-400">$20.00</div>
              <div className="text-green-400 text-xs mt-1">Save 20%</div>
            </HomeCard>
          </div>

          <div className="text-center">
            {user ? (
                <Link
                  to="/profile#purchase-tokens"
                  className="fd-action-primary px-8 py-4 text-lg"
                >
                  Buy Tokens →
                </Link>
            ) : (
              <button
                onClick={() => setShowAuthModal(true)}
                className="fd-action-primary px-8 py-4 text-lg"
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
