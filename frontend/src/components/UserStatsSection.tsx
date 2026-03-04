import { useEffect, useState } from 'react';
import { profileApi, type UserStats } from '../services/authApi';

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  highlight?: boolean;
}

function StatCard({ icon, label, value, sub, highlight }: StatCardProps) {
  return (
    <div
      className={`flex flex-col gap-0.5 rounded-lg px-3 py-2 border ${
        highlight
          ? 'bg-blue-900/30 border-blue-700/50'
          : 'bg-gray-700/40 border-gray-600/50'
      }`}
    >
      <div className="flex items-center gap-1.5 text-gray-400 text-xs font-medium uppercase tracking-wide">
        <span className="w-4 h-4 flex items-center justify-center">{icon}</span>
        {label}
      </div>
      <div className={`text-lg font-bold leading-tight ${highlight ? 'text-blue-300' : 'text-white'}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {sub && <div className="text-xs text-gray-500 leading-tight">{sub}</div>}
    </div>
  );
}

function formatDate(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function UserStatsSection() {
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    profileApi
      .getStats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Usage Statistics</h2>
        <p className="text-gray-400 text-sm">Loading stats…</p>
      </section>
    );
  }

  if (error || !stats) {
    return null; // Silently hide if stats fail to load
  }

  return (
    <section className="bg-gray-800 border border-gray-700 rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-1">Usage Statistics</h2>
      {stats.member_since && (
        <p className="text-xs text-gray-500 mb-3">
          Member since {formatDate(stats.member_since)}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        <StatCard
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
          }
          label="Analyses Created"
          value={stats.analyses_created}
          sub={`${stats.unique_tickers_analyzed} unique ticker${stats.unique_tickers_analyzed !== 1 ? 's' : ''}`}
        />
        <StatCard
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          }
          label="Reports Viewed"
          value={stats.reports_viewed}
        />
        <StatCard
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
          }
          label="Subscribed Stocks"
          value={stats.subscriptions_count}
        />
        <StatCard
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
          label="Tokens Spent"
          value={stats.tokens_spent_on_analyses}
          sub="on analyses (200 each)"
        />
        <StatCard
          icon={
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          label="Tokens Earned"
          value={stats.tokens_earned_from_views}
          sub="from report views"
          highlight={stats.tokens_earned_from_views > 0}
        />
      </div>
    </section>
  );
}

// Made with Bob
