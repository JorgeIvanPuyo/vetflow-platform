const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test } = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

// Use the installed TypeScript compiler and Node test runner; no added packages.
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

const { filterSaleServices, serviceLineFromCatalog, serviceLineFromSnapshot, serviceLineToInput, hasValidServicePrice } = require("./components/sale-service-helpers.ts");
const { SaleServiceOptions } = require("./components/sale-service-selector.tsx");
const { getServices } = require("../../services/services.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");
const { resolveMoneyPreferences, formatCurrency } = require("../../lib/money.ts");

const service = { id: "service-a", name: "Consulta clínica", price: "25.50", is_active: true, is_bookable: false };
const moneyPreferences = resolveMoneyPreferences({ currency_code: "USD", locale: "es-PA" });
const defaults = { services: [service], query: "", isLoading: false, hasError: false, canConfigure: false, moneyPreferences, onRetry() {}, onSelect() {} };
const renderOptions = (props = {}) => renderToStaticMarkup(React.createElement(SaleServiceOptions, { ...defaults, ...props }));

test("catalog selection copies name, price and origin without linking mutable values", () => {
  const catalog = { ...service };
  const line = serviceLineFromCatalog(catalog, "line-1");
  catalog.name = "Changed";
  catalog.price = "90.00";
  assert.deepEqual(serviceLineToInput(line), { line_type: "service", service_id: "service-a", description: "Consulta clínica", quantity: "1", unit_price_ars: "25.50", discount_percentage: "0" });
  line.price = "30.00";
  assert.equal(serviceLineToInput(line).unit_price_ars, "30.00");
  assert.equal(catalog.price, "90.00");
});

test("unknown price stays blank and requires manual entry; explicit zero remains valid", () => {
  const line = serviceLineFromCatalog({ ...service, price: null }, "line-2");
  assert.equal(line.price, "");
  assert.equal(hasValidServicePrice(line.price), false);
  for (const value of ["", " ", "-1", "NaN", "Infinity", "abc"]) assert.equal(hasValidServicePrice(value), false);
  line.price = "15.75";
  assert.equal(hasValidServicePrice(line.price), true);
  assert.equal(serviceLineToInput(line).unit_price_ars, "15.75");
  assert.equal(serviceLineFromCatalog({ ...service, price: "0.00" }, "free").price, "0.00");
  assert.equal(hasValidServicePrice("0.00"), true);
});

test("existing lines load snapshots with or without a catalog origin", () => {
  for (const serviceId of [null, "service-a"]) {
    const item = { id: "historic", service_id: serviceId, description_snapshot: "Nombre histórico", quantity: "2", unit_price_ars: "12.00", discount_percentage: "5" };
    const line = serviceLineFromSnapshot(item);
    assert.equal(line.description, "Nombre histórico");
    assert.equal(line.price, "12.00");
    assert.equal(serviceLineToInput(line).service_id, serviceId);
  }
});

test("selector filters inactive services, searches names and includes non-bookable services", () => {
  const services = [service, { ...service, id: "off", name: "Inactivo", is_active: false }];
  assert.deepEqual(filterSaleServices(services, "  CONSULTA   CLINICA ").map((item) => item.id), ["service-a"]);
  const html = renderOptions({ services });
  assert.ok(html.includes("Consulta clínica"));
  assert.ok(!html.includes("Inactivo"));
  assert.ok(html.includes(formatCurrency(service.price, moneyPreferences)));
  assert.ok(renderOptions({ services: [{ ...service, price: null }] }).includes("Precio no configurado"));
  assert.ok(renderOptions({ query: "inexistente" }).includes("No hay servicios que coincidan"));
});

test("selector renders loading, friendly error and role-appropriate empty states", () => {
  assert.ok(renderOptions({ isLoading: true }).includes("Cargando servicios..."));
  const error = renderOptions({ hasError: true });
  assert.ok(error.includes("No pudimos cargar los servicios. Intenta nuevamente."));
  assert.ok(error.includes("Reintentar"));
  assert.ok(!error.includes("Consulta clínica"));
  assert.ok(renderOptions({ services: [] }).includes("No hay servicios activos disponibles."));
  assert.ok(!renderOptions({ services: [] }).includes('href="/settings"'));
  assert.ok(renderOptions({ services: [], canConfigure: true }).includes('href="/settings"'));
});

test("service request uses the existing authenticated catalog API without choosing a tenant", async () => {
  const previousFetch = global.fetch;
  setAuthTokenProvider(async () => "test-token");
  setActingTenantId(null);
  let requested = false;
  global.fetch = async (url, init) => {
    requested = true;
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/api/v1/services");
    assert.equal(parsed.search, "?include_inactive=false");
    assert.equal(init.headers.get("Authorization"), "Bearer test-token");
    assert.equal(init.headers.has("X-Tenant-Id"), false);
    assert.equal(init.headers.has("X-Acting-Tenant-Id"), false);
    return new Response(JSON.stringify({ data: [service], meta: {} }), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    const response = await getServices({ include_inactive: false });
    assert.equal(response.data[0].price, "25.50");
    assert.ok(requested);
  } finally {
    global.fetch = previousFetch;
    setAuthTokenProvider(null);
  }
});
