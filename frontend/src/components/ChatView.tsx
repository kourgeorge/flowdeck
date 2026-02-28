import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi, type ChatMessage, type ToolCallEvent } from '../services/api';

// ── Friendly display names for tool names ──────────────────────────────────
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  get_stock_quote: 'Stock Quote',
  get_platform_reports: 'AI Reports',
  get_news: 'Company News',
  get_fundamentals: 'Fundamentals',
  get_balance_sheet: 'Balance Sheet',
  get_cashflow: 'Cash Flow',
  get_income_statement: 'Income Statement',
  get_stock_data: 'Historical Data',
  get_indicators: 'Technical Indicators',
  get_insider_transactions: 'Insider Transactions',
  get_insider_sentiment: 'Insider Sentiment',
  get_global_news: 'Global News',
  web_search: 'Web Search',
  get_user_context: 'User Profile',
  get_user_subscriptions: 'Watchlist',
  get_portfolio_overview: 'Portfolio Overview',
};

// ── Sub-components ─────────────────────────────────────────────────────────

export function StreamingCursor() {
  return <span className="inline-block w-0.5 h-3.5 bg-blue-400 ml-0.5 align-middle animate-pulse" />;
}

export function TypingIndicator({ status }: { status?: string | null }) {
  return (
    <div className="flex items-end gap-2 mb-4">
      <div className="bg-slate-700 rounded-2xl rounded-bl-sm px-4 py-3">
        {status ? (
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span className="text-xs text-slate-300">{status}…</span>
          </div>
        ) : (
          <div className="flex gap-1 items-center h-4">
            <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        )}
      </div>
    </div>
  );
}

export function ToolCallBlock({ toolCall }: { toolCall: ToolCallEvent }) {
  const [expanded, setExpanded] = useState(false);
  const displayName =
    TOOL_DISPLAY_NAMES[toolCall.name] ??
    toolCall.name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  let inputDisplay = toolCall.input;
  try {
    const parsed = JSON.parse(toolCall.input);
    const vals = Object.values(parsed);
    if (vals.length === 1) inputDisplay = String(vals[0]);
    else if (vals.length > 1)
      inputDisplay = Object.entries(parsed)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ');
  } catch { /* use raw */ }

  return (
    <div className="mb-1.5 rounded-lg border border-slate-600/60 bg-slate-800/60 overflow-hidden text-xs">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-slate-700/50 transition-colors text-left"
      >
        <svg className="w-3.5 h-3.5 text-violet-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span className="font-medium text-violet-300">{displayName}</span>
        {inputDisplay && (
          <span className="text-slate-400 truncate flex-1">
            <span className="text-slate-500 mr-1">·</span>{inputDisplay}
          </span>
        )}
        <svg
          className={`w-3.5 h-3.5 text-slate-500 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="border-t border-slate-600/60 divide-y divide-slate-700/60">
          {toolCall.input && (
            <div className="px-3 py-2">
              <div className="text-slate-500 uppercase tracking-wide text-[10px] font-semibold mb-1">Input</div>
              <pre className="text-slate-300 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed max-h-24 overflow-y-auto">
                {toolCall.input}
              </pre>
            </div>
          )}
          <div className="px-3 py-2">
            <div className="text-slate-500 uppercase tracking-wide text-[10px] font-semibold mb-1">Output</div>
            <pre className="text-slate-300 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed max-h-40 overflow-y-auto">
              {toolCall.output || '(empty)'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export type ChatMessageWithMeta = ChatMessage & {
  tokens_used?: number;
  tools_called?: number;
  tool_call_events?: ToolCallEvent[];
};

export function MessageBubble({
  message,
  isStreaming = false,
}: {
  message: ChatMessageWithMeta;
  isStreaming?: boolean;
}) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[85%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5 mb-4">
      <div className="flex-1 min-w-0">
        {message.tool_call_events && message.tool_call_events.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.tool_call_events.map((tc, i) => (
              <ToolCallBlock key={i} toolCall={tc} />
            ))}
          </div>
        )}
        <div className="bg-slate-700/80 text-slate-100 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed">
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ node, ...props }) => <p className="mb-2 last:mb-0 text-slate-100 text-sm leading-relaxed" {...props} />,
                ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-0.5 text-slate-100" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal list-outside pl-4 mb-2 space-y-0.5 text-slate-100" {...props} />,
                li: ({ node, ...props }) => <li className="text-slate-100 text-sm" {...props} />,
                strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
                em: ({ node, ...props }) => <em className="italic text-slate-200" {...props} />,
                code: ({ node, ...props }) => <code className="bg-slate-800 px-1 py-0.5 rounded text-xs text-green-400 font-mono" {...props} />,
                h1: ({ node, ...props }) => <h1 className="text-base font-bold text-white mb-2 mt-3 first:mt-0" {...props} />,
                h2: ({ node, ...props }) => <h2 className="text-sm font-bold text-white mb-1.5 mt-3 first:mt-0" {...props} />,
                h3: ({ node, ...props }) => <h3 className="text-sm font-semibold text-slate-200 mb-1 mt-2 first:mt-0" {...props} />,
                blockquote: ({ node, ...props }) => <blockquote className="border-l-2 border-blue-500 pl-3 text-slate-300 italic my-2" {...props} />,
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-2 rounded border border-slate-600">
                    <table className="min-w-full text-xs border-collapse" {...props} />
                  </div>
                ),
                thead: ({ node, ...props }) => <thead className="bg-slate-800 text-slate-200" {...props} />,
                tbody: ({ node, ...props }) => <tbody className="divide-y divide-slate-600" {...props} />,
                tr: ({ node, ...props }) => <tr className="hover:bg-slate-600/40" {...props} />,
                th: ({ node, ...props }) => <th className="px-2 py-1.5 text-left font-semibold text-white" {...props} />,
                td: ({ node, ...props }) => <td className="px-2 py-1.5 text-slate-300" {...props} />,
              }}
            >
              {message.content}
            </ReactMarkdown>
            {isStreaming && <StreamingCursor />}
          </div>
        </div>
        {(message.tokens_used != null || (message.tools_called != null && message.tools_called > 0)) && (
          <div className="flex items-center gap-2.5 text-xs text-slate-500 mt-1 ml-1">
            {message.tools_called != null && message.tools_called > 0 && (
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {message.tools_called} tool{message.tools_called !== 1 ? 's' : ''} used
              </span>
            )}
            {message.tokens_used != null && (
              <span>{message.tokens_used} token{message.tokens_used !== 1 ? 's' : ''} used</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── useChatState hook — all chat state and streaming logic ─────────────────

export interface UseChatStateReturn {
  messages: ChatMessageWithMeta[];
  input: string;
  setInput: (v: string) => void;
  isLoading: boolean;
  isStreaming: boolean;
  thinkingStatus: string | null;
  error: string | null;
  setError: (v: string | null) => void;
  tokenBalance: number | null;
  setTokenBalance: (v: number | null) => void;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  sendMessage: (text: string) => void;
  clearChat: () => void;
}

export function useChatState(onBalanceUpdate?: (balance: number) => void, context?: Record<string, unknown>): UseChatStateReturn {
  const [messages, setMessages] = useState<ChatMessageWithMeta[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tokenBalance, setTokenBalance] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Cancel stream on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isStreaming]);

  const sendMessage = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || isStreaming) return;

    const userMessage: ChatMessage = { role: 'user', content: trimmed };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setThinkingStatus(null);
    setError(null);

    const assistantIndex = newMessages.length;
    const apiMessages = newMessages.map((m) => ({ role: m.role, content: m.content }));

    abortRef.current = chatApi.streamMessage(
      apiMessages,
      (chunk) => {
        setIsLoading(false);
        setIsStreaming(true);
        setThinkingStatus(null);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              content: updated[assistantIndex].content + chunk,
            };
          } else {
            updated.splice(assistantIndex, 0, { role: 'assistant', content: chunk });
          }
          return updated;
        });
      },
      (tokensUsed, balance, toolsCalled) => {
        setIsStreaming(false);
        setIsLoading(false);
        setThinkingStatus(null);
        if (balance >= 0) {
          setTokenBalance(balance);
          onBalanceUpdate?.(balance);
        }
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              tokens_used: tokensUsed,
              tools_called: toolsCalled,
            };
          }
          return updated;
        });
      },
      (message) => {
        setIsStreaming(false);
        setIsLoading(false);
        setThinkingStatus(null);
        if (message.includes('402') || message.toLowerCase().includes('insufficient')) {
          setError('Insufficient token balance. Please purchase more tokens to continue chatting.');
        } else if (message.includes('401') || message.toLowerCase().includes('sign')) {
          setError('You must be signed in to use the AI chat.');
        } else {
          setError(message || 'Failed to get a response. Please try again.');
        }
      },
      (status) => {
        setThinkingStatus(status);
      },
      (toolCall) => {
        // Tool completed — clear the thinking status so the UI doesn't keep
        // showing the stale tool name while the LLM reasons over the results
        setThinkingStatus(null);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[assistantIndex]?.role === 'assistant') {
            const existing = updated[assistantIndex].tool_call_events ?? [];
            updated[assistantIndex] = {
              ...updated[assistantIndex],
              tool_call_events: [...existing, toolCall],
            };
          } else {
            updated.splice(assistantIndex, 0, {
              role: 'assistant',
              content: '',
              tool_call_events: [toolCall],
            });
          }
          return updated;
        });
      },
      context,
    );
  };

  const clearChat = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setError(null);
    setIsLoading(false);
    setIsStreaming(false);
    setThinkingStatus(null);
  };

  return {
    messages,
    input,
    setInput,
    isLoading,
    isStreaming,
    thinkingStatus,
    error,
    setError,
    tokenBalance,
    setTokenBalance,
    messagesEndRef,
    inputRef,
    sendMessage,
    clearChat,
  };
}

// ── ChatView — the full chat UI, layout-agnostic ───────────────────────────

export interface ChatViewProps {
  /** All chat state from useChatState() */
  chat: UseChatStateReturn;
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
  /** Suggested questions shown on the empty state */
  suggestedQuestions: string[];
  /** Optional welcome heading */
  welcomeHeading?: string;
  /** Optional welcome subtext */
  welcomeSubtext?: string;
  /** Placeholder text for the input */
  inputPlaceholder?: string;
  /** Extra content rendered above the input (e.g. disclaimer) */
  inputFooter?: React.ReactNode;
}

export default function ChatView({
  chat,
  isAuthenticated,
  suggestedQuestions,
  welcomeHeading,
  welcomeSubtext,
  inputPlaceholder,
  inputFooter,
}: ChatViewProps) {
  const {
    messages,
    input,
    setInput,
    isLoading,
    isStreaming,
    thinkingStatus,
    error,
    setError,
    messagesEndRef,
    inputRef,
    sendMessage,
  } = chat;

  const isEmpty = messages.length === 0;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <>
      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-4">
        {isEmpty && (
          <div className="flex flex-col items-center justify-center min-h-[60%] gap-4 pb-4">
            {!isAuthenticated ? (
              <div className="text-center max-w-xs px-2">
                <div className="w-12 h-12 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-white mb-1">Sign in to use AI Analyst</p>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Create a free account to chat with the AI Analyst and get live market insights.
                </p>
              </div>
            ) : (
              <>
                <div className="text-center max-w-xs px-2">
                  <div className="w-12 h-12 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                    </svg>
                  </div>
                  {welcomeHeading && (
                    <p className="text-sm font-semibold text-white mb-1">{welcomeHeading}</p>
                  )}
                  {welcomeSubtext && (
                    <p className="text-sm text-slate-400 leading-relaxed">{welcomeSubtext}</p>
                  )}
                </div>
                <div className="w-full space-y-1.5">
                  <p className="text-xs text-slate-500 text-center mb-1">Suggested questions</p>
                  {suggestedQuestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => sendMessage(q)}
                      className="w-full text-left text-[13px] text-slate-300 bg-slate-700/50 hover:bg-slate-700 border border-slate-600/60 hover:border-slate-500 rounded-xl px-3 py-2 transition-all"
                    >
                      <span className="text-blue-400 mr-1.5">→</span>
                      {q}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
          />
        ))}

        {isLoading && <TypingIndicator status={thinkingStatus} />}

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-red-800 bg-red-950/50 px-3 py-2.5 text-xs text-red-200 mb-4">
            <svg className="h-4 w-4 shrink-0 text-red-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="ml-auto text-red-400 hover:text-red-200"
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 px-3 pt-2">
        <div className="flex items-end gap-2 bg-slate-700/80 rounded-lg border border-slate-600 focus-within:border-blue-500 transition-colors px-3 py-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={inputPlaceholder ?? (isAuthenticated ? 'Ask about any stock…' : 'Sign in to start chatting…')}
            rows={4}
            disabled={isLoading || isStreaming || !isAuthenticated}
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-400 resize-none outline-none min-h-[80px] max-h-[200px] leading-6 disabled:opacity-50"
            style={{ overflowY: input.split('\n').length > 8 ? 'auto' : 'hidden' }}
          />
          <button
            type="button"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading || isStreaming || !isAuthenticated}
            className="shrink-0 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
            aria-label="Send message"
          >
            <svg className="w-4 h-4 text-white rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>

      {/* Optional footer below input */}
      {inputFooter}
    </>
  );
}

// Made with Bob