import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ChatView, { useChatState, type ChatMessageWithMeta } from '../components/ChatView';
import PageHeader from '../components/PageHeader';
import TickerSearch from '../components/TickerSearch';
import { useAuth } from '../contexts/AuthContext';
import { profileApi } from '../services/authApi';
import { chatApi, type ChatMessageWithMetaApi, type ChatSessionListItem, type ChatTurnStatus } from '../services/api';

const SUGGESTED_QUESTIONS = [
  "What's the current price and today's performance for AAPL?",
  'Compare MSFT and GOOGL fundamentals',
  'What are the key risks in the current market?',
  'Show me recent insider activity for NVDA',
  "What is FlowDeck's recommendation for TSLA?",
  'Summarize the latest news for AMZN',
  'Calculate the Pearson correlation between META and IBM daily returns over the past year',
];

const ACTIVE_CHAT_SESSION_STORAGE_KEY = 'flowdeck.chat.activeSessionId';

function apiMessageToChatMessageWithMeta(m: ChatMessageWithMetaApi): ChatMessageWithMeta {
  return {
    role: m.role as 'user' | 'assistant',
    content: m.content,
    tokens_used: m.tokens_used ?? undefined,
    platform_tokens_used: m.platform_tokens_used ?? undefined,
    model_metadata: m.model_metadata ?? undefined,
    cost_usd: m.cost_usd ?? undefined,
    tools_called: m.tools_called ?? undefined,
    tool_call_events: m.tool_call_events ?? undefined,
    skill_activation_events: m.skill_activation_events ?? undefined,
    charts: m.charts ?? undefined,
    follow_up_questions: m.follow_up_questions ?? undefined,
  };
}

function formatSessionTimestamp(updatedAt?: string | null) {
  if (!updatedAt) return 'No activity yet';

  const date = new Date(updatedAt);
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday · ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  }

  if (sameDay) {
    return `Today · ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  }

  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function getInitialHistoryCollapsed() {
  if (typeof window === 'undefined') return false;
  return window.innerWidth < 1024;
}

function getStoredActiveSessionId(): number | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function HistoryList({
  sessions,
  activeSessionId,
  runningTurnsBySession,
  onOpenSession,
  onDeleteSession,
}: {
  sessions: ChatSessionListItem[];
  activeSessionId: number | null;
  runningTurnsBySession: Record<number, ChatTurnStatus>;
  onOpenSession: (id: number) => void;
  onDeleteSession: (id: number, e: React.MouseEvent<HTMLButtonElement>) => void;
}) {
  if (sessions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-700/80 bg-slate-900/40 px-4 py-5 text-sm text-slate-400">
        Your saved conversations will appear here once you start chatting.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {sessions.map((session) => {
        const isActive = activeSessionId === session.id;
        const runningTurn = runningTurnsBySession[session.id] ?? session.active_turn;
        const isRunning = runningTurn?.status === 'running';

        return (
          <li
            key={session.id}
            className={`group rounded-lg border transition-all ${
              isActive
                ? 'border-blue-500/60 bg-blue-500/12 shadow-[0_12px_30px_rgba(37,99,235,0.16)]'
                : 'border-slate-800/80 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-800/70'
            }`}
          >
            <div className="flex items-start gap-2 px-3 py-3">
              <button
                type="button"
                onClick={() => onOpenSession(session.id)}
                className="flex min-w-0 flex-1 items-start gap-3 text-left"
              >
                <div
                  className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                    isRunning
                      ? 'animate-pulse bg-emerald-400 shadow-[0_0_0_4px_rgba(74,222,128,0.12)]'
                      : isActive
                        ? 'bg-blue-400'
                        : 'bg-slate-600 group-hover:bg-slate-400'
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-slate-100" title={session.title ?? undefined}>
                    {session.title || 'New chat'}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {isRunning ? 'Working…' : formatSessionTimestamp(session.updated_at)}
                  </div>
                </div>
              </button>
              <div>
                <button
                  type="button"
                  onClick={(e) => onDeleteSession(session.id, e)}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-700/80 hover:text-rose-300"
                  title="Delete chat"
                  aria-label="Delete chat"
                >
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default function ChatPage() {
  const { user } = useAuth();
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<ChatSessionListItem[]>([]);
  const [historyCollapsed, setHistoryCollapsed] = useState(getInitialHistoryCollapsed);
  const [isMobileHistory, setIsMobileHistory] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < 1024;
  });
  const [runningTurnsBySession, setRunningTurnsBySession] = useState<Record<number, ChatTurnStatus>>({});
  const restoreAttemptedRef = useRef(false);
  const turnPollTimeoutRef = useRef<number | null>(null);

  const refreshSessions = useCallback(() => {
    if (!user) return;
    chatApi.getChatSessions().then(setSessions).catch(() => {});
  }, [user]);

  const onStreamStart = useCallback(
    (_runningSessionId: number) => {
      refreshSessions();
      if (typeof window === 'undefined') return;
      window.setTimeout(() => refreshSessions(), 400);
      window.setTimeout(() => refreshSessions(), 1800);
    },
    [refreshSessions],
  );

  const createSessionIfNeeded = useCallback(async () => {
    const { id } = await chatApi.createChatSession();
    setSessionId(id);
    refreshSessions();
    return id;
  }, [refreshSessions]);

  const upsertRunningTurn = useCallback((turn: ChatTurnStatus) => {
    setRunningTurnsBySession((prev) => {
      const current = prev[turn.session_id];
      if (
        current &&
        current.id === turn.id &&
        current.status === turn.status &&
        current.last_thinking_status === turn.last_thinking_status &&
        current.error_message === turn.error_message
      ) {
        return prev;
      }
      return { ...prev, [turn.session_id]: turn };
    });
  }, []);

  const removeRunningTurn = useCallback((targetSessionId: number) => {
    setRunningTurnsBySession((prev) => {
      if (!(targetSessionId in prev)) return prev;
      const next = { ...prev };
      delete next[targetSessionId];
      return next;
    });
  }, []);

  const onStreamDone = useCallback(
    (newSessionId?: number) => {
      if (newSessionId != null) {
        setSessionId(newSessionId);
        removeRunningTurn(newSessionId);
      }
      refreshSessions();
    },
    [refreshSessions, removeRunningTurn],
  );

  const chat = useChatState(
    undefined,
    undefined,
    sessionId,
    onStreamDone,
    onStreamStart,
    upsertRunningTurn,
    createSessionIfNeeded,
  );
  const {
    inputRef,
    setTokenBalance,
    clearLoadingState,
    restorePendingTurn,
    setMessages,
    clearChat,
    messages,
    setError,
    isLoading,
    isStreaming,
    lastCompletedTurn,
  } = chat;

  const shouldRestorePendingTurn = useCallback(
    (turn?: ChatTurnStatus | null) => {
      if (!turn || turn.status !== 'running') return false;
      return !(lastCompletedTurn && turn.session_id === lastCompletedTurn.session_id && turn.id === lastCompletedTurn.id);
    },
    [lastCompletedTurn],
  );

  const clearTurnPoll = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (turnPollTimeoutRef.current != null) {
      window.clearTimeout(turnPollTimeoutRef.current);
      turnPollTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const syncViewport = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobileHistory(mobile);
      if (!mobile) return;
      setHistoryCollapsed(true);
    };

    syncViewport();
    window.addEventListener('resize', syncViewport);
    return () => window.removeEventListener('resize', syncViewport);
  }, []);

  useEffect(() => {
    if (!user) {
      setTokenBalance(null);
      setDisplayName(null);
      setSessions([]);
      setSessionId(null);
      setRunningTurnsBySession({});
      setHistoryCollapsed(true);
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
      }
      return;
    }

    profileApi.getMe().then((me) => {
      setTokenBalance(me.token_balance);
      setDisplayName(me.name && me.name.trim() ? me.name.trim() : null);
    }).catch(() => {});
  }, [setTokenBalance, user]);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    setRunningTurnsBySession((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const session of sessions) {
        const turn = session.active_turn?.status === 'running' ? session.active_turn : null;
        const current = next[session.id];

        if (!turn) {
          if (current) {
            delete next[session.id];
            changed = true;
          }
          continue;
        }

        if (
          !current ||
          current.id !== turn.id ||
          current.status !== turn.status ||
          current.last_thinking_status !== turn.last_thinking_status ||
          current.error_message !== turn.error_message
        ) {
          next[turn.session_id] = turn;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [sessions]);

  useEffect(() => {
    if (!user || typeof window === 'undefined') return undefined;
    if (Object.keys(runningTurnsBySession).length === 0 && !sessions.some((session) => session.active_turn?.status === 'running')) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      refreshSessions();
    }, 2000);

    return () => window.clearTimeout(timeoutId);
  }, [refreshSessions, runningTurnsBySession, sessions, user]);

  useEffect(() => {
    restoreAttemptedRef.current = false;
    clearTurnPoll();
  }, [clearTurnPoll, user]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!user) {
      window.localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
      return;
    }
    if (sessionId == null) return;
    window.localStorage.setItem(ACTIVE_CHAT_SESSION_STORAGE_KEY, String(sessionId));
  }, [sessionId, user]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [inputRef]);

  const openSessionById = useCallback(
    async (
      id: number,
      options?: { collapseHistory?: boolean },
    ) => {
      setSessionId(id);
      clearLoadingState();
      const detail = await chatApi.getChatSession(id);
      setSessionId(detail.id);
      setMessages(detail.messages.map(apiMessageToChatMessageWithMeta));
      if (detail.active_turn?.status === 'running') {
        upsertRunningTurn(detail.active_turn);
        if (shouldRestorePendingTurn(detail.active_turn)) {
          restorePendingTurn(detail.active_turn.last_thinking_status ?? 'Working…');
        } else {
          clearLoadingState();
        }
      } else {
        removeRunningTurn(detail.id);
        clearLoadingState();
      }
      if ((options?.collapseHistory ?? true) && isMobileHistory) setHistoryCollapsed(true);
      return detail;
    },
    [clearLoadingState, isMobileHistory, removeRunningTurn, restorePendingTurn, setMessages, shouldRestorePendingTurn, upsertRunningTurn],
  );

  useEffect(() => {
    if (!user || restoreAttemptedRef.current) return;
    if (sessionId != null || messages.length > 0) {
      restoreAttemptedRef.current = true;
      return;
    }

    const storedSessionId = getStoredActiveSessionId();
    restoreAttemptedRef.current = true;
    if (storedSessionId == null) return;

    openSessionById(storedSessionId, { collapseHistory: false }).catch(() => {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
      }
      removeRunningTurn(storedSessionId);
    });
  }, [messages.length, openSessionById, removeRunningTurn, sessionId, user]);

  useEffect(() => {
    if (!user || typeof window === 'undefined') return undefined;
    const runningTurns = Object.values(runningTurnsBySession).filter(
      (turn) => turn.status === 'running' && turn.id > 0,
    );
    if (runningTurns.length === 0) return undefined;

    let cancelled = false;

    const poll = async () => {
      try {
        const results = await Promise.all(runningTurns.map((turn) => chatApi.getChatTurn(turn.id)));
        if (cancelled) return;

        const completedTurns: ChatTurnStatus[] = [];
        for (const turn of results) {
          if (turn.status === 'running') {
            upsertRunningTurn(turn);
            continue;
          }
          completedTurns.push(turn);
          removeRunningTurn(turn.session_id);
        }

        for (const turn of completedTurns) {
          if (turn.session_id !== sessionId) continue;
          const detail = await chatApi.getChatSession(turn.session_id);
          if (cancelled) return;
          setMessages(detail.messages.map(apiMessageToChatMessageWithMeta));
          clearLoadingState();
          if (turn.status === 'failed') {
            setError(turn.error_message ?? 'The agent failed to complete this reply.');
          }
        }

        if (completedTurns.length > 0) {
          refreshSessions();
        }
        turnPollTimeoutRef.current = window.setTimeout(poll, 2000);
      } catch {
        if (!cancelled) {
          turnPollTimeoutRef.current = window.setTimeout(poll, 2000);
        }
      }
    };

    turnPollTimeoutRef.current = window.setTimeout(poll, 2000);

    return () => {
      cancelled = true;
      clearTurnPoll();
    };
  }, [clearLoadingState, clearTurnPoll, refreshSessions, removeRunningTurn, runningTurnsBySession, sessionId, setError, setMessages, upsertRunningTurn, user]);

  useEffect(() => {
    if (!user || sessionId == null) return;
    const runningTurn = runningTurnsBySession[sessionId] ?? sessions.find((session) => session.id === sessionId)?.active_turn;
    if (!shouldRestorePendingTurn(runningTurn)) return;
    if (!runningTurn) return;
    if (!isLoading && !isStreaming) {
      restorePendingTurn(runningTurn.last_thinking_status ?? 'Working…');
    }
  }, [isLoading, isStreaming, restorePendingTurn, runningTurnsBySession, sessionId, sessions, shouldRestorePendingTurn, user]);

  useEffect(() => () => clearTurnPoll(), [clearTurnPoll]);

  const handleOpenSession = (id: number) => {
    openSessionById(id).catch(() => {});
  };

  const handleDeleteSession = (id: number, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (!user) return;

    chatApi.deleteChatSession(id).then(() => {
      setSessions((prev) => prev.filter((session) => session.id !== id));
      removeRunningTurn(id);
      if (sessionId === id) {
        setSessionId(null);
        clearChat();
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
        }
      }
    }).catch(() => {});
  };

  const greeting = user
    ? displayName ?? (user.email.split('@')[0].charAt(0).toUpperCase() + user.email.split('@')[0].slice(1))
    : null;

  const sessionsByRecency = useMemo(
    () =>
      [...sessions].sort((a, b) => {
        const tA = (a.updated_at && new Date(a.updated_at).getTime()) || 0;
        const tB = (b.updated_at && new Date(b.updated_at).getTime()) || 0;
        return tB - tA;
      }),
    [sessions],
  );

  const currentSession = sessions.find((session) => session.id === sessionId) ?? null;
  const startNewChat = () => {
    setSessionId(null);
    clearChat();
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(ACTIVE_CHAT_SESSION_STORAGE_KEY);
    }
    inputRef.current?.focus();
    if (isMobileHistory) setHistoryCollapsed(true);
  };

  return (
    <div className="relative flex h-full min-h-0 flex-col overflow-hidden bg-slate-950 text-white">
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
            <button
              type="button"
              onClick={() => setHistoryCollapsed((prev) => !prev)}
              className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-700/80 bg-slate-800/70 text-slate-300 transition-colors hover:border-slate-600 hover:bg-slate-700/80 hover:text-white"
              title={historyCollapsed ? 'Show conversation history' : 'Hide conversation history'}
              aria-label={historyCollapsed ? 'Show conversation history' : 'Hide conversation history'}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <rect x="3" y="4" width="18" height="16" rx="2" strokeWidth="2" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 4v16M13 8h4M13 12h4M13 16h3" />
              </svg>
            </button>
            {chat.tokenBalance !== null && (
              <div
                key={chat.tokenBalance}
                className="flex items-center gap-2 rounded-md border border-amber-400/20 bg-amber-500/8 px-3 py-1.5 transition-all duration-300"
                title="Remaining token balance"
              >
                <svg className="h-3.5 w-3.5 shrink-0 text-amber-300" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z" />
                </svg>
                <span className="text-xs font-semibold text-amber-100 tabular-nums">{chat.tokenBalance.toLocaleString()}</span>
                <span className="text-xs text-amber-200/70">tokens</span>
              </div>
            )}
            <button
              type="button"
              onClick={startNewChat}
              className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-700/80 bg-slate-800/70 text-xs font-medium text-slate-200 transition-colors hover:border-slate-600 hover:bg-slate-700/80 hover:text-white sm:h-auto sm:w-auto sm:gap-1.5 sm:px-3 sm:py-1.5"
              title="Start a new chat"
              aria-label="Start a new chat"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span className="hidden sm:inline">New chat</span>
            </button>
          </>
        )}
      </PageHeader>

      <div className="px-4 pt-2 border-b border-gray-700 bg-gray-900 shrink-0">
        <div className="pb-2">
          <TickerSearch compact />
        </div>
      </div>

      {user && isMobileHistory && !historyCollapsed && (
        <>
          <button
            type="button"
            onClick={() => setHistoryCollapsed(true)}
            aria-label="Close conversation history"
            className="absolute inset-0 z-20 bg-slate-950/60 backdrop-blur-sm lg:hidden"
          />
          <aside className="absolute inset-y-0 left-0 z-30 flex w-[23rem] max-w-[calc(100%-1rem)] flex-col border-r border-slate-800 bg-slate-950/96 px-3 pb-4 pt-3 shadow-2xl shadow-black/40 lg:hidden">
            <div className="mb-4 flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/80 px-4 py-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">History</div>
                <div className="mt-1 text-sm text-slate-200">Saved conversations</div>
              </div>
              <button
                type="button"
                onClick={() => setHistoryCollapsed(true)}
                className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-700 bg-slate-800 text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                aria-label="Close conversation history"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="mb-4 rounded-lg border border-slate-800 bg-slate-900/70 p-4">
              <p className="text-sm font-medium text-white">Open a saved thread or start a new one.</p>
              <button
                type="button"
                onClick={startNewChat}
                className="mt-4 inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Start new chat
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              <HistoryList
                sessions={sessionsByRecency}
                activeSessionId={sessionId}
                runningTurnsBySession={runningTurnsBySession}
                onOpenSession={handleOpenSession}
                onDeleteSession={handleDeleteSession}
              />
            </div>
          </aside>
        </>
      )}

      <div className="relative z-10 flex-1 min-h-0 px-3 pb-3 pt-3 md:px-4 md:pb-4">
        <div className="mx-auto flex h-full min-h-0 w-full max-w-[1280px] gap-3 lg:gap-4">
          {user && !isMobileHistory && (
            <aside
              className={`hidden min-h-0 shrink-0 flex-col overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/75 shadow-[0_20px_80px_rgba(2,6,23,0.45)] backdrop-blur lg:flex ${
                historyCollapsed ? 'w-[88px]' : 'w-[320px]'
              }`}
            >
              <div className="border-b border-slate-800/80 p-3">
                {historyCollapsed ? (
                  <div className="flex flex-col items-center gap-3 py-2">
                    <button
                      type="button"
                      onClick={() => setHistoryCollapsed(false)}
                      className="flex h-11 w-11 items-center justify-center rounded-md border border-slate-700/80 bg-slate-800/80 text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                      title="Expand conversation history"
                    >
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      onClick={startNewChat}
                      className="flex h-11 w-11 items-center justify-center rounded-md bg-blue-600 text-white transition-colors hover:bg-blue-500"
                      title="Start a new chat"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  </div>
                ) : (
                  <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">History</h2>
                      </div>
                      <button
                        type="button"
                        onClick={() => setHistoryCollapsed(true)}
                        className="flex h-10 w-10 items-center justify-center rounded-md border border-slate-700/80 bg-slate-800/80 text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                        aria-label="Collapse conversation history"
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={startNewChat}
                      className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-500"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Start new chat
                    </button>
                  </div>
                )}
              </div>

              {!historyCollapsed && (
                <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3 pt-1">
                  <HistoryList
                    sessions={sessionsByRecency}
                    activeSessionId={sessionId}
                    runningTurnsBySession={runningTurnsBySession}
                    onOpenSession={handleOpenSession}
                    onDeleteSession={handleDeleteSession}
                  />
                </div>
              )}
            </aside>
          )}

          <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/75 shadow-[0_20px_80px_rgba(2,6,23,0.5)] backdrop-blur">
            <div className="border-b border-slate-800/80 bg-slate-950/55 px-3 py-2 md:px-5 md:py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 flex items-center gap-2 text-sm font-medium text-slate-100">
                  <span className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Thread</span>
                  <span className="truncate align-middle">
                    {currentSession?.title || (greeting ? `${greeting}'s new market thread` : 'New market thread')}
                  </span>
                </div>
                <div className="shrink-0">
                  <span className="rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-[11px] leading-none text-slate-400">
                    {sessions.length} chats
                  </span>
                </div>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col px-2 pb-2 pt-2 md:px-3 md:pb-3">
              <ChatView
                chat={chat}
                isAuthenticated={!!user}
                showAdminUsageDetails={!!user?.is_admin}
                suggestedQuestions={SUGGESTED_QUESTIONS}
                welcomeHeading={
                  greeting
                    ? `Hi ${greeting}. What are you researching?`
                    : undefined
                }
                welcomeSubtext="Build a thesis, stress-test an idea, or pull together price action, fundamentals, and news in one thread."
                inputPlaceholder={user ? 'Ask about any stock, theme, or portfolio question…' : 'Sign in to start chatting…'}
                inputFooter={
                  <p className="px-2 pb-0 pt-0.5 text-center text-[11px] leading-4 text-slate-500">
                    AI can make mistakes. Verify important details before acting. Not financial advice.
                  </p>
                }
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
