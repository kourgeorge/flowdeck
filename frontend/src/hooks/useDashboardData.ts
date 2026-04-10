import { useEffect, useState, useRef, useCallback } from 'react';
import { tickerApi } from '../services/api';
import { subscriptionApi } from '../services/subscriptionApi';
import type { TickerWidget as StockWidgetType } from '../services/types';
import { useAuth } from '../contexts/AuthContext';

const RECENT_PAGE_SIZE = 10;

export interface UseDashboardDataReturn {
  widgets: StockWidgetType[];
  recentAnalyzedWidgets: StockWidgetType[];
  recentTotal: number | null;
  loadingMoreRecent: boolean;
  tickerToName: Record<string, string>;
  isLoading: boolean;
  subscribedTickers: string[];
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
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [subscriptionsReady, setSubscriptionsReady] = useState(false);
  const [recentReady, setRecentReady] = useState(false);
  const [subscribedTickers, setSubscribedTickers] = useState<string[]>([]);

  const recentScrollRef = useRef<HTMLDivElement>(null);
  const recentEventRequestsRef = useRef<Set<string>>(new Set());

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
    if (!user) {
      setWidgets([]);
      setSubscribedTickers([]);
      setSubscriptionsReady(true);
      return;
    }
    try {
      const subs = await subscriptionApi.list();
      const tickers = subs.map((s) => s.ticker);
      
      // Set tickers immediately so newsroom can start loading
      setSubscribedTickers(tickers);
      
      if (tickers.length > 0) {
        const res = await tickerApi.getWidgets(tickers);
        setWidgets(res.widgets);
      } else {
        setWidgets([]);
      }
    } catch {
      setWidgets([]);
      setSubscribedTickers([]);
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
    const res = await tickerApi.getWidgets(undefined, undefined, false, RECENT_PAGE_SIZE, offset, undefined, true, false);
    if (res.total != null) setRecentTotal(res.total);
    if (append) {
      setRecentAnalyzedWidgets((prev) => {
        const existingTickers = new Set(prev.map((widget) => widget.ticker));
        const appended = res.widgets.filter((widget) => !existingTickers.has(widget.ticker));
        return appended.length > 0 ? [...prev, ...appended] : prev;
      });
    } else {
      setRecentAnalyzedWidgets(res.widgets);
    }
    return res;
  }, []);

  useEffect(() => {
    if (!user) {
      setRecentAnalyzedWidgets([]);
      setRecentTotal(null);
      recentEventRequestsRef.current.clear();
      setRecentReady(true);
      return;
    }
    if (!enableRecentAnalyzed) {
      setRecentReady(true);
      return;
    }

    setRecentReady(false);
    recentEventRequestsRef.current.clear();
    loadRecentPage(0, false)
      .catch(() => { setRecentAnalyzedWidgets([]); setRecentTotal(null); })
      .finally(() => setRecentReady(true));
    const interval = setInterval(() => {
      recentEventRequestsRef.current.clear();
      loadRecentPage(0, false).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [user, loadRecentPage, enableRecentAnalyzed]);

  useEffect(() => {
    if (!user || !enableRecentAnalyzed || recentAnalyzedWidgets.length === 0) return;

    const unresolvedTickers = recentAnalyzedWidgets
      .filter((widget) => widget.dominant_events == null && widget.event_count == null)
      .map((widget) => widget.ticker)
      .filter((ticker) => !recentEventRequestsRef.current.has(ticker));

    if (unresolvedTickers.length === 0) return;

    unresolvedTickers.forEach((ticker) => recentEventRequestsRef.current.add(ticker));

    tickerApi.getEventSummaries(unresolvedTickers)
      .then((response) => {
        setRecentAnalyzedWidgets((prev) => prev.map((widget) => {
          const summary = response.summaries[widget.ticker];
          if (!summary) return widget;
          return {
            ...widget,
            dominant_events: summary.dominant_events ?? [],
            event_count: summary.event_count ?? 0,
          };
        }));
      })
      .catch(() => {
        unresolvedTickers.forEach((ticker) => recentEventRequestsRef.current.delete(ticker));
      });
  }, [user, enableRecentAnalyzed, recentAnalyzedWidgets]);

  // Infinite scroll for overview tab recent list
  const handleRecentScroll = useCallback(() => {
    const el = recentScrollRef.current;
    if (!el || loadingMoreRecent || recentTotal == null) return;
    if (recentAnalyzedWidgets.length >= recentTotal) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
      setLoadingMoreRecent(true);
      loadRecentPage(recentAnalyzedWidgets.length, true)
        .then((res) => {
          if (res.total != null) setRecentTotal(res.total);
        })
        .finally(() => setLoadingMoreRecent(false));
    }
  }, [loadingMoreRecent, recentTotal, recentAnalyzedWidgets.length, loadRecentPage]);

  const handleSubscriptionChange = useCallback(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  const isLoading = !subscriptionsReady || !recentReady;

  return {
    widgets,
    recentAnalyzedWidgets,
    recentTotal,
    loadingMoreRecent,
    tickerToName,
    isLoading,
    subscribedTickers,
    recentScrollRef,
    handleRecentScroll,
    handleSubscriptionChange,
  };
}

// Made with Bob
