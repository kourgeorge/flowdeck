import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import PortfolioPulseDashboard from '../components/PortfolioPulseDashboard';
import TickerSearch from '../components/TickerSearch';
import { SIGNIFICANT_SEVEN_RANK, SIGNIFICANT_SEVEN_TICKERS } from '../constants/majorTickers';
import { useAuth } from '../contexts/AuthContext';
import { useDashboardData } from '../hooks/useDashboardData';
import { tickerApi } from '../services/api';
import type { TickerWidget } from '../services/types';

function PulseIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 12h4l2.5-6 5 12 2.5-6H21"
      />
    </svg>
  );
}

export default function PortfolioPulsePage() {
  const { user } = useAuth();
  const [publicWidgets, setPublicWidgets] = useState<TickerWidget[]>([]);
  const [publicError, setPublicError] = useState<string | null>(null);
  const [isLoadingPublicWidgets, setIsLoadingPublicWidgets] = useState(false);
  const { widgets, tickerToName, isLoading } = useDashboardData({
    enableRecentAnalyzed: false,
  });

  useEffect(() => {
    if (user) {
      setPublicWidgets([]);
      setPublicError(null);
      setIsLoadingPublicWidgets(false);
      return;
    }

    let cancelled = false;

    const loadPublicWidgets = async () => {
      setIsLoadingPublicWidgets(true);
      setPublicError(null);
      try {
        const today = new Date().toISOString().slice(0, 10);
        const response = await tickerApi.getWidgets([...SIGNIFICANT_SEVEN_TICKERS], today);
        if (cancelled) return;
        const sorted = [...response.widgets].sort((a, b) => {
          const aRank = SIGNIFICANT_SEVEN_RANK.get(a.ticker) ?? Number.MAX_SAFE_INTEGER;
          const bRank = SIGNIFICANT_SEVEN_RANK.get(b.ticker) ?? Number.MAX_SAFE_INTEGER;
          if (aRank !== bRank) return aRank - bRank;
          return a.ticker.localeCompare(b.ticker);
        });
        setPublicWidgets(sorted);
      } catch {
        if (!cancelled) {
          setPublicWidgets([]);
          setPublicError('Failed to load the Significant 7 preview.');
        }
      } finally {
        if (!cancelled) setIsLoadingPublicWidgets(false);
      }
    };

    loadPublicWidgets();
    const interval = setInterval(loadPublicWidgets, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [user]);

  const displayWidgets = user ? widgets : publicWidgets;
  const pageIsLoading = user ? isLoading : isLoadingPublicWidgets;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Portfolio Pulse" icon={<PulseIcon />} />

      <div className="px-4 pt-2 border-b border-gray-700 bg-gray-900 shrink-0">
        <div className="pb-2">
          <TickerSearch compact />
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 py-6 sm:p-6 lg:p-8">
          <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
            {!user && (
              <div className="mb-6 rounded-xl border border-blue-700/40 bg-blue-950/40 px-4 py-3 text-sm text-blue-100">
                Viewing a public Portfolio Pulse preview powered by the Significant 7.{' '}
                <Link to="/" className="font-medium text-white underline decoration-blue-400/60 underline-offset-2 hover:text-blue-100">
                  Sign in
                </Link>{' '}
                to replace it with your own subscribed portfolio.
              </div>
            )}

            {publicError && !user && (
              <div className="mb-6 rounded-lg border border-amber-600/40 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
                {publicError}
              </div>
            )}

            {pageIsLoading && displayWidgets.length === 0 ? (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <div className="flex items-center gap-2 text-gray-300 text-sm">
                  <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Loading portfolio pulse…</span>
                </div>
              </div>
            ) : (
              <PortfolioPulseDashboard
                widgets={displayWidgets}
                tickerToName={tickerToName}
                publicPreview={!user}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
