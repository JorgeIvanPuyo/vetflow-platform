const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const { test } = require('node:test');
const React = require('react'), ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, ...args) { return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args); };
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
};
let current;
const hooks = { ...React,
  useState(initial) { const h = current, i = h.index++; if (!(i in h.values)) h.values[i] = typeof initial === 'function' ? initial() : initial; return [h.values[i], value => { h.values[i] = typeof value === 'function' ? value(h.values[i]) : value; }]; },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useMemo(fn) { return fn(); },
  useEffect(fn, deps) { const h = current, i = h.index++; if (!h.values[i] || deps.some((v, j) => !Object.is(v, h.values[i].deps[j]))) { h.values[i]?.cleanup?.(); h.values[i] = { deps }; h.pending.push(() => { h.values[i].cleanup = fn(); }); } },
};
const load = Module._load;
Module._load = function(name, ...args) {
  if (name === 'react') return hooks;
  if (name === 'next/link') return () => null;
  if (name === 'next/navigation') return { useRouter: () => ({ push: url => current.navigations.push(url) }) };
  if (name === '@/features/clinic/clinic-context') return { useClinic: () => ({ preferences: null }) };
  if (name === './sale-customer-selector') return { SaleCustomerSelector: () => null };
  if (name === './sale-service-selector') return { SaleServiceSelector: () => null };
  return load.call(this, name, ...args);
};
const { SaleFormScreen } = require('./components/sale-form-screen.tsx');
Module._load = load;
const { setAuthTokenProvider } = require('../../lib/api.ts');
function nodes(tree) { if (Array.isArray(tree)) return tree.flatMap(nodes); if (!tree || typeof tree !== 'object') return []; return [tree, ...nodes(tree.props?.children)]; }
function content(tree) { if (Array.isArray(tree)) return tree.map(content).join(''); if (tree && typeof tree === 'object') return content(tree.props?.children); return typeof tree === 'string' || typeof tree === 'number' ? String(tree) : ''; }
const flush = async () => { for (let i = 0; i < 100; i++) await Promise.resolve(); };
const product = stock => ({ id: 'product', line_type: 'product', inventory_item_id: 'product', description_snapshot: 'Alimento', internal_code_snapshot: 'AL-1', unit_snapshot: 'unit', quantity: '5', unit_price_ars: '10', discount_percentage: '0', current_stock: stock });
function setup(t, { saleId = 'draft', stock = '2', service = false, respond } = {}) {
  const oldFetch = global.fetch, oldDocument = global.document, oldWindow = global.window;
  const h = { values: [], pending: [], requests: [], navigations: [] };
  global.document = { addEventListener() {}, removeEventListener() {} };
  global.window = { clearTimeout() {} };
  setAuthTokenProvider(async () => 'test-token');
  global.fetch = async (url, init) => {
    h.requests.push({ url: new URL(url), init });
    if (init.method !== 'GET' && respond) return respond(init);
    return new Response(JSON.stringify({ data: { id: saleId || 'new-sale', status: 'draft', sale_date: '2026-10-02', notes: 'Texto conservado', items: [service ? { ...product(null), id: 'service', line_type: 'service', service_id: null, inventory_item_id: null } : product(stock)] }, meta: {} }), { status: 200 });
  };
  h.render = () => { current = h; h.index = 0; h.tree = SaleFormScreen({ saleId }); h.pending.splice(0).forEach(fn => fn()); return h.tree; };
  h.ready = async () => { h.render(); await flush(); return h.render(); };
  h.submit = () => h.tree.props.onSubmit({ preventDefault() {} });
  h.quantity = value => { nodes(h.tree).find(n => n.type === 'input' && n.props.inputMode === 'numeric').props.onChange({ target: { value } }); h.render(); };
  t.after(() => { h.values.forEach(v => v?.cleanup?.()); global.fetch = oldFetch; global.document = oldDocument; global.window = oldWindow; setAuthTokenProvider(null); });
  return h;
}
for (const saleId of ['', 'draft']) test(`${saleId ? 'edit' : 'create'}: immediate feedback, synchronous guard and detail navigation`, async t => {
  let finish;
  const h = setup(t, { saleId, respond: () => new Promise(resolve => { finish = resolve; }) });
  await h.ready();
  if (!saleId) {
    nodes(h.tree).find(n => content(n).trim() === 'Agregar servicio' && n.type === 'button').props.onClick(); h.render();
    nodes(h.tree).find(n => n.props.onSelect).props.onSelect({ id: 'svc', name: 'Consulta', price: '10' }); h.render();
  }
  const first = h.submit(), second = h.submit();
  const pending = h.render();
  assert.match(content(pending), /Guardando…/);
  assert.equal(nodes(pending).find(n => n.props.type === 'submit').props.disabled, true);
  assert.equal(nodes(pending).find(n => n.type === 'fieldset').props.disabled, true);
  assert.equal(nodes(pending).find(n => n.props.type === 'submit').props['aria-live'], 'polite');
  await flush(); assert.equal(h.requests.filter(r => r.init.method !== 'GET').length, 1);
  finish(new Response(JSON.stringify({ data: { id: saleId || 'new-sale' } }), { status: 200 }));
  await Promise.all([first, second]);
  assert.deepEqual(h.navigations, [`/sales/${saleId || 'new-sale'}`]);
  await h.submit(); assert.equal(h.requests.filter(r => r.init.method !== 'GET').length, 1);
});
test('save error preserves values, enables controls, stays put and allows retry', async t => {
  let attempt = 0;
  const h = setup(t, { respond: () => ++attempt === 1 ? new Response(JSON.stringify({ error: { code: 'validation_error', message: 'No pudimos guardar el borrador.' } }), { status: 422 }) : new Response(JSON.stringify({ data: { id: 'draft' } }), { status: 200 }) });
  await h.ready(); h.quantity('7'); await h.submit(); h.render();
  assert.equal(nodes(h.tree).find(n => n.props.inputMode === 'numeric').props.value, '7');
  assert.equal(nodes(h.tree).find(n => n.type === 'textarea').props.value, 'Texto conservado');
  assert.equal(nodes(h.tree).find(n => n.props.type === 'submit').props.disabled, false);
  assert.equal(nodes(h.tree).find(n => n.type === 'fieldset').props.disabled, false);
  assert.match(content(h.tree), /No pudimos guardar/); assert.deepEqual(h.navigations, []);
  await h.submit(); assert.equal(attempt, 2); assert.deepEqual(h.navigations, ['/sales/draft']);
});
test('warning persists, clears with valid quantity, returns on excess and allows saving', async t => {
  const h = setup(t); await h.ready(); assert.match(content(h.tree), /Stock insuficiente/);
  assert.match(content(h.tree), /Disponible: 2 · En borrador: 5/);
  h.quantity('2'); assert.doesNotMatch(content(h.tree), /Stock insuficiente/);
  h.quantity('5'); assert.match(content(h.tree), /Stock insuficiente/);
  assert.equal(nodes(h.tree).find(n => n.props.className?.includes('sale-stock-warning')).props.role, 'status');
  await h.submit(); assert.deepEqual(h.navigations, ['/sales/draft']);
});
for (const [name, stock, service, warns] of [['sufficient', '5', false, false], ['replenished on reopen', '9', false, false], ['externally reduced', '1', false, true], ['zero stock', '0', false, true], ['service', '0', true, false], ['unknown stock', null, false, false]]) test(name, async t => {
  const h = setup(t, { stock, service }); await h.ready();
  assert.equal(content(h.tree).includes('Stock insuficiente'), warns);
});

test('zero stock warns even for one unit', async t => {
  const h = setup(t, { stock: '0' }); await h.ready(); h.quantity('1');
  assert.match(content(h.tree), /Disponible: 0 · En borrador: 1/);
  assert.equal(nodes(h.tree).find(n => n.props.type === 'submit').props.disabled, false);
});
