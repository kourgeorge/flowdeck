import axios from 'axios';
import type {
  WidgetsResponse,
  TickerPageData,
  TickerQuote,
  SimilarTickersResponse,
} from './types';
import { getStoredToken, getStoredUser } from './authApi';

// Base URL for API requests. Set VITE_API_URL in .env (e.g. https://api.example.com).
// In dev with proxy: use '' so Vite proxies /api to backend. In production: use VITE_API_URL or '' for same-origin.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: {
    'Content-Type': 'application/json',
  },
});

type AnalystRecommendationsResponse = {
  ticker: string;
  recommendation: string | null;
  target_price: number | null;
  recommendation_trend: Array<{
    period: string;
    strongBuy: number;
    buy: number;
    hold: number;
    sell: number;
    strongSell: number;
    total: number;
  }>;
  price_targets: {
    current: number | null;
    average: number | null;
    low: number | null;
    high: number | null;
  };
  breakdown: {
    'Strong Buy'?: number;
    'Buy'?: number;
    'Hold'?: number;
    'Sell'?: number;
    'Strong Sell'?: number;
  };
  total_analysts: number;
  latest_date: string | null;
  financial_data: {
    maxAge: number | null;
    currentPrice: number | null;
    targetHighPrice: number | null;
    targetLowPrice: number | null;
    targetMeanPrice: number | null;
    targetMedianPrice: number | null;
    recommendationMean: number | null;
    recommendationKey: string | null;
    numberOfAnalystOpinions: number | null;
  };
  error?: string;
};

function toSafeCount(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}

function toSafeNumber(value: unknown): number | null {
  if (value == null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function toSafeLatestDate(value: unknown): string | null {
  if (value == null) return null;
  const s = String(value).trim();
  if (!s) return null;
  // Guard against numeric row-index values from recommendation trend payloads (e.g. "0").
  if (/^\d+$/.test(s) && Number(s) < 10000) return null;
  const ts = new Date(s).getTime();
  return Number.isNaN(ts) ? null : s;
}

function normalizeRecommendationFromCounts(
  strongBuy: number,
  buy: number,
  hold: number,
  sell: number,
  strongSell: number,
): string | null {
  const buyScore = strongBuy + buy;
  const sellScore = sell + strongSell;
  const holdScore = hold;
  const maxScore = Math.max(buyScore, sellScore, holdScore);
  if (maxScore <= 0) return null;
  if (maxScore === buyScore) return 'BUY';
  if (maxScore === sellScore) return 'SELL';
  return 'HOLD';
}

function normalizeAnalystRecommendationsPayload(
  payload: unknown,
  ticker: string,
): AnalystRecommendationsResponse {
  const tickerUpper = ticker.toUpperCase();
  const empty: AnalystRecommendationsResponse = {
    ticker: tickerUpper,
    recommendation: null,
    target_price: null,
    recommendation_trend: [],
    price_targets: {
      current: null,
      average: null,
      low: null,
      high: null,
    },
    breakdown: {},
    total_analysts: 0,
    latest_date: null,
    financial_data: {
      maxAge: null,
      currentPrice: null,
      targetHighPrice: null,
      targetLowPrice: null,
      targetMeanPrice: null,
      targetMedianPrice: null,
      recommendationMean: null,
      recommendationKey: null,
      numberOfAnalystOpinions: null,
    },
  };

  const normalizeTrendRow = (row: Record<string, unknown>) => {
    const strongBuy = toSafeCount(row.strongBuy ?? row['Strong Buy']);
    const buy = toSafeCount(row.buy ?? row.Buy);
    const hold = toSafeCount(row.hold ?? row.Hold);
    const sell = toSafeCount(row.sell ?? row.Sell);
    const strongSell = toSafeCount(row.strongSell ?? row['Strong Sell']);
    return {
      period: String(row.period ?? ''),
      strongBuy,
      buy,
      hold,
      sell,
      strongSell,
      total: strongBuy + buy + hold + sell + strongSell,
    };
  };

  const mapCounts = (row: Record<string, unknown>) => {
    const normalizedRow = normalizeTrendRow(row);
    const strongBuy = normalizedRow.strongBuy;
    const buy = normalizedRow.buy;
    const hold = normalizedRow.hold;
    const sell = normalizedRow.sell;
    const strongSell = normalizedRow.strongSell;
    const breakdown = {
      'Strong Buy': strongBuy,
      Buy: buy,
      Hold: hold,
      Sell: sell,
      'Strong Sell': strongSell,
    };
    const total = strongBuy + buy + hold + sell + strongSell;
    return {
      breakdown,
      total,
      recommendation: normalizeRecommendationFromCounts(strongBuy, buy, hold, sell, strongSell),
    };
  };

  if (Array.isArray(payload)) {
    const rows = payload.filter((v) => v && typeof v === 'object') as Record<string, unknown>[];
    const trendRows = rows.map((row) => normalizeTrendRow(row));
    const latest = rows.find((row) => String(row.period ?? '') === '0m') ?? rows[0];
    if (!latest) return empty;
    const normalized = mapCounts(latest);
    return {
      ...empty,
      recommendation_trend: trendRows,
      breakdown: normalized.breakdown,
      total_analysts: normalized.total,
      recommendation: normalized.recommendation,
    };
  }

  if (!payload || typeof payload !== 'object') {
    return empty;
  }

  const raw = payload as Record<string, unknown>;

  const trendSource = Array.isArray(raw.recommendation_trend)
    ? raw.recommendation_trend
    : Array.isArray(raw.recommendationTrend)
      ? raw.recommendationTrend
      : null;

  if (
    trendSource !== null ||
    raw.recommendation !== undefined ||
    raw.breakdown !== undefined ||
    raw.total_analysts !== undefined ||
    raw.target_price !== undefined ||
    raw.financial_data !== undefined ||
    raw.financialData !== undefined
  ) {
    const breakdownRaw = (raw.breakdown && typeof raw.breakdown === 'object')
      ? (raw.breakdown as Record<string, unknown>)
      : {};
    const priceTargetsRaw = (raw.price_targets && typeof raw.price_targets === 'object')
      ? (raw.price_targets as Record<string, unknown>)
      : {};
    const financialDataRaw = (
      (raw.financial_data && typeof raw.financial_data === 'object')
      ? raw.financial_data
      : (raw.financialData && typeof raw.financialData === 'object')
        ? raw.financialData
        : {}
    ) as Record<string, unknown>;
    const trendRows = Array.isArray(raw.recommendation_trend)
      ? (raw.recommendation_trend as unknown[])
        .filter((v) => v && typeof v === 'object')
        .map((v) => normalizeTrendRow(v as Record<string, unknown>))
      : [];
    const latestTrend = trendRows.find((row) => row.period === '0m') ?? trendRows[0];
    const breakdown = {
      'Strong Buy': toSafeCount(breakdownRaw['Strong Buy']),
      Buy: toSafeCount(breakdownRaw.Buy),
      Hold: toSafeCount(breakdownRaw.Hold),
      Sell: toSafeCount(breakdownRaw.Sell),
      'Strong Sell': toSafeCount(breakdownRaw['Strong Sell']),
    };
    const breakdownTotal = Object.values(breakdown).reduce((sum, n) => sum + n, 0);
    const finalBreakdown = breakdownTotal > 0
      ? breakdown
      : latestTrend
        ? {
          'Strong Buy': latestTrend.strongBuy,
          Buy: latestTrend.buy,
          Hold: latestTrend.hold,
          Sell: latestTrend.sell,
          'Strong Sell': latestTrend.strongSell,
        }
        : breakdown;
    const totalAnalysts = toSafeCount(raw.total_analysts);
    const analystOpinions = toSafeCount(financialDataRaw.numberOfAnalystOpinions);
    const finalTotal = totalAnalysts > 0
      ? totalAnalysts
      : analystOpinions > 0
        ? analystOpinions
      : latestTrend?.total ?? Object.values(finalBreakdown).reduce((sum, n) => sum + n, 0);
    const normalizedRecommendation = raw.recommendation == null
      ? normalizeRecommendationFromCounts(
        finalBreakdown['Strong Buy'] ?? 0,
        finalBreakdown.Buy ?? 0,
        finalBreakdown.Hold ?? 0,
        finalBreakdown.Sell ?? 0,
        finalBreakdown['Strong Sell'] ?? 0,
      )
      : String(raw.recommendation);
    return {
      ticker: String(raw.ticker ?? tickerUpper).toUpperCase(),
      recommendation: normalizedRecommendation,
      target_price: toSafeNumber(raw.target_price) ?? toSafeNumber(financialDataRaw.targetMeanPrice),
      recommendation_trend: trendRows,
      price_targets: {
        current: toSafeNumber(priceTargetsRaw.current) ?? toSafeNumber(financialDataRaw.currentPrice),
        average: toSafeNumber(priceTargetsRaw.average)
          ?? toSafeNumber(raw.target_price)
          ?? toSafeNumber(financialDataRaw.targetMeanPrice),
        low: toSafeNumber(priceTargetsRaw.low) ?? toSafeNumber(financialDataRaw.targetLowPrice),
        high: toSafeNumber(priceTargetsRaw.high) ?? toSafeNumber(financialDataRaw.targetHighPrice),
      },
      breakdown: finalBreakdown,
      total_analysts: finalTotal,
      latest_date: toSafeLatestDate(raw.latest_date),
      financial_data: {
        maxAge: toSafeNumber(financialDataRaw.maxAge),
        currentPrice: toSafeNumber(financialDataRaw.currentPrice),
        targetHighPrice: toSafeNumber(financialDataRaw.targetHighPrice),
        targetLowPrice: toSafeNumber(financialDataRaw.targetLowPrice),
        targetMeanPrice: toSafeNumber(financialDataRaw.targetMeanPrice),
        targetMedianPrice: toSafeNumber(financialDataRaw.targetMedianPrice),
        recommendationMean: toSafeNumber(financialDataRaw.recommendationMean),
        recommendationKey: financialDataRaw.recommendationKey == null
          ? null
          : String(financialDataRaw.recommendationKey),
        numberOfAnalystOpinions: toSafeNumber(financialDataRaw.numberOfAnalystOpinions),
      },
      error: raw.error == null ? undefined : String(raw.error),
    };
  }

  const normalized = mapCounts(raw);
  return {
    ...empty,
    breakdown: normalized.breakdown,
    total_analysts: normalized.total,
    recommendation: normalized.recommendation,
  };
}

export const configApi = {
  getPublicConfig: async (): Promise<{ preview_tickers: string[] }> => {
    const response = await api.get<{ preview_tickers: string[] }>('/api/config/public');
    return response.data;
  },
};

export const tickerApi = {
  // Get widgets for tickers (optional date YYYY-MM-DD for report-of-day filter when no tickers).
  // When onlyAnalyzedToday=true and no tickers, returns only tickers that have reports for the date (no major-stocks list).
  // With recentDays>1 and onlyAnalyzedToday, returns tickers analyzed in the trailing N-day window ending at date.
  // When limit/offset are set with onlyAnalyzedToday, returns paginated results and response.total is set.
  getWidgets: async (
    tickers?: string[],
    date?: string,
    onlyAnalyzedToday?: boolean,
    limit?: number,
    offset?: number,
    recentDays?: number
  ): Promise<WidgetsResponse> => {
    const params: Record<string, string> = {};
    if (tickers?.length) params.tickers = tickers.join(',');
    if (date) params.date = date;
    if (onlyAnalyzedToday) params.only_date = 'true';
    if (recentDays != null) params.recent_days = String(recentDays);
    if (limit != null) params.limit = String(limit);
    if (offset != null) params.offset = String(offset);
    const response = await api.get<WidgetsResponse>('/api/tickers/widgets', { params });
    return response.data;
  },

  // Get stock page data (sends auth when logged in so views count for creator rewards)
  getTickerPage: async (ticker: string): Promise<TickerPageData> => {
    const token = getStoredToken();
    const response = await api.get<TickerPageData>(`/api/tickers/${ticker}`, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });
    return response.data;
  },

  // Get reports for a ticker via /api/data/reports (auth required)
  getReports: async (
    ticker: string,
    date?: string | null
  ): Promise<{
    report_run_id: number | null;
    report_date: string | null;
    reports: Record<string, { content?: string; score?: number; key_takeaways?: string[]; recommendation?: string; [key: string]: unknown }>;
    share_url?: string | null;
  }> => {
    const token = getStoredToken();
    const params = date ? { date } : {};
    const response = await api.get(`/api/data/reports/${ticker.toUpperCase()}`, {
      params,
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });
    return response.data;
  },

  // Batch fetch reports for multiple tickers (auth required)
  getReportsBatch: async (
    tickers: string[]
  ): Promise<{
    tickers: Record<
      string,
      {
        report_run_id: number | null;
        report_date: string | null;
        reports: Record<string, { content?: string; score?: number; key_takeaways?: string[]; recommendation?: string; [key: string]: unknown }>;
      }
    >;
  }> => {
    const token = getStoredToken();
    const response = await api.post(
      '/api/data/reports/batch',
      { tickers: tickers.map((t) => t.toUpperCase()) },
      {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      }
    );
    return response.data;
  },

  // List available report dates for a ticker (auth required)
  getReportDates: async (ticker: string): Promise<string[]> => {
    const token = getStoredToken();
    const response = await api.get<{ ticker: string; dates: string[] }>(
      `/api/data/reports/${ticker.toUpperCase()}/dates`,
      {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      }
    );
    return response.data.dates ?? [];
  },

  // Get ticker quote (raw market data via /api/data)
  getQuote: async (ticker: string): Promise<TickerQuote> => {
    const response = await api.get<TickerQuote>(`/api/data/quote/${ticker}`);
    return response.data;
  },

  // Get company info (raw market data via /api/data)
  getCompanyInfo: async (ticker: string): Promise<{
    name: string;
    sector: string;
    industry: string;
    exchange: string;
    country: string;
    website: string;
    quoteType?: string;
  }> => {
    const response = await api.get(`/api/data/company/${ticker}`);
    return response.data;
  },

  // Get company officers (raw market data via /api/data)
  getCompanyOfficers: async (ticker: string): Promise<{
    ticker: string;
    officers: Array<{
      name: string;
      title: string;
      age?: number | null;
      year_born?: number | null;
      fiscal_year?: number | null;
      total_pay?: number | null;
      exercised_value?: number | null;
      unexercised_value?: number | null;
    }>;
    count: number;
    error?: string;
  }> => {
    const response = await api.get(`/api/data/company-officers/${ticker}`);
    return response.data;
  },

  // Get extended ticker info (raw market data via /api/data)
  getExtendedInfo: async (ticker: string): Promise<any> => {
    const response = await api.get(`/api/data/extended-info/${ticker}`);
    return response.data;
  },

  // Get similar tickers based on sector/industry (raw market data via /api/data)
  getSimilarTickers: async (ticker: string, limit: number = 10, offset: number = 0): Promise<SimilarTickersResponse> => {
    const response = await api.get(`/api/data/similar-tickers/${ticker}`, {
      params: { limit, offset },
    });
    return response.data;
  },

  // Start analysis (requires signed-in user; initiator is emailed when report is done)
  startAnalysis: async (ticker: string, analysisDate?: string): Promise<{ analysis_run_id: number; ticker: string; date: string; existing?: boolean }> => {
    const token = getStoredToken();
    const user = getStoredUser();
    const response = await api.post(
      '/api/analyses/start',
      {
        ticker,
        analysis_date: analysisDate,
        ...(user?.email && { initiator_email: user.email }),
      },
      {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      }
    );
    return response.data;
  },

  // Get analysis status (requires auth)
  getAnalysisStatus: async (analysisRunId: number): Promise<any> => {
    const token = getStoredToken();
    const response = await api.get(`/api/analyses/${analysisRunId}/status`, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });
    return response.data;
  },

  // Get historical price data (raw market data via /api/data)
  getHistoricalPrices: async (ticker: string, period: string = '6mo', interval: string = '1d'): Promise<any> => {
    const response = await api.get(`/api/data/historical/${ticker}`, {
      params: { period, interval },
    });
    return response.data;
  },

  // Get fundamental data (raw market data via /api/data)
  getFundamentals: async (ticker: string): Promise<{ ticker: string; date: string; fundamentals: string | object }> => {
    const response = await api.get(`/api/data/fundamentals/${ticker}`);
    return response.data;
  },

  // Get ETF/fund-specific data (AUM, expense ratio, category, holdings, sector weightings)
  getFundInfo: async (ticker: string): Promise<{
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
  }> => {
    const response = await api.get(`/api/data/fund-info/${ticker}`);
    return response.data;
  },

  // Get financial statements (raw market data via /api/data)
  getFinancialStatements: async (
    ticker: string,
    statementType: string = 'all',
    freq: string = 'quarterly'
  ): Promise<{ ticker: string; date: string; frequency: string; statements: any }> => {
    const response = await api.get(`/api/data/financial-statements/${ticker}`, {
      params: { statement_type: statementType, freq },
    });
    return response.data;
  },

  // Get news articles (raw market data via /api/data)
  getNews: async (ticker: string): Promise<{
    ticker: string;
    date: string;
    articles: Array<{
      uuid: string;
      title: string;
      summary?: string | null;
      publisher: string;
      link: string;
      published_time: string | null;
      published_timestamp: number;
      type: string;
      thumbnail: string | null;
    }>;
    count: number;
    error?: string;
  }> => {
    const response = await api.get(`/api/data/news`, { params: { ticker } });
    return response.data;
  },

  // Get merged news for multiple tickers in one request (faster than N×getNews for headlines)
  getNewsBatch: async (tickers: string[]): Promise<{
    articles: Array<{
      uuid: string;
      title: string;
      summary?: string | null;
      publisher?: string;
      link: string;
      published_time: string | null;
      published_timestamp: number;
      type?: string;
      thumbnail?: string | null;
      tickers: string[];
    }>;
    count: number;
  }> => {
    if (tickers.length === 0) return { articles: [], count: 0 };
    const response = await api.get(`/api/data/news/batch`, {
      params: { tickers: tickers.slice(0, 50).join(',') },
    });
    return response.data;
  },

  // Get latest insider transactions (raw market data via /api/data)
  getInsiderTransactions: async (
    ticker: string,
    limit: number = 50
  ): Promise<{
    ticker: string;
    date: string;
    transactions: Array<{
      insider: string | null;
      position: string | null;
      transaction: string | null;
      start_date: string | null;
      shares: number | null;
      value: number | null;
      ownership: string | null;
      url: string | null;
      text: string | null;
    }>;
    count: number;
    error?: string;
  }> => {
    const response = await api.get(`/api/data/insider-transactions/${ticker}`, {
      params: { limit },
    });
    return response.data;
  },

  // Get upcoming earnings and ex-dividend dates (Yahoo Finance)
  getFutureEvents: async (ticker: string): Promise<{
    ticker: string;
    events: Array<{
      date: string;
      type: 'earnings' | 'ex_dividend';
      label: string;
      eps_estimate?: number;
    }>;
    count: number;
    error?: string;
  }> => {
    const response = await api.get(`/api/data/future-events/${ticker}`);
    return response.data;
  },

  // Get analyst recommendations from Yahoo (raw market data via /api/data)
  getAnalystRecommendations: async (ticker: string): Promise<AnalystRecommendationsResponse> => {
    const response = await api.get(`/api/data/analyst-recommendations/${ticker}`);
    return normalizeAnalystRecommendationsPayload(response.data, ticker);
  },

  // Get financial charts (raw market data via /api/data)
  getFinancialCharts: async (
    ticker: string,
    freq: 'annual' | 'quarterly' = 'annual'
  ): Promise<any> => {
    const response = await api.get(`/api/data/financial-charts/${ticker}`, {
      params: { freq },
    });
    return response.data;
  },

  // Get a single market overview section (only fetches that group from Yahoo). Use for map to avoid fetching sectors/commodities.
  getMarketOverviewSection: async (
    section: 'indices' | 'sectors' | 'regions' | 'commodities',
    params?: {
      limit?: number;
      offset?: number;
      range?: '1d' | '1w' | '1mo' | '3mo' | '6mo' | 'ytd';
    }
  ): Promise<{
    section: string;
    items: Array<{ ticker: string; name: string; price: number | null; change: number | null; changePercent: number | null }>;
    total: number;
  }> => {
    const response = await api.get(`/api/data/market-overview/section`, {
      params: { section, ...(params ?? {}) },
    });
    return response.data;
  },

  // Get market overview: indices, sectors, international (prices and change). Pagination per group. range: 1d, 1w, 1mo, 3mo, 6mo, ytd.
  getMarketOverview: async (params?: {
    limit_indices?: number;
    offset_indices?: number;
    limit_sectors?: number;
    offset_sectors?: number;
    limit_regions?: number;
    offset_regions?: number;
    limit_commodities?: number;
    offset_commodities?: number;
    range?: '1d' | '1w' | '1mo' | '3mo' | '6mo' | 'ytd';
  }): Promise<{
    indices: Array<{ ticker: string; name: string; price: number | null; change: number | null; changePercent: number | null }>;
    sectors: Array<{ ticker: string; name: string; price: number | null; change: number | null; changePercent: number | null }>;
    international: Array<{ ticker: string; name: string; price: number | null; change: number | null; changePercent: number | null }>;
    commodities: Array<{ ticker: string; name: string; price: number | null; change: number | null; changePercent: number | null }>;
    totalIndices: number;
    totalSectors: number;
    totalRegions: number;
    totalCommodities: number;
  }> => {
    const response = await api.get(`/api/data/market-overview`, { params: params ?? {} });
    return response.data;
  },

  // Get daily top gainers, losers, and most active (US market, yahooquery Screener)
  getMarketMovers: async (count: number = 8): Promise<{
    gainers: Array<{
      symbol: string | null;
      shortName: string | null;
      sector?: string | null;
      industry?: string | null;
      regularMarketPrice: number | null;
      regularMarketChange: number | null;
      regularMarketChangePercent: number | null;
      regularMarketPreviousClose: number | null;
      regularMarketVolume: number | null;
    }>;
    losers: Array<{
      symbol: string | null;
      shortName: string | null;
      sector?: string | null;
      industry?: string | null;
      regularMarketPrice: number | null;
      regularMarketChange: number | null;
      regularMarketChangePercent: number | null;
      regularMarketPreviousClose: number | null;
      regularMarketVolume: number | null;
    }>;
    most_active: Array<{
      symbol: string | null;
      shortName: string | null;
      sector?: string | null;
      industry?: string | null;
      regularMarketPrice: number | null;
      regularMarketChange: number | null;
      regularMarketChangePercent: number | null;
      regularMarketPreviousClose: number | null;
      regularMarketVolume: number | null;
    }>;
  }> => {
    const response = await api.get(`/api/data/market-movers`, { params: { count } });
    return response.data;
  },

  // Get SEC EDGAR filings (10-K, 10-Q) for a ticker (US companies only)
  getEdgarFilings: async (ticker: string): Promise<{
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
  }> => {
    const response = await api.get(`/api/data/edgar-filings/${ticker}`);
    return response.data;
  },

  // Get reports for a specific historical run (experimental)
  getHistoricalReports: async (ticker: string, analysisRunId: number): Promise<Record<string, {
    content: string | null;
    score: number | null;
    score_label: string | null;
    key_takeaways: string[];
    analysis_date: string | null;
    generated_at: string | null;
    days_ago: number | null;
    models_used: { provider?: string; deep_think?: string; quick_think?: string } | null;
    bull_viewpoint: string[] | null;
    bear_viewpoint: string[] | null;
    risky_viewpoint: string[] | null;
    safe_viewpoint: string[] | null;
    neutral_viewpoint: string[] | null;
    tps_plan: string | null;
    expected_return_pct?: number | null;
    bear_case_return_pct?: number | null;
    bull_case_return_pct?: number | null;
  }>> => {
    const token = getStoredToken();
    const response = await api.get(`/api/tickers/${ticker}/reports/${analysisRunId}`, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });
    return response.data;
  },

  // Get public stats (no auth required)
  getPublicStats: async (): Promise<{
    total_analyses: number;
    total_reports: number;
    unique_tickers_analyzed: number;
  }> => {
    const response = await api.get('/api/stats');
    return response.data;
  },
};

export const contactApi = {
  submit: async (data: { name: string; email: string; message: string }) => {
    const res = await api.post<{ ok: boolean; message: string }>('/api/contact', data);
    return res.data;
  },
};

/** User Daily Brief: narrative + what to watch. Requires auth. */
export type DigestSpan = 'daily' | 'weekly';

export interface DigestResponse {
  narrative: string;
  what_to_watch: string;
  digest_date: string;
  priority_tickers: string[];
  span_type?: string;
  span_label?: string;
  user_note?: string | null;
  narrative_style?: string | null;
  user_focus_tickers?: string[] | null;
  raw_metadata?: Record<string, unknown> | null;
  references?: {
    label: string;
    url?: string | null;
    source?: string | null;
    tickers?: string[] | null;
  }[] | null;
  share_url?: string | null;
}

export interface DigestDatesResponse {
  dates: string[];
  count_by_date: Record<string, number>;
}

export interface DigestBriefItem {
  execution_id: number;
  created_at: string;
  narrative: string;
  what_to_watch: string;
  digest_date: string;
  span_type?: string;
  span_label?: string;
  priority_tickers: string[];
  user_note?: string | null;
  narrative_style?: string | null;
  user_focus_tickers?: string[] | null;
  references?: { label: string; url?: string | null; source?: string | null; tickers?: string[] | null }[] | null;
  raw_metadata?: Record<string, unknown> | null;
  share_url?: string | null;
}

export interface DigestListForDateResponse {
  date: string;
  briefs: DigestBriefItem[];
}

export const digestApi = {
  getDigest: async (params?: { date?: string; span?: DigestSpan; max_priority_tickers?: number; user_note?: string; narrative_style?: string; user_focus_tickers?: string[] }): Promise<DigestResponse> => {
    const token = getStoredToken();
    if (!token) throw new Error('Sign in to get your User Daily Brief');
    const searchParams = new URLSearchParams();
    if (params) {
      if (params.date != null) searchParams.set('date', params.date);
      if (params.span != null && params.span !== 'daily') searchParams.set('span', params.span);
      if (params.max_priority_tickers != null) searchParams.set('max_priority_tickers', String(params.max_priority_tickers));
      if (params.user_note != null && params.user_note !== '') searchParams.set('user_note', params.user_note);
      if (params.narrative_style != null && params.narrative_style !== '') searchParams.set('narrative_style', params.narrative_style);
      if (params.user_focus_tickers?.length) {
        for (const t of params.user_focus_tickers) {
          searchParams.append('user_focus_tickers', t);
        }
      }
    }
    const response = await api.get<DigestResponse>('/api/digest', {
      headers: { Authorization: `Bearer ${token}` },
      params: searchParams,
    });
    return response.data;
  },

  getDigestDates: async (days: number = 90): Promise<DigestDatesResponse> => {
    const token = getStoredToken();
    if (!token) throw new Error('Sign in to view your User Daily Brief history');
    const response = await api.get<DigestDatesResponse>('/api/digest/history/dates', {
      headers: { Authorization: `Bearer ${token}` },
      params: { days },
    });
    return response.data;
  },

  getDigestsForDate: async (date: string): Promise<DigestListForDateResponse> => {
    const token = getStoredToken();
    if (!token) throw new Error('Sign in to view your User Daily Brief history');
    const response = await api.get<DigestListForDateResponse>(`/api/digest/history/${date}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },
};

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  tokens_used: number;
  /** Platform tokens deducted from balance (show this in the UI) */
  platform_tokens_used: number;
  balance: number;
  follow_up_questions?: string[];
  session_id?: number | null;
  llm_usage?: { cost_usd?: number };
}

export interface ToolCallEvent {
  name: string;
  input: string;
  output: string;
}

/** A skill activation event — emitted when a skill workflow starts */
export interface SkillActivationEvent {
  /** Skill name, e.g. "compare_stocks" */
  name: string;
  /** Individual tool steps the skill executed */
  steps: SkillStepEvent[];
}

/** One tool step executed inside a skill workflow */
export interface SkillStepEvent {
  tool: string;
  input: string;
  output: string;
  ok: boolean;
}

/** Chart spec emitted by the agent via execute_python CHART_JSON output */
export interface ChartSpec {
  title: string;
  type: 'line' | 'bar' | 'area' | 'scatter';
  xKey: string;
  yKeys: string[];
  data: Record<string, string | number>[];
  colors?: string[];
}

export interface ChatStreamEvent {
  type: 'token' | 'done' | 'error' | 'thinking' | 'tool_call' | 'chart' | 'skill_start' | 'skill_step' | 'skill_done';
  content?: string;
  tokens_used?: number;
  /** Platform tokens deducted (show this in the UI) */
  platform_tokens_used?: number;
  tools_called?: number;
  balance?: number;
  follow_up_questions?: string[];
  session_id?: number;
  llm_usage?: { cost_usd?: number };
  // tool_call fields
  name?: string;
  input?: string;
  output?: string;
  // chart fields
  spec?: ChartSpec;
  // skill_step fields
  skill?: string;
  tool?: string;
  ok?: boolean;
  // skill_done fields
  steps?: number;
}

/** Session list item from GET /api/chat/sessions */
export interface ChatSessionListItem {
  id: number;
  title: string | null;
  updated_at: string;
}

/** Model metadata stored per assistant message (provider, tokens, cost) */
export interface ModelMetadataApi {
  provider?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
  calls?: number;
  per_call?: Array<{ model?: string; input_tokens?: number; output_tokens?: number; cost_usd?: number }>;
}

/** Message as returned from GET /api/chat/sessions/:id (with meta) */
export interface ChatMessageWithMetaApi {
  role: string;
  content: string;
  sort_order: number;
  tokens_used?: number | null;
  /** Platform tokens deducted (show this in the UI) */
  platform_tokens_used?: number | null;
  /** LLM provider, token counts, cost (from DB) */
  model_metadata?: ModelMetadataApi | null;
  tools_called?: number | null;
  tool_call_events?: ToolCallEvent[] | null;
  skill_activation_events?: SkillActivationEvent[] | null;
  charts?: ChartSpec[] | null;
  follow_up_questions?: string[] | null;
  created_at?: string | null;
  cost_usd?: number | null;
}

/** Session detail from GET /api/chat/sessions/:id */
export interface ChatSessionDetail {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessageWithMetaApi[];
}

export const chatApi = {
  sendMessage: async (
    messages: ChatMessage[],
    context?: Record<string, unknown>,
    sessionId?: number | null,
  ): Promise<ChatResponse> => {
    const token = getStoredToken();
    const body: Record<string, unknown> = { messages, ...(context ? { context } : {}) };
    if (sessionId != null) body.session_id = sessionId;
    const response = await api.post<ChatResponse>('/api/chat', body, {
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
    });
    return response.data;
  },

  getChatSessions: async (): Promise<ChatSessionListItem[]> => {
    const token = getStoredToken();
    const res = await api.get<{ sessions: ChatSessionListItem[] }>('/api/chat/sessions', {
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
    });
    return res.data.sessions;
  },

  createChatSession: async (): Promise<{ id: number; title: string | null; created_at: string; updated_at: string }> => {
    const token = getStoredToken();
    const res = await api.post<{ id: number; title: string | null; created_at: string; updated_at: string }>(
      '/api/chat/sessions',
      {},
      { headers: { ...(token && { Authorization: `Bearer ${token}` }) } },
    );
    return res.data;
  },

  getChatSession: async (sessionId: number): Promise<ChatSessionDetail> => {
    const token = getStoredToken();
    const res = await api.get<ChatSessionDetail>(`/api/chat/sessions/${sessionId}`, {
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
    });
    return res.data;
  },

  deleteChatSession: async (sessionId: number): Promise<void> => {
    const token = getStoredToken();
    await api.delete(`/api/chat/sessions/${sessionId}`, {
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
    });
  },

  /**
   * Stream a chat response via SSE.
   * When sessionId is set, backend loads session history and persists new messages on done.
   * Calls `onToken` for each incremental text chunk,
   * `onThinking` for tool-call progress status messages,
   * `onToolCall` for each tool execution (name, input, output),
   * `onChart` for each chart spec emitted by execute_python,
   * `onSkillActivation` when a skill workflow starts (name + accumulated steps),
   * `onDone` when the stream finishes (with tokens_used, platform_tokens_used, and balance),
   * and `onError` on failure.
   * Returns an AbortController so the caller can cancel the stream.
   */
  streamMessage: (
    messages: ChatMessage[],
    onToken: (chunk: string) => void,
    onDone: (tokensUsed: number, balance: number, toolsCalled: number, followUpQuestions?: string[], sessionId?: number, platformTokensUsed?: number, costUsd?: number) => void,
    onError: (message: string) => void,
    onThinking?: (status: string) => void,
    onToolCall?: (toolCall: ToolCallEvent) => void,
    context?: Record<string, unknown>,
    onChart?: (spec: ChartSpec) => void,
    onSkillActivation?: (event: SkillActivationEvent) => void,
    sessionId?: number | null,
  ): AbortController => {
    const controller = new AbortController();
    const token = getStoredToken();
    const body: Record<string, unknown> = { messages, ...(context ? { context } : {}) };
    if (sessionId != null) body.session_id = sessionId;

    const run = async () => {
      let pendingSkill: SkillActivationEvent | null = null;
      try {
        const res = await fetch(`${API_BASE_URL}/api/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const body = await res.json();
            detail = body?.detail ?? detail;
          } catch { /* ignore */ }
          onError(detail);
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) { onError('No response body'); return; }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE lines are separated by \n\n
          const parts = buffer.split('\n\n');
          buffer = parts.pop() ?? '';

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data:')) continue;
            const jsonStr = line.slice('data:'.length).trim();
            if (!jsonStr) continue;
            try {
              const event: ChatStreamEvent = JSON.parse(jsonStr);
              if (event.type === 'token' && event.content) {
                onToken(event.content);
              } else if (event.type === 'thinking' && event.content) {
                onThinking?.(event.content);
              } else if (event.type === 'tool_call' && event.name) {
                onToolCall?.({ name: event.name, input: event.input ?? '', output: event.output ?? '' });
              } else if (event.type === 'chart' && event.spec) {
                onChart?.(event.spec);
              } else if (event.type === 'skill_start' && event.name) {
                // Skill workflow started — accumulate steps until skill_done
                pendingSkill = { name: event.name, steps: [] };
                onThinking?.(`Running ${event.name.replace(/_/g, ' ')} workflow…`);
              } else if (event.type === 'skill_step' && pendingSkill) {
                pendingSkill.steps.push({
                  tool: event.tool ?? '',
                  input: event.input ?? '',
                  output: event.output ?? '',
                  ok: event.ok !== false,
                });
              } else if (event.type === 'skill_done' && pendingSkill) {
                onSkillActivation?.(pendingSkill);
                pendingSkill = null;
              } else if (event.type === 'done') {
                onDone(
                  event.tokens_used ?? 1,
                  event.balance ?? 0,
                  event.tools_called ?? 0,
                  event.follow_up_questions,
                  event.session_id,
                  event.platform_tokens_used,
                  event.llm_usage?.cost_usd,
                );
              } else if (event.type === 'error') {
                onError(event.content ?? 'Unknown error');
              }
            } catch { /* malformed JSON, skip */ }
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError') return; // cancelled by caller
        onError(err?.message ?? 'Stream failed');
      }
    };

    run();
    return controller;
  },
};

export default tickerApi;
