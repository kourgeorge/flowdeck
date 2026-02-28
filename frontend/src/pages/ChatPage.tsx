import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi, type ChatMessage } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { profileApi } from '../services/authApi';

const SUGGESTED_QUESTIONS = [
  "What's the current price and today's performance for AAPL?",
  'Compare MSFT and GOOGL fundamentals',
  'What are the key risks in the current market?',
  'Show me recent insider activity for NVDA',
  "What is FlowDeck's recommendation for TSLA?",
  'Summarize the latest news for AMZN',
];

function StreamingCursor() {
  return <span className="inline-block w-0.5 h-3.5 bg-blue-400 ml-0.5 align-middle animate-pulse" />;
}

function TypingIndicator({ status }: { status?: string | null }) {
  return (
    <div className="flex items-end gap-3 mb-4">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
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

function MessageBubble({
  message,
  isStreaming = false,
}: {
  message: ChatMessage & { tokens_used?: number; tools_called?: number };
  isStreaming?: boolean;
}) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
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
                {message.tools_called} tool{message.tools_called !== 1 ? 's' : ''} accessed
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

export default function ChatPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<(ChatMessage & { tokens_used?: number; tools_called?: number })[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tokenBalance, setTokenBalance] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch initial token balance when user is logged in
  useEffect(() => {
    if (!user) { setTokenBalance(null); return; }
    profileApi.getMe().then((me) => setTokenBalance(me.token_balance)).catch(() => {});
  }, [user]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isStreaming]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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
        // Always update balance from the server's authoritative post-deduction value
        if (balance >= 0) setTokenBalance(balance);
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
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
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

  const isEmpty = messages.length === 0;

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
            {tokenBalance !== null && (
              <div
                key={tokenBalance}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-700/60 border border-slate-600/60 transition-all duration-300"
                title="Remaining token balance"
              >
                <svg className="w-3.5 h-3.5 text-yellow-400 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z"/>
                </svg>
                <span className="text-xs font-medium text-yellow-300 tabular-nums">{tokenBalance.toLocaleString()}</span>
                <span className="text-xs text-slate-400">tokens</span>
              </div>
            )}
            <button
              type="button"
              onClick={clearChat}
              disabled={messages.length === 0 && !error}
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

      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6 sm:px-8">
        <div className="max-w-3xl mx-auto">
          {isEmpty && (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
              {!user ? (
                <div className="text-center max-w-sm">
                  <div className="w-16 h-16 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <h2 className="text-lg font-semibold text-white mb-2">Sign in to use AI Analyst Agent</h2>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Create a free account to chat with the AI Analyst Agent and get live market insights.
                  </p>
                </div>
              ) : (
                <>
                  <div className="text-center max-w-md">
                    <div className="w-16 h-16 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-4">
                      <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                      </svg>
                    </div>
                    <h2 className="text-lg font-semibold text-white mb-2">Ask me anything about stocks</h2>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      I have access to live prices, specialized AI reports & recommendations, fundamentals, news, technical indicators, insider activity, and your preferred tickers.
                    </p>
                  </div>
                  <div className="w-full max-w-xl space-y-2">
                    <p className="text-xs text-slate-500 text-center mb-2">Suggested questions</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {SUGGESTED_QUESTIONS.map((q) => (
                        <button
                          key={q}
                          type="button"
                          onClick={() => sendMessage(q)}
                          className="text-left text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 border border-slate-600/60 hover:border-slate-500 rounded-xl px-3.5 py-2.5 transition-all"
                        >
                          <span className="text-blue-400 mr-1.5">→</span>
                          {q}
                        </button>
                      ))}
                    </div>
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
      </div>

      {/* Input area */}
      <div className="shrink-0 px-4 pb-2 pt-3 bg-gray-800/80 border-t border-gray-700">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-2 bg-slate-700/80 rounded-xl border border-slate-600 focus-within:border-blue-500 transition-colors px-3 py-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={user ? 'Ask about any stock…' : 'Sign in to start chatting…'}
              rows={1}
              disabled={isLoading || isStreaming || !user}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-400 resize-none outline-none min-h-[24px] max-h-[120px] leading-6 disabled:opacity-50"
              style={{ overflowY: input.split('\n').length > 4 ? 'auto' : 'hidden' }}
            />
            <button
              type="button"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading || isStreaming || !user}
              className="shrink-0 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
              aria-label="Send message"
            >
              <svg className="w-4 h-4 text-white rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
          <p className="text-xs text-slate-500 text-center mt-2">
            AI can make mistakes — always verify important information · Not financial advice
          </p>
        </div>
      </div>
    </div>
  );
}

// Made with Bob