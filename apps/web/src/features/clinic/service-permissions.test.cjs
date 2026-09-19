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

const service = {
  id: "service-a", code: "CONSULTA", name: "Consulta", description: "General",
  kind: "consultation", price: "25.00", default_duration_minutes: 30,
  calendar_color: "#2563eb", is_bookable: true, sort_order: 10, is_active: true,
};
const preferences = {
  currency_code: "USD", locale: "es-PA", default_appointment_duration_minutes: 30,
  appointment_duration_options: [30], default_purchase_tax_rate: "0",
  default_sale_tax_rate: "0", default_profit_margin: "0", money_rounding_increment: "0.01",
};
let harness;
const originalLoad = Module._load;
Module._load = function (request, ...args) {
  if (request === "react") return {
    ...React,
    useState(initial) {
      const index = harness.cursor++;
      if (!(index in harness.states)) harness.states[index] = initial;
      return [harness.states[index], (next) => {
        harness.states[index] = typeof next === "function" ? next(harness.states[index]) : next;
      }];
    },
    useEffect(effect) { if (harness.mounting) harness.effects.push(effect); },
  };
  if (request === "@/features/auth/current-user-context") return { useCurrentUser: () => ({ role: harness.role }) };
  if (request === "@/features/clinic/clinic-context") return { useClinic: () => ({ refreshProfile() {}, refreshPreferences() {} }) };
  if (request === "@/services/clinic") return {
    getClinicProfile: async () => ({ data: { display_name: "Clinic A" } }),
    getClinicTeam: async () => ({ data: [] }),
    getClinicConfiguration: async () => ({ data: { preferences, services: [service] } }),
  };
  return originalLoad.call(this, request, ...args);
};

const { SettingsScreen } = require("./components/settings-screen.tsx");
const { navigationItems, filterNavigationByRole } = require("../../components/layout/navigation-items.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");

function render() {
  harness.cursor = 0;
  return SettingsScreen();
}
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
  const result = nodes(tree).find((node) => node.type === "button" && (text(node).trim() === label || node.props["aria-label"] === label));
  assert.ok(result, `Button: ${label}`);
  return result;
}
async function mount(role) {
  harness = { role, states: [], cursor: 0, effects: [], mounting: true };
  render();
  harness.mounting = false;
  for (const effect of harness.effects) effect();
  await new Promise(setImmediate);
  const tree = render();
  nodes(tree).find((node) => node.type === "button" && text(node).startsWith("Servicios")).props.onClick();
  return render();
}

for (const role of ["clinic_admin", "medico_veterinario"]) {
  test(`${role} can open, change and save an existing service`, async () => {
    let tree = await mount(role);
    assert.equal(button(tree, "Editar").props.disabled, false);
    button(tree, "Editar").props.onClick();
    tree = render();
    assert.ok(text(tree).includes("Editar servicio"));
    for (const [label, value] of [["Nombre", "Consulta editada"], ["Precio (USD)", "45.50"], ["Duración", "45"]]) {
      const field = nodes(tree).find((node) => node.type === "label" && text(node).startsWith(label));
      const input = nodes(field).find((node) => node.type === "input");
      assert.ok(!input.props.disabled);
      input.props.onChange({ target: { value } });
      tree = render();
    }
    const previousFetch = global.fetch;
    let requested = false;
    setAuthTokenProvider(async () => "test-token");
    setActingTenantId(null);
    global.fetch = async (url, init) => {
      requested = true;
      assert.equal(new URL(url).pathname, "/api/v1/services/service-a");
      assert.equal(init.method, "PATCH");
      assert.equal(init.headers.get("Authorization"), "Bearer test-token");
      assert.equal(init.headers.has("X-Tenant-Id"), false);
      const payload = JSON.parse(init.body);
      assert.deepEqual(payload, {
        code: "CONSULTA", name: "Consulta editada", description: "General", kind: "consultation",
        price: "45.50", default_duration_minutes: 45, calendar_color: "#2563eb", is_bookable: true, sort_order: 10,
      });
      return new Response(JSON.stringify({ data: { ...service, ...payload }, meta: {} }), { status: 200 });
    };
    try {
      const dialog = nodes(tree).find((node) => node.props?.["aria-labelledby"] === "service-form-title");
      await nodes(dialog).find((node) => node.type === "form").props.onSubmit({ preventDefault() {} });
      assert.ok(requested);
      assert.ok(text(render()).includes("Servicio actualizado."));
      assert.ok(!text(render()).includes("Editar servicio"));
    } finally {
      global.fetch = previousFetch;
      setAuthTokenProvider(null);
    }
  });
}

test("veterinarian keeps admin service actions and preferences disabled", async () => {
  let tree = await mount("medico_veterinario");
  for (const label of ["Nuevo servicio", "Restaurar predeterminados", "Desactivar", "Subir servicio", "Bajar servicio"]) {
    assert.equal(button(tree, label).props.disabled, true, label);
  }
  button(tree, "Nuevo servicio").props.onClick();
  assert.ok(!nodes(render()).some((node) => node.props?.["aria-labelledby"] === "service-form-title"));
  nodes(tree).find((node) => node.type === "button" && text(node).startsWith("Preferencias")).props.onClick();
  tree = render();
  assert.equal(button(tree, "Guardar preferencias").props.disabled, true);
  const links = filterNavigationByRole(navigationItems, "medico_veterinario").map((item) => item.href);
  assert.ok(links.includes("/settings"));
  assert.ok(!links.includes("/users"));
  assert.ok(!links.includes("/accounting"));
});

for (const role of ["contador", "superadmin", null]) {
  test(`${role} still cannot open the service editor`, async () => {
    const tree = await mount(role);
    assert.equal(button(tree, "Editar").props.disabled, true);
    button(tree, "Editar").props.onClick();
    assert.ok(!nodes(render()).some((node) => node.props?.["aria-labelledby"] === "service-form-title"));
  });
}
