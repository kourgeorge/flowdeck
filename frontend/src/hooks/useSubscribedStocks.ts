import { useEffect, useState, useRef, useCallback } from 'react';
import { tickerApi } from '../services/api';
import { subscriptionApi } from '../services/subscriptionApi';
import type { TickerWidget as StockWidgetType, TickerPageData } from '../services/types';
import { useAuth } from '../contexts/AuthContext';

const PREFETCH_CONCURRENCY = 3;

export interface UseSubscribedStocksReturn {
  widgets: StockWidgetType[];
  tickerToName: Record<string, string>;
  isLoading: boolean;
  selectedTicker: string | null;
  setSelectedTicker: (ticker: string | null) => void;
  prefetchCache: Record<string, TickerPageData>;
  prefetchProgress: { completed: number; inFlight: number; total: number };
  handleSubscriptionChange: () => void;
  /** Add a ticker to the vibe list (fetches widget data on the fly) */
  addTicker: (ticker: string) => Promise<void>;
  /** Remove a ticker from the vibe list */
  removeTicker: (ticker: string) => void;
}

/**
 * Lightweight hook that loads only the user's subscribed stocks and prefetches
 * their StockPageData. Used by VibeTradingPage which only shows the portfolio.
 *
 * The list is initialised from the user's subscriptions but the user can freely
 * add/remove tickers without affecting their actual subscription state.
 */
export function useSubscribedStocks(): UseSubscribedStocksReturn {
  const { user } = useAuth();
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [prefetchCache, setPrefetchCache] = useState<Record<string, TickerPageData>>({});

  const prefetchedRef = useRef<Set<string>>(new Set());
  const prefetchingRef = useRef<Set<string>>(new Set());
  const [prefetchProgress, setPrefetchProgress] = useState({ completed: 0, inFlight: 0, total: 0 });
  // Track which tickers were loaded from subscriptions so we can detect
  // user-added extras that should survive a subscription reload.
  const userAddedRef = useRef<Set<string>>(new Set());

  const updatePrefetchProgress = useCallback((tickers: string[]) => {
    const total = tickers.length;
    const completed = tickers.filter((t) => prefetchedRef.current.has(t)).length;
    const inFlight = tickers.filter((t) => prefetchingRef.current.has(t)).length;
    setPrefetchProgress((prev) =>
      prev.completed === completed && prev.inFlight === inFlight && prev.total === total
        ? prev
        : { completed, inFlight, total }
    );
  }, []);

  // Load ticker name map
  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((arr: Array<{ ticker: string; name: string }>) => {
        const map: Record<string, string> = {};
        arr.forEach(({ ticker, name }) => { map[ticker] = name; });
        setTickerToName(map);
      })
      .catch(() => {});
  }, []);

  // Load subscribed stocks
  const loadSubscriptions = useCallback(async () => {
    if (!user) { setWidgets([]); setIsLoading(false); return; }
    try {
      setIsLoading(true);
      const subs = await subscriptionApi.list();
      const subTickers = subs.map((s) => s.ticker);

      // Merge subscription tickers with any user-added extras
      const allTickers = Array.from(
        new Set([...subTickers, ...Array.from(userAddedRef.current)])
      );

      if (allTickers.length > 0) {
        const res = await tickerApi.getWidgets(allTickers);
        setWidgets(res.widgets);
        setSelectedTicker((prev) => prev ?? (res.widgets[0]?.ticker ?? null));
      } else {
        setWidgets([]);
      }
    } catch {
      setWidgets([]);
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadSubscriptions();
    const interval = setInterval(loadSubscriptions, 60000);
    return () => clearInterval(interval);
  }, [loadSubscriptions]);

  // Prefetch stock page data for all tickers in the list
  useEffect(() => {
    if (!user || widgets.length === 0) return;
    const allTickers = widgets.map((w) => w.ticker);
    const newTickers = allTickers.filter(
      (t) => !prefetchedRef.current.has(t) && !prefetchingRef.current.has(t)
    );
    if (newTickers.length === 0) {
      updatePrefetchProgress(allTickers);
      return;
    }

    newTickers.forEach((t) => prefetchingRef.current.add(t));
    updatePrefetchProgress(allTickers);

    const fetchBatch = async (batch: string[]) => {
      await Promise.all(
        batch.map((ticker) =>
          tickerApi.getTickerPage(ticker)
            .then((data) => {
              setPrefetchCache((prev) => ({ ...prev, [ticker]: data }));
              prefetchedRef.current.add(ticker);
            })
            .catch(() => {
              // leave out of prefetched so it can retry later
            })
            .finally(() => {
              prefetchingRef.current.delete(ticker);
              updatePrefetchProgress(allTickers);
            })
        )
      );
    };

    const runQueue = async () => {
      for (let i = 0; i < newTickers.length; i += PREFETCH_CONCURRENCY) {
        await fetchBatch(newTickers.slice(i, i + PREFETCH_CONCURRENCY));
      }
    };

    runQueue();
  }, [user, widgets, updatePrefetchProgress]);

  const handleSubscriptionChange = useCallback(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  /** Add a ticker to the vibe list without subscribing */
  const addTicker = useCallback(async (ticker: string) => {
    const upper = ticker.toUpperCase();
    if (widgets.some((w) => w.ticker === upper)) return; // already in list
    userAddedRef.current.add(upper);
    try {
      const res = await tickerApi.getWidgets([upper]);
      if (res.widgets.length > 0) {
        setWidgets((prev) => {
          if (prev.some((w) => w.ticker === upper)) return prev;
          return [...prev, ...res.widgets];
        });
        setSelectedTicker(upper);
      }
    } catch {
      userAddedRef.current.delete(upper);
    }
  }, [widgets]);

  /** Remove a ticker from the vibe list without unsubscribing */
  const removeTicker = useCallback((ticker: string) => {
    const upper = ticker.toUpperCase();
    userAddedRef.current.delete(upper);
    prefetchedRef.current.delete(upper);
    setWidgets((prev) => prev.filter((w) => w.ticker !== upper));
    setPrefetchCache((prev) => {
      const next = { ...prev };
      delete next[upper];
      return next;
    });
    setSelectedTicker((prev) => {
      if (prev !== upper) return prev;
      // Select the next available ticker
      const remaining = widgets.filter((w) => w.ticker !== upper);
      return remaining[0]?.ticker ?? null;
    });
  }, [widgets]);

  return {
    widgets,
    tickerToName,
    isLoading,
    selectedTicker,
    setSelectedTicker,
    prefetchCache,
    prefetchProgress,
    handleSubscriptionChange,
    addTicker,
    removeTicker,
  };
}

// Made with Bob