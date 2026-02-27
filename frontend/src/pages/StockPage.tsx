import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { stockApi } from '../services/api';
import { WebSocketClient } from '../services/websocket';
import type { StockPageData } from '../services/types';
import { useQuoteRefresh } from '../hooks/useQuoteRefresh';
import { useAuth } from '../contexts/AuthContext';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import ReportTabs from '../components/ReportTabs';
import AspectSpiderChart, { getAnalysisScoreEntries } from '../components/AspectSpiderChart';
import ReportViewer from '../components/ReportViewer';
import SubscribeButton from '../components/SubscribeButton';
import AuthModal from '../components/AuthModal';
import PriceTrendWidget from '../components/PriceTrendWidget';
import FinancialStatementViewer from '../components/FinancialStatementViewer';
import FundamentalCharts from '../components/FundamentalCharts';
import FundamentalPanes from '../components/FundamentalPanes';
import NewsWidget from '../components/NewsWidget';
import InsiderTransactionsWidget from '../components/InsiderTransactionsWidget';
import AIAnalysisLoadingView from '../components/AIAnalysisLoadingView';
import { parseReportDate } from '../utils/date';
import { configApi } from '../services/api';

interface CompanyInfo {
  name: string;
  sector: string;
  industry: string;
  exchange: string;
  country: string;
  website: string;
  quoteType?: string | null;
}

interface ExtendedInfo {
  beta: number | null;
  market_cap: number | null;
  revenue: number | null;
  gross_margin: number | null;
  dividend_yield: number | null;
  trailing_eps: number | null;
  forward_eps: number | null;
  average_volume: number | null;
  enterprise_value: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  ebitda: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
}

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMessage, setAuthModalMessage] = useState('Please sign in to run a fresh analysis.');
  const [previewTickers, setPreviewTickers] = useState<Set<string>>(new Set());
  const [stockData, setStockData] = useState<StockPageData | null>(null);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const [extendedInfo, setExtendedInfo] = useState<ExtendedInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [wsClient, setWsClient] = useState<WebSocketClient | null>(null);
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
  const [fundInfo, setFundInfo] = useState<{
    ticker: string;
    totalAssets: number | null;
    yield: number | null;
    category: string | null;
    fundInception: number | string | null;
    expenseRatio: number | null;
    description: string | null;
    fund_overview: Record<string, unknown> | null;
    top_holdings: Array<Record<string, unknown>> | null;
    sector_weightings: Record<string, number> | null;
    asset_classes: Record<string, number> | null;
  } | null>(null);
  const [isLoadingFundInfo, setIsLoadingFundInfo] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<{
    agent_statuses: Record<string, string>;
    current_agent?: string | null;
  } | null>(null);
  const [edgarFilings, setEdgarFilings] = useState<{
    cik: string;
    company_name: string | null;
    filings: Array<{
      form: string;
      filing_date: string;
      accession_number: string;
      url: string;
      description: string;
    }>;
    error: string | null;
  } | null>(null);
  const [edgarFilingsError, setEdgarFilingsError] = useState<string | null>(null);
  const [isLoadingEdgar, setIsLoadingEdgar] = useState(false);
  const [futureEvents, setFutureEvents] = useState<{
    ticker: string;
    events: Array<{ date: string; type: string; label: string; eps_estimate?: number }>;
    count: number;
    error?: string;
  } | null>(null);
  const [isLoadingFutureEvents, setIsLoadingFutureEvents] = useState(false);
  const [subscriptionForTicker, setSubscriptionForTicker] = useState<Subscription | null>(null);
  const [emailPreferenceToggling, setEmailPreferenceToggling] = useState(false);

  const refreshedQuote = useQuoteRefresh(ticker ?? '', 60000);
  const prevPriceRef = useRef<number | null>(null);
  const [priceFlash, setPriceFlash] = useState(false);

  // Derive quote type: from company info (preferred) or fundamentals response; treat missing as equity
  const quoteType = companyInfo?.quoteType ?? (fundamentalsData && typeof fundamentalsData === 'object' && 'QuoteType' in fundamentalsData ? (fundamentalsData as { QuoteType?: string }).QuoteType : undefined);
  // Only equities have meaningful fundamentals (financial statements, P/E, revenue, etc.). ETFs/indices do not.
  const hasFundamentals = quoteType === 'EQUITY' || quoteType == null;

  // American companies have SEC EDGAR filings (10-K, 10-Q)
  const isUSCompany =
    companyInfo?.country === 'United States' || companyInfo?.country === 'USA';

  // When ticker is not an equity and user is on Fundamentals tab, switch to Overview
  useEffect(() => {
    if (activeTab === 'fundamentals' && quoteType != null && quoteType !== 'EQUITY') {
      setActiveTab('overview');
    }
  }, [quoteType, activeTab]);

  // Flicker price background when quote updates (e.g. from polling)
  useEffect(() => {
    const currentPrice = refreshedQuote?.current_price ?? stockData?.quote?.current_price;
    if (currentPrice == null) return;
    if (prevPriceRef.current !== null && prevPriceRef.current !== currentPrice) {
      setPriceFlash(true);
      const t = setTimeout(() => setPriceFlash(false), 600);
      return () => {
        clearTimeout(t);
        prevPriceRef.current = currentPrice;
      };
    }
    prevPriceRef.current = currentPrice;
  }, [refreshedQuote?.current_price, stockData?.quote?.current_price]);

  // Fetch preview tickers (major stocks) from server once on mount
  useEffect(() => {
    configApi.getPublicConfig()
      .then((cfg) => setPreviewTickers(new Set(cfg.preview_tickers.map((t) => t.toUpperCase()))))
      .catch(() => {}); // silently ignore; gate defaults to open (empty set = no lock)
  }, []);

  const loadStockData = async () => {
    if (!ticker) return;
    
    try {
      setIsLoading(true);
      setLoadError(null);
      // Only block initial render on stock page data (quote, reports, recommendations, etc.)
      const data = await stockApi.getStockPage(ticker);
      setStockData(data);
      
      // Set initial selected report - prefer final_trade_decision if available
      if (data.reports && Object.keys(data.reports).length > 0) {
        const reports = Object.keys(data.reports);
        const firstReport = reports.includes('final_trade_decision') 
          ? 'final_trade_decision' 
          : reports[0];
        setSelectedReport(firstReport);
      }

      // Connect WebSocket if analysis is generating
      if (data.is_generating && data.generation_analysis_id) {
        setAnalysisProgress(null);
        const client = new WebSocketClient(data.generation_analysis_id);
        client.on('status', (message: { data?: { agent_statuses?: Record<string, string> } }) => {
          const statuses = message?.data?.agent_statuses;
          if (statuses) setAnalysisProgress({ agent_statuses: statuses, current_agent: null });
        });
        client.on('progress', (message: { data?: { agent_statuses?: Record<string, string>; current_agent?: string | null } }) => {
          const statuses = message?.data?.agent_statuses;
          const current = message?.data?.current_agent;
          if (statuses) setAnalysisProgress({ agent_statuses: statuses, current_agent: current ?? null });
          loadStockData();
        });
        client.on('completed', () => {
          setAnalysisProgress(null);
          loadStockData();
        });
        client.connect();
        setWsClient(client);
      } else {
        setAnalysisProgress(null);
      }
    } catch (error: any) {
      console.error('Failed to load stock data:', error);
      const detail = error?.response?.data?.detail;
      const is404 = error?.response?.status === 404;
      setLoadError(
        typeof detail === 'string' ? detail : is404
          ? `Ticker "${ticker}" not found. Check the symbol and try again.`
          : 'Unable to load stock data. Please try again later.'
      );
      setStockData(null);
    } finally {
      setIsLoading(false);
    }

    // Overview data only: fetch in background so overview (including summary pane) can fill in
    if (!ticker) return;
    stockApi.getCompanyInfo(ticker).then((info) => {
      setCompanyInfo(info);
      const qt = info.quoteType;
      // Fetch fundamentals only for equities; not for ETF/index/currency/crypto (no meaningful statements)
      if (qt === 'EQUITY' || qt == null) {
        setIsLoadingFundamentals(true);
        stockApi.getFundamentals(ticker)
          .then((r) => r && setFundamentalsData(r.fundamentals))
          .catch((e) => console.error('Failed to load fundamentals:', e))
          .finally(() => setIsLoadingFundamentals(false));
      } else {
        setFundamentalsData(null);
        setIsLoadingFundamentals(false);
      }
      if (qt === 'ETF') {
        setIsLoadingFundInfo(true);
        stockApi.getFundInfo(ticker)
          .then(setFundInfo)
          .catch((e) => console.error('Failed to load fund info:', e))
          .finally(() => setIsLoadingFundInfo(false));
      } else {
        setFundInfo(null);
      }
    }).catch((e) => console.error('Failed to load company info:', e));
    stockApi.getExtendedInfo(ticker).then(setExtendedInfo).catch((e) => console.error('Failed to load extended info:', e));
    setIsLoadingRecommendations(true);
    stockApi.getAnalystRecommendations(ticker)
      .then(setAnalystRecommendations)
      .catch((e) => console.error('Failed to load analyst recommendations:', e))
      .finally(() => setIsLoadingRecommendations(false));
    setIsLoadingFutureEvents(true);
    stockApi.getFutureEvents(ticker)
      .then(setFutureEvents)
      .catch((e) => console.error('Failed to load future events:', e))
      .finally(() => setIsLoadingFutureEvents(false));
  };

  useEffect(() => {
    if (ticker) {
      setNewsData([]);
      setNewsError(null); // Clear news when ticker changes so we don't show previous stock's news
      setInsiderTransactions([]);
      setInsiderTransactionsError(null);
      setFundamentalsSubTab('charts'); // Reset when ticker changes
      setFundInfo(null);
      setAnalysisProgress(null);
      setEdgarFilings(null);
      setEdgarFilingsError(null);
      setFutureEvents(null);
    }
    loadStockData();

    return () => {
      setAnalysisProgress(null);
      if (wsClient) {
        wsClient.disconnect();
      }
    };
  }, [ticker]);

  // Poll for new reports while analysis is generating (server writes JSONs; WebSocket may not fire often)
  useEffect(() => {
    if (!ticker || !stockData?.is_generating) return;
    const interval = setInterval(() => {
      stockApi.getStockPage(ticker).then((data) => {
        setStockData(data);
        if (data.reports && Object.keys(data.reports).length > 0) {
          const keys = Object.keys(data.reports);
          const first = keys.includes('final_trade_decision') ? 'final_trade_decision' : keys[0];
          setSelectedReport(first);
        }
      }).catch((e) => console.error('Poll for reports failed:', e));
    }, 3500);
    return () => clearInterval(interval);
  }, [ticker, stockData?.is_generating]);

  // Load financial statements only when Fundamentals tab is active and ticker has fundamentals (equity/ETF)
  useEffect(() => {
    if (activeTab !== 'fundamentals' || !ticker || financialStatements) return;
    const qt = companyInfo?.quoteType;
    if (qt !== 'EQUITY' && qt != null) return; // Only equities have financial statements
    const loadStatements = () => {
      setIsLoadingFundamentals(true);
      stockApi.getFinancialStatements(ticker, 'all', 'quarterly')
        .then((r) => setFinancialStatements(r.statements))
        .catch((err) => console.error('Failed to load financial statements:', err))
        .finally(() => setIsLoadingFundamentals(false));
    };
    // If fundamentals not loaded yet (e.g. user opened Fundamentals tab first), fetch both
    if (!fundamentalsData && !isLoadingFundamentals) {
      setIsLoadingFundamentals(true);
      Promise.all([
        stockApi.getFundamentals(ticker).catch((err) => { console.error('Failed to load fundamentals:', err); return null; }),
        stockApi.getFinancialStatements(ticker, 'all', 'quarterly').catch((err) => { console.error('Failed to load financial statements:', err); return null; })
      ]).then(([fundamentals, st]) => {
        if (fundamentals) setFundamentalsData(fundamentals.fundamentals);
        if (st) setFinancialStatements(st.statements);
        setIsLoadingFundamentals(false);
      });
    } else {
      loadStatements();
    }
  }, [activeTab, ticker, fundamentalsData, financialStatements, isLoadingFundamentals, companyInfo?.quoteType]);

  const fetchNews = useCallback(() => {
    if (!ticker) return;
    setNewsError(null);
    setIsLoadingNews(true);
    stockApi.getNews(ticker)
      .then((response) => {
        setNewsData(response.articles || []);
        setNewsError('error' in response ? response.error ?? null : null);
        setIsLoadingNews(false);
      })
      .catch((err) => {
        const message = err.response?.data?.detail ?? err.message ?? 'Unable to fetch news. Please try again later.';
        setNewsError(message);
        setNewsData([]);
        setIsLoadingNews(false);
      });
  }, [ticker]);

  const fetchInsiderTransactions = useCallback(() => {
    if (!ticker) return;
    setInsiderTransactionsError(null);
    setIsLoadingInsiderTransactions(true);
    stockApi.getInsiderTransactions(ticker, 50)
      .then((response) => {
        setInsiderTransactions(response.transactions || []);
        setInsiderTransactionsError('error' in response ? response.error ?? null : null);
        setIsLoadingInsiderTransactions(false);
      })
      .catch((err) => {
        const message = err.response?.data?.detail ?? err.message ?? 'Unable to fetch insider transactions. Please try again later.';
        setInsiderTransactionsError(message);
        setInsiderTransactions([]);
        setIsLoadingInsiderTransactions(false);
      });
  }, [ticker]);

  // Load subscription for this ticker (for email preference toggle)
  const refreshSubscriptionForTicker = useCallback(async () => {
    if (!user || !ticker) {
      setSubscriptionForTicker(null);
      return;
    }
    try {
      const list = await subscriptionApi.list();
      const sub = list.find((s) => s.ticker.toUpperCase() === ticker.toUpperCase()) ?? null;
      setSubscriptionForTicker(sub);
    } catch {
      setSubscriptionForTicker(null);
    }
  }, [user, ticker]);

  useEffect(() => {
    refreshSubscriptionForTicker();
  }, [refreshSubscriptionForTicker]);

  const handleEmailUpdatesToggle = useCallback(
    async (email_updates: boolean) => {
      if (!ticker) return;
      setEmailPreferenceToggling(true);
      try {
        const updated = await subscriptionApi.updateEmailPreference(ticker, email_updates);
        setSubscriptionForTicker(updated);
      } finally {
        setEmailPreferenceToggling(false);
      }
    },
    [ticker]
  );

  // Load news data when news tab is active
  useEffect(() => {
    if (activeTab === 'news' && ticker && !isLoadingNews) {
      fetchNews();
    }
  }, [activeTab, ticker, fetchNews]);

  useEffect(() => {
    if (activeTab === 'news' && ticker && !isLoadingInsiderTransactions) {
      fetchInsiderTransactions();
    }
  }, [activeTab, ticker, fetchInsiderTransactions]);

  // Load SEC EDGAR filings when SEC Filings tab is active (US companies only)
  useEffect(() => {
    if (activeTab !== 'sec-filings' || !ticker) return;
    let cancelled = false;
    setIsLoadingEdgar(true);
    setEdgarFilingsError(null);
    stockApi
      .getEdgarFilings(ticker)
      .then((data) => {
        if (!cancelled) {
          setEdgarFilings(data);
          if (data.error) setEdgarFilingsError(data.error);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const message = err.response?.data?.detail ?? err.message ?? 'Unable to load SEC filings.';
          setEdgarFilingsError(message);
          setEdgarFilings(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingEdgar(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, ticker]);

  const handleGenerateReport = async (source: 'fresh' | 'generate' = 'fresh') => {
    if (!ticker) return;
    setAnalysisError(null);
    if (!user) {
      setAuthModalMessage(
        source === 'generate'
          ? 'Please sign in to generate an analysis report.'
          : 'Please sign in to run a fresh analysis.'
      );
      setAuthModalOpen(true);
      return;
    }
    try {
      await stockApi.startAnalysis(ticker);
      setAnalysisError(null);
      await loadStockData();
    } catch (error: unknown) {
      const axiosError = error as { response?: { status?: number; data?: { detail?: string | string[] } } };
      const detail = axiosError.response?.data?.detail;
      const message = typeof detail === 'string'
        ? detail
        : Array.isArray(detail) && detail.length > 0
          ? String(detail[0])
          : axiosError.response?.status === 402
            ? 'Insufficient token balance. Need 200 tokens to create a report.'
            : 'Failed to start analysis. Please try again.';
      setAnalysisError(message);
      console.error('Failed to start analysis:', error);
    }
  };

  const formatNumber = (value: number | null | undefined, decimals: number = 2): string => {
    if (value === null || value === undefined) return 'N/A';
    if (value >= 1e12) return `$${(value / 1e12).toFixed(decimals)}T`;
    if (value >= 1e9) return `$${(value / 1e9).toFixed(decimals)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(decimals)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(decimals)}K`;
    return `$${value.toFixed(decimals)}`;
  };

  const formatPercent = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(2)}%`;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-layout mx-auto px-6 py-8">
          <div className="animate-pulse">
            <div className="h-12 bg-gray-800 rounded mb-6"></div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="h-96 bg-gray-800 rounded"></div>
              <div className="h-96 bg-gray-800 rounded"></div>
              <div className="h-96 bg-gray-800 rounded"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!stockData) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-layout mx-auto">
          <div className="bg-gray-800 rounded-lg border border-amber-500/30 p-12 text-center max-w-lg mx-auto">
            <div className="text-5xl mb-4 opacity-80" aria-hidden>⚠</div>
            <h2 className="text-2xl font-bold text-white mb-2">Ticker not found</h2>
            <p className="text-gray-300 mb-1 font-mono text-lg">{ticker}</p>
            <p className="text-gray-400 mb-6">
              {loadError ?? `No stock data for "${ticker}". Check the symbol and try again.`}
            </p>
            <button
              onClick={() => navigate('/')}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Back to Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Order reports by TradingAgents process flow (analyst chain → debate → research manager → risk)
  const REPORT_PROCESS_ORDER = [
    'market_report',
    'sentiment_report',
    'news_report',
    'technical_report',
    'fundamentals_report',
    'sec_report',
    'investment_plan',
    'trader_investment_plan',
    'final_trade_decision',
  ];

  const allReports = Object.keys(stockData.reports || {});
  const availableReports = [...allReports].sort((a, b) => {
    const idxA = REPORT_PROCESS_ORDER.indexOf(a);
    const idxB = REPORT_PROCESS_ORDER.indexOf(b);
    if (idxA === -1 && idxB === -1) return a.localeCompare(b);
    if (idxA === -1) return 1;
    if (idxB === -1) return -1;
    return idxA - idxB;
  });
  
  // Get current report content and score
  const currentReportData = selectedReport && stockData.reports_with_scores 
    ? stockData.reports_with_scores[selectedReport]
    : null;
  const currentReportContent = currentReportData?.content || (selectedReport ? stockData.reports[selectedReport] : null);
  const currentReportScore = currentReportData?.score;
  const currentReportScoreLabel = currentReportData?.score_label;
  
  // Build report scores map for tabs
  const reportScores: Record<string, { score: number | null; score_label: string | null }> = {};
  if (stockData.reports_with_scores) {
    Object.entries(stockData.reports_with_scores).forEach(([key, value]) => {
      reportScores[key] = {
        score: value.score,
        score_label: value.score_label
      };
    });
  }
  // Models used for this analysis (same across all reports from one run)
  const modelsUsed = stockData.reports_with_scores
    ? (Object.values(stockData.reports_with_scores).find((r) => r.models_used)?.models_used ?? null)
    : null;
  const quote = refreshedQuote ?? stockData.quote;

  // Format last update time
  const lastUpdateTime = quote?.last_update_time 
    ? new Date(quote.last_update_time).toLocaleString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      })
    : '';

  return (
    <>
    <div className="min-h-screen p-8 min-w-0">
      <div className="w-full min-w-0 px-6">
        <div className="w-full max-w-6xl mx-auto space-y-6 min-w-0">
            {/* Top Header with Price */}
            <div className="bg-gray-800 border-b border-gray-700 rounded-lg overflow-hidden">
              <div className="px-4 sm:px-6 py-6 min-w-0">
                <div className="min-w-0 flex flex-wrap items-start justify-between gap-4">
                  <h1 className="text-xl sm:text-2xl font-semibold text-white mb-1 break-words">
                    {companyInfo?.name || stockData.ticker} ({stockData.ticker})
                  </h1>
                  <div className="flex flex-wrap items-center gap-3 shrink-0">
                    {ticker && (
                      <SubscribeButton
                        ticker={ticker}
                        onSubscribed={refreshSubscriptionForTicker}
                        onUnsubscribed={() => setSubscriptionForTicker(null)}
                      />
                    )}
                    {subscriptionForTicker && (
                      <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400">
                        <span>Email updates</span>
                        <input
                          type="checkbox"
                          checked={subscriptionForTicker.email_updates}
                          disabled={emailPreferenceToggling}
                          onChange={(e) => handleEmailUpdatesToggle(e.target.checked)}
                          className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
                        />
                      </label>
                    )}
                  </div>
                </div>
                  {quote && (
                    <>
                      <div className="flex flex-wrap items-baseline gap-2 sm:gap-4 mt-2 min-w-0">
                        <div
                          className={`inline-block px-2 py-0.5 rounded shrink-0 text-3xl sm:text-5xl font-bold text-white ${priceFlash ? 'animate-price-flash' : ''}`}
                        >
                          ${quote.current_price.toFixed(2)}
                        </div>
                        <div className={`text-lg sm:text-2xl font-semibold flex items-center gap-1 shrink-0 ${
                          quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          <span>{quote.daily_change_percent >= 0 ? '▲' : '▼'}</span>
                          <span>
                            ({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%){' '}
                            {quote.daily_change >= 0 ? '+' : ''}{quote.daily_change.toFixed(2)}
                          </span>
                        </div>
                      </div>
                      <div className="text-sm text-gray-400 mt-2">
                        Price as of {lastUpdateTime}
                      </div>
                    </>
                  )}
                </div>
              </div>

            {/* Tab views: tabs wrap to new lines on narrow screens */}
            <div className="border-b border-gray-700 min-w-0">
              <nav className="flex flex-wrap gap-1" aria-label="Stock page sections">
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
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`px-4 py-3 text-sm rounded-t-lg transition-colors border-b-2 -mb-px ${
                        isActive
                          ? isAiTab
                            ? 'bg-blue-950/70 text-blue-200 border-blue-500 font-semibold'
                            : 'bg-gray-800 text-white border-blue-500 font-medium'
                          : isAiTab
                            ? 'bg-blue-950/40 text-blue-200 hover:text-white hover:bg-blue-950/60 border-blue-700/50 font-semibold'
                            : 'text-gray-400 hover:text-white hover:bg-gray-800/70 border-transparent font-medium'
                      }`}
                    >
                      <span className="inline-flex items-center gap-1.5">
                        {tab.label}
                      </span>
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Tab content */}
            <div>
            {/* Fundamentals Tab Content */}
            {activeTab === 'fundamentals' && (
              <div className="mb-6 space-y-6">
                {/* Sub-tabs: Statements, Charts — data loaded on demand when tab is active */}
                <div className="flex gap-2 border-b border-gray-700 pb-3">
                  <button
                    type="button"
                    onClick={() => setFundamentalsSubTab('charts')}
                    className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                      fundamentalsSubTab === 'charts'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    Charts
                  </button>
                  <button
                    type="button"
                    onClick={() => setFundamentalsSubTab('statements')}
                    className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                      fundamentalsSubTab === 'statements'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    Financial Statements
                  </button>
                </div>

                {fundamentalsSubTab === 'charts' && ticker && (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <FundamentalCharts ticker={ticker} />
                  </div>
                )}

                {fundamentalsSubTab === 'statements' &&
                  (isLoadingFundamentals ? (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                      <div className="animate-pulse">
                        <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                        <div className="h-64 bg-gray-700 rounded"></div>
                      </div>
                    </div>
                  ) : financialStatements ? (
                    <div className="space-y-6">
                      {/* Cash Flow Statement - Show first as requested */}
                      {financialStatements.cashflow && (
                        <FinancialStatementViewer
                          data={financialStatements.cashflow}
                          statementType="cashflow"
                        />
                      )}
                      {financialStatements.balance_sheet && (
                        <FinancialStatementViewer
                          data={financialStatements.balance_sheet}
                          statementType="balance_sheet"
                        />
                      )}
                      {financialStatements.income_statement && (
                        <FinancialStatementViewer
                          data={financialStatements.income_statement}
                          statementType="income_statement"
                        />
                      )}
                    </div>
                  ) : (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                      <div className="text-gray-400 text-sm">No financial statements available</div>
                    </div>
                  ))}
              </div>
            )}

            {/* Overview Tab Content */}
            {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="flex flex-col lg:flex-row gap-6 items-stretch">
                {/* Key Data: fixed width so chart gets the rest */}
                <div className="lg:w-80 shrink-0">
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 h-full">
                    <h2 className="text-lg font-semibold text-white mb-4">Key Data Points</h2>
                    <div className="space-y-4">
                      {quote && (
                        <>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Current Price</span>
                            <span className="text-sm font-semibold text-white">
                              ${quote.current_price.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Daily Change</span>
                            <span className={`text-sm font-semibold ${
                              quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              ({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%) 
                              {quote.daily_change >= 0 ? '+' : ''}${quote.daily_change.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Day's Range</span>
                            <span className="text-sm font-semibold text-white">
                              ${quote.day_low?.toFixed(2) || 'N/A'} - ${quote.day_high?.toFixed(2) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Previous Close</span>
                            <span className="text-sm font-semibold text-white">
                              ${quote.previous_close?.toFixed(2) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Open</span>
                            <span className="text-sm font-semibold text-white">
                              ${quote.current_price.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Bid</span>
                            <span className="text-sm font-semibold text-white">
                              {quote.bid_price != null ? `$${quote.bid_price.toFixed(2)}` : 'N/A'}
                              {quote.bid_size != null ? ` ×${quote.bid_size}` : ''}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Ask</span>
                            <span className="text-sm font-semibold text-white">
                              {quote.ask_price != null ? `$${quote.ask_price.toFixed(2)}` : 'N/A'}
                              {quote.ask_size != null ? ` ×${quote.ask_size}` : ''}
                            </span>
                          </div>
                          {hasFundamentals && (
                            <div className="flex items-start justify-between">
                              <span className="text-sm text-gray-400">Beta</span>
                              <span className="text-sm font-semibold text-white">
                                {extendedInfo?.beta?.toFixed(2) || 'N/A'}
                              </span>
                            </div>
                          )}
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Volume</span>
                            <span className="text-sm font-semibold text-white">
                              {quote.volume ? quote.volume.toLocaleString() : 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">Average Volume</span>
                            <span className="text-sm font-semibold text-white">
                              {extendedInfo?.average_volume ? extendedInfo.average_volume.toLocaleString() : 'N/A'}
                            </span>
                          </div>
                          {hasFundamentals && (
                            <div className="flex items-start justify-between">
                              <span className="text-sm text-gray-400">Sector</span>
                              <span className="text-sm font-semibold text-white">
                                {companyInfo?.sector || 'N/A'}
                              </span>
                            </div>
                          )}
                          {hasFundamentals && (
                            <div className="flex items-start justify-between">
                              <span className="text-sm text-gray-400">Market Cap</span>
                                <span className="text-sm font-semibold text-white">
                                  {formatNumber(extendedInfo?.market_cap)}
                                </span>
                            </div>
                          )}
                          <div className="flex items-start justify-between">
                            <span className="text-sm text-gray-400">52wk Range</span>
                            <span className="text-sm font-semibold text-white">
                              {quote.fifty_two_week_low && quote.fifty_two_week_high
                                ? `$${quote.fifty_two_week_low.toFixed(2)} - $${quote.fifty_two_week_high.toFixed(2)}`
                                : 'N/A'}
                            </span>
                          </div>
                          {hasFundamentals && (
                            <>
                              <div className="flex items-start justify-between">
                                <span className="text-sm text-gray-400">Revenue</span>
                                <span className="text-sm font-semibold text-white">
                                  {formatNumber(extendedInfo?.revenue)}
                                </span>
                              </div>
                              <div className="flex items-start justify-between">
                                <span className="text-sm text-gray-400">Gross Margin</span>
                                <span className="text-sm font-semibold text-white">
                                  {formatPercent(extendedInfo?.gross_margin)}
                                </span>
                              </div>
                              <div className="flex items-start justify-between">
                                <span className="text-sm text-gray-400">Dividend Yield</span>
                                <span className="text-sm font-semibold text-white">
                                  {formatPercent(extendedInfo?.dividend_yield)}
                                </span>
                              </div>
                              <div className="flex items-start justify-between">
                                <span className="text-sm text-gray-400">EPS</span>
                                <span className="text-sm font-semibold text-white">
                                  {extendedInfo?.trailing_eps?.toFixed(2) || 'N/A'}
                                </span>
                              </div>
                            </>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Price Chart: fills all remaining space */}
                <div className="flex-1 min-w-0 min-h-[33vh] flex flex-col">
                  {quote && (
                    <div className="flex-1 min-h-0 flex flex-col">
                      <PriceTrendWidget ticker={stockData.ticker} fillTile />
                    </div>
                  )}
                </div>
              </div>

              {/* Future Events */}
              {isLoadingFutureEvents ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="animate-pulse">
                    <div className="h-6 bg-gray-700 rounded w-40 mb-4"></div>
                    <div className="h-24 bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : futureEvents && (futureEvents.events?.length ?? 0) > 0 ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <h2 className="text-lg font-semibold text-white mb-4">Upcoming Events (Yahoo Finance)</h2>
                  <ul className="space-y-3">
                    {futureEvents.events.map((evt, i) => (
                      <li key={`${evt.date}-${evt.type}-${i}`} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${
                            evt.type === 'earnings' ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'
                          }`}>
                            {evt.type === 'earnings' ? 'Earnings' : 'Ex-dividend'}
                          </span>
                          <span className="text-gray-300">{evt.label}</span>
                        </div>
                        <span className="text-white font-medium">{new Date(evt.date).toLocaleDateString(undefined, { dateStyle: 'medium' })}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : futureEvents && (futureEvents.events?.length === 0 || !futureEvents.events) ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <h2 className="text-lg font-semibold text-white mb-2">Upcoming Events (Yahoo Finance)</h2>
                  <p className="text-gray-400 text-sm">No upcoming earnings or ex-dividend dates available.</p>
                </div>
              ) : null}

              {/* Summary pane: fundamentals for equities; ETF details for ETFs; message for index/currency/crypto */}
              {quoteType === 'ETF' ? (
                isLoadingFundInfo ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                    <div className="animate-pulse">
                      <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                      <div className="h-64 bg-gray-700 rounded"></div>
                    </div>
                  </div>
                ) : fundInfo ? (
                  <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 space-y-6">
                    <h2 className="text-lg font-semibold text-white">ETF / Fund details</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      {fundInfo.totalAssets != null && (
                        <div>
                          <p className="text-sm text-gray-400 mb-1">Assets under management</p>
                          <p className="text-white font-semibold">{formatNumber(fundInfo.totalAssets)}</p>
                        </div>
                      )}
                      {fundInfo.expenseRatio != null && (
                        <div>
                          <p className="text-sm text-gray-400 mb-1">Expense ratio</p>
                          <p className="text-white font-semibold">{formatPercent(fundInfo.expenseRatio)}</p>
                        </div>
                      )}
                      {fundInfo.category && (
                        <div>
                          <p className="text-sm text-gray-400 mb-1">Category</p>
                          <p className="text-white font-semibold">{fundInfo.category}</p>
                        </div>
                      )}
                      {fundInfo.yield != null && (
                        <div>
                          <p className="text-sm text-gray-400 mb-1">Yield</p>
                          <p className="text-white font-semibold">{formatPercent(fundInfo.yield)}</p>
                        </div>
                      )}
                      {fundInfo.fundInception != null && (
                        <div>
                          <p className="text-sm text-gray-400 mb-1">Inception</p>
                          <p className="text-white font-semibold">
                            {typeof fundInfo.fundInception === 'number'
                              ? new Date(fundInfo.fundInception).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                              : typeof fundInfo.fundInception === 'string' && !Number.isNaN(Date.parse(fundInfo.fundInception))
                                ? new Date(fundInfo.fundInception).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                                : String(fundInfo.fundInception)}
                          </p>
                        </div>
                      )}
                    </div>
                    {fundInfo.description && (
                      <div>
                        <p className="text-sm text-gray-400 mb-1">Description</p>
                        <p className="text-gray-300 text-sm leading-relaxed">{fundInfo.description}</p>
                      </div>
                    )}
                    {fundInfo.sector_weightings && Object.keys(fundInfo.sector_weightings).length > 0 && (
                      <div>
                        <p className="text-sm text-gray-400 mb-2">Sector weightings</p>
                        <div className="space-y-1">
                          {Object.entries(fundInfo.sector_weightings).map(([name, pct]) => (
                            <div key={name} className="flex items-center gap-2">
                              <span className="text-gray-300 text-sm w-40 truncate">{name}</span>
                              <div className="flex-1 h-2 bg-gray-700 rounded overflow-hidden">
                                <div className="h-full bg-blue-500 rounded" style={{ width: `${Math.min(100, Math.max(0, Number(pct) * 100))}%` }} />
                              </div>
                              <span className="text-white text-sm font-medium w-12 text-right">{(Number(pct) * 100).toFixed(1)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {fundInfo.asset_classes && Object.keys(fundInfo.asset_classes).length > 0 && (
                      <div>
                        <p className="text-sm text-gray-400 mb-2">Asset allocation</p>
                        <div className="flex flex-wrap gap-3">
                          {Object.entries(fundInfo.asset_classes).map(([name, pct]) => (
                            <span key={name} className="text-gray-300 text-sm">
                              {name}: <span className="text-white font-medium">{(Number(pct) * 100).toFixed(1)}%</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {fundInfo.top_holdings && fundInfo.top_holdings.length > 0 && (
                      <div>
                        <p className="text-sm text-gray-400 mb-2">Top holdings</p>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-gray-400 border-b border-gray-600">
                                {Object.keys(fundInfo.top_holdings[0]).map((k) => (
                                  <th key={k} className="py-2 pr-4 capitalize">{k.replace(/_/g, ' ')}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {fundInfo.top_holdings.slice(0, 10).map((row, i) => (
                                <tr key={i} className="border-b border-gray-700/50">
                                  {Object.values(row).map((v, j) => (
                                    <td key={j} className="py-2 pr-4 text-white">{String(v ?? '—')}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null
              ) : !hasFundamentals ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <p className="text-gray-400 text-sm">Fundamental data and financial metrics are available for equities only.</p>
                </div>
              ) : isLoadingFundamentals ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="animate-pulse">
                    <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                    <div className="h-64 bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : fundamentalsData && typeof fundamentalsData === 'object' ? (
                <FundamentalPanes
                  data={fundamentalsData}
                  analystRecommendations={analystRecommendations}
                  isLoadingRecommendations={isLoadingRecommendations}
                />
              ) : null}
            </div>
            )}

            {/* AI Analysis Tab Content */}
            {activeTab === 'ai-analysis' && (
              <div className="space-y-6">
                {/* Lock gate for non-logged-in users on non-preview stocks */}
                {!user && !previewTickers.has((ticker ?? '').toUpperCase()) ? (
                  <div className="flex flex-col items-center justify-center py-20 rounded-lg border border-gray-700 bg-gray-800/60">
                    <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    <h3 className="text-lg font-semibold text-white mb-2">Sign in to view AI Analysis</h3>
                    <p className="text-gray-400 text-sm mb-6 text-center max-w-xs">
                      Create a free account to access AI-powered stock analysis reports.
                    </p>
                    <button
                      onClick={() => { setAuthModalMessage('Sign in to access AI analysis reports.'); setAuthModalOpen(true); }}
                      className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
                    >
                      Sign In / Register
                    </button>
                  </div>
                ) : (
                  <>
                <p className="text-sm text-amber-400/90 bg-amber-950/30 border border-amber-700/40 rounded-lg px-4 py-2">
                  For informational purposes only. Not investment advice.
                </p>
                {analysisError && (
                  <div className="flex items-center gap-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-red-200" role="alert">
                    <svg className="h-5 w-5 shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>{analysisError}</span>
                    <button
                      type="button"
                      onClick={() => setAnalysisError(null)}
                      className="ml-auto rounded p-1 text-red-300 hover:bg-red-900/50 hover:text-red-100"
                      aria-label="Dismiss"
                    >
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                )}
                {/* Analysis Summary Header */}
                {stockData.has_reports && stockData.report_date && (() => {
                  const summaryScoreEntries = getAnalysisScoreEntries(stockData.reports_with_scores ?? null);
                  return (
                  <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg border border-blue-700/50 p-6">
                    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                      <div className="flex-1">
                        <div className="text-sm text-gray-400 mb-1">Last Analysis Date</div>
                        <div className="text-lg font-semibold text-white">
                          {parseReportDate(stockData.report_date)?.toLocaleDateString('en-US', {
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric'
                              }) ?? 'N/A'}
                        </div>
                        {modelsUsed && (modelsUsed.provider || modelsUsed.deep_think || modelsUsed.quick_think) && (
                          <div className="text-sm text-gray-400 mt-1">
                            Generated by {[modelsUsed.provider && modelsUsed.provider, modelsUsed.deep_think && modelsUsed.deep_think, modelsUsed.quick_think && modelsUsed.quick_think].filter(Boolean).join(', ')}
                            {stockData.report_days_ago != null && stockData.report_days_ago > 7 && (
                              <span className="text-amber-400/90 ml-1">Consider re-running for fresh insights.</span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Radar chart + decision side by side */}
                      <div className="flex items-center gap-6 shrink-0">
                        {summaryScoreEntries.length >= 3 && (
                          <AspectSpiderChart scoreEntries={summaryScoreEntries} size={80} />
                        )}
                        <div className="text-right">
                          <div className="text-sm text-gray-400 mb-1">AI Decision</div>
                          <div className={`text-2xl font-bold ${
                            stockData.recommendation?.recommendation === 'BUY'
                              ? 'text-green-400'
                              : stockData.recommendation?.recommendation === 'SELL'
                              ? 'text-red-400'
                              : stockData.recommendation?.recommendation === 'HOLD'
                              ? 'text-yellow-400'
                              : 'text-white'
                          }`}>
                            {stockData.recommendation?.recommendation || 'N/A'}
                          </div>
                          {stockData.recommendation?.confidence && (
                            <div className="text-xs text-gray-400 mt-1">
                              Confidence: {(stockData.recommendation.confidence * 100).toFixed(0)}%
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 pt-4 border-t border-gray-600/50 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div className="flex flex-col gap-1">
                        {(stockData.expected_return_pct != null || stockData.bear_case_return_pct != null || stockData.bull_case_return_pct != null) && (
                          <div className="flex flex-wrap gap-6">
                            {stockData.expected_return_pct != null && (
                              <div>
                                <span className="text-sm text-gray-400">Expected: </span>
                                <span className={stockData.expected_return_pct >= 0 ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                                  {stockData.expected_return_pct >= 0 ? '+' : ''}{stockData.expected_return_pct.toFixed(2)}%
                                </span>
                              </div>
                            )}
                            {stockData.bear_case_return_pct != null && (
                              <div>
                                <span className="text-sm text-gray-400">Bear: </span>
                                <span className="text-red-400 font-semibold">
                                  {stockData.bear_case_return_pct >= 0 ? '+' : ''}{stockData.bear_case_return_pct.toFixed(2)}%
                                </span>
                              </div>
                            )}
                            {stockData.bull_case_return_pct != null && (
                              <div>
                                <span className="text-sm text-gray-400">Bull: </span>
                                <span className="text-green-400 font-semibold">
                                  {stockData.bull_case_return_pct >= 0 ? '+' : ''}{stockData.bull_case_return_pct.toFixed(2)}%
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                        {(stockData.report_view_count != null || stockData.report_earned_tokens != null) && (
                          <div className="flex flex-wrap gap-4 text-sm text-gray-400">
                            {stockData.report_view_count != null && (
                              <span title="Unique authenticated views of this report">
                                {stockData.report_view_count} unique view{stockData.report_view_count !== 1 ? 's' : ''}
                              </span>
                            )}
                            {stockData.report_earned_tokens != null && (
                              <span title="Tokens earned by the report creator from views (max 400 per report)">
                                {stockData.report_earned_tokens} tokens earned
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      {!stockData.is_generating && (
                        <button
                          onClick={() => handleGenerateReport('fresh')}
                          className="shrink-0 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                          Run Fresh Analysis
                        </button>
                      )}
                    </div>
                  </div>
                  );
                })()}

                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  {stockData.has_reports && !stockData.is_generating && (
                    <div>
                      <ReportTabs
                        availableReports={availableReports}
                        selectedReport={selectedReport}
                        onSelectReport={setSelectedReport}
                        reportScores={reportScores}
                      />
                      <div className="mt-6">
                        <ReportViewer
                          content={currentReportContent}
                          score={currentReportScore}
                          scoreLabel={currentReportScoreLabel}
                          keyTakeaways={currentReportData?.key_takeaways}
                          reportType={selectedReport}
                          bullViewpoint={currentReportData?.bull_viewpoint}
                          bearViewpoint={currentReportData?.bear_viewpoint}
                          riskyViewpoint={currentReportData?.risky_viewpoint}
                          safeViewpoint={currentReportData?.safe_viewpoint}
                          neutralViewpoint={currentReportData?.neutral_viewpoint}
                        />
                      </div>
                    </div>
                  )}
                  {!stockData.has_reports && !stockData.is_generating && (
                    <div className="text-center py-8">
                      <p className="text-gray-400 mb-4">No analysis reports available yet.</p>
                      <button
                        onClick={() => handleGenerateReport('generate')}
                        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
                      >
                        Generate Analysis Report →
                      </button>
                    </div>
                  )}
                  {stockData.is_generating && (
                    <AIAnalysisLoadingView
                      existingReportKeys={Object.keys(stockData.reports || {})}
                      agentStatuses={analysisProgress?.agent_statuses ?? null}
                      currentAgent={analysisProgress?.current_agent ?? null}
                    />
                  )}
                </div>
                  </>
                )}
              </div>
            )}

            {/* News Tab Content */}
            {activeTab === 'news' && (
              <div className="space-y-6 min-h-[100vh] flex flex-col">
                {/* News Section - longer pane with internal scroll */}
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 flex-1 min-h-0 flex flex-col overflow-hidden">
                  <h2 className="text-xl font-semibold text-white mb-4 shrink-0">Latest News</h2>
                  <div className="flex-1 min-h-0 overflow-y-auto">
                    {isLoadingNews ? (
                      <div className="animate-pulse">
                        <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                        <div className="space-y-4">
                          {[1, 2, 3].map((i) => (
                            <div key={i} className="h-24 bg-gray-700 rounded"></div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <NewsWidget
                        articles={newsData}
                        ticker={stockData.ticker}
                        onRetry={fetchNews}
                        isLoading={isLoadingNews}
                        errorMessage={newsError}
                      />
                    )}
                  </div>
                </div>
                <div className="flex-1 min-h-0">
                  {isLoadingInsiderTransactions ? (
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                      <div className="animate-pulse">
                        <div className="h-6 bg-gray-700 rounded w-64 mb-4"></div>
                        <div className="space-y-4">
                          {[1, 2, 3].map((i) => (
                            <div key={i} className="h-12 bg-gray-700 rounded"></div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <InsiderTransactionsWidget
                      transactions={insiderTransactions}
                      ticker={stockData.ticker}
                      onRetry={fetchInsiderTransactions}
                      isLoading={isLoadingInsiderTransactions}
                      errorMessage={insiderTransactionsError}
                    />
                  )}
                </div>
              </div>
            )}

            {/* SEC Filings Tab Content (US companies only) */}
            {activeTab === 'sec-filings' && (
              <div className="space-y-6">
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <h2 className="text-xl font-semibold text-white mb-4">SEC EDGAR Filings</h2>
                  <p className="text-sm text-gray-400 mb-4">
                    Quarterly (10-Q) and annual (10-K) reports filed with the U.S. Securities and Exchange Commission.
                  </p>
                  {isLoadingEdgar ? (
                    <div className="animate-pulse">
                      <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                      <div className="h-64 bg-gray-700 rounded"></div>
                    </div>
                  ) : edgarFilingsError ? (
                    <p className="text-amber-400 text-sm">{edgarFilingsError}</p>
                  ) : edgarFilings && edgarFilings.filings.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-gray-600 text-gray-400">
                            <th className="py-2 pr-4 font-medium">Form</th>
                            <th className="py-2 pr-4 font-medium">Filing Date</th>
                            <th className="py-2 font-medium">Filing</th>
                          </tr>
                        </thead>
                        <tbody>
                          {edgarFilings.filings.map((f) => (
                            <tr key={f.accession_number} className="border-b border-gray-700">
                              <td className="py-3 pr-4">
                                <span className="font-medium text-white">{f.form}</span>
                              </td>
                              <td className="py-3 pr-4 text-gray-300">{f.filing_date}</td>
                              <td className="py-3">
                                {f.url ? (
                                  <a
                                    href={f.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-400 hover:text-blue-300 underline"
                                  >
                                    View on SEC.gov
                                  </a>
                                ) : (
                                  <span className="text-gray-500">{f.description}</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-gray-400 text-sm">No SEC filings found for this symbol.</p>
                  )}
                </div>
              </div>
            )}

            </div>
        </div>
      </div>
    </div>
    {authModalOpen && (
      <AuthModal
        onClose={() => setAuthModalOpen(false)}
        message={authModalMessage}
      />
    )}
    </>
  );
}
