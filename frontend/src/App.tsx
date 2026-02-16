import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import HowItWorksPage from './pages/HowItWorksPage';
import ProfilePage from './pages/ProfilePage';
import StockPage from './pages/StockPage';
import TermsOfUsePage from './pages/TermsOfUsePage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import SubscriptionsPage from './pages/SubscriptionsPage';

function App() {
  return (
    <AuthProvider>
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="stocks/:ticker" element={<StockPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="subscriptions" element={<SubscriptionsPage />} />
          <Route path="admin" element={<AdminDashboardPage />} />
          <Route path="how-it-works" element={<HowItWorksPage />} />
          <Route path="terms" element={<TermsOfUsePage />} />
        </Route>
      </Routes>
    </Router>
    </AuthProvider>
  );
}

export default App;

