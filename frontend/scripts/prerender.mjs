// Renders a fixed set of fully-static routes to HTML via Vite's SSR build +
// react-dom/server, then splices the result into copies of dist/index.html.
// No browser/Chromium involved — see entry-prerender.tsx for the render side.
//
// Safety model: every route is rendered and gate-checked in memory first.
// Files are only written to dist/ if every route passes. A failure leaves
// dist/ exactly as `vite build` produced it, so a broken prerender run can
// never ship broken pages.
import { build } from 'vite';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = resolve('.');
const DIST = resolve(ROOT, 'dist');
const SSR_ENTRY = 'src/entry-prerender.tsx';
const SSR_OUT_DIR = 'node_modules/.vite-prerender';
const SSR_ENTRY_FILE = 'entry-prerender.mjs';
const REPORT_ONLY = process.env.PRERENDER_REPORT === '1';
const KEEP_BUNDLE = process.env.PRERENDER_KEEP_BUNDLE === '1';

const FORBIDDEN_TEXT = [
  'Failed to load stock data',
  'Please check if the backend is running',
  'Something went wrong',
];

// minTextLength is calibrated from real measurements via
// `PRERENDER_REPORT=1 npm run prerender` (measured: architecture 12742,
// contact 562, how-it-works 9598, privacy 22096, terms 7332, tps 6908),
// set to roughly half of measured — a real regression (empty render, error
// state) drops text length by far more than that.
const GATES = {
  '/architecture': { minTextLength: 6000, allowSpinner: false, expectJsonLd: true },
  '/contact': { minTextLength: 300, allowSpinner: false, expectJsonLd: false },
  '/how-it-works': { minTextLength: 4500, allowSpinner: false, expectJsonLd: true },
  '/privacy': { minTextLength: 10000, allowSpinner: false, expectJsonLd: false },
  '/terms': { minTextLength: 3500, allowSpinner: false, expectJsonLd: false },
  '/tps': { minTextLength: 3000, allowSpinner: false, expectJsonLd: true },
};

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function textLength(html) {
  const withoutScripts = html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '');
  const text = withoutScripts.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  return text.length;
}

function checkGates(route, gates) {
  const problems = [];
  const length = textLength(route.html);

  if (length < gates.minTextLength) {
    problems.push(`text length ${length} below minTextLength ${gates.minTextLength}`);
  }
  if (!/<main[\s>]/.test(route.html)) {
    problems.push('no <main> element found');
  }
  if (!gates.allowSpinner && route.html.includes('animate-spin')) {
    problems.push('found animate-spin (loading skeleton baked into static HTML)');
  }
  for (const forbidden of FORBIDDEN_TEXT) {
    if (route.html.includes(forbidden)) {
      problems.push(`forbidden text present: "${forbidden}"`);
    }
  }
  if (gates.expectJsonLd && route.jsonLdBlocks.length === 0) {
    problems.push('expected JSON-LD but resolveSeoTags produced none');
  }

  return { length, problems };
}

// Aborts the whole build if `pattern` doesn't match dist/index.html's
// template exactly once — the guard against silently shipping every page
// with the homepage's title/canonical after e.g. a Vite upgrade changes
// index.html's shape.
function replaceOnce(html, pattern, replacement, label) {
  const matches = html.match(new RegExp(pattern, 'g'));
  const count = matches ? matches.length : 0;
  if (count !== 1) {
    throw new Error(`prerender: expected exactly one match for "${label}" in dist/index.html, found ${count}`);
  }
  return html.replace(new RegExp(pattern, ''), replacement);
}

function metaContentPattern(attr, key) {
  return `(<meta\\s+${attr}="${escapeRegExp(key)}"\\s+content=")[^"]*(")`;
}

function loadManifest() {
  const candidates = [join(DIST, '.vite', 'manifest.json'), join(DIST, 'manifest.json')];
  for (const path of candidates) {
    if (existsSync(path)) {
      return JSON.parse(readFileSync(path, 'utf8'));
    }
  }
  return null;
}

const ROUTE_TO_PAGE_MODULE = {
  '/architecture': 'src/pages/ArchitecturePage.tsx',
  '/contact': 'src/pages/ContactUsPage.tsx',
  '/how-it-works': 'src/pages/HowItWorksPage.tsx',
  '/privacy': 'src/pages/PrivacyPage.tsx',
  '/terms': 'src/pages/TermsOfUsePage.tsx',
  '/tps': 'src/pages/TpsPage.tsx',
};

function modulepreloadTags(url, manifest, template) {
  if (!manifest) return '';
  const moduleId = ROUTE_TO_PAGE_MODULE[url];
  const entry = moduleId && manifest[moduleId];
  if (!entry) return '';

  const jsFiles = new Set();
  const cssFiles = new Set();
  const visit = (chunk) => {
    if (!chunk) return;
    if (chunk.file) jsFiles.add(chunk.file);
    (chunk.css ?? []).forEach((f) => cssFiles.add(f));
    (chunk.imports ?? []).forEach((id) => visit(manifest[id]));
  };
  visit(entry);

  // The main entry chunk (and its CSS) is already referenced by index.html
  // via a plain <script type="module">/<link rel="stylesheet"> — only the
  // route's own lazy-loaded chunk is worth preloading here.
  const alreadyReferenced = (file) => template.includes(`/${file}`);

  const tags = [];
  for (const file of jsFiles) {
    if (!alreadyReferenced(file)) tags.push(`<link rel="modulepreload" href="/${file}" />`);
  }
  for (const file of cssFiles) {
    if (!alreadyReferenced(file)) tags.push(`<link rel="stylesheet" href="/${file}" />`);
  }
  return tags.join('\n    ');
}

function buildDocument(template, route, manifest) {
  let html = template;

  html = replaceOnce(html, '<title>[^<]*</title>', `<title>${route.title}</title>`, 'title');
  html = replaceOnce(html, metaContentPattern('name', 'description'), `$1${route.description}$2`, 'meta description');
  html = replaceOnce(html, metaContentPattern('name', 'robots'), `$1${route.robots}$2`, 'meta robots');
  html = replaceOnce(html, metaContentPattern('property', 'og:type'), `$1${route.type}$2`, 'og:type');
  html = replaceOnce(html, metaContentPattern('property', 'og:title'), `$1${route.title}$2`, 'og:title');
  html = replaceOnce(html, metaContentPattern('property', 'og:description'), `$1${route.description}$2`, 'og:description');
  html = replaceOnce(html, metaContentPattern('property', 'og:url'), `$1${route.canonical}$2`, 'og:url');
  html = replaceOnce(html, metaContentPattern('property', 'og:image'), `$1${route.image}$2`, 'og:image');
  html = replaceOnce(html, metaContentPattern('name', 'twitter:title'), `$1${route.title}$2`, 'twitter:title');
  html = replaceOnce(html, metaContentPattern('name', 'twitter:description'), `$1${route.description}$2`, 'twitter:description');
  html = replaceOnce(html, metaContentPattern('name', 'twitter:image'), `$1${route.image}$2`, 'twitter:image');
  html = replaceOnce(html, '<link rel="canonical" href="[^"]*" ?/>', `<link rel="canonical" href="${route.canonical}" />`, 'canonical');
  html = replaceOnce(html, '<div id="root"></div>', `<div id="root">${route.html}</div>`, 'root div');

  const extraHead = [
    ...route.jsonLdBlocks.map(
      (block) => `<script type="application/ld+json" data-flowdeck-jsonld="true">${JSON.stringify(block)}</script>`,
    ),
    modulepreloadTags(route.url, manifest, template),
  ]
    .filter(Boolean)
    .join('\n    ');

  if (extraHead) {
    html = replaceOnce(html, '</head>', `${extraHead}\n  </head>`, 'head close tag');
  }

  return html;
}

async function main() {
  if (!existsSync(join(DIST, 'index.html'))) {
    throw new Error('prerender: dist/index.html not found — run `vite build` first');
  }

  const bundleDir = mkdtempSync(join(tmpdir(), 'flowdeck-prerender-'));
  const outDir = resolve(ROOT, SSR_OUT_DIR);

  await build({
    root: ROOT,
    logLevel: 'warn',
    build: {
      ssr: SSR_ENTRY,
      outDir: SSR_OUT_DIR,
      emptyOutDir: true,
      manifest: false,
      rollupOptions: {
        output: {
          format: 'es',
          entryFileNames: SSR_ENTRY_FILE,
          chunkFileNames: 'chunks/[name]-[hash].mjs',
        },
      },
    },
  });
  rmSync(bundleDir, { recursive: true, force: true });

  const modulePath = pathToFileURL(join(outDir, SSR_ENTRY_FILE)).href;
  const { renderRoute } = await import(`${modulePath}?t=${Date.now()}`);

  const template = readFileSync(join(DIST, 'index.html'), 'utf8');
  const manifest = loadManifest();

  const rendered = Object.keys(GATES).map((url) => renderRoute(url));
  const failures = [];

  for (const route of rendered) {
    const gates = GATES[route.url];
    const { length, problems } = checkGates(route, gates);
    if (REPORT_ONLY) {
      console.log(`${route.url}: textLength=${length} jsonLdBlocks=${route.jsonLdBlocks.length}`);
    }
    if (problems.length > 0) {
      failures.push({ url: route.url, problems });
    }
  }

  if (REPORT_ONLY) {
    console.log('PRERENDER_REPORT=1: no files written.');
    if (failures.length > 0) {
      console.log('Gate failures (would block a real run):');
      failures.forEach((f) => console.log(`  ${f.url}: ${f.problems.join('; ')}`));
    }
    return;
  }

  if (failures.length > 0) {
    failures.forEach((f) => console.error(`prerender: ${f.url} failed gates: ${f.problems.join('; ')}`));
    throw new Error(`prerender: ${failures.length} route(s) failed acceptance gates — dist/ left untouched`);
  }

  const documents = rendered.map((route) => ({ url: route.url, html: buildDocument(template, route, manifest) }));
  for (const doc of documents) {
    const outPath = join(DIST, `${doc.url.replace(/^\//, '')}.html`);
    writeFileSync(outPath, doc.html, 'utf8');
    console.log(`prerender: wrote ${outPath}`);
  }
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => {
    if (!KEEP_BUNDLE) {
      rmSync(resolve(ROOT, SSR_OUT_DIR), { recursive: true, force: true });
    }
  });
