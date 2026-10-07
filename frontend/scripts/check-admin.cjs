// Isolated execution of production components with controlled hooks/transports.
// No browser, network, or provider credentials are required.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = require('node:path').resolve(__dirname, '..');
const ts = require(root + '/node_modules/typescript');
const jsx = (type, props, key) => ({type, props, key});
const flush = async () => { for (let i=0; i<8; i++) await Promise.resolve(); };
function harness(file, imports, exportName = 'default') {
  const slots = [], effects = [];
  let index = 0;
  const changed = (old, deps) => !old || deps.some((v,i) => v !== old[i]);
  const react = {
    useState(value) {
      const i = index++;
      if (!(i in slots)) slots[i] = typeof value === 'function' ? value() : value;
      return [slots[i], next => { slots[i] = typeof next === 'function' ? next(slots[i]) : next; }];
    },
    useRef(value) { const i=index++; return slots[i] ||= {current: value}; },
    useMemo(fn, deps) {
      const i=index++;
      if (changed(slots[i]?.deps, deps)) slots[i] = {deps, value: fn()};
      return slots[i].value;
    },
    useCallback(fn, deps) { return react.useMemo(() => fn, deps); },
    useEffect(fn, deps) {
      const i=index++;
      if (changed(slots[i]?.deps, deps)) {
        const old = slots[i];
        slots[i] = {deps};
        effects.push(() => { old?.cleanup?.(); slots[i].cleanup = fn(); });
      }
    },
  };
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(root+'/'+file, 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}
  }).outputText, {
    exports, console, URLSearchParams, crypto: require('node:crypto').webcrypto, setInterval: () => 1, clearInterval() {},
    require: name => name === 'react' ? react : name === 'react/jsx-runtime' ? {jsx, jsxs: jsx} : imports(name),
  });
  return {slots, exports, unmount() {slots.forEach(slot => slot?.cleanup?.());}, render(props) {index=0; const tree=exports[exportName](props); effects.splice(0).forEach(fn=>fn()); return tree;}};
}
function nodes(tree) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
async function main() {
  const pending = new Map();
  const api = new Proxy({}, {get: (_, name) => days => new Promise((resolve, reject) => pending.set(name+':'+days, {resolve,reject}))});
  const payload = days => ({period_days:days, operations:[], users:[], daily_data:[], models:[], recommendations:[]});
  const analytics = harness('src/components/admin/AnalyticsTab.tsx', name => name.endsWith('/adminApi') ? {adminApi: api} : {});
  analytics.render({days:30});
  analytics.render({days:7});
  for (const [key, request] of pending) if (key.endsWith(':7')) request.resolve(payload(7));
  await flush();
  assert.equal(analytics.slots[0].period_days, 7);
  for (const [key, request] of pending) if (key.endsWith(':30')) request.resolve(payload(30));
  await flush();
  assert.equal(analytics.slots[0].period_days, 7);
  analytics.render({days:90});
  for (const [key, request] of pending) if (key.endsWith(':90')) {
    if (key.startsWith('getAnalyticsRecommendations')) request.reject(new Error('temporary'));
    else request.resolve(payload(90));
  }
  await flush();
  const partial = analytics.render({days:90});
  assert.equal(analytics.slots[0].period_days, 90);
  assert(JSON.stringify(partial).includes('Could not load recommendations'));
  analytics.unmount();

  let userCalls = [];
  let params = new URLSearchParams();
  let currentUser = {userId:1,is_admin:true};
  const setParams = fn => {params = fn(params);};
  const dashboardApi = {
    getStats: async () => ({total_users:101}),
    getReports: async () => ({reports:[], total:0}),
    getAnalyses: async () => ({analyses:[], total:0}),
    getAnalysesDaily: async () => ({data:[{date:'2026-10-06',count:1}]}),
    getViewsDaily: async () => ({data:[]}),
    getUsers: async (limit, offset, search) => {
      userCalls.push({limit, offset, search});
      if (userCalls.length === 1) throw new Error('temporary users failure');
      return {users:[{id: offset + 2,email:'user@example.test',token_balance:1500}],total:101};
    },
    getSubscriptions: async () => ({subscriptions:[], total:0}),
    getViewRuns: async () => ({runs:[], total_runs_with_views:0}),
  };
  const dashboard = harness('src/pages/AdminDashboardPage.tsx', name => {
    if (name.endsWith('/adminApi')) return {adminApi:dashboardApi};
    if (name.endsWith('/AuthContext')) return {useAuth:()=>({user:currentUser})};
    if (name === 'react-router-dom') return {useSearchParams:()=>[params,setParams], Link:'Link', Navigate:'Navigate'};
    return {default: name.split('/').pop()};
  }, 'AdminDashboardContent');
  const firstBoundary = dashboard.exports.default();
  currentUser = {userId:2,is_admin:true};
  assert.notEqual(dashboard.exports.default().key, firstBoundary.key);
  currentUser = null;
  assert.notEqual(dashboard.exports.default().type, dashboard.exports.AdminDashboardContent);
  currentUser = {userId:1,is_admin:true};
  dashboard.render(); await flush();
  let tree=dashboard.render();
  function click(label) {nodes(tree).find(n=>n.type==='button' && n.props.children===label).props.onClick(); tree=dashboard.render();}
  assert.equal(nodes(tree).find(n=>n.type==='OverviewTab').props.dailyAnalyses.length, 1);
  click('Users'); await flush(); tree=dashboard.render();
  assert.equal(userCalls.length, 1);
  assert.equal(nodes(tree).find(n=>n.type==='UsersTab').props.users.length, 0);
  assert(JSON.stringify(tree).includes('Could not load users'));
  click('Overview'); click('Users'); await flush(); tree=dashboard.render();
  assert.equal(userCalls.length, 2);
  assert.equal(nodes(tree).find(n=>n.type==='UsersTab').props.users.length, 1);
  nodes(tree).find(n=>n.type==='UsersTab').props.usersPagination.props.onChange(50);
  dashboard.render(); await flush(); tree=dashboard.render();
  assert.equal(userCalls.at(-1).offset, 50);
  nodes(tree).find(n=>n.type==='input' && n.props['aria-label']==='Search users').props.onChange({target:{value:'older'}});
  dashboard.render(); await flush(); tree=dashboard.render();
  assert.deepEqual(userCalls.at(-1), {limit:50,offset:0,search:'older'});
  dashboard.unmount();

  // Drive the actual token button: invalid input never sends; an uncertain
  // failure retries the same request identity, and a new grant gets a new one.
  const calls=[];
  let usersProps = {
    ...nodes(tree).find(n=>n.type==='UsersTab').props,
    addAmountByUser:{2:'0'}, users:[{id:2,email:'u@test',token_balance:1000,created_at:'2026-01-01'}],
    setUsers() {}, setAddTokensError() {}, setAddingForUserId() {},
  };
  const users = harness('src/components/admin/UsersTab.tsx', name => {
    if (name.endsWith('/adminApi')) return {adminApi:{addTokensToUser:async (...args) => {
      calls.push(args); if (calls.length===1) throw new Error('uncertain response'); return {token_balance:1500};
    }}};
    if (name.endsWith('/adminUtils')) return {formatDate: value=>value};
    return {};
  });
  let usersTree=users.render(usersProps);
  const grantButton = () => nodes(usersTree).find(n=>n.type==='button' && n.props.children==='Add tokens');
  assert(grantButton().props.disabled);
  await grantButton().props.onClick(); assert.equal(calls.length,0);
  usersProps={...usersProps,addAmountByUser:{2:'500'}};
  usersTree=users.render(usersProps);
  await grantButton().props.onClick();
  await grantButton().props.onClick();
  assert.equal(calls[0][2],calls[1][2]);
  await grantButton().props.onClick();
  assert.notEqual(calls[1][2],calls[2][2]);
  assert(nodes(usersTree).find(n=>n.props?.['aria-label']==='Delete user u@test').props.disabled === false);
  console.log('Passed: admin account ownership, stale/partial analytics, users retry and pagination, activity loading, grant validation and retry identity.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
