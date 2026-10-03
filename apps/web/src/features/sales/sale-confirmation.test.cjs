const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const ts = require("typescript");
const React = require("react");

// Follow P.4: installed TypeScript + Node, exercising real handlers across rerenders.
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

const { saleConfirmationAmounts, parseSaleMoney, createSaleConfirmationIntent, saleConfirmationRows, confirmationPayload, createSaleConfirmationRowsIntent, formatSaleConfirmationMoney } = require("./components/sale-confirmation-helpers.ts");
const { confirmSale } = require("../../services/sales.ts");
const { setAuthTokenProvider } = require("../../lib/api.ts");
let current;
const hooks = { ...React,
  useState(initial) {
    const h = current, index = h.index++;
    if (!(index in h.values)) h.values[index] = initial;
    return [h.values[index], value => { h.values[index] = typeof value === "function" ? value(h.values[index]) : value; }];
  },
  useRef(initial) { const h = current, index = h.index++; return h.values[index] ??= { current: initial }; },
  useCallback(fn, dependencies) {
    const h = current, index = h.index++;
    if (!h.values[index] || dependencies.some((value, i) => value !== h.values[index].dependencies[i])) h.values[index] = { fn, dependencies };
    return h.values[index].fn;
  },
  useEffect(fn, dependencies) {
    const h = current, index = h.index++;
    if (!h.values[index] || dependencies.some((value, i) => value !== h.values[index][i])) {
      h.values[index] = dependencies; h.effects.push(fn);
    }
  },
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return hooks;
  if (name === "react-dom") return { createPortal: child => child };
  if (name === "next/link") return () => null;
  if (name === "@/features/clinic/clinic-context") return { useClinic: () => ({ preferences: null }) };
  if (name === "@/features/sales/components/sale-payments-panel") return { SalePaymentsPanel: () => null };
  if (name === "@/features/sales/components/sale-fiscal-document-panel") return { SaleFiscalDocumentPanel: () => null };
  return load.call(this, name, ...args);
};
const { SaleConfirmationModal } = require("./components/sale-confirmation-modal.tsx");
const { SaleDetailScreen } = require("./components/sale-detail-screen.tsx");
Module._load = load;

function find(tree, predicate) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) return tree.map(child => find(child, predicate)).find(Boolean) || null;
  if (predicate(tree)) return tree;
  return find(tree.props?.children, predicate);
}
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
const event = { preventDefault() {} };
const sale = { id: "sale", currency: "ARS", status: "draft", sale_date: "2026-10-01", created_at: "2026-10-01T12:00:00Z", updated_at: "2026-10-01T12:00:00Z", total_ars: "50000.00", subtotal_ars: "50000.00", discount_total_ars: "0.00", paid_total_ars: "0.00", balance_due_ars: "50000.00", payment_status: null, items: [], payments: [] };
const methods = [{ id: "cash", label: "Efectivo", is_active: true, sort_order: 0 }, { id: "bank", label: "Transferencia", is_active: true, sort_order: 1 }, { id: "off", label: "Inactivo", is_active: false, sort_order: 2 }];
const confirmed = { ...sale, status: "confirmed", paid_total_ars: "50000.00", balance_due_ars: "0.00", payment_status: "paid", payments: [{ id: "payment-1" }] };
const response = (data = confirmed, status = 200, headers = {}) => new Response(JSON.stringify({ data, meta: {} }), { status, headers });

async function setup(t, total = "50000.00", outcome) {
  const original = { fetch: global.fetch, crypto: global.crypto, document: global.document };
  let generated = 0, closed = 0;
  const results = [], requests = [], reads = [], focuses = [];
  Object.defineProperty(global, "crypto", { configurable: true, value: { randomUUID: () => `uuid-${++generated}` } });
  global.document = { body: { style: {} }, activeElement: null, addEventListener() {}, removeEventListener() {}, getElementById(id) { return { focus() { focuses.push(id); } }; } };
  setAuthTokenProvider(async () => "test-token");
  global.fetch = async (url, init) => {
    if (init.method === "GET") { reads.push(new URL(url).pathname + new URL(url).search); return response(methods); }
    requests.push({ body: JSON.parse(init.body), key: init.headers.get("Idempotency-Key") });
    return outcome ? outcome(requests.length, requests.at(-1)) : response();
  };
  t.after(() => {
    global.fetch = original.fetch; global.document = original.document;
    Object.defineProperty(global, "crypto", { configurable: true, value: original.crypto });
    setAuthTokenProvider(null);
  });
  const h = { values: [], effects: [] };
  const props = { sale: { ...sale, total_ars: total }, onConfirmed: value => results.push(value), onClose: () => { closed++; } };
  const render = () => {
    h.index = 0; current = h;
    const tree = SaleConfirmationModal(props);
    h.effects.splice(0).forEach(fn => fn());
    return tree;
  };
  const input = label => find(render(), node => node.props?.["aria-label"] === label);
  const mode = value => find(render(), node => node.type === "input" && node.props.value === value).props.onChange();
  const change = (label, value) => input(label).props.onChange({ target: { value } });
  const form = () => find(render(), node => node.type === "form");
  render(); await flush(); render();
  return { render, input, mode, change, form, results, requests, reads, focuses,
    add: () => input("Agregar forma de pago").props.onClick(),
    remove: index => input(`Quitar pago ${index}`).props.onClick(),
    generated: () => generated, closed: () => closed };
}

test("partial summary is exact in cents and supports the clinic's decimal comma", () => {
  assert.deepEqual(saleConfirmationAmounts("50000.00", "partial", "30000,00"), { payment: "30000.00", balance: "20000.00", error: null });
  assert.deepEqual(saleConfirmationAmounts("99999999999999.99", "partial", "99999999999999.98"), { payment: "99999999999999.98", balance: "0.01", error: null });
  assert.equal(parseSaleMoney("99999999999999.99"), BigInt("9999999999999999"));
});

for (const amount of ["0", "-1", "50000", "50000.01", "60000", "1.001", "100000000000000", "NaN", "Infinity", "", "1e3"]) {
  test(`invalid partial amount ${JSON.stringify(amount)} is rejected before any POST`, async t => {
    const h = await setup(t);
    h.mode("partial"); h.change("Forma de pago", "bank"); h.change("Importe pagado", amount);
    await h.form().props.onSubmit(event);
    assert.equal(h.requests.length, 0);
    assert.ok(find(h.render(), node => node.props?.role === "alert"));
  });
}

for (const mode of ["full", "partial"]) test(`${mode} requires an active payment method`, async t => {
  const h = await setup(t);
  h.mode(mode);
  if (mode === "partial") h.change("Importe pagado", "30000");
  await h.form().props.onSubmit(event);
  assert.equal(h.requests.length, 0);
  assert.match(JSON.stringify(h.render()), /Selecciona una forma de pago disponible/);
  h.change("Forma de pago", "off");
  await h.form().props.onSubmit(event);
  assert.equal(h.requests.length, 0);
});

test("full payment starts with the editable total, sends initial_payment and a UUID, without received_at", async t => {
  const h = await setup(t);
  assert.equal(h.generated(), 0);
  h.mode("full"); h.change("Forma de pago", "cash");
  assert.equal(h.input("Importe").props.readOnly, undefined);
  assert.equal(h.input("Importe").props.value, "50000.00");
  h.render(); h.render(); assert.equal(h.generated(), 0);
  await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests, [{ key: "uuid-1", body: { confirm: true, initial_payment: { payment_method_id: "cash", amount_ars: "50000.00", reference: null, notes: null } } }]);
  assert.deepEqual(h.results, [confirmed]);
});

test("partial payment shows the balance live and sends normalized cents and optional text", async t => {
  const h = await setup(t);
  h.mode("partial"); h.change("Forma de pago", "bank"); h.change("Importe pagado", "30000,00");
  h.change("Referencia", "  REF-1 "); h.change("Notas", " Anticipo ");
  assert.match(JSON.stringify(h.render()), /20\.000/);
  await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests[0], { key: "uuid-1", body: { confirm: true, initial_payment: { payment_method_id: "bank", amount_ars: "30000.00", reference: "REF-1", notes: "Anticipo" } } });
});

test("pending sends the legacy body without a method or idempotency header", async t => {
  const h = await setup(t);
  assert.equal(h.input("Forma de pago"), null);
  assert.match(JSON.stringify(h.render()), /El saldo quedará pendiente/);
  await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests, [{ body: { confirm: true }, key: null }]);
  assert.equal(h.generated(), 0);
});

test("zero total hides modes, avoids the methods catalog and confirms without a payment", async t => {
  const h = await setup(t, "0.00");
  assert.match(JSON.stringify(h.render()), /Venta sin importe a cobrar/);
  assert.equal(find(h.render(), node => node.type === "input" && node.props.type === "radio"), null);
  assert.deepEqual(h.reads, []);
  await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests, [{ body: { confirm: true }, key: null }]);
});

test("catalog requests active methods only and filters inactive entries", async t => {
  const h = await setup(t);
  h.mode("full");
  assert.deepEqual(h.reads, ["/api/v1/payment-methods?active=true"]);
  assert.match(JSON.stringify(h.render()), /Efectivo/);
  assert.doesNotMatch(JSON.stringify(h.render()), /Inactivo/);
});

test("network loss retains the key across renders; replay header is a normal success", async t => {
  const h = await setup(t, "50000.00", count => {
    if (count === 1) throw new TypeError("Response lost after commit");
    return response(confirmed, 200, { "Idempotency-Replayed": "true" });
  });
  h.mode("full"); h.change("Forma de pago", "cash");
  await h.form().props.onSubmit(event);
  assert.match(JSON.stringify(h.render()), /Reintenta sin cambiar los datos/);
  assert.equal(h.results.length, 0); assert.equal(h.closed(), 0);
  h.render(); h.render();
  await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests.map(request => request.key), ["uuid-1", "uuid-1"]);
  assert.deepEqual(h.requests[0].body, h.requests[1].body);
  assert.deepEqual(h.results, [confirmed]);
});

test("pending retry recovers a committed legacy confirmation without a second POST", async t => {
  const h = await setup(t, "50000.00", () => { throw new TypeError("Response lost after commit"); });
  await h.form().props.onSubmit(event);
  assert.match(JSON.stringify(h.render()), /Reintenta sin cambiar los datos/);
  assert.equal(h.results.length, 0);
  global.fetch = async (url, init) => {
    assert.equal(init.method, "GET");
    assert.equal(new URL(url).pathname, "/api/v1/sales/sale");
    return response({ ...confirmed, payments: [], paid_total_ars: "0.00", balance_due_ars: "50000.00", payment_status: "unpaid" });
  };
  await h.form().props.onSubmit(event);
  assert.equal(h.requests.length, 1);
  assert.equal(h.results[0].payment_status, "unpaid");
  assert.deepEqual(h.requests[0], { body: { confirm: true }, key: null });
});

for (const field of ["Forma de pago", "Importe pagado", "Referencia", "Notas"]) test(`editing ${field} after an error rotates the intent key`, async t => {
  const h = await setup(t, "50000.00", () => { throw new TypeError("offline"); });
  h.mode("partial"); h.change("Forma de pago", "cash"); h.change("Importe pagado", "30000");
  await h.form().props.onSubmit(event);
  h.change(field, { "Forma de pago": "bank", "Importe pagado": "30001", "Referencia": "REF-2", "Notas": "Otra nota" }[field]);
  await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests.map(request => request.key), ["uuid-1", "uuid-2"]);
});

for (const code of ["sale_payment_idempotency_conflict", "payment_method_inactive", "payment_method_not_found", "sale_payment_exceeds_balance", "sale_insufficient_stock", "sale_not_editable", "validation_error"]) {
  test(`backend error ${code} remains visible without closing or declaring success`, async t => {
    const message = `Mensaje de negocio: ${code}`;
    const h = await setup(t, "50000.00", () => new Response(JSON.stringify({ error: { code, message } }), { status: code === "validation_error" ? 422 : 409 }));
    h.mode("full"); h.change("Forma de pago", "cash");
    await h.form().props.onSubmit(event);
    assert.ok(JSON.stringify(h.render()).includes(message));
    assert.equal(h.results.length, 0); assert.equal(h.closed(), 0);
  });
}

test("synchronous double-submit guard blocks another POST and disables controls while pending", async t => {
  let release;
  const h = await setup(t, "50000.00", () => new Promise(resolve => { release = () => resolve(response()); }));
  h.mode("full"); h.change("Forma de pago", "cash");
  const submit = h.form().props.onSubmit;
  const first = submit(event), second = submit(event);
  await flush();
  assert.equal(h.requests.length, 1);
  assert.equal(find(h.render(), node => node.type === "button" && node.props.type === "submit").props.disabled, true);
  assert.equal(find(h.render(), node => node.type === "fieldset").props.disabled, true);
  assert.match(JSON.stringify(h.render()), /Confirmando/);
  release(); await first; await second;
  assert.equal(h.results.length, 1);
});

test("legacy confirmSale callers remain valid", async t => {
  const h = await setup(t);
  await confirmSale("sale");
  assert.deepEqual(h.requests, [{ body: { confirm: true }, key: null }]);
});

test("confirmation intention discards its key on success and guards completed submissions", async () => {
  let generated = 0;
  const intent = createSaleConfirmationIntent(() => `key-${++generated}`);
  const payload = { payment_method_id: "cash", amount_ars: "50000.00" };
  assert.equal(await intent.submit("sale", payload, async () => {}), true);
  assert.equal(await intent.submit("sale", payload, async () => { throw Error("duplicate"); }), false);
  assert.equal(intent.begin(), true);
  assert.equal(generated, 2);
});

test("draft detail opens the modal; success replaces summary/history and closes immediately", async t => {
  await setup(t);
  global.fetch = async () => response(sale);
  const h = { values: [], effects: [] };
  const render = () => {
    h.index = 0; current = h;
    const tree = SaleDetailScreen({ saleId: "sale" });
    h.effects.splice(0).forEach(fn => fn());
    return tree;
  };
  render(); await flush();
  const button = find(render(), node => node.type === "button" && JSON.stringify(node.props.children).includes("Confirmar venta"));
  assert.ok(button); button.props.onClick();
  const modal = find(render(), node => node.type === SaleConfirmationModal);
  assert.ok(modal);
  modal.props.onConfirmed(confirmed);
  const updated = render();
  assert.equal(find(updated, node => node.type === SaleConfirmationModal), null);
  assert.ok(find(updated, node => node.props?.sale?.payments?.[0]?.id === "payment-1"));
  assert.match(JSON.stringify(updated), /Confirmada/);
});

const row = (amount, method = "cash", id = "row") => ({ id, payment_method_id: method, amount_ars: amount, reference: "", notes: "" });
const submitButton = h => find(h.render(), n => n.type === "button" && n.props.type === "submit");
function fillRows(h, amounts, selected = amounts.map(() => "cash")) {
  for (let i = 1; i < amounts.length; i++) h.add();
  amounts.forEach((amount, index) => {
    h.change(amounts.length === 1 ? "Forma de pago" : `Forma de pago ${index + 1}`, selected[index]);
    h.change(amounts.length === 1 ? "Importe pagado" : `Importe ${index + 1}`, amount);
  });
}
for (const [mode, amounts, paid, balance] of [
  ["full", ["20", "80"], "100.00", "0.00"],
  ["full", ["20", "30", "50"], "100.00", "0.00"],
  ["partial", ["20", "30"], "50.00", "50.00"],
]) test(`${mode} with ${amounts.length} rows sends the ordered batch and updates detail`, async t => {
  const batchSale = { ...confirmed, total_ars: "100.00", paid_total_ars: paid, balance_due_ars: balance,
    payment_status: mode === "full" ? "paid" : "partial", payments: amounts.map((amount, i) => ({ id: `p-${i}`, amount_ars: amount })) };
  const h = await setup(t, "100.00", () => response(batchSale)); h.mode(mode); fillRows(h, amounts);
  h.change("Referencia 1", " REF-1 "); h.change(`Notas ${amounts.length}`, " Nota final ");
  assert.equal(submitButton(h).props.disabled, false); await h.form().props.onSubmit(event);
  const request = h.requests[0]; assert.equal(request.key, "uuid-1");
  assert.equal("initial_payment" in request.body, false);
  assert.deepEqual(request.body.initial_payments.map(p => p.amount_ars), amounts.map(a => `${a}.00`));
  assert.ok(request.body.initial_payments.every(p => p.payment_method_id === "cash" && !("received_at" in p)));
  assert.equal(request.body.initial_payments[0].reference, "REF-1");
  assert.equal(request.body.initial_payments.at(-1).notes, "Nota final");
  assert.deepEqual(h.results, [batchSale]);
});
test("add/remove preserves order and stable IDs, retains one row, and moves focus", async t => {
  const h = await setup(t, "100.00"); h.mode("partial"); h.change("Forma de pago", "bank"); h.change("Importe pagado", "20");
  const firstId = h.input("Forma de pago").props.id;
  h.add(); h.change("Forma de pago 2", "cash"); h.change("Importe 2", "30");
  assert.ok(h.focuses.at(-1).endsWith("payment-2-method"));
  h.add(); h.change("Forma de pago 3", "bank"); h.change("Importe 3", "10");
  const thirdId = h.input("Forma de pago 3").props.id; h.remove(2); h.render();
  assert.equal(h.input("Forma de pago 1").props.id, firstId); assert.equal(h.input("Forma de pago 2").props.id, thirdId);
  assert.equal(h.input("Importe 2").props.value, "10"); assert.equal(h.focuses.at(-1), firstId);
  h.remove(2); assert.equal(h.input("Forma de pago").props.id, firstId); assert.equal(h.input("Quitar pago 1"), null);
  await h.form().props.onSubmit(event);
  assert.equal(h.requests[0].body.initial_payment.amount_ars, "20.00"); assert.equal("initial_payments" in h.requests[0].body, false);
});
test("twenty valid rows are accepted and the add handler cannot exceed twenty", async t => {
  const h = await setup(t, "100.00"); h.mode("full"); fillRows(h, Array(20).fill("5"));
  assert.equal(h.input("Agregar forma de pago").props.disabled, true); h.add(); assert.equal(h.input("Forma de pago 21"), null);
  await h.form().props.onSubmit(event); assert.equal(h.requests[0].body.initial_payments.length, 20);
});
for (const [mode, amounts, message] of [
  ["full", ["20", "30"], "Faltan"], ["full", ["60", "50"], "supera la venta por"],
  ["partial", ["20", "80"], "Usa “Pago completo”"], ["partial", ["60", "50"], "supera la venta por"],
]) test(`${mode} blocks sum ${amounts.join("+")} without silently changing mode`, async t => {
  const h = await setup(t, "100.00"); h.mode(mode); fillRows(h, amounts);
  assert.match(JSON.stringify(h.render()), new RegExp(message)); assert.equal(submitButton(h).props.disabled, true);
  await h.form().props.onSubmit(event); assert.equal(h.requests.length, 0);
  assert.equal(find(h.render(), n => n.type === "input" && n.props.value === mode).props.checked, true);
});
for (const amount of ["0", "-1", "1.001", "NaN", "Infinity", "100000000000000", ""]) test(`second-row invalid amount ${JSON.stringify(amount)} has an associated error`, async t => {
  const h = await setup(t, "100.00"); h.mode("partial"); fillRows(h, ["20", amount]);
  const field = h.input("Importe 2"); assert.equal(field.props["aria-invalid"], true);
  assert.ok(find(h.render(), n => n.props?.id === field.props["aria-describedby"]));
  await h.form().props.onSubmit(event); assert.equal(h.requests.length, 0);
});
test("every row requires an active method", async t => {
  const h = await setup(t, "100.00"); h.mode("full"); fillRows(h, ["20", "80"], ["cash", ""]);
  assert.equal(h.input("Forma de pago 2").props["aria-invalid"], true);
  assert.ok(h.input("Forma de pago 2").props["aria-describedby"]);
  await h.form().props.onSubmit(event); assert.equal(h.requests.length, 0);
  h.change("Forma de pago 2", "off"); await h.form().props.onSubmit(event); assert.equal(h.requests.length, 0);
  h.change("Forma de pago 2", "bank"); await h.form().props.onSubmit(event); assert.equal(h.requests.length, 1);
});
test("0.10 + 0.20 equals 0.30 and a cent balance at the P.2 limit stays exact", () => {
  const full = saleConfirmationRows("0.30", "full", [row("0,10"), row("0.20")], methods);
  assert.equal(full.error, null); assert.equal(full.payment, "0.30"); assert.equal(full.balance, "0.00");
  const partial = saleConfirmationRows("99999999999999.99", "partial", [row("99999999999999.97"), row("0.01")], methods);
  assert.equal(partial.error, null); assert.equal(partial.payment, "99999999999999.98"); assert.equal(partial.balance, "0.01");
  assert.equal(saleConfirmationRows("100.00", "full", [row("99999999999999.99"), row("99999999999999.99")], methods).error, "overpaid");
});
test("pending ignores retained rows, sends no key and never includes payment fields", async t => {
  assert.deepEqual(confirmationPayload([]), { confirm: true });
  const h = await setup(t, "100.00"); h.mode("partial"); fillRows(h, ["20", "30"]); h.mode("pending");
  assert.equal(h.input("Agregar forma de pago"), null); await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests, [{ body: { confirm: true }, key: null }]);
});
test("batch timeout retains payload/key across rerenders and replay is success", async t => {
  const h = await setup(t, "100.00", count => {
    if (count === 1) throw new TypeError("response lost"); return response(confirmed, 200, { "Idempotency-Replayed": "true" });
  });
  h.mode("full"); fillRows(h, ["20", "30", "50"]); await h.form().props.onSubmit(event);
  h.render(); h.render(); assert.equal(h.results.length, 0); assert.equal(h.generated(), 1);
  await h.form().props.onSubmit(event); assert.deepEqual(h.requests[0], h.requests[1]); assert.deepEqual(h.results, [confirmed]);
});
for (const field of ["Forma de pago 2", "Importe 2", "Referencia 2", "Notas 2"]) test(`editing batch ${field} invalidates lazily then rotates key`, async t => {
  const h = await setup(t, "100.00", () => { throw new TypeError("offline"); });
  h.mode("partial"); fillRows(h, ["20", "30"]); await h.form().props.onSubmit(event);
  h.change(field, { "Forma de pago 2": "bank", "Importe 2": "31", "Referencia 2": "REF-2", "Notas 2": "Notes" }[field]);
  h.render(); assert.equal(h.generated(), 1); await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests.map(r => r.key), ["uuid-1", "uuid-2"]);
});
test("normalized equivalent edits preserve the retry key", async t => {
  const h = await setup(t, "100.00", () => { throw new TypeError("offline"); });
  h.mode("partial"); fillRows(h, ["20", "30"]); h.change("Referencia 2", "REF"); await h.form().props.onSubmit(event);
  h.change("Importe 2", "30,00"); h.change("Referencia 2", " REF "); h.change("Notas 2", "   ");
  await h.form().props.onSubmit(event); assert.deepEqual(h.requests[0], h.requests[1]);
});
test("individual to batch to individual uses separate fresh keys", async t => {
  const h = await setup(t, "100.00", () => { throw new TypeError("offline"); });
  h.mode("partial"); h.change("Forma de pago", "cash"); h.change("Importe pagado", "20"); await h.form().props.onSubmit(event);
  h.add(); h.change("Forma de pago 2", "bank"); h.change("Importe 2", "30"); await h.form().props.onSubmit(event);
  h.remove(2); await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests.map(r => r.key), ["uuid-1", "uuid-2", "uuid-3"]);
  assert.deepEqual(h.requests.map(r => "initial_payments" in r.body), [false, true, false]);
});
test("adding/removing before retry invalidates even if final payload is unchanged", async t => {
  const h = await setup(t, "100.00", () => { throw new TypeError("offline"); });
  h.mode("partial"); h.change("Forma de pago", "cash"); h.change("Importe pagado", "20"); await h.form().props.onSubmit(event);
  h.add(); h.remove(2); await h.form().props.onSubmit(event);
  assert.deepEqual(h.requests.map(r => r.key), ["uuid-1", "uuid-2"]); assert.deepEqual(h.requests[0].body, h.requests[1].body);
});
test("ordered payload change rotates batch key and success discards it", async () => {
  let generated = 0; const intent = createSaleConfirmationRowsIntent(() => `k-${++generated}`);
  const payload = [{ payment_method_id: "cash", amount_ars: "20" }, { payment_method_id: "cash", amount_ars: "30" }]; const sent = [];
  const fail = async (id, rows, key) => { sent.push(key); throw Error("offline"); };
  await assert.rejects(intent.submit("sale", payload, fail)); await assert.rejects(intent.submit("sale", [...payload].reverse(), fail));
  assert.deepEqual(sent, ["k-1", "k-2"]);
  assert.equal(await intent.submit("sale", [...payload].reverse(), async () => {}), true);
  assert.equal(await intent.submit("sale", payload, async () => assert.fail("duplicate")), false); assert.equal(generated, 2);
});
test("batch 409 stays visible and keeps rows available for correction", async t => {
  const h = await setup(t, "100.00", () => new Response(JSON.stringify({ error: { code: "sale_payment_batch_idempotency_conflict", message: "El lote ya se utilizó con otros datos" } }), { status: 409 }));
  h.mode("full"); fillRows(h, ["20", "80"]); await h.form().props.onSubmit(event);
  assert.match(JSON.stringify(h.render()), /El lote ya se utilizó con otros datos/);
  assert.equal(h.input("Importe 2").props.value, "80"); assert.equal(h.results.length, 0); assert.equal(h.closed(), 0);
});
test("batch synchronous guard freezes row actions and inputs while sending once", async t => {
  let release; const h = await setup(t, "100.00", () => new Promise(resolve => { release = () => resolve(response()); }));
  h.mode("full"); fillRows(h, ["20", "80"]); const submit = h.form().props.onSubmit;
  const first = submit(event), second = submit(event); await flush(); assert.equal(h.requests.length, 1);
  assert.equal(h.input("Agregar forma de pago").props.disabled, true); assert.equal(h.input("Quitar pago 2").props.disabled, true);
  assert.equal(find(h.render(), n => n.props?.className === "sale-confirmation-row").props.disabled, true);
  h.add(); h.remove(2); h.change("Importe 2", "81"); assert.equal(h.input("Importe 2").props.value, "80"); assert.equal(h.input("Forma de pago 3"), null);
  release(); await first; await second; assert.equal(h.results.length, 1);
});
test("batch success replaces every history row and balance immediately", async t => {
  await setup(t); global.fetch = async () => response(sale); const state = { values: [], effects: [] };
  const render = () => { state.index = 0; current = state; const tree = SaleDetailScreen({ saleId: "sale" }); state.effects.splice(0).forEach(fn => fn()); return tree; };
  render(); await flush(); find(render(), n => n.type === "button" && JSON.stringify(n.props.children).includes("Confirmar venta")).props.onClick();
  const updatedSale = { ...confirmed, paid_total_ars: "25000.00", balance_due_ars: "25000.00", payment_status: "partial",
    payments: [{ id: "batch-1", amount_ars: "10000.00" }, { id: "batch-2", amount_ars: "15000.00" }] };
  find(render(), n => n.type === SaleConfirmationModal).props.onConfirmed(updatedSale); const updated = render();
  assert.equal(find(updated, n => n.type === SaleConfirmationModal), null);
  assert.ok(find(updated, n => n.props?.sale?.payments?.length === 2 && n.props.sale.balance_due_ars === "25000.00"));
});

for (const [value, expected] of [["99999999999999.99", "99.999.999.999.999,99"], ["-0.01", "-ARS\u00a00,01"], ["199999999999999.98", "199.999.999.999.999,98"]]) {
  test(`exact currency display ${value}`, () => {
    assert.ok(formatSaleConfirmationMoney(value, {currencyCode: "ARS", locale: "es-AR"}).includes(expected));
  });
}
