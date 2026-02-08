import React from 'react';

interface NewsArticle {
  uuid: string;
  title: string;
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

const NewsWidget: React.FC<NewsWidgetProps> = ({ articles, ticker, onRetry, isLoading, errorMessage }) => {
  if (!articles || articles.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        {errorMessage ? (
          <p className="text-amber-400/90 text-sm mb-2 font-medium">
            Unable to fetch news: {errorMessage}
          </p>
        ) : null}
        <p className="text-gray-400 text-sm mb-3">
          {isLoading ? 'Loading news…' : errorMessage ? 'Please try again later.' : `No news articles available for ${ticker}`}
        </p>
        {onRetry && !isLoading && (
          <button
            type="button"
            onClick={onRetry}
            className="text-sm px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-4">
        {articles.map((article) => (
          <div
            key={article.uuid}
            className="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition-colors"
          >
            <div className="flex gap-4">
              {article.thumbnail && (
                <div className="flex-shrink-0">
                  <img
                    src={article.thumbnail}
                    alt={article.title}
                    className="w-24 h-24 object-cover rounded"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <a
                    href={article.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300 font-semibold text-base leading-tight flex-1 hover:underline"
                  >
                    {article.title}
                  </a>
                </div>
                <div className="flex items-center gap-3 text-sm text-gray-400">
                  <span className="font-medium">{article.publisher}</span>
                  {article.published_time && (
                    <>
                      <span>•</span>
                      <span>{article.published_time}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default NewsWidget;

