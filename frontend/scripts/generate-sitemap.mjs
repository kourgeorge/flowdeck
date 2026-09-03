import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SITE_URL = (process.env.VITE_SITE_URL ?? 'https://flowdeck.biz').replace(/\/$/, '');
const today = new Date().toISOString().slice(0, 10);
const SITEMAP_TICKERS = ['NVDA', 'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'TSLA'];

const staticRoutes = [
  { path: '/', changefreq: 'daily', priority: '1.0', source: 'src/pages/HomePage.tsx' },
  { path: '/market', changefreq: 'daily', priority: '0.9', source: 'src/pages/MarketPage.tsx' },
  { path: '/portfolio-pulse', changefreq: 'daily', priority: '0.8', source: 'src/pages/PortfolioPulsePage.tsx' },
  { path: '/newsroom', changefreq: 'hourly', priority: '0.8', source: 'src/pages/NewsroomPage.tsx' },
  { path: '/how-it-works', changefreq: 'monthly', priority: '0.7', source: 'src/pages/HowItWorksPage.tsx' },
  { path: '/tps', changefreq: 'monthly', priority: '0.6', source: 'src/pages/TpsPage.tsx' },
  { path: '/architecture', changefreq: 'monthly', priority: '0.6', source: 'src/pages/ArchitecturePage.tsx' },
  { path: '/api-docs', changefreq: 'weekly', priority: '0.6', source: 'src/pages/ApiDocsPage.tsx' },
  { path: '/terms', changefreq: 'yearly', priority: '0.3', source: 'src/pages/TermsOfUsePage.tsx' },
  { path: '/privacy', changefreq: 'yearly', priority: '0.3', source: 'src/pages/PrivacyPage.tsx' },
  { path: '/contact', changefreq: 'yearly', priority: '0.4', source: 'src/pages/ContactUsPage.tsx' },
];

const stocksPath = resolve('public', 'stocks.json');
const sitemapPath = resolve('public', 'sitemap.xml');
const stocks = JSON.parse(readFileSync(stocksPath, 'utf8'));

function escapeXml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

// Falls back to the build date if the file isn't tracked yet or git isn't
// available in the build environment (e.g. a source archive without .git).
function lastCommitDate(sourcePath) {
  if (!sourcePath) return today;
  try {
    const output = execFileSync(
      'git',
      ['log', '-1', '--format=%cs', '--', sourcePath],
      { cwd: resolve('.'), encoding: 'utf8' }
    ).trim();
    return output || today;
  } catch {
    return today;
  }
}

function renderUrl(loc, changefreq, priority, lastmod) {
  return [
    '  <url>',
    `    <loc>${escapeXml(loc)}</loc>`,
    `    <lastmod>${lastmod}</lastmod>`,
    `    <changefreq>${changefreq}</changefreq>`,
    `    <priority>${priority}</priority>`,
    '  </url>',
  ].join('\n');
}

const availableTickers = new Set(
  stocks
    .map((stock) => stock?.ticker)
    .filter((ticker) => typeof ticker === 'string' && ticker.length > 0)
);

// Ticker pages show live market data with no meaningful "content last
// changed" date of their own, so they keep the build-date stamp.
const tickerUrls = SITEMAP_TICKERS
  .filter((ticker) => availableTickers.has(ticker))
  .map((ticker) => renderUrl(`${SITE_URL}/tickers/${encodeURIComponent(ticker)}`, 'daily', '0.7', today));

const staticUrls = staticRoutes.map((route) =>
  renderUrl(`${SITE_URL}${route.path}`, route.changefreq, route.priority, lastCommitDate(route.source))
);

const xml = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...staticUrls,
  ...tickerUrls,
  '</urlset>',
  '',
].join('\n');

writeFileSync(sitemapPath, xml, 'utf8');
console.log(`Generated sitemap with ${staticUrls.length + tickerUrls.length} URLs at ${sitemapPath}`);
