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

export interface ResolvedSeoTags {
  title: string;
  description: string;
  canonical: string;
  image: string;
  robots: string;
  type: 'website' | 'article';
  jsonLdBlocks: Array<Record<string, unknown>>;
}

export function resolveSeoTags(options: SeoOptions, pathname: string): ResolvedSeoTags {
  const {
    title,
    description = DEFAULT_SEO_DESCRIPTION,
    path,
    canonicalUrl,
    image = DEFAULT_OG_IMAGE,
    robots = 'index,follow',
    type = 'website',
    jsonLd,
  } = options;

  const fullTitle = title ? `${title} | ${APP_NAME}` : APP_NAME;
  const canonical = canonicalUrl ?? toAbsoluteUrl(path ?? pathname);
  const imageUrl = toAbsoluteUrl(image);
  const jsonLdBlocks = Array.isArray(jsonLd) ? jsonLd : jsonLd ? [jsonLd] : [];

  return { title: fullTitle, description, canonical, image: imageUrl, robots, type, jsonLdBlocks };
}

export function useSeo({
  title,
  description,
  path,
  canonicalUrl,
  image,
  robots,
  type,
  jsonLd,
}: SeoOptions) {
  useEffect(() => {
    const resolved = resolveSeoTags(
      { title, description, path, canonicalUrl, image, robots, type, jsonLd },
      window.location.pathname,
    );

    document.title = resolved.title;

    upsertMeta('name', 'description', resolved.description);
    upsertMeta('name', 'robots', resolved.robots);
    upsertMeta('property', 'og:site_name', APP_NAME);
    upsertMeta('property', 'og:type', resolved.type);
    upsertMeta('property', 'og:title', resolved.title);
    upsertMeta('property', 'og:description', resolved.description);
    upsertMeta('property', 'og:url', resolved.canonical);
    upsertMeta('property', 'og:image', resolved.image);
    upsertMeta('name', 'twitter:card', 'summary_large_image');
    upsertMeta('name', 'twitter:title', resolved.title);
    upsertMeta('name', 'twitter:description', resolved.description);
    upsertMeta('name', 'twitter:image', resolved.image);
    upsertLink('canonical', resolved.canonical);

    document.head.querySelectorAll('script[data-flowdeck-jsonld="true"]').forEach((node) => node.remove());

    resolved.jsonLdBlocks.forEach((block) => {
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
