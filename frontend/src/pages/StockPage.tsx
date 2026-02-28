import { useParams } from 'react-router-dom';
import StockDetailPanel from '../components/StockDetailPanel';
import StockSearch from '../components/StockSearch';

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();

  if (!ticker) return null;

  return (
    <div>
      {/* Search header */}
      <div className="bg-gray-800/80 border-b border-gray-700 px-4 py-2">
        <div className="max-w-layout mx-auto">
          <StockSearch compact />
        </div>
      </div>

      <StockDetailPanel ticker={ticker} />
    </div>
  );
}

// Made with Bob
