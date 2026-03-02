/**
 * TickerMentionInput
 *
 * A textarea that intercepts "@" keystrokes and shows a Fuse.js-powered
 * ticker autocomplete dropdown. Selecting a suggestion inserts "@TICKER"
 * into the text at the cursor position.
 *
 * Usage:
 *   <TickerMentionInput
 *     value={input}
 *     onChange={setInput}
 *     onKeyDown={handleKeyDown}
 *     inputRef={inputRef}
 *     placeholder="Ask about any stock…"
 *     disabled={false}
 *   />
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import Fuse from 'fuse.js';

interface Ticker {
  ticker: string;
  name: string;
}

interface TickerMentionInputProps {
  value: string;
  onChange: (value: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export default function TickerMentionInput({
  value,
  onChange,
  onKeyDown,
  inputRef: externalRef,
  placeholder,
  disabled,
  className,
}: TickerMentionInputProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = (externalRef ?? internalRef) as React.RefObject<HTMLTextAreaElement>;

  const [fuse, setFuse] = useState<Fuse<Ticker> | null>(null);
  const [suggestions, setSuggestions] = useState<Ticker[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  // The start position of the current "@query" in the textarea value
  const mentionStartRef = useRef<number>(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load stocks.json once on mount
  useEffect(() => {
    fetch('/stocks.json')
      .then((r) => r.json())
      .then((data: Ticker[]) => {
        const f = new Fuse(data, {
          keys: [
            { name: 'ticker', weight: 0.7 },
            { name: 'name', weight: 0.3 },
          ],
          threshold: 0.3,
          includeScore: true,
          minMatchCharLength: 1,
        });
        setFuse(f);
      })
      .catch(() => {/* silently ignore */});
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        textareaRef.current &&
        !textareaRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [textareaRef]);

  const closeMention = useCallback(() => {
    setShowDropdown(false);
    setSuggestions([]);
    mentionStartRef.current = -1;
  }, []);

  const insertMention = useCallback(
    (ticker: Ticker) => {
      const ta = textareaRef.current;
      if (!ta) return;

      const start = mentionStartRef.current;
      if (start < 0) return;

      // Replace from "@" up to the current cursor position with "@TICKER "
      const cursorPos = ta.selectionStart ?? value.length;
      const before = value.slice(0, start);
      const after = value.slice(cursorPos);
      const inserted = `@${ticker.ticker} `;
      const newValue = before + inserted + after;

      onChange(newValue);
      closeMention();

      // Move cursor to end of inserted mention
      requestAnimationFrame(() => {
        const newCursor = start + inserted.length;
        ta.setSelectionRange(newCursor, newCursor);
        ta.focus();
      });
    },
    [value, onChange, closeMention, textareaRef],
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    onChange(newValue);

    const cursor = e.target.selectionStart ?? newValue.length;

    // Find the last "@" before the cursor that isn't followed by a space
    const textBeforeCursor = newValue.slice(0, cursor);
    const atMatch = textBeforeCursor.match(/@([A-Za-z0-9.]*)$/);

    if (atMatch && fuse) {
      const query = atMatch[1]; // text after "@"
      mentionStartRef.current = cursor - atMatch[0].length; // position of "@"

      if (query.length === 0) {
        // Just typed "@" — show a short default list
        const topResults = fuse.search('A').slice(0, 8).map((r) => r.item);
        setSuggestions(topResults.length > 0 ? topResults : []);
        setShowDropdown(true);
        setSelectedIndex(0);
      } else {
        const results = fuse.search(query).slice(0, 8).map((r) => r.item);
        if (results.length > 0) {
          setSuggestions(results);
          setShowDropdown(true);
          setSelectedIndex(0);
        } else {
          closeMention();
        }
      }
    } else {
      closeMention();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showDropdown && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, suggestions.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(suggestions[selectedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        closeMention();
        return;
      }
    }

    // Delegate to parent handler (e.g. send on Enter)
    onKeyDown?.(e);
  };

  return (
    <div className="relative flex-1 min-w-0">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={3}
        className={`w-full ${className ?? ''}`}
        style={{ overflowY: value.split('\n').length > 8 ? 'auto' : 'hidden' }}
      />

      {/* Ticker autocomplete dropdown */}
      {showDropdown && suggestions.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute bottom-full mb-1 left-0 w-64 bg-gray-800 border border-gray-600 rounded-xl shadow-2xl z-50 overflow-hidden"
        >
          <div className="px-3 py-1.5 border-b border-gray-700 flex items-center gap-1.5">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Mention a ticker</span>
          </div>
          <ul className="max-h-52 overflow-y-auto">
            {suggestions.map((stock, i) => (
              <li key={stock.ticker}>
                <button
                  type="button"
                  onMouseDown={(e) => {
                    // Use mousedown so it fires before the textarea blur
                    e.preventDefault();
                    insertMention(stock);
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
                    i === selectedIndex
                      ? 'bg-blue-600/40 text-white'
                      : 'hover:bg-gray-700 text-slate-200'
                  }`}
                >
                  <span className="shrink-0 w-10 text-xs font-bold text-blue-300 font-mono">
                    {stock.ticker}
                  </span>
                  <span className="text-xs text-slate-400 truncate">{stock.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Made with Bob