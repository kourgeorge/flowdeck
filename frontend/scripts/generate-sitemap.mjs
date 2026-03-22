import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SITE_URL = (process.env.VITE_SITE_URL ?? 'https://flowdeck.biz').replace(/\/$/, '');
const today = new Date().toISOString().slice(0, 10);

const staticRoutes = [
  { path: '/', changefreq: 'daily', priority: '1.0' },
  { path: '/market', changefreq: 'daily', priority: '0.9' },
  { path: '/portfolio-pulse', changefreq: 'daily', priority: '0.8' },
  { path: '/newsroom', changefreq: 'hourly', priority: '0.8' },
  { path: '/how-it-works', changefreq: 'monthly', priority: '0.7' },
  { path: '/tps', changefreq: 'monthly', priority: '0.6' },
  { path: '/architecture', changefreq: 'monthly', priority: '0.6' },
  { path: '/api-docs', changefreq: 'weekly', priority: '0.6' },
  { path: '/terms', changefreq: 'yearly', priority: '0.3' },
  { path: '/contact', changefreq: 'yearly', priority: '0.4' },
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

function renderUrl(loc, changefreq, priority) {
  return [
    '  <url>',
    `    <loc>${escapeXml(loc)}</loc>`,
    `    <lastmod>${today}</lastmod>`,
    `    <changefreq>${changefreq}</changefreq>`,
    `    <priority>${priority}</priority>`,
    '  </url>',
  ].join('\n');
}

const tickerUrls = stocks
  .map((stock) => stock?.ticker)
  .filter((ticker, index, all) => typeof ticker === 'string' && ticker.length > 0 && all.indexOf(ticker) === index)
  .map((ticker) => renderUrl(`${SITE_URL}/tickers/${encodeURIComponent(ticker)}`, 'daily', '0.7'));

const staticUrls = staticRoutes.map((route) => renderUrl(`${SITE_URL}${route.path}`, route.changefreq, route.priority));

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
