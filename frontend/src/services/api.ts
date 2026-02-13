import axios from 'axios';
import type {
  WidgetsResponse,
  StockPageData,
  StockQuote,
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

export const stockApi = {
  // Get widgets for stocks (optional date YYYY-MM-DD for report-of-day filter when no tickers)
  getWidgets: async (tickers?: string[], date?: string): Promise<WidgetsResponse> => {
    const params: Record<string, string> = {};
    if (tickers?.length) params.tickers = tickers.join(',');
    if (date) params.date = date;
    const response = await api.get<WidgetsResponse>('/api/stocks/widgets', { params });
    return response.data;
  },

  // Get stock page data (sends auth when logged in so views count for creator rewards)
  getStockPage: async (ticker: string): Promise<StockPageData> => {
    const token = getStoredToken();
    const response = await api.get<StockPageData>(`/api/stocks/${ticker}`, {
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
    });
    return response.data;
  },

  // Get stock quote (raw market data via /api/data)
  getQuote: async (ticker: string): Promise<StockQuote> => {
    const response = await api.get<StockQuote>(`/api/data/quote/${ticker}`);
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

  // Get extended stock info (raw market data via /api/data)
  getExtendedInfo: async (ticker: string): Promise<any> => {
    const response = await api.get(`/api/data/extended-info/${ticker}`);
    return response.data;
  },

  // Start analysis (requires signed-in user; initiator is emailed when report is done)
  startAnalysis: async (ticker: string, analysisDate?: string): Promise<{ analysis_id: string; ticker: string; date: string; existing?: boolean }> => {
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

  // Get analysis status
  getAnalysisStatus: async (analysisId: string): Promise<any> => {
    const response = await api.get(`/api/analyses/${analysisId}/status`);
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

  // Get analyst recommendations from Yahoo (raw market data via /api/data)
  getAnalystRecommendations: async (ticker: string): Promise<{
    ticker: string;
    recommendation: string | null;
    target_price: number | null;
    breakdown: {
      'Strong Buy'?: number;
      'Buy'?: number;
      'Hold'?: number;
      'Sell'?: number;
      'Strong Sell'?: number;
    };
    total_analysts: number;
    latest_date: string | null;
    error?: string;
  }> => {
    const response = await api.get(`/api/data/analyst-recommendations/${ticker}`);
    return response.data;
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
};

export default stockApi;

