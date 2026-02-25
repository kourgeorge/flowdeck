import React from 'react';

interface InsiderTransaction {
  insider: string | null;
  position: string | null;
  transaction: string | null;
  start_date: string | null;
  shares: number | null;
  value: number | null;
  ownership: string | null;
  url: string | null;
  text: string | null;
}

interface InsiderTransactionsWidgetProps {
  transactions: InsiderTransaction[];
  ticker: string;
  onRetry?: () => void;
  isLoading?: boolean;
  errorMessage?: string | null;
}

const formatDate = (value: string | null): string => {
  if (!value) return 'N/A';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
};

const formatNumber = (value: number | null): string => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('en-US');
};

const formatCurrency = (value: number | null): string => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
};

const InsiderTransactionsWidget: React.FC<InsiderTransactionsWidgetProps> = ({
  transactions,
  ticker,
  onRetry,
  isLoading,
  errorMessage,
}) => {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        {errorMessage ? (
          <p className="text-amber-400/90 text-sm mb-2 font-medium">
            Unable to fetch insider transactions: {errorMessage}
          </p>
        ) : null}
        <p className="text-gray-400 text-sm mb-3">
          {isLoading
            ? 'Loading insider transactions…'
            : errorMessage
              ? 'Please try again later.'
              : `No insider transactions available for ${ticker}`}
        </p>
        {onRetry && !isLoading && (
          <button
            type="button"
            onClick={onRetry}
            className="text-sm px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Latest Insider Transactions</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-600 text-gray-400">
              <th className="py-2 pr-4 text-left font-medium">Date</th>
              <th className="py-2 pr-4 text-left font-medium">Insider</th>
              <th className="py-2 pr-4 text-left font-medium">Position</th>
              <th className="py-2 pr-4 text-left font-medium">Shares</th>
              <th className="py-2 pr-4 text-left font-medium">Type</th>
              <th className="py-2 pr-4 text-left font-medium">Ownership</th>
              <th className="py-2 pr-4 text-left font-medium">Value</th>
              <th className="py-2 text-left font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx, idx) => (
              <tr key={`${tx.insider ?? 'unknown'}-${tx.start_date ?? 'na'}-${idx}`} className="border-b border-gray-700/70">
                <td className="py-3 pr-4 text-gray-300">{formatDate(tx.start_date)}</td>
                <td className="py-3 pr-4 text-white font-medium">{tx.insider || 'Unknown'}</td>
                <td className="py-3 pr-4 text-gray-300">{tx.position || '—'}</td>
                <td className="py-3 pr-4 text-gray-300">{formatNumber(tx.shares)}</td>
                <td className="py-3 pr-4 text-gray-300">{tx.transaction || '—'}</td>
                <td className="py-3 pr-4 text-gray-300">{tx.ownership || '—'}</td>
                <td className="py-3 pr-4 text-gray-300">{formatCurrency(tx.value)}</td>
                <td className="py-3">
                  {tx.url ? (
                    <a
                      href={tx.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 underline"
                    >
                      Link
                    </a>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default InsiderTransactionsWidget;
