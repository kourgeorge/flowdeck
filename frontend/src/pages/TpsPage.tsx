import { Link } from 'react-router-dom';

const FIELD_ROWS = [
  {
    field: 'instrument',
    required: true,
    type: 'string',
    example: 'MAN',
    description: 'Ticker symbol of the instrument being traded.',
  },
  {
    field: 'timeframe',
    required: true,
    type: 'string',
    example: '1D',
    description: 'Candle resolution at which trade rules are evaluated (e.g. 1D, 4H, 15m). Flowdeck analyses use daily (1D) data.',
  },
  {
    field: 'side',
    required: true,
    type: 'long | short',
    example: 'short',
    description: 'Trade direction. "long" for BUY/HOLD-long positions, "short" for SELL/SHORT positions.',
  },
  {
    field: 'entry.near',
    required: true,
    type: 'number or band',
    example: '25.15  or  "25.15 ±1%"',
    description: 'Entry trigger. A single price number, or a price-band string allowing a tolerance zone.',
  },
  {
    field: 'risk.max_loss',
    required: true,
    type: 'percent string',
    example: '"1%"',
    description: 'Maximum allowed portfolio loss for this trade. Default is "1%" when not stated.',
  },
  {
    field: 'risk.stop',
    required: true,
    type: 'number',
    example: '24.00',
    description: 'Hard stop-loss price. Exit immediately when this level is breached.',
  },
  {
    field: 'entry.scale',
    required: false,
    type: 'string',
    example: '"40/30/30"',
    description: 'Tranche allocation of the intended position. "100" means enter all at once; "40/30/30" means three tranches.',
  },
  {
    field: 'entry.confirm',
    required: false,
    type: 'list of strings',
    example: '["rsi < 45", "macd_hist rising_2"]',
    description: 'Confirmation conditions. All must evaluate true before entry is allowed.',
  },
  {
    field: 'risk.max_position',
    required: false,
    type: 'percent string',
    example: '"5%"',
    description: 'Maximum exposure allowed for this instrument as a percentage of portfolio.',
  },
  {
    field: 'risk.invalidate',
    required: false,
    type: 'rule string',
    example: '"close > 28 for 2d -> exit"',
    description: 'Persistence-based exit rule. If the condition holds for N days, the trade thesis is invalidated and the position is exited.',
  },
  {
    field: 'take_profit.tp1',
    required: false,
    type: 'rule string',
    example: '"30.00 sell 50%"',
    description: 'First take-profit target. Sell the specified percentage of the position when price reaches the target.',
  },
  {
    field: 'take_profit.trail',
    required: false,
    type: 'percent string',
    example: '"4%"',
    description: 'Trailing stop distance applied to the remaining position after tp1 is hit.',
  },
  {
    field: 'vol_guard',
    required: false,
    type: 'rule string',
    example: '"atr20 > 1.5x avg -> reduce 30%"',
    description: 'Volatility guard. Reduces exposure when a volatility condition is met.',
  },
  {
    field: 'add_if',
    required: false,
    type: 'rule string',
    example: '"macd bull & close > ma50 -> max_position 7%"',
    description: 'Conditional position increase. Raises the maximum allowed exposure when a condition is met.',
  },
];

const EXAMPLE_JSON = `{
  "instrument": "MAN",
  "timeframe": "1D",
  "side": "short",
  "entry": {
    "near": "25.15 ±1%",
    "confirm": ["rsi > 60", "close < ma20"]
  },
  "risk": {
    "max_loss": "1%",
    "stop": 28.00,
    "max_position": "4%",
    "invalidate": "close > 28 for 2d -> exit"
  },
  "take_profit": {
    "tp1": "22.00 sell 50%",
    "trail": "4%"
  },
  "vol_guard": "atr20 > 1.5x avg -> reduce 30%"
}`;

function JsonLine({ line }: { line: string }) {
  const keyMatch = line.match(/^(\s*)("[\w_]+")(\s*:\s*)(.*)$/);
  if (keyMatch) {
    const [, indent, key, colon, val] = keyMatch;
    const isString = val.startsWith('"');
    const isNumber = /^-?\d/.test(val.trim());
    const isBool = val.trim() === 'true' || val.trim() === 'false';
    const isNull = val.trim() === 'null';
    return (
      <span>
        {indent}
        <span className="text-sky-300">{key}</span>
        <span className="text-slate-400">{colon}</span>
        <span className={
          isString ? 'text-amber-300' :
          isNumber ? 'text-green-300' :
          isBool || isNull ? 'text-purple-300' :
          'text-slate-300'
        }>{val}</span>
        {'\n'}
      </span>
    );
  }
  return <span className="text-slate-400">{line}{'\n'}</span>;
}

export default function TpsPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto text-gray-300">
        <Link
          to="/how-it-works"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to How It Works
        </Link>

        <div className="flex items-center gap-3 mb-2">
          <span className="text-xs font-semibold uppercase tracking-widest text-indigo-400 bg-indigo-900/40 border border-indigo-700/50 rounded px-2 py-0.5">
            TPS v0.1
          </span>
          <h1 className="text-3xl font-bold text-white">Trading Plan Specification</h1>
        </div>
        <p className="text-gray-500 text-sm mb-10">
          A minimal, machine-parseable format that encodes a complete trade plan — direction, entry zone, risk limits, and optional execution rules — in a single structured JSON object.
        </p>

        {/* What is TPS */}
        <div className="space-y-10 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">What Is a TPS Plan?</h2>
            <p className="mb-3">
              After the Trader agent produces its narrative investment plan, Flowdeck automatically generates a <strong className="text-white">TPS (Trading Plan Specification)</strong> — a compact JSON object that captures the same decision in a structured, unambiguous format. You can find it in the <strong className="text-white">Trader tab</strong> of any AI Analysis report.
            </p>
            <p className="mb-3">
              The TPS plan answers the five questions every trade needs: <em>what</em> (instrument), <em>which direction</em> (side), <em>where to enter</em> (entry.near), <em>where to stop out</em> (risk.stop), and <em>how much to risk</em> (risk.max_loss). Optional fields add execution detail: entry confirmation conditions, take-profit targets, trailing stops, volatility guards, and invalidation rules.
            </p>
            <p>
              Because the plan is structured JSON — not prose — it is unambiguous. Every field has a defined type and meaning. The Trader agent fills in the fields using Pydantic-validated structured output, so the plan always conforms to the schema.
            </p>
          </section>

          {/* Where to find it */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">Where to Find It</h2>
            <ol className="list-decimal list-outside pl-5 space-y-2 text-gray-300">
              <li>Open any stock page (e.g. <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs text-green-300">/tickers/MAN</code>).</li>
              <li>Scroll to the <strong className="text-white">AI Analysis</strong> section.</li>
              <li>Click the <strong className="text-white">Trader</strong> tab.</li>
              <li>The TPS plan appears as a syntax-highlighted JSON block below the narrative text.</li>
            </ol>
          </section>

          {/* Example */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">Example Plan</h2>
            <div className="rounded-lg border border-indigo-700/60 bg-indigo-950/30 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-indigo-700/40 bg-indigo-900/30">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-indigo-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <span className="text-xs font-semibold uppercase tracking-widest text-indigo-300">TPS v0.1 — MAN short example</span>
                </div>
                <span className="text-xs text-indigo-500 font-mono">JSON</span>
              </div>
              <div className="p-4">
                <pre className="bg-slate-900 rounded-lg p-4 overflow-x-auto text-sm font-mono leading-relaxed whitespace-pre">
                  {EXAMPLE_JSON.split('\n').map((line, i) => (
                    <JsonLine key={i} line={line} />
                  ))}
                </pre>
              </div>
            </div>
          </section>

          {/* Field reference */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">Field Reference</h2>
            <div className="overflow-x-auto rounded-lg border border-slate-700">
              <table className="min-w-full text-xs border-collapse">
                <thead className="bg-slate-700/80 text-slate-200">
                  <tr>
                    <th className="px-3 py-2.5 text-left font-semibold border-b border-slate-600 w-36">Field</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-b border-slate-600 w-16">Required</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-b border-slate-600 w-28">Type</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-b border-slate-600 w-40">Example</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-b border-slate-600">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {FIELD_ROWS.map((row) => (
                    <tr key={row.field} className="hover:bg-slate-700/30 transition-colors">
                      <td className="px-3 py-2.5 font-mono text-sky-300 align-top">{row.field}</td>
                      <td className="px-3 py-2.5 align-top">
                        {row.required
                          ? <span className="text-green-400 font-semibold">yes</span>
                          : <span className="text-slate-500">no</span>}
                      </td>
                      <td className="px-3 py-2.5 text-amber-300 font-mono align-top whitespace-nowrap">{row.type}</td>
                      <td className="px-3 py-2.5 font-mono text-green-300 align-top whitespace-nowrap">{row.example}</td>
                      <td className="px-3 py-2.5 text-slate-300 align-top">{row.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Rule string syntax */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">Rule String Syntax</h2>
            <p className="mb-3">
              Several optional fields use a <strong className="text-white">rule string</strong> — a compact expression that encodes a condition and an action:
            </p>
            <div className="space-y-3">
              {[
                { label: 'invalidate', pattern: 'CONDITION -> exit', example: 'close > 28 for 2d -> exit', note: 'Exit the trade if the condition persists for N days.' },
                { label: 'take_profit.tp1', pattern: 'PRICE sell PERCENT%', example: '30.00 sell 50%', note: 'Sell the specified percentage when price reaches the target.' },
                { label: 'vol_guard', pattern: 'CONDITION -> reduce PERCENT%', example: 'atr20 > 1.5x avg -> reduce 30%', note: 'Reduce exposure when volatility exceeds a threshold.' },
                { label: 'add_if', pattern: 'CONDITION -> max_position PERCENT%', example: 'macd bull & close > ma50 -> max_position 7%', note: 'Increase max allowed exposure when a condition is met.' },
              ].map((r) => (
                <div key={r.label} className="rounded-lg border border-slate-700 bg-slate-800/60 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <code className="text-sky-300 font-mono text-xs">{r.label}</code>
                    <span className="text-slate-500 text-xs">pattern:</span>
                    <code className="text-slate-400 font-mono text-xs">{r.pattern}</code>
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-slate-500 text-xs">example:</span>
                    <code className="text-green-300 font-mono text-xs">"{r.example}"</code>
                  </div>
                  <p className="text-slate-400 text-xs">{r.note}</p>
                </div>
              ))}
            </div>
          </section>

          {/* How it is generated */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">How It Is Generated</h2>
            <p className="mb-3">
              The TPS plan is produced by the <strong className="text-white">Trader agent</strong> as part of its structured output — in the same LLM call that produces the narrative investment plan. The agent uses <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs text-green-300">with_structured_output</code> with a Pydantic model (<code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs text-green-300">TpsPlan</code>) that mirrors the JSON schema exactly. This means:
            </p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-300 mb-3">
              <li>The LLM fills typed fields, not free-form text — schema compliance is enforced by Pydantic before serialization.</li>
              <li>Required fields (<code className="bg-slate-800 px-1 rounded text-xs text-green-300">instrument</code>, <code className="bg-slate-800 px-1 rounded text-xs text-green-300">timeframe</code>, <code className="bg-slate-800 px-1 rounded text-xs text-green-300">side</code>, <code className="bg-slate-800 px-1 rounded text-xs text-green-300">entry.near</code>, <code className="bg-slate-800 px-1 rounded text-xs text-green-300">risk.stop</code>, <code className="bg-slate-800 px-1 rounded text-xs text-green-300">risk.max_loss</code>) are always present.</li>
              <li>Optional fields are only included when the agent can infer them from the analysis — fabricated prices are never added.</li>
              <li>The validated object is serialized to JSON via <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs text-green-300">json.dumps</code> and stored alongside the narrative report.</li>
            </ul>
            <p>
              The TPS plan is stored in the report database and served through the API as part of the Trader report data. It is displayed in the Trader tab of the AI Analysis section on every stock page.
            </p>
          </section>

          {/* Limitations */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">Limitations & Freshness</h2>
            <p className="mb-3">
              The TPS plan is generated from daily (1D) data — the same resolution used by all Flowdeck analysts. This means:
            </p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-300 mb-3">
              <li><strong className="text-white">Directional thesis</strong> (side, narrative) remains useful for days to weeks — it is based on fundamentals, news, and macro context which change slowly.</li>
              <li><strong className="text-white">Price levels</strong> (entry.near, risk.stop, take_profit.tp1) decay within 1–3 trading days as the market moves. Treat them as reference zones, not exact orders.</li>
              <li>The <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs text-green-300">risk.invalidate</code> rule is designed to auto-expire the plan if the thesis breaks — e.g. <em>"close {'>'} 28 for 2d → exit"</em>.</li>
              <li>A report older than 3–5 trading days should be treated as directional context only. Generate a fresh analysis for updated price levels.</li>
            </ul>
            <p className="text-gray-500 text-xs">
              TPS-YAML v0.1 is an internal specification. The JSON schema is available at <code className="bg-slate-800 px-1 rounded text-xs">backend/TPS/TPS-YAML-v0.1.schema-1.json</code>.
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-gray-700 flex flex-wrap gap-6">
          <Link
            to="/how-it-works"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            ← How It Works
          </Link>
          <Link
            to="/architecture"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            Architecture →
          </Link>
        </div>
      </div>
    </div>
  );
}

// Made with Bob