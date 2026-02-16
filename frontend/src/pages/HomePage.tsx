import { useEffect, useState } from 'react';
import StockWidget from '../components/StockWidget';
import StockListView from '../components/StockListView';
import StockSearch from '../components/StockSearch';
import { stockApi, API_BASE_URL } from '../services/api';
import type { StockWidget as StockWidgetType } from '../services/types';
import { APP_NAME, LOGO_PATH } from '../config';

type ViewMode = 'tile' | 'list';

function Section({
  title,
  widgets,
  viewMode,
  setViewMode,
  tickerToName,
  emptyMessage,
}: {
  title: string;
  widgets: StockWidgetType[];
  viewMode: ViewMode;
  setViewMode: (m: ViewMode) => void;
  tickerToName: Record<string, string>;
  emptyMessage: string;
}) {
  return (
    <div className="mb-10">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-2xl font-semibold text-white">{title}</h2>
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
      </div>
      {widgets.length === 0 ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
          <p className="text-gray-400 text-sm">{emptyMessage}</p>
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
  );
}

export default function HomePage() {
  const [widgets, setWidgets] = useState<StockWidgetType[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [tickerToName, setTickerToName] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const loadWidgets = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const today = new Date().toISOString().slice(0, 10);
      const response = await stockApi.getWidgets(undefined, today);
      setWidgets(response.widgets);
    } catch (err: any) {
      console.error('Failed to load widgets:', err);
      const errorMessage = err?.response?.data?.detail || err?.message || 'Failed to load stock data.';
      const backendHint = API_BASE_URL ? ` (${API_BASE_URL})` : '';
      setError(`Failed to load stock data: ${errorMessage}. Please check if the backend is running${backendHint}.`);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadWidgets();
    const interval = setInterval(loadWidgets, 60000);
    return () => clearInterval(interval);
  }, []);

  const MAJOR_STOCKS_LIMIT = 10;
  const hasMajorFlag = widgets.some((w) => w.is_major === true || w.is_major === false);
  const majorFiltered = hasMajorFlag
    ? widgets.filter((w) => w.is_major === true)
    : widgets;
  const majorWidgets = majorFiltered.slice(0, MAJOR_STOCKS_LIMIT);

  if (isLoading && widgets.length === 0) {
    return (
      <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
          <div className="flex flex-col items-center justify-center mb-8">
            <img src={LOGO_PATH} alt="" className="w-40 h-40 object-contain mb-4" />
            <h1 className="text-4xl font-bold text-white">{APP_NAME}</h1>
            <p className="text-gray-400 mt-2 text-center max-w-2xl">
            Invest with the odds in your favor—an AI committee of specialized agents
            turns market noise into clear insights, smarter portfolio moves, and
            confident, data-driven decisions.
          </p>
          </div>
          <StockSearch />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="bg-gray-800 rounded-lg border border-gray-700 p-6 animate-pulse">
                <div className="h-8 bg-gray-700 rounded mb-4"></div>
                <div className="h-12 bg-gray-700 rounded mb-2"></div>
                <div className="h-6 bg-gray-700 rounded mb-4"></div>
                <div className="h-4 bg-gray-700 rounded"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
      <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
        <div className="flex flex-col items-center justify-center mb-8">
          <img src={LOGO_PATH} alt="" className="w-40 h-40 object-contain mb-4" />
          <h1 className="text-4xl font-bold text-white">{APP_NAME}</h1>
          <p className="text-gray-400 mt-2 text-center max-w-2xl">
            Invest with the odds in your favor—an AI committee of specialized agents
            turns market noise into clear insights, smarter portfolio moves, and
            confident, data-driven decisions.
          </p>
        </div>

        <StockSearch />

        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-400 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {widgets.length === 0 ? (
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center mb-10">
            <p className="text-gray-400 mb-4">No stock data available</p>
            <button
              onClick={loadWidgets}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          <Section
            title="Major Stocks"
            widgets={majorWidgets}
            viewMode={viewMode}
            setViewMode={setViewMode}
            tickerToName={tickerToName}
            emptyMessage="No major stock data available."
          />
        )}
      </div>
    </div>
  );
}

