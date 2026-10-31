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
let current, active;
const hooks = { ...React,
  useState(initial) { const h = current, i = h.index++; if (!(i in h.values)) h.values[i] = typeof initial === 'function' ? initial() : initial; return [h.values[i], value => { h.values[i] = typeof value === 'function' ? value(h.values[i]) : value; }]; },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useMemo(fn, deps) { const h = current, i = h.index++, prev = h.values[i]; if (!prev || deps.some((v,j) => !Object.is(v,prev.deps[j]))) h.values[i] = { deps, value: fn() }; return h.values[i].value; },
  useCallback(fn, deps) { return hooks.useMemo(() => fn, deps); },
  useEffect(fn, deps) { const h = current, i = h.index++, prev = h.effects[i]; if (!prev || deps.some((v,j) => !Object.is(v,prev.deps[j]))) h.pending.push(() => { prev?.cleanup?.(); h.effects[i] = { deps, cleanup: fn() }; }); },
};
const load = Module._load;
Module._load = function(name, ...args) {
  if (name === 'react') return hooks;
  if (name === 'react-dom') return { createPortal: children => children };
  if (name === 'next/navigation') return { useRouter: () => ({ push: href => { active.location = href; }, replace() {} }), useSearchParams: () => new URLSearchParams(), usePathname: () => '/purchases' };
  if (name === '@/features/clinic/clinic-context') return { useClinic: () => ({ preferences: { currency_code: 'ARS', locale: 'es-AR' } }) };
  return load.call(this, name, ...args);
};
const { PurchaseFormScreen } = require('./components/purchase-form-screen.tsx');
const { PurchaseDetailScreen } = require('./components/purchase-detail-screen.tsx');
const { PurchasesScreen } = require('./components/purchases-screen.tsx');
const { PurchaseDashboardScreen } = require('./components/purchase-dashboard-screen.tsx');
const { PurchaseReturnFormScreen } = require('./components/purchase-return-form-screen.tsx');
Module._load = load;
const { purchaseDiscountPreview } = require('./components/purchase-discount.ts');
const { setAuthTokenProvider } = require('../../lib/api.ts');
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, predicate) => nodes(h.tree).find(predicate);
const flush = async () => { for (let i = 0; i < 100; i++) await Promise.resolve(); };
const supplier = { id: 'supplier', name: 'Proveedor', is_active: true };
const line = { id: 'line', inventory_item_id: 'item', description_snapshot: 'Producto', internal_code_snapshot: 'P-1', unit: 'unit', quantity: '1', unit_price_without_tax_ars: '1000.00', tax_rate_percentage: '0', line_subtotal_ars: '1000.00', line_total_ars: '1000.00', line_tax_ars: '0', returnable_quantity: '1', confirmed_returned_quantity: '0' };
const purchase = { id: 'purchase', supplier, supplier_id: supplier.id, supplier_name: supplier.name, currency: 'ARS', status: 'draft', purchase_date: '2026-10-30', document_type: 'invoice', document_number: null, notes: 'Nota', subtotal_ars: '1000.00', tax_total_ars: '0.00', total_ars: '1000.00', discount_type: 'percentage', discount_value: '10.00', discount_amount_ars: '100.00', amount_payable_ars: '900.00', items: [line], returns: [], attachment_history: [], return_status: 'none', confirmed_return_count: 0, returned_total_ars: '0', can_register_return: false, attachment_status: 'pending' };
async function setup(t, { component = PurchaseFormScreen, editing = true, data = purchase } = {}) {
  const oldFetch = global.fetch, oldWindow = global.window, oldDocument = global.document;
  global.window = { setTimeout(fn) { fn(); return 0; }, clearTimeout() {}, requestAnimationFrame() { return 0; } };
  global.document = { body: { style: { overflow: '' } }, addEventListener() {}, removeEventListener() {} };
  const s = { body: null, mutations: 0, location: '', fail: false, response: null, values: [], effects: [], pending: [], props: editing ? { purchaseId: 'purchase' } : {} };
  active = s; setAuthTokenProvider(async () => 'test-token');
  const respond = (body, meta = {}) => new Response(JSON.stringify({ data: body, meta }), { status: 200 });
  global.fetch = async (href, init) => {
    const url = new URL(href);
    if (init.method === 'PATCH' || init.method === 'POST') {
      s.body = JSON.parse(init.body); s.mutations++;
      if (s.fail) return new Response(JSON.stringify({ error: { code: 'purchase_not_editable', message: 'Sólo se puede editar una compra en borrador' } }), { status: 409 });
      return respond(s.response ?? { ...data, id: 'purchase' });
    }
    if (url.pathname === '/api/v1/purchases/purchase') return respond(data);
    if (url.pathname === '/api/v1/suppliers') return respond([supplier], { total_pages: 1 });
    if (url.pathname === '/api/v1/inventory/items') return respond([{ id: 'item', name: 'Producto', internal_code: 'P-1', unit: 'unit', purchase_price_ars: '1000.00', purchase_tax_rate_percentage: '0' }], { page: 1, total_pages: 1 });
    if (url.pathname === '/api/v1/purchases/filter-options') return respond({ creators: [] });
    if (url.pathname === '/api/v1/purchases') return respond([data], { page: 1, page_size: 20, total: 1, total_pages: 1, summary: { purchase_count: 1, subtotal_ars: data.subtotal_ars, tax_total_ars: data.tax_total_ars, total_ars: data.total_ars, discount_amount_ars: data.discount_amount_ars, amount_payable_ars: data.amount_payable_ars } });
    if (url.pathname === '/api/v1/purchases/dashboard') return respond({ generated_at: '2026-10-30T10:00:00Z', period: { date_from: '2026-10-01', date_to: '2026-10-31' }, summary: { registered_total_ars: '1000.00', registered_amount_payable_ars: '900.00', registered_discount_amount_ars: '100.00', received_total_ars: '1000.00', received_amount_payable_ars: '900.00', net_received_amount_payable_ars: '900.00', net_received_total_ars: '1000.00', returned_total_ars: '0', registered_tax_total_ars: '0', purchase_count: 1 }, attention: [], recent_purchases: [], top_suppliers: [] });
    throw new Error(`Unexpected ${url.pathname}`);
  };
  s.render = () => { active = s; current = s; s.index = 0; s.tree = component(s.props); s.pending.splice(0).forEach(fn => fn()); };
  s.settle = async () => { await flush(); s.render(); await flush(); s.render(); };
  s.change = (label, value) => { find(s, n => n.props?.['aria-label'] === label).props.onChange({ target: { value } }); s.render(); };
  s.submit = async () => { await find(s, n => n.type === 'form').props.onSubmit({ preventDefault() {} }); s.render(); };
  t.after(() => { s.effects.forEach(effect => effect?.cleanup?.()); global.fetch = oldFetch; global.window = oldWindow; global.document = oldDocument; setAuthTokenProvider(null); });
  s.render(); await s.settle(); return s;
}
function fillField(s, label, value) {
  const field = find(s, n => n.type === 'label' && text(n).startsWith(label));
  const input = nodes(field).find(n => ['input', 'textarea'].includes(n.type));
  input.props.onChange({ target: { value } }); s.render();
}

test('preview applies one discount after purchase tax and rounds only the global discount', () => {
  const preview = purchaseDiscountPreview([{ quantity: '1', unitPrice: '0.05', taxRate: '21' }, { quantity: '1', unitPrice: '0.05', taxRate: '21' }], 'percentage', '10');
  assert.deepEqual(preview, { subtotal: '0.10', tax: '0.02', total: '0.12', discount_amount_ars: '0.01', amount_payable_ars: '0.11', error: null });
  assert.equal(purchaseDiscountPreview([{ quantity: '1', unitPrice: '99999999999999.99', taxRate: '0' }], 'amount', '0.01').amount_payable_ars, '99999999999999.98');
});

test('form loads a saved discount, preserves it when saving notes and displays backend authority', async t => {
  const s = await setup(t);
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Modalidad de descuento').props.value, 'percentage');
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Valor del descuento').props.value, '10.00');
  fillField(s, 'Notas', 'Nueva nota');
  s.response = { ...purchase, discount_amount_ars: '123.45', amount_payable_ars: '876.55' };
  await s.submit();
  assert.equal(s.body.discount_type, 'percentage'); assert.equal(s.body.discount_value, '10.00');
  assert.equal(s.body.items[0].unit_price_without_tax_ars, '1000.00');
  assert.equal(s.body.discount_amount_ars, undefined); assert.equal(s.body.amount_payable_ars, undefined);
  assert.equal(s.body.notes, 'Nueva nota');
  assert.equal(s.location, '/purchases/purchase');
  assert.match(text(s.tree), /876,55/); assert.match(text(s.tree), /Importes definitivos guardados/);
});

test('changing units resets the old value, preserves line cost and explicitly removes discount', async t => {
  const s = await setup(t);
  s.change('Modalidad de descuento', 'amount');
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Valor del descuento').props.value, '0');
  assert.match(text(s.tree), /Descuento \(ARS\)/);
  s.change('Valor del descuento', '150');
  assert.match(text(s.tree), /850,00/);
  assert.equal(s.mutations, 0);
  s.change('Modalidad de descuento', 'none');
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Valor del descuento'), undefined);
  await s.submit();
  assert.equal(s.body.discount_type, 'none'); assert.equal(s.body.discount_value, '0');
  assert.equal(s.body.items[0].unit_price_without_tax_ars, '1000.00');
});

test('line edits recalculate a percentage; a fixed amount exceeding the new gross blocks save', async t => {
  const s = await setup(t);
  fillField(s, 'Cantidad', '2'); assert.match(text(s.tree), /1\.800,00/);
  s.change('Modalidad de descuento', 'amount'); s.change('Valor del descuento', '150');
  fillField(s, 'Costo sin IVA', '10');
  assert.match(text(s.tree), /no puede superar el total original/);
  await s.submit(); assert.equal(s.mutations, 0);
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Valor del descuento').props.value, '150');
});

for (const [type, value, valid] of [['percentage', '100', true], ['amount', '0', true], ['percentage', '100.01', false], ['amount', '-1', false], ['amount', '1.001', false]]) test(`discount validation ${type} ${value}`, async t => {
  const s = await setup(t); s.change('Modalidad de descuento', type); s.change('Valor del descuento', value);
  await s.submit(); assert.equal(s.mutations, valid ? 1 : 0);
  if (value === '100') assert.match(text(s.tree), /Total a pagar/);
});

test('concurrent state change is shown without losing inputs or automatic mutation retries', async t => {
  const s = await setup(t); s.fail = true;
  const handler = find(s, n => n.type === 'form').props.onSubmit;
  await Promise.all([handler({ preventDefault() {} }), handler({ preventDefault() {} })]); s.render();
  assert.equal(s.mutations, 1); assert.match(text(s.tree), /Sólo se puede editar una compra en borrador/);
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Valor del descuento').props.value, '10.00');
  assert.equal(s.location, '');
});

test('new purchase defaults to none and saves the selected discount through existing supplier/product controls', async t => {
  const s = await setup(t, { editing: false });
  assert.equal(find(s, n => n.props?.['aria-label'] === 'Modalidad de descuento').props.value, 'none');
  find(s, n => n.props.role === 'combobox').props.onFocus(); s.render(); await s.settle();
  find(s, n => n.type === 'button' && n.props.role === 'option').props.onClick(); s.render();
  await find(s, n => n.type === 'button' && text(n).trim() === 'Buscar').props.onClick(); await s.settle();
  find(s, n => n.type === 'button' && text(n).includes('Costo actual')).props.onClick(); s.render();
  s.change('Modalidad de descuento', 'percentage'); s.change('Valor del descuento', '10'); await s.submit();
  assert.equal(s.mutations, 1); assert.equal(s.body.supplier_id, supplier.id);
  assert.equal(s.body.discount_value, '10'); assert.equal(s.body.items[0].unit_price_without_tax_ars, '1000.00');
});

for (const component of [PurchaseDetailScreen, PurchasesScreen]) test(`${component.name} shows gross, discount and payable separately`, async t => {
  const s = await setup(t, { component, data: { ...purchase, status: 'received' } });
  assert.match(text(s.tree), /Total original/); assert.match(text(s.tree), /Descuento/);
  assert.match(text(s.tree), /900,00/); assert.match(text(s.tree), /100,00/); assert.match(text(s.tree), /1\.000,00/);
});

test('dashboard renders net committed amounts while preserving an original-total card', async t => {
  const s = await setup(t, { component: PurchaseDashboardScreen });
  assert.match(find(s, n => n.props.label === 'A pagar registrado').props.value, /900,00/);
  assert.match(find(s, n => n.props.label === 'Total original registrado').props.value, /1\.000,00/);
});

test('discounted return form saves a separate supplier agreement including zero', async t => {
  const s = await setup(t, { component: PurchaseReturnFormScreen, data: { ...purchase, status: 'received', can_register_return: true } });
  assert.ok(find(s, n => n.type === 'form'));
  const agreement = find(s, n => n.type === 'label' && text(n).includes('Importe acordado con el proveedor (ARS)'));
  nodes(agreement).find(n => n.type === 'input').props.onChange({ target: { value: '0' } });
  find(s, n => n.type === 'textarea').props.onChange({ target: { value: 'Acuerdo local' } });
  find(s, n => n.props?.['aria-label'] === 'Cantidad a devolver de Producto').props.onChange({ target: { value: '1' } });
  s.render();
  assert.match(text(s.tree), /Bruto estimado de referencia/);
  await s.submit();
  assert.equal(s.body.agreed_amount_ars, '0');
  assert.deepEqual(s.body.items, [{ purchase_item_id: 'line', quantity: '1' }]);
  assert.equal(s.body.total_ars, undefined);
  assert.equal(s.mutations, 1);
});
