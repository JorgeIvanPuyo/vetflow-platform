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

test('calculated price mode drops a stale sale price so the margin applies', () => {
  const payload = helpers.inventoryFormToUpdatePayload(formState(), false);
  assert.equal(payload.sale_price_is_manual, false);
  assert.equal(payload.sale_price_ars, null);
  assert.equal(payload.profit_margin_percentage, 80);
});

test('manual price mode sends the fixed sale price', () => {
  const payload = helpers.inventoryFormToUpdatePayload(formState(), true);
  assert.equal(payload.sale_price_is_manual, true);
  assert.equal(payload.sale_price_ars, 64038.87);
  const createPayload = helpers.inventoryFormToCreatePayload(formState(), true);
  assert.equal(createPayload.sale_price_is_manual, true);
  assert.equal(createPayload.sale_price_ars, 64038.87);
});

test('manual price mode requires a sale price', () => {
  assert.match(helpers.validateInventoryForm(formState({ sale_price_ars: '' }), { manualSalePrice: true }), /precio de venta manual/);
  assert.equal(helpers.validateInventoryForm(formState({ sale_price_ars: '' }), { manualSalePrice: false }), null);
});
