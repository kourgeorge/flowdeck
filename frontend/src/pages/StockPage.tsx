import { useParams } from 'react-router-dom';
import StockDetailPanel from '../components/StockDetailPanel';

export default function StockPage() {
  const { ticker } = useParams<{ ticker: string }>();

  if (!ticker) return null;

  return <StockDetailPanel ticker={ticker} />;
}

// Made with Bob
