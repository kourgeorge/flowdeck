import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ChatView, { useChatState, type ChatMessageWithMeta, type UseChatStateReturn } from './ChatView';
import { useAuth } from '../contexts/AuthContext';
import { profileApi } from '../services/authApi';
import { chatApi, type ChatSessionListItem, type ChatMessageWithMetaApi } from '../services/api';
import { COPILOT_NAME } from '../config';

function apiMessageToChatMessageWithMeta(m: ChatMessageWithMetaApi): ChatMessageWithMeta {
  return {
    role: m.role as 'user' | 'assistant',
    content: m.content,
    tokens_used: m.tokens_used ?? undefined,
    platform_tokens_used: m.platform_tokens_used ?? undefined,
    cost_usd: m.cost_usd ?? undefined,
    tools_called: m.tools_called ?? undefined,
    tool_call_events: m.tool_call_events ?? undefined,
    skill_activation_events: m.skill_activation_events ?? undefined,
    charts: m.charts ?? undefined,
    follow_up_questions: m.follow_up_questions ?? undefined,
  };
}

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
  /** Display name shown in the panel header and collapsed strip. Defaults to COPILOT_NAME. */
  title?: string;
  /** Optional external chat state for persistence across component unmounts */
  chatState?: UseChatStateReturn;
  /** When using external chatState: current session id so continuing uses the same session */
  sessionId?: number | null;
  /** When using external chatState: called when user loads a session so parent can sync sessionId */
  onSessionIdChange?: (id: number | null) => void;
  /** When using external chatState: ref the parent can call to refresh the session list after stream done */
  externalRefreshSessionsRef?: React.MutableRefObject<(() => void) | null>;
}

export default function CopilotChatPanel({
  selectedTicker,
  tickers = [],
  collapsed = false,
  onToggleCollapse,
  title,
  chatState: externalChatState,
  sessionId: externalSessionId,
  onSessionIdChange,
  externalRefreshSessionsRef,
}: CopilotChatPanelProps) {
  const panelTitle = title ?? COPILOT_NAME;
  const { user } = useAuth();
  const useInternalSession = externalChatState == null;

  const [internalSessionId, setInternalSessionId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<ChatSessionListItem[]>([]);
  // When external chat state: parent owns sessionId; else we use internal state
  const sessionId = useInternalSession ? internalSessionId : (externalSessionId ?? null);
  const setSessionId = useInternalSession ? setInternalSessionId : (onSessionIdChange ?? (() => {}));
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyDropdownRef = useRef<HTMLDivElement>(null);

  const refreshSessions = useCallback(() => {
    if (!user) return;
    chatApi.getChatSessions().then(setSessions).catch(() => {});
  }, [user]);

  // Most recent first (recent at top)
  const sessionsByRecency = useMemo(
    () =>
      [...sessions].sort((a, b) => {
        const tA = (a.updated_at && new Date(a.updated_at).getTime()) || 0;
        const tB = (b.updated_at && new Date(b.updated_at).getTime()) || 0;
        return tB - tA;
      }),
    [sessions],
  );

  // Build context object with all tickers so the AI knows the full watchlist
  const context = useMemo(
    () => (tickers.length > 0 ? { tickers } : undefined),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tickers.join(',')],
  );
  const onStreamDone = useCallback(
    (newSessionId?: number) => {
      if (newSessionId != null) setSessionId(newSessionId);
      refreshSessions();
    },
    [setSessionId, refreshSessions],
  );

  const createSessionIfNeeded = useCallback(async () => {
    const { id } = await chatApi.createChatSession();
    setSessionId(id);
    refreshSessions();
    return id;
  }, [setSessionId, refreshSessions]);

  const internalChat = useChatState(
    undefined,
    context,
    useInternalSession ? sessionId : undefined,
    useInternalSession ? onStreamDone : undefined,
    useInternalSession ? createSessionIfNeeded : undefined,
  );
  const chat = externalChatState ?? internalChat;

  // Fetch token balance when user logs in
  useEffect(() => {
    if (!user) { chat.setTokenBalance(null); return; }
    profileApi.getMe().then((me) => {
      chat.setTokenBalance(me.token_balance);
    }).catch(() => {});
  }, [user, chat]);

  // Load session list when user is logged in (for history dropdown on both internal and external chat)
  useEffect(() => {
    if (!user) return;
    refreshSessions();
  }, [user, refreshSessions]);

  // When parent provides a ref, let it trigger session list refresh after stream done
  useEffect(() => {
    if (!externalRefreshSessionsRef) return;
    externalRefreshSessionsRef.current = refreshSessions;
    return () => { externalRefreshSessionsRef.current = null; };
  }, [externalRefreshSessionsRef, refreshSessions]);

  // Close history dropdown on click outside
  useEffect(() => {
    if (!historyOpen) return;
    const handle = (e: MouseEvent) => {
      if (historyDropdownRef.current && !historyDropdownRef.current.contains(e.target as Node)) {
        setHistoryOpen(false);
      }
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [historyOpen]);

  const handleNewChat = useCallback(() => {
    if (!user) return;
    setSessionId(null);
    chat.clearChat();
  }, [user, setSessionId, chat]);

  const handleLoadSession = useCallback((id: number) => {
    chat.clearLoadingState();
    chatApi.getChatSession(id).then((detail) => {
      setSessionId(detail.id);
      chat.setMessages(detail.messages.map(apiMessageToChatMessageWithMeta));
      setHistoryOpen(false);
    }).catch(() => {});
  }, [chat, setSessionId]);

  const handleDeleteSession = useCallback((id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    chatApi.deleteChatSession(id).then(() => {
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (sessionId === id) {
        setSessionId(null);
        chat.clearChat();
      }
    }).catch(() => {});
  }, [sessionId, chat]);

  // Focus input when panel expands
  useEffect(() => {
    if (!collapsed) {
      setTimeout(() => chat.inputRef.current?.focus(), 50);
    }
  }, [collapsed]);

  // ── Collapsed state: show a vertical strip with a toggle button ──
  if (collapsed) {
    return (
      <div className="flex flex-col items-center w-8 shrink-0 border-l border-gray-700 bg-gray-800/50 py-3 gap-2">
        <button
          type="button"
          onClick={onToggleCollapse}
          title={`Expand ${panelTitle}`}
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
            {panelTitle}
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
              <span className="text-sm font-semibold text-white leading-tight">{panelTitle}</span>
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
              onClick={useInternalSession ? handleNewChat : chat.clearChat}
              disabled={!useInternalSession && chat.messages.length === 0 && !chat.error}
              title="New chat"
              className="flex items-center justify-center w-7 h-7 text-slate-400 hover:text-slate-200 transition-colors rounded-lg hover:bg-gray-700 border border-gray-600 hover:border-gray-500 disabled:opacity-40 disabled:cursor-default"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          )}

          {/* Previous conversations (history) dropdown */}
          {user && (
            <div className="relative" ref={historyDropdownRef}>
              <button
                type="button"
                onClick={() => setHistoryOpen((v) => !v)}
                title="Previous conversations"
                className={`flex items-center justify-center w-7 h-7 rounded-lg border transition-colors ${
                  historyOpen
                    ? 'bg-gray-700 border-gray-500 text-white'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-gray-700 border-gray-600 hover:border-gray-500'
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
              {historyOpen && (
                <div className="absolute right-0 top-full mt-1 w-64 max-h-72 overflow-hidden rounded-lg border border-gray-600 bg-gray-800 shadow-xl z-50 flex flex-col">
                  <div className="px-2 py-2 border-b border-gray-700">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Previous conversations</p>
                  </div>
                  <ul className="overflow-y-auto py-1 flex-1 min-h-0">
                    {sessionsByRecency.length === 0 ? (
                      <li className="px-3 py-4 text-center text-xs text-slate-500">No conversations yet</li>
                    ) : (
                      sessionsByRecency.map((s) => (
                        <li key={s.id} className="flex items-center group">
                          <button
                            type="button"
                            onClick={() => handleLoadSession(s.id)}
                            className={`flex-1 min-w-0 text-left px-3 py-2 text-sm border-l-2 transition-colors ${
                              sessionId === s.id
                                ? 'border-blue-500 bg-gray-700/60 text-white'
                                : 'border-transparent hover:bg-gray-700/40 text-slate-300'
                            }`}
                          >
                            <span className="block truncate" title={s.title ?? undefined}>
                              {s.title || 'New chat'}
                            </span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteSession(s.id, e)}
                            title="Delete conversation"
                            className="shrink-0 p-1.5 mr-1 rounded text-slate-400 hover:text-red-400 hover:bg-gray-700/60 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Collapse toggle */}
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              title={`Collapse ${panelTitle}`}
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
        welcomeSubtext="I have access to live prices, AI reports, fundamentals, news, technicals, insider activity & your watchlist."
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