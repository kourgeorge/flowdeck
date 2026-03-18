import { useState, useEffect, useCallback } from 'react';
import type { ChangeEvent } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { profileApi, type InvestorProfile, type MeProfile } from '../services/authApi';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import PageHeader from '../components/PageHeader';
import TokenPurchase from '../components/TokenPurchase';
import UserStatsSection from '../components/UserStatsSection';
import ApiKeyManagement from '../components/ApiKeyManagement';
import { digestScheduleApi, type DigestSchedule, type DigestScheduleType } from '../services/api';

const DELETE_CONFIRM_TEXT = 'DELETE';

type TabType = 'overview' | 'investor-profile' | 'api-keys' | 'account' | 'brief-schedule';

type DigestNarrativeStyle = 'default' | 'concise' | 'professional' | 'technical';
type ScheduleEditorType = 'daily' | 'weekly' | null;
type InvestorSelectFieldKey =
  | 'persona_type'
  | 'experience_level'
  | 'risk_tolerance'
  | 'time_horizon'
  | 'primary_goal'
  | null;
type InvestorProfileFormState = {
  date_of_birth: string;
  persona_type: string;
  experience_level: string;
  risk_tolerance: string;
  time_horizon: string;
  primary_goal: string;
  goals: string[];
  constraints: string[];
  preferred_style: string;
  ai_memory_text: string;
};
type InvestorSelectOption = {
  value: string;
  label: string;
  description: string;
};

const WEEKDAY_SHORT_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WEEKDAY_FULL_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const NARRATIVE_STYLE_LABELS: Record<DigestNarrativeStyle, string> = {
  default: 'Balanced',
  concise: 'Concise',
  professional: 'Professional',
  technical: 'Technical',
};
const INVESTOR_GOAL_OPTIONS = [
  { value: 'dividend_income', label: 'Dividend income' },
  { value: 'long_term_compounding', label: 'Long-term compounding' },
  { value: 'capital_growth', label: 'Capital growth' },
  { value: 'retirement_planning', label: 'Retirement planning' },
  { value: 'swing_trades', label: 'Swing trades' },
  { value: 'short_term_opportunities', label: 'Short-term opportunities' },
  { value: 'hedging', label: 'Hedging' },
  { value: 'learning', label: 'Learning' },
] as const;
const INVESTOR_CONSTRAINT_OPTIONS = [
  { value: 'avoid_high_drawdowns', label: 'Avoid high drawdowns' },
  { value: 'avoid_options', label: 'Avoid options' },
  { value: 'avoid_leverage', label: 'Avoid leverage' },
  { value: 'prefer_large_caps', label: 'Prefer large caps' },
  { value: 'prefer_profitable_companies', label: 'Prefer profitable companies' },
  { value: 'income_focus', label: 'Income focus' },
  { value: 'esg_focus', label: 'ESG focus' },
  { value: 'tax_sensitive', label: 'Tax sensitive' },
] as const;
const INVESTOR_FIELD_CARD_CLASS =
  'rounded-2xl border border-slate-700 bg-slate-900 p-4';
const PERSONA_OPTIONS: InvestorSelectOption[] = [
  { value: 'investor', label: 'Investor', description: 'Prioritize thesis durability, valuation, and longer-term compounding.' },
  { value: 'trader', label: 'Trader', description: 'Lean into timing, catalysts, levels, and near-term setups.' },
  { value: 'both', label: 'Both', description: 'Blend investment framing with tactical trading awareness.' },
];
const EXPERIENCE_OPTIONS: InvestorSelectOption[] = [
  { value: 'beginner', label: 'Beginner', description: 'Use simpler framing and explain the core tradeoffs clearly.' },
  { value: 'intermediate', label: 'Intermediate', description: 'Assume some market fluency but still keep context explicit.' },
  { value: 'advanced', label: 'Advanced', description: 'Use tighter shorthand and focus on nuance over basics.' },
  { value: 'professional', label: 'Professional', description: 'Favor concise, high-signal language and institutional framing.' },
];
const RISK_OPTIONS: InvestorSelectOption[] = [
  { value: 'conservative', label: 'Conservative', description: 'Emphasize capital protection, downside risk, and steadier setups.' },
  { value: 'moderate', label: 'Moderate', description: 'Balance upside potential with drawdown control and flexibility.' },
  { value: 'aggressive', label: 'Aggressive', description: 'Accept more volatility in exchange for higher potential upside.' },
];
const HORIZON_OPTIONS: InvestorSelectOption[] = [
  { value: 'intraday', label: 'Intraday', description: 'Focus on same-day movement, price action, and immediate catalysts.' },
  { value: 'swing', label: 'Swing', description: 'Center on moves that can develop over days to a few weeks.' },
  { value: 'medium_term', label: 'Medium term', description: 'Weigh catalysts and thesis development over weeks to months.' },
  { value: 'long_term', label: 'Long term', description: 'Stress multi-quarter durability, compounding, and thesis quality.' },
];
const PRIMARY_GOAL_OPTIONS: InvestorSelectOption[] = [
  { value: 'wealth_building', label: 'Wealth building', description: 'Bias toward durable upside and long-run portfolio growth.' },
  { value: 'active_trading', label: 'Active trading', description: 'Optimize for tactical opportunities and active decision-making.' },
  { value: 'retirement', label: 'Retirement', description: 'Favor resilience, discipline, and lower-regret portfolio choices.' },
  { value: 'income', label: 'Income', description: 'Highlight yield, cash generation, and income-friendly tradeoffs.' },
  { value: 'capital_preservation', label: 'Capital preservation', description: 'Put downside control and balance-sheet safety first.' },
  { value: 'learning', label: 'Learning', description: 'Explain reasoning clearly so the brief teaches while it guides.' },
];

function getDefaultInvestorProfileForm(): InvestorProfileFormState {
  return {
    date_of_birth: '',
    persona_type: '',
    experience_level: '',
    risk_tolerance: '',
    time_horizon: '',
    primary_goal: '',
    goals: [],
    constraints: [],
    preferred_style: '',
    ai_memory_text: '',
  };
}

function buildInvestorProfileForm(profile: InvestorProfile | null): InvestorProfileFormState {
  if (!profile) return getDefaultInvestorProfileForm();
  return {
    date_of_birth: profile.date_of_birth ?? '',
    persona_type: profile.persona_type ?? '',
    experience_level: profile.experience_level ?? '',
    risk_tolerance: profile.risk_tolerance ?? '',
    time_horizon: profile.time_horizon ?? '',
    primary_goal: profile.primary_goal ?? '',
    goals: profile.goals ?? [],
    constraints: profile.constraints ?? [],
    preferred_style: profile.preferred_style ?? '',
    ai_memory_text: profile.ai_memory_text ?? '',
  };
}

function InvestorProfileSelect({
  fieldKey,
  label,
  helper,
  placeholder,
  value,
  options,
  isOpen,
  onToggle,
  onSelect,
}: {
  fieldKey: Exclude<InvestorSelectFieldKey, null>;
  label: string;
  helper: string;
  placeholder: string;
  value: string;
  options: InvestorSelectOption[];
  isOpen: boolean;
  onToggle: (fieldKey: Exclude<InvestorSelectFieldKey, null>) => void;
  onSelect: (value: string) => void;
}) {
  const selected = options.find((option) => option.value === value) ?? null;

  return (
    <div className={INVESTOR_FIELD_CARD_CLASS} data-investor-select-root="true">
      <label className="mb-1 block text-sm font-semibold text-slate-100">{label}</label>
      <p className="mb-3 text-xs leading-5 text-slate-400">{helper}</p>
      <div className="relative">
        <button
          type="button"
          onClick={() => onToggle(fieldKey)}
          className={`w-full rounded-xl border px-4 py-3 text-left transition-all ${
            isOpen
              ? 'border-slate-500 bg-slate-950 ring-2 ring-slate-600/50'
              : 'border-slate-600 bg-slate-800 hover:border-slate-500'
          }`}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
        >
          <div className="pr-8">
            <p className={`text-sm font-medium ${selected ? 'text-white' : 'text-slate-400'}`}>
              {selected ? selected.label : placeholder}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              {selected ? selected.description : 'Open the list to choose the best fit.'}
            </p>
          </div>
          <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition-transform ${isOpen ? 'rotate-180 text-slate-200' : ''}`}>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </button>

        {isOpen && (
          <div className="absolute left-0 right-0 top-[calc(100%+0.6rem)] z-30 overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-xl">
            <div className="border-b border-slate-800 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
                Select {label.toLowerCase()}
              </p>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {options.map((option) => {
                const selectedOption = option.value === value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onSelect(option.value)}
                    className={`flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors ${
                      selectedOption
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-200 hover:bg-slate-900'
                    }`}
                    role="option"
                    aria-selected={selectedOption}
                  >
                    <span className={`mt-1 h-2.5 w-2.5 rounded-full ${selectedOption ? 'bg-slate-200' : 'bg-slate-600'}`} />
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold">{option.label}</span>
                      <span className={`mt-1 block text-xs leading-5 ${selectedOption ? 'text-slate-300' : 'text-slate-400'}`}>
                        {option.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const { user, deleteAccount, setProfileCompletion } = useAuth();
  const navigate = useNavigate();
  const { hash } = useLocation();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [investorProfile, setInvestorProfile] = useState<InvestorProfile | null>(null);
  const [investorProfileForm, setInvestorProfileForm] = useState<InvestorProfileFormState>(
    getDefaultInvestorProfileForm(),
  );
  const [investorProfileLoading, setInvestorProfileLoading] = useState(false);
  const [investorProfileSaving, setInvestorProfileSaving] = useState(false);
  const [investorProfileMessage, setInvestorProfileMessage] = useState<string | null>(null);
  const [activeInvestorDropdown, setActiveInvestorDropdown] = useState<InvestorSelectFieldKey>(null);
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
  const [scheduleEditor, setScheduleEditor] = useState<ScheduleEditorType>(null);

  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

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

  const loadInvestorProfile = useCallback(async () => {
    if (!user) return;
    setInvestorProfileLoading(true);
    try {
      const data = await profileApi.getInvestorProfile();
      setInvestorProfile(data);
      setInvestorProfileForm(buildInvestorProfileForm(data));
      setInvestorProfileMessage(null);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setInvestorProfileMessage(typeof msg === 'string' ? msg : 'Failed to load investor profile');
      setInvestorProfile(null);
      setInvestorProfileForm(getDefaultInvestorProfileForm());
    } finally {
      setInvestorProfileLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadInvestorProfile();
  }, [loadInvestorProfile]);

  useEffect(() => {
    if (!activeInvestorDropdown) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-investor-select-root="true"]')) {
        return;
      }
      setActiveInvestorDropdown(null);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveInvestorDropdown(null);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [activeInvestorDropdown]);

  const loadSchedules = useCallback(async () => {
    if (!user) return;
    setSchedulesLoading(true);
    setSchedulesError(null);
    try {
      const data = await digestScheduleApi.getSchedules();
      if (data.daily) {
        applyScheduleToState(data.daily, 'daily');
      } else {
        setDailyTimezone(browserTimezone);
      }

      if (data.weekly) {
        applyScheduleToState(data.weekly, 'weekly');
      } else {
        setWeeklyTimezone(browserTimezone);
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
  }, [browserTimezone, user]);

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
    if (hash === '#investor-profile') {
      setActiveTab('investor-profile');
    } else if (hash === '#api-keys') {
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
    if (!scheduleEditor) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setScheduleEditor(null);
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [scheduleEditor]);

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

  const toggleInvestorProfileListValue = (
    field: 'goals' | 'constraints',
    value: string,
  ) => {
    setInvestorProfileForm((prev) => {
      const list = prev[field];
      const nextList = list.includes(value)
        ? list.filter((item) => item !== value)
        : [...list, value];
      return { ...prev, [field]: nextList };
    });
  };

  const toggleInvestorDropdown = (field: Exclude<InvestorSelectFieldKey, null>) => {
    setActiveInvestorDropdown((prev) => (prev === field ? null : field));
  };

  const handleInvestorSelectValue = (
    field: Exclude<InvestorSelectFieldKey, null>,
    value: string,
  ) => {
    setInvestorProfileForm((prev) => ({ ...prev, [field]: value }));
    setActiveInvestorDropdown(null);
  };

  const handleSaveInvestorProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setInvestorProfileSaving(true);
    setInvestorProfileMessage(null);
    try {
      const data = await profileApi.updateInvestorProfile({
        date_of_birth: investorProfileForm.date_of_birth || null,
        persona_type: investorProfileForm.persona_type || null,
        experience_level: investorProfileForm.experience_level || null,
        risk_tolerance: investorProfileForm.risk_tolerance || null,
        time_horizon: investorProfileForm.time_horizon || null,
        primary_goal: investorProfileForm.primary_goal || null,
        goals: investorProfileForm.goals,
        constraints: investorProfileForm.constraints,
        preferred_style: investorProfileForm.preferred_style || null,
        ai_memory_text: investorProfileForm.ai_memory_text.trim() || null,
      });
      setInvestorProfile(data);
      setInvestorProfileForm(buildInvestorProfileForm(data));
      setProfile((prev) => (prev ? { ...prev, has_completed_investor_profile: data.has_completed_investor_profile } : prev));
      setProfileCompletion(data.has_completed_investor_profile);
      setInvestorProfileMessage('Investor profile saved.');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setInvestorProfileMessage(typeof msg === 'string' ? msg : 'Failed to save investor profile');
    } finally {
      setInvestorProfileSaving(false);
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
    setSchedulesError(null);

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
      setScheduleEditor(null);
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
          {profile && !profile.has_completed_investor_profile && (
            <section className="bg-amber-500/10 border border-amber-400/30 rounded-xl p-6 mb-6">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-amber-100 mb-2">Complete your investor profile</h2>
                  <p className="text-sm text-amber-50/80 max-w-2xl">
                    Save your investing style, goals, risk tolerance, and private AI memory so chat and briefs can personalize recommendations around your profile.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab('investor-profile');
                    navigate('/profile#investor-profile', { replace: true });
                  }}
                  className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-slate-950 rounded-lg text-sm font-semibold transition-colors"
                >
                  Set up profile
                </button>
              </div>
            </section>
          )}

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

    if (activeTab === 'investor-profile') {
      const summaryItems = [
        investorProfileForm.persona_type || 'Persona not set',
        investorProfileForm.risk_tolerance || 'Risk not set',
        investorProfileForm.time_horizon || 'Horizon not set',
        investorProfileForm.primary_goal || 'Goal not set',
      ];

      return (
        <>
          <section className="bg-slate-900 border border-slate-700 rounded-2xl p-6 mb-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-3xl">
                <span className="inline-flex items-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-100">
                  AI personalization
                </span>
                <h2 className="mt-4 text-xl font-semibold text-white">Investor profile and memory</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  This profile is private. FlowDeck uses it to personalize chat and automated briefs around your investing style, goals, and constraints.
                </p>
              </div>
              <div className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${investorProfile?.has_completed_investor_profile ? 'border border-emerald-400/30 bg-emerald-400/15 text-emerald-200' : 'border border-amber-400/30 bg-amber-400/15 text-amber-100'}`}>
                {investorProfile?.has_completed_investor_profile ? 'Profile complete' : 'Profile incomplete'}
              </div>
            </div>
            {investorProfile?.has_completed_investor_profile === false && (
              <div className="mt-5 rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                Fill this out to get a more tailored experience in chat and automated briefs. You can skip it for now, but personalization will be weaker until it is saved.
              </div>
            )}
            <div className="mt-5 grid gap-3 md:grid-cols-4">
              {summaryItems.map((item, idx) => (
                <div key={`${item}-${idx}`} className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </section>

          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
            {investorProfileLoading ? (
              <p className="text-sm text-gray-400">Loading investor profile…</p>
            ) : (
              <form onSubmit={handleSaveInvestorProfile} className="space-y-6">
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <InvestorProfileSelect
                    fieldKey="persona_type"
                    label="Investor type"
                    helper="Choose the lens FlowDeck should use when weighing tradeoffs."
                    placeholder="Select investor type"
                    value={investorProfileForm.persona_type}
                    options={PERSONA_OPTIONS}
                    isOpen={activeInvestorDropdown === 'persona_type'}
                    onToggle={toggleInvestorDropdown}
                    onSelect={(value) => handleInvestorSelectValue('persona_type', value)}
                  />
                  <InvestorProfileSelect
                    fieldKey="experience_level"
                    label="Experience level"
                    helper="Controls how much context versus shorthand the brief should assume."
                    placeholder="Select experience level"
                    value={investorProfileForm.experience_level}
                    options={EXPERIENCE_OPTIONS}
                    isOpen={activeInvestorDropdown === 'experience_level'}
                    onToggle={toggleInvestorDropdown}
                    onSelect={(value) => handleInvestorSelectValue('experience_level', value)}
                  />
                  <InvestorProfileSelect
                    fieldKey="risk_tolerance"
                    label="Risk tolerance"
                    helper="Shapes how strongly FlowDeck emphasizes downside control versus upside capture."
                    placeholder="Select risk tolerance"
                    value={investorProfileForm.risk_tolerance}
                    options={RISK_OPTIONS}
                    isOpen={activeInvestorDropdown === 'risk_tolerance'}
                    onToggle={toggleInvestorDropdown}
                    onSelect={(value) => handleInvestorSelectValue('risk_tolerance', value)}
                  />
                  <InvestorProfileSelect
                    fieldKey="time_horizon"
                    label="Time horizon"
                    helper="Helps the brief decide whether to focus on immediate catalysts or longer arcs."
                    placeholder="Select time horizon"
                    value={investorProfileForm.time_horizon}
                    options={HORIZON_OPTIONS}
                    isOpen={activeInvestorDropdown === 'time_horizon'}
                    onToggle={toggleInvestorDropdown}
                    onSelect={(value) => handleInvestorSelectValue('time_horizon', value)}
                  />
                  <InvestorProfileSelect
                    fieldKey="primary_goal"
                    label="Primary goal"
                    helper="Tells the AI what outcome matters most when the answer is not obvious."
                    placeholder="Select primary goal"
                    value={investorProfileForm.primary_goal}
                    options={PRIMARY_GOAL_OPTIONS}
                    isOpen={activeInvestorDropdown === 'primary_goal'}
                    onToggle={toggleInvestorDropdown}
                    onSelect={(value) => handleInvestorSelectValue('primary_goal', value)}
                  />
                  <div className={INVESTOR_FIELD_CARD_CLASS}>
                    <label className="block text-sm font-medium text-gray-300 mb-1">Date of birth</label>
                    <p className="mb-3 text-xs leading-5 text-slate-400">Optional personal context stored in your private profile.</p>
                    <input
                      type="date"
                      value={investorProfileForm.date_of_birth}
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setInvestorProfileForm((prev) => ({ ...prev, date_of_birth: e.target.value }))}
                      className="w-full rounded-xl border border-slate-600/80 bg-[linear-gradient(180deg,rgba(30,41,59,0.96),rgba(15,23,42,0.98))] px-4 py-3 text-sm font-medium text-white transition-all focus:border-cyan-400/70 focus:outline-none focus:ring-4 focus:ring-cyan-400/10"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Goals</label>
                  <div className="flex flex-wrap gap-2">
                    {INVESTOR_GOAL_OPTIONS.map((option) => {
                      const selected = investorProfileForm.goals.includes(option.value);
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => toggleInvestorProfileListValue('goals', option.value)}
                          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                            selected
                              ? 'border-blue-400 bg-blue-500/20 text-blue-100'
                              : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-gray-500 hover:text-white'
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Constraints and preferences</label>
                  <div className="flex flex-wrap gap-2">
                    {INVESTOR_CONSTRAINT_OPTIONS.map((option) => {
                      const selected = investorProfileForm.constraints.includes(option.value);
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => toggleInvestorProfileListValue('constraints', option.value)}
                          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                            selected
                              ? 'border-emerald-400 bg-emerald-500/20 text-emerald-100'
                              : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-gray-500 hover:text-white'
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">Private AI memory</label>
                    <textarea
                      value={investorProfileForm.ai_memory_text}
                      onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setInvestorProfileForm((prev) => ({ ...prev, ai_memory_text: e.target.value.slice(0, 4000) }))}
                      rows={8}
                      maxLength={4000}
                      className="w-full resize-none rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Examples: I care more about downside protection than maximum upside. Avoid suggesting leverage. Remind me to check valuation before chasing momentum. My long-term accounts should stay diversified."
                    />
                    <div className="mt-2 flex items-center justify-between gap-3">
                      <p className="text-xs text-gray-500">
                        Editable private memory used by FlowDeck chat and scheduled briefs.
                      </p>
                      <span className="text-xs text-gray-500">
                        {investorProfileForm.ai_memory_text.length}/4000
                      </span>
                    </div>
                  </div>

                  <div className="rounded-xl border border-gray-700 bg-gray-900/70 p-4">
                    <h3 className="text-sm font-semibold text-white">Response style</h3>
                    <p className="mt-1 text-xs leading-5 text-gray-400">
                      This hints how you want FlowDeck to explain ideas when there is room to adapt tone.
                    </p>
                    <div className="mt-4 space-y-2">
                      {[
                        ['balanced', 'Balanced'],
                        ['concise', 'Concise'],
                        ['professional', 'Professional'],
                        ['technical', 'Technical'],
                      ].map(([value, label]) => (
                        <label
                          key={value}
                          className={`flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors ${
                            investorProfileForm.preferred_style === value
                              ? 'border-cyan-400/50 bg-cyan-500/10 text-cyan-50'
                              : 'border-gray-700 bg-gray-800 text-gray-200 hover:border-gray-600'
                          }`}
                        >
                          <span>{label}</span>
                          <input
                            type="radio"
                            name="preferred_style"
                            value={value}
                            checked={investorProfileForm.preferred_style === value}
                            onChange={(e: ChangeEvent<HTMLInputElement>) => setInvestorProfileForm((prev) => ({ ...prev, preferred_style: e.target.value }))}
                            className="h-4 w-4 border-gray-500 bg-gray-900 text-cyan-500 focus:ring-cyan-500"
                          />
                        </label>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={() => setInvestorProfileForm((prev) => ({ ...prev, preferred_style: '' }))}
                      className="mt-3 text-xs text-blue-300 hover:text-blue-200"
                    >
                      Clear style preference
                    </button>
                  </div>
                </div>

                {investorProfileMessage && (
                  <p className={`text-sm ${investorProfileMessage.startsWith('Investor profile saved') ? 'text-green-400' : 'text-red-400'}`}>
                    {investorProfileMessage}
                  </p>
                )}

                <div className="flex items-center justify-between gap-3 border-t border-gray-700 pt-5">
                  <p className="text-xs text-gray-500">
                    {investorProfile?.updated_at ? `Last updated ${new Date(investorProfile.updated_at).toLocaleString()}` : 'Not saved yet'}
                  </p>
                  <button
                    type="submit"
                    disabled={investorProfileSaving}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-default disabled:opacity-50"
                  >
                    {investorProfileSaving ? 'Saving…' : 'Save investor profile'}
                  </button>
                </div>
              </form>
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
      const openScheduleEditor = (which: Exclude<ScheduleEditorType, null>) => {
        setSchedulesError(null);
        setScheduleEditor(which);
      };
      const scheduleModalTitle =
        scheduleEditor === 'daily' ? 'Configure daily brief' : 'Configure weekly brief';

      return (
        <>
          <section className="relative overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-900 p-6 mb-6 shadow-[0_24px_80px_rgba(2,6,23,0.35)]">
            <div className="relative flex flex-col gap-4 mb-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <span className="inline-flex items-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-100">
                  Automated delivery
                </span>
                <h2 className="mt-4 text-xl font-semibold text-white">Brief schedule</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Configure when FlowDeck should generate and email your daily and weekly briefs. Each run uses your subscribed tickers, saved preferences, and your local timezone.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:w-auto sm:min-w-[320px]">
                <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Timezone</p>
                  <p className="mt-1 text-sm font-medium text-white">{browserTimezone}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Subscribed tickers</p>
                  <p className="mt-1 text-sm font-medium text-white">{subscriptionTickers.length}</p>
                </div>
              </div>
            </div>
            {schedulesError && (
              <p className="mb-3 text-sm text-red-400">{schedulesError}</p>
            )}
            {schedulesLoading ? (
              <p className="text-sm text-gray-400">Loading schedules…</p>
            ) : (
              <div className="grid gap-4 xl:grid-cols-2">
                <div className="group relative overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                  <div className="relative flex h-full flex-col">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-slate-300">
                          Daily brief
                        </div>
                        <p className="mt-4 text-3xl font-semibold tracking-tight text-white">
                          {dailyTime}
                        </p>
                        <p className="mt-1 text-sm text-slate-300">
                          Every day in {dailyTimezone || browserTimezone}
                        </p>
                      </div>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${dailyEnabled ? 'border border-emerald-400/30 bg-emerald-400/15 text-emerald-200' : 'border border-slate-600/80 bg-slate-800/80 text-slate-400'}`}>
                        {dailyEnabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Style</p>
                        <p className="mt-1 text-white">{NARRATIVE_STYLE_LABELS[dailyNarrativeStyle]}</p>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Focus</p>
                        <p className="mt-1 text-white">
                          {dailyFocusTickers.length === 0 ? 'Auto' : `${dailyFocusTickers.length} ticker${dailyFocusTickers.length > 1 ? 's' : ''}`}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
                      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Note</p>
                      <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-slate-200">
                        {dailyUserNote || 'No note added. FlowDeck will use your current subscriptions and default brief behavior.'}
                      </p>
                    </div>
                    <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-4">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Last run</p>
                        <p className="mt-1 text-sm text-slate-200">{formatLastRun(dailyLastExecutedAt)}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        {dailySaveMessage && (
                          <span className="text-xs text-emerald-300">{dailySaveMessage}</span>
                        )}
                        <button
                          type="button"
                          onClick={() => openScheduleEditor('daily')}
                          className="inline-flex items-center rounded-xl border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-50 transition-colors hover:bg-cyan-400/20"
                        >
                          Configure
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="group relative overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                  <div className="relative flex h-full flex-col">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-slate-300">
                          Weekly brief
                        </div>
                        <p className="mt-4 text-3xl font-semibold tracking-tight text-white">
                          {WEEKDAY_FULL_LABELS[weeklyDayOfWeek] ?? 'Monday'}
                        </p>
                        <p className="mt-1 text-sm text-slate-300">
                          {weeklyTime} in {weeklyTimezone || browserTimezone}
                        </p>
                      </div>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${weeklyEnabled ? 'border border-emerald-400/30 bg-emerald-400/15 text-emerald-200' : 'border border-slate-600/80 bg-slate-800/80 text-slate-400'}`}>
                        {weeklyEnabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Style</p>
                        <p className="mt-1 text-white">{NARRATIVE_STYLE_LABELS[weeklyNarrativeStyle]}</p>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Focus</p>
                        <p className="mt-1 text-white">
                          {weeklyFocusTickers.length === 0 ? 'Auto' : `${weeklyFocusTickers.length} ticker${weeklyFocusTickers.length > 1 ? 's' : ''}`}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
                      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Note</p>
                      <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-slate-200">
                        {weeklyUserNote || 'No note added. FlowDeck will generate a weekly recap using your saved subscriptions.'}
                      </p>
                    </div>
                    <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-4">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Last run</p>
                        <p className="mt-1 text-sm text-slate-200">{formatLastRun(weeklyLastExecutedAt)}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        {weeklySaveMessage && (
                          <span className="text-xs text-emerald-300">{weeklySaveMessage}</span>
                        )}
                        <button
                          type="button"
                          onClick={() => openScheduleEditor('weekly')}
                          className="inline-flex items-center rounded-xl border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-50 transition-colors hover:bg-emerald-400/20"
                        >
                          Configure
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>

          {scheduleEditor && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
              onClick={() => setScheduleEditor(null)}
              role="dialog"
              aria-modal="true"
              aria-labelledby="schedule-editor-title"
            >
              <div
                className="w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-[0_30px_120px_rgba(2,6,23,0.8)]"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-start justify-between gap-6 border-b border-slate-800 bg-slate-950 px-6 py-5">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
                      Brief schedule
                    </p>
                    <h3 id="schedule-editor-title" className="mt-2 text-xl font-semibold text-white">
                      {scheduleModalTitle}
                    </h3>
                    <p className="mt-2 text-sm text-slate-300">
                      {scheduleEditor === 'daily'
                        ? 'Choose when your daily market brief should be generated and which preferences should shape it.'
                        : 'Choose when your weekly recap should be sent and how FlowDeck should frame the summary.'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setScheduleEditor(null)}
                    className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                    aria-label="Close schedule editor"
                  >
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="max-h-[80vh] overflow-y-auto px-6 py-6">
                  {scheduleEditor === 'daily' ? (
                    <div className="space-y-5">
                      <div className="flex items-start justify-between gap-4 rounded-lg border border-gray-700 bg-gray-800 p-4">
                        <div>
                          <p className="text-sm font-medium text-white">Enable daily brief</p>
                          <p className="mt-1 text-xs text-gray-400">
                            Send a brief every day using this schedule.
                          </p>
                        </div>
                        <input
                          type="checkbox"
                          checked={dailyEnabled}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => setDailyEnabled(e.target.checked)}
                          className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900"
                        />
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <label className="mb-1 block text-xs font-medium text-gray-300">Time of day</label>
                          <input
                            type="time"
                            value={dailyTime}
                            onChange={(e: ChangeEvent<HTMLInputElement>) => setDailyTime(e.target.value)}
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-gray-300">Timezone</label>
                          <input
                            type="text"
                            value={dailyTimezone}
                            onChange={(e: ChangeEvent<HTMLInputElement>) => setDailyTimezone(e.target.value)}
                            placeholder="e.g. America/New_York"
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <p className="mt-1 text-[11px] text-gray-500">
                            Uses IANA timezone names. Leave blank to use {browserTimezone}.
                          </p>
                        </div>
                      </div>

                      <div>
                        <label className="mb-1 block text-xs font-medium text-gray-300">Brief style</label>
                        <select
                          value={dailyNarrativeStyle}
                          onChange={(e: ChangeEvent<HTMLSelectElement>) => setDailyNarrativeStyle(e.target.value as DigestNarrativeStyle)}
                          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="default">Balanced (default)</option>
                          <option value="concise">Concise</option>
                          <option value="professional">Professional</option>
                          <option value="technical">Technical (more detail)</option>
                        </select>
                      </div>

                      <div>
                        <label className="mb-1 block text-xs font-medium text-gray-300">Optional note</label>
                        <textarea
                          value={dailyUserNote}
                          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setDailyUserNote(e.target.value)}
                          maxLength={2000}
                          rows={4}
                          className="w-full resize-none rounded-lg border border-gray-700 bg-gray-800 px-3 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="Emphasize earnings, near-term portfolio risk, macro catalysts, or anything else you want highlighted."
                        />
                      </div>

                      <div>
                        <div className="mb-2 flex items-center justify-between">
                          <label className="block text-xs font-medium text-gray-300">Focus tickers</label>
                          {dailyFocusTickers.length > 0 && (
                            <button
                              type="button"
                              onClick={() => setDailyFocusTickers([])}
                              className="text-[11px] text-blue-300 transition-colors hover:text-blue-200"
                            >
                              Clear selection
                            </button>
                          )}
                        </div>
                        <p className="mb-3 text-[11px] text-gray-500">
                          Optional. Leave empty to let FlowDeck choose automatically.
                        </p>
                        <div className="flex min-h-[96px] flex-wrap gap-2 rounded-lg border border-gray-700 bg-gray-800 p-3">
                          {subscriptionTickers.length === 0 && (
                            <span className="text-xs text-gray-500">
                              Subscribe to tickers from the dashboard to select them here.
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
                                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                                  selected
                                    ? 'border-blue-400 bg-blue-500/20 text-blue-100'
                                    : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-gray-500 hover:text-white'
                                }`}
                              >
                                {t}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-3 border-t border-gray-700 pt-5">
                        <p className="text-xs text-gray-500">Last run: {formatLastRun(dailyLastExecutedAt)}</p>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() => setScheduleEditor(null)}
                            className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-800"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => saveSchedule('daily_digest')}
                            disabled={dailySaving}
                            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-default disabled:opacity-50"
                          >
                            {dailySaving ? 'Saving…' : 'Save daily schedule'}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <div className="flex items-start justify-between gap-4 rounded-lg border border-gray-700 bg-gray-800 p-4">
                        <div>
                          <p className="text-sm font-medium text-white">Enable weekly brief</p>
                          <p className="mt-1 text-xs text-gray-400">
                            Send a recap once per week using this schedule.
                          </p>
                        </div>
                        <input
                          type="checkbox"
                          checked={weeklyEnabled}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => setWeeklyEnabled(e.target.checked)}
                          className="mt-0.5 h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900"
                        />
                      </div>

                      <div className="grid gap-4 md:grid-cols-3">
                        <div>
                          <label className="mb-1 block text-xs font-medium text-gray-300">Weekday</label>
                          <select
                            value={weeklyDayOfWeek}
                            onChange={(e: ChangeEvent<HTMLSelectElement>) => setWeeklyDayOfWeek(Number(e.target.value) || 0)}
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            {WEEKDAY_SHORT_LABELS.map((label, idx) => (
                              <option key={label} value={idx}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-gray-300">Time of day</label>
                          <input
                            type="time"
                            value={weeklyTime}
                            onChange={(e: ChangeEvent<HTMLInputElement>) => setWeeklyTime(e.target.value)}
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-xs font-medium text-gray-300">Timezone</label>
                          <input
                            type="text"
                            value={weeklyTimezone}
                            onChange={(e: ChangeEvent<HTMLInputElement>) => setWeeklyTimezone(e.target.value)}
                            placeholder="e.g. America/New_York"
                            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <p className="mt-1 text-[11px] text-gray-500">
                            Uses IANA timezone names. Leave blank to use {browserTimezone}.
                          </p>
                        </div>
                      </div>

                      <div>
                        <label className="mb-1 block text-xs font-medium text-gray-300">Brief style</label>
                        <select
                          value={weeklyNarrativeStyle}
                          onChange={(e: ChangeEvent<HTMLSelectElement>) => setWeeklyNarrativeStyle(e.target.value as DigestNarrativeStyle)}
                          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="default">Balanced (default)</option>
                          <option value="concise">Concise</option>
                          <option value="professional">Professional</option>
                          <option value="technical">Technical (more detail)</option>
                        </select>
                      </div>

                      <div>
                        <label className="mb-1 block text-xs font-medium text-gray-300">Optional note</label>
                        <textarea
                          value={weeklyUserNote}
                          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setWeeklyUserNote(e.target.value)}
                          maxLength={2000}
                          rows={4}
                          className="w-full resize-none rounded-lg border border-gray-700 bg-gray-800 px-3 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="Ask for a portfolio recap, macro narrative, risk review, or any other weekly emphasis."
                        />
                      </div>

                      <div>
                        <div className="mb-2 flex items-center justify-between">
                          <label className="block text-xs font-medium text-gray-300">Focus tickers</label>
                          {weeklyFocusTickers.length > 0 && (
                            <button
                              type="button"
                              onClick={() => setWeeklyFocusTickers([])}
                              className="text-[11px] text-blue-300 transition-colors hover:text-blue-200"
                            >
                              Clear selection
                            </button>
                          )}
                        </div>
                        <p className="mb-3 text-[11px] text-gray-500">
                          Optional. Leave empty to let FlowDeck choose automatically.
                        </p>
                        <div className="flex min-h-[96px] flex-wrap gap-2 rounded-lg border border-gray-700 bg-gray-800 p-3">
                          {subscriptionTickers.length === 0 && (
                            <span className="text-xs text-gray-500">
                              Subscribe to tickers from the dashboard to select them here.
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
                                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                                  selected
                                    ? 'border-blue-400 bg-blue-500/20 text-blue-100'
                                    : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-gray-500 hover:text-white'
                                }`}
                              >
                                {t}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-3 border-t border-gray-700 pt-5">
                        <p className="text-xs text-gray-500">Last run: {formatLastRun(weeklyLastExecutedAt)}</p>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() => setScheduleEditor(null)}
                            className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-800"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => saveSchedule('weekly_digest')}
                            disabled={weeklySaving}
                            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-default disabled:opacity-50"
                          >
                            {weeklySaving ? 'Saving…' : 'Save weekly schedule'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
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
              setActiveTab('investor-profile');
              navigate('/profile#investor-profile', { replace: true });
            }}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === 'investor-profile'
                ? 'text-blue-400 border-blue-400'
                : 'text-gray-400 border-transparent hover:text-white hover:border-gray-600'
            }`}
          >
            Investor profile
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
