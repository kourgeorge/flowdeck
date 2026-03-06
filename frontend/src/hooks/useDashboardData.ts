import { useEffect, useState, useRef, useCallback } from 'react';
import { tickerApi } from '../services/api';
import { subscriptionApi } from '../services/subscriptionApi';
import type { TickerWidget as StockWidgetType, TickerPageData } from '../services/types';
import { useAuth } from '../contexts/AuthContext';

const RECENT_PAGE_SIZE = 20;
const RECENT_ANALYZED_DAYS = 3;
const PREFETCH_CONCURRENCY = 3;

export interface UseDashboardDataReturn {
  widgets: StockWidgetType[];
  recentAnalyzedWidgets: StockWidgetType[];
  recentTotal: number | null;
  loadingMoreRecent: boolean;
  backgroundLoadingAll: boolean;
  tickerToName: Record<string, string>;
  isLoading: boolean;
  selectedTicker: string | null;
  setSelectedTicker: (ticker: string | null) => void;
  prefetchCache: Record<string, TickerPageData>;
  sidebarScrollRef: React.RefObject<HTMLDivElement>;
  recentScrollRef: React.RefObject<HTMLDivElement>;
  handleSidebarScroll: () => void;
  handleRecentScroll: () => void;
  handleSubscriptionChange: () => void;
}

interface UseDashboardDataOptions {
  enablePrefetch?: boolean;
}

export function useDashboardData({ enablePrefetch = true }: UseDashboardDataOptions = {}): UseDashboardDataReturn {
  const { user } = useAuth();
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [recentAnalyzedWidgets, setRecentAnalyzedWidgets] = useState<StockWidgetType[]>([]);
  const [recentTotal, setRecentTotal] = useState<number | null>(null);
  const [loadingMoreRecent, setLoadingMoreRecent] = useState(false);
  const [backgroundLoadingAll, setBackgroundLoadingAll] = useState(false);
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [subscriptionsReady, setSubscriptionsReady] = useState(false);
  const [recentReady, setRecentReady] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [prefetchCache, setPrefetchCache] = useState<Record<string, TickerPageData>>({});

  const sidebarScrollRef = useRef<HTMLDivElement>(null);
  const recentScrollRef = useRef<HTMLDivElement>(null);
  const backgroundLoadStartedRef = useRef(false);
  const prefetchedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!user) {
      setSubscriptionsReady(true);
      setRecentReady(true);
      return;
    }
    setSubscriptionsReady(false);
    setRecentReady(false);
  }, [user]);

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
    if (!user) { setWidgets([]); setSubscriptionsReady(true); return; }
    try {
      const subs = await subscriptionApi.list();
      const tickers = subs.map((s) => s.ticker);
      if (tickers.length > 0) {
        const res = await tickerApi.getWidgets(tickers);
        setWidgets(res.widgets);
        setSelectedTicker((prev) => prev ?? (res.widgets[0]?.ticker ?? null));
      } else {
        setWidgets([]);
      }
    } catch {
      setWidgets([]);
    } finally {
      setSubscriptionsReady(true);
    }
  }, [user]);

  useEffect(() => {
    loadSubscriptions();
    const interval = setInterval(loadSubscriptions, 60000);
    return () => clearInterval(interval);
  }, [loadSubscriptions]);

  // Load first page of recently analyzed
  const loadRecentPage = useCallback(async (offset: number, append: boolean) => {
    const today = new Date().toISOString().slice(0, 10);
    const res = await tickerApi.getWidgets(undefined, today, true, RECENT_PAGE_SIZE, offset, RECENT_ANALYZED_DAYS);
    if (res.total != null) setRecentTotal(res.total);
    if (append) {
      setRecentAnalyzedWidgets((prev) => [...prev, ...res.widgets]);
    } else {
      setRecentAnalyzedWidgets(res.widgets);
      setSelectedTicker((prev) => {
        if (prev) return prev;
        return res.widgets[0]?.ticker ?? null;
      });
    }
    return res;
  }, []);

  // Background-load all remaining pages
  const loadAllRecentInBackground = useCallback(async (knownTotal: number, alreadyLoaded: number) => {
    if (backgroundLoadStartedRef.current) return;
    backgroundLoadStartedRef.current = true;
    setBackgroundLoadingAll(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      let offset = alreadyLoaded;
      while (offset < knownTotal) {
        const res = await tickerApi.getWidgets(undefined, today, true, RECENT_PAGE_SIZE, offset, RECENT_ANALYZED_DAYS);
        if (res.total != null) setRecentTotal(res.total);
        setRecentAnalyzedWidgets((prev) => {
          const existingTickers = new Set(prev.map((w) => w.ticker));
          const newWidgets = res.widgets.filter((w) => !existingTickers.has(w.ticker));
          return newWidgets.length > 0 ? [...prev, ...newWidgets] : prev;
        });
        offset += res.widgets.length;
        if (res.widgets.length === 0) break;
      }
    } catch {
      // Non-critical
    } finally {
      setBackgroundLoadingAll(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setRecentAnalyzedWidgets([]);
      setRecentTotal(null);
      setRecentReady(true);
      return;
    }
    backgroundLoadStartedRef.current = false;
    loadRecentPage(0, false)
      .catch(() => { setRecentAnalyzedWidgets([]); setRecentTotal(null); })
      .finally(() => setRecentReady(true));
    const interval = setInterval(() => {
      backgroundLoadStartedRef.current = false;
      loadRecentPage(0, false).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [user, loadRecentPage]);

  useEffect(() => {
    if (!user) return;
    if (recentTotal == null || backgroundLoadStartedRef.current) return;
    if (recentAnalyzedWidgets.length >= recentTotal) return;
    loadAllRecentInBackground(recentTotal, recentAnalyzedWidgets.length);
  }, [user, recentTotal, recentAnalyzedWidgets.length, loadAllRecentInBackground]);

  // Prefetch stock page data
  useEffect(() => {
    if (!user || !enablePrefetch) return;

    const allTickers = Array.from(new Set([
      ...widgets.map((w) => w.ticker),
      ...recentAnalyzedWidgets.map((w) => w.ticker),
    ]));
    const newTickers = allTickers.filter((t) => !prefetchedRef.current.has(t));
    if (newTickers.length === 0) return;

    newTickers.forEach((t) => prefetchedRef.current.add(t));
    let cancelled = false;

    const fetchBatch = async (batch: string[]) => {
      await Promise.all(
        batch.map((ticker) =>
          tickerApi.getTickerPage(ticker)
            .then((data) => {
              if (cancelled) return;
              setPrefetchCache((prev) => ({ ...prev, [ticker]: data }));
            })
            .catch(() => {
              if (cancelled) return;
              prefetchedRef.current.delete(ticker);
            })
        )
      );
    };

    const runQueue = async () => {
      for (let i = 0; i < newTickers.length; i += PREFETCH_CONCURRENCY) {
        if (cancelled) return;
        await fetchBatch(newTickers.slice(i, i + PREFETCH_CONCURRENCY));
      }
    };

    void runQueue();
    return () => {
      cancelled = true;
    };
  }, [user, widgets, recentAnalyzedWidgets, enablePrefetch]);

  // Infinite scroll for sidebar
  const handleSidebarScroll = useCallback(() => {
    const el = sidebarScrollRef.current;
    if (!el || loadingMoreRecent || backgroundLoadingAll || recentTotal == null) return;
    if (recentAnalyzedWidgets.length >= recentTotal) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) {
      setLoadingMoreRecent(true);
      const today = new Date().toISOString().slice(0, 10);
      tickerApi
        .getWidgets(undefined, today, true, RECENT_PAGE_SIZE, recentAnalyzedWidgets.length, RECENT_ANALYZED_DAYS)
        .then((res) => {
          if (res.total != null) setRecentTotal(res.total);
          setRecentAnalyzedWidgets((prev) => [...prev, ...res.widgets]);
        })
        .finally(() => setLoadingMoreRecent(false));
    }
  }, [loadingMoreRecent, backgroundLoadingAll, recentTotal, recentAnalyzedWidgets.length]);

  // Infinite scroll for overview tab recent list
  const handleRecentScroll = useCallback(() => {
    const el = recentScrollRef.current;
    if (!el || loadingMoreRecent || backgroundLoadingAll || recentTotal == null) return;
    if (recentAnalyzedWidgets.length >= recentTotal) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
      setLoadingMoreRecent(true);
      const today = new Date().toISOString().slice(0, 10);
      tickerApi
        .getWidgets(undefined, today, true, RECENT_PAGE_SIZE, recentAnalyzedWidgets.length, RECENT_ANALYZED_DAYS)
        .then((res) => {
          if (res.total != null) setRecentTotal(res.total);
          setRecentAnalyzedWidgets((prev) => [...prev, ...res.widgets]);
        })
        .finally(() => setLoadingMoreRecent(false));
    }
  }, [loadingMoreRecent, backgroundLoadingAll, recentTotal, recentAnalyzedWidgets.length]);

  const handleSubscriptionChange = useCallback(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  const isLoading = !subscriptionsReady || !recentReady;

  return {
    widgets,
    recentAnalyzedWidgets,
    recentTotal,
    loadingMoreRecent,
    backgroundLoadingAll,
    tickerToName,
    isLoading,
    selectedTicker,
    setSelectedTicker,
    prefetchCache,
    sidebarScrollRef,
    recentScrollRef,
    handleSidebarScroll,
    handleRecentScroll,
    handleSubscriptionChange,
  };
}

// Made with Bob
