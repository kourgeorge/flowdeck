import { useEffect, useState, useRef, useCallback } from 'react';
import { tickerApi } from '../services/api';
import { subscriptionApi } from '../services/subscriptionApi';
import type { TickerWidget as StockWidgetType } from '../services/types';
import { useAuth } from '../contexts/AuthContext';

const RECENT_PAGE_SIZE = 20;
const RECENT_ANALYZED_DAYS = 3;

export interface UseDashboardDataReturn {
  widgets: StockWidgetType[];
  recentAnalyzedWidgets: StockWidgetType[];
  recentTotal: number | null;
  loadingMoreRecent: boolean;
  backgroundLoadingAll: boolean;
  tickerToName: Record<string, string>;
  isLoading: boolean;
  recentScrollRef: React.RefObject<HTMLDivElement>;
  handleRecentScroll: () => void;
  handleSubscriptionChange: () => void;
}

interface UseDashboardDataOptions {
  enableRecentAnalyzed?: boolean;
}

export function useDashboardData({
  enableRecentAnalyzed = true,
}: UseDashboardDataOptions = {}): UseDashboardDataReturn {
  const { user } = useAuth();
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [recentAnalyzedWidgets, setRecentAnalyzedWidgets] = useState<StockWidgetType[]>([]);
  const [recentTotal, setRecentTotal] = useState<number | null>(null);
  const [loadingMoreRecent, setLoadingMoreRecent] = useState(false);
  const [backgroundLoadingAll, setBackgroundLoadingAll] = useState(false);
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [subscriptionsReady, setSubscriptionsReady] = useState(false);
  const [recentReady, setRecentReady] = useState(false);

  const recentScrollRef = useRef<HTMLDivElement>(null);
  const backgroundLoadStartedRef = useRef(false);

  useEffect(() => {
    if (!user) {
      setSubscriptionsReady(true);
      return;
    }
    setSubscriptionsReady(false);
  }, [user]);

  useEffect(() => {
    if (!user) {
      setRecentReady(true);
      return;
    }
    setRecentReady(!enableRecentAnalyzed);
  }, [user, enableRecentAnalyzed]);

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
    if (!enableRecentAnalyzed) {
      setRecentReady(true);
      return;
    }

    setRecentReady(false);
    backgroundLoadStartedRef.current = false;
    loadRecentPage(0, false)
      .catch(() => { setRecentAnalyzedWidgets([]); setRecentTotal(null); })
      .finally(() => setRecentReady(true));
    const interval = setInterval(() => {
      backgroundLoadStartedRef.current = false;
      loadRecentPage(0, false).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [user, loadRecentPage, enableRecentAnalyzed]);

  useEffect(() => {
    if (!user || !enableRecentAnalyzed) return;
    if (recentTotal == null || backgroundLoadStartedRef.current) return;
    if (recentAnalyzedWidgets.length >= recentTotal) return;
    loadAllRecentInBackground(recentTotal, recentAnalyzedWidgets.length);
  }, [user, recentTotal, recentAnalyzedWidgets.length, loadAllRecentInBackground, enableRecentAnalyzed]);

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
    recentScrollRef,
    handleRecentScroll,
    handleSubscriptionChange,
  };
}

// Made with Bob
