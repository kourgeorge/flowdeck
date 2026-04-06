import { useState, useEffect, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { profileApi, type InvestorProfile, type MeProfile } from '../services/authApi';
import { subscriptionApi, type Subscription } from '../services/subscriptionApi';
import { digestScheduleApi, type DigestSchedule, type DigestScheduleType } from '../services/api';
import { tokenApi, type UsageHistoryResponse } from '../services/tokenApi';
import PageHeader from '../components/PageHeader';
import ProfileAccountTab from '../components/profile/ProfileAccountTab';
import ProfileApiKeysTab from '../components/profile/ProfileApiKeysTab';
import ProfileBriefScheduleTab from '../components/profile/ProfileBriefScheduleTab';
import ProfileInvestorProfileTab from '../components/profile/ProfileInvestorProfileTab';
import ProfileOverviewTab from '../components/profile/ProfileOverviewTab';
import ProfileTabNavigation from '../components/profile/ProfileTabNavigation';
import ProfileUsageTab from '../components/profile/ProfileUsageTab';
import {
  type DigestNarrativeStyle,
  type InvestorProfileFormState,
  type InvestorSelectFieldKey,
  type ProfileTabType,
  type ScheduleEditorType,
} from '../components/profile/profileTypes';

const DELETE_CONFIRM_TEXT = 'DELETE';

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

export default function ProfilePage() {
  const { user, deleteAccount, setProfileCompletion } = useAuth();
  const navigate = useNavigate();
  const { hash } = useLocation();

  const [activeTab, setActiveTab] = useState<ProfileTabType>('overview');
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [investorProfile, setInvestorProfile] = useState<InvestorProfile | null>(null);
  const [investorProfileForm, setInvestorProfileForm] = useState<InvestorProfileFormState>(
    getDefaultInvestorProfileForm(),
  );
  const [investorProfileLoading, setInvestorProfileLoading] = useState(false);
  const [investorProfileSaving, setInvestorProfileSaving] = useState(false);
  const [investorProfileMessage, setInvestorProfileMessage] = useState<string | null>(null);
  const [activeInvestorDropdown, setActiveInvestorDropdown] = useState<InvestorSelectFieldKey>(null);
  const [usagePeriodDays, setUsagePeriodDays] = useState<number>(90);
  const [usageHistory, setUsageHistory] = useState<UsageHistoryResponse | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const [nameMessage, setNameMessage] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);

  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
  const [togglingTicker, setTogglingTicker] = useState<string | null>(null);

  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [schedulesError, setSchedulesError] = useState<string | null>(null);

  const [dailyEnabled, setDailyEnabled] = useState(false);
  const [dailyTime, setDailyTime] = useState('08:00');
  const [dailyNarrativeStyle, setDailyNarrativeStyle] = useState<DigestNarrativeStyle>('default');
  const [dailyUserNote, setDailyUserNote] = useState('');
  const [dailyFocusTickers, setDailyFocusTickers] = useState<string[]>([]);
  const [dailyTimezone, setDailyTimezone] = useState('');
  const [dailySaving, setDailySaving] = useState(false);
  const [dailySaveMessage, setDailySaveMessage] = useState<string | null>(null);
  const [dailyLastExecutedAt, setDailyLastExecutedAt] = useState<string | null>(null);

  const [weeklyEnabled, setWeeklyEnabled] = useState(false);
  const [weeklyTime, setWeeklyTime] = useState('08:00');
  const [weeklyDayOfWeek, setWeeklyDayOfWeek] = useState(0);
  const [weeklyNarrativeStyle, setWeeklyNarrativeStyle] = useState<DigestNarrativeStyle>('default');
  const [weeklyUserNote, setWeeklyUserNote] = useState('');
  const [weeklyFocusTickers, setWeeklyFocusTickers] = useState<string[]>([]);
  const [weeklyTimezone, setWeeklyTimezone] = useState('');
  const [weeklySaving, setWeeklySaving] = useState(false);
  const [weeklySaveMessage, setWeeklySaveMessage] = useState<string | null>(null);
  const [weeklyLastExecutedAt, setWeeklyLastExecutedAt] = useState<string | null>(null);
  const [scheduleEditor, setScheduleEditor] = useState<ScheduleEditorType>(null);

  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  const handleTabChange = useCallback((tab: ProfileTabType) => {
    setActiveTab(tab);
    navigate(`/profile#${tab}`, { replace: true });
  }, [navigate]);

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

  const loadInvestorProfile = useCallback(async () => {
    if (!user) return;
    setInvestorProfileLoading(true);
    try {
      const data = await profileApi.getInvestorProfile();
      setInvestorProfile(data);
      setInvestorProfileForm(buildInvestorProfileForm(data));
      setInvestorProfileMessage(null);
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setInvestorProfileMessage(typeof message === 'string' ? message : 'Failed to load investor profile');
      setInvestorProfile(null);
      setInvestorProfileForm(getDefaultInvestorProfileForm());
    } finally {
      setInvestorProfileLoading(false);
    }
  }, [user]);

  const loadUsageHistory = useCallback(async () => {
    if (!user) return;
    setUsageLoading(true);
    setUsageError(null);
    try {
      const data = await tokenApi.getUsageHistory(usagePeriodDays, 200);
      setUsageHistory(data);
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setUsageError(typeof message === 'string' ? message : 'Failed to load usage history');
      setUsageHistory(null);
    } finally {
      setUsageLoading(false);
    }
  }, [usagePeriodDays, user]);

  const applyScheduleToState = useCallback((schedule: DigestSchedule, which: 'daily' | 'weekly') => {
    const hour = String(schedule.hour).padStart(2, '0');
    const minute = String(schedule.minute).padStart(2, '0');
    const timezone = schedule.timezone || '';
    const metadata = schedule.metadata || {};
    const narrativeStyle =
      (metadata.narrative_style as DigestNarrativeStyle | null) ?? 'default';
    const userNote = metadata.user_note ?? '';
    const focusTickers = metadata.user_focus_tickers ?? [];

    if (which === 'daily') {
      setDailyEnabled(schedule.enabled);
      setDailyTime(`${hour}:${minute}`);
      setDailyTimezone(timezone);
      setDailyNarrativeStyle(narrativeStyle);
      setDailyUserNote(userNote);
      setDailyFocusTickers(focusTickers);
      setDailyLastExecutedAt(schedule.last_executed_at ?? null);
      return;
    }

    setWeeklyEnabled(schedule.enabled);
    setWeeklyTime(`${hour}:${minute}`);
    setWeeklyTimezone(timezone);
    setWeeklyNarrativeStyle(narrativeStyle);
    setWeeklyUserNote(userNote);
    setWeeklyFocusTickers(focusTickers);
    if (typeof schedule.day_of_week === 'number') {
      setWeeklyDayOfWeek(schedule.day_of_week);
    }
    setWeeklyLastExecutedAt(schedule.last_executed_at ?? null);
  }, []);

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
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSchedulesError(typeof message === 'string' ? message : 'Failed to load brief schedules');
    } finally {
      setSchedulesLoading(false);
    }
  }, [applyScheduleToState, browserTimezone, user]);

  useEffect(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

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

  useEffect(() => {
    switch (hash) {
      case '#usage':
        setActiveTab('usage');
        break;
      case '#investor-profile':
        setActiveTab('investor-profile');
        break;
      case '#api-keys':
        setActiveTab('api-keys');
        break;
      case '#account':
        setActiveTab('account');
        break;
      case '#brief-schedule':
        setActiveTab('brief-schedule');
        break;
      case '#overview':
      default:
        setActiveTab('overview');
        break;
    }
  }, [hash]);

  useEffect(() => {
    if (activeTab === 'brief-schedule') {
      loadSchedules();
    }
    if (activeTab === 'usage') {
      loadUsageHistory();
    }
  }, [activeTab, loadSchedules, loadUsageHistory]);

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

  const handleEmailUpdatesToggle = async (ticker: string, emailUpdates: boolean) => {
    setTogglingTicker(ticker);
    try {
      const updated = await subscriptionApi.updateEmailPreference(ticker, emailUpdates);
      setSubscriptions((prev) =>
        prev.map((subscription) =>
          subscription.ticker === updated.ticker ? updated : subscription,
        ),
      );
    } finally {
      setTogglingTicker(null);
    }
  };

  const handleSaveName = async (event: React.FormEvent) => {
    event.preventDefault();
    setNameMessage(null);
    setNameSaving(true);
    try {
      const data = await profileApi.updateProfile({ name: name.trim() || null });
      setProfile(data);
      setNameMessage('Name updated.');
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setNameMessage(typeof message === 'string' ? message : 'Failed to update name');
    } finally {
      setNameSaving(false);
    }
  };

  const handleChangePassword = async (event: React.FormEvent) => {
    event.preventDefault();
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
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPasswordMessage(typeof message === 'string' ? message : 'Failed to update password');
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleDeleteAccount = async (event: React.FormEvent) => {
    event.preventDefault();
    setDeleteError(null);

    if (deleteConfirmText !== DELETE_CONFIRM_TEXT) {
      setDeleteError(`Type ${DELETE_CONFIRM_TEXT} to confirm.`);
      return;
    }

    if (profile?.has_password && !deletePassword.trim()) {
      setDeleteError('Enter your password to confirm.');
      return;
    }

    setDeleteLoading(true);
    try {
      await deleteAccount(profile?.has_password ? deletePassword : undefined);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setDeleteError(typeof message === 'string' ? message : 'Failed to delete account');
    } finally {
      setDeleteLoading(false);
    }
  };

  const toggleInvestorProfileListValue = (field: 'goals' | 'constraints', value: string) => {
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

  const handleSaveInvestorProfile = async (event: React.FormEvent) => {
    event.preventDefault();
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
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              has_completed_investor_profile: data.has_completed_investor_profile,
            }
          : prev,
      );
      setProfileCompletion(data.has_completed_investor_profile);
      setInvestorProfileMessage('✓ Investor profile saved successfully!');
      window.setTimeout(() => setInvestorProfileMessage(null), 3000);
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setInvestorProfileMessage(typeof message === 'string' ? message : 'Failed to save investor profile');
    } finally {
      setInvestorProfileSaving(false);
    }
  };

  const parseTime = (value: string): { hour: number; minute: number } => {
    const [hourPart, minutePart] = value.split(':');
    const hour = Math.min(23, Math.max(0, Number(hourPart) || 0));
    const minute = Math.min(59, Math.max(0, Number(minutePart) || 0));
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
        window.setTimeout(() => setDailySaveMessage(null), 3000);
      } else {
        setWeeklySaveMessage('Weekly brief schedule saved.');
        window.setTimeout(() => setWeeklySaveMessage(null), 3000);
      }
      setScheduleEditor(null);
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSchedulesError(typeof message === 'string' ? message : 'Failed to save brief schedule');
    } finally {
      if (isDaily) {
        setDailySaving(false);
      } else {
        setWeeklySaving(false);
      }
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <ProfileOverviewTab
            profile={profile}
            subscriptions={subscriptions}
            subscriptionsLoading={subscriptionsLoading}
            togglingTicker={togglingTicker}
            onToggleEmailUpdates={handleEmailUpdatesToggle}
            onOpenInvestorProfile={() => handleTabChange('investor-profile')}
          />
        );
      case 'usage':
        return (
          <ProfileUsageTab
            usagePeriodDays={usagePeriodDays}
            usageHistory={usageHistory}
            usageLoading={usageLoading}
            usageError={usageError}
            onSelectPeriod={setUsagePeriodDays}
          />
        );
      case 'investor-profile':
        return (
          <ProfileInvestorProfileTab
            investorProfile={investorProfile}
            investorProfileForm={investorProfileForm}
            investorProfileLoading={investorProfileLoading}
            investorProfileSaving={investorProfileSaving}
            investorProfileMessage={investorProfileMessage}
            activeInvestorDropdown={activeInvestorDropdown}
            onInvestorProfileFormChange={setInvestorProfileForm}
            onToggleListValue={toggleInvestorProfileListValue}
            onToggleDropdown={toggleInvestorDropdown}
            onSelectValue={handleInvestorSelectValue}
            onSave={handleSaveInvestorProfile}
          />
        );
      case 'api-keys':
        return <ProfileApiKeysTab />;
      case 'account':
        return (
          <ProfileAccountTab
            profile={profile}
            name={name}
            nameSaving={nameSaving}
            nameMessage={nameMessage}
            currentPassword={currentPassword}
            newPassword={newPassword}
            confirmPassword={confirmPassword}
            passwordSaving={passwordSaving}
            passwordMessage={passwordMessage}
            deletePassword={deletePassword}
            deleteConfirmText={deleteConfirmText}
            deleteLoading={deleteLoading}
            deleteError={deleteError}
            deleteConfirmLabel={DELETE_CONFIRM_TEXT}
            onNameChange={setName}
            onCurrentPasswordChange={setCurrentPassword}
            onNewPasswordChange={setNewPassword}
            onConfirmPasswordChange={setConfirmPassword}
            onDeletePasswordChange={setDeletePassword}
            onDeleteConfirmTextChange={setDeleteConfirmText}
            onSaveName={handleSaveName}
            onChangePassword={handleChangePassword}
            onDeleteAccount={handleDeleteAccount}
          />
        );
      case 'brief-schedule':
        return (
          <ProfileBriefScheduleTab
            browserTimezone={browserTimezone}
            subscriptions={subscriptions}
            schedulesLoading={schedulesLoading}
            schedulesError={schedulesError}
            scheduleEditor={scheduleEditor}
            daily={{
              enabled: dailyEnabled,
              time: dailyTime,
              narrativeStyle: dailyNarrativeStyle,
              userNote: dailyUserNote,
              focusTickers: dailyFocusTickers,
              timezone: dailyTimezone,
              saveMessage: dailySaveMessage,
              lastExecutedAt: dailyLastExecutedAt,
              saving: dailySaving,
            }}
            weekly={{
              enabled: weeklyEnabled,
              time: weeklyTime,
              dayOfWeek: weeklyDayOfWeek,
              narrativeStyle: weeklyNarrativeStyle,
              userNote: weeklyUserNote,
              focusTickers: weeklyFocusTickers,
              timezone: weeklyTimezone,
              saveMessage: weeklySaveMessage,
              lastExecutedAt: weeklyLastExecutedAt,
              saving: weeklySaving,
            }}
            onOpenEditor={(which) => {
              setSchedulesError(null);
              setScheduleEditor(which);
            }}
            onCloseEditor={() => setScheduleEditor(null)}
            onSetDailyEnabled={setDailyEnabled}
            onSetDailyTime={setDailyTime}
            onSetDailyTimezone={setDailyTimezone}
            onSetDailyNarrativeStyle={setDailyNarrativeStyle}
            onSetDailyUserNote={setDailyUserNote}
            onSetDailyFocusTickers={setDailyFocusTickers}
            onSaveDaily={() => saveSchedule('daily_digest')}
            onSetWeeklyEnabled={setWeeklyEnabled}
            onSetWeeklyDayOfWeek={setWeeklyDayOfWeek}
            onSetWeeklyTime={setWeeklyTime}
            onSetWeeklyTimezone={setWeeklyTimezone}
            onSetWeeklyNarrativeStyle={setWeeklyNarrativeStyle}
            onSetWeeklyUserNote={setWeeklyUserNote}
            onSetWeeklyFocusTickers={setWeeklyFocusTickers}
            onSaveWeekly={() => saveSchedule('weekly_digest')}
          />
        );
      default:
        return null;
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen p-8">
        <div className="mx-auto max-w-lg text-center text-gray-400">
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
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <svg className="mx-auto mb-3 h-8 w-8 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-sm text-gray-400">Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="min-h-screen p-8">
        <div className="mx-auto max-w-lg text-center text-gray-400">
          <p className="mb-4">{error}</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300">
            Go to home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <PageHeader
        title="Profile"
        icon={(
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        )}
      />

      <div className="flex-1 px-4 py-6 sm:p-6 lg:p-8">
        <div className="mx-auto min-w-0 w-full max-w-layout">
          <ProfileTabNavigation activeTab={activeTab} onTabChange={handleTabChange} />
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
}
