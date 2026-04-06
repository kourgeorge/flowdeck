import type { SelectOption, SelectOptionGroup } from '../CustomSelect';
import type { DigestNarrativeStyle, InvestorSelectOption } from './profileTypes';

export const WEEKDAY_SHORT_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const WEEKDAY_FULL_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export const NARRATIVE_STYLE_LABELS: Record<DigestNarrativeStyle, string> = {
  default: 'Balanced',
  concise: 'Concise',
  professional: 'Professional',
  technical: 'Technical',
};

const COMMON_TIMEZONES = [
  { value: '', label: 'Use browser timezone', group: '' },
  { value: 'America/New_York', label: 'Eastern Time (US & Canada)', group: 'Americas' },
  { value: 'America/Chicago', label: 'Central Time (US & Canada)', group: 'Americas' },
  { value: 'America/Denver', label: 'Mountain Time (US & Canada)', group: 'Americas' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (US & Canada)', group: 'Americas' },
  { value: 'America/Anchorage', label: 'Alaska', group: 'Americas' },
  { value: 'Pacific/Honolulu', label: 'Hawaii', group: 'Americas' },
  { value: 'America/Toronto', label: 'Toronto', group: 'Americas' },
  { value: 'America/Mexico_City', label: 'Mexico City', group: 'Americas' },
  { value: 'America/Sao_Paulo', label: 'São Paulo', group: 'Americas' },
  { value: 'America/Buenos_Aires', label: 'Buenos Aires', group: 'Americas' },
  { value: 'Europe/London', label: 'London', group: 'Europe' },
  { value: 'Europe/Paris', label: 'Paris', group: 'Europe' },
  { value: 'Europe/Berlin', label: 'Berlin', group: 'Europe' },
  { value: 'Europe/Rome', label: 'Rome', group: 'Europe' },
  { value: 'Europe/Madrid', label: 'Madrid', group: 'Europe' },
  { value: 'Europe/Amsterdam', label: 'Amsterdam', group: 'Europe' },
  { value: 'Europe/Brussels', label: 'Brussels', group: 'Europe' },
  { value: 'Europe/Vienna', label: 'Vienna', group: 'Europe' },
  { value: 'Europe/Stockholm', label: 'Stockholm', group: 'Europe' },
  { value: 'Europe/Warsaw', label: 'Warsaw', group: 'Europe' },
  { value: 'Europe/Athens', label: 'Athens', group: 'Europe' },
  { value: 'Europe/Istanbul', label: 'Istanbul', group: 'Europe' },
  { value: 'Europe/Moscow', label: 'Moscow', group: 'Europe' },
  { value: 'Asia/Jerusalem', label: 'Jerusalem', group: 'Asia' },
  { value: 'Asia/Dubai', label: 'Dubai', group: 'Asia' },
  { value: 'Asia/Kolkata', label: 'Mumbai/Kolkata', group: 'Asia' },
  { value: 'Asia/Bangkok', label: 'Bangkok', group: 'Asia' },
  { value: 'Asia/Singapore', label: 'Singapore', group: 'Asia' },
  { value: 'Asia/Hong_Kong', label: 'Hong Kong', group: 'Asia' },
  { value: 'Asia/Shanghai', label: 'Beijing/Shanghai', group: 'Asia' },
  { value: 'Asia/Tokyo', label: 'Tokyo', group: 'Asia' },
  { value: 'Asia/Seoul', label: 'Seoul', group: 'Asia' },
  { value: 'Australia/Sydney', label: 'Sydney', group: 'Pacific' },
  { value: 'Australia/Melbourne', label: 'Melbourne', group: 'Pacific' },
  { value: 'Australia/Brisbane', label: 'Brisbane', group: 'Pacific' },
  { value: 'Australia/Perth', label: 'Perth', group: 'Pacific' },
  { value: 'Pacific/Auckland', label: 'Auckland', group: 'Pacific' },
];

export const BRIEF_STYLE_OPTIONS: SelectOption[] = [
  { value: 'default', label: 'Balanced', description: 'Well-rounded analysis with key insights' },
  { value: 'concise', label: 'Concise', description: 'Brief summaries, quick to read' },
  { value: 'professional', label: 'Professional', description: 'Formal tone with detailed context' },
  { value: 'technical', label: 'Technical', description: 'In-depth analysis with more detail' },
];

export const INVESTOR_GOAL_OPTIONS = [
  { value: 'dividend_income', label: 'Dividend income' },
  { value: 'long_term_compounding', label: 'Long-term compounding' },
  { value: 'capital_growth', label: 'Capital growth' },
  { value: 'retirement_planning', label: 'Retirement planning' },
  { value: 'swing_trades', label: 'Swing trades' },
  { value: 'short_term_opportunities', label: 'Short-term opportunities' },
  { value: 'hedging', label: 'Hedging' },
  { value: 'learning', label: 'Learning' },
] as const;

export const INVESTOR_CONSTRAINT_OPTIONS = [
  { value: 'avoid_high_drawdowns', label: 'Avoid high drawdowns' },
  { value: 'avoid_options', label: 'Avoid options' },
  { value: 'avoid_leverage', label: 'Avoid leverage' },
  { value: 'prefer_large_caps', label: 'Prefer large caps' },
  { value: 'prefer_profitable_companies', label: 'Prefer profitable companies' },
  { value: 'income_focus', label: 'Income focus' },
  { value: 'esg_focus', label: 'ESG focus' },
  { value: 'tax_sensitive', label: 'Tax sensitive' },
] as const;

export const PERSONA_OPTIONS: InvestorSelectOption[] = [
  { value: 'investor', label: 'Investor', description: 'Prioritize thesis durability, valuation, and longer-term compounding.' },
  { value: 'trader', label: 'Trader', description: 'Lean into timing, catalysts, levels, and near-term setups.' },
  { value: 'both', label: 'Both', description: 'Blend investment framing with tactical trading awareness.' },
];

export const EXPERIENCE_OPTIONS: InvestorSelectOption[] = [
  { value: 'beginner', label: 'Beginner', description: 'Use simpler framing and explain the core tradeoffs clearly.' },
  { value: 'intermediate', label: 'Intermediate', description: 'Assume some market fluency but still keep context explicit.' },
  { value: 'advanced', label: 'Advanced', description: 'Use tighter shorthand and focus on nuance over basics.' },
  { value: 'professional', label: 'Professional', description: 'Favor concise, high-signal language and institutional framing.' },
];

export const RISK_OPTIONS: InvestorSelectOption[] = [
  { value: 'conservative', label: 'Conservative', description: 'Emphasize capital protection, downside risk, and steadier setups.' },
  { value: 'moderate', label: 'Moderate', description: 'Balance upside potential with drawdown control and flexibility.' },
  { value: 'aggressive', label: 'Aggressive', description: 'Accept more volatility in exchange for higher potential upside.' },
];

export const HORIZON_OPTIONS: InvestorSelectOption[] = [
  { value: 'intraday', label: 'Intraday', description: 'Focus on same-day movement, price action, and immediate catalysts.' },
  { value: 'swing', label: 'Swing', description: 'Center on moves that can develop over days to a few weeks.' },
  { value: 'medium_term', label: 'Medium term', description: 'Weigh catalysts and thesis development over weeks to months.' },
  { value: 'long_term', label: 'Long term', description: 'Stress multi-quarter durability, compounding, and thesis quality.' },
];

export const PRIMARY_GOAL_OPTIONS: InvestorSelectOption[] = [
  { value: 'wealth_building', label: 'Wealth building', description: 'Bias toward durable upside and long-run portfolio growth.' },
  { value: 'active_trading', label: 'Active trading', description: 'Optimize for tactical opportunities and active decision-making.' },
  { value: 'retirement', label: 'Retirement', description: 'Favor resilience, discipline, and lower-regret portfolio choices.' },
  { value: 'income', label: 'Income', description: 'Highlight yield, cash generation, and income-friendly tradeoffs.' },
  { value: 'capital_preservation', label: 'Capital preservation', description: 'Put downside control and balance-sheet safety first.' },
  { value: 'learning', label: 'Learning', description: 'Explain reasoning clearly so the brief teaches while it guides.' },
];

export const INVESTOR_RESPONSE_STYLE_OPTIONS = [
  { value: 'balanced', label: 'Balanced' },
  { value: 'concise', label: 'Concise' },
  { value: 'professional', label: 'Professional' },
  { value: 'technical', label: 'Technical' },
] as const;

export function getTimezoneOptions(browserTimezone: string): SelectOptionGroup[] {
  const grouped = COMMON_TIMEZONES.reduce((acc, timezone) => {
    const group = timezone.group || 'Default';
    if (!acc[group]) acc[group] = [];
    acc[group].push({
      value: timezone.value,
      label:
        timezone.value === ''
          ? `Use browser timezone (${browserTimezone})`
          : timezone.label,
    });
    return acc;
  }, {} as Record<string, SelectOption[]>);

  return Object.entries(grouped).map(([group, options]) => ({
    group: group === 'Default' ? '' : group,
    options,
  }));
}
