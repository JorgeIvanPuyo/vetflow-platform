const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), Module = require("node:module");
const { test } = require("node:test");
const React = require("react"), ts = require("typescript");
const root = path.resolve(__dirname, "../..");
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) {
  return resolve.call(this, name.startsWith("@/") ? path.join(root, name.slice(2)) : name, ...args);
};
for (const ext of [".ts", ".tsx"]) require.extensions[ext] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
};
let current;
const hooks = { ...React,
  useState(initial) {
    const h = current, i = h.index++;
    if (!(i in h.values)) h.values[i] = typeof initial === "function" ? initial() : initial;
    return [h.values[i], value => { h.values[i] = typeof value === "function" ? value(h.values[i]) : value; }];
  },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useCallback(fn, deps) {
    const h = current, i = h.index++;
    if (!h.values[i] || deps.some((v, j) => !Object.is(v, h.values[i].deps[j]))) h.values[i] = { fn, deps };
    return h.values[i].fn;
  },
  useMemo(fn, deps) { return hooks.useCallback(fn, deps)(); },
  useEffect(fn, deps) {
    const h = current, i = h.index++;
    if (!h.values[i] || deps.some((v, j) => !Object.is(v, h.values[i].deps[j]))) {
      h.values[i]?.cleanup?.(); h.values[i] = { deps };
      h.pending.push(() => { h.values[i].cleanup = fn(); });
    }
  },
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return hooks;
  if (name === "next/link") return () => null;
  if (name === "next/navigation") return { useRouter: () => ({ push() {} }) };
  if (name === "@/features/auth/current-user-context") return { useCurrentUser: () => ({ role: "secretaria" }) };
  return load.call(this, name, ...args);
};
const { ReceivableBadge } = require("./components/receivable-badge.tsx");
const { OwnersScreen } = require("./components/owners-screen.tsx");
const { OwnerDetail } = require("./components/owner-detail.tsx");
const { PatientsScreen } = require("../patients/components/patients-screen.tsx");
const { PatientDetail } = require("../patients/components/patient-detail.tsx");
const { OwnerReceivablesPanel } = require("./components/owner-receivables-panel.tsx");
Module._load = load;
const { setAuthTokenProvider } = require("../../lib/api.ts");
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== "object") return [];
  if (tree.type === ReceivableBadge) return nodes(ReceivableBadge(tree.props));
  return [tree, ...nodes(tree.props?.children)];
}
function content(tree) {
  if (Array.isArray(tree)) return tree.map(content).join("");
  if (tree && typeof tree === "object") return tree.type === ReceivableBadge ? content(ReceivableBadge(tree.props)) : content(tree.props?.children);
  return typeof tree === "string" || typeof tree === "number" ? String(tree) : "";
}
const badges = tree => nodes(tree).filter(n => n.props?.className?.includes("receivable-badge"));
const flush = async () => { for (let i = 0; i < 100; i++) await Promise.resolve(); };
const owner = debt => ({ id: "owner", tenant_id: "tenant", full_name: "Juan Pérez", phone: "555", is_active: true, has_active_receivable: debt, created_at: "2026-10-02T13:00:00Z", updated_at: "2026-10-02T13:00:00Z" });
const pets = debt => ["Luna", "Milo", "Nina"].map((name, i) => ({ id: `pet-${i}`, owner_id: "owner", owner_name: "Juan Pérez", tenant_id: "tenant", name, species: "canine", owner_has_active_receivable: debt, breed: null, sex: null, allergies: null, chronic_conditions: null }));
const wire = data => new Response(JSON.stringify(data), { status: 200 });
function setup(t, component, options = {}) {
  const oldFetch = global.fetch, oldWindow = global.window;
  const h = { values: [], pending: [], requests: [], listeners: new Map(), debt: options.debt ?? true };
  global.window = { addEventListener: (name, fn) => h.listeners.set(name, fn), removeEventListener: name => h.listeners.delete(name) };
  setAuthTokenProvider(async () => "test-token");
  global.fetch = async (url, init) => {
    const request = { url: new URL(url), init }; h.requests.push(request);
    if (options.respond) { const result = options.respond(request, h); if (result !== undefined) return result; }
    const pathname = request.url.pathname;
    const o = { ...owner(h.debt), is_active: !options.archived };
    const p = pets(h.debt);
    if (pathname === "/api/v1/owners") return wire({ data: [o], meta: { page: 1, page_size: 12, total: 1 } });
    if (pathname === "/api/v1/owners/owner") return wire({ data: o, meta: {} });
    if (pathname === "/api/v1/patients") return wire({ data: p, meta: { page: 1, page_size: 12, total: 3 } });
    if (pathname === "/api/v1/patients/pet-0") return wire({ data: p[0], meta: {} });
    if (pathname.endsWith("/clinical-history")) return wire({ data: { patient: p[0], owner: o, consultations: [], exams: [], follow_ups: [], preventive_care: [], file_references: [], timeline: [] }, meta: {} });
    return wire({ data: [], meta: {} });
  };
  h.render = () => { current = h; h.index = 0; h.tree = component({ ownerId: "owner", patientId: "pet-0" }); h.pending.splice(0).forEach(fn => fn()); return h.tree; };
  h.ready = async () => { h.render(); await flush(); return h.render(); };
  t.after(() => { h.values.forEach(value => value?.cleanup?.()); global.fetch = oldFetch; global.window = oldWindow; setAuthTokenProvider(null); });
  return h;
}

test("badge uses an accessible native link to the existing account", () => {
  const badge = ReceivableBadge({ ownerId: "owner", hasActiveReceivable: true });
  assert.equal(badge.props.href, "/owners/owner/receivables");
  assert.equal(content(badge), "Saldo pendiente");
  assert.match(badge.props["aria-label"], /Ver cuenta corriente/);
  assert.equal(badge.props.tabIndex, undefined);
  assert.match(content(ReceivableBadge({ ownerId: "owner", hasActiveReceivable: true, forPatient: true })), /Propietario con saldo pendiente/);
});
test("false, missing and unknown signals never assert debt", () => {
  for (const hasActiveReceivable of [false, undefined, null]) assert.equal(ReceivableBadge({ ownerId: "owner", hasActiveReceivable }), null);
});
for (const [name, component, count] of [["owner list", OwnersScreen, 1], ["owner detail and pets", OwnerDetail, 4], ["patient list", PatientsScreen, 3], ["patient detail", PatientDetail, 1]]) {
  test(`${name} shows the server signal and all badges reach the same owner account`, async t => {
    const h = setup(t, component), tree = await h.ready();
    assert.equal(badges(tree).length, count);
    assert.ok(badges(tree).every(b => b.props.href === "/owners/owner/receivables"));
    assert.equal(h.requests.filter(r => r.url.pathname.endsWith("/receivables")).length, 0);
    assert.ok(h.requests.every(r => r.init.method === "GET"));
  });
  test(`${name} has no badge with zero balance or unconfigured tracking`, async t => {
    const h = setup(t, component, { debt: false });
    assert.equal(badges(await h.ready()).length, 0);
  });
  test(`${name} revalidates after payment and void on browser return`, async t => {
    const h = setup(t, component); await h.ready();
    h.debt = false; h.listeners.get("pageshow")();
    assert.equal(badges(await h.ready()).length, 0);
    h.debt = true; h.listeners.get("focus")();
    assert.equal(badges(await h.ready()).length, count);
  });
  test(`${name} ignores a late debt response after newer payment data`, async t => {
    let resolveOld, held = false;
    const pathname = component === OwnersScreen ? "/api/v1/owners" : component === OwnerDetail ? "/api/v1/owners/owner" : component === PatientsScreen ? "/api/v1/patients" : "/api/v1/patients/pet-0";
    const h = setup(t, component, { respond: request => {
      if (!held && request.url.pathname === pathname) {
        held = true;
        return new Promise(resolve => { resolveOld = resolve; });
      }
    } });
    await h.ready(); h.debt = false; h.listeners.get("pageshow")();
    assert.equal(badges(await h.ready()).length, 0);
    const oldData = component === OwnersScreen ? [owner(true)] : component === OwnerDetail ? owner(true) : component === PatientsScreen ? pets(true) : pets(true)[0];
    resolveOld(wire({ data: oldData, meta: { page: 1, page_size: 12, total: Array.isArray(oldData) ? oldData.length : 1 } }));
    await flush(); assert.equal(badges(h.render()).length, 0);
  });
}
test("archived owner remains badged in its detail", async t => {
  assert.equal(badges(await setup(t, OwnerDetail, { archived: true }).ready()).length, 4);
});
test("patient labels attribute the debt to the owner", async t => {
  const tree = await setup(t, PatientsScreen).ready();
  assert.equal(badges(tree).length, 3);
  assert.ok(badges(tree).every(b => content(b) === "Propietario con saldo pendiente"));
  for (const name of ["Luna", "Milo", "Nina"]) assert.ok(content(tree).includes(name));
});
for (const component of [OwnersScreen, PatientsScreen]) {
  test(`${component.name} cards have separate detail and badge links without nested anchors`, async t => {
    const tree = await setup(t, component).ready();
    const cards = nodes(tree).filter(n => n.props?.className?.includes("receivable-entity-card"));
    assert.ok(cards.length > 0);
    for (const card of cards) {
      assert.equal(card.type, "div");
      const links = nodes(card).filter(n => n.props?.href);
      assert.equal(links.length, 2);
      assert.equal(links.some(link => nodes(link.props.children).some(child => child.props?.href)), false);
    }
  });
}
test("refreshing the P.11 panel also revalidates owner detail signals", async t => {
  const h = setup(t, OwnerDetail); let tree = await h.ready(); h.debt = false;
  const panel = nodes(tree).find(n => n.type === OwnerReceivablesPanel);
  await panel.props.onRefresh(); tree = h.render();
  assert.equal(badges(tree).length, 0);
});
test("mobile badge styling wraps and provides touch and keyboard targets", () => {
  const css = fs.readFileSync(path.join(root, "styles/globals.css"), "utf8");
  const rules = css.match(/\.receivable-badge \{([^}]+)\}/)[1];
  assert.match(rules, /max-width: 100%/); assert.match(rules, /min-height: 44px/);
  assert.match(rules, /white-space: normal/); assert.match(rules, /overflow-wrap: anywhere/);
  assert.match(css, /\.receivable-badge:focus-visible/);
});
