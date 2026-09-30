const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const ts = require("typescript");
const React = require("react");

// Use the existing Node/TypeScript test setup. Drive the component's handlers
// with in-memory hooks; no browser renderer or additional dependencies.
const sourceRoot = path.resolve(__dirname, "../..");
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, ...args) {
  return originalResolve.call(this, request.startsWith("@/") ? path.join(sourceRoot, request.slice(2)) : request, ...args);
};
for (const extension of [".ts", ".tsx"]) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(`${sourceRoot}${path.sep}`));
    const { outputText } = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      fileName: filename,
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    });
    module._compile(outputText, filename);
  };
}


let harness;
let supplier;
const originalLoad = Module._load;
Module._load = function (request, ...args) {
  if (request === "next/navigation") return { useRouter: () => ({ push: (href) => harness.location = href }) };
  if (request === "react-dom") return { createPortal: (children) => children };
  if (request === "react") return {
    ...React,
    useState(initial) {
      const index = harness.cursor++;
      if (!(index in harness.states)) harness.states[index] = typeof initial === "function" ? initial() : initial;
      return [harness.states[index], (next) => {
        harness.states[index] = typeof next === "function" ? next(harness.states[index]) : next;
      }];
    },
    useEffect(effect) { if (harness.mounting) harness.effects.push(effect); },
    useCallback: (callback) => callback,
    useMemo: (callback) => callback(),
    useRef: (initial) => ({ current: initial }),
  };
  if (request === "@/features/auth/current-user-context") return { useCurrentUser: () => ({ role: harness.role }) };
  if (request === "@/features/clinic/clinic-context") return { useClinic: () => ({ preferences: null }) };
  return originalLoad.call(this, request, ...args);
};

const { SuppliersSection } = require("../clinic/components/suppliers-section.tsx");
const { SupplierFormScreen } = require("./components/supplier-form-screen.tsx");
const { SupplierDetailScreen } = require("./components/supplier-detail-screen.tsx");
const { SuppliersScreen } = require("./components/suppliers-screen.tsx");
const { PurchaseFormScreen } = require("../purchases/components/purchase-form-screen.tsx");
const { setAuthTokenProvider } = require("../../lib/api.ts");
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children)];
}
function text(tree) {
  if (typeof tree === "string") return tree;
  if (Array.isArray(tree)) return tree.map(text).join("");
  return tree?.props ? text(tree.props.children) : "";
}
function button(tree, label) {
  const node = nodes(tree).find((node) => node.type === "button" && text(node).trim() === label);
  assert.ok(node, label);
  assert.ok(!node.props.disabled, `${label} enabled`);
  return node;
}
const tick = () => new Promise(setImmediate);
async function mount(role, component) {
  harness = { role, component, states: [], cursor: 0, effects: [], mounting: true, requests: [] };
  render();
  harness.mounting = false;
  for (const effect of harness.effects) effect();
  await tick();
  return render();
}
function render() { harness.cursor = 0; return harness.component(); }
function fill(tree, label, value) {
  const field = nodes(tree).find((node) => node.type === "label" && text(node).startsWith(label));
  const input = nodes(field).find((node) => node.type === "input");
  assert.ok(input, label);
  input.props.onChange({ target: { value } });
  return render();
}
async function submit(tree) {
  await nodes(tree).find((node) => node.type === "form").props.onSubmit({ preventDefault() {} });
  await tick();
  return render();
}
function requested(method, suffix) {
  assert.ok(harness.requests.some(([verb, pathname]) => verb === method && pathname === `/api/v1/suppliers${suffix}`), `${method} ${suffix}`);
}
async function withApi(run) {
  const previousFetch = global.fetch;
  const previousDocument = global.document;
  supplier = { id: "supplier-a", name: "Proveedor A", is_active: true, tax_id: null };
  global.document = { body: {} };
  setAuthTokenProvider(async () => "test-token");
  global.fetch = async (url, init) => {
    assert.equal(init.headers.get("Authorization"), "Bearer test-token");
    const pathname = new URL(url).pathname;
    const method = init.method ?? "GET";
    const payload = init.body ? JSON.parse(init.body) : null;
    harness.requests.push([method, pathname, payload]);
    assert.ok(pathname.startsWith("/api/v1/suppliers"), pathname);
    if (method === "PATCH" || (method === "POST" && payload)) supplier = { ...supplier, ...payload };
    if (pathname.endsWith("/deactivate")) supplier.is_active = false;
    if (pathname.endsWith("/activate")) supplier.is_active = true;
    return new Response(JSON.stringify({ data: method === "GET" && pathname === "/api/v1/suppliers" ? [{ ...supplier }] : { ...supplier }, meta: { page: 1, total: 1, total_pages: 1 } }), { status: 200 });
  };
  try { await run(); }
  finally { global.fetch = previousFetch; global.document = previousDocument; setAuthTokenProvider(null); }
}

for (const role of ["clinic_admin", "medico_veterinario", "contador", "secretaria"]) {
  test(`${role}: settings supplier create, edit, deactivate and activate`, () => withApi(async () => {
    let tree = await mount(role, () => SuppliersSection({ isExpanded: true, onToggle() {} }));
    button(tree, "Nuevo proveedor").props.onClick();
    tree = fill(render(), "Nombre", "Nuevo proveedor");
    button(tree, "Crear proveedor");
    tree = await submit(tree);
    requested("POST", "");
    await button(tree, "Editar").props.onClick();
    await tick();
    tree = fill(render(), "Nombre", "Proveedor editado");
    tree = await submit(tree);
    requested("PATCH", "/supplier-a");
    for (const [label, action] of [["Desactivar", "deactivate"], ["Activar", "activate"]]) {
      button(tree, label).props.onClick();
      await tick();
      requested("POST", `/supplier-a/${action}`);
      tree = render();
    }
  }));

  test(`${role}: dedicated supplier list, form and detail actions`, () => withApi(async () => {
    let tree = await mount(role, () => SuppliersScreen());
    assert.ok(nodes(tree).some((node) => node.props?.href === "/suppliers/new" && text(node).includes("Nuevo proveedor")));
    assert.ok(nodes(tree).some((node) => node.props?.href === "/suppliers/supplier-a/edit"));
    tree = await mount(role, () => SupplierFormScreen({}));
    tree = fill(tree, "Nombre", "Nuevo proveedor");
    button(tree, "Guardar proveedor");
    await submit(tree);
    requested("POST", "");
    assert.equal(harness.location, "/suppliers/supplier-a");
    tree = await mount(role, () => SupplierFormScreen({ supplierId: "supplier-a" }));
    tree = fill(tree, "Nombre", "Editado");
    await submit(tree);
    requested("PATCH", "/supplier-a");
    assert.equal(supplier.name, "Editado");
    tree = await mount(role, () => SupplierDetailScreen({ supplierId: "supplier-a" }));
    assert.ok(nodes(tree).some((node) => node.props?.href === "/suppliers/supplier-a/edit"));
    for (const [label, active] of [["Inactivar", false], ["Activar", true]]) {
      button(tree, label).props.onClick();
      await tick();
      assert.equal(supplier.is_active, active);
      requested("PATCH", "/supplier-a");
      tree = render();
    }
  }));

  test(`${role}: quick creation selects supplier without losing purchase fields`, () => withApi(async () => {
    let tree = await mount(role, () => PurchaseFormScreen({}));
    tree = fill(tree, "Número", "COMPRA-123");
    button(tree, "Nuevo proveedor").props.onClick();
    tree = fill(render(), "Nombre", "Proveedor rápido");
    button(tree, "Crear y seleccionar").props.onClick();
    await tick();
    requested("POST", "");
    tree = render();
    assert.ok(text(tree).includes("Proveedor rápido"));
    assert.ok(text(tree).includes("Proveedor seleccionado"));
    assert.ok(nodes(tree).some((node) => node.type === "input" && node.props.value === "COMPRA-123"));
    assert.ok(!nodes(tree).some((node) => node.props?.["aria-labelledby"] === "quick-supplier-title"));
  }));
}

for (const role of ["superadmin", null]) {
  test(`${role}: settings supplier mutation permissions unchanged`, () => withApi(async () => {
    const tree = await mount(role, () => SuppliersSection({ isExpanded: true, onToggle() {} }));
    for (const label of ["Nuevo proveedor", "Editar", "Desactivar"]) {
      const action = nodes(tree).find((node) => node.type === "button" && text(node).trim() === label);
      assert.equal(action.props.disabled, true, label);
    }
  }));
}
