import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import HowItWorksPage from './pages/HowItWorksPage';
import ArchitecturePage from './pages/ArchitecturePage';
import ProfilePage from './pages/ProfilePage';
import StockPage from './pages/StockPage';
import TermsOfUsePage from './pages/TermsOfUsePage';
import ContactUsPage from './pages/ContactUsPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import SubscriptionsPage from './pages/SubscriptionsPage';
import PaymentSuccessPage from './pages/PaymentSuccessPage';
import PaymentCancelPage from './pages/PaymentCancelPage';

function App() {
  return (
    <AuthProvider>
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="stocks/:ticker" element={<StockPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="dashboard" element={<SubscriptionsPage />} />
          <Route path="subscriptions" element={<Navigate to="/dashboard" replace />} />
          <Route path="admin" element={<AdminDashboardPage />} />
          <Route path="how-it-works" element={<HowItWorksPage />} />
          <Route path="architecture" element={<ArchitecturePage />} />
          <Route path="terms" element={<TermsOfUsePage />} />
          <Route path="contact" element={<ContactUsPage />} />
          <Route path="payment/success" element={<PaymentSuccessPage />} />
          <Route path="payment/cancel" element={<PaymentCancelPage />} />
        </Route>
      </Routes>
    </Router>
    </AuthProvider>
  );
}

export default App;
