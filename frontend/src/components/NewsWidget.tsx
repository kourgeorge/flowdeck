import React from 'react';

interface NewsArticle {
  uuid: string;
  title: string;
  summary?: string | null;
  publisher: string;
  link: string;
  published_time: string | null;
  published_timestamp: number;
  type: string;
  thumbnail: string | null;
}

interface NewsWidgetProps {
  articles: NewsArticle[];
  ticker: string;
  onRetry?: () => void;
  isLoading?: boolean;
  errorMessage?: string | null;
}

const titleClampStyles: React.CSSProperties = {
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  WebkitLineClamp: 2,
  overflow: 'hidden',
};

const summaryClampStyles: React.CSSProperties = {
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  WebkitLineClamp: 3,
  overflow: 'hidden',
};

function formatRelativeTime(timestamp?: number | null): string {
  if (!timestamp) return 'Recently published';

  const diffMs = Date.now() - timestamp * 1000;
  if (!Number.isFinite(diffMs)) return 'Recently published';

  const diffMinutes = Math.round(diffMs / 60000);
  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(new Date(timestamp * 1000));
}

function formatAbsoluteTime(timestamp?: number | null, publishedTime?: string | null): string {
  if (timestamp) {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(timestamp * 1000));
  }

  return publishedTime || 'Publication time unavailable';
}

function formatTypeLabel(type?: string | null): string {
  if (!type) return 'News';

  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getSummary(article: NewsArticle, ticker: string): string {
  const summary = article.summary?.trim();
  if (summary) return summary;

  return `Coverage relevant to ${ticker}. Open the article for the full context, details, and source reporting.`;
}

function StoryThumbnail({
  article,
  className,
}: {
  article: NewsArticle;
  className: string;
}) {
  if (!article.thumbnail) {
    return (
      <div className={`${className} relative overflow-hidden bg-gradient-to-br from-slate-800 via-slate-900 to-blue-950`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(96,165,250,0.24),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(14,165,233,0.18),transparent_34%)]" />
        <div className="absolute right-4 top-4 h-20 w-20 rounded-full border border-white/10 bg-white/5 blur-2xl" />
        <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-xs text-slate-300/90">
          <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">{formatTypeLabel(article.type)}</span>
          <span>{article.publisher}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className} overflow-hidden bg-slate-900`}>
      <img
        src={article.thumbnail}
        alt={article.title}
        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
        onError={(event) => {
          (event.target as HTMLImageElement).style.display = 'none';
        }}
      />
    </div>
  );
}

function ExternalLinkIcon() {
  return (
    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M14 5h5m0 0v5m0-5L10 14" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 14v3a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3" />
    </svg>
  );
}

function NewsDeckSkeleton() {
  return (
    <div className="rounded-2xl border border-slate-700/80 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800/95 shadow-[0_24px_80px_-42px_rgba(15,23,42,0.9)]">
      <div className="border-b border-slate-700/70 px-5 py-5 sm:px-6">
        <div className="animate-pulse space-y-3">
          <div className="h-3 w-28 rounded-full bg-slate-700" />
          <div className="h-8 w-64 rounded-full bg-slate-700" />
          <div className="h-4 w-96 max-w-full rounded-full bg-slate-800" />
          <div className="flex flex-wrap gap-2 pt-2">
            {[1, 2, 3].map((item) => (
              <div key={item} className="h-9 w-28 rounded-full bg-slate-800" />
            ))}
          </div>
        </div>
      </div>
      <div className="grid gap-4 px-5 py-5 sm:px-6 xl:grid-cols-[minmax(0,1.45fr)_22rem]">
        <div className="animate-pulse overflow-hidden rounded-[1.5rem] border border-slate-700/70 bg-slate-800/60">
          <div className="aspect-[16/9] bg-slate-800" />
          <div className="space-y-3 p-5">
            <div className="h-4 w-40 rounded-full bg-slate-700" />
            <div className="h-8 w-5/6 rounded-full bg-slate-700" />
            <div className="h-4 w-full rounded-full bg-slate-800" />
            <div className="h-4 w-4/5 rounded-full bg-slate-800" />
          </div>
        </div>
        <div className="animate-pulse rounded-[1.5rem] border border-slate-700/70 bg-slate-800/50 p-4">
          <div className="mb-4 h-5 w-28 rounded-full bg-slate-700" />
          <div className="space-y-3">
            {[1, 2, 3].map((item) => (
              <div key={item} className="rounded-2xl border border-slate-700/60 bg-slate-900/50 p-4">
                <div className="h-4 w-3/4 rounded-full bg-slate-700" />
                <div className="mt-2 h-4 w-1/2 rounded-full bg-slate-800" />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="px-5 pb-5 sm:px-6 sm:pb-6">
        <div className="grid gap-4 lg:grid-cols-2">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="animate-pulse rounded-[1.35rem] border border-slate-700/70 bg-slate-800/40 p-4">
              <div className="mb-4 aspect-[16/9] rounded-2xl bg-slate-800" />
              <div className="h-4 w-32 rounded-full bg-slate-700" />
              <div className="mt-3 h-6 w-5/6 rounded-full bg-slate-700" />
              <div className="mt-2 h-4 w-full rounded-full bg-slate-800" />
              <div className="mt-2 h-4 w-3/4 rounded-full bg-slate-800" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  ticker,
  errorMessage,
  isLoading,
  onRetry,
}: {
  ticker: string;
  errorMessage?: string | null;
  isLoading?: boolean;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-700/80 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800/95 p-8 text-center shadow-[0_24px_80px_-42px_rgba(15,23,42,0.9)]">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-700 bg-slate-800/80 text-sky-300">
        <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 7H5m14 5H8m11 5H5" />
        </svg>
      </div>
      <h3 className="mt-4 text-xl font-semibold text-white">
        {errorMessage ? 'News feed unavailable' : `No recent headlines for ${ticker}`}
      </h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-400">
        {errorMessage
          ? `The latest fetch failed${errorMessage ? `: ${errorMessage}` : '.'}`
          : `We could not find recent articles for ${ticker} right now. Try again in a few minutes or switch to another section while the feed catches up.`}
      </p>
      {onRetry && !isLoading && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 rounded-full border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:border-slate-500 hover:bg-slate-700"
        >
          Refresh feed
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 4v5h5M20 20v-5h-5" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M20 9A7 7 0 0 0 8.34 5.34L4 9m16 6-4.34 3.66A7 7 0 0 1 4 15" />
          </svg>
        </button>
      )}
    </div>
  );
}

function CompactHeadline({ article }: { article: NewsArticle }) {
  return (
    <a
      href={article.link}
      target="_blank"
      rel="noopener noreferrer"
      className="group rounded-2xl border border-slate-700/70 bg-slate-900/65 p-4 transition-colors hover:border-slate-500 hover:bg-slate-900"
    >
      <div className="flex items-center justify-between gap-3 text-xs text-slate-400">
        <span className="truncate font-medium text-slate-200">{article.publisher}</span>
        <span className="shrink-0">{formatRelativeTime(article.published_timestamp)}</span>
      </div>
      <h4 className="mt-3 text-sm font-semibold leading-6 text-white transition-colors group-hover:text-sky-200" style={titleClampStyles}>
        {article.title}
      </h4>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="rounded-full border border-slate-700 bg-slate-800/90 px-2.5 py-1 text-[11px] uppercase tracking-[0.18em] text-slate-300">
          {formatTypeLabel(article.type)}
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-medium text-sky-300 transition-colors group-hover:text-sky-200">
          Open
          <ExternalLinkIcon />
        </span>
      </div>
    </a>
  );
}

function FeedCard({ article, ticker }: { article: NewsArticle; ticker: string }) {
  return (
    <a
      href={article.link}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex h-full flex-col overflow-hidden rounded-[1.35rem] border border-slate-700/75 bg-slate-900/55 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-500 hover:bg-slate-900"
    >
      <StoryThumbnail article={article} className="aspect-[16/9] w-full" />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-slate-400">
          <span className="rounded-full border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-slate-300">
            {formatTypeLabel(article.type)}
          </span>
          <span>{formatRelativeTime(article.published_timestamp)}</span>
        </div>
        <h4 className="mt-3 text-lg font-semibold leading-7 text-white transition-colors group-hover:text-sky-200" style={titleClampStyles}>
          {article.title}
        </h4>
        <p className="mt-3 text-sm leading-6 text-slate-300" style={summaryClampStyles}>
          {getSummary(article, ticker)}
        </p>
        <div className="mt-4 flex items-center justify-between gap-3 text-sm">
          <span className="truncate font-medium text-slate-200">{article.publisher}</span>
          <span className="inline-flex items-center gap-1 text-sky-300 transition-colors group-hover:text-sky-200">
            Open article
            <ExternalLinkIcon />
          </span>
        </div>
      </div>
    </a>
  );
}

const NewsWidget: React.FC<NewsWidgetProps> = ({ articles, ticker, onRetry, isLoading, errorMessage }) => {
  const sortedArticles = [...(articles || [])].sort(
    (left, right) => (right.published_timestamp ?? 0) - (left.published_timestamp ?? 0)
  );

  if (isLoading && sortedArticles.length === 0) {
    return <NewsDeckSkeleton />;
  }

  if (sortedArticles.length === 0) {
    return <EmptyState ticker={ticker} errorMessage={errorMessage} isLoading={isLoading} onRetry={onRetry} />;
  }

  const [leadArticle, ...remainingArticles] = sortedArticles;
  const rapidScanArticles = remainingArticles.slice(0, 3);
  const feedArticles = remainingArticles.slice(3);
  const publisherCount = new Set(sortedArticles.map((article) => article.publisher).filter(Boolean)).size;
  const topPublishers = Array.from(new Set(sortedArticles.map((article) => article.publisher).filter(Boolean))).slice(0, 4);

  return (
    <div className="rounded-2xl border border-slate-700/80 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800/95 shadow-[0_24px_80px_-42px_rgba(15,23,42,0.9)]">
      <div className="border-b border-slate-700/70 px-5 py-5 sm:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-sky-300/80">News Deck</div>
            <h3 className="mt-2 text-2xl font-semibold text-white">Latest coverage for {ticker}</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Lead story, rapid-scan headlines, and source diversity in one practical view.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
              <span className="font-semibold text-white">{sortedArticles.length}</span> stories
            </div>
            <div className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
              <span className="font-semibold text-white">{publisherCount}</span> sources
            </div>
            <div className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
              Latest {formatRelativeTime(leadArticle.published_timestamp)}
            </div>
            {isLoading && (
              <div className="rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-sm text-sky-200">
                Refreshing feed...
              </div>
            )}
          </div>
        </div>

        {topPublishers.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {topPublishers.map((publisher) => (
              <span
                key={publisher}
                className="rounded-full border border-slate-700/90 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-300"
              >
                {publisher}
              </span>
            ))}
          </div>
        )}

        {errorMessage && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            <span>Showing the last successful news pull. Refresh failed: {errorMessage}</span>
            {onRetry && !isLoading && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-full border border-amber-300/30 px-3 py-1.5 font-medium text-amber-100 transition-colors hover:bg-amber-400/10"
              >
                Try again
              </button>
            )}
          </div>
        )}
      </div>

      <div className="px-5 py-5 sm:px-6 sm:py-6">
        <div className={`grid gap-4 ${rapidScanArticles.length > 0 ? 'xl:grid-cols-[minmax(0,1.45fr)_22rem]' : ''}`}>
          <a
            href={leadArticle.link}
            target="_blank"
            rel="noopener noreferrer"
            className="group overflow-hidden rounded-[1.6rem] border border-slate-700/75 bg-slate-900/70 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-500"
          >
            <div className="relative">
              <StoryThumbnail article={leadArticle} className="aspect-[16/9] w-full" />
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/30 to-transparent" />
              <div className="absolute right-4 top-4">
                <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs font-medium text-white backdrop-blur">
                  Read feature
                  <ExternalLinkIcon />
                </span>
              </div>
            </div>

            <div className="p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-400">
                <span className="rounded-full border border-slate-700 bg-slate-800/90 px-2.5 py-1 text-slate-300">
                  {formatTypeLabel(leadArticle.type)}
                </span>
                <span className="font-medium text-slate-200">{leadArticle.publisher}</span>
                <span>{formatRelativeTime(leadArticle.published_timestamp)}</span>
              </div>
              <h4 className="mt-4 text-2xl font-semibold leading-tight text-white transition-colors group-hover:text-sky-200 sm:text-[2rem]">
                {leadArticle.title}
              </h4>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300 sm:text-[15px]">
                {getSummary(leadArticle, ticker)}
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-3 text-sm text-slate-400">
                <span>{formatAbsoluteTime(leadArticle.published_timestamp, leadArticle.published_time)}</span>
                <span className="hidden h-1 w-1 rounded-full bg-slate-600 sm:block" />
                <span>Source: {leadArticle.publisher}</span>
              </div>
            </div>
          </a>

          {rapidScanArticles.length > 0 && (
            <div className="rounded-[1.6rem] border border-slate-700/75 bg-slate-900/60 p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-white">Rapid Scan</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">Next key headlines</div>
                </div>
                <div className="rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-300">
                  {rapidScanArticles.length} stories
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {rapidScanArticles.map((article) => (
                  <CompactHeadline key={article.uuid || article.link} article={article} />
                ))}
              </div>
            </div>
          )}
        </div>

        {feedArticles.length > 0 && (
          <div className="mt-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h4 className="text-lg font-semibold text-white">More headlines</h4>
                <p className="mt-1 text-sm text-slate-400">A clean browsing grid for the rest of the feed.</p>
              </div>
              {onRetry && !isLoading && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="rounded-full border border-slate-600 bg-slate-900/70 px-3 py-2 text-sm font-medium text-white transition-colors hover:border-slate-500 hover:bg-slate-800"
                >
                  Refresh
                </button>
              )}
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {feedArticles.map((article) => (
                <FeedCard key={article.uuid || article.link} article={article} ticker={ticker} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NewsWidget;
