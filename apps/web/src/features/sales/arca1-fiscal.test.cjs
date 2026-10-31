const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), Module = require("node:module");
const { test } = require("node:test");
const React = require("react"), ts = require("typescript");

const root = path.resolve(__dirname, "../..");
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) { return resolve.call(this, name.startsWith("@/") ? path.join(root, name.slice(2)) : name, ...args); };
for (const ext of [".ts", ".tsx"]) require.extensions[ext] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
};
let current;
const hooks = { ...React,
  useState(initial) { const h = current, i = h.index++; if (!(i in h.values)) h.values[i] = typeof initial === "function" ? initial() : initial; return [h.values[i], value => { h.values[i] = typeof value === "function" ? value(h.values[i]) : value; }]; },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useCallback(fn, deps) { const h = current, i = h.index++; if (!h.values[i] || deps.some((value, j) => !Object.is(value, h.values[i].deps[j]))) h.values[i] = { deps, fn }; return h.values[i].fn; },
  useMemo(fn) { return fn(); },
  useEffect(fn, deps) { const h = current, i = h.index++; if (!h.values[i] || deps.some((value, j) => !Object.is(value, h.values[i].deps[j]))) { h.values[i]?.cleanup?.(); h.values[i] = { deps }; h.pending.push(() => { h.values[i].cleanup = fn(); }); } },
};
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return hooks;
  if (name === "next/link") return () => null;
  if (name === "@/features/auth/current-user-context") return { useCurrentUser: () => current.auth };
  if (name === "@/features/clinic/clinic-context") return { useClinic: () => ({ preferences: null }) };
  return load.call(this, name, ...args);
};
const { SaleFiscalReviewPanel } = require("./components/sale-fiscal-review-panel.tsx");
const { FiscalConfigurationScreen } = require("./components/fiscal-configuration-screen.tsx");
const { SaleFiscalDocumentPanel } = require("./components/sale-fiscal-document-panel.tsx");
Module._load = load;
const { selectedFiscalTotal, selectableFiscalPayments, canApproveFiscalProposal, fiscalPaymentStatusLabel, fiscalProposalStatusLabel } = require("./components/fiscal-review-helpers.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");

function nodes(tree) { if (Array.isArray(tree)) return tree.flatMap(nodes); if (!tree || typeof tree !== "object") return []; const children = typeof tree.type === "function" && tree.type.name === "FiscalBlockers" ? tree.type(tree.props) : tree.props?.children; return [tree, ...nodes(children)]; }
function content(tree) { if (Array.isArray(tree)) return tree.map(content).join(""); if (tree && typeof tree === "object") return content(typeof tree.type === "function" && tree.type.name === "FiscalBlockers" ? tree.type(tree.props) : tree.props?.children); return typeof tree === "string" || typeof tree === "number" ? String(tree) : ""; }
const flush = async () => { for (let i = 0; i < 150; i++) await Promise.resolve(); };
const issuer = { id: "issuer-a", user_id: "vet-a", display_name: "Dra. Uno", tax_id: "20123456786", legal_name: "Profesional Uno", cuit: "20123456786", tax_condition: "Monotributo", is_active: true, can_issue_service_receipt_c: true, can_issue_product_invoice_c: false, service_document_type: "receipt_c", service_document_code: "015" };
const series = { id: "series-a", fiscal_issuer_id: issuer.id, cuit_snapshot: issuer.cuit, environment: "homologation", point_of_sale: 7, document_type: "receipt_c", concept: 2, authorization_mode: "CAE", is_active: true, readiness: "ready", pending_reasons: [], credential_reference: "opaque://local-test", caea_reference: null, revision: 1, external_emission_available: false };
const payment = { payment_id: "payment-a", payment_method_id: "method-a", label: "Transferencia Uno", type: "bank_transfer", amount_ars: "10.10", status: "available", reason: null, suggested_fiscal_issuer_id: issuer.id };
const proposal = { id: "proposal-a", sale_id: "sale-a", fiscal_issuer_id: issuer.id, fiscal_series_id: series.id, status: "draft", payment_ids: [payment.payment_id], fiscal_description: "Consulta veterinaria", total_ars: "10.10", currency: "ARS", concept: 2, content_hash: "a".repeat(64), source_snapshot_hash: "b".repeat(64), snapshot: {}, blockers: [], is_stale: false, created_at: "2026-10-20T10:00:00Z", approved_at: null, allocations: [] };
const policy = { enabled: true, payment_scope: "electronic_only", accounting_reviewed_at: null, accounting_reviewed_by_user_id: null, accounting_review_note: null, revision: 1, production_blocked: true, external_emission_available: false, review_history: [] };

function setup(t, options = {}) {
  const oldFetch = global.fetch;
  const h = { values: [], pending: [], requests: [], sale: { id: "sale-a", status: "confirmed", currency: "ARS", total_ars: "10.10", fiscal_document: null, fiscal_status: "pending", items: [{ line_type: "service", fiscal_line_type: "service" }], ...options.sale },
    auth: options.auth ?? { currentUser: { id: "actor-a", is_active: true }, role: "clinic_admin" },
    review: structuredClone({ policy, eligibility: { eligible: true, blockers: [] }, payments: [payment], proposals: [], documents: [], totals: { active_payments_ars: "10.10", committed_ars: "0.00", proposed_ars: "0.00", excluded_ars: "0.00", pending_ars: "0.00", available_ars: "10.10" }, permissions: { can_generate: true, can_approve: true, can_manage_configuration: true, own_issuer_id: null }, external_emission_available: false, ...options.review }),
    configuration: structuredClone({ policy, issuers: [issuer], series: [series], payment_methods: [{ id: "method-a", label: "Transferencia Uno", type: "bank_transfer", operational_reference: "Cuenta operativa", suggested_fiscal_issuer_id: issuer.id }], permissions: { can_manage_configuration: true, can_review_proposals: true, can_approve_proposals: true, own_issuer_only: false }, ...options.configuration }),
  };
  setAuthTokenProvider(async () => "synthetic-test-token"); setActingTenantId(null);
  const response = (data, status = 200) => new Response(JSON.stringify(status === 200 ? { data, meta: {} } : { error: { message: data, code: "fiscal_conflict" } }), { status, headers: { "Content-Type": "application/json" } });
  global.fetch = async (url, init) => {
    const request = { url: new URL(url), init, body: init.body ? JSON.parse(init.body) : null }; h.requests.push(request);
    assert.equal(init.headers.get("Authorization"), "Bearer synthetic-test-token");
    assert.equal(init.headers.has("X-Tenant-Id"), false); assert.equal(init.headers.has("X-Acting-Tenant-Id"), false);
    if (options.respond) { const result = options.respond(request, h, response); if (result) return result; }
    if (init.method === "GET" && request.url.pathname === "/api/v1/fiscal-issuers") return response(h.configuration.issuers);
    if (init.method === "GET" && request.url.pathname === "/api/v1/clinic/team") return response(h.configuration.issuers.map(item => ({ id: item.user_id, is_active: true })));
    if (init.method === "GET") return response(request.url.pathname.endsWith("/fiscal-review") ? h.review : h.configuration);
    if (request.url.pathname.endsWith("/approve")) { h.review.proposals = h.review.proposals.map(p => p.id === proposal.id ? { ...p, status: "approved" } : p); h.review.totals.committed_ars = "10.10"; }
    if (request.url.pathname.endsWith("/cancel")) { h.review.proposals = h.review.proposals.map(p => ({ ...p, status: "cancelled", cancellation_reason: request.body.reason })); h.review.totals.committed_ars = "0.00"; }
    return response({});
  };
  h.render = () => { current = h; h.index = 0; h.tree = options.manual ? SaleFiscalDocumentPanel({ sale: h.sale, onUpdated: async () => {} }) : options.settings ? FiscalConfigurationScreen() : SaleFiscalReviewPanel({ sale: h.sale }); h.pending.splice(0).forEach(fn => fn()); return h.tree; };
  h.ready = async () => { h.render(); await flush(); h.render(); };
  h.find = predicate => { const value = nodes(h.tree).find(predicate); assert.ok(value, "Expected element"); return value; };
  h.button = label => h.find(n => n.type === "button" && content(n).trim() === label);
  h.click = label => { const button = h.button(label); assert.ok(!button.props.disabled, `Button disabled: ${label}`); const value = button.props.onClick(); h.render(); return value; };
  h.input = (id, value) => { h.find(n => n.props?.id === id).props.onChange({ target: { value } }); h.render(); };
  h.check = (text, checked = true) => { const label = h.find(n => n.type === "label" && content(n).includes(text)); const input = nodes(label).find(n => n.type === "input" && n.props.type === "checkbox"); assert.ok(input); assert.ok(!input.props.disabled); input.props.onChange({ target: { checked } }); h.render(); };
  h.submit = (label) => { const form = h.find(n => n.type === "form" && (!label || n.props["aria-label"] === label)); const value = form.props.onSubmit({ preventDefault() {} }); h.render(); return value; };
  h.writes = () => h.requests.filter(r => r.init.method !== "GET");
  t.after(() => { h.values.forEach(value => value?.cleanup?.()); global.fetch = oldFetch; setAuthTokenProvider(null); });
  return h;
}

test("whole-payment totals close at the cent without floating point or partial allocations", () => {
  const payments = [{ ...payment, amount_ars: "0.10" }, { ...payment, payment_id: "b", amount_ars: "0.20" }, { ...payment, payment_id: "c", amount_ars: "999999999999.99" }];
  assert.equal(selectedFiscalTotal(payments, [payment.payment_id, "b"]), "0.30");
  assert.equal(selectedFiscalTotal(payments, [payment.payment_id, "b", "c"]), "1000000000000.29");
  assert.equal(selectedFiscalTotal(payments, ["b", "b"]), "0.20");
  assert.throws(() => selectedFiscalTotal([{ ...payment, amount_ars: "0.001" }], [payment.payment_id]));
});

test("payment selection never makes reserved or policy-excluded funds available", () => {
  const payments = [payment, { ...payment, payment_id: "reserved", status: "committed" }, { ...payment, payment_id: "cash", type: "cash", status: "excluded" }];
  assert.deepEqual(selectableFiscalPayments(payments).map(p => p.payment_id), [payment.payment_id]);
  for (const status of ["available", "proposed", "committed", "excluded", "pending"]) assert.ok(fiscalPaymentStatusLabel(status));
});

test("sale review shows five outcomes, manual documents, and ARCA.2 boundary", async t => {
  const h = setup(t, { review: { payments: [payment, ...["proposed", "committed", "excluded", "pending"].map(status => ({ ...payment, payment_id: status, status }))], documents: [{ id: "manual-a", issuer_name_snapshot: "Profesional Uno", document_type: "receipt_c", document_number: "MAN-7", total_ars_snapshot: "10.10", source: "manual", authorization_status: "manual" }, { id: "manual-b", issuer_name_snapshot: "Profesional Dos", document_type: "invoice_c", document_number: "MAN-8", total_ars_snapshot: "5.00", source: "manual", authorization_status: "manual" }] } });
  await h.ready(); const text = content(h.tree);
  for (const status of ["Elegible", "Propuesto (sin reserva)", "Reservado", "Excluido por política", "Pendiente de resolver"]) assert.ok(text.includes(status));
  assert.match(text, /MAN-7/); assert.match(text, /MAN-8/); assert.match(text, /ARCA.2/); assert.match(text, /no se declara exento/); assert.equal(h.writes().length, 0);
});

test("generate requires explicit fiscal identity, description and intact payments", async t => {
  const h = setup(t); await h.ready(); h.click("Preparar propuesta revisable");
  assert.equal(h.find(n => n.props?.id === "proposal-series").props.value, "");
  h.submit("Revisar propuesta fiscal"); await flush(); h.render(); assert.equal(h.writes().length, 0);
  h.input("proposal-series", series.id); h.input("proposal-description", "Consulta fiscal confirmada"); h.check("Transferencia Uno · ARS 10.10");
  assert.match(content(h.tree), /Total de cobros seleccionados: ARS 10.10/);
  await h.submit("Revisar propuesta fiscal"); await flush(); h.render();
  assert.deepEqual(h.writes().map(r => [r.init.method, r.url.pathname, r.body]), [["POST", "/api/v1/sales/sale-a/fiscal-proposals", { fiscal_series_id: series.id, fiscal_description: "Consulta fiscal confirmada", payment_ids: [payment.payment_id] }]]);
  assert.match(content(h.tree), /Borrador guardado/);
});

test("secretary sees fiscal review and configuration without mutation controls", async t => {
  const h = setup(t, { review: { proposals: [proposal], permissions: { can_generate: false, can_approve: false, can_manage_configuration: false, own_issuer_id: null } } }); await h.ready();
  assert.match(content(h.tree), /Consulta fiscal/); assert.equal(nodes(h.tree).filter(n => n.type === "button").length, 0); assert.equal(h.writes().length, 0);
});

test("veterinarian can review only linked issuer and series", async t => {
  const h = setup(t, { review: { proposals: [proposal, { ...proposal, id: "other-proposal", fiscal_issuer_id: "issuer-b" }], permissions: { can_generate: true, can_approve: true, can_manage_configuration: false, own_issuer_id: issuer.id } }, configuration: { series: [series, { ...series, id: "series-b", fiscal_issuer_id: "issuer-b" }] } }); await h.ready();
  const other = h.find(n => n.props?.["aria-label"] === "Propuesta other-proposal"); assert.equal(nodes(other).some(n => n.type === "button"), false);
  h.click("Preparar propuesta revisable"); const select = h.find(n => n.props?.id === "proposal-series"); assert.deepEqual(nodes(select).filter(n => n.type === "option" && n.props.value).map(n => n.props.value), [series.id]);
});

test("stale and blocked drafts cannot approve and show recovery actions", async t => {
  for (const draft of [{ ...proposal, is_stale: true }, { ...proposal, blockers: [{ code: "mixed_attribution", message: "Atribución de conceptos pendiente" }] }]) {
    assert.equal(canApproveFiscalProposal({ permissions: { can_approve: true, can_generate: true, own_issuer_id: null } }, draft), false);
  }
  const h = setup(t, { review: { proposals: [{ ...proposal, is_stale: true, blockers: [{ code: "mixed_attribution", message: "Atribución de conceptos pendiente" }] }] } }); await h.ready();
  assert.equal(h.button("Aprobar y reservar cobros").props.disabled, true); assert.match(content(h.tree), /Propuesta obsoleta/); assert.match(content(h.tree), /no puede dividirse automáticamente/);
  h.click("Revisar o corregir"); assert.equal(h.find(n => n.props?.id === "proposal-series").props.value, series.id); assert.equal(h.find(n => n.props?.id === "proposal-description").props.value, proposal.fiscal_description);
});

test("approval confirms full identity and retries the same content with the same idempotency key", async t => {
  let fail = true;
  const h = setup(t, { review: { proposals: [proposal] }, respond(r, h, response) { if (r.url.pathname.endsWith("/approve") && fail) return response("Conflicto recuperable de reserva", 409); } }); await h.ready();
  assert.equal(h.button("Aprobar y reservar cobros").props.disabled, true); h.check("Confirmo emisor, CUIT");
  await h.click("Aprobar y reservar cobros"); await flush(); h.render(); assert.match(content(h.tree), /Conflicto recuperable/);
  fail = false; await h.click("Aprobar y reservar cobros"); await flush(); h.render();
  const requests = h.writes(); assert.equal(requests.length, 2); assert.equal(requests[0].init.headers.get("Idempotency-Key"), requests[1].init.headers.get("Idempotency-Key")); assert.ok(requests[0].init.headers.get("Idempotency-Key"));
  assert.deepEqual(requests[0].body, { content_hash: proposal.content_hash, confirm_fiscal_identity: true }); assert.match(content(h.tree), /No se emitió un comprobante ARCA/); assert.match(content(h.tree), /Aprobada · reserva activa/);
});

test("duplicate synchronous approval sends one write", async t => {
  let finish;
  const h = setup(t, { review: { proposals: [proposal] }, respond(r, h, response) { if (r.url.pathname.endsWith("/approve")) return new Promise(resolve => { finish = () => resolve(response({})); }); } }); await h.ready(); h.check("Confirmo emisor, CUIT");
  const approve = h.button("Aprobar y reservar cobros").props.onClick; approve(); approve(); await flush(); h.render(); assert.equal(h.writes().length, 1); finish(); await flush(); h.render();
});

test("approved cancellation needs an audited reason and refreshes reserves", async t => {
  const h = setup(t, { review: { proposals: [{ ...proposal, status: "approved" }], totals: { committed_ars: "10.10", available_ars: "0.00", proposed_ars: "0.00", excluded_ars: "0.00", pending_ars: "0.00" } } }); await h.ready();
  assert.match(content(h.tree), /Antes de anular un cobro reservado/); h.click("Cancelar propuesta y liberar reserva"); assert.equal(h.button("Confirmar cancelación").props.disabled, true);
  const form = h.find(n => n.props?.["aria-label"] === "Cancelar propuesta fiscal"); nodes(form).find(n => n.type === "textarea").props.onChange({ target: { value: "  Revisión contable solicitada  " } }); h.render(); await h.submit("Cancelar propuesta fiscal"); await flush(); h.render();
  assert.deepEqual(h.writes()[0].body, { reason: "Revisión contable solicitada" }); assert.match(content(h.tree), /reservas se liberaron/); assert.equal(h.review.totals.committed_ars, "0.00");
});

test("future unknown and CAEA states cannot be cancelled or presented as drafts", async t => {
  const h = setup(t, { review: { proposals: [{ ...proposal, status: "unknown" }, { ...proposal, id: "contingency", status: "caea_pending" }] } }); await h.ready();
  assert.match(content(h.tree), /Resultado desconocido/); assert.match(content(h.tree), /Contingencia CAEA pendiente/); assert.equal(nodes(h.tree).filter(n => n.type === "button" && /Cancelar propuesta|Aprobar y reservar/.test(content(n))).length, 0); assert.notEqual(fiscalProposalStatusLabel("sent"), fiscalProposalStatusLabel("draft"));
});

for (const status of ["authorized", "unknown"]) test(`${status} reservations direct the user to reconciliation without promising cancellation`, async t => {
  const h = setup(t, { review: { proposals: [{ ...proposal, status }], payments: [{ ...payment, status: "committed", reason: "Cancela la propuesta no enviada para liberar el cobro" }], totals: { committed_ars: "10.10" } } }); await h.ready();
  const text = content(h.tree);
  assert.match(text, /Consulta la propuesta o el comprobante antes de modificar este cobro/);
  assert.match(text, /conservan sus reservas; consulta o reconcilia la operación existente/);
  assert.match(text, /comprobantes manuales requieren revisión contable/);
  assert.doesNotMatch(text, /[Cc]ancela la propuesta|cancela explícitamente/);
  assert.equal(nodes(h.tree).filter(n => n.type === "button" && /Cancelar propuesta/.test(content(n))).length, 0);
});

test("currency and historical manual-document blockers explain the permitted action", async t => {
  const h = setup(t, { review: { eligibility: { eligible: false, blockers: [{ code: "currency_not_ars", message: "Venta USD incompatible" }, { code: "manual_document_unallocated", message: "Comprobante manual sin imputación" }] } } }); await h.ready();
  assert.equal(h.button("Preparar propuesta revisable").props.disabled, true); assert.match(content(h.tree), /no se convierten importes/); assert.match(content(h.tree), /Regulariza la imputación/); assert.equal(h.writes().length, 0);
});

test("configuration is read-only when server denies configuration permission", async t => {
  const h = setup(t, { settings: true, configuration: { permissions: { can_manage_configuration: false } } }); await h.ready(); assert.match(content(h.tree), /Consulta de configuración/);
  assert.equal(nodes(h.tree).filter(n => n.type === "button").length, 0); assert.equal(h.find(n => n.type === "fieldset").props.disabled, true);
});

test("policy and accounting review save without client-selected actor or tenant", async t => {
  const h = setup(t, { settings: true }); await h.ready(); h.input("fiscal-payment-scope", "all_payments"); h.input("fiscal-accounting-note", "  Revisión de todos los cobros  "); h.submit(); await flush(); h.render();
  const request = h.writes()[0]; assert.equal(request.url.pathname, "/api/v1/fiscal/configuration/policy"); assert.deepEqual(request.body, { enabled: true, payment_scope: "all_payments", accounting_review_note: "Revisión de todos los cobros" });
  assert.match(content(h.tree), /producción permanece bloqueada/); assert.match(content(h.tree), /ARCA.2/);
});

test("new series starts in homologation without inventing POS or accepting secret uploads", async t => {
  const h = setup(t, { settings: true }); await h.ready(); h.click("Nueva serie");
  const form = h.find(n => n.type === "form" && content(n).includes("Referencia opaca de credencial"));
  const environment = nodes(form).find(n => n.type === "select" && nodes(n).some(o => o.props?.value === "homologation")); assert.equal(environment.props.value, "homologation");
  const pos = nodes(form).find(n => n.type === "input" && n.props.type === "number"); assert.equal(pos.props.value, "");
  assert.equal(nodes(form).some(n => n.props.type === "password" || n.props.type === "file"), false); const references = nodes(form).filter(n => n.props.placeholder === "opaque://identificador"); assert.equal(references.length, 2); assert.ok(references.every(n => n.props.pattern.startsWith("opaque://")));
});

test("review error preserves selected series, description and payment ids for correction", async t => {
  const h = setup(t, { respond(r, h, response) { if (r.init.method === "POST") return response("Revisa la atribución del emisor", 422); } }); await h.ready(); h.click("Preparar propuesta revisable"); h.input("proposal-series", series.id); h.input("proposal-description", "Consulta revisable"); h.check("Transferencia Uno · ARS 10.10"); await h.submit("Revisar propuesta fiscal"); await flush(); h.render();
  assert.match(content(h.tree), /Revisa la atribución del emisor/); assert.equal(h.find(n => n.props?.id === "proposal-series").props.value, series.id); assert.equal(h.find(n => n.props?.id === "proposal-description").props.value, "Consulta revisable"); assert.match(content(h.tree), /Total de cobros seleccionados: ARS 10.10/);
});

test("approved proposal displays its frozen fiscal identity and original payment amounts", async t => {
  const h = setup(t, { review: { payments: [{ ...payment, amount_ars: "90.00" }], proposals: [{ ...proposal, status: "approved", snapshot: { issuer: { legal_name: "Identidad aprobada original", cuit: "20123456786", tax_condition: "Monotributo original" }, series: { environment: "homologation", point_of_sale: 9, document_type: "receipt_c", concept: 2 }, payments: [{ id: payment.payment_id, amount_ars: "10.10" }] } }] }, configuration: { issuers: [{ ...issuer, legal_name: "Nombre posterior" }], series: [{ ...series, point_of_sale: 31 }] } });
  await h.ready(); const card = h.find(n => n.props?.["aria-label"] === "Propuesta proposal-a"); const text = content(card);
  assert.match(text, /Identidad aprobada original/); assert.match(text, /PV 9/); assert.doesNotMatch(text, /PV 31|Nombre posterior|90.00/); assert.match(text, /10.10/);
});

test("manual regularization confirms exact whole payments including cash and uses idempotency", async t => {
  const document = { id: "manual-a", fiscal_issuer_id: issuer.id, is_active: true, source: "manual", authorization_status: "manual", issuer_name_snapshot: "Profesional Uno", issuer_tax_id_snapshot: issuer.cuit, document_type: "receipt_c", document_number: "HIST-1", total_ars_snapshot: "15.10" };
  const cash = { ...payment, payment_id: "cash-payment", label: "Efectivo histórico", type: "cash", status: "excluded", amount_ars: "5.00" };
  const h = setup(t, { review: { documents: [document], payments: [payment, cash], eligibility: { eligible: true, blockers: [{ code: "fiscal_manual_allocation_unknown", message: "Comprobante manual sin imputación" }] } } });
  await h.ready(); h.click("Regularizar imputación manual"); assert.equal(h.button("Confirmar imputación manual").props.disabled, true);
  h.check("Transferencia Uno · ARS 10.10"); h.check("Confirmo la identidad fiscal y que este comprobante"); assert.equal(h.button("Confirmar imputación manual").props.disabled, true); h.check("Efectivo histórico · ARS 5.00"); assert.equal(h.button("Confirmar imputación manual").props.disabled, false);
  h.submit("Regularizar comprobante manual"); await flush(); h.render(); const request = h.writes()[0]; assert.equal(request.url.pathname, "/api/v1/sales/sale-a/fiscal-documents/manual-a/allocate"); assert.deepEqual(request.body, { payment_ids: [payment.payment_id, cash.payment_id], confirm_fiscal_identity: true }); assert.ok(request.init.headers.get("Idempotency-Key")); assert.match(content(h.tree), /regularizada y auditada/);
});

test("manual regularization stays unavailable for a veterinarian linked to another issuer", async t => {
  const h = setup(t, { review: { permissions: { can_generate: true, can_approve: true, own_issuer_id: issuer.id }, documents: [{ id: "manual-other", fiscal_issuer_id: "other-issuer", source: "manual", is_active: true }], eligibility: { eligible: true, blockers: [{ code: "fiscal_manual_allocation_unknown", message: "Imputación pendiente" }] } } }); await h.ready();
  assert.equal(nodes(h.tree).some(n => n.type === "button" && content(n) === "Regularizar imputación manual"), false);
});

test("method mapping saves only the operational reference and explicit issuer suggestion", async t => {
  const h = setup(t, { settings: true }); await h.ready(); h.click("Revisar atribución");
  const form = h.find(n => n.type === "form" && content(n).includes("Cuenta o referencia operativa no secreta"));
  nodes(form).find(n => n.type === "input").props.onChange({ target: { value: "  Cuenta consultorio  " } }); h.render();
  const refreshed = h.find(n => n.type === "form" && content(n).includes("Cuenta o referencia operativa no secreta"));
  nodes(refreshed).find(n => n.type === "select").props.onChange({ target: { value: issuer.id } }); h.render();
  h.find(n => n.type === "form" && content(n).includes("Cuenta o referencia operativa no secreta")).props.onSubmit({ preventDefault() {} }); await flush(); h.render();
  assert.equal(h.writes()[0].url.pathname, "/api/v1/payment-methods/method-a"); assert.deepEqual(h.writes()[0].body, { operational_reference: "Cuenta consultorio", suggested_fiscal_issuer_id: issuer.id }); assert.match(content(h.tree), /propuestas futuras/);
});

const manualDocument = { id: "manual-permissions", source: "manual", authorization_status: "manual", fiscal_issuer_id: issuer.id, issuer_user_id_snapshot: issuer.user_id, issuer_name_snapshot: "Profesional Uno", issuer_tax_id_snapshot: issuer.cuit, document_type: "receipt_c", document_code: "015", document_number: "HIST-777", issue_date: "2026-10-20", total_ars_snapshot: "10.10", original_filename: "historico.pdf", content_type: "application/pdf", size_bytes: 100, uploaded_at: "2026-10-20T10:00:00Z", file_history: [{ id: "history-one", original_filename: "version-previa.pdf", uploaded_at: "2026-10-19T10:00:00Z", replaced_at: "2026-10-20T10:00:00Z" }] };

test("secretary preserves singular manual document, file history, view and download without mutations", async t => {
  const h = setup(t, { manual: true, sale: { fiscal_document: manualDocument }, auth: { role: "secretaria", currentUser: { id: "secretary-a", is_active: true } } }); await h.ready();
  assert.match(content(h.tree), /HIST-777/); assert.match(content(h.tree), /version-previa.pdf/); h.button("Ver"); h.button("Descargar");
  assert.equal(nodes(h.tree).some(n => n.type === "button" && /Corregir|Registrar/.test(content(n))), false); assert.equal(nodes(h.tree).some(n => n.type === "form"), false); assert.equal(h.writes().length, 0);
});

for (const [name, auth] of [
  ["secretary", { role: "secretaria", currentUser: { id: "secretary-a", is_active: true } }],
  ["missing actor", { role: "clinic_admin", currentUser: null }],
  ["inactive actor", { role: "clinic_admin", currentUser: { id: "inactive-a", is_active: false } }],
  ["superadmin without fiscal exception", { role: "superadmin", currentUser: { id: "super-a", is_active: true } }],
]) test(`${name} cannot add a manual document from the historical panel`, async t => {
  const h = setup(t, { manual: true, auth }); await h.ready(); assert.equal(nodes(h.tree).some(n => n.type === "button" && /Registrar comprobante/.test(content(n))), false); assert.match(content(h.tree), /Consulta fiscal/); assert.equal(h.writes().length, 0);
});

test("veterinarian manual form contains only the linked current issuer", async t => {
  const h = setup(t, { manual: true, sale: { fiscal_document: manualDocument }, auth: { role: "medico_veterinario", currentUser: { id: issuer.user_id, is_active: true } }, configuration: { issuers: [issuer, { ...issuer, id: "issuer-b", user_id: "vet-b", display_name: "Otro emisor" }] } }); await h.ready();
  h.click("Corregir o reemplazar"); const select = h.find(n => n.type === "select"); assert.deepEqual(nodes(select).filter(n => n.type === "option" && n.props.value).map(n => n.props.value), [issuer.id]);
});

test("veterinarian cannot replace a manual document whose issuer was linked to someone else", async t => {
  const h = setup(t, { manual: true, sale: { fiscal_document: manualDocument }, auth: { role: "medico_veterinario", currentUser: { id: issuer.user_id, is_active: true } }, configuration: { issuers: [{ ...issuer, user_id: "replacement-vet" }] } }); await h.ready();
  h.button("Ver"); h.button("Descargar"); assert.equal(nodes(h.tree).some(n => n.type === "button" && content(n).includes("Corregir o reemplazar")), false);
});

test("ARCA document totals and plural documents distinguish homologation without claiming fiscal coverage", async t => {
  const homol = { ...manualDocument, id: "homol-a", source: "arca", environment: "homologation", authorization_status: "authorized", is_active: true };
  const h = setup(t, { review: { documents: [homol, { ...manualDocument, environment: null }] }, sale: { fiscal_document_totals: [
    { source: "arca", authorization_status: "authorized", environment: "homologation", count: 1, total_ars: "10.10" },
    { source: "arca", authorization_status: "authorized", environment: "production", count: 2, total_ars: "20.20" },
    { source: "manual", authorization_status: "manual", environment: null, count: 1, total_ars: "5.00" },
  ] } }); await h.ready();
  const totals = h.find(n => n.props?.["aria-label"] === "Totales de comprobantes activos");
  assert.match(content(totals), /Homologación · sin validez fiscal · Autorizado · 1 comprobante/);
  assert.match(content(totals), /ARCA · Producción · Autorizado · 2 comprobante/);
  assert.match(content(totals), /Registro manual · Adjunto manual/);
  const rows = nodes(totals).filter(n => n.type === "div" && n.key);
  assert.deepEqual(rows.map(n => n.key), ["arca:authorized:homologation", "arca:authorized:production", "manual:manual:none"]);
  const documents = h.find(n => n.type === "details" && content(n).includes("Comprobantes registrados"));
  assert.match(content(documents), /ARCA · Homologación · sin validez fiscal/);
  assert.doesNotMatch(content(documents), /cobertura fiscal|Documentada/);
});
