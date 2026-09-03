import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import RouteSeoManager from './components/RouteSeoManager';

const HomePage = lazy(() => import('./pages/HomePage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const TickerPage = lazy(() => import('./pages/StockPage'));
const TermsOfUsePage = lazy(() => import('./pages/TermsOfUsePage'));
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'));
const ContactUsPage = lazy(() => import('./pages/ContactUsPage'));
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage'));
const BriefPage = lazy(() => import('./pages/BriefPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const MarketPage = lazy(() => import('./pages/MarketPage'));
const NewsroomPage = lazy(() => import('./pages/NewsroomPage'));
const PortfolioPulsePage = lazy(() => import('./pages/PortfolioPulsePage'));
const PaymentSuccessPage = lazy(() => import('./pages/PaymentSuccessPage'));
const PaymentCancelPage = lazy(() => import('./pages/PaymentCancelPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const CopilotPage = lazy(() => import('./pages/CopilotPage'));
const DocsPage = lazy(() => import('./pages/DocsPage'));
const AuthCallbackPage = lazy(() => import('./pages/AuthCallbackPage'));
const SharedReportPage = lazy(() => import('./pages/SharedReportPage'));
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage'));
const TpsPage = lazy(() => import('./pages/TpsPage'));
const ArchitecturePage = lazy(() => import('./pages/ArchitecturePage'));
const ApiDocsPage = lazy(() => import('./pages/ApiDocsPage'));

function RouteFallback() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-[#0f172a]">
      <svg className="h-8 w-8 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
    <Router>
      <RouteSeoManager />
      <Suspense fallback={<RouteFallback />}>
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
      </Suspense>
    </Router>
    </AuthProvider>
  );
}

export default App;
