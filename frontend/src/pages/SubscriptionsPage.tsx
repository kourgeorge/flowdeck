import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StockWidget from '../components/StockWidget';
import StockListView from '../components/StockListView';
import { stockApi } from '../services/api';
import { subscriptionApi } from '../services/subscriptionApi';
import type { StockWidget as StockWidgetType } from '../services/types';
import { useAuth } from '../contexts/AuthContext';

type ViewMode = 'tile' | 'list';

export default function SubscriptionsPage() {
  const { user } = useAuth();
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch('/stocks.json')
      .then((res) => res.json())
      .then((arr: Array<{ ticker: string; name: string }>) => {
        const map: Record<string, string> = {};
        arr.forEach(({ ticker, name }) => {
          map[ticker] = name;
        });
        setTickerToName(map);
      })
      .catch(() => {});
  }, []);

  const loadSubscriptions = async () => {
    if (!user) {
      setWidgets([]);
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      const subs = await subscriptionApi.list();
      const tickers = subs.map((s) => s.ticker);
      if (tickers.length > 0) {
        const res = await stockApi.getWidgets(tickers);
        setWidgets(res.widgets);
      } else {
        setWidgets([]);
      }
    } catch {
      setWidgets([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSubscriptions();
    const interval = setInterval(loadSubscriptions, 60000);
    return () => clearInterval(interval);
  }, [user]);

  if (!user) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8 flex items-center justify-center">
        <div className="max-w-md text-center">
          <h1 className="text-2xl font-semibold text-white mb-2">My Subscriptions</h1>
          <p className="text-gray-400 mb-6">
            Sign in to view and manage your subscribed stocks.
          </p>
          <Link
            to="/"
            className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
          >
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full">
          <h1 className="text-2xl font-semibold text-white mb-4">My Subscriptions</h1>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-gray-800 rounded-lg border border-gray-700 p-6 animate-pulse">
                <div className="h-8 bg-gray-700 rounded mb-4" />
                <div className="h-12 bg-gray-700 rounded mb-2" />
                <div className="h-6 bg-gray-700 rounded mb-4" />
                <div className="h-4 bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] px-4 py-6 sm:p-6 lg:p-8">
      <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold text-white">My Subscriptions</h1>
          {widgets.length > 0 && (
            <div className="flex rounded-lg border border-gray-600 overflow-hidden">
              <button
                type="button"
                onClick={() => setViewMode('tile')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'tile'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                Tiles
              </button>
              <button
                type="button"
                onClick={() => setViewMode('list')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'list'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                List
              </button>
            </div>
          )}
        </div>

        {widgets.length === 0 ? (
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
            <p className="text-gray-400 mb-4">You haven’t subscribed to any stocks yet.</p>
            <p className="text-gray-500 text-sm mb-6">
              Subscribe to stocks from the home page to see them here.
            </p>
            <Link
              to="/"
              className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
            >
              Browse stocks
            </Link>
          </div>
        ) : viewMode === 'tile' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {widgets.map((widget) => (
              <StockWidget key={widget.ticker} widget={widget} />
            ))}
          </div>
        ) : (
          <StockListView widgets={widgets} tickerToName={tickerToName} />
        )}
      </div>
    </div>
  );
}
