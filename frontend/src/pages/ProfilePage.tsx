import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { profileApi, type MeProfile } from '../services/authApi';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import TokenPurchase from '../components/TokenPurchase';

const DELETE_CONFIRM_TEXT = 'DELETE';

export default function ProfilePage() {
  const { user, deleteAccount } = useAuth();
  const navigate = useNavigate();
  const { hash } = useLocation();
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

  // Scroll to hash anchor after profile data is loaded
  useEffect(() => {
    if (!loading && profile && hash) {
      const el = document.querySelector(hash);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }, [loading, profile, hash]);

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
    if (!deletePassword.trim()) {
      setDeleteError('Enter your password to confirm.');
      return;
    }
    setDeleteLoading(true);
    try {
      await deleteAccount(deletePassword);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setDeleteError(typeof msg === 'string' ? msg : 'Failed to delete account');
    } finally {
      setDeleteLoading(false);
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
      <div className="min-h-screen p-8">
        <div className="max-w-lg mx-auto text-gray-400">Loading profile…</div>
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

  return (
    <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
      <div className="max-w-layout mx-auto min-w-0 w-full">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to Flowdeck
        </Link>

        <h1 className="text-2xl font-bold text-white mb-8">Profile</h1>

        {/* Email (read-only) */}
        {profile && (
          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-2">Email</h2>
            <p className="text-gray-300">{profile.email}</p>
            <p className="text-xs text-gray-500 mt-1">Email cannot be changed here.</p>
          </section>
        )}

        {/* Token Balance */}
        {profile && (
          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-2">Token balance</h2>
            <p className="text-3xl font-bold text-white">{profile.token_balance.toLocaleString()} tokens</p>
            <p className="text-sm text-gray-400 mt-1">
              Creating a report costs 200 tokens. You earn tokens when others view your reports.
            </p>
          </section>
        )}

        {/* Purchase Tokens */}
        {profile && (
          <section id="purchase-tokens" className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
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
            <ul className="space-y-3">
              {subscriptions.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between gap-4 py-2 border-b border-gray-700/50 last:border-0"
                >
                  <Link
                    to={`/stocks/${s.ticker}`}
                    className="text-blue-400 hover:text-blue-300 font-medium shrink-0"
                  >
                    {s.ticker}
                  </Link>
                  <label className="flex items-center gap-2 cursor-pointer shrink-0">
                    <span className="text-sm text-gray-400">Email updates</span>
                    <input
                      type="checkbox"
                      checked={s.email_updates}
                      disabled={togglingTicker === s.ticker}
                      onChange={(e) => handleEmailUpdatesToggle(s.ticker, e.target.checked)}
                      className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
                    />
                  </label>
                </li>
              ))}
            </ul>
          )}
        </section>

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

        {/* Password */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
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

        {/* Delete account */}
        <section className="bg-gray-800 border border-red-900/50 rounded-xl p-6 mt-8">
          <h2 className="text-lg font-semibold text-red-400 mb-2">Delete account</h2>
          <p className="text-sm text-gray-400 mb-4">
            This will permanently delete your account and all associated data (subscriptions, etc.). This cannot be undone.
          </p>
          <form onSubmit={handleDeleteAccount} className="space-y-4">
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
              disabled={deleteLoading || deleteConfirmText !== DELETE_CONFIRM_TEXT || !deletePassword.trim()}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            >
              {deleteLoading ? 'Deleting…' : 'Delete my account'}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
