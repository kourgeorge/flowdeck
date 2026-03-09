import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import ProfilePage from './pages/ProfilePage';
import TickerPage from './pages/StockPage';
import TermsOfUsePage from './pages/TermsOfUsePage';
import ContactUsPage from './pages/ContactUsPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import DashboardPage from './pages/DashboardPage';
import MarketPage from './pages/MarketPage';
import PaymentSuccessPage from './pages/PaymentSuccessPage';
import PaymentCancelPage from './pages/PaymentCancelPage';
import ChatPage from './pages/ChatPage';
import CopilotPage from './pages/CopilotPage';
import DocsPage from './pages/DocsPage';
import AuthCallbackPage from './pages/AuthCallbackPage';

function App() {
  return (
    <AuthProvider>
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="tickers/:ticker" element={<TickerPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="market" element={<MarketPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="copilot" element={<CopilotPage />} />
          <Route path="subscriptions" element={<Navigate to="/dashboard" replace />} />
          <Route path="admin" element={<AdminDashboardPage />} />
          <Route path="docs" element={<DocsPage />} />
          <Route path="how-it-works" element={<Navigate to="/docs?tab=how-it-works" replace />} />
          <Route path="how-it-works/tps" element={<Navigate to="/docs?tab=tps" replace />} />
          <Route path="tps" element={<Navigate to="/docs?tab=tps" replace />} />
          <Route path="architecture" element={<Navigate to="/docs?tab=architecture" replace />} />
          <Route path="api-docs" element={<Navigate to="/docs?tab=api" replace />} />
          <Route path="terms" element={<TermsOfUsePage />} />
          <Route path="contact" element={<ContactUsPage />} />
          <Route path="payment/success" element={<PaymentSuccessPage />} />
          <Route path="payment/cancel" element={<PaymentCancelPage />} />
          <Route path="auth/callback" element={<AuthCallbackPage />} />
        </Route>
      </Routes>
    </Router>
    </AuthProvider>
  );
}

export default App;
