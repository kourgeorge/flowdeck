import { useState } from 'react';
import StockDetailPanel from './TickerDetailPanel';
import CopilotChatPanel from './CopilotChatPanel';
import { COPILOT_NAME } from '../config';
import type { TickerPageData } from '../services/types';
import type { UseChatStateReturn } from './ChatView';

export interface MobileStockChatTabsProps {
  selectedTicker: string | null;
  tickers: string[];
  prefetchCache: Record<string, TickerPageData>;
  onSubscriptionChange: () => void;
  /** Label for the chat tab. Defaults to COPILOT_NAME. */
  chatTabLabel?: string;
  /** Optional external chat state (e.g. for Copilot page persistence). */
  chatState?: UseChatStateReturn;
  sessionId?: number | null;
  onSessionIdChange?: (id: number | null) => void;
  externalRefreshSessionsRef?: React.MutableRefObject<(() => void) | null>;
}

/** Mobile-only tabbed view: Stock Detail | Chat. Used by Copilot page. */
export default function MobileStockChatTabs({
  selectedTicker,
  tickers,
  prefetchCache,
  onSubscriptionChange,
  chatTabLabel = COPILOT_NAME,
  chatState,
  sessionId,
  onSessionIdChange,
  externalRefreshSessionsRef,
}: MobileStockChatTabsProps) {
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
          {chatTabLabel}
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
              title={chatTabLabel}
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
