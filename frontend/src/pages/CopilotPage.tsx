import { useState, useRef, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import DashboardTickerSidebar from '../components/DashboardTickerSidebar';
import StockDetailPanel from '../components/TickerDetailPanel';
import CopilotChatPanel from '../components/CopilotChatPanel';
import PageHeader from '../components/PageHeader';
import { useSubscribedStocks } from '../hooks/useSubscribedStocks';
import { useAuth } from '../contexts/AuthContext';
import { COPILOT_NAME } from '../config';
import type { TickerPageData, TickerWidget } from '../services/types';
import { chatApi } from '../services/api';
import { useChatState } from '../components/ChatView';

/** Desktop (md and up): tickers pane open by default. Mobile: collapsed by default. */
function getInitialSidebarCollapsed(): boolean {
  if (typeof window === 'undefined') return true;
  return !window.matchMedia('(min-width: 768px)').matches;
}

export default function CopilotPage() {
  const { user } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(getInitialSidebarCollapsed);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [chatWidth, setChatWidth] = useState(384); // default w-96
  const isResizing = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const {
    widgets,
    tickerToName,
    isLoading,
    selectedTicker,
    setSelectedTicker,
    prefetchCache,
    prefetchProgress,
    handleSubscriptionChange,
    addTicker,
    removeTicker,
  } = useSubscribedStocks();

  const prefetchPercent =
    prefetchProgress.total > 0
      ? Math.round((prefetchProgress.completed / prefetchProgress.total) * 100)
      : 0;
  const showCopilotLoadingStatus =
    isLoading ||
    (widgets.length > 0 &&
      (prefetchProgress.inFlight > 0 || prefetchProgress.completed < prefetchProgress.total));

  // All tickers in the user's watchlist — passed to the AI analyst for full context
  const allTickers = widgets.map((w: TickerWidget) => w.ticker);

  // Build context object with all tickers so the AI knows the full watchlist
  const context = useMemo(
    () => (allTickers.length > 0 ? { tickers: allTickers } : undefined),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allTickers.join(',')],
  );

  // Session id so that loading a conversation and continuing uses the same session (no new one created)
  const [sessionId, setSessionId] = useState<number | null>(null);
  const chatRefreshSessionsRef = useRef<(() => void) | null>(null);
  const onStreamDone = useCallback((newSessionId?: number) => {
    if (newSessionId != null) setSessionId(newSessionId);
    chatRefreshSessionsRef.current?.();
  }, []);

  const createSessionIfNeeded = useCallback(async () => {
    const { id } = await chatApi.createChatSession();
    setSessionId(id);
    chatRefreshSessionsRef.current?.();
    return id;
  }, []);

  // Lift chat state to parent component so it persists across tab switches in mobile mode
  const chatState = useChatState(undefined, context, sessionId, onStreamDone, createSessionIfNeeded);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    isResizing.current = true;
    startX.current = e.clientX;
    startWidth.current = chatWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      const delta = startX.current - ev.clientX; // dragging left increases width
      const newWidth = Math.min(800, Math.max(240, startWidth.current + delta));
      setChatWidth(newWidth);
    };

    const onMouseUp = () => {
      isResizing.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [chatWidth]);

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
          <h2 className="text-lg font-semibold text-white mb-2">Sign in to use {COPILOT_NAME}</h2>
          <p className="text-gray-400 mb-6 text-sm">
            {COPILOT_NAME} is your Trading Copilot — it combines the stock view with an AI analyst chat so you can research and discuss stocks side by side.
          </p>
          <Link to="/" className="inline-block px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
            Go to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">

      <PageHeader
        title={`${COPILOT_NAME} – Trading assistant`}
        icon={
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        }
      />

      {showCopilotLoadingStatus && (
        <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 px-3 py-2 text-xs text-gray-300">
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>Preparing {COPILOT_NAME}…</span>
          </div>
          <div className="mt-1.5 space-y-1">
            <div>
              Focus tickers:
              {' '}
              {isLoading ? 'loading…' : widgets.length}
            </div>
            <div>
              Stock prefetch:
              {' '}
              {prefetchProgress.completed} / {prefetchProgress.total}
              {prefetchProgress.inFlight > 0 ? ` (${prefetchProgress.inFlight} in progress)` : ''}
            </div>
            {prefetchProgress.total > 0 && (
              <div className="h-1.5 w-full rounded bg-gray-700 overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${prefetchPercent}%` }}
                />
              </div>
            )}
          </div>
        </div>
      )}

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
              <DashboardTickerSidebar
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

        {/* ── Right: AI Trading Copilot — {COPILOT_NAME} ── */}
        <div
          className="shrink-0 hidden md:flex flex-row min-h-0"
          style={{ width: chatCollapsed ? 24 : chatWidth }}
        >
          {/* Resize handle */}
          {!chatCollapsed && (
            <div
              onMouseDown={onResizeStart}
              className="shrink-0 w-1 self-stretch cursor-col-resize bg-gray-700 hover:bg-blue-500 transition-colors"
              title="Drag to resize chat panel"
            />
          )}
          <div className="flex-1 min-w-0 flex flex-col min-h-0">
            <CopilotChatPanel
              selectedTicker={selectedTicker}
              tickers={allTickers}
              collapsed={chatCollapsed}
              onToggleCollapse={() => setChatCollapsed((c) => !c)}
              chatState={chatState}
              sessionId={sessionId}
              onSessionIdChange={setSessionId}
              externalRefreshSessionsRef={chatRefreshSessionsRef}
            />
          </div>
        </div>

        {/* ── Mobile layout: stacked ── */}
        <div className="md:hidden flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Mobile: collapsible stock list */}
          <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 relative">
            <button
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-gray-300 hover:text-white bg-blue-900/20 hover:bg-blue-800/30 transition-colors"
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
              <div className="absolute top-full left-0 right-0 z-[60] bg-gray-950 border border-gray-700 shadow-2xl" style={{ maxHeight: '50vh', overflowY: 'auto' }}>
                <DashboardTickerSidebar
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
            chatState={chatState}
            sessionId={sessionId}
            onSessionIdChange={setSessionId}
            externalRefreshSessionsRef={chatRefreshSessionsRef}
          />
        </div>
      </div>
    </div>
  );
}

/** Mobile-only tabbed view: Stock Detail | {COPILOT_NAME} */
function MobileStockChatTabs({
  selectedTicker,
  tickers,
  prefetchCache,
  onSubscriptionChange,
  chatState,
  sessionId,
  onSessionIdChange,
  externalRefreshSessionsRef,
}: {
  selectedTicker: string | null;
  tickers: string[];
  prefetchCache: Record<string, TickerPageData>;
  onSubscriptionChange: () => void;
  chatState: ReturnType<typeof useChatState>;
  sessionId: number | null;
  onSessionIdChange: (id: number | null) => void;
  externalRefreshSessionsRef: React.MutableRefObject<(() => void) | null>;
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
          {COPILOT_NAME}
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
            <CopilotChatPanel
              selectedTicker={selectedTicker}
              tickers={tickers}
              chatState={chatState}
              sessionId={sessionId}
              onSessionIdChange={onSessionIdChange}
              externalRefreshSessionsRef={externalRefreshSessionsRef}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// Made with Bob