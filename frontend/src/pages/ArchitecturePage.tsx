import { Link } from 'react-router-dom';

type AgentKind = 'Analyst' | 'Researcher' | 'Manager' | 'Trader' | 'Risk Analyst';

type AgentContract = {
  id: string;
  name: string;
  kind: AgentKind;
  selectedByDefault: string;
  consumes: string[];
  tools?: string[];
  emits: string[];
  outputShape: Record<string, unknown>;
};

type ContractPhase = {
  id: string;
  title: string;
  description: string;
  agents: AgentContract[];
};

const analystOutputShape = (reportField: string, scoreField: string) => ({
  messages: [{ type: 'AIMessage', content: `<${reportField}>` }],
  [reportField]: '<string>',
  [scoreField]: '<int 1-10 | null>',
});

const AGENT_CONTRACTS: AgentContract[] = [
  {
    id: 'market-analyst',
    name: 'Market Analyst',
    kind: 'Analyst',
    selectedByDefault: 'Yes',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: ['get_stock_data', 'get_stock_quote', 'get_indicators'],
    emits: ['messages', 'market_report', 'market_score'],
    outputShape: analystOutputShape('market_report', 'market_score'),
  },
  {
    id: 'social-analyst',
    name: 'Social Media Analyst',
    kind: 'Analyst',
    selectedByDefault: 'No (available)',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: ['get_news'],
    emits: ['messages', 'sentiment_report', 'sentiment_score'],
    outputShape: analystOutputShape('sentiment_report', 'sentiment_score'),
  },
  {
    id: 'news-analyst',
    name: 'News Analyst',
    kind: 'Analyst',
    selectedByDefault: 'Yes',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: ['get_news', 'get_global_news', 'get_insider_transactions'],
    emits: ['messages', 'news_report', 'news_score'],
    outputShape: analystOutputShape('news_report', 'news_score'),
  },
  {
    id: 'fundamentals-analyst',
    name: 'Fundamentals Analyst',
    kind: 'Analyst',
    selectedByDefault: 'Yes',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: ['get_fundamentals', 'get_balance_sheet', 'get_cashflow', 'get_income_statement'],
    emits: ['messages', 'fundamentals_report', 'fundamentals_score'],
    outputShape: analystOutputShape('fundamentals_report', 'fundamentals_score'),
  },
  {
    id: 'technical-analyst',
    name: 'Technical Analyst',
    kind: 'Analyst',
    selectedByDefault: 'Yes',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: [
      'get_stock_data',
      'get_stock_quote',
      'get_indicators',
      'detect_divergence',
      'detect_regime',
      'detect_support_resistance',
    ],
    emits: ['messages', 'technical_report', 'technical_score'],
    outputShape: analystOutputShape('technical_report', 'technical_score'),
  },
  {
    id: 'sec-analyst',
    name: 'SEC Analyst',
    kind: 'Analyst',
    selectedByDefault: 'Yes (US companies)',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: ['get_edgar_filing_content'],
    emits: ['messages', 'sec_report', 'sec_score'],
    outputShape: analystOutputShape('sec_report', 'sec_score'),
  },
  {
    id: 'bull-researcher',
    name: 'Bull Researcher',
    kind: 'Researcher',
    selectedByDefault: 'Always',
    consumes: [
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'technical_report',
      'investment_debate_state',
    ],
    emits: ['investment_debate_state'],
    outputShape: {
      investment_debate_state: {
        history: '<string>',
        bull_history: '<string>',
        bear_history: '<string>',
        current_response: 'Bull Analyst: <string>',
        count: '<int>',
      },
    },
  },
  {
    id: 'bear-researcher',
    name: 'Bear Researcher',
    kind: 'Researcher',
    selectedByDefault: 'Always',
    consumes: [
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'technical_report',
      'investment_debate_state',
    ],
    emits: ['investment_debate_state'],
    outputShape: {
      investment_debate_state: {
        history: '<string>',
        bull_history: '<string>',
        bear_history: '<string>',
        current_response: 'Bear Analyst: <string>',
        count: '<int>',
      },
    },
  },
  {
    id: 'research-manager',
    name: 'Research Manager',
    kind: 'Manager',
    selectedByDefault: 'Always',
    consumes: [
      'investment_debate_state',
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'sec_report',
      'technical_report',
    ],
    emits: [
      'investment_debate_state',
      'investment_plan',
      'recommendation_score',
      'bull_summary',
      'bear_summary',
      'expected_return_pct',
      'bear_case_return_pct',
      'bull_case_return_pct',
    ],
    outputShape: {
      investment_debate_state: {
        judge_decision: '<string>',
        history: '<string>',
        bear_history: '<string>',
        bull_history: '<string>',
        current_response: '<string>',
        count: '<int>',
      },
      investment_plan: '<string>',
      recommendation_score: '<int 1-10 | null>',
      bull_summary: ['<string>'],
      bear_summary: ['<string>'],
      expected_return_pct: '<number | null>',
      bear_case_return_pct: '<number | null>',
      bull_case_return_pct: '<number | null>',
    },
  },
  {
    id: 'trader',
    name: 'Trader',
    kind: 'Trader',
    selectedByDefault: 'Always',
    consumes: [
      'company_of_interest',
      'investment_plan',
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
    ],
    emits: ['messages', 'trader_investment_plan', 'trader_recommendation', 'sender'],
    outputShape: {
      messages: [{ type: 'AIMessage', content: '<trader_investment_plan>' }],
      trader_investment_plan: '<string>',
      trader_recommendation: 'BUY | SELL | HOLD | null',
      sender: 'Trader',
    },
  },
  {
    id: 'risky-analyst',
    name: 'Risky Analyst',
    kind: 'Risk Analyst',
    selectedByDefault: 'Always',
    consumes: [
      'trader_investment_plan',
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'sec_report',
      'technical_report',
      'risk_debate_state',
    ],
    emits: ['risk_debate_state'],
    outputShape: {
      risk_debate_state: {
        history: '<string>',
        risky_history: '<string>',
        safe_history: '<string>',
        neutral_history: '<string>',
        latest_speaker: 'Risky',
        current_risky_response: 'Risky Analyst: <string>',
        current_safe_response: '<string>',
        current_neutral_response: '<string>',
        count: '<int>',
      },
    },
  },
  {
    id: 'safe-analyst',
    name: 'Safe Analyst',
    kind: 'Risk Analyst',
    selectedByDefault: 'Always',
    consumes: [
      'trader_investment_plan',
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'sec_report',
      'technical_report',
      'risk_debate_state',
    ],
    emits: ['risk_debate_state'],
    outputShape: {
      risk_debate_state: {
        history: '<string>',
        risky_history: '<string>',
        safe_history: '<string>',
        neutral_history: '<string>',
        latest_speaker: 'Safe',
        current_risky_response: '<string>',
        current_safe_response: 'Safe Analyst: <string>',
        current_neutral_response: '<string>',
        count: '<int>',
      },
    },
  },
  {
    id: 'neutral-analyst',
    name: 'Neutral Analyst',
    kind: 'Risk Analyst',
    selectedByDefault: 'Always',
    consumes: [
      'trader_investment_plan',
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'sec_report',
      'technical_report',
      'risk_debate_state',
    ],
    emits: ['risk_debate_state'],
    outputShape: {
      risk_debate_state: {
        history: '<string>',
        risky_history: '<string>',
        safe_history: '<string>',
        neutral_history: '<string>',
        latest_speaker: 'Neutral',
        current_risky_response: '<string>',
        current_safe_response: '<string>',
        current_neutral_response: 'Neutral Analyst: <string>',
        count: '<int>',
      },
    },
  },
  {
    id: 'risk-judge',
    name: 'Risk Judge (Risk Manager)',
    kind: 'Manager',
    selectedByDefault: 'Always',
    consumes: [
      'risk_debate_state',
      'investment_plan',
      'market_report',
      'sentiment_report',
      'news_report',
      'fundamentals_report',
      'sec_report',
      'market_score',
      'sentiment_score',
      'news_score',
      'fundamentals_score',
      'sec_score',
      'technical_score',
      'recommendation_score',
    ],
    emits: [
      'risk_debate_state',
      'final_trade_decision',
      'risk_score',
      'final_report_key_takeaways',
      'risky_summary',
      'safe_summary',
      'neutral_summary',
    ],
    outputShape: {
      risk_debate_state: {
        judge_decision: '<string>',
        history: '<string>',
        risky_history: '<string>',
        safe_history: '<string>',
        neutral_history: '<string>',
        latest_speaker: 'Judge',
        current_risky_response: '<string>',
        current_safe_response: '<string>',
        current_neutral_response: '<string>',
        count: '<int>',
      },
      final_trade_decision: '<string>',
      risk_score: '<int 1-10 | null>',
      final_report_key_takeaways: ['<string>'],
      risky_summary: ['<string>'],
      safe_summary: ['<string>'],
      neutral_summary: ['<string>'],
    },
  },
];

const selectContracts = (ids: string[]): AgentContract[] =>
  ids
    .map((id) => AGENT_CONTRACTS.find((agent) => agent.id === id))
    .filter((agent): agent is AgentContract => Boolean(agent));

const CONTRACT_PHASES: ContractPhase[] = [
  {
    id: 'phase-1-analysts',
    title: 'Phase 1: Analyst Pipeline',
    description:
      'Specialized analysts gather market, sentiment, news, fundamentals, technical, and SEC/regulatory evidence.',
    agents: selectContracts([
      'market-analyst',
      'social-analyst',
      'news-analyst',
      'fundamentals-analyst',
      'technical-analyst',
      'sec-analyst',
    ]),
  },
  {
    id: 'phase-2-investment',
    title: 'Phase 2: Investment Debate + Plan',
    description:
      'Bull and bear researchers debate, then the research manager produces the investment plan and the trader emits a concrete recommendation.',
    agents: selectContracts(['bull-researcher', 'bear-researcher', 'research-manager', 'trader']),
  },
  {
    id: 'phase-3-risk',
    title: 'Phase 3: Risk Debate + Final Judge',
    description:
      'Risky, safe, and neutral analysts debate risk tradeoffs before the risk judge emits the final decision narrative and risk score.',
    agents: selectContracts(['risky-analyst', 'safe-analyst', 'neutral-analyst', 'risk-judge']),
  },
];

const FINAL_LOGGED_OUTPUT_SHAPE = {
  company_of_interest: '<string>',
  trade_date: '<YYYY-MM-DD>',
  market_report: '<string>',
  market_score: '<int | null>',
  sentiment_report: '<string>',
  sentiment_score: '<int | null>',
  news_report: '<string>',
  news_score: '<int | null>',
  fundamentals_report: '<string>',
  fundamentals_score: '<int | null>',
  sec_report: '<string>',
  sec_score: '<int | null>',
  technical_report: '<string>',
  technical_score: '<int | null>',
  investment_debate_state: {
    bull_history: '<string>',
    bear_history: '<string>',
    history: '<string>',
    current_response: '<string>',
    judge_decision: '<string>',
  },
  trader_investment_decision: '<string>',
  risk_debate_state: {
    risky_history: '<string>',
    safe_history: '<string>',
    neutral_history: '<string>',
    history: '<string>',
    judge_decision: '<string>',
  },
  investment_plan: '<string>',
  recommendation_score: '<int | null>',
  expected_return_pct: '<number | null>',
  bear_case_return_pct: '<number | null>',
  bull_case_return_pct: '<number | null>',
  final_trade_decision: '<string>',
  risk_score: '<int | null>',
};

function FlowNode({
  title,
  subtitle,
  tone,
}: {
  title: string;
  subtitle: string;
  tone: 'input' | 'analyst' | 'manager' | 'decision';
}) {
  const toneClass =
    tone === 'input'
      ? 'border-sky-500/40 bg-sky-500/10'
      : tone === 'analyst'
        ? 'border-blue-500/40 bg-blue-500/10'
        : tone === 'manager'
          ? 'border-amber-500/40 bg-amber-500/10'
          : 'border-emerald-500/40 bg-emerald-500/10';

  return (
    <div className={`rounded-lg border px-3 py-2 min-w-[180px] ${toneClass}`}>
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="text-xs text-gray-300 mt-1">{subtitle}</p>
    </div>
  );
}

function FlowArrow() {
  return <span className="text-xs text-gray-400 px-1">-&gt;</span>;
}

function AgentContractCard({ agent }: { agent: AgentContract }) {
  return (
    <article className="rounded-xl border border-gray-700 bg-gray-900/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{agent.name}</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            {agent.kind} · default: {agent.selectedByDefault}
          </p>
        </div>
      </div>

      <div className="mt-3">
        <p className="text-xs uppercase tracking-wide text-gray-400">Consumes</p>
        <p className="mt-1 text-sm text-gray-200">{agent.consumes.join(', ')}</p>
      </div>

      {agent.tools && (
        <div className="mt-3">
          <p className="text-xs uppercase tracking-wide text-gray-400">Tools</p>
          <p className="mt-1 text-sm text-gray-200">{agent.tools.join(', ')}</p>
        </div>
      )}

      <div className="mt-3">
        <p className="text-xs uppercase tracking-wide text-gray-400">Emits</p>
        <p className="mt-1 text-sm text-gray-200">{agent.emits.join(', ')}</p>
      </div>

      <div className="mt-3 rounded-lg border border-gray-700 bg-gray-950/80 p-3">
        <p className="text-xs uppercase tracking-wide text-gray-400 mb-2">Output shape</p>
        <pre className="text-xs text-gray-200 whitespace-pre-wrap break-words">
          {JSON.stringify(agent.outputShape, null, 2)}
        </pre>
      </div>
    </article>
  );
}

export default function ArchitecturePage() {
  return (
    <div className="min-h-screen px-4 py-6 sm:p-6 lg:p-8">
      <div className="text-gray-300">
        <section className="rounded-2xl border border-gray-700 bg-gradient-to-b from-gray-800/80 to-gray-900/90 p-6 md:p-8">
          <p className="text-xs uppercase tracking-[0.2em] text-blue-300">TradingAgents Graph</p>
          <h1 className="mt-2 text-3xl md:text-4xl font-bold text-white">Architecture Blueprint</h1>
          <p className="mt-3 text-sm text-gray-300 max-w-3xl">
            This page maps the exact workflow implemented by the graph. It shows every analyst and manager,
            what each step consumes, and the precise output shape each step emits into shared state.
          </p>
          <p className="mt-2 text-xs text-gray-400">
            Runtime default analyst selection in backend: market -&gt; news -&gt; fundamentals -&gt; technical -&gt; sec (US only). Social analyst is available but not selected by default.
          </p>
        </section>

        <section className="mt-6 rounded-2xl border border-gray-700 bg-gray-900/70 p-6">
          <h2 className="text-xl font-semibold text-white">Schematic Workflow</h2>
          <p className="mt-2 text-sm text-gray-400">
            Graph order from `GraphSetup.setup_graph` and `ConditionalLogic`.
          </p>

          <div className="mt-5 space-y-6">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400 mb-2">Phase 1: Analyst Pipeline</p>
              <div className="overflow-x-auto pb-2">
                <div className="flex items-center gap-1 min-w-max">
                  <FlowNode title="Input State" subtitle="ticker + trade_date + empty reports" tone="input" />
                  <FlowArrow />
                  <FlowNode title="Market Analyst" subtitle="score + report" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Social Analyst" subtitle="optional" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="News Analyst" subtitle="score + report" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Fundamentals Analyst" subtitle="score + report" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Technical Analyst" subtitle="score + report" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="SEC Analyst" subtitle="US only" tone="analyst" />
                </div>
              </div>
              <p className="mt-2 text-xs text-gray-400">
                Each analyst loops with its `tools_*` node until no more tool calls, then graph clears messages and moves forward.
              </p>
            </div>

            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400 mb-2">Phase 2: Investment Debate + Plan</p>
              <div className="overflow-x-auto pb-2">
                <div className="flex items-center gap-1 min-w-max">
                  <FlowNode title="Bull Researcher" subtitle="writes bull argument" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Bear Researcher" subtitle="writes bear argument" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Bull/Bear Loop" subtitle="2 * max_debate_rounds" tone="manager" />
                  <FlowArrow />
                  <FlowNode title="Research Manager" subtitle="investment plan + score + returns" tone="manager" />
                  <FlowArrow />
                  <FlowNode title="Trader" subtitle="trader plan + BUY/SELL/HOLD" tone="decision" />
                </div>
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400 mb-2">Phase 3: Risk Debate + Final Judge</p>
              <div className="overflow-x-auto pb-2">
                <div className="flex items-center gap-1 min-w-max">
                  <FlowNode title="Risky Analyst" subtitle="high-risk case" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Safe Analyst" subtitle="conservative case" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Neutral Analyst" subtitle="balanced case" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Risk Loop" subtitle="3 * max_risk_discuss_rounds" tone="manager" />
                  <FlowArrow />
                  <FlowNode title="Risk Judge" subtitle="final_trade_decision + risk_score" tone="decision" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6">
          <h2 className="text-xl font-semibold text-white">Agent-by-Agent Contracts</h2>
          <p className="mt-2 text-sm text-gray-400">
            Exact state contracts for each analyst, researcher, manager, and trader.
          </p>

          <div className="mt-4 space-y-6">
            {CONTRACT_PHASES.map((phase) => (
              <div key={phase.id} className="rounded-2xl border border-gray-700 bg-gray-900/50 p-4 md:p-5">
                <h3 className="text-lg font-semibold text-white">{phase.title}</h3>
                <p className="mt-1 text-sm text-gray-400">{phase.description}</p>

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  {phase.agents.map((agent) => (
                    <AgentContractCard key={agent.id} agent={agent} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-gray-700 bg-gray-900/70 p-6">
          <h2 className="text-xl font-semibold text-white">Final Logged Run Output</h2>
          <p className="mt-2 text-sm text-gray-400">
            Final output structure persisted by `TradingAgentsGraph._log_state(...)`.
          </p>
          <div className="mt-3 rounded-lg border border-gray-700 bg-gray-950/80 p-4">
            <pre className="text-xs text-gray-200 whitespace-pre-wrap break-words">
              {JSON.stringify(FINAL_LOGGED_OUTPUT_SHAPE, null, 2)}
            </pre>
          </div>
        </section>
      </div>
    </div>
  );
}
