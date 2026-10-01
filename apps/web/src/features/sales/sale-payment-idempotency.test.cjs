const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const ts = require("typescript");
const React = require("react");

const root = path.resolve(__dirname, "../..");
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) {
  return resolve.call(this, name.startsWith("@/") ? path.join(root, name.slice(2)) : name, ...args);
};
for (const extension of [".ts", ".tsx"]) require.extensions[extension] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
};

const { createSalePaymentIntent } = require("./components/sale-payment-intent.ts");
const { createSalePayment } = require("../../services/sales.ts");
const { getApiErrorMessage, setAuthTokenProvider } = require("../../lib/api.ts");
const payload = { payment_method_id: "cash", amount_ars: "40.00", received_at: "2026-10-01T12:00:00.000Z", reference: "REF-1", notes: null };
const response = (status = 201) => new Response(JSON.stringify({ data: { id: "payment-1" }, meta: {} }), { status });

test("new intentions use new keys; success prevents resubmitting before a new operation", async () => {
  let generated = 0;
  const intent = createSalePaymentIntent(() => `key-${++generated}`);
  assert.equal(generated, 0);
  assert.equal(intent.begin(), true);
  assert.equal(generated, 1);
  const keys = [];
  const send = async (sale, body, key) => { keys.push(key); };
  assert.equal(await intent.submit("sale", payload, send), true);
  assert.equal(await intent.submit("sale", payload, send), false);
  assert.equal(intent.begin(), true);
  assert.equal(await intent.submit("sale", payload, send), true);
  assert.deepEqual(keys, ["key-1", "key-2"]);
});

test("in-flight submit is guarded synchronously and beginning another intent is blocked", async () => {
  const intent = createSalePaymentIntent(() => "key-1");
  intent.begin();
  let calls = 0, release;
  const send = () => { calls++; return new Promise(resolve => { release = resolve; }); };
  const first = intent.submit("sale", payload, send);
  assert.equal(intent.pending, true);
  assert.equal(intent.begin(), false);
  assert.equal(await intent.submit("sale", payload, send), false);
  assert.equal(calls, 1);
  release();
  assert.equal(await first, true);
  assert.equal(intent.pending, false);
});

test("network response loss retains the key, retries through the real service and does not auto-retry POST", async () => {
  const originalFetch = global.fetch;
  setAuthTokenProvider(async () => "local-test-token");
  let generated = 0, calls = 0;
  const keys = [], bodies = [];
  const intent = createSalePaymentIntent(() => `key-${++generated}`);
  intent.begin();
  global.fetch = async (url, init) => {
    calls++;
    assert.equal(new URL(url).pathname, "/api/v1/sales/sale/payments");
    assert.equal(init.headers.get("Authorization"), "Bearer local-test-token");
    keys.push(init.headers.get("Idempotency-Key"));
    bodies.push(JSON.parse(init.body));
    if (calls === 1) throw new TypeError("Response lost after commit");
    return response(200);
  };
  try {
    await assert.rejects(intent.submit("sale", payload));
    assert.equal(calls, 1);
    assert.equal(intent.pending, false);
    assert.equal(await intent.submit("sale", { ...payload }), true);
    assert.deepEqual(keys, ["key-1", "key-1"]);
    assert.deepEqual(bodies, [payload, payload]);
    assert.equal(generated, 1);
  } finally { global.fetch = originalFetch; setAuthTokenProvider(null); }
});

test("material edits after a failed request replace the key for every fingerprint field", async () => {
  for (const changed of [
    { sale: "another-sale" }, { payment_method_id: "bank" }, { amount_ars: "41.00" },
    { received_at: "2026-10-01T12:01:00.000Z" }, { reference: "REF-2" }, { notes: "Other notes" },
  ]) {
    let generated = 0;
    const keys = [];
    const intent = createSalePaymentIntent(() => `key-${++generated}`);
    intent.begin();
    const failing = async (sale, body, key) => { keys.push(key); throw new TypeError("offline"); };
    await assert.rejects(intent.submit("sale", payload, failing));
    const { sale = "sale", ...fields } = changed;
    await assert.rejects(intent.submit(sale, { ...payload, ...fields }, failing));
    assert.deepEqual(keys, ["key-1", "key-2"]);
  }
});

test("equivalent decimal and optional text spellings keep the same retry key", async () => {
  let generated = 0;
  const intent = createSalePaymentIntent(() => `key-${++generated}`);
  const keys = [];
  const failing = async (sale, body, key) => { keys.push(key); throw new TypeError("offline"); };
  intent.begin();
  await assert.rejects(intent.submit("sale", payload, failing));
  await assert.rejects(intent.submit("sale", { ...payload, amount_ars: "040.0", reference: " REF-1 ", notes: " " }, failing));
  await assert.rejects(intent.submit("sale", { ...payload, amount_ars: "4e1" }, failing));
  assert.deepEqual(keys, ["key-1", "key-1", "key-1"]);
  await assert.rejects(intent.submit("sale", { ...payload, amount_ars: "99999999999999.98" }, failing));
  await assert.rejects(intent.submit("sale", { ...payload, amount_ars: "99999999999999.99" }, failing));
  assert.deepEqual(keys.slice(-2), ["key-2", "key-3"]);
});

test("409 payload conflict retains the standard message and unchanged retry key", async () => {
  const originalFetch = global.fetch;
  setAuthTokenProvider(async () => "local-test-token");
  const message = "La solicitud de cobro ya se utilizó con datos diferentes";
  const keys = [];
  let generated = 0;
  const intent = createSalePaymentIntent(() => `key-${++generated}`);
  intent.begin();
  global.fetch = async (url, init) => {
    keys.push(init.headers.get("Idempotency-Key"));
    return new Response(JSON.stringify({ error: { code: "sale_payment_idempotency_conflict", message } }), { status: 409 });
  };
  try {
    for (let index = 0; index < 2; index++) {
      await assert.rejects(intent.submit("sale", payload), error => {
        assert.equal(error.status, 409);
        assert.equal(error.code, "sale_payment_idempotency_conflict");
        assert.equal(getApiErrorMessage(error), message);
        return true;
      });
    }
    assert.deepEqual(keys, ["key-1", "key-1"]);
  } finally { global.fetch = originalFetch; setAuthTokenProvider(null); }
});

test("legacy service calls do not acquire an idempotency header or put a key in the body", async () => {
  const originalFetch = global.fetch;
  setAuthTokenProvider(async () => "local-test-token");
  global.fetch = async (url, init) => {
    assert.equal(init.headers.has("Idempotency-Key"), false);
    assert.deepEqual(JSON.parse(init.body), payload);
    return response();
  };
  try { await createSalePayment("sale", payload); } finally { global.fetch = originalFetch; setAuthTokenProvider(null); }
});

// Exercise the actual panel's useRef and event handlers across rerenders.
let current;
const hooks = { ...React,
  useState(initial) {
    const h = current, index = h.index++;
    if (!(index in h.values)) h.values[index] = initial;
    return [h.values[index], value => { h.values[index] = typeof value === "function" ? value(h.values[index]) : value; }];
  },
  useRef(initial) { const h = current, index = h.index++; return h.values[index] ??= { current: initial }; },
  useMemo(fn) { current.index++; return fn(); },
  useCallback(fn) { current.index++; return fn; },
  useEffect(fn) { const h = current, index = h.index++; if (!(index in h.values)) { h.values[index] = true; h.effects.push(fn); } },
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return hooks;
  if (name === "react-dom") return { createPortal: child => child };
  if (name === "@/features/clinic/clinic-context") return { useClinic: () => ({ preferences: null }) };
  if (name === "@/features/sales/components/payment-methods-screen") return { labelPaymentType: value => value };
  if (name === "@/features/purchases/components/purchase-helpers") return {
    formatPurchaseCurrency: value => value, formatPurchaseDateTime: value => value, formatPurchaseUser: () => "User",
  };
  return load.call(this, name, ...args);
};
const { SalePaymentsPanel } = require("./components/sale-payments-panel.tsx");
Module._load = load;
function find(tree, predicate) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) return tree.map(child => find(child, predicate)).find(Boolean) || null;
  if (predicate(tree)) return tree;
  return find(tree.props?.children, predicate);
}
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };

test("actual panel keeps a UUID through rerenders and network errors and shows payload conflicts", async () => {
  const originalFetch = global.fetch, originalCrypto = global.crypto, originalDocument = global.document;
  setAuthTokenProvider(async () => "local-test-token");
  let generated = 0;
  Object.defineProperty(global, "crypto", { configurable: true, value: { randomUUID: () => `uuid-${++generated}` } });
  global.document = { body: {} };
  const keys = [];
  let outcome = "network";
  global.fetch = async (url, init) => {
    if (init.method === "GET") return new Response(JSON.stringify({ data: [{ id: "cash", label: "Cash", sort_order: 0 }] }));
    keys.push(init.headers.get("Idempotency-Key"));
    if (outcome === "network") throw new TypeError("Lost response");
    if (outcome === "conflict") return new Response(JSON.stringify({ error: { code: "sale_payment_idempotency_conflict", message: "La solicitud de cobro ya se utilizó con datos diferentes" } }), { status: 409 });
    return response(200);
  };
  const h = { values: [], effects: [] };
  const sale = { id: "sale", status: "confirmed", total_ars: "100.00", paid_total_ars: "0.00", balance_due_ars: "100.00", payment_status: "unpaid", payments: [] };
  let updated = 0;
  const render = () => { h.index = 0; current = h; const tree = SalePaymentsPanel({ sale, onUpdated: async () => { updated++; } }); h.effects.splice(0).forEach(fn => fn()); return tree; };
  const form = () => find(render(), node => node.type === "form" && node.props["aria-labelledby"] === "sale-payment-title");
  try {
    render(); await flush(); render();
    assert.equal(generated, 0);
    find(render(), node => node.type === "button" && node.props.className === "primary-button").props.onClick();
    assert.equal(generated, 1);
    render(); render(); assert.equal(generated, 1);
    await form().props.onSubmit({ preventDefault() {} });
    assert.match(JSON.stringify(form()), /Reintenta sin cambiar los datos/);
    render(); outcome = "conflict";
    await form().props.onSubmit({ preventDefault() {} });
    assert.match(JSON.stringify(form()), /La solicitud de cobro ya se utilizó con datos diferentes/);
    outcome = "success";
    await form().props.onSubmit({ preventDefault() {} });
    assert.equal(updated, 1);
    assert.equal(form(), null);
    assert.deepEqual(keys, ["uuid-1", "uuid-1", "uuid-1"]);
    find(render(), node => node.type === "button" && node.props.className === "primary-button").props.onClick();
    assert.equal(generated, 2);
  } finally {
    global.fetch = originalFetch; global.document = originalDocument;
    setAuthTokenProvider(null);
    Object.defineProperty(global, "crypto", { configurable: true, value: originalCrypto });
  }
});
