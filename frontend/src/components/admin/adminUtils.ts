export function formatDate(dateStr: string | null | undefined, includeTime = false): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '—';
  
  const options: Intl.DateTimeFormatOptions = {
    dateStyle: 'medium',
    ...(includeTime && { timeStyle: 'short' }),
  };
  
  return new Intl.DateTimeFormat('en-US', options).format(date);
}

export function formatMarketCap(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  return `$${value.toLocaleString()}`;
}

export function quoteTypeSortRank(quoteType: string | null | undefined): number {
  if (quoteType === 'EQUITY') return 0;
  return 1;
}

export function compareNullableNumber(a: number | null | undefined, b: number | null | undefined): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return a - b;
}

export function compareNullableString(a: string | null | undefined, b: string | null | undefined): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return a.localeCompare(b, undefined, { sensitivity: 'base' });
}

export function summarizeMissionRunResult(result: unknown): string {
  if (typeof result === 'string') return result;
  if (result && typeof result === 'object' && 'message' in result) {
    return String((result as { message: unknown }).message);
  }
  return JSON.stringify(result);
}

// Made with Bob
