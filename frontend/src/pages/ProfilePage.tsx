import { useState, useEffect, useCallback } from 'react';
import type { ChangeEvent } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { profileApi, type MeProfile } from '../services/authApi';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import PageHeader from '../components/PageHeader';
import TokenPurchase from '../components/TokenPurchase';
import UserStatsSection from '../components/UserStatsSection';
import ApiKeyManagement from '../components/ApiKeyManagement';
import { digestScheduleApi, type DigestSchedule, type DigestScheduleType } from '../services/api';

const DELETE_CONFIRM_TEXT = 'DELETE';

type TabType = 'overview' | 'api-keys' | 'account' | 'brief-schedule';

type DigestNarrativeStyle = 'default' | 'concise' | 'professional' | 'technical';

export default function ProfilePage() {
  const { user, deleteAccount } = useAuth();
  const navigate = useNavigate();
  const { hash } = useLocation();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Name form
  const [name, setName] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameMessage, setNameMessage] = useState<string | null>(null);

  // Password form
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);

  // Delete account
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Subscriptions (email preferences)
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
  const [togglingTicker, setTogglingTicker] = useState<string | null>(null);

  // Brief schedules
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [schedulesError, setSchedulesError] = useState<string | null>(null);

  const [dailyEnabled, setDailyEnabled] = useState(false);
  const [dailyTime, setDailyTime] = useState('08:00');
  const [dailyNarrativeStyle, setDailyNarrativeStyle] = useState<DigestNarrativeStyle>('default');
  const [dailyUserNote, setDailyUserNote] = useState('');
  const [dailyFocusTickers, setDailyFocusTickers] = useState<string[]>([]);
  const [dailyTimezone, setDailyTimezone] = useState<string>('');
  const [dailySaving, setDailySaving] = useState(false);
  const [dailySaveMessage, setDailySaveMessage] = useState<string | null>(null);
  const [dailyLastExecutedAt, setDailyLastExecutedAt] = useState<string | null>(null);

  const [weeklyEnabled, setWeeklyEnabled] = useState(false);
  const [weeklyTime, setWeeklyTime] = useState('08:00');
  const [weeklyDayOfWeek, setWeeklyDayOfWeek] = useState(0); // Monday by default
  const [weeklyNarrativeStyle, setWeeklyNarrativeStyle] = useState<DigestNarrativeStyle>('default');
  const [weeklyUserNote, setWeeklyUserNote] = useState('');
  const [weeklyFocusTickers, setWeeklyFocusTickers] = useState<string[]>([]);
  const [weeklyTimezone, setWeeklyTimezone] = useState<string>('');
  const [weeklySaving, setWeeklySaving] = useState(false);
  const [weeklySaveMessage, setWeeklySaveMessage] = useState<string | null>(null);
  const [weeklyLastExecutedAt, setWeeklyLastExecutedAt] = useState<string | null>(null);
  const [editingSchedules, setEditingSchedules] = useState(false);

  const loadSubscriptions = useCallback(async () => {
    if (!user) return;
    setSubscriptionsLoading(true);
    try {
      const list = await subscriptionApi.list();
      setSubscriptions(list);
    } catch {
      setSubscriptions([]);
    } finally {
      setSubscriptionsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  const loadSchedules = useCallback(async () => {
    if (!user) return;
    setSchedulesLoading(true);
    setSchedulesError(null);
    try {
      const data = await digestScheduleApi.getSchedules();
      const defaultTz =
        Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

      if (data.daily) {
        applyScheduleToState(data.daily, 'daily');
      } else {
        setDailyTimezone(defaultTz);
      }

      if (data.weekly) {
        applyScheduleToState(data.weekly, 'weekly');
      } else {
        setWeeklyTimezone(defaultTz);
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setSchedulesError(
        typeof msg === 'string'
          ? msg
          : 'Failed to load brief schedules',
      );
    } finally {
      setSchedulesLoading(false);
    }
  }, [user]);

  const formatLastRun = (iso: string | null) => {
    if (!iso) return 'Never';
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return 'Never';
      return d.toLocaleString();
    } catch {
      return 'Never';
    }
  };

  function applyScheduleToState(schedule: DigestSchedule, which: 'daily' | 'weekly') {
    const hh = String(schedule.hour).padStart(2, '0');
    const mm = String(schedule.minute).padStart(2, '0');
    const timeStr = `${hh}:${mm}`;
    const tz = schedule.timezone || '';
    const meta = schedule.metadata || {};
    const narrativeStyle = (meta.narrative_style as DigestNarrativeStyle | null) ?? 'default';
    const note = meta.user_note ?? '';
    const focus = meta.user_focus_tickers ?? [];

    if (which === 'daily') {
      setDailyEnabled(schedule.enabled);
      setDailyTime(timeStr);
      setDailyTimezone(tz);
      setDailyNarrativeStyle(narrativeStyle);
      setDailyUserNote(note);
      setDailyFocusTickers(focus);
      setDailyLastExecutedAt(schedule.last_executed_at ?? null);
    } else {
      setWeeklyEnabled(schedule.enabled);
      setWeeklyTime(timeStr);
      setWeeklyTimezone(tz);
      setWeeklyNarrativeStyle(narrativeStyle);
      setWeeklyUserNote(note);
      setWeeklyFocusTickers(focus);
      if (typeof schedule.day_of_week === 'number') {
        setWeeklyDayOfWeek(schedule.day_of_week);
      }
      setWeeklyLastExecutedAt(schedule.last_executed_at ?? null);
    }
  }

  const handleEmailUpdatesToggle = async (ticker: string, email_updates: boolean) => {
    setTogglingTicker(ticker);
    try {
      const updated = await subscriptionApi.updateEmailPreference(ticker, email_updates);
      setSubscriptions((prev) =>
        prev.map((s) => (s.ticker === updated.ticker ? updated : s))
      );
    } finally {
      setTogglingTicker(null);
    }
  };

  // Handle tab switching from hash
  useEffect(() => {
    if (hash === '#api-keys') {
      setActiveTab('api-keys');
    } else if (hash === '#account') {
      setActiveTab('account');
    } else if (hash === '#brief-schedule') {
      setActiveTab('brief-schedule');
    } else {
      setActiveTab('overview');
    }
  }, [hash]);

  useEffect(() => {
    if (activeTab === 'brief-schedule') {
      loadSchedules();
    }
  }, [activeTab, loadSchedules]);

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    profileApi
      .getMe()
      .then((data) => {
        if (!cancelled) {
          setProfile(data);
          setName(data.name ?? '');
        }
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load profile');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const handleSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameMessage(null);
    setNameSaving(true);
    try {
      const data = await profileApi.updateProfile({ name: name.trim() || null });
      setProfile(data);
      setNameMessage('Name updated.');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setNameMessage(typeof msg === 'string' ? msg : 'Failed to update name');
    } finally {
      setNameSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMessage(null);
    if (newPassword !== confirmPassword) {
      setPasswordMessage('New password and confirmation do not match.');
      return;
    }
    if (newPassword.length < 6) {
      setPasswordMessage('New password must be at least 6 characters.');
      return;
    }
    setPasswordSaving(true);
    try {
      await profileApi.updateProfile({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordMessage('Password updated.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      const data = await profileApi.getMe();
      setProfile(data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPasswordMessage(typeof msg === 'string' ? msg : 'Failed to update password');
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleDeleteAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError(null);
    if (deleteConfirmText !== DELETE_CONFIRM_TEXT) {
      setDeleteError(`Type ${DELETE_CONFIRM_TEXT} to confirm.`);
      return;
    }
    // Only require password if user has one (not Google-only)
    if (profile?.has_password && !deletePassword.trim()) {
      setDeleteError('Enter your password to confirm.');
      return;
    }
    setDeleteLoading(true);
    try {
      await deleteAccount(profile?.has_password ? deletePassword : undefined);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setDeleteError(typeof msg === 'string' ? msg : 'Failed to delete account');
    } finally {
      setDeleteLoading(false);
    }
  };

  const parseTime = (value: string): { hour: number; minute: number } => {
    const [h, m] = value.split(':');
    const hour = Math.min(23, Math.max(0, Number(h) || 0));
    const minute = Math.min(59, Math.max(0, Number(m) || 0));
    return { hour, minute };
  };

  const saveSchedule = async (type: DigestScheduleType) => {
    const isDaily = type === 'daily_digest';
    const { hour, minute } = parseTime(isDaily ? dailyTime : weeklyTime);
    const timezone = (isDaily ? dailyTimezone : weeklyTimezone) || null;
    const enabled = isDaily ? dailyEnabled : weeklyEnabled;
    const narrativeStyle = (isDaily ? dailyNarrativeStyle : weeklyNarrativeStyle) ?? 'default';
    const userNote = (isDaily ? dailyUserNote : weeklyUserNote) || null;
    const focusTickers = (isDaily ? dailyFocusTickers : weeklyFocusTickers) || [];
    const dayOfWeek = isDaily ? null : weeklyDayOfWeek;

    const payload = {
      enabled,
      hour,
      minute,
      day_of_week: dayOfWeek,
      timezone,
      metadata: {
        user_note: userNote,
        narrative_style: narrativeStyle === 'default' ? null : narrativeStyle,
        user_focus_tickers: focusTickers.length ? focusTickers : null,
      },
    };

    if (isDaily) {
      setDailySaving(true);
      setDailySaveMessage(null);
    } else {
      setWeeklySaving(true);
      setWeeklySaveMessage(null);
    }

    try {
      const updated = await digestScheduleApi.updateSchedule(type, payload);
      applyScheduleToState(updated, isDaily ? 'daily' : 'weekly');
      if (isDaily) {
        setDailySaveMessage('Daily brief schedule saved.');
        setTimeout(() => setDailySaveMessage(null), 3000);
      } else {
        setWeeklySaveMessage('Weekly brief schedule saved.');
        setTimeout(() => setWeeklySaveMessage(null), 3000);
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setSchedulesError(
        typeof msg === 'string'
          ? msg
          : 'Failed to save brief schedule',
      );
    } finally {
      if (isDaily) {
        setDailySaving(false);
      } else {
        setWeeklySaving(false);
      }
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-lg mx-auto text-center text-gray-400">
          <p className="mb-4">Please log in to view and edit your profile.</p>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="text-blue-400 hover:text-blue-300"
          >
            Go to home
          </button>
        </div>
      </div>
    );
  }

  if (loading || (!profile && !error)) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center">
          <svg className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-gray-400 text-sm">Loading profile…</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-lg mx-auto text-center text-gray-400">
          <p className="mb-4">{error}</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300">
            Go to home
          </Link>
        </div>
      </div>
    );
  }

  const renderTabContent = () => {
    if (activeTab === 'overview') {
      return (
        <>
          {/* Token Balance */}
          {profile && (
            <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-2">Token balance</h2>
              <p className="text-3xl font-bold text-white">{profile.token_balance.toLocaleString()} tokens</p>
              <p className="text-sm text-gray-400 mt-1">
                Ticker analysis and AI assistant usage cost tokens. Earn tokens when others view your reports.
              </p>
            </section>
          )}

          {/* Usage Statistics */}
          <UserStatsSection />

          {/* Purchase Tokens */}
          {profile && (
            <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">Purchase Tokens</h2>
              <p className="text-sm text-gray-400 mb-6">
                Need more tokens? Choose a package below to top up your account with PayPal.
              </p>
              <TokenPurchase />
            </section>
          )}

          {/* Subscription email preferences */}
          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-2">Subscription email preferences</h2>
            <p className="text-sm text-gray-400 mb-4">
              Choose whether to receive an email when a new analysis report is ready for each subscribed stock.
            </p>
            {subscriptionsLoading ? (
              <p className="text-gray-400 text-sm">Loading subscriptions…</p>
            ) : subscriptions.length === 0 ? (
              <p className="text-gray-400 text-sm">You have no subscriptions. Subscribe to stocks from a stock page or the dashboard.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {subscriptions.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between gap-4 py-2 px-3 rounded-lg bg-gray-700/30 border border-gray-600/30"
                  >
                    <Link
                      to={`/tickers/${s.ticker}`}
                      className="text-blue-400 hover:text-blue-300 font-medium shrink-0"
                    >
                      {s.ticker}
                    </Link>
                    <label className="flex items-center gap-2 cursor-pointer shrink-0">
                      <span className="text-sm text-gray-400">Email</span>
                      <input
                        type="checkbox"
                        checked={s.email_updates}
                        disabled={togglingTicker === s.ticker}
                        onChange={(e) => handleEmailUpdatesToggle(s.ticker, e.target.checked)}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      );
    }

    if (activeTab === 'api-keys') {
      return (
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">API Keys</h2>
          <p className="text-sm text-gray-400 mb-6">
            Create API keys for programmatic access to FlowDeck. Use them in bots, scripts, and integrations.
          </p>
          <ApiKeyManagement />
        </section>
      );
    }

    if (activeTab === 'account') {
      return (
        <>
          {/* Email (read-only) */}
          {profile && (
            <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-2">Email</h2>
              <p className="text-gray-300">{profile.email}</p>
              <p className="text-xs text-gray-500 mt-1">Email cannot be changed here.</p>
            </section>
          )}

          {/* Name */}
          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-4">Display name</h2>
            <form onSubmit={handleSaveName} className="space-y-4">
              <div>
                <label htmlFor="profile-name" className="block text-sm font-medium text-gray-300 mb-1">
                  Name
                </label>
                <input
                  id="profile-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Your name"
                />
              </div>
              {nameMessage && (
                <p className={`text-sm ${nameMessage.startsWith('Name updated') ? 'text-green-400' : 'text-red-400'}`}>
                  {nameMessage}
                </p>
              )}
              <button
                type="submit"
                disabled={nameSaving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {nameSaving ? 'Saving…' : 'Save name'}
              </button>
            </form>
          </section>

          {/* Password - only show for users with passwords */}
          {profile?.has_password && (
            <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">Change password</h2>
              <form onSubmit={handleChangePassword} className="space-y-4">
                <div>
                  <label htmlFor="profile-current-password" className="block text-sm font-medium text-gray-300 mb-1">
                    Current password
                  </label>
                  <input
                    id="profile-current-password"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                </div>
                <div>
                  <label htmlFor="profile-new-password" className="block text-sm font-medium text-gray-300 mb-1">
                    New password
                  </label>
                  <input
                    id="profile-new-password"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                    autoComplete="new-password"
                    minLength={6}
                  />
                </div>
                <div>
                  <label htmlFor="profile-confirm-password" className="block text-sm font-medium text-gray-300 mb-1">
                    Confirm new password
                  </label>
                  <input
                    id="profile-confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                    autoComplete="new-password"
                    minLength={6}
                  />
                </div>
                {passwordMessage && (
                  <p
                    className={`text-sm ${
                      passwordMessage.startsWith('Password updated') ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {passwordMessage}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={passwordSaving}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {passwordSaving ? 'Updating…' : 'Change password'}
                </button>
              </form>
            </section>
          )}

          {/* Delete account */}
          <section className="bg-gray-800 border border-red-900/50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-red-400 mb-2">Delete account</h2>
            <p className="text-sm text-gray-400 mb-4">
              This will permanently delete your account and all associated data (subscriptions, etc.). This cannot be undone.
            </p>
            <form onSubmit={handleDeleteAccount} className="space-y-4">
              {profile?.has_password && (
                <div>
                  <label htmlFor="delete-password" className="block text-sm font-medium text-gray-300 mb-1">
                    Your password
                  </label>
                  <input
                    id="delete-password"
                    type="password"
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                </div>
              )}
              <div>
                <label htmlFor="delete-confirm-text" className="block text-sm font-medium text-gray-300 mb-1">
                  Type {DELETE_CONFIRM_TEXT} to confirm
                </label>
                <input
                  id="delete-confirm-text"
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
                  placeholder={DELETE_CONFIRM_TEXT}
                  autoComplete="off"
                />
              </div>
              {deleteError && (
                <p className="text-sm text-red-400">{deleteError}</p>
              )}
              <button
                type="submit"
                disabled={deleteLoading || deleteConfirmText !== DELETE_CONFIRM_TEXT || (profile?.has_password && !deletePassword.trim())}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-default text-white rounded-lg text-sm font-medium transition-colors"
              >
                {deleteLoading ? 'Deleting…' : 'Delete my account'}
              </button>
            </form>
          </section>
        </>
      );
    }

    if (activeTab === 'brief-schedule') {
      const subscriptionTickers = subscriptions.map((s) => s.ticker);
      const weekDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

      return (
        <>
          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-2">User Daily Brief schedule</h2>
            <p className="text-sm text-gray-400 mb-4">
              Configure automatic email delivery of your User Daily Brief. The brief uses your subscribed tickers
              and the same engine as the dashboard tab, but runs on a schedule in your local timezone.
            </p>
            <div className="mb-4 flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                {/* Daily panel */}
                <div className="flex-1 bg-gray-900/60 border border-gray-700 rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs font-semibold text-gray-100 uppercase tracking-wide">Daily brief</p>
                    <span className={`text-[11px] font-mono ${dailyEnabled ? 'text-green-400' : 'text-gray-500'}`}>
                      {dailyEnabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <dl className="space-y-0.5 text-[11px] text-gray-300">
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Time:</dt>
                      <dd>{dailyTime || '—'}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Timezone:</dt>
                      <dd>{dailyTimezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'default'}</dd>
                    </div>
                  <div className="flex gap-1.5">
                    <dt className="text-gray-500">Last run:</dt>
                    <dd>{formatLastRun(dailyLastExecutedAt)}</dd>
                  </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Style:</dt>
                      <dd>
                        {dailyNarrativeStyle === 'default'
                          ? 'Balanced (default)'
                          : dailyNarrativeStyle.charAt(0).toUpperCase() + dailyNarrativeStyle.slice(1)}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Note:</dt>
                      <dd className="truncate max-w-[14rem]" title={dailyUserNote || undefined}>
                        {dailyUserNote ? dailyUserNote : '—'}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Focus:</dt>
                      <dd>
                        {dailyFocusTickers.length === 0
                          ? 'Auto-select from portfolio'
                          : `${dailyFocusTickers.length} ticker${dailyFocusTickers.length > 1 ? 's' : ''}`}
                      </dd>
                    </div>
                  </dl>
                </div>
                {/* Weekly panel */}
                <div className="flex-1 bg-gray-900/60 border border-gray-700 rounded-lg px-3 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs font-semibold text-gray-100 uppercase tracking-wide">Weekly brief</p>
                    <span className={`text-[11px] font-mono ${weeklyEnabled ? 'text-green-400' : 'text-gray-500'}`}>
                      {weeklyEnabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <dl className="space-y-0.5 text-[11px] text-gray-300">
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Weekday:</dt>
                      <dd>{(() => {
                        const weekDaysFull = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
                        return weekDaysFull[weeklyDayOfWeek] ?? '—';
                      })()}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Time:</dt>
                      <dd>{weeklyTime || '—'}</dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Timezone:</dt>
                      <dd>{weeklyTimezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'default'}</dd>
                    </div>
                  <div className="flex gap-1.5">
                    <dt className="text-gray-500">Last run:</dt>
                    <dd>{formatLastRun(weeklyLastExecutedAt)}</dd>
                  </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Style:</dt>
                      <dd>
                        {weeklyNarrativeStyle === 'default'
                          ? 'Balanced (default)'
                          : weeklyNarrativeStyle.charAt(0).toUpperCase() + weeklyNarrativeStyle.slice(1)}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Note:</dt>
                      <dd className="truncate max-w-[14rem]" title={weeklyUserNote || undefined}>
                        {weeklyUserNote ? weeklyUserNote : '—'}
                      </dd>
                    </div>
                    <div className="flex gap-1.5">
                      <dt className="text-gray-500">Focus:</dt>
                      <dd>
                        {weeklyFocusTickers.length === 0
                          ? 'Auto-select from portfolio'
                          : `${weeklyFocusTickers.length} ticker${weeklyFocusTickers.length > 1 ? 's' : ''}`}
                      </dd>
                    </div>
                  </dl>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setEditingSchedules((v) => !v)}
                className="self-start inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-600 bg-gray-800 text-gray-100 hover:bg-gray-700 transition-colors"
              >
                {editingSchedules ? (
                  <>
                    <span>Done editing</span>
                  </>
                ) : (
                  <>
                    <span>Edit schedules</span>
                  </>
                )}
              </button>
            </div>
            {schedulesError && (
              <p className="mb-3 text-sm text-red-400">{schedulesError}</p>
            )}
            {schedulesLoading ? (
              <p className="text-sm text-gray-400">Loading schedules…</p>
            ) : editingSchedules ? (
              <div className="space-y-6">
                {/* Daily schedule */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Daily brief</h3>
                      <p className="text-xs text-gray-400">
                        Get a brief for today&apos;s market every day at the selected time.
                      </p>
                    </div>
                    <label className="inline-flex items-center gap-2 cursor-pointer">
                      <span className="text-xs text-gray-400">Enabled</span>
                      <input
                        type="checkbox"
                        checked={dailyEnabled}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setDailyEnabled(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
                      />
                    </label>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Time of day
                      </label>
                      <input
                        type="time"
                        value={dailyTime}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setDailyTime(e.target.value)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Timezone
                      </label>
                      <input
                        type="text"
                        value={dailyTimezone}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setDailyTimezone(e.target.value)}
                        placeholder="e.g. Europe/Athens"
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <p className="mt-1 text-[11px] text-gray-500">
                        Uses IANA timezone names. Leave empty to use the default ({Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'}).
                      </p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Brief style
                      </label>
                      <select
                        value={dailyNarrativeStyle}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => setDailyNarrativeStyle(e.target.value as DigestNarrativeStyle)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="default">Balanced (default)</option>
                        <option value="concise">Concise</option>
                        <option value="professional">Professional</option>
                        <option value="technical">Technical (more detail)</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Optional note
                      </label>
                      <textarea
                        value={dailyUserNote}
                        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setDailyUserNote(e.target.value)}
                        maxLength={2000}
                        rows={3}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-xs text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                        placeholder="E.g. Emphasize earnings, focus on risk, income needs in 3 months…"
                      />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-xs font-medium text-gray-300">
                          Focus tickers
                        </label>
                        {dailyFocusTickers.length > 0 && (
                          <button
                            type="button"
                            onClick={() => setDailyFocusTickers([])}
                            className="text-[11px] text-blue-300 hover:text-blue-200 underline-offset-2 hover:underline"
                          >
                            Clear
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-gray-500 mb-1">
                        Optional subset of your subscribed tickers to emphasize. Leave empty to let the system pick.
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {subscriptionTickers.length === 0 && (
                          <span className="text-[11px] text-gray-500">
                            Subscribe to tickers on the dashboard to pick focus tickers here.
                          </span>
                        )}
                        {subscriptionTickers.map((t) => {
                          const selected = dailyFocusTickers.includes(t);
                          return (
                            <button
                              key={t}
                              type="button"
                              onClick={() => {
                                setDailyFocusTickers(
                                  selected
                                    ? dailyFocusTickers.filter((x) => x !== t)
                                    : [...dailyFocusTickers, t],
                                );
                              }}
                              className={`px-2 py-0.5 rounded-full border text-[11px] transition-colors ${
                                selected
                                  ? 'bg-blue-500/20 border-blue-400 text-blue-100'
                                  : 'bg-gray-900 border-gray-700 text-gray-200 hover:border-blue-400 hover:text-blue-100'
                              }`}
                            >
                              {t}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => saveSchedule('daily_digest')}
                    disabled={dailySaving}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    {dailySaving ? 'Saving…' : 'Save daily schedule'}
                  </button>
                  {dailySaveMessage && (
                    <p className="mt-2 text-xs text-green-400">
                      {dailySaveMessage}
                    </p>
                  )}
                </div>

                {/* Weekly schedule */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Weekly brief</h3>
                      <p className="text-xs text-gray-400">
                        Get a recap brief for the past week on the selected weekday and time.
                      </p>
                    </div>
                    <label className="inline-flex items-center gap-2 cursor-pointer">
                      <span className="text-xs text-gray-400">Enabled</span>
                      <input
                        type="checkbox"
                        checked={weeklyEnabled}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setWeeklyEnabled(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
                      />
                    </label>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Weekday
                      </label>
                      <select
                        value={weeklyDayOfWeek}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => setWeeklyDayOfWeek(Number(e.target.value) || 0)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {weekDays.map((label, idx) => (
                          <option key={label} value={idx}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Time of day
                      </label>
                      <input
                        type="time"
                        value={weeklyTime}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setWeeklyTime(e.target.value)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Timezone
                      </label>
                      <input
                        type="text"
                        value={weeklyTimezone}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => setWeeklyTimezone(e.target.value)}
                        placeholder="e.g. Europe/Athens"
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Brief style
                      </label>
                      <select
                        value={weeklyNarrativeStyle}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => setWeeklyNarrativeStyle(e.target.value as DigestNarrativeStyle)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="default">Balanced (default)</option>
                        <option value="concise">Concise</option>
                        <option value="professional">Professional</option>
                        <option value="technical">Technical (more detail)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-300 mb-1">
                        Optional note
                      </label>
                      <textarea
                        value={weeklyUserNote}
                        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setWeeklyUserNote(e.target.value)}
                        maxLength={2000}
                        rows={3}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-xs text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                        placeholder="E.g. Weekly recap with focus on portfolio risk, macro narratives…"
                      />
                    </div>
                  </div>
                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-xs font-medium text-gray-300">
                        Focus tickers
                      </label>
                      {weeklyFocusTickers.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setWeeklyFocusTickers([])}
                          className="text-[11px] text-blue-300 hover:text-blue-200 underline-offset-2 hover:underline"
                        >
                          Clear
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-500 mb-1">
                      Optional subset of your subscribed tickers to emphasize in weekly briefs.
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {subscriptionTickers.length === 0 && (
                        <span className="text-[11px] text-gray-500">
                          Subscribe to tickers on the dashboard to pick focus tickers here.
                        </span>
                      )}
                      {subscriptionTickers.map((t) => {
                        const selected = weeklyFocusTickers.includes(t);
                        return (
                          <button
                            key={t}
                            type="button"
                            onClick={() => {
                              setWeeklyFocusTickers(
                                selected
                                  ? weeklyFocusTickers.filter((x) => x !== t)
                                  : [...weeklyFocusTickers, t],
                              );
                            }}
                            className={`px-2 py-0.5 rounded-full border text-[11px] transition-colors ${
                              selected
                                ? 'bg-blue-500/20 border-blue-400 text-blue-100'
                                : 'bg-gray-900 border-gray-700 text-gray-200 hover:border-blue-400 hover:text-blue-100'
                            }`}
                          >
                            {t}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => saveSchedule('weekly_digest')}
                    disabled={weeklySaving}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    {weeklySaving ? 'Saving…' : 'Save weekly schedule'}
                  </button>
                  {weeklySaveMessage && (
                    <p className="mt-2 text-xs text-green-400">
                      {weeklySaveMessage}
                    </p>
                  )}
                </div>
              </div>
            ) : null}
          </section>
        </>
      );
    }

    return null;
  };

  return (
    <div className="flex flex-col min-h-screen">
      <PageHeader
        title="Profile"
        icon={
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        }
      />
      <div className="flex-1 px-4 py-6 sm:p-6 lg:p-8">
        <div className="max-w-layout mx-auto min-w-0 w-full">
          {/* Tab Navigation */}
          <div className="flex gap-1 mb-8 border-b border-gray-700">
          <button
            onClick={() => {
              setActiveTab('overview');
              navigate('/profile#overview', { replace: true });
            }}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'overview'
                ? 'text-blue-400 border-blue-400'
                : 'text-gray-400 border-transparent hover:text-white hover:border-gray-600'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => {
              setActiveTab('api-keys');
              navigate('/profile#api-keys', { replace: true });
            }}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'api-keys'
                ? 'text-blue-400 border-blue-400'
                : 'text-gray-400 border-transparent hover:text-white hover:border-gray-600'
            }`}
          >
            API Keys
          </button>
          <button
            onClick={() => {
              setActiveTab('account');
              navigate('/profile#account', { replace: true });
            }}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'account'
                ? 'text-blue-400 border-blue-400'
                : 'text-gray-400 border-transparent hover:text-white hover:border-gray-600'
            }`}
          >
            Account
          </button>
          <button
            onClick={() => {
              setActiveTab('brief-schedule');
              navigate('/profile#brief-schedule', { replace: true });
            }}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'brief-schedule'
                ? 'text-blue-400 border-blue-400'
                : 'text-gray-400 border-transparent hover:text-white hover:border-gray-600'
            }`}
          >
            Brief schedule
          </button>
        </div>

          {/* Tab Content */}
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
}
