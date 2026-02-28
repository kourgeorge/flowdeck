import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import StockDetailPanel from '../components/StockDetailPanel';
import StockSearch from '../components/StockSearch';

interface Stock {
  ticker: string;
  name: string;
}

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const [stocks, setStocks] = useState<Stock[]>([]);

  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((data: Stock[]) => setStocks(data))
      .catch(() => {});
  }, []);

  if (!ticker) return null;

  const upperTicker = ticker.toUpperCase();
  const currentIndex = stocks.findIndex((s) => s.ticker === upperTicker);
  const prevStock = currentIndex > 0 ? stocks[currentIndex - 1] : null;
  const nextStock = currentIndex >= 0 && currentIndex < stocks.length - 1 ? stocks[currentIndex + 1] : null;

  return (
    <div>
      {/* Search header */}
      <div className="bg-gray-800/80 border-b border-gray-700 px-4 py-2">
        <div className="flex items-center justify-center gap-3 max-w-layout mx-auto">
          {/* Prev */}
          <button
            onClick={() => prevStock && navigate(`/tickers/${prevStock.ticker}`)}
            disabled={!prevStock}
            title={prevStock ? `← ${prevStock.ticker}` : undefined}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium border border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            <span className="hidden sm:inline">{prevStock?.ticker ?? ''}</span>
          </button>

          {/* Search — centered, narrower */}
          <div className="w-full max-w-sm">
            <StockSearch compact />
          </div>

          {/* Next */}
          <button
            onClick={() => nextStock && navigate(`/tickers/${nextStock.ticker}`)}
            disabled={!nextStock}
            title={nextStock ? `${nextStock.ticker} →` : undefined}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium border border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            <span className="hidden sm:inline">{nextStock?.ticker ?? ''}</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      <StockDetailPanel ticker={ticker} />
    </div>
  );
}

// Made with Bob
