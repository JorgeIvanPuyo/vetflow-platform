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

let url, navigations, requests, savedItem, failSave, history;
const timers = new Map();
let timerId = 0;
global.window = {
  setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
  clearTimeout(id) { timers.delete(id); },
};
const router = {
  back() { url = new URL(history.pop()); },
  push(href) { history.push(url.href); navigations.push(href); url = new URL(href, 'http://localhost'); },
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
const { InventoryDetailModal } = require('./components/inventory-detail-modal.tsx');
const { InventoryDetail } = require('./components/inventory-detail.tsx');
const { InventoryPrintDialog } = require('./components/inventory-print-dialog.tsx');
Module._load = load;
function mount(component, props, attach) {
  const h = { values: [], effects: [], pending: [], props };
  h.render = () => { h.index = 0; current = h; h.tree = component(h.props); attach?.(h.tree); h.pending.splice(0).forEach((run) => run()); };
  h.dispose = () => h.effects.forEach((e) => e.cleanup?.());
  h.render(); return h;
}
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, predicate) => nodes(h.tree).find(predicate);
const tick = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };


const context = '/inventory?search=alimento+%26+gato&category=food&brand=Marca&supplier=Proveedor&stock_status=low_stock&is_active=false&sort_by=sale_price_ars&sort_direction=desc&page=3&page_size=50';
function reset(href = context) {
  url = new URL(href, 'http://localhost'); navigations = []; requests = []; history = [];
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


for (const view of ['Tarjetas', 'Tabla']) {
  test(`opening a product from ${view} preserves mounted list, filters and history`, async () => {
    reset(); const h = mount(InventoryScreen); await settle(h);
    if (view === 'Tabla') click(h, view);
    const before = requests.length;
    // Every item URL transition replaces PageReadBoundary and renews its cancelled GETs.
    let prevented = false;
    detailLink(h).props.onClick({ button: 0, preventDefault() { prevented = true; } });
    await settle(h);
    assert.ok(prevented); assert.equal(url.searchParams.get('item'), fixture.id);
    const modal = find(h, n => n.type === InventoryDetailModal); assert.ok(modal);
    assert.equal(search(h).props.value, 'alimento & gato');
    assert.equal(requests.length, before + 1);
    const openedUrl = url.href;
    modal.props.onClose(); await settle(h);
    assert.equal(url.pathname + url.search, context);
    assert.equal(find(h, n => n.type === InventoryDetailModal), undefined);
    assert.equal(requests.length, before + 2);
    // Forward restores the modal from URL state; browser Back closes it again.
    router.push(openedUrl); await settle(h); assert.ok(find(h, n => n.type === InventoryDetailModal));
    router.back(); await settle(h); assert.equal(find(h, n => n.type === InventoryDetailModal), undefined);
    assert.equal(requests.length, before + 4); h.dispose();
  });
}

test('modified clicks retain direct product links and direct modal URL closes without leaving inventory', async () => {
  reset(); const h = mount(InventoryScreen); await settle(h);
  detailLink(h).props.onClick({ button: 0, ctrlKey: true, preventDefault() { assert.fail('modified click intercepted'); } });
  assert.equal(navigations.length, 0); assert.match(detailLink(h).props.href, /^\/inventory\/product-1\?return_to=/);
  h.dispose();
  reset(context + '&item=product-1'); const direct = mount(InventoryScreen); await settle(direct);
  find(direct, n => n.type === InventoryDetailModal).props.onClose(); await settle(direct);
  assert.equal(url.pathname + url.search, context); direct.dispose();
});

test('native detail dialog opens modally, closes on Escape/button and restores scroll and focus', () => {
  const previousDocument = global.document;
  let shown = 0, nativeClosed = 0, closed = 0, focused = 0;
  global.document = { body: { style: { overflow: 'auto' } }, activeElement: { focus() { focused += 1; } } };
  const element = { showModal() { shown += 1; }, close() { nativeClosed += 1; } };
  const h = mount(InventoryDetailModal, { itemId: fixture.id, onClose() { closed += 1; }, onChanged() {} }, tree => { tree.ref.current = element; });
  try {
    assert.equal(h.tree.type, 'dialog'); assert.equal(shown, 1); assert.equal(document.body.style.overflow, 'hidden');
    let prevented = false; h.tree.props.onCancel({ preventDefault() { prevented = true; } });
    assert.ok(prevented); assert.equal(closed, 1);
    find(h, n => n.props?.['aria-label'] === 'Cerrar detalle').props.onClick(); assert.equal(closed, 2);
    h.dispose(); assert.equal(nativeClosed, 1); assert.equal(document.body.style.overflow, 'auto'); assert.equal(focused, 1);
  } finally { global.document = previousDocument; }
});

test('embedded detail preserves actions/history and uses one surface for editing; saving refreshes and closes', async () => {
  reset(); const previousDocument = global.document, previousMovements = api.getInventoryMovements;
  global.document = { activeElement: null };
  api.getInventoryMovements = async () => ({ data: [{ id: 'movement-1', movement_type: 'initial_stock', quantity: '10', stock_before: '0', stock_after: '10', created_at: '2026-09-23T12:00:00Z', reversal_status: 'active' }], meta: { page: 1, total_pages: 1 } });
  let closed = 0, changed = 0;
  const h = mount(InventoryDetail, { itemId: fixture.id, onClose() { closed += 1; }, onChanged() { changed += 1; } });
  try {
    await settle(h);
    for (const label of ['Editar', 'Desactivar', 'Registrar compra', 'Registrar salida', 'Historial de stock']) assert.ok(text(h.tree).includes(label));
    assert.ok(find(h, n => n.props?.href === '/inventory/movements/movement-1'));
    click(h, 'Editar'); assert.ok(find(h, n => n.props?.hidden === true));
    editForm(h).props.onCancel(); h.render(); assert.equal(closed, 0); assert.equal(editForm(h), undefined);
    click(h, 'Editar'); let prevented = false;
    h.tree.props.onKeyDown({ key: 'Escape', preventDefault() { prevented = true; }, stopPropagation() {} }); h.render();
    assert.ok(prevented); assert.equal(editForm(h), undefined); assert.equal(closed, 0);
    click(h, 'Editar'); await editForm(h).props.onSubmit({ preventDefault() {} });
    assert.equal(changed, 1); assert.equal(closed, 1); assert.equal(navigations.length, 0);
  } finally { h.dispose(); api.getInventoryMovements = previousMovements; global.document = previousDocument; }
});

test('pending pricing filter requests the complete server result and resets pagination', async () => {
  reset('/inventory?page=3&page_size=20&sort_by=name&sort_direction=asc');
  const h = mount(InventoryScreen); await settle(h);
  click(h, 'Completar costo/porcentaje'); await settle(h);
  assert.equal(url.searchParams.get('status'), 'pricing_pending');
  assert.equal(requests.at(-1).status, 'pricing_pending');
  assert.equal(requests.at(-1).page, 1);
  assert.equal(requests.at(-1).is_active, undefined);
  assert.equal(requests.at(-1).stock_status, undefined);
  h.dispose();
});

let bulkRequests = [], bulkConfirmCalls = 0, bulkServer, bulkTwoPages = false;
api.previewInventoryBulkOperation = async payload => {
  bulkRequests.push(payload);
  const row = { id: 'row', inventory_item_id: fixture.id, inventory_item_name: fixture.name,
    field_name: 'sale_price_ars', status: 'pending', error_message: null,
    old_value_json: { value: { profit_margin_percentage: '30', sale_price_ars: '1300' }, pricing_context: { purchase_price_ars: '1000', sale_tax_rate_percentage: '21' }, sale_price_with_tax_ars: '1573' },
    new_value_json: { value: { profit_margin_percentage: '43', sale_price_ars: '1430' }, pricing_context: { purchase_price_ars: '1000', sale_tax_rate_percentage: '21' }, sale_price_with_tax_ars: '1730.30' } };
  bulkServer = { id: 'bulk', status: 'preview', affected_count: 1, unchanged_count: 0, invalid_count: bulkTwoPages ? 1 : 0,
    selected_count: bulkTwoPages ? 2 : 1, excluded_count: 0, items: [row] };
  return { data: bulkServer, meta: { page: 1, total_pages: bulkTwoPages ? 2 : 1 } };
};
api.getInventoryBulkOperation = async (id, page) => ({ data: { ...bulkServer, items: [{ ...bulkServer.items[0], status: 'invalid', error_message: 'catalog_target_not_representable' }] }, meta: { page, total_pages: 2 } });
api.confirmInventoryBulkOperation = async id => {
  bulkConfirmCalls++;
  savedItem = { ...savedItem, name: 'Alimento confirmado', brand: 'Nueva' };
  return { data: { ...bulkServer, status: 'confirmed' } };
};
async function bulkForm(operation, value, { filtered = false, href = context } = {}) {
  reset(href); bulkRequests = []; bulkConfirmCalls = 0;
  const h = mount(InventoryScreen); await settle(h);
  click(h, filtered ? 'Seleccionar todos los resultados' : 'Seleccionar esta página');
  click(h, 'Editar grupo');
  const operationSelect = find(h, n => n.type === 'select' && nodes(n.props.children).some(c => c.props?.value === 'set_sale_price'));
  assert.ok(operationSelect);
  assert.equal(nodes(operationSelect.props.children).filter(c => c.type === 'option').length, 9);
  operationSelect.props.onChange({ target: { value: operation } }); h.render();
  const input = find(h, n => n.type === 'input' && n.props.placeholder && ['Porcentaje', 'Precio final', 'Stock mínimo', 'Marca', 'Proveedor'].includes(n.props.placeholder));
  if (input) { input.props.onChange({ target: { value } }); h.render(); }
  return h;
}
for (const [operation, raw, field, value] of [
  ['increase_sale_price_percentage', '10', 'percentage', 10],
  ['decrease_sale_price_percentage', '10', 'percentage', 10],
  ['set_profit_margin_percentage', '0', 'profit_margin_percentage', 0],
  ['set_sale_price', '1500', 'sale_price_ars', 1500],
  ['set_brand', 'Nueva', 'brand', 'Nueva'], ['set_supplier', 'Nuevo', 'supplier', 'Nuevo'],
  ['set_minimum_stock', '0', 'minimum_stock', 0], ['activate', '', null, null], ['deactivate', '', null, null],
]) test(`bulk component sends only the intended fields: ${operation}`, async () => {
  const h = await bulkForm(operation, raw);
  try {
    click(h, 'Simular'); await settle(h);
    assert.equal(bulkRequests.length, 1);
    assert.deepEqual(bulkRequests[0].operation, { operation_type: operation, confirm_clear: false, ...(field ? { [field]: value } : {}) });
    assert.deepEqual(bulkRequests[0].selection, { selection_mode: 'selected', selected_ids: [fixture.id], excluded_ids: [] });
    assert.match(text(h.tree), /Se aplicarán 1 filas válidas/);
  } finally { h.dispose(); }
});

test('bulk selection preserves filters, pending status and exclusions across pages', async () => {
  const h = await bulkForm('set_brand', 'Nueva', { filtered: true, href: context + '&status=pricing_pending' });
  try {
    // Exclude the visible product while retaining all other pages.
    find(h, n => n.type === 'input' && n.props.type === 'checkbox' && n.props.onChange && n.props.checked === true).props.onChange(); h.render();
    click(h, 'Simular'); await settle(h);
    const selection = bulkRequests[0].selection;
    assert.equal(selection.selection_mode, 'filtered');
    assert.deepEqual(selection.excluded_ids, [fixture.id]);
    assert.deepEqual(selection.filters, { search: 'alimento & gato', category: 'food', brand: 'Marca', supplier: 'Proveedor', stock_status: 'low_stock', is_active: false, status: 'pricing_pending' });
    assert.equal(selection.filters.page, undefined);
  } finally { h.dispose(); }
});

test('bulk preview displays base, sale tax, per-row reason and all preview pages', async () => {
  bulkTwoPages = true;
  const h = await bulkForm('set_sale_price', '1430');
  try {
    click(h, 'Simular'); await settle(h);
    assert.match(text(h.tree), /Venta base/); assert.match(text(h.tree), /Con impuesto de venta/);
    assert.match(text(h.tree), /Se omitirán 0 sin cambios y 1 inválidas/);
    const next = find(h, n => n.type === 'button' && text(n).trim() === 'Siguiente' && n.props.onClick.toString().includes('loadBulkPreviewPage'));
    assert.ok(next); await next.props.onClick(); await settle(h);
    assert.match(text(h.tree), /Página 2 de 2/);
    assert.match(text(h.tree), /No se alcanza el importe exacto/);
    assert.equal(bulkRequests.length, 1);
  } finally { h.dispose(); bulkTwoPages = false; }
});

for (const [operation, value] of [
  ['increase_sale_price_percentage', '1000.01'], ['set_profit_margin_percentage', '30.001'],
  ['set_sale_price', '99999999999'], ['set_minimum_stock', '1.001'], ['set_brand', ''], ['set_supplier', ''],
]) test(`bulk component validates limits or explicit clearing: ${operation}`, async () => {
  const h = await bulkForm(operation, value);
  try {
    click(h, 'Simular'); await settle(h);
    assert.equal(bulkRequests.length, 0);
    if (operation === 'set_brand' || operation === 'set_supplier') {
      const checkbox = find(h, n => n.type === 'input' && n.props.type === 'checkbox' && n.props.checked === false);
      checkbox.props.onChange({ target: { checked: true } }); h.render();
      click(h, 'Simular'); await settle(h);
      assert.equal(bulkRequests[0].operation.confirm_clear, true);
      assert.equal(bulkRequests[0].operation[operation === 'set_brand' ? 'brand' : 'supplier'], '');
    }
  } finally { h.dispose(); }
});

test('bulk confirmation disables duplicate sends and reports a read failure separately', async () => {
  const h = await bulkForm('set_brand', 'Nueva');
  const original = api.getInventoryItems;
  try {
    click(h, 'Simular'); await settle(h);
    api.getInventoryItems = async () => { throw new (require('../../lib/api.ts').ApiClientError)('No pudimos leer', 422, 'read_failed'); };
    const confirm = find(h, n => n.type === 'button' && text(n).trim() === 'Confirmar 1 productos');
    const first = confirm.props.onClick(), second = confirm.props.onClick();
    await Promise.all([first, second]); await settle(h);
    assert.equal(bulkConfirmCalls, 1);
    assert.match(text(h.tree), /Operación confirmada/);
    assert.match(text(h.tree), /Los cambios se guardaron.*No pudimos leer/);
    api.getInventoryItems = original;
    click(h, 'Reintentar'); await settle(h);
    assert.match(text(h.tree), /Alimento confirmado/);
    assert.doesNotMatch(text(h.tree), /No pudimos leer/);
    assert.equal(bulkConfirmCalls, 1);
  } finally { api.getInventoryItems = original; h.dispose(); }
});
