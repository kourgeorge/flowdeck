import { useEffect, useMemo } from 'react';
import ChatView, { useChatState } from './ChatView';
import { useAuth } from '../contexts/AuthContext';
import { profileApi } from '../services/authApi';
import { COPILOT_NAME } from '../config';

function getSuggestedQuestions(ticker?: string | null, tickers?: string[]): string[] {
  if (ticker) {
    return [
      `What is FlowDeck's recommendation for ${ticker}?`,
      `Summarize the AI analysis reports for ${ticker}`,
      `What are the key risks and opportunities for ${ticker}?`,
      `What do the technical indicators say about ${ticker}?`,
      `Show me the latest news and insider activity for ${ticker}`,
      `Calculate ${ticker}'s total return and max drawdown over the past year`,
    ];
  }
  if (tickers && tickers.length > 0) {
    const sample = tickers.slice(0, 3);
    return [
      `Give me an overview of all my focus tickers: ${tickers.join(', ')}`,
      `Which of my focus tickers has the best AI recommendation right now?`,
      `Compare the fundamentals of ${sample.join(' and ')}`,
      `What are the key risks across my focus tickers?`,
      `Show me the latest news for my focus tickers`,
      `Calculate the correlation between ${sample[0]} and ${sample[1] ?? 'SPY'} daily returns over the past year`,
    ];
  }
  return [
    "What's the current price and today's performance for AAPL?",
    'Compare MSFT and GOOGL fundamentals',
    'What are the key risks in the current market?',
    'Show me recent insider activity for NVDA',
    "What is FlowDeck's recommendation for TSLA?",
    'Summarize the latest news for AMZN',
    'Calculate the Pearson correlation between META and IBM daily returns over the past year',
  ];
}

export interface CopilotChatPanelProps {
  /** Currently selected ticker — drives suggested questions */
  selectedTicker?: string | null;
  /** All tickers in the user's watchlist — gives the AI full context */
  tickers?: string[];
  /** Whether the panel is collapsed to a narrow strip */
  collapsed?: boolean;
  /** Called when the user clicks the collapse/expand toggle */
  onToggleCollapse?: () => void;
}

export default function CopilotChatPanel({
  selectedTicker,
  tickers = [],
  collapsed = false,
  onToggleCollapse,
}: CopilotChatPanelProps) {
  const { user } = useAuth();
  // Build context object with all tickers so the AI knows the full watchlist
  const context = useMemo(
    () => (tickers.length > 0 ? { tickers } : undefined),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tickers.join(',')],
  );
  const chat = useChatState(undefined, context);

  // Fetch token balance when user logs in
  useEffect(() => {
    if (!user) { chat.setTokenBalance(null); return; }
    profileApi.getMe().then((me) => {
      chat.setTokenBalance(me.token_balance);
    }).catch(() => {});
  }, [user]);

  // Focus input when panel expands
  useEffect(() => {
    if (!collapsed) {
      setTimeout(() => chat.inputRef.current?.focus(), 50);
    }
  }, [collapsed]);

  // ── Collapsed state: show a vertical strip with a toggle button ──
  if (collapsed) {
    return (
      <div className="flex flex-col items-center w-6 shrink-0 border-l border-gray-700 bg-gray-800/50 py-3 gap-2">
        <button
          type="button"
          onClick={onToggleCollapse}
          title={`Expand ${COPILOT_NAME}`}
          className="flex items-center justify-center w-6 h-6 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded transition-colors"
        >
          <svg className="w-3.5 h-3.5 rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1 flex items-center justify-center">
          <span
            className="text-xs text-gray-500 font-medium select-none"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            {COPILOT_NAME}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0 border-l border-gray-700 bg-gray-900">
      {/* Header */}
      <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 px-3 py-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold text-white leading-tight">{COPILOT_NAME}</span>
            </div>
            <p className="text-xs text-slate-400 leading-tight">AI-powered · full analysis access</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Token balance */}
          {user && chat.tokenBalance !== null && (
            <div
              key={chat.tokenBalance}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-700/60 border border-slate-600/60"
              title="Remaining token balance"
            >
              <svg className="w-3 h-3 text-yellow-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z" />
              </svg>
              <span className="text-xs font-medium text-yellow-300 tabular-nums">{chat.tokenBalance.toLocaleString()}</span>
            </div>
          )}

          {/* New chat button */}
          {user && (
            <button
              type="button"
              onClick={chat.clearChat}
              disabled={chat.messages.length === 0 && !chat.error}
              title="New chat"
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors px-2 py-1 rounded-lg hover:bg-gray-700 border border-gray-600 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New
            </button>
          )}

          {/* Collapse toggle */}
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              title={`Collapse ${COPILOT_NAME}`}
              className="flex items-center justify-center w-6 h-6 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Chat content via shared ChatView */}
      <ChatView
        chat={chat}
        isAuthenticated={!!user}
        suggestedQuestions={getSuggestedQuestions(selectedTicker, tickers)}
        welcomeHeading="Ask me anything about the market"
        welcomeSubtext={
          selectedTicker
            ? `I have access to AI reports, live prices, fundamentals, news, technical indicators, and insider activity for ${selectedTicker}. I also know about all ${tickers.length} focus tickers in your list.`
            : tickers.length > 0
              ? `I have full context for all your focus tickers: ${tickers.join(', ')}. Ask me to compare, summarize, or analyze any of them.`
              : 'I have access to live prices, AI reports, fundamentals, news, technical indicators, and insider activity.'
        }
        inputPlaceholder={
          user
            ? selectedTicker
              ? `Ask about ${selectedTicker} or any of your ${tickers.length} focus tickers…`
              : tickers.length > 0
                ? `Ask about your ${tickers.length} focus tickers…`
                : 'Ask about any stock…'
            : 'Sign in to start chatting…'
        }
        inputFooter={
          <div className="shrink-0 px-3 py-1 bg-slate-900/40 border-t border-slate-700/50">
            <p className="text-xs text-slate-500 text-center">
              Each message uses tokens · Not financial advice
            </p>
          </div>
        }
      />
    </div>
  );
}

// Made with Bob