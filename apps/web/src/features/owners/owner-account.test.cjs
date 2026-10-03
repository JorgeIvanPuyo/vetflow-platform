const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const React = require("react");
const ts = require("typescript");

// Existing Node/TypeScript approach: real component, service and API handlers.
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
let current;
const hooks = { ...React,
  useState(initial) {
    const h = current, index = h.index++;
    if (!(index in h.values)) h.values[index] = initial;
    return [h.values[index], value => { h.values[index] = typeof value === "function" ? value(h.values[index]) : value; }];
  },
  useCallback(fn, dependencies) {
    const h = current, index = h.index++;
    if (!h.values[index] || dependencies.some((value, i) => value !== h.values[index].dependencies[i])) h.values[index] = { dependencies, callback: fn };
    return h.values[index].callback;
  },
  useEffect(fn, dependencies) {
    const h = current, index = h.index++;
    if (!h.values[index] || dependencies.some((value, i) => value !== h.values[index].dependencies[i])) {
      h.values[index]?.cleanup?.();
      h.values[index] = { dependencies };
      h.effects.push(() => { h.values[index].cleanup = fn(); });
    }
  },
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return hooks;
  if (name === "next/link") return () => null;
  return load.call(this, name, ...args);
};
const { OwnerAccountScreen } = require("./components/owner-account-screen.tsx");
Module._load = load;
const { setAuthTokenProvider } = require("../../lib/api.ts");

function find(tree, predicate) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) return tree.map(child => find(child, predicate)).find(Boolean) || null;
  return predicate(tree) ? tree : find(tree.props?.children, predicate);
}
function content(tree) {
  if (Array.isArray(tree)) return tree.map(content).join("");
  if (tree && typeof tree === "object") return content(tree.props?.children);
  return typeof tree === "string" || typeof tree === "number" ? String(tree) : "";
}
const flush = async () => { for (let i = 0; i < 50; i++) await Promise.resolve(); };
const sale = {
  sale_id: "aaaa1111-2222-3333-4444-555555555555", sale_date: "2026-10-02", confirmed_at: "2026-10-02T13:00:00Z",
  patient_id: "patient", patient_name_snapshot: "Luna", currency: "ARS", total_ars: "100.00", paid_total_ars: "30.00", balance_due_ars: "70.00", payment_status: "partial",
};
const config = { owner_id: "owner", tracking_configured: true, tracking_started_at: "2026-10-01T00:00:00Z", currency: "ARS", locale: "es-AR" };
const meta = { page: 1, page_size: 20, total: 1, total_pages: 1 };
const event = { event_id: "payment_recorded:payment", type: "payment_recorded", occurred_at: "2026-10-02T14:00:00Z", sale_id: sale.sale_id,
  sale_date: sale.sale_date, patient_id: "patient", patient_name_snapshot: "Luna", currency: "ARS", payment_id: "payment", amount_ars: "30.00", payment_method_label: "Efectivo",
  reference: "Ref 123", notes: "Pago posterior", reason: null, payment_is_active: true };
const pending = (overrides = {}, pagination = {}) => ({ data: { ...config, total_outstanding_ars: "135000.00", open_sales_count: 2, sales: [sale], ...overrides }, meta: { ...meta, ...pagination } });
const activity = (overrides = {}, pagination = {}) => ({ data: { ...config, events: [event], ...overrides }, meta: { ...meta, ...pagination } });
const wire = data => new Response(JSON.stringify(data), { status: 200 });
function setup(t, options = {}) {
  const previousFetch = global.fetch, previousWindow = global.window;
  const listeners = new Map(), requests = [], h = { values: [], effects: [], props: { ownerId: "owner" } };
  global.window = { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) };
  setAuthTokenProvider(async () => "test-token");
  global.fetch = async (url, init) => {
    const request = { url: new URL(url), init }; requests.push(request);
    if (options.respond) { const result = await options.respond(request); if (result !== undefined) return result; }
    if (request.url.pathname.endsWith("/activity")) return wire(options.activity || activity());
    if (request.url.pathname.endsWith("/receivables")) return wire(options.pending || pending());
    if (request.url.pathname === "/api/v1/patients") return wire({ data: [{ id: "patient", name: "Luna", owner_id: h.props.ownerId }], meta });
    return wire({ data: { id: h.props.ownerId, full_name: "Juan Pérez", is_active: options.archived !== true }, meta: {} });
  };
  h.render = () => { current = h; h.index = 0; const tree = OwnerAccountScreen(h.props); h.effects.splice(0).forEach(fn => fn()); return tree; };
  h.ready = async () => { h.render(); await flush(); return h.render(); };
  h.requests = requests; h.listeners = listeners;
  t.after(() => { h.values.forEach(value => value?.cleanup?.()); global.fetch = previousFetch; global.window = previousWindow; setAuthTokenProvider(null); });
  return h;
}
const button = (tree, label) => find(tree, node => node.type === "button" && content(node).includes(label));
const field = (tree, label) => find(tree, node => node.type === "label" && content(node).includes(label)).props.children[1];
const pagination = (tree, label) => find(tree, node => node.props?.label === label && node.props.meta);

test("summary remains global and pending sale cards show money, origin and status", async t => {
  const h = setup(t), tree = await h.ready();
  assert.match(content(tree), /Juan Pérez/); assert.match(content(tree), /135\.000,00/);
  assert.match(content(tree), /Ventas pendientes2/); assert.match(content(tree), /70,00/);
  assert.match(content(tree), /Luna/); assert.match(content(tree), /Cobro parcial/);
  assert.equal(find(tree, node => node.type === "h1").props.children, "Cuenta corriente");
});
test("activity includes method, effective date, reference, notes and exact signed amount", async t => {
  const tree = await setup(t).ready();
  assert.match(content(tree), /Pago registrado · Efectivo/); assert.match(content(tree), /− ARS\s*30,00/);
  assert.match(content(tree), /Referencia: Ref 123/); assert.match(content(tree), /Notas: Pago posterior/);
  assert.equal(find(tree, node => node.type === "time").props.dateTime, event.occurred_at);
});
test("voided payments retain original event and show a separate restoration", async t => {
  const tree = await setup(t, { activity: activity({ events: [{ ...event, payment_is_active: false }, { ...event, type: "payment_cancelled", event_id: "void", reason: "Error de carga", payment_is_active: false }] }) }).ready();
  assert.match(content(tree), /Este cobro fue anulado/); assert.match(content(tree), /Pago anulado/);
  assert.match(content(tree), /\+ ARS\s*30,00/); assert.match(content(tree), /Motivo: Error de carga/);
});
test("reversal has explanatory text without an invented credit or refund amount", async t => {
  const tree = await setup(t, { activity: activity({ events: [{ ...event, type: "sale_reversed", amount_ars: null, reason: "Cancelación" }] }) }).ready();
  assert.match(content(tree), /Venta revertida/); assert.match(content(tree), /no devuelve ni anula cobros automáticamente/);
  assert.equal(find(tree, node => node.props?.className === "owner-account-event-amount"), null);
});
test("date and patient filters reach P.11 while global balance and activity stay unchanged", async t => {
  const h = setup(t, { respond: request => request.url.searchParams.has("date_from") ? wire(pending({ sales: [] }, { total: 0, total_pages: 0 })) : undefined });
  let tree = await h.ready();
  field(tree, "Fecha desde").props.onChange({ target: { value: "2026-10-01" } });
  field(h.render(), "Fecha hasta").props.onChange({ target: { value: "2026-10-02" } });
  field(h.render(), "Paciente").props.onChange({ target: { value: "patient" } });
  find(h.render(), node => node.type === "form").props.onSubmit({ preventDefault() {} });
  tree = await h.ready();
  const request = h.requests.at(-1); assert.equal(request.url.searchParams.get("date_from"), "2026-10-01");
  assert.equal(request.url.searchParams.get("date_to"), "2026-10-02"); assert.equal(request.url.searchParams.get("patient_id"), "patient");
  assert.match(content(tree), /135\.000,00/); assert.match(content(tree), /No hay ventas pendientes que coincidan/);
  assert.match(content(tree), /Pago registrado/); assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/activity")).length, 1);
});
test("invalid date range is labelled and does not issue a filtered request", async t => {
  const h = setup(t); let tree = await h.ready(); const count = h.requests.length;
  field(tree, "Fecha desde").props.onChange({ target: { value: "2026-10-03" } });
  field(h.render(), "Fecha hasta").props.onChange({ target: { value: "2026-10-01" } });
  find(h.render(), node => node.type === "form").props.onSubmit({ preventDefault() {} });
  tree = await h.ready(); assert.match(content(tree), /La fecha desde debe/); assert.equal(h.requests.length, count);
});
test("clearing filters resets pending pagination only", async t => {
  const h = setup(t); let tree = await h.ready();
  field(tree, "Fecha desde").props.onChange({ target: { value: "2026-10-01" } });
  find(h.render(), node => node.type === "form").props.onSubmit({ preventDefault() {} });
  tree = await h.ready(); button(tree, "Limpiar filtros").props.onClick(); await h.ready();
  assert.equal(h.requests.at(-1).url.searchParams.has("date_from"), false);
  assert.equal(h.requests.at(-1).url.searchParams.get("page"), "1");
});
test("activity pagination is independent of pending rows and summary", async t => {
  const h = setup(t, { activity: activity({}, { total: 37, total_pages: 2 }) }); let tree = await h.ready();
  pagination(tree, "actividad").props.onPage(2); tree = await h.ready();
  assert.equal(h.requests.at(-1).url.pathname, "/api/v1/owners/owner/receivables/activity");
  assert.equal(h.requests.at(-1).url.searchParams.get("page"), "2"); assert.match(content(tree), /135\.000,00/);
  assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/receivables")).length, 1);
});
test("pending pagination does not refetch activity", async t => {
  const h = setup(t, { pending: pending({}, { total: 37, total_pages: 2 }) }); let tree = await h.ready();
  pagination(tree, "ventas pendientes").props.onPage(2); tree = await h.ready();
  assert.equal(h.requests.at(-1).url.searchParams.get("page"), "2");
  assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/activity")).length, 1);
});
test("loading states announce work and withhold financial assertions", t => {
  const h = setup(t, { respond: () => new Promise(() => {}) }), tree = h.render();
  assert.match(content(tree), /Cargando propietario/); assert.doesNotMatch(content(tree), /135\.000/);
  assert.equal(find(tree, node => node.props?.role === "status").props.children, "Cargando propietario…");
});
test("summary failure is announced without stale money", async t => {
  const h = setup(t, { respond: r => r.url.pathname.endsWith("/receivables") ? new Response(JSON.stringify({ error: { code: "failure", message: "Consulta fallida" } }), { status: 404 }) : undefined });
  const tree = await h.ready(); assert.match(content(tree), /Consulta fallida/); assert.doesNotMatch(content(tree), /135\.000/);
  assert.ok(find(tree, node => node.props?.role === "alert"));
});
test("activity failure preserves the current summary and sale list", async t => {
  const h = setup(t, { respond: r => r.url.pathname.endsWith("/activity") ? new Response(JSON.stringify({ error: { code: "failure", message: "Actividad fallida" } }), { status: 404 }) : undefined });
  const tree = await h.ready(); assert.match(content(tree), /Actividad fallida/); assert.match(content(tree), /135\.000,00/);
});
test("unconfigured tracking shows context without zero debt or historical events", async t => {
  const h = setup(t, { pending: pending({ tracking_configured: false, tracking_started_at: null, total_outstanding_ars: "0.00", open_sales_count: 0, sales: [] }) });
  const tree = await h.ready(); assert.match(content(tree), /aún no está configurado/); assert.doesNotMatch(content(tree), /0,00|Pago registrado|Saldo pendiente global/);
});
test("zero current balance still shows paid history", async t => {
  const tree = await setup(t, { pending: pending({ total_outstanding_ars: "0.00", open_sales_count: 0, sales: [] }) }).ready();
  assert.match(content(tree), /0,00/); assert.match(content(tree), /No hay ventas con saldo/); assert.match(content(tree), /Pago registrado/);
});
test("configured owner without eligible history has both empty states", async t => {
  const tree = await setup(t, { pending: pending({ total_outstanding_ars: "0.00", open_sales_count: 0, sales: [] }), activity: activity({ events: [] }) }).ready();
  assert.match(content(tree), /No hay ventas con saldo/); assert.match(content(tree), /Sin actividad desde/);
});
test("archived owner remains navigable and account is visible", async t => {
  const tree = await setup(t, { archived: true }).ready(); assert.match(content(tree), /Propietario archivado/); assert.match(content(tree), /135\.000,00/);
});
test("pending and historical sale links use existing detail navigation", async t => {
  const tree = await setup(t).ready();
  assert.ok(find(tree, node => node.props?.href === `/sales/${sale.sale_id}` && content(node).includes("Ver venta")));
  assert.ok(find(tree, node => node.props?.href === "/owners/owner"));
});
test("screen uses cards and semantic monetary lists without a horizontal table", async t => {
  const tree = await setup(t).ready(); assert.equal(find(tree, node => node.type === "table"), null);
  assert.ok(find(tree, node => node.type === "dl" && node.props.className === "owner-account-amounts"));
  assert.ok(find(tree, node => node.type === "ol" && node.props.className === "owner-account-activity"));
});
test("refresh and browser return refetch both resources using only GET", async t => {
  const h = setup(t); let tree = await h.ready(); button(tree, "Actualizar").props.onClick(); await h.ready();
  assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/activity")).length, 2);
  assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/receivables")).length, 2);
  h.listeners.get("pageshow")(); await h.ready(); h.listeners.get("focus")(); await h.ready();
  assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/activity")).length, 4);
  assert.ok(h.requests.every(r => r.init.method === "GET"));
});
test("large aggregate preserves exact cents in the screen", async t => {
  const tree = await setup(t, { pending: pending({ total_outstanding_ars: "199999999999999.95" }) }).ready();
  assert.match(content(tree), /199\.999\.999\.999\.999,95/);
});
test("patient-filter failure leaves date filters and account usable", async t => {
  const h = setup(t, { respond: r => r.url.pathname === "/api/v1/patients" ? new Response(JSON.stringify({ error: { code: "failure", message: "Pacientes fallidos" } }), { status: 403 }) : undefined });
  const tree = await h.ready(); assert.match(content(tree), /No pudimos cargar el filtro de pacientes/);
  assert.equal(field(tree, "Paciente").props.disabled, true); assert.match(content(tree), /135\.000,00/);
});

test("a late response from a previous owner cannot overwrite the current account", async t => {
  let resolveOld;
  const h = setup(t, { respond: r => {
    if (r.url.pathname === "/api/v1/owners/owner/receivables") return new Promise(resolve => { resolveOld = resolve; });
    if (r.url.pathname === "/api/v1/owners/other/receivables") return wire(pending({ owner_id: "other", total_outstanding_ars: "999.99" }));
  } });
  await h.ready(); h.props = { ownerId: "other" };
  let tree = await h.ready(); assert.match(content(tree), /999,99/);
  resolveOld(wire(pending())); await flush(); tree = h.render();
  assert.match(content(tree), /999,99/); assert.doesNotMatch(content(tree), /135\.000/);
});

test("pending refresh clamps a removed last page without changing activity page", async t => {
  let shrunk = false;
  const h = setup(t, { respond: r => r.url.pathname.endsWith("/receivables") ? wire(pending({}, { page: Number(r.url.searchParams.get("page")), total: shrunk ? 1 : 37, total_pages: shrunk ? 1 : 2 })) : undefined });
  let tree = await h.ready(); pagination(tree, "ventas pendientes").props.onPage(2); tree = await h.ready();
  shrunk = true; button(tree, "Actualizar").props.onClick(); await h.ready(); await h.ready();
  assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/receivables")).at(-1).url.searchParams.get("page"), "1");
  assert.ok(h.requests.filter(r => r.url.pathname.endsWith("/activity")).every(r => r.url.searchParams.get("page") === "1"));
});

test("pending loading preserves the independent activity section and hides stale rows", async t => {
  let wait = false;
  const h = setup(t, { pending: pending({}, { total: 37, total_pages: 2 }), respond: r => wait && r.url.pathname.endsWith("/receivables") ? new Promise(() => {}) : undefined });
  let tree = await h.ready(); wait = true; pagination(tree, "ventas pendientes").props.onPage(2); tree = h.render();
  assert.match(content(tree), /Cargando ventas pendientes/); assert.match(content(tree), /Pago registrado/);
  assert.equal(find(tree, node => node.props?.className === "owner-account-sale"), null);
});

test("USD activity and balances use the configured locale and preserve cents", async t => {
  const tree = await setup(t, { pending: pending({ currency: "USD", locale: "en-US", total_outstanding_ars: "1234.56", sales: [{ ...sale, currency: "USD" }] }), activity: activity({ currency: "USD", locale: "en-US", events: [{ ...event, currency: "USD" }] }) }).ready();
  assert.match(content(tree), /USD\s*1,234\.56/); assert.match(content(tree), /− USD\s*30\.00/);
});
