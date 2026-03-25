import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import ProfilePage from './pages/ProfilePage';
import TickerPage from './pages/StockPage';
import TermsOfUsePage from './pages/TermsOfUsePage';
import PrivacyPage from './pages/PrivacyPage';
import ContactUsPage from './pages/ContactUsPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import BriefPage from './pages/BriefPage';
import DashboardPage from './pages/DashboardPage';
import MarketPage from './pages/MarketPage';
import NewsroomPage from './pages/NewsroomPage';
import PortfolioPulsePage from './pages/PortfolioPulsePage';
import PaymentSuccessPage from './pages/PaymentSuccessPage';
import PaymentCancelPage from './pages/PaymentCancelPage';
import ChatPage from './pages/ChatPage';
import CopilotPage from './pages/CopilotPage';
import DocsPage from './pages/DocsPage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import SharedReportPage from './pages/SharedReportPage';
import HowItWorksPage from './pages/HowItWorksPage';
import TpsPage from './pages/TpsPage';
import ArchitecturePage from './pages/ArchitecturePage';
import ApiDocsPage from './pages/ApiDocsPage';
import RouteSeoManager from './components/RouteSeoManager';

function App() {
  return (
    <AuthProvider>
    <Router>
      <RouteSeoManager />
      <Routes>
        <Route path="r/:token" element={<SharedReportPage />} />
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="tickers/:ticker" element={<TickerPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="newsroom" element={<NewsroomPage />} />
          <Route path="portfolio-pulse" element={<PortfolioPulsePage />} />
          <Route path="brief" element={<BriefPage />} />
          <Route path="market" element={<MarketPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="copilot" element={<CopilotPage />} />
          <Route path="subscriptions" element={<Navigate to="/dashboard" replace />} />
          <Route path="admin" element={<AdminDashboardPage />} />
          <Route path="docs" element={<DocsPage />} />
          <Route path="how-it-works" element={<HowItWorksPage />} />
          <Route path="how-it-works/tps" element={<Navigate to="/tps" replace />} />
          <Route path="tps" element={<TpsPage />} />
          <Route path="architecture" element={<ArchitecturePage />} />
          <Route path="api-docs" element={<ApiDocsPage />} />
          <Route path="terms" element={<TermsOfUsePage />} />
          <Route path="privacy" element={<PrivacyPage />} />
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
