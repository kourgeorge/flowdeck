import { useCallback, useEffect, useRef, useState } from 'react';
import { stockApi, configApi } from '../services/api';
import { WebSocketClient } from '../services/websocket';
import type { StockPageData } from '../services/types';
import { useQuoteRefresh } from '../hooks/useQuoteRefresh';
import { useAuth } from '../contexts/AuthContext';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import ReportTabs from './ReportTabs';
import ReportViewer from './ReportViewer';
import SubscribeButton from './SubscribeButton';
import AuthModal from './AuthModal';
import PriceTrendWidget from './PriceTrendWidget';
import FinancialStatementViewer from './FinancialStatementViewer';
import FundamentalCharts from './FundamentalCharts';
import FundamentalPanes from './FundamentalPanes';
import NewsWidget from './NewsWidget';
import InsiderTransactionsWidget from './InsiderTransactionsWidget';
import AIAnalysisLoadingView from './AIAnalysisLoadingView';
import { parseReportDate } from '../utils/date';
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
  prefetchedData?: StockPageData | null;
  onSubscriptionChange?: () => void;
}
const REPORT_PROCESS_ORDER = [
  'market_report','sentiment_report','news_report','technical_report',
  'fundamentals_report','sec_report','investment_plan','trader_investment_plan','final_trade_decision',
];

export default function StockDetailPanel({ ticker, prefetchedData, onSubscriptionChange }: StockDetailPanelProps) {
  const { user } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMessage, setAuthModalMessage] = useState('Please sign in to run a fresh analysis.');
  const [previewTickers, setPreviewTickers] = useState<Set<string>>(new Set());
  const [stockData, setStockData] = useState<StockPageData | null>(prefetchedData ?? null);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [extendedInfo, setExtendedInfo] = useState<ExtendedInfo | null>(null);
  const [isLoading, setIsLoading] = useState(!prefetchedData);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [fundamentalsData, setFundamentalsData] = useState<string | object | null>(null);
  const [financialStatements, setFinancialStatements] = useState<any>(null);
  const [isLoadingFundamentals, setIsLoadingFundamentals] = useState(false);
  const [newsData, setNewsData] = useState<any[]>([]);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [isLoadingNews, setIsLoadingNews] = useState(false);
  const [insiderTransactions, setInsiderTransactions] = useState<any[]>([]);
  const [insiderTransactionsError, setInsiderTransactionsError] = useState<string | null>(null);
  const [isLoadingInsiderTransactions, setIsLoadingInsiderTransactions] = useState(false);
  const [analystRecommendations, setAnalystRecommendations] = useState<any>(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [fundamentalsSubTab, setFundamentalsSubTab] = useState<'statements' | 'charts'>('charts');
  const [fundInfo, setFundInfo] = useState<any>(null);
  const [isLoadingFundInfo, setIsLoadingFundInfo] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<{ agent_statuses: Record<string,string>; current_agent?: string | null } | null>(null);
  const [edgarFilings, setEdgarFilings] = useState<any>(null);
  const [edgarFilingsError, setEdgarFilingsError] = useState<string | null>(null);
  const [isLoadingEdgar, setIsLoadingEdgar] = useState(false);
  const [futureEvents, setFutureEvents] = useState<any>(null);
  const [isLoadingFutureEvents, setIsLoadingFutureEvents] = useState(false);
  const [subscriptionForTicker, setSubscriptionForTicker] = useState<Subscription | null>(null);
  const [emailPreferenceToggling, setEmailPreferenceToggling] = useState(false);
  const [priceFlash, setPriceFlash] = useState(false);

  const refreshedQuote = useQuoteRefresh(ticker, 60000);
  const prevPriceRef = useRef<number | null>(null);
  const wsClientRef = useRef<WebSocketClient | null>(null);

  const quoteType = companyInfo?.quoteType ?? (
    fundamentalsData && typeof fundamentalsData === 'object' && 'QuoteType' in fundamentalsData
      ? (fundamentalsData as { QuoteType?: string }).QuoteType : undefined
  );
  const hasFundamentals = quoteType === 'EQUITY' || quoteType == null;
  const isUSCompany = companyInfo?.country === 'United States' || companyInfo?.country === 'USA';

  useEffect(() => {
    configApi.getPublicConfig()
      .then((cfg) => setPreviewTickers(new Set(cfg.preview_tickers.map((t) => t.toUpperCase()))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (activeTab === 'fundamentals' && quoteType != null && quoteType !== 'EQUITY') setActiveTab('overview');
  }, [quoteType, activeTab]);

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

  const applyStockData = (data: StockPageData) => {
    setStockData(data);
    if (data.reports && Object.keys(data.reports).length > 0) {
      const reports = Object.keys(data.reports);
      setSelectedReport(reports.includes('final_trade_decision') ? 'final_trade_decision' : reports[0]);
    }
    if (data.is_generating && data.generation_analysis_id) {
      setAnalysisProgress(null);
      const client = new WebSocketClient(data.generation_analysis_id);
      client.on('status', (msg: any) => { const s = msg?.data?.agent_statuses; if (s) setAnalysisProgress({ agent_statuses: s, current_agent: null }); });
      client.on('progress', (msg: any) => { const s = msg?.data?.agent_statuses; const c = msg?.data?.current_agent; if (s) setAnalysisProgress({ agent_statuses: s, current_agent: c ?? null }); loadStockData(); });
      client.on('completed', () => { setAnalysisProgress(null); loadStockData(); });
      client.connect();
      wsClientRef.current = client;
    } else { setAnalysisProgress(null); }
  };

  const loadStockData = async () => {
    if (!ticker) return;
    try {
      setIsLoading(true); setLoadError(null);
      const data = await stockApi.getStockPage(ticker);
      applyStockData(data);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const is404 = error?.response?.status === 404;
      setLoadError(typeof detail === 'string' ? detail : is404 ? `Ticker "${ticker}" not found.` : 'Unable to load stock data.');
      setStockData(null);
    } finally { setIsLoading(false); }

    stockApi.getCompanyInfo(ticker).then((info) => {
      setCompanyInfo(info);
      const qt = info.quoteType;
      if (qt === 'EQUITY' || qt == null) {
        setIsLoadingFundamentals(true);
        stockApi.getFundamentals(ticker).then((r) => r && setFundamentalsData(r.fundamentals)).catch(() => {}).finally(() => setIsLoadingFundamentals(false));
      } else { setFundamentalsData(null); setIsLoadingFundamentals(false); }
      if (qt === 'ETF') {
        setIsLoadingFundInfo(true);
        stockApi.getFundInfo(ticker).then(setFundInfo).catch(() => {}).finally(() => setIsLoadingFundInfo(false));
      } else { setFundInfo(null); }
    }).catch(() => {});
    stockApi.getExtendedInfo(ticker).then(setExtendedInfo).catch(() => {});
    setIsLoadingRecommendations(true);
    stockApi.getAnalystRecommendations(ticker).then(setAnalystRecommendations).catch(() => {}).finally(() => setIsLoadingRecommendations(false));
    setIsLoadingFutureEvents(true);
    stockApi.getFutureEvents(ticker).then(setFutureEvents).catch(() => {}).finally(() => setIsLoadingFutureEvents(false));
  };

  useEffect(() => {
    // Reset all per-ticker state
    setCompanyInfo(null); setExtendedInfo(null); setFundamentalsData(null);
    setFinancialStatements(null); setNewsData([]); setNewsError(null); setInsiderTransactions([]);
    setInsiderTransactionsError(null); setFundamentalsSubTab('charts'); setFundInfo(null);
    setAnalysisProgress(null); setEdgarFilings(null); setEdgarFilingsError(null); setFutureEvents(null);
    setActiveTab('overview'); setSelectedReport(null); setLoadError(null); setAnalysisError(null);
    if (wsClientRef.current) { wsClientRef.current.disconnect(); wsClientRef.current = null; }

    if (prefetchedData) {
      // Use pre-fetched data immediately — no loading spinner
      setStockData(prefetchedData);
      setIsLoading(false);
      applyStockData(prefetchedData);
      // Silently refresh stock page data in the background to pick up any changes
      // since the prefetch (e.g. new report, updated price). No loading spinner shown.
      stockApi.getStockPage(ticker).then((fresh) => applyStockData(fresh)).catch(() => {});
      // Kick off background fetches for secondary data (company info, extended info, etc.)
      stockApi.getCompanyInfo(ticker).then((info) => {
        setCompanyInfo(info);
        const qt = info.quoteType;
        if (qt === 'EQUITY' || qt == null) {
          setIsLoadingFundamentals(true);
          stockApi.getFundamentals(ticker).then((r) => r && setFundamentalsData(r.fundamentals)).catch(() => {}).finally(() => setIsLoadingFundamentals(false));
        } else { setFundamentalsData(null); setIsLoadingFundamentals(false); }
        if (qt === 'ETF') {
          setIsLoadingFundInfo(true);
          stockApi.getFundInfo(ticker).then(setFundInfo).catch(() => {}).finally(() => setIsLoadingFundInfo(false));
        } else { setFundInfo(null); }
      }).catch(() => {});
      stockApi.getExtendedInfo(ticker).then(setExtendedInfo).catch(() => {});
      setIsLoadingRecommendations(true);
      stockApi.getAnalystRecommendations(ticker).then(setAnalystRecommendations).catch(() => {}).finally(() => setIsLoadingRecommendations(false));
      setIsLoadingFutureEvents(true);
      stockApi.getFutureEvents(ticker).then(setFutureEvents).catch(() => {}).finally(() => setIsLoadingFutureEvents(false));
    } else {
      setStockData(null);
      setIsLoading(true);
      loadStockData();
    }
    return () => { if (wsClientRef.current) wsClientRef.current.disconnect(); };
  }, [ticker]);

  useEffect(() => {
    if (!ticker || !stockData?.is_generating) return;
    const interval = setInterval(() => {
      stockApi.getStockPage(ticker).then((data) => {
        setStockData(data);
        if (data.reports && Object.keys(data.reports).length > 0) {
          const keys = Object.keys(data.reports);
          setSelectedReport(keys.includes('final_trade_decision') ? 'final_trade_decision' : keys[0]);
        }
      }).catch(() => {});
    }, 3500);
    return () => clearInterval(interval);
  }, [ticker, stockData?.is_generating]);

  useEffect(() => {
    if (activeTab !== 'fundamentals' || !ticker || financialStatements) return;
    const qt = companyInfo?.quoteType;
    if (qt !== 'EQUITY' && qt != null) return;
    if (!fundamentalsData && !isLoadingFundamentals) {
      setIsLoadingFundamentals(true);
      Promise.all([
        stockApi.getFundamentals(ticker).catch(() => null),
        stockApi.getFinancialStatements(ticker, 'all', 'quarterly').catch(() => null),
      ]).then(([fundamentals, st]) => {
        if (fundamentals) setFundamentalsData(fundamentals.fundamentals);
        if (st) setFinancialStatements(st.statements);
        setIsLoadingFundamentals(false);
      });
    } else {
      setIsLoadingFundamentals(true);
      stockApi.getFinancialStatements(ticker, 'all', 'quarterly').then((r) => setFinancialStatements(r.statements)).catch(() => {}).finally(() => setIsLoadingFundamentals(false));
    }
  }, [activeTab, ticker, fundamentalsData, financialStatements, isLoadingFundamentals, companyInfo?.quoteType]);

  const fetchNews = useCallback(() => {
    if (!ticker) return;
    setNewsError(null); setIsLoadingNews(true);
    stockApi.getNews(ticker).then((r) => { setNewsData(r.articles || []); setNewsError('error' in r ? r.error ?? null : null); setIsLoadingNews(false); })
      .catch((err) => { setNewsError(err.response?.data?.detail ?? err.message ?? 'Unable to fetch news.'); setNewsData([]); setIsLoadingNews(false); });
  }, [ticker]);

  const fetchInsiderTransactions = useCallback(() => {
    if (!ticker) return;
    setInsiderTransactionsError(null); setIsLoadingInsiderTransactions(true);
    stockApi.getInsiderTransactions(ticker, 50).then((r) => { setInsiderTransactions(r.transactions || []); setInsiderTransactionsError('error' in r ? r.error ?? null : null); setIsLoadingInsiderTransactions(false); })
      .catch((err) => { setInsiderTransactionsError(err.response?.data?.detail ?? err.message ?? 'Unable to fetch insider transactions.'); setInsiderTransactions([]); setIsLoadingInsiderTransactions(false); });
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

  useEffect(() => { if (activeTab === 'news' && ticker && !isLoadingNews) fetchNews(); }, [activeTab, ticker, fetchNews]);
  useEffect(() => { if (activeTab === 'news' && ticker && !isLoadingInsiderTransactions) fetchInsiderTransactions(); }, [activeTab, ticker, fetchInsiderTransactions]);

  useEffect(() => {
    if (activeTab !== 'sec-filings' || !ticker) return;
    let cancelled = false;
    setIsLoadingEdgar(true); setEdgarFilingsError(null);
    stockApi.getEdgarFilings(ticker)
      .then((data) => { if (!cancelled) { setEdgarFilings(data); if (data.error) setEdgarFilingsError(data.error); } })
      .catch((err) => { if (!cancelled) { setEdgarFilingsError(err.response?.data?.detail ?? err.message ?? 'Unable to load SEC filings.'); setEdgarFilings(null); } })
      .finally(() => { if (!cancelled) setIsLoadingEdgar(false); });
    return () => { cancelled = true; };
  }, [activeTab, ticker]);

  const handleGenerateReport = async (source: 'fresh' | 'generate' = 'fresh') => {
    if (!ticker) return;
    setAnalysisError(null);
    if (!user) { setAuthModalMessage(source === 'generate' ? 'Please sign in to generate an analysis report.' : 'Please sign in to run a fresh analysis.'); setAuthModalOpen(true); return; }
    try { await stockApi.startAnalysis(ticker); setAnalysisError(null); await loadStockData(); }
    catch (error: unknown) {
      const axiosError = error as { response?: { status?: number; data?: { detail?: string | string[] } } };
      const detail = axiosError.response?.data?.detail;
      setAnalysisError(typeof detail === 'string' ? detail : Array.isArray(detail) && detail.length > 0 ? String(detail[0]) : axiosError.response?.status === 402 ? 'Insufficient token balance. Need 200 tokens to create a report.' : 'Failed to start analysis. Please try again.');
    }
  };

  const formatNumber = (value: number | null | undefined, decimals = 2): string => {
    if (value == null) return 'N/A';
    if (value >= 1e12) return `$${(value / 1e12).toFixed(decimals)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(decimals)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(decimals)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(decimals)}K`;
    return `$${value.toFixed(decimals)}`;
  };
  const formatPercent = (value: number | null | undefined): string => value == null ? 'N/A' : `${(value * 100).toFixed(2)}%`;

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

  const allReports = Object.keys(stockData.reports || {});
  const availableReports = [...allReports].sort((a, b) => {
    const idxA = REPORT_PROCESS_ORDER.indexOf(a), idxB = REPORT_PROCESS_ORDER.indexOf(b);
    if (idxA === -1 && idxB === -1) return a.localeCompare(b);
    if (idxA === -1) return 1; if (idxB === -1) return -1;
    return idxA - idxB;
  });
  const currentReportData = selectedReport && stockData.reports_with_scores ? stockData.reports_with_scores[selectedReport] : null;
  const currentReportContent = currentReportData?.content || (selectedReport ? stockData.reports[selectedReport] : null);
  const currentReportScore = currentReportData?.score;
  const currentReportScoreLabel = currentReportData?.score_label;
  const reportScores: Record<string, { score: number | null; score_label: string | null }> = {};
  if (stockData.reports_with_scores) Object.entries(stockData.reports_with_scores).forEach(([k, v]) => { reportScores[k] = { score: v.score, score_label: v.score_label }; });
  const modelsUsed = stockData.reports_with_scores ? (Object.values(stockData.reports_with_scores).find((r) => r.models_used)?.models_used ?? null) : null;
  const quote = refreshedQuote ?? stockData.quote;
  const lastUpdateTime = quote?.last_update_time ? new Date(quote.last_update_time).toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }) : '';

// Made with Bob

  return (
    <>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-4 sm:p-6 space-y-4">

          {/* Header */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
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
                      ${quote.current_price.toFixed(2)}
                    </div>
                    <div className={`text-base sm:text-lg font-semibold flex items-center gap-1 ${quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      <span>{quote.daily_change_percent >= 0 ? '▲' : '▼'}</span>
                      <span>({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%) {quote.daily_change >= 0 ? '+' : ''}{quote.daily_change.toFixed(2)}</span>
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
                  { id: 'news', label: 'News' },
                  { id: 'ai-analysis', label: 'AI Analysis' },
                ].map((tab) => {
                  const isActive = activeTab === tab.id;
                  const isAiTab = tab.id === 'ai-analysis';
                  return (
                    <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                      className={`px-3 py-2 text-sm rounded-t-lg transition-colors border-b-2 -mb-px ${
                        isActive
                          ? isAiTab ? 'bg-blue-950/70 text-blue-200 border-blue-500 font-semibold' : 'bg-gray-800 text-white border-blue-500 font-medium'
                          : isAiTab ? 'bg-blue-950/40 text-blue-200 hover:text-white hover:bg-blue-950/60 border-blue-700/50 font-semibold' : 'text-gray-400 hover:text-white hover:bg-gray-800/70 border-transparent font-medium'
                      }`}>
                      {tab.label}
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
                <button type="button" onClick={() => setFundamentalsSubTab('charts')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${fundamentalsSubTab === 'charts' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>Charts</button>
                <button type="button" onClick={() => setFundamentalsSubTab('statements')}
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
                      {quote && (<>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Current Price</span><span className="text-xs font-semibold text-white">${quote.current_price.toFixed(2)}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Daily Change</span>
                          <span className={`text-xs font-semibold ${quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%) {quote.daily_change >= 0 ? '+' : ''}${quote.daily_change.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Day's Range</span><span className="text-xs font-semibold text-white">${quote.day_low?.toFixed(2) || 'N/A'} – ${quote.day_high?.toFixed(2) || 'N/A'}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Prev Close</span><span className="text-xs font-semibold text-white">${quote.previous_close?.toFixed(2) || 'N/A'}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Bid</span><span className="text-xs font-semibold text-white">{quote.bid_price != null ? `$${quote.bid_price.toFixed(2)}` : 'N/A'}{quote.bid_size != null ? ` ×${quote.bid_size}` : ''}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Ask</span><span className="text-xs font-semibold text-white">{quote.ask_price != null ? `$${quote.ask_price.toFixed(2)}` : 'N/A'}{quote.ask_size != null ? ` ×${quote.ask_size}` : ''}</span></div>
                        {hasFundamentals && <div className="flex justify-between"><span className="text-xs text-gray-400">Beta</span><span className="text-xs font-semibold text-white">{extendedInfo?.beta?.toFixed(2) || 'N/A'}</span></div>}
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Volume</span><span className="text-xs font-semibold text-white">{quote.volume ? quote.volume.toLocaleString() : 'N/A'}</span></div>
                        <div className="flex justify-between"><span className="text-xs text-gray-400">Avg Volume</span><span className="text-xs font-semibold text-white">{extendedInfo?.average_volume ? extendedInfo.average_volume.toLocaleString() : 'N/A'}</span></div>
                        {hasFundamentals && <div className="flex justify-between"><span className="text-xs text-gray-400">Sector</span><span className="text-xs font-semibold text-white truncate max-w-[140px]">{companyInfo?.sector || 'N/A'}</span></div>}
                        {hasFundamentals && <div className="flex justify-between"><span className="text-xs text-gray-400">Market Cap</span><span className="text-xs font-semibold text-white">{formatNumber(extendedInfo?.market_cap)}</span></div>}
                        <div className="flex justify-between"><span className="text-xs text-gray-400">52wk Range</span><span className="text-xs font-semibold text-white">{quote.fifty_two_week_low && quote.fifty_two_week_high ? `$${quote.fifty_two_week_low.toFixed(2)} – $${quote.fifty_two_week_high.toFixed(2)}` : 'N/A'}</span></div>
                        {hasFundamentals && <>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">Revenue</span><span className="text-xs font-semibold text-white">{formatNumber(extendedInfo?.revenue)}</span></div>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">Gross Margin</span><span className="text-xs font-semibold text-white">{formatPercent(extendedInfo?.gross_margin)}</span></div>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">Dividend Yield</span><span className="text-xs font-semibold text-white">{formatPercent(extendedInfo?.dividend_yield)}</span></div>
                          <div className="flex justify-between"><span className="text-xs text-gray-400">EPS</span><span className="text-xs font-semibold text-white">{extendedInfo?.trailing_eps?.toFixed(2) || 'N/A'}</span></div>
                        </>}
                      </>)}
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
                <FundamentalPanes data={fundamentalsData} analystRecommendations={analystRecommendations} isLoadingRecommendations={isLoadingRecommendations} />
              ) : null}
            </div>
          )}

          {/* AI Analysis Tab */}
          {activeTab === 'ai-analysis' && (
            <div className="space-y-4">
              {!user && !previewTickers.has((ticker ?? '').toUpperCase()) ? (
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
                  <p className="text-sm text-amber-400/90 bg-amber-950/30 border border-amber-700/40 rounded-lg px-4 py-2">For informational purposes only. Not investment advice.</p>
                  {analysisError && (
                    <div className="flex items-center gap-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-red-200" role="alert">
                      <svg className="h-5 w-5 shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <span>{analysisError}</span>
                      <button type="button" onClick={() => setAnalysisError(null)} className="ml-auto rounded p-1 text-red-300 hover:bg-red-900/50" aria-label="Dismiss">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  )}
                  {stockData.has_reports && stockData.report_date && (() => {
                    const summaryScoreEntries = getAnalysisScoreEntries(stockData.reports_with_scores ?? null);
                    return (
                    <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg border border-blue-700/50 p-4">
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                        <div className="flex-1">
                          <div className="text-xs text-gray-400 mb-0.5">Last Analysis Date</div>
                          <div className="text-base font-semibold text-white">
                            {parseReportDate(stockData.report_date)?.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) ?? 'N/A'}
                          </div>
                          {modelsUsed && (modelsUsed.provider || modelsUsed.deep_think || modelsUsed.quick_think) && (
                            <div className="text-xs text-gray-400 mt-0.5 space-y-0.5">
                              {modelsUsed.provider && <div>Provider: {modelsUsed.provider}</div>}
                              {(modelsUsed.deep_think || modelsUsed.quick_think) && (
                                <div>
                                  {modelsUsed.deep_think && <span>Deep: {modelsUsed.deep_think}</span>}
                                  {modelsUsed.deep_think && modelsUsed.quick_think && <span className="mx-1">·</span>}
                                  {modelsUsed.quick_think && <span>Fast: {modelsUsed.quick_think}</span>}
                                </div>
                              )}
                              {stockData.report_days_ago != null && stockData.report_days_ago > 7 && <div className="text-amber-400/90">Consider re-running for fresh insights.</div>}
                            </div>
                          )}
                        </div>
                        {/* Radar chart + decision */}
                        <div className="flex items-center gap-4 shrink-0">
                          {summaryScoreEntries.length >= 3 && (
                            <AspectSpiderChart scoreEntries={summaryScoreEntries} size={80} />
                          )}
                          <div className="text-right">
                            <div className="text-xs text-gray-400 mb-0.5">AI Decision</div>
                            <div className={`text-xl font-bold ${stockData.recommendation?.recommendation === 'BUY' ? 'text-green-400' : stockData.recommendation?.recommendation === 'SELL' ? 'text-red-400' : stockData.recommendation?.recommendation === 'HOLD' ? 'text-yellow-400' : 'text-white'}`}>
                              {stockData.recommendation?.recommendation || 'N/A'}
                            </div>
                            {stockData.recommendation?.confidence && <div className="text-xs text-gray-400 mt-0.5">Confidence: {(stockData.recommendation.confidence * 100).toFixed(0)}%</div>}
                          </div>
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-gray-600/50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="flex-1">
                          {(stockData.expected_return_pct != null || stockData.bear_case_return_pct != null || stockData.bull_case_return_pct != null) && (
                            <ReturnScenarioBar
                              expected={stockData.expected_return_pct}
                              bear={stockData.bear_case_return_pct}
                              bull={stockData.bull_case_return_pct}
                              compact
                            />
                          )}
                        </div>
                        {!stockData.is_generating && (
                          <button onClick={() => handleGenerateReport('fresh')} className="shrink-0 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                            Run Fresh Analysis
                          </button>
                        )}
                      </div>
                    </div>
                    );
                  })()}
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                    {stockData.has_reports && !stockData.is_generating && (
                      <div>
                        <ReportTabs availableReports={availableReports} selectedReport={selectedReport} onSelectReport={setSelectedReport} reportScores={reportScores} />
                        <div className="mt-4">
                          <ReportViewer content={currentReportContent} score={currentReportScore} scoreLabel={currentReportScoreLabel}
                            keyTakeaways={currentReportData?.key_takeaways} reportType={selectedReport}
                            bullViewpoint={currentReportData?.bull_viewpoint} bearViewpoint={currentReportData?.bear_viewpoint}
                            riskyViewpoint={currentReportData?.risky_viewpoint} safeViewpoint={currentReportData?.safe_viewpoint}
                            neutralViewpoint={currentReportData?.neutral_viewpoint} />
                        </div>
                      </div>
                    )}
                    {!stockData.has_reports && !stockData.is_generating && (
                      <div className="text-center py-8">
                        <p className="text-gray-400 mb-4">No analysis reports available yet.</p>
                        <button onClick={() => handleGenerateReport('generate')} className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors">Generate Analysis Report →</button>
                      </div>
                    )}
                    {stockData.is_generating && (
                      <AIAnalysisLoadingView existingReportKeys={Object.keys(stockData.reports || {})} agentStatuses={analysisProgress?.agent_statuses ?? null} currentAgent={analysisProgress?.current_agent ?? null} />
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* News Tab */}
          {activeTab === 'news' && (
            <div className="space-y-4">
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 flex flex-col" style={{ minHeight: '400px' }}>
                <h3 className="text-lg font-semibold text-white mb-4 shrink-0">Latest News</h3>
                <div className="flex-1 min-h-0 overflow-y-auto">
                  {isLoadingNews ? (
                    <div className="animate-pulse space-y-3">{[1,2,3].map((i) => <div key={i} className="h-20 bg-gray-700 rounded" />)}</div>
                  ) : (
                    <NewsWidget articles={newsData} ticker={stockData.ticker} onRetry={fetchNews} isLoading={isLoadingNews} errorMessage={newsError} />
                  )}
                </div>
              </div>
              <div>
                {isLoadingInsiderTransactions ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse"><div className="h-5 bg-gray-700 rounded w-64 mb-3" /><div className="space-y-3">{[1,2,3].map((i) => <div key={i} className="h-10 bg-gray-700 rounded" />)}</div></div>
                ) : (
                  <InsiderTransactionsWidget transactions={insiderTransactions} ticker={stockData.ticker} onRetry={fetchInsiderTransactions} isLoading={isLoadingInsiderTransactions} errorMessage={insiderTransactionsError} />
                )}
              </div>
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
