import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import StockDetailPanel from '../components/StockDetailPanel';
import StockSearch from '../components/StockSearch';

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  // Keep a session-scoped history stack of visited tickers
  const historyRef = useRef<string[]>([]);
  const posRef = useRef<number>(-1);
  const [historyPos, setHistoryPos] = useState(-1);

  useEffect(() => {
    if (!ticker) return;
    const upper = ticker.toUpperCase();
    const stack = historyRef.current;
    const pos = posRef.current;

    // If we navigated back/forward via our own buttons the ticker is already in the stack
    if (stack[pos] === upper) return;

    // Truncate forward history when navigating to a new ticker
    const newStack = stack.slice(0, pos + 1);
    newStack.push(upper);
    historyRef.current = newStack;
    posRef.current = newStack.length - 1;
    setHistoryPos(newStack.length - 1);
  }, [ticker, location.key]);

  if (!ticker) return null;

  const stack = historyRef.current;
  const pos = posRef.current;
  const canBack = pos > 0;
  const canForward = pos < stack.length - 1;
  const backTicker = canBack ? stack[pos - 1] : null;
  const forwardTicker = canForward ? stack[pos + 1] : null;

  const goBack = () => {
    if (!canBack) return;
    posRef.current = pos - 1;
    setHistoryPos(pos - 1);
    navigate(`/tickers/${stack[pos - 1]}`);
  };

  const goForward = () => {
    if (!canForward) return;
    posRef.current = pos + 1;
    setHistoryPos(pos + 1);
    navigate(`/tickers/${stack[pos + 1]}`);
  };

  return (
    <div>
      {/* Search header */}
      <div className="bg-gray-800/80 border-b border-gray-700 px-4 py-2">
        <div className="flex items-center gap-3 max-w-layout mx-auto">
          {/* Back / Forward */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={goBack}
              disabled={!canBack}
              title={backTicker ? `← ${backTicker}` : 'No previous stock'}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-sm font-medium border border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              {backTicker && <span className="hidden sm:inline text-xs">{backTicker}</span>}
            </button>
            <button
              onClick={goForward}
              disabled={!canForward}
              title={forwardTicker ? `${forwardTicker} →` : 'No next stock'}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-sm font-medium border border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {forwardTicker && <span className="hidden sm:inline text-xs">{forwardTicker}</span>}
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          {/* Search — centered, narrower */}
          <div className="flex-1 flex justify-center">
            <div className="w-full max-w-sm">
              <StockSearch compact />
            </div>
          </div>
        </div>
      </div>

      <StockDetailPanel ticker={ticker} />
    </div>
  );
}

// Made with Bob
