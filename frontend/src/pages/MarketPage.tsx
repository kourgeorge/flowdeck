import { useNavigate } from 'react-router-dom';
import MarketView from '../components/MarketView';

export default function MarketPage() {
  const navigate = useNavigate();

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full overflow-x-hidden">
          <MarketView
            onSelectTicker={(ticker) => navigate(`/tickers/${ticker}`)}
          />
        </div>
      </div>
    </div>
  );
}
