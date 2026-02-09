import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import HowItWorksPage from './pages/HowItWorksPage';
import StockPage from './pages/StockPage';
import TermsOfUsePage from './pages/TermsOfUsePage';

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="stocks/:ticker" element={<StockPage />} />
          <Route path="how-it-works" element={<HowItWorksPage />} />
          <Route path="terms" element={<TermsOfUsePage />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;

