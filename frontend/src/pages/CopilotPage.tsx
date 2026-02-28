import { useState } from 'react';
import { Link } from 'react-router-dom';
import DashboardStockSidebar from '../components/DashboardStockSidebar';
import StockDetailPanel from '../components/StockDetailPanel';
import CopilotChatPanel from '../components/CopilotChatPanel';
import { useSubscribedStocks } from '../hooks/useSubscribedStocks';
import { useAuth } from '../contexts/AuthContext';
import type { StockPageData, StockWidget } from '../services/types';

export default function CopilotPage() {
  const { user } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);

  const {
    widgets,
    tickerToName,
    isLoading,
    selectedTicker,
    setSelectedTicker,
    prefetchCache,
    handleSubscriptionChange,
    addTicker,
    removeTicker,
  } = useSubscribedStocks();

  // All tickers in the user's watchlist — passed to the AI analyst for full context
  const allTickers = widgets.map((w: StockWidget) => w.ticker);

  // ── Not logged in ──
  if (!user) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">Sign in to use Copilot</h2>
          <p className="text-gray-400 mb-6 text-sm">
            Copilot combines the stock view with an AI analyst chat so you can research and discuss stocks side by side.
          </p>
          <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  // ── Loading ──
  if (isLoading && widgets.length === 0) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <svg className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-gray-400 text-sm">Loading Copilot…</p>
        </div>
      </div>
    );
  }


  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Page header bar ── */}
      <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 px-4 py-2 flex items-center gap-3">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="text-sm font-semibold text-white">Copilot</span>
        </div>
        <div className="ml-auto" />
      </div>

      {/* ── Three-column layout (desktop) ── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Left: Ticker Sidebar ── */}
        <aside
          className={`shrink-0 border-r border-gray-700 bg-gray-800/50 hidden md:flex flex-row min-h-0 transition-all duration-200 ${
            sidebarCollapsed ? 'w-4' : 'w-64'
          }`}
        >
          {!sidebarCollapsed && (
            <div className="flex-1 min-w-0 min-h-0 overflow-y-auto">
              <DashboardStockSidebar
                subscribedWidgets={widgets}
                recentWidgets={[]}
                tickerToName={tickerToName}
                selectedTicker={selectedTicker}
                onSelect={setSelectedTicker}
                onAdd={addTicker}
                onRemove={removeTicker}
              />
            </div>
          )}
          {/* Collapse toggle strip */}
          <button
            type="button"
            onClick={() => setSidebarCollapsed((c) => !c)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="shrink-0 flex items-center justify-center w-4 self-stretch border-l border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700/50 transition-colors"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 ${sidebarCollapsed ? 'rotate-180' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </aside>

        {/* ── Middle: Stock Detail Panel ── */}
        <main className="flex-1 min-w-0 min-h-0 bg-gray-900 hidden md:flex flex-col">
          {selectedTicker ? (
            <StockDetailPanel
              key={selectedTicker}
              ticker={selectedTicker}
              prefetchedData={prefetchCache[selectedTicker] ?? null}
              onSubscriptionChange={handleSubscriptionChange}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500 text-sm gap-2 p-8">
              {widgets.length === 0 ? (
                <>
                  <p className="text-gray-400 font-medium">No focus tickers yet.</p>
                  <p className="text-gray-500 text-xs text-center max-w-xs">
                    Use the search box on the left to add any ticker, or subscribe to tickers from the Dashboard.
                  </p>
                </>
              ) : (
                <p>Select a focus ticker from the list to view details.</p>
              )}
            </div>
          )}
        </main>

        {/* ── Right: AI Copilot Panel ── */}
        <div
          className={`shrink-0 hidden md:flex flex-col min-h-0 transition-all duration-200 ${
            chatCollapsed ? 'w-6' : 'w-96'
          }`}
        >
          <CopilotChatPanel
            selectedTicker={selectedTicker}
            tickers={allTickers}
            collapsed={chatCollapsed}
            onToggleCollapse={() => setChatCollapsed((c) => !c)}
          />
        </div>

        {/* ── Mobile layout: stacked ── */}
        <div className="md:hidden flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Mobile: collapsible stock list */}
          <div className="shrink-0 border-b border-gray-700 bg-gray-800/80">
            <button
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors"
            >
              <span className="font-medium">Focus Tickers</span>
              <svg
                className={`w-4 h-4 transition-transform duration-200 ${sidebarCollapsed ? '' : 'rotate-180'}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {!sidebarCollapsed && (
              <div style={{ maxHeight: '30vh', overflowY: 'auto' }}>
                <DashboardStockSidebar
                  subscribedWidgets={widgets}
                  recentWidgets={[]}
                  tickerToName={tickerToName}
                  selectedTicker={selectedTicker}
                  onSelect={(ticker) => { setSelectedTicker(ticker); setSidebarCollapsed(true); }}
                  onAdd={(ticker) => { addTicker(ticker); setSidebarCollapsed(true); }}
                  onRemove={removeTicker}
                />
              </div>
            )}
          </div>

          {/* Mobile: stock detail + chat tabs */}
          <MobileStockChatTabs
            selectedTicker={selectedTicker}
            tickers={allTickers}
            prefetchCache={prefetchCache}
            onSubscriptionChange={handleSubscriptionChange}
          />
        </div>
      </div>
    </div>
  );
}

/** Mobile-only tabbed view: Stock Detail | Copilot */
function MobileStockChatTabs({
  selectedTicker,
  tickers,
  prefetchCache,
  onSubscriptionChange,
}: {
  selectedTicker: string | null;
  tickers: string[];
  prefetchCache: Record<string, StockPageData>;
  onSubscriptionChange: () => void;
}) {
  const [activeTab, setActiveTab] = useState<'stock' | 'chat'>('stock');

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Tab bar */}
      <div className="shrink-0 flex border-b border-gray-700 bg-gray-800/80">
        <button
          type="button"
          onClick={() => setActiveTab('stock')}
          className={`flex-1 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'stock'
              ? 'text-white border-blue-500 bg-gray-800'
              : 'text-gray-400 border-transparent hover:text-white'
          }`}
        >
          Stock Detail
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('chat')}
          className={`flex-1 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'chat'
              ? 'text-white border-blue-500 bg-gray-800'
              : 'text-gray-400 border-transparent hover:text-white'
          }`}
        >
          Copilot
        </button>
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === 'stock' && (
          <div className="h-full overflow-y-auto bg-gray-900">
            {selectedTicker ? (
              <StockDetailPanel
                key={selectedTicker}
                ticker={selectedTicker}
                prefetchedData={prefetchCache[selectedTicker] ?? null}
                onSubscriptionChange={onSubscriptionChange}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm p-8">
                Select a stock from the list above to view details.
              </div>
            )}
          </div>
        )}
        {activeTab === 'chat' && (
          <div className="h-full">
            <CopilotChatPanel selectedTicker={selectedTicker} tickers={tickers} />
          </div>
        )}
      </div>
    </div>
  );
}

// Made with Bob