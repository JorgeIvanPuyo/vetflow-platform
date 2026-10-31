const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const { test } = require('node:test');
const React = require('react'), ts = require('typescript');
const root = path.resolve(__dirname, '../..');
require.extensions['.css'] = module => { module.exports = {}; };
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, ...args) { return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args); };
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
};
let current, url, history;
const effect = layout => (callback, deps) => {
  const h = current, i = h.index++, prev = h.effects[i];
  if (!prev || deps.some((v, j) => !Object.is(v, prev.deps[j]))) (layout ? h.layout : h.pending).push(() => {
    prev?.cleanup?.(); h.effects[i] = { deps, cleanup: callback() };
  });
};
const hooks = { ...React,
  useState(initial) { const h = current, i = h.index++; if (!(i in h.values)) h.values[i] = typeof initial === 'function' ? initial() : initial; return [h.values[i], value => { h.values[i] = typeof value === 'function' ? value(h.values[i]) : value; }]; },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useMemo(fn, deps) { const h = current, i = h.index++, prev = h.values[i]; if (!prev || deps.some((v,j) => !Object.is(v,prev.deps[j]))) h.values[i] = { deps, value: fn() }; return h.values[i].value; },
  useCallback(fn, deps) { return hooks.useMemo(() => fn, deps); },
  useEffect: effect(false), useLayoutEffect: effect(true),
};
const router = { push(href) { history.push(url.href); url = new URL(href, url); }, replace(href) { url = new URL(href, url); }, back() { url = new URL(history.pop()); } };
const load = Module._load;
Module._load = function(name, ...args) {
  if (name === 'react') return hooks;
  if (name === 'next/navigation') return { useRouter: () => router, usePathname: () => url.pathname, useSearchParams: () => url.searchParams };
  if (name === '@/features/clinic/clinic-context') return { useClinic: () => ({ preferences: null }) };
  return load.call(this, name, ...args);
};
const { InventoryScreen } = require('./components/inventory-screen.tsx');
const { InventoryDetailModal } = require('./components/inventory-detail-modal.tsx');
const { InventoryDetail } = require('./components/inventory-detail.tsx');
const { PageReadBoundary } = require('../connectivity/page-read-boundary.tsx');
Module._load = load;
const { setAuthTokenProvider } = require('../../lib/api.ts');
function mount(component, props = {}) {
  const h = { values: [], effects: [], layout: [], pending: [], props };
  h.render = () => { current = h; h.index = 0; h.tree = component(h.props); h.layout.splice(0).forEach(fn => fn()); h.pending.splice(0).forEach(fn => fn()); };
  h.dispose = () => h.effects.forEach(effect => effect?.cleanup?.());
  h.render(); return h;
}
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, predicate) => nodes(h.tree).find(predicate);
const flush = async () => { for (let i = 0; i < 80; i++) await Promise.resolve(); };
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes; }); return { promise, resolve }; };
const context = '/inventory?search=alimento&brand=Marca&page=3&page_size=20&sort_by=name&sort_direction=asc';
const fixture = { id: 'product', name: 'Alimento', internal_code: 'P-1', category: 'food', unit: 'unit', brand: 'Marca', supplier: 'Proveedor', purchase_price_ars: '1000', purchase_tax_rate_percentage: '0', profit_margin_percentage: '30', sale_tax_rate_percentage: '0', sale_price_ars: '1300', current_stock: '2', minimum_stock: '3', round_sale_price: false, is_active: true, pricing_pending: false };
async function setup(t) {
  url = new URL(context, 'http://localhost'); history = [];
  const oldFetch = global.fetch, oldWindow = global.window, oldDocument = global.document;
  global.window = { setTimeout() { return 0; }, clearTimeout() {} };
  global.document = { body: { style: { overflow: '' } }, activeElement: { focus() {} } };
  const state = { item: { ...fixture }, requests: [], patchCount: 0, bulkConfirmCount: 0, failPatch: false, failRead: false, holdLists: false, held: [], aborts: 0 };
  setAuthTokenProvider(async () => 'test-token');
  const response = (data, meta = {}) => new Response(JSON.stringify({ data, meta }), { status: 200 });
  global.fetch = async (href, init) => {
    const target = new URL(href);
    state.requests.push({ target, method: init.method });
    if (init.method === 'PATCH') {
      state.patchCount++;
      if (state.failPatch) return new Response(JSON.stringify({ error: { code: 'validation_error', message: 'Costo inválido' } }), { status: 422 });
      const payload = JSON.parse(init.body);
      state.item = { ...state.item, ...payload, purchase_price_ars: String(payload.purchase_price_ars), profit_margin_percentage: String(payload.profit_margin_percentage), sale_price_ars: String(Number(payload.purchase_price_ars) * (1 + Number(payload.profit_margin_percentage) / 100)) };
      return response(state.item);
    }
    if (init.method === 'POST' && target.pathname.endsWith('/bulk-operations/preview')) {
      state.bulkPreview = { id: 'bulk', status: 'preview', affected_count: 1, unchanged_count: 0, invalid_count: 0, selected_count: 1, excluded_count: 0, items: [] };
      return response(state.bulkPreview, { page: 1, total_pages: 1 });
    }
    if (init.method === 'POST' && target.pathname.endsWith('/bulk-operations/bulk/confirm')) {
      state.bulkConfirmCount++;
      state.item = { ...state.item, profit_margin_percentage: '43', sale_price_ars: '1430' };
      return response({ ...state.bulkPreview, status: 'confirmed' });
    }
    if (target.pathname.endsWith('/items')) {
      if (state.holdLists) {
        const held = deferred(); state.held.push(held);
        init.signal?.addEventListener('abort', () => { state.aborts++; }, { once: true });
        return held.promise; // Deliberately allow a late response even after abort.
      }
      if (state.failRead) return new Response(JSON.stringify({ error: { code: 'read_failed', message: 'Lectura rechazada' } }), { status: 422 });
      const matches = state.item.name.toLowerCase().includes(target.searchParams.get('search')) && state.item.brand === target.searchParams.get('brand');
      return response(matches ? [state.item] : [], { page: Number(target.searchParams.get('page')), page_size: 20, total: matches ? 100 : 0, total_pages: matches ? 5 : 0 });
    }
    if (target.pathname.endsWith('/summary')) return response({ total_items: 1, low_stock_count: state.item.minimum_stock === 0 ? 0 : 1 });
    if (target.pathname.endsWith('/filter-options')) return response({ brands: [state.item.brand], suppliers: [state.item.supplier] });
    if (target.pathname.endsWith('/movements')) return response([], { page: 1, total_pages: 1 });
    if (target.pathname.endsWith('/items/product')) return response(state.item);
    throw new Error(`Unexpected request ${target.pathname}`);
  };
  const boundary = mount(PageReadBoundary, { children: null });
  const screen = mount(InventoryScreen);
  const mounted = [boundary, screen];
  state.commit = async () => { boundary.render(); screen.render(); await flush(); screen.render(); };
  state.open = async () => {
    const link = find(screen, n => n.props?.href?.startsWith('/inventory/product?'));
    link.props.onClick({ button: 0, preventDefault() {} });
    await state.commit();
    const modalNode = find(screen, n => n.type === InventoryDetailModal);
    const modal = mount(InventoryDetailModal, modalNode.props); mounted.push(modal);
    const detailNode = find(modal, n => n.type === InventoryDetail);
    const detail = mount(InventoryDetail, detailNode.props); mounted.push(detail);
    await flush(); detail.render();
    find(detail, n => n.type === 'button' && text(n).trim() === 'Editar').props.onClick(); detail.render();
    state.detail = detail;
    state.form = () => find(detail, n => n.props.submitLabel === 'Guardar cambios');
  };
  state.screen = screen;
  t.after(() => {
    mounted.reverse().forEach(h => h.dispose());
    state.held.forEach(held => held.resolve(response([], { page: 3, page_size: 20, total: 0, total_pages: 0 })));
    setAuthTokenProvider(null); global.fetch = oldFetch; global.window = oldWindow; global.document = oldDocument;
  });
  await flush(); screen.render();
  return state;
}

test('PATCH → URL close disposes old reads and refreshes list, summary, filters and reopened detail', async t => {
  const s = await setup(t);
  s.holdLists = true;
  await s.open();
  assert.ok(s.held.length > 0);
  s.form().props.onChange({ ...s.form().props.formState, purchase_price_ars: '1200', minimum_stock: '0', supplier: 'Nuevo' }); s.detail.render();
  await s.form().props.onSubmit({ preventDefault() {} });
  assert.equal(s.patchCount, 1);
  assert.equal(url.searchParams.has('item'), false);
  s.holdLists = false;
  await s.commit();
  assert.ok(s.aborts > 0, 'PageReadBoundary must cancel the old URL scope');
  const finalReads = s.requests.filter(r => r.method === 'GET' && r.target.pathname.endsWith('/items'));
  assert.equal(finalReads.at(-1).target.searchParams.get('page'), '3');
  assert.equal(finalReads.at(-1).target.searchParams.get('brand'), 'Marca');
  assert.match(text(s.screen.tree), /1[.,]560/);
  assert.match(text(s.screen.tree), /Bajo stock0/);
  assert.ok(s.requests.filter(r => r.target.pathname.endsWith('/filter-options')).length >= 3);
  assert.doesNotMatch(text(s.screen.tree), /Carga cancelada|No pudimos actualizar/);
  s.held.forEach(held => held.resolve(new Response(JSON.stringify({ data: [{ ...fixture, sale_price_ars: '1' }], meta: { page: 3, page_size: 20, total: 1, total_pages: 1 } }), { status: 200 })));
  await flush(); s.screen.render();
  assert.match(text(s.screen.tree), /1[.,]560/);
  assert.doesNotMatch(text(s.screen.tree), /Venta:.*\$.*1,00/);
  await s.open();
  assert.equal(s.form().props.formState.purchase_price_ars, '1200');
  assert.equal(s.form().props.formState.supplier, 'Nuevo');
  assert.equal(s.patchCount, 1);
});

test('saved product leaving the active filter disappears without losing pagination', async t => {
  const s = await setup(t); await s.open();
  s.form().props.onChange({ ...s.form().props.formState, brand: 'Otra' }); s.detail.render();
  await s.form().props.onSubmit({ preventDefault() {} }); await s.commit();
  assert.equal(url.searchParams.get('brand'), 'Marca');
  assert.equal(url.searchParams.get('page'), '3');
  assert.equal(find(s.screen, n => n.props?.href?.startsWith('/inventory/product?')), undefined);
  assert.equal(s.patchCount, 1);
});

test('PATCH failure keeps editing and permits one intentional retry', async t => {
  const s = await setup(t); await s.open(); s.failPatch = true;
  await s.form().props.onSubmit({ preventDefault() {} }); s.detail.render();
  assert.ok(s.form()); assert.match(s.form().props.flowMessage, /Costo inválido/);
  assert.equal(url.searchParams.get('item'), 'product'); assert.equal(s.patchCount, 1);
  s.failPatch = false;
  await s.form().props.onSubmit({ preventDefault() {} }); await s.commit();
  assert.equal(s.patchCount, 2); assert.equal(url.searchParams.has('item'), false);
});

test('read failure after successful save retries reads without repeating PATCH', async t => {
  const s = await setup(t); await s.open();
  await s.form().props.onSubmit({ preventDefault() {} });
  s.failRead = true; await s.commit();
  assert.match(text(s.screen.tree), /Los cambios se guardaron.*Lectura rechazada/);
  s.failRead = false;
  find(s.screen, n => n.type === 'button' && text(n).trim() === 'Reintentar').props.onClick();
  await flush(); s.screen.render();
  assert.doesNotMatch(text(s.screen.tree), /Lectura rechazada/);
  assert.equal(s.patchCount, 1);
});


test('closing without saving cancels the old URL reads and obtains a final list', async t => {
  const s = await setup(t); s.holdLists = true; await s.open();
  const modal = find(s.screen, n => n.type === InventoryDetailModal);
  modal.props.onClose(); s.holdLists = false; await s.commit();
  assert.ok(s.aborts > 0);
  assert.doesNotMatch(text(s.screen.tree), /Carga cancelada|No pudimos actualizar/);
  assert.equal(s.patchCount, 0);
  assert.ok(find(s.screen, n => n.props?.href?.startsWith('/inventory/product?')));
});

test('bulk confirmation obtains new reads instead of sharing a pending older GET in the same scope', async t => {
  const s = await setup(t);
  url.searchParams.set('sort_direction', 'desc'); s.holdLists = true; await s.commit();
  assert.ok(s.held.length > 0);
  const button = label => find(s.screen, n => n.type === 'button' && text(n).trim() === label);
  button('Seleccionar esta página').props.onClick(); s.screen.render();
  button('Editar grupo').props.onClick(); s.screen.render();
  find(s.screen, n => n.type === 'input' && n.props.placeholder === 'Porcentaje').props.onChange({ target: { value: '10' } }); s.screen.render();
  await button('Simular').props.onClick(); await flush(); s.screen.render();
  s.holdLists = false;
  await button('Confirmar 1 productos').props.onClick(); await flush(); s.screen.render();
  assert.equal(s.bulkConfirmCount, 1);
  assert.equal(s.patchCount, 0);
  assert.match(text(s.screen.tree), /1[.,]430/);
  assert.equal(url.searchParams.get('sort_direction'), 'desc');
  s.held.forEach(held => held.resolve(new Response(JSON.stringify({ data: [fixture], meta: { page: 3, page_size: 20, total: 100, total_pages: 5 } }), { status: 200 })));
  await flush(); s.screen.render();
  assert.match(text(s.screen.tree), /1[.,]430/);
  assert.equal(s.bulkConfirmCount, 1);
});
