import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { stockApi } from '../services/api';
import { WebSocketClient } from '../services/websocket';
import type { StockPageData } from '../services/types';
import { useQuoteRefresh } from '../hooks/useQuoteRefresh';
import ReportTabs from '../components/ReportTabs';
import ReportViewer from '../components/ReportViewer';
import PriceTrendWidget from '../components/PriceTrendWidget';
import FinancialStatementViewer from '../components/FinancialStatementViewer';
import FundamentalCharts from '../components/FundamentalCharts';
import FundamentalPanes from '../components/FundamentalPanes';
import NewsWidget from '../components/NewsWidget';
import AIAnalysisLoadingView from '../components/AIAnalysisLoadingView';
import { parseReportDate } from '../utils/date';

interface CompanyInfo {
  name: string;
  sector: string;
  industry: string;
  exchange: string;
  country: string;
  website: string;
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
  const [analystRecommendations, setAnalystRecommendations] = useState<any>(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [fundamentalsSubTab, setFundamentalsSubTab] = useState<'statements' | 'charts'>('charts');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<{
    agent_statuses: Record<string, string>;
    current_agent?: string | null;
  } | null>(null);

  const refreshedQuote = useQuoteRefresh(ticker ?? '', 60000);
  const prevPriceRef = useRef<number | null>(null);
  const [priceFlash, setPriceFlash] = useState(false);

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
    stockApi.getCompanyInfo(ticker).then(setCompanyInfo).catch((e) => console.error('Failed to load company info:', e));
    stockApi.getExtendedInfo(ticker).then(setExtendedInfo).catch((e) => console.error('Failed to load extended info:', e));
    setIsLoadingRecommendations(true);
    stockApi.getAnalystRecommendations(ticker)
      .then(setAnalystRecommendations)
      .catch((e) => console.error('Failed to load analyst recommendations:', e))
      .finally(() => setIsLoadingRecommendations(false));
    // Fundamentals for overview summary pane (not statements/charts — those load on Fundamentals tab)
    setIsLoadingFundamentals(true);
    stockApi.getFundamentals(ticker)
      .then((r) => r && setFundamentalsData(r.fundamentals))
      .catch((e) => console.error('Failed to load fundamentals:', e))
      .finally(() => setIsLoadingFundamentals(false));
  };

  useEffect(() => {
    if (ticker) {
      setNewsData([]);
      setNewsError(null); // Clear news when ticker changes so we don't show previous stock's news
      setFundamentalsSubTab('charts'); // Reset when ticker changes
      setAnalysisProgress(null);
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

  // Load financial statements only when Fundamentals tab is active (on demand; fundamentals for overview are fetched on landing)
  useEffect(() => {
    if (activeTab !== 'fundamentals' || !ticker || financialStatements) return;
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
  }, [activeTab, ticker, fundamentalsData, financialStatements, isLoadingFundamentals]);

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

  // Load news data when news tab is active
  useEffect(() => {
    if (activeTab === 'news' && ticker && !isLoadingNews) {
      fetchNews();
    }
  }, [activeTab, ticker, fetchNews]);

  const handleGenerateReport = async () => {
    if (!ticker) return;
    
    try {
      await stockApi.startAnalysis(ticker);
      await loadStockData();
    } catch (error) {
      console.error('Failed to start analysis:', error);
      alert('Failed to start analysis. Please try again.');
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
    'fundamentals_report',
    'technical_report',
    'investment_plan',
    'final_trade_decision',
  ];

  const allReports = Object.keys(stockData.reports || {}).filter((r) => r !== 'trader_investment_plan');
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
    <div className="min-h-screen p-8 min-w-0">
      <div className="w-full min-w-0 px-6">
        <div className="w-full max-w-6xl mx-auto space-y-6 min-w-0">
            {/* Back to Stocks - above stock name tile */}
            <button
              onClick={() => navigate('/')}
              className="text-gray-400 hover:text-white text-sm font-medium"
            >
              ← Back to Stocks
            </button>

            {/* Top Header with Price */}
            <div className="bg-gray-800 border-b border-gray-700 rounded-lg overflow-hidden">
              <div className="px-4 sm:px-6 py-6 min-w-0">
                <div className="min-w-0">
                  <h1 className="text-xl sm:text-2xl font-semibold text-white mb-1 break-words">
                    {companyInfo?.name || stockData.ticker} ({stockData.ticker})
                  </h1>
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
            </div>

            {/* Tab views: tabs wrap to new lines on narrow screens */}
            <div className="border-b border-gray-700 min-w-0">
              <nav className="flex flex-wrap gap-1" aria-label="Stock page sections">
                {[
                  { id: 'overview', label: 'Overview' },
                  { id: 'ai-analysis', label: 'AI Analysis' },
                  { id: 'fundamentals', label: 'Fundamentals' },
                  { id: 'news', label: 'News' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-4 py-3 text-sm font-medium rounded-t-lg transition-colors border-b-2 -mb-px ${
                      activeTab === tab.id
                        ? 'bg-gray-800 text-white border-blue-500'
                        : 'text-gray-400 hover:text-white hover:bg-gray-800/70 border-transparent'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
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
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Current Price</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              ${quote.current_price.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Daily Change</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className={`text-sm font-semibold ${
                              quote.daily_change_percent >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              ({quote.daily_change_percent >= 0 ? '+' : ''}{quote.daily_change_percent.toFixed(2)}%) 
                              {quote.daily_change >= 0 ? '+' : ''}${quote.daily_change.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Day's Range</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              ${quote.day_low?.toFixed(2) || 'N/A'} - ${quote.day_high?.toFixed(2) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Previous Close</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              ${quote.previous_close?.toFixed(2) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Open</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              ${quote.current_price.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Bid</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {quote.bid_price != null ? `$${quote.bid_price.toFixed(2)}` : 'N/A'}
                              {quote.bid_size != null ? ` ×${quote.bid_size}` : ''}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Ask</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {quote.ask_price != null ? `$${quote.ask_price.toFixed(2)}` : 'N/A'}
                              {quote.ask_size != null ? ` ×${quote.ask_size}` : ''}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Beta</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {extendedInfo?.beta?.toFixed(2) || 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Volume</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {quote.volume ? quote.volume.toLocaleString() : 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Average Volume</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {extendedInfo?.average_volume ? extendedInfo.average_volume.toLocaleString() : 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Sector</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {companyInfo?.sector || 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Market Cap</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {formatNumber(extendedInfo?.market_cap)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">52wk Range</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {quote.fifty_two_week_low && quote.fifty_two_week_high
                                ? `$${quote.fifty_two_week_low.toFixed(2)} - $${quote.fifty_two_week_high.toFixed(2)}`
                                : 'N/A'}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Revenue</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {formatNumber(extendedInfo?.revenue)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Gross Margin</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {formatPercent(extendedInfo?.gross_margin)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Dividend Yield</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {formatPercent(extendedInfo?.dividend_yield)}
                            </span>
                          </div>
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">EPS</span>
                              <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <span className="text-sm font-semibold text-white">
                              {extendedInfo?.trailing_eps?.toFixed(2) || 'N/A'}
                            </span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Price Chart: fills all remaining space */}
                <div className="flex-1 min-w-0 min-h-[33vh]">
                  {quote && (
                    <PriceTrendWidget ticker={stockData.ticker} fillTile />
                  )}
                </div>
              </div>

              {/* Analyst Recommendations */}
              {isLoadingRecommendations ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="animate-pulse">
                    <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                    <div className="h-32 bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : analystRecommendations && analystRecommendations.recommendation ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <h2 className="text-lg font-semibold text-white mb-4">Analyst Recommendations (Yahoo Finance)</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <div className="mb-4">
                        <div className="text-sm text-gray-400 mb-2">Overall Recommendation</div>
                        <div className={`text-3xl font-bold ${
                          analystRecommendations.recommendation === 'BUY' 
                            ? 'text-green-400' 
                            : analystRecommendations.recommendation === 'SELL'
                            ? 'text-red-400'
                            : 'text-yellow-400'
                        }`}>
                          {analystRecommendations.recommendation}
                        </div>
                        {analystRecommendations.target_price && (
                          <div className="text-sm text-gray-400 mt-2">
                            Target Price: <span className="text-white font-semibold">${analystRecommendations.target_price.toFixed(2)}</span>
                          </div>
                        )}
                        {analystRecommendations.latest_date && (
                          <div className="text-xs text-gray-500 mt-1">
                            Updated: {new Date(analystRecommendations.latest_date).toLocaleDateString()}
                          </div>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400 mb-3">Recommendation Breakdown</div>
                      <div className="space-y-2">
                        {analystRecommendations.breakdown && Object.entries(analystRecommendations.breakdown).map(([rating, count]) => {
                          const numCount = Number(count);
                          return (
                          <div key={rating} className="flex items-center justify-between">
                            <span className="text-sm text-gray-300">{rating}</span>
                            <div className="flex items-center gap-2">
                              <div className="w-32 bg-gray-700 rounded-full h-2">
                                <div 
                                  className={`h-2 rounded-full ${
                                    rating === 'Strong Buy' || rating === 'Buy' ? 'bg-green-500' :
                                    rating === 'Strong Sell' || rating === 'Sell' ? 'bg-red-500' :
                                    'bg-yellow-500'
                                  }`}
                                  style={{ width: `${analystRecommendations.total_analysts > 0 ? (numCount / analystRecommendations.total_analysts) * 100 : 0}%` }}
                                ></div>
                              </div>
                              <span className="text-sm font-semibold text-white w-8 text-right">{numCount}</span>
                            </div>
                          </div>
                        );})}
                        <div className="pt-2 border-t border-gray-700">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-gray-300">Total Analysts</span>
                            <span className="text-sm font-bold text-white">{analystRecommendations.total_analysts}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : analystRecommendations && !analystRecommendations.recommendation ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <h2 className="text-lg font-semibold text-white mb-2">Analyst Recommendations (Yahoo Finance)</h2>
                  <p className="text-gray-400 text-sm">No analyst recommendations available for this stock.</p>
                </div>
              ) : null}

              {/* Summary pane (fundamentals) — data fetched on landing with other overview data */}
              {isLoadingFundamentals ? (
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="animate-pulse">
                    <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
                    <div className="h-64 bg-gray-700 rounded"></div>
                  </div>
                </div>
              ) : fundamentalsData && typeof fundamentalsData === 'object' ? (
                <FundamentalPanes data={fundamentalsData} />
              ) : null}
            </div>
            )}

            {/* AI Analysis Tab Content */}
            {activeTab === 'ai-analysis' && (
              <div className="space-y-6">
                <p className="text-sm text-amber-400/90 bg-amber-950/30 border border-amber-700/40 rounded-lg px-4 py-2">
                  For informational purposes only. Not investment advice.
                </p>
                {/* Analysis Summary Header */}
                {stockData.has_reports && stockData.report_date && (
                  <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-lg border border-blue-700/50 p-6">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div>
                        <div className="text-sm text-gray-400 mb-1">Last Analysis Date</div>
                        <div className="text-lg font-semibold text-white">
                          {parseReportDate(stockData.report_date)?.toLocaleDateString('en-US', {
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric'
                              }) ?? 'N/A'}
                        </div>
                        {stockData.report_days_ago != null && (
                          <div className="text-sm text-gray-400 mt-1">
                            Report from {stockData.report_days_ago === 0 ? 'today' : stockData.report_days_ago === 1 ? '1 day ago' : `${stockData.report_days_ago} days ago`}.
                            {stockData.report_days_ago > 7 && (
                              <span className="text-amber-400/90 ml-1">Consider re-running for fresh insights.</span>
                            )}
                          </div>
                        )}
                        {modelsUsed && (modelsUsed.provider || modelsUsed.deep_think || modelsUsed.quick_think) && (
                          <div className="text-xs text-gray-500 mt-2">
                            Models: {[modelsUsed.provider && `${modelsUsed.provider}`, modelsUsed.deep_think && `deep: ${modelsUsed.deep_think}`, modelsUsed.quick_think && `quick: ${modelsUsed.quick_think}`].filter(Boolean).join(' · ')}
                          </div>
                        )}
                      </div>
                      <div className="md:text-right">
                        <div className="text-sm text-gray-400 mb-1">AI Decision</div>
                        <div className={`text-lg font-bold ${
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
                    {(stockData.expected_return_pct != null || stockData.bear_case_return_pct != null || stockData.bull_case_return_pct != null) && (
                      <div className="mt-4 pt-4 border-t border-gray-600/50 flex flex-wrap gap-6">
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
                  </div>
                )}

                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-white">AI Analysis Reports</h2>
                    {stockData.has_reports && !stockData.is_generating && (
                      <button
                        onClick={handleGenerateReport}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Run Fresh Analysis
                      </button>
                    )}
                  </div>
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
                        onClick={handleGenerateReport}
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
              </div>
            )}

            {/* News Tab Content */}
            {activeTab === 'news' && (
              <div className="space-y-6">
                {/* News Section */}
                <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                  <h2 className="text-xl font-semibold text-white mb-4">Latest News</h2>
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
            )}

            </div>
        </div>
      </div>
    </div>
  );
}
