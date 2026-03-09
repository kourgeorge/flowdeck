import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatApi, type ChatMessage } from '../services/api';
import { convertAsciiTableToMarkdown } from '../utils/chatMarkdown';

// ── RTL Detection Utility ──────────────────────────────────────────────────
/**
 * Detects if text contains RTL (Right-to-Left) characters.
 * Checks for Hebrew, Arabic, and other RTL scripts.
 */
function detectRTL(text: string): boolean {
  const rtlRegex = /[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F\u0750-\u077F\u0780-\u07BF\u07C0-\u07FF\u08A0-\u08FF]/;
  return rtlRegex.test(text);
}

/** Remove the FOLLOW_UP_JSON:... line so it is not shown in the bubble (options appear below). */
function stripFollowUpJsonLine(content: string): string {
  if (!content) return content;
  return content
    .split('\n')
    .filter((line) => !/^\s*FOLLOW_UP_JSON:/.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

interface TickerChatPanelProps {
  onClose: () => void;
  initialBalance?: number;
}

const SUGGESTED_QUESTIONS = [
  "What's the current price and today's performance for AAPL?",
  'Compare MSFT and GOOGL fundamentals',
  'What are the key risks in the current market?',
  'Show me recent insider activity for NVDA',
];

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 mb-3">
      <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      <div className="bg-slate-700 rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          <span className="text-xs text-slate-300">Thinking…</span>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage & { tokens_used?: number } }) {
  const isUser = message.role === 'user';
  
  // Detect if message contains RTL text
  const isRTL = detectRTL(message.content);
  const direction = isRTL ? 'rtl' : 'ltr';

  if (isUser) {
    return (
      <div className="flex justify-end mb-3">
        <div
          className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed chat-message-content"
          dir={direction}
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-end gap-2 mb-3">
      <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mb-0.5">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      <div className="max-w-[85%]">
        <div
          className="bg-slate-700 text-slate-100 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm leading-relaxed"
          dir={direction}
        >
          <div className="prose prose-invert prose-sm max-w-none chat-message-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ node, ...props }) => <p className="mb-2 last:mb-0 text-slate-100 text-sm leading-relaxed" {...props} />,
                ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-0.5 text-slate-100" {...props} />,
                ol: ({ node, ...props }) => <ol className="list-decimal list-outside pl-4 mb-2 space-y-0.5 text-slate-100" {...props} />,
                li: ({ node, ...props }) => <li className="text-slate-100 text-sm" {...props} />,
                strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
                code: ({ node, ...props }) => <code className="bg-slate-800 px-1 py-0.5 rounded text-xs text-green-400" {...props} />,
                h1: ({ node, ...props }) => <h1 className="text-base font-bold text-white mb-1 mt-2" {...props} />,
                h2: ({ node, ...props }) => <h2 className="text-sm font-bold text-white mb-1 mt-2" {...props} />,
                h3: ({ node, ...props }) => <h3 className="text-sm font-semibold text-white mb-1 mt-1" {...props} />,
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
              {convertAsciiTableToMarkdown(stripFollowUpJsonLine(message.content))}
            </ReactMarkdown>
          </div>
        </div>
        {message.tokens_used != null && (
          <div className="text-xs text-slate-500 mt-0.5 ml-1">{message.tokens_used} token{message.tokens_used !== 1 ? 's' : ''} used</div>
        )}
      </div>
    </div>
  );
}

export default function TickerChatPanel({ onClose, initialBalance }: TickerChatPanelProps) {
  const [messages, setMessages] = useState<(ChatMessage & { tokens_used?: number })[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | undefined>(initialBalance);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', content: trimmed };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const result = await chatApi.sendMessage(newMessages.map(m => ({ role: m.role, content: m.content })));
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: result.reply, tokens_used: result.tokens_used },
      ]);
      setBalance(result.balance);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 402) {
        setError('Insufficient token balance. Please purchase more tokens to continue chatting.');
      } else if (status === 401) {
        setError('You must be signed in to use the chat.');
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to get a response. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-end pointer-events-none">
      {/* Panel */}
      <div
        className="pointer-events-auto flex flex-col bg-slate-800 border border-slate-600 rounded-2xl shadow-2xl overflow-hidden"
        style={{ width: 420, height: 580, margin: '0 24px 24px 0' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-700 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold text-white">Market Analyst</div>
              <div className="text-xs text-slate-400">AI-powered · uses live data</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {balance != null && (
              <div className="flex items-center gap-1 text-xs text-slate-400">
                <svg className="w-3.5 h-3.5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12zm.75-9.25a.75.75 0 00-1.5 0v3.5l-1.72 1.72a.75.75 0 001.06 1.06l2-2A.75.75 0 0010.75 10V6.75z" />
                </svg>
                <span className="text-amber-400 font-medium">{balance}</span>
                <span>tokens</span>
              </div>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
              aria-label="Close chat"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
          {isEmpty && (
            <div className="flex flex-col items-center justify-center h-full gap-4 pb-4">
              <div className="text-center">
                <div className="w-12 h-12 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-white mb-1">Ask me anything about the market</p>
                <p className="text-xs text-slate-400">I have access to live prices, fundamentals, news, and more</p>
              </div>
              <div className="w-full space-y-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => sendMessage(q)}
                    className="w-full text-left text-xs text-slate-300 bg-slate-700/60 hover:bg-slate-700 border border-slate-600 rounded-xl px-3 py-2.5 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}

          {isLoading && <TypingIndicator />}

          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-red-800 bg-red-950/50 px-3 py-2.5 text-xs text-red-200 mb-3">
              <svg className="h-4 w-4 shrink-0 text-red-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Token notice */}
        <div className="px-4 py-1.5 bg-slate-900/50 border-t border-slate-700/50 shrink-0">
          <p className="text-xs text-slate-500 text-center">Each message costs tokens based on data fetched</p>
        </div>

        {/* Input */}
        <div className="px-3 pb-3 pt-2 bg-slate-900 border-t border-slate-700 shrink-0">
          <div className="flex items-end gap-2 bg-slate-700 rounded-xl border border-slate-600 focus-within:border-blue-500 transition-colors px-3 py-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about any stock…"
              rows={1}
              disabled={isLoading}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-400 resize-none outline-none min-h-[24px] max-h-[96px] leading-6 disabled:opacity-50"
              style={{ overflowY: input.split('\n').length > 3 ? 'auto' : 'hidden' }}
            />
            <button
              type="button"
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isLoading}
              className="shrink-0 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-default flex items-center justify-center transition-colors"
              aria-label="Send message"
            >
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Made with Bob
