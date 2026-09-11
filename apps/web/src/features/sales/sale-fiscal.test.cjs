const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const ts = require("typescript");

// Same dependency-free TypeScript/Node test approach as sale-services.test.cjs.
const filename = path.join(__dirname, "components/sale-fiscal-helpers.ts");
const compiled = new Module(filename, module);
compiled._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, filename);
const { getIssuerDocumentPair } = compiled.exports;

const serviceIssuer = {
  can_issue_service_receipt_c: true, service_document_type: "receipt_c", service_document_code: "015",
  can_issue_product_invoice_c: false, product_document_type: null, product_document_code: null,
};
const productIssuer = {
  can_issue_service_receipt_c: false, service_document_type: null, service_document_code: null,
  can_issue_product_invoice_c: true, product_document_type: "invoice_c", product_document_code: "011",
};
const product = { line_type: "product", fiscal_line_type: "product" };
const medication = { line_type: "product", fiscal_line_type: "service" };
const service = { line_type: "service", fiscal_line_type: "service" };
const pair = (items, issuer) => getIssuerDocumentPair({ items }, issuer);

test("medication and service offer the configured service document C 015", () => {
  for (const item of [medication, service]) {
    assert.deepEqual(pair([item], serviceIssuer), ["receipt_c", "015"]);
    assert.equal(pair([item], productIssuer), null);
  }
});

test("ordinary products retain product options and reject service-only issuers", () => {
  assert.deepEqual(pair([product], productIssuer), ["invoice_c", "011"]);
  assert.equal(pair([product], serviceIssuer), null);
});

test("mixed-sale policy uses fiscal composition and still requires matching capabilities", () => {
  assert.deepEqual(pair([medication, service], serviceIssuer), ["receipt_c", "015"]);
  const dual = { ...serviceIssuer, can_issue_product_invoice_c: true, product_document_type: "invoice_c", product_document_code: "011" };
  const matching = { ...dual, product_document_type: "receipt_c", product_document_code: "015" };
  for (const items of [[product, medication], [product, service], [product, medication, service]]) {
    for (const issuer of [productIssuer, serviceIssuer, dual]) assert.equal(pair(items, issuer), null);
    assert.deepEqual(pair(items, matching), ["receipt_c", "015"]);
  }
});

test("service document comes from issuer configuration and must be complete", () => {
  assert.deepEqual(pair([medication], { ...serviceIssuer, service_document_type: "invoice_c", service_document_code: "011" }), ["invoice_c", "011"]);
  assert.equal(pair([medication], { ...serviceIssuer, service_document_code: null }), null);
});
