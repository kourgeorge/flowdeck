/** Known currency codes -> symbol for price display. Missing codes fall back to "X.XX CODE". */
const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$',
  USDT: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  CHF: 'CHF',
  // ILS / ILA: use code suffix (e.g. "10,200.00 ILS") not symbol
  CAD: 'C$',
  AUD: 'A$',
  HKD: 'HK$',
  SEK: 'kr',
  NOK: 'kr',
  DKK: 'kr',
};

/**
 * Format a price amount with the appropriate currency symbol or code.
 * @param amount - Numeric price
 * @param currency - Currency code from quote (e.g. "USD", "ILS", "ILA"). If missing, defaults to $.
 * @param decimals - Decimal places (default 2)
 */
export function formatPrice(
  amount: number,
  currency?: string | null,
  decimals: number = 2
): string {
  const code = currency?.trim().toUpperCase() || 'USD';
  const symbol = CURRENCY_SYMBOLS[code];
  const absoluteAmount = Math.abs(amount);
  const formatted = absoluteAmount.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const prefix = amount < 0 ? '-' : '';
  if (symbol) {
    return `${prefix}${symbol}${formatted}`;
  }
  return `${prefix}${formatted} ${code}`;
}
