import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../services/api';

// Everything factual here is read from the live schema, not hardcoded -- the
// page this replaced drifted (it still taught the fixed tokens_used/
// platform_tokens_used bug) because its facts were typed by hand.
interface OpenApiInfo {
  title: string;
  version: string;
  description: string;
}

function extractSecurityNotice(description: string): string | null {
  const match = description.match(/\*\*(Never send your JWT[^*]*)\*\*/);
  return match ? match[1] : null;
}

export default function ApiDocsPage() {
  const [info, setInfo] = useState<OpenApiInfo | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/openapi.json`)
      .then((res) => res.json())
      .then((schema) => setInfo(schema.info))
      .catch(() => setInfo(null));
  }, []);

  const security = info ? extractSecurityNotice(info.description) : null;

  return (
    <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-bold text-white mb-2">
          {info?.title ?? 'Flowdeck API'} {info && <span className="text-gray-500 text-xl">v{info.version}</span>}
        </h1>
        <p className="text-gray-400 mb-6">
          Flowdeck is an AI-powered ticker analysis platform for agents. The full reference --
          every endpoint, request/response shape, and try-it console -- lives at{' '}
          <code className="text-sm bg-gray-800 px-1.5 py-0.5 rounded">/api/docs</code>.
        </p>

        <div className="bg-gray-900 rounded-lg p-4 mb-6 space-y-2 text-sm">
          <p className="text-gray-300">
            <span className="text-gray-500">Base URL:</span> https://flowdeck.biz
          </p>
          <p className="text-gray-300">
            <span className="text-gray-500">Agent guide:</span>{' '}
            <a href="/api/SKILL.md" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">
              GET /api/SKILL.md
            </a>{' '}
            -- fetch this before calling the API; it's the file agents are told to read.
          </p>
        </div>

        {security && (
          <p className="text-amber-400 text-sm mb-8 border-l-2 border-amber-500 pl-3">{security}</p>
        )}

        <a
          href="/api/docs"
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2.5 rounded-lg transition-colors"
        >
          View full API reference →
        </a>
      </div>
    </div>
  );
}
