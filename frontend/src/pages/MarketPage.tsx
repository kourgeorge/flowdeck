import { useNavigate } from 'react-router-dom';
import NewMarketView from '../components/NewMarketView';
import PageHeader from '../components/PageHeader';
import TickerSearch from '../components/TickerSearch';

export default function MarketPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <PageHeader
        title="Market View"
        icon={
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        }
      />
      <div className="px-4 pt-2 border-b border-gray-700 bg-gray-900 shrink-0">
        <div className="pb-2">
          <TickerSearch compact />
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 py-6 sm:p-6 lg:p-8">
          <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
            <NewMarketView
              onSelectTicker={(ticker) => navigate(`/tickers/${ticker}`)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
