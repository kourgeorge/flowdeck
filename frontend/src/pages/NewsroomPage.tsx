import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import DashboardNewsSection, { NewsroomSkeleton } from '../components/DashboardNewsSection';
import PageHeader from '../components/PageHeader';
import TickerSearch from '../components/TickerSearch';
import { SIGNIFICANT_SEVEN_RANK, SIGNIFICANT_SEVEN_TICKERS } from '../constants/majorTickers';
import { useAuth } from '../contexts/AuthContext';
import { useDashboardData } from '../hooks/useDashboardData';
import { tickerApi } from '../services/api';
import type { TickerWidget } from '../services/types';

function NewsroomIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 5H5a2 2 0 00-2 2v10a2 2 0 002 2h14a2 2 0 002-2V7a2 2 0 00-2-2z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 9h10M7 13h6M7 17h10" />
    </svg>
  );
}

export default function NewsroomPage() {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [publicWidgets, setPublicWidgets] = useState<TickerWidget[]>([]);
  const [publicError, setPublicError] = useState<string | null>(null);
  const [isLoadingPublicWidgets, setIsLoadingPublicWidgets] = useState(false);
  const { widgets, isLoading } = useDashboardData({
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
        const sorted = [...response.widgets].sort((left, right) => {
          const leftRank = SIGNIFICANT_SEVEN_RANK.get(left.ticker) ?? Number.MAX_SAFE_INTEGER;
          const rightRank = SIGNIFICANT_SEVEN_RANK.get(right.ticker) ?? Number.MAX_SAFE_INTEGER;
          if (leftRank !== rightRank) return leftRank - rightRank;
          return left.ticker.localeCompare(right.ticker);
        });
        setPublicWidgets(sorted);
      } catch {
        if (!cancelled) {
          setPublicWidgets([]);
          setPublicError('Failed to load the Significant 7 newsroom preview.');
        }
      } finally {
        if (!cancelled) setIsLoadingPublicWidgets(false);
      }
    };

    loadPublicWidgets();
    const intervalId = setInterval(loadPublicWidgets, 60000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [user]);

  const displayWidgets = user ? widgets : publicWidgets;
  const displayTickers = displayWidgets.map((widget) => widget.ticker);
  const pageIsLoading = user ? isLoading : isLoadingPublicWidgets;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Personal Newsroom" icon={<NewsroomIcon />} />

      <div className="px-4 py-1 border-b border-gray-700 bg-gray-900 shrink-0">
        <TickerSearch compact />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 py-6 sm:p-6 lg:p-8">
          <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
            {!user && (
              <div className="mb-6 rounded-xl border border-blue-700/40 bg-blue-950/40 px-4 py-3 text-sm text-blue-100">
                Viewing a public Newsroom preview powered by the Significant 7.{' '}
                <Link to="/" className="font-medium text-white underline decoration-blue-400/60 underline-offset-2 hover:text-blue-100">
                  Sign in
                </Link>{' '}
                to replace it with your own personal newsroom.
              </div>
            )}

            {publicError && !user && (
              <div className="mb-6 rounded-lg border border-amber-600/40 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
                {publicError}
              </div>
            )}

            {pageIsLoading && displayTickers.length === 0 ? (
              <NewsroomSkeleton />
            ) : displayTickers.length > 0 ? (
              <DashboardNewsSection
                tickers={displayTickers}
                refreshIntervalMs={120000}
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
                onClearSearch={() => setSearchQuery('')}
              />
            ) : (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-10 text-center">
                <h2 className="text-xl font-semibold text-white">{user ? 'Your newsroom is empty' : 'Newsroom preview unavailable'}</h2>
                <p className="mt-2 text-sm text-gray-400">
                  {user
                    ? 'Subscribe to a few stocks from the dashboard or a ticker page to populate the newsroom.'
                    : 'Try again shortly or sign in to open a personal newsroom curated from your subscribed stocks.'}
                </p>
                <div className="mt-6">
                  <Link
                    to={user ? '/dashboard' : '/'}
                    className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                  >
                    {user ? 'Go to Dashboard' : 'Go to Home'}
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
