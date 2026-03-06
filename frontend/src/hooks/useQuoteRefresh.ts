import { useEffect, useState } from 'react';
import { tickerApi } from '../services/api';
import type { TickerQuote } from '../services/types';

/**
 * Polls for the latest quote every N seconds for the given ticker.
 * Single source for refreshed quote: no dependency on stockData or closure staleness.
 * Cleans up interval on unmount or when ticker/intervalMs changes.
 */
export function useQuoteRefresh(
  ticker: string,
  intervalMs: number
): TickerQuote | null {
  const [quote, setQuote] = useState<TickerQuote | null>(null);

  useEffect(() => {
    if (!ticker) {
      setQuote(null);
      return;
    }

    const fetchQuote = () => {
      tickerApi
        .getQuote(ticker)
        .then(setQuote)
        .catch((err) => console.error('Quote refresh failed:', err));
    };

    fetchQuote();
    const id = setInterval(fetchQuote, intervalMs);
    return () => clearInterval(id);
  }, [ticker, intervalMs]);

  return quote;
}
