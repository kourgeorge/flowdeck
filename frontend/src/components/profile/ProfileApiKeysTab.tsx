import ApiKeyManagement from '../ApiKeyManagement';
import { PROFILE_PANEL_CLASS, PROFILE_PILL_CLASS } from './profileStyles';

export default function ProfileApiKeysTab() {
  return (
    <section className={`${PROFILE_PANEL_CLASS} p-6`}>
      <div className="max-w-3xl">
        <span className={`${PROFILE_PILL_CLASS} border-violet-400/30 bg-violet-400/10 text-violet-100`}>
          Developer access
        </span>
        <h2 className="mt-4 text-xl font-semibold text-white">API keys</h2>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          Create API keys for programmatic access to FlowDeck. Use them in bots,
          scripts, and integrations.
        </p>
      </div>
      <div className="mt-6">
        <ApiKeyManagement />
      </div>
    </section>
  );
}
