import { useEffect, useState } from 'react';
import ChatView, { useChatState } from '../components/ChatView';
import { useAuth } from '../contexts/AuthContext';
import { profileApi } from '../services/authApi';

const SUGGESTED_QUESTIONS = [
  "What's the current price and today's performance for AAPL?",
  'Compare MSFT and GOOGL fundamentals',
  'What are the key risks in the current market?',
  'Show me recent insider activity for NVDA',
  "What is FlowDeck's recommendation for TSLA?",
  'Summarize the latest news for AMZN',
  'Calculate the Pearson correlation between META and IBM daily returns over the past year',
];

export default function ChatPage() {
  const { user } = useAuth();
  const [displayName, setDisplayName] = useState<string | null>(null);

  const chat = useChatState();

  // Fetch initial token balance and display name when user is logged in
  useEffect(() => {
    if (!user) { chat.setTokenBalance(null); setDisplayName(null); return; }
    profileApi.getMe().then((me) => {
      chat.setTokenBalance(me.token_balance);
      setDisplayName(me.name && me.name.trim() ? me.name.trim() : null);
    }).catch(() => {});
  }, [user]);

  // Focus input on mount
  useEffect(() => {
    chat.inputRef.current?.focus();
  }, []);

  const greeting = user
    ? displayName ?? (user.email.split('@')[0].charAt(0).toUpperCase() + user.email.split('@')[0].slice(1))
    : null;

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Page header */}
      <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-semibold text-white">AI Analyst Agent</h1>
            <p className="text-xs text-slate-400">AI-powered · full analysis access</p>
          </div>
        </div>
        {user && (
          <div className="flex items-center gap-2">
            {chat.tokenBalance !== null && (
              <div
                key={chat.tokenBalance}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-700/60 border border-slate-600/60 transition-all duration-300"
                title="Remaining token balance"
              >
                <svg className="w-3.5 h-3.5 text-yellow-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z" />
                </svg>
                <span className="text-xs font-medium text-yellow-300 tabular-nums">{chat.tokenBalance.toLocaleString()}</span>
                <span className="text-xs text-slate-400">tokens</span>
              </div>
            )}
            <button
              type="button"
              onClick={chat.clearChat}
              disabled={chat.messages.length === 0 && !chat.error}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors px-3 py-1.5 rounded-lg hover:bg-gray-700 border border-gray-600 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed"
              title="Start a new chat"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New chat
            </button>
          </div>
        )}
      </div>

      {/* Centered content wrapper for the messages + input */}
      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex flex-col flex-1 min-h-0 max-w-3xl w-full mx-auto px-4">
          <ChatView
            chat={chat}
            isAuthenticated={!!user}
            suggestedQuestions={SUGGESTED_QUESTIONS}
            welcomeHeading={
              greeting
                ? `Hi ${greeting}!\nAsk me anything about the market`
                : undefined
            }
            welcomeSubtext="I have access to live prices, AI reports, fundamentals, news, technicals, insider activity & your watchlist."
            inputPlaceholder={user ? 'Ask about any stock…' : 'Sign in to start chatting…'}
            inputFooter={
              <p className="text-xs text-slate-500 text-center py-1.5">
                AI can make mistakes — always verify important information · Not financial advice
              </p>
            }
          />
        </div>
      </div>
    </div>
  );
}

// Made with Bob