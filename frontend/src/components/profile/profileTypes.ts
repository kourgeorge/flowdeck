export type ProfileTabType =
  | 'overview'
  | 'usage'
  | 'investor-profile'
  | 'api-keys'
  | 'account'
  | 'brief-schedule';

export type DigestNarrativeStyle =
  | 'default'
  | 'concise'
  | 'professional'
  | 'technical';

export type ScheduleEditorType = 'daily' | 'weekly' | null;

export type InvestorSelectFieldKey =
  | 'persona_type'
  | 'experience_level'
  | 'risk_tolerance'
  | 'time_horizon'
  | 'primary_goal'
  | null;

export type InvestorProfileFormState = {
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

export type InvestorSelectOption = {
  value: string;
  label: string;
  description: string;
};
