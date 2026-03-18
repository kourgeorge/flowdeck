import { useState } from 'react';
import { Link } from 'react-router-dom';
import DashboardNewsSection from '../components/DashboardNewsSection';
import PageHeader from '../components/PageHeader';
import TickerSearch from '../components/TickerSearch';
import { useAuth } from '../contexts/AuthContext';
import { useDashboardData } from '../hooks/useDashboardData';

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
  const { widgets, isLoading } = useDashboardData({
    enableRecentAnalyzed: false,
  });

  if (!user) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8 flex items-center justify-center">
        <div className="max-w-md text-center">
          <p className="text-gray-400 mb-6">Sign in to open your Newsroom and view headlines for your subscribed stocks.</p>
          <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  const subscribedTickers = widgets.map((widget) => widget.ticker);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PageHeader title="Personal Newsroom" icon={<NewsroomIcon />} compact />

      <div className="px-4 py-1 border-b border-gray-700 bg-gray-900 shrink-0">
        <TickerSearch compact />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 py-6 sm:p-6 lg:p-8">
          <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
            {isLoading && subscribedTickers.length === 0 ? (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
                <div className="flex items-center gap-2 text-gray-300 text-sm">
                  <svg className="w-4 h-4 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Loading newsroom...</span>
                </div>
              </div>
            ) : subscribedTickers.length > 0 ? (
              <DashboardNewsSection
                tickers={subscribedTickers}
                refreshIntervalMs={120000}
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
                onClearSearch={() => setSearchQuery('')}
              />
            ) : (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-10 text-center">
                <h2 className="text-xl font-semibold text-white">Your newsroom is empty</h2>
                <p className="mt-2 text-sm text-gray-400">
                  Subscribe to a few stocks from the dashboard or a ticker page to populate the newsroom.
                </p>
                <div className="mt-6">
                  <Link to="/dashboard" className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700">
                    Go to Dashboard
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
