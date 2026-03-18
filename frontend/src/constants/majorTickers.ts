export const SIGNIFICANT_SEVEN_TICKERS = ['NVDA', 'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA'] as const;

export const SIGNIFICANT_SEVEN_RANK = new Map<string, number>(
  SIGNIFICANT_SEVEN_TICKERS.map((ticker, index) => [ticker, index])
);
