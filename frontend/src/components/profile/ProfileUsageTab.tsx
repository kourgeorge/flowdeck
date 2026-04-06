import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { UsageHistoryResponse, UsageOperationItem } from '../../services/tokenApi';
import {
  PROFILE_METRIC_CARD_CLASS,
  PROFILE_MUTED_PANEL_CLASS,
  PROFILE_PANEL_CLASS,
  PROFILE_PILL_CLASS,
} from './profileStyles';

const USAGE_PERIOD_OPTIONS = [
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
  { value: 365, label: '1 year' },
] as const;

const USAGE_CHART_GRID = '#334155';
const USAGE_CHART_TICK = '#94a3b8';
const USAGE_CHART_TOOLTIP_STYLE = {
  backgroundColor: '#020617',
  border: '1px solid #334155',
  borderRadius: '12px',
  color: '#e2e8f0',
};

type ProfileUsageTabProps = {
  usagePeriodDays: number;
  usageHistory: UsageHistoryResponse | null;
  usageLoading: boolean;
  usageError: string | null;
  onSelectPeriod: (days: number) => void;
};

function formatUsageDate(iso: string | null): string {
  if (!iso) return 'Unknown time';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Unknown time';
  return date.toLocaleString();
}

function formatUsageKind(kind: UsageOperationItem['kind']): string {
  if (kind === 'analysis') return 'AI analysis';
  if (kind === 'chat') return 'Chat';
  if (kind === 'digest') return 'Digest';
  return kind;
}

function getUsageKindClasses(kind: UsageOperationItem['kind']): string {
  if (kind === 'analysis') return 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100';
  if (kind === 'chat') return 'border-amber-400/30 bg-amber-400/10 text-amber-100';
  if (kind === 'digest') return 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100';
  return 'border-slate-500/30 bg-slate-500/10 text-slate-200';
}

function getUsageStatusClasses(status: string): string {
  if (status === 'completed') return 'border-emerald-400/30 bg-emerald-400/15 text-emerald-200';
  if (status === 'failed') return 'border-red-400/30 bg-red-400/15 text-red-200';
  if (status === 'running') return 'border-amber-400/30 bg-amber-400/15 text-amber-100';
  return 'border-slate-500/30 bg-slate-500/10 text-slate-200';
}

function formatUsageTrendDate(value: string) {
  const date = new Date(value);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function formatTokenAxis(value: number) {
  if (value >= 1000000) return `${(value / 1000000).toFixed(value >= 10000000 ? 0 : 1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  return value.toLocaleString('en-US');
}

export default function ProfileUsageTab({
  usagePeriodDays,
  usageHistory,
  usageLoading,
  usageError,
  onSelectPeriod,
}: ProfileUsageTabProps) {
  const summary = usageHistory?.summary ?? null;
  const usageTrendData = usageHistory?.daily_trend ?? [];
  const hasTrendData = usageTrendData.some((point) => point.total_platform_tokens > 0);
  const usageTrendPeak = usageTrendData.reduce<(typeof usageTrendData)[number] | null>(
    (highest, point) => {
      if (!highest || point.total_platform_tokens > highest.total_platform_tokens) {
        return point;
      }
      return highest;
    },
    null,
  );

  return (
    <div className="space-y-6">
      <section className={`${PROFILE_PANEL_CLASS} p-6`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <span className={`${PROFILE_PILL_CLASS} border-blue-400/30 bg-blue-400/10 text-blue-100`}>
              Token usage
            </span>
            <h2 className="mt-4 text-xl font-semibold text-white">Exact usage history</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Review every paid operation across AI analysis, chat, and digest
              runs. Each row shows the DECK tokens charged and the exact LLM token
              counts when they are tracked.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {USAGE_PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onSelectPeriod(option.value)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  usagePeriodDays === option.value
                    ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100'
                    : 'border-slate-600 bg-slate-950 text-slate-300 hover:border-slate-500 hover:text-white'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {usageLoading ? (
        <section className={`${PROFILE_PANEL_CLASS} p-6`}>
          <p className="text-sm text-slate-400">Loading usage history...</p>
        </section>
      ) : usageError ? (
        <section className={`${PROFILE_PANEL_CLASS} border-red-900/50 p-6`}>
          <p className="text-sm text-red-300">{usageError}</p>
        </section>
      ) : !summary ? (
        <section className={`${PROFILE_PANEL_CLASS} p-6`}>
          <p className="text-sm text-slate-400">No usage data available for this period.</p>
        </section>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className={PROFILE_METRIC_CARD_CLASS}>
              <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Total spend</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {summary.total_platform_tokens.toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-slate-300">
                DECK tokens across {summary.total_operations.toLocaleString()} operations
              </p>
              <p className="mt-3 text-xs text-slate-500">
                {summary.total_llm_tokens.toLocaleString()} raw LLM tokens tracked
              </p>
            </div>

            <div className={`${PROFILE_METRIC_CARD_CLASS} border-cyan-500/20`}>
              <p className="text-[11px] uppercase tracking-[0.22em] text-cyan-200/80">AI analysis</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {summary.analysis_platform_tokens.toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-slate-300">
                {summary.analysis_count.toLocaleString()} executions
              </p>
              <p className="mt-3 text-xs text-slate-500">
                {summary.analysis_llm_tokens.toLocaleString()} LLM tokens tracked
              </p>
            </div>

            <div className={`${PROFILE_METRIC_CARD_CLASS} border-amber-500/20`}>
              <p className="text-[11px] uppercase tracking-[0.22em] text-amber-200/80">Chat</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {summary.chat_platform_tokens.toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-slate-300">{summary.chat_count.toLocaleString()} turns</p>
              <p className="mt-3 text-xs text-slate-500">
                {summary.chat_llm_tokens.toLocaleString()} LLM tokens tracked
              </p>
            </div>

            <div className={`${PROFILE_METRIC_CARD_CLASS} border-emerald-500/20`}>
              <p className="text-[11px] uppercase tracking-[0.22em] text-emerald-200/80">Digest</p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {summary.digest_platform_tokens.toLocaleString()}
              </p>
              <p className="mt-1 text-sm text-slate-300">
                {summary.digest_count.toLocaleString()} brief runs
              </p>
              <p className="mt-3 text-xs text-slate-500">
                {summary.digest_llm_tokens.toLocaleString()} LLM tokens tracked
              </p>
            </div>
          </section>

          <section className={`${PROFILE_PANEL_CLASS} p-6`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Usage trend</h3>
                <p className="mt-1 text-sm text-slate-400">
                  Daily DECK token spend over the last {summary.period_days} days,
                  split by analysis, chat, and digest usage.
                </p>
              </div>
              {usageTrendPeak && hasTrendData ? (
                <div className={`${PROFILE_MUTED_PANEL_CLASS} px-4 py-3`}>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Peak day</p>
                  <p className="mt-1 text-lg font-semibold text-white">
                    {usageTrendPeak.total_platform_tokens.toLocaleString()} tokens
                  </p>
                  <p className="text-xs text-slate-400">{formatUsageTrendDate(usageTrendPeak.date)}</p>
                </div>
              ) : null}
            </div>

            {hasTrendData ? (
              <div className="mt-5 h-[340px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={usageTrendData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={USAGE_CHART_GRID} strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatUsageTrendDate}
                      tick={{ fill: USAGE_CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: USAGE_CHART_GRID }}
                      tickLine={{ stroke: USAGE_CHART_GRID }}
                    />
                    <YAxis
                      yAxisId="tokens"
                      tickFormatter={(value: number) => formatTokenAxis(value)}
                      tick={{ fill: USAGE_CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: USAGE_CHART_GRID }}
                      tickLine={{ stroke: USAGE_CHART_GRID }}
                      width={72}
                    />
                    <YAxis
                      yAxisId="ops"
                      orientation="right"
                      tickFormatter={(value: number) => value.toLocaleString('en-US')}
                      tick={{ fill: USAGE_CHART_TICK, fontSize: 12 }}
                      axisLine={{ stroke: USAGE_CHART_GRID }}
                      tickLine={{ stroke: USAGE_CHART_GRID }}
                      width={44}
                    />
                    <Tooltip
                      contentStyle={USAGE_CHART_TOOLTIP_STYLE}
                      labelFormatter={(label) => formatUsageTrendDate(String(label ?? ''))}
                      formatter={(value, name) => {
                        const numericValue = Number(value ?? 0);
                        if (name === 'Operations') {
                          return [numericValue.toLocaleString('en-US'), name];
                        }
                        return [`${numericValue.toLocaleString('en-US')} tokens`, name];
                      }}
                    />
                    <Line yAxisId="tokens" type="monotone" dataKey="total_platform_tokens" name="Total" stroke="#f8fafc" strokeWidth={2.6} dot={false} />
                    <Line yAxisId="tokens" type="monotone" dataKey="analysis_platform_tokens" name="Analysis" stroke="#22d3ee" strokeWidth={2} dot={false} />
                    <Line yAxisId="tokens" type="monotone" dataKey="chat_platform_tokens" name="Chat" stroke="#f59e0b" strokeWidth={2} dot={false} />
                    <Line yAxisId="tokens" type="monotone" dataKey="digest_platform_tokens" name="Digest" stroke="#10b981" strokeWidth={2} dot={false} />
                    <Line yAxisId="ops" type="monotone" dataKey="operation_count" name="Operations" stroke="#a78bfa" strokeDasharray="6 6" strokeWidth={1.8} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className={`${PROFILE_MUTED_PANEL_CLASS} mt-5 px-4 py-4 text-sm text-slate-400`}>
                No daily token trend is available for this period yet.
              </div>
            )}
          </section>

          <section className={`${PROFILE_PANEL_CLASS} p-6`}>
            <div>
              <h3 className="text-lg font-semibold text-white">Operation history</h3>
              <p className="mt-1 text-sm text-slate-400">
                Showing {(usageHistory?.returned_operations ?? 0).toLocaleString()} most
                recent entries from the last {summary.period_days} days. Chat usage
                is grouped by conversation.
              </p>
            </div>

            <div className="mt-5 space-y-3">
              {usageHistory?.items.length ? (
                usageHistory.items.map((item, index) => {
                  const identifier =
                    item.chat_session_id != null
                      ? `Conversation #${item.chat_session_id}`
                      : item.execution_id != null
                        ? `Execution #${item.execution_id}`
                        : item.chat_turn_id != null
                          ? `Turn #${item.chat_turn_id}`
                          : `Operation #${index + 1}`;

                  return (
                    <article
                      key={`${item.kind}-${item.execution_id ?? item.chat_session_id ?? item.chat_turn_id ?? index}-${item.created_at ?? index}`}
                      className={`${PROFILE_MUTED_PANEL_CLASS} p-4`}
                    >
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${getUsageKindClasses(item.kind)}`}>
                              {formatUsageKind(item.kind)}
                            </span>
                            <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${getUsageStatusClasses(item.status)}`}>
                              {item.status}
                            </span>
                          </div>
                          <h4 className="mt-3 text-base font-semibold text-white">{item.title}</h4>
                          <p className="mt-1 text-sm text-slate-300">{item.subject_label}</p>
                          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500">
                            <span>{identifier}</span>
                            {item.chat_turn_count != null && item.chat_turn_count > 0 ? (
                              <span>{item.chat_turn_count.toLocaleString()} turns</span>
                            ) : null}
                            {item.tools_called != null && item.tools_called > 0 ? (
                              <span>{item.tools_called} tools called</span>
                            ) : null}
                            <span>{formatUsageDate(item.created_at)}</span>
                          </div>
                        </div>

                        <div className="grid min-w-full gap-3 sm:min-w-[360px] sm:grid-cols-2 lg:min-w-[420px] lg:grid-cols-4">
                          <div className={`${PROFILE_MUTED_PANEL_CLASS} p-3`}>
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">DECK spent</p>
                            <p className="mt-2 text-lg font-semibold text-white">
                              {item.platform_tokens != null ? item.platform_tokens.toLocaleString() : 'N/A'}
                            </p>
                          </div>
                          <div className={`${PROFILE_MUTED_PANEL_CLASS} p-3`}>
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">LLM total</p>
                            <p className="mt-2 text-lg font-semibold text-white">
                              {item.llm_tokens != null ? item.llm_tokens.toLocaleString() : 'N/A'}
                            </p>
                          </div>
                          <div className={`${PROFILE_MUTED_PANEL_CLASS} p-3`}>
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Input</p>
                            <p className="mt-2 text-lg font-semibold text-white">
                              {item.input_tokens != null ? item.input_tokens.toLocaleString() : 'N/A'}
                            </p>
                          </div>
                          <div className={`${PROFILE_MUTED_PANEL_CLASS} p-3`}>
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Output</p>
                            <p className="mt-2 text-lg font-semibold text-white">
                              {item.output_tokens != null ? item.output_tokens.toLocaleString() : 'N/A'}
                            </p>
                          </div>
                        </div>
                      </div>
                    </article>
                  );
                })
              ) : (
                <div className={`${PROFILE_MUTED_PANEL_CLASS} px-4 py-4 text-sm text-slate-400`}>
                  No paid operations found in this period.
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
