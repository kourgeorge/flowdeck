import { useEffect, useState } from 'react';
import { profileApi, type UserStats } from '../services/authApi';

interface StatCardProps {
  icon: string;
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
        <span className="text-sm">{icon}</span>
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
          icon="🔬"
          label="Analyses Created"
          value={stats.analyses_created}
          sub={`${stats.unique_tickers_analyzed} unique ticker${stats.unique_tickers_analyzed !== 1 ? 's' : ''}`}
        />
        <StatCard
          icon="👁"
          label="Reports Viewed"
          value={stats.reports_viewed}
        />
        <StatCard
          icon="📬"
          label="Subscribed Stocks"
          value={stats.subscriptions_count}
        />
        <StatCard
          icon="💸"
          label="Tokens Spent"
          value={stats.tokens_spent_on_analyses}
          sub="on analyses (200 each)"
        />
        <StatCard
          icon="💰"
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
