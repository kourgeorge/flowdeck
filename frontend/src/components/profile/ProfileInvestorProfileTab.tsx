import type { ChangeEvent, Dispatch, FormEvent, SetStateAction } from 'react';
import type { InvestorProfile } from '../../services/authApi';
import {
  EXPERIENCE_OPTIONS,
  HORIZON_OPTIONS,
  INVESTOR_CONSTRAINT_OPTIONS,
  INVESTOR_GOAL_OPTIONS,
  INVESTOR_RESPONSE_STYLE_OPTIONS,
  PERSONA_OPTIONS,
  PRIMARY_GOAL_OPTIONS,
  RISK_OPTIONS,
} from './profileConstants';
import {
  PROFILE_INPUT_CLASS,
  PROFILE_MUTED_PANEL_CLASS,
  PROFILE_PANEL_CLASS,
  PROFILE_PILL_CLASS,
  PROFILE_PRIMARY_BUTTON_CLASS,
  PROFILE_TEXTAREA_CLASS,
} from './profileStyles';
import type {
  InvestorProfileFormState,
  InvestorSelectFieldKey,
  InvestorSelectOption,
} from './profileTypes';

const INVESTOR_FIELD_CARD_CLASS =
  'rounded-2xl border border-slate-700 bg-slate-950/80 p-4';

type ProfileInvestorProfileTabProps = {
  investorProfile: InvestorProfile | null;
  investorProfileForm: InvestorProfileFormState;
  investorProfileLoading: boolean;
  investorProfileSaving: boolean;
  investorProfileMessage: string | null;
  activeInvestorDropdown: InvestorSelectFieldKey;
  onInvestorProfileFormChange: Dispatch<SetStateAction<InvestorProfileFormState>>;
  onToggleListValue: (field: 'goals' | 'constraints', value: string) => void;
  onToggleDropdown: (field: Exclude<InvestorSelectFieldKey, null>) => void;
  onSelectValue: (
    field: Exclude<InvestorSelectFieldKey, null>,
    value: string,
  ) => void;
  onSave: (event: FormEvent) => void;
};

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
              : 'border-slate-600 bg-slate-900 hover:border-slate-500'
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

        {isOpen ? (
          <div className="absolute left-0 right-0 top-[calc(100%+0.6rem)] z-30 overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-xl">
            <div className="border-b border-slate-800 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
                Select {label.toLowerCase()}
              </p>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              {options.map((option) => {
                const isSelected = option.value === value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onSelect(option.value)}
                    className={`flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors ${
                      isSelected ? 'bg-slate-800 text-white' : 'text-slate-200 hover:bg-slate-900'
                    }`}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <span className={`mt-1 h-2.5 w-2.5 rounded-full ${isSelected ? 'bg-slate-200' : 'bg-slate-600'}`} />
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold">{option.label}</span>
                      <span className={`mt-1 block text-xs leading-5 ${isSelected ? 'text-slate-300' : 'text-slate-400'}`}>
                        {option.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function ProfileInvestorProfileTab({
  investorProfile,
  investorProfileForm,
  investorProfileLoading,
  investorProfileSaving,
  investorProfileMessage,
  activeInvestorDropdown,
  onInvestorProfileFormChange,
  onToggleListValue,
  onToggleDropdown,
  onSelectValue,
  onSave,
}: ProfileInvestorProfileTabProps) {
  const summaryItems = [
    investorProfileForm.persona_type || 'Persona not set',
    investorProfileForm.risk_tolerance || 'Risk not set',
    investorProfileForm.time_horizon || 'Horizon not set',
    investorProfileForm.primary_goal || 'Goal not set',
  ];

  return (
    <div className="space-y-6">
      <section className={`${PROFILE_PANEL_CLASS} p-6`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <span className={`${PROFILE_PILL_CLASS} border-cyan-400/30 bg-cyan-400/10 text-cyan-100`}>
              Personalization
            </span>
            <h2 className="mt-4 text-xl font-semibold text-white">Investor profile and memory</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              This profile is private. FlowDeck uses it to personalize chat and
              automated briefs around your investing style, goals, and constraints.
            </p>
          </div>
          <div className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
            investorProfile?.has_completed_investor_profile
              ? 'border border-emerald-400/30 bg-emerald-400/15 text-emerald-200'
              : 'border border-amber-400/30 bg-amber-400/15 text-amber-100'
          }`}>
            {investorProfile?.has_completed_investor_profile ? 'Profile complete' : 'Profile incomplete'}
          </div>
        </div>

        {investorProfile?.has_completed_investor_profile === false ? (
          <div className="mt-5 rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Fill this out to get a more tailored experience in chat and automated
            briefs. You can skip it for now, but personalization will be weaker
            until it is saved.
          </div>
        ) : null}

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {summaryItems.map((item, index) => (
            <div key={`${item}-${index}`} className={`${PROFILE_MUTED_PANEL_CLASS} px-4 py-3 text-sm text-slate-200`}>
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className={`${PROFILE_PANEL_CLASS} p-6`}>
        {investorProfileLoading ? (
          <p className="text-sm text-slate-400">Loading investor profile...</p>
        ) : (
          <form onSubmit={onSave} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <InvestorProfileSelect
                fieldKey="persona_type"
                label="Investor type"
                helper="Choose the lens FlowDeck should use when weighing tradeoffs."
                placeholder="Select investor type"
                value={investorProfileForm.persona_type}
                options={PERSONA_OPTIONS}
                isOpen={activeInvestorDropdown === 'persona_type'}
                onToggle={onToggleDropdown}
                onSelect={(value) => onSelectValue('persona_type', value)}
              />
              <InvestorProfileSelect
                fieldKey="experience_level"
                label="Experience level"
                helper="Controls how much context versus shorthand the brief should assume."
                placeholder="Select experience level"
                value={investorProfileForm.experience_level}
                options={EXPERIENCE_OPTIONS}
                isOpen={activeInvestorDropdown === 'experience_level'}
                onToggle={onToggleDropdown}
                onSelect={(value) => onSelectValue('experience_level', value)}
              />
              <InvestorProfileSelect
                fieldKey="risk_tolerance"
                label="Risk tolerance"
                helper="Shapes how strongly FlowDeck emphasizes downside control versus upside capture."
                placeholder="Select risk tolerance"
                value={investorProfileForm.risk_tolerance}
                options={RISK_OPTIONS}
                isOpen={activeInvestorDropdown === 'risk_tolerance'}
                onToggle={onToggleDropdown}
                onSelect={(value) => onSelectValue('risk_tolerance', value)}
              />
              <InvestorProfileSelect
                fieldKey="time_horizon"
                label="Time horizon"
                helper="Helps the brief decide whether to focus on immediate catalysts or longer arcs."
                placeholder="Select time horizon"
                value={investorProfileForm.time_horizon}
                options={HORIZON_OPTIONS}
                isOpen={activeInvestorDropdown === 'time_horizon'}
                onToggle={onToggleDropdown}
                onSelect={(value) => onSelectValue('time_horizon', value)}
              />
              <InvestorProfileSelect
                fieldKey="primary_goal"
                label="Primary goal"
                helper="Tells the AI what outcome matters most when the answer is not obvious."
                placeholder="Select primary goal"
                value={investorProfileForm.primary_goal}
                options={PRIMARY_GOAL_OPTIONS}
                isOpen={activeInvestorDropdown === 'primary_goal'}
                onToggle={onToggleDropdown}
                onSelect={(value) => onSelectValue('primary_goal', value)}
              />
              <div className={INVESTOR_FIELD_CARD_CLASS}>
                <label className="mb-2 block text-sm font-semibold text-slate-100">Date of birth</label>
                <p className="mb-3 text-xs leading-5 text-slate-400">
                  Optional personal context stored in your private profile.
                </p>
                <input
                  type="date"
                  value={investorProfileForm.date_of_birth}
                  onChange={(event: ChangeEvent<HTMLInputElement>) =>
                    onInvestorProfileFormChange((prev) => ({
                      ...prev,
                      date_of_birth: event.target.value,
                    }))
                  }
                  className={PROFILE_INPUT_CLASS}
                />
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200">Goals</label>
              <div className="flex flex-wrap gap-2">
                {INVESTOR_GOAL_OPTIONS.map((option) => {
                  const selected = investorProfileForm.goals.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onToggleListValue('goals', option.value)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                        selected
                          ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100'
                          : 'border-slate-600 bg-slate-950 text-slate-300 hover:border-slate-500 hover:text-white'
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200">
                Constraints and preferences
              </label>
              <div className="flex flex-wrap gap-2">
                {INVESTOR_CONSTRAINT_OPTIONS.map((option) => {
                  const selected = investorProfileForm.constraints.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onToggleListValue('constraints', option.value)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                        selected
                          ? 'border-emerald-400 bg-emerald-500/20 text-emerald-100'
                          : 'border-slate-600 bg-slate-950 text-slate-300 hover:border-slate-500 hover:text-white'
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
                <label className="mb-2 block text-sm font-medium text-slate-200">Private AI memory</label>
                <textarea
                  value={investorProfileForm.ai_memory_text}
                  onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                    onInvestorProfileFormChange((prev) => ({
                      ...prev,
                      ai_memory_text: event.target.value.slice(0, 4000),
                    }))
                  }
                  rows={8}
                  maxLength={4000}
                  className={PROFILE_TEXTAREA_CLASS}
                  placeholder="Examples: I care more about downside protection than maximum upside. Avoid suggesting leverage. Remind me to check valuation before chasing momentum. My long-term accounts should stay diversified."
                />
                <div className="mt-2 flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">
                    Editable private memory used by FlowDeck chat and scheduled briefs.
                  </p>
                  <span className="text-xs text-slate-500">
                    {investorProfileForm.ai_memory_text.length}/4000
                  </span>
                </div>
              </div>

              <div className={`${PROFILE_MUTED_PANEL_CLASS} p-4`}>
                <h3 className="text-sm font-semibold text-white">Response style</h3>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  This hints how you want FlowDeck to explain ideas when there is room to adapt tone.
                </p>
                <div className="mt-4 space-y-2">
                  {INVESTOR_RESPONSE_STYLE_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className={`flex cursor-pointer items-center justify-between rounded-xl border px-3 py-2 text-sm transition-colors ${
                        investorProfileForm.preferred_style === option.value
                          ? 'border-cyan-400/50 bg-cyan-500/10 text-cyan-50'
                          : 'border-slate-700 bg-slate-950 text-slate-200 hover:border-slate-600'
                      }`}
                    >
                      <span>{option.label}</span>
                      <input
                        type="radio"
                        name="preferred_style"
                        value={option.value}
                        checked={investorProfileForm.preferred_style === option.value}
                        onChange={(event: ChangeEvent<HTMLInputElement>) =>
                          onInvestorProfileFormChange((prev) => ({
                            ...prev,
                            preferred_style: event.target.value,
                          }))
                        }
                        className="h-4 w-4 border-slate-500 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                      />
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => onInvestorProfileFormChange((prev) => ({ ...prev, preferred_style: '' }))}
                  className="mt-3 text-xs text-cyan-300 transition-colors hover:text-cyan-200"
                >
                  Clear style preference
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-slate-800 pt-5">
              <p className="text-xs text-slate-500">
                {investorProfile?.updated_at
                  ? `Last updated ${new Date(investorProfile.updated_at).toLocaleString()}`
                  : 'Not saved yet'}
              </p>
              <div className="flex items-center gap-3">
                {investorProfileMessage ? (
                  <div className={`rounded-lg border px-3 py-2 text-sm font-medium ${
                    investorProfileMessage.includes('successfully')
                      ? 'border-green-500/30 bg-green-500/10 text-green-400'
                      : 'border-red-500/30 bg-red-500/10 text-red-400'
                  }`}>
                    {investorProfileMessage}
                  </div>
                ) : null}
                <button type="submit" disabled={investorProfileSaving} className={PROFILE_PRIMARY_BUTTON_CLASS}>
                  {investorProfileSaving ? 'Saving...' : 'Save investor profile'}
                </button>
              </div>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
