export function formatDate(dateStr: string | null | undefined, includeTime = false): string {
  if (!dateStr) return '—';
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(dateStr)
    ? `${dateStr}Z`
    : dateStr;
  const date = new Date(normalized);
  if (isNaN(date.getTime())) return '—';
  
  if (includeTime) {
    // Use toLocaleString() with 24-hour format
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  }
  
  // For date only, use toLocaleDateString()
  return date.toLocaleDateString();
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
  
  // Handle MissionControlRunResponse
  if (result && typeof result === 'object') {
    const r = result as {
      triggered?: Array<{ ticker: string }>;
      already_running?: Array<{ ticker: string }>;
      skipped_existing?: string[];
      invalid_tickers?: string[];
      failed?: Array<{ ticker: string }>;
    };
    
    const parts: string[] = [];
    
    if (r.triggered && r.triggered.length > 0) {
      parts.push(`✓ Triggered: ${r.triggered.map(t => t.ticker).join(', ')}`);
    }
    if (r.already_running && r.already_running.length > 0) {
      parts.push(`⟳ Already running: ${r.already_running.map(t => t.ticker).join(', ')}`);
    }
    if (r.skipped_existing && r.skipped_existing.length > 0) {
      parts.push(`⊘ Skipped (recent): ${r.skipped_existing.join(', ')}`);
    }
    if (r.invalid_tickers && r.invalid_tickers.length > 0) {
      parts.push(`✗ Invalid: ${r.invalid_tickers.join(', ')}`);
    }
    
    if (parts.length > 0) {
      return parts.join(' • ');
    }
  }
  
  return JSON.stringify(result);
}

// Made with Bob
