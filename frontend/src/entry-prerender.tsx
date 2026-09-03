import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server';
import { Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import ArchitecturePage from './pages/ArchitecturePage';
import ContactUsPage from './pages/ContactUsPage';
import HowItWorksPage from './pages/HowItWorksPage';
import PrivacyPage from './pages/PrivacyPage';
import TermsOfUsePage from './pages/TermsOfUsePage';
import TpsPage from './pages/TpsPage';
import { resolveSeoTags, type ResolvedSeoTags } from './seo';
import { seoForPath } from './seoRoutes';

// Kept in sync with App.tsx's <Route> definitions for these six paths.
// A route missing here renders an empty <main>, which the prerender
// script's minTextLength/mainPresence gates catch.
const ROUTES = ['/architecture', '/contact', '/how-it-works', '/privacy', '/terms', '/tps'];

function PrerenderApp({ url }: { url: string }) {
  return (
    <AuthProvider>
      <StaticRouter location={url}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="architecture" element={<ArchitecturePage />} />
            <Route path="contact" element={<ContactUsPage />} />
            <Route path="how-it-works" element={<HowItWorksPage />} />
            <Route path="privacy" element={<PrivacyPage />} />
            <Route path="terms" element={<TermsOfUsePage />} />
            <Route path="tps" element={<TpsPage />} />
          </Route>
        </Routes>
      </StaticRouter>
    </AuthProvider>
  );
}

export function prerenderRoutes(): string[] {
  return ROUTES;
}

export interface RenderedRoute extends ResolvedSeoTags {
  url: string;
  html: string;
}

export function renderRoute(url: string): RenderedRoute {
  const html = renderToStaticMarkup(<PrerenderApp url={url} />);
  const seo = resolveSeoTags(seoForPath(url), url);
  return { url, html, ...seo };
}
