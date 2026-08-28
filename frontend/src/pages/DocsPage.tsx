import { useSearchParams, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import HowItWorksPage from './HowItWorksPage';
import TpsPage from './TpsPage';
import ArchitecturePage from './ArchitecturePage';

type TabId = 'how-it-works' | 'tps' | 'architecture';

export default function DocsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabId>('how-it-works');

  if (searchParams.get('tab') === 'api') {
    return <Navigate to="/api-docs" replace />;
  }

  useEffect(() => {
    const tab = searchParams.get('tab') as TabId;
    if (tab && ['how-it-works', 'tps', 'architecture'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const tabs = [
    { id: 'how-it-works' as TabId, label: 'How It Works', icon: '📖' },
    { id: 'tps' as TabId, label: 'TPS Spec', icon: '📋' },
    { id: 'architecture' as TabId, label: 'Architecture', icon: '🏗️' },
  ];

  return (
    <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
      <div className="w-full">
        <h1 className="text-3xl font-bold text-white mb-2">FlowDeck Documentation</h1>
        <p className="text-gray-400 mb-8">
          Complete guide to understanding and using FlowDeck's AI-powered stock analysis platform.
        </p>

        {/* Tab Navigation */}
        <div className="border-b border-gray-700 mb-8">
          <nav className="flex gap-1 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2 ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-white hover:border-gray-600'
                }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content - Render existing page components */}
        <div className="text-gray-300">
          {activeTab === 'how-it-works' && <HowItWorksPage />}
          {activeTab === 'tps' && <TpsPage />}
          {activeTab === 'architecture' && <ArchitecturePage />}
        </div>
      </div>
    </div>
  );
}

// Made with Bob
