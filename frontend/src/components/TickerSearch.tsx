import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Fuse from 'fuse.js';

interface Ticker {
  ticker: string;
  name: string;
}

interface TickerSearchProps {
  compact?: boolean;
}

export default function TickerSearch({ compact = false }: TickerSearchProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<Ticker[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [, setTickers] = useState<Ticker[]>([]);
  const [fuse, setFuse] = useState<Fuse<Ticker> | null>(null);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Load stock data on mount
  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((data: Ticker[]) => {
        setTickers(data);
        // Initialize Fuse.js with both ticker and name as searchable keys
        const fuseInstance = new Fuse(data, {
          keys: [
            { name: 'ticker', weight: 0.7 }, // Prioritize ticker matches
            { name: 'name', weight: 0.3 }
          ],
          threshold: 0.3, // Lower = more strict matching
          includeScore: true,
          minMatchCharLength: 1
        });
        setFuse(fuseInstance);
      })
      .catch((err) => {
        console.error('Failed to load stock data:', err);
      });
  }, []);

  // Handle search input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchTerm(value);
    setSelectedIndex(-1);

    if (value.trim().length === 0) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    if (fuse) {
      const results = fuse.search(value);
      const matches = results.slice(0, 8).map((result) => result.item); // Limit to 8 suggestions
      setSuggestions(matches);
      setShowSuggestions(matches.length > 0);
    }
  };

  // Handle form submission
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = searchTerm.trim().toUpperCase();
    if (ticker) {
      navigate(`/tickers/${ticker}`);
      setSearchTerm('');
      setShowSuggestions(false);
    }
  };

  // Handle suggestion selection
  const handleSelectSuggestion = (ticker: Ticker) => {
    setSearchTerm(ticker.ticker);
    setShowSuggestions(false);
    navigate(`/tickers/${ticker.ticker}`);
  };

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter') {
        handleSearch(e);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
          handleSelectSuggestion(suggestions[selectedIndex]);
        } else {
          handleSearch(e);
        }
        break;
      case 'Escape':
        setShowSuggestions(false);
        setSelectedIndex(-1);
        break;
    }
  };

  // Highlight matching text in suggestions
  const highlightMatch = (text: string, query: string) => {
    if (!query) return text;
    const regex = new RegExp(`(${query})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-500/30 text-yellow-200">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className={`w-full relative ${compact ? '' : 'max-w-2xl mx-auto mb-8'}`}>
      <form onSubmit={handleSearch} className="w-full">
        <div className="flex gap-2 relative">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={searchTerm}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (suggestions.length > 0) {
                  setShowSuggestions(true);
                }
              }}
              placeholder="Ticker search…"
              title="Use any Yahoo Finance symbol — even if it doesn't appear in the dropdown."
              className={`w-full bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                compact ? 'px-3 py-1.5 text-sm' : 'px-4 py-3'
              }`}
            />
            {showSuggestions && suggestions.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-80 overflow-y-auto"
              >
                {suggestions.map((ticker, index) => (
                  <div
                    key={`${ticker.ticker}-${index}`}
                    onClick={() => handleSelectSuggestion(ticker)}
                    className={`px-4 cursor-pointer transition-colors ${
                      compact ? 'py-2' : 'py-3'
                    } ${
                      index === selectedIndex
                        ? 'bg-blue-600/50'
                        : 'hover:bg-gray-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className={`font-semibold text-white ${compact ? 'text-sm' : ''}`}>
                          {highlightMatch(ticker.ticker, searchTerm)}
                        </div>
                        <div className="text-xs text-gray-400">
                          {highlightMatch(ticker.name, searchTerm)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            type="submit"
            className={`bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors ${
              compact ? 'px-4 py-1.5 text-sm' : 'px-6 py-3'
            }`}
          >
            Search
          </button>
        </div>
        {!compact && (
          <p className="mt-1.5 text-xs text-gray-500">
            Use any Yahoo Finance symbol — even if it doesn’t appear in the dropdown.
          </p>
        )}
      </form>
    </div>
  );
}

