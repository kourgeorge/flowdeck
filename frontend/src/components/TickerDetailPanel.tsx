import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { tickerApi, configApi } from '../services/api';
import { WebSocketClient } from '../services/websocket';
import type { SimilarTicker, TickerPageData, SimilarTickersResponse } from '../services/types';
import { useQuoteRefresh } from '../hooks/useQuoteRefresh';
import { useAuth } from '../contexts/AuthContext';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import ReportTabs, { OVERVIEW_TAB_KEY, CHAT_TAB_KEY } from './ReportTabs';
import { getErrorMessage } from '../utils/errorHandling';
import ReportViewer from './ReportViewer';
import HierarchicalMindMap from './HierarchicalMindMap';
import SubscribeButton from './SubscribeButton';
import AuthModal from './AuthModal';
import PriceTrendWidget from './PriceTrendWidget';
import FinancialStatementViewer from './FinancialStatementViewer';
import FundamentalCharts from './FundamentalCharts';
import FundamentalPanes from './FundamentalPanes';
import NewsWidget from './NewsWidget';
import InsiderTransactionsWidget from './InsiderTransactionsWidget';
import AIAnalysisLoadingView from './AIAnalysisLoadingView';
import EventsPanel from './EventsPanel';
import { parseReportDate } from '../utils/date';
import { formatPrice } from '../utils/currency';
import AspectSpiderChart, { getAnalysisScoreEntries } from './AspectSpiderChart';
import ReturnScenarioBar from './ReturnScenarioBar';

interface CompanyInfo {
  name: string; sector: string; industry: string; exchange: string;
  country: string; website: string; quoteType?: string | null;
}
interface ExtendedInfo {
  beta: number | null; market_cap: number | null; revenue: number | null;
  gross_margin: number | null; dividend_yield: number | null; trailing_eps: number | null;
  forward_eps: number | null; average_volume: number | null; enterprise_value: number | null;
  profit_margin: number | null; operating_margin: number | null; ebitda: number | null;
  pe_ratio: number | null; forward_pe: number | null;
}
interface StockDetailPanelProps {
  ticker: string;
  /** Pre-fetched stock page data from the dashboard cache (avoids loading spinner). */
  prefetchedData?: TickerPageData | null;
  onSubscriptionChange?: () => void;
}
const REPORT_PROCESS_ORDER = [
  'market_report','sentiment_report','news_report','technical_report',
  'fundamentals_report','sec_report','investment_plan','trader_investment_plan','final_trade_decision',
];
const SIMILAR_STOCKS_PER_PAGE = 10;

const MAIN_TAB_IDS = ['overview', 'fundamentals', 'sec-filings', 'insider-transactions', 'news', 'events', 'similar-stocks', 'ai-analysis'] as const;
type MainTabId = (typeof MAIN_TAB_IDS)[number];
const DEFAULT_MAIN_TAB: MainTabId = 'ai-analysis';

function reportKeyFromParam(param: string | null): string | null {
  if (param === 'overview') return OVERVIEW_TAB_KEY;
  if (param === 'chat') return CHAT_TAB_KEY;
  if (param) return param;
  return null;
}
function reportParamFromKey(key: string | null): string | null {
  if (key === OVERVIEW_TAB_KEY) return 'overview';
  if (key === CHAT_TAB_KEY) return 'chat';
  if (key) return key;
  return null;
}

function isMainTabId(value: string | null): value is MainTabId {
  return !!value && MAIN_TAB_IDS.includes(value as MainTabId);
}

function toAnalysisDateKey(value: string | null | undefined): string | null {
  if (!value) return null;
  return value.includes('_') ? value.slice(0, value.indexOf('_')) : value.slice(0, 10);
}

function getHistoricalPeriodForDate(dateKey: string): string {
  const target = new Date(`${dateKey}T00:00:00Z`);
  if (Number.isNaN(target.getTime())) return 'max';
  const now = new Date();
  const diffDays = Math.max(0, Math.ceil((now.getTime() - target.getTime()) / (1000 * 60 * 60 * 24)));
  if (diffDays <= 5) return '5d';
  if (diffDays <= 31) return '1mo';
  if (diffDays <= 92) return '3mo';
  if (diffDays <= 184) return '6mo';
  if (diffDays <= 366) return '1y';
  if (diffDays <= 731) return '2y';
  if (diffDays <= 1826) return '5y';
  if (diffDays <= 3652) return '10y';
  return 'max';
}

function getHistoricalCloseForDate(
  points: Array<{ date?: string; close?: number; adj_close?: number }> | undefined,
  dateKey: string,
): number | null {
  if (!Array.isArray(points) || points.length === 0) return null;
  for (let idx = points.length - 1; idx >= 0; idx -= 1) {
    const point = points[idx];
    const pointDate = toAnalysisDateKey(point?.date);
    if (!pointDate || pointDate > dateKey) continue;
    const price = typeof point.close === 'number' ? point.close : point.adj_close;
    if (typeof price === 'number' && Number.isFinite(price)) return price;
  }
  return null;
}

export default function StockDetailPanel({ ticker, prefetchedData, onSubscriptionChange }: StockDetailPanelProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMessage, setAuthModalMessage] = useState('Please sign in to run a fresh analysis.');
  const [previewTickers, setPreviewTickers] = useState<Set<string>>(new Set());
  const [stockData, setStockData] = useState<TickerPageData | null>(prefetchedData ?? null);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [extendedInfo, setExtendedInfo] = useState<ExtendedInfo | null>(null);
  const [isLoading, setIsLoading] = useState(!prefetchedData);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  // EXPERIMENTAL: historical run selector — remove this block + related JSX to disable
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [historicalReportsData, setHistoricalReportsData] = useState<Record<string, any> | null>(null);
  const [isLoadingHistoricalRun, setIsLoadingHistoricalRun] = useState(false);
  const [runSelectorOpen, setRunSelectorOpen] = useState(false);
  const runSelectorRef = useRef<HTMLDivElement>(null);
  const runDropdownRef = useRef<HTMLDivElement>(null);
  const [runDropdownPosition, setRunDropdownPosition] = useState<{ top: number; left: number; width: number } | null>(null);
  // END EXPERIMENTAL
  const [activeTab, setActiveTab] = useState<MainTabId>(DEFAULT_MAIN_TAB);
  const [fundamentalsData, setFundamentalsData] = useState<string | object | null>(null);
  const [financialStatements, setFinancialStatements] = useState<any>(null);
  const [isLoadingFundamentals, setIsLoadingFundamentals] = useState(false);
  const [newsData, setNewsData] = useState<any[]>([]);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [isLoadingNews, setIsLoadingNews] = useState(false);
  const [insiderTransactions, setInsiderTransactions] = useState<any[]>([]);
  const [insiderTransactionsError, setInsiderTransactionsError] = useState<string | null>(null);
  const [isLoadingInsiderTransactions, setIsLoadingInsiderTransactions] = useState(false);
  const [hasLoadedInsiderTransactions, setHasLoadedInsiderTransactions] = useState(false);
  const [analystRecommendations, setAnalystRecommendations] = useState<any>(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [fundamentalsSubTab, setFundamentalsSubTab] = useState<'statements' | 'charts'>('charts');
  const [fundInfo, setFundInfo] = useState<any>(null);
  const [isLoadingFundInfo, setIsLoadingFundInfo] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isStartingAnalysis, setIsStartingAnalysis] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState<{ agent_statuses: Record<string,string>; current_agent?: string | null } | null>(null);
  const [edgarFilings, setEdgarFilings] = useState<any>(null);
  const [edgarFilingsError, setEdgarFilingsError] = useState<string | null>(null);
  const [isLoadingEdgar, setIsLoadingEdgar] = useState(false);
  const [futureEvents, setFutureEvents] = useState<any>(null);
  const [isLoadingFutureEvents, setIsLoadingFutureEvents] = useState(false);
  const [eventsData, setEventsData] = useState<any>(null);
  const [eventsError, setEventsError] = useState<string | undefined>(undefined);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [subscriptionForTicker, setSubscriptionForTicker] = useState<Subscription | null>(null);
  const [emailPreferenceToggling, setEmailPreferenceToggling] = useState(false);
  const [similarTickers, setSimilarTickers] = useState<SimilarTickersResponse | null>(null);
  const [similarTickerPages, setSimilarTickerPages] = useState<Record<number, SimilarTicker[]>>({});
  const [similarHasMoreByPage, setSimilarHasMoreByPage] = useState<Record<number, boolean>>({});
  const [similarStocksPage, setSimilarStocksPage] = useState(1);
  const [isLoadingSimilarTickers, setIsLoadingSimilarTickers] = useState(false);
  const [showModelNames, setShowModelNames] = useState(() => {
    try {
      return localStorage.getItem('flowdeck_show_model_names') === 'true';
    } catch {
      return false;
    }
  });
  const [priceFlash, setPriceFlash] = useState(false);
  const [companyOfficers, setCompanyOfficers] = useState<any[]>([]);
  const [isLoadingOfficers, setIsLoadingOfficers] = useState(false);
  const [hasLoadedCompanyOfficers, setHasLoadedCompanyOfficers] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [analysisReferencePrice, setAnalysisReferencePrice] = useState<number | null>(null);

  const refreshedQuote = useQuoteRefresh(ticker, 60000);
  const prevPriceRef = useRef<number | null>(null);
  const wsClientRef = useRef<WebSocketClient | null>(null);
  const insiderFetchIdRef = useRef(0);
  const viewingHistoricalRunRef = useRef(false);
  const analysisReferencePriceCacheRef = useRef<Record<string, number | null>>({});

  const quoteType = companyInfo?.quoteType ?? (
    fundamentalsData && typeof fundamentalsData === 'object' && 'QuoteType' in fundamentalsData
      ? (fundamentalsData as { QuoteType?: string }).QuoteType : undefined
  );
  const normalizedTicker = (ticker ?? '').toUpperCase();
  const isPreviewTicker = previewTickers.has(normalizedTicker);
  const canAccessGuestPreviewContent = Boolean(user || isPreviewTicker);
  const hasFundamentals = quoteType === 'EQUITY' || quoteType == null;
  const hasInsiderTransactions = quoteType === 'EQUITY' || quoteType == null;
  const hasSimilarStocks = quoteType === 'EQUITY' || quoteType == null;
  const isUSCompany = companyInfo?.country === 'United States' || companyInfo?.country === 'USA';

  useEffect(() => {
    configApi.getPublicConfig()
      .then((cfg) => setPreviewTickers(new Set(cfg.preview_tickers.map((t) => t.toUpperCase()))))
      .catch(() => {});
  }, []);

  // Sync URL search params -> tab state (so reload / back restores tab)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    const subParam = searchParams.get('sub');
    const reportParam = searchParams.get('report');
    if (isMainTabId(tabParam)) {
      setActiveTab(tabParam);
      if (tabParam === 'fundamentals' && (subParam === 'charts' || subParam === 'statements')) {
        setFundamentalsSubTab(subParam);
      }
      if (tabParam === 'ai-analysis' && reportParam) {
        const key = reportKeyFromParam(reportParam);
        if (key) setSelectedReport(key);
      }
    } else if (!tabParam) {
      // No tab param in URL, set default and update URL
      setActiveTab(DEFAULT_MAIN_TAB);
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', DEFAULT_MAIN_TAB);
        return next;
      }, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (activeTab === 'fundamentals' && quoteType != null && quoteType !== 'EQUITY') {
      setActiveTab('overview');
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', 'overview');
        next.delete('sub');
        next.delete('report');
        return next;
      }, { replace: true });
    }
  }, [quoteType, activeTab, setSearchParams]);

  // When switching to the AI Analysis tab, open the Overview sub-tab by default
  const prevMainTabRef = useRef<string>(activeTab);
  useEffect(() => {
    if (prevMainTabRef.current !== 'ai-analysis' && activeTab === 'ai-analysis') {
      setSelectedReport(OVERVIEW_TAB_KEY);
    }
    prevMainTabRef.current = activeTab;
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'insider-transactions' && quoteType != null && quoteType !== 'EQUITY') {
      setActiveTab('overview');
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', 'overview');
        next.delete('sub');
        next.delete('report');
        return next;
      }, { replace: true });
    }
  }, [quoteType, activeTab, setSearchParams]);

  useEffect(() => {
    if (activeTab === 'similar-stocks' && quoteType != null && quoteType !== 'EQUITY') {
      setActiveTab('overview');
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', 'overview');
        next.delete('sub');
        next.delete('report');
        return next;
      }, { replace: true });
    }
  }, [quoteType, activeTab, setSearchParams]);

  const handleMainTabChange = useCallback((tabId: MainTabId) => {
    setActiveTab(tabId);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', tabId);
      if (tabId !== 'fundamentals') next.delete('sub');
      if (tabId !== 'ai-analysis') next.delete('report');
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  const handleFundamentalsSubTabChange = useCallback((sub: 'charts' | 'statements') => {
    setFundamentalsSubTab(sub);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', 'fundamentals');
      next.set('sub', sub);
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  const handleSelectReport = useCallback((reportType: string) => {
    setSelectedReport(reportType);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', 'ai-analysis');
      const param = reportParamFromKey(reportType);
      if (param) next.set('report', param);
      else next.delete('report');
      return next;
    }, { replace: false });
  }, [setSearchParams]);

  useEffect(() => {
    const currentPrice = refreshedQuote?.current_price ?? stockData?.quote?.current_price;
    if (currentPrice == null) return;
    if (prevPriceRef.current !== null && prevPriceRef.current !== currentPrice) {
      setPriceFlash(true);
      const t = setTimeout(() => setPriceFlash(false), 600);
      return () => { clearTimeout(t); prevPriceRef.current = currentPrice; };
    }
    prevPriceRef.current = currentPrice;
  }, [refreshedQuote?.current_price, stockData?.quote?.current_price]);

  useEffect(() => {
    viewingHistoricalRunRef.current = !!selectedRunId;
  }, [selectedRunId]);

  const activeAnalysisDate = selectedRunId != null
    ? stockData?.historical_analyses.find((x) => x.analysis_run_id === selectedRunId)?.date ?? stockData?.report_date ?? null
    : stockData?.report_date ?? null;
  const activeAnalysisDateKey = toAnalysisDateKey(activeAnalysisDate);
  const activeInvestmentPlanReport = selectedRunId != null
    ? historicalReportsData?.investment_plan
    : stockData?.reports_with_scores?.investment_plan;
  const analysisReferencePriceFromMetadata = typeof activeInvestmentPlanReport?.current_price === 'number'
    ? activeInvestmentPlanReport.current_price
    : null;

  useEffect(() => {
    if (analysisReferencePriceFromMetadata != null) {
      setAnalysisReferencePrice(analysisReferencePriceFromMetadata);
      return;
    }

    if (!ticker || !activeAnalysisDateKey) {
      setAnalysisReferencePrice(null);
      return;
    }

    const cacheKey = `${ticker}:${activeAnalysisDateKey}`;
    if (Object.prototype.hasOwnProperty.call(analysisReferencePriceCacheRef.current, cacheKey)) {
      setAnalysisReferencePrice(analysisReferencePriceCacheRef.current[cacheKey] ?? null);
      return;
    }

    let cancelled = false;
    setAnalysisReferencePrice(null);

    const loadAnalysisReferencePrice = async () => {
      try {
        const historical = await tickerApi.getHistoricalPrices(
          ticker,
          getHistoricalPeriodForDate(activeAnalysisDateKey),
          '1d',
        );
        const price = getHistoricalCloseForDate(historical?.data, activeAnalysisDateKey);
        analysisReferencePriceCacheRef.current[cacheKey] = price;
        if (!cancelled) setAnalysisReferencePrice(price);
      } catch {
        analysisReferencePriceCacheRef.current[cacheKey] = null;
        if (!cancelled) setAnalysisReferencePrice(null);
      }
    };

    void loadAnalysisReferencePrice();

    return () => {
      cancelled = true;
    };
  }, [ticker, activeAnalysisDateKey, analysisReferencePriceFromMetadata]);

  const applyStockData = (data: TickerPageData) => {
    setStockData(data);
    // Reset historical run selection when stock data refreshes
    setSelectedRunId(null);
    setHistoricalReportsData(null);
    if (data.reports && Object.keys(data.reports).length > 0) {
      setSelectedReport(OVERVIEW_TAB_KEY);
    }
    if (data.is_generating && data.generation_analysis_run_id != null) {
      setAnalysisProgress(null);
      const client = new WebSocketClient(data.generation_analysis_run_id);
      client.on('status', (msg: any) => { const s = msg?.data?.agent_statuses; if (s) setAnalysisProgress({ agent_statuses: s, current_agent: msg?.data?.current_agent ?? null }); });
      client.on('progress', (msg: any) => {
        const s = msg?.data?.agent_statuses;
        const c = msg?.data?.current_agent;
        if (s) setAnalysisProgress({ agent_statuses: s, current_agent: c ?? null });
        // Update stock data to get new reports, but keep the existing data structure
        tickerApi.getTickerPage(ticker).then((freshData) => {
          setStockData(freshData);
          // Don't change report tab when user is viewing a previous run
          if (viewingHistoricalRunRef.current) return;
          if (freshData.reports && Object.keys(freshData.reports).length > 0) {
            const keys = Object.keys(freshData.reports);
            setSelectedReport((prev) => {
              if (prev && prev !== OVERVIEW_TAB_KEY && keys.includes(prev)) return prev;
              return OVERVIEW_TAB_KEY;
            });
          }
        }).catch(() => {});
      });
      client.on('completed', () => {
        setAnalysisProgress(null);
        void loadStockData({ showGlobalLoading: false, refreshSupportingData: false });
      });
      client.connect();
      wsClientRef.current = client;
    } else { setAnalysisProgress(null); }
  };

  const fetchSimilarTickersPage = useCallback(async (page: number): Promise<boolean> => {
    if (!ticker || !canAccessGuestPreviewContent || !hasSimilarStocks) return false;

    const safePage = Math.max(1, page);
    const offset = (safePage - 1) * SIMILAR_STOCKS_PER_PAGE;

    setIsLoadingSimilarTickers(true);
    try {
      const data = await tickerApi.getSimilarTickers(ticker, SIMILAR_STOCKS_PER_PAGE, offset);
      console.log('Similar tickers response:', data);
      const rows = data.similar_tickers || [];
      const hasMore = typeof data.has_more === 'boolean'
        ? data.has_more
        : rows.length === SIMILAR_STOCKS_PER_PAGE;
      setSimilarTickers(data);
      setSimilarTickerPages((prev) => ({ ...prev, [safePage]: rows }));
      setSimilarHasMoreByPage((prev) => ({ ...prev, [safePage]: hasMore }));
      return safePage === 1 || rows.length > 0;
    } catch (error) {
      console.error('Error fetching similar tickers:', error);
      if (safePage === 1) {
        setSimilarTickers(null);
        setSimilarTickerPages({});
        setSimilarHasMoreByPage({});
      }
      return false;
    } finally {
      setIsLoadingSimilarTickers(false);
    }
  }, [ticker, canAccessGuestPreviewContent, hasSimilarStocks]);

  const loadStockData = async ({
    showGlobalLoading = true,
    refreshSupportingData = true,
  }: {
    showGlobalLoading?: boolean;
    refreshSupportingData?: boolean;
  } = {}) => {
    if (!ticker) return;
    try {
      if (showGlobalLoading) {
        setIsLoading(true);
        setLoadError(null);
      }
      const data = await tickerApi.getTickerPage(ticker);
      applyStockData(data);
    } catch (error: any) {
      if (showGlobalLoading) {
        const detail = error?.response?.data?.detail;
        const is404 = error?.response?.status === 404;
        setLoadError(typeof detail === 'string' ? detail : is404 ? `Ticker "${ticker}" not found.` : 'Unable to load stock data.');
        setStockData(null);
      }
    } finally {
      if (showGlobalLoading) setIsLoading(false);
    }

    if (!refreshSupportingData) return;

    tickerApi.getCompanyInfo(ticker).then((info) => {
      setCompanyInfo(info);
      const qt = info.quoteType;
      if (qt === 'EQUITY' || qt == null) {
        setIsLoadingFundamentals(true);
        tickerApi.getFundamentals(ticker).then((r) => r && setFundamentalsData(r.fundamentals)).catch(() => {}).finally(() => setIsLoadingFundamentals(false));
      } else { setFundamentalsData(null); setIsLoadingFundamentals(false); }
      if (qt === 'ETF') {
        setIsLoadingFundInfo(true);
        tickerApi.getFundInfo(ticker).then(setFundInfo).catch(() => {}).finally(() => setIsLoadingFundInfo(false));
      } else { setFundInfo(null); }
    }).catch(() => {});
    tickerApi.getExtendedInfo(ticker).then(setExtendedInfo).catch(() => {});
    setIsLoadingRecommendations(true);
    tickerApi.getAnalystRecommendations(ticker).then(setAnalystRecommendations).catch(() => {}).finally(() => setIsLoadingRecommendations(false));
    setIsLoadingFutureEvents(true);
    tickerApi.getFutureEvents(ticker).then(setFutureEvents).catch(() => {}).finally(() => setIsLoadingFutureEvents(false));
    setIsLoadingEvents(true);
    setEventsError(undefined);
    tickerApi
      .getEvents(ticker)
      .then(setEventsData)
      .catch((err) => setEventsError(getErrorMessage(err)))
      .finally(() => setIsLoadingEvents(false));
  };

  useEffect(() => {
    // Reset all per-ticker state
    const requestedTab = searchParams.get('tab');
    const nextTab: MainTabId = isMainTabId(requestedTab) ? requestedTab : DEFAULT_MAIN_TAB;
    const nextSub = searchParams.get('sub');
    const nextReport = searchParams.get('report');

    insiderFetchIdRef.current += 1;
    setCompanyInfo(null); setExtendedInfo(null); setFundamentalsData(null);
    setFinancialStatements(null); setNewsData([]); setNewsError(null); setInsiderTransactions([]);
    setInsiderTransactionsError(null); setIsLoadingInsiderTransactions(false); setHasLoadedInsiderTransactions(false);
    setCompanyOfficers([]); setIsLoadingOfficers(false); setHasLoadedCompanyOfficers(false);
    setFundamentalsSubTab(nextTab === 'fundamentals' && (nextSub === 'charts' || nextSub === 'statements') ? nextSub : 'charts'); setFundInfo(null);
    setAnalysisProgress(null); setEdgarFilings(null); setEdgarFilingsError(null); setFutureEvents(null);
    setEventsData(null); setEventsError(undefined); setIsLoadingEvents(false);
    setSimilarTickers(null); setSimilarTickerPages({}); setSimilarHasMoreByPage({}); setSimilarStocksPage(1);
    setActiveTab(nextTab);
    setSelectedReport(nextTab === 'ai-analysis' ? (reportKeyFromParam(nextReport) ?? null) : null);
    setLoadError(null); setAnalysisError(null);
    setIsStartingAnalysis(false);
    // EXPERIMENTAL: reset historical run state
    setSelectedRunId(null); setHistoricalReportsData(null);
    // END EXPERIMENTAL
    if (!isMainTabId(requestedTab)) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', DEFAULT_MAIN_TAB);
        next.delete('sub');
        next.delete('report');
        return next;
      }, { replace: true });
    }
    if (wsClientRef.current) { wsClientRef.current.disconnect(); wsClientRef.current = null; }

    if (prefetchedData) {
      // Use pre-fetched data immediately — no loading spinner
      setStockData(prefetchedData);
      setIsLoading(false);
      applyStockData(prefetchedData);
      // Silently refresh stock page data in the background to pick up any changes
      // since the prefetch (e.g. new report, updated price). No loading spinner shown.
      tickerApi.getTickerPage(ticker).then((fresh) => applyStockData(fresh)).catch(() => {});
      // Kick off background fetches for secondary data (company info, extended info, etc.)
      tickerApi.getCompanyInfo(ticker).then((info) => {
        setCompanyInfo(info);
        const qt = info.quoteType;
        if (qt === 'EQUITY' || qt == null) {
          setIsLoadingFundamentals(true);
          tickerApi.getFundamentals(ticker).then((r) => r && setFundamentalsData(r.fundamentals)).catch(() => {}).finally(() => setIsLoadingFundamentals(false));
        } else { setFundamentalsData(null); setIsLoadingFundamentals(false); }
        if (qt === 'ETF') {
          setIsLoadingFundInfo(true);
          tickerApi.getFundInfo(ticker).then(setFundInfo).catch(() => {}).finally(() => setIsLoadingFundInfo(false));
        } else { setFundInfo(null); }
      }).catch(() => {});
      tickerApi.getExtendedInfo(ticker).then(setExtendedInfo).catch(() => {});
      setIsLoadingRecommendations(true);
      tickerApi.getAnalystRecommendations(ticker).then(setAnalystRecommendations).catch(() => {}).finally(() => setIsLoadingRecommendations(false));
      setIsLoadingFutureEvents(true);
      tickerApi.getFutureEvents(ticker).then(setFutureEvents).catch(() => {}).finally(() => setIsLoadingFutureEvents(false));
      setIsLoadingEvents(true);
      tickerApi.getEvents(ticker).then(setEventsData).catch((err) => setEventsError(getErrorMessage(err))).finally(() => setIsLoadingEvents(false));
    } else {
      setStockData(null);
      setIsLoading(true);
      loadStockData();
    }
    return () => { if (wsClientRef.current) wsClientRef.current.disconnect(); };
  }, [ticker]);

  // If prefetch completes after mount, hydrate immediately instead of waiting for full fetch.
  useEffect(() => {
    if (!prefetchedData) return;
    if (!isLoading || stockData) return;
    setStockData(prefetchedData);
    setIsLoading(false);
    applyStockData(prefetchedData);
  }, [prefetchedData, isLoading, stockData, applyStockData]);

  useEffect(() => {
    if (!canAccessGuestPreviewContent || !hasSimilarStocks) {
      if (
        similarTickers ||
        Object.keys(similarTickerPages).length > 0 ||
        Object.keys(similarHasMoreByPage).length > 0 ||
        similarStocksPage !== 1 ||
        isLoadingSimilarTickers
      ) {
        setSimilarTickers(null);
        setSimilarTickerPages({});
        setSimilarHasMoreByPage({});
        setSimilarStocksPage(1);
        setIsLoadingSimilarTickers(false);
      }
      return;
    }

    if (isLoadingSimilarTickers) return;
    if (similarTickers || Object.keys(similarTickerPages).length > 0) return;
    void fetchSimilarTickersPage(1);
  }, [
    canAccessGuestPreviewContent,
    hasSimilarStocks,
    similarTickers,
    similarTickerPages,
    similarHasMoreByPage,
    similarStocksPage,
    isLoadingSimilarTickers,
    fetchSimilarTickersPage,
  ]);

  useEffect(() => {
    // Fallback polling mechanism:
    // 1. Always poll while generation is running so report progress updates in UI
    // 2. If WebSocket is healthy, poll less frequently as a safety net
    if (!ticker || !stockData?.is_generating) return;
    
    const hasWebSocket = wsClientRef.current?.isConnected() ?? false;
    const pollInterval = hasWebSocket ? 6000 : 3500; // 6s with WS, 3.5s without
    
    const interval = setInterval(() => {
      tickerApi.getTickerPage(ticker).then((data) => {
        setStockData(data);
        if (!viewingHistoricalRunRef.current && data.reports && Object.keys(data.reports).length > 0) {
          const keys = Object.keys(data.reports);
          setSelectedReport((prev) => {
            if (prev && prev !== OVERVIEW_TAB_KEY && keys.includes(prev)) return prev;
            return OVERVIEW_TAB_KEY;
          });
        }
        if (!data.is_generating) {
          setAnalysisProgress(null);
        }
      }).catch(() => {});
    }, pollInterval);
    return () => clearInterval(interval);
  }, [ticker, stockData?.is_generating, stockData?.generation_analysis_run_id]);

  useEffect(() => {
    if (activeTab !== 'fundamentals' || !ticker || financialStatements) return;
    const qt = companyInfo?.quoteType;
    if (qt !== 'EQUITY' && qt != null) return;
    if (!fundamentalsData && !isLoadingFundamentals) {
      setIsLoadingFundamentals(true);
      Promise.all([
        tickerApi.getFundamentals(ticker).catch(() => null),
        tickerApi.getFinancialStatements(ticker, 'all', 'quarterly').catch(() => null),
      ]).then(([fundamentals, st]) => {
        if (fundamentals) setFundamentalsData(fundamentals.fundamentals);
        if (st) setFinancialStatements(st.statements);
        setIsLoadingFundamentals(false);
      });
    } else {
      setIsLoadingFundamentals(true);
      tickerApi.getFinancialStatements(ticker, 'all', 'quarterly').then((r) => setFinancialStatements(r.statements)).catch(() => {}).finally(() => setIsLoadingFundamentals(false));
    }
  }, [activeTab, ticker, fundamentalsData, financialStatements, isLoadingFundamentals, companyInfo?.quoteType]);

  const fetchNews = useCallback(() => {
    if (!ticker) return;
    setNewsError(null); setIsLoadingNews(true);
    tickerApi.getNews(ticker).then((r) => { setNewsData(r.articles || []); setNewsError('error' in r ? r.error ?? null : null); setIsLoadingNews(false); })
      .catch((err) => { setNewsError(err.response?.data?.detail ?? err.message ?? 'Unable to fetch news.'); setNewsData([]); setIsLoadingNews(false); });
  }, [ticker]);

  const fetchInsiderTransactions = useCallback(() => {
    if (!ticker) return;
    const requestId = insiderFetchIdRef.current + 1;
    insiderFetchIdRef.current = requestId;
    setInsiderTransactionsError(null); setIsLoadingInsiderTransactions(true);
    tickerApi.getInsiderTransactions(ticker, 50)
      .then((r) => {
        if (insiderFetchIdRef.current !== requestId) return;
        setInsiderTransactions(r.transactions || []);
        setInsiderTransactionsError('error' in r ? r.error ?? null : null);
      })
      .catch((err) => {
        if (insiderFetchIdRef.current !== requestId) return;
        setInsiderTransactionsError(err.response?.data?.detail ?? err.message ?? 'Unable to fetch insider transactions.');
        setInsiderTransactions([]);
      })
      .finally(() => {
        if (insiderFetchIdRef.current !== requestId) return;
        setIsLoadingInsiderTransactions(false);
        setHasLoadedInsiderTransactions(true);
      });
  }, [ticker]);

  const fetchCompanyOfficers = useCallback(() => {
    if (!ticker) return;
    setIsLoadingOfficers(true);
    tickerApi.getCompanyOfficers(ticker)
      .then((r) => {
        setCompanyOfficers(r.officers || []);
        setHasLoadedCompanyOfficers(true);
      })
      .catch(() => {
        setCompanyOfficers([]);
        setHasLoadedCompanyOfficers(true);
      })
      .finally(() => setIsLoadingOfficers(false));
  }, [ticker]);

  const refreshSubscriptionForTicker = useCallback(async () => {
    if (!user || !ticker) { setSubscriptionForTicker(null); return; }
    try { const list = await subscriptionApi.list(); setSubscriptionForTicker(list.find((s) => s.ticker.toUpperCase() === ticker.toUpperCase()) ?? null); }
    catch { setSubscriptionForTicker(null); }
  }, [user, ticker]);

  useEffect(() => { refreshSubscriptionForTicker(); }, [refreshSubscriptionForTicker]);

  const handleEmailUpdatesToggle = useCallback(async (email_updates: boolean) => {
    if (!ticker) return;
    setEmailPreferenceToggling(true);
    try { const updated = await subscriptionApi.updateEmailPreference(ticker, email_updates); setSubscriptionForTicker(updated); }
    finally { setEmailPreferenceToggling(false); }
  }, [ticker]);

  // EXPERIMENTAL: load reports for a historical run
  const handleSelectHistoricalRun = useCallback(async (analysisRunId: number | null) => {
    if (analysisRunId == null) {
      setSelectedRunId(null);
      setHistoricalReportsData(null);
      // Reset to latest report tab (Overview by default)
      if (stockData?.reports && Object.keys(stockData.reports).length > 0) {
        setSelectedReport(OVERVIEW_TAB_KEY);
      }
      return;
    }
    setSelectedRunId(analysisRunId);
    setIsLoadingHistoricalRun(true);
    try {
      const data = await tickerApi.getHistoricalReports(ticker, analysisRunId);
      setHistoricalReportsData(data);
      const keys = Object.keys(data).sort((a, b) => {
        const ia = REPORT_PROCESS_ORDER.indexOf(a), ib = REPORT_PROCESS_ORDER.indexOf(b);
        if (ia === -1 && ib === -1) return a.localeCompare(b);
        if (ia === -1) return 1; if (ib === -1) return -1;
        return ia - ib;
      });
      setSelectedReport(keys.includes('final_trade_decision') ? 'final_trade_decision' : keys[0] ?? null);
    } catch {
      setHistoricalReportsData(null);
    } finally {
      setIsLoadingHistoricalRun(false);
    }
  }, [ticker, stockData]);
  // EXPERIMENTAL: close run selector on outside click (portal dropdown is in body, so check both refs)
  useEffect(() => {
    if (!runSelectorOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (runSelectorRef.current?.contains(target) || runDropdownRef.current?.contains(target)) return;
      setRunSelectorOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [runSelectorOpen]);

  // Position analysis-runs dropdown for portal (avoids clipping by scroll/tile below)
  useLayoutEffect(() => {
    if (!runSelectorOpen || !runSelectorRef.current) {
      setRunDropdownPosition(null);
      return;
    }
    const update = () => {
      if (!runSelectorRef.current) return;
      const rect = runSelectorRef.current.getBoundingClientRect();
      const width = 200;
      const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
      setRunDropdownPosition({
        top: rect.bottom + 4,
        left,
        width,
      });
    };
    update();
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [runSelectorOpen]);
  // END EXPERIMENTAL

  useEffect(() => { if (activeTab === 'news' && ticker && !isLoadingNews) fetchNews(); }, [activeTab, ticker, fetchNews]);
  useEffect(() => { if (activeTab === 'overview' && ticker && !hasLoadedCompanyOfficers && !isLoadingOfficers) fetchCompanyOfficers(); }, [activeTab, ticker, fetchCompanyOfficers, hasLoadedCompanyOfficers, isLoadingOfficers]);
  useEffect(() => {
    if (
      activeTab === 'insider-transactions'
      && hasInsiderTransactions
      && ticker
      && !hasLoadedInsiderTransactions
      && !isLoadingInsiderTransactions
    ) {
      fetchInsiderTransactions();
    }
  }, [activeTab, hasInsiderTransactions, ticker, fetchInsiderTransactions, hasLoadedInsiderTransactions, isLoadingInsiderTransactions]);

  useEffect(() => {
    if (activeTab !== 'sec-filings' || !ticker) return;
    let cancelled = false;
    setIsLoadingEdgar(true); setEdgarFilingsError(null);
    tickerApi.getEdgarFilings(ticker)
      .then((data) => { if (!cancelled) { setEdgarFilings(data); if (data.error) setEdgarFilingsError(data.error); } })
      .catch((err) => { if (!cancelled) { setEdgarFilingsError(err.response?.data?.detail ?? err.message ?? 'Unable to load SEC filings.'); setEdgarFilings(null); } })
      .finally(() => { if (!cancelled) setIsLoadingEdgar(false); });
    return () => { cancelled = true; };
  }, [activeTab, ticker]);

  const handleGenerateReport = async (source: 'fresh' | 'generate' = 'fresh') => {
    if (!ticker) return;
    setAnalysisError(null);
    if (!user) { setAuthModalMessage(source === 'generate' ? 'Please sign in to generate an analysis report.' : 'Please sign in to run a fresh analysis.'); setAuthModalOpen(true); return; }
    try {
      setIsStartingAnalysis(true);
      await tickerApi.startAnalysis(ticker);
      setAnalysisError(null);
      await loadStockData({ showGlobalLoading: false, refreshSupportingData: false });
    }
    catch (error: unknown) {
      setAnalysisError(getErrorMessage(error, 'Failed to start analysis. Please try again.'));
    } finally {
      setIsStartingAnalysis(false);
    }
  };

  const formatNumber = (value: number | null | undefined, decimals = 2): string => {
    if (value == null) return 'N/A';
    const absValue = Math.abs(value);
    const sign = value < 0 ? '-' : '';
    if (absValue >= 1e12) return `${sign}$${(absValue / 1e12).toFixed(decimals)}T`;
    if (absValue >= 1e9) return `${sign}$${(absValue / 1e9).toFixed(decimals)}B`;
    if (absValue >= 1e6) return `${sign}$${(absValue / 1e6).toFixed(decimals)}M`;
    if (absValue >= 1e3) return `${sign}$${(absValue / 1e3).toFixed(decimals)}K`;
    return `${sign}$${absValue.toFixed(decimals)}`;
  };
  const formatSignedPercent = (value: number | null | undefined): string => {
    if (value == null) return 'N/A';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };
  const formatRatio = (value: number | null | undefined): string => value == null ? 'N/A' : value.toFixed(2);
  const formatPercent = (value: number | null | undefined): string => value == null ? 'N/A' : `${(value * 100).toFixed(2)}%`;
  const knownTotalSimilarStockCount = typeof similarTickers?.total_count === 'number'
    ? similarTickers.total_count
    : null;
  const totalSimilarStockPages = knownTotalSimilarStockCount != null
    ? Math.max(1, Math.ceil(knownTotalSimilarStockCount / SIMILAR_STOCKS_PER_PAGE))
    : null;
  const currentSimilarStocksPage = totalSimilarStockPages != null
    ? Math.min(similarStocksPage, totalSimilarStockPages)
    : similarStocksPage;
  const visibleSimilarStocks = similarTickerPages[currentSimilarStocksPage] ?? [];
  const similarStartIndex = (currentSimilarStocksPage - 1) * SIMILAR_STOCKS_PER_PAGE;
  const similarEndIndex = similarStartIndex + SIMILAR_STOCKS_PER_PAGE;
  const currentPageHasMore = totalSimilarStockPages != null
    ? currentSimilarStocksPage < totalSimilarStockPages
    : (similarHasMoreByPage[currentSimilarStocksPage] ?? false);
  const canGoToNextSimilarStocksPage = Boolean(similarTickerPages[currentSimilarStocksPage + 1]) || currentPageHasMore;
  const canGoToPreviousSimilarStocksPage = currentSimilarStocksPage > 1;
  const shouldShowSimilarPaginationControls = canGoToPreviousSimilarStocksPage || canGoToNextSimilarStocksPage;

  const parseRecommendationPeriodOffset = (period: string): number => {
    const match = String(period).trim().match(/^-?\d+/);
    if (!match) return 0;
    const n = Number(match[0]);
    return Number.isFinite(n) ? n : 0;
  };

  const formatRecommendationPeriodLabel = (period: string): string => {
    const offset = parseRecommendationPeriodOffset(period);
    const d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() + offset);
    return d.toLocaleDateString(undefined, { month: 'short' });
  };

  const analystTrendRows: Array<{
    period: string;
    strongBuy: number;
    buy: number;
    hold: number;
    sell: number;
    strongSell: number;
    total: number;
  }> = Array.isArray(analystRecommendations?.recommendation_trend)
    ? analystRecommendations.recommendation_trend
      .map((row: any) => ({
        period: String(row?.period ?? ''),
        strongBuy: Number(row?.strongBuy ?? 0) || 0,
        buy: Number(row?.buy ?? 0) || 0,
        hold: Number(row?.hold ?? 0) || 0,
        sell: Number(row?.sell ?? 0) || 0,
        strongSell: Number(row?.strongSell ?? 0) || 0,
        total: Number(row?.total ?? (
          Number(row?.strongBuy ?? 0) +
          Number(row?.buy ?? 0) +
          Number(row?.hold ?? 0) +
          Number(row?.sell ?? 0) +
          Number(row?.strongSell ?? 0)
        )) || 0,
      }))
      .filter((row: { period: string }) => row.period.length > 0)
    : [];
  const analystTrendRowsSorted = [...analystTrendRows].sort(
    (a, b) => parseRecommendationPeriodOffset(a.period) - parseRecommendationPeriodOffset(b.period),
  );
  const analystPriceTargets = (analystRecommendations?.price_targets && typeof analystRecommendations.price_targets === 'object')
    ? analystRecommendations.price_targets
    : {};
  const analystFinancialData = (analystRecommendations?.financial_data && typeof analystRecommendations.financial_data === 'object')
    ? analystRecommendations.financial_data
    : {};
  const analystPriceCurrent = Number(analystFinancialData.currentPrice ?? analystPriceTargets.current ?? Number.NaN);
  const analystPriceAverage = Number(
    analystFinancialData.targetMeanPrice
      ?? analystPriceTargets.average
      ?? analystRecommendations?.target_price
      ?? Number.NaN,
  );
  const analystPriceLow = Number(analystFinancialData.targetLowPrice ?? analystPriceTargets.low ?? Number.NaN);
  const analystPriceHigh = Number(analystFinancialData.targetHighPrice ?? analystPriceTargets.high ?? Number.NaN);
  const analystHasPriceCurrent = Number.isFinite(analystPriceCurrent);
  const analystHasPriceAverage = Number.isFinite(analystPriceAverage);
  const analystHasPriceLow = Number.isFinite(analystPriceLow);
  const analystHasPriceHigh = Number.isFinite(analystPriceHigh);
  const analystPriceValues = [analystPriceLow, analystPriceCurrent, analystPriceAverage, analystPriceHigh]
    .filter((n) => Number.isFinite(n));
  const analystHasAnyTargets = analystPriceValues.length > 0;
  const analystBreakdownHasCounts = (analystRecommendations?.breakdown && typeof analystRecommendations.breakdown === 'object')
    ? Object.values(analystRecommendations.breakdown).some((v) => Number(v) > 0)
    : false;
  const analystHasData = Boolean(
    Number(analystRecommendations?.total_analysts ?? 0) > 0 ||
    analystBreakdownHasCounts ||
    analystTrendRowsSorted.length > 0 ||
    analystHasPriceLow ||
    analystHasPriceAverage ||
    analystHasPriceHigh,
  );
  const analystBreakdownFallback = {
    period: '0m',
    strongBuy: Number(analystRecommendations?.breakdown?.['Strong Buy'] ?? 0) || 0,
    buy: Number(analystRecommendations?.breakdown?.Buy ?? 0) || 0,
    hold: Number(analystRecommendations?.breakdown?.Hold ?? 0) || 0,
    sell: Number(analystRecommendations?.breakdown?.Sell ?? 0) || 0,
    strongSell: Number(analystRecommendations?.breakdown?.['Strong Sell'] ?? 0) || 0,
    total: Number(analystRecommendations?.total_analysts ?? 0) || 0,
  };
  const analystTrendDisplayRows = analystTrendRowsSorted.length > 0
    ? analystTrendRowsSorted
    : analystBreakdownFallback.total > 0
      ? [analystBreakdownFallback]
      : [];
  const analystTrendSeries = [
    { key: 'strongBuy', label: 'Strong Buy', colorClass: 'bg-emerald-600' },
    { key: 'buy', label: 'Buy', colorClass: 'bg-lime-500' },
    { key: 'hold', label: 'Hold', colorClass: 'bg-yellow-400' },
    { key: 'sell', label: 'Sell', colorClass: 'bg-orange-500' },
    { key: 'strongSell', label: 'Strong Sell', colorClass: 'bg-red-600' },
  ] as const;
  const analystTrendMaxValue = analystTrendDisplayRows.reduce((max, row) => {
    const rowMax = analystTrendSeries.reduce(
      (innerMax, series) => Math.max(innerMax, Number(row[series.key]) || 0),
      0,
    );
    return Math.max(max, rowMax);
  }, 0);

  const handleNextSimilarStocksPage = async () => {
    if (!canGoToNextSimilarStocksPage || isLoadingSimilarTickers) return;
    const nextPage = currentSimilarStocksPage + 1;
    if (similarTickerPages[nextPage]) {
      setSimilarStocksPage(nextPage);
      return;
    }

    const fetched = await fetchSimilarTickersPage(nextPage);
    if (fetched) setSimilarStocksPage(nextPage);
  };

  if (isLoading) return (
    <div className="flex-1 min-h-0 overflow-y-auto p-6">
      <div className="animate-pulse space-y-4">
        <div className="h-10 bg-gray-700 rounded w-64" /><div className="h-6 bg-gray-700 rounded w-40" />
        <div className="h-64 bg-gray-700 rounded" /><div className="h-48 bg-gray-700 rounded" />
      </div>
    </div>
  );

  if (!stockData) return (
    <div className="flex-1 min-h-0 overflow-y-auto p-6 flex items-center justify-center">
      <div className="bg-gray-800 rounded-lg border border-amber-500/30 p-10 text-center max-w-md">
        <div className="text-4xl mb-3 opacity-80" aria-hidden>⚠</div>
        <h2 className="text-xl font-bold text-white mb-2">Ticker not found</h2>
        <p className="text-gray-300 mb-1 font-mono">{ticker}</p>
        <p className="text-gray-400 text-sm">{loadError ?? `No stock data for "${ticker}".`}</p>
      </div>
    </div>
  );

  // EXPERIMENTAL: when a historical run is selected, use its data instead of the latest
  const activeReportsSource = (selectedRunId && historicalReportsData) ? historicalReportsData : stockData.reports_with_scores;
  const activeReportsRaw = (selectedRunId && historicalReportsData)
    ? Object.fromEntries(Object.entries(historicalReportsData).map(([k, v]) => [k, v.content ?? '']))
    : stockData.reports;
  // END EXPERIMENTAL

  const allReports = Object.keys(activeReportsRaw || {});
  const availableReports = [...allReports].sort((a, b) => {
    const idxA = REPORT_PROCESS_ORDER.indexOf(a), idxB = REPORT_PROCESS_ORDER.indexOf(b);
    if (idxA === -1 && idxB === -1) return a.localeCompare(b);
    if (idxA === -1) return 1; if (idxB === -1) return -1;
    return idxA - idxB;
  });
  const currentReportData = selectedReport && activeReportsSource ? activeReportsSource[selectedReport] : null;
  const currentReportContent = currentReportData?.content || (selectedReport ? activeReportsRaw?.[selectedReport] : null);
  const currentReportScore = currentReportData?.score;
  const currentReportScoreLabel = currentReportData?.score_label;
  const reportScores: Record<string, { score: number | null; score_label: string | null }> = {};
  if (activeReportsSource) Object.entries(activeReportsSource).forEach(([k, v]) => { reportScores[k] = { score: v.score, score_label: v.score_label }; });
  const activeRecommendation = selectedRunId != null && stockData.historical_analyses
    ? stockData.historical_analyses.find((x) => x.analysis_run_id === selectedRunId)?.recommendation ?? null
    : stockData.recommendation?.recommendation ?? null;
  const modelsUsed = activeReportsSource ? (Object.values(activeReportsSource).find((r) => r.models_used)?.models_used ?? null) : null;
  const quote = refreshedQuote ?? stockData.quote;
  const lastUpdateTime = quote?.last_update_time ? new Date(quote.last_update_time).toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }) : '';

// Made with Bob

  return (
    <>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-4 sm:p-6 space-y-4">

          {/* Header - overflow-visible so the analysis runs dropdown is not clipped by the tile below */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-visible">
            <div className="px-4 sm:px-6 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <h2 className="text-lg sm:text-xl font-semibold text-white break-words">
                  {companyInfo?.name || stockData.ticker}{' '}
                  <span className="text-gray-400 font-normal text-base">({stockData.ticker})</span>
                </h2>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <SubscribeButton
                    ticker={ticker}
                    onSubscribed={() => { refreshSubscriptionForTicker(); onSubscriptionChange?.(); }}
                    onUnsubscribed={() => { setSubscriptionForTicker(null); onSubscriptionChange?.(); }}
                  />
                  {subscriptionForTicker && (
                    <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400">
                      <span>Email updates</span>
                      <input type="checkbox" checked={subscriptionForTicker.email_updates} disabled={emailPreferenceToggling}
                        onChange={(e) => handleEmailUpdatesToggle(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800" />
                    </label>
                  )}
                </div>
              </div>
              {quote && (
                <>
                  <div className="flex flex-wrap items-baseline gap-2 mt-2">
                    <div className={`inline-block px-2 py-0.5 rounded text-2xl sm:text-3xl font-bold text-white ${priceFlash ? 'animate-price-flash' : ''}`}>
                      {formatPrice(quote.current_price, quote.currency)}
                    </div>
                    <div className={`text-base sm:text-lg font-semibold flex items-center gap-1 ${quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      <span>{quote.daily_change_percent >= 0 ? '▲' : '▼'}</span>
                      <span>({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%) {quote.daily_change >= 0 ? '+' : ''}{formatPrice(quote.daily_change, quote.currency)}</span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">Price as of {lastUpdateTime}</div>
                </>
              )}
            </div>
            {/* Tabs */}
            <div className="border-t border-gray-700">
              <nav className="flex flex-wrap gap-0.5 px-2 pt-1" aria-label="Stock sections">
                {[
                  { id: 'overview', label: 'Overview' },
                  ...(hasFundamentals ? [{ id: 'fundamentals', label: 'Fundamentals' }] : []),
                  ...(isUSCompany ? [{ id: 'sec-filings', label: 'SEC Filings' }] : []),
                  ...(hasInsiderTransactions ? [{ id: 'insider-transactions', label: 'Insider Transactions' }] : []),
                  { id: 'news', label: 'News' },
                  { id: 'events', label: 'Events' },
                  ...(hasSimilarStocks ? [{ id: 'similar-stocks', label: 'Similar Stocks' }] : []),
                  { id: 'ai-analysis', label: 'AI Analysis' },
                ].map((tab) => {
                  const isActive = activeTab === tab.id;
                  const isBlueTab = tab.id === 'ai-analysis';
                  const isSimilarStocksTab = tab.id === 'similar-stocks';
                  const isPlatformDataTab = tab.id === 'events';
                  return (
                    <button key={tab.id} onClick={() => handleMainTabChange(tab.id as MainTabId)}
                      className={`px-3 py-2 text-sm rounded-t-lg transition-colors border-b-2 -mb-px ${
                        isActive
                          ? isBlueTab
                            ? 'bg-indigo-950/70 text-indigo-200 border-indigo-500 font-semibold'
                            : isSimilarStocksTab
                              ? 'bg-blue-950/70 text-blue-200 border-blue-500 font-semibold'
                            : isPlatformDataTab
                              ? 'bg-sky-950/70 text-sky-200 border-sky-500 font-semibold'
                              : 'bg-gray-800 text-white border-blue-500 font-medium'
                          : isBlueTab
                            ? 'bg-indigo-950/40 text-indigo-200 hover:text-white hover:bg-indigo-950/60 border-indigo-700/50 font-semibold'
                            : isSimilarStocksTab
                              ? 'bg-blue-950/40 text-blue-200 hover:text-white hover:bg-blue-950/60 border-blue-700/50 font-semibold'
                            : isPlatformDataTab
                              ? 'bg-sky-950/30 text-sky-200 hover:text-white hover:bg-sky-950/50 border-sky-700/50 font-semibold'
                              : 'text-gray-400 hover:text-white hover:bg-gray-800/70 border-transparent font-medium'
                      }`}>
                      <span className="inline-flex items-center gap-1.5">
                        {tab.id === 'events' && (
                          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 18h16M7 15l3-3 3 2 4-5" />
                            <circle cx="7" cy="15" r="1.2" fill="currentColor" stroke="none" />
                            <circle cx="10" cy="12" r="1.2" fill="currentColor" stroke="none" />
                            <circle cx="13" cy="14" r="1.2" fill="currentColor" stroke="none" />
                            <circle cx="17" cy="9" r="1.2" fill="currentColor" stroke="none" />
                          </svg>
                        )}
                        {tab.id === 'similar-stocks' && (
                          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7h8M8 12h8M8 17h5" />
                            <circle cx="6" cy="7" r="1.2" fill="currentColor" stroke="none" />
                            <circle cx="18" cy="12" r="1.2" fill="currentColor" stroke="none" />
                            <circle cx="6" cy="17" r="1.2" fill="currentColor" stroke="none" />
                          </svg>
                        )}
                        {tab.id === 'ai-analysis' && (
                          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <rect x="7" y="7" width="10" height="10" rx="2" strokeWidth={1.8} />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 10h4v4h-4zM9 3v2m3-2v2m3-2v2M9 19v2m3-2v2m3-2v2M3 9h2m-2 3h2m-2 3h2M19 9h2m-2 3h2m-2 3h2" />
                          </svg>
                        )}
                        {tab.label}
                      </span>
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>

          {/* Fundamentals Tab */}
          {activeTab === 'fundamentals' && (
            <div className="space-y-4">
              <div className="flex gap-2 border-b border-gray-700 pb-3">
                <button type="button" onClick={() => handleFundamentalsSubTabChange('charts')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${fundamentalsSubTab === 'charts' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>Charts</button>
                <button type="button" onClick={() => handleFundamentalsSubTabChange('statements')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${fundamentalsSubTab === 'statements' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>Financial Statements</button>
              </div>
              {fundamentalsSubTab === 'charts' && (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6"><FundamentalCharts ticker={ticker} /></div>
              )}
              {fundamentalsSubTab === 'statements' && (
                isLoadingFundamentals ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 animate-pulse"><div className="h-6 bg-gray-700 rounded w-48 mb-4" /><div className="h-64 bg-gray-700 rounded" /></div>
                ) : financialStatements ? (
                  <div className="space-y-4">
                    {financialStatements.cashflow && <FinancialStatementViewer data={financialStatements.cashflow} statementType="cashflow" />}
                    {financialStatements.balance_sheet && <FinancialStatementViewer data={financialStatements.balance_sheet} statementType="balance_sheet" />}
                    {financialStatements.income_statement && <FinancialStatementViewer data={financialStatements.income_statement} statementType="income_statement" />}
                  </div>
                ) : (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6"><div className="text-gray-400 text-sm">No financial statements available</div></div>
                )
              )}
            </div>
          )}

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-4">
              <div className="flex flex-col lg:flex-row gap-4 items-stretch">
                <div className="lg:w-72 shrink-0">
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 h-full">
                    <h3 className="text-sm font-semibold text-white mb-3">Key Data Points</h3>
                    <div className="space-y-2">
                      {quote && (() => {
                        const fmt = (n: number) => formatPrice(n, quote.currency);
                        return (<>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Current Price</span><span className="text-xs font-semibold text-white">{fmt(quote.current_price)}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Daily Change</span>
                          <span className={`text-xs font-semibold ${quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%) {quote.daily_change >= 0 ? '+' : ''}{fmt(quote.daily_change)}
                          </span>
                        </div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Day's Range</span><span className="text-xs font-semibold text-white">{quote.day_low != null && quote.day_high != null ? `${fmt(quote.day_low)} – ${fmt(quote.day_high)}` : 'N/A'}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Prev Close</span><span className="text-xs font-semibold text-white">{quote.previous_close != null ? fmt(quote.previous_close) : 'N/A'}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Bid</span><span className="text-xs font-semibold text-white">{quote.bid_price != null ? fmt(quote.bid_price) : 'N/A'}{quote.bid_size != null ? ` ×${quote.bid_size}` : ''}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Ask</span><span className="text-xs font-semibold text-white">{quote.ask_price != null ? fmt(quote.ask_price) : 'N/A'}{quote.ask_size != null ? ` ×${quote.ask_size}` : ''}</span></div>
                        {hasFundamentals && <div className="flex justify-between"><span className="text-xs text-gray-400">Beta</span><span className="text-xs font-semibold text-white">{extendedInfo?.beta?.toFixed(2) || 'N/A'}</span></div>}
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Volume</span><span className="text-xs font-semibold text-white">{quote.volume ? quote.volume.toLocaleString() : 'N/A'}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Avg Volume</span><span className="text-xs font-semibold text-white">{extendedInfo?.average_volume ? extendedInfo.average_volume.toLocaleString() : 'N/A'}</span></div>
                        {hasFundamentals && <div className="flex justify-between"><span className="text-xs text-gray-400">Sector</span><span className="text-xs font-semibold text-white truncate max-w-[140px]">{companyInfo?.sector || 'N/A'}</span></div>}
                        {hasFundamentals && <div className="flex justify-between"><span className="text-xs text-gray-400">Market Cap</span><span className="text-xs font-semibold text-white">{formatNumber(extendedInfo?.market_cap)}</span></div>}
                        <div className="flex justify-between"><span className="text-xs text-gray-400">52wk Range</span><span className="text-xs font-semibold text-white">{quote.fifty_two_week_low != null && quote.fifty_two_week_high != null ? `${fmt(quote.fifty_two_week_low)} – ${fmt(quote.fifty_two_week_high)}` : 'N/A'}</span></div>
                        {hasFundamentals && <>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">Revenue</span><span className="text-xs font-semibold text-white">{formatNumber(extendedInfo?.revenue)}</span></div>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">Gross Margin</span><span className="text-xs font-semibold text-white">{formatPercent(extendedInfo?.gross_margin)}</span></div>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">Dividend Yield</span><span className="text-xs font-semibold text-white">{formatPercent(extendedInfo?.dividend_yield)}</span></div>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">EPS</span><span className="text-xs font-semibold text-white">{extendedInfo?.trailing_eps?.toFixed(2) || 'N/A'}</span></div>
                        </>}
                        </>);
                      })()}
                    </div>
                  </div>
                </div>
                <div className="flex-1 min-w-0 min-h-[260px] flex flex-col">
                  {quote && <div className="flex-1 min-h-0 flex flex-col"><PriceTrendWidget ticker={stockData.ticker} fillTile /></div>}
                </div>
              </div>

              {/* Future Events */}
              {isLoadingFutureEvents ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse"><div className="h-5 bg-gray-700 rounded w-40 mb-3" /><div className="h-20 bg-gray-700 rounded" /></div>
              ) : futureEvents && (futureEvents.events?.length ?? 0) > 0 ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <h3 className="text-sm font-semibold text-white mb-3">Upcoming Events</h3>
                  <ul className="space-y-2">
                    {futureEvents.events.map((evt: any, i: number) => (
                      <li key={`${evt.date}-${evt.type}-${i}`} className="flex items-center justify-between py-1.5 border-b border-gray-700 last:border-0">
                        <div className="flex items-center gap-2">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${evt.type === 'earnings' ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                            {evt.type === 'earnings' ? 'Earnings' : 'Ex-dividend'}
                          </span>
                          <span className="text-gray-300 text-sm">{evt.label}</span>
                        </div>
                        <span className="text-white text-sm font-medium">{new Date(evt.date).toLocaleDateString(undefined, { dateStyle: 'medium' })}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {/* Analyst Recommendations*/}
              {isLoadingRecommendations ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="animate-pulse">
                    <div className="h-6 bg-gray-700 rounded w-56 mb-4" />
                    <div className="h-28 bg-gray-700 rounded" />
                  </div>
                </div>
              ) : analystRecommendations && analystHasData ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 sm:p-6">
                    <h3 className="text-sm sm:text-base font-semibold text-white mb-3 sm:mb-4">Analyst Recommendations</h3>
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-5 sm:gap-6">
                      <div className="rounded-lg border border-gray-700 bg-gray-900/20 p-4 md:col-span-4 lg:col-span-3">
                        <h4 className="text-lg font-semibold text-white mb-4">Price Targets</h4>
                        <>
                          <div className="space-y-2">
                            <div className="rounded border border-gray-700 bg-gray-800/60 px-3 py-2 flex items-center justify-between gap-3">
                              <div className="text-sm text-gray-400">Current</div>
                              <div className="text-sm font-semibold text-white">
                                {analystHasPriceCurrent ? `$${analystPriceCurrent.toFixed(2)}` : 'N/A'}
                              </div>
                            </div>
                            <div className="rounded border border-gray-700 bg-gray-800/60 px-3 py-2 flex items-center justify-between gap-3">
                              <div className="text-sm text-gray-400">Target Low</div>
                              <div className="text-sm font-semibold text-white">
                                {analystHasPriceLow ? `$${analystPriceLow.toFixed(2)}` : 'N/A'}
                              </div>
                            </div>
                            <div className="rounded border border-gray-700 bg-gray-800/60 px-3 py-2 flex items-center justify-between gap-3">
                              <div className="text-sm text-gray-400">Target Mean</div>
                              <div className="text-sm font-semibold text-white">
                                {analystHasPriceAverage ? `$${analystPriceAverage.toFixed(2)}` : 'N/A'}
                              </div>
                            </div>
                            <div className="rounded border border-gray-700 bg-gray-800/60 px-3 py-2 flex items-center justify-between gap-3">
                              <div className="text-sm text-gray-400">Target High</div>
                              <div className="text-sm font-semibold text-white">
                                {analystHasPriceHigh ? `$${analystPriceHigh.toFixed(2)}` : 'N/A'}
                              </div>
                            </div>
                            <div className="rounded border border-gray-700 bg-gray-800/60 px-3 py-2 flex items-center justify-between gap-3">
                              <div className="text-sm text-gray-400">Total Analysts</div>
                              <div className="text-sm font-semibold text-white">
                                {analystRecommendations.total_analysts ?? 0}
                              </div>
                            </div>
                          </div>
                          {!analystHasAnyTargets && (
                            <p className="text-xs text-gray-400 mt-2">
                              No analyst price targets returned in YahooQuery financial_data for this ticker.
                            </p>
                          )}
                          {analystRecommendations.latest_date && (
                            <div className="text-xs text-gray-500 mt-2">
                              Updated: {new Date(analystRecommendations.latest_date).toLocaleDateString()}
                            </div>
                          )}
                        </>
                      </div>

                      <div className="rounded-lg border border-gray-700 bg-gray-900/20 p-4 md:col-span-8 lg:col-span-9">
                        <h4 className="text-lg font-semibold text-white mb-4">Recommendations</h4>
                        {analystTrendDisplayRows.length > 0 ? (
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                            {analystTrendDisplayRows.map((row) => (
                              <div key={row.period} className="rounded border border-gray-700 bg-gray-800/40 p-2.5">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-sm font-semibold text-white">{formatRecommendationPeriodLabel(row.period)}</span>
                                  <span className="text-xs text-gray-300">Total {Number(row.total) || 0}</span>
                                </div>
                                <div className="space-y-1.5">
                                  {analystTrendSeries.map((series) => {
                                    const value = Number(row[series.key]) || 0;
                                    const widthPct = analystTrendMaxValue > 0 ? (value / analystTrendMaxValue) * 100 : 0;
                                    return (
                                      <div key={`${row.period}-${series.key}`} className="space-y-0.5">
                                        <div className="flex items-center justify-between text-[11px] text-gray-300">
                                          <span>{series.label}</span>
                                          <span>{value}</span>
                                        </div>
                                        <div className="h-2.5 rounded bg-gray-700/80 overflow-hidden">
                                          <div
                                            className={`h-full ${series.colorClass}`}
                                            style={{ width: `${widthPct}%` }}
                                            title={`${series.label}: ${value}`}
                                          />
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-sm text-gray-400">No monthly recommendation history available.</div>
                        )}
                        <div className="mt-3 pt-2 border-t border-gray-700 flex items-center justify-between">
                          <span className="text-sm font-semibold text-gray-300">Current Recommendation</span>
                          <span className={`text-sm font-bold ${
                            analystRecommendations.recommendation === 'BUY'
                              ? 'text-green-400'
                              : analystRecommendations.recommendation === 'SELL'
                                ? 'text-red-400'
                                : analystRecommendations.recommendation === 'HOLD'
                                  ? 'text-yellow-300'
                                  : 'text-gray-300'
                          }`}>
                            {analystRecommendations.recommendation || 'N/A'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
              ) : null}

              {/* Fundamentals summary */}
              {quoteType === 'ETF' ? (
                isLoadingFundInfo ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse"><div className="h-5 bg-gray-700 rounded w-48 mb-3" /><div className="h-48 bg-gray-700 rounded" /></div>
                ) : fundInfo ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 space-y-4">
                    <h3 className="text-sm font-semibold text-white">ETF / Fund details</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                      {fundInfo.totalAssets != null && <div><p className="text-xs text-gray-400 mb-0.5">AUM</p><p className="text-white text-sm font-semibold">{formatNumber(fundInfo.totalAssets)}</p></div>}
                      {fundInfo.expenseRatio != null && <div><p className="text-xs text-gray-400 mb-0.5">Expense ratio</p><p className="text-white text-sm font-semibold">{formatPercent(fundInfo.expenseRatio)}</p></div>}
                      {fundInfo.category && <div><p className="text-xs text-gray-400 mb-0.5">Category</p><p className="text-white text-sm font-semibold">{fundInfo.category}</p></div>}
                      {fundInfo.yield != null && <div><p className="text-xs text-gray-400 mb-0.5">Yield</p><p className="text-white text-sm font-semibold">{formatPercent(fundInfo.yield)}</p></div>}
                    </div>
                    {fundInfo.description && <p className="text-gray-300 text-sm leading-relaxed">{fundInfo.description}</p>}
                    {fundInfo.sector_weightings && Object.keys(fundInfo.sector_weightings).length > 0 && (
                      <div>
                        <p className="text-xs text-gray-400 mb-2">Sector weightings</p>
                        <div className="space-y-1">
                          {Object.entries(fundInfo.sector_weightings).map(([name, pct]: [string, any]) => (
                            <div key={name} className="flex items-center gap-2">
                              <span className="text-gray-300 text-xs w-36 truncate">{name}</span>
                              <div className="flex-1 h-1.5 bg-gray-700 rounded overflow-hidden"><div className="h-full bg-blue-500 rounded" style={{ width: `${Math.min(100, Math.max(0, Number(pct) * 100))}%` }} /></div>
                              <span className="text-white text-xs font-medium w-10 text-right">{(Number(pct) * 100).toFixed(1)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {fundInfo.top_holdings && fundInfo.top_holdings.length > 0 && (
                      <div>
                        <p className="text-xs text-gray-400 mb-2">Top holdings</p>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead><tr className="text-left text-gray-400 border-b border-gray-600">{Object.keys(fundInfo.top_holdings[0]).map((k: string) => <th key={k} className="py-1.5 pr-3 capitalize">{k.replace(/_/g, ' ')}</th>)}</tr></thead>
                            <tbody>{fundInfo.top_holdings.slice(0, 10).map((row: any, i: number) => <tr key={i} className="border-b border-gray-700/50">{Object.values(row).map((v: any, j: number) => <td key={j} className="py-1.5 pr-3 text-white">{String(v ?? '—')}</td>)}</tr>)}</tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null
              ) : !hasFundamentals ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4"><p className="text-gray-400 text-sm">Fundamental data is available for equities only.</p></div>
              ) : isLoadingFundamentals ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse"><div className="h-5 bg-gray-700 rounded w-48 mb-3" /><div className="h-48 bg-gray-700 rounded" /></div>
              ) : fundamentalsData && typeof fundamentalsData === 'object' ? (
                <FundamentalPanes
                  data={fundamentalsData}
                  companyOfficers={companyOfficers}
                  isLoadingOfficers={isLoadingOfficers}
                />
              ) : null}
            </div>
          )}

          {/* Events Tab */}
          {activeTab === 'events' && (
            <EventsPanel
              ticker={ticker}
              eventScore={eventsData?.event_score ?? 0}
              events={eventsData?.events ?? []}
              dominantEvents={eventsData?.dominant_events ?? []}
              isLoading={isLoadingEvents}
              error={eventsError}
            />
          )}

          {/* Similar Stocks Tab */}
          {activeTab === 'similar-stocks' && hasSimilarStocks && (
            !canAccessGuestPreviewContent ? (
              <div className="flex flex-col items-center justify-center py-16 rounded-lg border border-gray-700 bg-gray-800/60">
                <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <h3 className="text-lg font-semibold text-white mb-2">Sign in to view Similar Stocks</h3>
                <p className="text-gray-400 text-sm mb-5 text-center max-w-xs">Create a free account to access similar stocks and peer comparisons.</p>
                <button
                  onClick={() => { setAuthModalMessage('Sign in to access similar stocks.'); setAuthModalOpen(true); }}
                  className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
                >
                  Sign In / Register
                </button>
              </div>
            ) : (
            <div className="space-y-4">
              {isLoadingSimilarTickers && visibleSimilarStocks.length === 0 ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 text-blue-400 animate-spin mt-0.5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <div>
                      <p className="text-sm font-semibold text-white">Loading Similar Stocks</p>
                      <p className="text-xs text-gray-400 mt-1">Fetching peer companies and market metrics...</p>
                    </div>
                  </div>
                  <div className="mt-4 h-1.5 w-full rounded bg-gray-700 overflow-hidden">
                    <div className="h-full w-1/3 bg-blue-500 animate-pulse rounded" />
                  </div>
                </div>
              ) : similarTickers && visibleSimilarStocks.length > 0 ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-white">
                      Similar Stocks {similarTickers.sector && `in ${similarTickers.sector}`}
                    </h3>
                    <span className="text-xs text-gray-400">
                      {similarTickers.match_type === 'sector_and_industry' ? 'Same sector & industry' :
                       similarTickers.match_type === 'sector_only' ? 'Same sector' :
                       similarTickers.match_type === 'industry_only' ? 'Same industry' : 'Related'}
                    </span>
                  </div>
                  <div className="relative">
                    <div className="overflow-x-auto rounded-lg border border-gray-700">
                      <table className="min-w-[1350px] w-full text-xs">
                        <thead className="bg-gray-900/70">
                          <tr className="text-left text-gray-300">
                            <th className="px-3 py-2">Ticker</th>
                            <th className="px-3 py-2">Name</th>
                            <th className="px-3 py-2">Price</th>
                            <th className="px-3 py-2">Change %</th>
                            <th className="px-3 py-2">Market Cap</th>
                            <th className="px-3 py-2">Revenue</th>
                            <th className="px-3 py-2">EBITDA</th>
                            <th className="px-3 py-2">P/E (TTM)</th>
                            <th className="px-3 py-2">EPS (TTM)</th>
                            <th className="px-3 py-2">Profit Margin</th>
                            <th className="px-3 py-2">Beta</th>
                            <th className="px-3 py-2">Dividend Yield</th>
                            <th className="px-3 py-2">52W Range</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleSimilarStocks.map((similar) => (
                            <tr
                              key={similar.ticker}
                              onClick={() => navigate(`/tickers/${similar.ticker}`)}
                              className="border-t border-gray-700/80 hover:bg-gray-700/30 cursor-pointer"
                            >
                              <td className="px-3 py-2 text-blue-300 font-semibold">{similar.ticker}</td>
                              <td className="px-3 py-2 text-white max-w-[220px] truncate" title={similar.name}>{similar.name}</td>
                              <td className="px-3 py-2 text-white">{formatNumber(similar.current_price, 2)}</td>
                              <td className={`px-3 py-2 ${similar.change_percent == null ? 'text-gray-400' : similar.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {formatSignedPercent(similar.change_percent)}
                              </td>
                              <td className="px-3 py-2 text-gray-200">{formatNumber(similar.market_cap, 2)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatNumber(similar.revenue, 2)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatNumber(similar.ebitda, 2)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatRatio(similar.trailing_pe)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatRatio(similar.trailing_eps)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatPercent(similar.profit_margin)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatRatio(similar.beta)}</td>
                              <td className="px-3 py-2 text-gray-200">{formatPercent(similar.dividend_yield)}</td>
                              <td className="px-3 py-2 text-gray-200">
                                {similar.fifty_two_week_low != null || similar.fifty_two_week_high != null
                                  ? `${formatNumber(similar.fifty_two_week_low, 2)} - ${formatNumber(similar.fifty_two_week_high, 2)}`
                                  : 'N/A'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {isLoadingSimilarTickers && visibleSimilarStocks.length > 0 && (
                      <div className="absolute inset-0 rounded-lg bg-gray-900/70 backdrop-blur-[1px] flex items-center justify-center">
                        <div className="flex items-center gap-2 px-3 py-2 rounded border border-gray-600 bg-gray-800/90">
                          <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                          </svg>
                          <span className="text-xs text-gray-200 font-medium">Loading next page...</span>
                        </div>
                      </div>
                    )}
                  </div>
                  {shouldShowSimilarPaginationControls && (
                    <div className="pt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                      <p className="text-gray-500 text-xs text-center sm:text-left">
                        {knownTotalSimilarStockCount != null
                          ? `Showing ${similarStartIndex + 1}-${Math.min(similarEndIndex, knownTotalSimilarStockCount)} of ${knownTotalSimilarStockCount} similar stocks`
                          : `Showing ${similarStartIndex + 1}-${similarStartIndex + visibleSimilarStocks.length} similar stocks`
                        }
                      </p>
                      <div className="flex items-center justify-center sm:justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setSimilarStocksPage(Math.max(1, currentSimilarStocksPage - 1))}
                          disabled={!canGoToPreviousSimilarStocksPage || isLoadingSimilarTickers}
                          className="px-3 py-1 text-xs rounded border border-gray-600 text-gray-300 disabled:opacity-40 disabled:cursor-default hover:bg-gray-700 transition-colors"
                        >
                          Previous
                        </button>
                        <span className="text-xs text-gray-400">
                          {totalSimilarStockPages != null
                            ? `Page ${currentSimilarStocksPage} of ${totalSimilarStockPages}`
                            : `Page ${currentSimilarStocksPage}`
                          }
                        </span>
                        <button
                          type="button"
                          onClick={() => { void handleNextSimilarStocksPage(); }}
                          disabled={!canGoToNextSimilarStocksPage || isLoadingSimilarTickers}
                          className="px-3 py-1 text-xs rounded border border-gray-600 text-gray-300 disabled:opacity-40 disabled:cursor-default hover:bg-gray-700 transition-colors"
                        >
                          {isLoadingSimilarTickers ? 'Loading...' : 'Next'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : similarTickers && similarTickers.message ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <h3 className="text-sm font-semibold text-white mb-2">Similar Stocks</h3>
                  <p className="text-gray-400 text-sm">{similarTickers.message}</p>
                </div>
              ) : (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                  <h3 className="text-sm font-semibold text-white mb-2">Similar Stocks</h3>
                  <p className="text-gray-400 text-sm">No similar stocks found.</p>
                </div>
              )}
            </div>
            )
          )}

          {/* AI Analysis Tab */}
          {activeTab === 'ai-analysis' && (
            <div className="space-y-4">
              {!canAccessGuestPreviewContent ? (
                <div className="flex flex-col items-center justify-center py-16 rounded-lg border border-gray-700 bg-gray-800/60">
                  <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <h3 className="text-lg font-semibold text-white mb-2">Sign in to view AI Analysis</h3>
                  <p className="text-gray-400 text-sm mb-5 text-center max-w-xs">Create a free account to access AI-powered stock analysis reports.</p>
                  <button onClick={() => { setAuthModalMessage('Sign in to access AI analysis reports.'); setAuthModalOpen(true); }}
                    className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors">Sign In / Register</button>
                </div>
              ) : (
                <>
                  {analysisError && (
                    <div className="flex items-center gap-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-red-200" role="alert">
                      <svg className="h-5 w-5 shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <span>{analysisError}</span>
                      <button type="button" onClick={() => setAnalysisError(null)} className="ml-auto rounded p-1 text-red-300 hover:bg-red-900/50" aria-label="Dismiss">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  )}
                  {stockData.has_reports && (stockData.report_date || selectedRunId != null) && (() => {
                    const summaryScoreEntries = getAnalysisScoreEntries(activeReportsSource ?? null);
                    const activeConfidence = selectedRunId ? null : stockData.recommendation?.confidence ?? null;
                    const planReport = activeReportsSource?.investment_plan;
                    const activeExpected = selectedRunId ? (planReport?.expected_return_pct ?? null) : stockData.expected_return_pct ?? null;
                    const activeBear = selectedRunId ? (planReport?.bear_case_return_pct ?? null) : stockData.bear_case_return_pct ?? null;
                    const activeBull = selectedRunId ? (planReport?.bull_case_return_pct ?? null) : stockData.bull_case_return_pct ?? null;
                    const activeReferencePrice = analysisReferencePriceFromMetadata ?? analysisReferencePrice;
                    const activeCurrency = planReport?.currency ?? quote?.currency ?? stockData.quote?.currency ?? null;
                    const hasReturnScenarios = activeExpected != null || activeBear != null || activeBull != null;
                    return (
                    <>
                    <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg border border-blue-700/50 p-5">
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                        <div className="flex-1">
                          <div className="text-sm text-gray-400 mb-0.5">
                            {stockData.is_generating ? 'Status' : 'Last Analysis Date'}
                          </div>
                          <div className="text-lg font-semibold text-white flex items-center gap-2 flex-wrap">
                            {stockData.is_generating ? (
                              <span className="inline-flex items-center gap-1.5 text-amber-400">
                                <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                                Running…
                              </span>
                            ) : (
                              parseReportDate(activeAnalysisDate)?.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) ?? 'N/A'
                            )}
                          </div>
                          {modelsUsed && (modelsUsed.provider || modelsUsed.deep_think || modelsUsed.quick_think) && (
                            <div className="text-xs text-gray-400 mt-0.5 space-y-0.5">
                              {showModelNames ? (
                                <>
                                  {modelsUsed.provider && <div>Provider: {modelsUsed.provider}</div>}
                                  {(modelsUsed.deep_think || modelsUsed.quick_think) && (
                                    <div>
                                      {modelsUsed.deep_think && <span>Deep: {modelsUsed.deep_think}</span>}
                                      {modelsUsed.deep_think && modelsUsed.quick_think && <span className="mx-1">·</span>}
                                      {modelsUsed.quick_think && <span>Fast: {modelsUsed.quick_think}</span>}
                                    </div>
                                  )}
                                  <button type="button" onClick={() => { setShowModelNames(false); try { localStorage.setItem('flowdeck_show_model_names', 'false'); } catch {} }} className="text-gray-500 hover:text-gray-300 underline">Hide model names</button>
                                </>
                              ) : (
                                <button type="button" onClick={() => { setShowModelNames(true); try { localStorage.setItem('flowdeck_show_model_names', 'true'); } catch {} }} className="text-gray-500 hover:text-gray-300 underline">Show model names</button>
                              )}
                              {!selectedRunId && stockData.report_days_ago != null && stockData.report_days_ago > 7 && <div className="text-amber-400/90">Consider re-running for fresh insights.</div>}
                            </div>
                          )}
                        </div>
                        {/* Radar chart + decision */}
                        <div className="flex items-center gap-4 shrink-0">
                          {summaryScoreEntries.length >= 3 && (
                            <AspectSpiderChart scoreEntries={summaryScoreEntries} size={80} />
                          )}
                          <div className="text-right">
                            <div className="text-sm text-gray-400 mb-0.5">AI Decision</div>
                            <div className={`text-2xl font-bold ${activeRecommendation === 'BUY' ? 'text-green-400' : activeRecommendation === 'SELL' ? 'text-red-400' : activeRecommendation === 'HOLD' ? 'text-yellow-400' : 'text-white'}`}>
                              {activeRecommendation || 'N/A'}
                            </div>
                            {activeConfidence != null && <div className="text-sm text-gray-400 mt-0.5">Confidence: {(activeConfidence * 100).toFixed(0)}%</div>}
                          </div>
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-gray-600/50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="flex-1">
                          {hasReturnScenarios && (
                            <ReturnScenarioBar
                              expected={activeExpected}
                              bear={activeBear}
                              bull={activeBull}
                              referencePrice={activeReferencePrice}
                              currency={activeCurrency}
                              compact
                            />
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {stockData.share_url && !selectedRunId && (
                            <button
                              type="button"
                              onClick={() => {
                                if (stockData.share_url) {
                                  navigator.clipboard.writeText(stockData.share_url);
                                  setShareCopied(true);
                                  setTimeout(() => setShareCopied(false), 2000);
                                }
                              }}
                              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-500 text-gray-300 hover:bg-gray-700/80 hover:text-white transition-colors text-sm"
                              title="Copy shareable link (viewable without login)"
                            >
                              {shareCopied ? (
                                <span className="text-green-400">Copied!</span>
                              ) : (
                                <>
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
                                  <span>Share</span>
                                </>
                              )}
                            </button>
                          )}
                        <div ref={runSelectorRef} className="relative flex items-stretch w-fit max-w-full rounded-lg border border-blue-500 bg-blue-600 hover:bg-blue-700 transition-colors">
                            <button
                              type="button"
                              onClick={() => handleGenerateReport('fresh')}
                              disabled={isStartingAnalysis || stockData.is_generating}
                              className={`flex items-center gap-2 px-4 py-2 text-white font-medium transition-colors ${isStartingAnalysis || stockData.is_generating ? 'bg-blue-500/60 cursor-default opacity-80' : ''} ${(stockData.historical_analyses?.length ?? 0) > 1 ? 'pr-2 rounded-l-lg' : 'rounded-lg'}`}
                            >
                              {isStartingAnalysis ? (
                                <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                              ) : stockData.is_generating ? (
                                <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                              ) : (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                              )}
                              {isStartingAnalysis ? 'Starting...' : stockData.is_generating ? 'Running…' : 'Run Fresh Analysis'}
                            </button>
                            {stockData.has_reports && (stockData.historical_analyses?.length ?? 0) > 1 && (
                              <>
                                <div className="w-px bg-white/20 shrink-0" aria-hidden />
                                <button
                                  type="button"
                                  disabled={isLoadingHistoricalRun}
                                  onClick={() => setRunSelectorOpen((o) => !o)}
                                  className="flex items-center justify-center px-2 py-2 text-white/90 hover:bg-white/10 transition-colors disabled:opacity-50 rounded-r-lg"
                                  title="Previous analysis runs"
                                  aria-label="Previous analysis runs"
                                >
                                  {isLoadingHistoricalRun ? (
                                    <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                    </svg>
                                  ) : (
                                    <svg className={`w-4 h-4 transition-transform ${runSelectorOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                  )}
                                </button>
                                {runSelectorOpen && runDropdownPosition && createPortal(
                                  <div
                                    ref={runDropdownRef}
                                    className="min-w-[200px] bg-gray-900 border border-gray-600 rounded-lg shadow-xl overflow-hidden"
                                    style={{
                                      position: 'fixed',
                                      top: runDropdownPosition.top,
                                      left: runDropdownPosition.left,
                                      width: runDropdownPosition.width,
                                      zIndex: 9999,
                                    }}
                                  >
                                    <div className="px-3 py-1.5 border-b border-gray-700">
                                      <span className="text-xs text-gray-400 font-medium uppercase tracking-wide">Analysis runs</span>
                                    </div>
                                    <ul className="max-h-52 overflow-y-auto py-1">
                                      <li>
                                        <button
                                          type="button"
                                          onClick={() => { handleSelectHistoricalRun(null); setRunSelectorOpen(false); }}
                                          className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between gap-2 transition-colors ${
                                            !selectedRunId ? 'bg-blue-900/50 text-blue-200' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                                          }`}
                                        >
                                          <span className="font-medium">Latest</span>
                                          <span className="text-gray-500 shrink-0">{stockData.report_date ?? ''}</span>
                                        </button>
                                      </li>
                                      {stockData.historical_analyses.slice(1).map((h) => (
                                        <li key={h.analysis_run_id}>
                                          <button
                                            type="button"
                                            onClick={() => { handleSelectHistoricalRun(h.analysis_run_id); setRunSelectorOpen(false); }}
                                            className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between gap-2 transition-colors ${
                                              selectedRunId === h.analysis_run_id ? 'bg-blue-900/50 text-blue-200' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                                            }`}
                                          >
                                            <span>{h.date}</span>
                                            {h.recommendation && (
                                              <span className={`shrink-0 font-semibold ${
                                                h.recommendation === 'BUY' ? 'text-green-400' :
                                                h.recommendation === 'SELL' ? 'text-red-400' :
                                                h.recommendation === 'HOLD' ? 'text-yellow-400' : 'text-gray-400'
                                              }`}>{h.recommendation}</span>
                                            )}
                                          </button>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>,
                                  document.body
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                    </>
                    );
                  })()}
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                    {((stockData.has_reports && !stockData.is_generating) || (selectedRunId && historicalReportsData)) && (
                      <div>
                        <div className="flex items-center justify-between gap-3 mb-3 pb-2 border-b border-gray-700">
                          <span className="text-sm text-amber-400/90">For informational purposes only. Not investment advice.</span>
                          {stockData.share_url && !selectedRunId && (
                            <button
                              type="button"
                              onClick={() => {
                                if (stockData.share_url) {
                                  navigator.clipboard.writeText(stockData.share_url);
                                  setShareCopied(true);
                                  setTimeout(() => setShareCopied(false), 2000);
                                }
                              }}
                              className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
                              title="Copy link — anyone with the link can view this report without signing in"
                            >
                              {shareCopied ? (
                                <span className="text-green-400">Link copied!</span>
                              ) : (
                                <>
                                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
                                  <span>Copy share link</span>
                                </>
                              )}
                            </button>
                          )}
                        </div>
                        <ReportTabs
                          availableReports={availableReports}
                          selectedReport={selectedReport}
                          onSelectReport={handleSelectReport}
                          reportScores={reportScores}
                          showOverviewTab
                        />
                        <div className="mt-4">
                          {(selectedReport === null || selectedReport === OVERVIEW_TAB_KEY) && availableReports.length > 0 ? (
                            availableReports.includes('final_trade_decision') ? (
                              <HierarchicalMindMap
                                ticker={stockData.ticker}
                                companyName={companyInfo?.name ?? null}
                                recommendation={activeRecommendation}
                                reports={activeReportsSource ?? {}}
                                onOpenReport={handleSelectReport}
                              />
                            ) : (
                              <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
                                <p className="text-gray-300 mb-4">
                                  The overview is available only when the full analysis has completed. Please re-run the analysis to see the overview.
                                </p>
                                <button
                                  type="button"
                                  onClick={() => handleGenerateReport('fresh')}
                                  disabled={isStartingAnalysis || stockData.is_generating}
                                  className="inline-flex items-center gap-2 px-5 py-2.5 text-white font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-70 disabled:cursor-not-allowed transition-colors"
                                >
                                  {isStartingAnalysis || stockData.is_generating ? (
                                    <>
                                      <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                      </svg>
                                      {stockData.is_generating ? 'Running…' : 'Starting...'}
                                    </>
                                  ) : (
                                    'Run Fresh Analysis'
                                  )}
                                </button>
                              </div>
                            )
                          ) : (
                            <ReportViewer content={currentReportContent} score={currentReportScore} scoreLabel={currentReportScoreLabel}
                              keyTakeaways={currentReportData?.key_takeaways} reportType={selectedReport}
                              bullViewpoint={currentReportData?.bull_viewpoint} bearViewpoint={currentReportData?.bear_viewpoint}
                              riskyViewpoint={currentReportData?.risky_viewpoint} safeViewpoint={currentReportData?.safe_viewpoint}
                              neutralViewpoint={currentReportData?.neutral_viewpoint}
                              tpsPlan={currentReportData?.tps_plan}
                              resources={currentReportData?.resources ?? null} />
                          )}
                        </div>
                      </div>
                    )}
                    {!stockData.has_reports && !stockData.is_generating && (
                      <div className="text-center py-8">
                        <p className="text-gray-400 mb-4">No analysis reports available yet.</p>
                        <button
                          type="button"
                          onClick={() => handleGenerateReport('generate')}
                          disabled={isStartingAnalysis}
                          className={`px-6 py-3 text-white font-semibold rounded-lg transition-colors ${
                            isStartingAnalysis ? 'bg-blue-500/60 cursor-default opacity-80' : 'bg-blue-600 hover:bg-blue-700'
                          }`}
                        >
                          {isStartingAnalysis ? 'Starting Analysis...' : 'Generate Analysis Report →'}
                        </button>
                      </div>
                    )}
                    {stockData.is_generating && !(selectedRunId && historicalReportsData) && (
                      <AIAnalysisLoadingView existingReportKeys={Object.keys(stockData.reports || {})} agentStatuses={analysisProgress?.agent_statuses ?? null} currentAgent={analysisProgress?.current_agent ?? null} />
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Insider Transactions Tab */}
          {activeTab === 'insider-transactions' && hasInsiderTransactions && (
            <div>
              {isLoadingInsiderTransactions ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse"><div className="h-5 bg-gray-700 rounded w-64 mb-3" /><div className="space-y-3">{[1,2,3].map((i) => <div key={i} className="h-10 bg-gray-700 rounded" />)}</div></div>
              ) : (
                <InsiderTransactionsWidget transactions={insiderTransactions} ticker={stockData.ticker} onRetry={fetchInsiderTransactions} isLoading={isLoadingInsiderTransactions} errorMessage={insiderTransactionsError} />
              )}
            </div>
          )}

          {/* News Tab */}
          {activeTab === 'news' && (
            <div className="min-h-[400px]">
              <NewsWidget articles={newsData} ticker={stockData.ticker} onRetry={fetchNews} isLoading={isLoadingNews} errorMessage={newsError} />
            </div>
          )}

          {/* SEC Filings Tab */}
          {activeTab === 'sec-filings' && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
              <h3 className="text-lg font-semibold text-white mb-2">SEC EDGAR Filings</h3>
              <p className="text-xs text-gray-400 mb-4">Quarterly (10-Q) and annual (10-K) reports filed with the U.S. Securities and Exchange Commission.</p>
              {isLoadingEdgar ? (
                <div className="animate-pulse"><div className="h-5 bg-gray-700 rounded w-48 mb-3" /><div className="h-48 bg-gray-700 rounded" /></div>
              ) : edgarFilingsError ? (
                <p className="text-amber-400 text-sm">{edgarFilingsError}</p>
              ) : edgarFilings && edgarFilings.filings.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead><tr className="border-b border-gray-600 text-gray-400"><th className="py-2 pr-4 font-medium">Form</th><th className="py-2 pr-4 font-medium">Filing Date</th><th className="py-2 font-medium">Filing</th></tr></thead>
                    <tbody>
                      {edgarFilings.filings.map((f: any) => (
                        <tr key={f.accession_number} className="border-b border-gray-700">
                          <td className="py-2.5 pr-4"><span className="font-medium text-white">{f.form}</span></td>
                          <td className="py-2.5 pr-4 text-gray-300">{f.filing_date}</td>
                          <td className="py-2.5">{f.url ? <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">View on SEC.gov</a> : <span className="text-gray-500">{f.description}</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No SEC filings found for this symbol.</p>
              )}
            </div>
          )}

        </div>
      </div>
      {authModalOpen && <AuthModal onClose={() => setAuthModalOpen(false)} message={authModalMessage} />}
    </>
  );
}
