const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const ts = require('typescript');
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

const helpers = require('./components/inventory-helpers.tsx');

function formState(overrides = {}) {
  return { ...helpers.getInitialInventoryFormState(), name: 'Bravecto', purchase_price_ars: '26849.90', profit_margin_percentage: '80', sale_price_ars: '64038.87', ...overrides };
}

test('individual payloads contain pricing inputs and omit a stale direct price', () => {
  for (const build of [helpers.inventoryFormToCreatePayload, helpers.inventoryFormToUpdatePayload]) {
    const payload = build(formState());
    assert.equal(payload.sale_price_is_manual, undefined);
    assert.equal(payload.sale_price_ars, undefined);
    assert.equal(payload.profit_margin_percentage, 80);
    assert.equal(payload.purchase_price_ars, 26849.90);
  }
});

test('purchase tax precedes markup and sale tax is applied once', () => {
  const preview = helpers.calculateInventoryPricePreview(formState({ purchase_price_ars: '100', purchase_tax_rate_percentage: '21', profit_margin_percentage: '30', sale_tax_rate_percentage: '10' }));
  assert.equal(preview.saleWithoutTax, 157.30);
  assert.equal(preview.saleWithTax, 173.03);
  assert.equal(helpers.calculateInventoryPricePreview(formState({ purchase_price_ars: '100', purchase_tax_rate_percentage: '21', profit_margin_percentage: '30', round_sale_price: true }), 25).saleWithoutTax, 150);
});

test('zero inputs are valid and absent inputs remain pending', () => {
  const zero = formState({ purchase_price_ars: '0', profit_margin_percentage: '0' });
  assert.equal(helpers.validateInventoryForm(zero), null);
  assert.equal(helpers.calculateInventoryPricePreview(zero).saleWithoutTax, 0);
  assert.equal(helpers.inventoryFormToCreatePayload(zero).profit_margin_percentage, 0);
  assert.equal(helpers.calculateInventoryPricePreview(formState({ purchase_price_ars: '' })).saleWithoutTax, null);
  assert.match(helpers.validateInventoryForm(formState({ profit_margin_percentage: '' })), /porcentaje/);
  assert.equal(helpers.calculateInventoryPricePreview(formState({ profit_margin_percentage: '' })).saleWithoutTax, null);
});

test('pending products carry an inventory badge', () => {
  const badges = helpers.getInventoryStatusBadges({ pricing_pending: true, current_stock: '0', minimum_stock: '0', is_active: true });
  assert.ok(badges.some((badge) => badge.label === 'Completar costo/porcentaje'));
});
