import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { watchlistNotificationApi, type WatchlistNotificationPreferences } from '../../services/api';
import { PROFILE_MUTED_PANEL_CLASS } from './profileStyles';

export default function WatchlistNotifications() {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState<WatchlistNotificationPreferences | null>(null);
  const [timezone, setTimezone] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPreferences(null);
    setError(null);
    watchlistNotificationApi.get().then((result) => {
      if (cancelled) return;
      setPreferences(result);
      setTimezone(result.timezone);
    }).catch(() => {
      if (!cancelled) setError('Could not load morning update preferences. Please refresh to try again.');
    });
    return () => { cancelled = true; };
  }, [user?.userId]);

  const save = async (enabled: boolean, timezoneName = timezone) => {
    setSaving(true);
    setError(null);
    try {
      const result = await watchlistNotificationApi.update(enabled, timezoneName);
      setPreferences(result);
      setTimezone(result.timezone);
    } catch {
      setError('Could not save. Check the timezone and try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`${PROFILE_MUTED_PANEL_CLASS} mt-6 p-4`}>
      <label className="flex items-start justify-between gap-4">
        <span>
          <span className="font-semibold text-white">Morning watchlist updates</span>
          <span className="mt-2 block text-sm leading-6 text-slate-300">
            Get an AI-researched article when a stock you follow moves more than 6% up or down
            and shows significant event signals. We explain the news, likely drivers, and what to watch.
            Enabled by default, with at most one update each morning.
          </span>
        </span>
        <input type="checkbox" aria-label="Morning watchlist updates"
          checked={preferences?.enabled ?? false} disabled={!preferences || saving}
          onChange={(event) => save(event.target.checked, preferences?.timezone)}
          className="mt-1 h-4 w-4 shrink-0 accent-cyan-500" />
      </label>
      {preferences && (
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-400">
            Check at {String(preferences.hour).padStart(2, '0')}:00 in this timezone
            <input value={timezone} onChange={(event) => setTimezone(event.target.value)}
              disabled={saving} placeholder="America/New_York"
              className="mt-1 block rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100" />
          </label>
          <button type="button" disabled={saving || timezone === preferences.timezone}
            onClick={() => save(preferences.enabled)}
            className="rounded-lg bg-cyan-700 px-3 py-2 text-sm text-white disabled:opacity-40">
            {saving ? 'Saving…' : 'Save timezone'}
          </button>
        </div>
      )}
      {!preferences && !error && <p className="mt-2 text-sm text-slate-400">Loading preferences…</p>}
      {error && <p role="alert" className="mt-2 text-sm text-rose-300">{error}</p>}
    </div>
  );
}
