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
    tools: ['get_ticker_data', 'get_ticker_quote', 'get_indicators'],
    emits: ['messages', 'market_report', 'market_score'],
    outputShape: analystOutputShape('market_report', 'market_score'),
  },
  {
    id: 'social-analyst',
    name: 'News & Sentiment Analyst',
    kind: 'Analyst',
    selectedByDefault: 'Yes',
    consumes: ['trade_date', 'company_of_interest', 'messages'],
    tools: ['get_ticker_quote', 'get_events', 'get_news', 'get_global_news', 'get_insider_transactions', 'get_reddit_company_social', 'get_polymarket_sentiment'],
    emits: ['messages', 'sentiment_report', 'sentiment_score'],
    outputShape: analystOutputShape('sentiment_report', 'sentiment_score'),
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
      'get_ticker_data',
      'get_ticker_quote',
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
        neutral_history: '<string>',
        latest_speaker: 'Bull',
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
        neutral_history: '<string>',
        latest_speaker: 'Bear',
        current_response: 'Bear Analyst: <string>',
        count: '<int>',
      },
    },
  },
  {
    id: 'neutral-researcher',
    name: 'Neutral Researcher',
    kind: 'Researcher',
    selectedByDefault: 'Always',
    consumes: [
      'market_report',
      'sentiment_report',
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
        neutral_history: '<string>',
        latest_speaker: 'Neutral',
        current_response: 'Neutral Analyst: <string>',
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
      'fundamentals_report',
      'sec_report',
      'technical_report',
    ],
    emits: [
      'investment_debate_state',
      'investment_plan',
      'recommendation',
      'recommendation_score',
      'bull_summary',
      'bear_summary',
      'neutral_summary',
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
        neutral_history: '<string>',
        latest_speaker: '<string>',
        current_response: '<string>',
        count: '<int>',
      },
      investment_plan: '<string>',
      recommendation: 'BUY | SELL | HOLD',
      recommendation_score: '<int 1-10 | null>',
      bull_summary: ['<string>'],
      bear_summary: ['<string>'],
      neutral_summary: ['<string>'],
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
      'fundamentals_report',
    ],
    emits: ['messages', 'trader_investment_plan', 'trader_recommendation', 'trader_tps_plan', 'trader_key_takeaways', 'sender'],
    outputShape: {
      messages: [{ type: 'AIMessage', content: '<trader_investment_plan>' }],
      trader_investment_plan: '<string>',
      trader_recommendation: 'BUY | SELL | HOLD | null',
      trader_tps_plan: '<TPS JSON string>',
      trader_key_takeaways: ['<string>'],
      sender: 'Trader',
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
      'Specialized analysts gather market, news & sentiment, fundamentals, technical, and SEC/regulatory evidence.',
    agents: selectContracts([
      'market-analyst',
      'social-analyst',
      'fundamentals-analyst',
      'technical-analyst',
      'sec-analyst',
    ]),
  },
  {
    id: 'phase-2-investment',
    title: 'Phase 2: Bull/Bear/Neutral Debate + Plan',
    description:
      'Bull, bear, and neutral researchers debate in round-robin, then the research manager weighs all three sides and emits the investment plan with the authoritative BUY/SELL/HOLD recommendation. The trader then turns it into an executable plan (TPS).',
    agents: selectContracts(['bull-researcher', 'bear-researcher', 'neutral-researcher', 'research-manager', 'trader']),
  },
];

// Briefing Agent workflow stages
const BRIEFING_STAGES = [
  {
    id: 'context-builder',
    title: 'Context Builder',
    description: 'Algorithmic stage that loads portfolio, fetches market data, ranks tickers by attention score, and builds comprehensive context.',
    inputs: ['user_id', 'digest_date', 'portfolio_tickers', 'span_type (daily/weekly/custom)'],
    outputs: ['DigestContext with quotes, returns, news, fundamentals, platform reports, market movers, sector/peer data'],
    isAlgorithmic: true,
  },
  {
    id: 'focus-selector',
    title: 'Focus Selector Agent',
    description: 'LLM agent that determines which tickers to focus on based on attention scores, user preferences, and portfolio context.',
    inputs: ['portfolio_tickers', 'attention_scores', 'user_note', 'user_focus_tickers'],
    outputs: ['focus_tickers (ordered list of priority tickers)'],
    isAlgorithmic: false,
  },
  {
    id: 'ticker-interpreter',
    title: 'Ticker Interpreter Agent',
    description: 'LLM agent that analyzes each priority ticker to explain what happened, identify the main driver, and compare to platform thesis.',
    inputs: ['ticker', 'quote', 'returns', 'news', 'fundamentals', 'platform_reports', 'sector/peer context'],
    outputs: ['TickerInterpretation (explanation, driver classification, thesis comparison)'],
    isAlgorithmic: false,
  },
  {
    id: 'market-interpreter',
    title: 'Market Interpreter Agent',
    description: 'LLM agent that synthesizes market-wide context and explains relevance to the portfolio.',
    inputs: ['market_movers', 'global_news', 'ticker_interpretations', 'portfolio_tickers'],
    outputs: ['MarketInterpretation (market summary, portfolio relevance)'],
    isAlgorithmic: false,
  },
  {
    id: 'narrative-writer',
    title: 'Narrative Writer Agent',
    description: 'LLM agent that composes the final brief narrative with market highlights, key signals, what to watch, and risks/opportunities.',
    inputs: ['ticker_interpretations', 'market_interpretation', 'user_note', 'narrative_style', 'resources'],
    outputs: ['narrative (structured or basic format)', 'what_to_watch', 'references'],
    isAlgorithmic: false,
  },
];

const FINAL_LOGGED_OUTPUT_SHAPE = {
  company_of_interest: '<string>',
  trade_date: '<YYYY-MM-DD>',
  market_report: '<string>',
  market_score: '<int | null>',
  sentiment_report: '<string>',
  sentiment_score: '<int | null>',
  fundamentals_report: '<string>',
  fundamentals_score: '<int | null>',
  sec_report: '<string>',
  sec_score: '<int | null>',
  technical_report: '<string>',
  technical_score: '<int | null>',
  investment_debate_state: {
    bull_history: '<string>',
    bear_history: '<string>',
    neutral_history: '<string>',
    history: '<string>',
    current_response: '<string>',
    judge_decision: '<string>',
  },
  trader_investment_decision: '<string>',
  trader_tps_plan: '<TPS JSON string>',
  investment_plan: '<string>',
  recommendation: 'BUY | SELL | HOLD',
  recommendation_score: '<int | null>',
  expected_return_pct: '<number | null>',
  bear_case_return_pct: '<number | null>',
  bull_case_return_pct: '<number | null>',
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
  return <span className="text-xs text-gray-400 px-1">→</span>;
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
          <p className="text-xs uppercase tracking-[0.2em] text-blue-300">AI Architecture</p>
          <h1 className="mt-2 text-3xl md:text-4xl font-bold text-white">Architecture Blueprint</h1>
          <p className="mt-3 text-sm text-gray-300 max-w-3xl">
            FlowDeck uses two complementary AI systems: the <strong>TradingAgents Graph</strong> for deep stock analysis 
            and the <strong>Briefing Agent</strong> for personalized daily portfolio briefs.
          </p>
        </section>

        {/* Briefing Agent Section */}
        <section className="mt-6 rounded-2xl border border-gray-700 bg-gray-900/70 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-purple-500/20 p-2">
              <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-white">Briefing Agent</h2>
              <p className="text-sm text-gray-400">User Daily Brief Pipeline</p>
            </div>
          </div>

          <p className="text-sm text-gray-300 mb-4">
            The Briefing Agent generates personalized daily (or weekly/custom) portfolio briefs by combining algorithmic 
            context building with specialized LLM agents. It analyzes your subscribed stocks, identifies priority tickers 
            based on attention scores, and produces a concise narrative with market context and actionable insights.
          </p>

          <div className="mt-5 space-y-4">
            <h3 className="text-lg font-semibold text-white">Pipeline Stages</h3>
            
            {BRIEFING_STAGES.map((stage, idx) => (
              <div 
                key={stage.id} 
                className={`rounded-xl border p-4 ${
                  stage.isAlgorithmic 
                    ? 'border-sky-500/40 bg-sky-500/10' 
                    : 'border-purple-500/40 bg-purple-500/10'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`rounded-full px-2 py-1 text-xs font-semibold ${
                    stage.isAlgorithmic ? 'bg-sky-500/20 text-sky-300' : 'bg-purple-500/20 text-purple-300'
                  }`}>
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-base font-semibold text-white">{stage.title}</h4>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        stage.isAlgorithmic 
                          ? 'bg-sky-500/20 text-sky-300' 
                          : 'bg-purple-500/20 text-purple-300'
                      }`}>
                        {stage.isAlgorithmic ? 'Algorithmic' : 'LLM Agent'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-300 mt-2">{stage.description}</p>
                    
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-gray-400 mb-1">Inputs</p>
                        <ul className="text-xs text-gray-200 space-y-1">
                          {stage.inputs.map((input, i) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-gray-500">•</span>
                              <span>{input}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-gray-400 mb-1">Outputs</p>
                        <ul className="text-xs text-gray-200 space-y-1">
                          {stage.outputs.map((output, i) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-gray-500">•</span>
                              <span>{output}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-lg border border-gray-700 bg-gray-950/80 p-4">
            <h4 className="text-sm font-semibold text-white mb-2">Key Features</h4>
            <ul className="text-xs text-gray-300 space-y-2">
              <li className="flex items-start gap-2">
                <span className="text-purple-400 mt-0.5">✓</span>
                <span><strong>Attention Scoring:</strong> Ranks tickers by absolute returns, abnormal moves, and recent news</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-purple-400 mt-0.5">✓</span>
                <span><strong>Multi-Span Support:</strong> Daily, weekly, or custom date ranges</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-purple-400 mt-0.5">✓</span>
                <span><strong>User Preferences:</strong> Optional user notes, focus tickers, and narrative style</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-purple-400 mt-0.5">✓</span>
                <span><strong>Platform Integration:</strong> References FlowDeck reports and provides shareable URLs</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-purple-400 mt-0.5">✓</span>
                <span><strong>Structured References:</strong> Tracks and cites news articles, feeds, and web sources</span>
              </li>
            </ul>
          </div>
        </section>

        {/* TradingAgents Graph Section */}
        <section className="mt-6 rounded-2xl border border-gray-700 bg-gray-900/70 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="rounded-lg bg-blue-500/20 p-2">
              <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-white">TradingAgents Graph</h2>
              <p className="text-sm text-gray-400">Deep Stock Analysis Pipeline</p>
            </div>
          </div>

          <p className="text-sm text-gray-300 mb-4">
            The TradingAgents Graph performs comprehensive stock analysis through a multi-phase debate system. 
            Specialized analysts gather evidence, bull/bear researchers debate investment merits, and risk analysts 
            evaluate tradeoffs before producing final recommendations.
          </p>

          <p className="text-xs text-gray-400 mb-4">
            Runtime default analyst selection: market → news → fundamentals → technical → sec (US only). 
            Social analyst is available but not selected by default.
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
                  <FlowNode title="News & Sentiment Analyst" subtitle="score + report" tone="analyst" />
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
                  <FlowNode title="Neutral Researcher" subtitle="writes balanced argument" tone="analyst" />
                  <FlowArrow />
                  <FlowNode title="Debate Loop" subtitle="3 * max_debate_rounds" tone="manager" />
                  <FlowArrow />
                  <FlowNode title="Research Manager" subtitle="investment plan + BUY/SELL/HOLD + score + returns" tone="decision" />
                  <FlowArrow />
                  <FlowNode title="Trader" subtitle="trader plan + TPS" tone="decision" />
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

// Made with Bob
