import { useCallback, useEffect, useState } from 'react';
import ChatView, { useChatState, type ChatMessageWithMeta } from '../components/ChatView';
import PageHeader from '../components/PageHeader';
import { useAuth } from '../contexts/AuthContext';
import { profileApi } from '../services/authApi';
import { chatApi, type ChatSessionListItem, type ChatMessageWithMetaApi } from '../services/api';

const SUGGESTED_QUESTIONS = [
  "What's the current price and today's performance for AAPL?",
  'Compare MSFT and GOOGL fundamentals',
  'What are the key risks in the current market?',
  'Show me recent insider activity for NVDA',
  "What is FlowDeck's recommendation for TSLA?",
  'Summarize the latest news for AMZN',
  'Calculate the Pearson correlation between META and IBM daily returns over the past year',
];

function apiMessageToChatMessageWithMeta(m: ChatMessageWithMetaApi): ChatMessageWithMeta {
  return {
    role: m.role as 'user' | 'assistant',
    content: m.content,
    tokens_used: m.tokens_used ?? undefined,
    tools_called: m.tools_called ?? undefined,
    tool_call_events: m.tool_call_events ?? undefined,
    skill_activation_events: m.skill_activation_events ?? undefined,
    charts: m.charts ?? undefined,
    follow_up_questions: m.follow_up_questions ?? undefined,
  };
}

export default function ChatPage() {
  const { user } = useAuth();
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<ChatSessionListItem[]>([]);
  const [historyCollapsed, setHistoryCollapsed] = useState(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) return true;
    return false;
  });

  const refreshSessions = useCallback(() => {
    if (!user) return;
    chatApi.getChatSessions().then(setSessions).catch(() => {});
  }, [user]);

  const onStreamDone = useCallback(
    (newSessionId?: number) => {
      if (newSessionId != null) setSessionId(newSessionId);
      refreshSessions();
    },
    [refreshSessions],
  );

  const chat = useChatState(undefined, undefined, sessionId, onStreamDone);

  // Fetch initial token balance and display name when user is logged in
  useEffect(() => {
    if (!user) {
      chat.setTokenBalance(null);
      setDisplayName(null);
      setSessions([]);
      setSessionId(null);
      return;
    }
    profileApi.getMe().then((me) => {
      chat.setTokenBalance(me.token_balance);
      setDisplayName(me.name && me.name.trim() ? me.name.trim() : null);
    }).catch(() => {});
  }, [user]);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  // Focus input on mount
  useEffect(() => {
    chat.inputRef.current?.focus();
  }, []);

  const handleOpenSession = (id: number) => {
    chatApi.getChatSession(id).then((detail) => {
      setSessionId(detail.id);
      chat.setMessages(detail.messages.map(apiMessageToChatMessageWithMeta));
      setHistoryCollapsed(true);
    }).catch(() => {});
  };

  const handleDeleteSession = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!user) return;
    chatApi.deleteChatSession(id).then(() => {
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (sessionId === id) {
        setSessionId(null);
        chat.clearChat();
      }
    }).catch(() => {});
  };

  const greeting = user
    ? displayName ?? (user.email.split('@')[0].charAt(0).toUpperCase() + user.email.split('@')[0].slice(1))
    : null;

  return (
    <div className="flex flex-col h-full bg-gray-900">
      <PageHeader
        title="AI Analyst Agent"
        icon={
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        }
      >
        {user && (
          <>
            {chat.tokenBalance !== null && (
              <div
                key={chat.tokenBalance}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-700/60 border border-slate-600/60 transition-all duration-300"
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
              onClick={() => { setSessionId(null); chat.clearChat(); }}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors px-2.5 py-1 rounded-lg hover:bg-gray-700 border border-gray-600 hover:border-gray-500"
              title="Start a new chat"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New chat
            </button>
          </>
        )}
      </PageHeader>

      <div className="flex flex-1 min-h-0">
        {/* Session list sidebar (authenticated only), collapsible */}
        {user && (
          <aside
            className={`shrink-0 border-r border-gray-700 bg-gray-800/50 flex flex-col overflow-hidden transition-[width] duration-200 ${
              historyCollapsed ? 'w-12' : 'w-56'
            }`}
          >
            <div className="flex items-center border-b border-gray-700 min-h-[40px]">
              {historyCollapsed ? (
                <button
                  type="button"
                  onClick={() => setHistoryCollapsed(false)}
                  title="Expand chat history"
                  className="w-full flex items-center justify-center py-2 text-slate-400 hover:text-white hover:bg-gray-700/50 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </button>
              ) : (
                <>
                  <div className="flex-1 px-3 py-2 min-w-0">
                    <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide truncate">Chat history</h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => setHistoryCollapsed(true)}
                    title="Collapse chat history"
                    className="shrink-0 w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-gray-700/50 transition-colors"
                    aria-label="Collapse chat history"
                  >
                    <svg className="w-4 h-4 rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </>
              )}
            </div>
            {!historyCollapsed && (
              <ul className="flex-1 overflow-y-auto py-1">
                {sessions.map((s) => (
                  <li key={s.id}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => handleOpenSession(s.id)}
                      onKeyDown={(e) => e.key === 'Enter' && handleOpenSession(s.id)}
                      className={`group flex items-center gap-2 px-3 py-2 text-left cursor-pointer border-l-2 transition-colors ${
                        sessionId === s.id
                          ? 'border-blue-500 bg-gray-700/60 text-white'
                          : 'border-transparent hover:bg-gray-700/40 text-slate-300'
                      }`}
                    >
                      <span className="flex-1 min-w-0 truncate text-sm" title={s.title ?? undefined}>
                        {s.title || 'New chat'}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSession(s.id, e)}
                        className="shrink-0 w-6 h-6 flex items-center justify-center rounded text-slate-500 hover:text-red-400 hover:bg-gray-600/60 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete chat"
                        aria-label="Delete chat"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        )}

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
    </div>
  );
}

// Made with Bob