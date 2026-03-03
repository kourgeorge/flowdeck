import { Link } from 'react-router-dom';
import { useState } from 'react';

export default function ApiDocsPage() {
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  const API_BASE_URL = 'https://flowdeck.biz';

  const copyToClipboard = (text: string, section: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(section);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  const CodeBlock = ({ code, language = 'python', section }: { code: string; language?: string; section: string }) => (
    <div className="relative">
      <div className="absolute top-2 right-2 flex gap-2">
        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">{language}</span>
        <button
          onClick={() => copyToClipboard(code, section)}
          className="text-xs bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded transition-colors"
        >
          {copiedSection === section ? '✓ Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
        <code className="text-sm text-gray-300">{code}</code>
      </pre>
    </div>
  );

  return (
    <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to Flowdeck
        </Link>

        <h1 className="text-3xl font-bold text-white mb-4">FlowDeck API Documentation</h1>
        <p className="text-gray-400 mb-8">
          Access FlowDeck's AI-powered stock analysis programmatically using our REST API.
        </p>

        {/* Quick Start */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">🚀 Quick Start</h2>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium text-white mb-2">1. Create an API Key</h3>
              <p className="text-gray-400 mb-3">
                Navigate to your <Link to="/profile#api-keys" className="text-blue-400 hover:text-blue-300">Profile page</Link> and create a new API key in the "API Keys" section.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-medium text-white mb-2">2. Make Your First Request</h3>
              <CodeBlock
                section="quickstart"
                language="python"
                code={`import requests

API_KEY = "fd_live_your_key_here"
BASE_URL = "${API_BASE_URL}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Get your profile
response = requests.get(f"{BASE_URL}/api/me", headers=headers)
print(response.json())`}
              />
            </div>
          </div>
        </section>

        {/* Authentication */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">🔐 Authentication</h2>
          
          <p className="text-gray-400 mb-4">
            All authenticated requests require an API key in the Authorization header:
          </p>

          <CodeBlock
            section="auth-header"
            language="bash"
            code={`Authorization: Bearer fd_live_your_key_here`}
          />

          <div className="mt-4 bg-blue-900/20 border border-blue-700 rounded-lg p-4">
            <p className="text-sm text-blue-300">
              <strong>💡 Tip:</strong> API keys never expire by default. You can set an optional expiration date when creating a key.
            </p>
          </div>
        </section>

        {/* Base URL */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">🌐 Base URL</h2>
          
          <div className="bg-gray-900 rounded-lg p-4">
            <code className="text-green-400 text-lg">{API_BASE_URL}</code>
          </div>

          <p className="text-gray-400 mt-4">
            All API endpoints are relative to this base URL.
          </p>
        </section>

        {/* Endpoints */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">📡 API Endpoints</h2>

          {/* User Profile */}
          <div className="mb-6">
            <h3 className="text-xl font-medium text-white mb-3">User Profile</h3>
            
            <div className="space-y-4">
              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-green-900/30 text-green-400 text-xs font-mono rounded">GET</span>
                  <code className="text-gray-300">/api/me</code>
                </div>
                <p className="text-sm text-gray-400 mb-3">Get your profile information and token balance.</p>
                <CodeBlock
                  section="get-me"
                  code={`response = requests.get(
    f"${API_BASE_URL}/api/me",
    headers={"Authorization": f"Bearer {API_KEY}"}
)

# Response:
# {
#   "user_id": 123,
#   "email": "user@example.com",
#   "name": "John Doe",
#   "token_balance": 1000,
#   "is_admin": false
# }`}
                />
              </div>

              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-green-900/30 text-green-400 text-xs font-mono rounded">GET</span>
                  <code className="text-gray-300">/api/me/stats</code>
                </div>
                <p className="text-sm text-gray-400 mb-3">Get your usage statistics.</p>
                <CodeBlock
                  section="get-stats"
                  code={`response = requests.get(
    f"${API_BASE_URL}/api/me/stats",
    headers={"Authorization": f"Bearer {API_KEY}"}
)

# Response includes:
# - analyses_created
# - tokens_earned_from_views
# - reports_viewed
# - subscriptions_count`}
                />
              </div>
            </div>
          </div>

          {/* Market Data */}
          <div className="mb-6">
            <h3 className="text-xl font-medium text-white mb-3">Market Data (Public)</h3>
            
            <div className="space-y-4">
              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-blue-900/30 text-blue-400 text-xs font-mono rounded">GET</span>
                  <code className="text-gray-300">/api/data/quote/&#123;ticker&#125;</code>
                </div>
                <p className="text-sm text-gray-400 mb-3">Get real-time stock quote (no authentication required).</p>
                <CodeBlock
                  section="get-quote"
                  code={`# No API key needed for public endpoints
response = requests.get(f"${API_BASE_URL}/api/data/quote/AAPL")

# Response:
# {
#   "ticker": "AAPL",
#   "current_price": 182.50,
#   "daily_change": 2.30,
#   "daily_change_percent": 1.28,
#   "market_status": "OPEN"
# }`}
                />
              </div>

              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-blue-900/30 text-blue-400 text-xs font-mono rounded">GET</span>
                  <code className="text-gray-300">/api/data/fundamentals/&#123;ticker&#125;</code>
                </div>
                <p className="text-sm text-gray-400">Get fundamental metrics (P/E, EPS, market cap, etc.).</p>
              </div>

              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-blue-900/30 text-blue-400 text-xs font-mono rounded">GET</span>
                  <code className="text-gray-300">/api/data/news?ticker=&#123;ticker&#125;</code>
                </div>
                <p className="text-sm text-gray-400">Get recent news articles for a stock.</p>
              </div>
            </div>
          </div>

          {/* AI Reports */}
          <div className="mb-6">
            <h3 className="text-xl font-medium text-white mb-3">AI Analysis Reports (Authenticated)</h3>
            
            <div className="space-y-4">
              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-green-900/30 text-green-400 text-xs font-mono rounded">GET</span>
                  <code className="text-gray-300">/api/data/reports/&#123;ticker&#125;</code>
                </div>
                <p className="text-sm text-gray-400 mb-3">Get FlowDeck's AI analysis and recommendation for a stock.</p>
                <CodeBlock
                  section="get-reports"
                  code={`response = requests.get(
    f"${API_BASE_URL}/api/data/reports/AAPL",
    headers={"Authorization": f"Bearer {API_KEY}"}
)

# Response:
# {
#   "report_date": "2026-03-03_10-30-00",
#   "reports": {
#     "final_trade_decision": {
#       "recommendation": "BUY",
#       "confidence": 0.85,
#       "content": "..."
#     },
#     "market_report": {...},
#     "technical_report": {...}
#   }
# }`}
                />
              </div>

              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-yellow-900/30 text-yellow-400 text-xs font-mono rounded">POST</span>
                  <code className="text-gray-300">/api/data/reports/batch</code>
                </div>
                <p className="text-sm text-gray-400 mb-3">Get reports for multiple tickers at once.</p>
                <CodeBlock
                  section="batch-reports"
                  code={`response = requests.post(
    f"${API_BASE_URL}/api/data/reports/batch",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"tickers": ["AAPL", "MSFT", "TSLA"]}
)`}
                />
              </div>
            </div>
          </div>

          {/* AI Chat */}
          <div className="mb-6">
            <h3 className="text-xl font-medium text-white mb-3">AI Chat (Authenticated, Costs Tokens)</h3>
            
            <div className="space-y-4">
              <div className="bg-gray-900/50 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2 py-1 bg-yellow-900/30 text-yellow-400 text-xs font-mono rounded">POST</span>
                  <code className="text-gray-300">/api/chat</code>
                </div>
                <p className="text-sm text-gray-400 mb-3">Chat with FlowDeck's AI stock analyst.</p>
                <CodeBlock
                  section="chat"
                  code={`response = requests.post(
    f"${API_BASE_URL}/api/chat",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "messages": [
            {"role": "user", "content": "What's the outlook for AAPL?"}
        ]
    }
)

# Response:
# {
#   "reply": "Based on FlowDeck's latest analysis...",
#   "tokens_used": 5,
#   "balance": 995
# }`}
                />
              </div>

              <div className="bg-yellow-900/20 border border-yellow-700 rounded-lg p-4">
                <p className="text-sm text-yellow-300">
                  <strong>⚠️ Note:</strong> Chat requests cost 1-15 tokens depending on complexity. Check your balance with <code className="bg-gray-800 px-1 rounded">GET /api/me</code>
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Complete Example */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">💻 Complete Example</h2>
          
          <p className="text-gray-400 mb-4">
            Here's a complete Python script that demonstrates the FlowDeck API:
          </p>

          <CodeBlock
            section="complete-example"
            code={'#!/usr/bin/env python3\n"""FlowDeck API Example"""\n\nimport requests\n\n# Configuration\nAPI_KEY = "fd_live_your_key_here"  # Get from Profile → API Keys\nBASE_URL = "' + API_BASE_URL + '"\n\nheaders = {\n    "Authorization": f"Bearer {API_KEY}",\n    "Content-Type": "application/json"\n}\n\n# 1. Get your profile\nprint("1. Getting profile...")\nresponse = requests.get(f"{BASE_URL}/api/me", headers=headers)\nprofile = response.json()\nprint(f"   Email: {profile[\'email\']}")\nprint(f"   Balance: {profile[\'token_balance\']} tokens")\n\n# 2. Get stock quote (public, no auth needed)\nprint("\\n2. Getting AAPL quote...")\nresponse = requests.get(f"{BASE_URL}/api/data/quote/AAPL")\nquote = response.json()\nprint(f"   Price: ${quote[\'current_price\']}")\nprint(f"   Change: {quote[\'daily_change_percent\']}%")\n\n# 3. Get AI analysis report\nprint("\\n3. Getting AI analysis for AAPL...")\nresponse = requests.get(\n    f"{BASE_URL}/api/data/reports/AAPL",\n    headers=headers\n)\nreports = response.json()\nif reports[\'report_date\']:\n    ftd = reports[\'reports\'].get(\'final_trade_decision\', {})\n    print(f"   Recommendation: {ftd.get(\'recommendation\', \'N/A\')}")\n    print(f"   Confidence: {ftd.get(\'confidence\', 0)*100:.0f}%")\nelse:\n    print("   No reports available yet")\n\n# 4. Chat with AI analyst\nprint("\\n4. Chatting with AI analyst...")\nresponse = requests.post(\n    f"{BASE_URL}/api/chat",\n    headers=headers,\n    json={\n        "messages": [\n            {"role": "user", "content": "What is AAPL\'s current price?"}\n        ]\n    }\n)\nchat = response.json()\nprint(f"   Reply: {chat[\'reply\'][:100]}...")\nprint(f"   Tokens used: {chat[\'tokens_used\']}")\nprint(f"   New balance: {chat[\'balance\']} tokens")\n\nprint("\\n✓ All requests completed successfully!")'}
          />
        </section>

        {/* Rate Limits & Costs */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">💰 Token Economy</h2>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium text-white mb-2">Token Costs</h3>
              <ul className="space-y-2 text-gray-400">
                <li>• <strong className="text-white">Chat:</strong> 1-15 tokens per message (based on complexity)</li>
                <li>• <strong className="text-white">Report Generation:</strong> 200 tokens per analysis</li>
                <li>• <strong className="text-white">Data Endpoints:</strong> Free (no tokens required)</li>
              </ul>
            </div>

            <div>
              <h3 className="text-lg font-medium text-white mb-2">Getting More Tokens</h3>
              <p className="text-gray-400">
                Purchase tokens via the <Link to="/profile#purchase-tokens" className="text-blue-400 hover:text-blue-300">Profile page</Link> or earn tokens when others view your analysis reports.
              </p>
            </div>
          </div>
        </section>

        {/* Error Handling */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
          <h2 className="text-2xl font-semibold text-white mb-4">⚠️ Error Handling</h2>
          
          <div className="space-y-3">
            <div className="bg-gray-900/50 rounded-lg p-3">
              <code className="text-red-400">401 Unauthorized</code>
              <p className="text-sm text-gray-400 mt-1">Invalid or expired API key</p>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <code className="text-red-400">402 Payment Required</code>
              <p className="text-sm text-gray-400 mt-1">Insufficient token balance</p>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <code className="text-red-400">404 Not Found</code>
              <p className="text-sm text-gray-400 mt-1">Ticker or resource not found</p>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3">
              <code className="text-red-400">429 Too Many Requests</code>
              <p className="text-sm text-gray-400 mt-1">Rate limit exceeded</p>
            </div>
          </div>
        </section>

        {/* Support */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
          <h2 className="text-2xl font-semibold text-white mb-4">💬 Support</h2>
          
          <p className="text-gray-400 mb-4">
            Need help? Have questions about the API?
          </p>

          <div className="flex gap-4">
            <Link
              to="/contact"
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Contact Us
            </Link>
            <Link
              to="/profile#api-keys"
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Manage API Keys
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}

// Made with Bob
