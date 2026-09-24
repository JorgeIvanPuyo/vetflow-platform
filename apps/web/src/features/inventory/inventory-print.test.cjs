const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args);
};
for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(root + path.sep));
    module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText, filename);
  };
}
const { loadInventoryPrintItems, buildInventoryPrintDocument, defaultInventoryPrintColumns, inventoryPrintColumns } = require('./components/inventory-print.ts');
const { setAuthTokenProvider, setActingTenantId } = require('../../lib/api.ts');
const { formatInventoryCurrency } = require('./components/inventory-helpers.tsx');
const money = { currencyCode: 'USD', locale: 'es-PA' };
const fixture = { id: '1', name: 'Alimento', internal_code: 'A001', category: 'food', current_stock: '5', unit: 'unit', sale_price_ars: '100', sale_price_with_tax_ars: '121', purchase_price_ars: '80', is_active: true };

async function withApi(handler, run) {
  const previousFetch = global.fetch;
  setAuthTokenProvider(async () => 'test-session'); setActingTenantId(null);
  global.fetch = async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, '/api/v1/inventory/items');
    assert.equal(init.headers.get('Authorization'), 'Bearer test-session');
    assert.equal(init.headers.has('X-Tenant-Id'), false);
    assert.equal(init.headers.has('X-Acting-Tenant-Id'), false);
    assert.equal(parsed.searchParams.has('tenant_id'), false);
    const response = await handler(parsed.searchParams);
    if (response instanceof Response) return response;
    return new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  try { await run(); } finally { global.fetch = previousFetch; setAuthTokenProvider(null); }
}

test('loads every filtered page sequentially using authenticated API and preserves server order', async () => {
  const filters = { search: 'gato & perro', category: 'food', brand: 'Marca', supplier: 'Proveedor', status: 'expiring_soon', stock_status: 'low_stock', is_active: false, sort_by: 'sale_price_ars', sort_direction: 'desc', page: 7, page_size: 20 };
  const rows = Array.from({ length: 205 }, (_, index) => ({ ...fixture, id: String(205 - index) }));
  const pages = [], progress = []; let active = 0, maximumActive = 0;
  await withApi(async params => {
    active += 1; maximumActive = Math.max(maximumActive, active);
    const page = Number(params.get('page')); pages.push(page);
    assert.equal(params.get('page_size'), '100');
    for (const [key, value] of Object.entries(filters)) if (!['page', 'page_size'].includes(key)) assert.equal(params.get(key), String(value));
    await Promise.resolve(); active -= 1;
    return { data: rows.slice((page - 1) * 100, page * 100), meta: { total: 205, total_pages: 3, page, page_size: 100 } };
  }, async () => {
    const result = await loadInventoryPrintItems(filters, (loaded, total) => progress.push([loaded, total]), () => false);
    assert.deepEqual(result, rows); assert.deepEqual(pages, [1, 2, 3]);
    assert.equal(maximumActive, 1); assert.deepEqual(progress, [[100, 205], [200, 205], [205, 205]]);
    assert.equal(filters.page, 7);
  });
});

test('empty inventory and oversized inventory never produce a partial printable list', async () => {
  await withApi(async () => ({ data: [], meta: { total: 0 } }), async () => {
    assert.deepEqual(await loadInventoryPrintItems({}, () => {}, () => false), []);
  });
  let calls = 0;
  await withApi(async () => { calls += 1; return { data: [], meta: { total: 5001 } }; }, async () => {
    await assert.rejects(loadInventoryPrintItems({}, () => {}, () => false), /5.000 productos/);
    assert.equal(calls, 1);
  });
});

test('failure or changed results prevent incomplete printing, and cancellation stops pagination', async () => {
  await withApi(async params => Number(params.get('page')) === 1
    ? { data: Array.from({ length: 100 }, (_, i) => ({ ...fixture, id: String(i) })), meta: { total: 200 } }
    : new Response(JSON.stringify({ error: { message: 'Acceso denegado' } }), { status: 403 }), async () => {
    await assert.rejects(loadInventoryPrintItems({}, () => {}, () => false), /Acceso denegado/);
  });
  await withApi(async () => ({ data: [], meta: { total: 200 } }), async () => {
    await assert.rejects(loadInventoryPrintItems({}, () => {}, () => false), /cambió durante la carga/);
  });
  let cancelled = false, calls = 0;
  await withApi(async () => { calls += 1; cancelled = true; return { data: [], meta: { total: 200 } }; }, async () => {
    assert.equal(await loadInventoryPrintItems({}, () => {}, () => cancelled), null);
    assert.equal(calls, 1);
  });
});

test('print document defaults to name and final price with taxes and escapes all product and clinic text', () => {
  assert.deepEqual(defaultInventoryPrintColumns, ['name', 'sale_price']);
  const html = buildInventoryPrintDocument([{ ...fixture, name: '<script>alert("x")</script>' }], defaultInventoryPrintColumns, '<img src=x onerror=alert(1)>', '2026-09-23T12:00:00Z', money);
  assert.ok(html.includes('Inventario')); assert.ok(html.includes('Precio final'));
  assert.ok(html.includes(formatInventoryCurrency('121', money)));
  assert.ok(html.includes('&lt;script&gt;')); assert.ok(html.includes('&lt;img'));
  assert.doesNotMatch(html, /<script|<img|<button|<nav|<aside|<input/);
  assert.ok(html.includes('@media print')); assert.ok(html.includes('table-header-group'));
  assert.ok(html.includes('break-inside: avoid')); assert.ok(html.includes('1 productos'));
});

test('selected columns use existing labels, catalog names and final price fallback', () => {
  const row = { ...fixture, brand: 'Marca', supplier: 'Viejo', supplier_name: 'Proveedor actual', category_catalog_item_name: 'Alimentos', is_active: false, sale_price_with_tax_ars: null };
  const html = buildInventoryPrintDocument([row], inventoryPrintColumns.map(c => c.id), 'Clínica', '2026-09-23T12:00:00Z', money);
  for (const label of ['Marca', 'Proveedor actual', 'Alimentos', 'Inactivo', 'Costo de compra (sin IVA)']) assert.ok(html.includes(label));
  assert.ok(html.includes(formatInventoryCurrency('100', money)));
  assert.ok(html.includes('size: landscape'));
  const onlyStock = buildInventoryPrintDocument([row], ['stock'], '', '2026-09-23T12:00:00Z', money);
  assert.doesNotMatch(onlyStock, /Precio final|Código interno|Alimento/);
  assert.match(onlyStock, />5<\/td>/);
});
