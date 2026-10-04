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
const { OwnerReceivablesPanel } = require("./components/owner-receivables-panel.tsx");
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
const pendingSale = (id = "aaaa1111-2222-3333-4444-555555555555") => ({
  sale_id: id, sale_date: "2026-10-02", confirmed_at: "2026-10-02T13:00:00Z",
  patient_id: "patient", patient_name_snapshot: "Firulais", currency: "ARS",
  total_ars: "80000.00", paid_total_ars: "30000.00", balance_due_ars: "50000.00", payment_status: "partial",
});
function response(overrides = {}, meta = {}) {
  return { data: { owner_id: "owner", tracking_configured: true, tracking_started_at: "2026-10-02T13:00:00Z",
    currency: "ARS", locale: "es-AR", total_outstanding_ars: "135000.00", open_sales_count: 2,
    sales: [pendingSale(), { ...pendingSale("bbbb1111-2222-3333-4444-555555555555"), total_ars: "85000.00", paid_total_ars: "0.00", balance_due_ars: "85000.00", payment_status: "unpaid" }], ...overrides },
    meta: { page: 1, page_size: 20, total: 2, total_pages: 1, ...meta } };
}
const wire = data => new Response(JSON.stringify(data), { status: 200 });
function setup(t, outcome = () => wire(response()), props = {}) {
  const previousFetch = global.fetch;
  const requests = [], h = { values: [], effects: [], props: { ownerId: "owner", ...props } };
  setAuthTokenProvider(async () => "test-token");
  global.fetch = async (url, init) => {
    requests.push({ url: new URL(url), init });
    return outcome(requests.at(-1), requests.length);
  };
  h.render = () => {
    current = h; h.index = 0;
    const tree = OwnerReceivablesPanel(h.props);
    h.effects.splice(0).forEach(fn => fn());
    return tree;
  };
  h.ready = async () => { h.render(); await flush(); return h.render(); };
  h.requests = requests;
  t.after(() => {
    h.values.forEach(value => value?.cleanup?.());
    global.fetch = previousFetch;
    setAuthTokenProvider(null);
  });
  return h;
}
const button = (tree, label) => find(tree, node => node.type === "button" && content(node).includes(label));

test("owner summary opens the dedicated account route", async t => {
  const tree = await setup(t).ready();
  assert.ok(find(tree, node => node.props?.href === "/owners/owner/receivables" && content(node) === "Ver cuenta corriente"));
});

test("owner revalidation refreshes the summary while preserving its open page", async t => {
  const h = setup(t, () => wire(response({}, { total: 37, total_pages: 2 })));
  let tree = await h.ready();
  find(tree, node => node.type === "details").props.onToggle({ currentTarget: { open: true } });
  button(h.render(), "Siguiente").props.onClick(); tree = await h.ready();
  assert.equal(h.requests.at(-1).url.searchParams.get("page"), "2");
  h.props = { ...h.props, refreshToken: 1 }; tree = await h.ready();
  assert.equal(find(tree, node => node.type === "details").props.open, true);
  assert.equal(h.requests.at(-1).url.searchParams.get("page"), "2");
});

test("shows global balance and count returned by the server", async t => {
  const h = setup(t); const tree = await h.ready();
  assert.match(content(tree), /135\.000,00/);
  assert.match(content(tree), /2\s+ventas\s+pendientes/);
  assert.equal(h.requests[0].url.pathname, "/api/v1/owners/owner/receivables");
  assert.equal(h.requests[0].url.searchParams.get("page_size"), "20");
  assert.equal(h.requests[0].init.method, "GET");
});

test("lists totals, active paid amounts, balances and patient snapshot", async t => {
  const h = setup(t); const tree = await h.ready();
  const text = content(tree);
  for (const value of ["80.000,00", "30.000,00", "50.000,00", "85.000,00", "Firulais", "Total", "Pagado", "Pendiente"]) assert.ok(text.includes(value), value);
  assert.ok(find(tree, node => node.type === "details"));
});

test("configured empty state shows a legitimate zero balance", async t => {
  const h = setup(t, () => wire(response({ total_outstanding_ars: "0.00", open_sales_count: 0, sales: [] }, { total: 0, total_pages: 0 })));
  const tree = await h.ready();
  assert.match(content(tree), /0,00/);
  assert.match(content(tree), /No hay ventas con saldo pendiente/);
  assert.equal(find(tree, node => node.type === "details"), null);
});

test("unconfigured tracking displays context without claiming zero debt", async t => {
  const h = setup(t, () => wire(response({ tracking_configured: false, tracking_started_at: null, total_outstanding_ars: "0.00", open_sales_count: 0, sales: [] })));
  const tree = await h.ready();
  assert.match(content(tree), /Control de cuentas por cobrar no configurado/);
  assert.doesNotMatch(content(tree), /0,00|ARS|ventas pendientes/);
});

test("archived owner retains balance and sales", async t => {
  const h = setup(t, undefined, { isArchived: true }); const tree = await h.ready();
  assert.match(content(tree), /Propietario archivado/);
  assert.match(content(tree), /135\.000,00/);
  assert.ok(find(tree, node => node.props?.href?.startsWith("/sales/")));
});

test("each pending sale links to its existing detail route", async t => {
  const h = setup(t); const tree = await h.ready();
  const link = find(tree, node => node.props?.href === "/sales/aaaa1111-2222-3333-4444-555555555555");
  assert.ok(link);
  assert.match(content(link), /Venta #AAAA1111/);
});

test("loading state has no balance and disables refresh", async t => {
  let finish;
  const h = setup(t, () => new Promise(resolve => { finish = resolve; }));
  const tree = h.render(); await flush();
  assert.ok(find(tree, node => node.props?.role === "status"));
  assert.equal(button(tree, "Actualizar saldo").props.disabled, true);
  assert.doesNotMatch(content(tree), /135\.000/);
  finish(wire(response())); await flush();
});

test("error state displays the API message without monetary data", async t => {
  const h = setup(t, () => new Response(JSON.stringify({ error: { code: "owner_not_found", message: "Propietario no encontrado" } }), { status: 404 }));
  const tree = await h.ready();
  assert.equal(content(find(tree, node => node.props?.role === "alert")), "Propietario no encontrado");
  assert.doesNotMatch(content(tree), /135\.000|0,00/);
  assert.equal(button(tree, "Actualizar saldo").props.disabled, false);
});

test("refresh reflects a later payment without writing new financial data", async t => {
  const h = setup(t, (_, count) => wire(response({ total_outstanding_ars: count === 1 ? "135000.00" : "50000.00" })));
  let tree = await h.ready();
  button(tree, "Actualizar saldo").props.onClick();
  tree = await h.ready();
  assert.match(content(tree), /50\.000,00/);
  assert.doesNotMatch(content(tree), /135\.000,00/);
  assert.equal(h.requests.length, 2);
  assert.ok(h.requests.every(request => request.init.method === "GET"));
});

test("pagination changes rows while preserving the global balance and count", async t => {
  const h = setup(t, request => {
    const page = Number(request.url.searchParams.get("page"));
    return wire(response({ total_outstanding_ars: "40.70", open_sales_count: 37, sales: [pendingSale(page === 1 ? "first" : "second")] }, { page, total: 37, total_pages: 2 }));
  });
  let tree = await h.ready();
  assert.equal(button(tree, "Anterior").props.disabled, true);
  button(tree, "Siguiente").props.onClick();
  tree = await h.ready();
  assert.match(content(tree), /40,70/);
  assert.match(content(tree), /37\s+ventas/);
  assert.ok(find(tree, node => node.props?.href === "/sales/second"));
  assert.equal(button(tree, "Siguiente").props.disabled, true);
  button(tree, "Anterior").props.onClick(); await h.ready();
  assert.deepEqual(h.requests.map(request => request.url.searchParams.get("page")), ["1", "2", "1"]);
});

test("changing owner hides old values and ignores a late previous response", async t => {
  let oldFinish;
  const h = setup(t, request => request.url.pathname.includes("/other/") ? wire(response({ owner_id: "other", total_outstanding_ars: "1.00" })) : new Promise(resolve => { oldFinish = resolve; }));
  h.render(); await flush();
  h.props.ownerId = "other";
  let tree = await h.ready();
  assert.match(content(tree), /1,00/);
  oldFinish(wire(response())); await flush(); tree = h.render();
  assert.match(content(tree), /1,00/);
  assert.doesNotMatch(content(tree), /135\.000,00/);
});

test("expanded sales remain open after loading another page", async t => {
  const h = setup(t, request => wire(response({}, { page: Number(request.url.searchParams.get("page")), total_pages: 2 })));
  let tree = await h.ready();
  find(tree, node => node.type === "details").props.onToggle({ currentTarget: { open: true } });
  tree = h.render();
  assert.equal(find(tree, node => node.type === "details").props.open, true);
  button(tree, "Siguiente").props.onClick(); tree = await h.ready();
  assert.equal(find(tree, node => node.type === "details").props.open, true);
});

test("a shrinking last page returns to a valid page after payments", async t => {
  const h = setup(t, (request, count) => {
    const page = Number(request.url.searchParams.get("page"));
    return wire(response({}, { page, total_pages: count <= 2 ? 2 : 1 }));
  });
  let tree = await h.ready();
  button(tree, "Siguiente").props.onClick(); tree = await h.ready();
  button(tree, "Actualizar saldo").props.onClick(); await h.ready(); await h.ready();
  assert.deepEqual(h.requests.map(request => request.url.searchParams.get("page")), ["1", "2", "2", "1"]);
});

test("large aggregates preserve every cent when rendered", async t => {
  const h = setup(t, () => wire(response({ total_outstanding_ars: "199999999999999.95" })));
  assert.match(content(await h.ready()), /199\.999\.999\.999\.999,95/);
});

test("uses the configured clinic currency and locale", async t => {
  const h = setup(t, () => wire(response({ currency: "USD", locale: "es-PA", sales: [] })));
  const tree = await h.ready();
  assert.match(content(tree), /USD/);
  assert.match(content(tree), /135,000\.00/);
});
