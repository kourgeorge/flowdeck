import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi, type ChatMessage } from '../services/api';

// Blinking cursor shown while streaming
function StreamingCursor() {
  return <span className="inline-block w-0.5 h-3.5 bg-blue-400 ml-0.5 align-middle animate-pulse" />;
}

interface StockAnalystChatProps {
  ticker: string;
  companyName?: string | null;
}

function getSuggestedQuestions(ticker: string, companyName?: string | null): string[] {
  const name = companyName || ticker;
  return [
    `What is FlowDeck's recommendation for ${ticker}?`,
    `Summarize the AI analysis reports for ${ticker}`,
    `What are the key risks and opportunities for ${name}?`,
    `What do the technical indicators say about ${ticker}?`,
    `Show me the latest news and insider activity for ${ticker}`,
  ];
}

function TypingIndicator({ status }: { status?: string | null }) {
  return (
    <div className="flex items-end gap-2 mb-4">
      <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
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
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2.5 mb-4">
      <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2z" />
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

export default function StockAnalystChat({ ticker, companyName }: StockAnalystChatProps) {
  const [messages, setMessages] = useState<(ChatMessage & { tokens_used?: number; tools_called?: number })[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const suggestedQuestions = getSuggestedQuestions(ticker, companyName);

  // Reset chat when ticker changes (and cancel any in-flight stream)
  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setInput('');
    setError(null);
    setIsLoading(false);
    setIsStreaming(false);
    setThinkingStatus(null);
  }, [ticker]);

  // Cancel stream on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

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

    // Placeholder assistant message that will be filled token-by-token
    const assistantIndex = newMessages.length; // index in the array we're about to set

    const apiMessages = newMessages.map((m) => ({ role: m.role, content: m.content }));

    abortRef.current = chatApi.streamMessage(
      apiMessages,
      // onToken — append chunk to the streaming assistant message
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
            // First token: insert the assistant message
            updated.splice(assistantIndex, 0, { role: 'assistant', content: chunk });
          }
          return updated;
        });
      },
      // onDone — tools_called comes authoritatively from the backend done event
      (tokensUsed, _balance, toolsCalled) => {
        setIsStreaming(false);
        setIsLoading(false);
        setThinkingStatus(null);
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
      // onError
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
      // onThinking — show tool progress status while tools are running
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

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col" style={{ height: '600px' }}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-900/60 border-b border-slate-700 shrink-0 rounded-t-lg">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">
              Stock Market Analyst
              <span className="ml-2 text-xs font-normal text-blue-400 bg-blue-500/10 border border-blue-500/30 rounded px-1.5 py-0.5">
                {ticker}
              </span>
            </div>
            <div className="text-xs text-slate-400">AI-powered · live data · full analysis access</div>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              abortRef.current?.abort();
              abortRef.current = null;
              setMessages([]);
              setError(null);
              setIsLoading(false);
              setIsStreaming(false);
              setThinkingStatus(null);
            }}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded hover:bg-slate-700"
          >
            Clear chat
          </button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 bg-slate-800/40">
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full gap-5 pb-4">
            {/* Welcome state */}
            <div className="text-center max-w-sm">
              <div className="w-14 h-14 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-3">
                <svg className="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
              </div>
              <p className="text-sm font-semibold text-white mb-1">
                Ask me anything about {companyName || ticker}
              </p>
              <p className="text-xs text-slate-400 leading-relaxed">
                I have access to FlowDeck's AI analysis reports, live prices, fundamentals, news, technical indicators, and insider activity for {ticker}.
              </p>
            </div>

            {/* Suggested questions */}
            <div className="w-full max-w-lg space-y-2">
              <p className="text-xs text-slate-500 text-center mb-1">Suggested questions</p>
              {suggestedQuestions.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => sendMessage(q)}
                  className="w-full text-left text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 border border-slate-600/60 hover:border-slate-500 rounded-xl px-3.5 py-2.5 transition-all"
                >
                  <span className="text-blue-400 mr-1.5">→</span>
                  {q}
                </button>
              ))}
            </div>
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

      {/* Token notice */}
      <div className="px-4 py-1.5 bg-slate-900/40 border-t border-slate-700/50 shrink-0">
        <p className="text-xs text-slate-500 text-center">
          Each message uses tokens based on data fetched · For informational purposes only
        </p>
      </div>

      {/* Input area */}
      <div className="px-3 pb-3 pt-2 bg-slate-900/60 border-t border-slate-700 shrink-0 rounded-b-lg">
        <div className="flex items-end gap-2 bg-slate-700/80 rounded-xl border border-slate-600 focus-within:border-blue-500 transition-colors px-3 py-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask about ${ticker}…`}
            rows={1}
            disabled={isLoading || isStreaming}
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-400 resize-none outline-none min-h-[24px] max-h-[120px] leading-6 disabled:opacity-50"
            style={{ overflowY: input.split('\n').length > 4 ? 'auto' : 'hidden' }}
          />
          <button
            type="button"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading || isStreaming}
            className="shrink-0 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
            aria-label="Send message"
          >
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-1.5 text-center">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}

// Made with Bob