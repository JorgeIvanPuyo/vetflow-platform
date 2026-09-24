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

let url, navigations, requests, savedItem, failSave;
const timers = new Map();
let timerId = 0;
global.window = {
  setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
  clearTimeout(id) { timers.delete(id); },
};
const router = {
  push(href) { navigations.push(href); url = new URL(href, 'http://localhost'); },
  replace(href) { navigations.push(href); url = new URL(href, 'http://localhost'); },
};
const fixture = {
  id: 'product-1', internal_code: 'P001', name: 'Alimento', category: 'food', unit: 'unit',
  current_stock: '10', minimum_stock: '2', profit_margin_percentage: '20',
  sale_price_ars: '120', purchase_price_ars: '100', is_active: true,
};
const api = {
  async getInventorySummary() { return { data: {} }; },
  async getInventoryFilterOptions() { return { data: { brands: [], suppliers: [] } }; },
  async getInventoryItems(filters) {
    requests.push(filters);
    return { data: [savedItem], meta: { page: filters.page, page_size: filters.page_size, total: 200, total_pages: 10 } };
  },
  async getInventoryItem() { return { data: savedItem }; },
  async getInventoryMovements() { return { data: [], meta: { page: 1, total_pages: 1 } }; },
  async updateInventoryItem(id, payload) {
    assert.equal(id, fixture.id);
    if (failSave) throw new Error('Save failed');
    savedItem = { ...savedItem, ...payload };
    return { data: savedItem };
  },
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === 'react') return hooks;
  if (name === 'next/navigation') return {
    useRouter: () => router, usePathname: () => url.pathname, useSearchParams: () => url.searchParams,
  };
  if (name === '@/features/clinic/clinic-context') return { useClinic: () => ({ preferences: null }) };
  if (name === '@/services/inventory') return api;
  return load.call(this, name, ...args);
};
const { InventoryScreen } = require('./components/inventory-screen.tsx');
const { InventoryDetail } = require('./components/inventory-detail.tsx');
const { InventoryPrintDialog } = require('./components/inventory-print-dialog.tsx');
Module._load = load;
function mount(component, props) {
  const h = { values: [], effects: [], pending: [], props };
  h.render = () => { h.index = 0; current = h; h.tree = component(h.props); h.pending.splice(0).forEach((run) => run()); };
  h.dispose = () => h.effects.forEach((e) => e.cleanup?.());
  h.render(); return h;
}
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, predicate) => nodes(h.tree).find(predicate);
const tick = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };


const context = '/inventory?search=alimento+%26+gato&category=food&brand=Marca&supplier=Proveedor&stock_status=low_stock&is_active=false&sort_by=sale_price_ars&sort_direction=desc&page=3&page_size=50';
function reset(href = context) {
  url = new URL(href, 'http://localhost'); navigations = []; requests = [];
  savedItem = { ...fixture }; failSave = false; timers.clear();
}
async function settle(h) {
  await tick(); h.render(); await tick(); h.render();
  for (const [id, callback] of [...timers]) { timers.delete(id); callback(); }
  await tick(); h.render();
}
function click(h, label) {
  const button = find(h, n => n.type === 'button' && text(n).trim() === label);
  assert.ok(button, label); button.props.onClick(); h.render();
}
const search = h => find(h, n => n.props?.placeholder === 'Buscar por nombre o código...');
const detailLink = h => find(h, n => n.props?.href?.startsWith('/inventory/product-1?'));
const editForm = h => find(h, n => n.props?.submitLabel && n.props?.onCancel);

for (const view of ['Tarjetas', 'Tabla']) {
  test(`URL reconstruction and detail return retain filters, search, page and order in ${view}`, async () => {
    reset(); const h = mount(InventoryScreen); await settle(h);
    if (view === 'Tabla') click(h, view);
    assert.equal(search(h).props.value, 'alimento & gato');
    assert.equal(navigations.length, 0);
    const filters = requests.at(-1);
    assert.equal(filters.search, 'alimento & gato'); assert.equal(filters.category, 'food');
    assert.equal(filters.brand, 'Marca'); assert.equal(filters.supplier, 'Proveedor');
    assert.equal(filters.stock_status, 'low_stock'); assert.equal(filters.is_active, false);
    assert.equal(filters.page, 3); assert.equal(filters.page_size, 50);
    assert.equal(filters.sort_by, 'sale_price_ars'); assert.equal(filters.sort_direction, 'desc');
    url = new URL(detailLink(h).props.href, url); h.dispose();
    const detail = mount(InventoryDetail, { itemId: fixture.id }); await settle(detail);
    const back = find(detail, n => n.props?.className === 'back-link');
    assert.equal(back.props.href, context);
    router.push(back.props.href); detail.dispose();
    const returned = mount(InventoryScreen); await settle(returned);
    assert.deepEqual(requests.at(-1), filters);
    assert.equal(url.pathname + url.search, context); returned.dispose();
  });
}

test('browser history changes restore URL search without stale debounce or page reset', async () => {
  reset(); const h = mount(InventoryScreen); await settle(h);
  search(h).props.onChange({ target: { value: 'draft' } }); h.render();
  url = new URL('/inventory?search=otro&page=5&page_size=20&sort_by=name&sort_direction=asc', url);
  await settle(h);
  assert.equal(search(h).props.value, 'otro'); assert.equal(requests.at(-1).page, 5);
  url = new URL(context, url); await settle(h);
  assert.equal(search(h).props.value, 'alimento & gato'); assert.equal(requests.at(-1).page, 3);
  assert.equal(navigations.length, 0); h.dispose();
});

for (const action of ['cancel', 'save']) {
  test(`${action} editing returns to the same list and reloads current data`, async () => {
    reset('/inventory/product-1?return_to=' + encodeURIComponent(context));
    const h = mount(InventoryDetail, { itemId: fixture.id }); await settle(h); click(h, 'Editar');
    const form = editForm(h); assert.ok(form);
    if (action === 'cancel') form.props.onCancel();
    else {
      form.props.onChange({ ...form.props.formState, name: 'Alimento actualizado' }); h.render();
      await editForm(h).props.onSubmit({ preventDefault() {} });
    }
    assert.equal(navigations.at(-1), context); h.dispose();
    const list = mount(InventoryScreen); await settle(list);
    assert.equal(requests.at(-1).page, 3); assert.equal(requests.at(-1).search, 'alimento & gato');
    assert.ok(text(list.tree).includes(action === 'save' ? 'Alimento actualizado' : 'Alimento'));
    assert.equal(url.pathname + url.search, context); list.dispose();
  });
}

test('failed save stays in editing with its return context', async () => {
  reset('/inventory/product-1?return_to=' + encodeURIComponent(context)); failSave = true;
  const h = mount(InventoryDetail, { itemId: fixture.id }); await settle(h); click(h, 'Editar');
  await editForm(h).props.onSubmit({ preventDefault() {} }); h.render();
  assert.equal(navigations.length, 0); assert.ok(editForm(h)); h.dispose();
});

test('normal inventory entry uses defaults; typing and clearing filters still work', async () => {
  reset('/inventory'); const h = mount(InventoryScreen); await settle(h);
  assert.equal(search(h).props.value, ''); assert.equal(requests.at(-1).page, 1);
  assert.equal(requests.at(-1).page_size, 20); assert.equal(requests.at(-1).sort_by, 'name');
  search(h).props.onChange({ target: { value: 'nuevo' } }); await settle(h);
  assert.equal(url.searchParams.get('search'), 'nuevo'); assert.equal(url.searchParams.get('page'), '1');
  url = new URL(context, url); await settle(h); click(h, 'Limpiar'); await settle(h);
  for (const key of ['search', 'category', 'brand', 'supplier', 'stock_status', 'is_active', 'status']) assert.equal(url.searchParams.has(key), false);
  assert.equal(search(h).props.value, ''); assert.equal(requests.at(-1).page, 1);
  assert.equal(requests.at(-1).page_size, 20); assert.equal(requests.at(-1).sort_by, 'name');
  assert.equal(requests.at(-1).sort_direction, 'asc'); h.dispose();
});

test('detail entered without context returns to the standard inventory route', async () => {
  reset('/inventory/product-1'); const h = mount(InventoryDetail, { itemId: fixture.id }); await settle(h);
  assert.equal(find(h, n => n.props?.className === 'back-link').props.href, '/inventory');
  click(h, 'Editar'); editForm(h).props.onCancel(); assert.equal(navigations.at(-1), '/inventory'); h.dispose();
});


test('print action passes current filters and closing preserves list URL, search and page', async () => {
  reset(); const h = mount(InventoryScreen); await settle(h);
  click(h, 'Imprimir inventario');
  const dialog = find(h, n => n.type === InventoryPrintDialog);
  assert.ok(dialog); assert.deepEqual(dialog.props.filters, requests.at(-1));
  dialog.props.onClose(); h.render();
  assert.equal(find(h, n => n.type === InventoryPrintDialog), undefined);
  assert.equal(url.pathname + url.search, context);
  assert.equal(search(h).props.value, 'alimento & gato');
  assert.equal(navigations.length, 0); h.dispose();
});

test('print dialog selects columns, previews all rows and invokes only the frame print dialog', async () => {
  reset();
  const original = api.getInventoryItems;
  const previousDocument = global.document;
  global.document = { activeElement: { focus() {} } };
  let closed = false, printed = 0;
  api.getInventoryItems = async () => ({ data: [fixture], meta: { total: 1 } });
  const h = mount(InventoryPrintDialog, { filters: { search: 'Alimento', page: 3 }, onClose() { closed = true; } });
  const boxes = () => nodes(h.tree).filter(n => n.type === 'input' && n.props.type === 'checkbox');
  try {
    assert.deepEqual(boxes().map(n => n.props.checked), [true, true, false, false, false, false, false, false, false, false]);
    boxes()[0].props.onChange(); h.render(); boxes()[1].props.onChange(); h.render();
    assert.equal(find(h, n => n.type === 'button' && text(n).trim() === 'Vista previa').props.disabled, true);
    boxes()[0].props.onChange(); h.render(); boxes()[6].props.onChange(); h.render();
    click(h, 'Vista previa'); await settle(h);
    const frame = find(h, n => n.type === 'iframe'); assert.ok(frame);
    assert.match(frame.props.srcDoc, /<th scope="col">Nombre<\/th>/);
    assert.match(frame.props.srcDoc, />Stock<\/th>/);
    assert.ok(!frame.props.srcDoc.includes('Precio final'));
    assert.ok(!frame.props.srcDoc.includes('<button'));
    frame.ref.current = { contentWindow: { focus() {}, print() { printed += 1; } } };
    frame.props.onLoad(); h.render(); click(h, 'Imprimir'); assert.equal(printed, 1);
    click(h, 'Volver al listado'); assert.equal(closed, true);
  } finally { h.dispose(); api.getInventoryItems = original; global.document = previousDocument; }
});

test('closing print during loading discards the response and stops requesting pages', async () => {
  reset(); const original = api.getInventoryItems, previousDocument = global.document;
  global.document = { activeElement: null };
  let resolvePage, calls = 0;
  api.getInventoryItems = () => { calls += 1; return new Promise(resolve => { resolvePage = resolve; }); };
  const h = mount(InventoryPrintDialog, { filters: {}, onClose() {} });
  try {
    click(h, 'Vista previa'); assert.match(text(h.tree), /Cargando productos/);
    click(h, 'Volver al listado'); h.dispose();
    resolvePage({ data: [fixture], meta: { total: 200 } }); await tick(); h.render();
    assert.equal(calls, 1); assert.equal(find(h, n => n.type === 'iframe'), undefined);
  } finally { api.getInventoryItems = original; global.document = previousDocument; }
});


test('empty and failed print loads show feedback, allow retry and never expose partial preview', async () => {
  reset(); const original = api.getInventoryItems, previousDocument = global.document;
  global.document = { activeElement: null };
  const h = mount(InventoryPrintDialog, { filters: {}, onClose() {} });
  try {
    api.getInventoryItems = async () => ({ data: [], meta: { total: 0 } });
    click(h, 'Vista previa'); await settle(h);
    assert.match(text(h.tree), /No hay productos/); assert.equal(find(h, n => n.type === 'iframe'), undefined);
    api.getInventoryItems = async () => { throw new Error('No se pudo cargar'); };
    click(h, 'Vista previa'); await settle(h);
    assert.match(text(h.tree), /No se pudo cargar/); assert.equal(find(h, n => n.type === 'iframe'), undefined);
    api.getInventoryItems = async () => ({ data: [fixture], meta: { total: 1 } });
    click(h, 'Vista previa'); await settle(h);
    assert.ok(find(h, n => n.type === 'iframe')); assert.equal(find(h, n => n.props?.role === 'alert'), undefined);
  } finally { h.dispose(); api.getInventoryItems = original; global.document = previousDocument; }
});
