const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const { test, after } = require("node:test");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

// Match the repository's Node/TypeScript component harness. All data is local;
// services below fail closed so this suite cannot contact an API or database.
const root = path.resolve(__dirname, "..");
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) {
  return resolve.call(this, name.startsWith("@/") ? path.join(root, name.slice(2)) : name, ...args);
};
for (const extension of [".ts", ".tsx"]) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(root + path.sep));
    module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      fileName: filename,
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText, filename);
  };
}
require.extensions[".css"] = (module) => { module.exports = { overview: "inventory-overview-preview" }; };

let current;
const router = { push(href) { current.navigations.push(href); }, replace() {} };
const hooks = {
  ...React,
  useState(initial) {
    const h = current, i = h.cursor++;
    if (!(i in h.states)) h.states[i] = typeof initial === "function" ? initial() : initial;
    return [h.states[i], (value) => { h.states[i] = typeof value === "function" ? value(h.states[i]) : value; }];
  },
  useRef(initial) { const h = current, i = h.cursor++; return h.states[i] ??= { current: initial }; },
  useMemo: (callback) => callback(),
  useCallback: (callback) => callback,
  useEffect(effect) { if (current.mounting) current.effects.push(effect); },
};
const date = "2026-10-17T15:00:00Z";
const meta = { page: 1, page_size: 20, total: 3, total_pages: 1, summary: { purchase_count: 3, subtotal_ars: "100", tax_total_ars: "0", total_ars: "100" } };
const sale = { id: "sale", status: "confirmed", sale_date: date, owner_name_snapshot: "Cliente de prueba", item_count: 1, subtotal_ars: "100", discount_total_ars: "0", total_ars: "100", payment_status: "unpaid", balance_due_ars: "100" };
const sales = ["confirmed", "cancelled", "reversed"].map((status) => ({ ...sale, id: `sale-${status}`, status }));
const purchase = { id: "purchase", status: "received", supplier_name: "Proveedor de prueba", purchase_date: date, document_type: "invoice", subtotal_ars: "100", tax_total_ars: "0", total_ars: "100", return_status: "none", attachment_status: "pending", items: [], returns: [], attachment_history: [] };
const purchases = ["received", "cancelled", "reversed"].map((status) => ({ ...purchase, id: `purchase-${status}`, status }));
const appointments = ["scheduled", "cancelled", "no_show"].map((status) => ({ id: `appointment-${status}`, status, title: `Turno ${status}`, appointment_type: "consultation", start_at: date, end_at: "2026-10-17T15:30:00Z" }));
const followUps = ["pending", "cancelled"].map((status) => ({ id: `followup-${status}`, status, title: `Seguimiento ${status}`, follow_up_type: "general", due_at: date }));
const movements = ["active", "reversed", "reversal"].map((reversal_status) => ({ id: `movement-${reversal_status}`, reversal_status, movement_type: reversal_status === "reversal" ? "reversal" : "manual_entry", inventory_item_name: "Producto de prueba", quantity: "2", unit: "unit", stock_before: "8", stock_after: "10", created_at: date }));
const item = { id: "product", name: "Producto de prueba", internal_code: "P001", category: "food", unit: "unit", current_stock: "10", minimum_stock: "1", purchase_price_ars: "100", sale_price_ars: "120", is_active: true };
const payments = [true, false].map((is_active) => ({ id: `payment-${is_active}`, is_active, payment_method_label_snapshot: "Efectivo", payment_method_type_snapshot: "cash", amount_ars: "10", received_at: date, voided_at: is_active ? null : date, void_reason: "Error de registro" }));
const returns = ["confirmed", "cancelled"].map((status) => ({ id: `return-${status}`, status, return_date: date, reason: "Producto dañado", total_ars: "10" }));
const operations = ["confirmed", "partially_reversed", "reversed"].map((status) => ({ id: `operation-${status}`, status, operation_type: "set_sale_price", created_at: date, confirmed_at: date, affected_count: 2, reversed_count: status === "reversed" ? 2 : 0 }));
const operation = { ...operations[2], items: ["changed", "reverted", "conflict"].map((status) => ({ id: status, status, inventory_item_name: "Producto de prueba", field_name: "sale_price_ars", old_value_json: { value: "100" }, new_value_json: { value: "120" } })) };
const dashboard = { generated_at: date, summary: {}, attention: [], recent_purchases: purchases, top_suppliers: [] };
const inventoryDashboard = { generated_at: date, indicators: {}, valuation: {}, movement_metrics: {}, alerts: [], attention_items: [], activity: { recent_movements: movements, recent_imports: [], recent_bulk_operations: operations } };
const services = {
  getSales: () => ({ data: sales, meta }), getSaleFilterOptions: () => ({ data: { creators: [] } }),
  getPurchases: () => ({ data: purchases, meta }), getPurchase: () => ({ data: { ...purchase, returns } }),
  getPurchaseFilterOptions: () => ({ data: { creators: [] } }), getPurchaseDashboard: () => ({ data: dashboard }),
  getAppointments: () => ({ data: appointments }), getFollowUps: () => ({ data: followUps }),
  getInventoryMovementList: () => ({ data: movements, meta }), getInventoryMovements: () => ({ data: movements, meta }),
  getInventoryItem: () => ({ data: item }), getInventoryBulkOperations: () => ({ data: operations }),
  getInventoryBulkOperation: () => ({ data: operation }),
  getInventoryDashboard: () => ({ data: inventoryDashboard }), getInventoryFilterOptions: () => ({ data: { brands: [], suppliers: [] } }),
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return hooks;
  if (name === "next/link") return function TestNextLink({ children, ...props }) { return React.createElement("a", props, children); };
  if (name === "next/navigation") return { useRouter: () => router, usePathname: () => current.pathname, useSearchParams: () => new URLSearchParams() };
  if (name === "@/features/clinic/clinic-context") return { useClinic: () => ({ preferences: null }) };
  if (name === "@/features/auth/auth-context") return { useAuth: () => ({ user: null }) };
  if (name === "@/features/auth/current-user-context") return { useCurrentUser: () => ({ role: "clinic_admin" }) };
  if (name.startsWith("@/services/")) return new Proxy({}, { get: (_, method) => async (...params) => {
    assert.ok(String(method).startsWith("get"), `Read-only service: ${String(method)}`);
    return services[method]?.(...params) ?? { data: [] };
  } });
  return load.call(this, name, ...args);
};
const { isDiscardedStatus, getRecordRowState, getPaymentRowState } = require("./record-row-state.ts");
const { SalesScreen } = require("../features/sales/components/sales-screen.tsx");
const { PurchasesScreen } = require("../features/purchases/components/purchases-screen.tsx");
const { AgendaScreen } = require("../features/agenda/components/agenda-screen.tsx");
const { InventoryMovementsScreen } = require("../features/inventory/components/inventory-movements-screen.tsx");
const { InventoryDetail } = require("../features/inventory/components/inventory-detail.tsx");
const { InventoryDashboardScreen } = require("../features/inventory/components/inventory-dashboard-screen.tsx");
const { PurchaseDetailScreen } = require("../features/purchases/components/purchase-detail-screen.tsx");
const { PurchaseDashboardScreen } = require("../features/purchases/components/purchase-dashboard-screen.tsx");
const { SalePaymentsPanel } = require("../features/sales/components/sale-payments-panel.tsx");
const { InventoryBulkOperationsScreen } = require("../features/inventory/components/inventory-bulk-operations-screen.tsx");
const { InventoryBulkOperationDetail } = require("../features/inventory/components/inventory-bulk-operation-detail.tsx");

function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== "object") return [];
  // Evaluate real row/card components, including the Next Link adapter.
  if (typeof tree.type === "function") return nodes(tree.type(tree.props));
  return [tree, ...nodes(tree.props?.children)];
}
function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join("");
  if (typeof tree === "string" || typeof tree === "number") return String(tree);
  return tree?.props ? text(tree.props.children) : "";
}
const previews = {};
async function mount(name, component, props = {}) {
  current = { states: [], cursor: 0, effects: [], mounting: true, navigations: [], pathname: `/${name}` };
  component(props);
  current.mounting = false;
  const cleanups = current.effects.map((effect) => effect());
  await new Promise(setImmediate);
  current.cursor = 0;
  const tree = component(props);
  const all = nodes(tree);
  previews[name] = renderToStaticMarkup(tree);
  cleanups.forEach((cleanup) => cleanup?.());
  return all;
}
function assertState(node, discarded, label) {
  assert.ok(node, label);
  assert.equal(node.props["data-record-state"], discarded ? "discarded" : undefined, label);
}
function row(all, key) { return all.find((n) => n.type === "tr" && n.key === key); }
function badge(node, label) {
  assert.ok(nodes(node).some((n) => n.props?.className?.split(" ").includes("badge") && text(n) === label), label);
}

test("helper maps only actual cancelled/reversed/reverted states; payment boolean is independent", () => {
  for (const status of ["cancelled", "reversed", "reverted"]) {
    assert.equal(isDiscardedStatus(status), true);
    assert.equal(getRecordRowState(status), "discarded");
  }
  for (const status of ["confirmed", "received", "scheduled", "completed", "draft", "active", "reversal", "partially_reversed", "returned", "partially_received", "no_show", "failed", "expired", "overdue", "conflict", "excluded", null, undefined, "Cancelada", "cancelled_unknown"]) {
    assert.equal(isDiscardedStatus(status), false, String(status));
    assert.equal(getRecordRowState(status), undefined, String(status));
  }
  assert.equal(getPaymentRowState({ is_active: true }), undefined);
  assert.equal(getPaymentRowState({ is_active: false }), "discarded");
});

test("sales: active unchanged, cancelled/reversed highlighted with badges and keyboard navigation", async () => {
  const all = await mount("sales", SalesScreen);
  for (const [status, label] of [["confirmed", "Confirmada"], ["cancelled", "Cancelada"], ["reversed", "Revertida"]]) {
    const node = row(all, `sale-${status}`);
    assertState(node, status !== "confirmed", status); badge(node, label);
    assert.equal(node.props.tabIndex, 0); assert.equal(node.props.role, "link");
    for (const key of ["Enter", " "]) {
      let prevented = false;
      node.props.onKeyDown({ key, preventDefault() { prevented = true; } });
      assert.ok(prevented); assert.equal(current.navigations.at(-1), `/sales/sale-${status}`);
    }
    node.props.onClick(); assert.equal(current.navigations.at(-1), `/sales/sale-${status}`);
  }
});

test("purchases: received normal, cancelled/reversed highlighted and badges retained", async () => {
  const all = await mount("purchases", PurchasesScreen);
  for (const [status, label] of [["received", "Recibida"], ["cancelled", "Cancelada"], ["reversed", "Recepción revertida"]]) {
    const node = row(all, `purchase-${status}`);
    assertState(node, status !== "received", status); badge(node, label);
    node.props.onClick(); assert.equal(current.navigations.at(-1), `/purchases/purchase-${status}`);
  }
});

test("agenda responsive cards: scheduled/no_show normal, cancelled highlighted with badge and link", async () => {
  const all = await mount("agenda", AgendaScreen);
  for (const [status, label] of [["scheduled", "Programado"], ["cancelled", "Cancelado"], ["no_show", "No asistió"]]) {
    const node = all.find((n) => n.props?.href === `/agenda/appointment-${status}`);
    assertState(node, status === "cancelled", status); badge(node, label);
  }
});

test("follow-up responsive cards use the same cancellation criterion and keep their badge", async () => {
  const all = await mount("follow-ups", AgendaScreen, { initialTab: "follow_ups" });
  const cards = all.filter((n) => n.type === "article" && n.props.className === "appointment-card follow-up-card");
  assert.equal(cards.length, 2);
  assertState(cards[0], false, "pending"); assertState(cards[1], true, "cancelled"); badge(cards[1], "Cancelado");
});

test("inventory table: only reversed original highlighted; active and compensating reversal stay normal", async () => {
  const all = await mount("movements", InventoryMovementsScreen);
  const rows = all.filter((n) => n.type === "tr" && n.props.role === "link");
  assert.equal(rows.length, 3);
  for (const [i, label] of ["Activo", "Revertido", "Reversa"].entries()) {
    assertState(rows[i], i === 1, label); badge(rows[i], label);
    rows[i].props.onClick(); assert.equal(current.navigations.at(-1), `/inventory/movements/${movements[i].id}`);
  }
});

test("inventory movement cards match table criterion without tinting the product", async () => {
  const all = await mount("inventory-detail", InventoryDetail, { itemId: "product" });
  const cards = all.filter((n) => n.props?.className === "inventory-movement-card");
  assert.equal(cards.length, 3);
  cards.forEach((card, i) => assertState(card, i === 1, movements[i].reversal_status));
  badge(cards[1], "Revertido");
  assert.ok(nodes(cards[1]).some((n) => n.props?.href === "/inventory/movements/movement-reversed"));
  assert.equal(all.filter((n) => n.props?.["data-record-state"] === "discarded").length, 1);
});

test("inventory dashboard: recent movements and bulk operations match their lists with a text indicator", async () => {
  const all = await mount("inventory-dashboard", InventoryDashboardScreen);
  for (const status of ["active", "reversed", "reversal"]) {
    const node = all.find((n) => n.props?.href === `/inventory/movements/movement-${status}`);
    assertState(node, status === "reversed", status);
    if (status === "reversed") badge(node, "Revertido");
  }
  for (const status of ["confirmed", "partially_reversed", "reversed"]) {
    const node = all.find((n) => n.props?.href === `/inventory/bulk-operations/operation-${status}`);
    assertState(node, status === "reversed", status);
    if (status === "reversed") assert.match(text(node), /Revertida/);
  }
});

test("purchase returns: only cancelled return card highlighted; purchase remains normal", async () => {
  const all = await mount("purchase-detail", PurchaseDetailScreen, { purchaseId: "purchase" });
  for (const [status, label] of [["confirmed", "Confirmada"], ["cancelled", "Cancelada"]]) {
    const node = all.find((n) => n.props?.href === `/purchase-returns/return-${status}`);
    assertState(node, status === "cancelled", status); badge(node, label);
  }
});

test("purchase dashboard responsive recent cards match purchase table and retain badges", async () => {
  const all = await mount("purchase-dashboard", PurchaseDashboardScreen);
  for (const [status, label] of [["received", "Recibida"], ["cancelled", "Cancelada"], ["reversed", "Recepción revertida"]]) {
    const node = all.find((n) => n.props?.className === "purchase-dashboard-recent-row" && n.props.href === `/purchases/purchase-${status}`);
    assertState(node, status !== "received", status); badge(node, label);
  }
});

test("payments: only voided payment highlighted, even when parent sale is reversed", async () => {
  const all = await mount("payments", SalePaymentsPanel, { sale: { ...sale, status: "reversed", payments }, onUpdated: async () => {} });
  assertState(row(all, "payment-true"), false, "active payment"); badge(row(all, "payment-true"), "Activo");
  assertState(row(all, "payment-false"), true, "voided payment"); badge(row(all, "payment-false"), "Anulado");
});

test("bulk operations: highlight fully reversed operation and reverted items only", async () => {
  const all = await mount("bulk-operations", InventoryBulkOperationsScreen);
  for (const status of ["confirmed", "partially_reversed", "reversed"]) assertState(row(all, `operation-${status}`), status === "reversed", status);
  const detail = await mount("bulk-detail", InventoryBulkOperationDetail, { operationId: operation.id });
  for (const status of ["changed", "reverted", "conflict"]) {
    const node = row(detail, status); assertState(node, status === "reverted", status); assert.match(text(node), new RegExp(status));
  }
});

// Optional offline browser fixtures render the actual screens above with their
// real CSS. No dev server, auth bypass, application route or dependency needed.
after(() => {
  const directory = process.env.RECORD_ROW_PREVIEW_DIR;
  if (!directory) return;
  fs.mkdirSync(directory, { recursive: true });
  const css = fs.readFileSync(path.join(root, "styles/globals.css"), "utf8");
  const detailCss = fs.readFileSync(path.join(root, "features/inventory/components/inventory-detail.module.css"), "utf8")
    .replace(/:global\(([^)]+)\)/g, "$1").replace(/\.overview/g, ".inventory-overview-preview");
  for (const [name, html] of Object.entries(previews)) {
    fs.writeFileSync(path.join(directory, `${name}.html`), `<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}\n${detailCss}\n.preview{padding:16px;max-width:1280px;margin:auto}</style><body><main class="preview">${html}</main></body></html>`);
  }
});
