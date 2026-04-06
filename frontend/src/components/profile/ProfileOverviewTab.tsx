import { Link } from 'react-router-dom';
import type { MeProfile } from '../../services/authApi';
import type { Subscription } from '../../services/subscriptionApi';
import TokenPurchase from '../TokenPurchase';
import UserStatsSection from '../UserStatsSection';
import {
  PROFILE_MUTED_PANEL_CLASS,
  PROFILE_PANEL_CLASS,
  PROFILE_PILL_CLASS,
} from './profileStyles';

type ProfileOverviewTabProps = {
  profile: MeProfile | null;
  subscriptions: Subscription[];
  subscriptionsLoading: boolean;
  togglingTicker: string | null;
  onToggleEmailUpdates: (ticker: string, emailUpdates: boolean) => void;
  onOpenInvestorProfile: () => void;
};

export default function ProfileOverviewTab({
  profile,
  subscriptions,
  subscriptionsLoading,
  togglingTicker,
  onToggleEmailUpdates,
  onOpenInvestorProfile,
}: ProfileOverviewTabProps) {
  return (
    <div className="space-y-6">
      {profile && !profile.has_completed_investor_profile && (
        <section className={`${PROFILE_PANEL_CLASS} border-amber-400/25 bg-amber-500/10 p-6`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <span className={`${PROFILE_PILL_CLASS} border-amber-300/30 bg-amber-300/10 text-amber-100`}>
                Personalization
              </span>
              <h2 className="mt-4 text-xl font-semibold text-amber-50">
                Complete your investor profile
              </h2>
              <p className="mt-2 text-sm leading-6 text-amber-50/80">
                Save your investing style, goals, risk tolerance, and private AI
                memory so chat and briefs can personalize recommendations around
                your profile.
              </p>
            </div>
            <button
              type="button"
              onClick={onOpenInvestorProfile}
              className="rounded-xl bg-amber-300 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-amber-200"
            >
              Set up profile
            </button>
          </div>
        </section>
      )}

      {profile && (
        <section className={`${PROFILE_PANEL_CLASS} p-6`}>
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <span className={`${PROFILE_PILL_CLASS} border-cyan-400/30 bg-cyan-400/10 text-cyan-100`}>
                Tokens
              </span>
              <h2 className="mt-4 text-xl font-semibold text-white">Token balance</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Ticker analysis and AI assistant usage cost tokens. You also earn
                tokens when others view your shared reports.
              </p>
            </div>
            <div className={`${PROFILE_MUTED_PANEL_CLASS} px-5 py-4 lg:min-w-[260px]`}>
              <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                Available now
              </p>
              <p className="mt-3 text-4xl font-semibold text-white">
                {profile.token_balance.toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-slate-400">DECK tokens</p>
            </div>
          </div>
        </section>
      )}

      <UserStatsSection />

      <section className={`${PROFILE_PANEL_CLASS} p-6`}>
        <div className="max-w-3xl">
          <span className={`${PROFILE_PILL_CLASS} border-emerald-400/30 bg-emerald-400/10 text-emerald-100`}>
            Top up
          </span>
          <h2 className="mt-4 text-xl font-semibold text-white">Purchase tokens</h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Choose a package below to add tokens to your account with PayPal.
          </p>
        </div>
        <div className="mt-6">
          <TokenPurchase />
        </div>
      </section>

      <section className={`${PROFILE_PANEL_CLASS} p-6`}>
        <div className="max-w-3xl">
          <span className={`${PROFILE_PILL_CLASS} border-blue-400/30 bg-blue-400/10 text-blue-100`}>
            Notifications
          </span>
          <h2 className="mt-4 text-xl font-semibold text-white">
            Subscription email preferences
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Choose whether FlowDeck should email you when a new analysis report is
            ready for each subscribed ticker.
          </p>
        </div>

        <div className="mt-6">
          {subscriptionsLoading ? (
            <p className="text-sm text-slate-400">Loading subscriptions...</p>
          ) : subscriptions.length === 0 ? (
            <div className={`${PROFILE_MUTED_PANEL_CLASS} px-4 py-5 text-sm text-slate-400`}>
              You have no subscriptions yet. Subscribe from a stock page or the
              dashboard to manage alert delivery here.
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {subscriptions.map((subscription) => (
                <div
                  key={subscription.id}
                  className={`${PROFILE_MUTED_PANEL_CLASS} flex items-center justify-between gap-4 px-4 py-3`}
                >
                  <div>
                    <Link
                      to={`/tickers/${subscription.ticker}`}
                      className="text-sm font-semibold text-cyan-300 transition-colors hover:text-cyan-200"
                    >
                      {subscription.ticker}
                    </Link>
                    <p className="mt-1 text-xs text-slate-500">
                      Report-ready email alerts
                    </p>
                  </div>
                  <label className="flex shrink-0 items-center gap-2 text-sm text-slate-400">
                    <span>Email</span>
                    <input
                      type="checkbox"
                      checked={subscription.email_updates}
                      disabled={togglingTicker === subscription.ticker}
                      onChange={(event) =>
                        onToggleEmailUpdates(subscription.ticker, event.target.checked)
                      }
                      className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-950"
                    />
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
