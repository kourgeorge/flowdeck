import type { ProfileTabType } from './profileTypes';

const TABS: Array<{ id: ProfileTabType; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'usage', label: 'Usage' },
  { id: 'investor-profile', label: 'Investor profile' },
  { id: 'api-keys', label: 'API keys' },
  { id: 'account', label: 'Account' },
  { id: 'brief-schedule', label: 'Brief schedule' },
];

type ProfileTabNavigationProps = {
  activeTab: ProfileTabType;
  onTabChange: (tab: ProfileTabType) => void;
};

export default function ProfileTabNavigation({
  activeTab,
  onTabChange,
}: ProfileTabNavigationProps) {
  return (
    <nav
      className="mb-8 overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/80 p-2 scrollbar-hide"
      aria-label="Profile sections"
    >
      <div className="flex min-w-max gap-2">
        {TABS.map((tab) => {
          const isActive = tab.id === activeTab;

          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={`rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-cyan-500 text-slate-950'
                  : 'text-slate-300 hover:bg-white/5 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
