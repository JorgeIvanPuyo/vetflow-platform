const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const ts = require('typescript');
const React = require('react');
require.extensions['.css'] = (module) => { module.exports = {}; };
const root = path.resolve(__dirname, '../..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) { return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args); };
for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(root + path.sep));
    module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText, filename);
  };
}
// Drive real handlers and effects using the existing Node runner, without new packages.
let current;
const hooks = { ...React,
  useMemo(callback, deps) {
    const h = current, i = h.index++, previous = h.values[i];
    if (!previous || deps.some((value, index) => !Object.is(value, previous.deps[index]))) h.values[i] = { value: callback(), deps };
    return h.values[i].value;
  },
  useCallback(callback, deps) {
    const h = current, i = h.index++, previous = h.values[i];
    if (!previous || deps.some((value, index) => !Object.is(value, previous.deps[index]))) h.values[i] = { callback, deps };
    return h.values[i].callback;
  },
  useState(initial) {
    const h = current, i = h.index++;
    if (!(i in h.values)) h.values[i] = initial;
    return [h.values[i], (value) => { h.values[i] = typeof value === 'function' ? value(h.values[i]) : value; }];
  },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useEffect(callback, deps) {
    const h = current, i = h.index++, prev = h.effects[i];
    if (!prev || deps.some((v, j) => !Object.is(v, prev.deps[j]))) h.pending.push(() => {
      prev?.cleanup?.(); h.effects[i] = { deps, cleanup: callback() };
    });
  },
};

const { PageReadRecovery } = require('./page-read-recovery.ts');
const { ApiClientError } = require('../../lib/api.ts');
const { renderToStaticMarkup } = require('react-dom/server');
let url, reads;
const router = { replace(href) { url = new URL(href, url); }, push(href) { url = new URL(href, url); } };
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const read = () => { const request = deferred(); reads.push(request); return request.promise; };
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === 'react') return hooks;
  if (name === 'next/navigation') return { useRouter: () => router, usePathname: () => url.pathname, useSearchParams: () => url.searchParams };
  if (name === '@/features/clinic/clinic-context') return { useClinic: () => ({ preferences: null }) };
  if (name === '@/services/purchases') return { getPurchaseDashboard: read, getPurchaseFilterOptions: async () => ({ data: { creators: [] } }) };
  if (name === '@/services/suppliers') return { getSuppliers: async () => ({ data: [] }) };
  if (name === '@/services/inventory') return { getInventoryDashboard: read, getInventoryFilterOptions: async () => ({ data: { brands: [], suppliers: [] } }) };
  return load.call(this, name, ...args);
};
const { PurchaseDashboardScreen } = require('../purchases/components/purchase-dashboard-screen.tsx');
const { InventoryDashboardScreen } = require('../inventory/components/inventory-dashboard-screen.tsx');
Module._load = load;
const { PageReadStatus } = require('./page-read-boundary.tsx');
function mount(component) {
  const h = { values: [], effects: [], pending: [] };
  h.render = () => { h.index = 0; current = h; h.tree = component(); h.pending.splice(0).forEach(run => run()); };
  h.dispose = () => h.effects.forEach(e => e.cleanup?.());
  h.render(); return h;
}
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
const hasError = h => nodes(h.tree).some(n => n.props?.className === 'error-state');
const hasLoader = h => nodes(h.tree).some(n => n.props?.className === 'loading-card');
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
const refresh = h => nodes(h.tree).find(n => n.type === 'button' && n.props.onClick && JSON.stringify(n.props.children).includes('Actualizar')).props.onClick();
const fixtures = {
  purchases: { generated_at: '2026-09-24T12:00:00Z', summary: {}, attention: [], recent_purchases: [], top_suppliers: [] },
  inventory: { generated_at: '2026-09-24T12:00:00Z', indicators: {}, movement_metrics: {}, valuation: {}, alerts: [], attention_items: [], activity: { recent_movements: [], recent_imports: [], recent_bulk_operations: [] } },
};
function clock() {
  let now = 0, id = 0; const tasks = new Map();
  const original = [global.setTimeout, global.clearTimeout, Date.now];
  Date.now = () => now;
  global.setTimeout = (fn, ms) => { tasks.set(++id, { at: now + ms, fn }); return id; };
  global.clearTimeout = id => tasks.delete(id);
  return {
    async advance(ms) {
      await flush(); const end = now + ms;
      while (true) {
        const next = [...tasks].filter(([, task]) => task.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) break;
        now = next[1].at; tasks.delete(next[0]); next[1].fn(); await flush();
      }
      now = end; await flush();
    },
    get now() { return now; }, get pending() { return tasks.size; },
    restore() { [global.setTimeout, global.clearTimeout, Date.now] = original; },
  };
}


for (const [name, component] of [['purchases', PurchaseDashboardScreen], ['inventory', InventoryDashboardScreen]]) {
  const response = { data: fixtures[name] };
  const reset = () => { reads = []; url = new URL(`http://localhost/${name}/dashboard?date_from=2026-09-01&date_to=2026-09-30`); };
  test(`${name}: initial loading and URL cancellation never show an error; success stays clean`, async () => {
    reset(); url.search = ''; const h = mount(component);
    assert.ok(hasLoader(h)); assert.ok(!hasError(h));
    // Boundary cleanup runs on date normalization before the next passive effect.
    reads[0].reject(new ApiClientError('cancelled', 0, 'read_cancelled'));
    await flush(); h.render(); assert.ok(!hasError(h));
    reads[1].resolve(response); await flush(); h.render();
    assert.ok(!hasError(h)); assert.ok(!hasLoader(h)); h.dispose();
  });
  test(`${name}: stale failure after success cannot restore an alert; permanent failure clears on recovery`, async () => {
    reset(); const h = mount(component); refresh(h);
    reads[1].resolve(response); await flush(); h.render();
    reads[0].reject(new ApiClientError('obsolete failure', 422)); await flush(); h.render(); assert.ok(!hasError(h));
    refresh(h); reads[2].reject(new ApiClientError('invalid filter', 422)); await flush(); h.render(); assert.ok(hasError(h));
    refresh(h); reads[3].resolve(response); await flush(); h.render(); assert.ok(!hasError(h)); h.dispose();
  });
  test(`${name}: real transient error shows countdown, successful retry removes it permanently`, async () => {
    reset(); const time = clock(), manager = new PageReadRecovery(); let state, calls = 0;
    manager.subscribe(value => { state = value; });
    const h = mount(component);
    reads[0].resolve(manager.run('/dashboard', async () => { if (++calls === 1) throw new ApiClientError('offline', 503); return response; }));
    try {
      await flush(); h.render(); assert.equal(state.phase, 'waiting');
      assert.match(renderToStaticMarkup(React.createElement(PageReadStatus, { state, retry() {} })), /Reintento automático/);
      await time.advance(5000); h.render(); assert.equal(state.phase, 'idle'); assert.ok(!hasError(h)); assert.ok(!hasLoader(h)); assert.equal(time.pending, 0);
      await time.advance(60000); h.render(); assert.equal(calls, 2); assert.ok(!hasError(h)); assert.equal(state.phase, 'idle');
    } finally { h.dispose(); manager.dispose(); time.restore(); }
  });
  test(`${name}: unmount during retry cancels timers and prevents late updates`, async () => {
    reset(); const time = clock(), manager = new PageReadRecovery(); let calls = 0;
    const h = mount(component);
    reads[0].resolve(manager.run('/dashboard', async () => { calls++; throw new ApiClientError('offline', 503); }));
    await flush(); h.dispose(); const before = h.values.slice(); manager.dispose();
    try { await time.advance(60000); assert.deepEqual(h.values, before); assert.equal(time.pending, 0); assert.equal(calls, 1); }
    finally { time.restore(); }
  });
}
