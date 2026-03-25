import { useLocation } from 'react-router-dom';
import { APP_NAME, COPILOT_NAME, DEFAULT_SEO_DESCRIPTION } from '../config';
import { useAuth } from '../contexts/AuthContext';
import { absoluteUrl, useSeo, type SeoOptions } from '../seo';

function normalizePath(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

function isPrivateRoute(pathname: string): boolean {
  return [
    '/dashboard',
    '/brief',
    '/chat',
    '/copilot',
    '/profile',
    '/admin',
    '/payment/success',
    '/payment/cancel',
    '/auth/callback',
  ].includes(pathname);
}

export default function RouteSeoManager() {
  const location = useLocation();
  const { user } = useAuth();
  const pathname = normalizePath(location.pathname);
  const searchParams = new URLSearchParams(location.search);

  const seo: SeoOptions = (() => {
    if (pathname === '/') {
      return {
        title: 'AI Stock Research Platform',
        description: 'Flowdeck helps investors move from live market data to actionable stock research with AI-generated analysis, portfolio monitoring, and conversational copilots.',
        path: '/',
        jsonLd: [
          {
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: APP_NAME,
            url: absoluteUrl('/'),
            logo: absoluteUrl('/logo.svg'),
          },
          {
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            name: APP_NAME,
            url: absoluteUrl('/'),
            description: 'AI stock research, market intelligence, and portfolio monitoring platform.',
          },
        ],
      };
    }

    if (pathname.startsWith('/tickers/')) {
      const ticker = decodeURIComponent(pathname.slice('/tickers/'.length)).toUpperCase();
      return {
        title: `${ticker} Stock Analysis & AI Research`,
        description: `Live market data, AI-generated stock analysis, news, fundamentals, technical context, and recommendation signals for ${ticker}.`,
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/market') {
      return {
        title: 'Market View',
        description: 'Track indices, sectors, movers, and market context in a single Flowdeck market intelligence workspace.',
        path: pathname,
      };
    }

    if (pathname === '/newsroom') {
      return {
        title: 'Newsroom',
        description: 'Follow company and market news with Flowdeck\'s investor-focused newsroom and research context.',
        path: pathname,
      };
    }

    if (pathname === '/portfolio-pulse') {
      return {
        title: 'Portfolio Pulse',
        description: 'Monitor portfolio-relevant moves, signals, and stock performance in Flowdeck\'s Portfolio Pulse dashboard.',
        path: pathname,
        robots: user ? 'noindex,nofollow' : 'index,follow',
      };
    }

    if (pathname === '/how-it-works') {
      return {
        title: 'How Flowdeck Works',
        description: 'Learn how Flowdeck combines live market data, specialist AI analysts, debate workflows, and risk checks to produce stock research and recommendations.',
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/tps') {
      return {
        title: 'Trading Plan Specification',
        description: 'Explore Flowdeck\'s trading plan specification framework and how the platform turns research into structured action plans.',
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/architecture') {
      return {
        title: 'Platform Architecture',
        description: 'Review the Flowdeck architecture behind AI analysis, market data workflows, and conversational research experiences.',
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/api-docs') {
      return {
        title: 'API Documentation',
        description: 'Browse Flowdeck API documentation for market data, AI analysis, and trading workflow integrations.',
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/docs') {
      const tab = searchParams.get('tab');
      const canonicalByTab: Record<string, string> = {
        'how-it-works': '/how-it-works',
        tps: '/tps',
        architecture: '/architecture',
        api: '/api-docs',
      };
      return {
        title: 'Documentation',
        description: 'Explore Flowdeck documentation, architecture notes, API references, and AI workflow guides.',
        path: pathname,
        canonicalUrl: absoluteUrl(canonicalByTab[tab ?? ''] ?? '/how-it-works'),
        robots: 'noindex,follow',
      };
    }

    if (pathname === '/terms') {
      return {
        title: 'Terms of Use',
        description: 'Read Flowdeck\'s terms of use for the AI-powered stock research and trading intelligence platform.',
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/privacy') {
      return {
        title: 'Privacy Policy',
        description: 'Learn how Flowdeck collects, uses, and protects your personal information and data privacy.',
        path: pathname,
        type: 'article',
      };
    }

    if (pathname === '/contact') {
      return {
        title: 'Contact',
        description: 'Contact Flowdeck for platform questions, partnerships, support, or product inquiries.',
        path: pathname,
      };
    }

    if (pathname === '/chat') {
      return {
        title: 'AI Analyst Agent',
        description: 'Flowdeck AI analyst workspace.',
        path: pathname,
        robots: 'noindex,nofollow',
      };
    }

    if (pathname === '/copilot') {
      return {
        title: `${COPILOT_NAME} Trading Copilot`,
        description: 'Flowdeck trading copilot workspace.',
        path: pathname,
        robots: 'noindex,nofollow',
      };
    }

    if (pathname.startsWith('/r/')) {
      return {
        title: 'Shared Report',
        description: 'Shared Flowdeck research report.',
        path: pathname,
        robots: 'noindex,nofollow',
      };
    }

    if (pathname === '/how-it-works/tps') {
      return {
        title: 'Trading Plan Specification',
        description: 'Legacy documentation route for Flowdeck\'s trading plan specification.',
        path: pathname,
        canonicalUrl: absoluteUrl('/tps'),
        robots: 'noindex,follow',
      };
    }

    if (isPrivateRoute(pathname)) {
      return {
        title: APP_NAME,
        description: DEFAULT_SEO_DESCRIPTION,
        path: pathname,
        robots: 'noindex,nofollow',
      };
    }

    return {
      title: APP_NAME,
      description: DEFAULT_SEO_DESCRIPTION,
      path: pathname,
      robots: 'noindex,follow',
    };
  })();

  useSeo(seo);

  return null;
}
