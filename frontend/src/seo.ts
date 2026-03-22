import { useEffect } from 'react';
import { APP_NAME, DEFAULT_OG_IMAGE, DEFAULT_SEO_DESCRIPTION, SITE_URL } from './config';

export interface SeoOptions {
  title?: string;
  description?: string;
  path?: string;
  canonicalUrl?: string;
  image?: string;
  robots?: string;
  type?: 'website' | 'article';
  jsonLd?: Record<string, unknown> | Array<Record<string, unknown>>;
}

function toAbsoluteUrl(pathOrUrl?: string): string {
  if (!pathOrUrl) return SITE_URL;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  return `${SITE_URL}${pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`}`;
}

function upsertMeta(attribute: 'name' | 'property', key: string, content: string) {
  let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute(attribute, key);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content);
}

function upsertLink(rel: string, href: string) {
  let tag = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!tag) {
    tag = document.createElement('link');
    tag.setAttribute('rel', rel);
    document.head.appendChild(tag);
  }
  tag.setAttribute('href', href);
}

export function useSeo({
  title,
  description = DEFAULT_SEO_DESCRIPTION,
  path,
  canonicalUrl,
  image = DEFAULT_OG_IMAGE,
  robots = 'index,follow',
  type = 'website',
  jsonLd,
}: SeoOptions) {
  useEffect(() => {
    const fullTitle = title ? `${title} | ${APP_NAME}` : APP_NAME;
    const canonical = canonicalUrl ?? toAbsoluteUrl(path ?? window.location.pathname);
    const imageUrl = toAbsoluteUrl(image);

    document.title = fullTitle;

    upsertMeta('name', 'description', description);
    upsertMeta('name', 'robots', robots);
    upsertMeta('property', 'og:site_name', APP_NAME);
    upsertMeta('property', 'og:type', type);
    upsertMeta('property', 'og:title', fullTitle);
    upsertMeta('property', 'og:description', description);
    upsertMeta('property', 'og:url', canonical);
    upsertMeta('property', 'og:image', imageUrl);
    upsertMeta('name', 'twitter:card', 'summary_large_image');
    upsertMeta('name', 'twitter:title', fullTitle);
    upsertMeta('name', 'twitter:description', description);
    upsertMeta('name', 'twitter:image', imageUrl);
    upsertLink('canonical', canonical);

    document.head.querySelectorAll('script[data-flowdeck-jsonld="true"]').forEach((node) => node.remove());

    const blocks = Array.isArray(jsonLd) ? jsonLd : jsonLd ? [jsonLd] : [];
    blocks.forEach((block) => {
      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.dataset.flowdeckJsonld = 'true';
      script.textContent = JSON.stringify(block);
      document.head.appendChild(script);
    });
  }, [canonicalUrl, description, image, jsonLd ? JSON.stringify(jsonLd) : '', path, robots, title, type]);
}

export function absoluteUrl(pathOrUrl?: string) {
  return toAbsoluteUrl(pathOrUrl);
}
