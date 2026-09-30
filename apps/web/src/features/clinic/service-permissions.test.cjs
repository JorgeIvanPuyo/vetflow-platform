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
  if (request === "next/navigation") return { usePathname: () => "/settings" };
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
  };
  if (request === "@/features/auth/current-user-context") return { useCurrentUser: () => ({ role: harness.role }) };
  if (request === "@/features/clinic/clinic-context") return { useClinic: () => ({ refreshProfile() {}, refreshPreferences() {} }) };
  if (request === "@/services/clinic") return {
    getClinicProfile: async () => ({ data: { display_name: "Clinic A" } }),
    getClinicTeam: async (responsibleOnly) => {
      harness.responsibleOnly = responsibleOnly;
      return { data: responsibleOnly ? [{ id: "vet", full_name: "Veterinario", email: "vet@example.com", is_active: true }] : [{ id: "admin", full_name: "Administrador" }] };
    },
    getClinicConfiguration: async () => ({ data: { preferences, services: [service] } }),
  };
  return originalLoad.call(this, request, ...args);
};

const { BottomNav } = require("../../components/layout/bottom-nav.tsx");
const { SettingsScreen } = require("./components/settings-screen.tsx");
const { navigationItems, filterNavigationByRole } = require("../../components/layout/navigation-items.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");

function render() {
  harness.cursor = 0;
  return harness.component ? harness.component() : SettingsScreen();
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
async function mount(role, component) {
  harness = { role, component, states: [], cursor: 0, effects: [], mounting: true };
  render();
  harness.mounting = false;
  for (const effect of harness.effects) effect();
  await new Promise(setImmediate);
  const tree = render();
  if (!component) nodes(tree).find((node) => node.type === "button" && text(node).startsWith("Servicios")).props.onClick();
  return render();
}

for (const role of ["clinic_admin", "medico_veterinario", "contador", "secretaria"]) {
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

for (const role of ["medico_veterinario", "contador"]) {
  test(`${role} can manage preferences and see operational navigation`, async () => {
    let tree = await mount(role);
    nodes(tree).find((node) => node.type === "button" && text(node).startsWith("Preferencias")).props.onClick();
    tree = render();
    assert.equal(button(tree, "Guardar preferencias").props.disabled, false);
    const links = filterNavigationByRole(navigationItems, role).map((item) => item.href);
    assert.ok(links.includes("/settings"));
    assert.ok(!links.includes("/users"));
    const mobileLinks = nodes(BottomNav()).map((node) => node.props?.href).filter(Boolean);
    assert.ok(mobileLinks.includes("/settings"));
    assert.ok(!mobileLinks.includes("/users"));
    if (role === "contador") {
      for (const href of ["/inventory/dashboard", "/purchases/dashboard", "/sales"]) {
        assert.ok(links.includes(href));
        assert.ok(mobileLinks.includes(href));
      }
    } else {
      assert.ok(!links.includes("/accounting"));
    }
  });
}

for (const role of ["clinic_admin", "medico_veterinario", "contador", "secretaria"]) {
  test(`${role} can create, toggle, reorder and restore services`, async () => {
    let tree = await mount(role);
    const previousFetch = global.fetch;
    const requests = [];
    setAuthTokenProvider(async () => "test-token");
    setActingTenantId(null);
    global.fetch = async (url, init) => {
      const pathname = new URL(url).pathname;
      const payload = init.body ? JSON.parse(init.body) : null;
      requests.push([pathname, init.method, payload]);
      let data;
      if (pathname.endsWith("/reorder")) {
        data = payload.items.map((item) => ({ ...service, ...item }));
      } else if (pathname.endsWith("/restore-defaults")) {
        data = [service];
      } else if (pathname.endsWith("/deactivate") || pathname.endsWith("/activate")) {
        data = { ...service, is_active: pathname.endsWith("/activate") };
      } else {
        data = { ...service, ...payload, id: "service-b", is_active: true };
      }
      return new Response(JSON.stringify({ data, meta: {} }), { status: 200 });
    };
    try {
      assert.equal(button(tree, "Nuevo servicio").props.disabled, false);
      button(tree, "Nuevo servicio").props.onClick();
      tree = render();
      for (const [label, value] of [["Código", "NEW"], ["Nombre", "Nuevo servicio"]]) {
        const field = nodes(tree).find((node) => node.type === "label" && text(node).startsWith(label));
        const input = nodes(field).find((node) => node.type === "input");
        input.props.onChange({ target: { value } });
        tree = render();
      }
      const dialog = nodes(tree).find((node) => node.props?.["aria-labelledby"] === "service-form-title");
      await nodes(dialog).find((node) => node.type === "form").props.onSubmit({ preventDefault() {} });
      assert.equal(requests.at(-1)[0], "/api/v1/services");
      assert.equal(requests.at(-1)[1], "POST");
      for (const [label, suffix] of [["Desactivar", "service-a/deactivate"], ["Activar", "service-a/activate"], ["Bajar servicio", "reorder"], ["Subir servicio", "reorder"], ["Restaurar predeterminados", "restore-defaults"]]) {
        tree = render();
        const action = nodes(tree).find((node) => node.type === "button" &&
          (text(node).trim() === label || node.props["aria-label"] === label) && !node.props.disabled);
        assert.ok(action, label);
        action.props.onClick();
        await new Promise(setImmediate);
        assert.equal(requests.at(-1)[0], `/api/v1/services/${suffix}`);
      }
      assert.equal(requests.length, 6);
    } finally {
      global.fetch = previousFetch;
      setAuthTokenProvider(null);
    }
  });
}

for (const role of ["superadmin", null]) {
  test(`${role} still cannot open the service editor`, async () => {
    const tree = await mount(role);
    for (const label of ["Editar", "Nuevo servicio", "Restaurar predeterminados", "Desactivar", "Subir servicio", "Bajar servicio"]) {
      assert.equal(button(tree, label).props.disabled, true, label);
    }
    button(tree, "Editar").props.onClick();
    assert.ok(!nodes(render()).some((node) => node.props?.["aria-labelledby"] === "service-form-title"));
  });
}

test("secretaria gets operational navigation and can open operational settings", async () => {
  const tree = await mount("secretaria");
  for (const label of ["Facturación", "Perfil", "Equipo", "Preferencias"]) {
    const section = nodes(tree).find((node) => node.type === "button" &&
      text(node).includes(label) && node.props["aria-expanded"] !== undefined);
    if (section) assert.ok(!section.props.disabled, label);
  }
  const links = filterNavigationByRole(navigationItems, "secretaria").map((item) => item.href);
  for (const href of ["/owners", "/patients", "/agenda", "/inventory/dashboard", "/purchases/dashboard", "/sales", "/settings"]) {
    assert.ok(links.includes(href), href);
  }
  for (const href of ["/users", "/accounting"]) assert.ok(!links.includes(href), href);
  const mobile = nodes(BottomNav()).map((node) => node.props?.href);
  for (const href of ["/patients", "/agenda", "/inventory/dashboard", "/sales", "/settings"]) assert.ok(mobile.includes(href));
  assert.ok(!mobile.includes("/users"));
  assert.ok(!mobile.includes("/accounting"));
});

test("secretaria can configure fiscal settings but cannot create clinical acts", async () => {
  await mount("secretaria");
  const { FiscalIssuersScreen } = require("../sales/components/fiscal-issuers-screen.tsx");
  const { PaymentMethodsScreen } = require("../sales/components/payment-methods-screen.tsx");
  const { ConsultationWorkflow } = require("../consultations/components/consultation-workflow.tsx");
  assert.equal(FiscalIssuersScreen().type.name, "FiscalIssuersScreenContent");
  assert.equal(PaymentMethodsScreen().type.name, "PaymentMethodsScreenContent");
  assert.match(text(ConsultationWorkflow({ mode: "new", patientId: "patient-a" })), /personal clínico/);
  const existing = ConsultationWorkflow({ mode: "edit", consultationId: "consultation-a" });
  assert.equal(existing.type.name, "ConsultationReadOnly");
});

test("secretaria cannot edit preventive records", async () => {
  await mount("secretaria");
  const { PreventiveCareSection } = require("../patients/components/preventive-care/preventive-care-section.tsx");
  const tree = PreventiveCareSection({
    records: [{ id: "preventive-a", name: "Vacuna", care_type: "vaccine", applied_at: "2026-09-27T10:00:00Z" }],
    onAdd() {}, onEdit() {}, onDelete() {},
  });
  const actions = nodes(tree).filter((node) => node.type === "button");
  assert.equal(actions.length, 3);
  assert.ok(actions.every((node) => node.props.disabled));
});

test("invitation offers secretaria as a distinct assignable role", () => {
  harness = { role: "superadmin", states: [], cursor: 0, effects: [], mounting: false };
  const { InviteUserModal } = require("../users/components/invite-user-modal.tsx");
  const tree = InviteUserModal({ tenants: [{ id: "tenant-a", name: "Clinic" }], onClose() {}, onInvited() {} });
  const option = nodes(tree).find((node) => node.type === "option" && node.props.value === "secretaria");
  assert.ok(option);
  assert.equal(text(option), "Secretaria");
});

for (const role of ["clinic_admin", "medico_veterinario", "contador", "secretaria"]) {
  for (const [file, exported] of [["inventory-catalogs-section", "InventoryCatalogsSection"], ["clinical-catalogs-section", "ClinicalCatalogsSection"], ["species-catalog-section", "SpeciesCatalogSection"]]) {
    test(`${role} manages ${file} through UI handlers`, async () => {
      const Component = require(`./components/${file}.tsx`)[exported];
      const previousFetch = global.fetch;
      const requests = [];
      let item = { id: "catalog-a", name: "Opción", is_active: true, sort_order: 0 };
      setAuthTokenProvider(async () => "test-token");
      global.fetch = async (url, init) => {
        const pathname = new URL(url).pathname;
        const method = init.method || "GET";
        const payload = init.body ? JSON.parse(init.body) : null;
        requests.push([method, pathname]);
        if (payload) item = { ...item, ...payload, catalog_type: pathname.split("/")[5] };
        if (pathname.endsWith("/deactivate")) item = { ...item, is_active: false };
        if (pathname.endsWith("/activate")) item = { ...item, is_active: true };
        return new Response(JSON.stringify({ data: method === "GET" ? [] : { ...item }, meta: {} }), { status: 200 });
      };
      try {
        let tree = await mount(role, () => Component({ isExpanded: true, onToggle() {} }));
        const create = button(tree, "Nueva opción");
        assert.ok(!create.props.disabled);
        create.props.onClick();
        const fillName = (value) => {
          const field = nodes(render()).find((node) => node.type === "label" && text(node).startsWith("Nombre"));
          nodes(field).find((node) => node.type === "input").props.onChange({ target: { value } });
        };
        fillName("Opción nueva");
        await nodes(render()).find((node) => node.type === "form").props.onSubmit({ preventDefault() {} });
        tree = render();
        assert.ok(requests.some(([method]) => method === "POST"));
        button(tree, "Editar").props.onClick();
        fillName("Editada");
        await nodes(render()).find((node) => node.type === "form").props.onSubmit({ preventDefault() {} });
        assert.ok(requests.some(([method]) => method === "PATCH"));
        for (const [label, suffix] of [["Desactivar", "/deactivate"], ["Activar", "/activate"]]) {
          const action = button(render(), label);
          assert.ok(!action.props.disabled);
          action.props.onClick();
          await new Promise(setImmediate);
          assert.ok(requests.at(-1)[1].endsWith(suffix));
        }
      } finally { global.fetch = previousFetch; setAuthTokenProvider(null); }
    });
  }
}

for (const role of ["clinic_admin", "contador", "secretaria"]) {
  test(`${role} has clinical read-only views and operational fiscal settings`, async () => {
    await mount(role);
    const { ConsultationWorkflow } = require("../consultations/components/consultation-workflow.tsx");
    assert.match(text(ConsultationWorkflow({ mode: "new", patientId: "patient-a" })), /personal clínico/);
    assert.equal(ConsultationWorkflow({ mode: "edit", consultationId: "consultation-a" }).type.name, "ConsultationReadOnly");
    const { FiscalIssuersScreen } = require("../sales/components/fiscal-issuers-screen.tsx");
    const { PaymentMethodsScreen } = require("../sales/components/payment-methods-screen.tsx");
    assert.equal(FiscalIssuersScreen().type.name, "FiscalIssuersScreenContent");
    assert.equal(PaymentMethodsScreen().type.name, "PaymentMethodsScreenContent");
    const { PreventiveCareSection } = require("../patients/components/preventive-care/preventive-care-section.tsx");
    const tree = PreventiveCareSection({ records: [{ id: "care", name: "Vacuna", care_type: "vaccine", applied_at: "2026-09-29T10:00:00Z" }], onAdd() {}, onEdit() {}, onDelete() {} });
    assert.ok(nodes(tree).filter((node) => node.type === "button").every((node) => node.props.disabled));
  });
}

test("fiscal user selector requests only active veterinarians", async () => {
  const { FiscalIssuersScreen } = require("../sales/components/fiscal-issuers-screen.tsx");
  const previousFetch = global.fetch;
  setAuthTokenProvider(async () => "test-token");
  global.fetch = async () => new Response(JSON.stringify({ data: [], meta: {} }), { status: 200 });
  try {
    const tree = await mount("secretaria", () => FiscalIssuersScreen().type());
    assert.equal(harness.responsibleOnly, true);
    button(tree, "Nuevo emisor").props.onClick();
    const options = nodes(render()).filter((node) => node.type === "option").map((node) => node.props.value);
    assert.ok(options.includes("vet"));
    assert.ok(!options.includes("admin"));
  } finally { global.fetch = previousFetch; setAuthTokenProvider(null); }
});

test("contador can stay on the dashboard home", async () => {
  await mount("contador");
  const { HomeLandingGuard } = require("../auth/components/home-landing-guard.tsx");
  assert.equal(text(HomeLandingGuard({ children: "Dashboard" })), "Dashboard");
});
