import axios from 'axios';
import type {
  WidgetsResponse,
  StockPageData,
  StockQuote,
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

export const configApi = {
  getPublicConfig: async (): Promise<{ preview_tickers: string[] }> => {
    const response = await api.get<{ preview_tickers: string[] }>('/api/config/public');
    return response.data;
  },
};

export const stockApi = {
  // Get widgets for stocks (optional date YYYY-MM-DD for report-of-day filter when no tickers).
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
  getStockPage: async (ticker: string): Promise<StockPageData> => {
    const token = getStoredToken();
    const response = await api.get<StockPageData>(`/api/tickers/${ticker}`, {
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

  // Get extended stock info (raw market data via /api/data)
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

  // Get analysis status (requires auth)
  getAnalysisStatus: async (analysisId: string): Promise<any> => {
    const token = getStoredToken();
    const response = await api.get(`/api/analyses/${analysisId}/status`, {
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
  getHistoricalReports: async (ticker: string, runId: string): Promise<Record<string, {
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
  }>> => {
    const token = getStoredToken();
    const response = await api.get(`/api/tickers/${ticker}/reports/${encodeURIComponent(runId)}`, {
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

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  tokens_used: number;
  balance: number;
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
  tools_called?: number;
  balance?: number;
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

export const chatApi = {
  sendMessage: async (messages: ChatMessage[], context?: Record<string, unknown>): Promise<ChatResponse> => {
    const token = getStoredToken();
    const response = await api.post<ChatResponse>(
      '/api/chat',
      { messages, ...(context ? { context } : {}) },
      {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
      }
    );
    return response.data;
  },

  /**
   * Stream a chat response via SSE.
   * Calls `onToken` for each incremental text chunk,
   * `onThinking` for tool-call progress status messages,
   * `onToolCall` for each tool execution (name, input, output),
   * `onChart` for each chart spec emitted by execute_python,
   * `onSkillActivation` when a skill workflow starts (name + accumulated steps),
   * `onDone` when the stream finishes (with tokens_used and balance),
   * and `onError` on failure.
   * Returns an AbortController so the caller can cancel the stream.
   */
  streamMessage: (
    messages: ChatMessage[],
    onToken: (chunk: string) => void,
    onDone: (tokensUsed: number, balance: number, toolsCalled: number) => void,
    onError: (message: string) => void,
    onThinking?: (status: string) => void,
    onToolCall?: (toolCall: ToolCallEvent) => void,
    context?: Record<string, unknown>,
    onChart?: (spec: ChartSpec) => void,
    onSkillActivation?: (event: SkillActivationEvent) => void,
  ): AbortController => {
    const controller = new AbortController();
    const token = getStoredToken();

    const run = async () => {
      let pendingSkill: SkillActivationEvent | null = null;
      try {
        const res = await fetch(`${API_BASE_URL}/api/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ messages, ...(context ? { context } : {}) }),
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
                onDone(event.tokens_used ?? 1, event.balance ?? 0, event.tools_called ?? 0);
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

export default stockApi;
