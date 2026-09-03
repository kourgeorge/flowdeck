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

function techArticleSchema(headline: string, path: string) {
  return {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    headline,
    author: { '@type': 'Organization', name: APP_NAME, url: absoluteUrl('/') },
    publisher: {
      '@type': 'Organization',
      name: APP_NAME,
      logo: { '@type': 'ImageObject', url: absoluteUrl('/logo.svg') },
    },
    mainEntityOfPage: absoluteUrl(path),
  };
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
            '@type': 'WebSite',
            name: APP_NAME,
            url: absoluteUrl('/'),
            description: 'AI stock research, market intelligence, and portfolio monitoring platform.',
            potentialAction: {
              '@type': 'SearchAction',
              target: `${absoluteUrl('/tickers/')}{search_term_string}`,
              'query-input': 'required name=search_term_string',
            },
          },
        ],
      };
    }

    if (pathname.startsWith('/tickers/')) {
      const ticker = decodeURIComponent(pathname.slice('/tickers/'.length)).toUpperCase();
      const title = `${ticker} Stock Analysis & AI Research`;
      const description = `Live market data, AI-generated stock analysis, news, fundamentals, technical context, and recommendation signals for ${ticker}.`;
      return {
        title,
        description,
        path: pathname,
        type: 'article',
        jsonLd: [
          {
            '@context': 'https://schema.org',
            '@type': 'Article',
            headline: title,
            description,
            author: { '@type': 'Organization', name: APP_NAME, url: absoluteUrl('/') },
            publisher: {
              '@type': 'Organization',
              name: APP_NAME,
              logo: { '@type': 'ImageObject', url: absoluteUrl('/logo.svg') },
            },
            mainEntityOfPage: absoluteUrl(pathname),
          },
          {
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            itemListElement: [
              { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteUrl('/') },
              { '@type': 'ListItem', position: 2, name: 'Market', item: absoluteUrl('/market') },
              { '@type': 'ListItem', position: 3, name: ticker, item: absoluteUrl(pathname) },
            ],
          },
        ],
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
      const title = 'How Flowdeck Works';
      return {
        title,
        description: 'Learn how Flowdeck combines live market data, specialist AI analysts, debate workflows, and risk checks to produce stock research and recommendations.',
        path: pathname,
        type: 'article',
        jsonLd: [techArticleSchema(title, pathname)],
      };
    }

    if (pathname === '/tps') {
      const title = 'Trading Plan Specification';
      return {
        title,
        description: 'Explore Flowdeck\'s trading plan specification framework and how the platform turns research into structured action plans.',
        path: pathname,
        type: 'article',
        jsonLd: [techArticleSchema(title, pathname)],
      };
    }

    if (pathname === '/architecture') {
      const title = 'Platform Architecture';
      return {
        title,
        description: 'Review the Flowdeck architecture behind AI analysis, market data workflows, and conversational research experiences.',
        path: pathname,
        type: 'article',
        jsonLd: [techArticleSchema(title, pathname)],
      };
    }

    if (pathname === '/api-docs') {
      const title = 'API Documentation';
      return {
        title,
        description: 'Browse Flowdeck API documentation for market data, AI analysis, and trading workflow integrations.',
        path: pathname,
        type: 'article',
        jsonLd: [techArticleSchema(title, pathname)],
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
