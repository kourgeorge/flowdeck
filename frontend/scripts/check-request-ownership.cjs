// Execute production hooks/classes with controlled effects and transports.
// No network, browser, or provider credentials are required.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const compile = file => ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8')
  .replaceAll('import.meta.env', '({ DEV: true })'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
const quiet = {log() {}, error() {}};

async function run() {
  const effects = [], pending = new Map();
  let quote = null;
  const exports = {};
  vm.runInNewContext(compile('src/hooks/useQuoteRefresh.ts'), {
    exports, console: quiet, setInterval: () => 1, clearInterval() {},
    require: name => name === 'react' ? {
      useState: () => [quote, value => { quote = value; }],
      useEffect: fn => effects.push(fn),
    } : {tickerApi: {getQuote: ticker => new Promise(resolve => pending.set(ticker, resolve))}},
  });
  exports.useQuoteRefresh('AAPL', 5000);
  const cleanup = effects.shift()();
  cleanup();
  exports.useQuoteRefresh('NVDA', 5000);
  const finish = effects.shift()();
  pending.get('NVDA')({ticker: 'NVDA', price: 200});
  await Promise.resolve();
  pending.get('AAPL')({ticker: 'AAPL', price: 100});
  await Promise.resolve();
  assert.equal(quote.ticker, 'NVDA');
  finish();

  // Exercise the actual component boundary: ticker/account changes must give
  // React a new child identity, and foreign prefetched data must be discarded.
  let user = {userId: 1};
  const panelExports = {};
  vm.runInNewContext(compile('src/components/TickerDetailPanel.tsx'), {
    exports: panelExports,
    require: name => name === 'react/jsx-runtime'
      ? {jsx: (type, props, key) => ({type, props, key})}
      : name.endsWith('/AuthContext') ? {useAuth: () => ({user})} : {},
  });
  const firstPanel = panelExports.default({ticker: 'AAPL', prefetchedData: {ticker: 'AAPL'}});
  const nextPanel = panelExports.default({ticker: 'NVDA', prefetchedData: {ticker: 'AAPL'}});
  assert.notEqual(firstPanel.key, nextPanel.key);
  assert.equal(nextPanel.props.prefetchedData, null);
  user = {userId: 2};
  assert.notEqual(nextPanel.key, panelExports.default({ticker: 'NVDA'}).key);

  const reportExports = {};
  vm.runInNewContext(compile('src/components/ReportViewer.tsx'), {
    exports: reportExports, require: () => ({}),
  });
  const sensitivity = reportExports.buildDeterministicValuationSensitivityMarkdown;
  assert.match(sensitivity({fcf_growth_rate: {delta_absolute: 0.03, fair_value_low: 80, fair_value_high: 120}}),
    /±3 percentage points -> Fair value range: \$80.00 to \$120.00/);
  assert.match(sensitivity({exit_multiple: {delta: 2, low: 90, high: 110}}), /±2x/);
  assert.match(sensitivity({fcf_growth_rate: null}), /FCF Growth Rate: Unavailable/);

  const timers = [], sockets = [], wsExports = {};
  class Socket {
    constructor() { sockets.push(this); }
    close() {}
  }
  vm.runInNewContext(compile('src/services/websocket.ts'), {
    exports: wsExports, console: quiet, WebSocket: Socket,
    window: {location: {protocol: 'http:', host: 'localhost:5173'}},
    require: () => ({getStoredToken: () => 'test'}),
    setTimeout: fn => { timers.push(fn); return timers.length; }, clearTimeout() {},
  });
  const client = new wsExports.WebSocketClient(1);
  client.connect();
  sockets[0].onclose();
  client.disconnect();
  timers.shift()(); // also prove a callback already queued cannot reopen
  assert.equal(sockets.length, 1);
  console.log('Passed: ticker/account ownership, foreign prefetch, stale quotes, reconnect cleanup, and valuation sensitivity rendering');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
