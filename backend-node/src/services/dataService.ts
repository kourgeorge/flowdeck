/**
 * Data fetching service using yahoo-finance2 (v2: quote + autoc). Historical/chart via Yahoo public APIs.
 * Matches Python info_fetcher response shapes.
 */

interface ChartQuote {
  open?: number[];
  high?: number[];
  low?: number[];
  close?: number[];
  volume?: number[];
}
interface ChartResult {
  timestamp?: number[];
  indicators?: { quote?: ChartQuote[] };
}
interface ChartApiResponse {
  chart?: { result?: ChartResult[] };
}

let yahooFinanceInstance: { quote: (q: string) => Promise<Record<string, unknown>> } | null = null;

async function getYahooFinance(): Promise<{ quote: (q: string) => Promise<Record<string, unknown>> }> {
  if (yahooFinanceInstance) return yahooFinanceInstance;
  const YahooFinance = (await import("yahoo-finance2")).default;
  const yf = new YahooFinance();
  yahooFinanceInstance = {
    quote: async (symbol: string) => {
      const result = await yf.quote(symbol);
      return (result ?? {}) as Record<string, unknown>;
    },
  };
  return yahooFinanceInstance;
}

const MARKET_STATE_MAP: Record<string, string> = {
  REGULAR: "OPEN",
  CLOSED: "CLOSED",
  PRE: "PRE_MARKET",
  POST: "AFTER_HOURS",
};

function marketStatus(info: { marketState?: string }): string {
  const state = (info.marketState ?? "").toUpperCase();
  return MARKET_STATE_MAP[state] ?? "UNKNOWN";
}

function isValidPrice(p: unknown): boolean {
  if (p == null) return false;
  const n = Number(p);
  return !Number.isNaN(n) && n > 0;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Quote response matching Python StockQuote / get_quote */
export async function getQuote(ticker: string): Promise<Record<string, unknown> | null> {
  const sym = ticker.toUpperCase();
  const buildResult = (quote: Record<string, unknown>) => {
    const currentPrice = quote.regularMarketPrice ?? quote.regularMarketPreviousClose;
    if (currentPrice == null || !isValidPrice(currentPrice)) return null;
    const prevClose = quote.regularMarketPreviousClose ?? currentPrice;
    const dailyChange = Number(currentPrice) - Number(prevClose);
    const dailyChangePercent = prevClose ? (dailyChange / Number(prevClose)) * 100 : 0;
    return {
      ticker: sym,
      current_price: Math.round(Number(currentPrice) * 100) / 100,
      daily_change: Math.round(dailyChange * 100) / 100,
      daily_change_percent: Math.round(dailyChangePercent * 100) / 100,
      bid_price: quote.bid != null ? Math.round(Number(quote.bid) * 100) / 100 : null,
      ask_price: quote.ask != null ? Math.round(Number(quote.ask) * 100) / 100 : null,
      bid_size: quote.bidSize ?? null,
      ask_size: quote.askSize ?? null,
      volume: quote.regularMarketVolume ?? null,
      previous_close: prevClose != null ? Math.round(Number(prevClose) * 100) / 100 : null,
      day_high: quote.regularMarketDayHigh != null ? Math.round(Number(quote.regularMarketDayHigh) * 100) / 100 : null,
      day_low: quote.regularMarketDayLow != null ? Math.round(Number(quote.regularMarketDayLow) * 100) / 100 : null,
      fifty_two_week_high: quote.fiftyTwoWeekHigh != null ? Math.round(Number(quote.fiftyTwoWeekHigh) * 100) / 100 : null,
      fifty_two_week_low: quote.fiftyTwoWeekLow != null ? Math.round(Number(quote.fiftyTwoWeekLow) * 100) / 100 : null,
      market_status: marketStatus(quote as { marketState?: string }),
      last_update_time: new Date().toISOString(),
    };
  };

  const retryDelays = [0, 1000, 2000, 3000]; // individual requests with spacing to avoid rate limits
  for (let i = 0; i < retryDelays.length; i++) {
    if (i > 0) await sleep(retryDelays[i]);
    try {
      const yf = await getYahooFinance();
      const quote = (await yf.quote(sym)) as Record<string, unknown>;
      if (!quote || Object.keys(quote).length === 0) continue;
      return buildResult(quote);
    } catch {
      if (i === retryDelays.length - 1) return null;
    }
  }
  return null;
}

/** Historical OHLCV via Yahoo Chart API. Matches Python get_historical. */
export async function getHistorical(
  ticker: string,
  period: string = "6mo",
  interval: string = "1d"
): Promise<{ ticker: string; period: string; interval: string; data: unknown[]; count: number }> {
  const sym = ticker.toUpperCase();
  const end = Math.floor(Date.now() / 1000);
  let start = end - 180 * 24 * 3600;
  const p = period.toLowerCase();
  if (p === "1d") start = end - 1 * 24 * 3600;
  else if (p === "5d") start = end - 5 * 24 * 3600;
  else if (p === "1mo") start = end - 30 * 24 * 3600;
  else if (p === "3mo") start = end - 90 * 24 * 3600;
  else if (p === "6mo") start = end - 180 * 24 * 3600;
  else if (p === "1y") start = end - 365 * 24 * 3600;
  else if (p === "2y") start = end - 2 * 365 * 24 * 3600;
  else if (p === "5y") start = end - 5 * 365 * 24 * 3600;
  else if (p === "10y") start = end - 10 * 365 * 24 * 3600;
  else if (p === "ytd") start = Math.floor(new Date(new Date().getFullYear(), 0, 1).getTime() / 1000);
  else if (p === "max") start = 0;

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?period1=${start}&period2=${end}&interval=${interval}`;
    const res = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = (await res.json()) as ChartApiResponse;
    const result = json?.chart?.result?.[0];
    const timestamps = result?.timestamp ?? [];
    const quote = result?.indicators?.quote?.[0];
    const opens = quote?.open ?? [];
    const highs = quote?.high ?? [];
    const lows = quote?.low ?? [];
    const closes = quote?.close ?? [];
    const volumes = quote?.volume ?? [];
    const data = timestamps.map((ts, i) => {
      const d = new Date(ts * 1000);
      return {
        date: d.toISOString().slice(0, 10),
        timestamp: ts * 1000,
        open: opens[i] != null ? Math.round(opens[i] * 100) / 100 : null,
        high: highs[i] != null ? Math.round(highs[i] * 100) / 100 : null,
        low: lows[i] != null ? Math.round(lows[i] * 100) / 100 : null,
        close: closes[i] != null ? Math.round(closes[i] * 100) / 100 : null,
        volume: volumes[i] ?? null,
        adj_close: closes[i] != null ? Math.round(closes[i] * 100) / 100 : null,
      };
    });
    return { ticker: sym, period, interval, data, count: data.length };
  } catch {
    return { ticker: sym, period, interval, data: [], count: 0 };
  }
}

/** Company profile from quote (quote has shortName, longName, exchange). Matches Python get_company_info. */
export async function getCompanyInfo(ticker: string): Promise<Record<string, string>> {
  const sym = ticker.toUpperCase();
  try {
    const yf = await getYahooFinance();
    const quote = await yf.quote(sym) as Record<string, unknown>;
    return {
      name: (quote.longName ?? quote.shortName ?? sym) as string,
      sector: "N/A",
      industry: "N/A",
      exchange: (quote.exchange ?? quote.fullExchangeName ?? "N/A") as string,
      country: "N/A",
      website: "N/A",
    };
  } catch {
    return { name: sym, sector: "N/A", industry: "N/A", exchange: "N/A", country: "N/A", website: "N/A" };
  }
}

/** Extended metrics from quote. Matches Python get_extended_info. */
export async function getExtendedInfo(ticker: string): Promise<Record<string, number | null>> {
  const sym = ticker.toUpperCase();
  const empty = {
    beta: null, market_cap: null, revenue: null, gross_margin: null, dividend_yield: null,
    trailing_eps: null, forward_eps: null, average_volume: null, enterprise_value: null,
    profit_margin: null, operating_margin: null, ebitda: null, pe_ratio: null, forward_pe: null,
  };
  try {
    const yf = await getYahooFinance();
    const q = await yf.quote(sym) as Record<string, unknown>;
    return {
      beta: (q.beta as number) ?? null,
      market_cap: (q.marketCap as number) ?? null,
      revenue: null,
      gross_margin: null,
      dividend_yield: (q.trailingAnnualDividendYield as number) ?? null,
      trailing_eps: (q.epsTrailingTwelveMonths as number) ?? null,
      forward_eps: (q.epsForward as number) ?? null,
      average_volume: (q.averageDailyVolume3Month as number) ?? null,
      enterprise_value: null,
      profit_margin: null,
      operating_margin: null,
      ebitda: null,
      pe_ratio: (q.trailingPE as number) ?? null,
      forward_pe: (q.forwardPE as number) ?? null,
    };
  } catch {
    return empty;
  }
}

/** Fundamentals from quote. Matches Python get_fundamentals shape. */
export async function getFundamentals(ticker: string): Promise<{ ticker: string; date: string; fundamentals: Record<string, unknown>; error?: string }> {
  const sym = ticker.toUpperCase();
  const currDate = new Date().toISOString().slice(0, 10);
  try {
    const yf = await getYahooFinance();
    const quote = await yf.quote(sym);
    return { ticker: sym, date: currDate, fundamentals: quote ?? {} };
  } catch (e) {
    return { ticker: sym, date: currDate, fundamentals: {}, error: String(e) };
  }
}

/** Financial statements. Stub shape for UI; full data would require quoteSummary. */
export async function getFinancialStatements(
  ticker: string,
  statementType: string = "all",
  freq: string = "quarterly"
): Promise<{ ticker: string; date: string; frequency: string; statements: Record<string, unknown> }> {
  const sym = ticker.toUpperCase();
  const currDate = new Date().toISOString().slice(0, 10);
  return {
    ticker: sym,
    date: currDate,
    frequency: freq,
    statements: {
      ...(statementType === "all" || statementType === "balance_sheet" ? { balance_sheet: null } : {}),
      ...(statementType === "all" || statementType === "cashflow" ? { cashflow: null } : {}),
      ...(statementType === "all" || statementType === "income_statement" ? { income_statement: null } : {}),
    },
  };
}

/** Financial charts. Stub shape for UI. */
export async function getFinancialCharts(ticker: string, freq: string = "annual"): Promise<Record<string, unknown>> {
  const sym = ticker.toUpperCase();
  return {
    ticker: sym,
    frequency: freq,
    balance_sheet: null,
    cashflow: null,
    income_statement: null,
    historical_financials: null,
  };
}

/** Stock data as CSV-like string for agents. Uses historical chart. */
export async function getStockData(ticker: string, startDate: string, endDate: string): Promise<string> {
  const sym = ticker.toUpperCase();
  try {
    const start = Math.floor(new Date(startDate).getTime() / 1000);
    const end = Math.floor(new Date(endDate).getTime() / 1000);
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?period1=${start}&period2=${end}&interval=1d`;
    const res = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    const json = (await res.json()) as ChartApiResponse;
    const result = json?.chart?.result?.[0];
    const timestamps = result?.timestamp ?? [];
    const quote = result?.indicators?.quote?.[0];
    const opens = quote?.open ?? [];
    const highs = quote?.high ?? [];
    const lows = quote?.low ?? [];
    const closes = quote?.close ?? [];
    const volumes = quote?.volume ?? [];
    const lines = ["Date,Open,High,Low,Close,Volume"];
    timestamps.forEach((ts, i) => {
      const dateStr = new Date(ts * 1000).toISOString().slice(0, 10);
      lines.push([dateStr, opens[i] ?? "", highs[i] ?? "", lows[i] ?? "", closes[i] ?? "", volumes[i] ?? ""].join(","));
    });
    return lines.join("\n");
  } catch {
    return "Date,Open,High,Low,Close,Volume\n";
  }
}

/** Analyst recommendations from quote (averageAnalystRating). */
export async function getAnalystRecommendations(ticker: string): Promise<{
  ticker: string;
  recommendation: string | null;
  target_price: number | null;
  breakdown: Record<string, number>;
  total_analysts: number;
  latest_date: string | null;
  error?: string;
}> {
  const sym = ticker.toUpperCase();
  try {
    const yf = await getYahooFinance();
    const q = await yf.quote(sym) as Record<string, unknown>;
    return {
      ticker: sym,
      recommendation: (q.averageAnalystRating as string) ?? null,
      target_price: null,
      breakdown: {},
      total_analysts: 0,
      latest_date: null,
    };
  } catch (e) {
    return { ticker: sym, recommendation: null, target_price: null, breakdown: {}, total_analysts: 0, latest_date: null, error: String(e) };
  }
}

/** News. Stub; Yahoo news endpoint often requires cookie/crumb. */
export async function getNews(
  ticker: string,
  _vendor?: string,
  _lookbackDays: number = 7
): Promise<{ ticker: string; date: string; articles: unknown[]; count: number; error?: string }> {
  const sym = ticker.toUpperCase();
  const currDate = new Date().toISOString().slice(0, 10);
  return { ticker: sym, date: currDate, articles: [], count: 0 };
}
