import type { ChangeEvent, ReactNode } from 'react';
import CustomSelect from '../CustomSelect';
import type { Subscription } from '../../services/subscriptionApi';
import {
  BRIEF_STYLE_OPTIONS,
  getTimezoneOptions,
  NARRATIVE_STYLE_LABELS,
  WEEKDAY_FULL_LABELS,
  WEEKDAY_SHORT_LABELS,
} from './profileConstants';
import {
  PROFILE_MUTED_PANEL_CLASS,
  PROFILE_PANEL_CLASS,
  PROFILE_PILL_CLASS,
  PROFILE_PRIMARY_BUTTON_CLASS,
  PROFILE_SECONDARY_BUTTON_CLASS,
  PROFILE_SELECT_CLASS,
  PROFILE_TEXTAREA_CLASS,
} from './profileStyles';
import type { DigestNarrativeStyle, ScheduleEditorType } from './profileTypes';

type BaseScheduleState = {
  enabled: boolean;
  time: string;
  narrativeStyle: DigestNarrativeStyle;
  userNote: string;
  focusTickers: string[];
  timezone: string;
  saveMessage: string | null;
  lastExecutedAt: string | null;
  saving: boolean;
};

type WeeklyScheduleState = BaseScheduleState & {
  dayOfWeek: number;
};

type ProfileBriefScheduleTabProps = {
  browserTimezone: string;
  subscriptions: Subscription[];
  schedulesLoading: boolean;
  schedulesError: string | null;
  scheduleEditor: ScheduleEditorType;
  daily: BaseScheduleState;
  weekly: WeeklyScheduleState;
  onOpenEditor: (which: Exclude<ScheduleEditorType, null>) => void;
  onCloseEditor: () => void;
  onSetDailyEnabled: (value: boolean) => void;
  onSetDailyTime: (value: string) => void;
  onSetDailyTimezone: (value: string) => void;
  onSetDailyNarrativeStyle: (value: DigestNarrativeStyle) => void;
  onSetDailyUserNote: (value: string) => void;
  onSetDailyFocusTickers: (value: string[]) => void;
  onSaveDaily: () => void;
  onSetWeeklyEnabled: (value: boolean) => void;
  onSetWeeklyDayOfWeek: (value: number) => void;
  onSetWeeklyTime: (value: string) => void;
  onSetWeeklyTimezone: (value: string) => void;
  onSetWeeklyNarrativeStyle: (value: DigestNarrativeStyle) => void;
  onSetWeeklyUserNote: (value: string) => void;
  onSetWeeklyFocusTickers: (value: string[]) => void;
  onSaveWeekly: () => void;
};

type ScheduleSummaryCardProps = {
  label: string;
  title: string;
  subtitle: string;
  enabled: boolean;
  accentClassName: string;
  buttonClassName: string;
  narrativeStyle: DigestNarrativeStyle;
  focusTickers: string[];
  userNote: string;
  lastExecutedAt: string | null;
  saveMessage: string | null;
  onConfigure: () => void;
};

type ScheduleEditorPanelProps = {
  title: string;
  description: string;
  enabled: boolean;
  saving: boolean;
  lastExecutedAt: string | null;
  note: string;
  focusTickers: string[];
  subscriptionTickers: string[];
  onEnabledChange: (value: boolean) => void;
  onNoteChange: (value: string) => void;
  onFocusTickersChange: (value: string[]) => void;
  onCancel: () => void;
  onSave: () => void;
  children: ReactNode;
};

function formatLastRun(iso: string | null) {
  if (!iso) return 'Never';
  try {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return 'Never';
    return date.toLocaleString();
  } catch {
    return 'Never';
  }
}

function toggleTickerInList(list: string[], ticker: string) {
  return list.includes(ticker)
    ? list.filter((value) => value !== ticker)
    : [...list, ticker];
}

function FocusTickerSelector({
  selectedTickers,
  subscriptionTickers,
  onChange,
}: {
  selectedTickers: string[];
  subscriptionTickers: string[];
  onChange: (nextTickers: string[]) => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label className="block text-xs font-medium text-slate-300">Focus tickers</label>
        {selectedTickers.length > 0 ? (
          <button
            type="button"
            onClick={() => onChange([])}
            className="text-[11px] text-cyan-300 transition-colors hover:text-cyan-200"
          >
            Clear selection
          </button>
        ) : null}
      </div>
      <p className="mb-3 text-[11px] text-slate-500">
        Optional. Leave empty to let FlowDeck choose automatically.
      </p>
      <div className="flex min-h-[96px] flex-wrap gap-2 rounded-xl border border-slate-700 bg-slate-900 p-3">
        {subscriptionTickers.length === 0 ? (
          <span className="text-xs text-slate-500">
            Subscribe to tickers from the dashboard to select them here.
          </span>
        ) : null}
        {subscriptionTickers.map((ticker) => {
          const selected = selectedTickers.includes(ticker);
          return (
            <button
              key={ticker}
              type="button"
              onClick={() => onChange(toggleTickerInList(selectedTickers, ticker))}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                selected
                  ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100'
                  : 'border-slate-600 bg-slate-950 text-slate-300 hover:border-slate-500 hover:text-white'
              }`}
            >
              {ticker}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ScheduleSummaryCard({
  label,
  title,
  subtitle,
  enabled,
  accentClassName,
  buttonClassName,
  narrativeStyle,
  focusTickers,
  userNote,
  lastExecutedAt,
  saveMessage,
  onConfigure,
}: ScheduleSummaryCardProps) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="relative flex h-full flex-col">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-slate-300">
              {label}
            </div>
            <p className="mt-4 text-3xl font-semibold tracking-tight text-white">{title}</p>
            <p className="mt-1 text-sm text-slate-300">{subtitle}</p>
          </div>
          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
            enabled
              ? 'border border-emerald-400/30 bg-emerald-400/15 text-emerald-200'
              : 'border border-slate-600/80 bg-slate-800/80 text-slate-400'
          }`}>
            {enabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
          <div className={`${PROFILE_MUTED_PANEL_CLASS} p-3`}>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Style</p>
            <p className="mt-1 text-white">{NARRATIVE_STYLE_LABELS[narrativeStyle]}</p>
          </div>
          <div className={`${PROFILE_MUTED_PANEL_CLASS} p-3`}>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Focus</p>
            <p className="mt-1 text-white">
              {focusTickers.length === 0 ? 'Auto' : `${focusTickers.length} ticker${focusTickers.length > 1 ? 's' : ''}`}
            </p>
          </div>
        </div>
        <div className={`${PROFILE_MUTED_PANEL_CLASS} mt-4 p-3`}>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Note</p>
          <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-slate-200">
            {userNote || 'No note added. FlowDeck will use your current subscriptions and default brief behavior.'}
          </p>
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Last run</p>
            <p className="mt-1 text-sm text-slate-200">{formatLastRun(lastExecutedAt)}</p>
          </div>
          <div className="flex items-center gap-3">
            {saveMessage ? <span className="text-xs text-emerald-300">{saveMessage}</span> : null}
            <button type="button" onClick={onConfigure} className={buttonClassName}>
              Configure
            </button>
          </div>
        </div>
        <div className={`pointer-events-none absolute inset-x-0 top-0 h-px opacity-80 ${accentClassName}`} />
      </div>
    </div>
  );
}

function ScheduleEditorPanel({
  title,
  description,
  enabled,
  saving,
  lastExecutedAt,
  note,
  focusTickers,
  subscriptionTickers,
  onEnabledChange,
  onNoteChange,
  onFocusTickersChange,
  onCancel,
  onSave,
  children,
}: ScheduleEditorPanelProps) {
  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 rounded-xl border border-slate-700 bg-slate-900 p-4">
        <div>
          <p className="text-sm font-medium text-white">{title}</p>
          <p className="mt-1 text-xs text-slate-400">{description}</p>
        </div>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onEnabledChange(event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-slate-950"
        />
      </div>

      {children}

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-300">Optional note</label>
        <textarea
          value={note}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onNoteChange(event.target.value)}
          maxLength={2000}
          rows={4}
          className={PROFILE_TEXTAREA_CLASS}
          placeholder="Emphasize earnings, macro catalysts, portfolio risk, or any other angle you want highlighted."
        />
      </div>

      <FocusTickerSelector
        selectedTickers={focusTickers}
        subscriptionTickers={subscriptionTickers}
        onChange={onFocusTickersChange}
      />

      <div className="flex items-center justify-between gap-3 border-t border-slate-800 pt-5">
        <p className="text-xs text-slate-500">Last run: {formatLastRun(lastExecutedAt)}</p>
        <div className="flex items-center gap-3">
          <button type="button" onClick={onCancel} className={PROFILE_SECONDARY_BUTTON_CLASS}>
            Cancel
          </button>
          <button type="button" onClick={onSave} disabled={saving} className={PROFILE_PRIMARY_BUTTON_CLASS}>
            {saving ? 'Saving...' : 'Save schedule'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProfileBriefScheduleTab({
  browserTimezone,
  subscriptions,
  schedulesLoading,
  schedulesError,
  scheduleEditor,
  daily,
  weekly,
  onOpenEditor,
  onCloseEditor,
  onSetDailyEnabled,
  onSetDailyTime,
  onSetDailyTimezone,
  onSetDailyNarrativeStyle,
  onSetDailyUserNote,
  onSetDailyFocusTickers,
  onSaveDaily,
  onSetWeeklyEnabled,
  onSetWeeklyDayOfWeek,
  onSetWeeklyTime,
  onSetWeeklyTimezone,
  onSetWeeklyNarrativeStyle,
  onSetWeeklyUserNote,
  onSetWeeklyFocusTickers,
  onSaveWeekly,
}: ProfileBriefScheduleTabProps) {
  const subscriptionTickers = subscriptions.map((subscription) => subscription.ticker);
  const scheduleModalTitle =
    scheduleEditor === 'daily' ? 'Configure daily brief' : 'Configure weekly brief';

  return (
    <>
      <section className={`${PROFILE_PANEL_CLASS} relative overflow-hidden p-6`}>
        <div className="relative mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <span className={`${PROFILE_PILL_CLASS} border-cyan-400/30 bg-cyan-400/10 text-cyan-100`}>
              Automated delivery
            </span>
            <h2 className="mt-4 text-xl font-semibold text-white">Brief schedule</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Configure when FlowDeck should generate and email your daily and
              weekly briefs. Each run uses your subscribed tickers, saved
              preferences, and your local timezone.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[320px]">
            <div className={`${PROFILE_MUTED_PANEL_CLASS} px-4 py-3`}>
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Timezone</p>
              <p className="mt-1 text-sm font-medium text-white">{browserTimezone}</p>
            </div>
            <div className={`${PROFILE_MUTED_PANEL_CLASS} px-4 py-3`}>
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Subscribed tickers</p>
              <p className="mt-1 text-sm font-medium text-white">{subscriptionTickers.length}</p>
            </div>
          </div>
        </div>

        {schedulesError ? <p className="mb-3 text-sm text-red-400">{schedulesError}</p> : null}

        {schedulesLoading ? (
          <p className="text-sm text-slate-400">Loading schedules...</p>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            <ScheduleSummaryCard
              label="Daily brief"
              title={daily.time}
              subtitle={`Every day in ${daily.timezone || browserTimezone}`}
              enabled={daily.enabled}
              accentClassName="bg-gradient-to-r from-cyan-400/80 via-transparent to-transparent"
              buttonClassName="inline-flex items-center rounded-xl border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-50 transition-colors hover:bg-cyan-400/20"
              narrativeStyle={daily.narrativeStyle}
              focusTickers={daily.focusTickers}
              userNote={daily.userNote}
              lastExecutedAt={daily.lastExecutedAt}
              saveMessage={daily.saveMessage}
              onConfigure={() => onOpenEditor('daily')}
            />
            <ScheduleSummaryCard
              label="Weekly brief"
              title={WEEKDAY_FULL_LABELS[weekly.dayOfWeek] ?? 'Monday'}
              subtitle={`${weekly.time} in ${weekly.timezone || browserTimezone}`}
              enabled={weekly.enabled}
              accentClassName="bg-gradient-to-r from-emerald-400/80 via-transparent to-transparent"
              buttonClassName="inline-flex items-center rounded-xl border border-emerald-300/30 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-50 transition-colors hover:bg-emerald-400/20"
              narrativeStyle={weekly.narrativeStyle}
              focusTickers={weekly.focusTickers}
              userNote={weekly.userNote}
              lastExecutedAt={weekly.lastExecutedAt}
              saveMessage={weekly.saveMessage}
              onConfigure={() => onOpenEditor('weekly')}
            />
          </div>
        )}
      </section>

      {scheduleEditor ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={onCloseEditor}
          role="dialog"
          aria-modal="true"
          aria-labelledby="schedule-editor-title"
        >
          <div
            className="w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-[0_30px_120px_rgba(2,6,23,0.8)]"
            onClick={(event) => event.stopPropagation()}
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
                onClick={onCloseEditor}
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
                <ScheduleEditorPanel
                  title="Enable daily brief"
                  description="Send a brief every day using this schedule."
                  enabled={daily.enabled}
                  saving={daily.saving}
                  lastExecutedAt={daily.lastExecutedAt}
                  note={daily.userNote}
                  focusTickers={daily.focusTickers}
                  subscriptionTickers={subscriptionTickers}
                  onEnabledChange={onSetDailyEnabled}
                  onNoteChange={onSetDailyUserNote}
                  onFocusTickersChange={onSetDailyFocusTickers}
                  onCancel={onCloseEditor}
                  onSave={onSaveDaily}
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-300">Time of day</label>
                      <input
                        type="time"
                        value={daily.time}
                        onChange={(event: ChangeEvent<HTMLInputElement>) => onSetDailyTime(event.target.value)}
                        className={PROFILE_SELECT_CLASS}
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-300">Timezone</label>
                      <CustomSelect
                        value={daily.timezone}
                        onChange={onSetDailyTimezone}
                        groupedOptions={getTimezoneOptions(browserTimezone)}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-300">Brief style</label>
                    <CustomSelect
                      value={daily.narrativeStyle}
                      onChange={(value) => onSetDailyNarrativeStyle(value as DigestNarrativeStyle)}
                      options={BRIEF_STYLE_OPTIONS}
                    />
                  </div>
                </ScheduleEditorPanel>
              ) : (
                <ScheduleEditorPanel
                  title="Enable weekly brief"
                  description="Send a recap once per week using this schedule."
                  enabled={weekly.enabled}
                  saving={weekly.saving}
                  lastExecutedAt={weekly.lastExecutedAt}
                  note={weekly.userNote}
                  focusTickers={weekly.focusTickers}
                  subscriptionTickers={subscriptionTickers}
                  onEnabledChange={onSetWeeklyEnabled}
                  onNoteChange={onSetWeeklyUserNote}
                  onFocusTickersChange={onSetWeeklyFocusTickers}
                  onCancel={onCloseEditor}
                  onSave={onSaveWeekly}
                >
                  <div className="grid gap-4 md:grid-cols-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-300">Weekday</label>
                      <select
                        value={weekly.dayOfWeek}
                        onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                          onSetWeeklyDayOfWeek(Number(event.target.value) || 0)
                        }
                        className={PROFILE_SELECT_CLASS}
                      >
                        {WEEKDAY_SHORT_LABELS.map((label, index) => (
                          <option key={label} value={index}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-300">Time of day</label>
                      <input
                        type="time"
                        value={weekly.time}
                        onChange={(event: ChangeEvent<HTMLInputElement>) => onSetWeeklyTime(event.target.value)}
                        className={PROFILE_SELECT_CLASS}
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-slate-300">Timezone</label>
                      <CustomSelect
                        value={weekly.timezone}
                        onChange={onSetWeeklyTimezone}
                        groupedOptions={getTimezoneOptions(browserTimezone)}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-300">Brief style</label>
                    <CustomSelect
                      value={weekly.narrativeStyle}
                      onChange={(value) => onSetWeeklyNarrativeStyle(value as DigestNarrativeStyle)}
                      options={BRIEF_STYLE_OPTIONS}
                    />
                  </div>
                </ScheduleEditorPanel>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
